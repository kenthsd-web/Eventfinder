import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
BACKUP_FILE = DATA_DIR / "events_before_district_geocode.json"
CACHE_FILE = DATA_DIR / "district_geocode_cache.json"

USER_AGENT = (
    "Eventfinder/1.0 "
    "(arena geocoding for Swedish sports events)"
)


# ============================================================
# DATA
# ============================================================

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


# ============================================================
# GEOKODNING
# ============================================================

def geocode_query(query):
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


# ============================================================
# SÄKER TRÄFF
# ============================================================

def score_result(
    arena,
    result,
):
    arena_lower = arena.lower()

    display = (
        result.get(
            "display_name",
            ""
        )
        .lower()
    )

    score = 0

    # Arenanamnet finns i träffen.
    words = [
        word
        for word in arena_lower.replace(
            "-",
            " ",
        ).split()
        if len(word) >= 4
    ]

    for word in words:
        if word in display:
            score += 2

    # Sverige måste finnas.
    if (
        "sverige" in display
        or "sweden" in display
    ):
        score += 2

    return score


def best_result(
    arena,
    results,
):
    if not results:
        return None

    ranked = sorted(
        results,
        key=lambda item: score_result(
            arena,
            item,
        ),
        reverse=True,
    )

    best = ranked[0]

    # Kräver åtminstone en rimlig namnmatch.
    if score_result(
        arena,
        best,
    ) < 2:
        return None

    return best


# ============================================================
# SÖKSTRATEGI
# ============================================================

def search_arena(arena):
    queries = [
        f"{arena}, Sweden",
        f"{arena}, Sverige",
    ]

    for query in queries:
        results = geocode_query(
            query
        )

        result = best_result(
            arena,
            results,
        )

        if result:
            return (
                query,
                result,
            )

        time.sleep(
            1.1
        )

    return (
        "",
        None,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print(
        "============================================="
    )
    print(
        " EVENTFINDER - GEOKODAR DISTRIKTSARENOR"
    )
    print(
        "============================================="
    )
    print()

    events = load_json(
        EVENT_FILE,
        [],
    )

    if not isinstance(
        events,
        list,
    ):
        raise RuntimeError(
            "events.json är inte en lista."
        )

    cache = load_json(
        CACHE_FILE,
        {},
    )

    district_matches = [
        event
        for event in events
        if event.get(
            "source_type"
        )
        == "district_competition_full_schedule"
    ]

    arenas = sorted(
        {
            event.get(
                "arena"
            )
            for event in district_matches
            if event.get(
                "arena"
            )
        }
    )

    print(
        f"Distriktsmatcher: "
        f"{len(district_matches)}"
    )

    print(
        f"Unika arenor: "
        f"{len(arenas)}"
    )

    print()

    # Backup före ändring.
    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    found = 0
    failed = 0
    cache_hits = 0
    api_searches = 0

    for index, arena in enumerate(
        arenas,
        start=1,
    ):
        print(
            f"[{index}/{len(arenas)}] "
            f"{arena}"
        )

        cached = cache.get(
            arena
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
                    "  cache: ingen säker träff"
                )
                failed += 1

            continue

        query, result = search_arena(
            arena
        )

        api_searches += 1

        if not result:
            cache[
                arena
            ] = {
                "lat": None,
                "lon": None,
                "query": "",
                "display_name": "",
            }

            print(
                "  Ingen säker träff"
            )

            failed += 1

            time.sleep(
                1.1
            )

            continue

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
            arena
        ] = {
            "lat": lat,
            "lon": lon,
            "query": query,
            "display_name":
                display_name,
        }

        print(
            f"  {lat}, {lon}"
        )

        print(
            f"  {display_name}"
        )

        found += 1

        # Nominatim kräver låg anropsfrekvens.
        time.sleep(
            1.1
        )

    # ========================================================
    # UPPDATERA EVENTS
    # ========================================================

    updated = 0

    for event in events:
        if (
            event.get(
                "source_type"
            )
            != "district_competition_full_schedule"
        ):
            continue

        arena = event.get(
            "arena"
        )

        if not arena:
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

        event["lat"] = geo[
            "lat"
        ]

        event["lon"] = geo[
            "lon"
        ]

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
        ] = "Nominatim"

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
        " GEOKODNING KLAR"
    )
    print(
        "============================================="
    )
    print()

    print(
        f"Arenor med träff: "
        f"{found}"
    )

    print(
        f"Arenor utan träff: "
        f"{failed}"
    )

    print(
        f"Cache-träffar: "
        f"{cache_hits}"
    )

    print(
        f"Nya API-sökningar: "
        f"{api_searches}"
    )

    print(
        f"Event uppdaterade: "
        f"{updated}"
    )

    print()
    print(
        f"Distriktsmatcher med koordinater: "
        f"{with_coords}"
    )

    print()
    print(
        f"Backup: "
        f"{BACKUP_FILE}"
    )

    print(
        f"Cache: "
        f"{CACHE_FILE}"
    )

    print(
        f"Uppdaterad fil: "
        f"{EVENT_FILE}"
    )


if __name__ == "__main__":
    main()

