import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


# ============================================================
# EVENTFINDER - DISCOVERY SVENSK SENIORINNEBANDY
# ============================================================

SEASON = "2026/27"

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"

OUTPUT_FILE = (
    DATA_DIR
    / "floorball_district_sources.json"
)

DEBUG_FILE = (
    DATA_DIR
    / "floorball_district_discovery_debug.json"
)

USER_AGENT = (
    "Eventfinder/1.0 "
    "(public Swedish floorball district discovery)"
)


# ============================================================
# SVENSK INNEBANDYS 19 SDF
# ============================================================

DISTRICTS = {
    "Dalarna": {
        "slug": "dalarna",
        "verified_id": "18",
    },

    "Gotland": {
        "slug": "gotland",
        "verified_id": "19",
    },

    "Gävleborg": {
        "slug": "gavleborg",
        "verified_id": "20",
    },

    "Halland": {
        "slug": "halland",
        "verified_id": "22",
    },

    "Jämtland-Härjedalen": {
        "slug": "jamtland-harjedalen",
        "verified_id": "24",
    },

    "Norrbotten": {
        "slug": "norrbotten",
        "verified_id": "4",
    },

    "Skåne": {
        "slug": "skane",
        "verified_id": "6",
    },

    "Småland-Blekinge": {
        "slug": "smaland-blekinge",
        "verified_id": "7",
    },

    "Stockholm": {
        "slug": "stockholm",
        "verified_id": "8",
    },

    "Södermanland": {
        "slug": "sodermanland",
        "verified_id": "9",
    },

    "Uppland": {
        "slug": "uppland",
        "verified_id": "10",
    },

    "Värmland": {
        "slug": "varmland",
        "verified_id": "11",
    },

    "Västerbotten": {
        "slug": "vasterbotten",
        "verified_id": "12",
    },

    "Västergötland": {
        "slug": "vastergotland",
        "verified_id": "23",
    },

    "Västernorrland": {
        "slug": "vasternorrland",
        "verified_id": "17",
    },

    "Västmanland": {
        "slug": "vastmanland",
        "verified_id": "15",
    },

    "Västsvenska": {
        "slug": "vastsvenska",
        "verified_id": "21",
    },

    "Örebro Län": {
        "slug": "orebro-lan",
        "verified_id": "5",
    },

    "Östergötland": {
        "slug": "ostergotland",
        "verified_id": "16",
    },
}


# ============================================================
# HTML-LÄNKPARSER
# ============================================================

class LinkParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.links = []

        self.in_link = False
        self.href = ""
        self.text_parts = []

    def handle_starttag(self, tag, attrs):

        if tag.lower() != "a":
            return

        attrs = dict(attrs)

        href = attrs.get("href")

        if not href:
            return

        self.in_link = True
        self.href = href
        self.text_parts = []

    def handle_data(self, data):

        if self.in_link:
            self.text_parts.append(
                data
            )

    def handle_endtag(self, tag):

        if (
            tag.lower() != "a"
            or not self.in_link
        ):
            return

        text = " ".join(
            self.text_parts
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        self.links.append(
            {
                "text": text,
                "href": self.href,
            }
        )

        self.in_link = False
        self.href = ""
        self.text_parts = []


# ============================================================
# HTTP
# ============================================================

def fetch_html(url):

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language":
                "sv-SE,sv;q=0.9",
        },
    )

    try:

        with urlopen(
            request,
            timeout=25,
        ) as response:

            raw = response.read()

            charset = (
                response.headers
                .get_content_charset()
                or "utf-8"
            )

            try:
                return raw.decode(
                    charset
                )

            except UnicodeDecodeError:
                return raw.decode(
                    "utf-8",
                    errors="replace",
                )

    except HTTPError as error:

        print(
            f"  HTTP {error.code}: "
            f"{url}"
        )

    except URLError as error:

        print(
            f"  Nätverksfel: "
            f"{error.reason}"
        )

    except TimeoutError:

        print(
            f"  Timeout: {url}"
        )

    return None


# ============================================================
# LÄNKAR
# ============================================================

def extract_links(
    html,
    source_url,
):

    parser = LinkParser()
    parser.feed(html)

    result = []

    for item in parser.links:

        full_url = urljoin(
            source_url,
            item["href"],
        )

        result.append(
            {
                "text": item["text"],
                "url": full_url,
                "source_page":
                    source_url,
            }
        )

    return result


# ============================================================
# SIDOR ATT UNDERSÖKA
# ============================================================

