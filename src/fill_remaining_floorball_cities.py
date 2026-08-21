import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"

EVENT_FILE = DATA_DIR / "events.json"
BACKUP_FILE = DATA_DIR / "events_before_remaining_city_fill.json"


ARENA_CITY_OVERRIDES = {
    "Torsviks Idrottshall": "Lidingö",
    "Stureforshallen": "Sturefors",
    "Larslunda Arena A": "Strängnäs",
    "Virda Sportcenter Hall 2 - Alvesta": "Alvesta",
    "Rödabergshallen": "Stockholm",
    "Kämpetorpshallen 2": "Stockholm",
    "Kämpetorpshallen 1": "Stockholm",
    "Kungsängshallen": "Norrköping",
    "Vasa Arena 2": "Linköping",
    "Movallen Iggesund": "Iggesund",
    "Radiomasten Innebandycenter": "Motala",
    "Pershagens Sporthall": "Södertälje",
    "Volvo CE Arena A2": "Eskilstuna",
    "Volvo CE Arena A": "Eskilstuna",
    "Sanda Sporthall 1": "Huskvarna",
    "Sanda Sporthall 1, 3-manna": "Huskvarna",
    "Pettersbergsskolan (S:T Ilian Skolan)": "Västerås",
    "Listerby Idrottshall": "Listerby",
    "Sporthallen Lärkan": "Sala",
    "Idrottshuset, Örebro Plan 1": "Örebro",
    "Carlforska gymnasiet": "Västerås",
    "Pinntorps Idrottshall": "Landvetter",
    "Valkebohallen": "Linköping",
    "Slättenskolan Idrottshall": "Månsarp",
    "Wahlbeckshallen A": "Linköping",
}


def main():
    print()
    print("=============================================")
    print(" EVENTFINDER - FYLLER KVARVARANDE ORTER")
    print("=============================================")
    print()

    events = json.loads(
        EVENT_FILE.read_text(encoding="utf-8")
    )

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    updated = 0
    skipped_no_arena = 0
    skipped_unknown_arena = 0

    for event in events:
        if (
            event.get("source_type")
            != "district_competition_full_schedule"
        ):
            continue

        if event.get("lat") is not None:
            continue

        if (event.get("ort") or "").strip():
            continue

        arena = (event.get("arena") or "").strip()

        if not arena:
            skipped_no_arena += 1
            continue

        city = ARENA_CITY_OVERRIDES.get(arena)

        if not city:
            skipped_unknown_arena += 1
            continue

        event["ort"] = city
        event["city_source"] = "verified_arena_mapping"

        updated += 1

    EVENT_FILE.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    remaining_without_city = sum(
        1
        for event in events
        if (
            event.get("source_type")
            == "district_competition_full_schedule"
            and event.get("lat") is None
            and not (event.get("ort") or "").strip()
        )
    )

    print(
        f"Matcher med ny ort: {updated}"
    )
    print(
        f"Utan arena: {skipped_no_arena}"
    )
    print(
        f"Arena utan mapping: {skipped_unknown_arena}"
    )
    print(
        f"Kvar utan ort och koordinater: "
        f"{remaining_without_city}"
    )

    print()
    print(
        f"Backup: {BACKUP_FILE}"
    )
    print(
        f"Uppdaterad fil: {EVENT_FILE}"
    )


if __name__ == "__main__":
    main()
