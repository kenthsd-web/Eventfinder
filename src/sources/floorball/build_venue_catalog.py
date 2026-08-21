import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright


SEASON_ID = 44

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"

COMPETITIONS_FILE = DATA_DIR / "floorball_senior_competitions.json"
EVENT_FILE = DATA_DIR / "events.json"

VENUE_CATALOG_FILE = DATA_DIR / "floorball_venue_catalog.json"
BACKUP_FILE = DATA_DIR / "events_before_venue_catalog_update.json"

STATS_BASE = "https://stats.innebandy.se"
API_BASE = "https://api.innebandy.se/v2/api"


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


def collect_venue_links(browser, competition_id):
    url = (
        f"{STATS_BASE}/"
        f"sasong/{SEASON_ID}/"
        f"serie/{competition_id}/"
        f"spelprogram/full"
    )

    page = browser.new_page()

    try:
        page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000,
        )

        page.wait_for_timeout(1200)

        links = page.locator(
            'a[href*="/anlaggning/"]'
        )

        result = {}

        for i in range(
            links.count()
        ):
            link = links.nth(i)

            text = (
                link.inner_text()
                .strip()
            )

            href = (
                link.get_attribute("href")
                or ""
            )

            match = re.search(
                r"/anlaggning/(\d+)",
                href,
            )

            if not match:
                continue

            venue_id = int(
                match.group(1)
            )

            if not text:
                continue

            result[text] = venue_id

        return result

    finally:
        page.close()


def fetch_venue_data(browser, venue_id):
    page = browser.new_page()

    api_url = (
        f"{API_BASE}/venues/{venue_id}"
    )

    captured = []

    def handle_response(response):
        if response.url != api_url:
            return

        try:
            data = response.json()

            if isinstance(data, dict):
                captured.append(data)

        except Exception:
            pass

    page.on(
        "response",
        handle_response,
    )

    try:
        page.goto(
            f"{STATS_BASE}/sasong/{SEASON_ID}/anlaggning/{venue_id}",
            wait_until="domcontentloaded",
            timeout=60000,
        )

        for _ in range(30):
            if captured:
                break

            page.wait_for_timeout(
                250
            )

        if not captured:
            return {}

        return captured[-1]

    finally:
        page.close()


