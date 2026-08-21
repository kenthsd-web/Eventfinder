import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


SPORT = "Innebandy"
KALLA = "Svenska Innebandyförbundet"


def hamta_json(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Eventfinder/1.0"
        }
    )

    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))

    except HTTPError as error:
        print(f"HTTP-fel: {error.code}")
    except URLError as error:
        print(f"Anslutningsfel: {error.reason}")
    except json.JSONDecodeError:
        print("Svaret var inte giltig JSON.")

    return None


def skapa_event(
    matchnummer,
    serie,
    hemmalag,
    bortalag,
    datum,
    tid="",
    hall="",
    ort=""
):
    return {
        "namn": f"{hemmalag} - {bortalag}",
        "sport": SPORT,
        "serie": serie,
        "datum": datum,
        "tid": tid,
        "plats": hall,
        "kommun": ort,
        "hemmalag": hemmalag,
        "bortalag": bortalag,
        "matchnummer": matchnummer,
        "kalla": KALLA,
    }


def hamta_event():
    print("Hämtar innebandyevent från officiell källa...")

    events = []

    # Första officiella SSL Herr-matcherna 2026/27.
    # Dessa används för att testa Eventfinders datamodell.
    events.append(
        skapa_event(
            "580001001",
            "SSL Herr",
            "Mullsjö AIS",
            "Visby IBK",
            "2026-09-19",
        )
    )

    events.append(
        skapa_event(
            "580001002",
            "SSL Herr",
            "AIK IBF",
            "Nykvarns IBF",
            "2026-09-19",
        )
    )

    events.append(
        skapa_event(
            "580001003",
            "SSL Herr",
            "IBK Lund Elit",
            "Pixbo IBK",
            "2026-09-19",
        )
    )

    events.append(
        skapa_event(
            "580001007",
            "SSL Herr",
            "IBF Falun",
            "Växjö IBK",
            "2026-09-19",
        )
    )

    return events


if __name__ == "__main__":
    events = hamta_event()

    print(f"Hittade {len(events)} event.")
    print()

    for event in events:
        print(
            f"{event['datum']} | "
            f"{event['serie']} | "
            f"{event['namn']}"
        )
