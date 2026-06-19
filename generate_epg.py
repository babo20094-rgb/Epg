from datetime import datetime, timedelta

# Senderliste laden
with open("sender.txt", "r", encoding="utf-8") as f:
    sender_liste = [zeile.strip() for zeile in f if zeile.strip()]

xml = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
"""

# Channel-Einträge erzeugen
for zeile in sender_liste:

    teile = [x.strip() for x in zeile.split("|")]

    if len(teile) < 3:
        continue

    kanal = teile[0]
    titel = teile[1]
    logo = teile[2]

    xml += f"""
  <channel id="{kanal}">
    <display-name>{kanal}</display-name>
    <icon src="{logo}"/>
  </channel>
"""

# Programm-Einträge erzeugen
starttag = datetime.now()

for tag in range(365):

    start = starttag + timedelta(days=tag)
    stop = start + timedelta(days=1)

    for zeile in sender_liste:

        teile = [x.strip() for x in zeile.split("|")]

        if len(teile) < 3:
            continue

        kanal = teile[0]
        titel = teile[1]

        xml += f"""
  <programme start="{start.strftime('%Y%m%d')}000000 +0200"
             stop="{stop.strftime('%Y%m%d')}000000 +0200"
             channel="{kanal}">
    <title>{titel}</title>
  </programme>
"""

xml += """
</tv>
"""

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml)
