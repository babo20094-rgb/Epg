import re
import sys

from playwright.sync_api import sync_playwright

kanal = sys.argv[1] if len(sys.argv) > 1 else "travelxp"
datum = sys.argv[2] if len(sys.argv) > 2 else "2026-09-19"
url = f"https://tvprofil.com/rs/tvprogram/#!datum={datum}&kanal={kanal}"

gesehene_requests = []


def on_request(request):
    if any(x in request.url for x in ("api", "ajax", "tvprogram", "kanal", "json")):
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

    print("\n=== HTML-Ausschnitt um 'travelxp'/'kanal' Vorkommen ===")
    html = page.content()
    for m in re.finditer(r"travelxp|kanal[=\"']", html, re.IGNORECASE):
        i = m.start()
        print(html[max(0, i - 100):i + 150])
        print("---")

    browser.close()
