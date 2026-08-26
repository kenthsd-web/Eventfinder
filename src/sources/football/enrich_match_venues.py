import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("data")
EVENTS_PATH = DATA / "events.json"
MAP_PATH = DATA / "football_match_venues.json"
DEBUG_PATH = DATA / "football_match_venue_unresolved.json"

PREFIX = "Hemmaplan ej verifierad"


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


events = load_json(EVENTS_PATH, [])
mapped = load_json(MAP_PATH, {})

matches = []

for e in events:
    if e.get("source_type") != "svff_widget_competition":
        continue

    arena = (e.get("arena") or "").strip()

    if not arena.startswith(PREFIX):
        continue

    match_id = str(e.get("match_id") or "").strip()

    if not match_id:
        continue

    if match_id in mapped:
        continue

    matches.append(e)


print("======================================")
print("SVFF MATCHARENA ENRICHMENT")
print("======================================")
print("Redan mappade:", len(mapped))
print("Kvar att kontrollera:", len(matches))
print()


def clean_line(s):
    return re.sub(r"\s+", " ", s).strip()


def extract_arena(text):
    """
    Försök hitta arena/spelplats i SvFF Matchfakta.
    Vi använder flera mönster eftersom sidans layout kan variera.
    """

    lines = [
        clean_line(x)
        for x in text.splitlines()
        if clean_line(x)
    ]

    labels = {
        "arena",
        "spelplats",
        "anläggning",
        "arena/spelplats",
    }

    # Modell 1:
    # Arena
    # Brunnbyvallen
    for i, line in enumerate(lines):
        if line.casefold().rstrip(":") in labels:
            for candidate in lines[i + 1:i + 4]:
                c = clean_line(candidate)

                if not c:
                    continue

                low = c.casefold()

                if low in labels:
                    continue

                if (
                    "visa karta" in low
                    or "vägbeskrivning" in low
                    or "matchinformation" in low
                ):
                    continue

                return c

    # Modell 2:
    # Arena: Brunnbyvallen
    patterns = [
        r"(?im)^arena\s*:\s*(.+)$",
        r"(?im)^spelplats\s*:\s*(.+)$",
        r"(?im)^anläggning\s*:\s*(.+)$",
    ]

    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            candidate = clean_line(m.group(1))
            if candidate:
                return candidate

    return None


unresolved = load_json(DEBUG_PATH, {})


with sync_playwright() as p:

    # Persistent profil gör att Cloudflare-cookie/session kan återanvändas.
    profile = str(
        (DATA / "svff_browser_profile").resolve()
    )

    context = p.chromium.launch_persistent_context(
        profile,
        headless=False,
        locale="sv-SE",
        viewport={
            "width": 1280,
            "height": 900,
        },
        args=[
            "--disable-blink-features=AutomationControlled",
        ],
    )

    page = context.pages[0] if context.pages else context.new_page()

    # --------------------------------------------------------
    # ÖPPNA FÖRSTA MATCHEN FÖR ATT ETABLERA SESSION
    # --------------------------------------------------------

    if matches:
        first = matches[0]

        print("Öppnar första SvFF-matchen...")
        print(first["url"])
        print()

        page.goto(
            first["url"],
            wait_until="domcontentloaded",
            timeout=90000,
        )

        # Om Cloudflare visas i synliga webbläsaren:
        # scriptet väntar tills sidan inte längre har "Vänta..."
        for _ in range(180):
            title = page.title().casefold()
            body = page.locator("body").inner_text().casefold()

            blocked = (
                "vänta" in title
                or "säkerhetsverifiering" in body
                or "verifying you are human" in body
            )

            if not blocked:
                break

            time.sleep(1)

        print("Session redo.")
        print()

    # --------------------------------------------------------
    # ALLA MATCHER
    # --------------------------------------------------------

    total = len(matches)

    for index, e in enumerate(matches, 1):

        match_id = str(e["match_id"])
        url = e["url"]

        print(
            f"[{index}/{total}] "
            f"{match_id} | "
            f"{e.get('namn', '')}"
        )

        try:
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=90000,
            )

            page.wait_for_timeout(1800)

            body = page.locator("body").inner_text()

            low = body.casefold()

            if (
                "säkerhetsverifiering" in low
                or "verifying you are human" in low
            ):
                print("  CLOUDFLARE - väntar")

                for _ in range(120):
                    page.wait_for_timeout(1000)

                    body = page.locator(
                        "body"
                    ).inner_text()

                    low = body.casefold()

                    if (
                        "säkerhetsverifiering" not in low
                        and
                        "verifying you are human" not in low
                    ):
                        break

            arena = extract_arena(body)

            # Extra kontroll:
            # leta efter arena-liknande länkar om textetiketten missas.
            if not arena:
                try:
                    links = page.locator("a").all()

                    for link in links:
                        label = clean_line(
                            link.inner_text()
                        )

                        href = (
                            link.get_attribute("href")
                            or ""
                        )

                        low_href = href.casefold()

                        if (
                            label
                            and any(
                                x in low_href
                                for x in [
                                    "arena",
                                    "venue",
                                    "anlaggning",
                                    "spelplats",
                                ]
                            )
                        ):
                            arena = label
                            break
                except Exception:
                    pass

            if arena:
                mapped[match_id] = {
                    "arena": arena,
                    "source": "svff_matchfakta_browser",
                    "url": page.url,
                }

                save_json(
                    MAP_PATH,
                    mapped,
                )

                unresolved.pop(
                    match_id,
                    None,
                )

                save_json(
                    DEBUG_PATH,
                    unresolved,
                )

                print("  OK |", arena)

            else:
                # Spara utdrag för senare analys.
                unresolved[match_id] = {
                    "match": e.get("namn"),
                    "url": page.url,
                    "text": body[:6000],
                }

                save_json(
                    DEBUG_PATH,
                    unresolved,
                )

                print("  INGEN ARENA HITTAD")

        except Exception as ex:
            unresolved[match_id] = {
                "match": e.get("namn"),
                "url": url,
                "error": str(ex),
            }

            save_json(
                DEBUG_PATH,
                unresolved,
            )

            print(
                "  FEL |",
                type(ex).__name__,
                str(ex)[:200],
            )

        # Lite lugnare mot SvFF.
        page.wait_for_timeout(1200)

    context.close()


print()
print("======================================")
print("KLART")
print("======================================")
print("Totalt mappade:", len(mapped))
print("Fortfarande olösta:", len(unresolved))
print("Mapping:", MAP_PATH)
print("Debug:", DEBUG_PATH)
