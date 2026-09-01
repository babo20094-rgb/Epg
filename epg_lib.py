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
import zlib


def sender_hash(sender):
    """Liefert einen gut gestreuten, deterministischen Hash-Wert fuer
    einen Sendernamen (fuer die Auswahl von Text-/Titel-Varianten).

    Bewusst NICHT einfach sum(ord(c) for c in sender): bei
    durchnummerierten Sendern wie "KIDS 1", "KIDS 2", "KIDS 3", ...
    unterscheidet sich der Name nur in einer Ziffer, wodurch die
    Zeichensumme (und damit die gewaehlte Textvariante) exakt um 1 pro
    Sender steigt - die Vorlagen liefen dann strikt der Reihe nach
    durch statt "zufaellig" zu wirken (sichtbar z.B. bei den
    VODAFONE-GO-Kanaelen). zlib.crc32 streut auch bei minimalen
    Namensunterschieden gut, bleibt aber deterministisch (gleicher
    Sender -> gleicher Wert bei jedem Lauf)."""
    return zlib.crc32(sender.encode("utf-8"))


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
            "{label} live auf {sender}.",
            "{label} nonstop bei {sender}.",
            "{label} den ganzen Tag auf {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{sender}: {label} pur."
        ],
        "EXYU": [
            "Non-stop {label} na {sender}.",
            "{sender} predstavlja {label}.",
            "{sender} donosi {label}.",
            "{label} bez pauze na {sender}.",
            "{label} uzivo na {sender}.",
            "Cijeli dan {label} na {sender}."
        ],
        "SI": [
            "{sender}: {label} brez prekinitve.",
            "{sender}: {label} vsako uro.",
            "Vedno sveze: {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "Ves dan {label} na {sender}.",
            "{sender} predstavlja {label}."
        ],
        "MK": [
            "{label} cel den na {sender}.",
            "{sender}: {label} bez prekin.",
            "{label} 24 casa na den.",
            "{label} nonstop na {sender}.",
            "{label} vo zivo na {sender}.",
            "Cel den {label} na {sender}."
        ],
        "EN": [
            "{label} live on {sender}.",
            "Nonstop {label} on {sender}.",
            "All day {label} on {sender}.",
            "{sender} presents {label}.",
            "{sender}: {label} every hour.",
            "{sender}: {label} nonstop."
        ]
    },

    "NEWS": {
        "label": {"DE": "Nachrichten", "EXYU": "Vijesti", "EN": "News", "SI": "Novice", "MK": "Vesti"},
        "keywords": [
            "NEWS", "CNN", "BBC NEWS", "SKY NEWS", "AL JAZEERA", "N24", "NTV", "WELT", "EURONEWS", "FRANCE 24", "BLOOMBERG", "DW", "CNBC", "FOX NEWS", "MSNBC", "RTRS", "RTS", "HRT", "BHT", "N1", "VIJESTI", "DNEVNIK", "ABC NEWS", "ITV NEWS", "GB NEWS", "TALKTV", "TALK TV", "C-SPAN", "NEWSMAX", "OANN", "PHOENIX", "TAGESSCHAU", "ARD", "ZDFINFO", "CHANNEL 4 NEWS", "SKY NEWS ARABIA", "KLAN", "RTV21", "MREZA", "PINK VIJESTI", "K3", "NOVA VIJESTI", "PBS NEWSHOUR"
        ],
        "DE": [
            "{label} jederzeit bei {sender}.",
            "{label} live auf {sender}.",
            "{sender} bringt {label}.",
            "Rund um die Uhr {label} auf {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{label} ohne Unterbrechung auf {sender}."
        ],
        "EXYU": [
            "{sender} predstavlja {label}.",
            "{label} uzivo na {sender}.",
            "{label} u svako doba na {sender}.",
            "Cijeli dan {label} na {sender}.",
            "{label} cijeli dan na {sender}.",
            "Uvijek aktuelno: {label} na {sender}."
        ],
        "SI": [
            "Vedno sveze: {label} na {sender}.",
            "{label} brez premora na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender} predstavlja {label}.",
            "{sender}: {label} vsako uro.",
            "{sender}: {label} brez prekinitve."
        ],
        "MK": [
            "Sekogas aktuelno: {label} na {sender}.",
            "{label} vo sekoe vreme na {sender}.",
            "{label} cel den na {sender}.",
            "{label} 24 casa na den.",
            "{label} nonstop na {sender}.",
            "{label} vo zivo na {sender}."
        ],
        "EN": [
            "Always on: {label} on {sender}.",
            "{sender} brings you {label}.",
            "{label} anytime on {sender}.",
            "All day {label} on {sender}.",
            "{sender} presents {label}.",
            "{label} live on {sender}."
        ]
    },

    "KINDER": {
        "label": {"DE": "Kinder", "EXYU": "Dječiji program", "EN": "Kids", "SI": "Otroški program", "MK": "Detska programa"},
        "keywords": [
            "KIDS", "KID", "KINDER", "JR", "JUNIOR", "DISNEY", "CARTOON", "CARTOONS", "NICKELODEON", "NICK", "BOOMERANG", "BABY", "TOON", "CBEEBIES", "MINIMAX", "TINY", "POPCORN", "GULLI", "DJECA", "CRTANI", "CBBC", "PBS KIDS", "MILKSHAKE", "BABY TV", "BABYTV", "SUPER RTL", "SUPERRTL", "KIKA", "PANDA", "DUCK TV", "MINI", "PLANETA DJECA"
        ],
        "DE": [
            "{label} jederzeit bei {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "Non-Stop {label} auf {sender}.",
            "{label} live auf {sender}.",
            "{label} den ganzen Tag auf {sender}.",
            "{label} rund um die Uhr."
        ],
        "EXYU": [
            "{sender} donosi {label}.",
            "{label} uzivo na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{label} u svako doba na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} svakog sata."
        ],
        "SI": [
            "{label} nonstop na {sender}.",
            "{label} ves dan na {sender}.",
            "Vedno sveze: {label} na {sender}.",
            "{label} brez premora na {sender}.",
            "{sender} prinasa {label}.",
            "{sender} predstavlja {label}."
        ],
        "MK": [
            "{sender} pretstavuva {label}.",
            "{sender}: {label} bez prekin.",
            "{label} vo zivo na {sender}.",
            "{label} bez pauza na {sender}.",
            "{label} vo sekoe vreme na {sender}.",
            "Sekogas aktuelno: {label} na {sender}."
        ],
        "EN": [
            "Always on: {label} on {sender}.",
            "{label} live on {sender}.",
            "{label} nonstop on {sender}.",
            "{label} anytime on {sender}.",
            "{label} all day on {sender}.",
            "{sender}: {label} nonstop."
        ]
    },

    "GAMING": {
        "label": {"DE": "Gaming", "EXYU": "Gaming", "EN": "Gaming", "SI": "Igre", "MK": "Gejming"},
        "keywords": [
            "GAMING", "ESPORTS", "E-SPORTS", "GAME", "IGRE", "TWITCH", "GAMER", "PLAYSTATION", "XBOX", "NINTENDO", "GINX"
        ],
        "DE": [
            "{label} jederzeit bei {sender}.",
            "{sender} praesentiert {label}.",
            "{label} rund um die Uhr.",
            "Non-Stop {label} auf {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{sender} bringt {label}."
        ],
        "EXYU": [
            "{label} u svako doba na {sender}.",
            "{label} uzivo na {sender}.",
            "Non-stop {label} na {sender}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{label} cijeli dan na {sender}.",
            "{sender} predstavlja {label}."
        ],
        "SI": [
            "Nonstop {label} na {sender}.",
            "{label} ves dan na {sender}.",
            "{label} nonstop na {sender}.",
            "{label} 24 ur na dan.",
            "{sender} predstavlja {label}.",
            "{label} kadarkoli na {sender}."
        ],
        "MK": [
            "{sender} - vasiot kanal za {label}.",
            "{label} nonstop na {sender}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{sender} pretstavuva {label}.",
            "{label} cel den na {sender}.",
            "{sender}: {label} bez prekin."
        ],
        "EN": [
            "All day {label} on {sender}.",
            "Nonstop {label} on {sender}.",
            "{sender}: {label} every hour.",
            "{label} without a break on {sender}.",
            "{sender} brings you {label}.",
            "{label} live on {sender}."
        ]
    },

    "RADIO": {
        "label": {"DE": "Radio", "EXYU": "Radio", "EN": "Radio", "SI": "Radio", "MK": "Radio"},
        "keywords": [
            "RADIO", "HÖRFUNK", "FM", "BBC RADIO", "CLASSIC FM", "HEART RADIO", "CAPITAL FM"
        ],
        "DE": [
            "{label} live auf {sender}.",
            "{label} jederzeit bei {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{sender}: {label} pur.",
            "{label} ohne Unterbrechung auf {sender}."
        ],
        "EXYU": [
            "Cijeli dan {label} na {sender}.",
            "{label} bez pauze na {sender}.",
            "Non-stop {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender} donosi {label}.",
            "{label} 24 sata na dan."
        ],
        "SI": [
            "{label} ves dan na {sender}.",
            "{label} nonstop na {sender}.",
            "{label} kadarkoli na {sender}.",
            "{sender}: {label} vsako uro.",
            "Ves dan {label} na {sender}.",
            "{label} 24 ur na dan."
        ],
        "MK": [
            "{sender} nudi {label}.",
            "Cel den {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{label} 24 casa na den.",
            "{sender}: {label} bez prekin.",
            "{sender} pretstavuva {label}."
        ],
        "EN": [
            "{sender} presents {label}.",
            "{sender}: {label} every hour.",
            "{label} all day on {sender}.",
            "All day {label} on {sender}.",
            "Nonstop {label} on {sender}.",
            "{label} live on {sender}."
        ]
    },

    "SHOPPING": {
        "label": {"DE": "Shopping", "EXYU": "Kupovina", "EN": "Shopping", "SI": "Nakupovanje", "MK": "Kupuvanje"},
        "keywords": [
            "SHOP", "SHOPPING", "QVC", "HSE", "KUPOVINA", "IDEAL WORLD", "BID TV", "JEWELLERY MAKER", "STUDIO SHOP", "TELESHOPPING", "TV SHOP"
        ],
        "DE": [
            "Immer aktuell: {label} auf {sender}.",
            "Non-Stop {label} auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{label} live auf {sender}.",
            "{label} jederzeit bei {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label}.",
            "{sender} - vas kanal za {label}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{label} cijeli dan na {sender}.",
            "{label} uzivo na {sender}."
        ],
        "SI": [
            "{sender}: {label} vsako uro.",
            "{sender} predstavlja {label}.",
            "Nonstop {label} na {sender}.",
            "{label} kadarkoli na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{label} v zivo na {sender}."
        ],
        "MK": [
            "{sender} - vasiot kanal za {label}.",
            "Nonstop {label} na {sender}.",
            "{sender} pretstavuva {label}.",
            "{label} bez pauza na {sender}.",
            "{label} vo zivo na {sender}.",
            "{sender}: {label} sekoj cas."
        ],
        "EN": [
            "{sender}: {label} every hour.",
            "{sender} presents {label}.",
            "{sender} - your channel for {label}.",
            "{sender}: {label} nonstop.",
            "Nonstop {label} on {sender}.",
            "Always on: {label} on {sender}."
        ]
    },

    "WISSEN": {
        "label": {"DE": "Wissen & Bildung", "EXYU": "Znanje i edukacija", "EN": "Science & Education", "SI": "Znanje in izobraževanje", "MK": "Znaenje i obrazovanie"},
        "keywords": [
            "SCIENCE", "EDUCATION", "ZNANJE", "NAUKA", "BILDUNG", "LEARN", "DISCOVERY SCIENCE", "OPEN UNIVERSITY"
        ],
        "DE": [
            "{sender} praesentiert {label}.",
            "{label} den ganzen Tag auf {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{label} rund um die Uhr.",
            "Rund um die Uhr {label} auf {sender}."
        ],
        "EXYU": [
            "{label} nonstop na {sender}.",
            "{sender} donosi {label}.",
            "{sender}: {label} svakog sata.",
            "{label} u svako doba na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{label} bez pauze na {sender}."
        ],
        "SI": [
            "{label} v zivo na {sender}.",
            "{sender}: {label} vsako uro.",
            "{sender} predstavlja {label}.",
            "{sender} prinasa {label}.",
            "{sender}: {label} brez prekinitve.",
            "Ves dan {label} na {sender}."
        ],
        "MK": [
            "{label} cel den na {sender}.",
            "{label} 24 casa na den.",
            "{sender} pretstavuva {label}.",
            "{label} nonstop na {sender}.",
            "{label} bez pauza na {sender}.",
            "Sekogas aktuelno: {label} na {sender}."
        ],
        "EN": [
            "Always on: {label} on {sender}.",
            "{label} around the clock.",
            "Nonstop {label} on {sender}.",
            "{label} nonstop on {sender}.",
            "{sender} - your channel for {label}.",
            "All day {label} on {sender}."
        ]
    },

    "NATUR": {
        "label": {"DE": "Natur", "EXYU": "Priroda", "EN": "Nature", "SI": "Narava", "MK": "Priroda"},
        "keywords": [
            "NATURE", "WILD", "ANIMAL", "SAFARI", "PLANET", "EARTH", "PRIRODA", "ZIVOTINJE", "ANIMAL PLANET"
        ],
        "DE": [
            "{sender}: {label} zu jeder Stunde.",
            "{sender}: {label} pur.",
            "{label} jederzeit bei {sender}.",
            "{label} rund um die Uhr.",
            "{label} den ganzen Tag auf {sender}.",
            "{label} live auf {sender}."
        ],
        "EXYU": [
            "{label} u svako doba na {sender}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{sender}: {label} svakog sata.",
            "{sender}: {label} bez prekida.",
            "{label} 24 sata na dan.",
            "{label} cijeli dan na {sender}."
        ],
        "SI": [
            "{label} brez premora na {sender}.",
            "{label} v zivo na {sender}.",
            "{label} ves dan na {sender}.",
            "Ves dan {label} na {sender}.",
            "{sender} prinasa {label}.",
            "{sender} predstavlja {label}."
        ],
        "MK": [
            "Cel den {label} na {sender}.",
            "{label} bez pauza na {sender}.",
            "{label} vo zivo na {sender}.",
            "{sender} nudi {label}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{sender}: {label} bez prekin."
        ],
        "EN": [
            "{label} all day on {sender}.",
            "{sender} - your channel for {label}.",
            "{label} around the clock.",
            "Nonstop {label} on {sender}.",
            "{label} nonstop on {sender}.",
            "{sender} presents {label}."
        ]
    },

    "DOKU": {
        "label": {"DE": "Dokumentation", "EXYU": "Dokumentarni program", "EN": "Documentary", "SI": "Dokumentarni program", "MK": "Dokumentarna programa"},
        "keywords": [
            "DISCOVERY", "NAT GEO", "NATIONAL", "HISTORY", "DOC", "DOKUMENTARNI", "SMITHSONIAN", "TRUE CRIME", "INVESTIGATION", "PBS", "ARTE", "YESTERDAY", "CURIOSITY", "VIASAT EXPLORE", "ID", "INVESTIGATION DISCOVERY"
        ],
        "DE": [
            "{sender} - Ihr Kanal fuer {label}.",
            "Non-Stop {label} auf {sender}.",
            "{sender}: {label} zu jeder Stunde.",
            "{label} jederzeit bei {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{label} ohne Unterbrechung auf {sender}."
        ],
        "EXYU": [
            "Non-stop {label} na {sender}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{sender} donosi {label}.",
            "{label} cijeli dan na {sender}.",
            "{label} nonstop na {sender}."
        ],
        "SI": [
            "{label} brez premora na {sender}.",
            "{label} 24 ur na dan.",
            "{sender} prinasa {label}.",
            "{label} ves dan na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender} predstavlja {label}."
        ],
        "MK": [
            "{label} bez pauza na {sender}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{sender} - vasiot kanal za {label}.",
            "{sender}: {label} sekoj cas.",
            "{label} vo zivo na {sender}.",
            "{sender}: {label} bez prekin."
        ],
        "EN": [
            "{label} all day on {sender}.",
            "{sender}: {label} every hour.",
            "{label} nonstop on {sender}.",
            "{label} anytime on {sender}.",
            "{label} around the clock.",
            "{sender} presents {label}."
        ]
    },

    "AUTO": {
        "label": {"DE": "Auto & Motor", "EXYU": "Auto i motor", "EN": "Auto & Motor", "SI": "Avto in motor", "MK": "Avtomobili i moto"},
        "keywords": [
            "AUTO", "MOTOR", "MOTORVISION", "AUTOMOBIL", "GARAZA", "TOP GEAR", "GRAND TOUR", "MOTORTREND", "VELOCITY", "AUTO MOTO", "DRIVE"
        ],
        "DE": [
            "{sender} bringt {label}.",
            "Immer aktuell: {label} auf {sender}.",
            "{label} nonstop bei {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{label} jederzeit bei {sender}."
        ],
        "EXYU": [
            "{label} 24 sata na dan.",
            "{label} u svako doba na {sender}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{label} uzivo na {sender}.",
            "{sender}: {label} bez prekida.",
            "{label} bez pauze na {sender}."
        ],
        "SI": [
            "{sender} predstavlja {label}.",
            "{label} kadarkoli na {sender}.",
            "{label} brez premora na {sender}.",
            "{sender} prinasa {label}.",
            "{sender}: {label} brez prekinitve.",
            "{sender}: {label} vsako uro."
        ],
        "MK": [
            "{sender}: {label} sekoj cas.",
            "{label} 24 casa na den.",
            "{sender} - vasiot kanal za {label}.",
            "{sender} nudi {label}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{sender}: {label} bez prekin."
        ],
        "EN": [
            "{sender}: {label} every hour.",
            "All day {label} on {sender}.",
            "{label} live on {sender}.",
            "Always on: {label} on {sender}.",
            "{label} nonstop on {sender}.",
            "{label} all day on {sender}."
        ]
    },

    "REISEN": {
        "label": {"DE": "Reisen", "EXYU": "Putovanja", "EN": "Travel", "SI": "Potovanja", "MK": "Patuvanja"},
        "keywords": [
            "TRAVEL", "TOUR", "TOURISM", "VACATION", "EXPLORE", "PUTOVANJA", "TRAVEL CHANNEL", "GEO TRAVEL"
        ],
        "DE": [
            "{sender}: {label} zu jeder Stunde.",
            "{sender} praesentiert {label}.",
            "Non-Stop {label} auf {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{label} live auf {sender}.",
            "{label} den ganzen Tag auf {sender}."
        ],
        "EXYU": [
            "Uvijek aktuelno: {label} na {sender}.",
            "{sender} donosi {label}.",
            "{label} cijeli dan na {sender}.",
            "{sender} predstavlja {label}.",
            "{label} u svako doba na {sender}.",
            "{sender}: {label} bez prekida."
        ],
        "SI": [
            "{sender}: {label} brez prekinitve.",
            "{sender} - vas kanal za {label}.",
            "Ves dan {label} na {sender}.",
            "{label} ves dan na {sender}.",
            "Vedno sveze: {label} na {sender}.",
            "{sender}: {label} vsako uro."
        ],
        "MK": [
            "{label} 24 casa na den.",
            "Nonstop {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender} nudi {label}.",
            "{label} vo sekoe vreme na {sender}.",
            "{label} vo zivo na {sender}."
        ],
        "EN": [
            "{label} around the clock.",
            "All day {label} on {sender}.",
            "{sender}: {label} nonstop.",
            "{label} anytime on {sender}.",
            "{label} nonstop on {sender}.",
            "{label} live on {sender}."
        ]
    },

    "KOCHEN": {
        "label": {"DE": "Kochen", "EXYU": "Kuhinja", "EN": "Food & Cooking", "SI": "Kuhanje", "MK": "Gotvenje"},
        "keywords": [
            "FOOD", "KITCHEN", "COOK", "CUISINE", "CHEF", "GUSTO", "KUHINJA", "RECEPTI", "MASTERCHEF", "BAKE OFF", "FOOD NETWORK", "TASTE", "GORDON RAMSAY", "COOKING CHANNEL", "KOCHT", "KOCHEN", "KOCHSHOW", "KOCHSTUDIO", "KÜCHE"
        ],
        "DE": [
            "{label} den ganzen Tag auf {sender}.",
            "{sender}: {label} zu jeder Stunde.",
            "{sender} praesentiert {label}.",
            "{label} rund um die Uhr.",
            "{sender} bringt {label}.",
            "Immer aktuell: {label} auf {sender}."
        ],
        "EXYU": [
            "{label} bez pauze na {sender}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "Non-stop {label} na {sender}.",
            "{sender}: {label} bez prekida.",
            "{label} u svako doba na {sender}.",
            "{label} cijeli dan na {sender}."
        ],
        "SI": [
            "{label} 24 ur na dan.",
            "{sender} - vas kanal za {label}.",
            "{label} ves dan na {sender}.",
            "{sender} prinasa {label}.",
            "{sender}: {label} brez prekinitve.",
            "{sender} predstavlja {label}."
        ],
        "MK": [
            "{label} vo zivo na {sender}.",
            "{sender} - vasiot kanal za {label}.",
            "{label} vo sekoe vreme na {sender}.",
            "{label} nonstop na {sender}.",
            "{label} bez pauza na {sender}.",
            "{label} 24 casa na den."
        ],
        "EN": [
            "{sender}: {label} nonstop.",
            "{label} live on {sender}.",
            "{label} all day on {sender}.",
            "{sender} - your channel for {label}.",
            "{label} around the clock.",
            "{sender} presents {label}."
        ]
    },

    "MUSIK": {
        "label": {"DE": "Musik", "EXYU": "Muzika", "EN": "Music", "SI": "Glasba", "MK": "Muzika"},
        "keywords": [
            "MUSIC", "MUSIK", "MTV", "VH1", "DELUXE", "CLUB", "HITS", "MEZZO", "TRACE", "4MUSIC", "CMC", "DM SAT", "FOLK", "BALKAN MUSIC", "NRJ", "KISS", "DANCE", "ROCK", "POP", "JAZZ", "MUZIKA", "HEART", "CAPITAL", "SMOOTH", "MAGIC RADIO", "GRAND", "HITRADIO", "ENERGY", "SCHLAGER", "NARODNA", "TURBO FOLK", "PARTY"
        ],
        "DE": [
            "{sender}: {label} pur.",
            "{label} rund um die Uhr.",
            "{label} den ganzen Tag auf {sender}.",
            "{label} ohne Unterbrechung auf {sender}.",
            "{label} live auf {sender}.",
            "{sender}: {label} zu jeder Stunde."
        ],
        "EXYU": [
            "{label} 24 sata na dan.",
            "Cijeli dan {label} na {sender}.",
            "{label} uzivo na {sender}.",
            "{sender} predstavlja {label}.",
            "{label} nonstop na {sender}.",
            "{label} cijeli dan na {sender}."
        ],
        "SI": [
            "{label} ves dan na {sender}.",
            "{sender} prinasa {label}.",
            "{label} 24 ur na dan.",
            "{sender}: {label} brez prekinitve.",
            "{sender} predstavlja {label}.",
            "Nonstop {label} na {sender}."
        ],
        "MK": [
            "{label} nonstop na {sender}.",
            "{label} vo zivo na {sender}.",
            "{sender} - vasiot kanal za {label}.",
            "{label} vo sekoe vreme na {sender}.",
            "{sender}: {label} bez prekin.",
            "{label} cel den na {sender}."
        ],
        "EN": [
            "All day {label} on {sender}.",
            "{sender} presents {label}.",
            "Nonstop {label} on {sender}.",
            "{sender} brings you {label}.",
            "{label} around the clock.",
            "{label} live on {sender}."
        ]
    },

    "COMEDY": {
        "label": {"DE": "Comedy", "EXYU": "Komedija", "EN": "Comedy", "SI": "Komedija", "MK": "Komedija"},
        "keywords": [
            "COMEDY", "HUMOR", "FUNNY", "LAUGH", "KOMEDIJA", "DAVE", "COMEDY CENTRAL", "PARANDOVCI", "SMIJEH"
        ],
        "DE": [
            "Non-Stop {label} auf {sender}.",
            "{label} nonstop bei {sender}.",
            "{sender}: {label} zu jeder Stunde.",
            "{sender} bringt {label}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{label} jederzeit bei {sender}."
        ],
        "EXYU": [
            "{sender}: {label} svakog sata.",
            "{label} nonstop na {sender}.",
            "{sender} predstavlja {label}.",
            "Non-stop {label} na {sender}.",
            "{label} uzivo na {sender}.",
            "{label} 24 sata na dan."
        ],
        "SI": [
            "{label} v zivo na {sender}.",
            "{sender}: {label} vsako uro.",
            "{label} nonstop na {sender}.",
            "{label} brez premora na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "{label} kadarkoli na {sender}."
        ],
        "MK": [
            "{sender} pretstavuva {label}.",
            "{sender}: {label} bez prekin.",
            "{label} nonstop na {sender}.",
            "{sender} nudi {label}.",
            "Nonstop {label} na {sender}.",
            "{sender} - vasiot kanal za {label}."
        ],
        "EN": [
            "{label} live on {sender}.",
            "{label} anytime on {sender}.",
            "{label} all day on {sender}.",
            "{sender} brings you {label}.",
            "{sender}: {label} every hour.",
            "{sender}: {label} nonstop."
        ]
    },

    "RELIGION": {
        "label": {"DE": "Religion", "EXYU": "Vjera", "EN": "Religion", "SI": "Vera", "MK": "Religija"},
        "keywords": [
            "EWTN", "KTV", "GOD", "ISLAM", "QURAN", "BIBLE", "CHURCH", "SVET", "VJERA", "HAYAT PLUS", "TRINITY", "GOOD TV", "DAAI"
        ],
        "DE": [
            "{label} live auf {sender}.",
            "{sender} bringt {label}.",
            "{sender}: {label} zu jeder Stunde.",
            "Immer aktuell: {label} auf {sender}.",
            "{label} den ganzen Tag auf {sender}.",
            "{label} jederzeit bei {sender}."
        ],
        "EXYU": [
            "{sender} - vas kanal za {label}.",
            "{label} bez pauze na {sender}.",
            "{label} 24 sata na dan.",
            "Non-stop {label} na {sender}.",
            "{label} u svako doba na {sender}.",
            "{label} cijeli dan na {sender}."
        ],
        "SI": [
            "{label} nonstop na {sender}.",
            "{label} v zivo na {sender}.",
            "Ves dan {label} na {sender}.",
            "{label} brez premora na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{label} ves dan na {sender}."
        ],
        "MK": [
            "{label} 24 casa na den.",
            "{label} cel den na {sender}.",
            "{sender} - vasiot kanal za {label}.",
            "{label} vo sekoe vreme na {sender}.",
            "Nonstop {label} na {sender}.",
            "{sender}: {label} sekoj cas."
        ],
        "EN": [
            "{sender}: {label} nonstop.",
            "All day {label} on {sender}.",
            "Nonstop {label} on {sender}.",
            "{sender}: {label} every hour.",
            "{sender} brings you {label}.",
            "{label} all day on {sender}."
        ]
    },

    "SPORT": {
        "label": {"DE": "Sport", "EXYU": "Sport", "EN": "Sport", "SI": "Šport", "MK": "Sport"},
        "keywords": [
            "SPORT", "SPORTS", "ESPN", "EUROSPORT", "DAZN", "SKY SPORT", "ARENA", "NBA", "NFL", "NHL", "MLB", "TENNIS", "GOLF", "RACING", "FORMULA", "F1", "MOTOGP", "BOX", "FIGHT", "UFC", "BT SPORT", "TNT SPORTS", "PREMIER LEAGUE", "SOCCER", "RUGBY", "CRICKET", "FLO SPORTS", "FLO RACING", "FANDUEL SPORTS", "BEIN SPORTS", "SPORT KLUB", "ARENA SPORT", "SPORTKLUB", "NASCAR", "PGA TOUR", "SKY SPORTS", "VIAPLAY SPORT", "DYN PPV", "WWE", "OLYMPIC", "OLIMPIJSKI"
        ],
        "DE": [
            "Immer aktuell: {label} auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{label} den ganzen Tag auf {sender}.",
            "Non-Stop {label} auf {sender}.",
            "{sender} praesentiert {label}.",
            "{sender}: {label} zu jeder Stunde."
        ],
        "EXYU": [
            "{label} bez pauze na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{sender}: {label} bez prekida.",
            "{sender} predstavlja {label}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{sender} donosi {label}."
        ],
        "SI": [
            "Ves dan {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "{label} ves dan na {sender}.",
            "{sender} predstavlja {label}.",
            "{label} brez premora na {sender}."
        ],
        "MK": [
            "Cel den {label} na {sender}.",
            "{label} cel den na {sender}.",
            "{label} bez pauza na {sender}.",
            "{sender}: {label} bez prekin.",
            "{label} vo zivo na {sender}.",
            "Nonstop {label} na {sender}."
        ],
        "EN": [
            "Always on: {label} on {sender}.",
            "{label} all day on {sender}.",
            "All day {label} on {sender}.",
            "{label} around the clock.",
            "{label} live on {sender}.",
            "{sender} presents {label}."
        ]
    },

    "SERIEN": {
        "label": {"DE": "Serien", "EXYU": "Serije", "EN": "Series", "SI": "Serije", "MK": "Serii"},
        "keywords": [
            "SERIES", "SERIJA", "SERIJE", "DRAMA", "SOAP", "SITCOM", "EPIX", "BRAVO", "USA NETWORK"
        ],
        "DE": [
            "Rund um die Uhr {label} auf {sender}.",
            "{sender}: {label} zu jeder Stunde.",
            "Immer aktuell: {label} auf {sender}.",
            "{label} live auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{sender}: {label} pur."
        ],
        "EXYU": [
            "{sender}: {label} bez prekida.",
            "{label} bez pauze na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{label} 24 sata na dan.",
            "Non-stop {label} na {sender}.",
            "{sender} donosi {label}."
        ],
        "SI": [
            "Nonstop {label} na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "Vedno sveze: {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{label} brez premora na {sender}.",
            "{label} kadarkoli na {sender}."
        ],
        "MK": [
            "{sender}: {label} bez prekin.",
            "{label} bez pauza na {sender}.",
            "{label} vo zivo na {sender}.",
            "{label} cel den na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} sekoj cas."
        ],
        "EN": [
            "{sender} - your channel for {label}.",
            "{sender}: {label} every hour.",
            "All day {label} on {sender}.",
            "{label} around the clock.",
            "{label} all day on {sender}.",
            "Always on: {label} on {sender}."
        ]
    },

    "FILM": {
        "label": {"DE": "Filme", "EXYU": "Filmovi", "EN": "Movies", "SI": "Filmi", "MK": "Filmovi"},
        "keywords": [
            "CINEMA", "FILM", "FILME", "MOVIE", "MOVIES", "HOLLYWOOD", "HBO", "CINEMAX", "SKY CINEMA", "WARNER", "PARAMOUNT", "UNIVERSAL", "SONY", "STAR", "AXN", "AMC", "SYFY", "TNT", "THRILLER", "FILMOVI", "FILM4", "ITV MOVIES", "MGM", "EPIC DRAMA", "PINK FILM", "KLASIK FILM", "CINESTAR", "CINE"
        ],
        "DE": [
            "{sender}: {label} pur.",
            "{sender} praesentiert {label}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{sender} bringt {label}.",
            "{label} jederzeit bei {sender}."
        ],
        "EXYU": [
            "Non-stop {label} na {sender}.",
            "{label} uzivo na {sender}.",
            "{label} nonstop na {sender}.",
            "{label} cijeli dan na {sender}.",
            "{sender}: {label} svakog sata.",
            "{sender}: {label} bez prekida."
        ],
        "SI": [
            "{sender} - vas kanal za {label}.",
            "{sender} predstavlja {label}.",
            "{sender}: {label} vsako uro.",
            "Ves dan {label} na {sender}.",
            "{label} kadarkoli na {sender}.",
            "Nonstop {label} na {sender}."
        ],
        "MK": [
            "{label} vo sekoe vreme na {sender}.",
            "{sender} pretstavuva {label}.",
            "{sender}: {label} bez prekin.",
            "{label} cel den na {sender}.",
            "{sender}: {label} sekoj cas.",
            "{label} bez pauza na {sender}."
        ],
        "EN": [
            "All day {label} on {sender}.",
            "Nonstop {label} on {sender}.",
            "{label} all day on {sender}.",
            "Always on: {label} on {sender}.",
            "{sender}: {label} nonstop.",
            "{label} anytime on {sender}."
        ]
    },

    "WETTER": {
        "label": {"DE": "Wetter", "EXYU": "Vrijeme", "EN": "Weather", "SI": "Vreme", "MK": "Vreme"},
        "keywords": [
            "WEATHER", "WETTER", "VRIJEME", "STORM", "METEO"
        ],
        "DE": [
            "{sender} bringt {label}.",
            "{label} live auf {sender}.",
            "{label} nonstop bei {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{label} ohne Unterbrechung auf {sender}."
        ],
        "EXYU": [
            "{sender}: {label} svakog sata.",
            "{label} nonstop na {sender}.",
            "{sender} predstavlja {label}.",
            "{label} bez pauze na {sender}.",
            "{label} uzivo na {sender}.",
            "Cijeli dan {label} na {sender}."
        ],
        "SI": [
            "{label} brez premora na {sender}.",
            "{sender}: {label} vsako uro.",
            "Ves dan {label} na {sender}.",
            "{label} ves dan na {sender}.",
            "Vedno sveze: {label} na {sender}.",
            "{sender} predstavlja {label}."
        ],
        "MK": [
            "Cel den {label} na {sender}.",
            "{sender} nudi {label}.",
            "{label} bez pauza na {sender}.",
            "{sender} pretstavuva {label}.",
            "{label} nonstop na {sender}.",
            "{label} vo zivo na {sender}."
        ],
        "EN": [
            "{label} nonstop on {sender}.",
            "{sender}: {label} nonstop.",
            "{label} all day on {sender}.",
            "{label} anytime on {sender}.",
            "Always on: {label} on {sender}.",
            "{label} live on {sender}."
        ]
    },

    "JAGD_FISCHEREI": {
        "label": {"DE": "Jagd & Angeln", "EXYU": "Lov i ribolov", "EN": "Hunting & Fishing", "SI": "Lov in ribolov", "MK": "Lov i ribolov"},
        "keywords": [
            "HUNT", "FISHING", "OUTDOOR", "ANGELN", "JAGD", "LOV", "RIBOLOV"
        ],
        "DE": [
            "Non-Stop {label} auf {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{label} nonstop bei {sender}.",
            "{label} den ganzen Tag auf {sender}.",
            "{sender} praesentiert {label}."
        ],
        "EXYU": [
            "{label} 24 sata na dan.",
            "{sender} - vas kanal za {label}.",
            "{label} bez pauze na {sender}.",
            "{label} cijeli dan na {sender}.",
            "Non-stop {label} na {sender}.",
            "{sender}: {label} svakog sata."
        ],
        "SI": [
            "{sender} predstavlja {label}.",
            "{label} 24 ur na dan.",
            "Vedno sveze: {label} na {sender}.",
            "Ves dan {label} na {sender}.",
            "{label} v zivo na {sender}.",
            "{sender} - vas kanal za {label}."
        ],
        "MK": [
            "Cel den {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "Nonstop {label} na {sender}.",
            "{sender} - vasiot kanal za {label}.",
            "{sender} pretstavuva {label}.",
            "Sekogas aktuelno: {label} na {sender}."
        ],
        "EN": [
            "{label} all day on {sender}.",
            "{label} anytime on {sender}.",
            "{sender}: {label} every hour.",
            "{sender} presents {label}.",
            "{label} live on {sender}.",
            "{sender} brings you {label}."
        ]
    },

    "MILITAER": {
        "label": {"DE": "Militär & Krieg", "EXYU": "Vojska i rat", "EN": "Military & War", "SI": "Vojska in vojna", "MK": "Vojska i vojna"},
        "keywords": [
            "MILITARY", "WAR", "ARMY", "VOJSKA", "RAT", "WEHRMACHT"
        ],
        "DE": [
            "Immer aktuell: {label} auf {sender}.",
            "{label} nonstop bei {sender}.",
            "{sender}: {label} pur.",
            "{sender} bringt {label}.",
            "{sender}: {label} zu jeder Stunde.",
            "{label} live auf {sender}."
        ],
        "EXYU": [
            "{label} bez pauze na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{sender} predstavlja {label}.",
            "{sender}: {label} bez prekida.",
            "{label} cijeli dan na {sender}.",
            "Non-stop {label} na {sender}."
        ],
        "SI": [
            "{label} 24 ur na dan.",
            "Ves dan {label} na {sender}.",
            "{sender}: {label} vsako uro.",
            "{label} v zivo na {sender}.",
            "{label} kadarkoli na {sender}.",
            "{sender} prinasa {label}."
        ],
        "MK": [
            "{sender} nudi {label}.",
            "{label} nonstop na {sender}.",
            "{label} bez pauza na {sender}.",
            "{sender}: {label} bez prekin.",
            "{sender} - vasiot kanal za {label}.",
            "Cel den {label} na {sender}."
        ],
        "EN": [
            "{sender}: {label} every hour.",
            "All day {label} on {sender}.",
            "Always on: {label} on {sender}.",
            "{sender} brings you {label}.",
            "{label} nonstop on {sender}.",
            "{sender} - your channel for {label}."
        ]
    },

    "FAMILIE": {
        "label": {"DE": "Familie", "EXYU": "Porodica", "EN": "Family", "SI": "Družina", "MK": "Semejstvo"},
        "keywords": [
            "FAMILY", "FAMILIE", "PORODICA", "HALLMARK"
        ],
        "DE": [
            "{label} nonstop bei {sender}.",
            "Non-Stop {label} auf {sender}.",
            "{sender} praesentiert {label}.",
            "{label} jederzeit bei {sender}.",
            "{label} den ganzen Tag auf {sender}.",
            "{sender} - Ihr Kanal fuer {label}."
        ],
        "EXYU": [
            "{sender}: {label} svakog sata.",
            "{label} u svako doba na {sender}.",
            "Non-stop {label} na {sender}.",
            "Cijeli dan {label} na {sender}.",
            "{sender} predstavlja {label}.",
            "{sender}: {label} bez prekida."
        ],
        "SI": [
            "{label} 24 ur na dan.",
            "{sender}: {label} brez prekinitve.",
            "{sender} - vas kanal za {label}.",
            "{label} nonstop na {sender}.",
            "Vedno sveze: {label} na {sender}.",
            "Ves dan {label} na {sender}."
        ],
        "MK": [
            "{label} cel den na {sender}.",
            "{sender} - vasiot kanal za {label}.",
            "Cel den {label} na {sender}.",
            "{label} bez pauza na {sender}.",
            "{sender}: {label} bez prekin.",
            "{label} 24 casa na den."
        ],
        "EN": [
            "{label} nonstop on {sender}.",
            "{sender} brings you {label}.",
            "{label} live on {sender}.",
            "All day {label} on {sender}.",
            "{label} around the clock.",
            "Nonstop {label} on {sender}."
        ]
    },

    "ANIME": {
        "label": {"DE": "Anime", "EXYU": "Anime", "EN": "Anime", "SI": "Anime", "MK": "Anime"},
        "keywords": [
            "ANIME", "TOONAMI", "CRUNCHYROLL", "MANGA"
        ],
        "DE": [
            "Rund um die Uhr {label} auf {sender}.",
            "{label} jederzeit bei {sender}.",
            "{sender}: {label} pur.",
            "{sender}: {label} zu jeder Stunde.",
            "{label} live auf {sender}.",
            "{label} rund um die Uhr."
        ],
        "EXYU": [
            "{label} u svako doba na {sender}.",
            "{label} 24 sata na dan.",
            "{label} uzivo na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} svakog sata.",
            "Cijeli dan {label} na {sender}."
        ],
        "SI": [
            "Nonstop {label} na {sender}.",
            "{sender} predstavlja {label}.",
            "{sender}: {label} vsako uro.",
            "{label} brez premora na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} brez prekinitve."
        ],
        "MK": [
            "{sender} - vasiot kanal za {label}.",
            "{label} vo zivo na {sender}.",
            "{label} 24 casa na den.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{label} cel den na {sender}.",
            "{label} nonstop na {sender}."
        ],
        "EN": [
            "{sender} - your channel for {label}.",
            "{sender} presents {label}.",
            "All day {label} on {sender}.",
            "{label} all day on {sender}.",
            "{label} nonstop on {sender}.",
            "{label} without a break on {sender}."
        ]
    },

    "KRIMI": {
        "label": {"DE": "Krimi", "EXYU": "Krimi", "EN": "Crime", "SI": "Kriminalka", "MK": "Kriminal"},
        "keywords": [
            "CRIME", "DETECTIVE", "MURDER", "CSI", "LAW & ORDER", "KRIMI"
        ],
        "DE": [
            "{label} live auf {sender}.",
            "{label} rund um die Uhr.",
            "{label} jederzeit bei {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{sender}: {label} pur.",
            "{sender} bringt {label}."
        ],
        "EXYU": [
            "{label} 24 sata na dan.",
            "{label} cijeli dan na {sender}.",
            "{sender}: {label} svakog sata.",
            "Non-stop {label} na {sender}.",
            "{sender} predstavlja {label}.",
            "Uvijek aktuelno: {label} na {sender}."
        ],
        "SI": [
            "{label} v zivo na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "{label} 24 ur na dan.",
            "Nonstop {label} na {sender}.",
            "{label} ves dan na {sender}.",
            "{sender}: {label} vsako uro."
        ],
        "MK": [
            "{sender} - vasiot kanal za {label}.",
            "{sender} pretstavuva {label}.",
            "{label} vo zivo na {sender}.",
            "{sender} nudi {label}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} bez prekin."
        ],
        "EN": [
            "{sender} presents {label}.",
            "{label} without a break on {sender}.",
            "Nonstop {label} on {sender}.",
            "{label} nonstop on {sender}.",
            "Always on: {label} on {sender}.",
            "{sender}: {label} nonstop."
        ]
    },

    "GESUNDHEIT": {
        "label": {"DE": "Gesundheit & Fitness", "EXYU": "Zdravlje i fitnes", "EN": "Health & Fitness", "SI": "Zdravje in fitnes", "MK": "Zdravje i fitnes"},
        "keywords": [
            "FITNESS", "HEALTH", "WELLNESS", "YOGA", "GYM", "ZDRAVLJE"
        ],
        "DE": [
            "{sender} - Ihr Kanal fuer {label}.",
            "{label} ohne Unterbrechung auf {sender}.",
            "{label} nonstop bei {sender}.",
            "{sender}: {label} pur.",
            "Immer aktuell: {label} auf {sender}.",
            "{sender} praesentiert {label}."
        ],
        "EXYU": [
            "{label} 24 sata na dan.",
            "{label} u svako doba na {sender}.",
            "Non-stop {label} na {sender}.",
            "Cijeli dan {label} na {sender}.",
            "{sender}: {label} bez prekida.",
            "{sender}: {label} svakog sata."
        ],
        "SI": [
            "{sender}: {label} brez prekinitve.",
            "{label} ves dan na {sender}.",
            "{sender} prinasa {label}.",
            "{label} kadarkoli na {sender}.",
            "{label} v zivo na {sender}.",
            "{sender} predstavlja {label}."
        ],
        "MK": [
            "{sender} pretstavuva {label}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{label} vo sekoe vreme na {sender}.",
            "{sender}: {label} bez prekin.",
            "{label} bez pauza na {sender}.",
            "{sender}: {label} sekoj cas."
        ],
        "EN": [
            "{sender}: {label} nonstop.",
            "{label} all day on {sender}.",
            "{label} around the clock.",
            "Always on: {label} on {sender}.",
            "{sender} - your channel for {label}.",
            "{sender} presents {label}."
        ]
    },

    "TECH": {
        "label": {"DE": "Technik", "EXYU": "Tehnologija", "EN": "Technology", "SI": "Tehnologija", "MK": "Tehnologija"},
        "keywords": [
            "TECH", "TECHNOLOGY", "GADGET", "TEHNOLOGIJA"
        ],
        "DE": [
            "{label} nonstop bei {sender}.",
            "{label} jederzeit bei {sender}.",
            "Non-Stop {label} auf {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{label} den ganzen Tag auf {sender}.",
            "{sender} bringt {label}."
        ],
        "EXYU": [
            "{sender}: {label} bez prekida.",
            "{label} 24 sata na dan.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{sender} donosi {label}.",
            "Non-stop {label} na {sender}.",
            "{label} cijeli dan na {sender}."
        ],
        "SI": [
            "{sender}: {label} brez prekinitve.",
            "{label} brez premora na {sender}.",
            "Vedno sveze: {label} na {sender}.",
            "Ves dan {label} na {sender}.",
            "{sender}: {label} vsako uro.",
            "{sender} prinasa {label}."
        ],
        "MK": [
            "{sender} nudi {label}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{label} vo sekoe vreme na {sender}.",
            "Nonstop {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} bez prekin."
        ],
        "EN": [
            "{label} anytime on {sender}.",
            "{sender}: {label} every hour.",
            "All day {label} on {sender}.",
            "{sender} - your channel for {label}.",
            "{sender} brings you {label}.",
            "{label} around the clock."
        ]
    },

    "HORROR": {
        "label": {"DE": "Horror & Thriller", "EXYU": "Horor i triler", "EN": "Horror & Thriller", "SI": "Grozljivke in trilerji", "MK": "Horor i triler"},
        "keywords": [
            "HORROR", "SCARY", "SCREAM", "CHILLER", "TERROR", "SLASHER"
        ],
        "DE": [
            "{label} rund um die Uhr.",
            "{sender}: {label} pur.",
            "{sender} - Ihr Kanal fuer {label}.",
            "{label} den ganzen Tag auf {sender}.",
            "{sender} praesentiert {label}.",
            "{label} live auf {sender}."
        ],
        "EXYU": [
            "{label} bez pauze na {sender}.",
            "{sender} donosi {label}.",
            "{label} cijeli dan na {sender}.",
            "Non-stop {label} na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{sender}: {label} bez prekida."
        ],
        "SI": [
            "{sender} prinasa {label}.",
            "{sender}: {label} vsako uro.",
            "{label} nonstop na {sender}.",
            "Nonstop {label} na {sender}.",
            "{sender} - vas kanal za {label}.",
            "Vedno sveze: {label} na {sender}."
        ],
        "MK": [
            "{sender} pretstavuva {label}.",
            "{label} vo zivo na {sender}.",
            "{sender}: {label} sekoj cas.",
            "Nonstop {label} na {sender}.",
            "{sender} - vasiot kanal za {label}.",
            "{label} vo sekoe vreme na {sender}."
        ],
        "EN": [
            "Nonstop {label} on {sender}.",
            "{sender}: {label} every hour.",
            "{sender} brings you {label}.",
            "Always on: {label} on {sender}.",
            "{label} nonstop on {sender}.",
            "{sender} - your channel for {label}."
        ]
    },

    "TALKSHOW": {
        "label": {"DE": "Talkshow", "EXYU": "Tok šou", "EN": "Talk Show", "SI": "Pogovorna oddaja", "MK": "Tok-šou"},
        "keywords": [
            "TALK SHOW", "TALKSHOW", "LATE NIGHT", "TONIGHT SHOW", "THIS MORNING"
        ],
        "DE": [
            "{sender} praesentiert {label}.",
            "{sender} bringt {label}.",
            "Non-Stop {label} auf {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{label} nonstop bei {sender}.",
            "{label} ohne Unterbrechung auf {sender}."
        ],
        "EXYU": [
            "{label} u svako doba na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} bez prekida.",
            "{label} 24 sata na dan.",
            "{sender} donosi {label}.",
            "{label} cijeli dan na {sender}."
        ],
        "SI": [
            "{sender}: {label} vsako uro.",
            "{sender} - vas kanal za {label}.",
            "Nonstop {label} na {sender}.",
            "{label} 24 ur na dan.",
            "{label} nonstop na {sender}.",
            "{label} brez premora na {sender}."
        ],
        "MK": [
            "{sender} - vasiot kanal za {label}.",
            "{label} vo sekoe vreme na {sender}.",
            "{label} cel den na {sender}.",
            "{sender} pretstavuva {label}.",
            "{label} 24 casa na den.",
            "Nonstop {label} na {sender}."
        ],
        "EN": [
            "{label} anytime on {sender}.",
            "{sender} presents {label}.",
            "{label} around the clock.",
            "{label} without a break on {sender}.",
            "All day {label} on {sender}.",
            "{label} live on {sender}."
        ]
    },

    "WIRTSCHAFT": {
        "label": {"DE": "Wirtschaft & Finanzen", "EXYU": "Biznis i finansije", "EN": "Business & Finance", "SI": "Posel in finance", "MK": "Biznis i finansii"},
        "keywords": [
            "BUSINESS", "FINANCE", "MONEY", "MARKETS", "WIRTSCHAFT", "BIZNIS"
        ],
        "DE": [
            "{sender} - Ihr Kanal fuer {label}.",
            "{label} ohne Unterbrechung auf {sender}.",
            "Non-Stop {label} auf {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{sender} praesentiert {label}.",
            "{label} live auf {sender}."
        ],
        "EXYU": [
            "{label} 24 sata na dan.",
            "{sender}: {label} svakog sata.",
            "{label} nonstop na {sender}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{label} bez pauze na {sender}.",
            "{sender}: {label} bez prekida."
        ],
        "SI": [
            "Ves dan {label} na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "{label} kadarkoli na {sender}.",
            "{sender}: {label} vsako uro.",
            "{sender} predstavlja {label}.",
            "{label} nonstop na {sender}."
        ],
        "MK": [
            "{sender}: {label} sekoj cas.",
            "{label} vo zivo na {sender}.",
            "{label} bez pauza na {sender}.",
            "{label} cel den na {sender}.",
            "{sender} nudi {label}.",
            "{label} 24 casa na den."
        ],
        "EN": [
            "{label} without a break on {sender}.",
            "{label} live on {sender}.",
            "{sender}: {label} nonstop.",
            "Nonstop {label} on {sender}.",
            "All day {label} on {sender}.",
            "{sender} - your channel for {label}."
        ]
    },

    "LIFESTYLE": {
        "label": {"DE": "Lifestyle", "EXYU": "Lifestyle", "EN": "Lifestyle", "SI": "Življenjski slog", "MK": "Lifestyle"},
        "keywords": [
            "LIFESTYLE", "STYLE", "FASHION", "HOME", "LIVING", "HGTV", "TLC", "BEAUTY", "DESIGN", "WOMAN", "LADY", "W NETWORK", "OPRAH", "OWN", "LIFETIME", "DECOR", "STIL"
        ],
        "DE": [
            "{label} live auf {sender}.",
            "{label} den ganzen Tag auf {sender}.",
            "{sender}: {label} zu jeder Stunde.",
            "Immer aktuell: {label} auf {sender}.",
            "{sender}: {label} pur.",
            "{sender} praesentiert {label}."
        ],
        "EXYU": [
            "{label} u svako doba na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{label} uzivo na {sender}.",
            "{label} 24 sata na dan.",
            "{sender} donosi {label}.",
            "Cijeli dan {label} na {sender}."
        ],
        "SI": [
            "{sender}: {label} vsako uro.",
            "{label} kadarkoli na {sender}.",
            "{label} v zivo na {sender}.",
            "{sender} predstavlja {label}.",
            "{label} ves dan na {sender}.",
            "{sender}: {label} brez prekinitve."
        ],
        "MK": [
            "{label} cel den na {sender}.",
            "{sender} pretstavuva {label}.",
            "{label} vo zivo na {sender}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{label} 24 casa na den."
        ],
        "EN": [
            "{sender}: {label} every hour.",
            "{label} all day on {sender}.",
            "{label} without a break on {sender}.",
            "{sender} brings you {label}.",
            "Nonstop {label} on {sender}.",
            "{label} nonstop on {sender}."
        ]
    },

    "REGIONAL": {
        "label": {"DE": "Regional", "EXYU": "Regionalni program", "EN": "Regional", "SI": "Regionalni program", "MK": "Regionalna programa"},
        "keywords": [
            "REGIONAL", "LOKAL", "LOKALNA"
        ],
        "DE": [
            "{label} ohne Unterbrechung auf {sender}.",
            "{sender} praesentiert {label}.",
            "{sender} bringt {label}.",
            "{sender}: {label} zu jeder Stunde.",
            "{label} den ganzen Tag auf {sender}.",
            "{label} rund um die Uhr."
        ],
        "EXYU": [
            "Uvijek aktuelno: {label} na {sender}.",
            "{label} u svako doba na {sender}.",
            "{sender}: {label} svakog sata.",
            "{sender} predstavlja {label}.",
            "{label} nonstop na {sender}.",
            "{sender} - vas kanal za {label}."
        ],
        "SI": [
            "{sender}: {label} brez prekinitve.",
            "{label} nonstop na {sender}.",
            "{label} v zivo na {sender}.",
            "Ves dan {label} na {sender}.",
            "Nonstop {label} na {sender}.",
            "{sender} prinasa {label}."
        ],
        "MK": [
            "{sender} - vasiot kanal za {label}.",
            "{label} 24 casa na den.",
            "Nonstop {label} na {sender}.",
            "{label} vo zivo na {sender}.",
            "Cel den {label} na {sender}.",
            "{sender} pretstavuva {label}."
        ],
        "EN": [
            "{label} around the clock.",
            "{label} without a break on {sender}.",
            "{sender}: {label} nonstop.",
            "{sender} - your channel for {label}.",
            "Nonstop {label} on {sender}.",
            "{label} nonstop on {sender}."
        ]
    },

    "UNTERHALTUNG": {
        "label": {"DE": "Unterhaltung", "EXYU": "Zabava", "EN": "Entertainment", "SI": "Zabava", "MK": "Zabava"},
        "keywords": [
            "RTL", "VOX", "SAT", "PRO7", "PRO SIEBEN", "KABEL", "NOVA", "PINK", "HAPPY", "HAYAT", "OBN", "FACE", "ATV", "KANAL", "TV", "FOX", "ABC", "CBS", "NBC", "SHOW", "PLUS", "PRIME", "ZABAVA", "ITV", "CHANNEL 4", "CHANNEL4", "CHANNEL 5", "CHANNEL5", "E4", "MORE4", "DAVE", "ITV2", "ITV3", "ITV4", "5STAR", "5 STAR", "DIREKT", "MREZA PLUS", "K1", "K3", "MTEL"
        ],
        "DE": [
            "{sender}: {label} pur.",
            "{label} nonstop bei {sender}.",
            "Non-Stop {label} auf {sender}.",
            "Rund um die Uhr {label} auf {sender}.",
            "{label} jederzeit bei {sender}.",
            "{sender} bringt {label}."
        ],
        "EXYU": [
            "{label} nonstop na {sender}.",
            "{label} u svako doba na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{sender}: {label} bez prekida.",
            "{label} bez pauze na {sender}.",
            "Non-stop {label} na {sender}."
        ],
        "SI": [
            "{label} 24 ur na dan.",
            "Ves dan {label} na {sender}.",
            "{label} ves dan na {sender}.",
            "{sender}: {label} vsako uro.",
            "{label} kadarkoli na {sender}.",
            "Vedno sveze: {label} na {sender}."
        ],
        "MK": [
            "{label} nonstop na {sender}.",
            "{label} vo zivo na {sender}.",
            "Nonstop {label} na {sender}.",
            "{sender}: {label} sekoj cas.",
            "{sender}: {label} bez prekin.",
            "{sender} pretstavuva {label}."
        ],
        "EN": [
            "{label} around the clock.",
            "{label} nonstop on {sender}.",
            "{sender}: {label} every hour.",
            "{label} live on {sender}.",
            "Always on: {label} on {sender}.",
            "{label} anytime on {sender}."
        ]
    },

    "GARTEN_HEIM": {
        "label": {"DE": "Garten & Heim", "EXYU": "Vrt i dom", "EN": "Home & Garden", "SI": "Vrt in dom", "MK": "Gradina i dom"},
        "keywords": [
            "GARDEN", "GARDENING", "HGTV", "HOME AND GARDEN", "DIY", "MONTY DON", "HOME NETWORK", "PROPERTY", "RENOVATION", "VRT", "DOM"
        ],
        "DE": [
            "{label} den ganzen Tag auf {sender}.",
            "{label} nonstop bei {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{label} live auf {sender}.",
            "{label} ohne Unterbrechung auf {sender}.",
            "{sender} bringt {label}."
        ],
        "EXYU": [
            "Cijeli dan {label} na {sender}.",
            "{label} 24 sata na dan.",
            "{label} u svako doba na {sender}.",
            "{sender} predstavlja {label}.",
            "{label} uzivo na {sender}.",
            "{label} nonstop na {sender}."
        ],
        "SI": [
            "{label} 24 ur na dan.",
            "{sender} prinasa {label}.",
            "{label} nonstop na {sender}.",
            "{label} ves dan na {sender}.",
            "{sender}: {label} vsako uro.",
            "Vedno sveze: {label} na {sender}."
        ],
        "MK": [
            "{label} vo sekoe vreme na {sender}.",
            "{sender}: {label} sekoj cas.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{label} bez pauza na {sender}.",
            "{label} vo zivo na {sender}.",
            "{sender} - vasiot kanal za {label}."
        ],
        "EN": [
            "{sender} - your channel for {label}.",
            "{sender}: {label} every hour.",
            "{label} live on {sender}.",
            "{sender} brings you {label}.",
            "{label} all day on {sender}.",
            "All day {label} on {sender}."
        ]
    },

    "WELTRAUM_WISSENSCHAFT": {
        "label": {"DE": "Weltraum & Wissenschaft", "EXYU": "Svemir i nauka", "EN": "Space & Science", "SI": "Vesolje in znanost", "MK": "Vselena i nauka"},
        "keywords": [
            "SPACE", "NASA", "COSMOS", "UNIVERSE", "GALAXY", "SVEMIR", "VESOLJE", "VSELENA"
        ],
        "DE": [
            "{label} den ganzen Tag auf {sender}.",
            "{label} nonstop bei {sender}.",
            "{sender}: {label} zu jeder Stunde.",
            "{sender} bringt {label}.",
            "{label} ohne Unterbrechung auf {sender}.",
            "Immer aktuell: {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} - vas kanal za {label}.",
            "Cijeli dan {label} na {sender}.",
            "{sender}: {label} svakog sata.",
            "{label} nonstop na {sender}.",
            "{label} bez pauze na {sender}.",
            "{label} u svako doba na {sender}."
        ],
        "SI": [
            "{label} brez premora na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "{sender} - vas kanal za {label}.",
            "{sender} prinasa {label}.",
            "Nonstop {label} na {sender}.",
            "Vedno sveze: {label} na {sender}."
        ],
        "MK": [
            "{sender} nudi {label}.",
            "{sender} - vasiot kanal za {label}.",
            "{label} vo zivo na {sender}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{label} nonstop na {sender}.",
            "{sender}: {label} bez prekin."
        ],
        "EN": [
            "{label} without a break on {sender}.",
            "{sender} brings you {label}.",
            "Nonstop {label} on {sender}.",
            "{label} around the clock.",
            "Always on: {label} on {sender}.",
            "{sender} presents {label}."
        ]
    },

    "MODE": {
        "label": {"DE": "Mode", "EXYU": "Moda", "EN": "Fashion", "SI": "Moda", "MK": "Moda"},
        "keywords": [
            "FASHION", "VOGUE", "GLAMOUR", "FASHION TV", "FASHIONTV", "STYLE NETWORK", "MODA"
        ],
        "DE": [
            "{label} live auf {sender}.",
            "Immer aktuell: {label} auf {sender}.",
            "{label} jederzeit bei {sender}.",
            "{sender}: {label} pur.",
            "{label} den ganzen Tag auf {sender}.",
            "Non-Stop {label} auf {sender}."
        ],
        "EXYU": [
            "Cijeli dan {label} na {sender}.",
            "{sender}: {label} svakog sata.",
            "{sender} donosi {label}.",
            "Non-stop {label} na {sender}.",
            "Uvijek aktuelno: {label} na {sender}.",
            "{label} uzivo na {sender}."
        ],
        "SI": [
            "{label} nonstop na {sender}.",
            "Vedno sveze: {label} na {sender}.",
            "{sender} - vas kanal za {label}.",
            "{sender}: {label} brez prekinitve.",
            "{sender} predstavlja {label}.",
            "{sender}: {label} vsako uro."
        ],
        "MK": [
            "{sender} - vasiot kanal za {label}.",
            "Sekogas aktuelno: {label} na {sender}.",
            "{label} bez pauza na {sender}.",
            "Cel den {label} na {sender}.",
            "{sender}: {label} sekoj cas.",
            "{label} nonstop na {sender}."
        ],
        "EN": [
            "{sender}: {label} every hour.",
            "{label} nonstop on {sender}.",
            "{label} around the clock.",
            "All day {label} on {sender}.",
            "{label} without a break on {sender}.",
            "{label} all day on {sender}."
        ]
    },

    "GLUECKSSPIEL": {
        "label": {"DE": "Glücksspiel", "EXYU": "Kockanje", "EN": "Gambling", "SI": "Igre na srečo", "MK": "Kockanje"},
        "keywords": [
            "CASINO", "POKER", "GAMBLING", "LOTTO", "BETTING", "BET365", "KOCKANJE"
        ],
        "DE": [
            "{sender}: {label} pur.",
            "{label} live auf {sender}.",
            "{sender} bringt {label}.",
            "{label} jederzeit bei {sender}.",
            "{sender} - Ihr Kanal fuer {label}.",
            "Rund um die Uhr {label} auf {sender}."
        ],
        "EXYU": [
            "{label} uzivo na {sender}.",
            "{label} 24 sata na dan.",
            "{sender} predstavlja {label}.",
            "Cijeli dan {label} na {sender}.",
            "Non-stop {label} na {sender}.",
            "{sender}: {label} svakog sata."
        ],
        "SI": [
            "{sender} prinasa {label}.",
            "{sender} - vas kanal za {label}.",
            "Vedno sveze: {label} na {sender}.",
            "{label} brez premora na {sender}.",
            "{label} 24 ur na dan.",
            "{sender} predstavlja {label}."
        ],
        "MK": [
            "Sekogas aktuelno: {label} na {sender}.",
            "{sender}: {label} sekoj cas.",
            "{label} 24 casa na den.",
            "{sender}: {label} bez prekin.",
            "{label} nonstop na {sender}.",
            "{label} cel den na {sender}."
        ],
        "EN": [
            "{sender}: {label} every hour.",
            "{sender} brings you {label}.",
            "{label} without a break on {sender}.",
            "{sender}: {label} nonstop.",
            "{sender} presents {label}.",
            "{label} anytime on {sender}."
        ]
    },

    "EROTIK": {
        "label": {"DE": "Erotik", "EXYU": "Erotika", "EN": "Adult", "SI": "Erotika", "MK": "Erotika"},
        "keywords": [
            "XXX", "EROTIC", "EROTIK", "EROTIKA", "PLAYBOY", "VENUS", "HUSTLER", "PRIVATE TV", "BRAZZERS"
        ],
        "DE": [
            "Immer aktuell: {label} auf {sender}.",
            "{sender}: {label} zu jeder Stunde.",
            "{label} nonstop bei {sender}.",
            "{sender}: {label} pur.",
            "{label} ohne Unterbrechung auf {sender}.",
            "Non-Stop {label} auf {sender}."
        ],
        "EXYU": [
            "{sender} donosi {label}.",
            "Cijeli dan {label} na {sender}.",
            "{label} u svako doba na {sender}.",
            "{label} 24 sata na dan.",
            "{sender} predstavlja {label}.",
            "{sender}: {label} svakog sata."
        ],
        "SI": [
            "Ves dan {label} na {sender}.",
            "{label} v zivo na {sender}.",
            "{label} 24 ur na dan.",
            "{sender} prinasa {label}.",
            "{label} brez premora na {sender}.",
            "{sender} - vas kanal za {label}."
        ],
        "MK": [
            "Sekogas aktuelno: {label} na {sender}.",
            "{sender} pretstavuva {label}.",
            "{label} vo zivo na {sender}.",
            "{sender}: {label} bez prekin.",
            "{sender}: {label} sekoj cas.",
            "{sender} nudi {label}."
        ],
        "EN": [
            "{sender} presents {label}.",
            "{label} anytime on {sender}.",
            "{label} around the clock.",
            "{label} live on {sender}.",
            "Nonstop {label} on {sender}.",
            "{sender} - your channel for {label}."
        ]
    },

    "KLASSIKER": {
        "label": {"DE": "Klassiker & Retro-TV", "EXYU": "Klasici i retro program", "EN": "Classics & Retro TV", "SI": "Klasika in retro program", "MK": "Klasici i retro programa"},
        "keywords": [
            "CLASSIC", "CLASSICS", "RETRO", "VINTAGE", "RIFLEMAN", "GUNSMOKE", "LEAVE IT TO BEAVER",
            "HONEYMOONERS", "ADDAMS FAMILY", "THREE STOOGES", "HITCHCOCK", "DICK VAN DYKE",
            "LONE RANGER", "SAVED BY THE BELL", "REAL MCCOYS", "GREEN ACRES", "OUTER LIMITS",
            "SIX MILLION DOLLAR MAN", "CHARLIES ANGELS", "FLINTSTONES", "JEFFERSONS", "GOOD TIMES",
            "GIRLFRIENDS", "A DIFFERENT WORLD", "CINEVAULT"
        ],
        "DE": [
            "{label} von damals.",
            "Retro-Klassiker auf {sender}.",
            "{sender}: {label} in voller Laenge.",
            "TV-Klassiker rund um die Uhr auf {sender}.",
            "{label} - die alten Folgen auf {sender}.",
            "Nostalgie pur: {label} auf {sender}."
        ],
        "EXYU": [
            "{label} iz starih dana.",
            "Retro klasici na {sender}.",
            "{sender}: {label} u cjelosti.",
            "TV klasici cijeli dan na {sender}.",
            "{label} - stare epizode na {sender}.",
            "Nostalgija na {sender}: {label}."
        ],
        "SI": [
            "{label} iz starih casov.",
            "Retro klasika na {sender}.",
            "{sender}: {label} v celoti.",
            "TV klasika ves dan na {sender}.",
            "{label} - stare epizode na {sender}.",
            "Nostalgija na {sender}: {label}."
        ],
        "MK": [
            "{label} od starite denovi.",
            "Retro klasici na {sender}.",
            "{sender}: {label} vo celost.",
            "TV klasici cel den na {sender}.",
            "{label} - starite epizodi na {sender}.",
            "Nostalgija na {sender}: {label}."
        ],
        "EN": [
            "{label} from way back.",
            "Retro classics on {sender}.",
            "{sender}: {label} in full.",
            "Classic TV all day on {sender}.",
            "{label} - the old episodes on {sender}.",
            "Pure nostalgia on {sender}: {label}."
        ]
    },

    "SPIELSHOW": {
        "label": {"DE": "Spielshow", "EXYU": "Kviz emisija", "EN": "Game Show", "SI": "Kvizovna oddaja", "MK": "Kviz emisija"},
        "keywords": [
            "GAME SHOW", "GAMESHOW", "QUIZ", "FAMILY FEUD", "SUPERMARKET SWEEP", "LET'S MAKE A DEAL",
            "LETS MAKE A DEAL", "NAME GAME", "THE APPRENTICE", "WHEEL OF FORTUNE",
            "JEOPARDY", "NINJA WARRIOR"
        ],
        "DE": [
            "{label} mit Spannung auf {sender}.",
            "{sender}: {label} rund um die Uhr.",
            "Ratefieber: {label} auf {sender}.",
            "{label} - mitraten auf {sender}.",
            "{sender} praesentiert {label}.",
            "Spannung pur: {label} auf {sender}."
        ],
        "EXYU": [
            "{label} sa napetoscu na {sender}.",
            "{sender}: {label} cijeli dan.",
            "Kvizovska groznica: {label} na {sender}.",
            "{label} - pogadjajte na {sender}.",
            "{sender} predstavlja {label}.",
            "Napetost na {sender}: {label}."
        ],
        "SI": [
            "{label} z napetostjo na {sender}.",
            "{sender}: {label} ves dan.",
            "Kvizovska vrocica: {label} na {sender}.",
            "{label} - ugibajte na {sender}.",
            "{sender} predstavlja {label}.",
            "Napetost na {sender}: {label}."
        ],
        "MK": [
            "{label} so napnatost na {sender}.",
            "{sender}: {label} cel den.",
            "Kviz treska: {label} na {sender}.",
            "{label} - pogodete na {sender}.",
            "{sender} pretstavuva {label}.",
            "Napnatost na {sender}: {label}."
        ],
        "EN": [
            "{label} with suspense on {sender}.",
            "{sender}: {label} around the clock.",
            "Quiz fever: {label} on {sender}.",
            "{label} - play along on {sender}.",
            "{sender} presents {label}.",
            "Pure suspense on {sender}: {label}."
        ]
    },

    "KARAOKE": {
        "label": {"DE": "Karaoke", "EXYU": "Karaoke", "EN": "Karaoke", "SI": "Karaoke", "MK": "Karaoke"},
        "keywords": [
            "KARAOKE"
        ],
        "DE": [
            "{label} zum Mitsingen auf {sender}.",
            "{sender}: {label} nonstop.",
            "Singen Sie mit: {label} auf {sender}.",
            "{label} rund um die Uhr auf {sender}.",
            "{sender} bringt {label}.",
            "Mikrofon an: {label} auf {sender}."
        ],
        "EXYU": [
            "{label} za pjevanje na {sender}.",
            "{sender}: {label} bez prekida.",
            "Pjevajte s nama: {label} na {sender}.",
            "{label} cijeli dan na {sender}.",
            "{sender} donosi {label}.",
            "Mikrofon upaljen: {label} na {sender}."
        ],
        "SI": [
            "{label} za petje na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "Pojte z nami: {label} na {sender}.",
            "{label} ves dan na {sender}.",
            "{sender} prinasa {label}.",
            "Mikrofon prizgan: {label} na {sender}."
        ],
        "MK": [
            "{label} za peenje na {sender}.",
            "{sender}: {label} bez prekin.",
            "Peejte so nas: {label} na {sender}.",
            "{label} cel den na {sender}.",
            "{sender} nudi {label}.",
            "Mikrofonot vklucen: {label} na {sender}."
        ],
        "EN": [
            "{label} for singalongs on {sender}.",
            "{sender}: {label} nonstop.",
            "Sing along: {label} on {sender}.",
            "{label} around the clock on {sender}.",
            "{sender} brings you {label}.",
            "Mic's on: {label} on {sender}."
        ]
    },

    "TELENOVELA": {
        "label": {"DE": "Telenovela", "EXYU": "Sapunica", "EN": "Soap Opera", "SI": "Nadaljevanka", "MK": "Sapunica"},
        "keywords": [
            "TELENOVELA", "TELENOVELAS", "SOAP OPERA", "SOAP OPERAS", "PRIMETIME SOAPS", "GENERAL HOSPITAL",
            "BOLD AND THE BEAUTIFUL", "REBELDE", "LAS 3 MARIAS", "GRANDES PAREJAS", "GALANES", "ALL DAY DRAMA"
        ],
        "DE": [
            "{label} den ganzen Tag auf {sender}.",
            "{sender}: {label} ohne Unterbrechung.",
            "Dramatisch: {label} auf {sender}.",
            "{label} rund um die Uhr auf {sender}.",
            "{sender} praesentiert {label}.",
            "Non-Stop {label} auf {sender}."
        ],
        "EXYU": [
            "{label} cijeli dan na {sender}.",
            "{sender}: {label} bez prekida.",
            "Dramatično: {label} na {sender}.",
            "{label} 24 sata na {sender}.",
            "{sender} predstavlja {label}.",
            "Non-stop {label} na {sender}."
        ],
        "SI": [
            "{label} ves dan na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "Dramatično: {label} na {sender}.",
            "{label} 24 ur na {sender}.",
            "{sender} predstavlja {label}.",
            "Non-stop {label} na {sender}."
        ],
        "MK": [
            "{label} cel den na {sender}.",
            "{sender}: {label} bez prekin.",
            "Dramatično: {label} na {sender}.",
            "{label} 24 časa na {sender}.",
            "{sender} pretstavuva {label}.",
            "Non-stop {label} na {sender}."
        ],
        "EN": [
            "{label} all day on {sender}.",
            "{sender}: {label} nonstop.",
            "Drama alert: {label} on {sender}.",
            "{label} around the clock on {sender}.",
            "{sender} presents {label}.",
            "Non-stop {label} on {sender}."
        ]
    },

    "GERICHTSSHOW": {
        "label": {"DE": "Gerichtsshow", "EXYU": "Sudska emisija", "EN": "Court Show", "SI": "Sodna oddaja", "MK": "Sudska emisija"},
        "keywords": [
            "COURT", "TRIBUNAL JUSTICE", "COUPLES COURT", "PERSONAL INJURY COURT", "JUDGE & JURY", "JUDGE AND JURY",
            "RELATIVE JUSTICE", "CASO CEBRADO", "PATERNITY COURT"
        ],
        "DE": [
            "{label} den ganzen Tag auf {sender}.",
            "{sender}: {label} nonstop.",
            "Urteil folgt: {label} auf {sender}.",
            "{label} rund um die Uhr auf {sender}.",
            "{sender} praesentiert {label}.",
            "Verhandlung laeuft: {label} auf {sender}."
        ],
        "EXYU": [
            "{label} cijeli dan na {sender}.",
            "{sender}: {label} bez prekida.",
            "Presuda stiže: {label} na {sender}.",
            "{label} 24 sata na {sender}.",
            "{sender} predstavlja {label}.",
            "Rasprava u toku: {label} na {sender}."
        ],
        "SI": [
            "{label} ves dan na {sender}.",
            "{sender}: {label} brez prekinitve.",
            "Sodba prihaja: {label} na {sender}.",
            "{label} 24 ur na {sender}.",
            "{sender} predstavlja {label}.",
            "Obravnava poteka: {label} na {sender}."
        ],
        "MK": [
            "{label} cel den na {sender}.",
            "{sender}: {label} bez prekin.",
            "Presudata doaǵa: {label} na {sender}.",
            "{label} 24 časa na {sender}.",
            "{sender} pretstavuva {label}.",
            "Rasprava vo tek: {label} na {sender}."
        ],
        "EN": [
            "{label} all day on {sender}.",
            "{sender}: {label} nonstop.",
            "Verdict pending: {label} on {sender}.",
            "{label} around the clock on {sender}.",
            "{sender} presents {label}.",
            "In session: {label} on {sender}."
        ]
    }
}

