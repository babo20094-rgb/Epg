from datetime import datetime, timedelta
import requests
import xml.etree.ElementTree as ET

xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'

sender_daten = []

# sender.txt einlesen
with open("sender.txt", "r", encoding="utf-8") as f:
    sender_liste = [zeile.strip() for zeile in f if zeile.strip()]

for zeile in sender_liste:
    teile = [x.strip() for x in zeile.split("|")]
    if len(teile) < 3:
        continue
    land = teile[0]
    sendername = teile[1]
    beschreibung = teile[2]
    logo = teile[3] if len(teile) >= 4 else ""
    kanal = f"{land}|{sendername}"
    sender_daten.append((kanal, beschreibung))
    xml += f""" <channel id="{kanal}"> <display-name>{sendername}</display-name> <icon src="{logo}"/> </channel> """

dyn_logo = "https://www.dslweb.de/public/resources/images/anbieter/dyn/dyn-teaser.jpg"
for i in range(1,21):
    kanal=f"DE| DYN PPV {i} HD"
    xml += f""" <channel id="{kanal}"> <display-name>{kanal}</display-name> <icon src="{dyn_logo}"/> </channel> """

# ... bestehende DYN und Standard-EPG Logik ...

def tvprofil_id(name):
    return name.lower().replace("de|","").replace(" hd","").replace(" ","")

print("Lade TVProfil XMLTV...")
try:
    response=requests.get("https://tvprofil.net/xmltv/data/epg_tvprofil.net.xml",timeout=120)
    if response.status_code==200:
        root=ET.fromstring(response.content)
        programme=root.findall("programme")
        tvprofil_channels={}
        for channel in root.findall("channel"):
            cid=channel.get("id")
            dn=channel.find("display-name")
            tvprofil_channels[cid]=dn.text.lower() if dn is not None and dn.text else ""
        with open("tvprofil_channels.txt","w",encoding="utf-8") as f:
            for cid,name in sorted(tvprofil_channels.items()):
                f.write(f"{cid}|{name}\n")
        print("TVProfil Sender exportiert:",len(tvprofil_channels))
        print("TVProfil Programme geladen:",len(programme))
        for eintrag in programme:
            channel=eintrag.get("channel","").lower()
            for kanal,beschreibung in sender_daten:
                sender=tvprofil_id(kanal)
                if sender and sender in channel:
                    eintrag.set("channel",kanal)
                    break
            xml += ET.tostring(eintrag,encoding="unicode")
    else:
        print("TVProfil HTTP Fehler:",response.status_code)
except Exception as e:
    print("TVProfil Fehler:",e)

xml += "\n</tv>"
with open("Epg_365_Tage.xml","w",encoding="utf-8") as f:
    f.write(xml)
print("EPG-Datei erfolgreich erstellt.")
