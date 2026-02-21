import logging
from datetime import datetime

import caldav
from icalendar import Calendar, Todo

from database import (
    get_all_settings, get_sync_map, get_sync_entry,
    get_sync_entry_by_uid, upsert_sync_entry
)
from grocy_client import GrocyClient

logger = logging.getLogger(__name__)

UID_TASK_PREFIX = 'grocy-task-'
UID_CHORE_PREFIX = 'grocy-chore-'
UID_DOMAIN = '@grocylink'


class CalDAVSync:
    def __init__(self):
        self.settings = get_all_settings()
        self.client = None
        self.calendar = None
        self.grocy = None

    def _build_url(self, url=None):
        url = url or self.settings.get('caldav_url', '')
        path = self.settings.get('caldav_path', '')
        if path:
            url = url.rstrip('/') + '/' + path.lstrip('/')
        return url

    def _create_client(self, url=None, username=None, password=None):
        full_url = self._build_url(url)
        username = username or self.settings.get('caldav_username', '')
        password = password or self.settings.get('caldav_password', '')
        verify_ssl = self.settings.get('caldav_verify_ssl', '1') != '0'
        return caldav.DAVClient(url=full_url, username=username, password=password,
                                ssl_verify_cert=verify_ssl)

    def connect(self):
        url = self.settings.get('caldav_url', '')
        username = self.settings.get('caldav_username', '')
        password = self.settings.get('caldav_password', '')
        calendar_name = self.settings.get('caldav_calendar', '')

        if not url or not username or not password:
            raise ConnectionError("CalDAV-Verbindungsdaten nicht vollständig konfiguriert")

        self.client = self._create_client()
        principal = self.client.principal()
        calendars = principal.calendars()

        if not calendars:
            raise ConnectionError("Keine Kalender auf dem CalDAV-Server gefunden")

        if calendar_name:
            for cal in calendars:
                if cal.name == calendar_name:
                    self.calendar = cal
                    break
            if not self.calendar:
                raise ConnectionError(f"Kalender '{calendar_name}' nicht gefunden")
        else:
            self.calendar = calendars[0]

        self.grocy = GrocyClient()
        return True

    def test_connection(self):
        try:
            url = self.settings.get('caldav_url', '')
            username = self.settings.get('caldav_username', '')
            password = self.settings.get('caldav_password', '')

            if not url or not username or not password:
                return False, "CalDAV-Verbindungsdaten nicht vollständig"

            client = self._create_client(url, username, password)
            principal = client.principal()
            calendars = principal.calendars()
            cal_names = [c.name for c in calendars]
            return True, f"Verbunden. Kalender: {', '.join(cal_names)}"
        except AttributeError as e:
            if "'NoneType' object has no attribute 'tag'" in str(e):
                hint = (
                    "Der Server hat keine gueltige WebDAV-Antwort geliefert. "
                    "Bitte pruefen Sie die URL - fuer Nextcloud/ownCloud muss der "
                    "vollstaendige DAV-Pfad angegeben werden, z.B.: "
                    "https://cloud.example.com/remote.php/dav"
                )
                return False, hint
            return False, str(e)
        except Exception as e:
            return False, str(e)

    def get_calendars(self):
        url = self.settings.get('caldav_url', '')
        username = self.settings.get('caldav_username', '')
        password = self.settings.get('caldav_password', '')

        if not url or not username or not password:
            return []

        client = self._create_client(url, username, password)
        principal = client.principal()
        return [c.name for c in principal.calendars()]

    def sync_all(self):
        self.connect()
        stats = {'tasks_synced': 0, 'chores_synced': 0, 'caldav_to_grocy': 0, 'errors': []}

        try:
            self._sync_caldav_to_grocy(stats)
        except Exception as e:
            logger.error(f"Fehler bei CalDAV->Grocy Sync: {e}")
            stats['errors'].append(f"CalDAV->Grocy: {e}")

        try:
            self._sync_tasks_to_caldav(stats)
        except Exception as e:
            logger.error(f"Fehler bei Task-Sync zu CalDAV: {e}")
            stats['errors'].append(f"Tasks->CalDAV: {e}")

        try:
            self._sync_chores_to_caldav(stats)
        except Exception as e:
            logger.error(f"Fehler bei Chore-Sync zu CalDAV: {e}")
            stats['errors'].append(f"Chores->CalDAV: {e}")

        return stats

    def _task_to_vtodo(self, task, uid=None):
        cal = Calendar()
        cal.add('prodid', '-//Grocylink//CalDAV Sync//DE')
        cal.add('version', '2.0')

        todo = Todo()
        if uid is None:
            uid = f"{UID_TASK_PREFIX}{task['id']}{UID_DOMAIN}"
        todo.add('uid', uid)
        todo.add('summary', task.get('name', f"Task #{task['id']}"))

        if task.get('description'):
            todo.add('description', task['description'])

        if task.get('due_date'):
            try:
                due = datetime.strptime(task['due_date'], '%Y-%m-%d %H:%M:%S')
                todo.add('due', due)
            except (ValueError, TypeError):
                try:
                    due = datetime.strptime(task['due_date'], '%Y-%m-%d')
                    todo.add('due', due)
                except (ValueError, TypeError):
                    pass

        if task.get('done') and str(task['done']) == '1':
            todo.add('status', 'COMPLETED')
            todo.add('percent-complete', 100)
        else:
            todo.add('status', 'NEEDS-ACTION')

        todo.add('dtstamp', datetime.utcnow())
        todo.add('last-modified', datetime.utcnow())

        cal.add_component(todo)
        return cal.to_ical().decode('utf-8')

    def _chore_to_vtodo(self, chore):
        cal = Calendar()
        cal.add('prodid', '-//Grocylink//CalDAV Sync//DE')
        cal.add('version', '2.0')

        todo = Todo()
        chore_id = chore.get('chore_id', chore.get('id'))
        uid = f"{UID_CHORE_PREFIX}{chore_id}{UID_DOMAIN}"
        todo.add('uid', uid)
        todo.add('summary', chore.get('chore_name', chore.get('name', f"Chore #{chore_id}")))

        if chore.get('description'):
            todo.add('description', chore['description'])

        next_exec = chore.get('next_estimated_execution_time')
        if next_exec and next_exec != '2999-12-31 23:59:59':
            try:
                due = datetime.strptime(next_exec, '%Y-%m-%d %H:%M:%S')
                todo.add('due', due)
            except (ValueError, TypeError):
                pass

        todo.add('status', 'NEEDS-ACTION')
        todo.add('dtstamp', datetime.utcnow())
        todo.add('last-modified', datetime.utcnow())

        cal.add_component(todo)
        return cal.to_ical().decode('utf-8')

    def _due_str(self, vtodo_component):
        """Extrahiert das Faelligkeitsdatum als YYYY-MM-DD aus einem VTODO-Component."""
        due = vtodo_component.get('due')
        if not due:
            return ''
        dt = due.dt
        if hasattr(dt, 'strftime'):
            date_str = dt.strftime('%Y-%m-%d')
            return '' if date_str.startswith('2999') else date_str
        return ''

    def _find_vtodo_by_uid(self, uid):
        try:
            # include_completed=True ist noetig, da manche Server (z.B. PrivateEmail/Dovecot)
            # abgeschlossene Todos aus normalen Suchergebnissen ausschliessen
            results = self.calendar.todos(include_completed=True)
            for item in results:
                try:
                    ical = Calendar.from_ical(item.data)
                    for component in ical.walk():
                        if component.name == 'VTODO':
                            item_uid = str(component.get('uid', ''))
                            if item_uid == uid:
                                return item, component
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Fehler bei VTODO-Suche fuer {uid}: {e}")
        return None, None

    def _sync_tasks_to_caldav(self, stats):
        all_tasks = self.grocy.get_all_tasks_including_done()
        logger.info(f"Synchronisiere {len(all_tasks)} Tasks zu CalDAV")

        for task in all_tasks:
            try:
                task_id = task['id']
                # UID aus Sync-Map lesen: CalDAV-importierte Tasks behalten ihre Original-UID,
                # Grocy-native Tasks bekommen die berechnete Grocylink-UID
                sync_entry = get_sync_entry('task', task_id)
                uid = sync_entry['caldav_uid'] if sync_entry else f"{UID_TASK_PREFIX}{task_id}{UID_DOMAIN}"
                is_done = str(task.get('done', '0')) == '1'
                status = 'COMPLETED' if is_done else 'NEEDS-ACTION'
                summary = task.get('name', '')
                due = task.get('due_date', '')

                existing_item, existing_vtodo = self._find_vtodo_by_uid(uid)

                if existing_item:
                    existing_status = str(existing_vtodo.get('status', 'NEEDS-ACTION'))
                    existing_summary = str(existing_vtodo.get('summary', ''))
                    existing_desc = str(existing_vtodo.get('description', '') or '')
                    grocy_desc = task.get('description', '') or ''
                    needs_update = (
                        existing_status != status or
                        existing_summary != summary or
                        existing_desc != grocy_desc
                    )
                    if needs_update:
                        vtodo_data = self._task_to_vtodo(task, uid=uid)
                        existing_item.data = vtodo_data
                        existing_item.save()
                        logger.debug(f"Task {task_id} aktualisiert auf CalDAV")
                else:
                    vtodo_data = self._task_to_vtodo(task, uid=uid)
                    self.calendar.save_todo(vtodo_data)
                    logger.debug(f"Task {task_id} neu auf CalDAV angelegt")

                upsert_sync_entry('task', task_id, uid, status, summary, due, direction='grocy→caldav')
                stats['tasks_synced'] += 1
            except Exception as e:
                logger.error(f"Fehler bei Task {task.get('id')}: {e}")
                stats['errors'].append(f"Task {task.get('id')}: {e}")

    def _sync_chores_to_caldav(self, stats):
        chores = self.grocy.get_chores()
        logger.info(f"Synchronisiere {len(chores)} Chores zu CalDAV")

        for chore in chores:
            try:
                chore_id = chore.get('chore_id', chore.get('id'))
                uid = f"{UID_CHORE_PREFIX}{chore_id}{UID_DOMAIN}"
                summary = chore.get('chore_name', chore.get('name', ''))
                next_exec = chore.get('next_estimated_execution_time', '')

                existing_item, existing_vtodo = self._find_vtodo_by_uid(uid)

                if existing_item:
                    existing_summary = str(existing_vtodo.get('summary', ''))
                    existing_due = self._due_str(existing_vtodo)
                    next_exec_date = str(next_exec)[:10] if next_exec and not str(next_exec).startswith('2999') else ''
                    needs_update = (existing_summary != summary or existing_due != next_exec_date)
                    if needs_update:
                        vtodo_data = self._chore_to_vtodo(chore)
                        existing_item.data = vtodo_data
                        existing_item.save()
                        logger.debug(f"Chore {chore_id} aktualisiert auf CalDAV (summary={summary!r}, due={next_exec_date!r})")
                else:
                    vtodo_data = self._chore_to_vtodo(chore)
                    self.calendar.save_todo(vtodo_data)
                    logger.debug(f"Chore {chore_id} neu auf CalDAV angelegt")

                upsert_sync_entry('chore', chore_id, uid, 'NEEDS-ACTION', summary, next_exec, direction='grocy→caldav')
                stats['chores_synced'] += 1
            except Exception as e:
                logger.error(f"Fehler bei Chore {chore.get('chore_id', chore.get('id'))}: {e}")
                stats['errors'].append(f"Chore {chore.get('chore_id')}: {e}")

    def _sync_caldav_to_grocy(self, stats):
        try:
            # include_completed=True ist noetig, damit abgeschlossene Todos erkannt werden
            # (manche Server wie PrivateEmail/Dovecot schliessen COMPLETED aus normalen Suchen aus)
            results = self.calendar.todos(include_completed=True)
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der VTODOs: {e}")
            return

        all_tasks = {t['id']: t for t in self.grocy.get_all_tasks_including_done()}

        for item in results:
            try:
                ical = Calendar.from_ical(item.data)
                for component in ical.walk():
                    if component.name != 'VTODO':
                        continue

                    uid = str(component.get('uid', ''))
                    caldav_status = str(component.get('status', 'NEEDS-ACTION'))

                    if uid.startswith(UID_TASK_PREFIX) and uid.endswith(UID_DOMAIN):
                        task_id_str = uid[len(UID_TASK_PREFIX):-len(UID_DOMAIN)]
                        try:
                            task_id = int(task_id_str)
                        except ValueError:
                            continue

                        task = all_tasks.get(task_id)
                        if not task:
                            continue

                        grocy_done = str(task.get('done', '0')) == '1'
                        changed = False

                        # Sync status
                        if caldav_status == 'COMPLETED' and not grocy_done:
                            self.grocy.complete_task(task_id)
                            logger.info(f"Task {task_id} in Grocy als erledigt markiert (CalDAV->Grocy)")
                            changed = True
                        elif caldav_status == 'NEEDS-ACTION' and grocy_done:
                            self.grocy.undo_task(task_id)
                            logger.info(f"Task {task_id} in Grocy als unerledigt markiert (CalDAV->Grocy)")
                            changed = True

                        # Sync due date
                        caldav_due = component.get('due')
                        if caldav_due:
                            caldav_due_str = caldav_due.dt.strftime('%Y-%m-%d %H:%M:%S') if hasattr(caldav_due.dt, 'hour') else caldav_due.dt.strftime('%Y-%m-%d') + ' 00:00:00'
                            grocy_due = task.get('due_date', '') or ''
                            if caldav_due_str != grocy_due:
                                self.grocy.update_task(task_id, {'due_date': caldav_due_str})
                                logger.info(f"Task {task_id} Datum aktualisiert: {grocy_due} -> {caldav_due_str} (CalDAV->Grocy)")
                                changed = True

                        # Sync summary/name
                        caldav_summary = str(component.get('summary', ''))
                        grocy_name = task.get('name', '')
                        if caldav_summary and caldav_summary != grocy_name:
                            self.grocy.update_task(task_id, {'name': caldav_summary})
                            logger.info(f"Task {task_id} Name aktualisiert: '{grocy_name}' -> '{caldav_summary}' (CalDAV->Grocy)")
                            changed = True

                        # Sync description
                        caldav_desc = str(component.get('description', '') or '')
                        grocy_desc = task.get('description', '') or ''
                        if caldav_desc != grocy_desc:
                            self.grocy.update_task(task_id, {'description': caldav_desc})
                            logger.info(f"Task {task_id} Beschreibung aktualisiert (CalDAV->Grocy)")
                            changed = True

                        if changed:
                            new_due = caldav_due.dt.strftime('%Y-%m-%d') if caldav_due else task.get('due_date', '')
                            upsert_sync_entry('task', task_id, uid, caldav_status,
                                              caldav_summary or task.get('name', ''), new_due,
                                              direction='caldav→grocy')
                            stats['caldav_to_grocy'] += 1

                    elif uid.startswith(UID_CHORE_PREFIX) and uid.endswith(UID_DOMAIN):
                        chore_id_str = uid[len(UID_CHORE_PREFIX):-len(UID_DOMAIN)]
                        try:
                            chore_id = int(chore_id_str)
                        except ValueError:
                            continue

                        if caldav_status == 'COMPLETED':
                            sync_entry = get_sync_entry('chore', chore_id)
                            if sync_entry and sync_entry['last_status'] != 'COMPLETED':
                                self.grocy.execute_chore(chore_id)
                                logger.info(f"Chore {chore_id} in Grocy ausgefuehrt (CalDAV->Grocy)")
                                upsert_sync_entry('chore', chore_id, uid, 'COMPLETED', direction='caldav→grocy')
                                stats['caldav_to_grocy'] += 1

                    else:
                        # Neue Aufgabe aus CalDAV -> Grocy erstellen
                        # Nur VTODOs verarbeiten, die nicht von Grocylink stammen
                        if uid.endswith(UID_DOMAIN):
                            continue

                        # Pruefen ob diese UID bereits synchronisiert wurde
                        existing = get_sync_entry_by_uid(uid)
                        if existing:
                            continue

                        caldav_summary = str(component.get('summary', ''))
                        if not caldav_summary:
                            continue

                        task_data = {'name': caldav_summary}

                        caldav_desc = str(component.get('description', '') or '')
                        if caldav_desc:
                            task_data['description'] = caldav_desc

                        caldav_due = component.get('due')
                        if caldav_due:
                            due_str = caldav_due.dt.strftime('%Y-%m-%d %H:%M:%S') if hasattr(caldav_due.dt, 'hour') else caldav_due.dt.strftime('%Y-%m-%d') + ' 00:00:00'
                            task_data['due_date'] = due_str

                        # Zusaetzliche Duplikat-Pruefung: Existiert bereits ein Task mit gleichem Namen in Grocy?
                        duplicate = any(
                            t.get('name', '').strip().lower() == caldav_summary.strip().lower()
                            for t in all_tasks.values()
                        )
                        if duplicate:
                            # Original-UID merken, damit sie nicht erneut verarbeitet wird
                            upsert_sync_entry('task', 0, uid,
                                              caldav_status, caldav_summary,
                                              task_data.get('due_date', ''),
                                              direction='caldav→grocy (duplikat)')
                            logger.info(f"Duplikat erkannt: '{caldav_summary}' existiert bereits in Grocy, uebersprungen")
                            continue

                        result = self.grocy.create_task(task_data)
                        new_task_id = result.get('created_object_id')
                        if new_task_id:
                            # Original CalDAV-UID in Sync-Map speichern.
                            # Kein UID-Update in CalDAV noetig: _sync_tasks_to_caldav liest
                            # die gespeicherte UID aus der Sync-Map und findet das VTODO direkt.
                            upsert_sync_entry('task', new_task_id, uid,
                                              caldav_status, caldav_summary,
                                              task_data.get('due_date', ''),
                                              direction='caldav→grocy')

                            if caldav_status == 'COMPLETED':
                                self.grocy.complete_task(new_task_id)

                            logger.info(f"Neue Aufgabe '{caldav_summary}' aus CalDAV in Grocy erstellt (ID: {new_task_id})")
                            stats['caldav_to_grocy'] += 1

            except Exception as e:
                logger.error(f"Fehler bei CalDAV->Grocy Sync: {e}")
                stats['errors'].append(f"CalDAV->Grocy: {e}")


def run_caldav_sync():
    settings = get_all_settings()
    if settings.get('caldav_sync_enabled', '0') != '1':
        return None
    try:
        sync = CalDAVSync()
        stats = sync.sync_all()
        logger.info(f"CalDAV Sync abgeschlossen: {stats}")
        return stats
    except Exception as e:
        logger.error(f"CalDAV Sync Fehler: {e}")
        return {'error': str(e)}
