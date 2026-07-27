"""
epg_lib.py - Reine Definitionen (Kategorien, Sprachlogik, Hilfsfunktionen)
ohne Seiteneffekte (kein Dateizugriff, kein Netzwerk-Request, kein Schreiben).

Ausgelagert aus generate_epg.py, damit diese Funktionen isoliert per
Unit-Tests geprueft werden koennen (siehe test_generate_epg.py), ohne
dass dabei sender.txt gelesen oder die DYN-API angefragt werden muss.
"""

import re


# ==========================================================
# Automatische Beschreibungen nach Kategorie
# ==========================================================

KATEGORIEN = {

    "REALITY": {
        "label": {"DE": "Reality-TV", "EXYU": "Rijaliti", "EN": "Reality TV"},
        "keywords": [
            "REALITY", "BIG BROTHER", "TEMPTATION",
            "LOVE ISLAND", "PAROVI", "ZADRUGA",
            "FARMA", "SURVIVOR", "BACHELOR", "BACHELORETTE",
            "TOWIE", "GEORDIE SHORE", "KARDASHIAN",
            "HOUSEWIVES", "90 DAY", "MAFS", "MARRIED AT FIRST SIGHT"
        ],
        "DE": [
            "{sender} zeigt Reality-TV, Alltagsdramen und packende Geschichten echter Menschen rund um die Uhr.",
            "{sender} begleitet echte Menschen in emotionalen Reality-Formaten und überraschenden Wendungen.",
            "{sender} bringt Ihnen Reality-Formate mit echten Emotionen, Konflikten und unerwarteten Wendungen aus dem echten Leben."
        ],
        "EXYU": [
            "{sender} prikazuje rijaliti sadržaj, svakodnevne drame i priče stvarnih ljudi tokom cijelog dana.",
            "{sender} donosi najgledanije rijaliti formate sa neočekivanim obrtima i pravim emocijama.",
            "{sender} prati učesnike rijalitija kroz svakodnevne izazove, sukobe i iznenađenja."
        ],
        "EN": [
            "{sender} features reality TV, everyday drama and gripping stories of real people around the clock.",
            "{sender} follows real people through emotional reality formats full of unexpected twists.",
            "{sender} brings you the biggest reality shows, packed with drama, romance and real-life surprises."
        ]
    },

    "NEWS": {
        "label": {"DE": "Nachrichten", "EXYU": "Vijesti", "EN": "News"},
        "keywords": [
            "NEWS", "CNN", "BBC NEWS", "SKY NEWS",
            "AL JAZEERA", "N24", "NTV", "WELT",
            "EURONEWS", "FRANCE 24", "BLOOMBERG",
            "DW", "CNBC", "FOX NEWS", "MSNBC",
            "RTRS", "RTS", "HRT", "BHT", "N1",
            "VIJESTI", "DNEVNIK", "ABC NEWS", "ITV NEWS",
            "GB NEWS", "TALKTV", "TALK TV", "C-SPAN",
            "NEWSMAX", "OANN", "PHOENIX", "TAGESSCHAU",
            "ARD", "ZDF", "CHANNEL 4 NEWS", "SKY NEWS ARABIA",
            "KLAN", "RTV21", "MREZA", "PINK VIJESTI", "K3",
            "NOVA VIJESTI", "PBS NEWSHOUR"
        ],
        "DE": [
            "{sender} informiert rund um die Uhr über aktuelle Nachrichten, Politik, Wirtschaft und Ereignisse aus aller Welt.",
            "{sender} bringt aktuelle Berichterstattung, Hintergründe und Analysen zum Weltgeschehen.",
            "{sender} liefert verlässliche News, Live-Berichte und Einordnungen zu den wichtigsten Themen des Tages."
        ],
        "EXYU": [
            "{sender} donosi najnovije vijesti, politiku, ekonomiju i aktuelna dešavanja iz cijelog svijeta.",
            "{sender} prati aktuelna zbivanja, politiku i društvo uz detaljne analize i izvještaje.",
            "{sender} emituje pouzdane vijesti, izvještaje uživo i komentare o najvažnijim temama dana."
        ],
        "EN": [
            "{sender} delivers breaking news, politics, business updates and major events from around the world.",
            "{sender} provides in-depth coverage, analysis and the latest headlines from across the globe.",
            "{sender} brings reliable news, live reports and expert analysis on the day's biggest stories."
        ]
    },

    "KINDER": {
        "label": {"DE": "Kinder", "EXYU": "Dječiji program", "EN": "Kids"},
        "keywords": [
            "KIDS", "KID", "JR", "JUNIOR",
            "DISNEY", "CARTOON", "NICKELODEON",
            "NICK", "BOOMERANG", "BABY",
            "TOON", "CBEEBIES", "MINIMAX",
            "TINY", "POPCORN", "GULLI",
            "DJECA", "CRTANI", "CBBC", "PBS KIDS",
            "MILKSHAKE", "BABY TV", "BABYTV", "SUPER RTL", "SUPERRTL",
            "KIKA", "PANDA", "DUCK TV", "MINI", "PLANETA DJECA"
        ],
        "DE": [
            "{sender} bietet Zeichentrick, Kinderfilme, Lernprogramme und familienfreundliche Unterhaltung für Groß und Klein.",
            "{sender} zeigt beliebte Kinderserien, Zeichentrick und pädagogisch wertvolle Sendungen den ganzen Tag.",
            "{sender} unterhält die Kleinsten mit bunten Zeichentrickserien, Spielfilmen und altersgerechtem Lernprogramm."
        ],
        "EXYU": [
            "{sender} prikazuje crtane filmove, dječije emisije, edukativni sadržaj i zabavu za cijelu porodicu.",
            "{sender} donosi omiljene crtane serije i edukativni program za najmlađe tokom cijelog dana.",
            "{sender} zabavlja najmlađe gledaoce crtanim serijama, igranim filmovima i edukativnim sadržajem."
        ],
        "EN": [
            "{sender} features cartoons, children's shows, educational programs and family entertainment throughout the day.",
            "{sender} offers popular kids' series, animation and educational content all day long.",
            "{sender} entertains young viewers with colorful cartoons, movies and age-appropriate learning content."
        ]
    },

    "GAMING": {
        "label": {"DE": "Gaming", "EXYU": "Gaming", "EN": "Gaming"},
        "keywords": [
            "GAMING", "ESPORTS", "E-SPORTS", "GAME",
            "IGRE", "TWITCH", "GAMER", "PLAYSTATION",
            "XBOX", "NINTENDO", "GINX"
        ],
        "DE": [
            "{sender} zeigt Gaming-Inhalte, eSports-Turniere und spannende Let's-Plays rund um die Uhr.",
            "{sender} bringt die besten eSports-Events, Gaming-News und Highlights der Szene.",
            "{sender} präsentiert Turniere, Streamer-Highlights und News aus der Welt des Gamings."
        ],
        "EXYU": [
            "{sender} prikazuje gaming sadržaj, eSports turnire i najzanimljivije igre uživo.",
            "{sender} donosi najbolje eSports događaje i vijesti iz svijeta video igara.",
            "{sender} prati najveće gaming turnire i najzanimljivije striming sadržaje."
        ],
        "EN": [
            "{sender} features gaming content, eSports tournaments and exciting live gameplay around the clock.",
            "{sender} brings the best eSports events, gaming news and highlights from the scene.",
            "{sender} showcases top tournaments, streamer highlights and the latest gaming news."
        ]
    },

    "RADIO": {
        "label": {"DE": "Radio", "EXYU": "Radio", "EN": "Radio"},
        "keywords": [
            "RADIO", "HÖRFUNK", "FM", "BBC RADIO", "CLASSIC FM",
            "HEART RADIO", "CAPITAL FM"
        ],
        "DE": [
            "{sender} bietet Radioprogramm mit Musik, Nachrichten und Unterhaltung rund um die Uhr.",
            "{sender} begleitet Sie mit Musik, Talk und aktuellen Themen durch den Tag.",
            "{sender} sendet rund um die Uhr Musik, Wortbeiträge und aktuelle Informationen."
        ],
        "EXYU": [
            "{sender} donosi radijski program sa muzikom, vijestima i zabavom tokom cijelog dana.",
            "{sender} prati vas uz muziku, razgovore i aktuelne teme tokom cijelog dana.",
            "{sender} emituje muziku, informativne priloge i zabavu tokom cijelog dana."
        ],
        "EN": [
            "{sender} offers radio programming with music, news and entertainment around the clock.",
            "{sender} keeps you company with music, talk and current topics throughout the day.",
            "{sender} broadcasts music, talk segments and current affairs around the clock."
        ]
    },

    "SHOPPING": {
        "label": {"DE": "Shopping", "EXYU": "Kupovina", "EN": "Shopping"},
        "keywords": [
            "SHOP", "SHOPPING", "QVC", "HSE", "KUPOVINA",
            "IDEAL WORLD", "BID TV", "JEWELLERY MAKER",
            "STUDIO SHOP", "TELESHOPPING", "TV SHOP"
        ],
        "DE": [
            "{sender} präsentiert Produkte, Angebote und Shopping-Sendungen rund um die Uhr.",
            "{sender} zeigt aktuelle Angebote und Produktvorstellungen im Dauerprogramm.",
            "{sender} bietet Live-Shopping mit wechselnden Produkten und exklusiven Angeboten."
        ],
        "EXYU": [
            "{sender} prikazuje proizvode, ponude i emisije o kupovini tokom cijelog dana.",
            "{sender} donosi aktuelne ponude i predstavljanje proizvoda tokom cijelog dana.",
            "{sender} emituje program uživo posvećen kupovini i predstavljanju proizvoda."
        ],
        "EN": [
            "{sender} showcases products, deals and shopping programs around the clock.",
            "{sender} features the latest offers and product presentations throughout the day.",
            "{sender} offers live shopping with rotating products and exclusive deals."
        ]
    },

    "WISSEN": {
        "label": {"DE": "Wissen & Bildung", "EXYU": "Znanje i edukacija", "EN": "Science & Education"},
        "keywords": [
            "SCIENCE", "EDUCATION", "ZNANJE", "NAUKA",
            "BILDUNG", "LEARN", "DISCOVERY SCIENCE", "OPEN UNIVERSITY"
        ],
        "DE": [
            "{sender} zeigt Wissenssendungen, Bildungsformate und spannende Erkenntnisse aus Wissenschaft und Technik.",
            "{sender} bringt Bildung und Wissenschaft anschaulich näher, mit Experimenten und Erklärungen.",
            "{sender} vermittelt Wissen zu Technik, Forschung und Alltagsphänomenen verständlich und unterhaltsam."
        ],
        "EXYU": [
            "{sender} prikazuje edukativne emisije i zanimljivosti iz svijeta nauke i tehnologije.",
            "{sender} donosi naučne teme i edukativni sadržaj na razumljiv i zanimljiv način.",
            "{sender} objašnjava naučne i tehničke teme na jednostavan i zanimljiv način."
        ],
        "EN": [
            "{sender} features educational programs and fascinating insights from science and technology.",
            "{sender} brings science and learning to life through experiments and clear explanations.",
            "{sender} explains scientific and technical topics in an engaging, accessible way."
        ]
    },

    "NATUR": {
        "label": {"DE": "Natur", "EXYU": "Priroda", "EN": "Nature"},
        "keywords": [
            "NATURE", "WILD", "ANIMAL", "SAFARI",
            "PLANET", "EARTH", "PRIRODA", "ZIVOTINJE", "ANIMAL PLANET"
        ],
        "DE": [
            "{sender} zeigt faszinierende Dokumentationen über Tiere, Natur und die Umwelt.",
            "{sender} nimmt Sie mit in die Tierwelt und zeigt beeindruckende Naturschauspiele.",
            "{sender} präsentiert atemberaubende Bilder aus der Tier- und Pflanzenwelt unseres Planeten."
        ],
        "EXYU": [
            "{sender} prikazuje dokumentarne emisije o životinjama, prirodi i svijetu koji nas okružuje.",
            "{sender} vodi vas u svijet životinja i prikazuje čuda prirode iz cijelog svijeta.",
            "{sender} donosi zadivljujuće slike biljnog i životinjskog svijeta našeg planeta."
        ],
        "EN": [
            "{sender} features fascinating documentaries about wildlife, nature and the environment.",
            "{sender} takes you into the animal kingdom and showcases breathtaking natural wonders.",
            "{sender} presents stunning footage of the plant and animal life of our planet."
        ]
    },

    "DOKU": {
        "label": {"DE": "Dokumentation", "EXYU": "Dokumentarni program", "EN": "Documentary"},
        "keywords": [
            "DISCOVERY", "NAT GEO", "NATIONAL",
            "HISTORY", "DOC", "DOKUMENTARNI", "SMITHSONIAN",
            "TRUE CRIME", "INVESTIGATION", "PBS", "ARTE",
            "YESTERDAY", "CURIOSITY", "VIASAT EXPLORE", "ID",
            "INVESTIGATION DISCOVERY"
        ],
        "DE": [
            "{sender} zeigt Dokumentationen über Natur, Wissenschaft, Geschichte und spannende Entdeckungen.",
            "{sender} präsentiert packende Dokus zu Geschichte, Kultur und aktuellen Themen.",
            "{sender} beleuchtet reale Ereignisse, historische Hintergründe und wahre Kriminalfälle."
        ],
        "EXYU": [
            "{sender} prikazuje dokumentarne emisije, prirodu, nauku, istoriju i zanimljivosti iz cijelog svijeta.",
            "{sender} donosi zanimljive dokumentarne priče o istoriji, kulturi i savremenim temama.",
            "{sender} istražuje stvarne događaje, istorijske pozadine i prave kriminalističke slučajeve."
        ],
        "EN": [
            "{sender} features documentaries about nature, science, history and fascinating discoveries.",
            "{sender} presents gripping documentaries covering history, culture and current affairs.",
            "{sender} explores real events, historical backgrounds and true crime cases."
        ]
    },

    "AUTO": {
        "label": {"DE": "Auto & Motor", "EXYU": "Auto i motor", "EN": "Auto & Motor"},
        "keywords": [
            "AUTO", "MOTOR", "MOTORVISION", "AUTOMOBIL", "GARAZA",
            "TOP GEAR", "GRAND TOUR", "MOTORTREND", "VELOCITY",
            "AUTO MOTO", "DRIVE"
        ],
        "DE": [
            "{sender} zeigt alles rund um Autos, Motorsport und Fahrzeugtechnik.",
            "{sender} präsentiert Fahrzeugtests, Motorsport-Highlights und Neuheiten aus der Autowelt.",
            "{sender} bringt Berichte über Klassiker, Tuning, Motorsport und aktuelle Modelle."
        ],
        "EXYU": [
            "{sender} prikazuje sve o automobilima, motosportu i tehnici vozila.",
            "{sender} donosi testove vozila, motosport i novosti iz svijeta automobila.",
            "{sender} prati priče o klasičnim automobilima, tuningu i motosportu."
        ],
        "EN": [
            "{sender} covers everything about cars, motorsports and vehicle technology.",
            "{sender} features vehicle reviews, motorsport highlights and the latest automotive news.",
            "{sender} covers classic cars, tuning culture, motorsport and the newest models."
        ]
    },

    "REISEN": {
        "label": {"DE": "Reisen", "EXYU": "Putovanja", "EN": "Travel"},
        "keywords": [
            "TRAVEL", "TOUR", "TOURISM", "VACATION",
            "EXPLORE", "PUTOVANJA", "TRAVEL CHANNEL", "GEO TRAVEL"
        ],
        "DE": [
            "{sender} nimmt Sie mit auf spannende Reisen zu faszinierenden Orten, Kulturen und Urlaubszielen weltweit.",
            "{sender} zeigt Reiseziele, fremde Kulturen und Urlaubsinspirationen aus aller Welt.",
            "{sender} entführt Sie zu fernen Orten und stellt Kulturen, Städte und Landschaften vor."
        ],
        "EXYU": [
            "{sender} vodi vas na zanimljiva putovanja kroz različite zemlje, kulture i turističke destinacije širom svijeta.",
            "{sender} prikazuje putničke destinacije, kulture i inspiracije za odmor iz cijelog svijeta.",
            "{sender} odvodi vas na daleke destinacije i predstavlja kulture, gradove i predjele."
        ],
        "EN": [
            "{sender} takes you on exciting journeys to amazing destinations, cultures and travel experiences worldwide.",
            "{sender} showcases travel destinations, cultures and vacation inspiration from around the globe.",
            "{sender} whisks you away to far-flung places, showcasing cultures, cities and landscapes."
        ]
    },

    "KOCHEN": {
        "label": {"DE": "Kochen", "EXYU": "Kuhinja", "EN": "Food & Cooking"},
        "keywords": [
            "FOOD", "KITCHEN", "COOK", "CUISINE",
            "CHEF", "GUSTO", "KUHINJA", "RECEPTI",
            "MASTERCHEF", "BAKE OFF", "FOOD NETWORK",
            "TASTE", "GORDON RAMSAY", "COOKING CHANNEL"
        ],
        "DE": [
            "{sender} präsentiert Kochsendungen, Rezepte, kulinarische Inspirationen und Spezialitäten aus aller Welt.",
            "{sender} zeigt Kochshows, Zubereitungstipps und kulinarische Highlights rund um den Globus.",
            "{sender} bringt Kochwettbewerbe, Rezeptideen und Geschichten rund um gutes Essen."
        ],
        "EXYU": [
            "{sender} prikazuje kulinarske emisije, recepte, savjete za kuhanje i specijalitete iz cijelog svijeta.",
            "{sender} donosi kulinarske emisije i recepte iz raznih kuhinja svijeta.",
            "{sender} prati kulinarska takmičenja, ideje za recepte i priče o dobroj hrani."
        ],
        "EN": [
            "{sender} offers cooking shows, recipes, culinary tips and delicious dishes from around the world.",
            "{sender} features cooking shows and recipe inspiration from cuisines across the globe.",
            "{sender} brings cooking competitions, recipe ideas and stories about great food."
        ]
    },

    "MUSIK": {
        "label": {"DE": "Musik", "EXYU": "Muzika", "EN": "Music"},
        "keywords": [
            "MUSIC", "MUSIK", "MTV", "VH1",
            "DELUXE", "CLUB", "HITS", "MEZZO",
            "TRACE", "4MUSIC", "CMC", "DM SAT",
            "FOLK", "BALKAN MUSIC", "NRJ", "KISS",
            "DANCE", "ROCK", "POP", "JAZZ", "MUZIKA",
            "HEART", "CAPITAL", "SMOOTH", "MAGIC RADIO",
            "GRAND", "HITRADIO", "ENERGY", "SCHLAGER",
            "NARODNA", "TURBO FOLK", "PARTY"
        ],
        "DE": [
            "{sender} präsentiert Musikvideos, Live-Konzerte, Charts und die größten Hits aus verschiedenen Musikrichtungen.",
            "{sender} spielt die angesagtesten Hits, Konzerte und Musikvideos rund um die Uhr.",
            "{sender} bringt Charts, Konzertmitschnitte und musikalische Neuentdeckungen aus aller Welt."
        ],
        "EXYU": [
            "{sender} prikazuje muzičke spotove, koncerte uživo, top liste i najveće hitove iz različitih žanrova.",
            "{sender} emituje najveće hitove, koncerte i muzičke spotove tokom cijelog dana.",
            "{sender} donosi top liste, snimke koncerata i nove muzičke izvođače iz cijelog svijeta."
        ],
        "EN": [
            "{sender} features music videos, live concerts, chart hits and the best songs from a variety of genres.",
            "{sender} plays the hottest hits, concerts and music videos around the clock.",
            "{sender} brings you the charts, concert footage and exciting new artists from around the world."
        ]
    },

    "COMEDY": {
        "label": {"DE": "Comedy", "EXYU": "Komedija", "EN": "Comedy"},
        "keywords": [
            "COMEDY", "HUMOR", "FUNNY", "LAUGH", "KOMEDIJA", "DAVE",
            "COMEDY CENTRAL", "PARANDOVCI", "SMIJEH"
        ],
        "DE": [
            "{sender} bietet Comedy, Humor, Sitcoms und beste Unterhaltung für gute Laune den ganzen Tag.",
            "{sender} sorgt mit Sitcoms und Comedy-Formaten für gute Laune rund um die Uhr.",
            "{sender} präsentiert Stand-up, Sketche und Comedy-Serien für jede Menge gute Laune."
        ],
        "EXYU": [
            "{sender} prikazuje humoristične emisije, sitkome i zabavni sadržaj koji će vas nasmijati tokom cijelog dana.",
            "{sender} donosi komedije i sitkome za dobro raspoloženje tokom cijelog dana.",
            "{sender} emituje stand-up nastupe, skečeve i komedije za odlično raspoloženje."
        ],
        "EN": [
            "{sender} features comedy shows, sitcoms and entertaining programs guaranteed to make you laugh.",
            "{sender} brings sitcoms and comedy formats to keep you entertained around the clock.",
            "{sender} presents stand-up, sketches and comedy series guaranteed to keep you laughing."
        ]
    },

    "RELIGION": {
        "label": {"DE": "Religion", "EXYU": "Vjera", "EN": "Religion"},
        "keywords": [
            "EWTN", "KTV", "GOD", "ISLAM",
            "QURAN", "BIBLE", "CHURCH", "SVET", "VJERA",
            "HAYAT PLUS", "TRINITY", "GOOD TV", "DAAI"
        ],
        "DE": [
            "{sender} sendet religiöse Inhalte, Gottesdienste, Dokumentationen und inspirierende Programme.",
            "{sender} bringt geistliche Sendungen, Gottesdienste und inspirierende Beiträge.",
            "{sender} zeigt spirituelle Formate, Predigten und Programme zum Nachdenken und Innehalten."
        ],
        "EXYU": [
            "{sender} emituje vjerske emisije, bogosluženja, dokumentarne sadržaje i inspirativne programe.",
            "{sender} donosi duhovni sadržaj, bogosluženja i inspirativne emisije.",
            "{sender} prikazuje duhovne formate, propovijedi i programe za razmišljanje."
        ],
        "EN": [
            "{sender} broadcasts religious services, documentaries and inspirational programming.",
            "{sender} features spiritual content, church services and inspiring programs.",
            "{sender} presents spiritual formats, sermons and programming for quiet reflection."
        ]
    },

    "SPORT": {
        "label": {"DE": "Sport", "EXYU": "Sport", "EN": "Sport"},
        "keywords": [
            "SPORT", "SPORTS", "ESPN", "EUROSPORT",
            "DAZN", "SKY SPORT", "ARENA", "NBA",
            "NFL", "NHL", "MLB", "TENNIS",
            "GOLF", "RACING", "FORMULA", "F1",
            "MOTOGP", "BOX", "FIGHT", "UFC",
            "BT SPORT", "TNT SPORTS", "PREMIER LEAGUE",
            "SOCCER", "RUGBY", "CRICKET", "FLO SPORTS",
            "FLO RACING", "FANDUEL SPORTS", "BEIN SPORTS",
            "SPORT KLUB", "ARENA SPORT", "SPORTKLUB", "NASCAR",
            "PGA TOUR", "SKY SPORTS", "VIAPLAY SPORT", "DYN PPV",
            "WWE", "OLYMPIC", "OLIMPIJSKI"
        ],
        "DE": [
            "{sender} bietet Live-Sport, Fußball, Motorsport, Tennis und viele weitere Sportereignisse aus aller Welt.",
            "{sender} überträgt Live-Events, Highlights und die größten Sportmomente weltweit.",
            "{sender} zeigt Live-Übertragungen, Analysen und Highlights aus Fußball, Motorsport und weiteren Disziplinen."
        ],
        "EXYU": [
            "{sender} donosi sportske prijenose uživo, fudbal, tenis, motosport i druge vrhunske sportske događaje.",
            "{sender} prenosi uživo najveće sportske događaje i highlighte iz cijelog svijeta.",
            "{sender} prikazuje prijenose uživo, analize i najbolje trenutke iz fudbala, motosporta i drugih sportova."
        ],
        "EN": [
            "{sender} features live sports including football, tennis, motorsports and many major sporting events worldwide.",
            "{sender} broadcasts live events, highlights and the biggest sporting moments from around the world.",
            "{sender} delivers live coverage, analysis and highlights from football, motorsport and more."
        ]
    },

    "SERIEN": {
        "label": {"DE": "Serien", "EXYU": "Serije", "EN": "Series"},
        "keywords": [
            "SERIES", "SERIJA", "SERIJE", "DRAMA", "SOAP",
            "SITCOM", "EPIX", "BRAVO", "USA NETWORK"
        ],
        "DE": [
            "{sender} zeigt beliebte Serien, Dramen und fesselnde Geschichten in fortlaufenden Episoden.",
            "{sender} präsentiert Serienhits verschiedener Genres, von Drama bis Krimi.",
            "{sender} zeigt Episoden voller Spannung, Emotionen und vielschichtiger Charaktere."
        ],
        "EXYU": [
            "{sender} prikazuje popularne serije, drame i uzbudljive priče u nastavcima.",
            "{sender} donosi serijske hitove raznih žanrova, od drame do krimića.",
            "{sender} prikazuje epizode pune napetosti, emocija i slojevitih likova."
        ],
        "EN": [
            "{sender} features popular series, dramas and gripping stories told across ongoing episodes.",
            "{sender} presents hit series across genres, from drama to crime.",
            "{sender} delivers episodes full of suspense, emotion and richly developed characters."
        ]
    },

    "FILM": {
        "label": {"DE": "Filme", "EXYU": "Filmovi", "EN": "Movies"},
        "keywords": [
            "CINEMA", "FILM", "MOVIE", "HOLLYWOOD",
            "HBO", "CINEMAX", "SKY CINEMA",
            "WARNER", "PARAMOUNT", "UNIVERSAL",
            "SONY", "STAR", "AXN", "AMC",
            "SYFY", "TNT", "THRILLER", "FILMOVI",
            "FILM4", "ITV MOVIES", "MGM", "EPIC DRAMA",
            "PINK FILM", "KLASIK FILM", "CINESTAR", "CINE"
        ],
        "DE": [
            "{sender} zeigt Spielfilme, Blockbuster, Filmklassiker und spannende Serien rund um die Uhr.",
            "{sender} präsentiert die größten Kinohits, Klassiker und Blockbuster aus Hollywood.",
            "{sender} zeigt ein rund um die Uhr wechselndes Programm aus Spielfilmen aller Genres."
        ],
        "EXYU": [
            "{sender} prikazuje filmske hitove, klasike i popularne serije tokom cijelog dana.",
            "{sender} donosi najveće filmske hitove i klasike iz Hollywooda tokom cijelog dana.",
            "{sender} emituje program igranih filmova svih žanrova tokom cijelog dana."
        ],
        "EN": [
            "{sender} features blockbuster movies, classic films and popular TV series throughout the day.",
            "{sender} presents the biggest Hollywood blockbusters and film classics around the clock.",
            "{sender} runs a rotating lineup of feature films spanning every genre, around the clock."
        ]
    },

    "WETTER": {
        "label": {"DE": "Wetter", "EXYU": "Vrijeme", "EN": "Weather"},
        "keywords": [
            "WEATHER", "WETTER", "VRIJEME", "STORM", "METEO"
        ],
        "DE": [
            "{sender} informiert rund um die Uhr über Wetterlage, Vorhersagen und Wetterphänomene weltweit.",
            "{sender} liefert aktuelle Vorhersagen, Warnungen und Hintergründe zum Wettergeschehen."
        ],
        "EXYU": [
            "{sender} informiše o vremenskoj prognozi, uslovima i vremenskim fenomenima širom svijeta.",
            "{sender} donosi aktuelne prognoze, upozorenja i pozadinu vremenskih dešavanja."
        ],
        "EN": [
            "{sender} provides around-the-clock forecasts, weather conditions and phenomena worldwide.",
            "{sender} delivers up-to-date forecasts, warnings and background on weather events."
        ]
    },

    "JAGD_FISCHEREI": {
        "label": {"DE": "Jagd & Angeln", "EXYU": "Lov i ribolov", "EN": "Hunting & Fishing"},
        "keywords": [
            "HUNT", "FISHING", "OUTDOOR", "ANGELN", "JAGD", "LOV", "RIBOLOV"
        ],
        "DE": [
            "{sender} zeigt Sendungen über Jagd, Angeln und das Leben in der freien Natur.",
            "{sender} präsentiert Outdoor-Abenteuer, Angeltouren und Jagdgeschichten aus aller Welt."
        ],
        "EXYU": [
            "{sender} prikazuje sadržaj o lovu, ribolovu i životu u prirodi.",
            "{sender} donosi avanture na otvorenom, izlete na pecanje i lovačke priče."
        ],
        "EN": [
            "{sender} features programs about hunting, fishing and life in the great outdoors.",
            "{sender} presents outdoor adventures, fishing trips and hunting stories from around the world."
        ]
    },

    "MILITAER": {
        "label": {"DE": "Militär & Krieg", "EXYU": "Vojska i rat", "EN": "Military & War"},
        "keywords": [
            "MILITARY", "WAR", "ARMY", "VOJSKA", "RAT", "WEHRMACHT"
        ],
        "DE": [
            "{sender} zeigt Dokumentationen über Militärgeschichte, Kriege und Streitkräfte weltweit.",
            "{sender} präsentiert historische und aktuelle Berichte über Armeen und Konflikte."
        ],
        "EXYU": [
            "{sender} prikazuje dokumentarne emisije o vojnoj istoriji, ratovima i oružanim snagama.",
            "{sender} donosi istorijske i aktuelne priče o vojskama i sukobima."
        ],
        "EN": [
            "{sender} features documentaries about military history, wars and armed forces worldwide.",
            "{sender} presents historical and current reports on armies and conflicts."
        ]
    },

    "FAMILIE": {
        "label": {"DE": "Familie", "EXYU": "Porodica", "EN": "Family"},
        "keywords": [
            "FAMILY", "FAMILIE", "PORODICA", "HALLMARK"
        ],
        "DE": [
            "{sender} zeigt familienfreundliche Filme, Serien und Sendungen für Jung und Alt.",
            "{sender} bietet warmherzige Geschichten und Unterhaltung für die ganze Familie."
        ],
        "EXYU": [
            "{sender} prikazuje filmove i serije prilagođene cijeloj porodici.",
            "{sender} nudi tople priče i zabavu za mlade i starije članove porodice."
        ],
        "EN": [
            "{sender} features family-friendly movies, series and shows for all ages.",
            "{sender} offers heartwarming stories and entertainment for the whole family."
        ]
    },

    "ANIME": {
        "label": {"DE": "Anime", "EXYU": "Anime", "EN": "Anime"},
        "keywords": [
            "ANIME", "TOONAMI", "CRUNCHYROLL", "MANGA"
        ],
        "DE": [
            "{sender} zeigt Anime-Serien, japanische Animation und beliebte Manga-Verfilmungen.",
            "{sender} präsentiert Anime-Klassiker und aktuelle Serien aus Japan für Fans jeden Alters."
        ],
        "EXYU": [
            "{sender} prikazuje anime serije, japansku animaciju i popularne ekranizacije mangi.",
            "{sender} donosi anime klasike i aktuelne serije iz Japana za sve generacije."
        ],
        "EN": [
            "{sender} features anime series, Japanese animation and popular manga adaptations.",
            "{sender} presents classic and current anime series from Japan for fans of all ages."
        ]
    },

    "KRIMI": {
        "label": {"DE": "Krimi", "EXYU": "Krimi", "EN": "Crime"},
        "keywords": [
            "CRIME", "DETECTIVE", "MURDER", "CSI", "LAW & ORDER", "KRIMI"
        ],
        "DE": [
            "{sender} zeigt Krimiserien, Ermittlerteams und packende Fälle aus der Welt des Verbrechens.",
            "{sender} präsentiert Kriminalfälle, Ermittlungen und Gerichtsdramen voller Spannung."
        ],
        "EXYU": [
            "{sender} prikazuje kriminalističke serije, timove istražitelja i uzbudljive slučajeve.",
            "{sender} donosi kriminalističke priče, istrage i sudske drame pune napetosti."
        ],
        "EN": [
            "{sender} features crime series, detective teams and gripping cases from the world of crime.",
            "{sender} presents criminal cases, investigations and courtroom dramas full of suspense."
        ]
    },

    "GESUNDHEIT": {
        "label": {"DE": "Gesundheit & Fitness", "EXYU": "Zdravlje i fitnes", "EN": "Health & Fitness"},
        "keywords": [
            "FITNESS", "HEALTH", "WELLNESS", "YOGA", "GYM", "ZDRAVLJE"
        ],
        "DE": [
            "{sender} zeigt Sendungen rund um Gesundheit, Fitness, Ernährung und ein aktives Leben.",
            "{sender} bringt Trainingsprogramme, Wellness-Tipps und Wissenswertes für Körper und Geist."
        ],
        "EXYU": [
            "{sender} prikazuje sadržaj o zdravlju, fitnesu, ishrani i aktivnom načinu života.",
            "{sender} donosi programe vježbanja, savjete o wellnessu i korisne informacije za tijelo i um."
        ],
        "EN": [
            "{sender} features programs about health, fitness, nutrition and active living.",
            "{sender} brings workout programs, wellness tips and insights for body and mind."
        ]
    },

    "TECH": {
        "label": {"DE": "Technik", "EXYU": "Tehnologija", "EN": "Technology"},
        "keywords": [
            "TECH", "TECHNOLOGY", "GADGET", "TEHNOLOGIJA"
        ],
        "DE": [
            "{sender} zeigt Sendungen über neue Technologien, Gadgets und digitale Innovationen.",
            "{sender} stellt aktuelle Geräte, Software-Neuheiten und Zukunftstechnologien vor."
        ],
        "EXYU": [
            "{sender} prikazuje sadržaj o novim tehnologijama, uređajima i digitalnim inovacijama.",
            "{sender} predstavlja aktuelne uređaje, softverske novosti i tehnologije budućnosti."
        ],
        "EN": [
            "{sender} features programs about new technology, gadgets and digital innovation.",
            "{sender} showcases the latest devices, software news and future technologies."
        ]
    },

    "HORROR": {
        "label": {"DE": "Horror & Thriller", "EXYU": "Horor i triler", "EN": "Horror & Thriller"},
        "keywords": [
            "HORROR", "SCARY", "SCREAM", "CHILLER", "TERROR", "SLASHER"
        ],
        "DE": [
            "{sender} zeigt Horrorfilme, Thriller und gruselige Geschichten für Nervenkitzel rund um die Uhr.",
            "{sender} präsentiert schaurige Klassiker und moderne Horrorfilme für starke Nerven."
        ],
        "EXYU": [
            "{sender} prikazuje horor filmove, trilere i jezive priče za ljubitelje adrenalina.",
            "{sender} donosi klasike horora i moderne strašne filmove tokom cijelog dana."
        ],
        "EN": [
            "{sender} features horror movies, thrillers and spine-chilling stories around the clock.",
            "{sender} presents classic and modern horror films for viewers who like a good scare."
        ]
    },

    "TALKSHOW": {
        "label": {"DE": "Talkshow", "EXYU": "Tok šou", "EN": "Talk Show"},
        "keywords": [
            "TALK SHOW", "TALKSHOW", "LATE NIGHT", "TONIGHT SHOW", "THIS MORNING"
        ],
        "DE": [
            "{sender} zeigt Talkshows mit prominenten Gästen, Diskussionen und unterhaltsamen Gesprächen.",
            "{sender} bringt Interviews, Studiogäste und aktuelle Gesprächsthemen auf die Bühne."
        ],
        "EXYU": [
            "{sender} prikazuje tok šou emisije sa poznatim gostima, diskusijama i zanimljivim razgovorima.",
            "{sender} donosi intervjue, goste u studiju i aktuelne teme za razgovor."
        ],
        "EN": [
            "{sender} features talk shows with celebrity guests, discussions and entertaining conversations.",
            "{sender} brings interviews, studio guests and topical conversation to the screen."
        ]
    },

    "WIRTSCHAFT": {
        "label": {"DE": "Wirtschaft & Finanzen", "EXYU": "Biznis i finansije", "EN": "Business & Finance"},
        "keywords": [
            "BUSINESS", "FINANCE", "MONEY", "MARKETS", "WIRTSCHAFT", "BIZNIS"
        ],
        "DE": [
            "{sender} informiert über Wirtschaft, Finanzmärkte, Börsennews und aktuelle Unternehmensthemen.",
            "{sender} liefert Analysen und Hintergründe zu Märkten, Unternehmen und Finanzthemen."
        ],
        "EXYU": [
            "{sender} informiše o biznisu, finansijskim tržištima i aktuelnim ekonomskim temama.",
            "{sender} donosi analize i pozadinu tržišnih kretanja, kompanija i finansija."
        ],
        "EN": [
            "{sender} covers business, financial markets, stock news and current corporate affairs.",
            "{sender} delivers analysis and background on markets, companies and finance."
        ]
    },

    "LIFESTYLE": {
        "label": {"DE": "Lifestyle", "EXYU": "Lifestyle", "EN": "Lifestyle"},
        "keywords": [
            "LIFESTYLE", "STYLE", "FASHION", "HOME",
            "LIVING", "HGTV", "TLC", "BEAUTY",
            "DESIGN", "WOMAN", "LADY", "W NETWORK",
            "OPRAH", "OWN", "LIFETIME", "DECOR", "STIL"
        ],
        "DE": [
            "{sender} zeigt Sendungen rund um Wohnen, Mode, Lifestyle, Schönheit und inspirierende Ideen für den Alltag.",
            "{sender} präsentiert Mode-, Wohn- und Beauty-Themen für ein inspirierendes Lebensgefühl.",
            "{sender} liefert Ideen und Inspiration für Wohnen, Mode und ein bewusstes Lebensgefühl."
        ],
        "EXYU": [
            "{sender} donosi emisije o modi, uređenju doma, ljepoti, životnom stilu i korisnim savjetima za svakodnevni život.",
            "{sender} prikazuje modu, uređenje doma i teme o ljepoti za inspirativan svakodnevni život.",
            "{sender} nudi ideje i inspiraciju za uređenje doma, modu i kvalitetniji svakodnevni život."
        ],
        "EN": [
            "{sender} features programs about fashion, home improvement, beauty, lifestyle and everyday inspiration.",
            "{sender} presents fashion, home and beauty content for an inspiring everyday lifestyle.",
            "{sender} offers ideas and inspiration for home, fashion and a more mindful everyday life."
        ]
    },

    "REGIONAL": {
        "label": {"DE": "Regional", "EXYU": "Regionalni program", "EN": "Regional"},
        "keywords": [
            "REGIONAL", "LOKAL", "LOKALNA"
        ],
        "DE": [
            "{sender} bietet regionale Berichterstattung, lokale Themen und Programme aus Ihrer Umgebung.",
            "{sender} zeigt lokale Nachrichten, Veranstaltungen und Geschichten aus der Region.",
            "{sender} berichtet aus erster Hand über Themen, Menschen und Ereignisse vor Ort."
        ],
        "EXYU": [
            "{sender} donosi regionalne vijesti, lokalne teme i program iz vaše okoline.",
            "{sender} prikazuje lokalna dešavanja, priče i teme iz regije.",
            "{sender} izvještava iz prve ruke o temama, ljudima i dešavanjima u vašem kraju."
        ],
        "EN": [
            "{sender} offers regional coverage, local topics and programming from your area.",
            "{sender} features local news, events and stories from the region.",
            "{sender} reports first-hand on the topics, people and events shaping your local area."
        ]
    },

    "UNTERHALTUNG": {
        "label": {"DE": "Unterhaltung", "EXYU": "Zabava", "EN": "Entertainment"},
        "keywords": [
            "RTL", "VOX", "SAT", "PRO7", "PRO SIEBEN",
            "KABEL", "NOVA", "PINK", "HAPPY",
            "HAYAT", "OBN", "FACE", "ATV",
            "KANAL", "TV", "FOX", "ABC",
            "CBS", "NBC", "SHOW", "PLUS",
            "PRIME", "ZABAVA", "ITV", "CHANNEL 4",
            "CHANNEL4", "CHANNEL 5", "CHANNEL5", "E4", "MORE4",
            "DAVE", "ITV2", "ITV3", "ITV4", "5STAR", "5 STAR",
            "DIREKT", "MREZA PLUS", "K1", "K3", "MTEL"
        ],
        "DE": [
            "{sender} bietet ein abwechslungsreiches Programm mit Unterhaltung, Shows, Serien und beliebten TV-Formaten für die ganze Familie.",
            "{sender} präsentiert vielfältige Unterhaltung mit Shows und beliebten Formaten für die ganze Familie.",
            "{sender} bietet Shows, Quizformate und Unterhaltung für die ganze Familie, den ganzen Tag über."
        ],
        "EXYU": [
            "{sender} donosi raznovrstan program sa zabavnim emisijama, serijama i popularnim TV formatima za cijelu porodicu.",
            "{sender} prikazuje raznovrstan zabavni program i popularne TV formate za cijelu porodicu.",
            "{sender} nudi kviz emisije, šou programe i zabavu za cijelu porodicu tokom cijelog dana."
        ],
        "EN": [
            "{sender} features a wide range of entertainment including TV shows, series and popular formats for the whole family.",
            "{sender} presents varied entertainment with shows and popular formats for the whole family.",
            "{sender} offers game shows, quiz formats and entertainment for the whole family, all day long."
        ]
    }
}

