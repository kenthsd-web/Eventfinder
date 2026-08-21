import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# ============================================================
# EVENTFINDER - SÄKER ARENAGEOKODNING
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
BACKUP_FILE = DATA_DIR / "events_before_geocode.json"
CACHE_FILE = DATA_DIR / "geocode_cache.json"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"

USER_AGENT = (
    "Eventfinder/1.0 "
    "(Swedish sports event geocoding)"
)


# ============================================================
# VERIFIERADE / FÖRBÄTTRADE ARENAUPPGIFTER
# ============================================================

ARENA_OVERRIDES = {
    "Scandinavium": {
        "lat": 57.7003,
        "lon": 11.9865,
        "ort": "Göteborg",
        "kommun": "Göteborg",
    },

    "Lunds Idrottshall": {
        "lat": 55.700561,
        "lon": 13.184439,
        "ort": "Lund",
        "kommun": "Lund",
    },

    "Jakobsbergs Sporthall": {
        "ort": "Järfälla",
        "kommun": "Järfälla",
        "search_query": (
            "Mjölnarvägen 3, "
            "177 41 Järfälla, Sweden"
        ),
    },

    "Uw-Tech Arena": {
        "ort": "Falun",
        "kommun": "Falun",
        "search_query": (
            "Lugnetvägen 5, "
            "791 31 Falun, Sweden"
        ),
    },

    "Sparbanken Wictory Center, Unihocplanen": {
        "ort": "Varberg",
        "kommun": "Varberg",
        "search_query": (
            "Stenåsavägen 1, "
            "432 32 Varberg, Sweden"
        ),
    },

    "Arena Varberg": {
        "ort": "Varberg",
        "kommun": "Varberg",
        "search_query": (
            "Kattegattsvägen 26, "
            "432 50 Varberg, Sweden"
        ),
    },

    "Jönköpings Idrotthus Arenan": {
        "ort": "Jönköping",
        "kommun": "Jönköping",
        "search_query": (
            "Lagermansgatan 4, "
            "553 18 Jönköping, Sweden"
        ),
    },

    "Umeå Energi Arena Vatten": {
        "ort": "Umeå",
        "kommun": "Umeå",
        "search_query": (
            "Gammlia idrottscentrum, "
            "Umeå, Sweden"
        ),
    },

    "Nolia Arena": {
        "ort": "Umeå",
        "kommun": "Umeå",
        "search_query": (
            "Signalvägen 3, "
            "Umeå, Sweden"
        ),
    },

    "Wallenstam Arena": {
        "ort": "Mölnlycke",
        "kommun": "Härryda",
        "search_query": (
            "Wallenstam Arena, "
            "Mölnlycke, Sweden"
        ),
    },

    "Furuborghallen": {
        "ort": "Nykvarn",
        "kommun": "Nykvarn",
        "search_query": (
            "Furuborghallen, "
            "Nykvarn, Sweden"
        ),
    },

    "TTM hallen": {
        "ort": "Kalmar",
        "kommun": "Kalmar",
        "search_query": (
            "TTM hallen, "
            "Kalmar, Sweden"
        ),
    },

    "Lerbäckshallen A": {
        "ort": "Lund",
        "kommun": "Lund",
        "search_query": (
            "Lerbäckshallen, "
            "Lund, Sweden"
        ),
    },
}


# ============================================================
# DATA
# ============================================================

def load_events():
    if not EVENT_FILE.exists():
        raise FileNotFoundError(
            f"Saknar {EVENT_FILE}"
        )

    data = json.loads(
        EVENT_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(data, list):
        raise ValueError(
            "events.json innehåller inte en lista."
        )

    return data


def save_events(events):
    EVENT_FILE.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def backup_events():
    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )


# ============================================================
# CACHE
# ============================================================

