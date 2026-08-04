# Hinweise für Claude

## Workflow-Vorgehen

- Dateien (z. B. `generate_epg.py`, `epg_lib.py`, `sender.txt`, ...) werden
  während der Session frei bearbeitet, **ohne** zwischendurch zu committen
  oder zu pushen.
- Erst wenn der Nutzer explizit sagt, dass jetzt committet und **auf main**
  gepusht werden soll (z. B. "jetzt auf main committen und pushen", "Final"),
  wird ein Commit erstellt und **direkt auf main** gepusht.
- Auch dann **immer zuerst kurz nachfragen und bestätigen lassen**
  (welche Dateien, Commit-Message), bevor der Commit/Push tatsächlich
  ausgeführt wird — auch bei wiederholten Anweisungen in derselben Session.

Diese Bestätigungspflicht gilt dauerhaft und darf nicht übersprungen werden.

## Workflow manuell starten

Der GitHub-Actions-Workflow "Update EPG"
(`.github/workflows/update_epg.yml`, `workflow_dispatch`) wird **nur** nach
direkter, expliziter Anweisung des Nutzers ausgelöst (z. B. "starte den
Workflow") — niemals automatisch oder proaktiv, auch nicht direkt nachdem
gemeinsam etwas am Skript geändert wurde, solange der Nutzer nicht
ausdrücklich danach fragt.

## Neue Sender in sender.txt

Neue Sender werden immer **ganz oben** in `sender.txt` eingefügt (nicht ans
Ende anhängen).

## Architektur-Überblick

`generate_epg.py` liest `sender.txt` (Format `Land|Sender|Beschreibung|Logo`,
oder `NAME:<exakter Kanalname>|Logo` für Sender, deren echter Playlist-Name
selbst Pipe-Zeichen enthält) und erzeugt daraus `Epg_365_Tage.xml`.
`epg_lib.py` enthält die Kategorie-/Sprach-/Text-Logik. Der
GitHub-Actions-Workflow `update_epg.yml` läuft alle 8h automatisch und bei
manuellem Trigger.

## DYN PPV / Live-Kanalname-Mechanismus

- DYN PPV 1-50 und andere `NAME:`-Sender bekommen ihren Sendungstitel
  automatisch aus dem echten, aktuellen Live-Kanalnamen des
  EPG-Anbieters (myepg.top), statt aus einem geratenen API-Round-Robin.
- Zwei GitHub Secrets liefern die Anbieter-Dateien: `DYN_EPG_PROVIDER_URL`
  (World) und `DYN_EPG_PROVIDER_URL_EU` (EU) - beide werden abgefragt und
  die Treffer zusammengeführt, da unterschiedliche Kategorien (z. B. DYN
  PPV) nur in einer der beiden Dateien stecken.
- DYN PPV zeigt bewusst auch den Leerlauf-Text ("- NO EVENT STREAMING -
  | 8K EXCLUSIVE") 1:1 an statt eines generischen Platzhalters - das ist
  gewolltes Verhalten, kein Bug.
- Status-Marker im rohen Kanalnamen ("NEXT | ...", "End | ...") werden
  automatisch in verständlichen deutschen Text übersetzt ("Es folgt: ...",
  fester Abmoderationstext bei "End").
- Komplett großgeschriebene Wörter im Event-Text werden normalisiert
  (z. B. "8K EXCLUSIVE" -> "8K Exclusive"), damit es nicht "schreit".
- **Bekanntes, ungelöstes Problem:** Die Anbieter-Daten (myepg.top) sind
  teils deutlich verzögert/asynchron zur echten DYN-Sport-Live-Zeitplanung
  (z. B. zeigt "beendet" an, obwohl noch gar kein Spiel lief). Das liegt an
  der Datenqualität des Anbieters, nicht am Skript.
- Kategorie-Erkennung (`epg_lib.py`, `standard_beschreibung()`) nutzt
  Wortgrenzen (`\b...\b`) statt reinem Teilstring-Vergleich, um
  Fehlzuordnungen zu vermeiden (z. B. "LOVE AND MARRIAGE" matchte früher
  fälschlich das Kurz-Keyword "LOV" der Kategorie Jagd & Angeln).
- Generische Sendetitel enthalten keinen Wochentag/kein Datum mehr, nur
  noch Event- bzw. Kategorietext.
- Der Mechanismus deckt zwei Namenskonventionen ab: Kern-HINTEN (DYN PPV,
  Flo Racing - Kern nach dem letzten Pipe) und Kern-VORNE (Clubber-PPV,
  Irland/GAA - Kern vor dem ersten Pipe, z. B. "(IE) (Clubber 01) | Kerry
  GAA: ..."). `epg_anbieter_datei_abgleichen()` probiert bei einem Sender
  automatisch beide Konventionen durch (`kern_und_event_extrahieren()` /
  `kern_vorne_und_event_extrahieren()`), bevor er den Kanal als
  "kein Treffer" überspringt. Clubber hatte vorher eine eigene
  Round-Robin-API-Zuordnung (unzuverlässig, siehe Git-Historie) - läuft
  jetzt komplett über denselben generischen myepg.top-Abgleich wie DYN PPV.
