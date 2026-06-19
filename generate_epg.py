from datetime import datetime, timedelta

# Senderliste laden
with open("sender.txt", "r", encoding="utf-8") as f:
    sender_liste = [zeile.strip() for zeile in f if zeile.strip()]

# XML-Kopf
xml = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
"""

# Channels erzeugen
for zeile in sender_liste:
    teile = [x.strip() for x in zeile.split("|")]

    if len(teile) < 4:
        continue

    land = teile[0]
    kanal = teile[1]
    titel = teile[2]
    logo = teile[3]

    channel_id = f"{land}|{kanal}"

    xml += f"""
<channel id="{channel_id}">
    <display-name>{titel}</display-name>
    <icon src="{logo}"/>
</channel>
"""

# Programme erzeugen
starttag = datetime.now()

zeiten = [
    (0, 6),
    (6, 12),
    (12, 18),
    (18, 24)
]

for tag in range(365):
    basis = starttag + timedelta(days=tag)

    for von, bis in zeiten:

        start = basis.replace(hour=von, minute=0, second=0)
        stop = basis.replace(hour=0, minute=0, second=0) + timedelta(hours=bis)

        for zeile in sender_liste:
            teile = [x.strip() for x in zeile.split("|")]

            if len(teile) < 4:
                continue

            land = teile[0]
            kanal = teile[1]
            titel = teile[2]

            channel_id = f"{land}|{kanal}"

            xml += f"""
<programme start="{start.strftime('%Y%m%d%H%M%S')} +0200"
stop="{stop.strftime('%Y%m%d%H%M%S')} +0200"
channel="{channel_id}">
    <title>{titel}</title>
</programme>
"""

xml += "\n</tv>"

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml)
