import json
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright


# ============================================================
# EVENTFINDER - SSL-BERIKNING 2026/27
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
BACKUP_FILE = DATA_DIR / "events_before_enrich.json"
DEBUG_TEXT_FILE = DATA_DIR / "ssl_rendered_text.txt"

SSL_URL = "https://www.ssl.se/game-schedule"

SEASON_START_YEAR = 2026
SEASON_END_YEAR = 2027


# ============================================================
# LAGNAMN
# ============================================================

TEAM_ALIASES = {
    # SSL Herr
    "AIK": "AIK IBF",
    "AIK IBF": "AIK IBF",

    "FBC": "FBC Kalmarsund",
    "KAL": "FBC Kalmarsund",
    "KALMARSUND": "FBC Kalmarsund",
    "FBC KALMARSUND": "FBC Kalmarsund",

    "FAL": "IBF Falun",
    "FALUN": "IBF Falun",
    "IBF FALUN": "IBF Falun",

    "DAL": "IBK Dalen",
    "IBKD": "IBK Dalen",
    "DALEN": "IBK Dalen",
    "IBK DALEN": "IBK Dalen",

    "LUND": "IBK Lund Elit",
    "IBK LUND": "IBK Lund Elit",
    "IBK LUND ELIT": "IBK Lund Elit",

    "JIK": "Jönköpings IK",
    "JÖNKÖPING": "Jönköpings IK",
    "JÖNKÖPINGS IK": "Jönköpings IK",

    "LIBK": "Linköping IBK",
    "LIN": "Linköping IBK",
    "LINKÖPING": "Linköping IBK",
    "LINKÖPING IBK": "Linköping IBK",

    "MAIS": "Mullsjö AIS",
    "MULLSJÖ": "Mullsjö AIS",
    "MULLSJÖ AIS": "Mullsjö AIS",

    "NYK": "Nykvarns IBF",
    "NYKVARN": "Nykvarns IBF",
    "NYKVARNS IBF": "Nykvarns IBF",

    "PIX": "Pixbo IBK",
    "PIXBO": "Pixbo IBK",
    "PIXBO IBK": "Pixbo IBK",

    "STO": "Storvreta IBK",
    "SIBK": "Storvreta IBK",
    "STORVRETA": "Storvreta IBK",
    "STORVRETA IBK": "Storvreta IBK",

    "VIS": "Visby IBK",
    "VISBY": "Visby IBK",
    "VISBY IBK": "Visby IBK",

    "VXO": "Växjö IBK",
    "VÄX": "Växjö IBK",
    "VÄXJÖ": "Växjö IBK",
    "VÄXJÖ IBK": "Växjö IBK",
    "VÄXJÖ VIPERS": "Växjö IBK",

    "WIC": "Warberg IC",
    "WARBERG": "Warberg IC",
    "WARBERG IC": "Warberg IC",

    # SSL Dam
    "END": "Endre IF",
    "ENDRE": "Endre IF",
    "ENDRE IF": "Endre IF",

    "LOCK": "IBK Lockerud Mariestad",
    "LOCKERUD": "IBK Lockerud Mariestad",
    "IBK LOCKERUD MARIESTAD": "IBK Lockerud Mariestad",

    "MORA": "KAIS Mora IF",
    "KAIS MORA": "KAIS Mora IF",
    "KAIS MORA IF": "KAIS Mora IF",

    "KAR": "Karlstad IBF",
    "KIBF": "Karlstad IBF",
    "KARLSTAD": "Karlstad IBF",
    "KARLSTAD IBF": "Karlstad IBF",

    "MAL": "Malmö FBC",
    "MALMÖ": "Malmö FBC",
    "MALMÖ FBC": "Malmö FBC",

    "TTG": "Thorengruppen IBK",
    "THORENGRUPPEN": "Thorengruppen IBK",
    "THORENGRUPPEN IBK": "Thorengruppen IBK",

    "TFC": "Täby FC IBK",
    "TÄBY": "Täby FC IBK",
    "TÄBY FC": "Täby FC IBK",
    "TÄBY FC IBK": "Täby FC IBK",

    "RÖN": "Västerås Rönnby IBK",
    "RÖNNBY": "Västerås Rönnby IBK",
    "VÄSTERÅS RÖNNBY": "Västerås Rönnby IBK",
    "VÄSTERÅS RÖNNBY IBK": "Västerås Rönnby IBK",
}


