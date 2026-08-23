#!/usr/bin/env python3
import concurrent.futures
import html
import json
import re
import shutil
import time
import urllib.request
import urllib.error
import zipfile
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path.home() / "eventfinder"
DATA = ROOT / "data"
CATALOG = DATA / "venue_catalog.json"

# Aktuella 2026/27-grupper ligger i detta intervall på stats.swehockey.se.
# Vi skannar ett litet säkerhetsmarginalintervall runt de kända grupp-ID:n.
START_ID = 20850
END_ID = 21650
SEASON_MARKERS = ("2026-27", "2026/27", "2026–27")
BASE = "https://stats.swehockey.se/ScheduleAndResults/Schedule/{}"
UA = "Eventfinder/1.0 hockey venue discovery (personal project)"

OUT_DISCOVERED = DATA / "hockey_venues_discovered_2026_27.json"
OUT_MISSING = DATA / "hockey_venues_missing_from_catalog_2026_27.json"
OUT_FOUND = DATA / "hockey_venues_already_in_catalog_2026_27.json"
OUT_SUMMARY = DATA / "hockey_venue_discovery_summary_2026_27.json"
OUT_ZIP = DATA / "hockey_venue_discovery_2026_27.zip"

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_tr = False
        self.in_cell = False
        self.cell_buf = []
        self.row = []
        self.rows = []
        self.title_buf = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "tr":
            self.in_tr = True
            self.row = []
        elif tag in ("td", "th") and self.in_tr:
            self.in_cell = True
            self.cell_buf = []
        elif tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ("td", "th") and self.in_cell:
            txt = " ".join("".join(self.cell_buf).split())
            self.row.append(txt)
            self.in_cell = False
        elif tag == "tr" and self.in_tr:
            if self.row:
                self.rows.append(self.row)
            self.in_tr = False
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_cell:
            self.cell_buf.append(data)
        if self.in_title:
            self.title_buf.append(data)

    @property
    def title(self):
        return " ".join("".join(self.title_buf).split())

def norm(s):
    s = html.unescape(str(s or "")).strip().casefold()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\wåäöæøéü\- ]+", "", s, flags=re.I)
    return s.strip()

def fetch_schedule(group_id):
    url = BASE.format(group_id)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read()
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return group_id, None

    # Snabbt filter: endast aktuell säsong.
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    if not any(m in plain for m in SEASON_MARKERS):
        return group_id, None

    p = TableParser()
    try:
        p.feed(text)
    except Exception:
        return group_id, None

    venues = []
    for row in p.rows:
        cells = [" ".join(x.split()) for x in row if x.strip()]
        if len(cells) < 2:
            continue

        # Matchrader innehåller normalt "Lag - Lag"; venue ligger sist.
        game_idx = None
        for i, c in enumerate(cells):
            if re.search(r"\s[-–]\s", c):
                game_idx = i
                break
        if game_idx is None:
            continue

        venue = cells[-1].strip()
        if not venue:
            continue
        nv = norm(venue)
        if nv in {"venue", "arena", "spelplats", "result"}:
            continue
        # Resultatkolumn kan råka vara sist på vissa tomma/ofullständiga rader.
        if re.fullmatch(r"\d+\s*[-–]\s*\d+", venue):
            continue

        game = cells[game_idx]
        home = re.split(r"\s[-–]\s", game, maxsplit=1)[0].strip()
        venues.append({
            "venue": venue,
            "home_team": home,
            "group_id": group_id,
            "source_url": url,
            "page_title": p.title,
        })

    return group_id, venues if venues else None

def catalog_entries(data):
    """Returnerar iterable av (visningsnamn, objekt) oavsett rimlig katalogstruktur."""
    if isinstance(data, list):
        for x in data:
            if isinstance(x, dict):
                name = x.get("name") or x.get("arena") or x.get("venue") or x.get("canonical_name")
                if name:
                    yield str(name), x
            elif isinstance(x, str):
                yield x, {"name": x}
        return

    if not isinstance(data, dict):
        return

    for key in ("venues", "arenas", "items", "catalog"):
        if key in data:
            yield from catalog_entries(data[key])
            return

    # Om toppnivån själv är name -> object
    likely = 0
    for k, v in data.items():
        if isinstance(v, dict):
            likely += 1
            yield str(k), v
    if likely:
        return

