import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# EVENTFINDER - ALL SVENSK SENIORINNEBANDY 2026/27
# API DISCOVERY + FULL SCHEDULE
# ============================================================

SEASON = "2026/27"
SEASON_ID = 44
SPORT = "Innebandy"

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
DEBUG_DIR = DATA_DIR / "all_senior_floorball_debug"

SOURCE_FILE = (
    DATA_DIR
    / "floorball_district_sources.json"
)

EVENT_FILE = (
    DATA_DIR
    / "events.json"
)

BACKUP_FILE = (
    DATA_DIR
    / "events_before_all_senior_import.json"
)

COMPETITION_DEBUG_FILE = (
    DATA_DIR
    / "floorball_senior_competitions.json"
)

STATS_BASE = (
    "https://stats.innebandy.se"
)

API_BASE = (
    "https://api.innebandy.se/v2/api"
)


# ============================================================
# MÅNADER
# ============================================================

MONTHS = {
    "januari": 1,
    "februari": 2,
    "mars": 3,
    "april": 4,
    "maj": 5,
    "juni": 6,
    "juli": 7,
    "augusti": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}


# ============================================================
# REGEX
# ============================================================

TIME_ONLY_PATTERN = re.compile(
    r"^([01]?\d|2[0-3]):([0-5]\d)$"
)

#
# Exempel:
#
# 18 september 19:30 Värmdö sporthall
# 6 februari 14:15 Lyckeby Sporthall
#
FULL_MATCH_INFO_PATTERN = re.compile(
    r"^"
    r"(\d{1,2})\s+"
    r"(januari|februari|mars|april|maj|juni|juli|augusti|"
    r"september|oktober|november|december)"
    r"\s+"
    r"([01]?\d|2[0-3]):([0-5]\d)"
    r"(?:\s+(.*))?"
    r"$",
    re.IGNORECASE,
)


# ============================================================
# EXKLUDERINGAR
# ============================================================

EXCLUDE_WORDS = [
    "junior",
    "juniorallsvenskan",
    "jas",
    "pantamera",
    "pojkar",
    "flickor",
    "ungdom",
    "u19",
    "u18",
    "u17",
    "u16",
    "u15",
    "u14",
    "u13",
    "u12",
    "veteran",
    "oldboys",
    "old girls",
    "träningsmatch",
    "traningsmatch",
    "svenska cupen",
    "bäst i stan",
    "bast i stan",
]


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


def safe_filename(text):
    value = norm(text)

    value = re.sub(
        r"[^a-z0-9]+",
        "_",
        value,
    )

    return value.strip("_")


# ============================================================
# DATA
# ============================================================

def load_sources():
    if not SOURCE_FILE.exists():
        raise FileNotFoundError(
            f"Saknar {SOURCE_FILE}"
        )

    data = json.loads(
        SOURCE_FILE.read_text(
            encoding="utf-8"
        )
    )

    districts = data.get(
        "districts",
        []
    )

    if not districts:
        raise RuntimeError(
            "Inga distrikt hittades."
        )

    return districts


