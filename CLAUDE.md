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

Findet sich für einen neuen Sender KEINE echte EPG-Quelle, wird er als
normale Zeile `Land|Sender|Beschreibung ᴸⁱᵛᵉ|Logo` eingetragen -
Beschreibungsfeld immer der Sendername in normaler Schrift (Title
Case) mit `ᴸⁱᵛᵉ` am Ende, automatisch und ohne Rückfrage, damit der
Sendername im EPG-Raster erscheint statt eines leeren generischen
Kategorietexts. Nur wenn der Nutzer explizit ein anderes Unicode-Suffix
statt `ᴸⁱᵛᵉ` nennt, wird stattdessen das verwendet.

## Architektur-Überblick

`generate_epg.py` liest `sender.txt` (Format `Land|Sender|Beschreibung|Logo`,
oder `NAME:<exakter Kanalname>|Logo` für Sender, deren echter Playlist-Name
selbst Pipe-Zeichen enthält) und erzeugt daraus `Epg_365_Tage.xml`.
`epg_lib.py` enthält die Kategorie-/Sprach-/Text-Logik. Der
GitHub-Actions-Workflow `update_epg.yml` läuft alle 4h automatisch und bei
manuellem Trigger.

## DYN PPV / Live-Kanalname-Mechanismus

- DYN PPV 1-50 und andere `NAME:`-Sender bekommen ihren Sendungstitel
  automatisch aus dem echten, aktuellen Live-Kanalnamen - ausgelesen aus
  der eigenen IPTV-Playlist des Nutzers (Secret `IPTV_M3U_PROVIDER_URL`,
  optional), statt aus einem geratenen API-Round-Robin.
- `m3u_playlist_abgleichen()` liest die `#EXTINF`-Anzeigenamen der
  M3U-Playlist und matcht sie ueber den Kernnamen gegen die `NAME:`-Sender
  aus `sender.txt`. Ohne gesetztes `IPTV_M3U_PROVIDER_URL`-Secret bleibt
  es bei den generischen Kategorie-Platzhaltertexten (siehe
  `epg_lib.py`).
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
- Status-Marker im rohen Kanalnamen ("NEXT | ...", "End | ...") werden
  automatisch in verständlichen deutschen Text übersetzt ("Es folgt: ...",
  fester Abmoderationstext bei "End").
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

## Pluto TV / tvmovie.de / hoerzu.de (DE, automatisch)

- Echte Programmdaten von Pluto TV Deutschland (`plutotv_epg.py`) gibt
  es AUTOMATISCH als ERSTE automatische Quelle fuer alle DE-Sender
  (kein eigenes sender.txt-Praefix noetig) - Nachfolger des wieder
  entfernten free-epg.de-DE-Blocks (siehe unten), diesmal mit echten,
  sauberen Pluto-TV-Kanalnamen statt generischer Land-Kuerzel.
- Datenquelle ist das offene, loginfreie i.mjh.nz/PlutoTV-XMLTV-Bulk-
  Projekt (generator-info-name "www.matthuisman.nz", bekannt und weit
  verbreitet, z.B. in vielen Kodi-Addons) - EINE komplette XMLTV-Datei
  (`https://i.mjh.nz/PlutoTV/de.xml.gz`) mit allen deutschen Pluto-TV-
  Kanaelen UND allen Sendungen darin, wird nur EINMAL pro Lauf komplett
  geladen und geparst (Modul-weiter Cache), danach werden alle DE-
  Sender lokal dagegen gematcht ohne weitere Netzwerk-Aufrufe.
- Deckt nur ca. 1-2 Tage im Voraus ab (kein mehrtaegiges Datumsraster
  wie Telemach/mts.rs), Tage danach sind ohnehin immer generisch.
- Findet Pluto TV fuer einen Sender nichts, wird automatisch tvmovie.de
  (`tvmovie_epg.py`, HTML-Scraping via `BeautifulSoup`, portiert aus
  dem WebGrab+Plus-Site-Plugin "tvmovie.de") als zweiter Versuch
  probiert, ueber eine im Repo mitgelieferte statische Kanalliste
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
  (`hoerzu_epg.py`) als dritter Versuch probiert, ueber eine im Repo
  mitgelieferte statische Kanalliste (`hoerzu_kanalliste.txt`, ~170
  Eintraege, aus der WebGrab+Plus-Kanalliste fuer hoerzu.de extrahiert,
  Zeilenformat "<slug>|<Name>"). Jede Kanalseite
  (`hoerzu.de/tv-programm/<slug>/`) enthaelt serverseitig gerendert
  einen JSON-LD-Block (schema.org "BroadcastEvent") mit dem kompletten
  Tagesraster - kein HTML-Gefrickel wie bei tvmovie.de, aber wie dort
  auch nur der aktuelle Tag (~24 Stunden), ein Datums-Query-Parameter
  wird von der Website ignoriert.
- Alle drei Quellen degradieren bei jedem Fehler (Netzwerk, kaputtes
  Gzip/XML, kein Kanal-Treffer, unerwartete HTML-Struktur/fehlender
  JSON-LD-Block) graceful auf die normale generische EPG-Generierung,
  kein Absturz moeglich.

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
