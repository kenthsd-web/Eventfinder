import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parents[3]
EVENT_FILE = BASE_DIR / "data" / "events.json"
TEAM_FILE = BASE_DIR / "data" / "floorball_national_teams.json"
BACKUP_FILE = (
    BASE_DIR
    / "data"
    / "events_before_national_api_enrich.json"
)

SEASON_ID = 44

SERIES = {
    "SSL Dam": 44030,
    "SSL Herr": 44033,
    "Allsvenskan Dam Norra": 44031,
    "Allsvenskan Dam Södra": 44032,
    "Allsvenskan Herr": 44034,
    "Division 1 Herr Mellersta": 44037,
    "Division 1 Herr Norra": 44041,
    "Division 1 Herr Södra Götaland": 44039,
    "Division 1 Herr Södra Svealand": 44036,
    "Division 1 Herr Västra Götaland": 44038,
    "Division 1 Herr Östra": 44035,
}


def load_json(path):
    return json.loads(
        path.read_text(encoding="utf-8")
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


def collect_team_ids(page, competition_id):
    target = (
        "https://api.innebandy.se/v2/api/"
        f"competitions/{competition_id}/standings"
    )

    captured = []

    def handle_response(response):
        if response.url == target:
            try:
                captured.append(response.json())
            except Exception:
                pass

    page.on("response", handle_response)

    page.goto(
        "https://stats.innebandy.se/"
        f"sasong/{SEASON_ID}/serie/"
        f"{competition_id}/serietabell",
        wait_until="networkidle",
        timeout=60000,
    )

    page.wait_for_timeout(800)

    if not captured:
        return []

    rows = (
        captured[-1].get("StandingsRows")
        or []
    )

    return sorted({
        row.get("TeamID")
        for row in rows
        if row.get("TeamID")
    })


def collect_team_matches(page, team_id, competition_id):
    target = (
        "https://api.innebandy.se/v2/api/"
        f"seasons/{SEASON_ID}/teams/{team_id}"
    )

    captured = []

    def handle_response(response):
        if response.url == target:
            try:
                captured.append(response.json())
            except Exception:
                pass

    page.on("response", handle_response)

    page.goto(
        "https://stats.innebandy.se/"
        f"sasong/{SEASON_ID}/lag/{team_id}/trupp",
        wait_until="networkidle",
        timeout=60000,
    )

    page.wait_for_timeout(500)

    if not captured:
        return []

    data = captured[-1]

    for comp in data.get("Competitions") or []:
        if comp.get("CompetitionID") == competition_id:
            return comp.get("Matches") or []

    return []


def main():
    print()
    print("=============================================")
    print(" EVENTFINDER - NATIONELL API-BERIKNING")
    print("=============================================")
    print()

    events = load_json(EVENT_FILE)

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    all_matches = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for serie, competition_id in SERIES.items():
            print()
            print(serie)

            team_ids = collect_team_ids(
                page,
                competition_id,
            )

            print("  Lag-ID:", len(team_ids))

            series_matches = {}

            for index, team_id in enumerate(
                team_ids,
                start=1,
            ):
                matches = collect_team_matches(
                    page,
                    team_id,
                    competition_id,
                )

                for match in matches:
                    match_no = str(
                        match.get("MatchNo") or ""
                    ).strip()

                    if match_no:
                        series_matches[match_no] = match

                print(
                    f"  [{index}/{len(team_ids)}] "
                    f"lag {team_id} -> "
                    f"{len(matches)} matcher"
                )

            print(
                "  Unika matcher:",
                len(series_matches),
            )

            all_matches.update(
                series_matches
            )

        browser.close()

    updated = 0
    arena_updated = 0
    time_updated = 0
    venue_id_updated = 0

    for event in events:
        if (
            event.get("sport") != "Innebandy"
            or event.get("source_type")
            != "officiellt_spelschema_pdf"
        ):
            continue

        match_no = str(
            event.get("match_id") or ""
        ).strip()

        match = all_matches.get(match_no)

        if not match:
            continue

        changed = False

        dt = match.get("MatchDateTime") or ""

        if "T" in dt:
            date_part, time_part = dt.split(
                "T",
                1,
            )

            time_part = time_part[:5]

            valid_date = (
                date_part
                and date_part != "0001-01-01"
            )

            if valid_date:
                event["datum"] = date_part
                event["datum_start"] = date_part
                event["datum_slut"] = date_part
                event["datum_exakt"] = True
                event["status"] = "schemalagd"
                changed = True

                if (
                    time_part
                    and time_part != "00:00"
                    and event.get("tid") != time_part
                ):
                    event["tid"] = time_part
                    time_updated += 1
                    changed = True

        venue = (
            match.get("Venue")
            or ""
        ).strip()

        venue_id = match.get("VenueID")

        if venue and event.get("arena") != venue:
            event["arena"] = venue
            event["plats"] = venue
            arena_updated += 1
            changed = True

        if venue_id and event.get("venue_id") != venue_id:
            event["venue_id"] = venue_id
            venue_id_updated += 1
            changed = True

        if changed:
            event["api_enriched"] = True
            event["api_competition_id"] = (
                match.get("CompetitionID")
            )
            updated += 1

    save_json(EVENT_FILE, events)

    print()
    print("=============================================")
    print(" NATIONELL API-BERIKNING KLAR")
    print("=============================================")
    print()
    print("API-matcher insamlade:", len(all_matches))
    print("Event uppdaterade:", updated)
    print("Tid uppdaterad:", time_updated)
    print("Arena uppdaterad:", arena_updated)
    print("VenueID uppdaterad:", venue_id_updated)
    print()
    print("Backup:", BACKUP_FILE)
    print("Fil:", EVENT_FILE)


if __name__ == "__main__":
    main()