def main():
    print()
    print(
        "============================================="
    )
    print(
        " EVENTFINDER - BYGGER VENUE-KATALOG"
    )
    print(
        "============================================="
    )
    print()

    competitions = load_json(
        COMPETITIONS_FILE,
        [],
    )

    events = load_json(
        EVENT_FILE,
        [],
    )

    if not competitions:
        raise RuntimeError(
            "Saknar floorball_senior_competitions.json"
        )

    arena_to_venue_id = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True
        )

        try:
            print(
                "Samlar arena-ID från spelprogram..."
            )

            for index, item in enumerate(
                competitions,
                start=1,
            ):
                competition_id = (
                    item.get(
                        "CompetitionID"
                    )
                )

                name = item.get(
                    "Name",
                    "",
                )

                print(
                    f"[{index}/{len(competitions)}] "
                    f"{competition_id} | {name}"
                )

                if not competition_id:
                    continue

                try:
                    links = collect_venue_links(
                        browser,
                        competition_id,
                    )

                except Exception as error:
                    print(
                        f"  FEL: {error}"
                    )
                    continue

                for arena, venue_id in links.items():
                    arena_to_venue_id[
                        arena
                    ] = venue_id

            print()
            print(
                f"Unika arenor med VenueID: "
                f"{len(arena_to_venue_id)}"
            )

            catalog = {}

            event_venue_ids = {
                int(event.get("venue_id"))
                for event in events
                if event.get("venue_id")
            }

            venue_ids = sorted(
                set(
                    arena_to_venue_id.values()
                )
                | event_venue_ids
            )

            print()
            print(
                "Hämtar venue-data..."
            )

            for index, venue_id in enumerate(
                venue_ids,
                start=1,
            ):
                print(
                    f"[{index}/{len(venue_ids)}] "
                    f"VenueID {venue_id}"
                )

                try:
                    data = fetch_venue_data(
                        browser,
                        venue_id,
                    )

                except Exception as error:
                    print(
                        f"  FEL: {error}"
                    )
                    continue

                if not data:
                    continue

                catalog[
                    str(venue_id)
                ] = data

        finally:
            browser.close()

    result = {
        "arena_to_venue_id":
            arena_to_venue_id,

        "venues":
            catalog,
    }

    save_json(
        VENUE_CATALOG_FILE,
        result,
    )

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    updated_coords = 0
    updated_city = 0
    updated_address = 0
    updated_venue_id = 0

    for event in events:
        source_type = event.get(
            "source_type"
        )

        if source_type not in (
            "district_competition_full_schedule",
            "officiellt_spelschema_pdf",
        ):
            continue

        arena = event.get(
            "arena"
        )

        venue_id = event.get(
            "venue_id"
        )

        if not venue_id and arena:
            venue_id = (
                arena_to_venue_id.get(
                    arena
                )
            )

            if venue_id:
                event[
                    "venue_id"
                ] = venue_id

                updated_venue_id += 1

        if not venue_id:
            continue

        venue = catalog.get(
            str(venue_id),
            {},
        )

        if not venue:
            continue

        city = (
            venue.get(
                "City"
            )
            or ""
        ).strip()

        address = (
            venue.get(
                "Address"
            )
            or ""
        ).strip()

        postcode = (
            venue.get(
                "Postcode"
            )
            or ""
        ).strip()

        lat = venue.get(
            "WGS84Latitude"
        )

        lon = venue.get(
            "WGS84Longitude"
        )

        if (
            city
            and not event.get(
                "ort"
            )
        ):
            event[
                "ort"
            ] = city

            updated_city += 1

        if address:
            full_address = " ".join(
                part
                for part in [
                    address,
                    postcode,
                    city,
                ]
                if part
            )

            event[
                "arena_adress"
            ] = full_address

            updated_address += 1

        if (
            isinstance(lat, (int, float))
            and isinstance(lon, (int, float))
            and lat != 0
            and lon != 0
            and event.get(
                "lat"
            ) is None
        ):
            event[
                "lat"
            ] = float(lat)

            event[
                "lon"
            ] = float(lon)

            event[
                "geocode_source"
            ] = "Svensk Innebandy venue API"

            event[
                "location_precision"
            ] = "arena"

            updated_coords += 1

    save_json(
        EVENT_FILE,
        events,
    )

    total_district = sum(
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

    venues_with_coords = sum(
        1
        for venue in catalog.values()
        if (
            venue.get(
                "WGS84Latitude"
            )
            not in (
                None,
                0,
            )
            and venue.get(
                "WGS84Longitude"
            )
            not in (
                None,
                0,
            )
        )
    )

    venues_with_address = sum(
        1
        for venue in catalog.values()
        if (
            venue.get(
                "Address"
            )
            or venue.get(
                "City"
            )
        )
    )

    print()
    print(
        "============================================="
    )
    print(
        " VENUE-KATALOG KLAR"
    )
    print(
        "============================================="
    )
    print()

    print(
        f"Arenor med VenueID: "
        f"{len(arena_to_venue_id)}"
    )

    print(
        f"Venue-poster hämtade: "
        f"{len(catalog)}"
    )

    print(
        f"Venue-poster med adress/ort: "
        f"{venues_with_address}"
    )

    print(
        f"Venue-poster med koordinater: "
        f"{venues_with_coords}"
    )

    print()
    print(
        f"Event med VenueID uppdaterade: "
        f"{updated_venue_id}"
    )

    print(
        f"Event med ny ort: "
        f"{updated_city}"
    )

    print(
        f"Event med ny adress: "
        f"{updated_address}"
    )

    print(
        f"Event med nya koordinater: "
        f"{updated_coords}"
    )

    print()
    print(
        f"Distriktsmatcher totalt: "
        f"{total_district}"
    )

    print(
        f"Distriktsmatcher med koordinater: "
        f"{with_coords}"
    )

    if total_district:
        print(
            f"Täckning: "
            f"{100 * with_coords / total_district:.1f}%"
        )

    print()
    print(
        f"Katalog: "
        f"{VENUE_CATALOG_FILE}"
    )

    print(
        f"Backup: "
        f"{BACKUP_FILE}"
    )


if __name__ == "__main__":
    main()
