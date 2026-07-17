#!/usr/bin/env python3
"""
scripts/enrich_m3u.py

Variante A: Ergänzt tvg-id/tvg-name/tvg-logo in einer lokalen M3U-Datei anhand deiner sender.txt.

Verhalten:
- Liest sender.txt (Format: id| country | name | desc | logo) und erstellt für jeden Eintrag eine xmltv-id im Format "<country>|<name>".
- Geht die M3U (.m3u) durch und versucht, jeden Kanal (Text nach dem Komma in #EXTINF) dem sender.txt-Eintrag zuzuordnen.
- Wenn ein Treffer gefunden wird, fügt das Skript vor dem Komma in der EXTINF-Zeile folgende Attribute ein: tvg-id, tvg-name, tvg-logo (falls vorhanden).

Warum das hilft:
- TiviMate matched das EPG zuverlässig über tvg-id (oder über tvg-name). Wenn die tvg-id in der M3U mit der channel id in deiner XMLTV (Epg_365_Tage.xml) übereinstimmt, werden die Sender automatisch zugeordnet.

Usage (lokal, empfohlen):
  python3 scripts/enrich_m3u.py --m3u-file /pfad/zu/playlist.m3u --sender-file sender.txt --output enriched_playlist.m3u

Hinweis: Die Playlist-URL, die du zuvor gepostet hast, wird nicht verwendet. Das Skript arbeitet nur mit lokalen Dateien oder einer URL, wenn du das explizit angibst.
"""

import argparse
import re
import sys


def normalize(s: str) -> str:
    # Kleinbuchstaben, kein mehrfaches Leerzeichen, nur alphanumerische Zeichen für Vergleich
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^A-Za-z0-9 ]", "", s)
    return s.lower()


def parse_sender_file(path: str):
    entries = []
    with open(path, encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = raw.strip()
            if not line or '|' not in line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 3:
                continue
            country = parts[1]
            name = parts[2]
            logo = parts[4] if len(parts) > 4 else ''
            # Build xmltv id like in deiner EPG-Datei: COUNTRY|NAME
            xmltv_id = f"{country}|{name}"
            entries.append({
                'country': country,
                'name': name,
                'logo': logo,
                'xmltv_id': xmltv_id,
                'norm': normalize(name)
            })
    return entries


def add_or_replace_attrs(extinf: str, attrs: dict) -> str:
    m = re.match(r'(#EXTINF:[^\n]*?)(,)(.*)', extinf, flags=re.DOTALL)
    if not m:
        return extinf
    prefix, comma, rest = m.group(1), m.group(2), m.group(3)
    # remove existing tvg-* attributes (if present)
    prefix = re.sub(r'\s+tvg-id="[^"]*"', '', prefix)
    prefix = re.sub(r'\s+tvg-name="[^"]*"', '', prefix)
    prefix = re.sub(r'\s+tvg-logo="[^"]*"', '', prefix)
    insert = ''.join([f' {k}="{v}"' for k, v in attrs.items() if v])
    return f'{prefix}{insert}{comma}{rest}'


def enrich_m3u_text(m3u_text: str, senders: list) -> str:
    out_lines = []
    lines = m3u_text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith('#EXTINF'):
            # Display name is the part after the first comma
            parts = line.split(',', 1)
            display = parts[1].strip() if len(parts) > 1 else ''
            norm = normalize(display)
            attrs = {}
            # direct normalized match
            match = next((s for s in senders if s['norm'] == norm), None)
            if not match:
                # case-insensitive exact
                match = next((s for s in senders if s['name'].lower() == display.lower()), None)
            if not match:
                # try fuzzy: check if sender name is substring of display or vice versa
                match = next((s for s in senders if s['norm'] and (s['norm'] in norm or norm in s['norm'])), None)
            if match:
                attrs['tvg-id'] = match['xmltv_id']
                attrs['tvg-name'] = match['name']
                if match.get('logo'):
                    attrs['tvg-logo'] = match['logo']
                line = add_or_replace_attrs(line, attrs)
        out_lines.append(line)
    return '\n'.join(out_lines) + '\n'


def main():
    p = argparse.ArgumentParser(description='Enrich M3U with tvg attributes using sender.txt (Variant A)')
    p.add_argument('--m3u-file', help='Local M3U file path (required)', required=True)
    p.add_argument('--sender-file', help='Path to sender.txt (required)', required=True)
    p.add_argument('--output', help='Output M3U path (required)', required=True)
    args = p.parse_args()

    try:
        senders = parse_sender_file(args.sender_file)
    except FileNotFoundError:
        print('sender.txt not found:', args.sender_file, file=sys.stderr)
        sys.exit(2)

    try:
        with open(args.m3u_file, encoding='utf-8', errors='ignore') as fh:
            m3u_text = fh.read()
    except FileNotFoundError:
        print('M3U file not found:', args.m3u_file, file=sys.stderr)
        sys.exit(2)

    out_text = enrich_m3u_text(m3u_text, senders)
    with open(args.output, 'w', encoding='utf-8') as fh:
        fh.write(out_text)
    print('Wrote', args.output)


if __name__ == '__main__':
    main()
