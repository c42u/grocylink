"""Persistente Laufzeitumgebung fuer den Bring!-Client.

Grocylink ist synchron (Flask + APScheduler), ``bring-api`` ist async
(aiohttp). Bis v1.4.x wurde deshalb pro Aufruf ein eigener Eventloop
gestartet, eine neue ``aiohttp.ClientSession`` geoeffnet und ein frischer
Login durchgefuehrt - bei jedem Tab-Wechsel in der Oberflaeche also gleich
mehrere Logins hintereinander.

Dieses Modul dreht das um: Ein einziger Daemon-Thread haelt einen dauerhaft
laufenden Eventloop, darin leben Session und Bring-Client weiter. Der
Access-Token wird von ``bring-api`` selbst per Refresh-Token erneuert
(``retrieve_new_access_token``), solange der Client am Leben bleibt.

Aufrufer bleiben synchron::

    from bring_runtime import get_runtime
    lists = get_runtime().execute(lambda bring: bring.load_lists())

Der Client wird anhand eines Fingerprints der Zugangsdaten gecacht. Aendern
sich Mail oder Passwort, wird beim naechsten Aufruf automatisch neu
eingeloggt; ``invalidate()`` erzwingt das sofort.
"""

import asyncio
import atexit
import hashlib
import logging
import threading
from concurrent.futures import TimeoutError as FutureTimeoutError

import aiohttp

logger = logging.getLogger(__name__)

# Zeitlimit fuer einen einzelnen HTTP-Request gegen die Bring-API
REQUEST_TIMEOUT_SECONDS = 30

# Zeitlimit fuer einen kompletten Aufruf inklusive Login und Retry.
# Ein voller Sync kann mehrere Requests umfassen, daher grosszuegiger.
CALL_TIMEOUT_SECONDS = 180


class BringRuntimeError(Exception):
    """Geworfen, wenn der Runtime keinen einsatzbereiten Client liefern kann."""


def _fingerprint(email, password):
    """Bildet einen Hash ueber die Zugangsdaten.

    Damit laesst sich ein Credential-Wechsel erkennen, ohne das Passwort
    im Speicher des Runtimes vorzuhalten.
    """
    raw = f"{email or ''}\0{password or ''}".encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


