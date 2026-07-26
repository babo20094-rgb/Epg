from datetime import datetime, timedelta, timezone
from xml.sax.saxutils import escape
import re
import requests
import xml.etree.ElementTree as ET

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


def sendetitel(kategorie_key, land, hash_wert, tageszeit):
    """Erzeugt einen realistischeren, tageszeitabhaengigen Sendetitel
    statt einfach nur den Sendernamen zu wiederholen. Die Auswahl der
    Vorlage erfolgt wie bei den Beschreibungen deterministisch ueber
    den Sender-Hash (kein Flackern zwischen Tagen)."""

    sprache = sprache_fuer_land(land)

    if kategorie_key:
        label = KATEGORIEN[kategorie_key]["label"][sprache]
    else:
        label = FALLBACK_LABEL[sprache]

    vorlagen = SENDETITEL_VORLAGEN[sprache][tageszeit]
    nummer = (hash_wert + len(tageszeit)) % len(vorlagen)
    return vorlagen[nummer].format(label=label)


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
# XML starten (Teile werden gesammelt und am Ende gejoint,
# statt bei jedem Schritt einen neuen String zu bauen)
# ==========================================================

xml_teile = ['<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n']

sender_daten = []

# ==========================================================
# sender.txt lesen
#
# Format (bis zu 4 Spalten, alles nach Sender ist optional):
#
# Land|Sender
# Land|Sender|Beschreibung
# Land|Sender|Beschreibung|Logo-URL
#
# Wird kein Logo angegeben, wird KEIN <icon>-Tag erzeugt -
# der Player/die Playlist behält dann ihr eigenes Logo.
# ==========================================================

try:
    with open("sender.txt", "r", encoding="utf-8") as f:
        zeilen = f.readlines()
except FileNotFoundError:
    raise SystemExit("Fehler: sender.txt wurde nicht gefunden.")

