import json
import httpx

with httpx.Client(timeout=20) as c:
    r = c.get("http://127.0.0.1:8000/api/photos")
    d = r.json()
    print("enabled:", d.get("enabled"), "coverage:", d.get("coverage"))
    cities = d.get("cities", {})
    print("cities with photos:", len(cities))
    if cities:
        k = list(cities)[0]
        items = cities[k]
        print("sample city:", k, "items:", len(items))
        print("first url:", items[0]["url"])
        u = "http://127.0.0.1:8000" + items[0]["url"]
        resp = c.get(u)
        print("image fetch:", resp.status_code, len(resp.content), resp.headers.get("content-type"))