MONTHS = {
    "JAN": 1,
    "FEB": 2,
    "MAR": 3,
    "APR": 4,
    "MAJ": 5,
    "JUN": 6,
    "JUL": 7,
    "AUG": 8,
    "SEP": 9,
    "OKT": 10,
    "NOV": 11,
    "DEC": 12,
}


# ============================================================
# HJÄLPFUNKTIONER
# ============================================================

def norm(text):
    text = text.strip().upper()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_team(text):
    value = norm(text)

    return TEAM_ALIASES.get(
        value,
        text.strip(),
    )


def is_known_team(text):
    return norm(text) in TEAM_ALIASES


def normalize_time(text):
    match = re.search(
        r"\b(\d{1,2})[:.]([0-5]\d)\s*(AM|PM)?\b",
        text,
        re.IGNORECASE,
    )

    if not match:
        return ""

    hour = int(match.group(1))
    minute = int(match.group(2))
    ampm = match.group(3)

    if ampm:
        ampm = ampm.upper()

        if ampm == "PM" and hour != 12:
            hour += 12

        if ampm == "AM" and hour == 12:
            hour = 0

    if hour > 23:
        return ""

    return f"{hour:02d}:{minute:02d}"


# ============================================================
# LADDA EVENTS
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
            "events.json är inte en lista."
        )

    return data


def backup_events():
    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )


def save_events(events):
    EVENT_FILE.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# RENDERA SSL MED PLAYWRIGHT
# ============================================================

