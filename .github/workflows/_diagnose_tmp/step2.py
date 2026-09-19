import re
import sys

from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "https://mojtv.hr/m2/tv-program/kanal.aspx?id=641"

gesehene_requests = []


def on_request(request):
    if any(x in request.url for x in ("api", "ajax", "tvprogram", "kanal", "json", ".aspx")):
        gesehene_requests.append((request.method, request.url))


def on_response(response):
    ct = response.headers.get("content-type", "")
    if "json" in ct or "/api" in response.url:
        print(f"[RESPONSE] {response.status} {ct} {response.url}")


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ))
    page.on("request", on_request)
    page.on("response", on_response)

    print(f"Oeffne {url} ...")
    try:
        page.goto(url, wait_until="networkidle", timeout=30000)
    except Exception as e:
        print("goto-Fehler (ggf. trotzdem teilweise geladen):", e)

    page.wait_for_timeout(4000)

    print("\n=== Status-Code der Hauptantwort (per erneutem Request) ===")
    try:
        resp = page.goto(url, timeout=15000)
        print(resp.status if resp else "kein Response-Objekt")
    except Exception as e:
        print("Fehler:", e)

    print("\n=== Alle interessanten Requests ===")
    for method, req_url in gesehene_requests:
        print(method, req_url)

    print("\n=== Seitentitel ===")
    print(page.title())

    print("\n=== Sichtbarer Text (erste 3000 Zeichen) ===")
    try:
        text = page.inner_text("body")
        print(text[:3000])
    except Exception as e:
        print("Konnte body-Text nicht lesen:", e)

    print("\n=== HTML-Ausschnitt um 'Travel'/'kanal' Vorkommen ===")
    html = page.content()
    for m in re.finditer(r"travel|kanal[=\"']", html, re.IGNORECASE):
        i = m.start()
        print(html[max(0, i - 100):i + 150])
        print("---")

    browser.close()
