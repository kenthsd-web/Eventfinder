import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
BACKUP_FILE = DATA_DIR / "events_before_district_geocode_pass2.json"
CACHE_FILE = DATA_DIR / "district_geocode_cache_pass2.json"

USER_AGENT = (
    "Eventfinder/1.0 "
    "(Swedish sports arena geocoding)"
)


TEAM_CITY_HINTS = {
    "Skattkärrs IK": "Karlstad",
    "Hultsberg IBF": "Karlstad",
    "BK Vålberg": "Karlstad",
    "IFK Haninge": "Haninge",
    "Älta IF": "Nacka",
    "IBK Lund": "Lund",
    "Järfälla Bele IBK": "Järfälla",
    "Mesta IBK": "Eskilstuna",
    "Torshälla IBK": "Eskilstuna",
    "Husqvarna IK": "Jönköping",
    "Craftstadens IBK Oskarshamn": "Oskarshamn",
    "FBC Karlskrona": "Karlskrona",
    "Vallentuna IBK": "Vallentuna",
    "Team Thorengruppen SK": "Umeå",
    "Umeå City IBK": "Umeå",
    "Umeå City IBF": "Umeå",
    "Hammarbyhöjden IBK": "Stockholm",
    "Älvsjö AIK IBF": "Stockholm",
    "Westerviks IBK": "Västervik",
    "Åstorp/Kvidinge IBS": "Åstorp",
    "Väsby AIK": "Upplands Väsby",
    "Högalids IF": "Stockholm",
    "BC Tulpankungen Stockholm IBK": "Stockholm",
    "Västerås IBS": "Västerås",
    "Boxholms IBK": "Boxholm",
    "Katrineholms IBF": "Katrineholm",
    "IBK Mantorp": "Mantorp",
    "Gantofta IBK": "Helsingborg",
    "Linköping IBK Ungdom": "Linköping",
    "Linköping IBS": "Linköping",
    "BKI Sunnanå": "Karlstad",
    "Nilsby IK": "Kil",
    "Tvååkers IBK": "Tvååker",
    "Ingelstad IBK": "Växjö",
    "IK Stanstad": "Staffanstorp",
    "Höllvikens IBF": "Höllviken",
    "Degerfors IBK": "Degerfors",
    "Onsala IBK": "Kungsbacka",
    "IBK Landskrona": "Landskrona",
}


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


def normalize_team_name(name):
    value = str(name or "").strip()

    for suffix in [
        " (A)",
        " (B)",
        " (C)",
        " A",
        " B",
        " C",
        " U",
        " U-lag",
        " Ungdom",
    ]:
        if value.endswith(suffix):
            value = value[
                : -len(suffix)
            ].strip()

    return value


def infer_city(teams):
    city_counter = Counter()

    for team, count in teams.items():
        normalized = normalize_team_name(
            team
        )

        for key, city in TEAM_CITY_HINTS.items():
            if (
                normalized == key
                or normalized.startswith(
                    key
                )
            ):
                city_counter[city] += count

    if not city_counter:
        return ""

    return city_counter.most_common(
        1
    )[0][0]


def geocode(query):
    params = urlencode(
        {
            "q": query,
            "format": "jsonv2",
            "limit": 5,
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


def score_result(
    arena,
    city,
    result,
):
    display = (
        result.get(
            "display_name",
            ""
        ).lower()
    )

    score = 0

    arena_words = [
        word.lower()
        for word in arena.replace(
            "-",
            " "
        ).split()
        if len(word) >= 4
    ]

    for word in arena_words:
        if word in display:
            score += 2

    if city.lower() in display:
        score += 4

    if (
        "sverige" in display
        or "sweden" in display
    ):
        score += 1

    return score


def choose_best(
    arena,
    city,
    results,
):
    if not results:
        return None

    ranked = sorted(
        results,
        key=lambda item: score_result(
            arena,
            city,
            item,
        ),
        reverse=True,
    )

    best = ranked[0]

    if score_result(
        arena,
        city,
        best,
    ) < 5:
        return None

    return best


def main():
    print()
    print(
        "============================================="
    )
    print(
        " EVENTFINDER - ARENAGEOKODNING PASS 2"
    )
    print(
        "============================================="
    )
    print()

    events = load_json(
        EVENT_FILE,
        [],
    )

    cache = load_json(
        CACHE_FILE,
        {},
    )

    missing = defaultdict(
        Counter
    )

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

        home = event.get(
            "hemmalag"
        )

        if (
            not arena
            or not home
        ):
            continue

        missing[arena][home] += 1

    arenas = sorted(
        missing.keys()
    )

    print(
        f"Arenor kvar utan koordinater: "
        f"{len(arenas)}"
    )

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    found = 0
    failed = 0
    skipped_no_city = 0
    api_calls = 0

    for index, arena in enumerate(
        arenas,
        start=1,
    ):
        city = infer_city(
            missing[arena]
        )

        print(
            f"[{index}/{len(arenas)}] "
            f"{arena}"
        )

        if not city:
            print(
                "  Ingen säker ortsignal"
            )

            skipped_no_city += 1
            continue

        print(
            f"  ortsignal: {city}"
        )

        cache_key = (
            f"{arena}|{city}"
        )

        cached = cache.get(
            cache_key
        )

        if cached:
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

        query = (
            f"{arena}, {city}, Sweden"
        )

        results = geocode(
            query
        )

        api_calls += 1

        best = choose_best(
            arena,
            city,
            results,
        )

        if not best:
            cache[
                cache_key
            ] = {
                "lat": None,
                "lon": None,
                "city": city,
                "query": query,
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
            best["lat"]
        )

        lon = float(
            best["lon"]
        )

        display_name = (
            best.get(
                "display_name",
                ""
            )
        )

        cache[
            cache_key
        ] = {
            "lat": lat,
            "lon": lon,
            "city": city,
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

        city = infer_city(
            missing.get(
                arena,
                Counter(),
            )
        )

        if not city:
            continue

        geo = cache.get(
            f"{arena}|{city}"
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

        event["ort"] = city

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
        ] = "Nominatim_pass2"

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
        " PASS 2 KLAR"
    )
    print(
        "============================================="
    )

    print()
    print(
        f"Arenor med ny träff: "
        f"{found}"
    )

    print(
        f"Arenor utan säker träff: "
        f"{failed}"
    )

    print(
        f"Arenor utan ortsignal: "
        f"{skipped_no_city}"
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
