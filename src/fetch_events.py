import hashlib
import json
import re
import sys
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


# ============================================================
# EVENTFINDER - SVENSK INNEBANDY 2026/27
# ============================================================

BASE_URL = "https://www.innebandy.se"
DOCUMENT_URL = f"{BASE_URL}/dokument"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PDF_DIR = DATA_DIR / "innebandy_pdfs"
EVENT_FILE = DATA_DIR / "events.json"
NATIONAL_TEAMS_FILE = DATA_DIR / "floorball_national_teams.json"

SPORT = "Innebandy"
SEASON = "2026/27"
SOURCE = "Svenska Innebandyförbundet"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 Eventfinder/1.0"
)


# ============================================================
# SERIER VI VILL IMPORTERA
# ============================================================

WANTED_DOCUMENTS = {
    "Spelschema SSL Herrar 2026 27": "SSL Herr",
    "Spelschema SSL Damer 2026 27": "SSL Dam",

    "Spelschema AH 2026 27": "Allsvenskan Herr",

    "Spelschema Allsvenskan Norra Dam 2026 27":
        "Allsvenskan Dam Norra",

    "Spelschema ASD 2026 27":
        "Allsvenskan Dam Södra",

    "Spelschema H1N 2026 27":
        "Division 1 Herr Norra",

    "Spelschema H1M 2026 27":
        "Division 1 Herr Mellersta",

    "Spelschema H1SS 2026 27":
        "Division 1 Herr Södra Svealand",

    "Spelschema H1SG 2026 27":
        "Division 1 Herr Södra Götaland",

    "Spelschema H1Ö 2026 27":
        "Division 1 Herr Östra",

    "Spelschema H1VG 2026 27":
        "Division 1 Herr Västra Götaland",
}


# ============================================================
# PYTHON-BEROENDE
# ============================================================

def kontrollera_pypdf():
    try:
        import pypdf
        return pypdf

    except ImportError:
        print()
        print("Paketet pypdf saknas.")
        print()
        print("Kör:")
        print()
        print("python3 -m pip install pypdf")
        print()
        print("Kör sedan programmet igen.")
        print()

        sys.exit(1)


# ============================================================
# HTML-LÄNKPARSER
# ============================================================

class LinkParser(HTMLParser):

    def __init__(self):
        super().__init__()

        self.links = []

        self.in_anchor = False
        self.current_href = ""
        self.current_text = []

    def handle_starttag(self, tag, attrs):

        if tag.lower() != "a":
            return

        attrs = dict(attrs)

        href = attrs.get("href")

        if not href:
            return

        self.in_anchor = True
        self.current_href = href
        self.current_text = []

    def handle_data(self, data):

        if self.in_anchor:
            self.current_text.append(data)

    def handle_endtag(self, tag):

        if tag.lower() != "a":
            return

        if not self.in_anchor:
            return

        text = " ".join(
            self.current_text
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        self.links.append(
            (
                text,
                self.current_href,
            )
        )

        self.in_anchor = False
        self.current_href = ""
        self.current_text = []


# ============================================================
# HTTP
# ============================================================

def request_bytes(url, timeout=30):

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "sv-SE,sv;q=0.9",
        },
    )

    try:

        with urlopen(
            request,
            timeout=timeout,
        ) as response:

            return response.read()

    except HTTPError as error:

        print(
            f"HTTP-fel {error.code}: {url}"
        )

    except URLError as error:

        print(
            f"Nätverksfel: {error.reason}"
        )

    except TimeoutError:

        print(
            f"Timeout: {url}"
        )

    return None


def request_text(url):

    raw = request_bytes(url)

    if not raw:
        return None

    try:
        return raw.decode("utf-8")

    except UnicodeDecodeError:
        return raw.decode(
            "latin-1",
            errors="replace",
        )


# ============================================================
# TEXTNORMALISERING
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
        "/": " ",
        "_": " ",
        "-": " ",
        "(": " ",
        ")": " ",
    }

    for old, new in replacements.items():
        text = text.replace(
            old,
            new,
        )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# ============================================================
# HITTA PDF-DOKUMENT
# ============================================================

