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

    precision = event.get(
        "location_precision",
        ""
    )

    if precision == "city":
        position_info = (
            '<div><strong>Position:</strong> '
            'Ungefärlig – placerad på orten</div>'
        )
    else:
        position_info = ""

    return f"""
    <div class="event-popup">
        <div class="popup-sport">{sport}</div>
        <h3>{namn}</h3>
        <div><strong>Serie:</strong> {serie}</div>
        <div><strong>Datum:</strong> {datum}</div>
        <div><strong>Tid:</strong> {tid}</div>
        <div><strong>Arena:</strong> {arena}</div>
        <div><strong>Kommun:</strong> {kommun}</div>
        {position_info}
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
                "typ": event.get("typ", ""),
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
                "location_precision": event.get(
                    "location_precision",
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

.controls button {{
    cursor: pointer;
}}

.search-input {{
    min-width: 220px;
    flex: 1;
}}

.location-panel {{
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
}}

.location-panel input {{
    min-width: 220px;
}}

.location-status {{
    color: #555;
    font-size: 13px;
}}

.date-buttons {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    width: 100%;
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

.event-distance {{
    margin-top: 5px;
    font-size: 12px;
    font-weight: bold;
    color: #333;
}}

.event-series {{
    display: inline-block;
    font-size: 11px;
    text-transform: uppercase;
    margin-bottom: 6px;
    color: #666;
}}

.arena-popup {{
    min-width: 270px;
    max-height: 330px;
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
    min-width: 34px;
    height: 34px;
    padding: 0 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    border: 2px solid white;
    box-shadow:
        0 1px 5px rgba(0, 0, 0, 0.35);
}}

.location-marker {{
    width: 18px;
    height: 18px;
    background: #1976d2;
    border: 3px solid white;
    border-radius: 50%;
    box-shadow:
        0 1px 5px rgba(0, 0, 0, 0.4);
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

    .location-panel {{
        width: 100%;
    }}

    .location-panel input,
    .location-panel select,
    .location-panel button {{
        flex: 1;
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
        Var? · När? · Vad? ·
        {total} event med koordinater
    </p>

</header>


<div class="controls">

    <input
        id="search"
        class="search-input"
        type="search"
        placeholder="Sök lag, arena eller kommun..."
    >

    <select id="typeFilter">
        <option value="">
            Alla eventtyper
        </option>
    </select>

    <select id="seriesFilter">

        <option value="">
            Alla serier
        </option>

    </select>

    <div
        id="counter"
        class="counter"
    ></div>


    <div class="location-panel">

        <strong>📍 Plats:</strong>

        <input
            id="locationSearch"
            type="search"
            placeholder="Exempel: Växjö eller Stockholm"
        >

        <button
            id="findLocation"
            type="button"
        >
            Sök plats
        </button>

        <button
            id="useMyLocation"
            type="button"
        >
            Min position
        </button>

        <select id="radiusFilter">

            <option value="10">
                10 km
            </option>

            <option value="25" selected>
                25 km
            </option>

            <option value="50">
                50 km
            </option>

            <option value="100">
                100 km
            </option>

            <option value="250">
                250 km
            </option>

        </select>

        <button
            id="clearLocation"
            type="button"
        >
            Rensa plats
        </button>

        <span
            id="locationStatus"
            class="location-status"
        ></span>

    </div>


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


let locationMarker = null;
let radiusCircle = null;


const markersByEventId =
    new Map();


let selectedLocation = null;


const searchInput =
    document.getElementById(
        "search"
    );

const typeFilter =
    document.getElementById(
        "typeFilter"
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


const locationSearch =
    document.getElementById(
        "locationSearch"
    );

const findLocation =
    document.getElementById(
        "findLocation"
    );

const useMyLocation =
    document.getElementById(
        "useMyLocation"
    );

const radiusFilter =
    document.getElementById(
        "radiusFilter"
    );

const clearLocation =
    document.getElementById(
        "clearLocation"
    );

const locationStatus =
    document.getElementById(
        "locationStatus"
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


function haversineDistance(
    lat1,
    lon1,
    lat2,
    lon2
) {{

    const earthRadius = 6371;

    const toRadians =
        degrees =>
            degrees * Math.PI / 180;

    const dLat =
        toRadians(
            lat2 - lat1
        );

    const dLon =
        toRadians(
            lon2 - lon1
        );

    const a =
        Math.sin(
            dLat / 2
        ) ** 2
        +
        Math.cos(
            toRadians(lat1)
        )
        *
        Math.cos(
            toRadians(lat2)
        )
        *
        Math.sin(
            dLon / 2
        ) ** 2;

    const c =
        2 * Math.atan2(
            Math.sqrt(a),
            Math.sqrt(1 - a)
        );

    return earthRadius * c;
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

    const today =
        new Date();

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

        dateFrom.value =
            value;

        dateTo.value =
            value;

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

        dateFrom.value =
            value;

        dateTo.value =
            value;

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

    const types = [
        ...new Set(
            events
                .map(
                    event =>
                        event.sport
                        || event.typ
                )
                .filter(Boolean)
        )
    ].sort();

    types.forEach(
        type => {{

            const option =
                document.createElement(
                    "option"
                );

            option.value =
                type;

            option.textContent =
                type;

            typeFilter.appendChild(
                option
            );
        }}
    );

    const series = [
        ...new Set(
            events
                .map(
                    event =>
                        event.serie
                )
                .filter(Boolean)
        )
    ].sort(
        (a, b) => {{
            const priority = name => {{
                if (name === "SSL Dam") return 1;
                if (name === "SSL Herr") return 2;
                if (name.startsWith("Allsvenskan")) return 3;
                if (
                    name.startsWith("Division 1 Herr")
                    || name === "Division 1 Damer"
                    || name === "Damer Division 1"
                ) return 4;

                return 10;
            }};

            const pa = priority(a);
            const pb = priority(b);

            if (pa !== pb) {{
                return pa - pb;
            }}

            return a.localeCompare(
                b,
                "sv"
            );
        }}
    );


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


function eventDistance(event) {{

    if (!selectedLocation) {{
        return null;
    }}

    return haversineDistance(
        selectedLocation.lat,
        selectedLocation.lon,
        event.lat,
        event.lon
    );
}}


function filteredEvents() {{

    const search =
        (
            searchInput.value
            || ""
        )
        .trim()
        .toLowerCase();


    const type =
        typeFilter.value
        || "";

    const serie =
        seriesFilter.value
        || "";


    const from =
        dateFrom.value
        || "";


    const to =
        dateTo.value
        || "";


    const radius =
        Number(
            radiusFilter.value
        );


    const visible =
        events.filter(
            event => {{

                if (
                    search
                    &&
                    !searchableText(
                        event
                    ).includes(
                        search
                    )
                ) {{
                    return false;
                }}

                if (
                    type
                    &&
                    (
                        event.sport
                        || event.typ
                    )
                    !== type
                ) {{
                    return false;
                }}


                if (
                    serie
                    &&
                    event.serie
                    !== serie
                ) {{
                    return false;
                }}


                if (
                    from
                    &&
                    event.datum
                    < from
                ) {{
                    return false;
                }}


                if (
                    to
                    &&
                    event.datum
                    > to
                ) {{
                    return false;
                }}


                if (
                    selectedLocation
                ) {{

                    const distance =
                        eventDistance(
                            event
                        );

                    if (
                        distance
                        > radius
                    ) {{
                        return false;
                    }}

                }}


                return true;

            }}
        );


    return visible.sort(
        (a, b) => {{

            if (selectedLocation) {{

                const distanceA =
                    eventDistance(a);

                const distanceB =
                    eventDistance(b);

                if (
                    Math.abs(
                        distanceA
                        - distanceB
                    ) > 0.1
                ) {{
                    return (
                        distanceA
                        - distanceB
                    );
                }}

            }}


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

    const groups =
        new Map();


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


function groupPopup(
    eventsAtLocation
) {{

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


                const distance =
                    eventDistance(
                        event
                    );


                const distanceText =
                    distance !== null
                    ? `<div>${{distance.toFixed(1)}} km bort</div>`
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

                        ${{distanceText}}

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

    eventList.innerHTML =
        "";


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
                +
                (
                    event.tid
                    ? " · " + event.tid
                    : ""
                );


            const distance =
                eventDistance(
                    event
                );


            const distanceHtml =
                distance !== null
                ? `
                    <div class="event-distance">
                        📍 ${{distance.toFixed(1)}} km bort
                    </div>
                `
                : "";


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

                ${{distanceHtml}}

            `;


            card.addEventListener(
                "click",
                () =>
                    focusEvent(
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
}}


function drawSelectedLocation() {{

    if (locationMarker) {{

        map.removeLayer(
            locationMarker
        );

        locationMarker =
            null;

    }}


    if (radiusCircle) {{

        map.removeLayer(
            radiusCircle
        );

        radiusCircle =
            null;

    }}


    if (!selectedLocation) {{
        return;
    }}


    const icon =
        L.divIcon(
            {{
                className: "",

                html:
                    '<div class="location-marker"></div>',

                iconSize: [
                    18,
                    18
                ],

                iconAnchor: [
                    9,
                    9
                ]
            }}
        );


    locationMarker =
        L.marker(
            [
                selectedLocation.lat,
                selectedLocation.lon
            ],
            {{
                icon: icon
            }}
        ).addTo(
            map
        );


    const radiusKm =
        Number(
            radiusFilter.value
        );


    radiusCircle =
        L.circle(
            [
                selectedLocation.lat,
                selectedLocation.lon
            ],
            {{
                radius:
                    radiusKm
                    * 1000,

                fillOpacity:
                    0.05,

                weight:
                    2
            }}
        ).addTo(
            map
        );
}}


function fitVisible(
    visible
) {{

    if (selectedLocation) {{

        const radius =
            Number(
                radiusFilter.value
            );


        map.setView(
            [
                selectedLocation.lat,
                selectedLocation.lon
            ],
            radius <= 10
                ? 11
                : radius <= 25
                    ? 10
                    : radius <= 50
                        ? 9
                        : radius <= 100
                            ? 8
                            : 6
        );


        return;

    }}


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

                    maxZoom:
                        11
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


    drawSelectedLocation();


    fitVisible(
        visible
    );
}}


async function geocodeLocation(
    query
) {{

    const url =
        "https://nominatim.openstreetmap.org/search"
        +
        "?format=jsonv2"
        +
        "&limit=1"
        +
        "&countrycodes=se"
        +
        "&q="
        +
        encodeURIComponent(
            query
        );


    const response =
        await fetch(
            url,
            {{
                headers: {{
                    "Accept-Language":
                        "sv-SE,sv;q=0.9"
                }}
            }}
        );


    if (!response.ok) {{

        throw new Error(
            "Kunde inte söka plats."
        );

    }}


    const data =
        await response.json();


    if (
        !data
        ||
        data.length === 0
    ) {{

        return null;

    }}


    return {{
        lat:
            Number(
                data[0].lat
            ),

        lon:
            Number(
                data[0].lon
            ),

        name:
            data[0].display_name
    }};
}}


findLocation.addEventListener(
    "click",
    async () => {{

        const query =
            locationSearch.value
            .trim();


        if (!query) {{

            locationStatus.textContent =
                "Skriv en plats först.";

            return;

        }}


        locationStatus.textContent =
            "Söker...";


        try {{

            const result =
                await geocodeLocation(
                    query
                );


            if (!result) {{

                locationStatus.textContent =
                    "Platsen hittades inte.";

                return;

            }}


            selectedLocation =
                result;


            locationStatus.textContent =
                result.name;


            render();

        }}

        catch (error) {{

            locationStatus.textContent =
                "Kunde inte söka plats.";

            console.error(
                error
            );

        }}

    }}
);


locationSearch.addEventListener(
    "keydown",
    event => {{

        if (
            event.key === "Enter"
        ) {{

            findLocation.click();

        }}

    }}
);


useMyLocation.addEventListener(
    "click",
    () => {{

        if (
            !navigator.geolocation
        ) {{

            locationStatus.textContent =
                "Din webbläsare stöder inte position.";

            return;

        }}


        locationStatus.textContent =
            "Hämtar position...";


        navigator.geolocation.getCurrentPosition(

            position => {{

                selectedLocation = {{

                    lat:
                        position.coords.latitude,

                    lon:
                        position.coords.longitude,

                    name:
                        "Min position"
                }};


                locationStatus.textContent =
                    "Min position";


                render();

            }},

            error => {{

                locationStatus.textContent =
                    "Kunde inte läsa din position.";

                console.error(
                    error
                );

            }},

            {{
                enableHighAccuracy:
                    false,

                timeout:
                    10000,

                maximumAge:
                    300000
            }}
        );

    }}
);


clearLocation.addEventListener(
    "click",
    () => {{

        selectedLocation =
            null;

        locationSearch.value =
            "";

        locationStatus.textContent =
            "";


        render();

    }}
);


radiusFilter.addEventListener(
    "change",
    () => render()
);


searchInput.addEventListener(
    "input",
    render
);


typeFilter.addEventListener(
    "change",
    render
);

seriesFilter.addEventListener(
    "change",
    render
);


dateFrom.addEventListener(
    "change",
    () => {{

        setPeriodButton(
            ""
        );

        render();

    }}
);


dateTo.addEventListener(
    "change",
    () => {{

        setPeriodButton(
            ""
        );

        render();

    }}
);


clearDates.addEventListener(
    "click",
    () => {{

        dateFrom.value =
            "";

        dateTo.value =
            "";

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
            () =>
                applyPeriod(
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
        " EVENTFINDER - PLATS + AVSTÅND + DATUM"
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