def catalog_name_index(data):
    idx = {}
    for key_name, obj in catalog_entries(data):
        names = {key_name}
        if isinstance(obj, dict):
            for k in ("name", "arena", "venue", "canonical_name", "canonical"):
                if obj.get(k):
                    names.add(str(obj[k]))
            aliases = obj.get("aliases") or obj.get("alias") or []
            if isinstance(aliases, str):
                aliases = [aliases]
            if isinstance(aliases, list):
                names.update(str(a) for a in aliases if a)
        for n in names:
            nn = norm(n)
            if nn:
                idx[nn] = {"catalog_name": key_name, "object": obj}
    return idx

def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def main():
    if not CATALOG.exists():
        raise SystemExit(f"Saknar {CATALOG}")

    # Backup före hockeyarbetet.
    backup = DATA / "venue_catalog_before_hockey_2026_08_23.json"
    if not backup.exists():
        shutil.copy2(CATALOG, backup)

    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    cidx = catalog_name_index(catalog)

    print("ISHOCKEY – ARENADISCOVERY START")
    print(f"Skannar officiella Swehockey grupp-ID {START_ID}–{END_ID} ...", flush=True)

    usage = defaultdict(lambda: {
        "venue": None,
        "games_seen": 0,
        "home_teams": set(),
        "group_ids": set(),
        "sources": set(),
        "page_titles": set(),
    })
    groups_with_games = 0

    ids = list(range(START_ID, END_ID + 1))
    completed = 0

    # Måttlig parallellism: snabbare men utan att hamra sajten.
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_schedule, gid): gid for gid in ids}
        for fut in concurrent.futures.as_completed(futs):
            completed += 1
            gid, rows = fut.result()
            if rows:
                groups_with_games += 1
                for r in rows:
                    k = norm(r["venue"])
                    u = usage[k]
                    u["venue"] = r["venue"]
                    u["games_seen"] += 1
                    if r["home_team"]:
                        u["home_teams"].add(r["home_team"])
                    u["group_ids"].add(r["group_id"])
                    u["sources"].add(r["source_url"])
                    if r["page_title"]:
                        u["page_titles"].add(r["page_title"])
            if completed % 50 == 0:
                print(f"{completed}/{len(ids)} skannade | grupper med matcher: {groups_with_games} | unika hallar: {len(usage)}", flush=True)

    discovered = []
    found = []
    missing = []

    for k in sorted(usage, key=lambda x: usage[x]["venue"].casefold()):
        u = usage[k]
        item = {
            "venue": u["venue"],
            "games_seen": u["games_seen"],
            "home_teams": sorted(u["home_teams"]),
            "group_ids": sorted(u["group_ids"]),
            "sources": sorted(u["sources"]),
            "page_titles": sorted(u["page_titles"]),
            "official_source": "stats.swehockey.se",
            "season": "2026-27",
        }
        hit = cidx.get(k)
        if hit:
            item["catalog_match"] = hit["catalog_name"]
            item["catalog_status"] = "found"
            found.append(item)
        else:
            item["catalog_status"] = "missing"
            missing.append(item)
        discovered.append(item)

    summary = {
        "season": "2026-27",
        "official_source": "https://stats.swehockey.se/",
        "group_id_range_scanned": [START_ID, END_ID],
        "groups_with_games": groups_with_games,
        "unique_hockey_venues": len(discovered),
        "already_in_venue_catalog": len(found),
        "missing_from_venue_catalog": len(missing),
        "note": "Ingen katalogpost har lagts till automatiskt ännu. Saknade hallar ska först få verifierad adress/koordinat.",
    }

    save(OUT_DISCOVERED, discovered)
    save(OUT_FOUND, found)
    save(OUT_MISSING, missing)
    save(OUT_SUMMARY, summary)

    with zipfile.ZipFile(OUT_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for p in (OUT_DISCOVERED, OUT_FOUND, OUT_MISSING, OUT_SUMMARY):
            z.write(p, arcname=p.name)

    print("\n======================================")
    print("ISHOCKEY – ARENADISCOVERY KLAR")
    print("======================================")
    print(f"Grupper med matcher: {groups_with_games}")
    print(f"Unika ishallar/arenor använda 2026/27: {len(discovered)}")
    print(f"Redan i venue_catalog: {len(found)}")
    print(f"Saknas i venue_catalog: {len(missing)}")
    print(f"Ladda upp: {OUT_ZIP}")
    print("\nOBS: venue_catalog har INTE ändrats ännu; det är avsiktligt.")
    print("Nästa pass verifierar adress/koordinater för de saknade innan de läggs in.")

if __name__ == "__main__":
    main()
