from datetime import datetime, timedelta

start = datetime.now()

xml = """<?xml version="1.0" encoding="UTF-8"?>
<tv>

<channel id="RS| MASA I MEDVJED">
<display-name>RS| MASA I MEDVJED</display-name>
<icon src="https://www.talentshow.hr/Brands/Masha/Logo.png"/>
</channel>

"""

for i in range(365):

    a = start + timedelta(days=i)
    b = a + timedelta(days=1)

    xml += f'''
<programme start="{a.strftime("%Y%m%d")}000000 +0200"
stop="{b.strftime("%Y%m%d")}000000 +0200"
channel="RS| MASA I MEDVJED">
<title>Masa i Medvjed Crtani Film</title>
</programme>
'''

xml += "</tv>"

with open("Epg_365_Tage.xml","w",encoding="utf-8") as f:
    f.write(xml)
