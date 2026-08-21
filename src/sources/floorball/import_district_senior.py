import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# EVENTFINDER - IMPORT ALL DISTRICT SENIOR FLOORBALL
# ============================================================

SEASON = "2026/27"
SPORT = "Innebandy"

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
DEBUG_DIR = DATA_DIR / "district_floorball_debug"

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
    / "events_before_district_import.json"
)


# ============================================================
# SENIORFILTER
# ============================================================

SENIOR_INCLUDE_WORDS = [
    "herr",
    "herrar",
    "dam",
    "damer",
    "division",
    "div ",
    "div.",
    "senior",
]

SENIOR_EXCLUDE_WORDS = [
    "junior",
    "juniorallsvenskan",
    "jas",
    "u19",
    "u17",
    "u16",
    "u15",
    "u14",
    "u13",
    "u12",
    "u11",
    "u10",
    "pojkar",
    "flickor",
    "p16",
    "p15",
    "p14",
    "p13",
    "p12",
    "f16",
    "f15",
    "f14",
    "f13",
    "f12",
    "grön",
    "gron",
    "blå",
    "bla",
    "röd",
    "rod",
    "ungdom",
]


# ============================================================
# DATUM
# ============================================================

MONTHS = {
    "JANUARI": 1,
    "FEBRUARI": 2,
    "MARS": 3,
    "APRIL": 4,
    "MAJ": 5,
    "JUNI": 6,
    "JULI": 7,
    "AUGUSTI": 8,
    "SEPTEMBER": 9,
    "OKTOBER": 10,
    "NOVEMBER": 11,
    "DECEMBER": 12,
}


DATE_PATTERN = re.compile(
    r"^(?:MÅNDAG|TISDAG|ONSDAG|TORSDAG|FREDAG|"
    r"LÖRDAG|SÖNDAG)\s+"
    r"(\d{1,2})\s+"
    r"([A-ZÅÄÖ]+)$",
    re.IGNORECASE,
)


TIME_PATTERN = re.compile(
    r"\b(\d{1,2})[:.]([0-5]\d)\s*(AM|PM)?\b",
    re.IGNORECASE,
)


MATCH_PATTERN = re.compile(
    r"^(.+?)\s+[–—-]\s+(.+?)$"
)


# ============================================================
# NORMALISERING
# ============================================================

def norm(text):
    text = (
        text
        .strip()
        .lower()
    )

    text = (
        text
        .replace("å", "a")
        .replace("ä", "a")
        .replace("ö", "o")
        .replace("–", "-")
        .replace("—", "-")
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    )


