"""Prueft, dass jeder verwendete Uebersetzungsschluessel auch existiert.

Anlass: In 1.7.0 standen in der Oberflaeche Rohschluessel -- "keys.title"
statt "App-Zugaenge", "keys.device" statt "Geraet". Zwei Ursachen, die kein
bestehender Test bemerkt hat:

1. Fuenf Schluessel wurden in `index.html` verwendet, aber nie in `i18n.js`
   angelegt.
2. Ein ganzer Satz Schluessel landete beim Einfuegen im **englischen** Block,
   nicht im deutschen. Auf Deutsch fehlten sie damit, auf Englisch standen
   deutsche Texte.

`t()` gibt bei einem unbekannten Schluessel den Schluessel selbst zurueck --
das faellt nur auf, wenn jemand hinsieht. Dieser Test sieht hin.
"""

import os
import re
import sys

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
I18N = os.path.join(CODE, 'static', 'i18n.js')
APP_JS = os.path.join(CODE, 'static', 'app.js')
HTML = os.path.join(CODE, 'templates', 'index.html')


def _bloecke():
    """Die Schluessel je Sprache -- getrennt am Beginn des en-Abschnitts."""
    text = open(I18N, encoding='utf-8').read()
    grenze = text.index('  en: {')
    muster = r"^\s*'([a-z0-9_.]+)':"
    de = set(re.findall(muster, text[:grenze], re.M))
    en = set(re.findall(muster, text[grenze:], re.M))
    return de, en


def test_beide_sprachen_haben_dieselben_schluessel():
    de, en = _bloecke()
    assert de, "im deutschen Block wurde kein Schluessel gefunden"
    assert de == en, (
        "Unterschied zwischen den Sprachen -- nur de: %s | nur en: %s"
        % (sorted(de - en), sorted(en - de)))


def test_verwendete_schluessel_sind_angelegt():
    de, en = _bloecke()
    vorhanden = de & en

    verwendet = set()
    html = open(HTML, encoding='utf-8').read()
    verwendet |= set(re.findall(r'data-i18n="([a-z0-9_.]+)"', html))
    js = open(APP_JS, encoding='utf-8').read()
    verwendet |= set(re.findall(r"\bt\('([a-z0-9_.]+)'\)", js))

    fehlend = sorted(verwendet - vorhanden)
    assert not fehlend, (
        "diese Schluessel werden verwendet, stehen aber nicht in beiden "
        "Sprachen: %s" % fehlend)


def test_keine_doppelten_schluessel_je_sprache():
    """Ein zweites Vorkommen ueberschreibt das erste stillschweigend."""
    text = open(I18N, encoding='utf-8').read()
    grenze = text.index('  en: {')
    for name, teil in (('de', text[:grenze]), ('en', text[grenze:])):
        gefunden = re.findall(r"^\s*'([a-z0-9_.]+)':", teil, re.M)
        doppelt = sorted({k for k in gefunden if gefunden.count(k) > 1})
        assert not doppelt, "%s enthaelt Schluessel doppelt: %s" % (name, doppelt)
