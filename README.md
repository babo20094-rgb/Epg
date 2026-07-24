# Epg
EPG Generator

Python-Skript zur Erstellung einer XMLTV-EPG-Datei (Epg_365_Tage.xml) für die Nutzung mit TiviMate (oder anderen Playern, die XMLTV unterstützen).


Funktionsweise

Das Skript liest Senderdaten aus sender.txt und erzeugt daraus:



<channel>-Einträge (display-name, ggf. Icon)

Platzhalter-Programme im 4-Stunden-Block-Raster für 365 Tage


Da die genutzte Playlist kein tvg-id enthält, erfolgt die Zuordnung zwischen Playlist und EPG über den tvg-name.


Eingabedateien

sender.txt

Bis zu 4 Spalten, Trennzeichen |:


Land|Sender|Beschreibung|Logo

Je nach Sender werden nur 2 oder alle 4 Spalten befüllt. Ein icon-Tag wird im XML nur erzeugt, wenn in dieser Datei explizit ein Logo angegeben ist – ansonsten bleibt das ursprüngliche Playlist-Logo erhalten.


Land-Feld:



Klammerzusätze (z. B. US (ESPN+ 001)) werden bei der Spracherkennung ignoriert

Unterstützte Präfixe: EXYU, BS (serbokroatischer Text), AU, TUBI, CITY, GO, PRIME, JOYN, WOW (englischer Text)


logo_only.txt (optional)

Gleiches 4-Spalten-Format wie sender.txt. Für Sender, deren echtes EPG bereits von einer anderen Quelle kommt und die nur ein Logo benötigen, ohne dass Platzhalter-Programme erzeugt werden.


Sonderfall – dynamische Kanalnamen:
Für Sender, deren Kanalname mehrere Pipes enthält und sich dynamisch ändert (z. B. - LIVE - | 8K EXCLUSIVE | DE: DYN PPV 1), wird nur der stabile Kurzname ohne Präfix eingetragen:


DE: DYN PPV 1|https://www.dslweb.de/public/resources/images/anbieter/dyn/dyn-teaser.jpg

Zeilen mit genau einem Pipe werden automatisch als Name|Logo-URL erkannt.


Namenskonventionen


Playlist-tvg-name-Format: LAND| SENDER in Großbuchstaben, z. B. DE| ACHTELFINALE - USA VS BELGIEN (Pipe gefolgt von Leerzeichen)

display-name im XML: entspricht exakt dem Playlist-Format (für die automatische Zuordnung)

Programmtitel im EPG-Raster: normale Schreibweise (nicht Großbuchstaben)


Ausgabe


Datei: Epg_365_Tage.xml

Format: XMLTV

Zeitraum: 365 Tage im 4-Stunden-Block-Raster


Nutzung

python epg_generator.py

Voraussetzung: sender.txt (und optional logo_only.txt) liegen im selben Verzeichnis.


Bekannte Konventionen / Sonderfälle


Fehlt ein Logo in sender.txt, wird kein icon-Tag erzeugt

logos.txt-Fallback wird nicht mehr genutzt

ca. 50 Sender ohne eigenes Logo nutzen einheitlich das DYN-Logo

