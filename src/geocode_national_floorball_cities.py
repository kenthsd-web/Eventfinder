import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
BACKUP_FILE = DATA_DIR / "events_before_national_city_geocode.json"
CACHE_FILE = DATA_DIR / "national_floorball_city_cache.json"

USER_AGENT = (
    "Eventfinder/1.0 "
    "(national floorball city fallback geocoding)"
)


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def geocode_city(city):
    params = urlencode(
        {
            "q": f"{city}, Sweden",
            "format": "jsonv2",
            "limit": 3,
            "countrycodes": "se",
            "addressdetails": 1,
        }
    )

    request = Request(
        "https://nominatim.openstreetmap.org/search?" + params,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "sv-SE,sv;q=0.9",
        },
    )

    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError):
        return []


def main():
    print()
    print("=============================================")
    print(" EVENTFINDER - NATIONELL INNEBANDY ORTSFALLBACK")
    print("=============================================")
    print()

    events = load_json(EVENT_FILE, [])
    cache = load_json(CACHE_FILE, {})

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    targets = [
        e for e in events
        if e.get("sport") == "Innebandy"
        and e.get("source_type") == "officiellt_spelschema_pdf"
        and e.get("lat") is None
        and (e.get("ort") or "").strip()
    ]

    cities = sorted({
        e["ort"].strip()
        for e in targets
    })

    print("Matcher att behandla:", len(targets))
    print("Unika orter:", len(cities))
    print()

    found = 0
    failed = 0
    cache_hits = 0
    api_calls = 0

    for index, city in enumerate(cities, start=1):
        print(f"[{index}/{len(cities)}] {city}")

        cached = cache.get(city)

        if cached is not None:
            cache_hits += 1

            if cached.get("lat") is not None:
                found += 1
                print(
                    f"  cache: {cached['lat']}, {cached['lon']}"
                )
            else:
                failed += 1
                print("  cache: ingen träff")

            continue

        results = geocode_city(city)
        api_calls += 1

        if not results:
            cache[city] = {
                "lat": None,
                "lon": None,
                "display_name": "",
            }
            failed += 1
            print("  Ingen träff")
        else:
            result = results[0]

            cache[city] = {
                "lat": float(result["lat"]),
                "lon": float(result["lon"]),
                "display_name": result.get("display_name", ""),
            }

            found += 1

            print(
                f"  {cache[city]['lat']}, {cache[city]['lon']}"
            )
            print(
                f"  {cache[city]['display_name']}"
            )

        save_json(CACHE_FILE, cache)
        time.sleep(1.1)

    updated = 0

    for event in events:
        if event.get("sport") != "Innebandy":
            continue
        if event.get("source_type") != "officiellt_spelschema_pdf":
            continue
        if event.get("lat") is not None:
            continue

        city = (event.get("ort") or "").strip()

        if not city:
            continue

        geo = cache.get(city)

        if not geo or geo.get("lat") is None:
            continue

        event["lat"] = geo["lat"]
        event["lon"] = geo["lon"]
        event["geocode_source"] = "national_city_fallback_nominatim"
        event["location_precision"] = "city"
        event["geocode_display_name"] = geo.get("display_name", "")

        updated += 1

    save_json(EVENT_FILE, events)
    save_json(CACHE_FILE, cache)

    remaining = sum(
        1 for e in events
        if e.get("sport") == "Innebandy"
        and e.get("source_type") == "officiellt_spelschema_pdf"
        and e.get("lat") is None
    )

    print()
    print("=============================================")
    print(" NATIONELL ORTSFALLBACK KLAR")
    print("=============================================")
    print()
    print("Orter med träff:", found)
    print("Orter utan träff:", failed)
    print("Cache-träffar:", cache_hits)
    print("Nya API-anrop:", api_calls)
    print("Event uppdaterade:", updated)
    print("Nationella matcher kvar utan koordinater:", remaining)
    print()
    print("Backup:", BACKUP_FILE)
    print("Cache:", CACHE_FILE)


if __name__ == "__main__":
    main()
