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


def map_events(events):
    return [
        event
        for event in events
        if event.get("lat") is not None
        and event.get("lon") is not None
        and event.get("datum")
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

    return f"""
    <div class="event-popup">
        <div class="popup-sport">{sport}</div>
        <h3>{namn}</h3>
        <div><strong>Serie:</strong> {serie}</div>
        <div><strong>Datum:</strong> {datum}</div>
        <div><strong>Tid:</strong> {tid}</div>
        <div><strong>Arena:</strong> {arena}</div>
        <div><strong>Kommun:</strong> {kommun}</div>
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
        .controls select,
        .controls button {{
            min-height: 40px;
            padding: 8px 10px;
            border: 1px solid #bbb;
            border-radius: 7px;
            background: white;
            font-size: 14px;
        }}

        .controls input[type="search"] {{
            min-width: 230px;
            flex: 1;
        }}

        .date-buttons {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            width: 100%;
        }}

        .date-buttons button {{
            cursor: pointer;
        }}

        .date-buttons button.active {{
            background: #222;
            color: white;
            border-color: #222;
        }}

        .date-range {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
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

        .arena-popup {{
            min-width: 260px;
            max-height: 320px;
            overflow-y: auto;
        }}

        .arena-popup h3 {{
            margin: 0 0 8px;
        }}

        .arena-popup-count {{
            color: #666;
            font-size: 13px;
            margin-bottom: 10px;
        }}

        .arena-popup-event {{
            padding: 8px 0;
            border-top: 1px solid #eee;
        }}

        .arena-popup-event:first-of-type {{
            border-top: none;
        }}

        .arena-popup-date {{
            font-size: 12px;
            color: #666;
        }}

        .arena-popup-title {{
            font-weight: bold;
            margin-top: 2px;
        }}

        .arena-marker {{
            background: #202020;
            color: white;
            border-radius: 50%;
            min-width: 32px;
            height: 32px;
            padding: 0 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            border: 2px solid white;
            box-shadow:
                0 1px 5px rgba(0, 0, 0, 0.35);
        }}

        .empty {{
            padding: 20px;
            color: #666;
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
    </style>
</head>

<body>

<div class="app">

    <header>
        <h1>Eventfinder</h1>
        <p>
            Hitta event efter plats och dag ·
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

        <div
            id="counter"
            class="counter"
        ></div>

        <div class="date-buttons">
            <button
                type="button"
                data-period="all"
                class="active"
            >
                Alla datum
            </button>

            <button
                type="button"
                data-period="today"
            >
                Idag
            </button>

            <button
                type="button"
                data-period="tomorrow"
            >
                Imorgon
            </button>

            <button
                type="button"
                data-period="weekend"
            >
                Helgen
            </button>

            <button
                type="button"
                data-period="7days"
            >
                Nästa 7 dagar
            </button>
        </div>

        <div class="date-range">
            <label>Från</label>
            <input
                id="dateFrom"
                type="date"
            >

            <label>Till</label>
            <input
                id="dateTo"
                type="date"
            >

            <button
                id="clearDates"
                type="button"
            >
                Rensa datum
            </button>
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

    const markersByEventId =
        new Map();

    const searchInput =
        document.getElementById(
            "search"
        );

    const seriesFilter =
        document.getElementById(
            "seriesFilter"
        );

    const counter =
        document.getElementById(
            "counter"
        );

    const eventList =
        document.getElementById(
            "eventList"
        );

    const dateFrom =
        document.getElementById(
            "dateFrom"
        );

    const dateTo =
        document.getElementById(
            "dateTo"
        );

    const clearDates =
        document.getElementById(
            "clearDates"
        );

    const periodButtons =
        document.querySelectorAll(
            "[data-period]"
        );


    function localDateString(date) {{
        const year =
            date.getFullYear();

        const month =
            String(
                date.getMonth() + 1
            ).padStart(
                2,
                "0"
            );

        const day =
            String(
                date.getDate()
            ).padStart(
                2,
                "0"
            );

        return `${{year}}-${{month}}-${{day}}`;
    }}


    function addDays(date, days) {{
        const copy =
            new Date(date);

        copy.setDate(
            copy.getDate() + days
        );

        return copy;
    }}


    function setPeriodButton(period) {{
        periodButtons.forEach(
            button => {{
                button.classList.toggle(
                    "active",
                    button.dataset.period
                    === period
                );
            }}
        );
    }}


    function applyPeriod(period) {{
        const today = new Date();

        today.setHours(
            0,
            0,
            0,
            0
        );

        if (period === "all") {{
            dateFrom.value = "";
            dateTo.value = "";
        }}

        if (period === "today") {{
            const value =
                localDateString(
                    today
                );

            dateFrom.value = value;
            dateTo.value = value;
        }}

        if (period === "tomorrow") {{
            const tomorrow =
                addDays(
                    today,
                    1
                );

            const value =
                localDateString(
                    tomorrow
                );

            dateFrom.value = value;
            dateTo.value = value;
        }}

        if (period === "7days") {{
            dateFrom.value =
                localDateString(
                    today
                );

            dateTo.value =
                localDateString(
                    addDays(
                        today,
                        6
                    )
                );
        }}

        if (period === "weekend") {{
            const day =
                today.getDay();

            let daysUntilSaturday =
                (6 - day + 7) % 7;

            if (day === 0) {{
                daysUntilSaturday = -1;
            }}

            const saturday =
                addDays(
                    today,
                    daysUntilSaturday
                );

            const sunday =
                addDays(
                    saturday,
                    1
                );

            dateFrom.value =
                localDateString(
                    saturday
                );

            dateTo.value =
                localDateString(
                    sunday
                );
        }}

        setPeriodButton(
            period
        );

        render();
    }}


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

                option.value =
                    serie;

                option.textContent =
                    serie;

                seriesFilter.appendChild(
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

        const from =
            dateFrom.value
            || "";

        const to =
            dateTo.value
            || "";

        return events
            .filter(
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
                        && event.serie
                        !== serie
                    ) {{
                        return false;
                    }}

                    if (
                        from
                        && event.datum
                        < from
                    ) {{
                        return false;
                    }}

                    if (
                        to
                        && event.datum
                        > to
                    ) {{
                        return false;
                    }}

                    return true;
                }}
            )
            .sort(
                (a, b) => {{
                    const aKey =
                        `${{a.datum}} ${{a.tid || "23:59"}}`;

                    const bKey =
                        `${{b.datum}} ${{b.tid || "23:59"}}`;

                    return aKey.localeCompare(
                        bKey
                    );
                }}
            );
    }}


    function groupByLocation(visible) {{
        const groups = new Map();

        visible.forEach(
            event => {{
                const key =
                    `${{event.lat.toFixed(6)}},${{event.lon.toFixed(6)}}`;

                if (!groups.has(key)) {{
                    groups.set(
                        key,
                        []
                    );
                }}

                groups.get(
                    key
                ).push(
                    event
                );
            }}
        );

        return groups;
    }}


    function groupPopup(eventsAtLocation) {{
        const first =
            eventsAtLocation[0];

        const arena =
            first.arena
            || first.kommun
            || "Plats";

        const rows =
            eventsAtLocation
                .map(
                    event => {{
                        const time =
                            event.tid
                            ? " · " + event.tid
                            : "";

                        return `
                            <div class="arena-popup-event">
                                <div class="arena-popup-date">
                                    ${{event.datum}}${{time}}
                                </div>
                                <div class="arena-popup-title">
                                    ${{event.namn}}
                                </div>
                                <div>
                                    ${{event.serie || ""}}
                                </div>
                            </div>
                        `;
                    }}
                )
                .join("");

        return `
            <div class="arena-popup">
                <h3>${{arena}}</h3>
                <div class="arena-popup-count">
                    ${{eventsAtLocation.length}} event
                </div>
                ${{rows}}
            </div>
        `;
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
            markersByEventId.get(
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

            empty.className =
                "empty";

            empty.textContent =
                "Inga event matchar dina filter.";

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


    function renderMarkers(visible) {{
        markerLayer.clearLayers();
        markersByEventId.clear();

        const groups =
            groupByLocation(
                visible
            );

        groups.forEach(
            eventsAtLocation => {{
                const first =
                    eventsAtLocation[0];

                const count =
                    eventsAtLocation.length;

                const icon =
                    L.divIcon(
                        {{
                            className: "",
                            html:
                                `<div class="arena-marker">${{count}}</div>`,
                            iconSize: [
                                36,
                                36
                            ],
                            iconAnchor: [
                                18,
                                18
                            ]
                        }}
                    );

                const marker =
                    L.marker(
                        [
                            first.lat,
                            first.lon
                        ],
                        {{
                            icon: icon
                        }}
                    );

                marker.bindPopup(
                    groupPopup(
                        eventsAtLocation
                    )
                );

                marker.addTo(
                    markerLayer
                );

                eventsAtLocation.forEach(
                    event => {{
                        markersByEventId.set(
                            event.id,
                            marker
                        );
                    }}
                );
            }}
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


    function render() {{
        const visible =
            filteredEvents();

        counter.textContent =
            visible.length
            + " event";

        renderMarkers(
            visible
        );

        renderList(
            visible
        );
    }}


    searchInput.addEventListener(
        "input",
        render
    );

    seriesFilter.addEventListener(
        "change",
        render
    );

    dateFrom.addEventListener(
        "change",
        () => {{
            setPeriodButton("");
            render();
        }}
    );

    dateTo.addEventListener(
        "change",
        () => {{
            setPeriodButton("");
            render();
        }}
    );

    clearDates.addEventListener(
        "click",
        () => {{
            dateFrom.value = "";
            dateTo.value = "";
            setPeriodButton(
                "all"
            );
            render();
        }}
    );

    periodButtons.forEach(
        button => {{
            button.addEventListener(
                "click",
                () => applyPeriod(
                    button.dataset.period
                )
            );
        }}
    );


    populateFilters();
    render();
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
        " EVENTFINDER - KARTA MED ARENAGRUPPERING"
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
