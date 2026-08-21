import json
import hashlib
from datetime import datetime
from pathlib import Path


SPORT = "Innebandy"
KALLA = "Svenska Innebandyförbundet"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
EVENT_FILE = DATA_DIR / "events.json"


# ---------------------------------------------------------
# GEMENSAM EVENTMODELL
# ---------------------------------------------------------

def skapa_event(
    serie,
    hemmalag,
    bortalag,
    datum,
    tid="",
    hall="",
    ort="",
    match_id="",
    url="",
):
    event_id_text = "|".join([
        SPORT,
        serie,
        hemmalag,
        bortalag,
        datum,
        tid,
    ])

    event_id = hashlib.sha256(
        event_id_text.encode("utf-8")
    ).hexdigest()[:16]

    return {
        "id": event_id,
        "sport": SPORT,
        "typ": "match",
        "namn": f"{hemmalag} - {bortalag}",
        "serie": serie,
        "hemmalag": hemmalag,
        "bortalag": bortalag,
        "datum": datum,
        "tid": tid,
        "plats": hall,
        "ort": ort,
        "kommun": "",
        "lat": None,
        "lon": None,
        "match_id": match_id,
        "kalla": KALLA,
        "url": url,
        "hamtad": datetime.now().isoformat(timespec="seconds"),
    }


# ---------------------------------------------------------
# LAGRING
# ---------------------------------------------------------

def las_befintliga_event():
    if not EVENT_FILE.exists():
        return []

    try:
        with open(EVENT_FILE, "r", encoding="utf-8") as fil:
            data = json.load(fil)

        if isinstance(data, list):
            return data

    except (json.JSONDecodeError, OSError):
        pass

    return []


def spara_event(events):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(EVENT_FILE, "w", encoding="utf-8") as fil:
        json.dump(
            events,
            fil,
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------
# DUBLETTER
# ---------------------------------------------------------

def sla_ihop_event(gamla_event, nya_event):
    event_map = {}

    for event in gamla_event:
        event_map[event["id"]] = event

    for event in nya_event:
        event_map[event["id"]] = event

    return list(event_map.values())


# ---------------------------------------------------------
# SORTERING
# ---------------------------------------------------------

def sorteringsnyckel(event):
    datum = event.get("datum", "")
    tid = event.get("tid", "") or "23:59"

    try:
        return datetime.strptime(
            f"{datum} {tid}",
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        return datetime.max


def sortera_event(events):
    return sorted(events, key=sorteringsnyckel)


# ---------------------------------------------------------
# FILTER
# ---------------------------------------------------------

def filtrera_serie(events, serie):
    return [
        event
        for event in events
        if event.get("serie", "").lower() == serie.lower()
    ]


def filtrera_lag(events, lag):
    lag = lag.lower()

    return [
        event
        for event in events
        if lag in event.get("hemmalag", "").lower()
        or lag in event.get("bortalag", "").lower()
    ]


def filtrera_framtida(events):
    idag = datetime.now().date()

    resultat = []

    for event in events:
        try:
            eventdatum = datetime.strptime(
                event["datum"],
                "%Y-%m-%d",
            ).date()

            if eventdatum >= idag:
                resultat.append(event)

        except (ValueError, KeyError):
            continue

    return resultat


# ---------------------------------------------------------
# IMPORTKÄLLOR
# ---------------------------------------------------------

def hamta_ssl_herr():
    """
    Första importerlagret.

    Vi håller detta separat från lagringen så att vi senare kan
    byta ut implementationen mot:
    - officiellt iBIS API
    - publik matchfeed
    - annan tillåten officiell källa

    utan att resten av Eventfinder behöver ändras.
    """

    return [
        skapa_event(
            serie="SSL Herr",
            hemmalag="Mullsjö AIS",
            bortalag="Visby IBK",
            datum="2026-09-19",
        ),
        skapa_event(
            serie="SSL Herr",
            hemmalag="AIK IBF",
            bortalag="Nykvarns IBF",
            datum="2026-09-19",
        ),
        skapa_event(
            serie="SSL Herr",
            hemmalag="IBK Lund Elit",
            bortalag="Pixbo IBK",
            datum="2026-09-19",
        ),
        skapa_event(
            serie="SSL Herr",
            hemmalag="IBF Falun",
            bortalag="Växjö IBK",
            datum="2026-09-19",
        ),
    ]


def hamta_ssl_dam():
    """
    Förberedd importer för SSL Dam.
    """
    return []


def hamta_allsvenskan_herr():
    """
    Förberedd importer för Allsvenskan Herr.
    """
    return []


def hamta_allsvenskan_dam():
    """
    Förberedd importer för Allsvenskan Dam.
    """
    return []


# ---------------------------------------------------------
# HUVUDIMPORT
# ---------------------------------------------------------

def hamta_alla_innebandyevent():
    events = []

    kallor = [
        hamta_ssl_herr,
        hamta_ssl_dam,
        hamta_allsvenskan_herr,
        hamta_allsvenskan_dam,
    ]

    for kalla in kallor:
        try:
            nya = kalla()

            print(
                f"{kalla.__name__}: "
                f"{len(nya)} event"
            )

            events.extend(nya)

        except Exception as error:
            print(
                f"Fel i {kalla.__name__}: "
                f"{error}"
            )

    return events


# ---------------------------------------------------------
# VISNING
# ---------------------------------------------------------

def visa_event(events):
    if not events:
        print("Inga event hittades.")
        return

    for event in sortera_event(events):
        tid = event.get("tid") or "--:--"
        plats = event.get("plats") or "Plats ej satt"

        print(
            f"{event['datum']} "
            f"{tid} | "
            f"{event['serie']} | "
            f"{event['namn']} | "
            f"{plats}"
        )


# ---------------------------------------------------------
# PROGRAMSTART
# ---------------------------------------------------------

def main():
    print()
    print("===================================")
    print(" EVENTFINDER - INNEBANDYIMPORT")
    print("===================================")
    print()

    gamla_event = las_befintliga_event()

    print(
        f"Befintliga event i databasen: "
        f"{len(gamla_event)}"
    )

    nya_event = hamta_alla_innebandyevent()

    print()
    print(
        f"Hämtade innebandyevent: "
        f"{len(nya_event)}"
    )

    alla_event = sla_ihop_event(
        gamla_event,
        nya_event,
    )

    alla_event = sortera_event(alla_event)

    spara_event(alla_event)

    print(
        f"Totalt lagrade event: "
        f"{len(alla_event)}"
    )

    print(
        f"Sparat i: {EVENT_FILE}"
    )

    print()
    print("Kommande innebandyevent:")
    print("-------------------------")

    framtida = filtrera_framtida(
        [
            event
            for event in alla_event
            if event.get("sport") == SPORT
        ]
    )

    visa_event(framtida)


if __name__ == "__main__":
    main()