# Feste Prüfreihenfolge: spezifischere Kategorien zuerst, damit
# generische Keywords (z.B. "TV", "SHOW" in UNTERHALTUNG) nicht
# fälschlich vor eindeutigeren Treffern (z.B. "SCIENCE", "REALITY")
# gewinnen. UNTERHALTUNG steht bewusst ganz am Ende als breitester
# Auffang-Kategorie vor dem generischen Fallback-Text.
KATEGORIE_PRIORITAET = [
    "REALITY", "NEWS", "WETTER", "KINDER", "ANIME", "FAMILIE", "GAMING", "RADIO", "SHOPPING",
    "WISSEN", "NATUR", "JAGD_FISCHEREI", "DOKU", "MILITAER", "AUTO", "REISEN", "KOCHEN",
    "MUSIK", "COMEDY", "RELIGION", "HORROR", "KRIMI", "TALKSHOW",
    "WIRTSCHAFT", "GESUNDHEIT", "TECH",
    "SPORT", "SERIEN", "FILM",
    "LIFESTYLE", "REGIONAL", "UNTERHALTUNG"
]

DE_STANDARD = [
    "Willkommen beim Programm von {sender}. Freuen Sie sich auf abwechslungsreiche Unterhaltung während des ganzen Tages.",
    "{sender} begleitet Sie mit einem vielseitigen Programm durch den Tag.",
    "{sender} sendet ein abwechslungsreiches Programm für die ganze Familie."
]