class BringRuntime:
    """Haelt Eventloop, aiohttp-Session und eingeloggten Bring-Client."""

    def __init__(self):
        # Schuetzt das Hochfahren von Thread und Loop (aufrufende Threads)
        self._thread_lock = threading.Lock()
        self._loop = None
        self._thread = None

        # Alles Folgende wird ausschliesslich im Loop-Thread angefasst
        self._session = None
        self._bring = None
        self._fingerprint = None
        self._login_lock = None

    # ── Loop-Verwaltung ────────────────────────────────────────────────

    def _ensure_loop(self):
        """Startet den Loop-Thread beim ersten Aufruf (und nach Shutdown)."""
        with self._thread_lock:
            if self._loop is not None and not self._loop.is_closed():
                return self._loop
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=self._run_loop, args=(loop,),
                name='bring-runtime', daemon=True,
            )
            thread.start()
            self._loop = loop
            self._thread = thread
            # Der Login-Lock gehoert zum Loop und muss mit ihm neu entstehen
            self._login_lock = None
            logger.debug("Bring-Runtime: Eventloop gestartet")
            return loop

    @staticmethod
    def _run_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    # ── Client-Verwaltung (laeuft im Loop-Thread) ──────────────────────

    async def _get_client(self, email, password):
        """Liefert einen eingeloggten Bring-Client, ggf. aus dem Cache."""
        from bring_api import Bring

        if not email or not password:
            raise BringRuntimeError(
                "Bring-Zugangsdaten nicht vollstaendig konfiguriert"
            )

        if self._login_lock is None:
            self._login_lock = asyncio.Lock()

        fp = _fingerprint(email, password)
        async with self._login_lock:
            # Zwischenzeitlich von einem parallelen Aufruf erledigt?
            if self._bring is not None and self._fingerprint == fp:
                return self._bring

            if self._bring is not None:
                logger.debug("Bring-Runtime: Zugangsdaten geaendert, neuer Login")
                await self._close_client()

            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
            self._session = aiohttp.ClientSession(timeout=timeout)
            bring = Bring(self._session, email, password)
            try:
                await bring.login()
            except Exception:
                # Session nicht verwaisen lassen, sonst warnt aiohttp
                await self._close_client()
                raise
            self._bring = bring
            self._fingerprint = fp
            logger.info("Bring-Runtime: Login erfolgreich, Client zwischengespeichert")
            return bring

    async def _close_client(self):
        """Gibt Session und Client frei (immer im Loop-Thread)."""
        session = self._session
        self._session = None
        self._bring = None
        self._fingerprint = None
        if session is not None and not session.closed:
            try:
                await session.close()
            except Exception as e:
                logger.warning(f"Bring-Runtime: Session-Close fehlgeschlagen: {e}")

    async def _run_guarded(self, coro_factory, email, password):
        """Fuehrt den Aufruf aus und wiederholt ihn einmal nach Auth-Fehler."""
        from bring_api.exceptions import BringAuthException

        bring = await self._get_client(email, password)
        try:
            return await coro_factory(bring)
        except BringAuthException:
            # Token abgelaufen und Refresh gescheitert: einmal frisch einloggen
            logger.info("Bring-Runtime: Auth-Fehler, versuche Relogin")
            async with self._login_lock:
                await self._close_client()
            bring = await self._get_client(email, password)
            return await coro_factory(bring)

    # ── Oeffentliche, synchrone Schnittstelle ──────────────────────────

    def execute(self, coro_factory, email, password, timeout=CALL_TIMEOUT_SECONDS):
        """Fuehrt ``coro_factory(bring)`` im Loop-Thread aus.

        ``coro_factory`` bekommt den eingeloggten Client und gibt eine
        Coroutine zurueck. Der Rueckgabewert wird synchron durchgereicht,
        Exceptions werden im aufrufenden Thread erneut geworfen.
        """
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(
            self._run_guarded(coro_factory, email, password), loop
        )
        try:
            return future.result(timeout)
        except FutureTimeoutError:
            future.cancel()
            raise BringRuntimeError(
                f"Bring-Anfrage nach {timeout}s ohne Antwort abgebrochen"
            )

    def invalidate(self):
        """Verwirft den gecachten Client, der naechste Aufruf loggt neu ein."""
        with self._thread_lock:
            loop = self._loop
            if loop is None or loop.is_closed():
                return
        future = asyncio.run_coroutine_threadsafe(self._close_client(), loop)
        try:
            future.result(REQUEST_TIMEOUT_SECONDS)
        except Exception as e:
            logger.warning(f"Bring-Runtime: Invalidierung fehlgeschlagen: {e}")

    def shutdown(self):
        """Faehrt Client und Loop herunter (Prozessende)."""
        with self._thread_lock:
            loop, thread = self._loop, self._thread
            self._loop = self._thread = None
        if loop is None or loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self._close_client(), loop
            ).result(REQUEST_TIMEOUT_SECONDS)
        except Exception:
            pass
        loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5)
        logger.debug("Bring-Runtime: heruntergefahren")

    # ── Diagnose ───────────────────────────────────────────────────────

    @property
    def is_connected(self):
        """True, wenn ein eingeloggter Client vorgehalten wird."""
        return self._bring is not None


# ── Modul-Singleton ────────────────────────────────────────────────────

_runtime = None
_runtime_lock = threading.Lock()


def get_runtime():
    """Liefert den prozessweiten Runtime (Singleton)."""
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = BringRuntime()
        return _runtime


def invalidate_runtime():
    """Verwirft den gecachten Bring-Client, falls ein Runtime existiert."""
    with _runtime_lock:
        rt = _runtime
    if rt is not None:
        rt.invalidate()


@atexit.register
def _shutdown_runtime():
    with _runtime_lock:
        rt = _runtime
    if rt is not None:
        rt.shutdown()
