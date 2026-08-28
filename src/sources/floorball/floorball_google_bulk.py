#!/usr/bin/env python3
import argparse
import asyncio
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError


WORKLIST = Path("data/floorball_google_worklist.json")
OUT_DIR = Path("data/floorball_google_bulk")
CACHE_FILE = OUT_DIR / "cache.json"
RESULTS_FILE = OUT_DIR / "results.json"
APPROVED_FILE = OUT_DIR / "approved.json"
REVIEW_FILE = OUT_DIR / "review.json"
ERRORS_FILE = OUT_DIR / "errors.json"
SHOTS_DIR = OUT_DIR / "screenshots"


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def clean_venue_name(raw: str) -> str:
    s = (raw or "").strip()

    # Common floor/court suffixes.
    s = re.sub(
        r"\s+(A-hall|B-hall|C-hall|D-hall|A hall|B hall|C hall|D hall)$",
        "",
        s,
        flags=re.I,
    )
    s = re.sub(r"\s+[A-D]\s*\d*$", "", s, flags=re.I)
    s = re.sub(r"\s+(Plan|Hall)\s*[A-D0-9]+$", "", s, flags=re.I)

    # Trailing single court marker in parentheses, e.g. "(D)".
    s = re.sub(r"\s*\([A-D]\)\s*$", "", s, flags=re.I)

    return s.strip()


def meaningful_tokens(s: str):
    stop = {
        "sverige", "sweden", "hall", "hallen", "arena", "sporthall",
        "idrottshall", "sportcentrum", "center", "centrum",
    }
    return {
        t for t in norm(s).split()
        if len(t) >= 3 and t not in stop
    }