EXYU_STANDARD = [
    "Dobro došli u program {sender}. Očekuje vas raznovrstan sadržaj tokom cijelog dana.",
    "{sender} vas prati sa raznovrsnim programom tokom cijelog dana.",
    "{sender} emituje raznovrstan program za cijelu porodicu."
]

EN_STANDARD = [
    "Welcome to {sender}. Enjoy a wide variety of entertainment throughout the day.",
    "{sender} keeps you entertained with a varied program throughout the day.",
    "{sender} broadcasts a varied program for the whole family."
]


# ==========================================================
# Automatische Beschreibung
# ==========================================================

EXYU_LAENDER = [
    "BA", "RS", "HR", "ME", "CG", "MNE", "MNG", "MO", "MK", "SI",
    "EXYU", "BS", "SRB", "SRBIJA", "HRVATSKA", "BIH", "CRNA GORA",
    "KOSOVO", "KS", "SEVERNA MAKEDONIJA", "SLOVENIJA", "MAKEDONIJA",
    "SANDZAK", "SANDŽAK"
]

# UK und US laufen beide über die Sprache "EN", werden hier aber
# bewusst als eigene Listen gefuehrt (statt einer gemeinsamen), damit
# sie unabhaengig voneinander erweitert werden koennen, falls spaeter
# doch einmal britisches/amerikanisches Englisch unterschieden werden
# soll.
UK_LAENDER = [
    "UK", "GB", "ENGLAND", "SCOTLAND", "WALES", "BRITAIN", "UNITED KINGDOM",
    "NORTHERN IRELAND", "N.IRELAND"
]