def hitta_spelscheman():

    print(
        "Hämtar Svenska Innebandyförbundets dokumentlista..."
    )

    html = request_text(
        DOCUMENT_URL
    )

    if not html:
        return {}

    parser = LinkParser()
    parser.feed(html)

    pdf_links = []

    for text, href in parser.links:

        full_url = urljoin(
            BASE_URL,
            href,
        )

        if ".pdf" not in full_url.lower():
            continue

        pdf_links.append(
            {
                "text": text,
                "url": full_url,
            }
        )

    print(
        f"Hittade {len(pdf_links)} PDF-länkar."
    )

    resultat = {}

    for wanted_name, serie in WANTED_DOCUMENTS.items():

        wanted_normalized = normalize(
            wanted_name
        )

        bästa = None

        for link in pdf_links:

            text_normalized = normalize(
                link["text"]
            )

            url_normalized = normalize(
                link["url"]
            )

            ord_lista = [
                word
                for word in wanted_normalized.split()
                if len(word) >= 2
            ]

            score = 0

            for word in ord_lista:

                if (
                    word in text_normalized
                    or word in url_normalized
                ):
                    score += 1

            if bästa is None:
                bästa = (
                    score,
                    link,
                )

            elif score > bästa[0]:
                bästa = (
                    score,
                    link,
                )

        if bästa:

            required = max(
                3,
                len(
                    wanted_normalized.split()
                ) // 2,
            )

            if bästa[0] >= required:

                resultat[serie] = {
                    "namn": wanted_name,
                    "serie": serie,
                    "url": bästa[1]["url"],
                    "score": bästa[0],
                }

    return resultat


# ============================================================
# PDF-NEDLADDNING
# ============================================================

def safe_filename(text):

    text = normalize(text)

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return text.strip("_")


def download_pdf(serie, info):

    PDF_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    filename = (
        safe_filename(serie)
        + "_2026_27.pdf"
    )

    path = PDF_DIR / filename

    print(
        f"Laddar {serie}..."
    )

    raw = request_bytes(
        info["url"],
        timeout=45,
    )

    if not raw:

        if path.exists():

            print(
                "  Använder tidigare nedladdad PDF."
            )

            return path

        print(
            "  Kunde inte hämta."
        )

        return None

    if not raw.startswith(
        b"%PDF"
    ):

        print(
            "  Svaret var inte en PDF."
        )

        return None

    path.write_bytes(raw)

    print(
        f"  {len(raw) // 1024} KB"
    )

    return path


# ============================================================
# PDF -> TEXT
# ============================================================

def pdf_to_lines(
    pypdf,
    path,
):

    try:

        reader = pypdf.PdfReader(
            str(path)
        )

    except Exception as error:

        print(
            f"  Kunde inte läsa PDF: {error}"
        )

        return []

    lines = []

    for page in reader.pages:

        try:

            text = (
                page.extract_text()
                or ""
            )

        except Exception:

            continue

        for line in text.splitlines():

            line = re.sub(
                r"\s+",
                " ",
                line,
            ).strip()

            if line:
                lines.append(line)

    return lines


# ============================================================
# DATUM
# ============================================================

DATE_REGEX = re.compile(
    r"^20\d{2}-\d{2}-\d{2}$"
)

MATCH_ID_REGEX = re.compile(
    r"^58\d{7}$"
)

ROUND_REGEX = re.compile(
    r"^\d{1,2}$"
)


def is_date(text):

    return bool(
        DATE_REGEX.match(
            text.strip()
        )
    )


def is_match_id(text):

    return bool(
        MATCH_ID_REGEX.match(
            text.strip()
        )
    )


# ============================================================
# EVENT-ID
# ============================================================

def skapa_event_id(match_id):

    return hashlib.sha256(
        (
            f"{SPORT}|"
            f"{SEASON}|"
            f"{match_id}"
        ).encode("utf-8")
    ).hexdigest()[:20]


# ============================================================
# NATIONELLA LAGLISTOR
# ============================================================

