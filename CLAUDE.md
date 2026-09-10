# Hinweise für Claude

> **Detailarchiv:** Die vollständige Fallgeschichte (alle bisherigen
> Bugfixes, Debugging-Lehren, historische Sonderfälle) steht in
> `docs/HISTORIE.md` und wird NICHT bei jeder Session automatisch
> mitgelesen. **Regel:** Bei einer neuen "Sender X zeigt falsches/kein
> Programm"-Meldung oder einem neuen Bug-Verdacht IMMER zuerst per
> `grep -i "<Stichwort>" docs/HISTORIE.md` nach ähnlichen vergangenen
> Fällen suchen (Sendername, Quelle, Symptom wie "Keine Information",
> "Fuzzy", "TiviMate", "Kern-Extraktion"), bevor von vorne debuggt wird -
> viele Symptome sind bereits einmal aufgetreten und dort mit Ursache
> und Fix dokumentiert. Bei neuen relevanten Erkenntnissen/Bugfixes: neuen
> Abschnitt in `docs/HISTORIE.md` ergänzen (nicht in dieser Datei).

## Sprache

- Claude antwortet in dieser Session **und in jeder neuen Session sofort und
  komplett auf Deutsch** - keine Rückfrage nötig, keine englischen
  Zwischentexte. Auch alle Statusmeldungen, Zusammenfassungen und Erklärungen
  werden auf Deutsch angezeigt.

## Workflow-Vorgehen

- Dateien (z. B. `generate_epg.py`, `epg_lib.py`, `sender.txt`, ...) werden
  während der Session frei bearbeitet, **ohne** zwischendurch zu committen
  oder zu pushen.