US_LAENDER = [
    "US", "USA", "UNITED STATES", "AMERICA"
]

EN_LAENDER = UK_LAENDER + US_LAENDER + [
    "AU", "AUS", "AUSTRALIA", "CA", "CAN", "CANADA", "NZ", "IRELAND", "IE",
    "TUBI", "CITY", "GO", "PRIME", "JOYN", "WOW", "PLUTO", "ROKU"
]


def standard_beschreibung(land, sender):
    """
    Ermittelt Sprache + passende Kategorie für einen Sender und gibt
    ein Tupel (beschreibungstext, kategorie_key) zurueck. kategorie_key
    ist None, wenn keine Kategorie erkannt wurde (generischer Fallback-
    Text) - in dem Fall wird spaeter kein <category>-Tag geschrieben.

    Die Auswahl zwischen den mehreren Text-Varianten pro Kategorie/
    Sprache erfolgt deterministisch ueber einen Hash aus dem Sender-
    namen (Summe der Zeichencodes), NICHT per Zufall. So bekommt
    derselbe Sender bei jedem taeglichen Lauf wieder dieselbe Variante -
    kein "Flackern" zwischen unterschiedlichen Texten von Tag zu Tag.
    """

    # Klammerzusätze im Land-Feld ignorieren, z.B. "US (ESPN+ 001)" -> "US"
    land_code = land.split("(")[0].strip().upper()

    if land_code == "DE":
        sprache = "DE"

    elif land_code in EXYU_LAENDER:
        sprache = "EXYU"

    elif land_code in EN_LAENDER:
        sprache = "EN"

    else:
        sprache = "EN"

    sender_upper = sender.upper()
    hash_wert = sum(ord(c) for c in sender)

    for kategorie_key in KATEGORIE_PRIORITAET:
        daten = KATEGORIEN[kategorie_key]

        for keyword in daten["keywords"]:

            if keyword in sender_upper:
                varianten = daten[sprache]
                nummer = hash_wert % len(varianten)
                text = varianten[nummer].format(sender=sender)
                return text, kategorie_key

    if sprache == "DE":
        texte = DE_STANDARD

    elif sprache == "EXYU":
        texte = EXYU_STANDARD

    else:
        texte = EN_STANDARD

    nummer = hash_wert % len(texte)

    return texte[nummer].format(sender=sender), None