def fetch_rendered_text():
    print(
        "Startar webbläsare och renderar SSL:s spelschema..."
    )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            viewport={
                "width": 1440,
                "height": 1600,
            }
        )

        page.goto(
            SSL_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        # Vänta på att JavaScript-data ska hinna laddas.
        page.wait_for_timeout(5000)

        # Scrolla för att trigga lazy loading.
        previous_height = 0

        for _ in range(20):
            height = page.evaluate(
                "document.body.scrollHeight"
            )

            if height == previous_height:
                break

            previous_height = height

            page.evaluate(
                "window.scrollTo(0, document.body.scrollHeight)"
            )

            page.wait_for_timeout(750)

        body_text = page.locator(
            "body"
        ).inner_text()

        browser.close()

    DEBUG_TEXT_FILE.write_text(
        body_text,
        encoding="utf-8",
    )

    return body_text


# ============================================================
# DATUMTOLKNING
# ============================================================

def parse_date_from_context(lines, index):
    day = None
    month = None

    start = max(
        0,
        index - 8,
    )

    end = min(
        len(lines),
        index + 3,
    )

    for pos in range(start, end):
        value = (
            lines[pos]
            .replace(".", "")
            .strip()
        )

        if re.fullmatch(
            r"\d{1,2}",
            value,
        ):
            number = int(value)

            if 1 <= number <= 31:
                day = number

        month_key = value[:3].upper()

        if month_key in MONTHS:
            month = MONTHS[
                month_key
            ]

    if (
        day is None
        or month is None
    ):
        return None

    year = (
        SEASON_START_YEAR
        if month >= 8
        else SEASON_END_YEAR
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
# PARSA RENDERAD TEXT
# ============================================================

def parse_matches(rendered_text):
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in rendered_text.splitlines()
        if line.strip()
    ]

    month_map = {
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

    date_pattern = re.compile(
        r"^(?:MÅNDAG|TISDAG|ONSDAG|TORSDAG|FREDAG|"
        r"LÖRDAG|SÖNDAG)\s+"
        r"(\d{1,2})\s+"
        r"([A-ZÅÄÖ]+)$",
        re.IGNORECASE,
    )

    match_pattern = re.compile(
        r"^(.+?)\s+[–—-]\s+(.+?)$"
    )

    matches = []
    current_date = None
    current_series = "SSL Herr"

    i = 0

    while i < len(lines):
        line = lines[i]

        # Serie
        if norm(line) == "SSL HERR":
            current_series = "SSL Herr"
            i += 1
            continue

        if norm(line) == "SSL DAM":
            current_series = "SSL Dam"
            i += 1
            continue

        # Datumrubrik, t.ex. LÖRDAG 19 SEPTEMBER
        date_match = date_pattern.match(
            line.upper()
        )

        if date_match:
            day = int(
                date_match.group(1)
            )

            month_name = (
                date_match.group(2)
                .upper()
            )

            month = month_map.get(
                month_name
            )

            if month:
                year = (
                    2026
                    if month >= 8
                    else 2027
                )

                try:
                    current_date = datetime(
                        year,
                        month,
                        day,
                    ).strftime(
                        "%Y-%m-%d"
                    )

                except ValueError:
                    current_date = None

            i += 1
            continue

        # Matchrubrik:
        # "IBF Falun – Växjö Vipers"
        title_match = match_pattern.match(
            line
        )

        if (
            not title_match
            or not current_date
        ):
            i += 1
            continue

        home_raw = (
            title_match.group(1)
            .strip()
        )

        away_raw = (
            title_match.group(2)
            .strip()
        )

        home = normalize_team(
            home_raw
        )

        away = normalize_team(
            away_raw
        )

        # Bara fortsätt om båda ser ut som
        # lag vi känner igen.
        if (
            norm(home_raw)
            not in TEAM_ALIASES
            or norm(away_raw)
            not in TEAM_ALIASES
        ):
            i += 1
            continue

        match_time = ""
        arena = ""

        # Strukturen efter matchrubriken är normalt:
        #
        # hemmalag
        # Starttid:
        # 4:00 PM
        # bortalag
        # arena
        # Inför match

        for j in range(
            i + 1,
            min(
                i + 10,
                len(lines),
            ),
        ):
            candidate = lines[j]

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

            # När vi hittar bortalaget är nästa
            # användbara rad normalt arenan.
            if (
                normalize_team(candidate)
                == away
            ):
                for arena_pos in range(
                    j + 1,
                    min(
                        j + 5,
                        len(lines),
                    ),
                ):
                    arena_candidate = (
                        lines[arena_pos]
                        .strip()
                    )

                    if not arena_candidate:
                        continue

                    if arena_candidate in (
                        "Inför match",
                        "Köp biljett",
                        "Matchcenter",
                        "Starttid:",
                    ):
                        continue

                    # Undvik ny datumrubrik.
                    if date_pattern.match(
                        arena_candidate.upper()
                    ):
                        break

                    arena = (
                        arena_candidate
                    )
                    break

                break

        matches.append(
            {
                "serie": current_series,
                "datum": current_date,
                "tid": match_time,
                "hemmalag": home,
                "bortalag": away,
                "arena": arena,
                "source": SSL_URL,
            }
        )

        i += 1

    # Dubblettkontroll
    unique = {}

    for match in matches:
        key = (
            match["datum"],
            match["hemmalag"],
            match["bortalag"],
        )

        unique[key] = match

    return list(
        unique.values()
    )

# ============================================================
# MATCHA MOT GRUNDSCHEMAT
# ============================================================

def find_event(events, match):
    candidates = []

    for event in events:
        if event.get(
            "sport"
        ) != "Innebandy":
            continue

        if event.get(
            "serie"
        ) not in (
            "SSL Herr",
            "SSL Dam",
        ):
            continue

        if event.get(
            "hemmalag"
        ) != match["hemmalag"]:
            continue

        if event.get(
            "bortalag"
        ) != match["bortalag"]:
            continue

        candidates.append(
            event
        )

    if not candidates:
        return None

    target_date = datetime.strptime(
        match["datum"],
        "%Y-%m-%d",
    ).date()

    best_event = None
    best_distance = None

    for event in candidates:
        start_text = event.get(
            "datum_start"
        )

        end_text = (
            event.get("datum_slut")
            or start_text
        )

        if not start_text:
            continue

        try:
            start_date = datetime.strptime(
                start_text,
                "%Y-%m-%d",
            ).date()

            end_date = datetime.strptime(
                end_text,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            continue

        if (
            start_date
            <= target_date
            <= end_date
        ):
            return event

        distance = min(
            abs(
                (
                    target_date
                    - start_date
                ).days
            ),
            abs(
                (
                    target_date
                    - end_date
                ).days
            ),
        )

        if (
            best_distance is None
            or distance < best_distance
        ):
            best_distance = distance
            best_event = event

    if (
        best_event is not None
        and best_distance is not None
        and best_distance <= 7
    ):
        return best_event

    return None

# ============================================================
# BERIKA EVENTS
# ============================================================

def enrich(events, matches):
    updated = 0
    exact_dates = 0
    times = 0
    arenas = 0
    unmatched = []

    for match in matches:
        event = find_event(
            events,
            match,
        )

        if not event:
            unmatched.append(
                match
            )
            continue

        changed = False

        # Exakt datum
        if (
            event.get("datum")
            != match["datum"]
            or not event.get("datum_exakt")
        ):
            event["datum"] = (
                match["datum"]
            )

            event["datum_start"] = (
                match["datum"]
            )

            event["datum_slut"] = (
                match["datum"]
            )

            event["datum_exakt"] = True
            event["status"] = "schemalagd"

            exact_dates += 1
            changed = True

        # Exakt starttid
        if (
            match.get("tid")
            and event.get("tid")
            != match["tid"]
        ):
            event["tid"] = (
                match["tid"]
            )

            times += 1
            changed = True

        # Arena
        if (
            match.get("arena")
            and event.get("arena")
            != match["arena"]
        ):
            event["arena"] = (
                match["arena"]
            )

            event["plats"] = (
                match["arena"]
            )

            event[
                "location_precision"
            ] = "arena"

            arenas += 1
            changed = True

        # Källa och tidsstämpel
        if changed:
            event[
                "ssl_schedule_url"
            ] = SSL_URL

            event[
                "senast_berikad"
            ] = (
                datetime.now()
                .isoformat(
                    timespec="seconds"
                )
            )

            updated += 1

    return {
        "updated": updated,
        "exact_dates": exact_dates,
        "times": times,
        "arenas": arenas,
        "unmatched": unmatched,
    }


# ============================================================
# RAPPORT
# ============================================================

def quality_report(events):
    ssl_events = [
        event
        for event in events
        if event.get(
            "serie"
        ) in (
            "SSL Herr",
            "SSL Dam",
        )
    ]

    exact_dates = sum(
        1
        for event in ssl_events
        if event.get(
            "datum_exakt"
        )
    )

    with_time = sum(
        1
        for event in ssl_events
        if event.get("tid")
    )

    with_arena = sum(
        1
        for event in ssl_events
        if event.get("arena")
    )

    with_kommun = sum(
        1
        for event in ssl_events
        if event.get("kommun")
    )

    print()
    print("SSL datakvalitet")
    print("----------------")

    print(
        f"SSL-matcher totalt: "
        f"{len(ssl_events)}"
    )

    print(
        f"Exakt datum: "
        f"{exact_dates}"
    )

    print(
        f"Exakt tid: "
        f"{with_time}"
    )

    print(
        f"Arena: "
        f"{with_arena}"
    )

    print(
        f"Kommun: "
        f"{with_kommun}"
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
        " EVENTFINDER - SSL BERIKNING 2026/27"
    )
    print(
        "============================================="
    )

    events = load_events()

    print()
    print(
        f"Laddade {len(events)} event."
    )

    rendered_text = fetch_rendered_text()

    print(
        f"Renderad sidtext: "
        f"{len(rendered_text):,} tecken."
    )

    matches = parse_matches(
        rendered_text
    )

    print(
        f"Tolkade {len(matches)} "
        f"SSL-matcher."
    )

    if not matches:
        print()
        print(
            "Ingen match hittades."
        )
        print(
            "events.json ändras inte."
        )
        print()
        print(
            f"Debug-text sparad i:"
        )
        print(
            DEBUG_TEXT_FILE
        )
        return

    backup_events()

    result = enrich(
        events,
        matches,
    )

    save_events(
        events
    )

    print()
    print("Berikning")
    print("---------")

    print(
        f"Uppdaterade event: "
        f"{result['updated']}"
    )

    print(
        f"Nya exakta datum: "
        f"{result['exact_dates']}"
    )

    print(
        f"Nya/ändrade tider: "
        f"{result['times']}"
    )

    print(
        f"Ej matchade: "
        f"{len(result['unmatched'])}"
    )

    quality_report(
        events
    )

    if result["unmatched"]:
        print()
        print(
            "Ej matchade exempel"
        )
        print(
            "------------------"
        )

        for match in (
            result["unmatched"][:10]
        ):
            print(
                f"{match['datum']} "
                f"{match['tid'] or '--:--'} | "
                f"{match['hemmalag']} - "
                f"{match['bortalag']}"
            )

    print()
    print(
        f"Backup: {BACKUP_FILE}"
    )

    print(
        f"Debug-text: "
        f"{DEBUG_TEXT_FILE}"
    )

    print(
        f"Uppdaterad fil: "
        f"{EVENT_FILE}"
    )


if __name__ == "__main__":
    main()
