import hashlib
import html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from discover_venues import (
    TableParser,
    BASE,
    UA,
    START_ID,
    END_ID,
    SEASON_MARKERS,
    norm,
)

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"

EVENTS = DATA / "events.json"
CATALOG = DATA / "venue_catalog.json"
PREVIEW = DATA / "swehockey_2026_27_preview.json"
REPORT = DATA / "swehockey_2026_27_import_report.json"
CACHE_DIR = DATA / "swehockey_schedule_cache_2026_27"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SEASON_START = "2026-07-01"
SEASON_END = "2027-06-30"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_venue_lookup(catalog):
    lookup = {}

    for canonical, venue in catalog.items():
        if not isinstance(venue, dict):
            continue

        lookup[norm(canonical)] = canonical

        for alias in venue.get("aliases", []) or []:
            lookup[norm(alias)] = canonical

    return lookup


def split_game(value):
    parts = re.split(r"\s[-–]\s", value.strip(), maxsplit=1)
    if len(parts) != 2:
        return None, None
    return parts[0].strip(), parts[1].strip()


def game_key(date, time, home, away, venue=""):
    return (
        date,
        time[:5],
        norm(home),
        norm(away),
        norm(venue),
    )


def existing_key(event):
    return (
        str(event.get("datum") or ""),
        str(event.get("tid") or "")[:5],
        norm(event.get("hemmalag") or ""),
        norm(event.get("bortalag") or ""),
    )


def event_id(date, time, home, away, canonical):
    raw = "|".join([
        "swehockey",
        "2026-27",
        date,
        time[:5],
        norm(home),
        norm(away),
        norm(canonical),
    ])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def fetch_group(group_id):
    url = BASE.format(group_id)
    cache_file = CACHE_DIR / f"{group_id}.html"

    text = None

    # Använd redan hämtad sida först.
    if cache_file.exists():
        try:
            text = cache_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            text = None

    # Hämta bara från Swehockey om gruppen inte finns i cache.
    if text is None:
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=15) as response:
                    raw = response.read()

                text = raw.decode("utf-8", errors="replace")
                cache_file.write_text(text, encoding="utf-8")
                break

            except Exception:
                if attempt < 3:
                    time.sleep(0.75 * (attempt + 1))

    if text is None:
        return group_id, [], None

    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    if not any(marker in plain for marker in SEASON_MARKERS):
        return group_id, [], None

    parser = TableParser()

    try:
        parser.feed(text)
    except Exception:
        return group_id, [], None

    title = parser.title.split("|", 1)[0].strip()

    # SHL importeras separat från SHL:s officiella API.
    if title.casefold() == "shl":
        return group_id, [], title

    header_index = None
    header = None

    for i, row in enumerate(parser.rows):
        lowered = [str(x).strip().casefold() for x in row]

        if "date" in lowered and "game" in lowered and "venue" in lowered:
            header_index = i
            header = lowered
            break

    if header_index is None:
        return group_id, [], title

    venue_i = header.index("venue")
    round_i = header.index("round") if "round" in header else None
    group_i = header.index("group") if "group" in header else None

    games = []
    current_date = None

    for row in parser.rows[header_index + 1:]:
        cells = [str(x).strip() for x in row]

        if not any(cells):
            continue

        # Hitta matchcellen semantiskt eftersom Swehockey använder
        # flera olika tabellformat.
        game_idx = None
        for i, cell in enumerate(cells):
            if re.search(r"\s[-–]\s", cell):
                game_idx = i
                break

        if game_idx is None:
            continue

        home, away = split_game(cells[game_idx])
        if not home or not away:
            continue

        # Datum kan stå på varje rad eller bara på första matchen
        # för respektive matchdag.
        row_date = None
        for cell in cells[:game_idx]:
            m = re.search(r"(20\d{2}-\d{2}-\d{2})", cell)
            if m:
                row_date = m.group(1)
                break

        if row_date:
            current_date = row_date

        if not current_date:
            continue

        if not (SEASON_START <= current_date <= SEASON_END):
            continue

        # Tid kan ligga separat eller tillsammans med datum.
        row_time = None

        exact_times = []
        for cell in cells[:game_idx]:
            m = re.fullmatch(r"(\d{1,2}:\d{2})", cell)
            if m:
                exact_times.append(m.group(1))

        if exact_times:
            row_time = exact_times[-1]
        else:
            for cell in reversed(cells[:game_idx]):
                m = re.search(r"(?<!\d)(\d{1,2}:\d{2})(?!\d)", cell)
                if m:
                    row_time = m.group(1)
                    break

        if not row_time:
            continue

        # I formatet med Group ligger venue på sin normala kolumn.
        # I formatet utan Group ligger venue sist på raden.
        subgroup = ""

        if group_i is not None:
            if venue_i >= len(cells):
                continue

            venue = cells[venue_i].strip()

            if group_i < len(cells):
                subgroup = cells[group_i].strip()
        else:
            venue = ""
            for cell in reversed(cells[game_idx + 1:]):
                if cell:
                    venue = cell
                    break

        if not venue:
            continue

        result = ""
        for cell in cells[game_idx + 1:]:
            if re.fullmatch(r"\s*\d+\s*[-–]\s*\d+\s*", cell):
                result = cell.strip()
                break

        round_value = ""
        if round_i is not None and round_i < len(cells):
            round_value = cells[round_i].strip()

        games.append({
            "group_id": group_id,
            "source_url": url,
            "series": title,
            "subgroup": subgroup,
            "round": round_value,
            "date": current_date,
            "time": row_time,
            "home": home,
            "away": away,
            "result": result,
            "venue": venue,
        })

    return group_id, games, title

