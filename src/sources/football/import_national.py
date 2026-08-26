import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

from series_catalog import SERIES

EVENT_FILE = Path("data/events.json")
VENUE_CATALOG_FILE = Path("data/venue_catalog.json")
MATCH_VENUES_FILE = Path("data/football_match_venues.json")
STABLE_HOME_FILE = Path("data/football_stable_home_venues.json")

BASE_URL = "https://www.svenskfotboll.se/widget.aspx"
PLACEHOLDER = "Hemmaplan ej verifierad"


class RowParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current = []
        self.href = None
        self.in_row = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.in_row = True
            self.current = []
            self.href = None

        if self.in_row and tag == "a":
            attrs = dict(attrs)
            self.href = attrs.get("href")

    def handle_data(self, data):
        if self.in_row:
            text = data.strip()
            if text:
                self.current.append(text)

    def handle_endtag(self, tag):
        if tag == "tr" and self.in_row:
            if self.current:
                self.rows.append(
                    {
                        "text": self.current[:],
                        "href": self.href,
                    }
                )
            self.in_row = False


def load_json(path, default):
    if not path.exists():
        return default

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def norm(text):
    text = str(text or "").strip().casefold()

    text = (
        text.replace("–", "-")
            .replace("—", "-")
            .replace("‐", "-")
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    text = re.sub(
        r"\s*-\s*",
        "-",
        text,
    )

    return text


def build_venue_lookup(catalog):
    lookup = {}
    collisions = set()

    def add(key, main_name):
        key = norm(key)

        if not key:
            return

        if (
            key in lookup
            and lookup[key] != main_name
        ):
            collisions.add(key)
        else:
            lookup[key] = main_name

    for main_name, row in catalog.items():
        add(
            main_name,
            main_name,
        )

        for alias in row.get(
            "aliases",
            []
        ) or []:
            add(
                alias,
                main_name,
            )

        canonical = row.get(
            "canonical_venue_name"
        )

        if canonical:
            add(
                canonical,
                main_name,
            )

    for key in collisions:
        lookup.pop(
            key,
            None,
        )

    return lookup


def find_catalog_venue(
    arena,
    catalog,
    lookup,
):
    if not arena:
        return None

    if arena in catalog:
        return arena

    return lookup.get(
        norm(arena)
    )


def fetch_html(competition_id):
    url = (
        f"{BASE_URL}?"
        f"p=1&scr=cominginleague&"
        f"ftid={competition_id}&nbr=500"
    )

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0"
        },
    )

    with urllib.request.urlopen(
        req,
        timeout=30,
    ) as r:
        data = json.loads(
            r.read().decode(
                "utf-8",
                errors="ignore",
            )
        )

    return data.get(
        "html"
    ) or ""


def parse_matches(html):
    parser = RowParser()
    parser.feed(html)

    matches = []

    for row in parser.rows:
        parts = row["text"]

        if len(parts) < 3:
            continue

        if not re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            parts[0],
        ):
            continue

        if not re.fullmatch(
            r"\d{2}:\d{2}",
            parts[1],
        ):
            continue

        match_name = parts[-1]

        if " - " not in match_name:
            continue

        home, away = match_name.split(
            " - ",
            1,
        )

        match_id = None

        href = (
            row.get("href")
            or ""
        )

        m = re.search(
            r"fmid=(\d+)",
            href,
        )

        if m:
            match_id = m.group(1)

        matches.append(
            {
                "match_id":
                    match_id,
                "datum":
                    parts[0],
                "tid":
                    parts[1],
                "hemmalag":
                    home.strip(),
                "bortalag":
                    away.strip(),
            }
        )

    return matches


def resolve_football_arena(
    match,
    match_venues,
    stable_home,
):
    match_id = str(
        match.get("match_id")
        or ""
    ).strip()

    # 1. Matchspecifik arena
    info = match_venues.get(
        match_id
    )

    if isinstance(
        info,
        dict,
    ):
        arena = (
            info.get("arena")
            or ""
        ).strip()

        if arena:
            return (
                arena,
                "football_match_specific",
            )

    # 2. Stabil hemmaplan
    home_team = (
        match.get("hemmalag")
        or ""
    ).strip()

    info = stable_home.get(
        home_team
    )

    if (
        isinstance(
            info,
            dict,
        )
        and info.get("status")
        == "verified"
    ):
        arena = (
            info.get("arena")
            or ""
        ).strip()

        if arena:
            return (
                arena,
                "football_stable_home",
            )

    return (
        "",
        None,
    )