for zeile in zeilen:

    zeile = zeile.strip()

    if not zeile or zeile.startswith("#"):
        continue

    # NAME:-Präfix: für Sender, deren echter Playlist-Name selbst
    # Pipe-Zeichen enthält (z.B. "- NO EVENT STREAMING - | 8K
    # EXCLUSIVE | DE: DYN PPV 1"). Normales Land|Sender|Beschreibung|
    # Logo-Format würde so einen Namen an den falschen Stellen
    # zerschneiden. Bei "NAME:" wird stattdessen nur am LETZTEN Pipe
    # der Zeile getrennt - alles davor ist der komplette, unveränderte
    # Kanalname (wird 1:1 als id/display-name verwendet, keine
    # Land|Sender-Rekonstruktion), alles danach das Logo.
    if zeile.upper().startswith("NAME:"):
        rest = zeile[5:]
        teile_name = rest.rsplit("|", 1)

        if len(teile_name) != 2:
            continue

        voller_name = teile_name[0].strip()
        logo = teile_name[1].strip()

        if not voller_name:
            continue

        # Für den Sendungstitel NICHT den kompletten Rohnamen
        # wiederverwenden - der ist fast identisch mit dem Kanalnamen
        # selbst (nur andere Groß-/Kleinschreibung). Viele Player
        # (u.a. TiviMate) interpretieren einen Sendungstitel, der
        # praktisch gleich dem Kanalnamen ist, als "keine echten
        # Daten" und zeigen dann trotz vorhandener <title>/<desc>
        # nur "Keine Information" an. Stattdessen wird der stabile
        # Kern des Namens (z.B. "DYN PPV 1" oder "FLO RACING 3")
        # herausgelöst, falls vorhanden - das unterscheidet sich klar
        # vom Kanalnamen. Erfasst sowohl DYN-PPV- als auch
        # FLO-RACING-Sender (gleiches Prinzip, gleiche Behandlung).
        kurzname_match = re.search(r"(DYN\s*PPV|FLO\s*RACING)\s*\d+", voller_name, re.IGNORECASE)
        kurzname = kurzname_match.group(0) if kurzname_match else voller_name

        beschreibung, kategorie_key = standard_beschreibung("DE", kurzname)

        # DYN PPV 1-50 UND FLO RACING (diese NAME:-Einträge in
        # sender.txt - NICHT zu verwechseln mit den fest verdrahteten
        # API-Kanälen "DYN PPV 1-20" weiter unten, die unverändert
        # bleiben):
        #
        # Zwei unterschiedliche Formate, je nach Anbieter:
        #
        # a) DYN (Pipe-Format): der Name besteht aus mehreren mit "|"
        #    getrennten Teilen, z.B.
        #    "- NO EVENT STREAMING - | 8K EXCLUSIVE | DE: DYN PPV 1"
        #    Der vordere Teil (vor dem ersten "|") ist im Leerlauf ein
        #    Platzhalter ("- NO EVENT STREAMING -"), läuft ein Event
        #    steht dort stattdessen der Event-Name (z.B.
        #    "FC Bayern - Real Madrid").
        #
        # b) FLO RACING (Doppelpunkt-Format, kein "|" im Namen): im
        #    Leerlauf steht NUR der Kanalname selbst, z.B.
        #    "Flo Racing 03". Läuft ein Event, wird davor Datum/Uhrzeit
        #    eingefügt, getrennt durch ":", z.B.
        #    "Sa 14:00 : Flo Racing 05".
        #
        # In beiden Fällen gilt: steht vor dem Kurznamen zusätzlicher,
        # nicht-generischer Text -> Event läuft, dieser Text wird als
        # Sendungstitel/-beschreibung übernommen. Steht nichts oder nur
        # der bekannte "NO EVENT"-Platzhalter davor -> Leerlauf, es
        # bleibt beim generischen Standardtext (beschreibung s.o.).
        if "|" in voller_name:
            # DYN-Format: erster Pipe-Abschnitt ist der relevante Teil
            event_teil = voller_name.split("|", 1)[0].strip()
        elif kurzname_match and kurzname_match.start() > 0:
            # FLO-RACING-Format: alles vor dem gefundenen Kurznamen,
            # führende/trailing ":" bzw. Leerzeichen entfernt
            event_teil = voller_name[:kurzname_match.start()].strip(" :").strip()
        else:
            # Name besteht nur aus dem Kurznamen selbst -> kein Event
            event_teil = ""

        event_titel = None

        if event_teil and "no event" not in event_teil.lower():
            event_titel = event_teil

        sender_daten.append({
            "kanal": voller_name,
            "land": "DE",
            "sender": kurzname,
            "beschreibung": beschreibung,
            "logo": logo,
            "exakter_name": True,
            "event_titel": event_titel,
            "kategorie": kategorie_key
        })
        continue

    teile = [x.strip() for x in zeile.split("|")]

    while len(teile) < 4:
        teile.append("")

    land = teile[0]
    sender = teile[1]
    beschreibung = teile[2]
    logo = teile[3]
    kanal = f"{land}|{sender}"

    auto_beschreibung, kategorie_key = standard_beschreibung(land, sender)

    if beschreibung == "":
        beschreibung = auto_beschreibung

    sender_daten.append({
        "kanal": kanal,
        "land": land,
        "sender": sender,
        "beschreibung": beschreibung,
        "logo": logo,
        "exakter_name": False,
        "kategorie": kategorie_key
    })

