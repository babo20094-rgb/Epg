from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

tree = ET.parse("Epg_365_Tage.xml")
root = tree.getroot()

today = datetime.now()

programmes = root.findall("programme")

for i, programme in enumerate(programmes):
    start = today + timedelta(days=i)
    stop = start + timedelta(days=1)

    programme.set(
        "start",
        start.strftime("%Y%m%d000000 +0200")
    )

    programme.set(
        "stop",
        stop.strftime("%Y%m%d000000 +0200")
    )

tree.write(
    "Epg_365_Tage.xml",
    encoding="UTF-8",
    xml_declaration=True
)
