"""Einmaliges Debug-Skript: prueft, ob die EU-TREX-EPG-Datei
(DYN_EPG_PROVIDER_URL_EU) ueberhaupt "FLO RACING"- oder "DIRTVISION"-
Kanaele enthaelt. Kein Teil der eigentlichen EPG-Generierung - nur zur
einmaligen Diagnose, warum diese Sender bisher keinen Live-Namen aus der
World-Datei bekommen. Wird nach dem Test wieder entfernt.
"""
import os
import re
import zlib

import requests

URL = os.environ.get("DYN_EPG_PROVIDER_URL_EU")
if not URL:
    print("DYN_EPG_PROVIDER_URL_EU nicht gesetzt - Test uebersprungen.")
    raise SystemExit(0)

response = requests.get(URL, timeout=30, stream=True)
response.raise_for_status()

dekomprimierer = zlib.decompressobj(16 + zlib.MAX_WBITS)
gepuffert = ""
for chunk in response.iter_content(chunk_size=65536):
    gepuffert += dekomprimierer.decompress(chunk).decode("utf-8", errors="ignore")
    if "<programme" in gepuffert or len(gepuffert) > 20_000_000:
        break
response.close()

kanal_bereich = gepuffert.split("<programme", 1)[0]
print(f"Gelesener Kanal-Bereich: {len(kanal_bereich)} Zeichen")

treffer = set()
for name_match in re.finditer(r"<display-name>([^<]*)</display-name>", kanal_bereich):
    name = name_match.group(1)
    if re.search(r"FLO\s*RACING|DIRTVISION", name, re.IGNORECASE):
        treffer.add(name.strip())

if treffer:
    print(f"{len(treffer)} passende Kanalnamen gefunden:")
    for t in sorted(treffer):
        print(" -", t)
else:
    print("Keine FLO RACING/DIRTVISION-Kanaele in der EU-Datei gefunden.")
