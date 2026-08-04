"""
epg_lib.py - Reine Definitionen (Kategorien, Sprachlogik, Hilfsfunktionen)
ohne Seiteneffekte (kein Dateizugriff, kein Netzwerk-Request, kein Schreiben).

Ausgelagert aus generate_epg.py, damit diese Funktionen isoliert per
Unit-Tests geprueft werden koennen (siehe test_generate_epg.py), ohne
dass dabei sender.txt gelesen oder die DYN-API angefragt werden muss.
"""

import re
import unicodedata
import difflib


# ==========================================================
# Automatische Beschreibungen nach Kategorie
# ==========================================================

KATEGORIEN = {
    "REALITY": {
        "label": {"DE": "Reality-TV", "EXYU": "Rijaliti", "EN": "Reality TV", "SI": "Resničnostni šov", "MK": "Rijaliti"},
        "keywords": [
            "REALITY", "BIG BROTHER", "TEMPTATION", "LOVE ISLAND", "PAROVI", "ZADRUGA", "FARMA", "SURVIVOR", "BACHELOR", "BACHELORETTE", "TOWIE", "GEORDIE SHORE", "KARDASHIAN", "HOUSEWIVES", "90 DAY", "MAFS", "MARRIED AT FIRST SIGHT"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "NEWS": {
        "label": {"DE": "Nachrichten", "EXYU": "Vijesti", "EN": "News", "SI": "Novice", "MK": "Vesti"},
        "keywords": [
            "NEWS", "CNN", "BBC NEWS", "SKY NEWS", "AL JAZEERA", "N24", "NTV", "WELT", "EURONEWS", "FRANCE 24", "BLOOMBERG", "DW", "CNBC", "FOX NEWS", "MSNBC", "RTRS", "RTS", "HRT", "BHT", "N1", "VIJESTI", "DNEVNIK", "ABC NEWS", "ITV NEWS", "GB NEWS", "TALKTV", "TALK TV", "C-SPAN", "NEWSMAX", "OANN", "PHOENIX", "TAGESSCHAU", "ARD", "ZDF", "CHANNEL 4 NEWS", "SKY NEWS ARABIA", "KLAN", "RTV21", "MREZA", "PINK VIJESTI", "K3", "NOVA VIJESTI", "PBS NEWSHOUR"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "KINDER": {
        "label": {"DE": "Kinder", "EXYU": "Dječiji program", "EN": "Kids", "SI": "Otroški program", "MK": "Detska programa"},
        "keywords": [
            "KIDS", "KID", "JR", "JUNIOR", "DISNEY", "CARTOON", "NICKELODEON", "NICK", "BOOMERANG", "BABY", "TOON", "CBEEBIES", "MINIMAX", "TINY", "POPCORN", "GULLI", "DJECA", "CRTANI", "CBBC", "PBS KIDS", "MILKSHAKE", "BABY TV", "BABYTV", "SUPER RTL", "SUPERRTL", "KIKA", "PANDA", "DUCK TV", "MINI", "PLANETA DJECA"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "GAMING": {
        "label": {"DE": "Gaming", "EXYU": "Gaming", "EN": "Gaming", "SI": "Igre", "MK": "Gejming"},
        "keywords": [
            "GAMING", "ESPORTS", "E-SPORTS", "GAME", "IGRE", "TWITCH", "GAMER", "PLAYSTATION", "XBOX", "NINTENDO", "GINX"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "RADIO": {
        "label": {"DE": "Radio", "EXYU": "Radio", "EN": "Radio", "SI": "Radio", "MK": "Radio"},
        "keywords": [
            "RADIO", "HÖRFUNK", "FM", "BBC RADIO", "CLASSIC FM", "HEART RADIO", "CAPITAL FM"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "SHOPPING": {
        "label": {"DE": "Shopping", "EXYU": "Kupovina", "EN": "Shopping", "SI": "Nakupovanje", "MK": "Kupuvanje"},
        "keywords": [
            "SHOP", "SHOPPING", "QVC", "HSE", "KUPOVINA", "IDEAL WORLD", "BID TV", "JEWELLERY MAKER", "STUDIO SHOP", "TELESHOPPING", "TV SHOP"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "WISSEN": {
        "label": {"DE": "Wissen & Bildung", "EXYU": "Znanje i edukacija", "EN": "Science & Education", "SI": "Znanje in izobraževanje", "MK": "Znaenje i obrazovanie"},
        "keywords": [
            "SCIENCE", "EDUCATION", "ZNANJE", "NAUKA", "BILDUNG", "LEARN", "DISCOVERY SCIENCE", "OPEN UNIVERSITY"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "NATUR": {
        "label": {"DE": "Natur", "EXYU": "Priroda", "EN": "Nature", "SI": "Narava", "MK": "Priroda"},
        "keywords": [
            "NATURE", "WILD", "ANIMAL", "SAFARI", "PLANET", "EARTH", "PRIRODA", "ZIVOTINJE", "ANIMAL PLANET"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "DOKU": {
        "label": {"DE": "Dokumentation", "EXYU": "Dokumentarni program", "EN": "Documentary", "SI": "Dokumentarni program", "MK": "Dokumentarna programa"},
        "keywords": [
            "DISCOVERY", "NAT GEO", "NATIONAL", "HISTORY", "DOC", "DOKUMENTARNI", "SMITHSONIAN", "TRUE CRIME", "INVESTIGATION", "PBS", "ARTE", "YESTERDAY", "CURIOSITY", "VIASAT EXPLORE", "ID", "INVESTIGATION DISCOVERY"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "AUTO": {
        "label": {"DE": "Auto & Motor", "EXYU": "Auto i motor", "EN": "Auto & Motor", "SI": "Avto in motor", "MK": "Avtomobili i moto"},
        "keywords": [
            "AUTO", "MOTOR", "MOTORVISION", "AUTOMOBIL", "GARAZA", "TOP GEAR", "GRAND TOUR", "MOTORTREND", "VELOCITY", "AUTO MOTO", "DRIVE"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "REISEN": {
        "label": {"DE": "Reisen", "EXYU": "Putovanja", "EN": "Travel", "SI": "Potovanja", "MK": "Patuvanja"},
        "keywords": [
            "TRAVEL", "TOUR", "TOURISM", "VACATION", "EXPLORE", "PUTOVANJA", "TRAVEL CHANNEL", "GEO TRAVEL"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "KOCHEN": {
        "label": {"DE": "Kochen", "EXYU": "Kuhinja", "EN": "Food & Cooking", "SI": "Kuhanje", "MK": "Gotvenje"},
        "keywords": [
            "FOOD", "KITCHEN", "COOK", "CUISINE", "CHEF", "GUSTO", "KUHINJA", "RECEPTI", "MASTERCHEF", "BAKE OFF", "FOOD NETWORK", "TASTE", "GORDON RAMSAY", "COOKING CHANNEL"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "MUSIK": {
        "label": {"DE": "Musik", "EXYU": "Muzika", "EN": "Music", "SI": "Glasba", "MK": "Muzika"},
        "keywords": [
            "MUSIC", "MUSIK", "MTV", "VH1", "DELUXE", "CLUB", "HITS", "MEZZO", "TRACE", "4MUSIC", "CMC", "DM SAT", "FOLK", "BALKAN MUSIC", "NRJ", "KISS", "DANCE", "ROCK", "POP", "JAZZ", "MUZIKA", "HEART", "CAPITAL", "SMOOTH", "MAGIC RADIO", "GRAND", "HITRADIO", "ENERGY", "SCHLAGER", "NARODNA", "TURBO FOLK", "PARTY"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "COMEDY": {
        "label": {"DE": "Comedy", "EXYU": "Komedija", "EN": "Comedy", "SI": "Komedija", "MK": "Komedija"},
        "keywords": [
            "COMEDY", "HUMOR", "FUNNY", "LAUGH", "KOMEDIJA", "DAVE", "COMEDY CENTRAL", "PARANDOVCI", "SMIJEH"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "RELIGION": {
        "label": {"DE": "Religion", "EXYU": "Vjera", "EN": "Religion", "SI": "Vera", "MK": "Religija"},
        "keywords": [
            "EWTN", "KTV", "GOD", "ISLAM", "QURAN", "BIBLE", "CHURCH", "SVET", "VJERA", "HAYAT PLUS", "TRINITY", "GOOD TV", "DAAI"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "SPORT": {
        "label": {"DE": "Sport", "EXYU": "Sport", "EN": "Sport", "SI": "Šport", "MK": "Sport"},
        "keywords": [
            "SPORT", "SPORTS", "ESPN", "EUROSPORT", "DAZN", "SKY SPORT", "ARENA", "NBA", "NFL", "NHL", "MLB", "TENNIS", "GOLF", "RACING", "FORMULA", "F1", "MOTOGP", "BOX", "FIGHT", "UFC", "BT SPORT", "TNT SPORTS", "PREMIER LEAGUE", "SOCCER", "RUGBY", "CRICKET", "FLO SPORTS", "FLO RACING", "FANDUEL SPORTS", "BEIN SPORTS", "SPORT KLUB", "ARENA SPORT", "SPORTKLUB", "NASCAR", "PGA TOUR", "SKY SPORTS", "VIAPLAY SPORT", "DYN PPV", "WWE", "OLYMPIC", "OLIMPIJSKI"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "SERIEN": {
        "label": {"DE": "Serien", "EXYU": "Serije", "EN": "Series", "SI": "Serije", "MK": "Serii"},
        "keywords": [
            "SERIES", "SERIJA", "SERIJE", "DRAMA", "SOAP", "SITCOM", "EPIX", "BRAVO", "USA NETWORK"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "FILM": {
        "label": {"DE": "Filme", "EXYU": "Filmovi", "EN": "Movies", "SI": "Filmi", "MK": "Filmovi"},
        "keywords": [
            "CINEMA", "FILM", "MOVIE", "HOLLYWOOD", "HBO", "CINEMAX", "SKY CINEMA", "WARNER", "PARAMOUNT", "UNIVERSAL", "SONY", "STAR", "AXN", "AMC", "SYFY", "TNT", "THRILLER", "FILMOVI", "FILM4", "ITV MOVIES", "MGM", "EPIC DRAMA", "PINK FILM", "KLASIK FILM", "CINESTAR", "CINE"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "WETTER": {
        "label": {"DE": "Wetter", "EXYU": "Vrijeme", "EN": "Weather", "SI": "Vreme", "MK": "Vreme"},
        "keywords": [
            "WEATHER", "WETTER", "VRIJEME", "STORM", "METEO"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "JAGD_FISCHEREI": {
        "label": {"DE": "Jagd & Angeln", "EXYU": "Lov i ribolov", "EN": "Hunting & Fishing", "SI": "Lov in ribolov", "MK": "Lov i ribolov"},
        "keywords": [
            "HUNT", "FISHING", "OUTDOOR", "ANGELN", "JAGD", "LOV", "RIBOLOV"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "MILITAER": {
        "label": {"DE": "Militär & Krieg", "EXYU": "Vojska i rat", "EN": "Military & War", "SI": "Vojska in vojna", "MK": "Vojska i vojna"},
        "keywords": [
            "MILITARY", "WAR", "ARMY", "VOJSKA", "RAT", "WEHRMACHT"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "FAMILIE": {
        "label": {"DE": "Familie", "EXYU": "Porodica", "EN": "Family", "SI": "Družina", "MK": "Semejstvo"},
        "keywords": [
            "FAMILY", "FAMILIE", "PORODICA", "HALLMARK"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "ANIME": {
        "label": {"DE": "Anime", "EXYU": "Anime", "EN": "Anime", "SI": "Anime", "MK": "Anime"},
        "keywords": [
            "ANIME", "TOONAMI", "CRUNCHYROLL", "MANGA"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "KRIMI": {
        "label": {"DE": "Krimi", "EXYU": "Krimi", "EN": "Crime", "SI": "Kriminalka", "MK": "Kriminal"},
        "keywords": [
            "CRIME", "DETECTIVE", "MURDER", "CSI", "LAW & ORDER", "KRIMI"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "GESUNDHEIT": {
        "label": {"DE": "Gesundheit & Fitness", "EXYU": "Zdravlje i fitnes", "EN": "Health & Fitness", "SI": "Zdravje in fitnes", "MK": "Zdravje i fitnes"},
        "keywords": [
            "FITNESS", "HEALTH", "WELLNESS", "YOGA", "GYM", "ZDRAVLJE"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "TECH": {
        "label": {"DE": "Technik", "EXYU": "Tehnologija", "EN": "Technology", "SI": "Tehnologija", "MK": "Tehnologija"},
        "keywords": [
            "TECH", "TECHNOLOGY", "GADGET", "TEHNOLOGIJA"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "HORROR": {
        "label": {"DE": "Horror & Thriller", "EXYU": "Horor i triler", "EN": "Horror & Thriller", "SI": "Grozljivke in trilerji", "MK": "Horor i triler"},
        "keywords": [
            "HORROR", "SCARY", "SCREAM", "CHILLER", "TERROR", "SLASHER"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "TALKSHOW": {
        "label": {"DE": "Talkshow", "EXYU": "Tok šou", "EN": "Talk Show", "SI": "Pogovorna oddaja", "MK": "Tok-šou"},
        "keywords": [
            "TALK SHOW", "TALKSHOW", "LATE NIGHT", "TONIGHT SHOW", "THIS MORNING"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "WIRTSCHAFT": {
        "label": {"DE": "Wirtschaft & Finanzen", "EXYU": "Biznis i finansije", "EN": "Business & Finance", "SI": "Posel in finance", "MK": "Biznis i finansii"},
        "keywords": [
            "BUSINESS", "FINANCE", "MONEY", "MARKETS", "WIRTSCHAFT", "BIZNIS"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "LIFESTYLE": {
        "label": {"DE": "Lifestyle", "EXYU": "Lifestyle", "EN": "Lifestyle", "SI": "Življenjski slog", "MK": "Lifestyle"},
        "keywords": [
            "LIFESTYLE", "STYLE", "FASHION", "HOME", "LIVING", "HGTV", "TLC", "BEAUTY", "DESIGN", "WOMAN", "LADY", "W NETWORK", "OPRAH", "OWN", "LIFETIME", "DECOR", "STIL"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "REGIONAL": {
        "label": {"DE": "Regional", "EXYU": "Regionalni program", "EN": "Regional", "SI": "Regionalni program", "MK": "Regionalna programa"},
        "keywords": [
            "REGIONAL", "LOKAL", "LOKALNA"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "UNTERHALTUNG": {
        "label": {"DE": "Unterhaltung", "EXYU": "Zabava", "EN": "Entertainment", "SI": "Zabava", "MK": "Zabava"},
        "keywords": [
            "RTL", "VOX", "SAT", "PRO7", "PRO SIEBEN", "KABEL", "NOVA", "PINK", "HAPPY", "HAYAT", "OBN", "FACE", "ATV", "KANAL", "TV", "FOX", "ABC", "CBS", "NBC", "SHOW", "PLUS", "PRIME", "ZABAVA", "ITV", "CHANNEL 4", "CHANNEL4", "CHANNEL 5", "CHANNEL5", "E4", "MORE4", "DAVE", "ITV2", "ITV3", "ITV4", "5STAR", "5 STAR", "DIREKT", "MREZA PLUS", "K1", "K3", "MTEL"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "GARTEN_HEIM": {
        "label": {"DE": "Garten & Heim", "EXYU": "Vrt i dom", "EN": "Home & Garden", "SI": "Vrt in dom", "MK": "Gradina i dom"},
        "keywords": [
            "GARDEN", "GARDENING", "HGTV", "HOME AND GARDEN", "DIY", "MONTY DON", "HOME NETWORK", "PROPERTY", "RENOVATION", "VRT", "DOM"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "WELTRAUM_WISSENSCHAFT": {
        "label": {"DE": "Weltraum & Wissenschaft", "EXYU": "Svemir i nauka", "EN": "Space & Science", "SI": "Vesolje in znanost", "MK": "Vselena i nauka"},
        "keywords": [
            "SPACE", "NASA", "COSMOS", "UNIVERSE", "GALAXY", "SVEMIR", "VESOLJE", "VSELENA"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "MODE": {
        "label": {"DE": "Mode", "EXYU": "Moda", "EN": "Fashion", "SI": "Moda", "MK": "Moda"},
        "keywords": [
            "FASHION", "VOGUE", "GLAMOUR", "FASHION TV", "FASHIONTV", "STYLE NETWORK", "MODA"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "GLUECKSSPIEL": {
        "label": {"DE": "Glücksspiel", "EXYU": "Kockanje", "EN": "Gambling", "SI": "Igre na srečo", "MK": "Kockanje"},
        "keywords": [
            "CASINO", "POKER", "GAMBLING", "LOTTO", "BETTING", "BET365", "KOCKANJE"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
        ]
    },

    "EROTIK": {
        "label": {"DE": "Erotik", "EXYU": "Erotika", "EN": "Adult", "SI": "Erotika", "MK": "Erotika"},
        "keywords": [
            "XXX", "EROTIC", "EROTIK", "EROTIKA", "PLAYBOY", "VENUS", "HUSTLER", "PRIVATE TV", "BRAZZERS"
        ],
        "DE": [
            "{sender} zeigt {label} rund um die Uhr.",
            "{label} live und aktuell bei {sender}.",
            "{sender} - Ihr Sender fuer {label}.",
            "Erleben Sie {label} jederzeit auf {sender}.",
            "{sender} - immer aktuell mit {label}.",
            "Schalten Sie ein und genießen Sie {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label} tokom cijelog dana.",
            "{label} uzivo i aktuelno na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Pratite {label} u svakom trenutku na {sender}.",
            "{sender} - uvijek aktuelno sa {label}.",
            "Ukljucite se i uzivajte u {label} na {sender}."
        ],
        "SI": [
            "{sender} prinaša {label} 24 ur na dan.",
            "{label} v živo in ažurno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Spremljajte {label} kadarkoli na {sender}.",
            "{sender} - vedno sveže z {label}.",
            "Prižgite in uživajte v {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label} tekom celiot den.",
            "{label} vo živo i aktuelno na {sender}.",
            "{sender} - vaš kanal za {label}.",
            "Sledete {label} vo sekoe vreme na {sender}.",
            "{sender} - sekogash aktuelno so {label}.",
            "Vklucete se i uzivajte vo {label} na {sender}."
        ],
        "EN": [
            "{sender} brings you {label} around the clock.",
            "{label} live and up to date on {sender}.",
            "{sender} - your channel for {label}.",
            "Enjoy {label} anytime on {sender}.",
            "{sender} - always up to date with {label}.",
            "Tune in and enjoy {label} on {sender}."
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
    "EROTIK", "GLUECKSSPIEL", "WELTRAUM_WISSENSCHAFT", "MODE", "GARTEN_HEIM",
    "WISSEN", "NATUR", "JAGD_FISCHEREI", "DOKU", "MILITAER", "AUTO", "REISEN", "KOCHEN",
    "MUSIK", "COMEDY", "RELIGION", "HORROR", "KRIMI", "TALKSHOW",
    "WIRTSCHAFT", "GESUNDHEIT", "TECH",
    "SPORT", "SERIEN", "FILM",
    "LIFESTYLE", "REGIONAL", "UNTERHALTUNG"
]

DE_STANDARD = [
    "{sender} sendet abwechslungsreiches Programm rund um die Uhr.",
    "Vielseitige Unterhaltung erwartet Sie bei {sender}.",
    "{sender} - Programm fuer die ganze Familie.",
    "Schalten Sie ein bei {sender} fuer kurzweiliges Programm.",
    "{sender} - rund um die Uhr fuer Sie auf Sendung.",
    "Verpassen Sie nichts - {sender} begleitet Sie durch den Tag."
]

EXYU_STANDARD = [
    "{sender} emituje raznovrstan program tokom cijelog dana.",
    "Raznovrsna zabava vas ocekuje na {sender}.",
    "{sender} - program za cijelu porodicu.",
    "Ukljucite se na {sender} za zanimljiv program.",
    "{sender} - na programu 24 sata dnevno.",
    "Ne propustite nista - {sender} vas prati tokom dana."
]

SI_STANDARD = [
    "{sender} predvaja raznolik program 24 ur na dan.",
    "Pestra zabava vas čaka na {sender}.",
    "{sender} - program za vso družino.",
    "Prižgite {sender} za zanimiv program.",
    "{sender} - na sporedu 24 ur na dan.",
    "Ne zamudite nič - {sender} vas spremlja skozi dan."
]

MK_STANDARD = [
    "{sender} emituva raznovidna programa tekom celiot den.",
    "Raznovidna zabava ve čeka na {sender}.",
    "{sender} - programa za celoto semejstvo.",
    "Vklučete se na {sender} za interesna programa.",
    "{sender} - na programa 24 časa na den.",
    "Ne propuštajte ništo - {sender} ve prati tekom denot."
]

EN_STANDARD = [
    "{sender} broadcasts varied programming around the clock.",
    "Varied entertainment awaits you on {sender}.",
    "{sender} - programming for the whole family.",
    "Tune in to {sender} for engaging programming.",
    "{sender} - on air 24 hours a day.",
    "Don't miss out - {sender} keeps you company all day long."
]


# ==========================================================
# Automatische Beschreibung
# ==========================================================

EXYU_LAENDER = [
    "BA", "RS", "HR", "ME", "CG", "MNE", "MNG", "MO",
    "EXYU", "BS", "SRB", "SRBIJA", "HRVATSKA", "BIH", "CRNA GORA",
    "KOSOVO", "KS",
    "SANDZAK", "SANDŽAK"
]

# Slowenisch und Mazedonisch waren frueher Teil des gemeinsamen
# EXYU-Textpools (mit BA/RS/HR/ME geteilt), obwohl sie eigenstaendige
# Sprachen sind (nicht nur Dialektunterschiede wie bei den anderen 4).
# Bekommen daher jetzt eigene Laenderlisten + eigene Texte.
SI_LAENDER = ["SI", "SLOVENIJA", "SLOVENIA"]
MK_LAENDER = ["MK", "MAKEDONIJA", "SEVERNA MAKEDONIJA", "MACEDONIA", "NORTH MACEDONIA"]

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

    # Sprachzuordnung ueber die zentrale Funktion (inkl. SI/MK), statt
    # die Laendererkennung ein zweites Mal hier zu duplizieren.
    sprache = sprache_fuer_land(land)

    sender_upper = sender.upper()
    hash_wert = sum(ord(c) for c in sender)

    for kategorie_key in KATEGORIE_PRIORITAET:
        daten = KATEGORIEN[kategorie_key]

        for keyword in daten["keywords"]:

            if re.search(rf"\b{re.escape(keyword)}\b", sender_upper):
                varianten = daten[sprache]
                nummer = hash_wert % len(varianten)
                label = daten["label"][sprache]
                text = varianten[nummer].format(sender=sender, label=label)
                return text, kategorie_key

    if sprache == "DE":
        texte = DE_STANDARD

    elif sprache == "EXYU":
        texte = EXYU_STANDARD

    elif sprache == "SI":
        texte = SI_STANDARD

    elif sprache == "MK":
        texte = MK_STANDARD

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

FALLBACK_LABEL = {"DE": "Programm", "EXYU": "Program", "SI": "Program", "MK": "Programa", "EN": "Programme"}

# Wochentags-Kuerzel je Sprache fuer den Datumsbezug im Sendetitel
# (z.B. "Mo 27.07: Sport am Abend"). Index 0 = Montag (passend zu
# date.weekday()).
WOCHENTAGE = {
    "DE": ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    "EXYU": ["Pon", "Uto", "Sri", "Čet", "Pet", "Sub", "Ned"],
    "SI": ["Pon", "Tor", "Sre", "Čet", "Pet", "Sob", "Ned"],
    "MK": ["Pon", "Vto", "Sre", "Čet", "Pet", "Sab", "Ned"],
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
        "NACHT": ["{label} in der Nacht", "Best of {label}", "{label} Nachtprogramm", "{label} bis in die Nacht", "Nachtschicht: {label}"],
        "MORGEN": ["{label} am Morgen", "Morgenmagazin: {label}", "{label} zum Frühstück", "Guten Morgen mit {label}", "{label} Frühprogramm"],
        "VORMITTAG": ["{label} Vormittag", "{label} Magazin", "Vormittagsprogramm: {label}", "{label} am Vormittag", "{label} bis Mittag"],
        "MITTAG": ["{label} zur Mittagszeit", "{label} Mittagsprogramm", "Mittagsmagazin: {label}", "{label} zum Mittag", "{label} in der Mittagspause"],
        "NACHMITTAG": ["{label} am Nachmittag", "{label} Spezial", "Nachmittagsprogramm: {label}", "{label} zum Nachmittag", "{label} bis zum Abend"],
        "ABEND": ["{label} Primetime", "{label} am Abend", "Abendprogramm: {label}", "{label} zur besten Sendezeit", "{label} am Vorabend"],
        "SPAETABEND": ["{label} Spätprogramm", "{label} Late Night", "Spätabend: {label}", "{label} nach Mitternacht", "{label} zur späten Stunde"],
    },
    "EXYU": {
        "NACHT": ["{label} tokom noći", "Najbolje iz: {label}", "{label} noćni program", "{label} do kasno u noć", "Noćna smjena: {label}"],
        "MORGEN": ["{label} ujutro", "Jutarnji program: {label}", "{label} uz doručak", "Dobro jutro uz {label}", "{label} rani program"],
        "VORMITTAG": ["{label} prijepodne", "{label} magazin", "Prijepodnevni program: {label}", "{label} do podneva", "{label} pred podne"],
        "MITTAG": ["{label} u podne", "{label} program", "Podnevni magazin: {label}", "{label} za vrijeme pauze", "{label} u podnevnim satima"],
        "NACHMITTAG": ["{label} popodne", "{label} specijal", "Popodnevni program: {label}", "{label} do večeri", "{label} u popodnevnim satima"],
        "ABEND": ["{label} večernji program", "{label} u udarnom terminu", "Večernji program: {label}", "{label} predveče", "{label} u najgledanijem terminu"],
        "SPAETABEND": ["{label} kasno navečer", "{label} noćni program", "Kasna večer: {label}", "{label} poslije ponoći", "{label} u kasnim satima"],
    },
    "SI": {
        "NACHT": ["{label} ponoči", "Najboljše: {label}", "{label} nočni program", "{label} pozno v noč", "Nočna izmena: {label}"],
        "MORGEN": ["{label} zjutraj", "Jutranji program: {label}", "{label} ob zajtrku", "Dobro jutro z {label}", "{label} zgodnji program"],
        "VORMITTAG": ["{label} dopoldne", "{label} magazin", "Dopoldanski program: {label}", "{label} do poldneva", "{label} pred poldnevom"],
        "MITTAG": ["{label} opoldne", "{label} program", "Poldanski magazin: {label}", "{label} v odmoru", "{label} v poldanskih urah"],
        "NACHMITTAG": ["{label} popoldne", "{label} posebno", "Popoldanski program: {label}", "{label} do večera", "{label} v popoldanskih urah"],
        "ABEND": ["{label} zvečer", "{label} ob najboljšem času", "Večerni program: {label}", "{label} predvečer", "{label} v najbolj gledanem terminu"],
        "SPAETABEND": ["{label} pozno zvečer", "{label} nočni program", "Pozni večer: {label}", "{label} po polnoči", "{label} v poznih urah"],
    },
    "MK": {
        "NACHT": ["{label} navečer", "Najdobro od: {label}", "{label} nokna programa", "{label} do docna vo nokta", "Nokna smena: {label}"],
        "MORGEN": ["{label} nautro", "Utrinska programa: {label}", "{label} na pojadok", "Dobro utro so {label}", "{label} rana programa"],
        "VORMITTAG": ["{label} pretpladne", "{label} magazin", "Pretpladnevna programa: {label}", "{label} do pladne", "{label} pred pladne"],
        "MITTAG": ["{label} napladne", "{label} programa", "Pladnevna programa: {label}", "{label} vo pauza", "{label} vo pladnevni časovi"],
        "NACHMITTAG": ["{label} popladne", "{label} specijal", "Popladnevna programa: {label}", "{label} do večer", "{label} vo popladnevni časovi"],
        "ABEND": ["{label} večerna programa", "{label} udaren termin", "Večerna programa: {label}", "{label} predvečer", "{label} vo najgledaniot termin"],
        "SPAETABEND": ["{label} docna navečer", "{label} nokna programa", "Docna večer: {label}", "{label} po polnok", "{label} vo docni časovi"],
    },
    "EN": {
        "NACHT": ["{label} Overnight", "Best of {label}", "{label} Night Program", "{label} Through the Night", "Night Shift: {label}"],
        "MORGEN": ["{label} in the Morning", "Morning {label}", "{label} at Breakfast", "Good Morning {label}", "Early {label}"],
        "VORMITTAG": ["{label} Late Morning", "{label} Magazine", "Late Morning {label}", "{label} Before Noon", "{label} Mid-Morning"],
        "MITTAG": ["{label} at Noon", "Midday {label}", "{label} Lunch Hour", "{label} at Midday", "Noon {label}"],
        "NACHMITTAG": ["{label} in the Afternoon", "{label} Special", "Afternoon {label}", "{label} Into the Evening", "{label} Mid-Afternoon"],
        "ABEND": ["{label} Primetime", "{label} Tonight", "Evening {label}", "{label} at Prime Time", "{label} This Evening"],
        "SPAETABEND": ["Late Night {label}", "{label} After Hours", "{label} Late Show", "{label} Past Midnight", "{label} in the Late Hours"],
    },
}

# ==========================================================
# Kategorie-spezifische Titelwoerter (statt des generischen Labels)
#
# Fuer ausgewaehlte Kategorien wird im Sendetitel ein konkreteres,
# programmartigeres Wort statt des reinen Kategorie-Labels verwendet
# (z.B. "Sport-Highlights" statt nur "Sport", "Kochshow" statt
# "Kochen"). Kategorien ohne eigenen Eintrag hier fallen weiterhin
# auf ihr normales Label zurueck (siehe titelwort_fuer_kategorie()).
# ==========================================================
KATEGORIE_TITELWORT = {
    "SPORT": {"DE": ["Sport-Highlights", "Sportmagazin"], "EXYU": ["Sportski pregled", "Sportski magazin"], "EN": ["Sports Highlights", "Sports Roundup"], "SI": ["Športni pregled", "Športna oddaja"], "MK": ["Sportski pregled", "Sportska emisija"]},
    "KOCHEN": {"DE": ["Kochshow", "Kulinarik-Magazin"], "EXYU": ["Kulinarska emisija", "Kulinarski magazin"], "EN": ["Cooking Show", "Culinary Feature"], "SI": ["Kuharska oddaja", "Kulinarična oddaja"], "MK": ["Kulinarska emisija", "Kulinarska programa"]},
    "NEWS": {"DE": ["Nachrichtenüberblick", "Nachrichtenmagazin"], "EXYU": ["Pregled vijesti", "Informativni program"], "EN": ["News Roundup", "News Update"], "SI": ["Pregled novic", "Informativna oddaja"], "MK": ["Pregled na vesti", "Informativna programa"]},
    "MUSIK": {"DE": ["Musikshow", "Musikmagazin"], "EXYU": ["Muzička emisija", "Muzički program"], "EN": ["Music Show", "Music Special"], "SI": ["Glasbena oddaja", "Glasbeni magazin"], "MK": ["Muzička emisija", "Muzička programa"]},
    "FILM": {"DE": ["Spielfilm", "Filmklassiker"], "EXYU": ["Igrani film", "Filmski klasik"], "EN": ["Feature Film", "Movie Classic"], "SI": ["Igrani film", "Filmska klasika"], "MK": ["Igran film", "Filmski klasik"]},
    "SERIEN": {"DE": ["Serienmarathon", "Serien-Doppelfolge"], "EXYU": ["Serijski maraton", "Duple epizode"], "EN": ["Series Marathon", "Double Episode"], "SI": ["Serijski maraton", "Dvojna epizoda"], "MK": ["Serijski maraton", "Dvojna epizoda"]},
    "GAMING": {"DE": ["Gaming-Show", "Gaming-Magazin"], "EXYU": ["Gejming emisija", "Gejming magazin"], "EN": ["Gaming Show", "Gaming Roundup"], "SI": ["Igričarska oddaja", "Igričarski magazin"], "MK": ["Gejming emisija", "Gejming magazin"]},
    "REISEN": {"DE": ["Reisemagazin", "Reisereportage"], "EXYU": ["Putopisni magazin", "Putopisna reportaža"], "EN": ["Travel Magazine", "Travel Report"], "SI": ["Potopisni magazin", "Potopisna reportaža"], "MK": ["Patopisen magazin", "Patopisna reportaža"]},
    "AUTO": {"DE": ["Automagazin", "Motorsport-Magazin"], "EXYU": ["Auto magazin", "Motosport magazin"], "EN": ["Auto Show", "Motoring Show"], "SI": ["Avto magazin", "Avtomobilistična oddaja"], "MK": ["Avto magazin", "Avtomobilska programa"]},
    "COMEDY": {"DE": ["Comedy-Show", "Comedy-Spezial"], "EXYU": ["Komedijaška emisija", "Komedijaški specijal"], "EN": ["Comedy Show", "Comedy Special"], "SI": ["Humoristična oddaja", "Humoristični posebni program"], "MK": ["Komedijaška emisija", "Komedijaski specijal"]},
    "KRIMI": {"DE": ["Krimi des Tages", "Krimi-Doppelfolge"], "EXYU": ["Kriminalistička priča", "Kriminalistička dvostruka epizoda"], "EN": ["Crime Feature", "Crime Double Bill"], "SI": ["Kriminalka dneva", "Kriminalna dvojna epizoda"], "MK": ["Kriminalistička priča", "Kriminalna dvojna epizoda"]},
    "HORROR": {"DE": ["Horrornacht", "Horror-Klassiker"], "EXYU": ["Horor noć", "Horor klasik"], "EN": ["Horror Night", "Horror Classic"], "SI": ["Grozljiva noč", "Grozljivka klasika"], "MK": ["Horor noќ", "Horor klasik"]},
    "TALKSHOW": {"DE": ["Talkrunde", "Late-Night-Talk"], "EXYU": ["Tok šou emisija", "Kasnonoćni tok šou"], "EN": ["Talk Round", "Late Night Talk"], "SI": ["Pogovorni krog", "Poznovečerni pogovor"], "MK": ["Tok-šou emisija", "Docnovečerno tok-šou"]},
    "WIRTSCHAFT": {"DE": ["Wirtschaftsreport", "Börsenmagazin"], "EXYU": ["Poslovni izvještaj", "Berzanski magazin"], "EN": ["Business Report", "Markets Update"], "SI": ["Poslovno poročilo", "Borzni magazin"], "MK": ["Biznis izveštaj", "Berzanski magazin"]},
    "REALITY": {"DE": ["Reality-Highlights", "Reality-Spezial"], "EXYU": ["Rijaliti pregled", "Rijaliti specijal"], "EN": ["Reality Highlights", "Reality Special"], "SI": ["Resničnostni pregled", "Resničnostni posebni program"], "MK": ["Rijaliti pregled", "Rijaliti specijal"]},
    "DOKU": {"DE": ["Doku-Highlight", "Doku-Reportage"], "EXYU": ["Dokumentarni pregled", "Dokumentarna reportaža"], "EN": ["Documentary Feature", "Documentary Special"], "SI": ["Dokumentarni izbor", "Dokumentarna reportaža"], "MK": ["Dokumentaren izbor", "Dokumentarna reportaža"]},
    "KINDER": {"DE": ["Kinderprogramm", "Kindershow"], "EXYU": ["Dječiji program", "Dječija emisija"], "EN": ["Kids Show", "Kids Special"], "SI": ["Otroški program", "Otroška oddaja"], "MK": ["Detska programa", "Detska emisija"]},
    "RADIO": {"DE": ["Radioshow", "Radiomagazin"], "EXYU": ["Radio emisija", "Radio magazin"], "EN": ["Radio Show", "Radio Special"], "SI": ["Radijska oddaja", "Radijski magazin"], "MK": ["Radio emisija", "Radio magazin"]},
    "SHOPPING": {"DE": ["Shopping-Show", "Teleshopping"], "EXYU": ["Šoping emisija", "TV šoping"], "EN": ["Shopping Show", "Teleshopping"], "SI": ["Nakupovalna oddaja", "TV nakupovanje"], "MK": ["Emisija za kupuvanje", "TV kupuvanje"]},
    "WISSEN": {"DE": ["Wissensmagazin", "Wissenschaftsmagazin"], "EXYU": ["Edukativni magazin", "Naučni magazin"], "EN": ["Knowledge Magazine", "Science Feature"], "SI": ["Izobraževalni magazin", "Znanstveni magazin"], "MK": ["Edukativen magazin", "Naučna programa"]},
    "NATUR": {"DE": ["Naturdokumentation", "Tierdokumentation"], "EXYU": ["Dokumentarac o prirodi", "Dokumentarac o životinjama"], "EN": ["Nature Documentary", "Wildlife Feature"], "SI": ["Naravoslovni dokumentarec", "Dokumentarec o živalih"], "MK": ["Dokumentarec za priroda", "Dokumentarec za životni"]},
    "RELIGION": {"DE": ["Andacht", "Gottesdienst"], "EXYU": ["Vjerski program", "Bogosluženje"], "EN": ["Devotional Program", "Church Service"], "SI": ["Verski program", "Bogoslužje"], "MK": ["Religiozna programa", "Bogosluženie"]},
    "WETTER": {"DE": ["Wetterbericht", "Wetteraussichten"], "EXYU": ["Vremenska prognoza", "Vremenski izgledi"], "EN": ["Weather Report", "Weather Outlook"], "SI": ["Vremenska napoved", "Vremenski obeti"], "MK": ["Vremenska prognoza", "Vremenski izgledi"]},
    "JAGD_FISCHEREI": {"DE": ["Jagdreport", "Angelmagazin"], "EXYU": ["Lovački izvještaj", "Ribolovni magazin"], "EN": ["Hunting Report", "Fishing Feature"], "SI": ["Lovsko poročilo", "Ribiški magazin"], "MK": ["Lovački izveštaj", "Ribolovna programa"]},
    "MILITAER": {"DE": ["Kriegsdokumentation", "Militärgeschichte"], "EXYU": ["Ratni dokumentarac", "Vojna istorija"], "EN": ["War Documentary", "Military History"], "SI": ["Vojni dokumentarec", "Vojaška zgodovina"], "MK": ["Voen dokumentarec", "Vojna istorija"]},
    "FAMILIE": {"DE": ["Familienfilm", "Familienabend"], "EXYU": ["Porodični film", "Porodično veče"], "EN": ["Family Feature", "Family Night"], "SI": ["Družinski film", "Družinski večer"], "MK": ["Semeen film", "Semeen večer"]},
    "ANIME": {"DE": ["Anime-Marathon", "Anime-Spezial"], "EXYU": ["Anime maraton", "Anime specijal"], "EN": ["Anime Marathon", "Anime Special"], "SI": ["Anime maraton", "Anime posebni program"], "MK": ["Anime maraton", "Anime specijal"]},
    "GESUNDHEIT": {"DE": ["Fitnessprogramm", "Wellness-Magazin"], "EXYU": ["Fitnes program", "Wellness magazin"], "EN": ["Fitness Program", "Wellness Feature"], "SI": ["Fitnes program", "Wellness oddaja"], "MK": ["Fitnes programa", "Wellness programa"]},
    "TECH": {"DE": ["Technikmagazin", "Innovationsmagazin"], "EXYU": ["Tehnički magazin", "Magazin o inovacijama"], "EN": ["Tech Magazine", "Innovation Feature"], "SI": ["Tehnološki magazin", "Magazin o inovacijah"], "MK": ["Tehnološki magazin", "Magazin za inovacii"]},
    "LIFESTYLE": {"DE": ["Lifestyle-Magazin", "Trend-Magazin"], "EXYU": ["Lifestyle magazin", "Magazin o trendovima"], "EN": ["Lifestyle Magazine", "Trend Report"], "SI": ["Lifestyle magazin", "Magazin o trendih"], "MK": ["Lifestyle magazin", "Magazin za trendovi"]},
    "REGIONAL": {"DE": ["Regionalmagazin", "Lokalmagazin"], "EXYU": ["Regionalni magazin", "Lokalni magazin"], "EN": ["Regional Magazine", "Local Feature"], "SI": ["Regionalni magazin", "Lokalni magazin"], "MK": ["Regionalna programa", "Lokalna programa"]},
    "UNTERHALTUNG": {"DE": ["Showprogramm", "Abendshow"], "EXYU": ["Šou program", "Večernji šou"], "EN": ["Entertainment Show", "Evening Show"], "SI": ["Zabavni program", "Večerna oddaja"], "MK": ["Zabavna programa", "Večerno šou"]},
}


# ==========================================================
# Vorbericht-Texte fuer DYN/Flo-Racing-Events, die spaeter am Tag
# noch bevorstehen (siehe generate_epg.py). Sprachabhaengig, damit
# EXYU/SI/MK/EN-Sender nicht faelschlich einen deutschen Text
# bekommen.
# ==========================================================
VORBERICHT_TEXTE = {
    "DE": {"praefix": "Vorbericht", "uhr": "Uhr", "in_kuerze": "in Kürze"},
    "EXYU": {"praefix": "Najava", "uhr": "h", "in_kuerze": "uskoro"},
    "SI": {"praefix": "Napoved", "uhr": "h", "in_kuerze": "kmalu"},
    "MK": {"praefix": "Najava", "uhr": "č", "in_kuerze": "naskoro"},
    "EN": {"praefix": "Preview", "uhr": "", "in_kuerze": "coming up soon"},
}


def vorbericht_text(sprache, event_titel, uhrzeit_str, ist_naechster_block):
    """Baut den Vorbericht-Text fuer ein spaeter am Tag bevorstehendes
    Event in der zur Sprache passenden Form. Ist es der Block
    UNMITTELBAR vor dem Event (ist_naechster_block=True), wird statt
    der festen Uhrzeit ein "in Kuerze"-Hinweis verwendet - wirkt im
    Player dynamischer als bei jedem frueheren Block dieselbe feste
    Zeit zu wiederholen."""
    texte = VORBERICHT_TEXTE.get(sprache, VORBERICHT_TEXTE["EN"])

    if ist_naechster_block:
        zeit_teil = texte["in_kuerze"]
    else:
        uhr_suffix = f" {texte['uhr']}" if texte["uhr"] else ""
        zeit_teil = f"{uhrzeit_str}{uhr_suffix}"

    return f"{texte['praefix']}: {event_titel} ({zeit_teil})"


def titelwort_fuer_kategorie(kategorie_key, sprache, fallback_label, hash_wert=0, tag_index=0):
    """Liefert das spezifischere Titelwort fuer eine Kategorie, falls
    vorhanden, sonst das normale Kategorie-Label als Fallback (auch
    wenn die Kategorie zwar existiert, aber fuer die konkrete Sprache
    kein eigenes Titelwort hinterlegt ist).

    Jede Kategorie/Sprache hat mehrere Titelwort-Varianten (Liste).
    Die Auswahl erfolgt deterministisch ueber hash_wert + tag_index,
    damit dieselbe Kategorie nicht an jedem Tag exakt gleich heisst,
    aber innerhalb eines Tages stabil bleibt (kein Flackern)."""
    if kategorie_key and kategorie_key in KATEGORIE_TITELWORT:
        varianten = KATEGORIE_TITELWORT[kategorie_key].get(sprache)
        if not varianten:
            return fallback_label
        nummer = (hash_wert + tag_index) % len(varianten)
        return varianten[nummer]
    return fallback_label


def sprache_fuer_land(land):
    land_code = land.split("(")[0].strip().upper()
    if land_code == "DE":
        return "DE"
    elif land_code in SI_LAENDER:
        return "SI"
    elif land_code in MK_LAENDER:
        return "MK"
    elif land_code in EXYU_LAENDER:
        return "EXYU"
    else:
        return "EN"


def sendetitel(kategorie_key, land, hash_wert, tageszeit, datum=None, tag_index=0):
    """Erzeugt einen realistischeren, tageszeitabhaengigen Sendetitel
    statt einfach nur den Sendernamen zu wiederholen. Die Auswahl der
    Vorlage erfolgt deterministisch ueber den Sender-Hash KOMBINIERT
    mit tag_index (0 = heute, 1 = morgen, ...): derselbe Sender
    bekommt an einem gegebenen Tag bei jedem Lauf wieder dieselbe
    Variante (kein "Flackern" innerhalb eines Tages), wechselt aber
    kontrolliert von Tag zu Tag, statt ueber die gesamte EPG-Laufzeit
    immer exakt dieselbe Formulierung zu zeigen.

    Wird ein "datum" (date/datetime-Objekt) uebergeben, wird zusaetzlich
    ein echter Datumsbezug vorangestellt (z.B. "Mo 27.07: Sport am
    Abend") statt nur des generischen Tageszeit-Titels."""

    sprache = sprache_fuer_land(land)

    if kategorie_key:
        label = KATEGORIEN[kategorie_key]["label"][sprache]
    else:
        label = FALLBACK_LABEL[sprache]

    # Fuer ausgewaehlte Kategorien wird statt des generischen Labels
    # ein spezifischeres Titelwort verwendet (z.B. "Sport-Highlights"
    # statt nur "Sport"), siehe KATEGORIE_TITELWORT weiter oben.
    titelwort = titelwort_fuer_kategorie(kategorie_key, sprache, label, hash_wert=hash_wert, tag_index=tag_index)

    vorlagen = SENDETITEL_VORLAGEN[sprache][tageszeit]
    nummer = (hash_wert + len(tageszeit) + tag_index) % len(vorlagen)
    titel = vorlagen[nummer].format(label=titelwort)

    return datumspraefix(sprache, datum) + titel


def beschreibung_fuer_sender(kategorie_key, land, sender, hash_wert, tag_index=0):
    """Gibt die Beschreibung nur in der zum Sender-Land passenden
    Sprache zurueck (DE/EXYU/SI/MK/EN) - keine parallelen
    Mehrsprachen-Tags mehr, sondern wie urspruenglich eine Sprache
    pro Sender.

    tag_index (0 = heute, 1 = morgen, ...) fliesst zusaetzlich zum
    Sender-Hash in die Variantenauswahl ein: am selben Tag bleibt der
    Text stabil (kein Flackern zwischen Laeufen), wechselt aber
    kontrolliert von Tag zu Tag statt ueber die gesamte EPG-Laufzeit
    immer exakt gleich zu bleiben."""

    sprache = sprache_fuer_land(land)
    standard_texte = {"DE": DE_STANDARD, "EXYU": EXYU_STANDARD, "SI": SI_STANDARD, "MK": MK_STANDARD, "EN": EN_STANDARD}
    lang_code = {"DE": "de", "EXYU": "hr", "SI": "sl", "MK": "mk", "EN": "en"}[sprache]

    if kategorie_key:
        varianten = KATEGORIEN[kategorie_key][sprache]
        label = KATEGORIEN[kategorie_key]["label"][sprache]
    else:
        varianten = standard_texte[sprache]
        label = FALLBACK_LABEL[sprache]

    nummer = (hash_wert + tag_index) % len(varianten)
    # {label} wird nur befuellt, falls die Vorlage ihn nutzt (die
    # STANDARD-Fallback-Texte kommen ohne {label} aus).
    text = varianten[nummer].format(sender=sender, label=label)

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


# ==========================================================
# Normale (nicht durchgehend groSSgeschriebene) Anzeige von
# Kanalnamen, z.B. fuer DAZN-Sender, deren Name direkt als
# Sendungstitel/-beschreibung uebernommen wird (siehe
# generate_epg.py). Ein simples str.capitalize() je Wort wuerde
# bekannte Abkuerzungen wie "HD"/"DAZN"/"TV" haesslich verhunzen
# (z.B. "Dazn Bar 1 Hevc" oder "(dazn Stream)"), daher bleiben
# Woerter aus KANALNAME_ABKUERZUNGEN unveraendert groSS, der Rest
# wird normal kapitalisiert. Fuehrende/folgende Klammern bzw.
# Satzzeichen an einem Wort werden dabei erhalten.
# ==========================================================

KANALNAME_ABKUERZUNGEN = {
    "DAZN", "HD", "FHD", "UHD", "SD", "HEVC", "TV", "ACL", "RAW", "4K", "8K"
}


def kanalname_normal_geschrieben(name):
    """Formatiert einen (oft komplett groSSgeschriebenen) Kanalnamen
    lesbarer: normale Woerter werden kapitalisiert ("BAR" -> "Bar"),
    bekannte Abkuerzungen bleiben unveraendert groSS ("HD" bleibt
    "HD", "DAZN" bleibt "DAZN")."""
    if not name:
        return name

    worte = name.split(" ")
    ergebnis = []

    for wort in worte:
        praefix = ""
        suffix = ""
        kern = wort

        while kern and kern[0] in "([":
            praefix += kern[0]
            kern = kern[1:]
        while kern and kern[-1] in ")]":
            suffix = kern[-1] + suffix
            kern = kern[:-1]

        if kern.upper() in KANALNAME_ABKUERZUNGEN:
            kern_formatiert = kern.upper()
        else:
            kern_formatiert = kern.capitalize()

        ergebnis.append(praefix + kern_formatiert + suffix)

    return " ".join(ergebnis)


# ==========================================================
# Automatische Logo-Suche ueber die oeffentliche iptv-org-Datenbank
# (https://iptv-org.github.io/api/ - freie, offene Sammlung von
# Kanal-Metadaten inkl. Logos, unabhaengig von jeder konkreten
# IPTV-Quelle). Fehlt einem Sender in sender.txt/logo_only.txt ein
# Logo, wird hier versucht, per (fuzzy) Namensabgleich ein passendes
# Logo automatisch zuzuordnen - der eigentliche Netzwerk-Abruf der
# beiden JSON-Dateien (channels.json/logos.json) passiert bewusst in
# generate_epg.py, hier stehen nur die reinen, testbaren
# Verarbeitungsfunktionen ohne Seiteneffekte.
# ==========================================================

# Manche unserer "Land"-Kuerzel in sender.txt entsprechen nicht dem
# ISO-3166-1-Alpha-2-Code, den die iptv-org-Datenbank nutzt (z.B.
# "UK" statt "GB"). Nur fuer die Priorisierung von Treffern relevant,
# nicht fuer eine harte Filterung.
LAND_ISO_MAPPING = {"UK": "GB", "MO": "ME"}


def normalisiere_sendername(name):
    """Reduziert einen Sendernamen auf reine Grossbuchstaben/Ziffern
    (keine Leerzeichen, Satzzeichen, Akzente) fuer einen robusten
    Namensabgleich, z.B. "Al Jazeera Balkans FHD" und "AL JAZEERA
    BALKANS" ergeben denselben Schluessel."""
    if not name:
        return ""

    name = unicodedata.normalize("NFKD", name)
    name = "".join(zeichen for zeichen in name if not unicodedata.combining(zeichen))
    name = name.upper()
    name = re.sub(r"[^A-Z0-9]", "", name)
    return name


def baue_logo_index(channels_daten, logos_daten):
    """Baut aus den beiden iptv-org-JSON-Listen (channels.json/
    logos.json) zwei Nachschlage-Strukturen:
    - name_index: normalisierter Sendername -> Liste von (Kanal-ID, Land)
    - logo_by_id: Kanal-ID -> Logo-Eintrag (bevorzugt "in_use"-Logos)
    """
    logo_by_id = {}
    for eintrag in logos_daten:
        kanal_id = eintrag.get("channel")
        if not kanal_id:
            continue
        bisheriger = logo_by_id.get(kanal_id)
        if bisheriger is None or (eintrag.get("in_use") and not bisheriger.get("in_use")):
            logo_by_id[kanal_id] = eintrag

    name_index = {}
    for kanal in channels_daten:
        kanal_id = kanal.get("id")
        if not kanal_id:
            continue
        land = kanal.get("country") or ""
        namen = [kanal.get("name", "")] + list(kanal.get("alt_names") or [])
        for name in namen:
            schluessel = normalisiere_sendername(name)
            if not schluessel:
                continue
            name_index.setdefault(schluessel, []).append((kanal_id, land))

    return name_index, logo_by_id


def finde_logo(sender_name, land, name_index, logo_by_id, min_score=0.72):
    """Sucht fuer einen gegebenen Sendernamen ein passendes Logo in
    der iptv-org-Datenbank. Erst exakter Namensabgleich (nach
    Normalisierung), sonst unscharfer Abgleich (difflib) mit
    Mindest-Aehnlichkeit min_score. Treffer aus demselben Land werden
    bevorzugt, sind aber keine harte Bedingung (viele unserer
    Land-Kuerzel wie EXYU/TUBI/PRIME sind keine echten Laendercodes).
    Gibt die Logo-URL zurueck oder None, wenn nichts Passendes
    gefunden wurde."""
    schluessel = normalisiere_sendername(sender_name)
    if not schluessel or not name_index:
        return None

    land_iso = LAND_ISO_MAPPING.get(land, land)

    if schluessel in name_index:
        kandidaten = name_index[schluessel]
    else:
        aehnliche_schluessel = difflib.get_close_matches(
            schluessel, name_index.keys(), n=5, cutoff=min_score
        )
        if not aehnliche_schluessel:
            return None
        kandidaten = []
        for treffer in aehnliche_schluessel:
            kandidaten.extend(name_index[treffer])

    # Treffer aus demselben Land bevorzugen, falls vorhanden
    land_treffer = [kanal_id for kanal_id, l in kandidaten if l == land_iso]
    ziel_ids = land_treffer if land_treffer else [kanal_id for kanal_id, l in kandidaten]

    for kanal_id in ziel_ids:
        logo_eintrag = logo_by_id.get(kanal_id)
        if logo_eintrag and logo_eintrag.get("url"):
            return logo_eintrag["url"]

    return None

