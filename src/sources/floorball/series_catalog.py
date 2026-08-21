# ============================================================
# EVENTFINDER - SERIEKATALOG SVENSK SENIORINNEBANDY 2026/27
# ============================================================

SEASON = "2026/27"


def serie(
    name,
    level,
    gender,
    organiser,
    district=None,
    source_type="ibis_public",
    active=True,
):
    return {
        "name": name,
        "season": SEASON,
        "level": level,
        "gender": gender,
        "organiser": organiser,
        "district": district,
        "source_type": source_type,
        "active": active,
    }


# ============================================================
# NATIONELLA SERIER
# ============================================================

NATIONAL_SERIES = [
    serie(
        "SSL Herr",
        1,
        "herr",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "SSL Dam",
        1,
        "dam",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Allsvenskan Herr",
        2,
        "herr",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Allsvenskan Dam Norra",
        2,
        "dam",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Allsvenskan Dam Södra",
        2,
        "dam",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Division 1 Herr Norra",
        3,
        "herr",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Division 1 Herr Mellersta",
        3,
        "herr",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Division 1 Herr Östra",
        3,
        "herr",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Division 1 Herr Västra Götaland",
        3,
        "herr",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Division 1 Herr Södra Svealand",
        3,
        "herr",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
    serie(
        "Division 1 Herr Södra Götaland",
        3,
        "herr",
        "Svenska Innebandyförbundet",
        source_type="national",
    ),
]


# ============================================================
# DISTRIKT
# ============================================================
#
# Serienamnen nedan beskriver strukturen vi vill stödja.
# Exakta serie-ID:n och publika matchkällor kopplas på separat.
# ============================================================

DISTRICTS = {
    "Stockholm": {
        "slug": "stockholm",
        "series": [
            ("Division 1 Dam Stockholm", 3, "dam"),
            ("Division 2 Dam Stockholm", 4, "dam"),
            ("Division 3 Dam Stockholm", 5, "dam"),
            ("Division 2 Herr Stockholm", 4, "herr"),
            ("Division 3 Herr Stockholm", 5, "herr"),
            ("Division 4 Herr Stockholm", 6, "herr"),
            ("Division 5 Herr Stockholm", 7, "herr"),
        ],
    },

    "Uppland": {
        "slug": "uppland",
        "series": [
            ("Division 1 Dam Uppland/GUD", 3, "dam"),
            ("Division 2 Dam Uppland", 4, "dam"),
            ("Division 3 Dam Uppland", 5, "dam"),
            ("Division 2 Herr Uppland/GUD", 4, "herr"),
            ("Division 3 Herr Uppland", 5, "herr"),
            ("Division 4 Herr Uppland", 6, "herr"),
        ],
    },

    "Småland-Blekinge": {
        "slug": "smaland-blekinge",
        "series": [
            ("Division 1 Dam Småland-Blekinge", 3, "dam"),
            ("Division 2 Dam Småland-Blekinge", 4, "dam"),
            ("Division 2 Herr Småland-Blekinge", 4, "herr"),
            ("Division 3 Herr Småland-Blekinge", 5, "herr"),
            ("Division 4 Herr Småland-Blekinge", 6, "herr"),
            ("Division 5 Herr Småland-Blekinge", 7, "herr"),
        ],
    },

    "Västsvenska": {
        "slug": "vastsvenska",
        "series": [
            ("Division 2 Dam Västsvenska", 4, "dam"),
            ("Division 3 Dam Västsvenska", 5, "dam"),
            ("Division 2 Herr Västsvenska", 4, "herr"),
            ("Division 3 Herr Västsvenska", 5, "herr"),
            ("Division 4 Herr Västsvenska", 6, "herr"),
        ],
    },

    "Skåne": {
        "slug": "skane",
        "series": [
            ("Division 1 Dam Skåne", 3, "dam"),
            ("Division 2 Dam Skåne", 4, "dam"),
            ("Division 2 Herr Skåne", 4, "herr"),
            ("Division 3 Herr Skåne", 5, "herr"),
            ("Division 4 Herr Skåne", 6, "herr"),
        ],
    },

    "Halland": {
        "slug": "halland",
        "series": [
            ("Division 2 Dam Halland", 4, "dam"),
            ("Division 2 Herr Halland", 4, "herr"),
            ("Division 3 Herr Halland", 5, "herr"),
        ],
    },

    "Östergötland": {
        "slug": "ostergotland",
        "series": [
            ("Division 1 Dam Östergötland", 3, "dam"),
            ("Division 2 Dam Östergötland", 4, "dam"),
            ("Division 2 Herr Östergötland", 4, "herr"),
            ("Division 3 Herr Östergötland", 5, "herr"),
            ("Division 4 Herr Östergötland", 6, "herr"),
        ],
    },

    "Värmland": {
        "slug": "varmland",
        "series": [
            ("Division 1 Dam Värmland", 3, "dam"),
            ("Division 2 Dam Värmland", 4, "dam"),
            ("Division 2 Herr Värmland", 4, "herr"),
            ("Division 3 Herr Värmland", 5, "herr"),
            ("Division 4 Herr Värmland", 6, "herr"),
        ],
    },

    "Västmanland-Örebro": {
        "slug": "vastmanland-orebro",
        "series": [
            ("Division 1 Dam Västmanland-Örebro", 3, "dam"),
            ("Division 2 Dam Västmanland-Örebro", 4, "dam"),
            ("Division 2 Herr Västmanland-Örebro", 4, "herr"),
            ("Division 3 Herr Västmanland-Örebro", 5, "herr"),
            ("Division 4 Herr Västmanland-Örebro", 6, "herr"),
        ],
    },

    "Dalarna-Gävleborg": {
        "slug": "dalarna-gavleborg",
        "series": [
            ("Division 1 Dam Dalarna-Gävleborg", 3, "dam"),
            ("Division 2 Dam Dalarna-Gävleborg", 4, "dam"),
            ("Division 2 Herr Dalarna-Gävleborg", 4, "herr"),
            ("Division 3 Herr Dalarna-Gävleborg", 5, "herr"),
            ("Division 4 Herr Dalarna-Gävleborg", 6, "herr"),
        ],
    },

    "Västerbotten": {
        "slug": "vasterbotten",
        "series": [
            ("Division 1 Dam Västerbotten", 3, "dam"),
            ("Division 2 Herr Västerbotten", 4, "herr"),
            ("Division 3 Herr Västerbotten", 5, "herr"),
        ],
    },

    "Norrbotten": {
        "slug": "norrbotten",
        "series": [
            ("Division 1 Dam Norrbotten", 3, "dam"),
            ("Division 2 Herr Norrbotten", 4, "herr"),
            ("Division 3 Herr Norrbotten", 5, "herr"),
        ],
    },

    "Jämtland-Härjedalen": {
        "slug": "jamtland-harjedalen",
        "series": [
            ("Division 1 Dam Jämtland-Härjedalen", 3, "dam"),
            ("Division 2 Herr Jämtland-Härjedalen", 4, "herr"),
            ("Division 3 Herr Jämtland-Härjedalen", 5, "herr"),
        ],
    },
}


def district_series():
    result = []

    for district_name, district in DISTRICTS.items():
        for name, level, gender in district["series"]:
            result.append(
                serie(
                    name=name,
                    level=level,
                    gender=gender,
                    organiser=f"{district_name} Innebandyförbund",
                    district=district_name,
                    source_type="district",
                )
            )

    return result


def all_series():
    return (
        NATIONAL_SERIES
        + district_series()
    )


def active_series():
    return [
        item
        for item in all_series()
        if item.get("active", True)
    ]


def summary():
    series = active_series()

    national = [
        item
        for item in series
        if item["district"] is None
    ]

    district = [
        item
        for item in series
        if item["district"] is not None
    ]

    men = [
        item
        for item in series
        if item["gender"] == "herr"
    ]

    women = [
        item
        for item in series
        if item["gender"] == "dam"
    ]

    return {
        "total": len(series),
        "national": len(national),
        "district": len(district),
        "men": len(men),
        "women": len(women),
        "district_count": len(DISTRICTS),
    }


def main():
    info = summary()

    print()
    print("=============================================")
    print(" EVENTFINDER - SENIORINNEBANDY SERIEKATALOG")
    print("=============================================")
    print()

    print(f"Säsong: {SEASON}")
    print(f"Serier totalt: {info['total']}")
    print(f"Nationella serier: {info['national']}")
    print(f"Distriktsserier: {info['district']}")
    print(f"Damserier: {info['women']}")
    print(f"Herrserier: {info['men']}")
    print(f"Distrikt: {info['district_count']}")

    print()
    print("Distrikt")
    print("--------")

    for district_name, district in DISTRICTS.items():
        print(
            f"{district_name}: "
            f"{len(district['series'])} seniorserier"
        )


if __name__ == "__main__":
    main()