def exact_coords_from_text(text: str):
    if not text:
        return None, None

    for p in [
        r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)",
        r"%213d(-?\d+\.\d+)%214d(-?\d+\.\d+)",
    ]:
        m = re.search(p, text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None, None


def map_center_from_url(url: str):
    if not url:
        return None, None
    m = re.search(r"/@(-?\d+\.\d+),(-?\d+\.\d+)", url)
    if m:
        return float(m.group(1)), float(m.group(2))
    return None, None


def parse_context_coords(text: str):
    if not text:
        return None, None
    for m in re.finditer(
        r"(-?\d{1,2}\.\d{4,8})\s*,\s*(-?\d{1,3}\.\d{4,8})",
        text,
    ):
        lat = float(m.group(1))
        lon = float(m.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    return None, None


async def coords_from_map_right_click(page, place_name: str):
    candidates = []

    if place_name:
        safe = place_name.replace('"', '\\"')
        candidates.extend([
            f'[role="button"][aria-label="{safe}"]',
            f'[role="button"][aria-label*="{safe}"]',
            f'[aria-label="{safe}"]',
            f'[aria-label*="{safe}"]',
        ])

    for selector in candidates:
        try:
            loc = page.locator(selector)
            count = await loc.count()
            for i in range(min(count, 5)):
                item = loc.nth(i)
                try:
                    box = await item.bounding_box()
                    if not box or box["width"] <= 0 or box["height"] <= 0:
                        continue

                    viewport = page.viewport_size or {"width": 1440, "height": 1000}
                    center_x = box["x"] + box["width"] / 2

                    # Avoid right-clicking the details panel.
                    if center_x < viewport["width"] * 0.40:
                        continue

                    await item.click(button="right", timeout=2500)
                    await page.wait_for_timeout(600)
                    body = await page.locator("body").inner_text()
                    lat, lon = parse_context_coords(body)
                    await page.keyboard.press("Escape")

                    if lat is not None:
                        return lat, lon, "MAP_RIGHT_CLICK_MARKER"
                except Exception:
                    try:
                        await page.keyboard.press("Escape")
                    except Exception:
                        pass
        except Exception:
            pass

    return None, None, None


async def exact_coords_from_page(page):
    # 1) Current URL.
    lat, lon = exact_coords_from_text(page.url)
    if lat is not None:
        return lat, lon, "PLACE_URL"

    # 2) Live links in the selected place panel.
    try:
        hrefs = await page.locator("a[href]").evaluate_all(
            "(els) => els.map(e => e.href).filter(Boolean)"
        )
        for href in hrefs:
            lat, lon = exact_coords_from_text(href)
            if lat is not None:
                return lat, lon, "PAGE_LINK"
    except Exception:
        pass

    # 3) Embedded Google Maps state in the DOM.
    try:
        html = await page.content()
        lat, lon = exact_coords_from_text(html)
        if lat is not None:
            return lat, lon, "PAGE_HTML"
    except Exception:
        pass

    # 4) Open Google's Share dialog and follow the share link.
    share_url = None
    share_clicked = False

    for selector in [
        'button[aria-label*="Dela"]',
        'button[jsaction*="share"]',
    ]:
        try:
            loc = page.locator(selector)
            if await loc.count():
                await loc.first.click(timeout=2500)
                await page.wait_for_timeout(1000)
                share_clicked = True
                break
        except Exception:
            pass

    if not share_clicked:
        try:
            loc = page.get_by_text("Dela", exact=True)
            if await loc.count():
                await loc.first.click(timeout=2500)
                await page.wait_for_timeout(1000)
                share_clicked = True
        except Exception:
            pass

    try:
        inputs = page.locator("input")
        for i in range(await inputs.count()):
            value = await inputs.nth(i).input_value()
            if value and ("maps.app.goo.gl" in value or "google.com/maps" in value):
                share_url = value
                break
    except Exception:
        pass

    if not share_url:
        try:
            links = page.locator('a[href*="maps.app.goo.gl"], a[href*="google.com/maps"]')
            for i in range(await links.count()):
                href = await links.nth(i).get_attribute("href")
                if href and ("maps.app.goo.gl" in href or "google.com/maps" in href):
                    share_url = href
                    break
        except Exception:
            pass

    if share_url:
        share_page = None
        try:
            share_page = await page.context.new_page()
            await share_page.goto(share_url, wait_until="domcontentloaded", timeout=30000)
            await share_page.wait_for_timeout(2500)

            lat, lon = exact_coords_from_text(share_page.url)
            if lat is not None:
                return lat, lon, "SHARE_URL"

            html = await share_page.content()
            lat, lon = exact_coords_from_text(html)
            if lat is not None:
                return lat, lon, "SHARE_HTML"
        except Exception:
            pass
        finally:
            if share_page:
                try:
                    await share_page.close()
                except Exception:
                    pass

    # 5) Manual-style fallback: right-click the venue marker on the map.
    place_name = ""
    try:
        h1 = page.locator("h1")
        if await h1.count():
            place_name = (await h1.first.inner_text()).strip()
    except Exception:
        pass

    lat, lon, source = await coords_from_map_right_click(page, place_name)
    if lat is not None:
        return lat, lon, source

    return None, None, None


async def click_cookie_consent(page):
    for label in [
        "Acceptera alla",
        "Godkänn alla",
        "Accept all",
        "Reject all",
        "Avvisa alla",
    ]:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.I))
            if await btn.count():
                await btn.first.click(timeout=1500)
                await page.wait_for_timeout(400)
                return
        except Exception:
            pass


async def read_place_panel(page):
    name = ""
    for selector in ["h1.DUwDvf", "h1"]:
        try:
            loc = page.locator(selector)
            if await loc.count():
                txt = (await loc.first.inner_text()).strip()
                if txt and txt.lower() not in {"resultat", "results"}:
                    name = txt
                    break
        except Exception:
            pass

    address = ""
    for selector in [
        'button[data-item-id="address"]',
        '[data-item-id="address"]',
    ]:
        try:
            loc = page.locator(selector)
            if await loc.count():
                txt = (await loc.first.inner_text()).strip()
                if txt:
                    address = re.sub(
                        r"^\s*Adress\s*",
                        "",
                        txt,
                        flags=re.I,
                    ).strip()
                    break
        except Exception:
            pass

    if address:
        address = " ".join(
            x.strip() for x in address.splitlines() if x.strip()
        )
        address = re.sub(
            r"^[^0-9A-Za-zÅÄÖåäö]+",
            "",
            address,
        ).strip()

    body = ""
    try:
        body = (await page.locator("body").inner_text())[:5000]
    except Exception:
        pass

    return {
        "google_name": name,
        "google_address": address,
        "map_center_latitude": map_center_from_url(page.url)[0],
        "map_center_longitude": map_center_from_url(page.url)[1],
        "google_url": page.url,
        "body_excerpt": body[:1200],
    }


