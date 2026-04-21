import urllib.request

urls = [
    "http://127.0.0.1:5173/api/dashboard?limit=1",
    "http://127.0.0.1:8000/api/dashboard?limit=1",
]

for url in urls:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            print(url, response.status)
            body = response.read().decode("utf-8", errors="replace")
            print(body[:400])
    except Exception as exc:
        print(url, "ERROR", repr(exc))
