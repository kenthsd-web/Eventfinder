import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"

BACKUP_FILE = (
    DATA_DIR
    / "events_before_all_remaining_geocode.json"
)

CACHE_FILE = (
    DATA_DIR
    / "all_remaining_geocode_cache.json"
)

REPORT_FILE = (
    DATA_DIR
    / "all_remaining_geocode_report.json"
)

USER_AGENT = (
    "Eventfinder/1.0 "
    "(Swedish sports arena geocoding)"
)


DISTRICT_HINTS = {
    "Stockholm": "Stockholms län",
    "Uppland": "Uppsala län",
    "Södermanland": "Södermanland",
    "Värmland": "Värmland",
    "Västerbotten": "Västerbotten",
    "Västmanland": "Västmanland",
    "Örebro Län": "Örebro",
    "Östergötland": "Östergötland",
    "Halland": "Halland",
    "Skåne": "Skåne",
    "Småland-Blekinge": "Småland",
    "Norrbotten": "Norrbotten",
    "Dalarna": "Dalarna",
    "Gävleborg": "Gävleborg",
}


TEAM_CITY_HINTS = {
    "Skattkärrs IK": "Karlstad",
    "Hultsberg IBF": "Karlstad",
    "BK Vålberg": "Karlstad",
    "IFK Haninge": "Haninge",
    "Älta IF": "Älta",
    "IBK Lund": "Lund",
    "Järfälla Bele IBK": "Järfälla",
    "Mesta IBK": "Eskilstuna",
    "Torshälla IBK": "Eskilstuna",
    "IK Standard": "Eskilstuna",
    "Husqvarna IK": "Huskvarna",
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
    "Gantofta IBK": "Gantofta",
    "Linköping IBK Ungdom": "Linköping",
    "Linköping IBS": "Linköping",
    "BKI Sunnanå": "Karlstad",
    "Nilsby IK": "Kil",
    "Tvååkers IBK": "Tvååker",
    "Ingelstad IBK": "Ingelstad",
    "IK Stanstad": "Staffanstorp",
    "Höllvikens IBF": "Höllviken",
    "Degerfors IBK": "Degerfors",
    "Onsala IBK": "Onsala",
    "IBK Landskrona": "Landskrona",
    "Sävsjö IBK": "Sävsjö",
    "IBF Tranås": "Tranås",
    "CL98IC": "Kalmar",
    "Rimforsa IF": "Rimforsa",
    "Solfjäderstaden IBK": "Motala",
    "Åby IBK": "Åby",
    "Onyx IBS": "Nyköping",
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


def clean(text):
    return re.sub(
        r"\s+",
        " ",
        str(text or ""),
    ).strip()


def norm(text):
    value = clean(text).lower()

    replacements = {
        "å": "a",
        "ä": "a",
        "ö": "o",
        "é": "e",
        "–": "-",
        "—": "-",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    return value


def normalize_team_name(name):
    value = clean(name)

    value = re.sub(
        r"\s+\([ABC]\)$",
        "",
        value,
    )

    value = re.sub(
        r"\s+(A|B|C|U-lag|U)$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    return value.strip()


def infer_city(team_counter):
    cities = Counter()

    for team, count in team_counter.items():
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
                cities[city] += count

    if not cities:
        return ""

    return cities.most_common(
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


def arena_words(arena):
    words = re.split(
        r"[\s\-/]+",
        norm(arena),
    )

    stop = {
        "arena",
        "sporthall",
        "sporthallen",
        "hallen",
        "hall",
        "idrottshall",
        "idrottshallen",
        "a",
        "b",
        "c",
        "1",
        "2",
        "3",
    }

    return [
        word
        for word in words
        if len(word) >= 4
        and word not in stop
    ]


def score_result(
    arena,
    city,
    district,
    result,
):
    display = norm(
        result.get(
            "display_name",
            ""
        )
    )

    score = 0

    words = arena_words(
        arena
    )

    matched_words = 0

    for word in words:
        if word in display:
            matched_words += 1
            score += 3

    if words and matched_words == len(words):
        score += 2

    if city:
        city_norm = norm(city)

        if city_norm in display:
            score += 7
        else:
            score -= 3

    district_hint = DISTRICT_HINTS.get(
        district,
        "",
    )

    if district_hint:
        if norm(
            district_hint
        ) in display:
            score += 2

    if (
        "sverige" in display
        or "sweden" in display
    ):
        score += 1

    result_type = norm(
        result.get(
            "type",
            ""
        )
    )

    category = norm(
        result.get(
            "category",
            ""
        )
    )

    if any(
        token in (
            result_type
            + " "
            + category
        )
        for token in [
            "sports",
            "stadium",
            "sports_centre",
            "leisure",
        ]
    ):
        score += 2

    return score


def build_queries(
    arena,
    city,
    district,
):
    queries = []

    if city:
        queries.extend(
            [
                f"{arena}, {city}, Sweden",
                f"{arena}, {city}",
            ]
        )

    district_hint = DISTRICT_HINTS.get(
        district,
        "",
    )

    if district_hint:
        queries.append(
            f"{arena}, {district_hint}, Sweden"
        )

    queries.append(
        f"{arena}, Sweden"
    )

    unique = []

    for query in queries:
        if query not in unique:
            unique.append(
                query
            )

    return unique


def find_best_match(
    arena,
    city,
    district,
):
    best = None

    best_score = -999

    best_query = ""

    queries = build_queries(
        arena,
        city,
        district,
    )

    calls = 0

    for query in queries:
        results = geocode(
            query
        )

        calls += 1

        for result in results:
            score = score_result(
                arena,
                city,
                district,
                result,
            )

            if score > best_score:
                best = result
                best_score = score
                best_query = query

        time.sleep(
            1.1
        )

    return (
        best,
        best_score,
        best_query,
        calls,
    )


def main():
    print()
    print(
        "============================================="
    )
    print(
        " EVENTFINDER - GEOKODAR ALLA KVARVARANDE"
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

    if not isinstance(
        events,
        list,
    ):
        raise RuntimeError(
            "events.json är inte en lista."
        )

    missing = defaultdict(
        lambda: {
            "teams": Counter(),
            "districts": Counter(),
            "count": 0,
        }
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

        arena = clean(
            event.get(
                "arena"
            )
        )

        if not arena:
            continue

        missing[
            arena
        ][
            "count"
        ] += 1

        home = clean(
            event.get(
                "hemmalag"
            )
        )

        if home:
            missing[
                arena
            ][
                "teams"
            ][home] += 1

        district = clean(
            event.get(
                "district"
            )
        )

        if district:
            missing[
                arena
            ][
                "districts"
            ][district] += 1

    arenas = sorted(
        missing.keys(),
        key=lambda arena:
            missing[
                arena
            ][
                "count"
            ],
        reverse=True,
    )

    print(
        f"Arenor kvar: "
        f"{len(arenas)}"
    )

    print(
        f"Matcher kvar utan koordinater: "
        f"{sum(missing[a]['count'] for a in arenas)}"
    )

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    report = {}

    accepted = 0
    rejected = 0
    cache_hits = 0
    api_calls = 0

    for index, arena in enumerate(
        arenas,
        start=1,
    ):
        info = missing[
            arena
        ]

        city = infer_city(
            info[
                "teams"
            ]
        )

        district = ""

        if info[
            "districts"
        ]:
            district = (
                info[
                    "districts"
                ]
                .most_common(
                    1
                )[0][0]
            )

        cache_key = (
            f"{arena}|{city}|{district}"
        )

        print()
        print(
            f"[{index}/{len(arenas)}] "
            f"{arena}"
        )

        print(
            f"  matcher: "
            f"{info['count']}"
        )

        if city:
            print(
                f"  ortsignal: "
                f"{city}"
            )

        if district:
            print(
                f"  distrikt: "
                f"{district}"
            )

        cached = cache.get(
            cache_key
        )

        if cached is not None:
            cache_hits += 1

            if cached.get(
                "accepted"
            ):
                print(
                    f"  cache: "
                    f"{cached['lat']}, "
                    f"{cached['lon']}"
                )
                accepted += 1
            else:
                print(
                    "  cache: ej godkänd"
                )
                rejected += 1

            report[
                arena
            ] = cached

            continue

        (
            best,
            score,
            query,
            calls,
        ) = find_best_match(
            arena,
            city,
            district,
        )

        api_calls += calls

        accepted_match = (
            best is not None
            and score >= 8
        )

        if not accepted_match:
            cache[
                cache_key
            ] = {
                "accepted": False,
                "score": score,
                "city_hint": city,
                "district_hint": district,
                "query": query,
                "lat": None,
                "lon": None,
                "display_name": (
                    best.get(
                        "display_name",
                        ""
                    )
                    if best
                    else ""
                ),
            }

            report[
                arena
            ] = cache[
                cache_key
            ]

            print(
                f"  EJ GODKÄND "
                f"(score {score})"
            )

            if best:
                print(
                    f"  {best.get('display_name', '')}"
                )

            rejected += 1

            continue

        lat = float(
            best[
                "lat"
            ]
        )

        lon = float(
            best[
                "lon"
            ]
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
            "accepted": True,
            "score": score,
            "city_hint": city,
            "district_hint": district,
            "query": query,
            "lat": lat,
            "lon": lon,
            "display_name":
                display_name,
        }

        report[
            arena
        ] = cache[
            cache_key
        ]

        print(
            f"  GODKÄND score "
            f"{score}"
        )

        print(
            f"  {lat}, {lon}"
        )

        print(
            f"  {display_name}"
        )

        accepted += 1

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

        arena = clean(
            event.get(
                "arena"
            )
        )

        if not arena:
            continue

        result = report.get(
            arena
        )

        if not result:
            continue

        if not result.get(
            "accepted"
        ):
            continue

        event[
            "lat"
        ] = result[
            "lat"
        ]

        event[
            "lon"
        ] = result[
            "lon"
        ]

        if (
            not event.get(
                "ort"
            )
            and result.get(
                "city_hint"
            )
        ):
            event[
                "ort"
            ] = result[
                "city_hint"
            ]

        event[
            "geocode_query"
        ] = result.get(
            "query",
            "",
        )

        event[
            "geocode_display_name"
        ] = result.get(
            "display_name",
            "",
        )

        event[
            "geocode_source"
        ] = "Nominatim_auto_pass3"

        event[
            "location_precision"
        ] = "arena"

        event[
            "geocode_score"
        ] = result.get(
            "score"
        )

        updated += 1

    save_json(
        CACHE_FILE,
        cache,
    )

    save_json(
        REPORT_FILE,
        report,
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

    total_matches = sum(
        1
        for event in events
        if event.get(
            "source_type"
        )
        == "district_competition_full_schedule"
    )

    print()
    print(
        "============================================="
    )
    print(
        " PASS 3 KLAR"
    )
    print(
        "============================================="
    )
    print()

    print(
        f"Arenor automatiskt godkända: "
        f"{accepted}"
    )

    print(
        f"Arenor ej godkända: "
        f"{rejected}"
    )

    print(
        f"Cache-träffar: "
        f"{cache_hits}"
    )

    print(
        f"API-anrop: "
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
        f"{total_matches}"
    )

    if total_matches:
        coverage = (
            100
            * with_coords
            / total_matches
        )

        print(
            f"Täckning: "
            f"{coverage:.1f}%"
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
        f"Rapport: "
        f"{REPORT_FILE}"
    )


if __name__ == "__main__":
    main()
