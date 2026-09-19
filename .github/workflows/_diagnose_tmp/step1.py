from curl_cffi import requests as cffi_requests

urls = [
    "https://tvprofil.com/rs/tvprogram/",
    "https://tvprofil.com/rs/show/9946893/world-heritage",
]

for url in urls:
    print(f"\n=== {url} ===")
    try:
        r = cffi_requests.get(url, impersonate="chrome124", timeout=20)
        print("Status:", r.status_code)
        print("Laenge:", len(r.text))
        print(r.text[:1500])
    except Exception as e:
        print("Fehler:", e)