def candidate_pages(slug):

    base = (
        f"https://www.innebandy.se/"
        f"{slug}"
    )

    return [
        base,
        base + "/tavling",
        base + "/tavling/seriespel",
        base + "/tavling/distriktsserier",
        base + "/tavling/spelprogram-och-tabeller",
        base + "/tavling/hitta-din-serie",
    ]


# ============================================================
# FORBUND-ID
# ============================================================

FORBUND_PATTERN = re.compile(
    r"https?://stats\.innebandy\.se/"
    r"forbund/(\d+)/livematches",
    re.IGNORECASE,
)

OLD_FORBUND_PATTERN = re.compile(
    r"[?&]ffid=(\d+)",
    re.IGNORECASE,
)


def extract_forbund_id(url):

    match = FORBUND_PATTERN.search(
        url
    )

    if match:
        return match.group(1)

    match = OLD_FORBUND_PATTERN.search(
        url
    )

    if match:
        return match.group(1)

    return None


# ============================================================
# NORMALISERING
# ============================================================

def normalize(text):

    text = text.lower()

    replacements = {
        "å": "a",
        "ä": "a",
        "ö": "o",
        "é": "e",
        "–": "-",
        "—": "-",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# ============================================================
# RELEVANS
# ============================================================

def score_link(link):

    text = normalize(
        link["text"]
    )

    url = normalize(
        link["url"]
    )

    combined = (
        text
        + " "
        + url
    )

    score = 0

    phrases = [
        "matcher och resultat",
        "dagens matcher",
        "matcher i dag",
        "matcher, tabeller",
        "spelprogram",
        "tabeller",
    ]

    for phrase in phrases:

        if phrase in combined:
            score += 5

    if (
        "stats.innebandy.se/forbund/"
        in url
    ):
        score += 20

    if (
        "statistik.innebandy.se"
        in url
    ):
        score += 10

    if extract_forbund_id(
        link["url"]
    ):
        score += 20

    return score


# ============================================================
# DISCOVERY PER DISTRIKT
# ============================================================

def discover_district(
    district_name,
    info,
):

    slug = info["slug"]

    expected_id = (
        info["verified_id"]
    )

    print()
    print(
        f"=== {district_name} ==="
    )

    print(
        f"Förväntat ID: "
        f"{expected_id}"
    )

    all_links = []
    visited_pages = []

    for page_url in candidate_pages(
        slug
    ):

        print(
            f"Hämtar: "
            f"{page_url}"
        )

        html = fetch_html(
            page_url
        )

        if not html:
            continue

        visited_pages.append(
            page_url
        )

        all_links.extend(
            extract_links(
                html,
                page_url,
            )
        )

        time.sleep(
            0.25
        )

    # --------------------------------------------------------
    # Ta bort duplicerade länkar
    # --------------------------------------------------------

    unique_links = {}

    for link in all_links:

        url = link["url"]

        if url not in unique_links:
            unique_links[url] = link

    ranked = []

    for link in unique_links.values():

        found_id = extract_forbund_id(
            link["url"]
        )

        score = score_link(
            link
        )

        if (
            not found_id
            and score <= 0
        ):
            continue

        item = dict(link)

        item["score"] = score
        item["forbund_id"] = found_id

        item["matches_expected_id"] = (
            found_id == expected_id
        )

        ranked.append(
            item
        )

    ranked.sort(
        key=lambda item: (
            not item[
                "matches_expected_id"
            ],
            -item["score"],
            item["url"],
        )
    )

    # --------------------------------------------------------
    # Välj ENDAST länk med rätt distrikts-ID
    # --------------------------------------------------------

    selected = None

    for item in ranked:

        if (
            item.get(
                "forbund_id"
            )
            == expected_id
        ):
            selected = item
            break

    print(
        f"Relevanta länkar: "
        f"{len(ranked)}"
    )

    for item in ranked[:10]:

        label = (
            item["text"]
            or "(ingen länktext)"
        )

        found_id = (
            item.get(
                "forbund_id"
            )
        )

        marker = ""

        if found_id:

            if found_id == expected_id:
                marker = " ✓"

            else:
                marker = " ✗"

        print(
            f"  {item['score']:>2} | "
            f"{label[:50]}"
        )

        print(
            f"       {item['url']}"
            f"{marker}"
        )

    # --------------------------------------------------------
    # Resultat
    # --------------------------------------------------------

    if selected:

        print()
        print(
            f"VERIFIERAT ID: "
            f"{expected_id}"
        )

        print(
            f"Källa: "
            f"{selected['url']}"
        )

        status = "verified"

        livematches_url = (
            f"https://stats.innebandy.se/"
            f"forbund/{expected_id}/"
            f"livematches"
        )

    else:

        print()
        print(
            "Ingen matchande länk hittades "
            "på distriktswebben."
        )

        print(
            "Använder verifierat distrikts-ID "
            "som fallback."
        )

        status = "verified_fallback"

        livematches_url = (
            f"https://stats.innebandy.se/"
            f"forbund/{expected_id}/"
            f"livematches"
        )

    return {
        "district":
            district_name,

        "slug":
            slug,

        "status":
            status,

        "forbund_id":
            expected_id,

        "livematches_url":
            livematches_url,

        "source_page":
            (
                selected[
                    "source_page"
                ]
                if selected
                else None
            ),

        "selected_text":
            (
                selected["text"]
                if selected
                else None
            ),

        "visited_pages":
            visited_pages,

        "candidate_links":
            ranked,
    }


# ============================================================
# KONTROLL AV ID-DUBLETTER
# ============================================================

def validate_unique_ids(results):

    seen = {}

    errors = []

    for item in results:

        forbund_id = (
            item["forbund_id"]
        )

        district = (
            item["district"]
        )

        if forbund_id in seen:

            errors.append(
                (
                    forbund_id,
                    seen[forbund_id],
                    district,
                )
            )

        else:

            seen[
                forbund_id
            ] = district

    return errors


# ============================================================
# SPARA
# ============================================================

def save_json(
    path,
    data,
):

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# RAPPORT
# ============================================================

def print_summary(results):

    live_verified = [
        item
        for item in results
        if item["status"]
        == "verified"
    ]

    fallback = [
        item
        for item in results
        if item["status"]
        == "verified_fallback"
    ]

    errors = validate_unique_ids(
        results
    )

    print()
    print(
        "============================================="
    )

    print(
        " DISCOVERY-RAPPORT"
    )

    print(
        "============================================="
    )

    print()
    print(
        f"Officiella SDF: "
        f"{len(results)}"
    )

    print(
        f"Direkt verifierade via webb: "
        f"{len(live_verified)}"
    )

    print(
        f"Verifierade fallback-ID:n: "
        f"{len(fallback)}"
    )

    print(
        f"ID-dubletter: "
        f"{len(errors)}"
    )

    print()
    print(
        "Förbunds-ID"
    )

    print(
        "----------"
    )

    for item in sorted(
        results,
        key=lambda item: int(
            item["forbund_id"]
        ),
    ):

        print(
            f"{item['forbund_id']:>2} | "
            f"{item['district']} | "
            f"{item['status']}"
        )

    if errors:

        print()
        print(
            "FEL: samma ID används av flera distrikt"
        )

        for (
            forbund_id,
            district_a,
            district_b,
        ) in errors:

            print(
                f"{forbund_id}: "
                f"{district_a} / "
                f"{district_b}"
            )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "============================================="
    )

    print(
        " EVENTFINDER - DISCOVERY 19 SDF"
    )

    print(
        "============================================="
    )

    print()
    print(
        f"Säsong: {SEASON}"
    )

    results = []

    debug = {}

    for (
        district_name,
        info
    ) in DISTRICTS.items():

        result = discover_district(
            district_name,
            info,
        )

        results.append(
            {
                "district":
                    result["district"],

                "slug":
                    result["slug"],

                "status":
                    result["status"],

                "forbund_id":
                    result[
                        "forbund_id"
                    ],

                "livematches_url":
                    result[
                        "livematches_url"
                    ],

                "source_page":
                    result[
                        "source_page"
                    ],

                "selected_text":
                    result[
                        "selected_text"
                    ],
            }
        )

        debug[
            district_name
        ] = result

    errors = validate_unique_ids(
        results
    )

    if errors:

        print()
        print(
            "STOPP: distrikts-ID:n är inte unika."
        )

        print_summary(
            results
        )

        return

    output = {
        "season":
            SEASON,

        "district_count":
            len(results),

        "districts":
            results,
    }

    save_json(
        OUTPUT_FILE,
        output,
    )

    save_json(
        DEBUG_FILE,
        debug,
    )

    print_summary(
        results
    )

    print()
    print(
        "Discovery-fil:"
    )

    print(
        OUTPUT_FILE
    )

    print()
    print(
        "Debug-fil:"
    )

    print(
        DEBUG_FILE
    )


if __name__ == "__main__":
    main()
