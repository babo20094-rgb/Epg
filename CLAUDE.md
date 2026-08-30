# Hinweise für Claude

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

## Workflow manuell starten

Der GitHub-Actions-Workflow "Update EPG"
(`.github/workflows/update_epg.yml`, `workflow_dispatch`) wird **nur** nach
direkter, expliziter Anweisung des Nutzers ausgelöst (z. B. "starte den
Workflow") — niemals automatisch oder proaktiv, auch nicht direkt nachdem
gemeinsam etwas am Skript geändert wurde, solange der Nutzer nicht
ausdrücklich danach fragt.

## Neue Sender in sender.txt

Der Nutzer schreibt seine Playlist-Kanalnamen durchgängig in
GROSSBUCHSTABEN (z. B. "US| NBC SPORTS BAY AREA HD"). Diese
Großschreibung gilt NUR für den Sendernamen, den Claude ihm im Chat zum
Kopieren für seine Playlist ausgibt (und entsprechend für das 4. Feld
bei TVPASSPORT:/SKY: etc., wenn es genau diesen Playlist-Namen abbildet
- muss ja zum Playlist-Eintrag passen). Das Suchbegriff-Feld (2. Feld,
Name bei der externen EPG-Quelle) bleibt immer in der Original-
Schreibweise der Quelle (TVPassport, Sky usw.).

Alles andere bleibt UNVERÄNDERT wie bisher dokumentiert - insbesondere
die generische Beschreibung bei Sendern ohne echte Quelle (`Land|
Sender|Beschreibung ᴸⁱᵛᵉ|Logo`, siehe unten): Das Beschreibungsfeld
bleibt weiterhin normale Schrift/Title Case + `ᴸⁱᵛᵉ`, NICHT
großgeschrieben.

Neue Sender werden immer **ganz oben** in `sender.txt` eingefügt (nicht ans
Ende anhängen), außer der Nutzer nennt explizit eine andere Stelle
(z. B. "unter diesem Header einordnen").

Bevor ein neuer Sender eingetragen wird, IMMER zuerst prüfen, ob eine
echte EPG-Quelle (Pluto TV/tvmovie.de automatisch bei Land `DE`, sonst
gezielt `MAGENTA:`, `SKY:`, `TVGUIDE:`, `TVPASSPORT:`, `DAZN:`,
`ARENA:`, `FREEVIEW:` je nach Land/Anbieter) für den Sender echte
Programmdaten liefert (z. B. per `*_kanal_finden()`/`*_hole_programme()`
lokal testen). Erst danach wird die Zeile mit dem passenden Präfix
eingetragen — nicht blind als einfacher `Land|Sender`-Eintrag, wenn ein
Präfix mit echten Daten möglich wäre. Kein pauschales automatisches
Durchsuchen ALLER Quellen für jeden `DE|`-Sender (bewusst nicht gebaut -
zu hohe Laufzeit/Fehltreffer-Risiko bei der großen Zahl an DE-Zeilen),
sondern gezielt pro Sender auf Zuruf.

**Ausnahme (Direktauftrag ohne Quellenprüfung):** Gibt der Nutzer einen
neuen Header/Kategorienamen UND die Sendernamen direkt vor (z. B. "lege
unter dem Header X diese Sender an: ..."), wird OHNE Prüfung auf echte
EPG-Quellen eingetragen — als normale Zeile `Land|Sender|Beschreibung
ᴸⁱᵛᵉ|Logo` (Beschreibung = Sendername in Title Case + `ᴸⁱᵛᵉ`, wie im
Abschnitt unten beschrieben), direkt unter einem neuen `##### <Header>
#####`-Kommentarzeilen-Header, außer der Nutzer nennt eine andere
Einfügestelle. Die Quellenprüfung wird nur dann trotzdem durchgeführt,
wenn der Nutzer explizit **PRÜFE AUF ECHTE PROGRAMMDATEN** schreibt.

Findet sich für einen neuen Sender KEINE echte EPG-Quelle, wird er als
normale Zeile `Land|Sender|Beschreibung ᴸⁱᵛᵉ|Logo` eingetragen -
Beschreibungsfeld immer der Sendername in normaler Schrift (Title
Case) mit `ᴸⁱᵛᵉ` am Ende, automatisch und ohne Rückfrage, damit der
Sendername im EPG-Raster erscheint statt eines leeren generischen
Kategorietexts. Nur wenn der Nutzer explizit ein anderes Unicode-Suffix
statt `ᴸⁱᵛᵉ` nennt, wird stattdessen das verwendet.

## Kuerzung echter Titel/Beschreibungen (alle echten Quellen, ausser DYN PPV)

- Der Nutzer will im EPG-Raster NUR den kompakten Sendungs-/Spieltitel
  sehen (z. B. "Probuđena srca" oder "Fudbal - Španska liga: Betis -
  Real Sociedad"), NICHT die oft mehrsaetzigen Liga-/Ankuendigungstexte,
  die manche echten Quellen (v. a. Telemachs "shortDescription") an den
  eigentlichen Titel anhaengen.
- `kuerze_beschreibung(text)` in `generate_epg.py` erledigt das
  zentral fuer ALLE echten Quellen (Telemach, mtel.ba, mts.rs,
  MojMaxTV, Sky, Magenta, Arena, DAZN, TVGuide, TVPassport, Pluto TV,
  tvmovie.de, hoerzu.de, Tubi TV, klix.ba, mymedia.ba) ueber die eine
  gemeinsame Funktion `_schreibe_echte_programme()` - wird sowohl auf
  `title` als auch auf `beschreibung`/`desc` angewendet. DYN PPV hat
  eine eigene, davon unabhaengige Team-vs-Team-Logik (siehe oben) und
  ist ausgenommen.
- Vorgehen: Text wird an ": " aufgeteilt; jedes abschliessende Segment,
  das wie ein ausformulierter Erklaersatz aussieht (grossgeschrieben,
  endet mit Satzzeichen, >= 6 Woerter, siehe
  `_wirkt_wie_ausformulierter_satz()`), wird entfernt - so bleiben nur
  kompakte Kern-Segmente (Kategorie/Liga/Teams/Datum) uebrig, egal wie
  die jeweilige Quelle formatiert. Ohne Doppelpunkt-Struktur (reiner
  Fliesstext) greift ein Satzende-Fallback (erster vollstaendiger Satz).
  Ohne beides wird bei sehr langen Texten hart bei einer Wortgrenze
  abgeschnitten ("…" angehaengt). Kurze Texte bleiben unveraendert.
- WICHTIG: `_schreibe_echte_programme()` schreibt bewusst KEIN
  `<sub-title>`-Tag mehr. Manche Player (TiviMate) haengen den
  Untertitel im kompakten Wochenraster direkt hinter den (bereits
  gekuerzten) Titel an, wodurch trotz Kuerzung wieder ein langer Text
  in der Zeile stand - das war die eigentliche Ursache eines
  hartnaeckigen Bugs, nicht die Kuerzungslogik selbst. Die volle
  Beschreibung bleibt weiterhin im `<desc>`-Feld (Detailansicht).
- Bei Aenderungen an dieser Logik immer `python3 -m pytest
  test_generate_epg.py` laufen lassen (90 Tests, u. a.
  `test_arena_hr_erfolgreicher_abruf_liefert_echte_sendungen` prueft
  explizit, dass Titel/Beschreibung bei Arena HR NICHT vertauscht sind
  - frueher gab es dort einen absichtlichen, aber fehlerhaften Tausch
  in `arena_epg.py`, der den langen Blurb faelschlich zum `<title>`
  machte; wurde entfernt).

## Nummerierte/einheitliche Logos fuer Sender-Gruppen

- Wenn der Nutzer fuer eine Gruppe gleichartiger Sender (z. B. DYN PPV
  1-50, Vodafone GO 1-53, Sky Select 1-8, MAX TV Select 1-6, PLEX-
  Varianten, Sky Sport 1-14/Austria/Bundesliga) ein "einheitliches Logo
  mit der jeweiligen Nummer" wünscht, wird das Basis-Logo einmal
  bearbeitet (Firmen-/Sender-Wordmark, ggf. freigestellt/aufgehellt)
  und dann per Skript für jede Nummer eine eigene PNG-Datei erzeugt.
- Alle generierten Logo-Sets liegen unter `logos/<name>/<name>_<N>.png`
  (z. B. `logos/dyn_ppv/dyn_ppv_23.png`, `logos/sky_sport/sky_sport_4.png`)
  und werden ueber die raw.githubusercontent.com-URL
  (`https://raw.githubusercontent.com/babo20094-rgb/Epg/main/logos/...`)
  in `sender.txt` eingetragen. Design-Feedback (Groesse, Farbe,
  Positionierung, Farbverlauf passend zum Original) wird immer erst an
  1-2 Beispielen gezeigt und bestaetigt, bevor alle Nummern erzeugt und
  eingetragen werden.
- "Logo kann aus Playlist übernommen werden" (wörtliche Nutzer-Formulierung)
  heisst: Logo-Feld in `sender.txt` leer lassen, NICHT das Logo selbst
  heraussuchen - der Nutzer übernimmt es aus seiner eigenen Playlist.

## Logo-Groesse (August 2026 optimiert)

- Mehrere Logo-Sets (`logos/dyn_ppv/`, `logos/sky_select/`,
  `logos/vodafone_go/`, `logos/plex/`, `logos/maxtv_select/`,
  `logos/balkan_sky.png`) waren fuer ein kleines TV-Guide-Icon massiv
  ueberdimensioniert (DYN PPV z.B. 1920x540px Full-HD-Banner-Groesse,
  MAX TV Select trotz nur 250x250px durch schlechte Kompression bei
  ~54 KB/Bild) - das sorgte im Player sichtbar fuer langsames,
  nacheinander erfolgendes Laden der Sender-Logos.
- Alle Logos wurden auf max. 300px Kantenlaenge verkleinert (Pillow
  `Image.resize()`, `Image.LANCZOS`) UND zusaetzlich auf eine
  256-Farben-Palette quantisiert (`Image.quantize(colors=256,
  method=Image.FASTOCTREE)` fuer RGBA/Transparenz, `MEDIANCUT` fuer
  RGB) - bei so kleinen Icons visuell nicht wahrnehmbar, aber massiv
  kleinere Dateigroesse bei fotografischen/farbreichen Logos (teils
  75-98% Ersparnis). Bei neuen nummerierten Logo-Sets (siehe Abschnitt
  oben) diese Groessen-/Kompressionsregel von Anfang an anwenden, statt
  spaeter nachtraeglich optimieren zu muessen.
- `HR|SK 1-10` liefen zusaetzlich extern ueber tvprofil.com (teils
  riesige Originaldateien, SK2 z.B. 3560x1888px/1,1 MB) - wurden
  heruntergeladen, genauso optimiert und liegen jetzt selbst gehostet
  unter `logos/hr_sk/sk_<N>.png`. Bei weiteren extern verlinkten
  Logos mit auffaellig langer Ladezeit im Player gleiches Vorgehen
  (herunterladen, optimieren, unter `logos/<name>/` selbst hosten,
  sender.txt-URL auf raw.githubusercontent.com umstellen) in Betracht
  ziehen, statt nur den externen Host zu verlinken.

## Architektur-Überblick

`generate_epg.py` liest `sender.txt` (Format `Land|Sender|Beschreibung|Logo`,
oder `NAME:<exakter Kanalname>|Logo` für Sender, deren echter Playlist-Name
selbst Pipe-Zeichen enthält) und erzeugt daraus `Epg_365_Tage.xml`.
`epg_lib.py` enthält die Kategorie-/Sprach-/Text-Logik. Der
GitHub-Actions-Workflow `update_epg.yml` läuft alle 4h automatisch und bei
manuellem Trigger.

## Luecken-Fuellung bei teilweiser Ueberlappung mit echten Programmdaten

- Fuer Sender mit einer aktiven echten EPG-Quelle (Telemach/mtel.ba/
  mymedia.ba/klix.ba, SKY:, MAGENTA:, ARENA:, DAZN:, FREEVIEW:, TVGUIDE:,
  TVPASSPORT:, Pluto TV/tvmovie.de/hoerzu.de, mts.rs, MojMaxTV,
  tv-spored.siol.net, Tubi TV) wird im generischen Tagesraster (siehe
  unten) fuer jeden Zeitblock geprueft, ob er mit echten Programmdaten
  ueberlappt (`hat_aktive_echte_quelle()` / `alle_echten_intervalle()`).
- Frueher (bis August 2026) wurde ein Block komplett uebersprungen, sobald
  er auch nur TEILWEISE mit echten Daten ueberlappte - endete z.B. die
  letzte echte Sendung (Pluto TV/tvmovie.de) mitten in einem mehrstuendigen
  Block, bekam der unbedeckte Rest gar keinen `<programme>`-Eintrag mehr.
  Das zeigte sich im Player (z.B. TiviMate) als sichtbare "Keine
  Information"-Luecke zwischen der letzten echten Sendung und dem
  naechsten generischen Block (beobachtet z.B. bei RTL Crime).
- Behoben: `segmente_ohne_ueberlappung()` (urspruenglich nur fuer die
  DYN-PPV-Leerzeiten genutzt) schneidet aus dem Zeitblock jetzt praezise
  nur den tatsaechlich unbedeckten Rest heraus. Dieser Rest wird mit
  "`<Sendername>` ᴸⁱᵛᵉ" gefuellt statt des generischen, abwechslungsreichen
  Kategorietexts - komplett abgedeckte Bloecke bleiben unveraendert leer
  (keine Duplikate ueber echte Daten), komplett unbedeckte Bloecke
  bekommen wie bisher den ganzen Block als "`<Sendername>` ᴸⁱᵛᵉ"-Platzhalter.
- Betrifft automatisch ALLE Sender mit einer der obigen echten Quellen,
  keine sender.txt-Aenderung noetig.

## WICHTIG: Zwei komplett getrennte DYN-Sport-Kategorien - nicht verwechseln!

Es gibt ZWEI unabhaengige "DYN Sport"-Kanal-Gruppen im Repo - bei
Fragen/Fixes zu "DYN Sport" IMMER zuerst klaeren, welche der beiden
gemeint ist, statt anzunehmen:

1. **DYN PPV 1-50** (`NAME:`-Zeilen in `sender.txt`, Kanal-ID/Kern
   z.B. "DE: DYN PPV 3"): Bekommt Sendungstitel aus dem ECHTEN,
   sich aendernden Live-Kanalnamen der eigenen IPTV-Playlist des
   Nutzers (`PROVIDER`-Secret, `m3u_playlist_abgleichen()`).
   Deckt ALLE Sportarten ab, die der Anbieter selbst im Kanalnamen
   nennt - keine Einschraenkung auf bestimmte Ligen/Sportarten.
   Siehe Abschnitt "DYN PPV / Live-Kanalname-Mechanismus" unten.
2. **DYN PPV 1-20** (fest im Code als `DE| DYN PPV {i} HD`, NICHT in
   `sender.txt`): Bekommt Sendungstitel aus der oeffentlichen DYN-API
   (`streaming.contentdesk.sport`), komplett unabhaengig von der
   Playlist des Nutzers. Deckt bisher nur Handball/Tischtennis
   (`/public/live-productions`) sowie zusaetzlich Basketball
   (`/public/competitions/{id}/matches`, nur NCAA College Basketball/
   easyCredit BBL/Netto BBL Pokal - explizit auf Nutzerwunsch NUR
   diese drei, keine weiteren Sportarten/Wettbewerbe) ab. Siehe
   Abschnitt "DYN PPV: Echte API-Daten (1-20, getrennt von den
   Playlist-Sendern 1-50)" unten.

Beide Gruppen nutzen zufaellig denselben Namen "DYN PPV" und liegen im
selben Zahlenbereich (1-20 bzw. 1-50) - das ist die Hauptquelle fuer
Missverstaendnisse. Meldet der Nutzer "kein Event, nur Platzhalter",
IMMER nachfragen bzw. anhand des Kontexts (Playlist-Kanalname sichtbar
vs. reine EPG-Beobachtung) klaeren, welche der beiden gemeint ist,
bevor an der falschen Stelle gesucht wird.

## DYN PPV / Live-Kanalname-Mechanismus

- DYN PPV 1-50 und andere `NAME:`-Sender bekommen ihren Sendungstitel
  automatisch aus dem echten, aktuellen Live-Kanalnamen - ausgelesen aus
  der eigenen IPTV-Playlist des Nutzers (Secret `PROVIDER`,
  optional), statt aus einem geratenen API-Round-Robin.
- `m3u_playlist_abgleichen()` liest die `#EXTINF`-Anzeigenamen der
  M3U-Playlist und matcht sie ueber den Kernnamen gegen die `NAME:`-Sender
  aus `sender.txt`.
- **Leerlauf-Standardtext (WICHTIG, August 2026 behoben):** JEDER
  `NAME:`-Sender ohne erkanntes Live-Event (kein gesetztes
  `PROVIDER`-Secret, kein Playlist-Treffer, oder schlicht
  kein bekanntes Anbieter-Muster wie DYN PPV/DirtVision/Flo Racing/FA
  Player/Super League Plus) zeigt automatisch "`<Kurzname>` ᴸⁱᵛᵉ" -
  EXAKT dieselbe Konvention wie bei normalen `Land|Sender|Beschreibung
  ᴸⁱᵛᵉ|Logo`-Zeilen ohne echte Quelle. Frueher fiel ein `NAME:`-Sender
  ohne eines der hartcodierten Anbieter-Muster (z. B. neu angelegte
  Sender wie "Premier League+ 1") stattdessen auf den generischen,
  kategoriebasierten Zufallstext zurueck (z. B. "Sport den ganzen Tag
  auf Premier League+ 1" mit wechselnden Sport-Phrasen) - das war ein
  Bug, kein gewolltes Verhalten, und wurde durch einen zentralen
  Catch-all in `generate_epg.py` behoben. Gilt automatisch fuer JEDEN
  neuen `NAME:`-Sender, keine Sonderbehandlung pro Anbieter noetig.
- Frueher gab es zusaetzlich einen Fallback auf eine separate
  Anbieter-Datei (myepg.top, Secrets `DYN_EPG_PROVIDER_URL`/`_EU`) - der
  wurde entfernt, da die eigene Playlist vollstaendiger und aktueller
  ist (z. B. bei Clubber: myepg.top kannte oft nur 1 von 50 Kanälen,
  die Playlist alle 50) und der Fallback in der Praxis nie noch etwas
  beigetragen hat.
- DYN PPV zeigt bei Leerlauf (kein erkanntes Event, z.B. Anbieter-
  Platzhaltertext "- NO EVENT STREAMING - | 8K EXCLUSIVE") NICHT mehr
  den rohen Platzhaltertext, sondern "Dyn Sport (N) ᴺᵒ ᴸⁱᵛᵉ" (N = Kanal-
  Nummer 1-50) - gleiche Konvention wie bei DirtVision/Flo Racing.
- Status-Marker im rohen Kanalnamen ("NEXT | ...", "LIVE | ...",
  "ENDED | ...") werden erkannt: Bei NEXT/LIVE zeigt das EPG-Raster NUR
  die extrahierten Team-/Gegnernamen plus Uhrzeit (z. B. "Deutschland
  vs. Guinea 18:10 Uhr ᴸⁱᵛᵉ" bzw. mit ᴺᵉˣᵗ/ᴸⁱᵛᵉ-Suffix je nach Marker,
  siehe `dyn_next_team_namen()`) - kein Rohdatum/Zeitzone/Zusatztext und
  KEIN "Dyn Sport (N)"-Praefix mehr. Bei ENDED (und ohne erkennbares
  Event) faellt es auf den generischen Leerlauf-Text "Dyn Sport (N)
  ᴺᵒ ᴸⁱᵛᵉ" zurueck statt eines festen Abmoderationstexts - ENDED wird
  also wie Leerlauf behandelt, nicht wie ein eigenes Event.
- **Bug August 2026 behoben:** `_live_event_uebernehmen()` setzte bei
  ENDED den `event_titel` faelschlich auf `None` statt den beim
  Einlesen bereits gesetzten Fallback ("Dyn Sport (N) ᴺᵒ ᴸⁱᵛᵉ")
  unveraendert zu lassen - der Kommentar im Code sagte zwar "Fallback
  bleibt stehen", das tatsaechliche Verhalten loeschte ihn aber. Das
  EPG-Raster zeigte dadurch bei ENDED faelschlich den generischen
  kategoriebasierten Zufallstext (z.B. "Sportarena: Immer aktuell:
  Sport auf DYN PPV 1") statt "Dyn Sport (1) ᴺᵒ ᴸⁱᵛᵉ". Jetzt verlaesst
  die Funktion bei ENDED fruehzeitig, ohne `real_daten["event_titel"]`
  zu ueberschreiben.
- Komplett großgeschriebene Wörter im Event-Text werden normalisiert
  (z. B. "8K EXCLUSIVE" -> "8K Exclusive"), damit es nicht "schreit".
- Kategorie-Erkennung (`epg_lib.py`, `standard_beschreibung()`) nutzt
  Wortgrenzen (`\b...\b`) statt reinem Teilstring-Vergleich, um
  Fehlzuordnungen zu vermeiden (z. B. "LOVE AND MARRIAGE" matchte früher
  fälschlich das Kurz-Keyword "LOV" der Kategorie Jagd & Angeln).
- Generische Sendetitel enthalten keinen Wochentag/kein Datum mehr, nur
  noch Event- bzw. Kategorietext.
- Der Mechanismus deckt zwei Namenskonventionen ab: Kern-HINTEN (DYN PPV,
  Flo Racing - Kern nach dem letzten Pipe) und Kern-VORNE (Clubber-PPV,
  Irland/GAA - Kern vor dem ersten Pipe, z. B. "(IE) (Clubber 01) | Kerry
  GAA: ..."). `m3u_playlist_abgleichen()` probiert bei einem Sender
  automatisch beide Konventionen durch (`kern_und_event_extrahieren()` /
  `kern_vorne_und_event_extrahieren()`), bevor er den Kanal als
  "kein Treffer" überspringt.

## DYN PPV: Echte API-Daten (1-20, getrennt von den Playlist-Sendern 1-50)

- **Nicht zu verwechseln mit DYN PPV 1-50 oben** (siehe Warnhinweis
  weiter oben) - diese 20 Kanaele (`DE| DYN PPV 1 HD` bis `DE| DYN PPV
  20 HD`) sind fest im Code definiert, stehen NICHT in `sender.txt` und
  bekommen ihre Sendungstitel unabhaengig von der Nutzer-Playlist direkt
  aus der oeffentlichen DYN-API (`streaming.contentdesk.sport`).
- Haupt-Endpunkt `/public/live-productions` liefert bisher nur Handball
  und Tischtennis - andere Sportarten (Basketball, Volleyball,
  Feldhockey) fehlen dort komplett, auch wenn DYN sie tatsaechlich
  streamt (z. B. Sonderwettbewerbe wie der "Rexel Super Cup" haben oft
  keine "liveProduction"-Verknuepfung und tauchen deshalb dort nicht
  auf, obwohl das Spiel laut `/public/competitions/{id}/matches`
  existiert und live laeuft).
- Auf ausdruecklichen Nutzerwunsch wird NUR Basketball zusaetzlich
  nachgeladen (August 2026) - ueber `/public/competitions/{id}/matches`
  fuer genau drei Wettbewerbe: NCAA College Basketball, easyCredit BBL,
  Netto BBL Pokal (Competition-IDs siehe `DYN_BASKETBALL_COMPETITION_IDS`
  in `generate_epg.py`). KEINE weiteren Sportarten/Wettbewerbe (kein
  Volleyball, Feldhockey, weitere Handball-/Tischtennis-Wettbewerbe) -
  das will der Nutzer bewusst nicht.
- Diese Competitions-API liefert keine Endzeit, nur den Anstoss - es
  wird pauschal eine 2h-Spieldauer angenommen (`DYN_BASKETBALL_SPIELDAUER`).
  Nur Spiele in den naechsten 14 Tagen werden uebernommen
  (`DYN_BASKETBALL_VORSCHAU_TAGE`), da die API teils Spielplaene fuer
  Monate im Voraus liefert.
- Beide API-Quellen (Live-Productions + Basketball-Competitions)
  schreiben rundenweise (Round-Robin) auf dieselben 20 Kanaele, unter
  Beachtung von `dyn_synth_api_fenster` fuer die Leerzeiten-Luecken-
  Fuellung (siehe DYN-Leerzeiten-Abschnitt in `generate_epg.py`).
  Degradiert bei jedem Fehler (Netzwerk, einzelner Wettbewerb nicht
  erreichbar) graceful auf den generischen Platzhalter fuer die
  betroffenen Kanaele/Wettbewerbe - kein Abbruch des gesamten Laufs.

## TELEMACH:-Sender (echte Programmdaten, opt-in)

- Jeder ganz normal eingetragene Sender mit Land `BA` oder `ME` in
  `sender.txt` (z. B. `BA|BHT 1||AUTO`) wird automatisch beim
  Generieren per Name gegen die Telemach-Kanalliste geprueft - kein
  eigenes Prefix noetig. Bei Treffer gibt's echte Programmdaten statt
  der generischen Kategorie-Platzhaltertexte, bei keinem Treffer oder
  Fehler unveraendert die normale generische Beschreibung.
- Zusaetzlich gibt es weiterhin `TELEMACH:<Land BA oder ME,
  optional>|<Kanalname wie bei Telemach>|<Logo-URL>` (z. B.
  `TELEMACH:BA|BHT 1|https://example.com/logo.png`) fuer Sender, die
  in der eigenen Playlist unter einem anderen Namen laufen als bei
  Telemach - der Kanalname hier ist gezielt der Telemach-Suchbegriff,
  unabhaengig vom sonstigen Playlist-Namen.
- Login, Kanalsuche (`telemach_kanal_finden()`, exakt dann fuzzy per
  `difflib`) und Programmabruf (`telemach_hole_programme()`, bis zu 3
  Tage) laufen in `telemach_epg.py` und degradieren bei jedem Fehler
  (Netzwerk, kein Kanal-Treffer, keine Daten) graceful auf die normale
  generische EPG-Generierung fuer diesen Sender - Tage 4-365 sind
  ohnehin immer generisch.
- Fuer BA-Sender (Bosnien, keine Montenegro-Variante) gibt es zusaetzlich
  `mtel.ba` als zweite echte EPG-Quelle (`mtel_epg.py`): findet Telemach
  fuer einen Sender gar nichts (kein Kanal-Treffer oder keine
  Programmdaten), wird mtel.ba automatisch als zweiter Versuch probiert,
  bevor es auf die generische Beschreibung zurueckfaellt. Gleiche
  Zero-Risk-Garantie wie bei Telemach: jeder Fehler (Netzwerk, kein
  Treffer, kaputtes JSON) degradiert still auf die normale generische
  EPG-Generierung, kein neues sender.txt-Praefix noetig.
- Der Namensabgleich fuer mtel.ba (`mtel_kanal_finden()`) wird zusaetzlich
  um eine statische Namenserweiterung ergaenzt (`mtel_kanalliste.txt`,
  ~500 Eintraege, aus der offiziellen iptv-org/epg-Kanalliste fuer
  mtel.ba extrahiert, Zeilenformat "<platform>#<code>|<Name>") - kostet
  keinen zusaetzlichen Netzwerk-Request, greift nur dort, wo der
  Live-Kanalabruf einen Namen (noch) nicht liefert; bei Ueberschneidung
  hat der Live-Eintrag immer Vorrang.

## mts.rs (Serbien, automatisch)

- Echte Programmdaten von mts.rs (`mts_epg.py`, oeffentliche Hybris-
  Ecommerce-API, kein Login) gibt es AUTOMATISCH fuer jeden ganz normal
  eingetragenen Sender mit Land `RS` in `sender.txt` - kein eigenes
  Praefix noetig, gleiches Prinzip wie der BA/ME-Telemach-Autoabgleich.
  Bei aktuell ~60 RS-Zeilen ist das Volumen an zusaetzlichen API-
  Aufrufen pro Lauf ueberschaubar (analog zur BA/ME/MK-Begruendung).
- Kanalsuche (`mts_kanal_finden()`, exakt dann fuzzy per `difflib`) und
  Programmabruf (`mts_hole_programme()`, bis zu 2 Tage) degradieren bei
  jedem Fehler (Netzwerk, kein Kanal-Treffer, keine Daten) graceful auf
  die normale generische EPG-Generierung fuer diesen Sender.

## MojMaxTV (Kroatien, automatisch)

- Echte Programmdaten von MojMaxTV/Hrvatski Telekom
  (`mojmaxtv_epg.py`, signierte, aber loginfreie API) gibt es
  AUTOMATISCH fuer jeden ganz normal eingetragenen Sender mit Land `HR`
  in `sender.txt` - kein eigenes Praefix noetig, gleiches Prinzip wie
  der BA/ME-Telemach-Autoabgleich. Bei aktuell ~42 HR-Zeilen ist das
  Volumen an zusaetzlichen API-Aufrufen pro Lauf ueberschaubar.
- Kanalsuche und Programmabruf (bis zu 2 Tage, ohne Programm-Detail-
  Nachladung wie sub_title/season/episode) degradieren bei jedem
  Fehler (Netzwerk, kein Kanal-Treffer, keine Daten) graceful auf die
  normale generische EPG-Generierung fuer diesen Sender.

## tv-spored.siol.net (Slowenien, automatisch)

- Echte Programmdaten von tv-spored.siol.net (`siol_epg.py`) gibt es
  AUTOMATISCH fuer jeden ganz normal eingetragenen Sender mit Land `SI`
  in `sender.txt` - kein eigenes Praefix noetig, gleiches Prinzip wie
  der BA/ME-Telemach-Autoabgleich. Bei aktuell nur ~2 SI-Zeilen ist das
  Volumen minimal.
- Anders als die anderen echten EPG-Quellen dieses Repos gibt es hier
  keine stabile JSON-API, sondern HTML-Scraping eines in <script>-Tags
  eingebetteten Next.js-JSON-Payloads - das ist prinzipiell deutlich
  anfaelliger fuer Breaking Changes bei einem Website-Redesign als
  Telemach/mtel/mts.rs/MojMaxTV. Degradiert aber nach derselben Zero-
  Risk-Garantie bei jedem Fehler (Netzwerk, kein Kanal-Treffer,
  unerwartete Seitenstruktur) still auf die normale generische EPG-
  Generierung fuer diesen Sender.

## TVPASSPORT:-Sender (tvpassport.com US, opt-in)

- Echte Programmdaten von tvpassport.com (`tvpassport_epg.py`) gibt es
  NUR ueber das explizite Praefix `TVPASSPORT:<Land, nur "US"
  unterstuetzt/optional>|<Kanalname wie bei TVPassport>|<Logo-URL>`, z. B.
  `TVPASSPORT:US|FOX (KFFX) Yakima, WA|https://example.com/logo.png`.
  Im Unterschied zu TVGuide.com (nur EINE feste nationale
  Grundaufstellung, siehe TVGUIDE:-Abschnitt oben) deckt tvpassport.com
  gezielt LOKALE US-Affiliate-Sender pro Stadt/Call-Sign ab und ergaenzt
  damit TVGuide.com fuer genau die Art lokaler Sender-Zeilen, die in
  dieser sender.txt haeufig vorkommen.
- Bewusst KEIN automatisches Matching wie bei BA/ME (Telemach/mtel) -
  genau wie bei TVGUIDE:/SKY:/DAZN:/FREEVIEW:: reines Opt-in ueber die
  explizite Zeile.
- Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
  (`tvpassport_kanalliste.xml`, ~19.000 Eintraege, eine Kopie der
  bereits vom iptv-org/epg-Projekt gecrawlten tvpassport.com-Kanalliste)
  statt live alle Seiten zu crawlen - das kostet keinen einzigen
  Netzwerk-Request fuer die Kanalsuche selbst, nur der eigentliche
  Programmabruf fuer tatsaechlich getroffene Kanaele geht live. Die
  Datei sollte gelegentlich manuell aus dem iptv-org/epg-Projekt
  aktualisiert werden, falls sich Sender-Seiten dort aendern - das
  passiert hier nicht automatisch.
- Da hier HTML statt einer stabilen JSON-API geparst wird
  (`BeautifulSoup`), ist die Programmabruf-Quelle prinzipiell
  anfaelliger fuer Breaking Changes bei einem Website-Redesign als z. B.
  Telemach/mtel/mts.rs - degradiert aber nach derselben Zero-Risk-
  Garantie bei jedem Fehler (Netzwerk, kein Kanal-Treffer, unerwartete
  HTML-Struktur) still auf die normale generische EPG-Generierung fuer
  diesen Sender.
- WICHTIG (August 2026 behoben): Die Kanalseiten-URL braucht zwingend
  die numerische Kanal-ID aus der site_id im Pfad
  (`stations/<slug>/<numerische-id>/<datum>`). Frueher baute der Code
  die URL nur aus Slug+Datum ohne ID - die Website leitete das seit
  einem Redesign OHNE Fehler auf eine generische Platzhalterseite um
  ("PT CHECK: Global BC"), die faelschlich als echte, kanalspezifische
  Daten geparst wurde (ALLE TVPASSPORT:-Sender bekamen dadurch
  identische, falsche Sendungen statt eines sauberen Fallbacks auf
  generisch). Falls sowas nochmal auftritt (z. B. nach einem erneuten
  Website-Redesign): Testweise `_tag_seite_holen()`/die erzeugte URL
  pruefen, ob der Seitentitel wirklich zum angefragten Kanal passt -
  identische Sendungen bei unterschiedlichen Kanaelen sind das
  Alarmsignal.

## MAGENTA:-Sender (Magenta TV, opt-in)

- Echte Programmdaten von Magenta TV (Deutsche Telekom, `magenta_epg.py`)
  gibt es NUR ueber das explizite Praefix `MAGENTA:<Territory, nur "DE"
  unterstuetzt/optional>|<Kanalname wie bei Magenta/eigener Playlist>|<Logo-
  URL>`, z. B. `MAGENTA:DE|RTL|https://example.com/logo.png`.
- Bewusst KEIN automatisches Matching wie bei BA/ME (Telemach/mtel) -
  genau wie bei SKY: gibt es zu viele DE-Sender-Zeilen in sender.txt,
  das waeren zu viele API-Aufrufe pro Lauf und ein zu hohes
  Fehltreffer-Risiko.
- Intern werden zwei Magenta-Quellen verkettet probiert (analog zum
  Telemach->mtel.ba-Fallback): zuerst die neuere www.magenta.tv-API
  (MPX-Feed-basiert, keine Anmeldung noetig), bei keinem Kanal-Treffer
  oder keinen Programmdaten als zweiter Versuch die aeltere
  web.magentatv.de-API (Cookie/CSRF-JSON).
- Degradiert bei jedem Fehler (Netzwerk, kein Kanal-Treffer bei beiden
  Quellen, keine Daten) graceful auf die normale generische
  EPG-Generierung, kein Absturz moeglich - Tage 3-365 sind ohnehin
  immer generisch.

## DAZN:-Sender (DAZN, opt-in)

- Echte Programmdaten von DAZN (`dazn_epg.py`, Rail-API) gibt es NUR ueber
  das explizite Praefix `DAZN:<Land, 2-Buchstaben-Laendercode,
  optional/Default "DE">|<Kanalname wie bei DAZN>|<Logo-URL>`, z. B.
  `DAZN:DE|DAZN 1 HD|https://example.com/logo.png`.
- Bewusst KEIN automatisches Matching wie bei BA/ME (Telemach/mtel) -
  genau wie bei SKY/MAGENTA: reines Opt-in ueber die explizite Zeile.
- Anders als Sky (nur "DE") oder Arena (nur HR/RS) akzeptiert DAZN einen
  beliebigen 2-Buchstaben-Laendercode; ein leerer oder ungueltiger Wert
  faellt still auf "DE" zurueck. Die Sprachzuordnung fuer die Anfrage ist
  bewusst vereinfacht: nur de/at/ch/li -> Deutsch, alle anderen Laender
  -> Englisch (kein vollstaendiger Port der Original-Laendertabelle).
- Degradiert bei jedem Fehler (Netzwerk, kein Kanal-Treffer, keine Daten)
  graceful auf die normale generische EPG-Generierung, kein Absturz
  moeglich.
- Wichtige Einschraenkung: DAZNs API liefert kein echtes mehrtaegiges
  Datumsraster, sondern nur ihr aktuelles Now/Next/Later-Fenster - die
  Datenabdeckung ist entsprechend duenn (meist nur die naechsten paar
  Sendungen/Stunden statt mehrerer voller Tage).

## SKY:-Sender (Sky Deutschland/UK, opt-in)

- Echte Programmdaten von Sky (`sky_epg.py`, HAWK-API) gibt es NUR ueber
  das explizite Praefix `SKY:<Territory, "DE" oder "GB",
  optional/Default "DE">|<Kanalname wie bei Sky/eigener Playlist>|<Logo-
  URL>`, z. B. `SKY:DE|Sky Sport Bundesliga 1|https://example.com/logo.png`
  oder `SKY:GB|Sky Showcase|https://example.com/logo.png`.
- "DE" deckt technisch auch Oesterreich/Schweiz mit ab (Sky kennt dafuer
  kein eigenes Territory, "Sky Sport Austria"-Kanaele laufen ueber DE).
  "UK" wird als Alias fuer "GB" akzeptiert. Andere Werte fallen graceful
  auf "DE" zurueck.
- Die erzeugte <channel> id/display-name zeigt bei GB-Sendern bewusst
  immer "UK|..." (nicht "GB|..."), damit sie zur "UK|..."-Konvention der
  eigenen IPTV-Playlist passt und TiviMate automatisch zuordnen kann -
  intern (API-Anfragen an Sky) wird trotzdem immer "GB" verwendet, das
  ist Skys eigener Territory-Code.
- Bewusst KEIN automatisches Matching wie bei BA/ME (Telemach/mtel) -
  dafuer gibt es schlicht zu viele DE/GB-Sender-Zeilen in sender.txt, das
  waeren zu viele API-Aufrufe pro Lauf und ein zu hohes Fehltreffer-
  Risiko.
- Kanalsuche (`sky_kanal_finden()`, exakt dann fuzzy per `difflib`) und
  Programmabruf (`sky_hole_programme()`, bis zu 2 Tage) degradieren bei
  jedem Fehler (Netzwerk, kein Kanal-Treffer, keine Daten) graceful auf
  die normale generische EPG-Generierung - Tage 3-365 sind ohnehin immer
  generisch.
- Nur die Territories "DE"/"GB" und die nicht-UHD-Kanaele (HAWK-API)
  werden unterstuetzt, kein "IT" und keine UHD-Kanaele (Atlantis-API).

**Fallstrick "Sky Cinema Special"/"Sky Cinema Highlights" (August
2026 behoben):** Sky Cinema Special existiert seit April 2024 nicht
mehr als fester, eigenstaendiger Kanal - weder in Skys eigener
HAWK-API-Kanalliste noch bei deswird.org gibt es einen Eintrag mit
genau diesem Namen. Der `difflib`-Fuzzy-Fallback in
`kanal_index_suchen()` (Cutoff 0.72) matchte "Sky Cinema Special"
faelschlich auf den aehnlich benannten, aber inhaltlich komplett
anderen Kanal "Sky Cinema Premiere" (75,7% Aehnlichkeit) - das
EPG-Raster zeigte dadurch das falsche Programm. Die zugrunde liegende,
tatsaechlich existierende Sendung heisst "Sky Cinema Highlights" (bei
deswird.org als exakter Treffer vorhanden) - die betroffenen
sender.txt-Zeilen wurden entsprechend umbenannt (Land bleibt `DE`,
Sendername jetzt "Sky Cinema Highlights FHD"/"HD"/"HEVC" statt
"Special"). **Lehre fuer aehnliche Faelle:** Wenn ein Sender bei KEINER
Quelle einen exakten oder eindeutigen Kern-Treffer findet und nur der
Fuzzy-Fallback greift, immer pruefen, ob der gefundene Kanal inhaltlich
wirklich passt (z.B. per `*_hole_programme()` das aktuelle Programm mit
dem echten Sender/TV-Guide vergleichen), bevor man dem Treffer traut -
aehnliche Namen (Special/Premiere/Highlights, Cinema Special/Premium
usw.) fuehren bei Sky-Cinema-Pop-up-Kanaelen erfahrungsgemaess leicht zu
falschen Treffern.

## ARENA:-Sender (Arena Sport HR/RS, opt-in)

- Echte, HTML-gescrapte Programmdaten von Arena Sport (`arena_epg.py`)
  gibt es NUR ueber das explizite Praefix `ARENA:<Land HR oder RS>|
  <Kanalname, z.B. "Arena Sport 1">|<Logo-URL>`, z. B.
  `ARENA:HR|Arena Sport 1|https://example.com/logo.png`. HR nutzt
  tvarenasport.hr (Kroatisch, Zeitzone Europe/Budapest), RS nutzt
  tvarenasport.com (Serbisch, Zeitzone Europe/Belgrade); unbekannte/
  leere Land-Werte fallen auf HR zurueck.
- Bewusst KEIN automatisches Matching wie bei BA/ME (Telemach/mtel) -
  genau wie bei SKY: nur reines Opt-in ueber die explizite Zeile.
- Da hier HTML statt einer stabilen JSON-API geparst wird
  (`BeautifulSoup`), ist die Quelle prinzipiell anfaelliger fuer
  Breaking Changes bei einem Website-Redesign als Telemach/mtel/Sky -
  degradiert aber nach derselben Zero-Risk-Garantie bei jedem Fehler
  (Netzwerk, kein Kanal-Treffer, unerwartete HTML-Struktur) still auf
  die normale generische EPG-Generierung fuer diesen Sender.

## FREEVIEW:-Sender (Freeview UK, opt-in)

- Echte Programmdaten von Freeview UK (`freeview_epg.py`) gibt es NUR
  ueber das explizite Praefix `FREEVIEW:<Land, nur "GB"/"UK"
  unterstuetzt/optional>|<Kanalname wie bei Freeview>|<Logo-URL>`, z. B.
  `FREEVIEW:GB|BBC One|https://example.com/logo.png`. Die erzeugte
  <channel> id/display-name zeigt bewusst immer "UK|..." (nicht "GB|..."),
  damit sie zur "UK|..."-Konvention der eigenen IPTV-Playlist passt und
  TiviMate automatisch zuordnen kann.
- Bewusst KEIN automatisches Matching wie bei BA/ME (Telemach/mtel) -
  genau wie bei SKY/DAZN: reines Opt-in ueber die explizite Zeile.
- Die Kanalliste stammt aus nur EINER repraesentativen UK-Network-ID
  ("Greater London" statt aller ~169 regionalen IDs des Originals) und
  deckt damit nur nationale Kanaele ab (BBC One, ITV1, Channel 4, Sky-
  Kanaele auf Freeview, ...), keine rein regionalen Lokalnachrichten-
  Opt-outs - eine bewusste Vereinfachung. Ebenso wird keine erweiterte
  Sendungs-Synopsis nachgeladen (kein Extra-Request pro Sendung wie im
  Original), `beschreibung` bleibt daher meist leer.
- Degradiert bei jedem Fehler (Netzwerk, kein Kanal-Treffer, keine
  Daten, unparsbare Sendungsdauer) graceful auf die normale generische
  EPG-Generierung, kein Absturz moeglich.

## mymedia.ba (Sender "MY TV", automatisch)

- Echte, HTML-gescrapte Programmdaten von mymedia.ba/tv-program/
  (`mymedia_epg.py`) gibt es AUTOMATISCH als dritter Fallback nach
  Telemach und mtel.ba (siehe Block oben), aber NUR fuer einen Sender
  mit Namen exakt "MY TV" (Land BA) - kein eigenes Praefix noetig.
- Die Seite deckt technisch nur EINEN einzigen, festen Kanal ab (kein
  Kanal-Verzeichnis, kein Login), daher gibt es hier bewusst keine
  eigene Kanalsuche wie bei den anderen Quellen - die Zuordnung
  passiert per direktem Namensvergleich, nicht per Fuzzy-Match.
- Pro Tag wird die Seite mit `?epg_day=YYYY-MM-DD` einzeln abgerufen
  (bis zu 3 Tage). Da hier HTML statt einer stabilen JSON-API geparst
  wird (`BeautifulSoup`), ist die Quelle prinzipiell anfaelliger fuer
  Breaking Changes bei einem Website-Redesign als Telemach/mtel.ba -
  degradiert aber nach derselben Zero-Risk-Garantie bei jedem Fehler
  (Netzwerk, unerwartete HTML-Struktur) still auf die normale
  generische EPG-Generierung.

## klix.ba (Bosnien, automatisch)

- Echte Programmdaten von klix.ba (`klix_epg.py`, oeffentliche,
  loginfreie JSON-API) gibt es AUTOMATISCH als vierter Fallback fuer
  BA-Sender, nach Telemach/mtel.ba/mymedia.ba (siehe Bloecke oben) -
  kein eigenes sender.txt-Praefix noetig.
- Die Kanalsuche nutzt eine im Repo mitgelieferte statische Datei
  (`klix_kanalliste.txt`, ~55 Eintraege, aus der Original-Kanalliste
  des WebGrab+Plus-Site-Plugins "klix.ba" extrahiert, Zeilenformat
  "<site_id>|<Name>") statt live zu crawlen - kein Netzwerk-Request
  fuer die Kanalsuche selbst, nur der eigentliche Programmabruf fuer
  tatsaechlich getroffene Kanaele geht live.
- Pro Kanal/Tag wird `api.klix.ba/v1/tvprogram/<id>?datum=YYYY-MM-DD`
  einzeln abgerufen (bis zu 3 Tage). Die API liefert nur Startzeiten -
  die Endzeit einer Sendung wird aus der Startzeit der naechsten
  Sendung berechnet (letzte Sendung des Tages endet um Mitternacht),
  analog zu arena_epg.py/mymedia_epg.py. Eine ausfuehrliche
  Beschreibung gibt es laut Original-Plugin nur ueber einen
  zusaetzlichen Detailseiten-Abruf pro Sendung - wird hier bewusst
  NICHT nachgeladen (kein Extra-Request pro Sendung), `beschreibung`
  bleibt daher leer.
- Degradiert bei jedem Fehler (Netzwerk, kein Kanal-Treffer, keine
  Daten, unerwartetes JSON) graceful auf die normale generische
  EPG-Generierung fuer diesen Sender.

## Tubi TV (PRIME/TUBI/GO, automatisch)

- Echte Programmdaten von Tubi TV (USA, `tubi_epg.py`) gibt es
  AUTOMATISCH fuer jeden ganz normal eingetragenen Sender mit Land
  `PRIME`, `TUBI` oder `GO` in `sender.txt` - kein eigenes Praefix
  noetig, gleiches Prinzip wie der PlutoTV-Autoabgleich fuer DE.
- Datenquelle ist die community-gepflegte, loginfreie XMLTV-Datei des
  BuddyChewChew/tubi-scraper-Projekts auf GitHub (eine komplette Datei
  mit allen Tubi-TV-Kanaelen UND deren echten Sendungen sowie
  Kanal-Icons), wird nur EINMAL pro Lauf komplett geladen und geparst
  (Modul-weiter Cache), danach werden alle PRIME-/TUBI-/GO-Sender
  lokal dagegen gematcht ohne weitere Netzwerk-Aufrufe.
- Bewusst NICHT Tubis eigene offizielle API (`tubitv.com/oz/epg`)
  verwendet, da die ein Login/Zugangstoken braucht - der GitHub-Mirror
  ist loginfrei.
- Bei Treffer wird zusaetzlich automatisch ein passendes Kanal-Icon
  von Tubi uebernommen, aber nur wenn in sender.txt noch kein
  manuelles Logo gesetzt wurde (leeres Logo-Feld oder der `AUTO`-
  Marker).
- Deckt nur ca. 1-2 Tage im Voraus ab (kein mehrtaegiges Datumsraster),
  Tage danach sind ohnehin immer generisch.
- Degradiert bei jedem Fehler (Netzwerk, kaputtes XML, kein
  Kanal-Treffer) graceful auf die normale generische EPG-Generierung,
  kein Absturz moeglich.

## deswird.org / Pluto TV / tvmovie.de / hoerzu.de / Samsung TV Plus (DE, automatisch)

- Fuenfstufige automatische Fallback-Kaskade fuer alle DE-Sender (kein
  eigenes sender.txt-Praefix noetig), der Reihe nach: deswird.org
  (`deswird_epg.py`) -> Pluto TV (`plutotv_epg.py`) -> tvmovie.de
  (`tvmovie_epg.py`) -> hoerzu.de (`hoerzu_epg.py`) -> Samsung TV Plus
  (`samsungtv_epg.py`). Jede Stufe wird nur probiert, wenn alle
  vorherigen fuer diesen Sender nichts gefunden haben.
- **deswird.org als primaere Quelle** (`https://deswird.org/iptv/
  GuideFull.xml.gz`, Generator "Tempest EPG Generator" von K-vanc/
  GitHub): ~785 deutsche Kanaele, beste Datenqualitaet aller DE-Quellen
  (Titel + Sub-Title/Episodentitel + ausfuehrliche Beschreibung mit
  Jahr/Staffel/Episode) und beste Abdeckung (~6 Tage im Voraus statt
  nur 1-2 Tage wie die anderen DE-Quellen). Im EPG-Raster soll NUR der
  Titel (plus ggf. ein kompakter Episodentitel) erscheinen, keine
  ausformulierten Magazin-Teaser - `_episodentitel_kompakt()` filtert
  deshalb lange/mehrteilige Sub-Titles (Semikolon, >60 Zeichen) heraus,
  bevor sie an den Titel angehaengt werden; die volle Beschreibung
  bleibt im `<desc>`-Feld. Kleine, nicht-offizielle Drittanbieter-Seite
  ohne Stabilitaetsgarantie, degradiert wie alle anderen Quellen
  graceful.
- Pluto TV Deutschland (`plutotv_epg.py`) als zweite Stufe - Nachfolger
  des wieder entfernten free-epg.de-DE-Blocks (siehe unten), mit
  echten, sauberen Pluto-TV-Kanalnamen statt generischer Land-Kuerzel.
- Datenquelle ist das offene, loginfreie i.mjh.nz/PlutoTV-XMLTV-Bulk-
  Projekt (generator-info-name "www.matthuisman.nz", bekannt und weit
  verbreitet, z.B. in vielen Kodi-Addons) - EINE komplette XMLTV-Datei
  (`https://i.mjh.nz/PlutoTV/de.xml.gz`) mit allen deutschen Pluto-TV-
  Kanaelen UND allen Sendungen darin, wird nur EINMAL pro Lauf komplett
  geladen und geparst (Modul-weiter Cache), danach werden alle DE-
  Sender lokal dagegen gematcht ohne weitere Netzwerk-Aufrufe.
- Deckt nur ca. 1-2 Tage im Voraus ab (kein mehrtaegiges Datumsraster
  wie Telemach/mts.rs), Tage danach sind ohnehin immer generisch.
- Findet weder deswird.org noch Pluto TV fuer einen Sender etwas, wird
  automatisch tvmovie.de (`tvmovie_epg.py`, HTML-Scraping via
  `BeautifulSoup`, portiert aus dem WebGrab+Plus-Site-Plugin
  "tvmovie.de") als dritter Versuch probiert, ueber eine im Repo
  mitgelieferte statische Kanalliste
  (`tvmovie_kanalliste.txt`, ~180 Eintraege, Zeilenformat
  "<slug>|<Name>"). WICHTIGE EINSCHRAENKUNG: Die Sender-Seite
  (`tvmovie.de/tv/sender-<slug>`) unterstuetzt anders als im Original-
  Plugin KEINEN Datumsparameter mehr (Website-Redesign,
  `?date=...&type=day` liefert nur noch 404) - es gibt daher nur den
  aktuellen Tag, und laut Beobachtung eines Snapshots offenbar auch
  davon nur einen Teil (~05:00-20:00 Uhr statt der vollen 24 Stunden,
  vermutlich laedt der Rest der Seite serverseitig ueber Nachladen/
  Scrollen per JavaScript nach, das ein reiner Server-Abruf ohne
  Browser nicht bekommt). Da hier HTML statt einer stabilen JSON-API
  geparst wird, ist diese Quelle prinzipiell anfaelliger fuer Breaking
  Changes bei einem weiteren Website-Redesign als Pluto TV.
- Findet auch tvmovie.de nichts, wird automatisch hoerzu.de
  (`hoerzu_epg.py`) als vierter Versuch probiert, ueber eine im Repo
  mitgelieferte statische Kanalliste (`hoerzu_kanalliste.txt`, ~170
  Eintraege, aus der WebGrab+Plus-Kanalliste fuer hoerzu.de extrahiert,
  Zeilenformat "<slug>|<Name>"). Jede Kanalseite
  (`hoerzu.de/tv-programm/<slug>/`) enthaelt serverseitig gerendert
  einen JSON-LD-Block (schema.org "BroadcastEvent") mit dem kompletten
  Tagesraster - kein HTML-Gefrickel wie bei tvmovie.de, aber wie dort
  auch nur der aktuelle Tag (~24 Stunden), ein Datums-Query-Parameter
  wird von der Website ignoriert.
- Findet auch hoerzu.de nichts, wird automatisch Samsung TV Plus
  (`samsungtv_epg.py`, XMLTV-Datei von kodi-unlimited-support.de,
  ~205 Kanaele) als fuenfter und letzter Versuch probiert - ebenfalls
  eine kleine, nicht-offizielle Drittanbieter-Seite ohne
  Stabilitaetsgarantie.
- Alle fuenf Quellen degradieren bei jedem Fehler (Netzwerk, kaputtes
  Gzip/XML, kein Kanal-Treffer, unerwartete HTML-Struktur/fehlender
  JSON-LD-Block) graceful auf die normale generische EPG-Generierung,
  kein Absturz moeglich.
- Land `JOYN` loest denselben fuenfstufigen Autoabgleich aus wie Land
  `DE` (JOYN-Sender sind inhaltlich deutsche Kanaele, nur mit
  "JOYN|"-Praefix in der eigenen Playlist statt "DE|") - kein eigenes
  Praefix noetig, gleiche Zero-Risk-Garantie.
- Land `PRIME` (siehe auch Tubi-TV-Abschnitt unten) laeuft ZUSAETZLICH
  zu Tubi auch durch diese DE-Kaskade, da der PRIME-Bereich der
  eigenen Playlist neben US-Sendern auch deutschsprachige Kanaele
  enthaelt (z.B. "X-Factor: Das Unfassbare", das als echter Live-Kanal
  bei Pluto TV DE existiert). Tubi wird zuerst probiert, die DE-Kaskade
  nur als Ergaenzung danach; eine Sperre in der Tubi-Verarbeitung
  verhindert, dass beide Quellen bei einem Treffer dieselben Sendungen
  doppelt ins XML schreiben (kein Sender wird automatisch angelegt -
  nur der bestehende Code-Pfad wird fuer PRIME-Sender mit erweitert,
  die konkrete sender.txt-Zeile bleibt Sache des Nutzers).
- Land `WOW` (die eigene Playlist-Kennzeichnung fuer den WOW/Sky-
  Streaming-Bereich, siehe auch den SKY:-Display-ID-Override "WOW|
  SKY CRIME ᴴᴰ ◉" im SKY:-Abschnitt) laeuft ebenfalls durch diese
  DE-Kaskade - WOW-Sender sind inhaltlich deutsche Kanaele (z.B.
  "Cartoon Network", das bei deswird.org als echter Kanal existiert).

**Mehrdeutige Kanalnamen bei deswird.org:** deswird.org fuehrt manche
Sender (z.B. "Cartoon Network") mehrfach unter identischem
Anzeigenamen, aber mit unterschiedlicher Kanal-ID und unterschiedlichem
Programm (z.B. site_id "Cartoon Network" mit 717 Sendungen/7 Tagen vs.
site_id "CartoonNetwork.de" mit 2063 Sendungen/9 Tagen - zwei echte,
aber verschiedene aggregierte Feeds). Ohne Sonderbehandlung wuerde der
normale Namens-/Kern-Index das als mehrdeutig verwerfen und der
difflib-Fallback koennte einen komplett falschen, nur aehnlich
benannten Kanal treffen (siehe Sky-Cinema-Highlights-Fall im
SKY:-Abschnitt unten). `deswird_kanal_finden()` baut daher einen
eigenen Namens-/Kern-Index (NICHT `epg_lib.kern_index_aufbauen()`) und
bevorzugt bei Mehrdeutigkeit die Kanal-ID, die explizit auf ".de"
endet (`_de_id_bevorzugen()`) - eindeutig die richtige Wahl fuer diese
DE-spezifische Quelle, statt den Treffer ganz zu verwerfen.

Fuer MK gab es frueher MaxTV Go (wegen toter Domain entfernt) und
zwischenzeitlich free-epg.de (wegen leerer/unzuverlaessiger Datenbasis
auf ausdruecklichen Wunsch wieder entfernt) - MK laeuft bis auf
Weiteres rein generisch, sofern keine andere Quelle
(TVGUIDE:/TVPASSPORT:/MAGENTA:/SKY:/DAZN: etc.) explizit als Praefix
eingetragen wird.

## TVGUIDE:-Sender (TVGuide.com US, opt-in)

- Echte Programmdaten von TVGuide.com (`tvguide_epg.py`) gibt es NUR
  ueber das explizite Praefix `TVGUIDE:<Land, nur "US"
  unterstuetzt/optional>|<Kanalname wie bei TVGuide>|<Logo-URL>`, z. B.
  `TVGUIDE:US|CBS|https://example.com/logo.png`.
- Bewusst KEIN automatisches Matching wie bei BA/ME (Telemach/mtel) -
  genau wie bei SKY/DAZN/FREEVIEW: reines Opt-in ueber die explizite
  Zeile.
- Es wird nur EINE fest hinterlegte, nationale providerId verwendet
  (nicht die postleitzahl-/anbieterabhaengige Provider-Auswahl des
  Originals), deckt also die gaengigen US-Networks ab, aber keine
  lokalen/kabelanbieter-spezifischen Sender. Ebenso wird keine
  ausfuehrliche Sendungsbeschreibung/Rating/Genre nachgeladen (kein
  Extra-Request pro Sendung wie im Original), `beschreibung` bleibt
  daher immer leer.
- Degradiert bei jedem Fehler (Netzwerk, kein Kanal-Treffer, keine
  Daten) graceful auf die normale generische EPG-Generierung, kein
  Absturz moeglich.

## meine_logos.txt (Sendername-zu-Logo-Referenz, noch nicht aktiv genutzt)

- Der Nutzer hat eine grosse XMLTV-EPG-Datei eines Drittanbieters
  (generiert mit "IPTVEditor 4", ~205 MB entpackt, ~13.500
  Kanaele, ~514.000 Sendungseintraege) hochgeladen. Ein Teil der Kanaele
  darin hat echte Sendungsdaten (z. B. RTL Crime mit echten Episoden-
  titeln/Beschreibungen), ein Teil ist nur Dummy-Platzhalter (Kanalname
  als Titel wiederholt).
- Daraus wurde NUR die Sendername-zu-Logo-Zuordnung extrahiert (Format
  `Sendername|Logo-URL`, exakt wie die Playlist-Namenskonvention des
  Nutzers, z. B. `DE| 3SAT HD|https://logo.m3uassets.com/3sat.png`) -
  gefiltert auf die Laender DE und EXYU (BA/RS/HR/ME/SI/MK, siehe
  `EXYU_LAENDER`/`SI_LAENDER`/`MK_LAENDER` in `epg_lib.py`), da der
  Nutzer nur diese beiden Gruppen wollte. Liegt als
  `logos_bei_bedarf/meine_logos.txt` (eigener Ordner, bewusst getrennt
  von `logos/` mit den echten, selbst erstellten PNG-Logo-Dateien -
  diese Datei enthaelt nur Text/Links, keine Bilder) (1975 Zeilen:
  969 DE, 1006 EXYU).
- **WICHTIG:** Diese Datei ist bisher nur eine reine Referenz/
  Nachschlagewerk - sie ist NICHT mit `generate_epg.py` verknuepft und
  wird beim EPG-Erzeugen noch nicht automatisch genutzt (weder fuer
  Logos noch fuer Sendungsdaten). Erst auf expliziten Nutzerwunsch
  waere eine Einbindung zu bauen (z. B. als zusaetzliche automatische
  Logo-Quelle fuer Sender ohne eigenes Logo, aehnlich der Tubi-TV-
  Icon-Uebernahme).
- Die vollstaendige, ungefilterte Namensliste aller ~370 Laender-/
  Anbieter-Praefixe (inkl. weiterer dynamischer PPV-Kanaele wie
  "DISNEY+ PPV"/"CH: SFL PPV" nach demselben NEXT/LIVE/ENDED-Muster wie
  DYN PPV) wurde dem Nutzer nur als Chat-Datei geschickt, NICHT ins
  Repo committet (Datenschutz/Uebersicht - der Nutzer wollte zunaechst
  nur DE+EXYU dauerhaft im Repo).

## alle_logos.txt (Sendername-zu-Logo-Referenz, ALLE Laender, noch nicht aktiv genutzt)

- Zusaetzlich zu `meine_logos.txt` (nur DE+EXYU) gibt es
  `logos_bei_bedarf/alle_logos.txt` (August 2026 angelegt) - deckt
  ALLE Laender/Anbieter-Praefixe ab, nicht nur DE+EXYU, aus zwei
  weiteren, aehnlich grossen XMLTV-EPG-Drittanbieter-Dateien
  (zusammengefuehrt und dedupliziert, exakt gleiches Format
  `Sendername|Logo-URL` wie `meine_logos.txt`). Aktuell 47.567
  eindeutige Zeilen.
- Zweck: falls der Nutzer irgendwann unabhaengig von seinem aktuellen
  EPG-Provider werden will, stehen fuer praktisch jeden denkbaren
  Sendernamen (nicht nur DE/EXYU) schon Name+Logo-URL bereit, ohne
  dass jedes Mal einzeln online gesucht werden muss.
- Dedupliziert wurde NUR bei komplett identischen Zeilen (identischer
  Sendername UND identische Logo-URL, Zeichen fuer Zeichen) - bewusst
  NICHT nach Sendername allein, da z.B. gleicher Sendername mit
  unterschiedlichem Laender-Praefix (z.B. "DE| RTL" vs. "AT| RTL")
  fuer den Nutzer je nach eigener Playlist relevant sein kann. Nichts
  inhaltlich entfernt, nur echte 1:1-Duplikate beim Zusammenfuehren
  beider Quelldateien rausgefiltert.
- **WICHTIG:** Wie `meine_logos.txt` bisher nur reine Referenz - NICHT
  mit `generate_epg.py` verknuepft, keine automatische Nutzung beim
  EPG-Erzeugen. Erst auf expliziten Nutzerwunsch waere eine Einbindung
  zu bauen.

## ppv_kernnamen.txt (Kern-Kanalnamen fuer dynamische PPV-Sendergruppen, Referenz)

- `logos_bei_bedarf/ppv_kernnamen.txt` (August 2026 angelegt, 6742
  Zeilen) extrahiert speziell die STABILEN Kern-Kanalnamen (Format
  `Kernname|Logo-URL`, z.B. `AT: DAZN PPV 1|...`, `NO: VGTV PPV 10|...`)
  aus allen dynamischen PPV-/Live-Event-Sendergruppen (analog zum
  eigenen DYN-PPV/NAME:-Mechanismus: Sendungstitel wechselt staendig
  z.B. "End | ... | AT: DAZN PPV 1", nur der letzte Namensteil nach dem
  letzten Pipe bleibt stabil).
- Erkennung heuristisch ueber typische Marker (`End |`, `Live |`,
  `Next |`, `NO EVENT STREAMING NOW...`) in den Anzeigenamen beider
  Quelldateien, danach wird das letzte Pipe-Segment als Kernname
  genommen. Funktioniert bei den meisten Gruppen sauber, aber es
  koennen vereinzelt Ausreisser/Fehltreffer drin sein (z.B. ein Team-
  vs-Team-Titel ohne Laender-Praefix an der Stelle) - vor einer
  tatsaechlichen Uebernahme in `sender.txt` stichprobenartig
  gegenchecken.
- Ergaenzt `meine_logos.txt` (DE+EXYU, feste Namen) und `alle_logos.txt`
  (Momentaufnahme aller Anzeigenamen, alle Laender) um genau die
  Kanalgruppen, die NUR ueber ihren dynamischen Live-Titel erkennbar
  sind - ohne diese Datei waeren deren stabile Kernnamen in den beiden
  anderen Referenzdateien nicht sauber auffindbar gewesen.
- **WICHTIG:** Ebenfalls bisher nur reine Referenz - NICHT mit
  `generate_epg.py` verknuepft.