# Feste Prüfreihenfolge: spezifischere Kategorien zuerst, damit
# generische Keywords (z.B. "TV", "SHOW" in UNTERHALTUNG) nicht
# fälschlich vor eindeutigeren Treffern (z.B. "SCIENCE", "REALITY")
# gewinnen. UNTERHALTUNG steht bewusst ganz am Ende als breitester
# Auffang-Kategorie vor dem generischen Fallback-Text.
KATEGORIE_PRIORITAET = [
    "REALITY", "NEWS", "WETTER", "KINDER", "ANIME", "FAMILIE", "GAMING", "RADIO", "KARAOKE", "SHOPPING",
    "EROTIK", "GLUECKSSPIEL", "WELTRAUM_WISSENSCHAFT", "MODE", "GARTEN_HEIM",
    "WISSEN", "NATUR", "JAGD_FISCHEREI", "DOKU", "MILITAER", "AUTO", "REISEN", "KOCHEN",
    "MUSIK", "COMEDY", "RELIGION", "HORROR", "KRIMI", "GERICHTSSHOW", "SPIELSHOW", "TALKSHOW",
    "WIRTSCHAFT", "GESUNDHEIT", "TECH",
    "KLASSIKER", "TELENOVELA", "SPORT", "SERIEN", "FILM",
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
    hash_wert = sender_hash(sender)

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
    "TELENOVELA": "12", "GERICHTSSHOW": "12",
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


def sender_anzeigename(name):
    worte = [wort.capitalize() for wort in name.split()]
    return " ".join(worte)


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
    "DAZN", "HD", "FHD", "UHD", "SD", "HEVC", "TV", "ACL", "RAW", "4K", "8K",
    "ZDF", "ARD", "RTL", "MDR", "NDR", "WDR", "SWR", "BR", "HR", "SR", "RBB",
    "PPV", "VIP", "UFC", "NFL", "NBA", "NHL", "MLB", "NCAA", "MLS", "EPL",
    "DE", "US", "UK", "BA", "RS", "SI", "MK", "EXYU", "MO", "MNG", "CG",
    "SPFL", "NA", "SK", "GO", "CITY", "EN", "IR", "LIGA", "JOYN", "PRIME",
    "WOW", "TUBI",
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
        while kern and kern[-1] in ")]:":
            suffix = kern[-1] + suffix
            kern = kern[:-1]

        if kern.upper() in KANALNAME_ABKUERZUNGEN:
            kern_formatiert = kern.upper()
        else:
            # Jeden Bindestrich-Teil einzeln kapitalisieren, sonst wird
            # aus "YU-GI-OH!" nur "Yu-gi-oh!" statt "Yu-Gi-Oh!".
            kern_formatiert = "-".join(teil.capitalize() for teil in kern.split("-"))

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
    BALKANS" ergeben denselben Schluessel.

    Entfernt zusaetzlich die Anbieter-eigenen Deko-Marker "VIP"/"RAW"
    (auch in hochgestellter Unicode-Schreibweise wie "ⱽᴵᴾ ᴿᴬᵂ" - NFKD
    zerlegt diese Zeichen zu normalen Buchstaben, siehe unten) als
    eigene Woerter, BEVOR die Buchstaben zusammengeschoben werden -
    diese Marker sind reine Playlist-Tags des Nutzers, tauchen in
    keiner echten Sender-API auf und wuerden sonst bei kurzen
    Sendernamen (z.B. "ATV ⱽᴵᴾ ᴿᴬᵂ" -> "ATVVIPRAW") den unscharfen
    difflib-Abgleich gegen den echten Namen ("ATV") unter die
    Aehnlichkeits-Schwelle druecken und den Treffer verhindern.

    Wandelt ausserdem "+" in das Wort "PLUS" um (statt es ersatzlos zu
    entfernen), damit z.B. "Sky Premieren +24" und "Sky Premieren Plus
    24" auf denselben Schluessel abbilden - beide Schreibweisen sind in
    freier Wildbahn ueblich (eigene Playlist vs. Anbieter-API)."""
    if not name:
        return ""

    name = unicodedata.normalize("NFKD", name)
    name = "".join(zeichen for zeichen in name if not unicodedata.combining(zeichen))
    name = name.upper()
    name = re.sub(r"\bVIP\b|\bRAW\b", " ", name)
    name = name.replace("+", " PLUS ")
    name = re.sub(r"[^A-Z0-9]", "", name)
    return name


def normalisiere_sendername_kern(name):
    """Wie normalisiere_sendername(), entfernt zusaetzlich die
    Qualitaets-Suffixe "HD"/"FHD"/"UHD"/"SD" als eigene Woerter (z.B.
    "QVC FHD" -> gleicher Kern wie "QVC"). Nur als KERN-Fallback
    gedacht, NICHT als Ersatz fuer normalisiere_sendername(): manche
    Anbieter fuehren HD/SD als eigene, unterschiedliche Kanaele (z.B.
    zwei getrennte TVPassport-Eintraege fuer dieselbe Lokalstation), der
    exakte Abgleich nach normalisiere_sendername() muss daher immer
    zuerst versucht werden - der Kern-Vergleich ist nur ein Fallback,
    wenn dieser keinen Treffer findet."""
    if not name:
        return ""

    name = unicodedata.normalize("NFKD", name)
    name = "".join(zeichen for zeichen in name if not unicodedata.combining(zeichen))
    name = name.upper()
    name = re.sub(r"\bVIP\b|\bRAW\b|\bU?HD\b|\bFHD\b|\bSD\b", " ", name)
    name = name.replace("+", " PLUS ")
    name = re.sub(r"[^A-Z0-9]", "", name)
    return name


def kanal_index_suchen(ziel_name, name_index, kern_index=None, cutoff=0.72):
    """Generischer Kanal-Namensabgleich fuer die *_kanal_finden()-
    Funktionen: erst exakter Abgleich nach normalisiere_sendername(),
    dann (falls kern_index uebergeben) ein eindeutiger Kern-Abgleich
    ohne HD/FHD/UHD/SD, zuletzt unscharfer difflib-Abgleich auf dem
    vollen Namen. name_index/kern_index sind Dicts Schluessel->Wert,
    kern_index sollte bei mehrdeutigem Kern-Schluessel keinen Eintrag
    enthalten (siehe Aufrufer), damit dieser Fallback nie einen von
    mehreren echten HD/SD-Varianten falsch auswaehlt. Gibt den Wert aus
    name_index/kern_index zurueck oder None."""
    ziel_schluessel = normalisiere_sendername(ziel_name)
    if not ziel_schluessel:
        return None

    if ziel_schluessel in name_index:
        return name_index[ziel_schluessel]

    if kern_index:
        ziel_kern = normalisiere_sendername_kern(ziel_name)
        if ziel_kern and ziel_kern in kern_index:
            return kern_index[ziel_kern]

    aehnliche = difflib.get_close_matches(ziel_schluessel, name_index.keys(), n=1, cutoff=cutoff)
    if aehnliche:
        return name_index[aehnliche[0]]

    return None


def kern_index_aufbauen(eintraege, namensfeld, wertfeld):
    """Baut aus einer Liste von Kanal-Dicts einen Kern-Index (siehe
    normalisiere_sendername_kern()) fuer kanal_index_suchen(). Ist ein
    Kern-Schluessel mehrdeutig (mehrere unterschiedliche Werte, z.B.
    echte getrennte HD/SD-Kanaele desselben Namens), wird er bewusst
    NICHT aufgenommen, damit der Fallback nie zufaellig die falsche
    Variante trifft."""
    kern_index = {}
    mehrdeutig = set()
    for eintrag in eintraege:
        kern = normalisiere_sendername_kern(eintrag[namensfeld])
        if not kern:
            continue
        wert = eintrag[wertfeld]
        if kern in kern_index and kern_index[kern] != wert:
            mehrdeutig.add(kern)
        else:
            kern_index.setdefault(kern, wert)
    for kern in mehrdeutig:
        kern_index.pop(kern, None)
    return kern_index


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