def load_cache():
    if not CACHE_FILE.exists():
        return {}

    try:
        data = json.loads(
            CACHE_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


def save_cache(cache):
    CACHE_FILE.write_text(
        json.dumps(
            cache,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# HJÄLPFUNKTIONER
# ============================================================

def get_arena(event):
    return (
        event.get("arena")
        or event.get("plats")
        or ""
    ).strip()


def normalize(text):
    return (
        text.lower()
        .replace("-", " ")
        .replace(",", " ")
        .replace("å", "a")
        .replace("ä", "a")
        .replace("ö", "o")
    )


# ============================================================
# OVERRIDES
# ============================================================

def apply_override_metadata(event):
    arena = get_arena(event)

    override = ARENA_OVERRIDES.get(
        arena
    )

    if not override:
        return None

    if override.get("ort"):
        event["ort"] = override["ort"]

    if override.get("kommun"):
        event["kommun"] = (
            override["kommun"]
        )

    return override


def apply_direct_coordinates(event):
    override = apply_override_metadata(
        event
    )

    if not override:
        return False

    if (
        override.get("lat") is None
        or override.get("lon") is None
    ):
        return False

    event["lat"] = float(
        override["lat"]
    )

    event["lon"] = float(
        override["lon"]
    )

    event["geocode_source"] = (
        "verified_manual_override"
    )

    event["location_precision"] = (
        "arena_verified"
    )

    return True


# ============================================================
# SÖKFRÅGOR
# ============================================================

def build_queries(event):
    arena = get_arena(event)

    ort = (
        event.get("ort")
        or ""
    ).strip()

    kommun = (
        event.get("kommun")
        or ""
    ).strip()

    override = ARENA_OVERRIDES.get(
        arena,
        {},
    )

    queries = []

    if override.get("search_query"):
        queries.append(
            override["search_query"]
        )

    if arena:
        queries.append(
            f"{arena}, Sweden"
        )

    if arena and ort:
        queries.append(
            f"{arena}, {ort}, Sweden"
        )

    if (
        arena
        and kommun
        and kommun != ort
    ):
        queries.append(
            f"{arena}, {kommun}, Sweden"
        )

    return list(
        dict.fromkeys(queries)
    )


# ============================================================
# NOMINATIM
# ============================================================

def geocode_query(query):
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 5,
        "countrycodes": "se",
        "addressdetails": 1,
    }

    url = (
        NOMINATIM_URL
        + "?"
        + urlencode(params)
    )

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language":
                "sv-SE,sv;q=0.9",
        },
    )

    try:
        with urlopen(
            request,
            timeout=20,
        ) as response:

            return json.loads(
                response.read().decode(
                    "utf-8"
                )
            )

    except HTTPError as error:
        print(
            f"  HTTP-fel {error.code}"
        )

    except URLError as error:
        print(
            f"  Nätverksfel: "
            f"{error.reason}"
        )

    except TimeoutError:
        print(
            "  Timeout"
        )

    except Exception as error:
        print(
            f"  Fel: {error}"
        )

    return []


# ============================================================
# BEDÖM TRÄFF
# ============================================================

def result_score(result, event):
    display = normalize(
        result.get(
            "display_name",
            ""
        )
    )

    arena = normalize(
        get_arena(event)
    )

    ort = normalize(
        event.get(
            "ort",
            "",
        )
    )

    kommun = normalize(
        event.get(
            "kommun",
            "",
        )
    )

    score = 0

    arena_words = [
        word
        for word in arena.split()
        if len(word) >= 4
    ]

    for word in arena_words:
        if word in display:
            score += 3

    if ort and ort in display:
        score += 5

    if kommun and kommun in display:
        score += 5

    if (
        "sverige" in display
        or "sweden" in display
    ):
        score += 1

    return score


def choose_best_result(
    results,
    event,
):
    if not results:
        return None

    ranked = sorted(
        results,
        key=lambda item: result_score(
            item,
            event,
        ),
        reverse=True,
    )

    best = ranked[0]

    if result_score(
        best,
        event,
    ) < 5:
        return None

    return best


# ============================================================
# GEOKODNING
# ============================================================

def needs_geocoding(event):
    if event.get("sport") != "Innebandy":
        return False

    if (
        event.get("lat") is not None
        and event.get("lon") is not None
    ):
        return False

    return bool(
        get_arena(event)
    )