def location_match_status(item, hit):
    """
    True  = tydligt platsstöd.
    False = Google-adressen motsäger våra platsankare.
    None  = för lite information för säkert beslut.

    Prioritet:
    1. Postnummer
    2. Källort/eventort
    3. Ort i hemmalag som mjukt stöd
    4. Källadress
    """

    cities, source_address, postcode = location_anchors(item)

    gaddr = hit.get("google_address", "") or ""
    if not gaddr:
        return None

    n_addr = norm(gaddr)

    # 1. Exakt postnummer är mycket starkt.
    if postcode:
        google_compact = re.sub(r"\s+", "", gaddr)
        if postcode in google_compact:
            return True

    # 2. Källort eller eventort.
    for city in cities:
        if norm(city) and norm(city) in n_addr:
            return True

    # 3. Hemmalag kan innehålla den lokala orten.
    # Används ENDAST som positivt stöd, aldrig som negativt bevis.
    team_stop = {
        "ibk", "ibf", "ibs", "fbc", "aik", "ifk", "if",
        "ik", "bk", "fc", "sk", "hf",
        "herr", "dam", "ungdom", "laget", "lag"
    }

    addr_tokens = set(n_addr.split())

    for team in item.get("home_teams", []):
        for token in norm(team).split():
            if len(token) < 5 or token in team_stop:
                continue

            for at in addr_tokens:
                # Hanterar även t.ex. Skutskär / Skutskärs.
                if (
                    token == at
                    or (
                        len(at) >= 5
                        and (
                            token.startswith(at)
                            or at.startswith(token)
                        )
                    )
                ):
                    return True

    # 4. Officiell källadress.
    src_tokens = meaningful_tokens(source_address)
    hit_tokens = meaningful_tokens(gaddr)

    if src_tokens:
        overlap = len(src_tokens & hit_tokens) / len(src_tokens)
        if overlap >= 0.40:
            return True

    # Google gav en faktisk adress, men inget av våra
    # platsankare stödjer den.
    if cities or source_address or postcode:
        return False

    return None


async def finalize_place_hit(page, hit):
    lat, lon, coord_source = await exact_coords_from_page(page)

    hit = dict(hit)
    hit["latitude"] = lat
    hit["longitude"] = lon
    hit["coordinate_source"] = coord_source
    hit["map_center_latitude"], hit["map_center_longitude"] = (
        map_center_from_url(page.url)
    )
    hit["google_url"] = page.url
    return hit


