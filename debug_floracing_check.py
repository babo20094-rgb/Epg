"""Einmaliges Debug-Skript: prueft, ob/wie die myepg.top-EPG-Dateien
(World und EU) FLO RACING- und DIRTVISION-Kanaele benennen - Diagnose
fuer den Verdacht, dass ein Trenn-Doppelpunkt-Mismatch zwischen
sender.txt-Kernnamen und den echten Anbieter-Kanalnamen verhindert,
dass Events fuer diese Sender uebernommen werden. Wird nach dem Test
wieder entfernt."""
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
        if re.search(r"FLO\s*RACING|DIRTVISION", name, re.IGNORECASE):
            treffer.add(name.strip())

    if treffer:
        print(f"{quelle_name}: {len(treffer)} passende Kanalnamen gefunden:")
        for t in sorted(treffer):
            print(" -", repr(t))
    else:
        print(f"{quelle_name}: Keine FLO RACING/DIRTVISION-Kanaele gefunden.")


pruefe(os.environ.get("DYN_EPG_PROVIDER_URL"), "World")
pruefe(os.environ.get("DYN_EPG_PROVIDER_URL_EU"), "EU")