def load_national_team_map():

    if not NATIONAL_TEAMS_FILE.exists():
        return {}

    try:
        data = json.loads(
            NATIONAL_TEAMS_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return data

    except Exception as error:
        print(
            "Kunde inte läsa nationell lagkatalog:",
            error,
        )

    return {}


# ============================================================
# PDF-PARSER
# ============================================================
def parse_schedule_lines(
    lines,
    serie,
    source_url,
):

    events = []

    # Matchradens struktur i förbundets PDF:
    #
    # matchnr omgång hemmalag bortalag startdatum slutdatum
    #
    # Lag kan innehålla flera ord, därför använder vi
    # datumen och en lista över kända lag för serien.

    TEAM_MAP = {
        "SSL Herr": [
            "AIK IBF",
            "FBC Kalmarsund",
            "IBF Falun",
            "IBK Dalen",
            "IBK Lund Elit",
            "Jönköpings IK",
            "Linköping IBK",
            "Mullsjö AIS",
            "Nykvarns IBF",
            "Pixbo IBK",
            "Storvreta IBK",
            "Visby IBK",
            "Växjö IBK",
            "Warberg IC",
        ],
        "SSL Dam": [
            "Endre IF",
            "FBC Kalmarsund",
            "IBK Lockerud Mariestad",
            "IBK Lund Elit",
            "KAIS Mora IF",
            "Karlstad IBF",
            "Malmö FBC",
            "Pixbo IBK",
            "Storvreta IBK",
            "Thorengruppen IBK",
            "Täby FC IBK",
            "Västerås Rönnby IBK",
            "Växjö IBK",
            "Warberg IC",
        ],
    }

    national_team_map = load_national_team_map()

    teams = TEAM_MAP.get(
        serie,
        []
    )

    if not teams:
        teams = national_team_map.get(
            serie,
            []
        )

    for raw_line in lines:

        # Vissa sidbrytningar kan slå ihop rubrik + matchrad.
        # Vi letar därför efter matchnumret var som helst i raden.

        match = re.search(
            r"(58\d{7})\s+"
            r"(\d{1,2})\s+"
            r"(.+?)\s+"
            r"(20\d{2}-\d{2}-\d{2})\s+"
            r"(20\d{2}-\d{2}-\d{2})",
            raw_line,
        )

        if not match:
            continue

        match_id = match.group(1)
        round_number = match.group(2)
        team_text = match.group(3).strip()
        start_date = match.group(4)
        end_date = match.group(5)

        hemmalag = ""
        bortalag = ""

        # SSL kan delas säkert via den officiella laglistan.
        if teams:

            for home in sorted(
                teams,
                key=len,
                reverse=True,
            ):

                prefix = home + " "

                if not team_text.startswith(prefix):
                    continue

                rest = team_text[
                    len(prefix):
                ].strip()

                for away in teams:

                    if rest == away:
                        hemmalag = home
                        bortalag = away
                        break

                if hemmalag:
                    break

        # Generisk fallback för andra serier.
        # Vi delar texten ungefär i mitten om ingen
        # laglista finns ännu.
        if not hemmalag:

            words = team_text.split()

            if len(words) < 2:
                continue

            best_split = None

            for split_pos in range(
                1,
                len(words),
            ):

                home = " ".join(
                    words[:split_pos]
                )

                away = " ".join(
                    words[split_pos:]
                )

                # Föredra två rimligt stora lagnamn.
                score = min(
                    len(home),
                    len(away),
                )

                if (
                    best_split is None
                    or score > best_split[0]
                ):
                    best_split = (
                        score,
                        home,
                        away,
                    )

            if best_split:
                hemmalag = best_split[1]
                bortalag = best_split[2]

        if not hemmalag or not bortalag:
            continue

        event = {
            "id": skapa_event_id(
                match_id
            ),
            "match_id": match_id,
            "sport": SPORT,
            "typ": "match",
            "sasong": SEASON,
            "serie": serie,
            "omgang": round_number,
            "namn": (
                f"{hemmalag} - "
                f"{bortalag}"
            ),
            "hemmalag": hemmalag,
            "bortalag": bortalag,
            "datum": start_date,
            "datum_start": start_date,
            "datum_slut": end_date,
            "datum_exakt": (
                start_date == end_date
            ),
            "tid": "",
            "plats": "",
            "arena": "",
            "ort": "",
            "kommun": "",
            "lat": None,
            "lon": None,
            "resultat": "",
            "status": (
                "schemalagd"
                if start_date == end_date
                else "datumintervall"
            ),
            "kalla": SOURCE,
            "source_type":
                "officiellt_spelschema_pdf",
            "url": source_url,
            "senast_uppdaterad":
                datetime.now().isoformat(
                    timespec="seconds"
                ),
        }

        events.append(event)

    return events


# ============================================================
# DUBLETTER
# ============================================================

def dedupe(events):

    result = {}

    for event in events:

        match_id = event.get(
            "match_id"
        )

        if not match_id:
            continue

        result[match_id] = event

    return list(
        result.values()
    )


# ============================================================
# BEFINTLIG DATA
# ============================================================

def load_existing():

    if not EVENT_FILE.exists():
        return []

    try:

        data = json.loads(
            EVENT_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(
            data,
            list,
        ):
            return data

    except Exception as error:

        print(
            f"Kunde inte läsa events.json: "
            f"{error}"
        )

    return []


# ============================================================
# MERGE
# ============================================================

def merge_events(
    existing,
    imported,
):

    result = {}

    # Behåll andra sporter och gamla event.

    for event in existing:

        key = event.get("id")

        if key:
            result[key] = event

    for new_event in imported:

        key = new_event["id"]

        old = result.get(key)

        if old:

            # Data vi senare kan ha kompletterat
            # från livekälla eller geokodning.

            preserve_fields = [
                "tid",
                "plats",
                "arena",
                "ort",
                "kommun",
                "lat",
                "lon",
                "resultat",
            ]

            for field in preserve_fields:

                old_value = old.get(
                    field
                )

                new_value = new_event.get(
                    field
                )

                if (
                    old_value not in (
                        "",
                        None,
                    )
                    and new_value in (
                        "",
                        None,
                    )
                ):
                    new_event[field] = (
                        old_value
                    )

        result[key] = new_event

    return list(
        result.values()
    )


# ============================================================
# SORTERING
# ============================================================

def sort_key(event):

    date = event.get(
        "datum",
        ""
    )

    time = (
        event.get("tid")
        or "23:59"
    )

    try:

        return datetime.strptime(
            f"{date} {time}",
            "%Y-%m-%d %H:%M",
        )

    except ValueError:

        return datetime.max


# ============================================================
# SPARA
# ============================================================

def save_events(events):

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    events = sorted(
        events,
        key=sort_key,
    )

    EVENT_FILE.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


# ============================================================
# STATISTIK
# ============================================================

def print_stats(events):

    series = {}

    exact_dates = 0
    date_ranges = 0

    for event in events:

        serie = event.get(
            "serie",
            "Okänd"
        )

        series[serie] = (
            series.get(
                serie,
                0,
            )
            + 1
        )

        if event.get(
            "datum_exakt"
        ):
            exact_dates += 1

        else:
            date_ranges += 1

    print()
    print("Importerade serier")
    print("------------------")

    for serie in sorted(series):

        print(
            f"{serie}: "
            f"{series[serie]} matcher"
        )

    print()
    print(
        f"Matcher med exakt datum: "
        f"{exact_dates}"
    )

    print(
        f"Matcher med datumintervall: "
        f"{date_ranges}"
    )


# ============================================================
# VISA EXEMPEL
# ============================================================

def show_examples(
    events,
    limit=20,
):

    print()
    print("Första importerade matcherna")
    print("---------------------------")

    for event in sorted(
        events,
        key=sort_key,
    )[:limit]:

        if event["datum_exakt"]:

            date_text = (
                event["datum"]
            )

        else:

            date_text = (
                f"{event['datum_start']}"
                f"–"
                f"{event['datum_slut']}"
            )

        print(
            f"{date_text} | "
            f"{event['serie']} | "
            f"{event['namn']} | "
            f"match {event['match_id']}"
        )


# ============================================================
# HUVUDIMPORT
# ============================================================
# ============================================================
# RENSNING AV GAMLA TESTEVENT
# ============================================================

TEST_EVENT_NAMES = {
    "Exempelmatch",
    "Exempelturnering",
    "Mullsjö AIS - Visby IBK",
    "AIK IBF - Nykvarns IBF",
    "IBK Lund Elit - Pixbo IBK",
    "IBF Falun - Växjö IBK",
}


def ar_gammalt_testevent(event):
    """
    Tar bort tidigare manuella testevent.

    Riktiga importerade matcher har source_type
    'officiellt_spelschema_pdf' och ett riktigt match_id.
    """

    source_type = event.get("source_type", "")
    match_id = str(event.get("match_id", ""))

    if source_type == "officiellt_spelschema_pdf":
        return False

    if match_id.startswith("58") and len(match_id) == 9:
        return False

    namn = event.get("namn", "")

    if namn in TEST_EVENT_NAMES:
        return True

    if event.get("kalla") in (
        "Manuellt exempel",
        "Svenska Innebandyförbundet",
    ):
        # äldre manuella objekt saknar normalt sasong/source_type
        if not event.get("sasong"):
            return True

    return False


def rensa_testevent(events):

    rena = []

    borttagna = []

    for event in events:

        if ar_gammalt_testevent(event):
            borttagna.append(event)
        else:
            rena.append(event)

    return rena, borttagna


# ============================================================
# LAGENS HEMORTER / KOMMUNER
# ============================================================
#
# Detta är INTE matcharena.
# Det är lagets normala hemort och används bara som fallback
# tills exakt matchplats finns.
# ============================================================

TEAM_LOCATIONS = {
    # SSL Herr
    "AIK IBF": {
        "ort": "Solna",
        "kommun": "Solna",
    },
    "FBC Kalmarsund": {
        "ort": "Kalmar",
        "kommun": "Kalmar",
    },
    "IBF Falun": {
        "ort": "Falun",
        "kommun": "Falun",
    },
    "IBK Dalen": {
        "ort": "Umeå",
        "kommun": "Umeå",
    },
    "IBK Lund Elit": {
        "ort": "Lund",
        "kommun": "Lund",
    },
    "Jönköpings IK": {
        "ort": "Jönköping",
        "kommun": "Jönköping",
    },
    "Linköping IBK": {
        "ort": "Linköping",
        "kommun": "Linköping",
    },
    "Mullsjö AIS": {
        "ort": "Mullsjö",
        "kommun": "Mullsjö",
    },
    "Nykvarns IBF": {
        "ort": "Nykvarn",
        "kommun": "Nykvarn",
    },
    "Pixbo IBK": {
        "ort": "Mölnlycke",
        "kommun": "Härryda",
    },
    "Storvreta IBK": {
        "ort": "Uppsala",
        "kommun": "Uppsala",
    },
    "Visby IBK": {
        "ort": "Visby",
        "kommun": "Gotland",
    },
    "Växjö IBK": {
        "ort": "Växjö",
        "kommun": "Växjö",
    },
    "Warberg IC": {
        "ort": "Varberg",
        "kommun": "Varberg",
    },

    # SSL Dam
    "Endre IF": {
        "ort": "Visby",
        "kommun": "Gotland",
    },
    "IBK Lockerud Mariestad": {
        "ort": "Mariestad",
        "kommun": "Mariestad",
    },
    "KAIS Mora IF": {
        "ort": "Mora",
        "kommun": "Mora",
    },
    "Karlstad IBF": {
        "ort": "Karlstad",
        "kommun": "Karlstad",
    },
    "Malmö FBC": {
        "ort": "Malmö",
        "kommun": "Malmö",
    },
    "Thorengruppen IBK": {
        "ort": "Umeå",
        "kommun": "Umeå",
    },
    "Täby FC IBK": {
        "ort": "Täby",
        "kommun": "Täby",
    },
    "Västerås Rönnby IBK": {
        "ort": "Västerås",
        "kommun": "Västerås",
    },
}


def komplettera_med_hemort(events):
    """
    Sätter hemort/kommun från hemmalaget när matchens
    exakta arena och ort ännu inte är känd.

    Fältet location_precision visar att detta är fallback-data.
    """

    antal = 0

    for event in events:

        if event.get("sport") != SPORT:
            continue

        hemmalag = event.get("hemmalag", "")

        location = TEAM_LOCATIONS.get(
            hemmalag
        )

        if not location:
            continue

        # Skriv inte över verifierad platsdata.
        if not event.get("ort"):
            event["ort"] = location["ort"]

        if not event.get("kommun"):
            event["kommun"] = location["kommun"]

        if not event.get("arena"):
            event["location_precision"] = "hemmalag_hemort"
        else:
            event["location_precision"] = "arena"

        antal += 1

    return antal


# ============================================================
# DATAKVALITET
# ============================================================

def data_quality_report(events):

    total = len(events)

    med_tid = 0
    med_arena = 0
    med_kommun = 0
    med_geo = 0
    exakta_datum = 0

    for event in events:

        if event.get("tid"):
            med_tid += 1

        if event.get("arena"):
            med_arena += 1

        if event.get("kommun"):
            med_kommun += 1

        if (
            event.get("lat") is not None
            and event.get("lon") is not None
        ):
            med_geo += 1

        if event.get("datum_exakt"):
            exakta_datum += 1

    print()
    print("Datakvalitet")
    print("------------")

    print(
        f"Totalt: {total}"
    )

    print(
        f"Exakt datum: {exakta_datum}"
    )

    print(
        f"Exakt tid: {med_tid}"
    )

    print(
        f"Arena: {med_arena}"
    )

    print(
        f"Kommun/hemort: {med_kommun}"
    )

    print(
        f"Koordinater: {med_geo}"
    )


# ============================================================
# SLUTBEARBETNING
# ============================================================

def slutbearbeta_events(events):

    events, borttagna = rensa_testevent(
        events
    )

    if borttagna:

        print()
        print(
            f"Rensade bort {len(borttagna)} "
            f"gamla testevent."
        )

    location_count = komplettera_med_hemort(
        events
    )

    print(
        f"Kompletterade hemort/kommun "
        f"för {location_count} event."
    )

    return events
def main():

    print()
    print(
        "============================================="
    )

    print(
        " EVENTFINDER - SVENSK INNEBANDY 2026/27"
    )

    print(
        "============================================="
    )

    pypdf = kontrollera_pypdf()

    documents = hitta_spelscheman()

    print()
    print(
        f"Matchande spelscheman: "
        f"{len(documents)}"
    )

    for serie in sorted(
        documents
    ):

        print(
            f"  ✓ {serie}"
        )

    missing = []

    for wanted_serie in (
        WANTED_DOCUMENTS.values()
    ):

        if wanted_serie not in documents:
            missing.append(
                wanted_serie
            )

    if missing:

        print()
        print(
            "Hittade inte automatiskt:"
        )

        for serie in missing:
            print(
                f"  - {serie}"
            )

    imported = []

    print()
    print("Importerar matcher")
    print("------------------")

    for serie, info in (
        documents.items()
    ):

        path = download_pdf(
            serie,
            info,
        )

        if not path:
            continue

        lines = pdf_to_lines(
            pypdf,
            path,
        )

        print(
            f"  Text-rader: "
            f"{len(lines)}"
        )

        events = (
            parse_schedule_lines(
                lines,
                serie,
                info["url"],
            )
        )

        events = dedupe(
            events
        )

        print(
            f"  Matcher: "
            f"{len(events)}"
        )

        imported.extend(
            events
        )

    imported = dedupe(
        imported
    )

    print()
    print(
        f"Totalt automatiskt importerade: "
        f"{len(imported)} matcher"
    )

    if not imported:

        print()
        print(
            "Ingen match kunde importeras."
        )

        print(
            "events.json ändras därför inte."
        )

        return

    existing = load_existing()
    combined = merge_events(
        existing,
        imported,
    )

    combined = slutbearbeta_events(
        combined
    )

    save_events(
        combined
    )

    data_quality_report(
        combined
    )

    print_stats(
        imported
    )

    show_examples(
        imported
    )

    show_examples(
        imported
    )

    print()
    print(
        "============================================="
    )

    print(
        f"Klart. events.json innehåller "
        f"{len(combined)} event."
    )

    print(
        f"Fil: {EVENT_FILE}"
    )

    print(
        "============================================="
    )


if __name__ == "__main__":
    main()
