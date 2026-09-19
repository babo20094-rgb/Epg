from curl_cffi import requests as cffi_requests

urls = [
    "https://mojtv.hr/",
    "https://mojtv.hr/m2/tv-program/kanal.aspx?id=641",
]

for url in urls:
    print(f"\n=== {url} ===")
    try:
        r = cffi_requests.get(url, impersonate="chrome124", timeout=20)
        print("Status:", r.status_code)
        print("Laenge:", len(r.text))
        print(r.text[:2500])
    except Exception as e:
        print("Fehler:", e)
