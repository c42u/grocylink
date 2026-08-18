"""
Grocylink – Sprache serverseitig
================================================================================
Bis 1.6.0 war die Sprachwahl eine Sache des Browsers: `static/i18n.js` uebersetzt
die Oberflaeche anhand von `localStorage`. Alles, was der **Server** formuliert,
blieb deutsch -- die Antwort auf "Jetzt pruefen", die Testnachricht an einen
Kanal, die Eintraege im Log. Gemeldet als Fehler #1 auf GitHub:

    "The test message sent to Discord appears in German. The 'check completed'
     toast appears in German." (Some-Random-Person, 15.06.2026)

Dieses Modul ist die eine Stelle, an der serverseitige Texte stehen. Die Sprache
kommt aus den Einstellungen (`settings.language`), nicht aus dem Browser: Eine
Testnachricht an Discord entsteht ohne Browser, und der Warnungsversand aus dem
Zeitplan erst recht.

    from sprache import t, sprache_lesen
    t('msg.check_done')                 # in der eingestellten Sprache
    t('log.test_sent', lang='en')       # ausdruecklich englisch
    t('warn.title', count=3)            # mit Platzhaltern

**Nicht** uebersetzt wird das Anwendungsprotokoll (`logger.…`). Das ist
Betriebsdiagnostik; beim Suchen nach einer Meldung hilft eine feste Sprache mehr
als eine wechselnde. Die Eintraege im Log **der Oberflaeche** dagegen sind
Nutzertext -- die stehen hier.

Autor:    c42u
Co-Autor: ClaudeCode
Lizenz:   GPLv3
"""

from __future__ import annotations

VORGABE = 'de'

