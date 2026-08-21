import json
from html import escape
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

EVENT_FILE = DATA_DIR / "events.json"
MAP_FILE = OUTPUT_DIR / "eventfinder_map.html"


def load_events():
    if not EVENT_FILE.exists():
        raise FileNotFoundError(f"Saknar {EVENT_FILE}")

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


def map_events(events):
    return [
        event
        for event in events
        if event.get("lat") is not None
        and event.get("lon") is not None
    ]


def popup_html(event):
    namn = escape(
        event.get("namn", "Event")
    )

    serie = escape(
        event.get("serie", "")
    )

    datum = escape(
        event.get("datum", "")
    )

    tid = escape(
        event.get("tid", "")
        or "Tid ej angiven"
    )

    arena = escape(
        event.get("arena", "")
        or event.get("plats", "")
        or "Arena ej angiven"
    )

    kommun = escape(
        event.get("kommun", "")
        or ""
    )

    sport = escape(
        event.get("sport", "")
    )

    source_url = (
        event.get("ssl_schedule_url")
        or event.get("url")
        or ""
    )

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


def build_js_events(events):
    output = []

    for event in events:
        output.append(
            {
                "id": event.get("id", ""),
                "lat": event["lat"],
                "lon": event["lon"],
                "namn": event.get("namn", ""),
                "sport": event.get("sport", ""),
                "serie": event.get("serie", ""),
                "datum": event.get("datum", ""),
                "tid": event.get("tid", ""),
                "arena": (
                    event.get("arena")
                    or event.get("plats")
                    or ""
                ),
                "kommun": event.get(
                    "kommun",
                    "",
                ),
                "hemmalag": event.get(
                    "hemmalag",
                    "",
                ),
                "bortalag": event.get(
                    "bortalag",
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

        html,
        body {{
            margin: 0;
            height: 100%;
            font-family:
                Arial,
                Helvetica,
                sans-serif;
            background: #f5f5f5;
            color: #202020;
        }}

        .app {{
            height: 100vh;
            display: flex;
            flex-direction: column;
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
            min-height: 40px;
            padding: 8px 10px;
            border: 1px solid #bbb;
            border-radius: 7px;
            background: white;
            font-size: 14px;
        }}

        .controls input {{
            min-width: 250px;
            flex: 1;
        }}

        .counter {{
            display: flex;
            align-items: center;
            padding: 0 8px;
            color: #555;
            font-weight: bold;
        }}

        .main {{
            flex: 1;
            min-height: 0;
            display: grid;
            grid-template-columns:
                minmax(0, 2fr)
                minmax(320px, 1fr);
        }}

        #map {{
            width: 100%;
            height: 100%;
            min-height: 0;
        }}

        .sidebar {{
            background: white;
            border-left: 1px solid #ddd;
            min-height: 0;
            display: flex;
            flex-direction: column;
        }}

        .sidebar-header {{
            padding: 14px;
            border-bottom: 1px solid #ddd;
        }}

        .sidebar-header h2 {{
            margin: 0;
            font-size: 18px;
        }}

        #eventList {{
            overflow-y: auto;
            flex: 1;
        }}

        .event-card {{
            padding: 14px;
            border-bottom: 1px solid #eee;
            cursor: pointer;
            background: white;
            transition:
                background 0.15s ease,
                transform 0.15s ease;
        }}

        .event-card:hover {{
            background: #f7f7f7;
        }}

        .event-card.active {{
            background: #eef5ff;
        }}

        .event-date {{
            font-size: 13px;
            color: #666;
            margin-bottom: 5px;
        }}

        .event-title {{
            font-weight: bold;
            font-size: 16px;
            margin-bottom: 5px;
        }}

        .event-meta {{
            font-size: 13px;
            line-height: 1.45;
            color: #555;
        }}

        .event-series {{
            display: inline-block;
            font-size: 11px;
            text-transform: uppercase;
            margin-bottom: 6px;
            color: #666;
        }}

        .empty {{
            padding: 20px;
            color: #666;
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

        .leaflet-popup-content {{
            margin: 14px 16px;
        }}

        @media (max-width: 900px) {{
            .main {{
                grid-template-columns: 1fr;
                grid-template-rows:
                    minmax(340px, 55vh)
                    minmax(240px, 1fr);
            }}

            .sidebar {{
                border-left: none;
                border-top: 1px solid #ddd;
            }}
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

            .main {{
                grid-template-rows:
                    50vh
                    1fr;
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

    <div class="main">

        <div id="map"></div>

        <aside class="sidebar">

            <div class="sidebar-header">
                <h2>Event</h2>
            </div>

            <div id="eventList"></div>

        </aside>

    </div>

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


    const markerLayer =
        L.layerGroup().addTo(
            map
        );

    const markersById = new Map();

    const searchInput =
        document.getElementById(
            "search"
        );

    const seriesFilter =
        document.getElementById(
            "seriesFilter"
        );

    const monthFilter =
        document.getElementById(
            "monthFilter"
        );

    const counter =
        document.getElementById(
            "counter"
        );

    const eventList =
        document.getElementById(
            "eventList"
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
                const option =
                    document.createElement(
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
                const option =
                    document.createElement(
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
            event.kommun,
            event.hemmalag,
            event.bortalag
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

        const serie =
            seriesFilter.value
            || "";

        const month =
            monthFilter.value
            || "";

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


    function clearActiveCards() {{
        document
            .querySelectorAll(
                ".event-card.active"
            )
            .forEach(
                card =>
                    card.classList.remove(
                        "active"
                    )
            );
    }}


    function focusEvent(event) {{
        const marker =
            markersById.get(
                event.id
            );

        if (!marker) {{
            return;
        }}

        map.setView(
            [
                event.lat,
                event.lon
            ],
            14,
            {{
                animate: true
            }}
        );

        marker.openPopup();

        clearActiveCards();

        const card =
            document.querySelector(
                `[data-event-id="${{event.id}}"]`
            );

        if (card) {{
            card.classList.add(
                "active"
            );
        }}
    }}


    function renderList(visible) {{
        eventList.innerHTML = "";

        if (
            visible.length === 0
        ) {{
            const empty =
                document.createElement(
                    "div"
                );

            empty.className = "empty";
            empty.textContent =
                "Inga event matchar filtren.";

            eventList.appendChild(
                empty
            );

            return;
        }}

        visible.forEach(
            event => {{
                const card =
                    document.createElement(
                        "div"
                    );

                card.className =
                    "event-card";

                card.dataset.eventId =
                    event.id;

                const dateText =
                    event.datum
                    + (
                        event.tid
                        ? " · " + event.tid
                        : ""
                    );

                card.innerHTML = `
                    <div class="event-series">
                        ${{event.serie || ""}}
                    </div>

                    <div class="event-date">
                        ${{dateText}}
                    </div>

                    <div class="event-title">
                        ${{event.namn}}
                    </div>

                    <div class="event-meta">
                        ${{event.arena || "Arena ej angiven"}}
                        ${{event.kommun ? " · " + event.kommun : ""}}
                    </div>
                `;

                card.addEventListener(
                    "click",
                    () => focusEvent(
                        event
                    )
                );

                eventList.appendChild(
                    card
                );
            }}
        );
    }}


    function renderMarkers() {{
        markerLayer.clearLayers();
        markersById.clear();

        const visible =
            filteredEvents();

        visible.forEach(
            event => {{
                const marker =
                    L.marker(
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

                markersById.set(
                    event.id,
                    marker
                );
            }}
        );

        counter.textContent =
            visible.length
            + " event";

        renderList(
            visible
        );

        if (
            visible.length > 0
        ) {{
            const bounds =
                L.latLngBounds(
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


def main():
    print()
    print(
        "============================================="
    )
    print(
        " EVENTFINDER - BYGGER KARTA + EVENTLISTA"
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
            "Inga event kan visas ännu."
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


if __name__ == "__main__":
    main()
