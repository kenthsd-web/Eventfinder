import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
OVERRIDE_FILE = DATA_DIR / "arena_overrides.json"
CACHE_FILE = DATA_DIR / "arena_override_geocode_cache.json"
BACKUP_FILE = DATA_DIR / "events_before_arena_overrides.json"

USER_AGENT = (
    "Eventfinder/1.0 "
    "(verified Swedish sports arena geocoding)"
)


def load_json(path, default):
    if not path.exists():
        return default

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
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
                response.read().decode(
                    "utf-8"
                )
            )

    except (
        HTTPError,
        URLError,
        TimeoutError,
    ):
        return []


def main():
    print()
    print(
        "============================================="
    )
    print(
        " EVENTFINDER - ARENA OVERRIDES"
    )
    print(
        "============================================="
    )
    print()

    events = load_json(
        EVENT_FILE,
        [],
    )

    overrides = load_json(
        OVERRIDE_FILE,
        {},
    )

    cache = load_json(
        CACHE_FILE,
        {},
    )

    if not overrides:
        raise RuntimeError(
            "arena_overrides.json är tom."
        )

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    found = 0
    failed = 0
    cache_hits = 0
    api_calls = 0

    for index, (
        arena,
        info,
    ) in enumerate(
        overrides.items(),
        start=1,
    ):
        print(
            f"[{index}/{len(overrides)}] "
            f"{arena}"
        )

        address = (
            info.get("adress")
            or ""
        ).strip()

        city = (
            info.get("ort")
            or ""
        ).strip()

        if not address:
            print(
                "  Saknar adress"
            )
            failed += 1
            continue

        cache_key = arena

        cached = cache.get(
            cache_key
        )

        if cached:
            cache_hits += 1

            if cached.get(
                "lat"
            ) is not None:
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

        query = (
            f"{address}, Sweden"
        )

        results = geocode(
            query
        )

        api_calls += 1

        if not results:
            cache[
                cache_key
            ] = {
                "lat": None,
                "lon": None,
                "query": query,
                "display_name": "",
                "ort": city,
            }

            print(
                "  Ingen träff"
            )

            failed += 1

            time.sleep(
                1.1
            )

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

        cache[
            cache_key
        ] = {
            "lat": lat,
            "lon": lon,
            "query": query,
            "display_name":
                display_name,
            "ort": city,
        }

        print(
            f"  {lat}, {lon}"
        )

        print(
            f"  {display_name}"
        )

        found += 1

        time.sleep(
            1.1
        )

    updated = 0

    for event in events:
        if (
            event.get(
                "source_type"
            )
            != "district_competition_full_schedule"
        ):
            continue

        if event.get(
            "lat"
        ) is not None:
            continue

        arena = event.get(
            "arena"
        )

        if not arena:
            continue

        if arena not in overrides:
            continue

        geo = cache.get(
            arena
        )

        if not geo:
            continue

        if geo.get(
            "lat"
        ) is None:
            continue

        event["lat"] = (
            geo["lat"]
        )

        event["lon"] = (
            geo["lon"]
        )

        event["ort"] = (
            geo.get(
                "ort",
                "",
            )
        )

        event[
            "geocode_query"
        ] = geo.get(
            "query",
            "",
        )

        event[
            "geocode_display_name"
        ] = geo.get(
            "display_name",
            "",
        )

        event[
            "geocode_source"
        ] = "arena_override"

        event[
            "location_precision"
        ] = "arena"

        updated += 1

    save_json(
        CACHE_FILE,
        cache,
    )

    save_json(
        EVENT_FILE,
        events,
    )

    with_coords = sum(
        1
        for event in events
        if (
            event.get(
                "source_type"
            )
            == "district_competition_full_schedule"
            and event.get(
                "lat"
            ) is not None
            and event.get(
                "lon"
            ) is not None
        )
    )

    print()
    print(
        "============================================="
    )
    print(
        " OVERRIDES KLARA"
    )
    print(
        "============================================="
    )
    print()

    print(
        f"Overrides med träff: "
        f"{found}"
    )

    print(
        f"Overrides utan träff: "
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

    print()
    print(
        f"Backup: {BACKUP_FILE}"
    )

    print(
        f"Cache: {CACHE_FILE}"
    )


if __name__ == "__main__":
    main()