def apply_catalog_data(
    event,
    arena,
    method,
    catalog,
    venue_lookup,
):
    main_name = find_catalog_venue(
        arena,
        catalog,
        venue_lookup,
    )

    if not main_name:
        event["arena"] = arena
        event[
            "venue_resolution_method"
        ] = method

        event[
            "venue_catalog_verified"
        ] = False

        event[
            "arena_verified"
        ] = False

        event[
            "venue_verified"
        ] = False

        return False

    venue = catalog[
        main_name
    ]

    if (
        venue.get("verified")
        is not True
    ):
        event["arena"] = main_name

        event[
            "venue_resolution_method"
        ] = method

        event[
            "venue_catalog_verified"
        ] = False

        event[
            "arena_verified"
        ] = False

        event[
            "venue_verified"
        ] = False

        return False

    event["arena"] = main_name

    event[
        "arena_catalog_name"
    ] = main_name

    event[
        "venue_resolution_method"
    ] = method

    event[
        "venue_catalog_verified"
    ] = True

    event[
        "arena_verified"
    ] = True

    event[
        "venue_verified"
    ] = True

    address = (
        venue.get("address")
        or ""
    ).strip()

    city = (
        venue.get("city")
        or ""
    ).strip()

    if address:
        event[
            "arena_adress"
        ] = address

        event[
            "plats"
        ] = address

    if city:
        event[
            "ort"
        ] = city

    if (
        venue.get("lat")
        is not None
    ):
        event[
            "lat"
        ] = venue["lat"]

    if (
        venue.get("lon")
        is not None
    ):
        event[
            "lon"
        ] = venue["lon"]

    event[
        "location_precision"
    ] = (
        venue.get(
            "location_precision"
        )
        or "venue"
    )

    event[
        "geocode_source"
    ] = "venue_catalog"

    return True


def main():
    events = load_json(
        EVENT_FILE,
        [],
    )

    catalog = load_json(
        VENUE_CATALOG_FILE,
        {},
    )

    match_venues = load_json(
        MATCH_VENUES_FILE,
        {},
    )

    stable_home = load_json(
        STABLE_HOME_FILE,
        {},
    )

    venue_lookup = (
        build_venue_lookup(
            catalog
        )
    )

    existing = {
        str(e.get("match_id"))
        for e in events
        if (
            e.get("sport")
            == "Fotboll"
            and e.get("match_id")
        )
    }

    added = 0
    linked = 0
    match_specific = 0
    stable = 0
    unresolved = 0

    for series in SERIES:
        competition_id = (
            series[
                "competition_id"
            ]
        )

        print(
            "Hämtar:",
            series["name"],
            competition_id,
        )

        html = fetch_html(
            competition_id
        )

        matches = parse_matches(
            html
        )

        print(
            "  Matcher:",
            len(matches),
        )

        for match in matches:
            match_id = str(
                match.get(
                    "match_id"
                )
                or ""
            )

            if (
                match_id
                and match_id in existing
            ):
                continue

            arena, method = (
                resolve_football_arena(
                    match,
                    match_venues,
                    stable_home,
                )
            )

            event = {
                "id":
                    f"football_{match_id}",
                "sport":
                    "Fotboll",
                "typ":
                    "match",
                "sasong":
                    "2026",
                "serie":
                    series["name"],
                "competition_id":
                    competition_id,
                "match_id":
                    match.get(
                        "match_id"
                    ),
                "gender":
                    series["gender"],
                "namn": (
                    f"{match['hemmalag']} - "
                    f"{match['bortalag']}"
                ),
                "hemmalag":
                    match["hemmalag"],
                "bortalag":
                    match["bortalag"],
                "datum":
                    match["datum"],
                "datum_start":
                    match["datum"],
                "datum_slut":
                    match["datum"],
                "datum_exakt":
                    True,
                "tid":
                    match["tid"],
                "arena":
                    "",
                "plats":
                    "",
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
                    "Svensk Fotboll",
                "source_type":
                    "svff_widget_competition",
                "url": (
                    "https://www."
                    "svenskfotboll.se/"
                    "widget-go-to/"
                    f"?scr=result&"
                    f"fmid={match_id}"
                ),
            }

            if arena:
                ok = apply_catalog_data(
                    event,
                    arena,
                    method,
                    catalog,
                    venue_lookup,
                )

                if ok:
                    linked += 1

                if (
                    method
                    == "football_match_specific"
                ):
                    match_specific += 1

                elif (
                    method
                    == "football_stable_home"
                ):
                    stable += 1

            else:
                unresolved += 1

            events.append(
                event
            )

            if match_id:
                existing.add(
                    match_id
                )

            added += 1

    EVENT_FILE.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print()
    print(
        "======================================"
    )
    print(
        "FOTBOLLSIMPORT KLAR"
    )
    print(
        "======================================"
    )
    print(
        "Fotbollsmatcher tillagda:",
        added,
    )
    print(
        "Direkt katalogkopplade:",
        linked,
    )
    print(
        "Matchspecifik arena hittad:",
        match_specific,
    )
    print(
        "Stabil hemmaplan hittad:",
        stable,
    )
    print(
        "Utan arenakandidat:",
        unresolved,
    )


if __name__ == "__main__":
    main()