- Erst wenn der Nutzer explizit sagt, dass jetzt committet und **auf main**
  gepusht werden soll (z. B. "jetzt auf main committen und pushen", "ja,
  committen und pushen", "Final"), wird ein Commit erstellt und **direkt
  auf main** gepusht.
- Auch dann **immer zuerst kurz nachfragen und bestätigen lassen**
  (welche Dateien, Commit-Message), bevor der Commit/Push tatsächlich
  ausgeführt wird — auch bei wiederholten Anweisungen in derselben Session.

Diese Bestätigungspflicht gilt dauerhaft und darf nicht übersprungen werden.

**Wichtig (aus wiederholten Fehlern gelernt):** Committen/pushen NUR bei
einem wörtlichen "ja, committen und pushen" (oder eindeutig gleichbedeutender
Formulierung) auf eine explizite Rückfrage. Ein Screenshot, ein "ja" auf eine
andere Frage (z. B. "passt das Design so?"), eine allgemeine Zustimmung zur
Änderung selbst oder gar keine Antwort zählen NICHT als Freigabe zum Pushen -
in diesen Fällen bleibt die Änderung nur im Arbeitsverzeichnis, bis explizit
committet/gepusht werden soll. Vor jedem Commit zusätzlich `git fetch origin
main` + `git pull origin main --no-edit` (der automatische 3h-Workflow
committet z. B. "Daily EPG update" selbststaendig auf main), damit nicht am
lokal veralteten Stand vorbei gepusht wird.

**Session-Branch stillschweigend mitsynchronisieren:** Diese Remote-
Session läuft technisch auf einem eigenen Branch (z. B.
`claude/mein-epg-twiol2`), pusht inhaltlich aber wie oben beschrieben
direkt auf `main`. Nach jedem Push auf `main` deshalb automatisch UND
OHNE Rückfrage/Erwähnung zusätzlich `git push origin <Session-Branch>`
ausführen (denselben lokalen Stand, der gerade auf main gepusht wurde),
damit der Stop-Hook dieser Umgebung ("There are unpushed commits on
branch ...") gar nicht erst anschlägt. Das ist reine technische
Haushaltsführung dieser Sitzungsumgebung, hat mit dem eigentlichen
EPG-Projekt nichts zu tun und wird dem Nutzer NICHT als eigener
Schritt gemeldet oder erklärt - nur bei einem tatsächlichen Fehler
dabei kurz erwähnen.

**Zur wiederkehrenden Stop-Hook-Meldung ("There are uncommitted
changes..."):** Dieser Hook (`~/.claude/stop-hook-git-check.sh`) ist
KEIN Projekt-/Nutzer-Setting, sondern feste Infrastruktur der jeweiligen
Remote-Sitzungsumgebung selbst (root-eigen, nicht editierbar/deaktivierbar)
- er verhindert, dass beim Zuruecksetzen des Sitzungscontainers unbemerkt
Arbeit verloren geht. Hat NICHTS mit der Commit/Push-Bestaetigungspflicht
oben zu tun (bleibt reine Chat-Verhaltensregel) und meldet sich schlicht
immer dann, wenn zwischen zwei "ja, committen und pushen"-Freigaben
Aenderungen offen im Arbeitsverzeichnis liegen - normal/erwartet, keine
Fehlfunktion. Nicht versuchen, ihn zu deaktivieren oder zu umgehen.

## Workflow manuell starten

Der GitHub-Actions-Workflow "Update EPG"
(`.github/workflows/update_epg.yml`, `workflow_dispatch`) wird **nur** nach
direkter, expliziter Anweisung des Nutzers ausgelöst (z. B. "starte den
Workflow") — niemals automatisch oder proaktiv, auch nicht direkt nachdem
gemeinsam etwas am Skript geändert wurde, solange der Nutzer nicht
ausdrücklich danach fragt. Aktuelle Laufzeit: ca. 25-30 Minuten (nach
Parallelisierung der Netzwerk-Abrufe der groessten Quellen, siehe
`docs/HISTORIE.md`).

## Neue Sender in sender.txt

- Der Nutzer schreibt seine Playlist-Kanalnamen durchgängig in
  GROSSBUCHSTABEN. Diese Großschreibung gilt NUR für den Sendernamen
  (und das 4. Feld bei TVPASSPORT:/SKY: etc., wenn es den Playlist-Namen
  abbildet). Das Suchbegriff-Feld (2. Feld bei Opt-in-Präfixen) bleibt
  immer in der Original-Schreibweise der Quelle. Die generische
  Beschreibung (`Land|Sender|Beschreibung ᴸⁱᵛᵉ|Logo`) bleibt normale
  Schrift/Title Case + `ᴸⁱᵛᵉ`, NICHT großgeschrieben.
- Neue Sender werden immer **ganz oben** in `sender.txt` eingefügt (nicht
  ans Ende anhängen), außer der Nutzer nennt explizit eine andere Stelle.
- Bevor ein neuer Sender eingetragen wird, IMMER zuerst gezielt prüfen, ob
  eine echte EPG-Quelle (siehe Quellen-Übersicht unten) für ihn echte
  Programmdaten liefert (`*_kanal_finden()`/`*_hole_programme()` lokal
  testen), bevor die passende Präfix-Zeile eingetragen wird. Kein
  pauschales automatisches Durchsuchen ALLER Quellen für jeden `DE|`-
  Sender (bewusst nicht gebaut - Laufzeit/Fehltreffer-Risiko), sondern
  gezielt pro Sender auf Zuruf.
- **Ausnahme (Direktauftrag ohne Quellenprüfung):** Gibt der Nutzer einen
  neuen Header UND die Sendernamen direkt vor ("lege unter Header X diese
  Sender an: ..."), wird OHNE Quellenprüfung als normale Zeile
  `Land|Sender|Beschreibung ᴸⁱᵛᵉ|Logo` unter einem neuen
  `##### <Header> #####`-Header eingetragen. Quellenprüfung nur bei
  explizitem **PRÜFE AUF ECHTE PROGRAMMDATEN**.
- Findet sich KEINE echte Quelle, wird automatisch (ohne Rückfrage) als
  `Land|Sender|Beschreibung ᴸⁱᵛᵉ|Logo` eingetragen (Beschreibung =
  Sendername in Title Case + `ᴸⁱᵛᵉ`), außer der Nutzer nennt ein anderes
  Unicode-Suffix.

## Kürzung echter Titel/Beschreibungen (alle echten Quellen, außer DYN PPV)

- Nutzer will im EPG-Raster nur den kompakten Sendungs-/Spieltitel, nicht
  mehrsätzige Liga-/Ankündigungstexte. `kuerze_beschreibung(text)` in
  `generate_epg.py` erledigt das zentral für ALLE echten Quellen über
  `_schreibe_echte_programme()` (Titel + Beschreibung). DYN PPV hat eine
  eigene, unabhängige Team-vs-Team-Logik und ist ausgenommen.
- Text wird an ": " aufgeteilt, ausformulierte Erklärsätze am Ende werden
  entfernt (`_wirkt_wie_ausformulierter_satz()`); ohne Doppelpunkt greift
  ein Satzende-Fallback, sonst harter Abschnitt bei Wortgrenze.
- `_schreibe_echte_programme()` schreibt bewusst KEIN `<sub-title>`-Tag
  (manche Player hängen es im kompakten Raster an den Titel an, was die
  Kürzung wieder zunichtemacht). Volle Beschreibung bleibt im `<desc>`.
- Komplett großgeschriebene Titel/Beschreibungen (z. B. MojMaxTV) werden
  über `normalisiere_grossschreibung()` (`epg_lib.py`) in normale
  Schreibweise umgewandelt, bereits normale Texte bleiben unverändert.
- Bei Änderungen an dieser Logik immer `python3 -m pytest
  test_generate_epg.py` laufen lassen (aktuell ~95 Tests).

## Logos

- **Immer selbst hosten, nie extern verlinken** (bestätigte Dauerregel):
  jedes neu gefundene/geprüfte Logo wird heruntergeladen, optimiert und
  unter `logos/<name>/` im eigenen Repo abgelegt (URL über
  `raw.githubusercontent.com/babo20094-rgb/Epg/main/logos/...`) - nie
  eine externe URL direkt in `sender.txt` eintragen, auch nicht bei
  seriösen Quellen. Grund: Kontrolle über Erreichbarkeit/Ladezeit.
- **Größe/Kompression:** max. 300px Kantenlänge (Pillow `Image.resize()`,
  `LANCZOS`) + 256-Farben-Palette (`quantize(colors=256,
  method=FASTOCTREE)` für RGBA, `MEDIANCUT` für RGB) - bei kleinen Icons
  visuell nicht wahrnehmbar, aber massive Dateigrößen-Ersparnis.
- **Nummerierte Sender-Gruppen** (z. B. DYN PPV 1-50, Sky Select 1-8):
  Basis-Logo einmal bearbeiten, dann per Skript für jede Nummer eine
  eigene PNG unter `logos/<name>/<name>_<N>.png` erzeugen. Design-Feedback
  immer erst an 1-2 Beispielen zeigen und bestätigen lassen, bevor alle
  Nummern erzeugt werden.
- "Logo kann aus Playlist übernommen werden" heißt: Logo-Feld leer lassen,
  NICHT selbst heraussuchen.
- Referenzdateien für Sendername→Logo-Zuordnung (bisher NICHT mit
  `generate_epg.py` verknüpft, reine Nachschlagewerke):
  `logos_bei_bedarf/meine_logos.txt` (DE+EXYU), `alle_logos.txt` (alle
  Länder), `ppv_kernnamen.txt` (Kern-Namen dynamischer PPV-Gruppen),
  `kategorien.txt` (Sendername→Playlist-Kategorie).

## Architektur-Überblick

`generate_epg.py` liest `sender.txt` und erzeugt daraus `Epg_365_Tage.xml`
(+ komprimiert `Epg_365_Tage.xml.gz`, wegen GitHub-100-MB-Limit - der
Workflow committet NUR die `.gz`-Datei, Player-URL muss auf `.xml.gz`
zeigen). `epg_lib.py` enthält Kategorie-/Sprach-/Text-Logik. Der
GitHub-Actions-Workflow `update_epg.yml` läuft alle 4h automatisch und bei
manuellem Trigger (~25-30 Min. Laufzeit).

**sender.txt-Zeilenformate:**
- `Land|Sender|Beschreibung|Logo` - Standardformat.
- `NAME:<exakter Kanalname>|Logo` - für Sender, deren echter Playlist-Name
  selbst ein Pipe-Zeichen enthält oder dynamisch ist (PPV/Live-Event-
  Kanäle); der gespeicherte Kern muss stabil sein, kein Roh-Event-Text
  (siehe "Datenmüll"-Fälle in `docs/HISTORIE.md`).
- `|<Sendername mit eigenen Pipes>|Beschreibung|Logo` - "leeres Land"-
  Format: Zeile beginnt mit `|`, Parser trennt nur an den LETZTEN ZWEI
  Pipes, alles davor ist der Sendername (egal wie viele Pipes er selbst
  enthält).
- `<PREFIX>:<Land>|<Kanalname bei der Quelle>|<Logo-URL>[|<Anzeigename-
  Override>]` - Opt-in-Präfixe (siehe Quellen-Übersicht), optionales 4.
  Feld überschreibt den Anzeigenamen/die Kanal-ID.

## Quellen-Übersicht (welche Quelle liefert wofür echte Programmdaten)

**Automatisch (kein sender.txt-Präfix nötig, nur passendes Land):**
- **DE / JOYN / WOW** (auch ergänzend bei **PRIME**): Kaskade
  deswird.org → Pluto TV → tvmovie.de → hoerzu.de → Joyn-VOD →
  Magenta-myTeamTV (nur `MAGENTA SPORT PPV N`) → iptv-epg.org/DE. Jede
  Stufe füllt nur die von vorherigen Stufen noch unbedeckte Restzeit.
  (Samsung TV Plus wurde entfernt, Host liefert die Datei nicht mehr.)
- **BA / ME / MNG / MO**: Telemach → mtel.ba → klix.ba (mymedia.ba wurde
  entfernt, Quelle liefert keine Daten mehr).
- **RS**: mts.rs → SportKlub (für "Sport Klub N", mts.rs führt das nicht)
  → Arena Sport (für "Arena Adrenalin").
- **HR**: MojMaxTV (A1) → SportKlub (für "Sport Klub"/"SK N" - MojMaxTV
  führt keinen Sport-Klub-Kanal mehr, nur exakter Match erlaubt).
- **SI**: tv-spored.siol.net → delo.si (für "Sport Klub"/"SK N",
  slowenische Daten, NICHT identisch mit den kroatischen SportKlub-Daten)
  → SportKlub als letzter Fallback.
- **MK**: tv-spored.siol.net → iptv-epg.org/MK.
- **PRIME / TUBI / GO**: Tubi TV (XMLTV-Mirror, vor der DE-Kaskade).
- **CITY**: automatischer Call-Sign-Abgleich gegen tvpassport.com
  (`tvpassport_kanal_finden_callsign()`).

**Opt-in (nur mit explizitem Präfix in sender.txt):**
`TELEMACH:`, `MAGENTA:` (DE), `SKY:` (DE/GB, zeigt display als "UK|..."),
`ARENA:` (HR/RS), `DAZN:` (beliebiges Land, Default DE), `FREEVIEW:`
(GB, zeigt als "UK|..."), `TVGUIDE:` (US), `TVPASSPORT:` (US, lokale
Call-Sign-Sender).

**DYN PPV - zwei komplett getrennte Mechanismen, nicht verwechseln:**
1. DYN PPV 1-50 (`NAME:`-Zeilen): Titel aus dem echten Live-Kanalnamen
   der eigenen IPTV-Playlist (`m3u_playlist_abgleichen()`).
2. DYN PPV 1-20 (fest im Code, NICHT in sender.txt): Titel aus der
   öffentlichen DYN-API (Handball/Tischtennis + Basketball NCAA/BBL/
   BBL-Pokal).

Alle Quellen degradieren bei jedem Fehler (Netzwerk, kein Treffer, kaputte
Daten) graceful auf die normale generische EPG-Generierung - nie ein
Absturz des gesamten Laufs. Details, Sonderfälle und die komplette
Fallgeschichte zu jeder Quelle: `docs/HISTORIE.md`.

## Bekannter offener Fall

`HR|SPORT KLUB 1` zeigt in TiviMate gelegentlich falsches Programm
("Container Wars", ein deutscher Sender) - unsere generierte XML ist
nachweislich sauber (verifiziert per `xml.etree.ElementTree`), vermutlich
eine verwaiste alte Kanal-Bindung in TiviMates lokaler Datenbank. Nutzer
möchte die EPG-Quelle NICHT komplett neu anlegen (Risiko, alte
Zuordnungen zu verlieren) - bewusst offen gelassen, kein weiterer
Code-Fix ohne neue Evidenz. Details: `docs/HISTORIE.md`.