TEXTE = {
    'de': {
        # -- Warnungsversand (bis 1.6.0 in scheduler.TRANSLATIONS) ----------
        'expiry_date': 'Ablaufdatum (MHD)',
        'use_by_date': 'Verbrauchsdatum',
        'expired_since': 'Abgelaufen seit (MHD)',
        'use_by_since': 'Verbrauchsdatum überschritten seit',
        'missing_amount': 'Fehlmenge',
        'unknown': 'Unbekannt',
        'product_nr': 'Produkt',
        'type_expiring': 'Bald ablaufend',
        'type_expired': 'Abgelaufen',
        'type_missing': 'Mindestbestand unterschritten',
        'title': 'Grocy Warnung: {count} Produkt(e) erfordern Aufmerksamkeit',

        # -- Antworten der Schnittstelle ------------------------------------
        'msg.check_done': 'Check durchgeführt!',
        'msg.test_sent': 'Testnachricht gesendet!',
        'msg.sync_done': 'Synchronisation abgeschlossen!',
        'msg.channel_missing': 'Kanal nicht gefunden',
        'msg.grocy_missing': 'Grocy nicht konfiguriert',
        'msg.receipt_missing': 'Kassenbon nicht gefunden',
        'msg.no_file': 'Keine Datei hochgeladen',
        'msg.pdf_only': 'Nur PDF-Dateien erlaubt',
        'msg.need_list_uuid': 'list_uuid erforderlich',
        'msg.need_item': 'list_uuid + item_uuid erforderlich',
        'msg.need_name': 'name erforderlich',
        'msg.need_product': 'product_id erforderlich',
        'msg.need_product_amount': 'product_id und amount erforderlich',

        # -- Testnachricht an einen Kanal -----------------------------------
        'notify.test_title': 'Grocylink - Test',
        'notify.test_body': 'Dies ist eine Testnachricht von Grocylink.',

        # -- Eintraege im Log der Oberflaeche -------------------------------
        'log.test_sent': 'Testnachricht erfolgreich gesendet',
        'log.bring_sync': ('Sync erfolgreich: +{added} neu, ~{updated} '
                           'aktualisiert, -{removed} entfernt, {errors} Fehler'),
        'log.bring_sync_job': ('Bring-Sync in Ordnung: +{added} neu, '
                               '{updated} aktualisiert, {skipped} unverändert, '
                               '{removed} entfernt, {errors} Fehler'),
        'log.bring_manual': 'Manuell hinzugefügt: {name}',
        'log.bring_manual_spec': 'Manuell hinzugefügt: {name} ({spec})',
        'log.receipt_error': '{receipt}: {error}',
        'log.receipt_summary': '{receipt}: {added} gebucht, {failed} fehlgeschlagen',
        'log.receipt_summary_skipped': ('{receipt}: {added} gebucht, {failed} '
                                        'fehlgeschlagen, {skipped} ohne '
                                        'Zuordnung übersprungen'),
    },
    'en': {
        'expiry_date': 'Best before date',
        'use_by_date': 'Use by date',
        'expired_since': 'Best before exceeded since',
        'use_by_since': 'Use by date exceeded since',
        'missing_amount': 'Missing amount',
        'unknown': 'Unknown',
        'product_nr': 'Product',
        'type_expiring': 'Expiring soon',
        'type_expired': 'Expired',
        'type_missing': 'Below minimum stock',
        'title': 'Grocy Warning: {count} product(s) require attention',

        'msg.check_done': 'Check completed!',
        'msg.test_sent': 'Test notification sent!',
        'msg.sync_done': 'Synchronisation completed!',
        'msg.channel_missing': 'Channel not found',
        'msg.grocy_missing': 'Grocy is not configured',
        'msg.receipt_missing': 'Receipt not found',
        'msg.no_file': 'No file uploaded',
        'msg.pdf_only': 'Only PDF files are allowed',
        'msg.need_list_uuid': 'list_uuid required',
        'msg.need_item': 'list_uuid + item_uuid required',
        'msg.need_name': 'name required',
        'msg.need_product': 'product_id required',
        'msg.need_product_amount': 'product_id and amount required',

        'notify.test_title': 'Grocylink - Test',
        'notify.test_body': 'This is a test notification from Grocylink.',

        'log.test_sent': 'Test notification sent successfully',
        'log.bring_sync': ('Sync successful: +{added} new, ~{updated} updated, '
                           '-{removed} removed, {errors} errors'),
        'log.bring_sync_job': ('Bring sync OK: +{added} new, {updated} updated, '
                               '{skipped} unchanged, {removed} removed, '
                               '{errors} errors'),
        'log.bring_manual': 'Added manually: {name}',
        'log.bring_manual_spec': 'Added manually: {name} ({spec})',
        'log.receipt_error': '{receipt}: {error}',
        'log.receipt_summary': '{receipt}: {added} booked, {failed} failed',
        'log.receipt_summary_skipped': ('{receipt}: {added} booked, {failed} '
                                        'failed, {skipped} skipped without '
                                        'assignment'),
    },
}


def sprache_lesen() -> str:
    """Die eingestellte Sprache -- oder die Vorgabe.

    Der Import steht **im** Aufruf: `database` importiert nichts von hier, aber
    ein Import auf Modulebene machte aus zwei unabhaengigen Modulen einen Ring.
    """
    try:
        from database import get_all_settings
        return (get_all_settings() or {}).get('language') or VORGABE
    except Exception:
        # Ohne Datenbank (Tests, erster Start) bleibt es bei der Vorgabe --
        # eine fehlende Einstellung darf keinen Versand verhindern.
        return VORGABE


def t(schluessel: str, lang: str | None = None, **werte) -> str:
    """Uebersetzt einen Schluessel und setzt Platzhalter ein.

    Unbekannte Schluessel kommen unveraendert zurueck statt einen Fehler zu
    werfen: Ein fehlender Text ist ein Schoenheitsfehler, kein Grund, eine
    Benachrichtigung ausfallen zu lassen.
    """
    if lang is None:
        lang = sprache_lesen()
    tabelle = TEXTE.get(lang) or TEXTE[VORGABE]
    text = tabelle.get(schluessel)
    if text is None:
        text = TEXTE[VORGABE].get(schluessel, schluessel)
    if not werte:
        return text
    try:
        return text.format(**werte)
    except (KeyError, IndexError):
        return text