# ==========================================================
# logo_only.txt lesen (optional)
#
# Für Sender, bei denen NUR das Logo gesetzt/geändert werden
# soll - z.B. weil das eigentliche EPG (die Programme) von
# einer anderen Quelle kommt und nicht überschrieben werden soll.
#
# Zwei Zeilenformate werden unterstützt:
#
# 1) Normale Sender (Land + Sendername getrennt):
#    Land|Sender|Logo-URL
#    Land|Sender||Logo-URL   (gleiches Schema wie sender.txt)
#
# 2) Kanalnamen mit Pipe-Zeichen im Namen selbst (z.B. Namen wie
#    "- NO EVENT STREAMING - | 8K EXCLUSIVE | DE: DYN PPV 1"):
#    NAME:<kompletter Kanalname exakt wie in der Playlist>|Logo-URL
#    Hier wird NUR das letzte "|" in der Zeile als Trenner zur
#    Logo-URL verwendet - alles davor (nach "NAME:") ist der Name,
#    egal wie viele Pipes darin vorkommen.
#
#    Das gilt auch für Sender mit täglich wechselndem Namen (z.B.
#    Live-Event-Kanäle wie "(Victory+ 001) | VNL Men's Live Matches :
#    France vs Belgium"). Hier reicht der stabile Teil in Klammern:
#    NAME:(Victory+ 001)|Logo-URL
#    oder kurz (funktioniert automatisch, sobald nur ein "|" in der
#    Zeile vorkommt):
#    (Victory+ 001)|Logo-URL
#
#    Ablauf für dieses Format:
#    a) Zuerst wird per TEILSTRING-Suche (Groß-/Kleinschreibung egal)
#       geprüft, ob ein Sender aus sender.txt diesen Text enthält.
#       Bei Treffer(n) wird dort NUR das Logo überschrieben.
#    b) Kein Treffer? Dann wird ein eigenständiger <channel>-Block
#       angelegt - mit mehreren <display-name>-Varianten (mit und
#       ohne Klammern), damit der Player den Sender trotz wechselndem
#       vollen Namen per Teilstring zuordnen kann.
#
# - Steht der Sender bereits in sender.txt (Format 1), wird dort
#   nur das Logo überschrieben (kein zusätzlicher Eintrag).
# - Sonst wird nur ein <channel>-Block mit Icon angelegt - OHNE
#   <programme>-Platzhalter, damit das echte EPG dieser Quelle
#   erhalten bleibt.
# ==========================================================

kanal_index = {d["kanal"]: d for d in sender_daten}
logo_only_channels = []
gesehene_logo_only_kanaele = set()

# Logo-Overrides für die fest eingebauten DYN-PPV-Kanäle (1-20).
# Diese Kanäle existieren bereits als eigener <channel>-Block mit
# eigener id ("DE| DYN PPV {i} HD") und bekommen dort auch ihre
# Programme (Live-Events/Leerzeiten) zugewiesen. Ein Logo-Eintrag
# in logo_only.txt für einen DYN-PPV-Sender darf deshalb KEINEN
# eigenständigen neuen Channel erzeugen (sonst gehen die Programme
# an der falschen, neuen Channel-id vorbei) - stattdessen wird hier
# nur das Logo für die passende Nummer gemerkt.
dyn_ppv_logo_overrides = {}
DYN_PPV_MUSTER = re.compile(r"DYN\s*PPV\s*(\d+)", re.IGNORECASE)

try:
    with open("logo_only.txt", "r", encoding="utf-8") as f:
        logo_only_zeilen = f.readlines()
except FileNotFoundError:
    logo_only_zeilen = []

