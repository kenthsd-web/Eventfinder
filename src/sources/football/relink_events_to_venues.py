import json
import re
from collections import Counter
from pathlib import Path

DATA = Path("data")

EVENTS_PATH = DATA / "events.json"
CATALOG_PATH = DATA / "venue_catalog.json"
MATCH_MAP_PATH = DATA / "football_match_venues.json"
HOME_MAP_PATH = DATA / "football_stable_home_venues.json"

PLACEHOLDER = "Hemmaplan ej verifierad"


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def norm(text):
    text = str(text or "").strip().casefold()
    text = (
        text.replace("–", "-")
        .replace("—", "-")
        .replace("‐", "-")
    )
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*-\s*", "-", text)
    return text


events = load_json(EVENTS_PATH, [])
catalog = load_json(CATALOG_PATH, {})
match_map = load_json(MATCH_MAP_PATH, {})
home_map = load_json(HOME_MAP_PATH, {})

lookup = {}
collisions = set()


def add_lookup(key, main_name):
    key = norm(key)

    if not key:
        return

    if key in lookup and lookup[key] != main_name:
        collisions.add(key)
    else:
        lookup[key] = main_name


for main_name, row in catalog.items():
    add_lookup(main_name, main_name)

    for alias in row.get("aliases", []) or []:
        add_lookup(alias, main_name)

    canonical = row.get("canonical_venue_name")

    if canonical:
        add_lookup(canonical, main_name)


for key in collisions:
    lookup.pop(key, None)


def find_catalog_venue(arena):
    if not arena:
        return None

    if arena in catalog:
        return arena

    return lookup.get(norm(arena))


stats = Counter()
missing = Counter()

for event in events:
    sport = event.get("sport") or ""

    original_arena = (
        event.get("arena")
        or ""
    ).strip()

    candidate_arena = None
    method = None

    # 1. Befintlig riktig arena
    if (
        original_arena
        and not original_arena.startswith(PLACEHOLDER)
    ):
        candidate_arena = original_arena
        method = "event_arena"

    # 2. Fotboll: matchspecifik arena
    if (
        sport == "Fotboll"
        and (
            not candidate_arena
            or original_arena.startswith(PLACEHOLDER)
        )
    ):
        match_id = str(
            event.get("match_id")
            or ""
        ).strip()

        info = match_map.get(match_id)

        if isinstance(info, dict):
            arena = (
                info.get("arena")
                or ""
            ).strip()

            if arena:
                candidate_arena = arena
                method = "football_match_specific"

    # 3. Fotboll: verifierad stabil hemmaplan
    if (
        sport == "Fotboll"
        and not candidate_arena
    ):
        team = (
            event.get("hemmalag")
            or ""
        ).strip()

        info = home_map.get(team)

        if (
            isinstance(info, dict)
            and info.get("status") == "verified"
        ):
            arena = (
                info.get("arena")
                or ""
            ).strip()

            if arena:
                candidate_arena = arena
                method = "football_stable_home"

    if not candidate_arena:
        stats["no_candidate"] += 1
        continue

    main_name = find_catalog_venue(candidate_arena)

    if not main_name:
        stats["not_in_catalog"] += 1
        missing[candidate_arena] += 1
        continue

    venue = catalog[main_name]

    if venue.get("verified") is not True:
        stats["unverified_catalog"] += 1
        continue

    event["arena"] = main_name
    event["arena_catalog_name"] = main_name
    event["arena_verified"] = True
    event["venue_verified"] = True
    event["venue_catalog_verified"] = True
    event["venue_resolution_method"] = method

    address = (
        venue.get("address")
        or ""
    ).strip()

    city = (
        venue.get("city")
        or ""
    ).strip()

    if address:
        event["arena_adress"] = address
        event["plats"] = address

    if city:
        event["ort"] = city

    if venue.get("lat") is not None:
        event["lat"] = venue["lat"]

    if venue.get("lon") is not None:
        event["lon"] = venue["lon"]

    event["location_precision"] = (
        venue.get("location_precision")
        or "venue"
    )

    event["geocode_source"] = "venue_catalog"

    stats["linked"] += 1
    stats[method] += 1


EVENTS_PATH.write_text(
    json.dumps(
        events,
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print("======================================")
print("OMKOPPLING KLAR")
print("======================================")
print("Event totalt:", len(events))
print("Kopplade:", stats["linked"])
print("Via befintlig arena:", stats["event_arena"])
print(
    "Via matchspecifik fotbollsarena:",
    stats["football_match_specific"],
)
print(
    "Via stabil hemmaplan:",
    stats["football_stable_home"],
)
print("Ingen arenakandidat:", stats["no_candidate"])
print(
    "Arena saknas fortfarande i katalogen:",
    stats["not_in_catalog"],
)
print(
    "Ej verifierad katalogpost:",
    stats["unverified_catalog"],
)

print()
print("SAKNAS FORTFARANDE I KATALOGEN:")

for arena, count in missing.most_common(50):
    print(f"{count:4d} event | {arena}")
