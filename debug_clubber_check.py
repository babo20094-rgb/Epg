"""Einmaliges Debug-Skript: prueft, ob die myepg.top-EPG-Dateien (World
und EU) ueberhaupt "CLUBBER"-Kanaele enthalten. Kein Teil der
eigentlichen EPG-Generierung - nur zur einmaligen Diagnose, ob sich der
generische NAME:-Live-Kanalname-Abgleich (bisher DYN PPV, Flo Racing,
DirtVision) auch fuer die 50 echten Clubber-PPV-Sender nutzen liesse,
statt der aktuellen Clubber-eigenen API mit Round-Robin-Zuordnung. Wird
nach dem Test wieder entfernt.
"""
import os
import re
import zlib

import requests


def pruefe(url, quelle_name):
    if not url:
        print(f"{quelle_name}: URL nicht gesetzt - Test uebersprungen.")
        return

    response = requests.get(url, timeout=30, stream=True)
    response.raise_for_status()

    dekomprimierer = zlib.decompressobj(16 + zlib.MAX_WBITS)
    gepuffert = ""
    for chunk in response.iter_content(chunk_size=65536):
        gepuffert += dekomprimierer.decompress(chunk).decode("utf-8", errors="ignore")
        if "<programme" in gepuffert or len(gepuffert) > 20_000_000:
            break
    response.close()

    kanal_bereich = gepuffert.split("<programme", 1)[0]
    print(f"{quelle_name}: gelesener Kanal-Bereich: {len(kanal_bereich)} Zeichen")

    treffer = set()
    for name_match in re.finditer(r"<display-name>([^<]*)</display-name>", kanal_bereich):
        name = name_match.group(1)
        if re.search(r"CLUBBER", name, re.IGNORECASE):
            treffer.add(name.strip())

    if treffer:
        print(f"{quelle_name}: {len(treffer)} passende Kanalnamen gefunden:")
        for t in sorted(treffer):
            print(" -", t)
    else:
        print(f"{quelle_name}: Keine CLUBBER-Kanaele gefunden.")


pruefe(os.environ.get("DYN_EPG_PROVIDER_URL"), "World")
pruefe(os.environ.get("DYN_EPG_PROVIDER_URL_EU"), "EU")
