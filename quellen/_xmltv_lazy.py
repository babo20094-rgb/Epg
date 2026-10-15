"""Schneller, lazy Ladepfad fuer grosse XMLTV-Feeds (epgshare01, ...).

Hintergrund (Oktober 2026): Der Lauf ist rechengebunden (GIL). Das komplette
Parsen grosser Feeds per ElementTree (z.B. CH1: 53 MB, 87.701 Sendungen, ~5 s
CPU) ist Verschwendung, weil nur ein Bruchteil der Kanaele je angefragt wird.
Dieser Pfad parst nur den Kopf (Kanalliste) per ElementTree; die
<programme>-Bloecke bleiben als Rohbytes pro Kanal liegen und werden erst beim
ersten Zugriff auf den Kanal geparst (gecached, thread-sicher). Bei JEDEM
unerwarteten Format wirft zerlege() - der Aufrufer faellt dann auf den
bisherigen Voll-Parse zurueck (gleiches Ergebnis).
"""

import re
import threading
import xml.etree.ElementTree as ET

_PROGRAMM_BLOCK = re.compile(
    rb'<programme\b[^>]*?\bchannel="([^"]*)"[^>]*?(?:/>|>.*?</programme>)', re.S
)


def _attribut_wert(roh_wert):
    """Attributwert (Rohbytes) wie ElementTree aufloesen (&amp;, &apos;,
    &#39; ...) - nur bei '&' noetig, sonst direkt dekodieren."""
    if b"&" not in roh_wert:
        return roh_wert.decode("utf-8")
    return ET.fromstring(b'<x a="' + roh_wert + b'"/>').get("a")


def zerlege(xml_bytes):
    """Gibt (kopf_wurzel, roh) zurueck: kopf_wurzel = ElementTree-Wurzel mit
    allen <channel>-Elementen, roh = {kanal_id: [Rohbytes der Bloecke]}.
    Wirft ValueError bei jedem unerwarteten Format."""
    erstes = xml_bytes.find(b"<programme")
    if erstes < 0:
        raise ValueError("kein <programme> gefunden")
    kopf = xml_bytes[:erstes]
    if b"encoding" in kopf[:200] and b"UTF-8" not in kopf[:200].upper():
        raise ValueError("Kodierung nicht UTF-8")
    if xml_bytes.find(b"<channel", erstes) >= 0:
        raise ValueError("<channel> hinter dem ersten <programme>")
    wurzel = ET.fromstring(kopf + b"</tv>")

    roh = {}
    anzahl = 0
    for m in _PROGRAMM_BLOCK.finditer(xml_bytes, erstes):
        roh.setdefault(_attribut_wert(m.group(1)), []).append(m.group(0))
        anzahl += 1
    if anzahl != xml_bytes.count(b"<programme", erstes):
        raise ValueError("Programmbloecke nicht vollstaendig erkannt")
    return wurzel, roh


class LazyProgramme(dict):
    """dict {schluessel: [Sendungen]} mit lazy Rohbloecken. Nur get(),
    `in` und Einzelzugriff loesen das Parsen aus; die Schluessel der
    Rohbloecke zaehlen als vorhanden."""

    def __init__(self, parser):
        """parser(schluessel, [Rohbytes]) -> sortierte Sendungsliste."""
        super().__init__()
        self._parser = parser
        self._roh = {}
        self._sperre = threading.Lock()

    def roh_hinzufuegen(self, schluessel_roh):
        self._roh.update(schluessel_roh)

    def _fertig(self, schluessel):
        if schluessel in self._roh and not dict.__contains__(self, schluessel):
            with self._sperre:
                if not dict.__contains__(self, schluessel):
                    try:
                        eintraege = self._parser(schluessel, self._roh[schluessel])
                    except Exception:
                        eintraege = []
                    self[schluessel] = eintraege

    def get(self, schluessel, default=None):
        self._fertig(schluessel)
        return dict.get(self, schluessel, default)

    def __getitem__(self, schluessel):
        self._fertig(schluessel)
        return dict.__getitem__(self, schluessel)

    def __contains__(self, schluessel):
        return dict.__contains__(self, schluessel) or schluessel in self._roh


def bloecke_zu_elementen(bloecke):
    """Rohbloecke eines Kanals -> Liste von <programme>-Elementen."""
    return ET.fromstring(b"<tv>" + b"".join(bloecke) + b"</tv>").findall("programme")
