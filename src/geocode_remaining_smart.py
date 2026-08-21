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
    / "events_before_smart_remaining_geocode.json"
)

CACHE_FILE = (
    DATA_DIR
    / "smart_remaining_geocode_cache.json"
)

REPORT_FILE = (
    DATA_DIR
    / "smart_remaining_geocode_report.json"
)

USER_AGENT = (
    "Eventfinder/1.0 "
    "(Swedish sports arena geocoding)"
)


# ============================================================
# DISTRIKTSHINTAR
# ============================================================

DISTRICT_HINTS = {
    "Stockholm": "Stockholm",
    "Uppland": "Uppsala",
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


# ============================================================
# LAG -> ORT
# ============================================================

TEAM_CITY_HINTS = {
    "Team Thorengruppen SK": "Umeå",
    "Umeå City IBK": "Umeå",
    "Umeå City IBF": "Umeå",

    "Katrineholms IBF": "Katrineholm",

    "IBK Mantorp": "Mantorp",

    "Gantofta IBK": "Gantofta",

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

    "Rimforsa IF": "Rimforsa",

    "Åby IBK": "Åby",

    "Onyx IBS": "Nyköping",

    "Tungelsta IF": "Tungelsta",

    "Järfälla Bele IBK": "Järfälla",

    "Craftstadens IBK Oskarshamn": "Oskarshamn",

    "FBC Karlskrona": "Karlskrona",

    "Skattkärrs IK": "Karlstad",

    "Väsby AIK": "Upplands Väsby",

    "Husqvarna IK": "Huskvarna",

    "Westerviks IBK": "Västervik",

    "Boxholms IBK": "Boxholm",

    "Åstorp/Kvidinge IBS": "Åstorp",

    "Västerås IBS": "Västerås",

    "Vallentuna IBK": "Vallentuna",

    "Linköping IBK Ungdom": "Linköping",

    "Linköping IBS": "Linköping",

    "Mesta IBK": "Eskilstuna",

    "Torshälla IBK": "Eskilstuna",

    "IFK Haninge": "Haninge",

    "Älta IF": "Älta",

    "IBK Lund": "Lund",
}


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
# TEXT
# ============================================================

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
        value = value.replace(
            old,
            new,
        )

    return value


def normalize_team(name):
    value = clean(name)

    value = re.sub(
        r"\s+\([ABC]\)$",
        "",
        value,
    )

    value = re.sub(
        r"\s+(A|B|C|U|U-lag)$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    return value.strip()


# ============================================================
# ORTSIGNAL
# ============================================================

def infer_city(team_counter):
    cities = Counter()

    for team, count in team_counter.items():
        normalized = normalize_team(
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


# ============================================================
# ARENAVARIANTER
# ============================================================

def arena_variants(arena):
    variants = []

    def add(value):
        value = clean(value)

        if (
            value
            and value not in variants
        ):
            variants.append(
                value
            )

    add(arena)

    value = arena

    # Ta bort plan/hall-suffix.
    replacements = [
        r"\s+A-hall$",
        r"\s+B-hall$",
        r"\s+A$",
        r"\s+B$",
        r"\s+C$",
        r"\s+Plan\s+\d+$",
        r"\s+\d+$",
        r"\s+\([A-Z]\)$",
        r",\s*3-manna$",
        r"\s+3-manna$",
    ]

    for pattern in replacements:
        simplified = re.sub(
            pattern,
            "",
            value,
            flags=re.IGNORECASE,
        )

        add(
            simplified
        )

    # Vanliga specialsuffix.
    simplified = re.sub(
        r"\s+Mirva\s+\([A-Z]\)$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    add(
        simplified
    )

    simplified = re.sub(
        r"\s+DHinox\s+\([A-Z]\)$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    add(
        simplified
    )

    simplified = re.sub(
        r"\s+Upplands Energi\s+\([A-Z]\)$",
        "",
        value,
        flags=re.IGNORECASE,
    )

    add(
        simplified
    )

    # IFU Arena-varianter.
    if norm(value).startswith(
        "ifu arena"
    ):
        add(
            "IFU Arena"
        )

    # Fortnox.
    if norm(value).startswith(
        "fortnox arena"
    ):
        add(
            "Fortnox Arena"
        )

    # Nolia.
    if norm(value).startswith(
        "nolia arena"
    ):
        add(
            "Nolia"
        )

    # Rosvalla.
    if norm(value).startswith(
        "rosvalla"
    ):
        add(
            "Rosvalla"
        )

    # Halmstad Arena.
    if norm(value).startswith(
        "halmstad arena"
    ):
        add(
            "Halmstad Arena"
        )

    # Mälarenergi.
    if norm(value).startswith(
        "malarenergi arena"
    ):
        add(
            "Mälarenergi Arena"
        )

    return variants


# ============================================================
# NOMINATIM
# ============================================================

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


# ============================================================
# SCORE
# ============================================================

GENERIC_ARENA_WORDS = {
    "arena",
    "sporthall",
    "sporthallen",
    "idrottshall",
    "idrottshallen",
    "hallen",
    "hall",
    "sportcenter",
    "sportcentra",
    "plan",
}


def meaningful_words(text):
    words = re.split(
        r"[\s\-/(),]+",
        norm(text),
    )

    return [
        word
        for word in words
        if (
            len(word) >= 4
            and word
            not in GENERIC_ARENA_WORDS
        )
    ]


def score_result(
    arena_variant,
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

    words = meaningful_words(
        arena_variant
    )

    matched = 0

    for word in words:
        if word in display:
            matched += 1
            score += 4

    if words and matched == len(
        words
    ):
        score += 3

    if city:
        if norm(city) in display:
            score += 8
        else:
            score -= 4

    district_hint = DISTRICT_HINTS.get(
        district,
        "",
    )

    if (
        district_hint
        and norm(
            district_hint
        ) in display
    ):
        score += 2

    category = norm(
        result.get(
            "category",
            ""
        )
    )

    result_type = norm(
        result.get(
            "type",
            ""
        )
    )

    if any(
        token in (
            category
            + " "
            + result_type
        )
        for token in [
            "leisure",
            "sports",
            "sports_centre",
            "stadium",
        ]
    ):
        score += 2

    if "sverige" in display:
        score += 1

    return score


# ============================================================
# SÖKFRÅGOR
# ============================================================

def build_queries(
    arena,
    city,
    district,
):
    variants = arena_variants(
        arena
    )

    queries = []

    def add(
        variant,
        query,
    ):
        item = (
            variant,
            clean(query),
        )

        if (
            item[1]
            and item
            not in queries
        ):
            queries.append(
                item
            )

    for variant in variants:
        if city:
            add(
                variant,
                f"{variant}, {city}, Sweden",
            )

        district_hint = (
            DISTRICT_HINTS.get(
                district,
                ""
            )
        )

        if district_hint:
            add(
                variant,
                f"{variant}, {district_hint}, Sweden",
            )

        add(
            variant,
            f"{variant}, Sweden",
        )

    return queries


# ============================================================
# HITTA BÄSTA
# ============================================================

def find_best(
    arena,
    city,
    district,
):
    best = None
    best_score = -999
    best_query = ""
    best_variant = ""

    calls = 0

    queries = build_queries(
        arena,
        city,
        district,
    )

    # Begränsa antalet frågor per arena.
    queries = queries[:8]

    for (
        variant,
        query,
    ) in queries:
        results = geocode(
            query
        )

        calls += 1

        for result in results:
            score = score_result(
                variant,
                city,
                district,
                result,
            )

            if score > best_score:
                best_score = score
                best = result
                best_query = query
                best_variant = variant

        time.sleep(
            1.05
        )

    return (
        best,
        best_score,
        best_query,
        best_variant,
        calls,
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
        " EVENTFINDER - SMART GEOKODNING KVARVARANDE"
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
            "count": 0,
            "teams": Counter(),
            "districts": Counter(),
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

    print()

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

    # Hög gräns eftersom vi vill vara försiktiga.
    MIN_SCORE = 10

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
                    f"  CACHE GODKÄND "
                    f"score "
                    f"{cached.get('score')}"
                )

                accepted += 1
            else:
                print(
                    f"  CACHE EJ GODKÄND "
                    f"score "
                    f"{cached.get('score')}"
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
            variant,
            calls,
        ) = find_best(
            arena,
            city,
            district,
        )

        api_calls += calls

        accepted_match = (
            best is not None
            and score >= MIN_SCORE
        )

        if not accepted_match:
            result = {
                "accepted":
                    False,

                "score":
                    score,

                "arena_variant":
                    variant,

                "city_hint":
                    city,

                "district_hint":
                    district,

                "query":
                    query,

                "lat":
                    None,

                "lon":
                    None,

                "display_name":
                    (
                        best.get(
                            "display_name",
                            "",
                        )
                        if best
                        else ""
                    ),
            }

            cache[
                cache_key
            ] = result

            report[
                arena
            ] = result

            print(
                f"  EJ GODKÄND "
                f"score {score}"
            )

            if best:
                print(
                    f"  variant: "
                    f"{variant}"
                )

                print(
                    f"  {best.get('display_name', '')}"
                )

            rejected += 1

            # Spara efter varje arena.
            save_json(
                CACHE_FILE,
                cache,
            )

            save_json(
                REPORT_FILE,
                report,
            )

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

        result = {
            "accepted":
                True,

            "score":
                score,

            "arena_variant":
                variant,

            "city_hint":
                city,

            "district_hint":
                district,

            "query":
                query,

            "lat":
                lat,

            "lon":
                lon,

            "display_name":
                best.get(
                    "display_name",
                    "",
                ),
        }

        cache[
            cache_key
        ] = result

        report[
            arena
        ] = result

        print(
            f"  GODKÄND "
            f"score {score}"
        )

        print(
            f"  variant: "
            f"{variant}"
        )

        print(
            f"  {lat}, "
            f"{lon}"
        )

        print(
            f"  "
            f"{result['display_name']}"
        )

        accepted += 1

        # Spara löpande så Ctrl+C inte förstör rapporten.
        save_json(
            CACHE_FILE,
            cache,
        )

        save_json(
            REPORT_FILE,
            report,
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

        # Aldrig skriv över tidigare koordinater.
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

        geo = report.get(
            arena
        )

        if not geo:
            continue

        if not geo.get(
            "accepted"
        ):
            continue

        event[
            "lat"
        ] = geo[
            "lat"
        ]

        event[
            "lon"
        ] = geo[
            "lon"
        ]

        if (
            not event.get(
                "ort"
            )
            and geo.get(
                "city_hint"
            )
        ):
            event[
                "ort"
            ] = geo[
                "city_hint"
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
        ] = "Nominatim_smart"

        event[
            "location_precision"
        ] = "arena"

        event[
            "geocode_score"
        ] = geo.get(
            "score"
        )

        updated += 1

    save_json(
        EVENT_FILE,
        events,
    )

    save_json(
        CACHE_FILE,
        cache,
    )

    save_json(
        REPORT_FILE,
        report,
    )

    total_matches = sum(
        1
        for event in events
        if event.get(
            "source_type"
        )
        == "district_competition_full_schedule"
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

    remaining = (
        total_matches
        - with_coords
    )

    print()
    print(
        "============================================="
    )
    print(
        " SMART GEOKODNING KLAR"
    )
    print(
        "============================================="
    )
    print()

    print(
        f"Arenor godkända: "
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

    print()
    print(
        f"Distriktsmatcher totalt: "
        f"{total_matches}"
    )

    print(
        f"Med koordinater: "
        f"{with_coords}"
    )

    print(
        f"Kvar utan koordinater: "
        f"{remaining}"
    )

    if total_matches:
        print(
            f"Täckning: "
            f"{100 * with_coords / total_matches:.1f}%"
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