def kategorie_label(kategorie_key, land):
    """Liefert den sprachlich passenden Anzeigenamen fuer das
    <category>-Tag, oder None, falls keine Kategorie erkannt wurde."""

    if not kategorie_key:
        return None

    land_code = land.split("(")[0].strip().upper()

    if land_code == "DE":
        sprache = "DE"
    elif land_code in EXYU_LAENDER:
        sprache = "EXYU"
    else:
        sprache = "EN"

    return KATEGORIEN[kategorie_key]["label"][sprache]


# ==========================================================
# Altersfreigabe je Kategorie (fuer <rating>-Tag)
# ==========================================================

ALTERSFREIGABE = {
    "HORROR": "16", "KRIMI": "12", "KINDER": "0", "FAMILIE": "0",
    "ANIME": "12", "REALITY": "12", "GAMING": "6", "COMEDY": "6",
    "SERIEN": "12", "FILM": "12", "SPORT": "0", "NEWS": "0",
    "MILITAER": "12", "TALKSHOW": "12", "WETTER": "0",
    "SHOPPING": "0", "RADIO": "0", "MUSIK": "0",
}
DEFAULT_ALTERSFREIGABE = "6"

# Kategorien, fuer die ein <episode-num> Sinn ergibt (fortlaufende
# Formate statt einmaliger Sendungen)
EPISODEN_KATEGORIEN = {"SERIEN", "ANIME", "KRIMI", "COMEDY", "FILM"}

