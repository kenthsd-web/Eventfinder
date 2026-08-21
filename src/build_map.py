import json
from html import escape
from pathlib import Path


# ============================================================
# EVENTFINDER - INTERAKTIV EVENTKARTA
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

EVENT_FILE = DATA_DIR / "events.json"
MAP_FILE = OUTPUT_DIR / "eventfinder_map.html"


# ============================================================
# DATA
# ============================================================

def load_events():
    if not EVENT_FILE.exists():
        raise FileNotFoundError(
            f"Saknar {EVENT_FILE}"
        )

    data = json.loads(
        EVENT_FILE.read_text(
            encoding="utf-8"
        )
    )

    if not isinstance(data, list):
        raise ValueError(
            "events.json innehåller inte en lista."
        )

    return data


# ============================================================
# FILTRERING
# ============================================================

def map_events(events):
    result = []

    for event in events:
        if event.get("lat") is None:
            continue

        if event.get("lon") is None:
            continue

        result.append(event)

    return result


# ============================================================
# POPUP
# ============================================================

def popup_html(event):
    namn = escape(
        event.get(
            "namn",
            "Event",
        )
    )

    serie = escape(
        event.get(
            "serie",
            "",
        )
    )

    datum = escape(
        event.get(
            "datum",
            "",
        )
    )

    tid = escape(
        event.get(
            "tid",
            "",
        )
        or "Tid ej angiven"
    )

    arena = escape(
        event.get(
            "arena",
            "",
        )
        or event.get(
            "plats",
            "",
        )
        or "Arena ej angiven"
    )

    kommun = escape(
        event.get(
            "kommun",
            "",
        )
        or ""
    )

    sport = escape(
        event.get(
            "sport",
            "",
        )
    )

    source_url = event.get(
        "ssl_schedule_url"
    ) or event.get(
        "url"
    ) or ""

    source_link = ""

    if source_url:
        safe_url = escape(
            source_url,
            quote=True,
        )

        source_link = (
            f'<div class="popup-source">'
            f'<a href="{safe_url}" '
            f'target="_blank" '
            f'rel="noopener noreferrer">'
            f'Öppna källa'
            f'</a>'
            f'</div>'
        )

    return f"""
    <div class="event-popup">
        <div class="popup-sport">{sport}</div>
        <h3>{namn}</h3>
        <div><strong>Serie:</strong> {serie}</div>
        <div><strong>Datum:</strong> {datum}</div>
        <div><strong>Tid:</strong> {tid}</div>
        <div><strong>Arena:</strong> {arena}</div>
        <div><strong>Kommun:</strong> {kommun}</div>
        {source_link}
    </div>
    """


# ============================================================
# JAVASCRIPT-DATA
# ============================================================

def build_js_events(events):
    output = []

    for event in events:
        output.append(
            {
                "id": event.get(
                    "id",
                    "",
                ),
                "lat": event["lat"],
                "lon": event["lon"],
                "namn": event.get(
                    "namn",
                    "",
                ),
                "sport": event.get(
                    "sport",
                    "",
                ),
                "serie": event.get(
                    "serie",
                    "",
                ),
                "datum": event.get(
                    "datum",
                    "",
                ),
                "tid": event.get(
                    "tid",
                    "",
                ),
                "arena": (
                    event.get(
                        "arena"
                    )
                    or event.get(
                        "plats"
                    )
                    or ""
                ),
                "kommun": event.get(
                    "kommun",
                    "",
                ),
                "popup": popup_html(
                    event
                ),
            }
        )

    return json.dumps(
        output,
        ensure_ascii=False,
    )


# ============================================================
# HTML
# ============================================================

def build_html(events):
    js_events = build_js_events(
        events
    )

    total = len(events)

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >

    <title>Eventfinder</title>

    <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    >

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            font-family:
                Arial,
                Helvetica,
                sans-serif;
            background: #f5f5f5;
            color: #202020;
        }}

        .app {{
            display: flex;
            flex-direction: column;
            height: 100vh;
        }}

        header {{
            background: white;
            padding: 14px 18px;
            border-bottom: 1px solid #ddd;
        }}

        header h1 {{
            margin: 0;
            font-size: 24px;
        }}

        header p {{
            margin: 5px 0 0;
            color: #666;
        }}

        .controls {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            padding: 10px 18px;
            background: white;
            border-bottom: 1px solid #ddd;
        }}

        .controls input,
        .controls select {{
            min-height: 38px;
            padding: 8px 10px;
            border: 1px solid #bbb;
            border-radius: 6px;
            background: white;
        }}

        .controls input {{
            min-width: 220px;
            flex: 1;
        }}

        .counter {{
            display: flex;
            align-items: center;
            padding: 0 8px;
            color: #555;
        }}

        #map {{
            flex: 1;
            width: 100%;
        }}

        .event-popup {{
            min-width: 220px;
            line-height: 1.45;
        }}

        .event-popup h3 {{
            margin:
                4px
                0
                10px;
            font-size: 17px;
        }}

        .popup-sport {{
            font-size: 12px;
            text-transform: uppercase;
            color: #666;
        }}

        .popup-source {{
            margin-top: 10px;
        }}

        .popup-source a {{
            font-weight: bold;
        }}

        .leaflet-popup-content {{
            margin:
                14px
                16px;
        }}

        @media (max-width: 650px) {{
            header h1 {{
                font-size: 20px;
            }}

            .controls {{
                padding: 8px;
            }}

            .controls input,
            .controls select {{
                width: 100%;
                min-width: 0;
            }}
        }}
    </style>