def normalize_time(text):
    match = TIME_PATTERN.search(
        text
    )

    if not match:
        return ""

    hour = int(
        match.group(1)
    )

    minute = int(
        match.group(2)
    )

    ampm = match.group(3)

    if ampm:
        ampm = ampm.upper()

        if (
            ampm == "PM"
            and hour != 12
        ):
            hour += 12

        if (
            ampm == "AM"
            and hour == 12
        ):
            hour = 0

    if hour > 23:
        return ""

    return (
        f"{hour:02d}:"
        f"{minute:02d}"
    )


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
        raise ValueError(
            "Discovery-filen innehåller inga distrikt."
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
    if EVENT_FILE.exists():
        BACKUP_FILE.write_text(
            EVENT_FILE.read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )


# ============================================================
# EVENT-ID
# ============================================================

def create_event_id(
    district,
    series,
    home,
    away,
    date,
    time_value,
):
    identity = "|".join(
        [
            SPORT,
            SEASON,
            district,
            series,
            home,
            away,
            date,
            time_value,
        ]
    )

    return hashlib.sha256(
        identity.encode(
            "utf-8"
        )
    ).hexdigest()[:20]


# ============================================================
# SENIOR?
# ============================================================

def is_senior_series(text):
    value = norm(
        text
    )

    if not value:
        return False

    for word in SENIOR_EXCLUDE_WORDS:
        if word in value:
            return False

    for word in SENIOR_INCLUDE_WORDS:
        if word in value:
            return True

    return False


# ============================================================
# PLAYWRIGHT
# ============================================================

def create_browser():
    playwright = (
        sync_playwright()
        .start()
    )

    browser = (
        playwright
        .chromium
        .launch(
            headless=True
        )
    )

    return (
        playwright,
        browser,
    )


def close_browser(
    playwright,
    browser,
):
    browser.close()
    playwright.stop()


def render_page(
    browser,
    url,
):
    page = browser.new_page(
        viewport={
            "width": 1440,
            "height": 1600,
        }
    )

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(
            4000
        )

        # Försök avvisa cookie-dialog
        # om den finns.
        for label in [
            "GODKÄNN INTE",
            "Avvisa",
            "Neka",
            "Reject",
        ]:
            try:
                button = (
                    page
                    .get_by_text(
                        label,
                        exact=True,
                    )
                )

                if button.count():
                    button.first.click(
                        timeout=1500
                    )

                    page.wait_for_timeout(
                        500
                    )

                    break

            except Exception:
                pass

        # Scroll för lazy loading.
        previous_height = 0

        for _ in range(30):
            height = page.evaluate(
                "document.body.scrollHeight"
            )

            if height == previous_height:
                break

            previous_height = height

            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(
                500
            )

        text = (
            page
            .locator("body")
            .inner_text()
        )

        return text

    finally:
        page.close()


# ============================================================
# DEBUG
# ============================================================

def debug_filename(
    district,
):
    safe = norm(
        district
    )

    safe = re.sub(
        r"[^a-z0-9]+",
        "_",
        safe,
    ).strip("_")

    return (
        DEBUG_DIR
        / f"{safe}.txt"
    )


def save_debug(
    district,
    text,
):
    DEBUG_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    debug_filename(
        district
    ).write_text(
        text,
        encoding="utf-8",
    )


# ============================================================
# TEXT-RADER
# ============================================================

def text_lines(text):
    return [
        re.sub(
            r"\s+",
            " ",
            line,
        ).strip()
        for line in text.splitlines()
        if line.strip()
    ]


# ============================================================
# DATUM
# ============================================================

def parse_date_header(line):
    match = DATE_PATTERN.match(
        line.upper()
    )

    if not match:
        return None

    day = int(
        match.group(1)
    )

    month_name = (
        match.group(2)
        .upper()
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
        return datetime(
            year,
            month,
            day,
        ).strftime(
            "%Y-%m-%d"
        )

    except ValueError:
        return None


# ============================================================
# PARSER
# ============================================================

def parse_district_text(
    text,
    district,
    source_url,
):
    lines = text_lines(
        text
    )

    events = []

    current_date = None
    current_series = ""

    index = 0

    while index < len(lines):
        line = lines[index]

        # ---------------------------------------------
        # Datum
        # ---------------------------------------------

        parsed_date = (
            parse_date_header(
                line
            )
        )

        if parsed_date:
            current_date = (
                parsed_date
            )

            index += 1
            continue

        # ---------------------------------------------
        # Seriesammanhang
        # ---------------------------------------------

        if is_senior_series(
            line
        ):
            # Begränsa orimliga rubriker.
            if len(line) <= 120:
                current_series = (
                    line
                )

        # ---------------------------------------------
        # Matchrubrik
        # ---------------------------------------------

        match = MATCH_PATTERN.match(
            line
        )

        if (
            not match
            or not current_date
        ):
            index += 1
            continue

        home = (
            match
            .group(1)
            .strip()
        )

        away = (
            match
            .group(2)
            .strip()
        )

        # Undvik resultat som "5 - 3".
        if (
            home.isdigit()
            and away.isdigit()
        ):
            index += 1
            continue

        # Kräver rimliga lagnamn.
        if (
            len(home) < 2
            or len(away) < 2
        ):
            index += 1
            continue

        # Om vi inte har en seniorserie
        # i närliggande sammanhang ska
        # matchen inte importeras.
        series = current_series

        if not is_senior_series(
            series
        ):
            index += 1
            continue

        match_time = ""
        arena = ""

        # ---------------------------------------------
        # Titta framåt efter tid + arena
        # ---------------------------------------------

        for pos in range(
            index + 1,
            min(
                index + 12,
                len(lines),
            ),
        ):
            candidate = (
                lines[pos]
            )

            # Ny match eller ny dag:
            # sluta leta.
            if parse_date_header(
                candidate
            ):
                break

            if (
                MATCH_PATTERN.match(
                    candidate
                )
            ):
                break

            if not match_time:
                possible_time = (
                    normalize_time(
                        candidate
                    )
                )

                if possible_time:
                    match_time = (
                        possible_time
                    )

            # Arenaheuristik:
            # raden efter bortalaget/tiden
            # brukar vara hall.
            lower = norm(
                candidate
            )

            if (
                "hall" in lower
                or "arena" in lower
                or "sportcenter" in lower
                or "idrottshus" in lower
                or "sporthall" in lower
            ):
                arena = (
                    candidate
                )

        event_id = create_event_id(
            district=district,
            series=series,
            home=home,
            away=away,
            date=current_date,
            time_value=match_time,
        )

        events.append(
            {
                "id": event_id,

                "sport": SPORT,

                "typ": "match",

                "sasong": SEASON,

                "district":
                    district,

                "serie":
                    series,

                "namn":
                    f"{home} - {away}",

                "hemmalag":
                    home,

                "bortalag":
                    away,

                "datum":
                    current_date,

                "datum_start":
                    current_date,

                "datum_slut":
                    current_date,

                "datum_exakt":
                    True,

                "tid":
                    match_time,

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

                "resultat":
                    "",

                "status":
                    "schemalagd",

                "kalla":
                    "Svensk Innebandy",

                "source_type":
                    "district_public_stats",

                "url":
                    source_url,

                "senast_uppdaterad":
                    datetime.now()
                    .isoformat(
                        timespec="seconds"
                    ),
            }
        )

        index += 1

    return events


# ============================================================
# DEDUPE
# ============================================================

def dedupe(events):
    result = {}

    for event in events:
        key = event["id"]
        result[key] = event

    return list(
        result.values()
    )


# ============================================================
# MERGE
# ============================================================

def merge_events(
    existing,
    imported,
):
    result = {}

    for event in existing:
        event_id = event.get(
            "id"
        )

        if event_id:
            result[event_id] = (
                event
            )

    for new_event in imported:
        event_id = (
            new_event["id"]
        )

        old = result.get(
            event_id
        )

        if old:
            # Bevara geo-data.
            for field in [
                "ort",
                "kommun",
                "lat",
                "lon",
                "geocode_query",
                "geocode_source",
                "geocode_display_name",
                "location_precision",
            ]:
                if (
                    new_event.get(
                        field
                    ) in (
                        None,
                        "",
                    )
                    and old.get(
                        field
                    ) not in (
                        None,
                        "",
                    )
                ):
                    new_event[
                        field
                    ] = old[
                        field
                    ]

        result[event_id] = (
            new_event
        )

    return list(
        result.values()
    )


# ============================================================
# SORTERING
# ============================================================

def sort_key(event):
    date_value = (
        event.get(
            "datum",
            ""
        )
    )

    time_value = (
        event.get(
            "tid"
        )
        or "23:59"
    )

    try:
        return datetime.strptime(
            f"{date_value} "
            f"{time_value}",
            "%Y-%m-%d %H:%M",
        )

    except ValueError:
        return datetime.max


# ============================================================
# IMPORT PER DISTRIKT
# ============================================================

def import_district(
    browser,
    source,
):
    district = (
        source["district"]
    )

    url = (
        source[
            "livematches_url"
        ]
    )

    print()
    print(
        f"=== {district} ==="
    )

    print(
        f"Källa: {url}"
    )

    try:
        text = render_page(
            browser,
            url,
        )

    except Exception as error:
        print(
            f"Renderingsfel: "
            f"{error}"
        )

        return []

    save_debug(
        district,
        text,
    )

    print(
        f"Renderad text: "
        f"{len(text):,} tecken"
    )

    events = (
        parse_district_text(
            text,
            district,
            url,
        )
    )

    events = dedupe(
        events
    )

    print(
        f"Seniorposter hittade: "
        f"{len(events)}"
    )

    return events


# ============================================================
# RAPPORT
# ============================================================

def print_summary(
    imported,
):
    districts = {}
    series = {}

    for event in imported:
        district = (
            event.get(
                "district",
                "Okänt"
            )
        )

        series_name = (
            event.get(
                "serie",
                "Okänd serie"
            )
        )

        districts[
            district
        ] = (
            districts.get(
                district,
                0
            )
            + 1
        )

        series[
            series_name
        ] = (
            series.get(
                series_name,
                0
            )
            + 1
        )

    print()
    print(
        "============================================="
    )

    print(
        " IMPORT-RAPPORT"
    )

    print(
        "============================================="
    )

    print()
    print(
        f"Importerade distriktsmatcher: "
        f"{len(imported)}"
    )

    print(
        f"Distrikt med matcher: "
        f"{len(districts)}"
    )

    print(
        f"Upptäckta seniorserier: "
        f"{len(series)}"
    )

    print()
    print(
        "Matcher per distrikt"
    )

    print(
        "-------------------"
    )

    for district, count in sorted(
        districts.items()
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
        " EVENTFINDER - IMPORT ALL SENIOR FLOORBALL"
    )
    print(
        "============================================="
    )

    print()
    print(
        f"Säsong: {SEASON}"
    )

    sources = load_sources()

    print(
        f"Distriktskällor: "
        f"{len(sources)}"
    )

    existing = load_events()

    print(
        f"Befintliga event: "
        f"{len(existing)}"
    )

    playwright = None
    browser = None

    imported = []

    try:
        (
            playwright,
            browser,
        ) = create_browser()

        for index, source in enumerate(
            sources,
            start=1,
        ):
            print()
            print(
                f"[{index}/"
                f"{len(sources)}]"
            )

            events = import_district(
                browser,
                source,
            )

            imported.extend(
                events
            )

            time.sleep(
                0.5
            )

    finally:
        if (
            playwright is not None
            and browser is not None
        ):
            close_browser(
                playwright,
                browser,
            )

    imported = dedupe(
        imported
    )

    print_summary(
        imported
    )

    # Viktigt:
    # skriv inte över databasen om parsern
    # ännu inte hittat något.
    if not imported:
        print()
        print(
            "Ingen distriktsmatch kunde importeras."
        )

        print(
            "events.json ändras inte."
        )

        print()
        print(
            f"Debug-filer finns i:"
        )

        print(
            DEBUG_DIR
        )

        return

    backup_events()

    combined = merge_events(
        existing,
        imported,
    )

    combined = sorted(
        combined,
        key=sort_key,
    )

    save_events(
        combined
    )

    print()
    print(
        f"events.json innehåller nu: "
        f"{len(combined)} event"
    )

    print(
        f"Backup: "
        f"{BACKUP_FILE}"
    )

    print(
        f"Debug: "
        f"{DEBUG_DIR}"
    )


if __name__ == "__main__":
    main()