# ==========================================================
# Poster/Still-Bilder je Kategorie (fuer <icon> im <programme>-Tag,
# zusaetzlich zum Sender-Logo im <channel>-Tag). Alle URLs stammen
# vom kanonischen Wikimedia-Commons-Endpunkt "Special:FilePath/<Datei>",
# der dauerhaftes Hotlinking auf frei lizenzierte Bilder erlaubt
# (CC0/CC BY/CC BY-SA/Public Domain). Optional laesst sich per
# "?width=NNN" eine kleinere Bildgroesse anfordern.
#
# Quelle/Recherche: siehe Projekt-Artefakt
# "EPG-Icons: 32 stabile, direkt einbettbare Wikimedia-Commons-Bild-URLs"
# ==========================================================

_WM = "https://commons.wikimedia.org/wiki/Special:FilePath/"

POSTER_URLS = {
    "REALITY": _WM + "Broadcast_studio_camera_(53997810821).jpg",
    "NEWS": _WM + "WBZ-TV_Studio.jpg",
    "WETTER": _WM + "Sky_clouds.JPG",
    "KINDER": _WM + "Kids_Playing_Games.jpg",
    "ANIME": _WM + "Cosplay_portraits_from_the_Con-nichiwa_anime_convention_in_Tucson.jpg",
    "FAMILIE": _WM + "Coloured-family.jpg",
    "GAMING": _WM + "Control_para_juegos.jpg",
    "RADIO": _WM + "Microphone_studio.jpg",
    "SHOPPING": _WM + "Mall_Shopping_(Unsplash).jpg",
    "WISSEN": _WM + "Library_book_shelves.jpg",
    "NATUR": _WM + "Nature-forest-trees-fog.jpg",
    "JAGD_FISCHEREI": _WM + "Angler_on_a_Wintry_Lake,_by_Ma_Yuan,_1195.jpg",
    "DOKU": _WM + "Wildlife_photography.jpg",
    "MILITAER": _WM + "Iraqi_soldiers_marching_during_the_parade.jpg",
    "AUTO": _WM + "Waymo_self-driving_car_front_view.gk.jpg",
    "REISEN": _WM + "Luggage_at_airport.jpg",
    "KOCHEN": _WM + "Kitchen_utensils-01.jpg",
    "MUSIK": _WM + "Musicians_performing_on_stage_at_a_night_concert_featuring_vibrant_lights_and_energetic_atmosphere.jpg",
    "COMEDY": _WM + "Jesus_is_coming.._Look_Busy_(George_Carlin).jpg",
    "RELIGION": _WM + "The_Church_of_the_Cross_(Bluffton).jpg",
    "HORROR": _WM + "Dark_Forest.jpg",
    "KRIMI": _WM + "Police_Line_Crime_Scene_2498847226.jpg",
    "TALKSHOW": _WM + "Woman_Conducting_an_Interview.jpg",
    "WIRTSCHAFT": _WM + "NYSE-floor.jpg",
    "GESUNDHEIT": _WM + "Stethoskop.jpg",
    "TECH": _WM + "A_printed_circuit_board_IMG_1487.JPG",
    "SPORT": _WM + "Football_match.jpg",
    "SERIEN": _WM + "Family_watching_television_1958.jpg",
    "FILM": _WM + "Clapperboard,_O2_film,_September_2008.jpg",
    "LIFESTYLE": _WM + "A_small_cup_of_coffee.JPG",
    "REGIONAL": _WM + "0_Thimougies_-_Panorama_du_village_(1).JPG",
    "UNTERHALTUNG": _WM + "Chiba-Ichikawa_fireworks_festival-xl.jpg",
}

