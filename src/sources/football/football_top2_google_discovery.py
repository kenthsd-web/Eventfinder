#!/usr/bin/env python3
import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path("src/sources/floorball").resolve()))
import floorball_google_bulk as gm

TARGETS = Path("data/football_top2_current_venue_targets.json")
OUT = Path("data/football_top2_google_discovery")
CACHE = OUT / "cache.json"
RESULTS = OUT / "results.json"


def norm(s):
    return gm.norm(s or "")


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def queries_for(row):
    team = row["team"]
    city = row.get("source_city", "")
    historical = row.get("historical_candidate") or ""
    official = row.get("official_current_venue") or ""

    q = []

    def add(x):
        x = " ".join(x.split())
        if x and x not in q:
            q.append(x)

    # Officiellt verifierad aktuell arena har högsta prioritet.
    if official:
        add(f"{official} {city}")
        add(f"{team} {official} {city}")

    # Aktuell arena discovery – laget är utgångspunkten.
    add(f"{team} hemmaarena {city}")
    add(f"{team} fotbollsarena {city}")
    add(f"{team} arena {city}")

    # Historisk kandidat används bara sist som sökhjälp.
    # Den får aldrig ensam avgöra resultatet.
    if historical:
        add(f"{historical} {city}")

    return q


def location_score(row, hit):
    score = 0
    evidence = []

    name = hit.get("google_name") or ""
    address = hit.get("google_address") or ""
    city = row.get("source_city") or ""
    municipality = (row.get("source_municipality") or "").replace(" Kommun", "")

    if name and norm(name) not in {"resultat", "results"}:
        score += 20
        evidence.append("REAL_PLACE_NAME")

    naddr = norm(address)

    if city and norm(city) in naddr:
        score += 50
        evidence.append("CITY_MATCH")
    elif municipality and norm(municipality) in naddr:
        score += 40
        evidence.append("MUNICIPALITY_MATCH")

    if hit.get("latitude") is not None and hit.get("longitude") is not None:
        score += 30
        evidence.append("EXACT_COORDS_FOUND")

    if address:
        score += 10
        evidence.append("ADDRESS_FOUND")

    # Discovery only: aldrig slutgodkänd här.
    if (
        name
        and norm(name) not in {"resultat", "results"}
        and hit.get("latitude") is not None
        and hit.get("longitude") is not None
        and ("CITY_MATCH" in evidence or "MUNICIPALITY_MATCH" in evidence)
    ):
        status = "GOOD_CANDIDATE"
    else:
        status = "REVIEW"

    return score, status, evidence


async def resolve_one(page, row):
    best = None

    anchor_item = {
        "source_city": row.get("source_city", ""),
        "event_cities": [],
        "source_address": "",
        "source_postcode": "",
        "home_teams": [row["team"]],
    }

    for query in queries_for(row):
        url = (
            "https://www.google.com/maps/search/?api=1&query="
            + quote_plus(query)
        )

        try:
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000,
            )
            await gm.click_cookie_consent(page)

            hit = await gm.extract_place(page, anchor_item)

            # Om Google gav en riktig plats med adress men inga exakta
            # koordinater: gör en andra, exakt sökning på platsnamn + adress.
            if (
                hit.get("google_name")
                and hit.get("google_address")
                and (
                    hit.get("latitude") is None
                    or hit.get("longitude") is None
                )
            ):
                exact_query = (
                    f"{hit['google_name']} {hit['google_address']}"
                )
                exact_url = (
                    "https://www.google.com/maps/search/?api=1&query="
                    + quote_plus(exact_query)
                )

                try:
                    await page.goto(
                        exact_url,
                        wait_until="domcontentloaded",
                        timeout=30000,
                    )
                    exact_hit = await gm.extract_place(page, anchor_item)

                    if (
                        exact_hit.get("google_name")
                        and exact_hit.get("latitude") is not None
                        and exact_hit.get("longitude") is not None
                    ):
                        hit = exact_hit
                except Exception:
                    pass

            # Skydd mot gamla V9-problemet:
            # generisk Google-resultatsida är INTE en plats.
            if not hit.get("google_name"):
                continue
            if norm(hit.get("google_name")) in {"resultat", "results"}:
                continue

            score, status, evidence = location_score(row, hit)

            cand = {
                **row,
                "query": query,
                **hit,
                "discovery_score": score,
                "discovery_status": status,
                "evidence": evidence,
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            }

            if best is None or score > best.get("discovery_score", -999):
                best = cand

            if status == "GOOD_CANDIDATE" and score >= 100:
                break

        except Exception as e:
            if best is None:
                best = {
                    **row,
                    "query": query,
                    "discovery_score": 0,
                    "discovery_status": "ERROR",
                    "error": repr(e),
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                }

    if best is None:
        best = {
            **row,
            "discovery_score": 0,
            "discovery_status": "NO_PLACE_FOUND",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }

    return best


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--retry", action="store_true")
    args = ap.parse_args()

    rows = load(TARGETS, [])
    cache = load(CACHE, {})

    pending = []
    for row in rows:
        team = row["team"]
        old = cache.get(team)

        if old is None or args.retry:
            pending.append(row)

    if args.limit:
        pending = pending[:args.limit]

    print("=" * 68)
    print("FOTBOLL TOP2 – GOOGLE DISCOVERY")
    print("=" * 68)
    print("Lag totalt:", len(rows))
    print("Redan cachade:", len(cache))
    print("Kvar denna körning:", len(pending))
    print()

    OUT.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=not args.headed,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        context = await browser.new_context(
            locale="sv-SE",
            viewport={"width": 1440, "height": 1000},
        )
        page = await context.new_page()

        for i, row in enumerate(pending, 1):
            print(
                f"[{i}/{len(pending)}] "
                f"{row['team']} | {row.get('source_city','')}",
                flush=True,
            )

            result = await resolve_one(page, row)
            cache[row["team"]] = result
            save(CACHE, cache)

            print(
                "   ",
                result.get("discovery_status"),
                "|",
                result.get("google_name", ""),
                "|",
                result.get("google_address", ""),
                "|",
                result.get("latitude"),
                result.get("longitude"),
                flush=True,
            )

        await browser.close()

    results = [cache[r["team"]] for r in rows if r["team"] in cache]
    save(RESULTS, results)

    good = sum(x.get("discovery_status") == "GOOD_CANDIDATE" for x in results)
    review = len(results) - good

    print()
    print("DISCOVERY KLAR")
    print("GOOD_CANDIDATE:", good)
    print("REVIEW/ÖVRIGT:", review)
    print("Resultat:", RESULTS)
    print()
    print("OBS: Inga arenor har skrivits till venue_catalog.json.")


if __name__ == "__main__":
    asyncio.run(main())