async def extract_place(page, item=None):
    await page.wait_for_timeout(1800)

    # Om Google visar flera resultat provar vi flera i stället för
    # att automatiskt acceptera första platsen.
    try:
        hrefs = await page.locator(
            'a[href*="/maps/place/"]'
        ).evaluate_all(
            """els => [...new Set(
                els.map(e => e.href).filter(Boolean)
            )]"""
        )
    except Exception:
        hrefs = []

    if hrefs and "/maps/place/" not in page.url:
        first_hit = None
        unknown_hit = None

        for href in hrefs[:10]:
            try:
                await page.goto(
                    href,
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await page.wait_for_timeout(1200)

                hit = await read_place_panel(page)

                if not hit.get("google_name"):
                    continue

                if first_hit is None:
                    first_hit = (href, dict(hit))

                status = (
                    location_match_status(item, hit)
                    if item is not None else None
                )

                # Rätt ort/postnummer/adress vinner direkt.
                if status is True:
                    return await finalize_place_hit(page, hit)

                # Spara en kandidat där Google saknar tillräcklig platsdata.
                if status is None and unknown_hit is None:
                    unknown_hit = (href, dict(hit))

            except Exception:
                continue

        # Ingen platsbekräftad träff. Hellre en oklar kandidat än
        # en uttryckligen felaktig ort.
        fallback = unknown_hit or first_hit
        if fallback:
            href, hit = fallback
            try:
                await page.goto(
                    href,
                    wait_until="domcontentloaded",
                    timeout=20000,
                )
                await page.wait_for_timeout(1000)
                hit = await read_place_panel(page)
            except Exception:
                pass
            return await finalize_place_hit(page, hit)

    # Google öppnade en enskild plats direkt.
    hit = await read_place_panel(page)
    return await finalize_place_hit(page, hit)


def location_anchors(item):
    cities = []

    for c in [item.get("source_city"), *item.get("event_cities", [])]:
        c = (c or "").strip()
        if c and norm(c) not in {norm(x) for x in cities}:
            cities.append(c)

    address = (item.get("source_address") or "").strip()
    postcode = re.sub(r"\s+", "", item.get("source_postcode") or "")

    return cities, address, postcode



def venue_name_roots(s):
    """
    Plockar ut tydliga namnrotter utan generiska halländelser.
    Ex:
      Stavsborgshallen -> stavsborg
      Vedeby Sporthall -> vedeby
      Rotskärsskolans Sporthall -> rotskars
    """
    roots = set()

    generic = {
        "sporthall", "idrottshall", "hall", "hallen",
        "arena", "center", "centrum", "sportcenter",
        "plan", "stora", "lilla"
    }

    for token in norm(s).split():
        if token in generic or len(token) < 5:
            continue

        root = token

        # Sammansatta hallnamn.
        for suffix in [
            "idrottshallen",
            "sporthallen",
            "idrottshall",
            "sporthall",
            "hallen",
            "hall",
            "skolans",
            "skolan",
        ]:
            if root.endswith(suffix) and len(root) > len(suffix) + 3:
                root = root[:-len(suffix)]
                break

        # Enkel svensk genitiv efter normalisering.
        if root.endswith("s") and len(root) >= 7:
            root = root[:-1]

        if len(root) >= 5 and root not in generic:
            roots.add(root)

    return roots

def confidence(item, hit):
    raw_name = item.get("source_name", "")
    clean_name = clean_venue_name(raw_name)

    n_raw = norm(clean_name)
    n_hit = norm(hit.get("google_name", ""))
    n_addr = norm(hit.get("google_address", ""))

    score = 0
    reasons = []

    # Name evidence.
    name_strength = 0
    if n_raw and n_hit:
        raw_tokens = set(n_raw.split())
        hit_tokens = set(n_hit.split())
        overlap = len(raw_tokens & hit_tokens) / max(1, len(raw_tokens))

        if n_raw == n_hit:
            score += 60
            name_strength = 3
            reasons.append("NAME_EXACT")
        elif overlap >= 0.80:
            score += 50
            name_strength = 3
            reasons.append("NAME_STRONG")
        elif overlap >= 0.50:
            score += 30
            name_strength = 2
            reasons.append("NAME_PARTIAL")

    for alias in item.get("aliases", []):
        if norm(alias) and norm(alias) == n_hit:
            score += 55
            name_strength = max(name_strength, 3)
            reasons.append("ALIAS_EXACT")
            break

    # Försiktig namnrotsmatch.
    # Används bara när vanlig namnmatchning inte räckte.
    if name_strength < 2:
        src_roots = venue_name_roots(clean_name)
        hit_roots = venue_name_roots(hit.get("google_name", ""))

        if src_roots and hit_roots and (src_roots & hit_roots):
            score += 35
            name_strength = 2
            reasons.append("NAME_ROOT_MATCH")

    # Location evidence.
    cities, source_address, postcode = location_anchors(item)
    location_strength = 0

    # Hård spärr mot tydligt fel ort/plats.
    location_status = location_match_status(item, hit)
    if location_status is False:
        score -= 120
        reasons.append("LOCATION_HARD_MISMATCH")

    for city in cities:
        if norm(city) and norm(city) in n_addr:
            score += 30
            location_strength = max(location_strength, 2)
            reasons.append("CITY_IN_ADDRESS")
            break

    if postcode:
        google_digits = re.sub(r"\s+", "", hit.get("google_address", ""))
        if postcode in google_digits:
            score += 30
            location_strength = max(location_strength, 3)
            reasons.append("POSTCODE_MATCH")

    src_tokens = meaningful_tokens(source_address)
    hit_tokens = meaningful_tokens(hit.get("google_address", ""))

    if src_tokens:
        overlap = len(src_tokens & hit_tokens) / len(src_tokens)
        if overlap >= 0.75:
            score += 35
            location_strength = max(location_strength, 3)
            reasons.append("ADDRESS_STRONG")
        elif overlap >= 0.40:
            score += 20
            location_strength = max(location_strength, 2)
            reasons.append("ADDRESS_PARTIAL")

    if location_status is True and location_strength < 2:
        score += 20
        location_strength = 2
        reasons.append("LOCATION_SMART_MATCH")

    if hit.get("latitude") is not None and hit.get("longitude") is not None:
        score += 20
        reasons.append("COORDS_FOUND")

    if hit.get("google_address"):
        score += 5
        reasons.append("ADDRESS_FOUND")

    has_source_location = bool(cities or source_address or postcode)
    has_coords = (
        hit.get("latitude") is not None
        and hit.get("longitude") is not None
    )

    # Strict auto-approval rule:
    # - exact/strong identity
    # - exact Google coordinates
    # - location support if source provides any location anchor
    if (
        name_strength >= 2
        and has_coords
        and (
            (has_source_location and location_strength >= 2)
            or (not has_source_location and name_strength >= 3)
        )
    ):
        label = "STRONG"
    elif name_strength >= 2 and has_coords:
        label = "REVIEW"
        reasons.append("LOCATION_NOT_CONFIRMED")
    elif name_strength >= 1:
        label = "REVIEW"
    else:
        label = "WEAK"

    return score, label, reasons


def build_queries(item):
    raw = (item.get("source_name") or "").strip()
    clean = clean_venue_name(raw)
    cities, address, postcode = location_anchors(item)

    primary_city = cities[0] if cities else ""
    full_source_address = " ".join(
        x for x in [address, postcode, primary_city] if x
    ).strip()

    queries = []

    def add(q):
        q = " ".join((q or "").split()).strip()
        if q and q not in queries:
            queries.append(q)

    # Strongest sources first.
    if full_source_address:
        add(f"{raw} {full_source_address}")
        if clean != raw:
            add(f"{clean} {full_source_address}")

    if primary_city:
        add(f"{raw} {primary_city}")
        if clean != raw:
            add(f"{clean} {primary_city}")

    for alias in item.get("aliases", [])[:5]:
        if primary_city:
            add(f"{alias} {primary_city}")
        elif full_source_address:
            add(f"{alias} {full_source_address}")
        else:
            add(alias)

    # Additional event city variants, useful when source City is missing/stale.
    for city in cities[1:4]:
        add(f"{raw} {city}")
        if clean != raw:
            add(f"{clean} {city}")

    # Home team is only a late fallback.
    for team in item.get("home_teams", [])[:2]:
        if primary_city:
            add(f"{team} {clean} {primary_city}")
        else:
            add(f"{team} {clean}")

    add(raw)
    if clean != raw:
        add(clean)

    return queries[:12]


async def search_one(page, item):
    queries = build_queries(item)
    best = None

    for query in queries:
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
            await click_cookie_consent(page)

            hit = await extract_place(page, item)
            score, label, reasons = confidence(item, hit)

            candidate = {
                **item,
                "query": query,
                **hit,
                "score": score,
                "confidence": label,
                "evidence": reasons,
                "checked_at": datetime.now().isoformat(timespec="seconds"),
            }

            if (
                best is None
                or candidate["score"] > best.get("score", -1)
                or (
                    candidate["score"] == best.get("score", -1)
                    and candidate["confidence"] == "STRONG"
                    and best.get("confidence") != "STRONG"
                )
            ):
                best = candidate

            if label == "STRONG":
                break

        except PlaywrightTimeoutError:
            continue
        except Exception as e:
            if best is None:
                best = {
                    **item,
                    "query": query,
                    "error": repr(e),
                    "score": 0,
                    "confidence": "ERROR",
                    "checked_at": datetime.now().isoformat(timespec="seconds"),
                }

    if best is None:
        best = {
            **item,
            "score": 0,
            "confidence": "ERROR",
            "error": "No Google Maps query completed",
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        }

    return best


def load_cache():
    if not CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(cache):
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(CACHE_FILE)


def write_outputs(worklist, cache):
    results = []

    for item in worklist:
        key = str(item["venue_id"])
        if key in cache:
            results.append(cache[key])

    approved = [
        x for x in results
        if x.get("confidence") == "STRONG"
    ]
    review = [
        x for x in results
        if x.get("confidence") in {"REVIEW", "WEAK"}
    ]
    errors = [
        x for x in results
        if x.get("confidence") == "ERROR"
    ]

    RESULTS_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    APPROVED_FILE.write_text(
        json.dumps(approved, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    REVIEW_FILE.write_text(
        json.dumps(review, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ERRORS_FILE.write_text(
        json.dumps(errors, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return results, approved, review, errors


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N not-yet-cached venues; 0 = all.",
    )
    parser.add_argument(
        "--retry-review",
        action="store_true",
        help="Re-run cached REVIEW/WEAK/ERROR venues.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Show Chromium instead of running headless.",
    )
    args = parser.parse_args()

    if not WORKLIST.exists():
        raise SystemExit(f"Missing worklist: {WORKLIST}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SHOTS_DIR.mkdir(parents=True, exist_ok=True)

    worklist = json.loads(WORKLIST.read_text(encoding="utf-8"))
    cache = load_cache()

    pending = []
    for item in worklist:
        key = str(item["venue_id"])
        old = cache.get(key)

        if old is None:
            pending.append(item)
        elif args.retry_review and old.get("confidence") in {
            "REVIEW", "WEAK", "ERROR"
        }:
            pending.append(item)

    if args.limit > 0:
        pending = pending[:args.limit]

    print("=" * 68)
    print("INNEBANDY – GOOGLE MAPS MASSKÖRNING")
    print("=" * 68)
    print("Totalt i arbetslistan:", len(worklist))
    print("Redan i cache:", len(cache))
    print("Kvar i denna körning:", len(pending))
    print("Cache:", CACHE_FILE)
    print()

    if not pending:
        results, approved, review, errors = write_outputs(worklist, cache)
        print("Inget kvar att köra.")
        print("STRONG:", len(approved))
        print("REVIEW/WEAK:", len(review))
        print("ERROR:", len(errors))
        return

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

        for i, item in enumerate(pending, 1):
            vid = item["venue_id"]
            name = item.get("source_name", "")
            city = item.get("source_city", "")
            print(
                f"[{i}/{len(pending)}] VenueID {vid} | "
                f"{name} | {city}",
                flush=True,
            )

            result = await search_one(page, item)
            cache[str(vid)] = result
            save_cache(cache)

            print(
                "   "
                f"{result.get('confidence')} "
                f"score={result.get('score')} | "
                f"{result.get('google_name', '')} | "
                f"{result.get('google_address', '')} | "
                f"{result.get('latitude')}, {result.get('longitude')} | "
                f"{result.get('coordinate_source')}",
                flush=True,
            )

            if result.get("confidence") != "STRONG":
                safe = re.sub(
                    r"[^A-Za-z0-9_-]+",
                    "_",
                    f"{vid}_{name}",
                )[:90]
                try:
                    await page.screenshot(
                        path=str(SHOTS_DIR / f"{safe}.png"),
                        full_page=True,
                    )
                except Exception:
                    pass

            # Refresh summary files continuously too.
            write_outputs(worklist, cache)

        await browser.close()

    results, approved, review, errors = write_outputs(worklist, cache)

    print()
    print("=" * 68)
    print("GOOGLE-MASSKÖRNING KLAR")
    print("=" * 68)
    print("Kontrollerade VenueID:", len(results))
    print("STRONG:", len(approved))
    print("REVIEW/WEAK:", len(review))
    print("ERROR:", len(errors))
    print("Resultat:", RESULTS_FILE)
    print("Godkända:", APPROVED_FILE)
    print("Granskning:", REVIEW_FILE)
    print("Fel:", ERRORS_FILE)

    sources = Counter(
        x.get("coordinate_source")
        for x in approved
        if x.get("coordinate_source")
    )
    if sources:
        print("\nKoordinatkällor:")
        for key, count in sources.most_common():
            print(f"  {key}: {count}")


if __name__ == "__main__":
    asyncio.run(main())