</head>

<body>

<div class="app">

    <header>
        <h1>Eventfinder</h1>
        <p>
            Sportevent på karta ·
            {total} event med koordinater
        </p>
    </header>

    <div class="controls">

        <input
            id="search"
            type="search"
            placeholder="Sök lag, arena eller kommun..."
        >

        <select id="seriesFilter">
            <option value="">
                Alla serier
            </option>
        </select>

        <select id="monthFilter">
            <option value="">
                Alla månader
            </option>
        </select>

        <div
            id="counter"
            class="counter"
        >
        </div>

    </div>

    <div id="map"></div>

</div>


<script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js">
</script>

<script>
    const events = {js_events};

    const map = L.map(
        "map"
    ).setView(
        [62.0, 15.0],
        5
    );

    L.tileLayer(
        "https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png",
        {{
            maxZoom: 19,
            attribution:
                '&copy; OpenStreetMap contributors'
        }}
    ).addTo(map);


    const markerLayer = L.layerGroup().addTo(
        map
    );

    const searchInput = document.getElementById(
        "search"
    );

    const seriesFilter = document.getElementById(
        "seriesFilter"
    );

    const monthFilter = document.getElementById(
        "monthFilter"
    );

    const counter = document.getElementById(
        "counter"
    );


    function populateFilters() {{
        const series = [
            ...new Set(
                events
                    .map(
                        event => event.serie
                    )
                    .filter(Boolean)
            )
        ].sort();

        series.forEach(
            serie => {{
                const option = document.createElement(
                    "option"
                );

                option.value = serie;
                option.textContent = serie;

                seriesFilter.appendChild(
                    option
                );
            }}
        );


        const months = [
            ...new Set(
                events
                    .map(
                        event =>
                            event.datum
                                ? event.datum.substring(
                                    0,
                                    7
                                )
                                : ""
                    )
                    .filter(Boolean)
            )
        ].sort();

        months.forEach(
            month => {{
                const option = document.createElement(
                    "option"
                );

                option.value = month;
                option.textContent = month;

                monthFilter.appendChild(
                    option
                );
            }}
        );
    }}


    function searchableText(event) {{
        return [
            event.namn,
            event.sport,
            event.serie,
            event.arena,
            event.kommun
        ]
            .join(" ")
            .toLowerCase();
    }}


    function filteredEvents() {{
        const search = (
            searchInput.value
            || ""
        )
            .trim()
            .toLowerCase();

        const serie = (
            seriesFilter.value
            || ""
        );

        const month = (
            monthFilter.value
            || ""
        );

        return events.filter(
            event => {{
                if (
                    search
                    && !searchableText(
                        event
                    ).includes(
                        search
                    )
                ) {{
                    return false;
                }}

                if (
                    serie
                    && event.serie !== serie
                ) {{
                    return false;
                }}

                if (
                    month
                    && !event.datum.startsWith(
                        month
                    )
                ) {{
                    return false;
                }}

                return true;
            }}
        );
    }}


    function renderMarkers() {{
        markerLayer.clearLayers();

        const visible = filteredEvents();

        visible.forEach(
            event => {{
                const marker = L.marker(
                    [
                        event.lat,
                        event.lon
                    ]
                );

                marker.bindPopup(
                    event.popup
                );

                marker.addTo(
                    markerLayer
                );
            }}
        );

        counter.textContent =
            visible.length
            + " event";

        if (
            visible.length > 0
        ) {{
            const bounds = L.latLngBounds(
                visible.map(
                    event => [
                        event.lat,
                        event.lon
                    ]
                )
            );

            if (
                bounds.isValid()
            ) {{
                map.fitBounds(
                    bounds,
                    {{
                        padding: [
                            25,
                            25
                        ],
                        maxZoom: 11
                    }}
                );
            }}
        }}
    }}


    searchInput.addEventListener(
        "input",
        renderMarkers
    );

    seriesFilter.addEventListener(
        "change",
        renderMarkers
    );

    monthFilter.addEventListener(
        "change",
        renderMarkers
    );


    populateFilters();
    renderMarkers();
</script>

</body>
</html>
"""


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print(
        "============================================="
    )
    print(
        " EVENTFINDER - BYGGER KARTA"
    )
    print(
        "============================================="
    )

    events = load_events()

    mapped = map_events(
        events
    )

    print()
    print(
        f"Totalt event: "
        f"{len(events)}"
    )

    print(
        f"Event med koordinater: "
        f"{len(mapped)}"
    )

    if not mapped:
        print()
        print(
            "Inga event kan visas på karta ännu."
        )
        return

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    html = build_html(
        mapped
    )

    MAP_FILE.write_text(
        html,
        encoding="utf-8",
    )

    print()
    print(
        "Kartan skapad:"
    )

    print(
        MAP_FILE
    )

    print()
    print(
        "Öppna filen i Chrome för att testa kartan."
    )


if __name__ == "__main__":
    main()