for zeile in logo_only_zeilen:

    zeile = zeile.strip()

    if not zeile or zeile.startswith("#"):
        continue

    ist_name_praefix = zeile.upper().startswith("NAME:")
    roh_teile = zeile.split("|")

    if ist_name_praefix or len(roh_teile) == 2:
        # Kompletter/kurzer Name + Logo-URL, getrennt durch das LETZTE
        # Pipe-Zeichen in der Zeile. "NAME:" Präfix ist optional - wird
        # automatisch erkannt, wenn die Zeile nur ein einziges Pipe hat
        # (z.B. "DE: DYN PPV 1|https://...") oder wenn "NAME:" davor steht
        # (für Namen, die selbst mehrere Pipes enthalten).
        rest = zeile[5:] if ist_name_praefix else zeile
        teile_name = rest.rsplit("|", 1)

        if len(teile_name) != 2:
            continue

        voller_name = teile_name[0].strip()
        logo = teile_name[1].strip()

        if not voller_name or not logo:
            continue

        # a) Teilstring-Treffer gegen bereits bekannte Sender aus
        # sender.txt suchen (z.B. wenn nur "(Victory+ 001)" angegeben
        # wird, der volle Sendername in sender.txt aber
        # "(Victory+ 001) | VNL Men's Live Matches : ..." lautet).
        suchtext = voller_name.lower()
        treffer = [
            d for d in sender_daten
            if suchtext in d["sender"].lower()
        ]

        if treffer:
            for d in treffer:
                d["logo"] = logo
            print(
                f"logo_only.txt: '{voller_name}' per Teilstring auf "
                f"{len(treffer)} Sender aus sender.txt angewendet."
            )
            continue

        # b) Kein Treffer in sender.txt: prüfen, ob es sich um einen
        # DYN-PPV-Sender handelt (z.B. "DE: DYN PPV 1"). Diese Kanäle
        # gibt es weiter unten bereits fest mit eigener Channel-id und
        # eigenen Programmen - hier deshalb NUR das Logo überschreiben,
        # statt einen zweiten, konkurrierenden Channel anzulegen.
        dyn_match = DYN_PPV_MUSTER.search(voller_name)
        if dyn_match:
            nummer = int(dyn_match.group(1))
            dyn_ppv_logo_overrides[nummer] = logo
            print(
                f"logo_only.txt: '{voller_name}' als DYN-PPV-Logo-Override "
                f"für Kanal {nummer} übernommen."
            )
            continue

        # Sonst: eigenständigen Channel anlegen. Klammerinhalt zusätzlich
        # als Alias ohne Klammern herauslösen, damit der Player mehr
        # Chancen zur Zuordnung per Teilstring hat.
        kanal = voller_name

        if kanal not in gesehene_logo_only_kanaele:
            aliase = [voller_name]

            klammer_match = re.search(r"\(([^)]+)\)", voller_name)
            if klammer_match:
                klammer_inhalt = klammer_match.group(1).strip()
                if klammer_inhalt and klammer_inhalt not in aliase:
                    aliase.append(klammer_inhalt)

            ohne_klammern = re.sub(r"[()]", "", voller_name).strip()
            if ohne_klammern and ohne_klammern not in aliase:
                aliase.append(ohne_klammern)

            logo_only_channels.append({
                "kanal": kanal,
                "voller_name": voller_name,
                "aliase": aliase,
                "logo": logo
            })
            gesehene_logo_only_kanaele.add(kanal)

        continue

    # Format 1: Land|Sender|Logo bzw. Land|Sender||Logo
    teile = [x.strip() for x in zeile.split("|")]

    # Gleiches Spaltenschema wie sender.txt: Land|Sender|Beschreibung|Logo
    # Die Beschreibung-Spalte wird hier ignoriert, das Logo ist immer
    # die letzte (4.) Spalte. Wird nur "Land|Sender|Logo" mit 3 Spalten
    # angegeben, ist das Logo dann Spalte 3.
    while len(teile) < 4:
        teile.append("")

    land = teile[0]
    sender = teile[1]
    logo = teile[3] if teile[3] else teile[2]

    if not logo:
        continue

    kanal = f"{land}|{sender}"

    if kanal in kanal_index:
        # Logo für bereits vorhandenen Sender überschreiben
        kanal_index[kanal]["logo"] = logo
    elif kanal not in gesehene_logo_only_kanaele:
        # Neuer, eigenständiger Channel NUR mit Icon, ohne Programme
        logo_only_channels.append({
            "kanal": kanal,
            "land": land,
            "sender": sender,
            "logo": logo
        })
        gesehene_logo_only_kanaele.add(kanal)

# ==========================================================
# <channel>-Blöcke schreiben (sender.txt, mit ggf.
# überschriebenem Logo aus logo_only.txt)
# ==========================================================

for daten in sender_daten:

    # So wie er in der Playlist als tvg-name steht (z.B. "DE| RTL"),
    # unverändert übernommen - das ist entscheidend für die
    # automatische Sender-Zuordnung in TiviMate.
    # Ausnahme: Einträge mit "exakter_name" (aus NAME:-Zeilen in
    # sender.txt) haben ihren kompletten, echten Playlist-Namen
    # bereits direkt in "kanal" stehen - hier NICHT aus Land+Sender
    # neu zusammenbauen, sonst geht der Name kaputt.
    if daten.get("exakter_name"):
        playlist_name = daten["kanal"]
    else:
        playlist_name = f"{daten['land']}| {daten['sender']}"

    xml_teile.append(
        f' <channel id="{escape(daten["kanal"])}"> <display-name>{escape(playlist_name)}</display-name> '
    )

    # Icon wird NUR erzeugt, wenn ein Logo angegeben ist
    # (aus sender.txt oder als Override aus logo_only.txt)
    if daten["logo"]:
        xml_teile.append(f' <icon src="{escape(daten["logo"])}"/>\n')

    xml_teile.append("</channel>\n")