# Fallback-Poster, falls keine Kategorie erkannt wurde
DEFAULT_POSTER = POSTER_URLS["UNTERHALTUNG"]


def poster_fuer_kategorie(kategorie_key):
    """Liefert die Poster-URL fuer eine Kategorie, oder das generische
    Fallback-Poster, falls keine Kategorie erkannt wurde/kein Eintrag
    existiert."""
    if not kategorie_key:
        return DEFAULT_POSTER
    return POSTER_URLS.get(kategorie_key, DEFAULT_POSTER)

# ==========================================================
# Tagesraster: variable Blocklaengen statt starrer 2h-Slots.
# Die 7 Bloecke ergeben zusammen 24h (6+3+3+2+4+4+2).
# ==========================================================

TAGESRASTER = [
    (6, "NACHT"),
    (3, "MORGEN"),
    (3, "VORMITTAG"),
    (2, "MITTAG"),
    (4, "NACHMITTAG"),
    (4, "ABEND"),
    (2, "SPAETABEND"),
]

FALLBACK_LABEL = {"DE": "Programm", "EXYU": "Program", "EN": "Programme"}

# Wochentags-Kuerzel je Sprache fuer den Datumsbezug im Sendetitel
# (z.B. "Mo 27.07: Sport am Abend"). Index 0 = Montag (passend zu
# date.weekday()).
WOCHENTAGE = {
    "DE": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    "EXYU": ["Pon", "Uto", "Sri", "Čet", "Pet", "Sub", "Ned"],
    "EN": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
}


