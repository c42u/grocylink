"""Tests fuer den persistenten Bring-Runtime.

Kernaussage der Suite: Ein einmal eingeloggter Client ueberlebt mehrere
Aufrufe. Genau das war bis v1.4.x nicht der Fall - dort kostete jeder
Request einen kompletten Login.
"""

import pytest

from bring_runtime import BringRuntime, BringRuntimeError, _fingerprint


@pytest.fixture
def runtime():
    """Eigener Runtime je Test, damit kein Zustand ueberspringt."""
    rt = BringRuntime()
    yield rt
    rt.shutdown()


def test_client_wird_ueber_aufrufe_hinweg_wiederverwendet(runtime, fake_bring):
    """Zwei Aufrufe, ein Login - der Kern der Haertung."""
    for _ in range(3):
        runtime.execute(lambda bring: bring.load_lists(), 'a@b.de', 'geheim')

    assert len(fake_bring.instances) == 1, "es darf nur ein Client entstehen"
    client = fake_bring.instances[0]
    assert client.login_count == 1
    assert client.count('load_lists') == 3


def test_credential_wechsel_erzwingt_neuen_login(runtime, fake_bring):
    runtime.execute(lambda bring: bring.load_lists(), 'a@b.de', 'altes-pw')
    runtime.execute(lambda bring: bring.load_lists(), 'a@b.de', 'neues-pw')

    assert len(fake_bring.instances) == 2
    assert fake_bring.instances[1].password == 'neues-pw'


def test_relogin_nach_abgelaufenem_token(runtime, fake_bring):
    """Ein Auth-Fehler fuehrt zu genau einem Wiederholungsversuch."""
    from bring_api.exceptions import BringAuthException

    aufrufe = {'n': 0}

    async def flaky(bring):
        aufrufe['n'] += 1
        if aufrufe['n'] == 1:
            raise BringAuthException("Token abgelaufen")
        return 'erfolg'

    ergebnis = runtime.execute(flaky, 'a@b.de', 'geheim')

    assert ergebnis == 'erfolg'
    assert len(fake_bring.instances) == 2, "nach Auth-Fehler frisch einloggen"


def test_auth_fehler_wird_nach_zweitem_versuch_durchgereicht(runtime, fake_bring):
    from bring_api.exceptions import BringAuthException

    async def immer_kaputt(bring):
        raise BringAuthException("dauerhaft ungueltig")

    with pytest.raises(BringAuthException):
        runtime.execute(immer_kaputt, 'a@b.de', 'geheim')


def test_fehlende_zugangsdaten(runtime, fake_bring):
    with pytest.raises(BringRuntimeError):
        runtime.execute(lambda bring: bring.load_lists(), '', '')


def test_login_fehler_hinterlaesst_keinen_client(runtime, fake_bring):
    """Scheitert der Login, darf kein halbfertiger Client zurueckbleiben."""
    fake_bring.login_side_effects = [RuntimeError("Passwort falsch")]

    with pytest.raises(RuntimeError):
        runtime.execute(lambda bring: bring.load_lists(), 'a@b.de', 'falsch')

    assert not runtime.is_connected
    # Der naechste Versuch muss wieder einen Login wagen
    runtime.execute(lambda bring: bring.load_lists(), 'a@b.de', 'richtig')
    assert runtime.is_connected


def test_invalidate_verwirft_den_client(runtime, fake_bring):
    runtime.execute(lambda bring: bring.load_lists(), 'a@b.de', 'geheim')
    assert runtime.is_connected

    runtime.invalidate()
    assert not runtime.is_connected

    runtime.execute(lambda bring: bring.load_lists(), 'a@b.de', 'geheim')
    assert len(fake_bring.instances) == 2


def test_zeitueberschreitung_wird_gemeldet(runtime, fake_bring):
    """Haengt Bring, bricht der Aufruf ab statt den Worker zu blockieren."""
    import asyncio

    async def haengt(bring):
        await asyncio.sleep(5)

    with pytest.raises(BringRuntimeError, match='ohne Antwort'):
        runtime.execute(haengt, 'a@b.de', 'geheim', timeout=0.2)


def test_invalidate_ohne_laufenden_loop_ist_harmlos():
    """Invalidieren, bevor je ein Aufruf lief, darf nicht scheitern."""
    rt = BringRuntime()
    rt.invalidate()
    rt.shutdown()


def test_fingerprint_unterscheidet_zugangsdaten():
    assert _fingerprint('a@b.de', 'x') == _fingerprint('a@b.de', 'x')
    assert _fingerprint('a@b.de', 'x') != _fingerprint('a@b.de', 'y')
    assert _fingerprint('a@b.de', 'x') != _fingerprint('c@d.de', 'x')
    # Trennzeichen: Verschiebung zwischen den Feldern darf nicht kollidieren
    assert _fingerprint('ab', 'c') != _fingerprint('a', 'bc')


def test_runtime_ueberlebt_shutdown_und_startet_neu(fake_bring):
    rt = BringRuntime()
    try:
        rt.execute(lambda bring: bring.load_lists(), 'a@b.de', 'geheim')
        rt.shutdown()
        # Nach dem Herunterfahren muss ein neuer Aufruf den Loop neu starten
        rt.execute(lambda bring: bring.load_lists(), 'a@b.de', 'geheim')
        assert len(fake_bring.instances) == 2
    finally:
        rt.shutdown()