# ==========================================================
# <channel>-Blöcke für reine Logo-Einträge (kein Sender in
# sender.txt) - nur Icon, keine Programme
# ==========================================================

for daten in logo_only_channels:
    if "voller_name" in daten:
        namen = daten.get("aliase") or [daten["voller_name"]]
    else:
        namen = [f"{daten['land']}| {daten['sender']}"]

    xml_teile.append(f' <channel id="{escape(daten["kanal"])}">')

    for name in namen:
        xml_teile.append(f' <display-name>{escape(name)}</display-name>')

    xml_teile.append(
        f' <icon src="{escape(daten["logo"])}"/> </channel>\n'
    )

# ==========================================================
# DYN PPV CHANNELS
# ==========================================================

dyn_logo = "https://www.dslweb.de/public/resources/images/anbieter/dyn/dyn-teaser.jpg"

for i in range(1, 21):
    kanal = f"DE| DYN PPV {i} HD"
    logo_fuer_kanal = dyn_ppv_logo_overrides.get(i, dyn_logo)
    xml_teile.append(
        f' <channel id="{escape(kanal)}"> <display-name>DYN PPV {i} HD</display-name> <icon src="{escape(logo_fuer_kanal)}"/> </channel> '
    )

# ==========================================================
# STANDARD-EPG (2-Stunden-Blöcke für 3 Tage, als Platzhalter)
# ==========================================================

starttag = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

# ==========================================================
# STANDARD-EPG (variable Tagesraster-Bloecke für 3 Tage, als
# Platzhalter). Statt starrer 2h-Slots orientieren sich die
# Blocklaengen an einem realistischen Tagesablauf (Nacht/Morgen/
# Vormittag/Mittag/Nachmittag/Abend/Spaetabend).
# ==========================================================

starttag = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

ANZAHL_TAGE = 3

for tag_index in range(ANZAHL_TAGE):

    tag_start = starttag + timedelta(days=tag_index)
    stunden_cursor = 0

    for block_index, (dauer, tageszeit) in enumerate(TAGESRASTER):

        start = tag_start + timedelta(hours=stunden_cursor)
        ende = start + timedelta(hours=dauer)
        stunden_cursor += dauer

        start_str = start.strftime("%Y%m%d%H%M%S +0000")
        ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

        for daten in sender_daten:
            # DYN PPV 1-50 (NAME:-Einträge): hat sich der Kanalname wegen
            # eines laufenden Events geändert (siehe Erkennung weiter
            # oben beim Einlesen), wird dieser Event-Name hier als
            # Sendungstitel/-beschreibung übernommen. Ohne Event bleibt
            # es beim bisherigen kategoriebasierten Text.
            event_titel = daten.get("event_titel")
            kategorie_key = daten.get("kategorie")
            hash_wert = sum(ord(c) for c in daten["sender"])

            if event_titel:
                titel_text = escape(event_titel)
                beschr_text = event_titel
                lang_code = "de"
            else:
                titel_text = escape(
                    sendetitel(kategorie_key, daten["land"], hash_wert, tageszeit)
                )
                beschr_text, lang_code = beschreibung_fuer_sender(
                    kategorie_key, daten["land"], daten["sender"], hash_wert
                )

            # Genre-Tag: nur wenn eine Kategorie erkannt wurde. Sprache
            # richtet sich nach dem Land des Senders, damit z.B. ein
            # EXYU-Sender "Sport" auch als "Sport"/"Sport" in seiner
            # Sprache bekommt statt eines fix deutschen Labels.
            label = kategorie_label(kategorie_key, daten["land"])
            category_tag = (
                f' <category lang="{lang_code}">{escape(label)}</category>' if label else ""
            )

            # Altersfreigabe passend zur Kategorie (Standard: 6)
            altersfreigabe = ALTERSFREIGABE.get(kategorie_key, DEFAULT_ALTERSFREIGABE)
            rating_tag = (
                f' <rating system="FSK"><value>{altersfreigabe}</value></rating>'
            )

            # Episoden-Nummer nur bei fortlaufenden Formaten (Serien,
            # Anime, Krimi, Comedy, Filme) und nicht bei Live-Events.
            episode_tag = ""
            if kategorie_key in EPISODEN_KATEGORIEN and not event_titel:
                staffel = 1 + (tag_index % 3)
                episode = block_index + 1
                episode_tag = (
                    f' <episode-num system="onscreen">'
                    f'S{staffel:02d}E{episode:02d}</episode-num>'
                )

            # Beschreibung nur in der zum Sender-Land passenden Sprache
            # (DE/EXYU/EN) - jeweils identisch fuer sub-title und desc.
            beschr_escaped = escape(beschr_text)
            desc_tag = f' <desc lang="{lang_code}">{beschr_escaped}</desc>'
            sub_title_tag = f' <sub-title lang="{lang_code}">{beschr_escaped}</sub-title>'

            xml_teile.append(
                f' <programme start="{start_str}" stop="{ende_str}" channel="{escape(daten["kanal"])}">'
                f' <title lang="{lang_code}">{titel_text}</title>'
                f'{sub_title_tag}'
                f'{desc_tag}{category_tag}{rating_tag}{episode_tag} </programme> '
            )

