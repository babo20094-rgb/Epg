# EPG-Projekt: Historie, Bugfälle, Lehren (Detailarchiv)

Dies ist das vollständige Detailarchiv aller bisherigen Debugging-Fälle,
Bugfixes und "Lehren" aus der Entwicklung dieses Repos. Die kompakte
`CLAUDE.md` im Projekt-Root enthält nur noch die aktiven Regeln und eine
knappe Quellen-Übersicht; hier steht die ausführliche Fallgeschichte.

**Wann hier nachschlagen:** Bei einer neuen "Sender X zeigt falsches/kein
Programm"-Meldung oder einem neuen Bug-Verdacht IMMER zuerst per `grep -i`
nach Stichworten suchen (Sendername, Quelle, Symptom wie "Keine
Information", "Fuzzy", "Kern-Extraktion", "TiviMate") - viele Symptome
sind bereits einmal aufgetreten und hier mit Ursache + Fix dokumentiert.
Erst wenn hier nichts Passendes gefunden wird, von vorne debuggen.

---

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

**Zur wiederkehrenden Stop-Hook-Meldung ("There are uncommitted
changes..."):** Dieser Hook (`~/.claude/stop-hook-git-check.sh`) ist
KEIN Projekt-/Nutzer-Setting, sondern feste Infrastruktur der jeweiligen
Remote-Sitzungsumgebung selbst (liegt in `~/.claude/launcher-settings.json`,
root-eigen, nicht editierbar/deaktivierbar) - er verhindert, dass beim
Zuruecksetzen des Sitzungscontainers unbemerkt Arbeit verloren geht,
solange noch uncommittete/ungepushte Aenderungen im Arbeitsverzeichnis
liegen. Er hat NICHTS mit der Commit/Push-Bestaetigungspflicht oben zu
tun (die bleibt unveraendert reine Chat-Verhaltensregel) und meldet sich
schlicht immer dann, wenn zwischen zwei "ja, committen und pushen"-
Freigaben Aenderungen offen im Arbeitsverzeichnis liegen - das ist
normal/erwartet bei diesem Workflow und keine Fehlfunktion. Nicht
versuchen, ihn zu deaktivieren oder zu umgehen.

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

- `logos_bei_bedarf/ppv_kernnamen.txt` (August 2026 angelegt, 12315
  Zeilen) extrahiert speziell die STABILEN Kern-Kanalnamen (Format
  `Kernname|Logo-URL`, z.B. `AT: DAZN PPV 1|...`, `NO: VGTV PPV 10|...`)
  aus allen dynamischen PPV-/Live-Event-Sendergruppen (analog zum
  eigenen DYN-PPV/NAME:-Mechanismus: Sendungstitel wechselt staendig,
  nur ein Teil des Namens bleibt stabil).
- Erkennung ueber fuenf Muster, je nach Anbieter-Konvention: (1) Kern
  HINTEN/VORNE im Format "LAND: NAME PPV N" (Pflicht: Wort "PPV" muss
  im erkannten Kern vorkommen, sonst greifen zufaellige Ligennamen mit
  Doppelpunkt+Zahl wie "AEW: All In London 2026" faelschlich zuerst),
  (2) Kern in Klammern (z.B. "(FLSP 671) | live: ..."), (3)
  "LIVE EVENT N - ..." ohne Laender-Code, (4) "Name N | Spielinfos"
  ohne Doppelpunkt (z.B. "National League 3 | Scunthorpe vs Chester",
  Erkennung nur wenn der Rest nach dem Pipe dynamisch wirkt - "vs",
  "//" oder eine Uhrzeit enthaelt), (5) ":Name(n) N" ganz am Zeilenende
  ohne "PPV"-Wort (z.B. "Tennis: Spieler A vs Spieler B @ Datum
  :Tennis 30" -> Kern "Tennis 30", oder ":MAX DK 01" -> Kern "MAX DK
  01" - deckt Faelle ab, wo ein Kategorietext wie "Tennis:" vorne
  mehrfach fuer unterschiedliche Events steht und nur der Teil nach
  dem letzten Doppelpunkt am Ende stabil pro Kanal ist), (6) "Name N:"
  ganz am ZeilenANFANG (z.B. "TC+ 1: 12/02 12:50pm,..." oder auch
  "TC+ 100:" ganz ohne Text danach, wenn der Kanal gerade kein Event
  zeigt - Kern "TC+ 100:"), (7) doppelte Klammer-Gruppe + Nummer
  (z.B. "(Apple) (MLS) 001 | Columbus vs. New England..." -> Kern
  "(Apple) (MLS) 001 |"). Erkennung laeuft case-insensitiv
  (nicht nur GROSSBUCHSTABEN, da manche Anbieter gemischte
  Schreibweise nutzen z.B. "SE: AftonBlade PPV 24"). Funktioniert bei
  den meisten Gruppen sauber (z.B. alle 200 "US: SOCCER PPV",
  alle 99 "DE: DAZN PPV", alle 100 "DE: SPORT DEUTSCHLAND PPV"
  gefunden), aber es koennen vereinzelt Ausreisser/Fehltreffer drin
  sein - vor einer tatsaechlichen Uebernahme in `sender.txt`
  stichprobenartig gegenchecken. Fehlende Einzelnummern innerhalb
  einer Gruppe (z.B. "DE: LEAGUES FOOTBALL PPV 6") sind idR keine
  Erkennungsluecke, sondern eine echte Datenluecke der Quelle (Kanal
  war zum Downloadzeitpunkt nicht im Feed aktiv) - vor weiterer Suche
  erst direkt in den Rohdaten gegenchecken. Ein kleiner Rest
  (~250 Kanaele) mit "LIVE"/"END" als normalem Namensbestandteil (z.B.
  "Sky Sport 5", "Eurosport Live 9") wurde bewusst NICHT extrahiert,
  da das bereits stabile, statische Namen ohne wechselnden Anteil
  sind - die stehen vollstaendig in `alle_logos.txt`.
- Ergaenzt `meine_logos.txt` (DE+EXYU, feste Namen) und `alle_logos.txt`
  (Momentaufnahme aller Anzeigenamen, alle Laender) um genau die
  Kanalgruppen, die NUR ueber ihren dynamischen Live-Titel erkennbar
  sind - ohne diese Datei waeren deren stabile Kernnamen in den beiden
  anderen Referenzdateien nicht sauber auffindbar gewesen.
- **WICHTIG:** Ebenfalls bisher nur reine Referenz - NICHT mit
  `generate_epg.py` verknuepft.

## Playlist-Vollimport (August/September 2026) - sender.txt auf ~19.100 Zeilen erweitert

Ziel des Nutzers: unabhaengig vom aktuellen EPG-Provider werden, indem
ALLE Sender aus der eigenen IPTV-Playlist (nicht nur eine Auswahl) mit
echten Programmdaten wo moeglich in `sender.txt` stehen. Umgesetzt und
bereits auf `main` committet/gepusht (Commit `42d635d`).

- **Live-TV vs. VOD-Trennung:** Die Playlist hat insgesamt ~1,38 Mio.
  `#EXTINF`-Zeilen, weil riesige VOD-/Serien-/Film-Kataloge mitlaufen.
  Erkennungsmerkmal: VOD-Gruppen haben ein FUEHRENDES `|` im
  `group-title` (z. B. `|DE| SERIEN`), echte Live-/PPV-Kanaele haben
  KEIN fuehrendes `|` (z. B. `DE| ALLGEMEIN`, `US| ESPN+ PPV VIP`).
  Reicht als Filter aber NICHT allein - manche No-Pipe-Gruppen sind
  trotzdem VOD-Kataloge (siehe unten).
- **Finale, per Stichprobe verifizierte Zahl: 18.979 echte Live-Sender**
  in 234 Gruppen (Stand des Imports). Ausgeschlossen wurden nur 11
  Gruppen (3.473 Eintraege) mit eindeutigen Einzeltitel-VOD-Katalogen
  (Filmtitel mit Jahreszahl, keine Kanal-Nummerierung): `NETFLIX
  MOVIES`, `NETFLIX KIDS`, `NETFLIX ASIA`, `TOP IMDB/OSCAR MOVIES`,
  `DISNEY+ MOVIES`, `4K NETFLIX MOVIES`, `APPLE+ MOVIES`, `DISNEY+
  KIDS`, `APPLE+ KIDS`, eine namenlose Gruppe (Lernvideos), `US|
  NETFLIX ON AIR RAW` (aktuell leer). **Wichtige Lehre dabei:**
  durchnummerierte Gruppen (z. B. `SKY GO FILME 1-57`, `NETFLIX PPV
  1-10`, `PRIME VIDEO SERIE 1-10`) sind KEINE Kataloge, sondern
  echte (wenn auch thematische) Live-Kanaele - Nummerierung ist das
  Unterscheidungsmerkmal, nicht das Vorkommen von Wörtern wie
  "Filme"/"Movies"/"Serie" im Namen. `SKY GO KINO` wurde faelschlich
  erst als VOD eingestuft, enthielt aber echte Kanaele (13th Street,
  Sky Atlantic, Sky Crime usw.) - bei Unsicherheit immer echte
  Beispiel-Eintraege der Gruppe pruefen, nicht nur den Gruppennamen.
- **Sender-Namensformat aus der Playlist:** `Land| Sendername` (z. B.
  `DE| ZDF HD`) fuer normale Kanaele -> wurde 1:1 in normale
  `Land|Sender|Beschreibung|Logo`-Zeilen uebernommen. Namen OHNE
  dieses Land-Pipe-Format sind ueberwiegend dynamische PPV-/Live-
  Event-Kanaele (roher Name aendert sich mit jedem Event, z. B. "End |
  Team A vs. Team B | ... | DE: DAZN PPV 17") - dafuer wurde der
  stabile Kern (Land: Name PPV N) extrahiert und als `NAME:`-Zeile
  eingetragen, exakt nach der bestehenden DYN-PPV-Konvention (siehe
  oben). 9.303 `NAME:`-Zeilen stehen jetzt insgesamt in `sender.txt`.
- **Dedup gegen bestehende Zeilen:** Vor dem Einfuegen wurde jeder neue
  Playlist-Name gegen die vorhandenen `sender.txt`-Zeilen abgeglichen
  (exaktes 4. Feld bei SKY:/TVPASSPORT:/etc.-Zeilen, rekonstruiertes
  `Land| Sender` bei normalen Zeilen) - nur wirklich neue Sender
  wurden ergaenzt, nichts Bestehendes veraendert oder ueberschrieben.
  Von 18.155 eindeutigen Sendernamen waren bereits 1.320 vorhanden,
  16.835 wurden neu ergaenzt.
- **Echte Quellen fuer die neuen Sender:**
  - DE/BA/RS/HR/SI/MNG/MO/JOYN/PRIME/WOW/TUBI/GO laufen automatisch
    ueber die bereits bestehenden Code-Pfade (siehe jeweilige
    Abschnitte oben) - **wichtige Erkenntnis dabei:** `MNG` und `MO`
    sind im Code (`TELEMACH_LAND_ALIAS`) bereits als Alias fuer
    Montenegro (`ME`) hinterlegt und laufen daher automatisch durch
    Telemach, obwohl das vorher nirgends explizit dokumentiert war.
  - US-Sender wurden auf `TVPASSPORT:US|`/`TVGUIDE:US|` umgestellt
    (lokale Sender mit Sender-Kuerzel in Klammern -> TVPASSPORT,
    sonst TVGUIDE), UK-Sender auf `SKY:GB|`/`FREEVIEW:GB|` (Sky-Marke
    im Namen -> SKY, sonst FREEVIEW) - reines Best-Effort-Mapping per
    Namensmuster, kein garantierter Treffer pro Sender, degradiert bei
    Nichttreffer graceful auf generischen Text (Zero-Risk, siehe unten).
  - MK, CITY, EN, LIGA, EXYU, IR, EPL, SPFL, PPV, UFC, NA, MLB, SK und
    alle `NAME:`-Kanaele ohne erkanntes Anbieter-Muster bleiben
    generisch (kein automatischer Massen-Abgleich vorgesehen/moeglich).
- **Fallback-Text-Fix (generate_epg.py):** Vorher fiel bei SKY:/
  MAGENTA:/DAZN:/ARENA:/FREEVIEW:/TVGUIDE:/TVPASSPORT:/TELEMACH:-
  Sendern OHNE Treffer bei der echten Quelle der alte, abwechslungs-
  reiche Kategorietext (`standard_beschreibung()`) als Fallback an -
  das betraf auch schon VORHER bestehende Sender, nicht nur die neuen.
  Auf Nutzerwunsch fuer alle acht Quellen-Praefixe vereinheitlicht auf
  `<Sendername in Title Case> ᴸⁱᵛᵉ`, exakt wie beim generischen
  Land|Sender-Format ohne Quelle.
- **Logos:** Playlist selbst traegt bei fast jedem Kanal ein
  `tvg-logo`-Attribut (18.433 von 18.979 Live-Kanaelen) - direkt
  daraus extrahiert, zusaetzlich Abgleich gegen `meine_logos.txt`/
  `alle_logos.txt`. 2.500 einzigartige Bild-URLs wurden heruntergeladen,
  auf max. 300px/256 Farben optimiert (gleiche Konvention wie die
  anderen `logos/`-Sets) und liegen jetzt selbst gehostet unter
  `logos/playlist_import/<sha1-hash>.png`. **Bekannte Luecke:** ca.
  1.580 Sender haben noch eine externe Logo-URL statt selbst gehostet -
  deren Bilder liegen auf den privaten Picon-Servern des Anbieters
  (`103.176.90.95`, `51.158.145.100`), die aus der damaligen Claude-
  Code-Sandbox-Umgebung nicht erreichbar waren (kein Fehler im
  Code/den Daten, rein eine Netzwerk-Einschraenkung der damaligen
  Session - ein erneuter Versuch mit vollem Internetzugriff koennte
  das nachtraeglich vervollstaendigen). 105 Sender haben noch gar kein
  Logo (kein Treffer in Playlist-tvg-logo oder Referenzdateien).
- **Laufzeit:** Mit dem deutlich groesseren `sender.txt` dauert ein
  Workflow-Lauf laenger als vorher (grobe Schaetzung ~27-45 Minuten
  statt vorher ~12-16 Minuten) - noch nicht abschliessend mit echtem
  Internetzugriff verifiziert, da die Entwickler-Sandbox beim Import
  selbst keinen vollen Zugriff auf die externen EPG-Quellen hatte
  (Telemach, mtel.ba etc. wurden dort blockiert). Der naechste/erste
  echte Workflow-Lauf auf `main` nach diesem Import ist die eigentliche
  Bewaehrungsprobe - Ergebnis ggf. hier oder im naechsten Gespraech
  nachtragen, sobald bekannt.
- **Playlist-Herkunft:** Die verwendete Playlist-URL enthaelt
  Zugangsdaten des Nutzers und wird auf dessen ausdruecklichen Wunsch
  NIRGENDS im Klartext wiederholt (weder im Chat noch in Dateien) -
  lokale Kopien der Playlist wurden nach jeder Analyse wieder aus dem
  Scratchpad geloescht.

## Playlist-Vollimport: Nacharbeiten nach dem ersten echten Workflow-Lauf

Nach dem ersten echten Workflow-Lauf auf `main` (mit vollem
Internetzugriff, anders als die Entwickler-Sandbox beim Import selbst)
kamen mehrere Nachbesserungen dazu - alle bereits auf `main`
committet/gepusht:

- **GitHub-100-MB-Limit gesprengt:** Die unkomprimierte
  `Epg_365_Tage.xml` wuchs mit ~19.000 Sendern auf ueber 200 MB - der
  automatische Commit im Workflow schlug fehl (`GH001: Large files
  detected`). Fix: `generate_epg.py` schreibt zusaetzlich eine
  gzip-komprimierte `Epg_365_Tage.xml.gz` (91,5 % kleiner, aktuell
  ~15-18 MB), der Workflow committet nur noch diese; die
  unkomprimierte Datei bleibt lokal bestehen, ist aber per
  `.gitignore` nicht mehr versioniert. **Der Nutzer musste seine
  Player-EPG-URL manuell von `.../Epg_365_Tage.xml` auf
  `.../Epg_365_Tage.xml.gz` umstellen** - fast jeder IPTV-Player
  (u.a. TiviMate) unterstuetzt gezippte XMLTV-Quellen direkt per URL.
  Git LFS wurde bewusst NICHT gewaehlt (GitHubs kostenloses
  LFS-Bandbreiten-Kontingent von 1 GB/Monat waere bei einer alle 3h
  neu gepushten ~100+MB-Datei sofort aufgebraucht).
- **260 doppelte Kanal-IDs:** Der urspruengliche Dedup-Check beim
  Import verglich bei `SKY:`/`TELEMACH:`/`MAGENTA:`/`ARENA:`/`DAZN:`/
  `FREEVIEW:`/`TVGUIDE:`/`TVPASSPORT:`-Zeilen OHNE expliziten
  Display-Namen-Override nicht gegen die tatsaechliche, zur
  Laufzeit gebaute Kanal-ID (z.B. `TELEMACH:BA|ARENA SPORT 1 HD|AUTO`
  baut zur Laufzeit dieselbe ID wie eine neue, generische
  `BA|ARENA SPORT 1 HD|...`-Zeile) - 246 neue Zeilen kollidierten
  dadurch mit laengst bestehenden, echte Daten liefernden Eintraegen.
  Weitere 20 Kollisionen kamen von neuen `DE|DYN PPV 1-20 HD`-Zeilen,
  die zufaellig dieselbe ID wie die fest im Code verankerten
  DYN-PPV-API-Kanaele (siehe oben, komplett getrennter Mechanismus)
  erzeugten. Wenn zwei `<channel>`-Eintraege dieselbe ID haben,
  entscheidet der Player selbst (unvorhersehbar) welchen er zeigt -
  in den beobachteten Faellen wurde faelschlich der neue, echte-
  Quelle-lose Eintrag angezeigt statt des alten funktionierenden.
  Alle 260 ueberfluessigen neuen Zeilen wurden entfernt, die
  bestehenden bleiben unangetastet.
- **Fallback-Grossschreibung bei `NAME:`-Sendern:** Der Fallback-Text
  ("<Kurzname> ᴸⁱᵛᵉ") fuer `NAME:`-Sender OHNE erkanntes
  Anbietermuster (betrifft die meisten der ~9.000 neuen dynamischen
  PPV-Kanaele) uebernahm den Kurznamen unveraendert komplett
  grossgeschrieben (z.B. "24/7 ALL RISE ᴸⁱᵛᵉ" statt "24/7 All Rise
  ᴸⁱᵛᵉ"), anders als bei den acht anderen Quellen-Praefixen. Nutzt
  jetzt `kanalname_normal_geschrieben()` wie an anderen Stellen im
  Skript. `KANALNAME_ABKUERZUNGEN` (epg_lib.py) um PPV/VIP/UFC/NFL/
  NBA/NHL/MLB/NCAA/MLS/EPL sowie gaengige Land-/Kategorie-Codes
  (DE/US/UK/BA/RS/SI/MK/EXYU/MO/MNG/CG/SPFL/NA/SK/GO/CITY/EN/IR/LIGA/
  JOYN/PRIME/WOW/TUBI) erweitert, damit diese gross bleiben statt zu
  "De"/"Us" zu werden. Doppelpunkt zusaetzlich als abtrennbares
  Suffix-Zeichen ergaenzt (analog zu Klammern), damit z.B. "DE:" am
  Wortanfang korrekt als Ganzes (nicht als "De:") erkannt wird.
- **Logos fuer `NAME:`-Kanaele nachgetragen:** Der urspruengliche
  Logo-Nachtrag beim Import deckte nur normale `Land|Sender`-Zeilen
  ab, die ~9.221 `NAME:`-Kanaele wurden dabei versehentlich
  uebersprungen (blieben ohne jedes Logo). Nachtraeglich per
  Playlist-`tvg-logo`-Abgleich (exakter Kern-Treffer + Suffix-Index
  fuer dynamische Eintraege, deren aktueller Rohname nicht mehr dem
  Kern entspricht) 7.007 Logo-URLs ergaenzt, davon 125 heruntergeladen/
  optimiert und selbst gehostet unter `logos/playlist_import/`. Rest
  extern verlinkt (ueberwiegend vom in der Entwickler-Sandbox
  blockierten Picon-Host des Anbieters) oder ganz ohne Logo (kein
  Playlist-Treffer fuer den aktuellen Kernnamen, 2.058 Kanaele).
- **HEVC/4K/8K als Suffix erkannt + VOX-Ambiguitaets-Bug:**
  `normalisiere_sendername_kern()` (epg_lib.py) ignorierte bisher nur
  HD/FHD/UHD/SD als Qualitaets-Suffix beim unscharfen Namensabgleich,
  nicht aber HEVC/4K/8K - z.B. "RTL HEVC"/"VOX HEVC" fanden dadurch
  keinen Treffer bei deswird.org, obwohl der Sender dort existiert.
  Um HEVC/4K/8K erweitert. Zusaetzlich in `deswird_kanal_finden()`
  einen echten Bug behoben: Kanaele, die deswird.org mehrfach mit nur
  unterschiedlicher Gross-/Kleinschreibung der Kanal-ID fuehrt (z.B.
  "VOX.de" vs. "Vox.de" - derselbe echte Sender, kein zweiter Kanal),
  wurden faelschlich als "mehrdeutig" verworfen und komplett vom
  Kern-Index ausgeschlossen. Case-insensitiver Vergleich vor der
  Mehrdeutigkeits-Pruefung behebt das. **Wichtige Lehre dabei:** ein
  erster, breiterer Loesungsversuch (zusaetzlicher unscharfer
  Kern-gegen-Kern-Abgleich als letzter Fallback) wurde wieder
  verworfen, weil er einen echten Fehltreffer erzeugte ("ProSieben
  Maxx" wurde mit "ProSieben Fun" verwechselt, da beide denselben
  langen "ProSieben"-Praefix teilen und der verkuerzte Kern-Vergleich
  zu unspezifisch wurde) - nur die eng gefassten, gezielten Fixes
  (weitere Suffix-Woerter, Gross-/Kleinschreibungs-Bug) wurden
  behalten. Generelles Prinzip fuer kuenftige Matching-Verbesserungen:
  einzelne, klar abgegrenzte Faelle gezielt fixen und jedes Mal gegen
  mehrere andere Sender (insbesondere aehnlich benannte wie ProSieben
  Maxx/Fun oder Sky Cinema Premiere/Special) gegentesten, statt die
  Fuzzy-Suche pauschal zu lockern.
- **RTL Nitro auf "Nitro" umbenannt:** Der Nutzer hat den Sender in
  seiner eigenen IPTV-App (TiviMate) von "RTL Nitro" auf "Nitro"
  umbenannt (seine eigene Vermutung: das wuerde das serverseitige
  Matching verbessern - stimmt so pauschal NICHT, siehe unten). Da der
  Nutzer aber bestaetigte, dass in seiner tatsaechlichen
  Anbieter-Playlist "NITRO HEVC" bereits ohne "RTL"-Praefix gefuehrt
  wird (waehrend "RTL NITRO FHD"/"RTL NITRO HD" als SEPARATE, echte
  Playlist-Eintraege mit "RTL"-Praefix existieren, per direktem
  Playlist-Abgleich bestaetigt), wurden `DE|RTL NITRO FHD` und
  `DE|RTL NITRO HD` in `sender.txt` zu `DE|NITRO FHD`/`DE|NITRO HD`
  umbenannt - das aendert auch die generierte `<channel>`-ID. Beide
  matchen jetzt korrekt gegen deswird.org (vorher: kein Treffer, da
  der "RTL"-Praefix den unscharfen Namensabgleich unter die
  Aehnlichkeits-Schwelle drueckte). **Wichtig zu wissen:** Eine rein
  lokale Umbenennung IM PLAYER (ohne zugehoerige Aenderung in
  `sender.txt`) haette NICHTS gebracht - unser Matching laeuft
  serverseitig gegen den rohen Namen aus `sender.txt`/der echten
  Anbieter-Playlist, nicht gegen player-lokale Anzeigenamen.
- **Stand:** Alle oben genannten Fixes sind auf `main` committet und
  gepusht, aber der Nutzer hat ausdruecklich gebeten, den
  Workflow-Lauf NICHT mehr automatisch/proaktiv zu starten (frueher
  wurden dadurch teils parallel laufende, sich widersprechende Laeufe
  ausgeloest) - **immer erst auf explizite Anweisung des Nutzers
  hin** `run_workflow` aufrufen. Ob die neuesten Fixes (Grossschreibung,
  HEVC/4K/8K, VOX-Bug, Nitro-Umbenennung, NAME:-Logos) wie erwartet
  wirken, ist zum Zeitpunkt dieses Eintrags noch nicht mit einem
  frischen Lauf verifiziert.

## Logo-Recherche September 2026: Abdeckung von ~40% auf 90% gesteigert

Nach dem Playlist-Vollimport hatten tausende Sender (v. a. die ~9.300
`NAME:`-PPV-Kanaele) noch kein Logo oder eines, das auf den toten
Picon-Host des Anbieters zeigte. In einer sehr langen Session wurde das
systematisch aufgearbeitet - Endergebnis: **90% aller Sender (16.867
von 18.715) haben jetzt ein funktionierendes, selbst gehostetes oder
verifiziert erreichbares Logo.**

- **Toter Picon-Host bestaetigt, nicht nur Sandbox-Problem:** Ein
  eigens angelegter Workflow (`logos_nachladen.yml`, inzwischen wieder
  entfernt) versuchte, die ~1.669 eindeutigen Bilder von
  `103.176.90.95`/`51.158.145.100` ueber einen GitHub-Actions-Runner
  mit vollem Internetzugriff herunterzuladen - lief nach 45 Minuten
  auf reine `Connection timeout`-Fehler (0 von 1.669 erfolgreich). Der
  Server ist also grundsaetzlich tot, nicht nur aus der Entwickler-
  Sandbox heraus unerreichbar - dieser Weg wurde aufgegeben.
- **Genutzte Logo-Quellen** (jeweils mit Namensabgleich + Stichproben-
  Erreichbarkeitspruefung vor Uebernahme): eigene Referenzdateien
  (`meine_logos.txt`/`alle_logos.txt`), die `logo.m3uassets.com`-CDN
  (Namenskonvention direkt erraten und per HEAD-Request geprueft), die
  oeffentliche iptv-org-Kanaldatenbank (`channels.json`/`logos.json`,
  exakter Namensabgleich + streng gefilterter Fuzzy-Abgleich ≥90%
  Aehnlichkeit), das GitHub-Projekt `tv-logo/tv-logos` (laenderweise
  sortierte Logo-Sammlung), Wikimedia Commons (gezielt per Websuche pro
  Titel gefunden, v. a. fuer die vielen Serien-/Film-"Kanaele" wie
  "Ahsoka", "The Godfather", "Guardians Of The Galaxy"), TMDB (Website-
  HTML-Scraping der Suchergebnisseite, kein API-Key noetig, liefert
  Poster-Bilder ueber `media.themoviedb.org`) sowie Marken-Logos direkt
  (Netflix/Disney+/Amazon Prime Video/HBO fuer alle "NETFLIX ..."-,
  "DISNEY+ ..."-Kategoriekanaele usw.).
- **Wichtigster Fund - die eigene externe EPG-Datenquelle des Nutzers**
  (myepg.top, zwei grosse IPTVEditor-4-XMLTV-Dateien, ~32.000 Kanaele
  gesamt): Der Nutzer bestand darauf, dass darin praktisch alle Logos
  vorhanden sein muessten - und hatte recht. Der erste Abgleichsversuch
  fand nur wenige hundert Treffer per exaktem Namensvergleich; das
  eigentliche Problem war, dass myepg (wie die eigene Playlist) PPV-
  Kanaele unter dem VOLLEN, sich staendig aendernden Live-Event-Namen
  fuehrt (z. B. "- NO EVENT STREAMING - | 8K EXCLUSIVE | DE: SPORT
  DEUTSCHLAND PPV 19"), nicht unter dem stabilen Kern. Erst die
  Anwendung derselben Kern-Extraktions-Logik wie beim eigenen
  `m3u_playlist_abgleichen()` (siehe `kern_und_event_extrahieren()`/
  `kern_vorne_und_event_extrahieren()` in `generate_epg.py`) auf die
  myepg-Rohnamen brachte den Durchbruch: mehrere tausend zusaetzliche
  Treffer in mehreren Nachbesserungsrunden, u. a. durch Beheben von:
  - faelschlich abgeschnittenem Laender-Praefix (die Extraktion nahm
    an, "US:" vor einem Kern sei immer ein reines Land-Kuerzel und
    entfernte es - bei Kernen wie "US: ESPN+ PPV 376" ist der Praefix
    aber Teil des eigentlichen, in `sender.txt` gespeicherten Kerns)
  - Doppelpunkt-Suffix-Muster ganz ohne Pipe-Zeichen (z. B. "...
    :Flo College 03")
  - Kern-am-Zeilenanfang-Muster ohne Pipe (z. B. "CA: CHICAGO WOLVES")
  - der Erkenntnis, dass die Kern-Extraktion nicht nur auf myepgs
    Rohdaten angewendet werden muss, sondern auch auf die EIGENEN in
    `sender.txt` gespeicherten `NAME:`-Werte, wenn diese selbst noch
    unverarbeiteten Roh-Event-Text enthalten (ein Ueberbleibsel
    fehlerhafter Kern-Erkennung beim urspruenglichen Playlist-Import)
  - Marken-Fallback: hat mindestens eine Nummer einer nummerierten
    PPV-Reihe (z. B. "SPORT DEUTSCHLAND PPV") ein funktionierendes
    Logo gefunden, wird dasselbe Logo automatisch auch den anderen
    Nummern derselben Reihe ohne eigenen Treffer zugewiesen
- **Selbst-Hosting:** Alle neu gefundenen externen Bilder wurden
  heruntergeladen, auf max. 300px/256 Farben optimiert (gleiche
  Konvention wie `logos/playlist_import/`) und liegen jetzt unter
  `logos/m3uassets_import/` bzw. `logos/externe_logos_import/` -
  98% aller funktionierenden Logos sind mittlerweile selbst gehostet,
  nur noch ~300 (v. a. Wikimedia, wegen aggressivem serverseitigem
  Rate-Limiting bei vielen parallelen Downloads) haengen extern.
- **Verbleibende ~1.850 Sender ohne Logo:** stichprobenartig direkt
  gegen die myepg-Rohdaten verifiziert - dort entweder gar nicht als
  eigener Kanal vorhanden oder selbst mit dem toten Picon-Host
  verlinkt. Das duerfte nah am tatsaechlich erreichbaren Maximum sein.
- **Wichtige Lehre:** Der Nutzer wusste aus eigener Erfahrung, dass
  seine bezahlte externe EPG-Quelle vollstaendiger ist, als es der
  erste (zu oberflaechliche) Abgleichsversuch nahelegte - sich
  gegenueber dieser Einschaetzung nicht vorschnell mit "ist wohl nicht
  da" zufriedengeben, sondern bei Unstimmigkeiten (Kanal laut Nutzer
  vorhanden, aber kein Treffer) gezielt mit `grep`/Stichproben in den
  Rohdaten nachschauen, ob die eigene Abgleichslogik (nicht die Quelle)
  die Luecke ist - hier lag die Ursache dreimal hintereinander an neuen
  Kern-Extraktions-Sonderfaellen, nicht an fehlenden Daten.
- Die myepg.top-Download-URLs enthalten personenbezogene Zugangsdaten
  des Nutzers (Auftragsnummer + Schluessel) und wurden wie die Playlist-
  URL nirgends im Klartext dauerhaft festgehalten - nur temporaer im
  Scratchpad verwendet und danach wieder geloescht.

## TiviMate-Automatik-Zuordnung fuer NAME:-Sender (September 2026, grosse Untersuchung)

Der Nutzer meldete, dass TiviMate nach einem kompletten Neu-Laden der
EPG-Quelle (Loeschen + neu Anlegen) nur noch einen Bruchteil der
`NAME:`-Sender (DYN/SOCCER/DAZN/ESPN+ PPV usw. - dynamische
Live-Event-Kanaele) automatisch zuordnete (18.952 -> 12.865 von
~19.000, spaeter Fehlversuche zwischendurch bis knapp ueber 12.000).
Nach vielen Sackgassen (Leerzeichen-Varianten, Laender-Kollisionen im
internen Index, DE-Bug bei DYN PPV) war die Kernursache: TiviMate
matcht Playlist-Kanaele gegen EPG-`<channel>` primaer per **exaktem
Namensvergleich** - `tvg-id` ist in der Playlist des Nutzers praktisch
immer leer (`tvg-id=""`), Matching laeuft also ausschliesslich ueber
den sichtbaren Namen. Unsere `<channel id>`/`display-name` fuer
`NAME:`-Sender war bis dahin immer der FESTE Kern (z.B.
"US: ESPN+ PPV 1"), waehrend die Playlist selbst den KOMPLETTEN,
staendig wechselnden Live-Event-Text zeigt (z.B. "NEXT | Fairways of
Life... | US: ESPN+ PPV 1") - diese beiden Texte sind fast nie
identisch, die Namens-Zuordnung konnte darum strukturell nie
zuverlaessig greifen. Bestaetigt durch direkten Playlist-Abgleich
(Playlist-URL vom Nutzer erhalten, temporaer heruntergeladen,
analysiert, sofort wieder geloescht - wie bei den myepg-URLs oben).

**Umgesetzte Loesung** (nach dem Vorbild des frueher genutzten
externen Anbieters myepg.top, bei dem automatische Zuordnung
nachweislich funktioniert hat): `generate_epg.py`,
`m3u_playlist_abgleichen()` setzt bei jedem per Kernname gefundenen
Live-Playlist-Treffer `real_daten["kanal"]` jetzt DIREKT auf den
kompletten aktuellen Rohnamen aus der Playlist (nicht mehr nur den
stabilen Kern, und nicht nur als zusaetzlicher Alias-`display-name`
wie in einer Zwischenversion) - unabhaengig davon, ob gerade ein
echtes Event laeuft oder Leerlauf ist. Die `<channel>`-Erzeugung
(Schleife `for daten in sender_daten:`) laeuft deshalb bewusst ERST
NACH dem Live-Playlist-Abgleich, nicht mehr davor. **Bewusster
Trade-off:** eine einmal in TiviMate manuell gesetzte Zuordnung kann
bei einem Lauf mit geaendertem Live-Namen verloren gehen (die ID
aendert sich mit) - automatische Zuordnung hat hier auf Nutzerwunsch
Prioritaet.

Ergebnis nach diesem Fix (naechster Lauf): 17.287 von ~19.000 Kanaelen
automatisch zugeordnet - deutliche Verbesserung, aber noch nicht
vollstaendig.

**Zwei zusaetzliche, kleinere Fixes im selben Zuge:**
- `kern_und_event_extrahieren()`: Laender-Praefix ("DE:", "US:", ...)
  bleibt jetzt NUR bei DYN PPV/FLO RACING (deren historischer
  Sonderkonvention ohne Land) aus dem internen Live-Event-Index-
  Schluessel entfernt - bei allen anderen NAME:-Sendern (SOCCER PPV,
  DAZN PPV, ESPN+ PPV, ...) bleibt das Land Teil des Schluessels.
  Vorher kollidierten z.B. "DE: SOCCER PPV 43" und "US: SOCCER PPV 43"
  auf denselben Schluessel und ueberschrieben sich im Index gegenseitig
  (nur einer der beiden Laender bekam je Lauf ein Live-Event).
- `kanal_id_varianten()` (neue Funktion): fuer Kanal-IDs im
  "Land|Sender"-Muster (z.B. "UK| AMAZON UK EVENT 0" vs.
  "UK|AMAZON UK EVENT 0") werden jetzt BEIDE Leerzeichen-Schreibweisen
  als `<channel>`/`<programme>` ausgegeben - bestaetigt per Playlist-
  Abgleich, dass verschiedene Sender-Gruppen in derselben Playlist des
  Nutzers uneinheitlich mal mit, mal ohne Leerzeichen nach dem Pipe
  schreiben. Betrifft normale `Land|Sender|...`-Zeilen sowie
  TELEMACH:/SKY:/ARENA:/DAZN:/FREEVIEW:/TVGUIDE:/TVPASSPORT:-Sender
  und die 20 fest kodierten "DE| DYN PPV N HD"-API-Kanaele (deren
  `display-name` zusaetzlich von nur "DYN PPV N HD" auf "DE| DYN PPV N
  HD" korrigiert wurde - der echte Playlist-Name hat das Laenderkuerzel,
  vorher fehlte es nur im display-name, nicht in der ID).

**sender.txt-Datenmuell entdeckt und teilweise bereinigt:** Beim
Debuggen von "US| ESPN PLUS" (Format "US (ESPN+ 001)") fiel auf, dass
919 `NAME:`-Zeilen (500 bei "US (ESPN+ NNN)", 419 bei aehnlichen
Gruppen wie "AU (STAN NNN)") noch den kompletten alten Rohtext vom
urspruenglichen Playlist-Import (31. August) im Kernnamen stehen
hatten statt nur des sauberen Kerns, z.B.
`NAME:US (ESPN+ 001) | Soccer: Washington vs. Bay FC (ESP)
(2026-08-31 09:00:00)|<Logo>` statt `NAME:US (ESPN+ 001)|<Logo>`. Da
dieser Wert selbst ein Pipe-Zeichen enthielt, griff beim Einlesen die
Pipe-Zweig-Logik in `kern_und_event_extrahieren()` und nahm
faelschlich den alten Event-Text als Kern - der Live-Playlist-Abgleich
fand diese Sender dadurch nie. Auf reine Kernnamen reduziert (per
Skript, `NAME:(Land \([^)]+\)) \| .*?\|(Logo)` -> `NAME:\1|\2`).

**Offen/noch NICHT bereinigt:** ~500 weitere `NAME:`-Zeilen mit
aehnlichem, aber UNEINHEITLICHEM Datenmuell (unterschiedliche rohe
Restfragmente bei UEFA-, NFL-/NHL-/NBA-Team-Kanaelen, Setanta, HBO Max
UK, National League, Serie A, TNT Sports, Ligue N, Clubber TV, GaaGo,
u.a. - siehe `grep -cP '^NAME:[A-Z]{2,4} \([^)]+\)[^|]*\| ' sender.txt`
als Ausgangspunkt, aber die Formate variieren zu stark fuer eine
einzige sichere Regex-Korrektur wie beim ESPN+/STAN-Fix). Diese
koennten einen Teil der nach dem 17.287-Fix weiterhin fehlenden ~1.000
bis 2.000 Sender erklaeren - noch nicht mit einem frischen Lauf
verifiziert, ob nach den ESPN+/STAN-Fixes noch was fehlt und woran es
dann liegt. Bei kuenftigen "Sender X wird nicht automatisch zugeordnet"
Meldungen: ZUERST `grep "^NAME:.*<Sendername>" sender.txt` pruefen, ob
der Kernname sauber ist (kein eingebetteter alter Event-Text), BEVOR
an der generate_epg.py-Logik gesucht wird - das war in dieser Session
oft die eigentliche Ursache, nicht ein Code-Bug.

**Wichtige Lehren fuer kuenftige Debugging-Sessions zu diesem Thema:**
- TiviMates automatische Kanalzuordnung ist eine reine Client-Logik,
  die von hier aus nicht direkt einsehbar ist - Verifikation lief
  ausschliesslich ueber (a) die generierte XML-Datei direkt pruefen
  (`gunzip -c Epg_365_Tage.xml.gz`, nach `<channel id=` und
  `<programme ... channel=` grep-en) und (b) den Nutzer Screenshots
  aus TiviMate zeigen zu lassen (v.a. der "Sendernamen-Editor", der den
  ROHEN aktuellen Playlist-Namen zeigt - sehr nuetzlich zum Vergleich
  gegen unsere generierte ID).
  - Zwischenzeitlich wurde ein bereits gepushter Fix (Laender-Praefix
    beim Kern entfernen) auf Nutzerwunsch komplett zurueckgesetzt, weil
    zunaechst der falsche Verdacht bestand, er sei fuer den
    TiviMate-Einbruch verantwortlich - spaeter per Log-Vergleich zweier
    Workflow-Laeufe widerlegt (der fragliche Lauf hatte davor UND
    danach denselben Live-Match-Mechanismus, nur mit 0 vs. echten
    Treffern - TiviMates Zuordnungszahl war in beiden Faellen aehnlich
    hoch/niedrig, unabhaengig vom Fix). Der Fix wurde in einer
    Folge-Session wieder eingebaut, diesmal korrekt mit Laender-
    Kollisions-Schutz. Lehre: Bei Verdacht "mein letzter Commit hat X
    kaputt gemacht" IMMER zuerst per `git diff <alter-commit> --
    <datei>` und Workflow-Logs (`gh`/GitHub-MCP-Tools,
    `get_workflow_run_logs_url` + Log-Text durchsuchen) verifizieren,
    ob der Verdacht wirklich stimmt, bevor zurueckgesetzt wird -
    spart ggf. eine komplette Neuentwicklung.
- Playlist-URL des Nutzers wurde in dieser Session mehrfach direkt
  angefragt (temporaerer Download nach `/scratchpad`, sofort nach
  Auswertung wieder geloescht, niemals im Chat wiederholt) - sehr
  nuetzlich, um TiviMate-Verhalten mit echten Rohdaten statt Vermutungen
  zu erklaeren. Bei aehnlichen Debugging-Faellen (Kanal X wird nicht
  erkannt) ist ein gezielter `grep` in der frisch heruntergeladenen
  Playlist nach dem Kanalnamen oft der schnellste Weg zur Diagnose.

## September 2026: Komma-Bug im Playlist-Parser + DYN-PPV-1-20-Playlist-Abgleich

Nach dem TiviMate-Zuordnungs-Fix (17.287 Kanaele) meldete der Nutzer per
Screenshot zwei einzelne Sender ("Rich Eisen Show"/"US: ESPN+ PPV 4",
"ESPN FC"/"US: ESPN+ PPV 7"), die trotzdem "Keine Information" zeigten.

- **Ursache:** `m3u_playlist_abgleichen()` trennte den #EXTINF-
  Anzeigenamen bisher am LETZTEN Komma der gesamten Zeile
  (`zeile.rsplit(",", 1)`). Enthaelt der rohe Live-Event-Name selbst ein
  Komma (z.B. "NEXT | WED, 9/2 - THE RICH EISEN SHOW | ... | US: ESPN+
  PPV 4" - das Komma steckt in "WED, 9/2"), schnitt das faelschlich den
  Anfang ab ("NEXT | WED" ging verloren) - die erzeugte Kanal-ID
  entsprach dann nicht mehr dem echten Playlist-Namen. Fix: Trenner ist
  jetzt das erste Komma NACH dem letzten Anfuehrungszeichen der Zeile
  (Ende des letzten #EXTINF-Attributs wie `group-title="..."`) -
  funktioniert unabhaengig davon, ob der Name selbst Kommas enthaelt.
  Im gesamten generierten XML gab es zum Pruefzeitpunkt nur genau diese
  zwei betroffenen Kanaele.
- **DYN PPV 1-20 (API-Kanaele, siehe Abschnitt oben) ebenfalls
  betroffen:** Kanal 14-20 zeigten "Keine Information", obwohl die
  Sendungsdaten (Leerzeiten-Platzhalter, echte API-Events) im XML
  nachweislich vorhanden waren - reines TiviMate-Zuordnungsproblem,
  keine Datenluecke. Ursache vermutlich: anders als die NAME:-Sender
  nutzte diese Gruppe bisher IMMER einen hartcodierten String
  ("DE| DYN PPV {i} HD") als Kanal-ID, nie den tatsaechlichen Playlist-
  Namen - eine minimale, unsichtbare Abweichung dort wuerde das
  automatische Matching verhindern, obwohl der Name auf den ersten
  Blick identisch aussieht (bestaetigt: manuelle Zuordnung durch den
  Nutzer funktionierte und blieb nach Refresh bestehen, automatische
  nicht). Fix: Vor der Kanal-Definition wird jetzt einmalig die eigene
  Playlist nach den 20 "DE| DYN PPV N HD"-Kanaelen durchsucht (gleiche
  Komma-Trennlogik wie oben) und bei Treffer der exakte rohe Playlist-
  Name fuer ID/display-name UND alle zugehoerigen `<programme>`-
  Eintraege (Live-Events, Basketball, Leerzeiten) verwendet - ohne
  PROVIDER-Secret oder bei Fehler bleibt der bisherige hartcodierte
  String als Fallback. Noch nicht mit einem frischen Lauf verifiziert,
  ob das die Kanaele 14-20 tatsaechlich behebt.
- **Leerlauf-Text der DYN-PPV-1-20-API-Kanaele vereinheitlicht:** zeigte
  bisher "Im Moment keine Live Events, bleib dran" - auf Nutzerwunsch
  jetzt "Dyn Sport (N) ᴺᵒ ᴸⁱᵛᵉ", identisch zur DYN-PPV-1-50-Konvention.

## Logo-Regel: IMMER selbst hosten, nie extern verlinken (bestaetigt September 2026)

Der Nutzer hat ausdruecklich bestaetigt: JEDES neu gefundene/gepruefte
Logo wird IMMER heruntergeladen, optimiert (max. 300px Kantenlaenge,
256-Farben-Palette, siehe "Logo-Groesse"-Abschnitt oben) und unter
`logos/<name>/` im eigenen Repo abgelegt - niemals eine externe URL
direkt in `sender.txt` eintragen, auch nicht bei "seriösen" Quellen wie
Logopedia/Fandom oder offiziellen Sender-Webseiten. Grund: Kontrolle
ueber Erreichbarkeit/Ladezeit/Persistenz behalten ("safe sein"), statt
von Drittanbieter-Hosts abhaengig zu sein (die immer wieder ausfallen,
siehe die toten Picon-Hosts 103.176.90.95/51.158.145.100). Diese Regel
gilt fuer JEDE zukuenftige Logo-Recherche, nicht nur fuer die in dieser
Session gefundenen Faelle.

### Konkrete Logo-Funde dieser Session

- **BR HD** (`DE|BR HD`): totem Picon-Host-Link ersetzt durch aus
  `tv-logo/tv-logos` (GitHub, oeffentliches Logo-Repo, `countries/
  germany/br-de.png`) heruntergeladenes, selbst gehostetes Logo unter
  `logos/br/br.png`.
- **Hajduk TV** (`HR|HAJDUK TV`): das bisherige Logo
  (`logos/hajduk_tv/hajduk_tv.png`, urspruenglich "von tvprofil.com")
  stellte sich als falsch heraus - nur ein generisches "HD"-
  Platzhaltersymbol, kein echtes Senderlogo. Durch vom Nutzer
  bereitgestelltes echtes Logo (rot-blaue Vereinsfarben, "H" +
  Play-Symbol) ersetzt, unter derselben Datei/URL.
- **Hayat Love Box** und **Hayat Stil i Zivot** (beide `BA|...  ⱽᴵᴾ
  ᴿᴬᵂ`): hatten noch den toten Picon-Host - echte Logos gefunden ueber
  die MediaWiki-API von logopedia.fandom.com
  (`Category:Television_channels_in_Bosnia_and_Herzegovina`, per
  `action=query&list=categorymembers` + `prop=pageimages`, da die
  normale Wiki-Seite hinter einer Cloudflare-Challenge haengt). Beide
  Logos lagen zufaellig schon identisch unter `logos/externe_logos_import/`
  (fuer die "VIP RAW"-Varianten) - kein neuer Download noetig, nur die
  bestehenden URLs in den betroffenen Zeilen nachgetragen.
- **Recherchierte, aber KEIN Treffer:** `tv-logo/tv-logos` deckt weder
  Bosnien noch Nordmazedonien als eigene Laender ab (nur Kroatien/
  Serbien u.a.) - gegen unsere ~224 logolosen Sender und ~923 Sender mit
  totem Picon-Host kaum Ueberschneidung (nur BR HD als echter Treffer).
  Logopedia deckt bei Bosnien nur ~104 groessere/nationale Kanaele ab,
  keine lokalen Sender wie Doboj TV/Simic TV/RTV Herceg Bosne/Super TV
  Media Tuzla/TV Sandzak/Hit Televizija Brcko/Blagovijesti TV - fuer
  diese bleibt weiterhin keine verlaessliche Logo-Quelle bekannt.
  `hrvatskitelekom.hr/televizija/programski-paketi` ist login-geschuetzt
  (SSO/OIDC, "login_required") und ohne Kundenzugang nicht abrufbar.

## DE: SOCCER PPV 1-200: fehlender Sender-Eintrag behoben

Bei einer Ueberpruefung auf Nutzerwunsch ("nicht alle Logos werden
angezeigt") stellte sich heraus: Alle 200 Logo-Dateien
(`logos/soccer_ppv/soccer_ppv_1.png` bis `_200.png`) waren vorhanden,
korrekt benannt und live erreichbar, und alle 199 vorhandenen
`NAME:DE: SOCCER PPV N`-Zeilen zeigten korrekt auf ihre jeweilige
Nummer - ABER die Zeile fuer Nummer 8 fehlte komplett in `sender.txt`
(reines Datenluecken-Problem beim urspruenglichen Playlist-Import, kein
Logik-Fehler). Ergaenzt an der alphabetisch richtigen Stelle (zwischen
"PPV 79" und "PPV 80", da die Datei nicht numerisch sortiert ist).
Bei aehnlichen "manche Logos fehlen"-Meldungen bei nummerierten
NAME:-Gruppen: IMMER zuerst pruefen, ob fuer JEDE Nummer im erwarteten
Bereich (1 bis N) tatsaechlich eine eigene `NAME:`-Zeile existiert
(`for n in range(1,N+1): ...` gegen die Zeilen abgleichen), nicht nur
die Logo-Dateien selbst - eine fehlende Zeile faellt beim reinen
Datei-Check nicht auf.

**Offene Frage (noch nicht verifiziert):** Der Nutzer fragte, ob die
fehlende Nummer 8 der Grund war, warum in TiviMate auch mehrere ANDERE
Nummern derselben Gruppe keine Logos zeigten - technisch unwahrscheinlich,
da jeder `<channel>`/`<programme>`-Block in der generierten XML
unabhaengig ist und ein fehlender Block fuer Nummer 8 keinen Einfluss
auf das Parsen/Anzeigen der Bloecke fuer 1-7/9-200 haben sollte. Falls
nach dem naechsten Lauf weiterhin einzelne andere Nummern fehlen,
liegt die Ursache vermutlich woanders (z.B. dasselbe TiviMate-
Auto-Matching-Verhalten wie bei DYN PPV 1-20/ESPN+) - noch nicht mit
echten Daten gegengeprueft.

## Sport Klub HR (SK 1-12/4K/Esports/Fight/Golf): neue Quelle sportklub_epg.py

Der Nutzer meldete per Screenshot, dass `HR|SK 1`-`SK 10` nur den
generischen Text zeigten und SK1 sogar eine komplett falsche deutsche
Sendung anzeigte. Root Cause: MojMaxTV (unsere normale automatische
HR-Quelle) fuehrt seit September 2026 GAR KEINEN "Sport Klub"-Kanal mehr
in der eigenen Kanalliste (nur noch Arena Sport 1-10 u.ae., live per API
verifiziert) - der unscharfe difflib-Fallback in `mojmaxtv_kanal_finden()`
matchte "SK 1" dadurch faelschlich auf den voellig unabhaengigen Kanal
"Sport 1" (deutsche Sendungen). Fix in zwei Teilen:

1. **`mojmaxtv_epg.py`**: Der "SK N"->"Sport Klub N"-Alias akzeptiert
   jetzt nur noch einen EXAKTEN Namenstreffer, keinen unscharfen
   Fallback mehr (lieber kein Treffer als ein falscher).
2. **Neue Quelle `sportklub_epg.py`**: Der Nutzer bestand darauf, ECHTE
   Programmdaten zu bekommen, nicht nur "kein falscher Treffer" - auf
   ausdruecklichen Hinweis des Nutzers wurde zuerst live geprueft, ob
   eine bereits integrierte Quelle (Telemach/mtel.ba/mts.rs) Sport Klub
   fuehrt (alle drei live per API abgefragt: kein einziger "Sport
   Klub"/"SK"-Treffer in allen dreien). `sportklub.hr` selbst laedt sein
   TV-Programm per JS-Bundle nach (`web-apps.ug.cdn.united.cloud`), ist
   nicht direkt per HTTP-Request scrapbar. Stattdessen wird jetzt der
   oeffentliche, community-gepflegte XMLTV-Spiegel von epgshare01.online
   (`epg_ripper_SPORTKLUB1.xml.gz`, laut eigenem `<url>`-Tag von
   sportklub.hr selbst gespeist, 16 Kanaele: SK 1-12, SK 4K, SK Esports,
   SK Fight, SK Golf) als zweiter automatischer Versuch fuer alle
   `HR|SK N`-Sender genutzt, NACH MojMaxTV (nur wenn MojMaxTV nichts
   liefert - siehe `mojmaxtv_sender`-Schleife in `generate_epg.py`, neuer
   `sportklub_intervalle`-Eintrag in der `mojmaxtv`-Fallback-Kette).
   Genau wie bei plutotv_epg.py wird die komplette XMLTV-Datei nur
   EINMAL pro Lauf geladen und lokal gematcht (kein API-Request pro
   Kanal). Kanalzuordnung laeuft bewusst NICHT ueber Fuzzy-/Kern-Abgleich
   (die epgshare01-Namen "SK 1"/"SK 10"/"SK 11" sind sich als Text zu
   aehnlich), sondern ueber einen exakten Nummern-/Wort-Vergleich
   (`sportklub_kanal_finden()`, Regex auf die fuehrende Zahl bzw. feste
   Woerter Esports/Fight/Golf) - kein Fehltreffer-Risiko. Degradiert wie
   alle anderen Quellen graceful auf [] bei jedem Fehler.
   Live verifiziert: SK 1-12/4K/Esports/Fight/Golf liefern jeweils echte
   Sendungen (z.B. SK 1: 44 Sendungen/2 Tage), SK 99 (nicht existent)
   liefert sauber `None`.

## RS| ARENA SPORT 1-5 PREMIUM: identisches Programm bei allen 5 Sendern (mts.rs)

Der Nutzer meldete per Screenshot, dass `RS|ARENA SPORT 1-5 PREMIUM`
(HD und nicht-HD) im EPG-Raster ueberall identisches Programm zeigten
("Fudbal - Brazilska liga" bei allen). Root Cause: mts.rs (unsere
automatische RS-Quelle) fuehrt diese Kanaele unter vertauschter
Wortreihenfolge ("Arena PREMIUM 1".."Arena PREMIUM 5" statt "Arena
Sport 1 Premium" wie in `sender.txt`) - der exakte Namensabgleich in
`mts_kanal_finden()` griff dadurch nie, und der unscharfe difflib-
Fallback kollabierte alle 5 sich sehr aehnlichen, kurzen normalisierten
Namen faelschlich auf denselben einen Kanal (beobachtet: alle auf
"Arena PREMIUM 5"). Fix: `mts_kanal_finden()` (`quellen/mts_epg.py`)
prueft jetzt VOR dem Fuzzy-Pfad eine feste Regex-Alias-Aufloesung
(`ARENA SPORT N PREMIUM[ HD]` -> exakt `Arena PREMIUM N`), analog zum
MRT/SK-Alias-Muster weiter oben - kein Fehltreffer-Risiko mehr. Live
verifiziert: alle 5 Kanaele liefern jetzt jeweils eigene, unterschiedliche
echte Sendungen.

## MAGENTA SPORT PPV 1-18: echte Programmdaten ueber epgshare01.online/myTeamTV (neue Quelle magenta_myteam_epg.py)

Der Nutzer meldete, dass `MAGENTA SPORT PPV 1`-`18` NIE ein Event zeigen -
weder aktuell noch in Zukunft - obwohl er wusste, dass z.B. auf PPV 1
Donnerstag gegen 19 Uhr ein echtes Event laeuft.

**Erster Loesungsversuch war falsch und wurde zurueckgenommen:** Zunaechst
wurde vermutet, dies sei derselbe Datenluecken-Bug wie bei DAZN PPV/SPORT
DEUTSCHLAND PPV (statische `DE|...`-Zeile statt `NAME:`-Zeile) und die 36
Zeilen entsprechend auf `NAME:DE: MAGENTA SPORT PPV N` umgestellt. Ein
direkter Abgleich gegen die echte IPTV-Playlist des Nutzers (temporaer
heruntergeladen, ausgewertet, sofort wieder geloescht) widerlegte das
aber: Anders als DAZN/SOCCER/ESPN+ PPV ist der rohe Playlist-Kanalname
bei MAGENTA SPORT PPV 1-18 (HD UND RAW) komplett STATISCH - kein NEXT/
LIVE/ENDED-Marker, kein sich aenderender Text. Der
`m3u_playlist_abgleichen()`-Mechanismus hat hier also strukturell nichts
zum Auslesen, unabhaengig vom sender.txt-Format - die `NAME:`-Umstellung
haette nichts gebracht und haette zusaetzlich das HD/RAW-Playlist-
Matching kaputt gemacht (beide Varianten waeren auf dieselbe Kanal-ID
kollabiert). Wurde vollstaendig zurueckgerollt.
Zusaetzlich bestaetigt: Magenta selbst hat in seiner oeffentlichen
MPX-Feed-API (die normale `MAGENTA:`-Quelle, siehe `magenta_epg.py`)
KEINE separaten PPV-Kanaele - nur den einen Basis-Kanal "MagentaSport"
(liefert dort nur einen generischen "MagentaSport Programmübersicht"-
Platzhalter alle 4h, keine echten Einzel-Event-Titel) - ein
`MAGENTA:`-Praefix haette hier also ohnehin nicht geholfen.

**Tatsaechliche Loesung:** Magentas PPV-Events werden auf epgshare01.online
unter der Marke "myTeamTV" gefuehrt ("Sport 1 - myTeamTV" bis "Sport 18 -
myTeamTV", Nummerierung identisch zu unseren PPV-Nummern) - Teil des
allgemeinen `epg_ripper_DE1.xml.gz`-Sammelfeeds, kein eigener Feed. Live
bestaetigt: Kanal 1 zeigt Donnerstag 17:00 UTC (=19:00 Uhr deutscher Zeit)
"Live: Champions Hockey League" - exakt das vom Nutzer erwartete Event.
Neues Modul `magenta_myteam_epg.py` (Muster wie plutotv_epg.py/
sportklub_epg.py: EINMAL pro Lauf laden, gefiltert auf die 18 relevanten
Kanaele um den Speicherbedarf klein zu halten, dann lokal matchen) als
SECHSTER Versuch in die bestehende DE-Kaskade eingehaengt (nach deswird.org/
Pluto TV/tvmovie.de/hoerzu.de/Samsung TV Plus), NUR fuer Sender, deren Name
auf "MAGENTA SPORT PPV N" passt (exakter Nummern-Regex, kein Fuzzy-Abgleich -
kein Fehltreffer-Risiko). Der generische "myTeamTV: Momentan kein Programm"-
Platzhalter der Quelle selbst wird herausgefiltert (gilt nicht als echtes
Event). Die urspruenglichen statischen `DE|MAGENTA SPORT PPV N HD/RAW`-
Zeilen in sender.txt bleiben unveraendert (korrekt so, siehe oben) - der
Fix sitzt komplett im DE-Kaskade-Code, keine sender.txt-Aenderung noetig.

## Kern-Extraktion um generische Kern-am-Ende/Kern-am-Anfang-Muster erweitert (Milb, Flo College, Tennis, MLS, NBA, NCAAF)

Der Nutzer schickte Screenshots mehrerer NAME:-Sendergruppen (Milb 1-100,
Flo College 1-100, Tennis, MLS, NBA Summer League, NCAAF 1-70), die trotz
vorhandener sender.txt-Zeilen NIE ein echtes Live-Event zeigten. Zwei
getrennte Ursachen, beide behoben:

1. **Datenmuell in sender.txt (wie beim fruehereren ESPN+/STAN-Fix):**
   64 von 100 Milb-Zeilen, 2 von 100 Flo-College-Zeilen sowie ALLE
   Tennis-/MLS-/NBA-Zeilen trugen noch den kompletten alten Rohtext vom
   urspruenglichen Playlist-Import im Kernnamen (z.B. `NAME:TAMIU vs West
   Alabama @ Aug 31 5:00 PM :Flo College  02|<Logo>` statt `NAME::Flo
   College  02|<Logo>`) - dadurch registrierte `name_pipe_kanal_index`
   einen falschen/instabilen Index-Schluessel. Per Skript auf den reinen
   Kern reduziert (106 Zeilen insgesamt: 64 Milb, 2 Flo College, 30
   Tennis, 3 MLS, 5 NBA). Milb hatte dadurch zusaetzlich eine
   Nummernluecke (1-64 fehlten de facto, da unter Muell-Namen verborgen) -
   nach der Bereinigung durchgehend 1-100 ohne Luecke.
2. **Struktureller Code-Gap in der Kern-Extraktion (der eigentliche,
   schwerwiegendere Bug):** `kern_und_event_extrahieren()`/
   `kern_vorne_und_event_extrahieren()` (`generate_epg.py`) erkannten im
   No-Pipe-Zweig bisher NUR das DYN-PPV/FLO-RACING-Muster bzw. (Kern-
   vorne) nur DIRTVISION/FA PLAYER - jedes andere No-Pipe-Namensschema
   (egal wie sauber der sender.txt-Kern selbst war) wurde beim
   Live-Playlist-Abgleich NIE erkannt, weil der KOMPLETTE rohe Playlist-
   Name als "Kern" genommen wurde, statt den eigentlichen stabilen Teil
   herauszuloesen. Das betraf strukturell JEDE Sendergruppe mit Kern-am-
   Ende- (`<Event> :<Name> <N>`, z.B. Milb/Flo College/Tennis/MLS/NBA)
   oder Kern-am-Anfang-Doppelpunkt-Konvention (`<Name> <N>: <Event>`,
   z.B. NCAAF) - unabhaengig von sender.txt.
   **Fix:** Beide Funktionen um generische, an `^`/`$` verankerte Muster
   erweitert (`:\s*([A-Za-z][A-Za-z0-9+.]*(?:\s+[A-Za-z0-9+.]+)*\s+0*\d+)\s*$`
   fuer Kern-am-Ende, `^\s*([A-Za-z][A-Za-z0-9+.]*(?:\s+[A-Za-z0-9+.]+)*\s+0*\d+)\s*:\s*(.*)$`
   fuer Kern-am-Anfang) - greift jetzt automatisch fuer JEDE aktuelle und
   kuenftige No-Pipe-NAME:-Gruppe mit diesem Namensschema, ohne
   anbieterspezifischen Code. Risikofrei: ein falsch geratener Kern
   findet einfach keinen Treffer im Index (`name_pipe_kanal_index.get()`
   liefert `None`) und faellt auf den bisherigen generischen Fallback
   zurueck - kein Fehltreffer-Risiko wie bei einem unscharfen Abgleich,
   da hier ausschliesslich exakte Dictionary-Lookups entscheiden. Die
   Ankerung an `^`/`$` verhindert, dass eine Uhrzeitangabe im Event-Text
   selbst (z.B. "7:00 PM"/"5:00 PM") faelschlich als Trenner-Doppelpunkt
   genommen wird - manuell gegen alle Beispieltexte aus den Nutzer-
   Screenshots verifiziert (Milb, Flo College, NCAAF, Tennis, MLS, NBA).
   Bestehende Sonderfaelle (DYN PPV, FLO RACING, Super League Plus,
   DIRTVISION, FA PLAYER, Clubber) werden weiterhin zuerst geprueft und
   bleiben unveraendert, da sie vor dem neuen generischen Pfad im
   Code stehen.

## MAGENTA SPORT PPV: myTeamTV-Fix griff nicht (deswird.org-Fehltreffer verhinderte es)

Nach dem myTeamTV-Fix (siehe oben) und dem naechsten automatischen
Workflow-Lauf zeigte PPV 1 trotzdem weiterhin nur "MagentaSport
Programmübersicht" (generischer Text) statt des erwarteten Events -
der Nutzer sprang testweise per Vorlauf auf Donnerstag 19 Uhr, ohne
Erfolg. Root Cause: deswird.org (die ERSTE Quelle in der DE-Kaskade,
also VOR dem neu eingebauten myTeamTV-sechsten-Versuch) matcht "MAGENTA
SPORT PPV 1 HD" per unscharfem Abgleich (`deswird_kanal_finden()`)
faelschlich auf den voelling anderen, echten Basis-Kanal "MagentaSport"
(derselbe Kanal, der schon bei der urspruenglichen Magenta-API-
Untersuchung nur einen generischen "Programmübersicht"-Platzhalter
lieferte - hier aber via deswird.org, nicht via magenta_epg.py). Diese
"echten" (aber fuer den Nutzer nutzlosen) Daten zaehlten als Treffer
und beendeten die Kaskade per `continue`, BEVOR myTeamTV ueberhaupt
drankam - der klassische Fehltreffer-Bug-Typ dieser Session (wie
Sport Klub/Arena Premium/MRT), nur diesmal in deswird_kanal_finden()
statt in einem der difflib-basierten Module.
**Fix:** In der DE-Kaskaden-Schleife (`generate_epg.py`,
`plutotv_sender`-Schleife) wurde ein frueher Check ergaenzt: Sender,
deren Name auf `^MAGENTA\s*SPORT\s*PPV\s*\d+` passt, ueberspringen
deswird.org/PlutoTV/tvmovie.de/hoerzu.de/Samsung TV Plus komplett und
gehen DIREKT zu myTeamTV (`continue` nach dem myTeamTV-Versuch) - kein
Risiko, dass irgendeine der fuenf generischen DE-Quellen sie noch
abfaengt. Der alte myTeamTV-Code-Block tief in der samsungtv-Kaskade
wurde entfernt (jetzt ueberfluessig). Live verifiziert: `deswird_kanal_finden("MAGENTA SPORT PPV 1 HD")`
matcht weiterhin auf "MagentaSport" (das Modul selbst wurde nicht
veraendert - der Fehltreffer ist an sich harmlos fuer andere Sender),
aber die PPV-Sender erreichen deswird.org jetzt gar nicht mehr und
bekommen stattdessen zuverlaessig die myTeamTV-Daten ("Live: Champions
Hockey League" fuer PPV 1 am Donnerstag 19 Uhr).
**Lehre:** Bei einer neuen Fallback-Quelle IMMER pruefen, ob eine der
VORGESCHALTETEN Quellen in der Kaskade den Sendernamen per Fuzzy-
Abgleich auf einen unpassenden, aber "echten" Kanal matchen und damit
generische/falsche Daten als "Treffer" liefern koennte - das Vorhandensein
ECHTER (aber falscher) Daten wird vom bestehenden Code nicht von einem
ECHTEN, PASSENDEN Treffer unterschieden.

## DE: SPORT DEUTSCHLAND PPV 1-100: totes Logo + eigener Leerlauf-Text

Der Nutzer meldete, dass alle 100 `DE: SPORT DEUTSCHLAND PPV`-Sender kein
Logo zeigen. Ursache: alle 100 Zeilen zeigten auf denselben toten
Picon-Host `51.158.145.100` (siehe "Logo-Regel"-Abschnitt oben - einer
der beiden bereits bekannten toten Hosts). Fix: offizielles App-Icon von
sportdeutschland.tv selbst (`/apple-touch-icon.png`, S+Pfeil-Logo,
schwarzer Hintergrund) heruntergeladen, optimiert (max. 300px/256
Farben) und unter `logos/sport_deutschland/sport_deutschland.png`
selbst gehostet, alle 100 Zeilen darauf umgestellt.
Zusaetzlich auf Nutzerwunsch: Leerlauf-Text (kein erkanntes Live-Event)
folgt jetzt derselben "N ᴺᵒ ᴸⁱᵛᵉ"-Konvention wie DYN PPV/FA Player/
Super League Plus (z.B. "Sport Deutschland Ppv 42 ᴺᵒ ᴸⁱᵛᵉ") statt des
generischen "<Kurzname> ᴸⁱᵛᵉ"-Catch-all-Fallbacks - neuer Regex-Zweig
in `generate_epg.py` (`SPORT\s*DEUTSCHLAND\s*PPV\s*0*(\d+)`) vor dem
generischen Fallback, betrifft automatisch alle 100 Nummern.
Auf Nutzerwunsch spaeter durch ein nummeriertes Logo-Set ersetzt
(gleiches Prinzip wie DYN PPV/Sky Select/Vodafone GO): offizielles
Icon (S+Pfeil, schwarzer Hintergrund) plus "SPORT DEUTSCHLAND"-
Schriftzug plus Kanalnummer in Gelb, alle 100 Varianten per Skript
erzeugt und optimiert unter `logos/sport_deutschland/<N>.png`.

## KRITISCHER REGRESSIONS-BUG (September 2026): Kern-am-Ende-Fix brach "Land: Name PPV N"-Konvention flaechendeckend

Der Nutzer meldete per Screenshots viele verschiedene Sendergruppen
(RTL+ PPV, ESPN+ PPV VIP, NETFLIX PPV, B/R MAX SPORTS PPV, FIFA+ PPV,
NA| PPV & LIVE EVENTS, DE: SOCCER PPV) gleichzeitig kaputt: Sendungstitel
zeigte teils nur noch "DE"/"US" statt eines sinnvollen Textes, Live-
Events wurden nicht mehr extrahiert, keine generischen Platzhalter mehr.
Root Cause: Der in derselben Nacht eingebaute generische Kern-am-Ende-
Fix (siehe Abschnitt oben, fuer Milb/Flo College/Tennis/MLS/NBA) wird
in `kern_und_event_extrahieren()` NICHT nur beim Live-Playlist-Abgleich
verwendet, sondern auch beim URSPRUENGLICHEN EINLESEN jeder NAME:-Zeile
aus `sender.txt` selbst (Zeile ~598) - und das neue Regex-Muster
(":<Kern> <Nummer>" am Zeilenende) matchte dabei UNBEABSICHTIGT auch
die weit verbreitete pipe-lose "Land: Name PPV N"-Konvention selbst
(z.B. "DE: RTL+ PPV 28" - der Doppelpunkt direkt nach "DE" wurde
faelschlich als der gesuchte Trenner erkannt, "RTL+ PPV 28" als Kern,
das blosse "DE" als vermeintlicher "Event-Text"). Das betraf potenziell
JEDE NAME:-Sendergruppe in diesem Format (RTL+/SOCCER/ESPN+/DAZN/
NETFLIX/MLS/FIFA+/B-R-MAX-SPORTS/NA-PPV-LIVE-EVENTS PPV usw. - mehrere
tausend Zeilen), da der urspruengliche Kern durch das Laenderkuerzel
verloren ging und "DE"/"US" als angeblicher Event-Text durchging.
**Fix:** `kern_und_event_extrahieren()` prueft jetzt VOR der Uebernahme
des Kern-am-Ende-Treffers, ob der Text VOR dem gefundenen Doppelpunkt
nur ein blosses 2-4-Buchstaben-Laenderkuerzel ist (`re.fullmatch(r"[A-Za-z]{2,4}", ...)`,
dieselbe Pruefung wie an mehreren anderen Stellen in dieser Funktion
bereits verwendet) - trifft das zu, wird der Treffer verworfen und
die Zeile faellt auf die alte, korrekte Behandlung zurueck (kompletter
String bleibt Kern, keine Aenderung). Gegen alle betroffenen echten
Beispiele aus den Nutzer-Screenshots verifiziert (RTL+/ESPN+ PPV VIP/
NETFLIX/B-R-MAX-SPORTS/FIFA+/NA-PPV-LIVE-EVENTS/SOCCER PPV) sowie
gegen die urspruenglichen Milb/Flo-College-Faelle - beide funktionieren
jetzt nebeneinander korrekt.
**Lehre:** Eine neue generische Regex-Erweiterung an einer zentral
wiederverwendeten Parsing-Funktion (hier: sowohl fuers Einlesen von
sender.txt als auch fuer den Live-Playlist-Abgleich verwendet) IMMER
gegen die HAEUFIGSTEN bestehenden Formate der Datei testen, nicht nur
gegen die neuen Zielformate, die der Fix eigentlich beheben sollte -
"risikofrei, weil der Index-Lookup sonst einfach fehlschlaegt" gilt nur
fuer den LIVE-Abgleich (wo ein falscher Kern einfach keinen Treffer
findet), NICHT fuers Einlesen von sender.txt selbst, wo der falsch
erkannte Kern direkt und ungeprueft zum tatsaechlichen Sendernamen wird.

## Grosse Logo-/Extraktions-Aufraeumrunde (September 2026, nach Regressions-Fix)

Nach dem kritischen Regressions-Fix (siehe oben) meldete der Nutzer per
9 Screenshots eine ganze Reihe weiterer Logo-/Extraktionsluecken, der
Reihe nach behoben:

- **FIFA+ PPV (50 Sender):** Logo verlinkte nur extern auf Wikimedia
  (Regelverstoss) - Original-Logo heruntergeladen, optimiert, selbst
  gehostet unter `logos/fifa_plus/`.
- **US Tennis Channel Plus / "TC+ N" (100 Sender):** hatten GAR KEIN
  Logo (leeres Feld) - bekommen jetzt dasselbe bereits vorhandene
  Tennis-Channel-Logo wie die "US: Tennis PPV"-Gruppe.
- **PBS (33 Sender):** zeigten auf den bekannten toten Picon-Host
  `51.158.145.100` - offizielles PBS-Icon (`pbs.org/favicons/`)
  heruntergeladen, optimiert, unter `logos/pbs/` selbst gehostet, als
  einheitliches Fallback-Logo fuer alle betroffenen PBS-Varianten
  eingetragen (besser ein generisches echtes Logo als gar keins).
- **B/R Max Sports Events (12 Sender):** ebenfalls toter Picon-Host,
  kein offizielles Logo online auffindbar (bleacherreport.com liefert
  keine brauchbaren Assets) - eigenes Text-Logo erstellt ("B/R" weiss +
  "MAX SPORTS" rot auf dunkelblauem Grund), nutzergegengeprueft, unter
  `logos/br_max_sports/`.
- **UK Champions League Replay/Highlights (18 Sender):** ebenfalls
  toter Picon-Host, uefa.com aus der Sandbox nicht erreichbar (Timeout)
  - eigenes Text-Logo erstellt ("CHAMPIONS" weiss + "LEAGUE REPLAY"
    gold auf dunkelblauem Grund), unter `logos/uefa_replay/`.
- **"LIVE EVENT N" (34 Sender, `NAME:LIVE EVENT 01`-`34`):** hatte GAR
  KEIN Logo UND wurde beim Live-Playlist-Abgleich strukturell NIE
  erkannt (siehe eigener Abschnitt unten zum Bindestrich-Format) -
  eigenes Text-Logo erstellt ("LIVE" rot + "EVENT" weiss auf
  dunkelgrauem Grund), unter `logos/live_event/`.
- **RTL+ PPV/ESPN+ PPV VIP #4+#7/US NETFLIX PPV/DE SOCCER PPV:** alles
  Symptome desselben, bereits behobenen "DE"/"US"-Regressionsbugs
  (siehe Abschnitt oben) - keine weitere Aenderung noetig, loest sich
  automatisch mit dem naechsten Lauf. Alle 200 SOCCER-PPV-Nummern
  wurden zusaetzlich stichprobenartig auf Luecken geprueft (keine
  gefunden).
- Alle neuen eigenen Logos wurden dem Nutzer vor der Uebernahme als
  Bildvorschau gezeigt und explizit bestaetigt (gilt fuer B/R Max
  Sports, Champions League Replay UND "LIVE EVENT").

## "LIVE EVENT N": eigenes Bindestrich-Namensformat ohne Pipe/Doppelpunkt ergaenzt

Der Nutzer meldete, dass die "LIVE EVENT N"-Sender (34 Stueck) trotz
vorhandener sender.txt-Zeile in TiviMate komplett "Keine Information"
zeigten, obwohl unsere generierte XML fuer den KANAL-NAMEN "LIVE EVENT
07" durchaus den generischen Fallback-Text ("Live Event 07 ᴸⁱᵛᵉ")
enthielt. Root Cause: der ECHTE Rohname in der Playlist dieses Senders
lautet nicht "LIVE EVENT 07", sondern "LIVE EVENT 07 - NO EVENT" (bzw.
bei einem echten Event "LIVE EVENT 06 - 9pm High Limit Racing Skagit")
- ein eigenes Bindestrich-Format, weder Pipe- noch Doppelpunkt-basiert,
das `kern_und_event_extrahieren()`/`kern_vorne_und_event_extrahieren()`
bisher gar nicht kannten. Der Live-Playlist-Abgleich
(`m3u_playlist_abgleichen()`) konnte den Kern aus dem Rohnamen deshalb
nie extrahieren, wodurch `daten["kanal"]` beim statischen sender.txt-
Kern ("LIVE EVENT 07") stehen blieb, statt auf den tatsaechlichen,
laengeren Playlist-Namen aktualisiert zu werden - TiviMates exakter
Namensabgleich (siehe September-2026-Lehre oben) scheiterte dadurch
strukturell, unabhaengig von den (eigentlich vorhandenen) Programmdaten.
**Fix:** `kern_vorne_und_event_extrahieren()` um ein eng auf "LIVE
EVENT N -" begrenztes Muster erweitert (bewusst NICHT generisch auf
jeden Bindestrich, um nicht denselben Fehltreffer-Typ wie beim
generischen Doppelpunkt-Muster zu riskieren) - "LIVE EVENT 07 - NO
EVENT" wird jetzt korrekt in Kern "LIVE EVENT 07" und Event-Text "NO
EVENT" zerlegt; "NO EVENT" greift automatisch ueber `LEERLAUF_MARKER`
("no event" ist dort bereits als Substring gelistet).

## SI Sport Klub 1-3, EXYU Arena Adrenalin, HR Arena Sport 1/6 HD: drei kleinere Datenluecken behoben

- **SI|SPORT KLUB 1-3** (und alle weiteren SI/RS "SPORT KLUB N"-
  Sender): siol.net (unsere automatische SI-Quelle) fuehrt keine
  "Sport Klub"-Kanaele - `sportklub_epg.py` (bisher nur als HR-Fallback
  nach MojMaxTV im Einsatz, siehe Abschnitt oben) wurde daher auch als
  zweiter Versuch fuer SI-Sender in die Siol-Verarbeitungsschleife
  eingehaengt (`siol_sportklub_intervalle` in der `siol`-Fallback-Kette).
  `sportklub_kanal_finden()` akzeptierte bisher nur die Kurzform "SK N"
  - um "SPORT KLUB N" (voller sender.txt-Name) erweitert. Live
  verifiziert: SI|SPORT KLUB 1-3 liefern jetzt 38-43 echte Sendungen.
- **EXYU|ARENA ADRENALIN (FHD/HD/SD):** mts.rs (unsere automatische
  RS-Quelle) fuehrt den Kanal echt als "Arena Adrenalin" - aber "EXYU"
  ist keines der Laender, die automatisch eine Quelle ausloesen (bewusst
  keine generische EXYU-weite Quellenpruefung, siehe "kein pauschales
  Durchsuchen"-Regel oben). Stattdessen gezielt NUR fuer den
  Sendernamen "Arena Adrenalin" (Regex-Anker) mts.rs aktiviert, egal ob
  Land RS oder EXYU - kein Risiko fuer andere EXYU-Zeilen. Live
  verifiziert: 49 echte Sendungen.
- **HR|ARENA SPORT 1 HD und HR|ARENA SPORT 6 HD fehlten komplett** in
  sender.txt (reine Datenluecke wie bei den frueheren SOCCER-PPV-8-/
  Milb-Faellen) - andere Nummern/Varianten (`1 ⱽᴵᴾ ᴿᴬᵂ`, `6` ohne "HD")
  waren vorhanden. Ergaenzt (gleiches Logo wie die jeweilige VIP-RAW-
  bzw. Nicht-HD-Variante desselben Kanals) - MojMaxTV (die normale
  HR-Quelle) liefert dafuer bereits nachweislich echte Daten (16-18
  Sendungen), sobald die Zeile existiert.

## 24/7-Serien-/Film-Sender: automatisierte TMDB-Poster-Recherche (1.752 Sender)

Der Nutzer meldete, dass bei den `NAME:24/7 <Titel>`-Sendern (2.268
Zeilen insgesamt - jeder Titel laeuft rund um die Uhr als eigener
Kanal) den meisten nur ein generischer Platzhalter-Logo angezeigt
wurde, obwohl es sich um echte Serien/Filme handelt, fuer die es
Poster gibt. 1.748 Zeilen zeigten auf den generischen Platzhalter
(`externe_logos_import/f8c8f601...`), 4 weitere auf einen der
bekannten toten Picon-Hosts - macht 1.752 zu bearbeitende Sender.

**Vorgehen:** Automatisiertes Skript (`fetch_247_logos.py`, temporaer
im Scratchpad, nicht ins Repo uebernommen) durchsucht fuer jeden Titel
TMDB per HTML-Scraping der Suchergebnisseite (kein API-Key noetig,
gleiche Technik wie bei frueheren Logo-Recherchen dieser Session):
erstes Suchergebnis (`/tv/<id>-...` oder `/movie/<id>-...`, Navigations-
Links wie "now-playing" werden durch das numerische ID-Praefix
ausgeschlossen) -> Detailseite -> `og:image`-Meta-Tag als Poster-URL.
Lief als Hintergrundprozess (~45-50 Minuten fuer alle 1.752 Titel,
bei ~1,5 Sekunden pro Titel durch die 2 noetigen HTTP-Requests),
Zwischenspeichern von sender.txt alle 25 Titel als Absicherung gegen
einen Abbruch mitten im Lauf.

**Ergebnis:** 1.405 von 1.752 Titeln (80%) haben jetzt ein echtes,
selbst gehostetes Poster unter `logos/tv247_import/<sha1-hash-des-
Titels>.png` (max. 300px/256 Farben, gleiche Optimierungs-Konvention
wie alle anderen Logo-Sets). 347 Titel (20%) blieben beim bisherigen
Fallback - entweder kein TMDB-Treffer (z.B. sehr kurzlebige/seltene
Sendungen, Tippfehler im Titel, mehrdeutige generische Namen) oder der
Bild-Download selbst schlug fehl. Stichprobenartig gegengeprueft
(z.B. "24 Legacy", "12 Oz Mouse") - Poster passen korrekt zum Titel.

**Bekannte Einschraenkung:** Bei mehrdeutigen/sehr kurzen Titeln
(z.B. reine Zahlen, generische Ein-Wort-Titel) kann das ERSTE
TMDB-Suchergebnis theoretisch zum falschen Film/zur falschen Serie
gehoeren, falls TMDB mehrere Treffer mit aehnlicher Popularitaet hat -
anders als bei den strikten Alias-/Exakt-Match-Fixes weiter oben in
diesem Dokument ist das hier ein bewusster Kompromiss (kein Fuzzy-
Score-Vergleich, einfach der oberste Suchtreffer), da eine manuelle
Pruefung bei 1.405 Treffern nicht praktikabel war. Bei einer kuenftigen
Meldung "falsches Logo bei 24/7 X" zuerst pruefen, ob TMDB fuer genau
diesen Titel mehrere sehr aehnliche Ergebnisse listet.

## logos_bei_bedarf/kategorien.txt: Sendername-zu-Playlist-Kategorie-Referenz

Auf Nutzerwunsch angelegt, damit Claude bei einer Nutzer-Nachricht wie
"die DRAMA-Sender" oder "die 24/7 COMEDY VIP-Sender" sofort weiss,
welche konkreten sender.txt-Zeilen gemeint sind, ohne jedes Mal
erneut die Playlist abfragen zu muessen. Format `Sendername|Kategorie`
(exakter `group-title`-Wert aus der Playlist des Nutzers), 22.451
Zeilen, 235 unterschiedliche Kategorien (z.B. "24/7 SHOWS VIP" 659,
"24/7 COMEDY VIP" 426, "24/7 DRAMA VIP" 408, "ESPN+ PPV VIP" 1001,
"SOCCER PPV" 402 usw.). Deckt ALLE Live-Kategorien ab (nicht nur
24/7) - reine Namens-/Kategoriereferenz, keine Logos/Programmdaten,
NICHT mit generate_epg.py verknuepft.
**Wichtig:** anders als bei `meine_logos.txt`/`alle_logos.txt`/
`ppv_kernnamen.txt` (Sommer 2026, spaeter wieder entfernt, da nicht
mehr benoetigt) wurde bei dieser Datei die VOD-Ausschlussliste (siehe
"Playlist-Vollimport"-Abschnitt oben, 11 bekannte reine Filmkatalog-
Gruppen wie "NETFLIX MOVIES") NICHT angewendet - sie enthaelt
zusaetzlich auch diese VOD-Kategorien, da der Zweck hier reine
Namens-/Kategoriezuordnung ist, nicht der Sender-Import selbst.

## NameError im DYN-PPV-API-Kanalnamen-Abgleich (Workflow-Log-Fehler behoben)

Der Nutzer schickte einen Screenshot des GitHub-Actions-Workflow-Logs
mit "DYN-PPV-API-Kanalnamen-Abgleich Fehler: name
'M3U_PROVIDER_TIMEOUT_SEKUNDEN' is not defined". Root Cause: Die
Konstanten `M3U_PROVIDER_TIMEOUT_SEKUNDEN`/`M3U_PROVIDER_MAX_ZEICHEN`
wurden im Skript-Ablauf erst WEITER UNTEN definiert (im Abschnitt
"LIVE-KANALNAMEN AUS DER EIGENEN IPTV-PLAYLIST", `m3u_playlist_
abgleichen()`), aber bereits VORHER im "DYN PPV CHANNELS"-Abschnitt
verwendet (dem eigenstaendigen Playlist-Abgleich fuer die 20 fest
kodierten API-Kanaele) - Python fuehrt Modul-Code von oben nach unten
aus, der Name existierte an dieser Stelle schlicht noch nicht. Der
Fehler wurde intern abgefangen (kein Absturz des gesamten Laufs dank
Try/Except), degradierte aber fuer DIESEN einen Abgleich auf den alten
hartcodierten Kanalnamen-Fallback - betraf nur die Umbenennung auf den
exakten Live-Playlist-Namen fuer DYN PPV 1-20 (API-Gruppe), nicht die
eigentlichen Programmdaten selbst. Fix: beide Konstanten vor den
DYN-PPV-Block verschoben (Abschnittskommentar mit verschoben), keine
doppelte Definition mehr noetig, da `m3u_playlist_abgleichen()` weiter
unten dieselben (jetzt frueher definierten) Konstanten mitverwendet.

## Temporaerer Diagnose-Workflow: PlutoTV/SamsungTV/Mazedonien mit vollem Internetzugriff geprueft

Auf Nutzerwunsch wurde (analog zum frueheren `logos_nachladen.yml`,
siehe "Logo-Recherche September 2026") ein temporaerer Workflow
`quellen_recherche.yml` angelegt, einmalig per `workflow_dispatch`
ausgefuehrt und danach wieder geloescht - Zweck: einige Quellen, die
aus der Entwickler-Sandbox blockiert waren, ueber den GitHub-Actions-
Runner (voller Internetzugriff) direkt zu testen. Ergebnis:
- **PlutoTV DE funktioniert einwandfrei** (200 OK, 516 KB) - das 403
  in der Sandbox war ein reines Sandbox-Netzwerk-Artefakt (blockierter
  Zugriff auf github.com selbst), im echten Workflow lief diese Quelle
  nie und muss nicht angefasst werden.
- **Mazedonien ist endgueltig geklaert (negativ):** `prd-static-
  mkt.spectar.tv` (MaxTV-GO/Spectar-Backend) sowie `mkbox.mk`/
  `programa.mk`/`tv-programa.mk`/`epg.mk`/`tv.mk` loesen sich per DNS
  ueberhaupt nicht auf ("Name or service not known") - diese Domains
  existieren nicht mehr, das ist kein Sandbox-Problem. Es gibt aktuell
  keine bekannte funktionierende echte Quelle fuer Mazedonien.
- **Samsung TV Plus DE ist dauerhaft tot:** `samsungtv_de_guide.xml.gz`
  wurde vom Host (kodi-unlimited-support.de) entfernt (per Verzeichnis-
  Listing direkt bestaetigt) - das 404 ist kein temporaerer Fehler.
  Der Aufruf blieb in der DE-Kaskade (degradiert dank des Cache-Fixes
  oben ohnehin billig graceful), lohnt sich aber fuer eine kuenftige
  Bereinigung, falls der Host die Datei nie wieder bereitstellt.
- **Neuer Fund, direkt umgesetzt:** derselbe Host bietet neu
  `joyn_vod_de_guide.xml.gz` (Joyns eigenes VOD-EPG fuer thematische
  Serien-/Doku-"Sender" wie "Ancient Aliens"/"Der letzte Bulle") -
  siehe eigener Abschnitt unten.

## Joyn-VOD-EPG: sechster und letzter Fallback der DE-Kaskade (joyn_vod_epg.py)

Neue Quelle `joyn_vod_epg.py` (Muster wie plutotv_epg.py/
sportklub_epg.py: komplette XMLTV-Datei EINMAL pro Lauf laden, dann
lokal matchen) deckt Joyns eigene "ODC"-Themenkanaele ab (~100 Kanaele,
z.B. "Ancient Aliens", "Charmed", "Der letzte Bulle", "Focus TV") -
viele durchnummerierte/thematische DE/JOYN/PRIME/WOW-sender.txt-Zeilen
sind genau diese Art rund-um-die-Uhr-Serien-"Sender", die deswird.org &
Co. (nur "grosse" TV-Sender) nicht kennen.
Kanalzuordnung laeuft bewusst NUR ueber einen EXAKTEN Namensabgleich
(kein Fuzzy-Anteil) - die Kanalnamen sind kurze, spezifische Serien-
titel, bei denen ein unscharfer Abgleich zu leicht falsch matchen
wuerde (z.B. "Charmed" vs. ein aehnlich klingender, aber inhaltlich
anderer Sender). Als SECHSTER und letzter Versuch in die bestehende
DE-Kaskade eingehaengt (`generate_epg.py`, `plutotv_sender`-Schleife,
nach Samsung TV Plus), neuer `joyn_vod_intervalle`-Eintrag im
`plutotv`-Fallback-Ketten-Dict. Live verifiziert: 6 von ~2.170 DE/
JOYN/WOW/PRIME-Sendern (z.B. "ALIAS", "DER LETZTE BULLE ᴿᴬᵂ", "FOCUS
TV", " ANCIENT ALIENS ᴿᴬᵂ") finden einen exakten Treffer mit je 20
echten Sendungen - kleiner, aber sauberer, risikofreier Zugewinn ohne
sender.txt-Aenderung. Degradiert wie alle anderen Quellen graceful auf
[] bei jedem Fehler.

## CITY|-Sender (lokale US-Sender mit Call-Sign): automatischer Call-Sign-Abgleich gegen tvpassport.com

Auf Nutzerwunsch ("mach mit Option 1 weiter" nach der blockierten
Mazedonien-Recherche) wurde die Landgruppe `CITY` (175 Sender, lokale
US-Affiliates mit Call-Sign im Namen, z.B. `CITY|ABC KATC BROOKLYN`)
untersucht - tvpassport.com (bereits als `TVPASSPORT:`-Opt-in-Quelle im
Repo vorhanden) fuehrt genau diese Art Sender.

**Warum kein normaler Fuzzy-Abgleich:** Die Stadtangaben in dieser
sender.txt-Gruppe sind oft falsch/generisch (z.B. "KATC" steht bei
tvpassport.com fuer Lafayette, LA, bei uns aber fuer "Brooklyn") und
das Format weicht stark ab ("ABC KATC BROOKLYN" vs. "ABC (KATC)
Lafayette, LA") - der bestehende `tvpassport_kanal_finden()`
(Fuzzy-Abgleich auf den kompletten Namen) haette hier mit hohem
Fehltreffer-Risiko gearbeitet (das immer wiederkehrende Fuzzy-Match-
Bug-Muster dieser Session).

**Loesung:** Neue Funktion `tvpassport_kanal_finden_callsign()`
(`quellen/tvpassport_epg.py`) extrahiert per Regex (`\b[KW][A-Z0-9]{2,4}\b`)
die US-Call-Sign aus dem sender.txt-Namen (z.B. "KATC") und sucht in
der statischen tvpassport-Kanalliste NUR nach einem Eintrag mit der
Call-Sign EXAKT in Klammern OHNE Zusatz (z.B. "(KATC)", nicht
"(KATC2)"/"(KATC-DT2)") - bei tvpassport.com ist das immer der
Haupt-Affiliate-Kanal, waehrend Zahlen-/Bindestrich-Suffixe eigene
Subkanaele mit komplett anderem Programm sind (z.B. "Grit TV
(KATC3)"). Kein Fehltreffer-Risiko: nur exakter Klammer-Text-
Vergleich, kein Fuzzy-Anteil. In `generate_epg.py` automatisch fuer
JEDEN `CITY|`-Sender aktiviert (`eintrag["tvpassport_callsign"] = True`
bei Land "CITY", eigener Verarbeitungsblock nach dem normalen
TVPASSPORT:-Block, gleiche `tvpassport_intervalle`-Lueckenfuellung).
Kein eigenes Praefix noetig, keine sender.txt-Aenderung noetig.
Live verifiziert: 157 von 175 Sendern (90%) finden einen Treffer mit
echten Programmdaten; die restlichen 18 haben schlicht keinen
Haupt-Affiliate-Eintrag in der statischen tvpassport-Kanalliste (z.B.
"KICU SAN FRANCISCO", einige CW/IND/MNT-Subkanaele) - degradiert dort
graceful auf die normale generische Beschreibung.

## Bug behoben: fehlgeschlagener Download bei deswird/PlutoTV/SamsungTV/SportKlub/Magenta-myTeamTV wurde NICHT gecacht

Beim Aufbau einer "welche DE-Sender haben keine echte Quelle"-
Auswertung (auf Nutzerwunsch, siehe naechster Abschnitt) fiel ein
echter Performance-/Zuverlaessigkeits-Bug auf: `_xml_laden()` (bzw.
das Aequivalent) in `deswird_epg.py`, `plutotv_epg.py`,
`samsungtv_epg.py`, `sportklub_epg.py` und `magenta_myteam_epg.py`
setzte den Modul-Cache bei einem Fehlschlag (Netzwerk, HTTP-Fehler,
kaputtes Gzip/XML) auf `None` statt auf ein leeres Ergebnis - der
Cache-Treffer-Check (`if _daten_cache is not None: return`) griff
dadurch NIE, jeder einzelne Sender dieser Quelle loeste bei einem
andauernden Fehler (z.B. Host down) einen komplett neuen, ebenfalls
fehlschlagenden Download aus statt sich den einen Fehlschlag zu
merken. Bei ~1.200 DE/JOYN/WOW/PRIME-Sendern haette ein toter Host
also potenziell 1.200 unnoetige, langsame Fehlversuche pro Lauf
verursacht statt EINEM. (tvmovie_epg.py/hoerzu_epg.py/tvpassport_epg.py
waren bereits korrekt, da sie im Fehlerfall `[]` statt `None`
cachen - `[]` ist ebenfalls "not None" und wird daher korrekt aus dem
Cache zurueckgegeben.)
**Fix:** Alle fuenf betroffenen Module cachen einen Fehlschlag jetzt
als `{"kanaele": [], "programme": {}}` (statt `None`) - wird beim
naechsten Aufruf sofort aus dem Cache zurueckgegeben, kein erneuter
Download-Versuch. Verhalten fuer den Sender selbst unveraendert (bleibt
weiterhin ein sauberer Fehlschlag -> generische Generierung).

## DE-Sender-Abdeckungs-Check + ARD-Regionalsender-Alias (WDR/NDR/MDR/SWR/RBB/BR)

Auf Nutzerwunsch ("suche nach weiteren es gibt auch deutsche sender
ohne echte Programmdaten", direkt nach der CITY|-tvpassport-Erweiterung)
wurden alle ~2.170 DE/JOYN/WOW/PRIME-Sender lokal gegen alle sechs
DE-Kaskaden-Quellen (deswird.org/PlutoTV/tvmovie.de/hoerzu.de/
Samsung TV Plus/Magenta-myTeamTV) geprueft. PlutoTV und Samsung TV
Plus waren aus dieser Sandbox-Umgebung NICHT erreichbar (403 bei
github.com selbst, nicht nur beim Zielhost - vermutlich dieselbe
Netzwerk-Policy-Einschraenkung wie beim Mazedonien-Versuch), daher ist
die reine Trefferzahl aus dieser Session nicht 1:1 auf den echten
GitHub-Actions-Workflow-Lauf uebertragbar (dort ist i.d.R. mehr
erreichbar) - als reine Stichprobe aber trotzdem nuetzlich.
Grösster Teil der ~1.510 verbleibenden Nicht-Treffer sind erwartbar
ohne echte Quelle (VOD-artige 24/7-Serien-/Film-Einzelkanaele, Sky-
Subkanaele ohne SKY:-Praefix, US-Lokalsender faelschlich unter Land
"DE" statt "CITY"/"TVPASSPORT:") - kein Massenpotenzial gefunden.

**Eine echte, konkrete Luecke gefunden und behoben:** Die 9 ARD-
Regionalsender-Zeilen (`WDR DORTMUND HD`, `NDR MECKLENBURG-
VORPOMMERN HD`, `NDR NIEDERSACHSEN HD`, `NDR HAMBURG HD`, `MDR
THÜRINGEN HD`, `SWR BW HD`, `RBB HD`, `BR HD`, `WDR HD Köln HD`)
hatten NIE einen Treffer bei deswird.org, obwohl der jeweilige Sender
dort echt existiert - deswird.org fuehrt WDR/NDR/MDR/SWR/RBB/BR nur
als EINEN nationalen Sammelkanal (kein Regionalfenster pro Bundesland/
Stadt), der normale Namensabgleich verglich aber den KOMPLETTEN
Regional-/Studio-Namen und fand deshalb nie einen Treffer.
`generate_epg.py` (deswird-Verarbeitungsblock) probiert jetzt bei
diesen sieben festen ARD-Kuerzeln (`WDR|NDR|MDR|SWR|RBB|BR|HR`
+ Wortgrenze am Anfang) zusaetzlich den blossen Kern OHNE Regional-/
Studioname als zweiten Suchbegriff, falls der volle Name keinen
Treffer findet - kein Fehltreffer-Risiko (nur dieser feste, kurze
Kuerzel-Satz betroffen). Live verifiziert: alle 9 Zeilen liefern jetzt
echte Sendungen (z.B. RBB HD: 99 Sendungen/Tag). Bewusster Trade-off:
liefert das bundesweite ARD-Hauptprogramm dieses Senders, nicht das
tatsaechliche Regionalfenster (deswird.org hat dafuer keine Daten) -
trotzdem naeher an echt als der bisherige generische Platzhaltertext.

## Workflow-Log entrümpelt: keine Sender-Einzelauflistung mehr

Der Nutzer wollte im GitHub-Actions-Log nicht mehr fuer JEDEN
einzelnen Sender eine eigene "X-EPG: N echte Sendungen fuer 'Y'
geladen"-Zeile sehen (bei ~19.000 Sendern eine sehr lange, kaum
lesbare Liste) - nur noch, DASS der Lauf erfolgreich war und alle
Sender verarbeitet wurden. Alle 23 Print-Aufrufe dieser Art (Telemach,
mtel.ba, mymedia.ba, klix.ba, Sky, Magenta, Arena, DAZN, Freeview,
TVGuide, TVPassport, mts.rs, MojMaxTV, SportKlub, Siol, Magenta-
myTeamTV, Deswird, PlutoTV, TvMovie, Hoerzu, SamsungTV, Tubi) zaehlen
jetzt nur noch still mit (`echte_quelle_zaehler`/`_echte_quelle_
zaehlen()`, ganz oben in `generate_epg.py` definiert) statt eine
eigene Log-Zeile pro Sender auszugeben. Am Ende des Laufs (kurz vor
"EPG erfolgreich erstellt") steht jetzt EINE kompakte Zusammenfassung,
z.B. "Echte Programmdaten fuer 8432 Sender geladen (Telemach: 120,
mts.rs: 45, Deswird: 3200, ...)". Die "Live-Kanalabgleich Treffer:
..."-Zeile (kompletter Namens-Liste der per Playlist aktualisierten
NAME:-Sender) wurde ebenso auf eine reine Anzahl gekuerzt. Echte
Fehlermeldungen (404s, Netzwerkfehler etc.) bleiben unveraendert
bestehen - die sind fuer die Fehlersuche weiterhin wichtig, nur die
Erfolgsmeldungen pro Sender wurden entfernt.

## HR|SK/RS|SPORT KLUB-Verwechslung + DYN-PPV-1-20-Dateiposition + Bindestrich-ohne-Pipe-Kernbug (September 2026)

Drei getrennte, in derselben Session gefundene Bugs - bei kuenftigen
"Sender X zeigt falsche/keine Daten"-Meldungen erst hier nachschauen,
ob eines der Muster passt, bevor von vorne debuggt wird:

1. **mts.rs matchte "SPORT KLUB N" (RS-Sender) per Fuzzy-Fallback
   faelschlich auf den unabhaengigen ungarischen Kanal "Sorozatklub"**
   (endet ebenfalls auf "klub", hohe Zeichen-Aehnlichkeit) - alle
   Nummern zeigten identisches, falsches (ungarisches) Programm. mts.rs
   fuehrt GAR KEINE "Sport Klub"-Kanaele. Fix: `mts_kanal_finden()`
   (`quellen/mts_epg.py`) ueberspringt "SPORT KLUB"-Namen jetzt
   komplett (`_SPORT_KLUB_GUARD`), SportKlub (epgshare01.online,
   bereits fuer HR/SI im Einsatz) uebernimmt als echter Fallback fuer
   RS (`generate_epg.py`, neuer `mts_sportklub_intervalle`-Block nach
   dem normalen `mts_sender`-Block). **Wichtig fuer die Fehlersuche
   dabei:** der Nutzer meldete das Symptom zunaechst als "HR|SK zeigt
   falsches EPG" - gemeint war aber tatsaechlich `RS|SPORT KLUB`
   (Verwechslung durch aehnliche Markennamen). Immer den EXAKTEN
   sender.txt-Zeilennamen nachfragen/verifizieren, bevor an der
   falschen Stelle gesucht wird.
2. **HR|SK 1-10: TiviMate ordnete die EPG-Daten teils falsch zu**,
   obwohl MojMaxTV/SportKlub fuer diese Kanaele nachweislich korrekte,
   unterschiedliche Sendungen lieferten - Kanal-ID war bisher immer
   die starre sender.txt-Schreibweise ("HR|SK N"), nicht der exakte
   Live-Playlist-Name. Fix: analog zum DYN-PPV-1-20-Mechanismus wird
   jetzt einmalig die eigene Playlist nach "HR| SK N" durchsucht und
   bei Treffer der exakte rohe Playlist-Name fuer ID UND Anzeigename
   uebernommen (`hr_sk_playlist_namen` in `generate_epg.py`).
3. **DYN-PPV-1-20-API-Kanaele zeigten NUR bei diesen 20 Kanaelen
   durchgaengig "Keine Information"**, obwohl die Platzhalter-Daten
   ("Dyn Sport (N) No Live") nachweislich vollstaendig in der Datei
   standen und alle anderen ~18.000 Sender normal angezeigt wurden.
   Ursache-Verdacht (nicht 100% verifizierbar, aber sehr stimmige
   Beweislage): die unkomprimierte `Epg_365_Tage.xml` ist mittlerweile
   ueber 300 MB gross, und der DYN-PPV-Leerzeiten-Block lag bisher als
   ALLERLETZTES Stueck Inhalt direkt vor `</tv>` - ein schwaecheres
   Android-TV-Geraet duerfte beim Parsen/Download einer so grossen
   Datei irgendwo gegen Ende abbrechen, bevor der letzte Abschnitt
   fertig eingelesen ist. Fix: Block direkt hinter die
   `<channel>`-Definitionen verschoben, noch vor der grossen
   Tagesraster-Schleife fuer alle Sender - liegt dadurch in den ersten
   Prozentpunkten der Datei statt im letzten. **Kein vollstaendiger
   Fix des Grundproblems** (Datei bleibt riesig) - verschiebt das
   Truncation-Risiko nur auf die zuletzt in `sender.txt` stehenden
   Sender. Bei weiteren "nur bestimmte Sender zeigen nichts trotz
   nachweislich vorhandener Daten"-Meldungen: IMMER zuerst die
   Dateiposition des betroffenen Kanals pruefen (`data.find(...)`,
   Position in % der Gesamtlaenge) - liegt sie nahe 100%, ist das ein
   Kandidat fuer dasselbe Problem, weiteres Verschieben nach vorne
   waere der naheliegende naechste Schritt.
4. **Neuer, echter Bindestrich-ohne-Pipe-Parsing-Bug bei manchen
   NAME:-Sendern gefunden** (z.B. "AR: DAZN PPV N"): manche Anbieter
   haengen den Leerlauf-Platzhaltertext OHNE trennendes Pipe-Zeichen
   direkt an den Kern an, z.B. "AR: DAZN PPV 1 - NO EVENT STREAMING -
   | 8K EXCLUSIVE" (Kern und "- NO EVENT STREAMING -" durch ein
   Leerzeichen, nicht durch ein Pipe getrennt). Weder die Kern-hinten-
   noch die bisherige Kern-vorne-Erkennung (`kern_vorne_und_
   event_extrahieren()`) fand dadurch den sauberen Kern "AR: DAZN PPV
   1" - die Live-Zuordnung schlug fuer diese Momentaufnahmen komplett
   fehl. Fix: ein angehaengter, in Bindestriche eingeschlossener Text
   ("- ... -" am Ende des ersten Pipe-Abschnitts) wird jetzt
   abgetrennt und dem Event-Text zugeschlagen, bevor der Kern-Abgleich
   laeuft - risikofrei (nur bei diesem spezifischen Muster aktiv,
   sonst unveraendertes Verhalten). Getestet gegen mehrere echte und
   synthetische Beispiele (AR: DAZN PPV, SOCCER PPV, Clubber, normale
   Live-Events).
5. **Wichtige Abgrenzung, die in dieser Session mehrfach zu
   Missverstaendnissen fuehrte:** "Sender X zeigt falsche/keine Daten"
   kann PRINZIPIELL vier komplett unterschiedliche Ursachen haben, die
   sich oberflaechlich alle gleich anfuehlen ("Keine Information"/
   falscher Text) - IMMER an den echten Daten (generierte XML direkt
   pruefen, nicht raten) verifizieren, WELCHE es ist, bevor gefixt
   wird:
   - **Datenmuell im sender.txt-Kernnamen** (alter Rohtext im
     NAME:-Wert selbst, siehe fruehere ESPN+/STAN/UEFA-Faelle weiter
     oben) - IMMER zuerst `grep "^NAME:.*<Sendername>" sender.txt`
     pruefen.
   - **Fuzzy-Fehltreffer bei einer echten Quelle** (siehe SPORT-KLUB-
     bei-mts.rs-Fall oben, oder die frueheren Arena-PREMIUM-/MRT-Faelle)
     - Kanalliste der Quelle direkt abfragen und pruefen, ob der
     Fuzzy-Treffer inhaltlich wirklich passt.
   - **Struktureller Parsing-Bug in kern_und_event_extrahieren()/
     kern_vorne_und_event_extrahieren()** (neues, bisher unbekanntes
     Rohnamen-Format) - den rohen Text aus dem TiviMate-Sendernamen-
     Editor holen und Schritt fuer Schritt durch die Extraktions-
     funktionen nachrechnen (siehe Bindestrich-Fix oben als Vorlage).
   - **Reines Datenalter/Timing** (unser Workflow laeuft nur alle 4h,
     der rohe Live-Playlist-Name bei dynamischen PPV-Kanaelen aendert
     sich aber alle paar Minuten) - erkennbar daran, dass der aktuell
     im TiviMate-Sendernamen-Editor angezeigte Rohname ein ANDERER
     ist als der, der in der zuletzt generierten XML steht (Zeit-
     stempel des letzten erfolgreichen Workflow-Laufs mit der Uhrzeit
     des Nutzer-Screenshots vergleichen). Das ist KEIN Bug, sondern ein
     bekannter, akzeptierter Kompromiss bei ~9.000 dynamischen
     PPV-Kanaelen mit nur alle 4h aktualisierten Snapshots.

## UK: VOLLEY PPV 1-30: neues Bindestrich-nach-Nummer-Kernmuster + GaaGo 07-11 bereinigt

Der Nutzer meldete per Screenshot, dass `UK: VOLLEY PPV 1`/`30` trotz
sender.txt-Zeile "Keine Information" zeigten. Root Cause: ein bisher
unbekanntes Rohnamen-Format, bei dem der Leerlauf-/Event-Text OHNE
trennendes Pipe-Zeichen direkt mit einem einzelnen Bindestrich an die
Kern-Nummer angehaengt wird und selbst wieder eigene Pipes enthaelt
(z. B. "UK: VOLLEY PPV 1 - MELISSA/BRANDIE (CAN) VS MÄDER/KERNEN (SUI),
WOMEN SEMIFINALS ON CC | OSTRAVA (CZE) | Sun 31 May 08:50 |
8K EXCLUSIVE" oder "UK: VOLLEY PPV 30 - NO EVENT STREAMING -
8K EXCLUSIVE") - weder die bestehende Kern-hinten- noch die
Kern-vorne-Logik (inkl. der bereits vorhandenen Bindestrich-Suffix-Faelle
"US: NETFLIX PPV N -"/"AR: DAZN PPV N - ... -", die den Bindestrich nur
am ENDE eines Pipe-Abschnitts erwarten) erkannte das.
**Fix:** `kern_vorne_und_event_extrahieren()` (`generate_epg.py`) prueft
jetzt ganz am Anfang zusaetzlich ein neues, global auf `voller_name`
angewandtes Muster `^<Laendercode 2-4 Buchstaben>: <Name> <Nummer> -
<Rest>` (Bindestrich direkt nach der Nummer, unabhaengig von Pipes davor
oder danach) - liefert Kern "UK: VOLLEY PPV 1" bzw. "UK: VOLLEY PPV 30",
der Rest wird komplett zum Event-Text. Das 2-4-Buchstaben-Laendercode-
Praefix mit Doppelpunkt ist Pflicht, damit derselbe September-2026-
Regressionsbug (blosses "DE: RTL+ PPV 28" ohne Bindestrich nach der
Nummer wuerde faelschlich matchen) nicht erneut auftritt - gegen alle
bekannten Regressionsfaelle (Clubber, DAZN NEXT, Netflix-PPV-Bindestrich-
Suffix US+UK, DirtVision, LIVE-EVENT-Bindestrich, Matchroom, DE:/US:-
PPV-Regressionsguard) sowie die neuen VOLLEY-PPV-Faelle verifiziert,
`pytest` (98 Tests) bestaetigt gruen.
Zusaetzlich in derselben Session gefunden (Screenshot "Sender von 01 bis
11"): 5 von 11 `GaaGo`-Sendern (07-11) trugen noch eingebetteten
Rohtext-Muell im gespeicherten Kernnamen selbst (z. B.
`NAME:GaaGo | 08 23 Aug | Galway: Athenry v Ardrahan - Forvis Mazars
Senior Hurling Championship Group 4 Round 2 | 17:15 GMT` statt
`NAME:GaaGo 08`) - derselbe Datenmuell-Bug-Typ wie bei den frueheren
ESPN+/STAN-/Milb-Faellen weiter oben. Auf das saubere, bereits bei
Gaago 01-03 funktionierende Format (`GaaGo NN`, ohne Pipe) reduziert.
Fuer `UK: VOLLEY PPV` gab es zudem noch KEIN Logo (alle 30 Zeilen leer) -
offizielle Quellen (fivb.com, volleyballworld.com, tv-logo/tv-logos)
waren aus der Sandbox nicht erreichbar (403/404), daher ein eigenes
Text-Logo erstellt (Volleyball-Icon + "VOLLEY PPV"-Schriftzug, dunkelblauer
Hintergrund), dem Nutzer per Bildvorschau gezeigt und bestaetigt, unter
`logos/volley_ppv/volley_ppv.png` selbst gehostet und in allen 30 Zeilen
eingetragen - gleiche "immer selbst hosten"-Regel wie bei allen anderen
Logo-Funden dieser Session.

## September 2026: XML-Absturz endgueltig behoben (escape() escaped jetzt auch ")

Der Workflow brach wiederholt mit "Erzeugtes XML ist ungueltig, Abbruch
ohne Schreiben: not well-formed (invalid token): line 36713, column 63"
ab - IMMER an derselben Zeile/Spalte, unabhaengig vom Lauf/Datum.

**Erster Fix (unvollstaendig):** `escape()` in `generate_epg.py` entfernte
zusaetzlich zu xml.sax.saxutils.escape()'s Standard-Maskierung (&/</>)
auch fuer XML 1.0 illegale Steuerzeichen (z.B. vereinzelte Muellbytes
aus einer HTML-gescrapten Quelle). Das war zwar ein echtes, notwendiges
Problem, behob den konkreten Absturz aber NICHT - der naechste Lauf
schlug an EXAKT derselben Stelle erneut fehl.

**Eigentliche Ursache:** `escape()` wird in diesem Skript durchgaengig
auch fuer XML-ATTRIBUTWERTE verwendet (z.B. `channel id="{escape(...)}"`,
`icon src="{escape(...)}"`), aber `xml.sax.saxutils.escape()` maskiert
per Default NUR `&`/`<`/`>` - NICHT das doppelte Anfuehrungszeichen `"`.
Ein einzelnes rohes `"` in einem Sender-/Kanalnamen (z.B. ein Team-
Spitzname in Anfuehrungszeichen in einem dynamischen Live-Event-Titel)
bricht dadurch das umschliessende Attribut und macht die GESAMTE Datei
ungueltig - immer an derselben Stelle, weil eine stabile Kanal-ID
betroffen war, nicht wechselnder Sendungstext.

**Fix:** `escape()` escaped jetzt zusaetzlich `"` zu `&quot;` (per
`entities={'"': '&quot;'}` an `xml.sax.saxutils.escape()` uebergeben).
Unschaedlich fuer normale `<title>`/`<desc>`-Textinhalte, da `&quot;`
von jedem XML-Parser ohnehin wieder zu `"` decodiert wird, auch
ausserhalb von Attributen.

**Lehre fuer kuenftige "not well-formed"-Faelle:** Wenn ein Fix (z.B.
Steuerzeichen entfernen) nach einem erneuten Workflow-Lauf am EXAKT
GLEICHEN line:column-Wert erneut fehlschlaegt, ist die erste Diagnose
mit hoher Wahrscheinlichkeit unvollstaendig oder falsch - eine
identische Position bei unterschiedlichen Live-Daten deutet auf eine
STRUKTURELLE Ursache (z.B. fehlendes Attribut-Escaping) hin, nicht auf
zufaellig wechselnden Sendungstext. Immer zuerst `mcp__github__
get_job_logs`/`actions_list` gegen den TATSAECHLICHEN Workflow-Lauf
pruefen, ob ein vorheriger Fix ueberhaupt schon mitgelaufen ist, bevor
man einen neuen Fix als bestaetigt annimmt.

## September 2026: Samsung TV Plus und mymedia.ba dauerhaft entfernt

Beide Quellen degradierten zwar schon vorher graceful (kein Absturz),
lieferten aber keine echten Daten mehr und wurden komplett aus
`generate_epg.py` UND als eigene Module (`quellen/samsungtv_epg.py`,
`quellen/mymedia_epg.py`) entfernt, inkl. der zugehoerigen Tests:

- **Samsung TV Plus:** Host hat die XMLTV-Datei entfernt (404 bei
  jedem Abruf) - bereits laenger bekannt, siehe frueherer Abschnitt.
- **mymedia.ba (Sender "MY TV", 3. BA-Fallback):** Die Seite laeuft
  jetzt auf einem neuen Plugin ("neoepg" statt "tvsmepg", andere CSS-
  Klassen). Live geprueft: fuer "MY TV" zeigt die Seite selbst an
  MEHREREN Tagen (nicht nur heute) einen "Keine Sendungen"-Leerzustand
  ("EMPTY STATE" im HTML-Kommentar) - kein Scraper-Problem, die Quelle
  hat aktuell schlicht keine Daten fuer diesen einen Kanal (kein
  Kanal-Verzeichnis zum Ausweichen, mymedia.ba deckte immer nur "MY TV"
  ab).

Bei erneuten "Quelle X liefert nichts mehr"-Meldungen: IMMER zuerst wie
hier live pruefen (mehrere Tage/Daten durchprobieren, nach einem
"keine Daten"-Leerzustand im HTML suchen), bevor an der eigenen
Scraping-Logik gesucht wird - manchmal hat der Anbieter selbst
schlicht keine Daten mehr, unabhaengig vom eigenen Code.

## September 2026: Sport Klub Slowenien - neue Quelle delo_si_epg.py (tvspored.delo.si)

Sport Klub Kroatien (epgshare01.online, `sportklub_epg.py`, bisher
automatischer Fallback fuer `SI|SPORT KLUB N` nach siol.net) und Sport
Klub Slowenien zeigen NICHT immer dasselbe Programm - per Nutzer-
Screenshot bestaetigt lief auf dem echten slowenischen SK1 "Ingolstadt
- Aachen" (3. Bundesliga), waehrend die kroatischen Daten fuer "SK 1"
zeitgleich die saudische Liga zeigten. tv-spored.siol.net (die normale
automatische SI-Quelle) fuehrt selbst keine echten Sport-Klub-Daten
(die Kanalseiten "sportkl"/"sportklubp" existieren dort zwar, haben
aber keine eigene Sendungsliste - nur ein "andere Kanaele"-Widget).

**Neue Quelle:** `quellen/delo_si_epg.py` liest die echte slowenische
Sendungsliste von tvspored.delo.si (schema.org "BroadcastEvent"-
Microdata, serverseitig gerendert, kein JS-Scraping noetig) fuer
"SK 1" bis "SK 6" (feste Slug-Zuordnung `sk1`.."sk6"). Erkennt "SK N"/
"SPORT KLUB N" (optional HD/FHD/UHD/SD und/oder VIP/RAW-Deko-Marker,
auch als hochgestelltes Unicode "ⱽᴵᴾ ᴿᴬᵂ" via NFKD-Normalisierung).
Live gegen "Ingolstadt - Aachen" verifiziert - exakter Treffer.

In `generate_epg.py`'s SI-Sport-Klub-Fallback-Kette (nach siol.net)
jetzt ERSTER Versuch, die kroatische SportKlub-Quelle nur noch letzter
Fallback, falls delo.si fuer einen Sender einmal nichts liefert.

**Bekannte Einschraenkung:** Die Seite liefert keine echte mehrtaegige
Datumsnavigation ohne JavaScript (der Datums-Dropdown im HTML aendert
die serverseitige Antwort nicht) - ein einzelner Abruf der
Standardseite deckt aber bereits ca. 24-30 Stunden ab (von "gestern
spaet abends" bis "morgen frueh"), das reicht fuer die aktuelle
Sendung/naechste Stunden. Tageswechsel-Erkennung: die Liste beginnt
oft noch am spaeten VORTAG (z.B. "23:15" vor "01:15") - der
Anfangs-Tagesversatz wird per Peek auf die ersten zwei Zeiten bestimmt
(faellt die zweite Zeit kleiner aus als die erste, ist die erste Zeile
noch "gestern"), nicht einfach bei 0 begonnen - sonst verschiebt sich
die gesamte Liste um einen Tag nach vorne (fruehe Bug-Version dieser
Session, per direktem Live-Vergleich mit "Ingolstadt-Aachen" gefunden
und korrigiert).

## September 2026: RS|Arena Sport - Nutzer-Fehlbenennung, KEIN Code-Fix noetig

Der Nutzer meldete falsche Programmdaten bei `RS|ARENA SPORT`-Sendern
(z.B. tvarenasport.com Serbien zeigte "Ruska Liga: Fakel - Zenit",
real lief "Europa Liga: Porto - Stuttgart", passend zu den
KROATISCHEN Daten). Ein Fix (RS auf MojMaxTV/HR-Quelle umstellen)
wurde zunaechst implementiert, getestet und gepusht - dann aber auf
Nutzerwunsch WIEDER VOLLSTAENDIG ZURUECKGEROLLT (`git revert`), weil
sich herausstellte: Der Nutzer hatte seine tatsaechlichen Playlist-
Kanaele lediglich FALSCH dem `RS|`-EPG-Eintrag zugeordnet (TiviMate-
Auto-Matching-Fehler, exakt dasselbe Muster wie beim frueheren HR|SK-
Fall) - die echten `RS|ARENA SPORT`-Sender (wo tatsaechlich serbischer
Feed dahinter steckt) haetten durch den Fix faelschlich kroatische
Daten bekommen. Der Nutzer ordnet seine betroffenen Kanaele stattdessen
manuell in TiviMate auf die passenden `HR|ARENA SPORT`-Eintraege um.

**Lehre:** Bei "Sender X zeigt falsches Programm" IMMER zuerst per
Live-Video-Vergleich klaeren, ob es wirklich ein Quellen-/Matching-Bug
in unserem Code ist, oder ob der Nutzer (bzw. sein IPTV-Anbieter) den
Playlist-Kanal schlicht dem falschen EPG-Eintrag zugeordnet hat -
letzteres braucht KEINEN Code-Fix, nur eine correcte manuelle
TiviMate-Zuordnung durch den Nutzer. Vor einem Quellen-Umbau lieber
einmal zu oft nachfragen ("hast du das schon selbst umbenannt/
zugeordnet?") als einen unnoetigen, potenziell falschen Fix committen.

## September 2026: MK|KANAL 8 / MK|ROMA TV - falsche/kaputte Logos ersetzt

Bei einer Nutzer-Ueberpruefung (Screenshot mehrerer MK-Sender mit
"Keine Information") stellte sich heraus: `MK|24 VESTI`, `24 VESTI HD`,
`K3`, `SUTEL TV`, `ALFA TV`/`ALFA TV SD` hatten bereits korrekte
Logos UND den generischen "ᴸⁱᵛᵉ"-Platzhaltertext (TiviMate-Zuordnungs-
Problem, kein Datenproblem) - `KANAL 8` und `ROMA TV` hatten aber
tatsaechlich kaputte/falsche Logos:
- **KANAL 8** zeigte faelschlich das Logo von "Kanal 5" (komplett
  anderer Sender).
- **ROMA TV** verlinkte auf ein laengst kaputtes Imgur-"Bild nicht
  gefunden"-Bild.

Neue Logos gefunden (offizielles Icon von kanal8.mk fuer Kanal 8,
Senderlogo von roma-tv.com fuer Roma TV), dem Nutzer per Bildvorschau
gezeigt und bestaetigt, auf max. 300px/256 Farben optimiert und selbst
gehostet unter `logos/kanal8/kanal8.png` bzw. `logos/roma_tv/roma_tv.png`.
`MK|ALFA` (nicht "ALFA TV") und `MK|SKYFOLK MK` haben ebenfalls
fragwuerdige/generische Logos (graues "a"-Symbol bzw. generisches
Radio-Symbol) - auf Nutzerwunsch NICHT angefasst ("Rest kann bleiben").

## September 2026: Playlist-Vollabgleich - wichtige Lehre ueber das "leeres Land"-Format

Auf Nutzerwunsch wurde die komplette eigene IPTV-Playlist (~407 MB,
~2,76 Mio. Zeilen, temporaer heruntergeladen/analysiert/wieder
geloescht wie bei allen fruehereren Playlist-Abgleichen) gegen
`sender.txt` verglichen, um fehlende Live-Sender zu finden.

**Wichtige Lehre (grosser Fehlalarm in dieser Session):** Ein erstes,
selbstgeschriebenes Python-Vergleichsskript meldete zunaechst "883 +
301 fehlende Sender" (u.a. komplette Kategorien wie UK Championship/
League One/League Two/Formula 1 Fahrer-Kanaele/PBS-Affiliates) - das
war ZUM GROSSTEN TEIL FALSCH. Ursache: `generate_epg.py` unterstuetzt
bereits ein eigenes, dokumentiertes Format fuer Sendernamen, die selbst
ein Pipe-Zeichen enthalten ODER kein Land-Praefix haben - die Zeile
beginnt dann direkt mit `|` (leeres Land-Feld), z.B.
`|CHAMP | Wrexham|Wrexham ᴸⁱᵛᵉ|` oder `|UK|FORMULA 1| ALB - ALBON
WILLIAMS|...`. `generate_epg.py` erkennt das explizit (`if
zeile.startswith("|"):`, Kommentar direkt im Code) und trennt nur an
den LETZTEN ZWEI Pipes der Zeile (Beschreibung, Logo) - alles davor
bleibt unveraendert der komplette Sendername, egal wie viele Pipes er
selbst enthaelt. Das eigene Vergleichsskript kannte dieses Format
zunaechst nicht und stufte deshalb hunderte laengst korrekt
eingetragene Sender faelschlich als "fehlend" ein (UK Championship/
League One/League Two/TT Race PPV/Formula 1/PBS-Affiliates/Fox 24
Santa Barbara - LETZTERES sogar ueber ein TVPASSPORT:-4.-Feld-Override,
noch ein weiteres Sonderformat). Nach Korrektur des Vergleichsskripts
blieben nur noch 22 echte Kandidaten uebrig, von denen die meisten sich
bei manueller `grep`-Verifikation zusaetzlich als bereits vorhanden
herausstellten.

**Tatsaechlich neu ergaenzt (nur 3 Sender):**
- `UK|UK| BEIN SPORTS ASIA 3` (unter "##### UK| WORLD SPORTS #####",
  direkt neben der bereits vorhandenen "...ASIA 2"-Zeile im selben
  leeren-Land-Format)
- `HR|SPORT KLUB` ohne Nummer (unter "#EXYU SPORTSKI KANALI" - zu
  unterscheiden von den nummerierten `HR|SK N`-Sendern, siehe TiviMate-
  Abschnitt weiter oben; noch keine echte Quelle, generischer
  Platzhalter bis auf Weiteres)

**Zusaetzlich gefunden und behoben: 11 weitere Datenmuell-Zeilen**
(derselbe seit Sommer 2026 bekannte Bug-Typ - alter Roh-Event-Text im
NAME:-Kern gespeichert statt des stabilen Kerns): `UFC 02`/`UFC 03`
(hatten volle Kampfnamen+Datum als Kern), `LOI 06`-`LOI 09` und
`LoiTV event 1`-`5` (hatten volle Team-vs-Team+Datum-Texte als Kern).
Alle auf den reinen, stabilen Kern reduziert.

**Wichtige Lehre fuer kuenftige Playlist-Abgleiche:** Ein eigenes
Vergleichsskript gegen `sender.txt` MUSS mindestens folgende Sonder-
formate kennen, bevor seine "fehlend"-Liste als verlaesslich gilt:
(1) das "leeres Land"-Format (Zeile beginnt mit `|`, siehe oben),
(2) `NAME:`-Kernwerte (Substring-Vergleich gegen den vollen
Playlist-Rohnamen, nicht nur exakter Match), (3) Opt-in-Praefixe
(`TELEMACH:`/`SKY:`/`MAGENTA:`/`ARENA:`/`DAZN:`/`FREEVIEW:`/
`TVGUIDE:`/`TVPASSPORT:`) MIT ihrem optionalen 4. Feld (expliziter
Playlist-Namen-Override, weicht vom 2. Feld/Suchbegriff ab). Ohne
alle drei Faelle abzudecken, produziert ein Abgleich massenhaft
Fehlalarme - vor einer Bulk-Ergaenzung IMMER jeden einzelnen
vermeintlich fehlenden Kandidaten zusaetzlich per direktem `grep`
gegenchecken, nicht blind dem eigenen Skript vertrauen (wie in dieser
Session anfangs faelschlich geschehen).

## September 2026: Grossgeschriebene Sendungstitel echter Quellen normalisiert (z.B. HR|ARENA SPORT 1-10)

Der Nutzer meldete per Screenshot, dass `HR|ARENA SPORT 1`-`10` (echte
Programmdaten von MojMaxTV, unserer automatischen HR-Quelle) im
EPG-Raster komplett in GROSSBUCHSTABEN angezeigt werden (z.B. "UŽIVO:
CHAMPIONSHIP: PRESTON - BLACKBURN, NOGOMET" statt normal geschrieben) -
MojMaxTV liefert seine Sendungstitel roh so, wie sie selbst komplett
grossgeschrieben sind.
**Fix:** Neue Funktion `normalisiere_grossschreibung()` in `epg_lib.py`
- wandelt einen Text NUR dann in normale Schreibweise um, wenn er
komplett grossgeschrieben ist (`text == text.upper()` und mindestens ein
Buchstabe enthalten); bereits normal formatierte Texte (Telemach,
mtel.ba usw.) bleiben unveraendert. Jedes Wort wird einzeln kapitalisiert
(Doppelpunkte/Klammern werden als Suffix erkannt, Bindestrich-Teile
einzeln kapitalisiert - "PRESTON - BLACKBURN, NOGOMET" wird "Preston -
Blackburn, Nogomet"). Nutzt bewusst eine EIGENE, kleine Abkuerzungsliste
`SATZ_ABKUERZUNGEN` (nur reine technische Kuerzel: HD/FHD/UHD/SD/HEVC/
4K/8K/DAZN/TV/UFC/NFL/NBA/NHL/MLB/NCAA/MLS/EPL) statt der bestehenden
`KANALNAME_ABKUERZUNGEN` - letztere enthaelt auch Land-/Kategorie-Kuerzel
wie "LIGA"/"SK"/"NA"/"SI", die in kroatischen/serbischen Sendungstiteln
aber ganz normale Woerter sind ("liga" = Liga, "na" = auf, "si" = du
bist) - eine Wiederverwendung haette z.B. "Talijanska LIGA" statt
"Talijanska Liga" erzeugt (im ersten Versuch tatsaechlich passiert, dann
korrigiert).
In `generate_epg.py`'s zentraler `_schreibe_echte_programme()` (schreibt
`<title>`/`<desc>` fuer ALLE echten Quellen) wird `normalisiere_
grossschreibung()` nach `kuerze_beschreibung()` auf Titel UND
Beschreibung angewendet - betrifft damit automatisch JEDE aktuelle und
kuenftige echte Quelle, die (wie MojMaxTV) komplett grossgeschrieben
liefert, nicht nur Arena Sport/MojMaxTV. `pytest` (95 Tests) bestaetigt
gruen.

## September 2026: ImportError im Workflow behoben (tvpassport_kanal_finden_callsign aus falschem Modul importiert)

Nach dem Einbau der neuen Quelle `epgshare_us_locals_epg.py` (siehe
CITY|-Abschnitt oben, vorherige Session) brach der naechste Workflow-Lauf
komplett ab: `ImportError: cannot import name
'tvpassport_kanal_finden_callsign' from 'quellen.epgshare_us_locals_epg'`
(`generate_epg.py`, Zeile 72) - ein Copy-Paste-Fehler beim Einbau: die
Funktion `tvpassport_kanal_finden_callsign()` gehoert zu
`quellen/tvpassport_epg.py` (dort auch tatsaechlich definiert), wurde
aber versehentlich zusaetzlich in die `from quellen.epgshare_us_locals_epg
import ...`-Zeile mit aufgenommen statt in die bereits bestehende
`from quellen.tvpassport_epg import tvpassport_kanal_finden,
tvpassport_hole_programme`-Zeile. Da Python-Imports beim Start des
gesamten Skripts ausgefuehrt werden, fuehrte das zum sofortigen Absturz
VOR jeder Sender-Verarbeitung - kein Sender bekam ueberhaupt ein EPG.
**Fix:** Import korrigiert - `tvpassport_kanal_finden_callsign` steht
jetzt in der `tvpassport_epg`-Import-Zeile, aus der
`epgshare_us_locals_epg`-Import-Zeile entfernt. Verifiziert per
`python3 -m py_compile` UND per komplettem Testlauf (`python3 -c "import
generate_epg"` im Hintergrund, lief mit Exit-Code 0 komplett durch,
inkl. vollem EPG-Generierungslauf) sowie `pytest` (95 Tests, gruen).
**Lehre:** Bei einer neuen Quellen-Integration IMMER pruefen, dass jeder
importierte Funktionsname auch tatsaechlich aus dem Modul kommt, in dem
er implementiert ist - ein falsches, aber syntaktisch gueltiges
Import-Statement wird von `pytest` (importiert Module oft schon vor dem
eigentlichen Test) nicht zwingend erfasst, wenn die Tests das betroffene
Modul nicht direkt beruehren; ein echter `python3 -m py_compile` +
kompletter Skriptstart ist der zuverlaessigere Check vor einem Push.

## September 2026: DYN PPV 1-20 (API-Kanaele) - Platzhalter zwischen Events endlich sichtbar (chronologische Reihenfolge behoben)

Der Nutzer meldete ueber mehrere Tage hinweg, dass bei den 20 fest
kodierten DYN-PPV-API-Kanaelen (`DE| DYN PPV 1 HD` bis `20 HD`, siehe
Abschnitt "DYN PPV: Echte API-Daten" oben - NICHT zu verwechseln mit den
`NAME:`-Playlist-Sendern 1-50) zwischen echten Events durchgaengig
"Keine Information" statt des Leerlauf-Platzhalters ("Dyn Sport (N)
ᴺᵒ ᴸⁱᵛᵉ") angezeigt wurde - obwohl die Platzhalter-Daten nachweislich
vollstaendig in der generierten XML standen (kein Datenluecken-Problem).

**Ursache:** In `generate_epg.py` wurden echte API-Events (Handball/
Tischtennis/Basketball, teils Wochen bis Monate in der Zukunft) IMMER
VOR den bei "heute 00:00 Uhr" beginnenden stuendlichen Leerzeit-
Platzhaltern in die Datei geschrieben (zwei getrennte Code-Bloecke
hintereinander). Fuer einen einzelnen Kanal sprang die Zeitachse
dadurch mittendrin zurueck (z.B. erst ein Event im November, danach
Platzhalter ab dem 5. September) - die `<programme>`-Eintraege eines
Kanals waren also nicht mehr chronologisch aufsteigend sortiert.
TiviMate (wie offenbar viele EPG-Parser) erwartet das aber und bricht
die weitere Anzeige fuer einen Kanal nach so einem Rueckwaertssprung
ab - echte Events (die zuerst in der Datei stehen) wurden dadurch noch
angezeigt, alles danach nicht mehr.

**Fix:** Echte Events UND Leerzeit-Platzhalter werden jetzt in
`dyn_kanal_programme` (Dict `{kanalnummer: [(start, ende, titel,
beschreibung), ...]}`) gesammelt, statt sofort in `xml_teile`
geschrieben zu werden. Erst am Ende wird pro Kanal ALLES zusammen nach
Startzeit sortiert und dann erst als `<programme>`-Eintraege emittiert
- keine Rueckwaertssprruenge mehr. `pytest` (95 Tests) sowie eine
eigene Simulation (synthetische Events + Leerzeit-Platzhalter,
Pruefung auf chronologische Reihenfolge) bestaetigten den Fix vor dem
Push; ein kompletter Testlauf von `generate_epg.py` selbst war in der
Entwickler-Sandbox nicht moeglich (zu viele externe Quellen, teils
blockiert) - der eigentliche Nachweis lief ueber den naechsten echten
Workflow-Lauf.

**Bestaetigt vom Nutzer nach dem naechsten Workflow-Lauf:** Platzhalter
werden jetzt korrekt vor/nach/zwischen Events angezeigt - der Fix
funktioniert wie erwartet.

**Lehre fuer aehnliche Faelle:** Wenn ein EPG-Parser (TiviMate o.ae.)
fuer einen Kanal trotz nachweislich vollstaendiger Daten in der XML
"Keine Information" zeigt, IMMER auch die REIHENFOLGE der
`<programme>`-Eintraege fuer genau diesen Kanal in der Datei pruefen
(chronologisch aufsteigend?), nicht nur, ob die Daten ueberhaupt
vorhanden sind - ein Rueckwaertssprung in der Zeitachse ist ein
eigener, leicht zu uebersehender Bug-Typ neben den bereits bekannten
(Datenluecke, Kanal-ID-Mismatch, Dateiposition/Truncation).

## September 2026: Zwei neue echte Quellen (iptv-epg.org MK + DE) + Kaskaden-Luecken-Bug behoben (mehrere Quellen pro Sender statt nur die erste)

**Neue Quelle `quellen/mk_epg.py`:** Nach langer erfolgloser Suche nach
einer echten Mazedonien-Quelle (MaxTV-GO/Spectar tot, A1s eigene
"Xplore TV"-API per IP gesperrt) wurde `https://iptv-epg.org/files/
epg-mk.xml` gefunden und integriert - 109 mazedonische Kanaele, live
verifiziert (u.a. MRT 1 mit echten Titeln). AUTOMATISCH fuer jeden
`MK|...`-Sender als letzter Fallback nach Siol/TvProfil.net, kein
eigenes Praefix noetig. Gleiches Cache-/Match-Prinzip wie alle anderen
XMLTV-Sammeldatei-Quellen (deswird.org/PlutoTV/SportKlub) - exakter
Namensabgleich, dann Kern-Abgleich, dann difflib-Fallback (cutoff 0.72).

**Neue Quelle `quellen/iptvepg_de_epg.py`:** `https://iptv-epg.org/
files/epg-de.xml` (438 deutsche Kanaele) als SIEBTER und letzter
Fallback der DE-Kaskade (nach deswird.org/PlutoTV/tvmovie.de/hoerzu.de/
Joyn-VOD/search.ch). Deckt v.a. ARD-Regionalstudios ab, die deswird.org
nicht kennt (alle 10 WDR-Lokalstudios, MDR Sachsen/Sachsen-Anhalt/
Thueringen, NDR Hamburg/Mecklenburg-Vorpommern/Schleswig-Holstein, rbb
Berlin/Brandenburg, SWR BW) sowie weitere Luecken (DF1, Nitro, Zee One,
Sat.1 Bayern, TVA Ostbayern, Oberpfalz TV, ClipMyHorse.TV, GEO DE,
Artflix u.a.). Live verifiziert im Produktions-Workflow: 210 zusaetzliche
Sender.

**Kaskaden-Luecken-Bug behoben (betraf ALLE Multi-Quellen-Kaskaden):**
Bisher galt in jeder Kaskade (DE, BA/ME-Telemach, RS-mts.rs, HR-MojMaxTV,
SI/MK-Siol) das Prinzip "erste Quelle mit IRGENDWELCHEN Daten gewinnt,
alle folgenden Quellen werden komplett uebersprungen" (`continue` nach
erstem Treffer). Das fuehrte dazu, dass Sender wie Sixx trotz
verfuegbarer, vollstaendigerer Daten bei einer spaeteren Quelle (z.B.
hoerzu.de) den ganzen Tag ueber grosse Luecken mit generischem
Platzhaltertext zeigten, weil die erste Quelle (deswird.org) nur einen
Teil des Tages abdeckte. Fix: ALLE Quellen einer Kaskade werden jetzt
IMMER der Reihe nach versucht; jede schreibt nur noch den Teil des
Zeitraums, der von vorherigen Quellen in derselben Kaskade noch NICHT
abgedeckt wurde (`_ohne_bereits_geschriebene_ueberlappung()`-Muster,
analog zur bereits bestehenden `segmente_ohne_ueberlappung()`-Logik fuer
generische Luecken). Umgesetzt fuer alle fuenf betroffenen Kaskaden.
Kein Risiko von doppelten/widerspruechlichen Eintraegen, da jede Quelle
nur die noch unbedeckte Restzeit bekommt.

**HR|SK-Playlist-Namensabgleich erweitert:** `hr_sk_playlist_namen`
(fuer die exakte TiviMate-Kanal-ID-Zuordnung, analog zu DYN PPV 1-20)
erkannte bisher nur "HR| SK N" in der eigenen Playlist, nicht "HR|
SPORT KLUB N" (die tatsaechliche Schreibweise in der Playlist des
Nutzers) - Regex entsprechend erweitert.

**Kleinere sender.txt-Ergaenzungen (echte Datenluecken, per direktem
Playlist-Abgleich gefunden):** `DE|RTL NITRO FHD`/`DE|RTL NITRO HD`
(komplett gefehlt), `US|FANDUEL TV EXTRA`, sowie drei PBS-Lokalsender
(PBS Detroit WTVS, PBS NY Plainview WLIW, PBS WGBH MA Boston - letztere
zwei im "leeres Land"-Format wegen eingebetteter Pipe-Zeichen im Namen).

**September 2026: Quellen-Audit - keine Quelle ist redundant, nichts
entfernt.** Auf Nutzerwunsch wurde geprueft, ob (analog zur frueheren
Entfernung von Samsung TV Plus/mymedia.ba) irgendeine der ~26
`quellen/*.py`-Module inzwischen ueberfluessig ist, weil eine andere
Quelle in derselben Kaskade laengst alles abdeckt. Grundlage war die am
Ende jedes Laufs ausgegebene Zusammenfassungszeile "Echte
Programmdaten fuer N Sender geladen (Quelle: Anzahl, ...)" aus einem
frischen, echten Workflow-Lauf. Ergebnis: JEDE der 26 Quellen hat einen
Beitrag von mindestens 2 Sendern (Search.ch: 2, DAZN: 5, Joyn-VOD: 6),
keine einzige liefert 0 - anders als bei Samsung TV Plus/mymedia.ba
(die dort nachweislich tot waren) gibt es aktuell keine wirklich
ueberfluessige Quelle. Nichts wurde entfernt. **Lehre:** Eine kleine
Trefferzahl allein ist bei Opt-in-Quellen (SKY:/DAZN:/MAGENTA:/etc.,
die nur fuer explizit markierte Zeilen zustaendig sind) KEIN Hinweis
auf Redundanz - erst eine Zahl von 0 (bei einer automatischen Quelle,
die theoretisch fuer viele Sender zustaendig waere) ist ein echter
Entfernungs-Kandidat, wie bei Samsung TV Plus/mymedia.ba.

## September 2026: Neuer sender.txt-Bug-Typ gefunden - eingebettetes Pipe im Beschreibungsfeld verfaelscht die Kanal-ID bei "leeres Land"-Zeilen

Auf Nutzerwunsch ("kriegst du noch die letzten paar fehlenden raus?")
wurde die eigene Playlist erneut komplett heruntergeladen (temporaer,
danach wieder geloescht) und gegen `sender.txt`/die generierte XML
abgeglichen - diesmal mit einem deutlich genaueren Vergleichsskript
(Beruecksichtigung von Gross-/Kleinschreibung, dem UK-Anzeige-Override
bei SKY:/FREEVIEW:, `maxsplit=3` beim 4.-Feld-Override analog zu
`generate_epg.py`, und der exakten `rsplit(2)`-Logik fuer "leeres
Land"-Zeilen). Von anfangs ueber 2000 vermeintlich fehlenden Sendern
blieben nach Ausschluss bewusst deaktivierter Kategorien (BBCI/NOW TV)
und VOD-Lernvideos nur noch ~35 echte Kandidaten uebrig.

**Neuer, bisher unbekannter Bug-Typ gefunden:** Bei "leeres Land"-
Zeilen (Zeile beginnt mit `|`, siehe `generate_epg.py`-Kommentar bei
`zeile.startswith("|")`) trennt der Parser NUR an den LETZTEN ZWEI
Pipes der Zeile (Beschreibung, Logo) - alles davor ist der Sendername,
egal wie viele Pipes er selbst enthaelt. Enthaelt aber das
BESCHREIBUNGSFELD selbst faelschlich ein eingebettetes Pipe-Zeichen
(z.B. `Uk| Bein Sports Asia 2 ᴸⁱᵛᵉ` statt `Bein Sports Asia 2 ᴸⁱᵛᵉ`),
verschiebt sich die vom Parser erkannte Grenze - der TATSAECHLICH
geparste Sendername bekommt dadurch einen stummeligen, falschen
Suffix angehaengt (z.B. `UK|UK| BEIN SPORTS ASIA 2|Uk` statt
`UK|UK| BEIN SPORTS ASIA 2`), was die Kanal-ID verfaelscht und die
automatische TiviMate-Zuordnung fuer genau diesen Sender verhindert -
ohne dass sich das in `sender.txt` selbst als offensichtlicher Fehler
zeigt (die Zeile sieht auf den ersten Blick normal aus).
Betroffen und behoben (7 Zeilen, stummeliger Pipe-Rest aus dem
Beschreibungsfeld entfernt, Sendername selbst NIE angefasst): BEIN
SPORTS ASIA 2/3, PBS NJ/NY (WNET)/KY (WKLE), PBS WGBH MA Boston (in
einer fruehreren Session dieser Art selbst neu angelegt), Crime Scene
TV DE, Car 54 Where Are You.
**Erkennungsmethode fuer kuenftige Faelle:** Fuer jede "leeres Land"-
Zeile den Sendernamen nach der echten `rsplit(2)`-Logik berechnen und
gegen die tatsaechlichen Playlist-Namen abgleichen (case-/whitespace-
normalisiert); ergibt das keinen exakten Treffer, aber ein Abschneiden
an einem FRUEHEREN internen Pipe im berechneten Sendernamen einen
Treffer, ist das der eindeutige Beweis fuer diesen Bug-Typ (Skript
`find_stray_pipe_bugs.py`-Methodik, nicht dauerhaft im Repo). Reiner
Zufallstreffer ("beschreibung startet mit dem Sendernamen") ist KEIN
verlaesslicher Indikator - das ist bei korrekten Zeilen (z.B. `|CHAMP
| Wrexham|Wrexham ᴸⁱᵛᵉ|`) das normale, gewollte Muster (Beschreibung =
Sendername in Title Case + Live-Suffix) und erzeugt viele Fehlalarme.

**Echte Datenluecken ergaenzt** (Playlist hat den Sender, `sender.txt`
hatte eine Nummernluecke innerhalb einer sonst vollstaendigen Reihe):
`NAME:LOI 01`-`05` (nur 06-15 vorhanden), `NAME::Paramount+  01`/`02`
(nur ab 03), `NAME::Flo Racing  03`/`04` (nur ab 05) - jeweils mit dem
Logo der benachbarten, bereits vorhandenen Nummer ergaenzt.

**Datenmuell bereinigt** (derselbe seit Sommer 2026 bekannte Bug-Typ,
siehe fruehere ESPN+/STAN/GaaGo-Faelle): `Boxing 1`/`2`/`4`/` 05`
hatten noch den alten, vollen Roh-Event-Text im NAME:-Kern gespeichert
statt des sauberen Kerns - auf den reinen Kern reduziert (`Boxing  05`
bewusst mit doppeltem Leerzeichen und fuehrender Null belassen, da
genau diese Schreibweise durch die generische Kern-Extraktions-Regex
`kern_vorne_und_event_extrahieren()` fuer den Rohtext "Boxing  05  :
FURY vs HALL  6PM" erzeugt wird - siehe Kommentar dort zu
"\s+0*\d+").

**Bestaetigte False Positives des Vergleichs (kein Fix noetig):**
`DE| DYN PPV 1-20 HD` (fest im Code, nicht in `sender.txt` - laut
Workflow-Log "20 von 20 exakt abgeglichen") und `HR| SPORT KLUB 1-10`
(laufzeitseitig per `hr_sk_playlist_namen` auf den exakten Playlist-
Namen umgeschrieben - laut Log "10 von 10 exakt abgeglichen") - beide
Mechanismen sind fuer ein rein statisches Vergleichsskript unsichtbar,
da sie die Kanal-ID erst zur Laufzeit gegen die Playlist aktualisieren.

## September 2026: HR|SK 1-10 endgueltig auf HR|SPORT KLUB 1-10 umbenannt (Playlist-Abgleich-Mechanismus entfernt)

Der Nutzer meldete, dass nach dem `hr_sk_playlist_namen`-Fix (siehe
Abschnitt "HR|SK/RS|SPORT KLUB-Verwechslung..." weiter oben) seine
manuelle TiviMate-Zuordnung fuer `HR|SK 1-10` wiederholt automatisch
auf `RS|SPORT KLUB` zurueckgesetzt wurde, obwohl er sie korrekt auf
die kroatischen Sender gesetzt hatte.

**Root Cause (kein Bug in unserem Code, sondern eine Namenskollision):**
Der ROHE Anbieter-Playlist-Name fuer diese Kanaele ist faelschlich
identisch zum ECHTEN `RS|SPORT KLUB N`-Sender benannt (Fehlbenennung
durch den Anbieter selbst). `hr_sk_playlist_namen` griff hier nicht
(der Rohname beginnt mit "RS|", nicht "HR|", die Regex matchte also
nie) - die generierte ID blieb bei der statischen `HR|SK N`-Schreibweise.
TiviMates eigener automatischer Namensabgleich (bei jedem EPG-Neuladen)
verglich aber weiterhin den ROHEN Anbieternamen "RS| SPORT KLUB N"
exakt gegen unsere ECHTEN `RS|SPORT KLUB N`-Sendereintraege in
`sender.txt` und ueberschrieb dadurch bei jedem Reload die manuelle
Korrektur des Nutzers zurueck auf den falschen (aber echten) RS-Kanal.

**Wichtige Klaerung dabei:** Der Nutzer hatte diese Kanaele urspruenglich
auf "SK" umbenannt, weil er annahm, nur unter diesem Namen wuerden
unsere Quellen echte Programmdaten liefern - das stimmt so nicht (mehr):
`sportklub_kanal_finden()` (`quellen/sportklub_epg.py`, `_SK_NUMMER_
PATTERN`) akzeptiert bereits BEIDE Schreibweisen, "SK N" und "SPORT
KLUB N", gleichwertig. Der eigentliche Grund fuer die damalige
Umbenennung (ein `RS|SPORT KLUB`-Fehltreffer bei mts.rs, siehe Abschnitt
"HR|SK/RS|SPORT KLUB-Verwechslung" oben) betraf eine ANDERE Sendergruppe/
Land (RS-Sender bei mts.rs), nicht die HR-Kaskade (MojMaxTV/SportKlub).

**Fix:** `sender.txt` umbenannt: `HR|SK 1-10` -> `HR|SPORT KLUB 1-10`
(gleiche Logos). Der `hr_sk_playlist_namen`-Mechanismus (Playlist nach
"HR| SK N"/"HR| SPORT KLUB N" durchsuchen und die ID laufzeitseitig
umschreiben) sowie der zwischenzeitlich eingebaute Alias-Hack in
`kanal_id_varianten()` wurden komplett entfernt - beide sind durch die
Umbenennung ueberfluessig geworden, da die generierte ID jetzt direkt
`HR|SPORT KLUB N` lautet. Kollisionsfrei, da Land `HR` (nicht `RS`) -
TiviMates Namensabgleich kann `HR|SPORT KLUB N` und `RS|SPORT KLUB N`
jetzt eindeutig unterscheiden. Der Nutzer hat seine 10 TiviMate-Kanaele
entsprechend auf `HR| SPORT KLUB 1` bis `10` umbenannt.

**Lehre fuer aehnliche Faelle:** Wenn der ROHE Anbieter-Playlist-Name
eines Kanals zufaellig exakt mit einer ANDEREN, echten `sender.txt`-ID
uebereinstimmt (Anbieter-Fehlbenennung, nicht unser Code), kann das
NICHT durch eine laufzeitseitige ID-Ueberschreibung geloest werden
(die betrifft nur den Fall, dass unsere ID vom Playlist-Namen abweicht,
nicht dass zwei verschiedene Sender denselben Playlist-Namen tragen) -
einzige zuverlaessige Loesung ist, die eigene `sender.txt`-ID so zu
aendern (anderer Sendername/anderes Land-Praefix), dass sie sich vom
kollidierenden echten Sender unterscheidet, UND den Nutzer seinen
Playlist-/TiviMate-Kanalnamen (falls von ihm aenderbar) entsprechend
anpassen zu lassen. Vor einer Aenderung immer pruefen, ob die
Zielschreibweise von der zustaendigen echten Quelle (hier: `sportklub_
epg.py`) bereits unterstuetzt wird, bevor eine sender.txt-Umbenennung
vorgeschlagen wird.

## September 2026: HR|SK->HR|SPORT KLUB-Umbenennung hat einen alten Fuzzy-Match-Schutz umgangen (Cindy aus Marzahn/Hardcore Pawn Bug) + WICHTIGE LEHRE zu TiviMates Auto-Matching

Direkt nach der obigen `HR|SK` -> `HR|SPORT KLUB`-Umbenennung meldete
der Nutzer voellig falsche Sendungen bei diesen Kanaelen (u.a. "Cindy
aus Marzahn", "Hardcore Pawn Chicago" - deutsche Trash-TV-Sendungen
statt kroatischem Sport-Klub-Programm).

**Root Cause:** `mojmaxtv_kanal_finden()` (`quellen/mojmaxtv_epg.py`)
hatte bereits seit einem frueheren Bug (siehe "Sport Klub HR"-Abschnitt
weiter oben) eine Sicherung: MojMaxTV fuehrt gar keinen "Sport Klub"-
Kanal mehr, deshalb wird fuer das Namensmuster `SK N` NUR ein exakter
Treffer akzeptiert, kein unscharfer `difflib`-Fallback (der bei kurzen
Strings sonst zufaellig auf einen komplett falschen Kanal matchen kann).
Diese Sicherung war aber nur an das Muster `^SK\s*0*(\d+)$` gekoppelt -
nach der Umbenennung auf `SPORT KLUB N` griff sie nicht mehr, der
Sendername fiel in den unscharfen Fallback und matchte zufaellig auf
irgendeinen aehnlich kurzen MojMaxTV-Kanalnamen.
**Fix:** Die Regex-Sicherung deckt jetzt BEIDE Schreibweisen ab
(`^(?:SK|SPORT\s*KLUB)\s*0*(\d+)$`) - `sportklub_epg.py` (die
tatsaechlich zustaendige, korrekte Quelle) liefert unter "SPORT KLUB N"
weiterhin unveraendert echte Daten.

**Lehre fuer JEDE kuenftige sender.txt-Umbenennung, die eine bestehende
Namensform aendert:** Bevor ein Sendername in `sender.txt` umbenannt
wird (nicht nur bei HR-Sport-Klub, generell), IMMER per `grep -rn
"<alte Schreibweise>"` durch ALLE `quellen/*.py`-Module suchen, ob dort
irgendwo eine Regex/ein Namensmuster HART an die ALTE Schreibweise
gekoppelt ist (Sicherungen gegen fruehere Fehltreffer sind oft genau so
eng gefasst) - eine Umbenennung kann sonst unsichtbar eine bestehende
Fehltreffer-Sicherung umgehen und einen laengst behobenen Bug in neuer
Form wieder einschleppen. `pytest` allein haette das hier NICHT
aufgefangen (kein Test deckte den Live-API-Fuzzy-Fallback ab).

**WICHTIGE, KORRIGIERTE Lehre zu TiviMates automatischem Matching:**
In dieser Session wurde zunaechst angenommen (und dem Nutzer so gesagt),
eine Umbenennung des Kanals INNERHALB von TiviMate (Sendernamen-Editor)
wuerde ausreichen, damit TiviMates automatischer Namensabgleich auf
unsere neue `HR|SPORT KLUB N`-ID matcht - analog zu anderen Sendern, bei
denen eine TiviMate-Umbenennung offenbar funktioniert hatte. Der Nutzer
hat das exakt so umgesetzt (TiviMate-Kanaele umbenannt, ID bei uns
angepasst, bestehende Zuordnung VORHER aufgehoben, TiviMate-Cache
geleert, EPG neu geladen) - **die automatische Zuordnung ist trotzdem
NICHT auf `HR|SPORT KLUB N` gesprungen**, sondern weiterhin auf das
gleich klingende, aber inhaltlich falsche `RS|SPORT KLUB N`.
Das widerlegt die urspruengliche Annahme: TiviMates automatischer
Namensabgleich matcht ganz offensichtlich gegen den ROHEN, vom Anbieter
in der M3U-Playlist gelieferten Kanalnamen (hier faelschlich "RS| SPORT
KLUB N" - eine Anbieter-Fehlbenennung, siehe Abschnitt oben) - NICHT
gegen einen vom Nutzer INNERHALB von TiviMate frei vergebenen
Anzeigenamen. Eine TiviMate-seitige Umbenennung aendert also nur die
Darstellung in der Senderliste, nicht die fuer den automatischen EPG-
Abgleich verwendete Kennung.
**Praktische Konsequenz:** Bei diesen 10 Kanaelen (und jedem aehnlich
gelagerten Fall, wo der rohe Anbieter-Playlist-Name zufaellig exakt mit
einem ANDEREN, echten `sender.txt`-Sender kollidiert) ist KEINE
sender.txt-Umbenennung/ID-Anpassung in der Lage, eine automatische
TiviMate-Zuordnung herzustellen - das laesst sich serverseitig nicht
loesen. Die manuelle Zuordnung in TiviMate bleibt hier dauerhaft
noetig; einzig die tatsaechlich angezeigten PROGRAMMDATEN hinter dieser
manuellen Zuordnung lassen sich (wie mit obigem Fix geschehen) korrigieren.
**Fuer kuenftige, aehnliche Faelle:** NIE wieder vorab zusichern, dass
eine TiviMate-interne Umbenennung die automatische Zuordnung herstellen
wird, ohne das nach einem echten Workflow-Lauf + EPG-Reload beim Nutzer
tatsaechlich verifiziert zu haben - das ist reines TiviMate-Client-
Verhalten, das sich aus dem Code hier nicht ableiten laesst.

## September 2026: Workflow-Laufzeit halbiert - Netzwerk-Abrufe der groessten Quellen parallelisiert

Der Workflow lief zuletzt im Schnitt ~50-55 Minuten (Schritt "Generate
EPG" allein: 52-55 Min., per echten Laufzeiten aus den letzten
Workflow-Runs verifiziert - die aeltere Schaetzung "~27-45 Min." weiter
oben im Dokument war veraltet/zu optimistisch). Ursache: KEINE der
~29 `quellen/*.py`-Module nutzte bisher irgendeine Parallelisierung -
jeder einzelne Sender-Request (Kanalsuche + Programmabruf) lief
strikt sequenziell nacheinander, obwohl es sich um reine I/O-gebundene
Netzwerk-Wartezeit handelt (die GIL ist dabei kein Flaschenhals).

**Fix:** Neuer genereller Helper `_parallel_abrufen(sender_liste,
abruf_fn, worker=12)` (`generate_epg.py`, direkt vor dem TELEMACH-
Abschnitt) nutzt `concurrent.futures.ThreadPoolExecutor`, um den
REINEN Netzwerk-Abruf-Teil (Kanalsuche + Programmabruf, OHNE die
anschliessende XML-Erzeugung) einer ganzen Senderliste gleichzeitig
in mehreren Threads auszufuehren - `ThreadPoolExecutor.map()` erhaelt
dabei die Eingabereihenfolge, sodass das anschliessende sequenzielle
Schreiben in `xml_teile` (inkl. der Ueberlappungs-/Luecken-Fuellungs-
Logik zwischen mehreren Fallback-Quellen) unveraendert bleibt - jeder
Fehler faellt weiterhin pro Sender still auf die naechste Quelle bzw.
den generischen Text zurueck (Zero-Risk-Garantie bleibt erhalten, nur
der Netzwerk-Teil selbst laeuft jetzt parallel statt sequenziell).

Umgesetzt fuer die Quellen mit den meisten Einzel-Requests (ein
HTTP-Request pro Sender/Tag): Telemach + mtel.ba + klix.ba (BA/ME-
Kaskade), Sky, mts.rs + SportKlub + Arena (RS-Kaskade), A1 + MojMaxTV
+ SportKlub (HR-Kaskade), TVPassport. NICHT angefasst: alle "einmal
pro Lauf komplett laden, dann lokal matchen"-Quellen (deswird.org,
PlutoTV, Tubi, Joyn-VOD, iptv-epg.org DE/MK, Magenta-myTeamTV,
delo.si) - die sind bereits optimal (nur 1 Request unabhaengig von der
Senderzahl) und brauchen keine Parallelisierung.

**Ergebnis (per echtem Workflow-Lauf verifiziert, Commit `d8210af`):**
Schritt "Generate EPG" 54:31 Min. -> 25:41 Min. (mehr als halbiert).
Sender-Gesamtzahl im generierten EPG identisch (19133 vor und nach dem
Fix) - keine Sender verloren gegangen. Die Aufteilung "echte
Programmdaten pro Quelle" verschob sich minimal zwischen A1 (109 ->
37 Treffer) und MojMaxTV (81 -> 141 Treffer) - das liegt an A1s
eigener Instabilitaet (503 Service Unavailable, siehe eigener
A1-Abschnitt weiter oben) an diesem konkreten Lauf, nicht am Fix
selbst: die RS/HR-Luecken-Fuellungs-Kaskade hat das automatisch
kompensiert (MojMaxTV sprang fuer die A1-Ausfaelle ein), in Summe
blieb die Zahl echter Treffer nahezu gleich (3879 -> 3870).

**Noch nicht umgesetzt (moegliche weitere Optimierungen, besprochen
aber auf Nutzerwunsch noch nicht gebaut):**
- Die uebrigen kleineren Opt-in-Quellen mit Request-pro-Sender
  (Magenta, DAZN, Arena/ARENA:-Praefix, Freeview, TVGuide, klix.ba,
  EpgshareUS-Locals) sind noch nicht parallelisiert - dort faellt die
  Ersparnis geringer aus (weniger Sender pro Quelle), waere aber nach
  demselben `_parallel_abrufen()`-Muster leicht nachruestbar.
- Kein Retry bei transienten Fehlern (502/503/Timeout) - ein
  fehlgeschlagener Request wird sofort als "kein Treffer" gewertet,
  kein zweiter Versuch. Wuerde die A1-Fehlerquote (siehe oben) weiter
  senken, ist aber ein separates Thema von der reinen Laufzeit-
  Optimierung.
- Der eigentliche Rest der Laufzeit (unter 26 Minuten fuer die
  restlichen NAME:-Kaskaden, die DE-Kaskade mit ihren mittlerweile
  sieben Quellen, das generische Tagesraster fuer alle ~19.000 Sender
  usw.) wurde noch nicht analysiert/optimiert - naechster Kandidat fuer
  eine weitere Laufzeitverbesserung, falls gewuenscht.

## September 2026: ARENA:-Praefix mit nicht unterstuetztem Land erzeugt doppelte/ueberlappende Kanal-ID (behoben)

Der Nutzer meldete "Keine Information"-Platzhalter zwischen echten
Sendungen bei mehreren Arena-Sport-/Sport-Klub-Sendern (BA/HR/SI/RS).
Konkret nachgewiesen und behoben wurde ein Fall:

- **Ursache:** `sender.txt` enthielt zusaetzlich zur normalen Zeile
  `HR|ARENA SPORT 1 HD` noch eine Zeile `ARENA:BA|ARENA SPORT 1 HD|...`.
  Arena Sport hat aber KEINE eigene bosnische Seite (`arena_epg.py`
  unterstuetzt nur `HR`/`RS`) - der Code (`generate_epg.py`, ARENA:-
  Block) faellt bei einem nicht unterstuetzten Land-Wert (hier "BA")
  silently auf "HR" zurueck (`if arena_land not in ("HR","RS"):
  arena_land = "HR"`). Dadurch entstand ein ZWEITER, komplett
  unabhaengiger `<channel id="HR|ARENA SPORT 1 HD">`-Eintrag, der
  AUSSERHALB der normalen A1/MojMaxTV/SportKlub-Ueberlappungs-Logik
  (`_hr_geschrieben_intervalle`) lief und deshalb eigene, mit dem
  echten HR-Sender exakt ueberlappende `<programme>`-Eintraege in
  denselben Kanal schrieb. Per direktem XML-Vergleich verifiziert: 145
  Zeitslots mit je ZWEI widerspruechlichen Sendungen fuer dieselbe ID
  und denselben Zeitraum. Ein Player kann zwei sich ueberlappende
  Eintraege fuer exakt dieselbe Zeit nicht sauber aufloesen - das
  aeussert sich als "Keine Information" oder falsches Programm.
- **Fix:** Die ueberfluessige `ARENA:BA`-Zeile wurde aus `sender.txt`
  entfernt (Commit `e0dfdb9`) - sie war ohnehin redundant, da Bosniens
  eigenes, echtes Arena-Sport-1-Programm bereits ueber
  `TELEMACH:BA|ARENA SPORT 1 HD` (mtel.ba/Telemach, live verifiziert
  mit eigenstaendigen, von Kroatien abweichenden Sendungen) abgedeckt
  wird.
- **Lehre/Vorsichtsmassnahme fuer kuenftige Faelle:** Bei JEDEM
  Opt-in-Praefix mit Land-Whitelist und Silent-Fallback (`ARENA:` nur
  HR/RS, `TELEMACH:` nur BA/ME, `SKY:` nur DE/GB, ...) IMMER pruefen,
  ob fuer die erzeugte `<channel>`-ID (Land-Fallback-Wert + Kanalname)
  bereits eine andere Zeile in `sender.txt` dieselbe ID erzeugt, BEVOR
  eine neue Opt-in-Zeile mit einem exotischen/nicht unterstuetzten
  Land-Wert eingetragen wird - der Silent-Fallback ist an sich
  gewolltes Verhalten (siehe Doku bei den einzelnen Quellen-
  Abschnitten), macht aber unentdeckte Kollisionen mit bereits
  bestehenden, "richtigen" Land-Zeilen moeglich. Bei einer erneuten
  Meldung "Sender X zeigt Platzhalter/Konflikte" IMMER zuerst per
  Python direkt im generierten `Epg_365_Tage.xml.gz` pruefen (mit
  `xml.etree.ElementTree`, NICHT nur Regex/Text-Suche - siehe naechster
  Punkt) ob (a) doppelte `<channel id>` existieren
  (`collections.Counter` ueber alle `id`-Attribute) und (b) ob fuer den
  betroffenen Kanal `<programme>`-Eintraege mit identischem/ueberlappendem
  Zeitfenster mehrfach vorkommen - beides ist der zuverlaessigste Weg,
  diese Klasse von Bug zu erkennen, bevor an der Matching-Logik der
  einzelnen Quellen gesucht wird.
- **Wichtig fuer die Verifikation selbst:** Regex-basierte Textsuche im
  (sehr grossen, ueber 300 MB) rohen XML kann bei komplexen Mustern
  (verschachtelte Anfuehrungszeichen, mehrzeilige Tags) zu falschen
  Ergebnissen fuehren. Fuer eine wirklich verlaessliche Aussage ("hat
  Kanal X wirklich Sendung Y?", "gibt es doppelte IDs?") immer
  `xml.etree.ElementTree.fromstring()` auf die entpackte Datei anwenden
  und ueber `root.iter("channel")`/`root.iter("programme")` gehen -
  das ist in dieser Session der entscheidende Schritt gewesen, um einen
  ersten (falschen) Verdacht zu widerlegen bzw. zu erhaerten.

## Offener Fall: HR|SPORT KLUB 1 zeigt in TiviMate gelegentlich falsches Programm ("Container Wars") - KEIN bestaetigter Datenfehler bei uns

Der Nutzer meldete per Screenshot, dass der von ihm in TiviMate
ausgewaehlte EPG-Eintrag "HR| SPORT KLUB 1" zeitweise das Programm des
komplett anderen, echten deutschen Senders "Sport1" zeigt (u.a.
"Container Wars", "Ladykracher", "Pastewka" - alles reale Sport1-
Sendungen zur exakt richtigen Uhrzeit, live bei MojMaxTV unter dem
eigenstaendigen Kanal "Sport 1" verifiziert, siehe `HR|SPORT 1 ⱽᴵᴾ ᴿᴬᵂ`
in `sender.txt`).

**Grundlich verifiziert und NICHT die Ursache:**
- `arena_epg.py`/`mojmaxtv_epg.py`/`sportklub_epg.py` haben (Stand
  September 2026) bereits explizite Exact-Match-Sicherungen fuer
  "SK N"/"SPORT KLUB N" gegen genau diese Art Fehltreffer (siehe
  Abschnitte weiter oben) - kein Fuzzy-Fallback moeglich.
- Mit `xml.etree.ElementTree` (nicht nur Regex) direkt im generierten
  `Epg_365_Tage.xml.gz` geprueft: `HR|SPORT KLUB 1` UND `HR| SPORT KLUB
  1` (beide Leerzeichen-ID-Varianten, siehe `kanal_id_varianten()`)
  existieren jeweils genau EINMAL, haben beide das korrekte Sport-Klub-
  Logo (`logos/hr_sk/sk_1.png`, NICHT irgendein Sport1-Logo) und
  jeweils 47 durchgehend echte Sport-Sendungen (Bundesliga, span./
  tuerk. Liga usw.) - NULL Treffer fuer "Container Wars" in der Datei,
  zu keinem Zeitpunkt.
- Der Nutzer hat bestaetigt, dass in TiviMate nur EINE EPG-Quelle
  eingetragen ist (unsere eigene `.xml.gz`-URL) - eine zweite,
  kollidierende Drittanbieter-Quelle scheidet damit als Erklaerung aus.

**Arbeitshypothese (nicht verifizierbar ohne TiviMate-internen
Zugriff):** TiviMates lokale EPG-Datenbank haelt fuer diese Senderzeile
vermutlich noch eine alte, verwaiste Bindung aus der Zeit VOR der
September-Umbenennung `HR|SK 1` -> `HR|SPORT KLUB 1` (siehe
"HR|SK->HR|SPORT KLUB-Umbenennung"-Abschnitt weiter oben, wo im
selben Zeitraum tatsaechlich ein MojMaxTV-Fuzzy-Fehltreffer auf
"Sport 1" auftrat, ABER fuer die "SK N"-Schreibweise, nicht "SPORT
KLUB N"). Ein einfaches "EPG aktualisieren" in TiviMate raeumt so eine
verwaiste Bindung offenbar nicht auf - nur ein kompletter Loeschen-und-
neu-Anlegen-Vorgang der EPG-Quelle wuerde das voraussichtlich beheben.
**Der Nutzer moechte das aber ausdruecklich NICHT tun** (schlechte
Erfahrung: verlor beim letzten Neuaufbau 1009 Sender-Zuordnungen) - der
Fall bleibt also bewusst ungeloest/offen stehen, KEIN weiterer
Code-Fix-Versuch ohne neue, konkrete Evidenz.

**Vorgehen bei kuenftigen aehnlichen Meldungen ("Sender X zeigt
falsches Programm, obwohl korrekt zugeordnet"):** Erst IMMER wie oben
beschrieben mit `xml.etree.ElementTree` die eigene generierte Datei
lueckenlos verifizieren (Kanal-ID(s), Logo, alle `<programme>`-
Eintraege). Wenn die eigene Datei nachweislich sauber ist UND der
Nutzer nur eine einzige, korrekte EPG-Quelle bestaetigt, liegt die
Ursache mit hoher Wahrscheinlichkeit auf TiviMate-Client-Seite
(verwaiste alte Kanal-Bindung in der lokalen Datenbank) - nicht weiter
an der Matching-Logik der Quellen suchen, sondern das dem Nutzer genau
so kommunizieren, statt einen ungerechtfertigten Code-Fix vorzuschlagen.

## September 2026: US| TENNIS PPV 1-30 (und alle anderen "::Kern"-Zeilen ohne Event-Text) - fuehrender Doppelpunkt blieb faelschlich im gespeicherten Kern, Live-Abgleich traf nie

Der Nutzer meldete per Screenshot, dass ALLE 30 Sender der Gruppe
`US| TENNIS PPV` weder eine automatische Kanalzuordnung noch echte
Live-Events bekamen - trotz vorhandener, sauberer `sender.txt`-Zeilen
(`NAME::Tennis  01|<Logo>` bis `NAME::Tennis  30|<Logo>`, KEIN
Datenmuell wie bei frueheren aehnlichen Faellen).

**Root Cause:** Beim Einlesen einer `NAME:`-Zeile wird `voller_name`
aus allem VOR dem letzten Pipe gebildet - bei diesen Zeilen also
`:Tennis  04` MIT fuehrendem Doppelpunkt (Teil der `":Kernname"`-
Konvention, die auch bei Flo Racing/Paramount+ verwendet wird). Die
generische Kern-am-Ende-Extraktion (`kern_und_event_extrahieren()`)
erkennt daraus korrekt Kern "Tennis  04" (OHNE Doppelpunkt) und
Event-Text "" (leer, da vor dem Doppelpunkt nichts steht). Ein
Sicherheits-Rollback direkt danach (`if kurzname != voller_name and
not _wirkt_wie_rohtext_muell(event_teil): kurzname, event_teil =
voller_name, ""` - gedacht als Schutz vor Faellen wie "TNT SPORTS |
Event 1", wo "TNT SPORTS" faelschlich als Event-Text abgetrennt
werden koennte) griff hier aber FAELSCHLICH: ein LEERER Event-Text
gilt per `_wirkt_wie_rohtext_muell("")` als "kein Muell" (Funktion
gibt bei leerem Text `False` zurueck) - das Rollback nahm den
unveraenderten `voller_name` MIT fuehrendem Doppelpunkt als
gespeicherten Kern (`daten["sender"] = ":Tennis  04"`, nicht
"Tennis  04"). Der Live-Playlist-Abgleich (`m3u_playlist_
abgleichen()`) extrahiert aus dem ECHTEN Rohnamen aber korrekt
"Tennis 04" OHNE Doppelpunkt (siehe Screenshots: "... :Tennis 04" /
"... :Tennis 15" - der Doppelpunkt ist dort nur Trenner, nicht Teil
des Kerns). Die beiden normalisierten Kernnamen ("`:TENNIS 04`" vs.
"`TENNIS 04`") waren dadurch NIE identisch - `name_pipe_kanal_index`
fand fuer keinen der 30 Sender einen Treffer, weder fuer die
Kanalnamen-Zuordnung noch fuer echte Events.
**Fix:** Das Rollback greift jetzt nur noch, wenn tatsaechlich ein
NICHT-LEERER Event-Text abgetrennt wurde, der zusaetzlich nicht wie
Muell aussieht (`if kurzname != voller_name and event_teil and not
_wirkt_wie_rohtext_muell(event_teil)`) - der urspruengliche
Schutzzweck ("TNT SPORTS | Event 1" bleibt unangetastet, da dort
event_teil nicht leer waere) bleibt erhalten. Bei leerem Event-Text
(reine "`:Kernname`"-Zeilen ohne jeglichen Event-Text davor) wird
jetzt korrekt der bereinigte Kern OHNE fuehrenden Doppelpunkt
uebernommen. Betraf strukturell ALLE `NAME::<Kern>`-Zeilen ohne
Event-Text vor dem Doppelpunkt, nicht nur Tennis PPV - z.B. auch
"Flo Racing  03"-"07" (mit `NAME::Flo Racing  0N|...` in derselben
Konvention gespeichert). `pytest` (95 Tests) bestaetigt gruen nach
dem Fix.
**Lehre:** Bei einem Sicherheits-Rollback, der eine Extraktion nur
unter bestimmten Bedingungen verwirft, IMMER auch den Fall "nichts
wurde abgetrennt" (leerer/None Ergebniswert) explizit bedenken - eine
Helper-Funktion wie `_wirkt_wie_rohtext_muell()`, die bei leerem Input
konservativ `False` zurueckgibt (technisch korrekt: ein leerer Text
"sieht nicht wie Muell aus"), kann in einer Sicherheitsbedingung genau
deshalb zum Gegenteil des Gewollten fuehren, wenn "leer" und "sauberer
Text, der nicht abgetrennt werden sollte" nicht auseinandergehalten
werden.

## September 2026: 13 fehlende Playlist-Kategorie-Trenner ergaenzt + automatische NAME:-Datenmuell-/Duplikat-Bereinigung eingebaut

Der Nutzer meldete "12 von ~18957 Playlist-Sendern noch nicht
zugeordnet" und dass er sie bei der schieren Menge nicht mehr von Hand
finden koenne. Ein reiner Textabgleich Playlist gegen `sender.txt`
(unter Beruecksichtigung aller bekannten Sonderformate: leeres-Land-
Zeilen, `NAME:`-Kernwerte, Opt-in-Praefixe mit 4. Feld, UK/GB-Alias bei
SKY:/FREEVIEW:) fand am Ende NULL echte fehlende Sender - jeder
Playlist-Name hatte rein textlich eine passende Zeile. Der eigentliche
Fund war eine andere Kanal-Art: die Playlist enthaelt fuer jede
Kategorie zusaetzlich eine eigene, rein dekorative "Trenner"-Kanalzeile
(`#EXTINF`-Eintrag mit einem Namen wie "##### GERMANY HEVC #####" oder
identisch zum `group-title`, ohne echtes Programm) - TiviMate zaehlt
diese mit als eigenen, zuzuordnenden Kanal. Es gibt dafuer bereits
einen eigenen, frueher angelegten Abschnitt in `sender.txt`
("##### PLAYLIST-KATEGORIE-TRENNER ... #####", alle Zeilen im
leeres-Land-Format `|<Trenner-Text exakt wie in der Playlist>|<Logo-
URL>` mit demselben `logos/kategorie_trenner/kategorie_trenner.png`-
Logo) - 392 von 405 in der aktuellen Playlist vorkommenden Trennern
standen dort bereits, 13 fehlten (u.a. "WOW ENTERTAINMENT ᴴᴰ ᴰᴼᴸᴮʸ
ᴬᵁᴰᴵᴼ", "LEAGUES FOOTBALL PPV", "APPLE TV F1 PPV", "MONTENEGRO/CMA
GORA ⱽᴵᴾ ᴿᴬᵂ") - ergaenzt, exakter Rohtext 1:1 aus der Playlist
uebernommen (temporaerer Download, danach geloescht, wie bei allen
frueheren Playlist-Abgleichen), keine Duplikate.
**Wichtige Lehre fuer kuenftige Abgleiche dieser Art:** ein erster
Vergleichsversuch verglich den Header-Text faelschlich gegen die
NORMALISIERTE GESAMTE sender.txt-Zeile (inkl. URL) statt nur gegen den
geparsten Sendernamen-Teil - das erzeugte zunaechst 404 "fehlende"
Treffer, obwohl 392 davon laengst vorhanden waren. Vor einer Bulk-
Ergaenzung IMMER den tatsaechlich geparsten Sendernamen vergleichen,
nicht die rohe Zeile.

**Zusaetzlich (separate Anfrage direkt danach): alter Datenmuell in
NAME:-Kernen systematisch gesucht und automatisiert.** Nach demselben
Muster wie in frueheren Sessions (ESPN+/STAN/GaaGo/Milb/Boxing, siehe
Abschnitte oben) fanden sich weitere 18 `NAME:`-Zeilen mit eingebettetem
altem Roh-Event-Text im Kern (DIRTVISION 01-03, FA Player 01-07, Fite
TV 1 HD, OHL 01, Rugby 6/13, US (P+) Italy SerieA 6, 2× Serie A ->
Paramount+, 2× -> Flo Racing). 14 davon waren reine Duplikate einer
bereits an anderer Stelle vorhandenen sauberen Zeile (z.B. `NAME:DIRTVISION
01 : Nodak Speedway 7:15 PM|` duplizierte das laengst vorhandene
`NAME:DIRTVISION 01 :|<echtes Logo>`) - geloescht. 5 hatten keine
saubere Zeile daneben und wurden auf den reinen Kern gekuerzt.

Auf Nutzerwunsch ("kann man das automatisch machen, damit wir das
nicht jedes mal manuell machen muessen") wurde direkt danach eine
DAUERHAFTE automatische Erkennung in `generate_epg.py` eingebaut, statt
das jedes Mal erneut von Hand zu suchen:

- Ein neuer, einmaliger Vorab-Durchlauf ueber alle `NAME:`-Zeilen
  (VOR der eigentlichen Verarbeitungsschleife) registriert zuerst
  saemtliche bereits sauberen Kerne in `_name_kern_registry` - "sauber"
  heisst: die Extraktion (`kern_und_event_extrahieren()`/
  `kern_vorne_und_event_extrahieren()`, unveraendert) trennt entweder
  gar nichts ab, oder nur einen leeren Doppelpunkt-Marker ohne
  jeglichen Text dahinter (z.B. ":Paramount+  02" oder "OHL 02 :").
  Ein NICHT-leerer abgetrennter Text gilt dagegen immer als echter
  Datenmuell.
- In der eigentlichen Verarbeitungsschleife wird bei jeder `NAME:`-
  Zeile mit erkanntem, nicht-leerem Muelltext gegen diese Registry
  geprueft: existiert der bereinigte Kern dort schon (aus dem
  Vorab-Durchlauf ODER aus einer bereits verarbeiteten Muell-Zeile
  weiter oben in derselben Datei), wird die Zeile als Duplikat komplett
  uebersprungen (kein doppelter `<channel>`-Eintrag mehr). Existiert er
  noch nicht, wird die Zeile trotzdem verwendet, aber der BEREINIGTE
  Kern (nicht der Roh-Datenmuell) wird als `<channel>`-ID benutzt -
  matcht dadurch sofort korrekt gegen den Live-Playlist-Abgleich, ganz
  ohne manuelle sender.txt-Korrektur.
- Der Vorab-Durchlauf (Reihenfolge-Unabhaengigkeit) ist wichtig: Steht
  die Muell-Zeile in `sender.txt` VOR der sauberen Zeile (der
  haeufigere Fall, da Muell oft aus dem urspruenglichen Playlist-Import
  stammt und saubere Ergaenzungen spaeter angehaengt wurden), wuerde
  ohne Vorab-Durchlauf die Muell-Zeile faelschlich zuerst registriert
  und die eigentlich bessere, saubere Zeile als Duplikat verworfen -
  genau umgekehrt vom gewuenschten Verhalten.
- `_wirkt_wie_rohtext_muell()` wurde dafuer von einer bei jeder
  Schleifeniteration neu definierten inneren Funktion auf Modulebene
  verschoben (identischer Code, keine Logikaenderung) - wird jetzt
  sowohl vom Vorab-Durchlauf als auch von der Hauptverarbeitung
  gemeinsam genutzt.
- Log-Ausgabe am Laufende (nur EINE Zeile, keine Einzelauflistung):
  "NAME:-Datenmuell automatisch bereinigt: N Kanal-IDs korrigiert, M
  Duplikate uebersprungen."
- **Wichtig: Die eigentliche Event-/Sendungstitel-Extraktion selbst
  wurde NICHT angefasst** - `kern_und_event_extrahieren()`,
  `kern_vorne_und_event_extrahieren()` und alle anbieterspezifischen
  Sonderfaelle (DYN PPV/DirtVision/FA Player/Rugby/etc.) sind
  unveraendert. Die neue Logik betrifft ausschliesslich, WELCHE
  `<channel>`-ID eine `NAME:`-Zeile am Ende bekommt bzw. ob die Zeile
  ueberhaupt einen eigenen Kanal erzeugt - nicht, was als
  Sendungstitel/-beschreibung angezeigt wird.
- Verifiziert durch isoliertes Nachbauen der echten Code-Bloecke
  (`exec()` der relevanten `generate_epg.py`-Ausschnitte mit
  synthetischen Test-Zeilen, da ein kompletter Lauf in der
  Entwickler-Sandbox wegen blockierter externer Quellen zu lange
  dauert) - mehrfach mit echten Faellen (DIRTVISION, FA Player,
  Paramount+) in BEIDEN Reihenfolgen (Muell zuerst / sauber zuerst)
  getestet, `pytest` (95 Tests) bleibt gruen.

**Direkt im Anschluss ein echter, durch die neue Logik AUFGEDECKTER
Bug gefunden:** Der Nutzer meldete per Screenshot, dass bei den 50
`DE: DYN PPV`-Sendern (NAME:-Playlist-Gruppe 1-50, nicht zu verwechseln
mit den 20 API-Kanaelen) in TiviMate ploetzlich nur noch ein generisches
Ordner-Icon statt des individuellen, nummerierten Logos angezeigt
wurde. Ursache: in `sender.txt` gab es fuer JEDE der 50 Nummern zwei
komplett getrennte `NAME:`-Zeilen mit demselben Kern - eine strukturell
"saubere" (kein abgetrennter Text) mit einem FALSCHEN, generischen
`externe_logos_import`-Logo, und eine mit eingebettetem Leerlauf-
Platzhaltertext im Kern ("- NO EVENT STREAMING - | 8K EXCLUSIVE | DE:
DYN PPV N") aber mit dem KORREKTEN, nummerierten Logo
(`logos/dyn_ppv/dyn_ppv_N.png`). Die neue automatische Duplikat-
Erkennung (siehe oben) hat bei diesem Sonderfall die STRUKTURELL
saubere, aber inhaltlich falsche Zeile registriert und die inhaltlich
richtige (aber wie Datenmuell aussehende) Zeile faelschlich als
Duplikat verworfen - "strukturell sauber" ist eben nicht automatisch
gleichbedeutend mit "inhaltlich korrekt". Behoben durch direkte
Bereinigung in `sender.txt`: pro Nummer nur noch EINE Zeile
(`NAME:DE: DYN PPV N|https://.../logos/dyn_ppv/dyn_ppv_N.png`), die
jeweils andere geloescht. **Lehre:** Bei zwei konkurrierenden
`NAME:`-Zeilen fuer denselben Kern IMMER pruefen, welche der beiden
tatsaechlich das korrekte, gewollte Logo/die gewollten Daten traegt,
bevor die "sauberer aussehende" pauschal bevorzugt wird - dieser Fall
war ein reines sender.txt-Datenproblem (zwei widerspruechliche
historische Eintraege), kein Fehler in der neuen Erkennungslogik
selbst.

## NFL TEAMS-Sender: Live-Playlist-Abgleich fand nie einen Treffer
(Kern-Rollback beim Einlesen vs. beim Abgleich unterschiedlich, September 2026)

**Symptom:** Nutzer meldete, dass der Sender `NAME:NFL TEAMS| FOX
PACKERS ST. LOUIS MO|...` im Player nicht gefunden/automatisch
zugeordnet wurde ("andere kommen, der aber nicht"). Erste Pruefung:
die Zeile war korrekt in `sender.txt` vorhanden (keine fehlende
Eintragung) - der Fehler lag also im Code, nicht in den Daten.

**Ursache:** Beim Einlesen von `sender.txt` trennt
`kern_und_event_extrahieren()` den Namen zunaechst am letzten Pipe:
Kern = `FOX PACKERS ST. LOUIS MO`, abgetrennter Text = `NFL TEAMS`.
Da `NFL TEAMS` NICHT wie Rohtext-Muell aussieht (kein Datum/keine
Uhrzeit/kein "vs"/kein bekannter Marker, ≤4 Woerter -
`_wirkt_wie_rohtext_muell()` liefert `False`), greift direkt danach
das bestehende Rollback ("kein echter Muelltext abgetrennt, also
bleibt der KOMPLETTE Rohname der Kern" - siehe Kommentar bei der
`NAME:`-Verarbeitung, urspruenglich fuer Faelle wie "TNT SPORTS |
Event 1" gedacht). Ergebnis: der in `name_pipe_kanal_index`
gespeicherte, fuer den Live-Abgleich massgebliche Kern (`daten
["sender"]`) ist der VOLLE String `NFL TEAMS| FOX PACKERS ST. LOUIS
MO` (inkl. Gruppenpraefix und Pipe) - identisch zur `<channel>`-ID.

Der Live-Playlist-Abgleich (`_kern_und_event_aus_rohname()`, aufgerufen
aus `m3u_playlist_abgleichen()`) rief zum Ermitteln des Such-Schluessels
aber NUR `kern_und_event_extrahieren()` OHNE dieses Rollback auf -
berechnete also fuer denselben Rohnamen nur `FOX PACKERS ST. LOUIS MO`
(ohne `NFL TEAMS|`). Dieser verkuerzte Schluessel existierte im Index
nicht (dort steht ja der volle String als Key) - der Lookup schlug
IMMER fehl, fuer saemtliche `NAME:NFL TEAMS|...`-Zeilen strukturell
gleichermassen (nicht nur fuer "FOX PACKERS ST. LOUIS MO"), da bei
jeder dieser Zeilen derselbe Effekt greift (`NFL TEAMS` ist bei jeder
Zeile der abgetrennte, nicht wie Muell aussehende Text). Die
`<channel>`-Definition selbst erschien zwar trotzdem korrekt in der
generierten XML (die haengt nicht vom Live-Abgleich ab), aber der
Sendungstitel konnte nie den aktuellen Live-Namen aus der eigenen
IPTV-Playlist des Nutzers uebernehmen.

**Fix:** `_kern_und_event_aus_rohname()` in `generate_epg.py` wendet
jetzt exakt dasselbe Rollback an wie die `NAME:`-Verarbeitung beim
sender.txt-Einlesen (gleiche Bedingung: `kurzname != voller_name and
event_teil and not _wirkt_wie_rohtext_muell(event_teil)` -> kompletter
Rohname wird zum Kern). Dadurch berechnen Index-Aufbau und
Live-Abgleich fuer denselben Rohnamen jetzt garantiert denselben
Schluessel. `pytest` (95 Tests) bleibt gruen.

**Lehre:** Wann immer ein Kernname aus einem rohen Playlist-/
Sender.txt-Namen extrahiert wird, MUSS exakt dieselbe Extraktions-
UND Rollback-Logik an BEIDEN Stellen laufen, an denen dieser Kern
verwendet wird (einmal beim Einlesen/Speichern in den Index, einmal
beim spaeteren Nachschlagen/Abgleich) - sonst diverging die
berechneten Schluessel unbemerkt und der Abgleich schlaegt lautlos
(ohne Fehlermeldung, da `real_daten is None` nur zu "kein Treffer"
fuehrt) fuer eine ganze Sendergruppe fehl.

## September 2026: Serie von Kanal-ID-Bugs bei kanal_id_varianten() - Sport Klub HD, Filme 2022 4k, RT UK, The Blaze, UEFA/NHL-Kerne, NOW TV, BBC iPlayer, PRIME

Nutzer meldete, dass TiviMate bei ~18.957 Live-Sendern eine kleine,
aber hartnaeckige Zahl an Sendern dauerhaft "Keine Information" zeigt,
trotz mehrerer vorheriger Fixes. Eine ganze Session lang wurden
nacheinander mehrere UNABHAENGIGE Bugs in `kanal_id_varianten()`
(generate_epg.py) gefunden, die alle denselben Symptomtyp erzeugen:
die generierte `<channel id>` weicht in Kleinigkeiten von der
tatsaechlichen `tvg-name`-Schreibweise in der Playlist des Nutzers ab,
wodurch TiviMates automatischer ID-Abgleich fehlschlaegt.

**Fund- und Fix-Reihenfolge:**

1. **`HR|SPORT KLUB 1-10` ohne "HD"-Suffix:** sender.txt hatte nur
   `HR|SPORT KLUB 1` etc., Playlist nutzt `HR| SPORT KLUB 1 HD` (mit
   angehaengtem "HD"). Fix: zusaetzliche `HR|SPORT KLUB N HD`-Zeilen in
   sender.txt ergaenzt. Das war vermutlich auch die tatsaechliche
   Ursache des seit Monaten offenen "Sport Klub 1 zeigt falsches
   Programm"-Falls (siehe "Bekannter offener Fall" in CLAUDE.md) - kein
   TiviMate-Cache-Problem, sondern ein echter fehlender ID-Treffer.
2. **`DE|FILME 2022 1/3 4k`** (kleines "k") und **`UK|RT uk HD`**
   (falsche Gross-/Kleinschreibung in sender.txt, sollte `RT UK HD`
   sein): beides reine Datenfehler in sender.txt, per Zusatzzeile bzw.
   Korrektur behoben.
3. **`US|THE BLAZE HD`:** Playlist enthaelt vor "HD" ein geschuetztes
   Leerzeichen (U+00A0) statt eines normalen - per 4. Feld
   (ID-Override) bei der `TVPASSPORT:`-Zeile mit dem exakten Zeichen
   ergaenzt, KEIN genereller Code-Fix (haette bei jedem Sender mit
   Leerzeichen im Namen die Anzahl der `<channel>`-Varianten
   verdoppelt - erster Ansatz dazu wurde wieder verworfen).
4. **UEFA/NHL "PRAEFIX \| NN -"-Kerne:** `kern_und_event_extrahieren()`
   behandelte den Text vor dem letzten Pipe als Laenderkuerzel und warf
   ihn weg, WENN er 2-4 Buchstaben lang ist - "UEFA" (4 Buchstaben)
   erfuellt dieses Muster zufaellig genauso wie echte Laendercodes
   ("US", "DE"), wurde also faelschlich verworfen. Dadurch gingen
   sowohl der Event-Text ("UEFA | 01 - Fenerbahce vs Roma") als auch
   die Zuordnung zu den in sender.txt hinterlegten
   `NAME:UEFA \| NN -`-Kernen verloren. **Fix:** Sonderfall fuer das
   "PRAEFIX \| NUMMER -"-Muster in `kern_und_event_extrahieren()`
   ergaenzt, der das Praefix (z.B. "UEFA", "NHL") explizit als Teil des
   Kerns behaelt statt es als Laendercode zu verwerfen.
5. **Leerzeichen VOR dem Pipe bei UEFA/NHL-Kernen:** Playlist schreibt
   zusaetzlich unterschiedlich viele Leerzeichen ZWISCHEN Praefix und
   Pipe (z.B. "UEFA  \| 01 -" mit zwei Leerzeichen), waehrend die
   bestehende Leerzeichen-Logik in `kanal_id_varianten()` nur
   Leerzeichen NACH dem Pipe abdeckte. Fix: zusaetzlicher
   `fullmatch()`-Zweig fuer genau dieses "PRAEFIX \| NUMMER -"-Muster,
   der alle Kombinationen aus 0/1/2 Leerzeichen vor UND nach dem Pipe
   erzeugt (9 Varianten) - bewusst nur fuer dieses spezielle Muster,
   nicht fuer alle "Land\|Sender"-IDs (haette sonst jeden Sender im
   Land verdreifacht statt verneunfacht).
6. **UEFA-Logo:** Alle 37 UEFA-Kanaele hatten 14 unterschiedliche,
   ausnahmslos FALSCHE Logos (zufaellig durch dieselbe Nummer-Kollision
   wie Punkt 4 verursacht - Logo-Suche lief teilweise ueber dieselbe
   blosse Nummer und traf fremde Sender wie "K16", "Region 25",
   "Siam Thai 13"). Nutzer schickte das echte UEFA-Logo als Bild,
   wurde herunterskaliert (300px, 256-Farben-Palette) und unter
   `logos/uefa/uefa.png` selbst gehostet, alle 37 Zeilen darauf
   umgestellt.
7. **NOW TV (`UK-NOWTV\|...`) und BBC iPlayer (`UK-BBCI\|...`):**
   NOW TV (Skys Streaming-Ableger) und BBC iPlayer fuehren exakt
   dasselbe Kanal-Lineup wie die bereits vorhandenen
   `SKY:GB\|.../FREEVIEW:GB\|...`-Sender (die als "UK\|..." angezeigt
   werden), aber die Playlist des Nutzers fuehrt sie unter einem
   zusaetzlichen Suffix am Laenderkuerzel ("UK-NOWTV\|", "UK-BBCI\|"
   statt "UK\|"). `kanal_id_varianten()` erzeugt jetzt fuer jede
   "UK\|..."-ID zusaetzlich beide Alias-Praefix-Varianten (je mit 0/1/2
   Leerzeichen nach dem Pipe).
8. **`PRIME\|`-Sender (915 Zeilen in sender.txt):** Der Regex in
   `kanal_id_varianten()` fuer die Laenderkuerzel-Erkennung war auf
   `[A-Za-z]{2,4}` begrenzt (2-4 Buchstaben) - "PRIME" hat aber 5
   Buchstaben und fiel dadurch KOMPLETT durchs Raster, bekam also nie
   eine Leerzeichen-Variante, obwohl alle anderen "Land\|Sender"-Sender
   laengst davon profitierten. Regex auf `{2,5}` erweitert (geprueft:
   "PRIME" ist aktuell das einzige 5-Buchstaben-Praefix in sender.txt).

**Vorgehen, das zum Erfolg fuehrte (Lehre fuer aehnliche Faelle):**
Ein Playlist-Download direkt aus der Sandbox-Umgebung war blockiert
(HTTP 511 von Cloudflare, vermutlich IP-Sperre des Anbieters gegen
Cloud-Sandboxes) - trotz mehrerer Versuche mit unterschiedlichen
User-Agents/Protokollen. Der zuverlaessige Ersatz war ein **temporaeres
Diagnose-Skript** (`tools/diagnose_fehlende_sender.py` +
`.github/workflows/diagnose_fehlende_sender.yml`, jeweils nach
Gebrauch wieder aus dem Repo entfernt), das exakt den `sender_daten`-
Aufbauteil von `generate_epg.py` importiert, alle `kanal_id_varianten()`
sammelt und gegen die echten `tvg-name`-Werte der Playlist vergleicht -
ausgefuehrt ueber GitHub Actions (kann die Playlist erreichen, im
Gegensatz zur Sandbox). Wichtige Verfeinerung dabei: die Playlist hat
~1,38 Mio. Zeilen, davon nur ~18.957 echte Live-Sender - der Rest ist
VOD (Filme/Serien), das ueber KEINEN zuverlaessigen Keyword-Filter
sauber vom echten Live-TV zu trennen ist (viele VOD-Gruppen heissen
harmlos wie "|AF| SOUTH AFRICA" oder "|NL| FORMULE 1"). Der einzige
zuverlaessige Weg war, sich vom Nutzer die exakte Liste der in
TiviMates "Gruppen verwalten"-Bildschirm sichtbaren Kategorienamen
geben zu lassen (Screenshots) und das Diagnose-Skript darauf als feste
Whitelist zu beschraenken - dabei auch die dort DEAKTIVIERTEN
Kategorien einschliessen, da Aktivierungsstatus nicht zuverlaessig mit
"gehoert zu den Live-Sendern" korreliert (Beispiel: "UK\| NOW TV" war
deaktiviert, hatte aber 149 tatsaechlich fehlende Sender).

Nach Anwendung der Whitelist sank die Zahl der fehlenden Treffer von
"nicht sinnvoll auswertbar" (>1,3 Mio., ueberwiegend VOD) auf 364
konkrete Eintraege in 22 Kategorien - davon liessen sich 266 auf die
zwei letzten echten Bugs (PRIME-Regex, BBCI-Alias) zurueckfuehren. Die
verbleibenden ~90 sind KEIN Bug, sondern einzelne, gerade aktuelle
Live-Event-Kanalnummern (FLO Network Volleyball, NFL-Spielwoche,
DirtVision-Rennen etc.), die schlicht noch nicht als `NAME:`-Zeile in
sender.txt eingetragen sind - normale laufende Pflege bei einer
Playlist mit staendig neuen dynamischen PPV-Kanaelen, kein einmalig
behebbarer Fehler.

---

## BTN+ 1-7 zeigten alten Roh-Event-Text oder "Keine Information" (Sept. 2026)

**Symptom:** In TiviMate zeigten die Kanaele BTN+ 1, 6 und 7 dauerhaft
denselben laengst vergangenen Spieltermin als "Kanalname"/Titel (z. B.
"BTN+ 2 HD (D): B1G+ \| Soccer (W) \| Michigan at Maryland \| Thu 16 Oct
19:00"), BTN+ 2-5 zeigten stattdessen "Keine Information". BTN+ 8 (und
alle hoeheren Nummern) funktionierten korrekt und zeigten das aktuell
laufende Live-Event.

**Ursache:** Bekannter Bug-Typ (derselbe wie bei DIRTVISION 01-03, FA
Player 01-07, Fite - siehe oben): Bei den betroffenen `NAME:`-Zeilen in
`sender.txt` war der komplette Roh-Event-Text eines einzelnen,
vergangenen Live-Events fest in den eigentlich stabilen `NAME:`-Kern
eingebrannt worden (z. B. `NAME:BTN+ 2 HD (D): B1G+ \| Soccer (W) \|
Michigan at Maryland \| Thu 16 Oct 19:00|<logo>`), statt nur
`NAME:BTN+ 2 HD (D)|<logo>` zu speichern. Der `m3u_playlist_abgleichen()`-
Mechanismus vergleicht diesen Kern gegen den aktuellen, sich staendig
aendernden Playlist-Kanalnamen - ein derart ueberladener, veralteter
Kern findet nie mehr einen Treffer, daher altes/kein Programm.

**Fix:** Bei allen betroffenen `NAME:BTN+ 1` bis `NAME:BTN+ 7`-Zeilen
den Kern auf `NAME:BTN+ N HD (D)` gekuerzt (Logo unveraendert
beibehalten), analog zum bereits korrekten `NAME:BTN+ 8 HD (D)`.
**Lehre:** Bei einem neuen "zeigt alten/falschen Event-Text dauerhaft"-
Verdacht bei einer `NAME:`-Zeile immer zuerst pruefen, ob der Kern noch
Doppelpunkt+Event-Details/ein Datum enthaelt statt nur dem stabilen
Basisnamen.

---

## Ueberzaehliges leeres Pipe vor dem Logo (MLB 16, LOI TV, NHL LIVE,
## NIFL, PDC Board, ULSTER GAA, Vidio EPL - Sept. 2026)

**Symptom:** "MLB 16 |" wurde in TiviMate zwar als Kanal zugeordnet/
angezeigt, aber es erschien dauerhaft "Keine Information" - anders als
alle Nachbarkanaele (MLB 01-15, 17 usw.), die normal funktionierten.

**Ursache:** Die betroffene Zeile lautete `NAME:MLB 16 ||<logo>` -
ein zusaetzliches, komplett leeres Pipe-Zeichen VOR dem eigentlichen
Logo-Trenner-Pipe (vermutlich Ueberbleibsel aus einem Kopier-Vorgang
von einer echten Event-Zeile, bei der das Event-Feld danach wieder
geleert, das Pipe-Zeichen davor aber nicht mit entfernt wurde). Beim
Einlesen trennt `generate_epg.py` den Kern IMMER am LETZTEN Pipe der
Zeile - der Abschnitt danach war hier leer, wodurch der gespeicherte
Kern selbst zu einer leeren Zeichenkette wurde (statt "MLB 16" wie bei
allen sauberen Nachbarn). Eine leere Kanal-ID kann nie einen Live-
Playlist-Treffer liefern, daher dauerhaft keine Programminformation
trotz sichtbarer Kanalzuordnung.

**Fix:** Systematische Suche im gesamten `sender.txt` nach demselben
Muster (`NAME:<Text>\s*\|\|<Logo-URL>` - zwei Pipes ohne echten Text
dazwischen) foerderte 39 betroffene Zeilen in mehreren Sendergruppen
zutage (MLB, LOI TV, MLS, NHL LIVE, NIFL, PDC Board, ULSTER GAA, Vidio
EPL) - alle mit demselben leeren Extra-Pipe. Ueberzaehliges Pipe
jeweils entfernt, sodass der Kern wieder exakt dem Muster der sauberen
Nachbarzeilen entspricht (z.B. `NAME:MLB 16|<logo>`).
**Lehre:** Bei einem "zugeordnet aber keine Information"-Verdacht bei
einer `NAME:`-Zeile IMMER auch auf ein leeres, ueberzaehliges Pipe-
Zeichen direkt vor der Logo-URL pruefen (`grep -nE
"^NAME:[^|]*\|\|https?://"` gegen die ganze Datei) - dieser Fehler
betrifft typischerweise nicht nur den gemeldeten Einzelfall, sondern
mehrere Sendergruppen gleichzeitig.

---

## NFL TEAMS| FOX REDSKINS WASHINGTON DC fehlte das NAME:-Praefix (Sept. 2026)

**Symptom:** Nutzer zaehlte in TiviMate 38 "NFL Teams|..."-Kanaele,
`sender.txt` enthielt aber nur 37 passende `NAME:`-Zeilen. Der fehlende
Kanal ("FOX Redskins Washington DC") zeigte einen anderen, generischen
(nicht-dynamischen) Titel ohne "Live"-Markierung, obwohl alle
Nachbarkanaele per Live-Playlist-Abgleich funktionierten.

**Ursache:** Die betroffene Zeile begann NICHT mit `NAME:` (`NFL TEAMS|
FOX REDSKINS WASHINGTON DC||<logo>` statt `NAME:NFL TEAMS| FOX REDSKINS
WASHINGTON DC|<logo>`) - dadurch griff beim Einlesen das normale
`Land|Sender|Beschreibung|Logo`-Format statt der NAME:-Sonderbehandlung,
"NFL TEAMS" wurde faelschlich als Laendercode interpretiert, der Sender
landete nie im `name_pipe_kanal_index` fuer den Live-Abgleich. Direkt
daneben stand zudem ein Duplikat fuer "BALTIMORE MD" (derselbe Bug,
gleiches fehlendes Praefix) - dieses Team existierte bereits an anderer
Stelle korrekt, das Duplikat war ueberfluessig.

**Fix:** `NAME:`-Praefix bei "FOX REDSKINS WASHINGTON DC" ergaenzt
(inkl. Behebung des ueberzaehligen leeren Pipes), das doppelte
"BALTIMORE MD"-Duplikat entfernt. Insgesamt jetzt wieder 38
`NAME:NFL TEAMS|`-Zeilen, exakt wie vom Nutzer in der Playlist gezaehlt.
**Lehre:** Bei "Sender X fehlt/verhaelt sich anders als alle
Nachbarn"-Verdacht innerhalb einer `NAME:`-Sendergruppe IMMER pruefen,
ob die Zeile ueberhaupt mit `NAME:` beginnt (`grep -n "^NFL TEAMS\|"`
OHNE das Praefix findet genau solche Faelle) - ein fehlendes Praefix
sieht auf den ersten Blick wie ein ganz normaler Eintrag aus, wird aber
komplett anders (und falsch) geparst.

---

## KORREKTUR zum "leeres Extra-Pipe"-Fix oben: NHL LIVE| brauchte das
## Pipe tatsaechlich (Sept. 2026)

**Wichtige Einschraenkung zum oben beschriebenen 39-Zeilen-Fix:** Bei
`NAME:NHL LIVE||<logo>` war das doppelte Pipe KEIN Fehler, sondern
Absicht - der Nutzer bestaetigte per TiviMate-Screenshot ("Kanalname:
NHL LIVE|"), dass der ECHTE rohe Playlist-Name dieses Kanals selbst mit
einem Pipe-Zeichen endet (Leerlauf-Zustand ohne angehaengte Event-
Nummer, analog zu "NHL LIVE| 17 -" MIT Nummer). Die pauschale Bereinigung
hatte dieses legitime Pipe faelschlich mit entfernt, wodurch der
gespeicherte Kern ("NHL LIVE" ohne Pipe) nicht mehr exakt mit dem echten
Playlist-Namen ("NHL LIVE|" mit Pipe) uebereinstimmte - der Sender war
dadurch in TiviMates Sender-Suche nicht mehr auffindbar/zuordenbar.
Zurueckgesetzt auf `NAME:NHL LIVE||<logo>`.
**Lehre:** Das generische "leeres Extra-Pipe"-Muster
(`^NAME:[^|]*\|\|https?://`) ist NUR dann ein Bug, wenn sich das auch an
sauberen Nachbar-Zeilen DERSELBEN Sendergruppe zeigen laesst (wie bei
MLB 16 vs. MLB 01-15/17, alle ohne Pipe). Gibt es keine solchen
Nachbarn zum Vergleich (wie bei "NHL LIVE" ohne Nummer), ist ohne
echten Playlist-Zugriff oder Nutzer-Bestaetigung NICHT sicher
entscheidbar, ob das Pipe Teil des echten Kanalnamens ist - im
Zweifel beim Nutzer nachfragen statt blind zu vereinheitlichen.

---

## DIRTVISION 01-08: echter Code-Bug in kern_vorne_und_event_extrahieren()
## (leerer event_vorne wurde immer verworfen, Sept. 2026)

**Symptom:** ALLE Kanaele "DIRTVISION 01" bis "DIRTVISION 08" zeigten
dauerhaft "Keine Information", obwohl sie in TiviMate korrekt
zugeordnet waren - anders als z.B. BTN+ oder MLB 16 war hier keine
fehlerhafte sender.txt-Zeile die Ursache, sondern ein echter Bug im
Extraktions-Code selbst.

**Ursache:** `sender.txt` speichert den Leerlauf-Kern korrekt als
"DIRTVISION 01 :" (mit abschliessendem Doppelpunkt, kein Event-Text
dahinter). Beim Einlesen erkennt `kern_vorne_und_event_extrahieren()`
zwar zuverlaessig den sauberen Kern "DIRTVISION 01" (event_vorne dabei
leer, weil im Leerlauf nichts hinter dem Doppelpunkt steht) - die
aufrufende Stelle uebernahm dieses Ergebnis aber NUR, wenn
`_wirkt_wie_rohtext_muell(event_vorne)` true war. Diese Funktion gibt
bei leerem Text IMMER `False` zurueck (Zeile 1: `if not text: return
False`) - der korrekt erkannte, saubere Kern wurde dadurch verworfen,
der komplette Rohtext MIT Doppelpunkt ("DIRTVISION 01 :") blieb
stattdessen als gespeicherter Kern stehen. Der Live-Playlist-Abgleich
berechnet aus dem tatsaechlich laufenden Event-Namen (z.B. "DIRTVISION
01 : Sharon Speedway 6:30 PM", event_vorne hier NICHT leer, besteht die
Muell-Pruefung problemlos wegen der enthaltenen Uhrzeit) dagegen den
SAUBEREN Kern "DIRTVISION 01" - beide Varianten trafen sich nie.

**Fix:** In `generate_epg.py` an BEIDEN Stellen, die
`kern_vorne_und_event_extrahieren()` auswerten (Vorab-Registrierungs-
Durchlauf UND eigentliche NAME:-Verarbeitung), die Bedingung um `or not
event_vorne` erweitert - ein leerer Rest gilt jetzt genauso als sicher
wie ein als Muell erkannter, ohne die bestehende Schutzwirkung fuer
echte Namensbestandteile (z.B. "TNT SPORTS | Event 1", dort ist der
Rest "Event 1" nicht leer) zu beeintraechtigen. `sender.txt` selbst war
unveraendert korrekt und musste nicht angepasst werden.
**Lehre:** `_wirkt_wie_rohtext_muell("")` gibt IMMER `False` zurueck -
jede Stelle, die deren Ergebnis als alleinige Freigabebedingung fuer
einen erkannten Kern nutzt, verwirft dadurch automatisch jeden Treffer
mit leerem Rest. Bei einem neuen "erkennt Kern korrekt, wendet ihn aber
nicht an"-Verdacht immer pruefen, ob eine solche Muell-Pruefung
faelschlich auch den harmlosen Leerlauf-Fall (leerer Rest) blockiert.

---

## September 2026: Vollstaendiger Playlist-Abgleich (2 fehlende Sender gemeldet) -
## 4 echte Code-/Datenbugs gefunden, NFL-Team-Logos vereinheitlicht

**Ausgangslage:** Nutzer meldete "Playlist gesamt 18957, EPG-Zuordnung
gesamt 18955" (nur 2 Sender fehlen), konnte sie aber nicht selbst in
TiviMate finden (keine Filterfunktion dafuer). Direkter Download der
eigenen Xtream-Codes-Playlist von dieser Session aus schlug fehl (`HTTP
511 Network Authentication Required` von Cloudflare, IP-Sperre des
Anbieters gegen Rechenzentrums-IPs, auch mit VLC-User-Agent) - Nutzer
hat stattdessen selbst die `player_api.php?...&action=get_live_streams`-
Xtream-Codes-API (JSON, viel kleiner als volles M3U) von seinem eigenen
Geraet geladen und hochgeladen.

**MERKE fuer kuenftige Playlist-Abgleiche (Standard-Vorgehen bei
IP-Sperre):** Der direkte M3U-Download von dieser Session aus schlaegt
bei diesem Anbieter zuverlaessig fehl (Rechenzentrums-IP-Sperre) UND
die volle M3U-Datei ist selbst als Upload zu gross (mehrere hundert MB
wegen Stream-URLs/Metadaten aller ~19.000 Kanaele). Loesung, die
zuverlaessig funktioniert: den Nutzer bitten, statt der M3U-Playlist-URL
die Xtream-Codes-JSON-API von seinem EIGENEN Geraet/Browser aus
aufzurufen und die Antwort hochzuladen -
`http://<Host>/player_api.php?username=<User>&password=<Pass>&type=m3u_plus&output=m3u8`
(dieselben Zugangsdaten wie fuer die normale M3U-URL) wird dafuer zu
`http://<Host>/player_api.php?username=<User>&password=<Pass>&action=get_live_streams`
umgebaut - liefert ein kompaktes JSON-Array (`name`, `stream_id`,
`stream_icon`, `category_id`, ...) OHNE Stream-URLs, dadurch nur wenige
MB statt mehrere hundert MB und problemlos hochladbar. Dieses JSON
enthaelt alle noetigen Felder fuer einen vollstaendigen Namens-Abgleich
gegen `sender.txt`/die generierte XML.

**Methodik (wichtig fuer kuenftige Playlist-Abgleiche):** Ein selbst-
geschriebenes Vergleichsskript, das die *_kanal_finden()/Kern-
Extraktions-Funktionen NACHBAUT statt sie zu benutzen, produziert
garantiert Fehlalarme (siehe bereits fruehere Lehre "883+301 fehlende
Sender" oben) - dieses Mal wurde deshalb `kern_und_event_extrahieren()`,
`kern_vorne_und_event_extrahieren()` und `_wirkt_wie_rohtext_muell()`
per `ast.parse()` EXAKT aus der aktuellen `generate_epg.py` extrahiert
und in einem isolierten Namespace ausgefuehrt (kein Neuschreiben der
Logik von Hand) - inkl. exakter Nachbildung des Registrierungs-
Rollbacks (`_kern_und_event_aus_rohname()`/NAME:-Einlesen-Block) UND
des Live-Lookup-Fallbacks (hinten -> vorne). Erst mit dieser 1:1-Kopie
der echten Funktionen sank die Kandidatenliste von anfangs 239
(rechnerisch grob "ID stimmt nicht ueberein") über 29 (nach korrekter
Kern-Extraktion) auf am Ende 0 vermeintlich fehlende Sender.

**4 unabhaengige, jeweils bestaetigte Ursachen gefunden:**

1. **`LOI 01`-`LOI 10` vs. `LOI TV 1`-`LOI TV 10`:** Reine
   `sender.txt`-Datenpflege, kein Code-Bug. Der Anbieter benennt seine
   Kanaele inzwischen durchgaengig mit "TV" (wie bereits bei den
   ebenfalls vorhandenen `LOI TV 11/13/14/15`), die 10 aeltesten
   Eintraege fuehrten aber noch die alte Kurzform ohne "TV" - die
   Kanal-ID stimmte dadurch nicht mehr mit dem echten Playlist-Namen
   ueberein. Fix: alle 10 Zeilen auf `LOI TV N` umbenannt.

2. **`PDC Board 03`/`04`/`05` fehlten komplett** in `sender.txt` (nur
   01, 02, 06, 07, 8 waren eingetragen) - simple Ergaenzung.

3. **Code-Bug in `kern_vorne_und_event_extrahieren()`:** Die Kern-
   vorne-Regex (Kern direkt vor dem ersten Doppelpunkt, z.B. "BTN+ 1 HD
   (D): B1G+ | Field Hockey | ...") erlaubte in ihrer Zeichenklasse kein
   `(`/`)` UND verlangte zwingend, dass der Kern auf eine Zahl endet.
   Kerne mit Klammer-Suffix wie "BTN+ 1 HD (D)", "Fite TV 1 HD (D)" oder
   "US (P+) Italy SerieA 6" (endet zwar auf Zahl, aber "(P+)" mittendrin
   enthaelt Klammern) matchten dadurch NIE, der Fallback nahm
   stattdessen den KOMPLETTEN Text bis zum ersten Pipe als (falschen)
   Kern. Fix: Zeichenklasse um `()` erweitert UND das Schluss-Element
   vor dem Doppelpunkt akzeptiert jetzt alternativ auch ein
   Klammer-Suffix (`(?:0*\d+|\([A-Za-z0-9]+\))` statt nur `0*\d+`) - an
   BEIDEN Fundstellen dieser Regex in `generate_epg.py` (frueher
   Pipe-Zweig und genereller kern-vorne-Zweig ohne Pipe).

4. **Code-Bug in `_wirkt_wie_rohtext_muell()`:** NFL-Sender liefern ihr
   Live-Event inzwischen im Format "1pm Buccaneers at Bengals" (kein
   "vs.", kein Doppelpunkt-Uhrzeit-Format, nur 4 Woerter - die
   bestehenden Muell-Kriterien griffen alle nicht). Der abgetrennte
   Event-Text wurde faelschlich NICHT als Rohtext-Muell erkannt, wodurch
   der Rollback in `_kern_und_event_aus_rohname()`/beim Einlesen den
   korrekt erkannten Kern ("NFL | 03 -") wieder verwarf und durch den
   kompletten Rohtext ersetzte - betraf alle "NFL 01"-"16". Fix: Regex
   um `\d{1,2}\s*(?:am|pm)\b` (Uhrzeit ohne Doppelpunkt) ergaenzt.

5. **Format-Drift bei "Super League Plus":** Bisherige Sonderregex
   verlangte zwingend das Wort "EVENT" nach "SUPER LEAGUE PLUS" - der
   Anbieter liefert inzwischen auch die Kurzform "Super League Plus 03 |
   ..." ganz ohne dieses Wort. Fix: "EVENT" in der Regex optional
   gemacht (`(?:EVENT\s*)?` statt `EVENT\s*`).

**Alle 5 Fixes zusammen** reduzierten die rechnerisch "fehlenden"
Sender beim vollstaendigen 18957-Kanal-Abgleich auf 0. `pytest` (95
Tests) bestaetigte nach jedem einzelnen Fix gruen.

**Zusatzaufgabe (Logos, kein EPG-Matching-Bug):** Auf Nutzerwunsch
wurden zwei sender.txt-Logo-Inkonsistenzen bereinigt, die mit obigen
Matching-Fixes NICHTS zu tun haben:
- `NFL | 01`-`16`: alle 16 Zeilen auf dasselbe NFL-Schild-Logo
  vereinheitlicht (10-14 hatten zuvor eigene, uneinheitliche Logo-
  Dateien).
- `NFL TEAMS| ...` (37 Zeilen, statische lokale CBS/FOX-Team-
  Zuordnungen): 35 davon teilten sich bisher EIN generisches NFL-Logo.
  Fuer 35 Zeilen wurde per Team-Name-Erkennung (z.B. "BUCCANEERS" ->
  Tampa Bay) das jeweils echte Team-Logo von `a.espncdn.com/i/
  teamlogos/nfl/500/<team-code>.png` geladen, auf max. 300px + 256-
  Farben-Palette komprimiert und unter `logos/nfl_teams/<code>.png`
  selbst gehostet (siehe Logo-Regel in CLAUDE.md). 2 Zeilen bewusst
  NICHT vereinzelt, da sie mehrere Teams gleichzeitig im Namen fuehren
  ("CBS BILLS GIANTS JETS NEW YORK NY", "CBS CHIEFS BEARS ST. LOUIS
  MO") - ein einzelnes Team-Logo waere hier falsch/irrefuehrend, bleibt
  beim generischen NFL-Logo. `FOX REDSKINS WASHINGTON DC` hatte bereits
  ein eigenes Commanders-Logo und wurde nicht angefasst.

**Wichtig fuer den ungeloest gebliebenen Ausgangs-Report:** Ein per
TiviMate-Screenshot gemeldetes falsches Team-Logo bei "NFL | 01/02/15"
(zeigte New York Giants statt NFL-Schild) hat sich als NICHT durch
unsere Daten verursacht herausgestellt - sowohl `sender.txt` als auch
die Playlist selbst (`stream_icon` in der Xtream-API) fuehren fuer
diese Kanaele durchgehend dasselbe generische NFL-Logo, unveraendert
seit vor dieser Session. Ursache vermutlich eine alte, manuell in
TiviMate gesetzte oder gecachte Kanal-Logo-Zuordnung (gleiches Muster
wie der bereits bekannte offene Fall bei `HR|SPORT KLUB 1`, siehe
CLAUDE.md) - kein weiterer Code-Fix ohne neue Evidenz.