def main():
    events = load_json(EVENTS)
    catalog = load_json(CATALOG)
    venue_lookup = build_venue_lookup(catalog)

    existing_hockey = {
        existing_key(event)
        for event in events
        if event.get("sport") == "Ishockey"
    }

    all_games = []
    groups_with_games = 0

    ids = range(START_ID, END_ID + 1)

    print("SWEHOCKEY 2026/27 – MATCHDISCOVERY")
    print("=" * 48)
    print(f"Skannar grupp-ID {START_ID}–{END_ID} ...")

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {
            pool.submit(fetch_group, group_id): group_id
            for group_id in ids
        }

        completed = 0

        for future in as_completed(futures):
            completed += 1

            try:
                group_id, games, title = future.result()
            except Exception:
                continue

            if games:
                groups_with_games += 1
                all_games.extend(games)

            if completed % 100 == 0:
                print(
                    f"{completed}/{END_ID - START_ID + 1} skannade"
                    f" | grupper med matcher: {groups_with_games}"
                    f" | matchrader: {len(all_games)}",
                    flush=True,
                )

    unique = {}
    duplicate_rows = 0

    for game in all_games:
        key = game_key(
            game["date"],
            game["time"],
            game["home"],
            game["away"],
            game["venue"],
        )

        if key in unique:
            duplicate_rows += 1
            unique[key]["source_group_ids"].append(game["group_id"])
            continue

        game["source_group_ids"] = [game["group_id"]]
        unique[key] = game

    now = datetime.now().astimezone().isoformat(timespec="seconds")

    output = []
    arena_errors = []
    already_existing = 0

    for game in sorted(
        unique.values(),
        key=lambda x: (
            x["date"],
            x["time"],
            x["home"],
            x["away"],
        ),
    ):
        canonical = venue_lookup.get(norm(game["venue"]))

        if not canonical:
            arena_errors.append({
                "venue": game["venue"],
                "group_id": game["group_id"],
                "series": game["series"],
                "source_url": game["source_url"],
            })
            continue

        venue = catalog[canonical]

        lat = venue.get("lat", venue.get("latitude"))
        lon = venue.get("lon", venue.get("longitude"))

        if lat in (None, "") or lon in (None, ""):
            arena_errors.append({
                "venue": game["venue"],
                "canonical": canonical,
                "problem": "coordinates_missing",
                "group_id": game["group_id"],
            })
            continue

        existing = (
            game["date"],
            game["time"][:5],
            norm(game["home"]),
            norm(game["away"]),
        )

        if existing in existing_hockey:
            already_existing += 1
            continue

        address = str(
            venue.get("address")
            or venue.get("adress")
            or ""
        ).strip()

        city = str(
            venue.get("city")
            or venue.get("ort")
            or ""
        ).strip()

        municipality = str(
            venue.get("municipality")
            or venue.get("kommun")
            or ""
        ).strip()

        played = bool(
            re.fullmatch(
                r"\s*\d+\s*[-–]\s*\d+\s*",
                game["result"],
            )
        )

        output.append({
            "id": event_id(
                game["date"],
                game["time"],
                game["home"],
                game["away"],
                canonical,
            ),
            "sport": "Ishockey",
            "typ": "match",
            "sasong": "2026/27",
            "district": "Svensk ishockey",
            "serie": game["series"],
            "category": game["subgroup"] or game["series"],
            "namn": f'{game["home"]} - {game["away"]}',
            "hemmalag": game["home"],
            "bortalag": game["away"],
            "datum": game["date"],
            "datum_start": game["date"],
            "datum_slut": game["date"],
            "datum_exakt": True,
            "tid": game["time"][:5],
            "arena": game["venue"],
            "plats": address,
            "ort": city,
            "kommun": municipality,
            "lat": float(lat),
            "lon": float(lon),
            "status": "spelad" if played else "schemalagd",
            "resultat": game["result"],
            "kalla": "Swehockey",
            "source_type": "official_swehockey_schedule",
            "url": game["source_url"],
            "senast_uppdaterad": now,
            "swehockey_group_id": game["group_id"],
            "swehockey_group_ids": sorted(set(game["source_group_ids"])),
            "swehockey_round": game["round"],
            "swehockey_subgroup": game["subgroup"],
            "venue_address": address,
            "arena_adress": address,
            "venue_verified": True,
            "venue_catalog_verified": True,
            "arena_catalog_name": canonical,
            "arena_verified": True,
            "geocode_source": "venue_catalog",
            "location_precision": "venue",
            "venue_resolution_method": "event_arena",
        })

    unique_arena_errors = {}
    for error in arena_errors:
        unique_arena_errors[norm(error["venue"])] = error

    report = {
        "season": "2026/27",
        "group_range": [START_ID, END_ID],
        "groups_with_games": groups_with_games,
        "raw_match_rows": len(all_games),
        "unique_matches_before_existing_filter": len(unique),
        "duplicate_rows_removed": duplicate_rows,
        "already_existing_hockey_matches": already_existing,
        "new_events_ready": len(output),
        "arena_errors": len(arena_errors),
        "unique_unmatched_arenas": len(unique_arena_errors),
        "unmatched_arenas": list(unique_arena_errors.values()),
    }

    PREVIEW.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print()
    print("SWEHOCKEY 2026/27 – DRY RUN KLAR")
    print("=" * 48)
    print("Grupper med matcher:", groups_with_games)
    print("Matchrader totalt:", len(all_games))
    print("Unika matcher:", len(unique))
    print("Dubblettrader borttagna:", duplicate_rows)
    print("Redan befintliga hockeymatcher:", already_existing)
    print("Nya matcher redo:", len(output))
    print("Arena-/koordinatfel:", len(arena_errors))
    print("Unika ej matchade arenor:", len(unique_arena_errors))

    if output:
        print(
            "Datumintervall:",
            output[0]["datum"],
            "–",
            output[-1]["datum"],
        )

    if unique_arena_errors:
        print("\nEj matchade arenor:")
        for error in list(unique_arena_errors.values())[:30]:
            print(
                " -",
                error["venue"],
                "|",
                error.get("series", ""),
                "| grupp",
                error.get("group_id", ""),
            )

    print("\nPreview:", PREVIEW)
    print("Rapport:", REPORT)


if __name__ == "__main__":
    main()