# ==========================================================
# DYN LIVE EVENTS
# ==========================================================

try:
    response = requests.get(
        "https://streaming.contentdesk.sport/api/public/live-productions",
        timeout=30
    )

    if response.status_code == 200:
        daten = response.json()

        if len(daten) == 0:
            print("Keine DYN Live-Events - Standardtext wird erstellt")
        else:
            kanal_nummer = 1

            for event in daten:
                titel = event.get("title", "Dyn Sport")
                beschreibung = event.get("description", titel)

                start = event.get("scheduledAt")
                ende = event.get("scheduledEnd")

                if not start or not ende:
                    continue

                startzeit = datetime.fromisoformat(
                    start.replace("Z", "+00:00")
                ).strftime("%Y%m%d%H%M%S +0000")

                endzeit = datetime.fromisoformat(
                    ende.replace("Z", "+00:00")
                ).strftime("%Y%m%d%H%M%S +0000")

                kanal = f"DE| DYN PPV {kanal_nummer} HD"

                xml_teile.append(
                    f' <programme start="{startzeit}" stop="{endzeit}" channel="{escape(kanal)}">'
                    f' <title>{escape(titel)}</title> <desc>{escape(beschreibung)}</desc> </programme> '
                )

                kanal_nummer += 1
                if kanal_nummer > 20:
                    kanal_nummer = 1

except Exception as e:
    print("DYN Fehler:", e)

# ==========================================================
# DYN LEERZEITEN
# ==========================================================

jetzt = datetime.now(timezone.utc).replace(
    hour=0, minute=0, second=0, microsecond=0
)

for i in range(1, 21):
    kanal = f"DE| DYN PPV {i} HD"

    for stunde in range(24 * 3):
        start = jetzt + timedelta(hours=stunde)
        ende = start + timedelta(hours=1)

        start_str = start.strftime("%Y%m%d%H%M%S +0000")
        ende_str = ende.strftime("%Y%m%d%H%M%S +0000")

        xml_teile.append(
            f' <programme start="{start_str}" stop="{ende_str}" channel="{escape(kanal)}">'
            f' <title>Im Moment keine Live Events, bleib dran</title>'
            f' <desc>Im Moment keine Live Events, bleib dran.</desc> </programme> '
        )

# ==========================================================
# XML ABSCHLIESSEN
# ==========================================================

xml_teile.append("\n</tv>")

xml_inhalt = "".join(xml_teile)

# ==========================================================
# XML-Validitätsprüfung
#
# Bevor die Datei geschrieben (und später committet) wird, wird
# geprüft, ob das erzeugte XML überhaupt wohlgeformt ist. Bricht das
# Skript hier ab, bleibt die zuletzt funktionierende Epg_365_Tage.xml
# unangetastet erhalten, statt durch eine kaputte Datei ersetzt zu
# werden.
# ==========================================================

try:
    ET.fromstring(xml_inhalt)
except ET.ParseError as e:
    raise SystemExit(f"Fehler: Erzeugtes XML ist ungültig, Abbruch ohne Schreiben: {e}")

with open("Epg_365_Tage.xml", "w", encoding="utf-8") as f:
    f.write(xml_inhalt)

print(f"EPG erfolgreich erstellt ({len(sender_daten)} Sender).")
