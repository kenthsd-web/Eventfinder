import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
EVENT_FILE = BASE_DIR / "data" / "events.json"
BACKUP_FILE = (
    BASE_DIR
    / "data"
    / "events_before_placeholder_cleanup.json"
)


def main():
    print()
    print("=============================================")
    print(" EVENTFINDER - STÄDAR PLACEHOLDER-DATUM")
    print("=============================================")
    print()

    events = json.loads(
        EVENT_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(events, list):
        raise RuntimeError(
            "events.json innehåller inte en lista."
        )

    BACKUP_FILE.write_text(
        EVENT_FILE.read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )

    changed = 0

    for event in events:
        if (
            event.get("source_type")
            != "district_competition_full_schedule"
        ):
            continue

        if (
            event.get("datum") != "2027-01-01"
            or event.get("tid") != "00:00"
        ):
            continue

        event["datum_exakt"] = False
        event["tid"] = ""
        event["status"] = "datum_ej_faststallt"

        event["date_placeholder"] = True
        event["original_placeholder_date"] = "2027-01-01"
        event["original_placeholder_time"] = "00:00"

        changed += 1

    EVENT_FILE.write_text(
        json.dumps(
            events,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    exact_dates = 0
    uncertain_dates = 0
    with_time = 0
    district_matches = 0

    for event in events:
        if (
            event.get("source_type")
            != "district_competition_full_schedule"
        ):
            continue

        district_matches += 1

        if event.get("datum_exakt") is True:
            exact_dates += 1
        else:
            uncertain_dates += 1

        if event.get("tid"):
            with_time += 1

    print(f"Placeholder-matcher ändrade: {changed}")

    print()
    print("Datakvalitet")
    print("------------")
    print(f"Distriktsmatcher totalt: {district_matches}")
    print(f"Exakta datum: {exact_dates}")
    print(f"Ej exakta datum: {uncertain_dates}")
    print(f"Matcher med exakt tid: {with_time}")

    print()
    print(f"Backup: {BACKUP_FILE}")
    print(f"Uppdaterad fil: {EVENT_FILE}")


if __name__ == "__main__":
    main()
