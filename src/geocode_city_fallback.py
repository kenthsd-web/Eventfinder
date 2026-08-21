import json
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
BACKUP_FILE = DATA_DIR / "events_before_city_fallback.json"
CACHE_FILE = DATA_DIR / "city_geocode_cache.json"

USER_AGENT = (
    "Eventfinder/1.0 "
    "(city fallback geocoding for Swedish sports events)"
)


def load_json(path, default):
    if not path.exists():
        return default

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def save_json(path, data):
    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
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

    url = (
        "https://nominatim.openstreetmap.org/search?"
        + params
    )

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "sv-SE,sv;q=0.9",
        },
    )

    try:
        with urlopen(
            request,
            timeout=25,
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except (
        HTTPError,
        URLError,
        TimeoutError,
    ):
        return []


def main():
    print()
    print("=============================================")
    print(" EVENTFINDER - ORTSFALLBACK")
    print("=============================================")
    print()

    events = load_json(
        EVENT_FILE,
        [],
    )

    cache = load_json(
        CACHE_FILE,
        {},
    )

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    cities = sorted(
        {
            (event.get("ort") or "").strip()
            for event in events
            if (
                event.get("source_type")
                == "district_competition_full_schedule"
                and event.get("lat") is None
                and (event.get("ort") or "").strip()
            )
        }
    )

    print(
        f"Unika orter att geokoda: "
        f"{len(cities)}"
    )
    print()

    found = 0
    failed = 0
    cache_hits = 0
    api_calls = 0

    for index, city in enumerate(
        cities,
        start=1,
    ):
        print(
            f"[{index}/{len(cities)}] "
            f"{city}"
        )

        cached = cache.get(city)

        if cached is not None:
            cache_hits += 1

            if cached.get("lat") is not None:
                print(
                    f"  cache: "
                    f"{cached['lat']}, "
                    f"{cached['lon']}"
                )
                found += 1
            else:
                print(
                    "  cache: ingen träff"
                )
                failed += 1

            continue

        results = geocode_city(
            city
        )

        api_calls += 1

        if not results:
            cache[city] = {
                "lat": None,
                "lon": None,
                "display_name": "",
            }

            print(
                "  Ingen träff"
            )

            failed += 1

            save_json(
                CACHE_FILE,
                cache,
            )

            time.sleep(1.1)
            continue

        result = results[0]

        lat = float(
            result["lat"]
        )

        lon = float(
            result["lon"]
        )

        display_name = (
            result.get(
                "display_name",
                ""
            )
        )

        cache[city] = {
            "lat": lat,
            "lon": lon,
            "display_name": display_name,
        }

        print(
            f"  {lat}, {lon}"
        )

        print(
            f"  {display_name}"
        )

        found += 1

        save_json(
            CACHE_FILE,
            cache,
        )

        time.sleep(1.1)

    updated = 0

    for event in events:
        if (
            event.get("source_type")
            != "district_competition_full_schedule"
        ):
            continue

        if event.get("lat") is not None:
            continue

        city = (
            event.get("ort")
            or ""
        ).strip()

        if not city:
            continue

        geo = cache.get(city)

        if not geo:
            continue

        if geo.get("lat") is None:
            continue

        event["lat"] = geo["lat"]
        event["lon"] = geo["lon"]

        event["geocode_display_name"] = (
            geo.get(
                "display_name",
                "",
            )
        )

        event["geocode_source"] = (
            "city_fallback_nominatim"
        )

        event["location_precision"] = "city"

        updated += 1

    save_json(
        EVENT_FILE,
        events,
    )

    save_json(
        CACHE_FILE,
        cache,
    )

    total = sum(
        1
        for event in events
        if event.get("source_type")
        == "district_competition_full_schedule"
    )

    with_coords = sum(
        1
        for event in events
        if (
            event.get("source_type")
            == "district_competition_full_schedule"
            and event.get("lat") is not None
            and event.get("lon") is not None
        )
    )

    exact_arena = sum(
        1
        for event in events
        if (
            event.get("source_type")
            == "district_competition_full_schedule"
            and event.get("lat") is not None
            and event.get("location_precision") == "arena"
        )
    )

    city_level = sum(
        1
        for event in events
        if (
            event.get("source_type")
            == "district_competition_full_schedule"
            and event.get("lat") is not None
            and event.get("location_precision") == "city"
        )
    )

    print()
    print("=============================================")
    print(" ORTSFALLBACK KLAR")
    print("=============================================")
    print()

    print(
        f"Orter med träff: "
        f"{found}"
    )

    print(
        f"Orter utan träff: "
        f"{failed}"
    )

    print(
        f"Cache-träffar: "
        f"{cache_hits}"
    )

    print(
        f"Nya API-anrop: "
        f"{api_calls}"
    )

    print(
        f"Event uppdaterade: "
        f"{updated}"
    )

    print()
    print(
        f"Distriktsmatcher totalt: "
        f"{total}"
    )

    print(
        f"Med koordinater totalt: "
        f"{with_coords}"
    )

    print(
        f"Arenaprecision: "
        f"{exact_arena}"
    )

    print(
        f"Ortsprecision: "
        f"{city_level}"
    )

    if total:
        print(
            f"Täckning: "
            f"{100 * with_coords / total:.1f}%"
        )

    print()
    print(
        f"Backup: {BACKUP_FILE}"
    )

    print(
        f"Cache: {CACHE_FILE}"
    )


if __name__ == "__main__":
    main()
