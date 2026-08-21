from datetime import datetime

SPORTER = [
    "Fotboll",
    "Hockey",
    "Handboll",
    "Innebandy",
    "Volleyboll",
    "Golf",
]

events = [
    {
        "namn": "Exempelmatch",
        "sport": "Fotboll",
        "datum": "2026-08-22",
        "tid": "15:00",
        "plats": "Stockholms stadion",
        "kommun": "Stockholm",
        "lat": 59.3427,
        "lon": 18.0786,
        "kalla": "Manuellt exempel",
        "url": "",
    },
    {
        "namn": "Exempelturnering",
        "sport": "Volleyboll",
        "datum": "2026-08-23",
        "tid": "10:00",
        "plats": "Fyrishov",
        "kommun": "Uppsala",
        "lat": 59.8769,
        "lon": 17.6244,
        "kalla": "Manuellt exempel",
        "url": "",
    },
]


def sortera_event(eventlista):
    return sorted(
        eventlista,
        key=lambda event: datetime.strptime(
            f"{event['datum']} {event['tid']}",
            "%Y-%m-%d %H:%M",
        ),
    )


def filtrera_sport(eventlista, sport):
    return [
        event
        for event in eventlista
        if event["sport"].lower() == sport.lower()
    ]


def filtrera_kommun(eventlista, kommun):
    return [
        event
        for event in eventlista
        if event["kommun"].lower() == kommun.lower()
    ]


def visa_event(eventlista):
    if not eventlista:
        print("Inga event hittades.")
        return

    for event in sortera_event(eventlista):
        print(
            f"{event['datum']} {event['tid']} | "
            f"{event['sport']} | "
            f"{event['namn']} | "
            f"{event['plats']}, {event['kommun']}"
        )


def main():
    print("Eventfinder startar...")
    print(f"Antal event: {len(events)}")
    print()

    visa_event(events)


if __name__ == "__main__":
    main()
