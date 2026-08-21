import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
BACKUP_FILE = DATA_DIR / "events_before_venue_address_geocode.json"
CACHE_FILE = DATA_DIR / "venue_address_geocode_cache.json"

USER_AGENT = (
    "Eventfinder/1.0 "
    "(geocoding official Swedish floorball venue addresses)"
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


def geocode(query):
    params = urlencode(
        {
            "q": query,
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
    print(" EVENTFINDER - GEOKODAR OFFICIELLA ADRESSER")
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

    address_to_events = {}

    for event in events:
        if (
            event.get("source_type")
            != "district_competition_full_schedule"
        ):
            continue

        if event.get("lat") is not None:
            continue

        address = (
            event.get("arena_adress")
            or ""
        ).strip()

        if not address:
            continue

        address_to_events.setdefault(
            address,
            []
        ).append(event)

    addresses = sorted(
        address_to_events.keys()
    )

    print(
        f"Unika officiella adresser att geokoda: "
        f"{len(addresses)}"
    )
    print()

    found = 0
    failed = 0
    cache_hits = 0
    api_calls = 0

    for index, address in enumerate(
        addresses,
        start=1,
    ):
        print(
            f"[{index}/{len(addresses)}] "
            f"{address}"
        )

        cached = cache.get(address)

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

        query = f"{address}, Sweden"

        results = geocode(query)

        api_calls += 1

        if not results:
            cache[address] = {
                "lat": None,
                "lon": None,
                "query": query,
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

        cache[address] = {
            "lat": lat,
            "lon": lon,
            "query": query,
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

        address = (
            event.get("arena_adress")
            or ""
        ).strip()

        if not address:
            continue

        geo = cache.get(address)

        if not geo:
            continue

        if geo.get("lat") is None:
            continue

        event["lat"] = geo["lat"]
        event["lon"] = geo["lon"]

        event["geocode_query"] = (
            geo.get(
                "query",
                "",
            )
        )

        event["geocode_display_name"] = (
            geo.get(
                "display_name",
                "",
            )
        )

        event["geocode_source"] = (
            "official_venue_address_nominatim"
        )

        event["location_precision"] = "arena"

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

    print()
    print("=============================================")
    print(" ADRESSGEOKODNING KLAR")
    print("=============================================")
    print()

    print(
        f"Adresser med träff: "
        f"{found}"
    )

    print(
        f"Adresser utan träff: "
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

    print(
        f"Distriktsmatcher med koordinater: "
        f"{with_coords}"
    )

    print(
        f"Distriktsmatcher totalt: "
        f"{total}"
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
