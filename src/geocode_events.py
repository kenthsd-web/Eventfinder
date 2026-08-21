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
# VERIFIERADE ARENOR / SÖKOVERRIDES
# ============================================================
#
# Vissa arenanamn fungerar dåligt i OpenStreetMap-sökningen.
# Därför kan vi här ange korrekt ort/kommun och en bättre
# sökfråga.
#
# Om lat/lon anges används koordinaterna direkt.
# Om bara search_query anges verifieras platsen fortfarande
# via Nominatim.
# ============================================================

ARENA_OVERRIDES = {
    "Scandinavium": {
        "lat": 57.7003,
        "lon": 11.9865,
        "ort": "Göteborg",
        "kommun": "Göteborg",
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

    "Umeå Energi Arena Vatten": {
        "ort": "Umeå",
        "kommun": "Umeå",
        "search_query": (
            "Umeå Energi Arena Vatten, "
            "Gammlia, Umeå, Sweden"
        ),
    },

    "Lunds Idrottshall": {
        "ort": "Lund",
        "kommun": "Lund",
        "search_query": (
            "Lunds Idrottshall, "
            "Lund, Sweden"
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

    "Jönköpings Idrotthus Arenan": {
        "ort": "Jönköping",
        "kommun": "Jönköping",
        "search_query": (
            "Jönköpings Idrottshus, "
            "Jönköping, Sweden"
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

    "TTM hallen": {
        "ort": "Kalmar",
        "kommun": "Kalmar",
        "search_query": (
            "TTM-hallen, "
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

    "Nolia Arena": {
        "ort": "Umeå",
        "kommun": "Umeå",
        "search_query": (
            "Nolia Arena, "
            "Umeå, Sweden"
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
    if not EVENT_FILE.exists():
        return

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
            "Accept-Language": "sv-SE,sv;q=0.9",
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
            f"  Nätverksfel: {error.reason}"
        )

    except TimeoutError:
        print(
            "  Timeout"
        )

    except Exception as error:
        print(
            f"  Geokodningsfel: {error}"
        )

    return []


# ============================================================
# ARENA / SÖKFRÅGOR
# ============================================================

def get_arena(event):
    return (
        event.get("arena")
        or event.get("plats")
        or ""
    ).strip()


def apply_override_metadata(event):
    arena = get_arena(event)

    override = ARENA_OVERRIDES.get(
        arena
    )

    if not override:
        return None

    if override.get("ort"):
        event["ort"] = (
            override["ort"]
        )

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

    event[
        "geocode_source"
    ] = "manual_override"

    event[
        "location_precision"
    ] = "arena_verified"

    return True


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

    override_query = override.get(
        "search_query"
    )

    if override_query:
        queries.append(
            override_query
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

    # Ta bort dubletter utan att ändra ordningen.
    return list(
        dict.fromkeys(
            queries
        )
    )


# ============================================================
# POÄNGSÄTT TRÄFFAR
# ============================================================

def normalize_for_match(text):
    text = (
        text
        .lower()
        .replace("-", " ")
        .replace(",", " ")
    )

    return " ".join(
        text.split()
    )


def result_score(result, event):
    display = normalize_for_match(
        result.get(
            "display_name",
            ""
        )
    )

    arena = normalize_for_match(
        get_arena(event)
    )

    ort = normalize_for_match(
        event.get(
            "ort",
            "",
        )
    )

    kommun = normalize_for_match(
        event.get(
            "kommun",
            "",
        )
    )

    score = 0

    # Arena
    arena_words = [
        word
        for word in arena.split()
        if len(word) >= 4
    ]

    matched_arena_words = sum(
        1
        for word in arena_words
        if word in display
    )

    score += (
        matched_arena_words * 3
    )

    # Ort
    if ort and ort in display:
        score += 4

    # Kommun
    if kommun and kommun in display:
        score += 4

    # Sverige
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

    best_score = result_score(
        best,
        event,
    )

    # Kräver mer än en väldigt svag träff.
    if best_score < 4:
        return None

    return best


# ============================================================
# VILKA EVENT SKA GEOKODAS?
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


# ============================================================
# GEOKODNING
# ============================================================

def geocode_events(events):
    cache = load_cache()

    updated = 0
    manual = 0
    searched = 0
    cached = 0
    failed = 0

    arena_groups = {}

    # --------------------------------------------------------
    # Gruppera matcherna per arena
    # --------------------------------------------------------

    for event in events:
        if not needs_geocoding(event):
            continue

        # Lägg först på verifierad ort/kommun.
        apply_override_metadata(
            event
        )

        # Har vi redan verifierade koordinater?
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
        ).append(
            event
        )

    print()
    print(
        f"Unika arenor att geokoda: "
        f"{len(arena_groups)}"
    )

    # --------------------------------------------------------
    # Geokoda varje unik arena en gång
    # --------------------------------------------------------

    for index, (
        arena,
        matching_events,
    ) in enumerate(
        arena_groups.items(),
        start=1,
    ):

        sample_event = (
            matching_events[0]
        )

        print()
        print(
            f"[{index}/{len(arena_groups)}] "
            f"{arena}"
        )

        queries = build_queries(
            sample_event
        )

        best_result = None
        best_query = None

        for query in queries:
            if query in cache:
                results = cache[
                    query
                ]

                cached += 1

            else:
                results = geocode_query(
                    query
                )

                cache[
                    query
                ] = results

                save_cache(
                    cache
                )

                searched += 1

                # Nominatim:
                # max ungefär ett anrop per sekund.
                time.sleep(
                    1.1
                )

            candidate = choose_best_result(
                results,
                sample_event,
            )

            if candidate:
                best_result = candidate
                best_query = query
                break

        if not best_result:
            print(
                "  Ingen säker träff"
            )

            failed += 1
            continue

        lat = float(
            best_result["lat"]
        )

        lon = float(
            best_result["lon"]
        )

        display_name = (
            best_result.get(
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
        "unique_arenas": len(
            arena_groups
        ),
    }


# ============================================================
# DATAKVALITET
# ============================================================

def quality_report(events):
    total = 0
    with_arena = 0
    with_coordinates = 0
    ssl_total = 0
    ssl_with_coordinates = 0

    unique_arenas = set()
    geocoded_arenas = set()

    for event in events:
        if event.get(
            "sport"
        ) != "Innebandy":
            continue

        total += 1

        arena = get_arena(
            event
        )

        if arena:
            with_arena += 1
            unique_arenas.add(
                arena
            )

        has_coordinates = (
            event.get("lat")
            is not None
            and event.get("lon")
            is not None
        )

        if has_coordinates:
            with_coordinates += 1

            if arena:
                geocoded_arenas.add(
                    arena
                )

        if event.get("serie") in (
            "SSL Herr",
            "SSL Dam",
        ):
            ssl_total += 1

            if has_coordinates:
                ssl_with_coordinates += 1

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
        f"{len(geocoded_arenas)}"
    )

    print()
    print(
        f"SSL-matcher totalt: "
        f"{ssl_total}"
    )

    print(
        f"SSL-matcher med koordinater: "
        f"{ssl_with_coordinates}"
    )


# ============================================================
# VISA ARENOR SOM SAKNAS
# ============================================================

def print_missing_arenas(events):
    missing = {}

    for event in events:
        if event.get(
            "sport"
        ) != "Innebandy":
            continue

        arena = get_arena(
            event
        )

        if not arena:
            continue

        if (
            event.get("lat")
            is not None
            and event.get("lon")
            is not None
        ):
            continue

        missing[arena] = (
            missing.get(
                arena,
                0,
            )
            + 1
        )

    if not missing:
        print()
        print(
            "Alla kända arenor har koordinater."
        )
        return

    print()
    print(
        "Arenor som fortfarande saknar koordinater"
    )

    print(
        "-----------------------------------------"
    )

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

    # Säkerhetskopia innan ändring.
    backup_events()

    result = geocode_events(
        events
    )

    save_events(
        events
    )

    print()
    print("Geokodning klar")
    print("---------------")

    print(
        f"Event uppdaterade: "
        f"{result['updated']}"
    )

    print(
        f"Direkta manuella koordinater: "
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
