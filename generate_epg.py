from datetime import datetime, timedelta

# sender.txt einlesen
with open("sender.txt", "r", encoding="utf-8") as f:
    sender_liste = [zeile.strip() for zeile in f if zeile.strip()]

xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'

sender_daten = []

# Sender erzeugen
for zeile in sender_liste:
    teile = [x.strip() for x in zeile.split("|")]

    # Erwartet:
    # DE|SKY GO FILME 1 FHD|https://logo.png|Beschreibung
    if len(teile) < 4:
        continue

    kanal = teile[0] + "|" + teile[1]
    titel = teile[1]
    logo = teile[2]
    beschreibung = teile[3]

    sender_daten.append((kanal, titel, beschreibung))

    xml += f'''
<channel id="{kanal}">
    <display-name>{titel}</display-name>
    <icon src="{logo}"/>
</channel>
'''

# Programme erzeugen
starttag = datetime.now()

for tag in range(365):

    start = (starttag + timedelta(days=tag)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0
    )

    stop = start + timedelta(days=1)

    for kanal, titel, beschreibung in sender_daten:

        xml += f'''
<programme start="{start.strftime('%Y%m%d%H%M%S')} +0200"
           stop="{stop.strftime('%Y%m%d%H%M%S')} +0200"
           channel="{kanal}">
    <title>{titel}</title>
    <desc>{beschreibung}</desc>
</programme>
'''

xml += "\n</tv>"

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml)