def datumspraefix(sprache, datum):
    """Erzeugt ein Praefix wie 'Mo 27.07: ' aus einem date/datetime-
    Objekt, in der zur Sprache passenden Wochentags-Abkuerzung. Bei
    datum=None wird ein leerer String zurueckgegeben (kein Praefix)."""
    if datum is None:
        return ""
    kuerzel = WOCHENTAGE[sprache][datum.weekday()]
    return f"{kuerzel} {datum.day:02d}.{datum.month:02d}: "

# Generische Sendetitel-Vorlagen je Sprache/Tageszeit. {label} wird
# durch das sprachlich passende Kategorie-Label ersetzt (oder durch
# einen neutralen Fallback, falls keine Kategorie erkannt wurde).
SENDETITEL_VORLAGEN = {
    "DE": {
        "NACHT": ["{label} in der Nacht", "Best of {label}"],
        "MORGEN": ["{label} am Morgen", "Morgenmagazin: {label}"],
        "VORMITTAG": ["{label} Vormittag", "{label} Magazin"],
        "MITTAG": ["{label} zur Mittagszeit", "{label} Mittagsprogramm"],
        "NACHMITTAG": ["{label} am Nachmittag", "{label} Spezial"],
        "ABEND": ["{label} Primetime", "{label} am Abend"],
        "SPAETABEND": ["{label} Spätprogramm", "{label} Late Night"],
    },
    "EXYU": {
        "NACHT": ["{label} tokom noći", "Najbolje iz: {label}"],
        "MORGEN": ["{label} ujutro", "Jutarnji program: {label}"],
        "VORMITTAG": ["{label} prijepodne", "{label} magazin"],
        "MITTAG": ["{label} u podne", "{label} program"],
        "NACHMITTAG": ["{label} popodne", "{label} specijal"],
        "ABEND": ["{label} večernji program", "{label} u udarnom terminu"],
        "SPAETABEND": ["{label} kasno navečer", "{label} noćni program"],
    },
    "EN": {
        "NACHT": ["{label} Overnight", "Best of {label}"],
        "MORGEN": ["{label} in the Morning", "Morning {label}"],
        "VORMITTAG": ["{label} Late Morning", "{label} Magazine"],
        "MITTAG": ["{label} at Noon", "Midday {label}"],
        "NACHMITTAG": ["{label} in the Afternoon", "{label} Special"],
        "ABEND": ["{label} Primetime", "{label} Tonight"],
        "SPAETABEND": ["Late Night {label}", "{label} After Hours"],
    },
}


def sprache_fuer_land(land):
    land_code = land.split("(")[0].strip().upper()
    if land_code == "DE":
        return "DE"
    elif land_code in EXYU_LAENDER:
        return "EXYU"
    else:
        return "EN"


def sendetitel(kategorie_key, land, hash_wert, tageszeit, datum=None):
    """Erzeugt einen realistischeren, tageszeitabhaengigen Sendetitel
    statt einfach nur den Sendernamen zu wiederholen. Die Auswahl der
    Vorlage erfolgt wie bei den Beschreibungen deterministisch ueber
    den Sender-Hash (kein Flackern zwischen Tagen).

    Wird ein "datum" (date/datetime-Objekt) uebergeben, wird zusaetzlich
    ein echter Datumsbezug vorangestellt (z.B. "Mo 27.07: Sport am
    Abend") statt nur des generischen Tageszeit-Titels."""

    sprache = sprache_fuer_land(land)

    if kategorie_key:
        label = KATEGORIEN[kategorie_key]["label"][sprache]
    else:
        label = FALLBACK_LABEL[sprache]

    vorlagen = SENDETITEL_VORLAGEN[sprache][tageszeit]
    nummer = (hash_wert + len(tageszeit)) % len(vorlagen)
    titel = vorlagen[nummer].format(label=label)

    return datumspraefix(sprache, datum) + titel


def beschreibung_fuer_sender(kategorie_key, land, sender, hash_wert):
    """Gibt die Beschreibung nur in der zum Sender-Land passenden
    Sprache zurueck (DE/EXYU/EN) - keine parallelen Mehrsprachen-Tags
    mehr, sondern wie urspruenglich eine Sprache pro Sender."""

    sprache = sprache_fuer_land(land)
    standard_texte = {"DE": DE_STANDARD, "EXYU": EXYU_STANDARD, "EN": EN_STANDARD}
    lang_code = {"DE": "de", "EXYU": "hr", "EN": "en"}[sprache]

    if kategorie_key:
        varianten = KATEGORIEN[kategorie_key][sprache]
    else:
        varianten = standard_texte[sprache]

    nummer = hash_wert % len(varianten)
    text = varianten[nummer].format(sender=sender)

    return text, lang_code


def sender_anzeigename(name):
    worte = [wort.capitalize() for wort in name.split()]
    return " ".join(worte)


# ==========================================================
# DYN PPV / Flo Racing: Uhrzeit aus Event-Namen herauslesen
#
# Flo-Racing-Namen enthalten bei laufendem/geplantem Event oft eine
# Uhrzeit direkt im Namen, z.B. "Sa 14:00 : Flo Racing 05". Statt den
# Event-Titel nur als Text in einen der groben Tagesraster-Bloecke
# (z.B. den ganzen 4h-Nachmittagsblock) zu packen, wird hier - wenn
# moeglich - die exakte Uhrzeit erkannt, damit das Programm im EPG
# zeitlich genauer (Standard: 2 Stunden Dauer) statt ueber den
# gesamten Block hinweg angezeigt wird.
# ==========================================================

_ZEIT_MUSTER = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


def parse_event_zeit(event_text):
    """Sucht in einem Event-Namen/-Text nach einer Uhrzeit im Format
    HH:MM (z.B. "14:00" in "Sa 14:00 : Flo Racing 05") und gibt bei
    Erfolg ein Tupel (stunde, minute) zurueck, sonst None.

    Bewusst KEIN Datum/Wochentag-Parsing - die Wochentagskuerzel vor
    der Uhrzeit (z.B. "Sa") sind nicht eindeutig genug, um daraus
    zuverlaessig ein konkretes Kalenderdatum abzuleiten (koennte
    diese oder naechste Woche sein). Die Uhrzeit selbst reicht aber,
    um das Event am naechsten passenden Tag (i.d.R. heute, siehe
    Anwendung in generate_epg.py) praeziser statt blockweise
    einzutragen."""

    if not event_text:
        return None

    treffer = _ZEIT_MUSTER.search(event_text)
    if not treffer:
        return None

    stunde = int(treffer.group(1))
    minute = int(treffer.group(2))
    return stunde, minute

