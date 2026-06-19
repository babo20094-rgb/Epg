from datetime import datetime, timedelta

with open("sender.txt", "r", encoding="utf-8") as f:
    sender_liste = [zeile.strip() for zeile in f if zeile.strip()]

xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'

# Channels erzeugen
for zeile in sender_liste:
    teile = [x.strip() for x in zeile.split(";", 3)]

    kanal = teile[0]
    titel = teile[1]
    logo = teile[2]

    xml += f'''
<channel id="{kanal}">
    <display-name>{titel}</display-name>
    <icon src="{logo}"/>
</channel>
'''

# Programme erzeugen
starttag = datetime.now()

zeiten = [
    (0, 6),
    (6, 12),
    (12, 18),
    (18, 24)
]

for zeile in sender_liste:
    teile = [x.strip() for x in zeile.split(";", 3)]

    kanal = teile[0]
    titel = teile[1]

    for tag in range(365):

        basis = starttag + timedelta(days=tag)

        for von, bis in zeiten:

            start = basis.replace(hour=von, minute=0, second=0)
            stop = basis.replace(hour=0, minute=0, second=0) + timedelta(hours=bis)

            xml += f'''
<programme start="{start.strftime('%Y%m%d%H%M%S')} +0200"
stop="{stop.strftime('%Y%m%d%H%M%S')} +0200"
channel="{kanal}">
    <title>{titel}</title>
</programme>
'''

xml += "\n</tv>"

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml)