def geocode_events(events):
    cache = load_cache()

    updated = 0
    manual = 0
    searched = 0
    cached = 0
    failed = 0

    arena_groups = {}

    for event in events:
        if not needs_geocoding(event):
            continue

        apply_override_metadata(
            event
        )

        if apply_direct_coordinates(
            event
        ):
            manual += 1
            updated += 1
            continue

        arena = get_arena(event)

        arena_groups.setdefault(
            arena,
            [],
        ).append(event)

    print()
    print(
        f"Unika arenor att geokoda: "
        f"{len(arena_groups)}"
    )

    for index, (
        arena,
        matching_events,
    ) in enumerate(
        arena_groups.items(),
        start=1,
    ):

        sample = matching_events[0]

        print()
        print(
            f"[{index}/{len(arena_groups)}] "
            f"{arena}"
        )

        best = None
        best_query = None

        for query in build_queries(
            sample
        ):

            if query in cache:
                results = cache[query]
                cached += 1

            else:
                results = geocode_query(
                    query
                )

                cache[query] = results

                save_cache(
                    cache
                )

                searched += 1

                time.sleep(
                    1.1
                )

            candidate = (
                choose_best_result(
                    results,
                    sample,
                )
            )

            if candidate:
                best = candidate
                best_query = query
                break

        if not best:
            failed += 1

            print(
                "  Ingen säker träff"
            )

            continue

        lat = float(
            best["lat"]
        )

        lon = float(
            best["lon"]
        )

        display_name = (
            best.get(
                "display_name",
                "",
            )
        )

        print(
            f"  {lat}, {lon}"
        )

        print(
            f"  {display_name}"
        )

        print(
            f"  via: {best_query}"
        )

        for event in matching_events:
            event["lat"] = lat
            event["lon"] = lon

            event[
                "geocode_query"
            ] = best_query

            event[
                "geocode_source"
            ] = (
                "OpenStreetMap Nominatim"
            )

            event[
                "geocode_display_name"
            ] = display_name

            event[
                "location_precision"
            ] = "arena_geocoded"

            updated += 1

    return {
        "updated": updated,
        "manual": manual,
        "searched": searched,
        "cached": cached,
        "failed": failed,
    }


# ============================================================
# RAPPORT
# ============================================================

def quality_report(events):
    total = 0
    with_arena = 0
    with_coordinates = 0

    unique_arenas = set()
    arenas_with_coordinates = set()

    for event in events:
        if event.get(
            "sport"
        ) != "Innebandy":
            continue

        total += 1

        arena = get_arena(event)

        if arena:
            with_arena += 1
            unique_arenas.add(
                arena
            )

        if (
            event.get("lat") is not None
            and event.get("lon") is not None
        ):
            with_coordinates += 1

            if arena:
                arenas_with_coordinates.add(
                    arena
                )

    print()
    print("Datakvalitet")
    print("------------")

    print(
        f"Innebandymatcher totalt: "
        f"{total}"
    )

    print(
        f"Matcher med arena: "
        f"{with_arena}"
    )

    print(
        f"Matcher med koordinater: "
        f"{with_coordinates}"
    )

    print(
        f"Unika arenor: "
        f"{len(unique_arenas)}"
    )

    print(
        f"Arenor med koordinater: "
        f"{len(arenas_with_coordinates)}"
    )


def print_missing_arenas(events):
    missing = {}

    for event in events:
        if event.get(
            "sport"
        ) != "Innebandy":
            continue

        arena = get_arena(event)

        if not arena:
            continue

        if (
            event.get("lat") is not None
            and event.get("lon") is not None
        ):
            continue

        missing[arena] = (
            missing.get(
                arena,
                0,
            )
            + 1
        )

    print()
    print(
        "Arenor utan koordinater"
    )
    print(
        "-----------------------"
    )

    if not missing:
        print(
            "Alla kända arenor har koordinater."
        )
        return

    for arena, count in sorted(
        missing.items(),
        key=lambda item: (
            -item[1],
            item[0],
        ),
    ):
        print(
            f"{arena}: "
            f"{count} matcher"
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
        " EVENTFINDER - SÄKER ARENAGEOKODNING"
    )
    print(
        "============================================="
    )

    events = load_events()

    print()
    print(
        f"Laddade {len(events)} event."
    )

    backup_events()

    result = geocode_events(
        events
    )

    save_events(
        events
    )

    print()
    print(
        "Geokodning klar"
    )
    print(
        "---------------"
    )

    print(
        f"Event uppdaterade: "
        f"{result['updated']}"
    )

    print(
        f"Direkta verifierade: "
        f"{result['manual']}"
    )

    print(
        f"Nya API-sökningar: "
        f"{result['searched']}"
    )

    print(
        f"Cache-träffar: "
        f"{result['cached']}"
    )

    print(
        f"Misslyckade arenor: "
        f"{result['failed']}"
    )

    quality_report(
        events
    )

    print_missing_arenas(
        events
    )

    print()
    print(
        f"Backup: {BACKUP_FILE}"
    )

    print(
        f"Cache: {CACHE_FILE}"
    )

    print(
        f"Uppdaterad fil: "
        f"{EVENT_FILE}"
    )


if __name__ == "__main__":
    main()
