import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data"

EVENTS = DATA / "events.json"
CATALOG = DATA / "venue_catalog.json"
PREVIEW = DATA / "shl_2026_27_preview.json"

SEASON_UUID = "ndcf81nlb3"
SERIES_UUID = "qQ9-bb0bzEWUk"
GAME_TYPE_UUID = "qQ9-af37Ti40B"

SCHEDULE_URL = (
    "https://www.shl.se/game-schedule"
    "?seasonUuid=ndcf81nlb3"
    "&seriesUuid=qQ9-bb0bzEWUk"
    "&gameTypeUuid=qQ9-af37Ti40B"
    "&completeSeason=all"
    "&homeAway=all"
    "&allGames=all"
)

API = "https://www.shl.se/api/sports-v2/game-schedule"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fetch_shl():
    params = {
        "seasonUuid": SEASON_UUID,
        "seriesUuid": SERIES_UUID,
        "gameTypeUuid": GAME_TYPE_UUID,
        "gamePlace": "all",
        "played": "all",
    }

    req = Request(
        API + "?" + urlencode(params),
        headers={
            "User-Agent": "Mozilla/5.0 Eventfinder/1.0",
            "Accept": "application/json",
            "x-s8y-instance-id": "shl1_shl",
        },
    )

    with urlopen(req, timeout=30) as r:
        return json.load(r)


def build_venue_lookup(catalog):
    lookup = {}

    for canonical, v in catalog.items():
        if not isinstance(v, dict):
            continue

        lookup[canonical.casefold()] = canonical

        for alias in v.get("aliases", []) or []:
            lookup[str(alias).casefold()] = canonical

    return lookup


def event_id(game_uuid):
    return hashlib.sha1(
        f"shl:2026-27:{game_uuid}".encode("utf-8")
    ).hexdigest()[:20]


def main():
    events = load_json(EVENTS)
    catalog = load_json(CATALOG)
    shl = fetch_shl()
    lookup = build_venue_lookup(catalog)

    games = shl.get("gameInfo", [])
    output = []
    errors = []

    now = datetime.now().astimezone().isoformat(timespec="seconds")

    for g in games:
        home = g["homeTeamInfo"]["names"]["long"]
        away = g["awayTeamInfo"]["names"]["long"]

        venue_name = g.get("venueInfo", {}).get("name", "")
        canonical = lookup.get(venue_name.casefold())

        if not canonical:
            errors.append(f"Arena saknas: {venue_name}")
            continue

        venue = catalog[canonical]

        lat = venue.get("lat", venue.get("latitude"))
        lon = venue.get("lon", venue.get("longitude"))

        if lat in (None, "") or lon in (None, ""):
            errors.append(f"Koordinater saknas: {canonical}")
            continue

        start = g["startDateTime"]
        datum, tid_full = start.split(" ", 1)
        tid = tid_full[:5]

        address = str(venue.get("address") or "").strip()
        city = str(venue.get("city") or venue.get("ort") or "").strip()
        municipality = str(
            venue.get("municipality") or venue.get("kommun") or ""
        ).strip()

        output.append({
            "id": event_id(g["uuid"]),
            "sport": "Ishockey",
            "typ": "match",
            "sasong": "2026/27",
            "district": "Nationell",
            "serie": "SHL",
            "category": "SHL",
            "namn": f"{home} - {away}",
            "hemmalag": home,
            "bortalag": away,
            "datum": datum,
            "datum_start": datum,
            "datum_slut": datum,
            "datum_exakt": True,
            "tid": tid,
            "arena": venue_name,
            "plats": address,
            "ort": city,
            "kommun": municipality,
            "lat": float(lat),
            "lon": float(lon),
            "status": "schemalagd",
            "kalla": "SHL",
            "source_type": "official_shl_api",
            "url": SCHEDULE_URL,
            "senast_uppdaterad": now,
            "shl_game_uuid": g["uuid"],
            "shl_ssgt_uuid": g.get("ssgtUuid"),
            "shl_round": g.get("roundNumber"),
            "shl_state": g.get("state"),
            "shl_venue_uuid": g.get("venueInfo", {}).get("uuid"),
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

    ids = [e["id"] for e in output]

    print("SHL 2026/27 – DRY RUN")
    print("=" * 40)
    print("API-matcher:", len(games))
    print("Byggda event:", len(output))
    print("Unika event-ID:", len(set(ids)))
    print("Arena-/koordinatfel:", len(errors))
    print("Befintliga events.json:", len(events))

    if output:
        dates = sorted(e["datum"] for e in output)
        print("Första matchdatum:", dates[0])
        print("Sista matchdatum:", dates[-1])

    if errors:
        print("\nFEL:")
        for x in errors:
            print(" ", x)

    PREVIEW.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print("\nPreview:", PREVIEW)


if __name__ == "__main__":
    main()