def load_events():
    if not EVENT_FILE.exists():
        return []

    data = json.loads(
        EVENT_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(
        data,
        list,
    ):
        raise RuntimeError(
            "events.json är inte en lista."
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
# SENIORSERIE?
# ============================================================

def is_senior_competition(
    competition,
    expected_federation_id,
):
    federation_id = (
        competition.get(
            "FederationID"
        )
    )

    season_id = (
        competition.get(
            "SeasonID"
        )
    )

    age_id = (
        competition.get(
            "AgeCategoryID"
        )
    )

    gender_id = (
        competition.get(
            "GenderID"
        )
    )

    schedule_public = (
        competition.get(
            "SchedulePublic"
        )
    )

    name = clean(
        competition.get(
            "Name"
        )
    )

    category = clean(
        competition.get(
            "CategoryName"
        )
    )

    combined = norm(
        name
        + " "
        + category
    )

    # Rätt distrikt.
    if str(
        federation_id
    ) != str(
        expected_federation_id
    ):
        return False

    # Rätt säsong.
    if int(
        season_id or 0
    ) != SEASON_ID:
        return False

    # Publikt spelprogram.
    if schedule_public is not True:
        return False

    # Senior/junior ligger båda på 4.
    # Veteran ligger på 5.
    if age_id != 4:
        return False

    # 2 = Herr
    # 3 = Dam
    if gender_id not in (
        2,
        3,
    ):
        return False

    # Junior m.m. filtreras med namn.
    for word in EXCLUDE_WORDS:
        if norm(word) in combined:
            return False

    # Behåll divisionsserier.
    if (
        "division" not in combined
        and " div " not in combined
        and not combined.startswith(
            "div "
        )
    ):
        return False

    return True


# ============================================================
# API DISCOVERY
# ============================================================

def capture_competitions(
    browser,
    source,
):
    federation_id = str(
        source[
            "forbund_id"
        ]
    )

    page_url = (
        f"{STATS_BASE}/"
        f"forbund/{federation_id}/"
        f"livematches"
    )

    target_url = (
        f"{API_BASE}/"
        f"seasons/{SEASON_ID}/"
        f"federations/{federation_id}/"
        f"competitions"
    )

    page = browser.new_page(
        viewport={
            "width": 1440,
            "height": 1200,
        }
    )

    captured = []

    def handle_response(response):
        if response.url != target_url:
            return

        try:
            data = response.json()

            if isinstance(
                data,
                list,
            ):
                captured.append(
                    data
                )

        except Exception:
            pass

    page.on(
        "response",
        handle_response,
    )

    try:
        page.goto(
            page_url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        for _ in range(40):
            if captured:
                break

            page.wait_for_timeout(
                250
            )

        if not captured:
            print(
                f"  API-svar saknas för "
                f"förbund {federation_id}."
            )

            return []

        data = captured[-1]

        senior = [
            item
            for item in data
            if is_senior_competition(
                item,
                federation_id,
            )
        ]

        print(
            f"  API-serier totalt: "
            f"{len(data)}"
        )

        print(
            f"  Seniorserier efter filter: "
            f"{len(senior)}"
        )

        return senior

    finally:
        page.close()


# ============================================================
# DATUM/TID/ARENA FRÅN FULL-RAD
# ============================================================

def parse_match_info_line(text):
    value = clean(
        text
    )

    match = (
        FULL_MATCH_INFO_PATTERN.match(
            value
        )
    )

    if not match:
        return None

    day = int(
        match.group(1)
    )

    month_name = (
        match.group(2)
        .lower()
    )

    hour = int(
        match.group(3)
    )

    minute = int(
        match.group(4)
    )

    arena = clean(
        match.group(5)
        or ""
    )

    month = MONTHS.get(
        month_name
    )

    if not month:
        return None

    year = (
        2026
        if month >= 8
        else 2027
    )

    try:
        date_value = datetime(
            year,
            month,
            day,
        ).strftime(
            "%Y-%m-%d"
        )

    except ValueError:
        return None

    time_value = (
        f"{hour:02d}:"
        f"{minute:02d}"
    )

    return {
        "date": date_value,
        "time": time_value,
        "arena": arena,
    }


def is_time_only(text):
    return bool(
        TIME_ONLY_PATTERN.match(
            clean(text)
        )
    )


# ============================================================
# SYSTEMRADER
# ============================================================

SYSTEM_LINES = {
    "hela",
    "<<",
    ">>",
    "tabell",
    "statistik",
    "spelprogram",
    "matchinfo",
    "saknas",
}


def is_system_line(text):
    value = norm(
        text
    )

    if value in SYSTEM_LINES:
        return True

    if value.startswith(
        "valj "
    ):
        return True

    return False


def is_team_candidate(text):
    value = clean(
        text
    )

    if not value:
        return False

    if is_system_line(
        value
    ):
        return False

    if is_time_only(
        value
    ):
        return False

    if parse_match_info_line(
        value
    ):
        return False

    lower = norm(
        value
    )

    bad = [
        "turneringar",
        "serier",
        "matcher",
        "statistik",
        "landslag",
        "sok",
        "2026/27",
    ]

    if lower in bad:
        return False

    if len(value) > 120:
        return False

    return True


# ============================================================
# EVENT
# ============================================================

def create_event_id(
    competition_id,
    date_value,
    time_value,
    home,
    away,
):
    identity = "|".join(
        [
            SPORT,
            SEASON,
            str(
                competition_id
            ),
            date_value,
            time_value,
            home,
            away,
        ]
    )

    return hashlib.sha256(
        identity.encode(
            "utf-8"
        )
    ).hexdigest()[:20]


def make_event(
    district,
    competition,
    date_value,
    time_value,
    home,
    away,
    arena,
    url,
):
    competition_id = (
        competition[
            "CompetitionID"
        ]
    )

    return {
        "id": create_event_id(
            competition_id,
            date_value,
            time_value,
            home,
            away,
        ),

        "sport": SPORT,
        "typ": "match",
        "sasong": SEASON,

        "district":
            district,

        "serie":
            clean(
                competition[
                    "Name"
                ]
            ),

        "competition_id":
            competition_id,

        "category":
            competition.get(
                "CategoryName",
                "",
            ),

        "federation_id":
            competition.get(
                "FederationID"
            ),

        "federation_name":
            competition.get(
                "FederationName",
                "",
            ),

        "gender_id":
            competition.get(
                "GenderID"
            ),

        "namn":
            f"{home} - {away}",

        "hemmalag":
            home,

        "bortalag":
            away,

        "datum":
            date_value,

        "datum_start":
            date_value,

        "datum_slut":
            date_value,

        "datum_exakt":
            True,

        "tid":
            time_value,

        "arena":
            arena,

        "plats":
            arena,

        "ort":
            "",

        "kommun":
            "",

        "lat":
            None,

        "lon":
            None,

        "status":
            "schemalagd",

        "kalla":
            "Svensk Innebandy",

        "source_type":
            "district_competition_full_schedule",

        "url":
            url,

        "senast_uppdaterad":
            datetime.now().isoformat(
                timespec="seconds"
            ),
    }


# ============================================================
# FULL-SCHEDULE PARSER
# ============================================================

def extract_schedule_section(
    lines,
):
    positions = []

    for index, line in enumerate(
        lines
    ):
        if norm(line) == "spelprogram":
            positions.append(
                index
            )

    if positions:
        return lines[
            positions[-1] + 1:
        ]

    return lines


def find_teams_before_info(
    lines,
    info_index,
):
    """
    Verifierat format kan exempelvis vara:

        Värmdö IF (A)
        19:30
        Väsby AIK (A)
        18 september 19:30 Värmdö sporthall

    Då är:
        -3 = hemmalag
        -2 = separat tidslänk
        -1 = bortalag

    Vi har även en fallback som söker bakåt.
    """

    # --------------------------------------------------------
    # PRIMÄRT FORMAT
    # --------------------------------------------------------

    if info_index >= 3:
        possible_home = clean(
            lines[
                info_index - 3
            ]
        )

        possible_time = clean(
            lines[
                info_index - 2
            ]
        )

        possible_away = clean(
            lines[
                info_index - 1
            ]
        )

        if (
            is_team_candidate(
                possible_home
            )
            and is_time_only(
                possible_time
            )
            and is_team_candidate(
                possible_away
            )
        ):
            return (
                possible_home,
                possible_away,
            )

    # --------------------------------------------------------
    # ALTERNATIV:
    #
    # Hemmalag
    # Bortalag
    # datum tid arena
    # --------------------------------------------------------

    if info_index >= 2:
        possible_home = clean(
            lines[
                info_index - 2
            ]
        )

        possible_away = clean(
            lines[
                info_index - 1
            ]
        )

        if (
            is_team_candidate(
                possible_home
            )
            and is_team_candidate(
                possible_away
            )
        ):
            return (
                possible_home,
                possible_away,
            )

    # --------------------------------------------------------
    # FALLBACK:
    # sök bakåt efter två lämpliga lagnamn.
    # --------------------------------------------------------

    candidates = []

    start = max(
        0,
        info_index - 8,
    )

    for pos in range(
        info_index - 1,
        start - 1,
        -1,
    ):
        value = clean(
            lines[pos]
        )

        if is_time_only(
            value
        ):
            continue

        if not is_team_candidate(
            value
        ):
            continue

        candidates.append(
            value
        )

        if len(candidates) >= 2:
            break

    if len(candidates) < 2:
        return (
            "",
            "",
        )

    # Bakåtsökningen hittar away först,
    # sedan home.
    away = candidates[0]
    home = candidates[1]

    return (
        home,
        away,
    )


def parse_schedule(
    text,
    district,
    competition,
    url,
):
    lines = [
        clean(line)
        for line in text.splitlines()
        if clean(line)
    ]

    lines = extract_schedule_section(
        lines
    )

    events = []

    for index, line in enumerate(
        lines
    ):
        info = parse_match_info_line(
            line
        )

        if not info:
            continue

        (
            home,
            away,
        ) = find_teams_before_info(
            lines,
            index,
        )

        if (
            not home
            or not away
        ):
            continue

        if norm(home) == norm(away):
            continue

        events.append(
            make_event(
                district=district,
                competition=competition,
                date_value=info[
                    "date"
                ],
                time_value=info[
                    "time"
                ],
                home=home,
                away=away,
                arena=info[
                    "arena"
                ],
                url=url,
            )
        )

    return events


# ============================================================
# DEBUG
# ============================================================

def save_schedule_debug(
    district,
    competition,
    text,
):
    directory = (
        DEBUG_DIR
        / safe_filename(
            district
        )
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        f"{competition['CompetitionID']}_"
        f"{safe_filename(competition['Name'])}"
        ".txt"
    )

    (
        directory
        / filename
    ).write_text(
        text,
        encoding="utf-8",
    )


# ============================================================
# IMPORTERA SERIE
# ============================================================

def import_competition(
    browser,
    district,
    competition,
):
    competition_id = (
        competition[
            "CompetitionID"
        ]
    )

    url = (
        f"{STATS_BASE}/"
        f"sasong/{SEASON_ID}/"
        f"serie/{competition_id}/"
        f"spelprogram/full"
    )

    page = browser.new_page(
        viewport={
            "width": 1400,
            "height": 1400,
        }
    )

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(
            1000
        )

        text = (
            page.locator(
                "body"
            ).inner_text()
        )

        save_schedule_debug(
            district,
            competition,
            text,
        )

        return parse_schedule(
            text,
            district,
            competition,
            url,
        )

    finally:
        page.close()


# ============================================================
# DEDUPE
# ============================================================

def dedupe(events):
    unique = {}

    for event in events:
        unique[
            event["id"]
        ] = event

    return list(
        unique.values()
    )


# ============================================================
# MERGE
# ============================================================

def merge_events(
    existing,
    imported,
):
    result = list(
        existing
    )

    existing_ids = {
        event.get(
            "id"
        )
        for event in existing
        if event.get(
            "id"
        )
    }

    existing_match_keys = set()

    for event in existing:
        date_value = (
            event.get(
                "datum"
            )
            or event.get(
                "datum_start"
            )
            or ""
        )

        home = norm(
            event.get(
                "hemmalag",
                "",
            )
        )

        away = norm(
            event.get(
                "bortalag",
                "",
            )
        )

        if (
            date_value
            and home
            and away
        ):
            existing_match_keys.add(
                (
                    date_value,
                    home,
                    away,
                )
            )

    added = 0
    duplicate_matches = 0

    for event in imported:
        if (
            event["id"]
            in existing_ids
        ):
            continue

        match_key = (
            event[
                "datum"
            ],
            norm(
                event[
                    "hemmalag"
                ]
            ),
            norm(
                event[
                    "bortalag"
                ]
            ),
        )

        if (
            match_key
            in existing_match_keys
        ):
            duplicate_matches += 1
            continue

        result.append(
            event
        )

        existing_ids.add(
            event["id"]
        )

        existing_match_keys.add(
            match_key
        )

        added += 1

    return (
        result,
        added,
        duplicate_matches,
    )


# ============================================================
# SORTERING
# ============================================================

def sort_events(events):
    def key(event):
        return (
            event.get(
                "datum"
            )
            or event.get(
                "datum_start"
            )
            or "9999-12-31",

            event.get(
                "tid"
            )
            or "23:59",

            event.get(
                "namn",
                "",
            ),
        )

    return sorted(
        events,
        key=key,
    )


# ============================================================
# RAPPORT
# ============================================================

def report(
    imported,
    competition_catalog,
):
    district_counts = {}
    series_keys = set()

    with_time = 0
    with_arena = 0

    for event in imported:
        district = (
            event[
                "district"
            ]
        )

        district_counts[
            district
        ] = (
            district_counts.get(
                district,
                0,
            )
            + 1
        )

        series_keys.add(
            (
                district,
                event[
                    "competition_id"
                ],
            )
        )

        if event.get(
            "tid"
        ):
            with_time += 1

        if event.get(
            "arena"
        ):
            with_arena += 1

    print()
    print(
        "============================================="
    )
    print(
        " ALL SENIOR IMPORT-RAPPORT"
    )
    print(
        "============================================="
    )

    print()
    print(
        f"Upptäckta seniorserier: "
        f"{len(competition_catalog)}"
    )

    print(
        f"Importerade matcher: "
        f"{len(imported)}"
    )

    print(
        f"Distrikt med matcher: "
        f"{len(district_counts)}"
    )

    print(
        f"Seniorserier med matcher: "
        f"{len(series_keys)}"
    )

    print(
        f"Matcher med tid: "
        f"{with_time}"
    )

    print(
        f"Matcher med arena: "
        f"{with_arena}"
    )

    print()
    print(
        "Matcher per distrikt"
    )
    print(
        "-------------------"
    )

    for district, count in sorted(
        district_counts.items()
    ):
        print(
            f"{district}: "
            f"{count}"
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
        " EVENTFINDER - API SENIORINNEBANDY 2026/27"
    )
    print(
        "============================================="
    )

    sources = load_sources()
    existing = load_events()

    print()
    print(
        f"Distrikt: "
        f"{len(sources)}"
    )

    print(
        f"Befintliga event: "
        f"{len(existing)}"
    )

    DEBUG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_imported = []
    competition_catalog = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        try:
            # =================================================
            # 1. DISCOVERY
            # =================================================

            print()
            print(
                "============================================="
            )
            print(
                " HÄMTAR SENIORSERIER VIA API"
            )
            print(
                "============================================="
            )

            for index, source in enumerate(
                sources,
                start=1,
            ):
                district = (
                    source[
                        "district"
                    ]
                )

                federation_id = (
                    source[
                        "forbund_id"
                    ]
                )

                print()
                print(
                    f"[{index}/"
                    f"{len(sources)}] "
                    f"{district} "
                    f"(ID {federation_id})"
                )

                try:
                    competitions = (
                        capture_competitions(
                            browser,
                            source,
                        )
                    )

                except Exception as error:
                    print(
                        f"  FEL: {error}"
                    )
                    continue

                for competition in competitions:
                    competition_catalog.append(
                        {
                            "district":
                                district,

                            **competition,
                        }
                    )

                    print(
                        f"    "
                        f"{competition['CompetitionID']} | "
                        f"{competition['Name']} | "
                        f"{competition['CategoryName']}"
                    )

            COMPETITION_DEBUG_FILE.write_text(
                json.dumps(
                    competition_catalog,
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            print()
            print(
                f"Totalt upptäckta seniorserier: "
                f"{len(competition_catalog)}"
            )

            if not competition_catalog:
                print()
                print(
                    "Ingen seniorserie hittades."
                )

                print(
                    "events.json ändras inte."
                )

                return

            # =================================================
            # 2. IMPORT
            # =================================================

            print()
            print(
                "============================================="
            )
            print(
                " IMPORTERAR HELA SPELPROGRAM"
            )
            print(
                "============================================="
            )

            for index, item in enumerate(
                competition_catalog,
                start=1,
            ):
                district = (
                    item[
                        "district"
                    ]
                )

                competition = {
                    key: value
                    for key, value
                    in item.items()
                    if key != "district"
                }

                print()
                print(
                    f"[{index}/"
                    f"{len(competition_catalog)}] "
                    f"{district} | "
                    f"{competition['Name']}"
                )

                try:
                    events = (
                        import_competition(
                            browser,
                            district,
                            competition,
                        )
                    )

                except Exception as error:
                    print(
                        f"  FEL: "
                        f"{error}"
                    )
                    continue

                events = dedupe(
                    events
                )

                print(
                    f"  Matcher: "
                    f"{len(events)}"
                )

                if events:
                    first = events[0]

                    print(
                        f"  Exempel: "
                        f"{first['datum']} "
                        f"{first['tid']} | "
                        f"{first['hemmalag']} - "
                        f"{first['bortalag']} | "
                        f"{first['arena']}"
                    )

                all_imported.extend(
                    events
                )

                time.sleep(
                    0.08
                )

        finally:
            browser.close()

    all_imported = dedupe(
        all_imported
    )

    report(
        all_imported,
        competition_catalog,
    )

    # =========================================================
    # SÄKERHET
    # =========================================================

    if len(
        competition_catalog
    ) < 10:
        print()
        print(
            "SÄKERHETSSTOPP:"
        )

        print(
            "För få seniorserier upptäcktes."
        )

        print(
            "events.json ändras inte."
        )

        return

    if len(
        all_imported
    ) < 100:
        print()
        print(
            "SÄKERHETSSTOPP:"
        )

        print(
            "Färre än 100 matcher importerades."
        )

        print(
            "events.json ändras inte."
        )

        return

    # =========================================================
    # MERGE
    # =========================================================

    backup_events()

    (
        combined,
        added,
        duplicate_matches,
    ) = merge_events(
        existing,
        all_imported,
    )

    combined = sort_events(
        combined
    )

    save_events(
        combined
    )

    print()
    print(
        "============================================="
    )
    print(
        " DATABAS UPPDATERAD"
    )
    print(
        "============================================="
    )

    print()
    print(
        f"Importerade distriktsmatcher: "
        f"{len(all_imported)}"
    )

    print(
        f"Nya event tillagda: "
        f"{added}"
    )

    print(
        f"Redan befintliga matcher: "
        f"{duplicate_matches}"
    )

    print(
        f"events.json totalt: "
        f"{len(combined)}"
    )

    print()
    print(
        f"Backup:"
    )

    print(
        BACKUP_FILE
    )

    print()
    print(
        f"Seriekatalog:"
    )

    print(
        COMPETITION_DEBUG_FILE
    )

    print()
    print(
        f"Debug:"
    )

    print(
        DEBUG_DIR
    )


if __name__ == "__main__":
    main()
