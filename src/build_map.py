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
    """
    Normalisera både äldre sportevent och nyare kommun-event
    till de fältnamn som kartans befintliga JS/HTML använder.

    Originalfält bevaras, inklusive:
    category, subcategory och subcategory_color.
    """
    placeholder_terms = (
        "uppflyttat lag",
        "urdraget lag",
        "vinnare semifinal",
    )

    output = []

    for event in events:
        mapped = dict(event)

        mapped["datum"] = (
            event.get("datum")
            or event.get("start_date")
            or event.get("date_start")
            or ""
        )

        mapped["namn"] = (
            event.get("namn")
            or event.get("title")
            or "Event"
        )

        mapped["tid"] = (
            event.get("tid")
            or event.get("time_text")
            or event.get("start_time")
            or ""
        )

        display_venue = (
            event.get("subvenue")
            or event.get("arena")
            or event.get("venue_name")
            or event.get("location_name")
            or event.get("plats")
            or ""
        )

        mapped["arena"] = display_venue
        mapped["plats"] = display_venue

        mapped["kommun"] = (
            event.get("kommun")
            or event.get("municipality")
            or ""
        )

        mapped["serie"] = (
            event.get("serie")
            or event.get("series")
            or ""
        )

        if (
            mapped.get("lat") is None
            or mapped.get("lon") is None
            or not mapped.get("datum")
        ):
            continue

        text = " ".join([
            str(mapped.get("hemmalag") or ""),
            str(mapped.get("bortalag") or ""),
        ]).lower()

        if any(term in text for term in placeholder_terms):
            continue

        output.append(mapped)

    return output


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
                "category": event.get(
                    "category",
                    "",
                ),
                "subcategory": event.get(
                    "subcategory",
                    "",
                ),
                "subcategory_color": event.get(
                    "subcategory_color",
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
                "kalla": event.get("kalla", ""),
                "url": event.get("url", ""),
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


.subcategory-multiselect {{
    position: relative;
    min-width: 320px;
    flex: 1 1 440px;
    max-width: 620px;
}}

.subcategory-toggle {{
    width: 100%;
    min-height: 44px;
    padding: 8px 34px 8px 10px;
    text-align: left;
    background: white;
    border: 1px solid #bbb;
    border-radius: 4px;
    cursor: pointer;
    white-space: nowrap;
    font-size: 15px;
}}

.subcategory-menu {{
    position: absolute;
    z-index: 2000;
    top: calc(100% + 4px);
    left: 0;
    min-width: 100%;
    max-width: 520px;
    max-height: 420px;
    overflow-y: auto;
    padding: 10px;
    background: white;
    border: 1px solid #bbb;
    border-radius: 6px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
}}

.subcategory-actions {{
    display: flex;
    gap: 6px;
    padding-bottom: 8px;
    margin-bottom: 6px;
    border-bottom: 1px solid #eee;
}}

.subcategory-actions button {{
    flex: 1;
    padding: 6px 8px;
    font-size: 12px;
    cursor: pointer;
}}

.subcategory-option {{
    display: flex;
    align-items: center;
    gap: 13px;
    padding: 10px 5px;
    cursor: pointer;
    font-size: 15px;
}}

.subcategory-option:hover {{
    background: #f7f7f7;
}}


.subcategory-group-heading {{
    margin:
        10px 4px 4px 4px;

    padding:
        8px 4px 5px 4px;

    border-bottom:
        1px solid #e6e6e6;

    font-size: 13px;
    font-weight: 700;

    color: #444;
}}


.subcategory-group-heading:first-child {{
    margin-top: 0;
}}

.subcategory-option input {{
    width: 16px;
    height: 16px;
    margin: 0;
    flex: 0 0 auto;
}}

.subcategory-option-dot {{
    --pin-color: #777;

    width: 32px;
    height: 32px;
    min-width: 32px;

    display: inline-flex;
    align-items: center;
    justify-content: center;

    background: var(--pin-color);

    border-radius:
        50% 50% 50% 0;

    transform:
        rotate(-45deg);

    border: 2px solid white;

    box-shadow:
        0 1px 4px rgba(0, 0, 0, 0.30);
}}


.subcategory-option-dot span {{
    display: flex;
    align-items: center;
    justify-content: center;

    transform:
        rotate(45deg);

    color: white;

    font-size: 15px;
    line-height: 1;
}}


.subcategory-option-dot span svg {{
    width: 18px;
    height: 18px;

    fill: none;
    stroke: currentColor;

    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
}}

@media (max-width: 900px) {{
    .subcategory-multiselect {{
        min-width: 200px;
        width: 100%;
    }}

    .subcategory-menu {{
        min-width: 100%;
        max-width: min(360px, 90vw);
    }}
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
    grid-template-columns: 1fr;
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
    --marker-bg: #202020;

    position: relative;

    width: 46px;
    height: 58px;

    min-width: 46px;

    overflow: visible;
}}


.arena-marker::before {{
    content: "";

    position: absolute;

    left: 3px;
    top: 2px;

    width: 40px;
    height: 40px;

    background: var(--marker-bg);

    border-radius: 50%;

    border: 2px solid white;

    box-shadow:
        0 2px 6px rgba(0, 0, 0, 0.36);

    z-index: 2;
}}


.arena-marker::after {{
    content: "";

    position: absolute;

    left: 16px;
    top: 34px;

    width: 14px;
    height: 14px;

    background: var(--marker-bg);

    transform: rotate(45deg);

    border-right: 2px solid white;
    border-bottom: 2px solid white;

    border-radius: 0 0 4px 0;

    z-index: 1;
}}


.arena-marker-inner {{
    position: absolute;

    left: 3px;
    top: 2px;

    width: 40px;
    height: 40px;

    display: flex;
    align-items: center;
    justify-content: center;

    z-index: 3;
}}


.arena-marker-symbol {{
    display: flex;
    align-items: center;
    justify-content: center;

    color: white;

    font-size: 19px;
    line-height: 1;

    text-align: center;
}}


.arena-marker-symbol svg {{
    width: 25px;
    height: 25px;

    fill: none;
    stroke: currentColor;

    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
}}


.arena-marker-count {{
    position: absolute;

    right: -6px;
    top: -5px;

    min-width: 17px;
    height: 17px;

    padding: 0 4px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 999px;

    background: white;
    color: #202020;

    border:
        1px solid rgba(0, 0, 0, 0.18);

    box-shadow:
        0 1px 3px rgba(0, 0, 0, 0.30);

    font-size: 10px;
    font-weight: 700;

    line-height: 1;
}}


.arena-marker.football,
.arena-marker.floorball,
.arena-marker.handball,
.arena-marker.hockey,
.arena-marker.basket {{
    --marker-bg: #2e7d32;
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


        /* RUNTMIGO_SPORT_GLOSSY_SIZE_V2_1 */
        .arena-marker:has(.runtmigo-sport-glossy-pin)
        .runtmigo-sport-glossy-pin {{
            width: 34px !important;
            height: 42px !important;
            max-width: none !important;
            max-height: none !important;
        }}


        /* RUNTMIGO_GLOSSY_PIN_AS_FULL_MARKER_V2_4_3 */
        .arena-marker:has(.runtmigo-glossy-pin)::before,
        .arena-marker:has(.runtmigo-glossy-pin)::after {{
            display: none !important;
            content: none !important;
        }}

        .arena-marker:has(.runtmigo-glossy-pin)
        .arena-marker-symbol {{
            overflow: visible !important;
        }}

</style>


<style id="eventfinder-popup-legend-style">

.main {{
    grid-template-columns:
        minmax(0, 1fr)
        190px;
}}

.legend-sidebar {{
    min-height: 0;
    align-self: start;
    margin: 12px;
    border: 1px solid #ddd;
    border-radius: 10px;
    background: white;
    overflow: hidden;
}}

.legend-panel {{
    padding: 14px;
}}

.legend-panel h2 {{
    margin: 0 0 12px 0;
    font-size: 15px;
}}

.legend-row {{
    display: flex;
    align-items: center;
    gap: 9px;
    margin: 8px 0;
    font-size: 14px;
}}

.legend-dot {{
    width: 15px;
    height: 15px;
    flex: 0 0 15px;
    border-radius: 50%;
    border: 2px solid white;
    box-shadow:
        0 1px 4px rgba(0, 0, 0, 0.28);
}}

.legend-dot.football {{
    background: #2e7d32;
}}

.legend-dot.floorball {{
    background: #29b6f6;
}}

.legend-dot.handball {{
    background: #fbc02d;
}}

.legend-dot.hockey {{
    background: #163a70;
}}

.legend-dot.basket {{
    background: #8d5a3b;
}}

.legend-dot.other {{
    background: #202020;
}}

.arena-popup-kind {{
    display: inline-block;
    margin-top: 5px;
    padding: 3px 7px;
    border-radius: 10px;
    background: #f0f0f0;
    font-size: 12px;
    font-weight: bold;
}}

.arena-popup-series {{
    margin-top: 4px;
    font-size: 13px;
}}

.arena-popup-source {{
    margin-top: 7px;
}}

.arena-popup-source a {{
    font-size: 13px;
    font-weight: bold;
    text-decoration: none;
}}

.arena-popup-source a:hover {{
    text-decoration: underline;
}}


.arena-popup-directions {{
    margin-top: 5px;
}}


.arena-popup-directions a {{
    display: inline-flex;
    align-items: center;
    gap: 5px;

    font-size: 13px;
    font-weight: bold;

    text-decoration: none;

    color: #1565c0;
}}


.arena-popup-directions a:hover {{
    text-decoration: underline;
}}

@media (max-width: 900px) {{

    .main {{
        grid-template-columns: 1fr;
        grid-template-rows:
            minmax(340px, 1fr)
            auto;
    }}

    .legend-sidebar {{
        margin: 8px 12px 12px 12px;
    }}

    .legend-panel {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 7px 14px;
    }}

    .legend-panel h2 {{
        width: 100%;
        margin-bottom: 3px;
    }}

    .legend-row {{
        margin: 2px 0;
    }}
}}

</style>


<style id="eventfinder-legend-category-style">

.legend-sidebar {{
    width: 275px;
}}

.legend-panel {{
    display: block !important;
    padding: 12px;
}}

.legend-panel h2 {{
    margin: 0 0 10px 0;
}}

.legend-category {{
    border-top: 1px solid #eeeeee;
}}

.legend-category:last-of-type {{
    border-bottom: 1px solid #eeeeee;
}}

.legend-category summary {{
    padding: 9px 2px;
    cursor: pointer;
    font-size: 14px;
    font-weight: 600;
    user-select: none;
}}

.legend-category summary:hover {{
    background: #f7f7f7;
}}

.legend-items {{
    padding: 0 4px 6px 12px;
}}

.legend-category .legend-row {{
    margin: 7px 0;
}}

.legend-category .legend-dot {{
    width: 18px;
    height: 18px;
    min-width: 18px;
    border-radius: 50%;
    display: inline-block;
    margin-right: 8px;
    vertical-align: middle;
}}

.legend-placeholder {{
    padding: 2px 6px 10px 12px;
    font-size: 12px;
    line-height: 1.35;
    color: #777;
}}

@media (max-width: 900px) {{

    .legend-sidebar {{
        width: auto;
    }}

    .legend-panel {{
        display: block !important;
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

    <select id="seriesFilter" style="display:none">
        <option value=""></option>
    </select>

    <div class="subcategory-multiselect" id="subcategoryMultiselect">
        <button
            id="subcategoryToggle"
            class="subcategory-toggle"
            type="button"
            aria-expanded="false"
        >
            Alla underkategorier ▾
        </button>

        <div
            id="subcategoryMenu"
            class="subcategory-menu"
            hidden
        >
            <div class="subcategory-actions">
                <button id="subcategorySelectAll" type="button">
                    Markera alla
                </button>
                <button id="subcategoryClearAll" type="button">
                    Avmarkera alla
                </button>
            </div>

            <div id="subcategoryOptions"></div>
        </div>
    </div>

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
            data-period="today"
            class="active"
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

    <div
        id="eventList"
        style="display:none"
    ></div>
</div>

</div>


<script
src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js">
</script>


<script>

const events = {js_events};

function legendEscapeHtml(
    value
) {{

    return String(
        value ?? ""
    )
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}}


function populateSubcategoryLegend() {{

    const targets = {{
        "Musik": "legend-music",
        "Kultur": "legend-culture",
        "Mat & dryck": "legend-food",
        "Familj & barn": "legend-family",
        "Marknad & mässa": "legend-market",
        "Övrigt": "legend-other"
    }};


    Object.entries(
        targets
    ).forEach(
        ([category, elementId]) => {{

            const container =
                document.getElementById(
                    elementId
                );


            if (!container) {{
                return;
            }}


            const rows =
                new Map();


            events.forEach(
                event => {{

                    if (
                        eventMainCategory(event) !== category
                        || !event.subcategory
                        || !event.subcategory_color
                    ) {{
                        return;
                    }}


                    if (
                        !rows.has(
                            eventSubcategory(event)
                        )
                    ) {{
                        rows.set(
                            eventSubcategory(event),
                            eventSubcategoryColor(event)
                        );
                    }}
                }}
            );


            if (rows.size === 0) {{

                container.innerHTML =
                    '<div class="legend-placeholder">'
                    + 'Inga färgkodade event ännu.'
                    + '</div>';

                return;
            }}


            container.innerHTML =
                [
                    ...rows.entries()
                ]
                    .sort(
                        (a, b) =>
                            a[0].localeCompare(
                                b[0],
                                "sv"
                            )
                    )
                    .map(
                        ([subcategory, color]) =>

                            '<div class="legend-row">'
                            + '<span class="legend-dot" '
                            + 'style="background: '
                            + legendEscapeHtml(color)
                            + '"></span>'
                            + '<span>'
                            + legendEscapeHtml(subcategory)
                            + '</span>'
                            + '</div>'
                    )
                    .join("");
        }}
    );
}}


populateSubcategoryLegend();



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


const subcategoryMultiselect =
    document.getElementById(
        "subcategoryMultiselect"
    );

const subcategoryToggle =
    document.getElementById(
        "subcategoryToggle"
    );

const subcategoryMenu =
    document.getElementById(
        "subcategoryMenu"
    );

const subcategoryOptions =
    document.getElementById(
        "subcategoryOptions"
    );

const subcategorySelectAll =
    document.getElementById(
        "subcategorySelectAll"
    );

const subcategoryClearAll =
    document.getElementById(
        "subcategoryClearAll"
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



subcategoryToggle.addEventListener(
    "click",
    () => {{
        const opening =
            subcategoryMenu.hidden;

        subcategoryMenu.hidden =
            !opening;

        subcategoryToggle.setAttribute(
            "aria-expanded",
            opening
                ? "true"
                : "false"
        );
    }}
);


subcategorySelectAll.addEventListener(
    "click",
    () => {{
        setAllSubcategories(
            true
        );
    }}
);


subcategoryClearAll.addEventListener(
    "click",
    () => {{
        setAllSubcategories(
            false
        );
    }}
);


document.addEventListener(
    "click",
    event => {{
        if (
            !subcategoryMultiselect.contains(
                event.target
            )
        ) {{
            subcategoryMenu.hidden =
                true;

            subcategoryToggle.setAttribute(
                "aria-expanded",
                "false"
            );
        }}
    }}
);


const MAIN_CATEGORIES = [
    "Familj & barn",
    "Häst & ridsport",
    "Kultur",
    "Marknad & mässa",
    "Mat & dryck",
    "Motor & fordon",
    "Musik",
    "Sport",
    "Övrigt"
];


const CATEGORY_SUBCATEGORIES = {{
    "Familj & barn": [
        "Babyrelaterat",
        "Barnbio",
        "Barnteater",
        "Lovaktiviteter",
        "Pyssel & skapande",
        "Övrigt"
    ],

    "Häst & ridsport": [
        "Clinics, shower & uppvisningar",
        "Dressyr",
        "Fälttävlan & distansritt",
        "Galopp",
        "Hoppning",
        "Ridskola & prova på",
        "Trav",
        "Övrigt"
    ],

    "Kultur": [
        "Film & bio",
        "Föreläsning & samtal",
        "Konst & utställning",
        "Litteratur & författare",
        "Museum & kulturarv",
        "Teater",
        "Övrigt"
    ],

    "Marknad & mässa": [
        "Fritidsmässa",
        "Husdjursmässa",
        "Jobbmässa",
        "Julmarknad",
        "Lokal marknad",
        "Loppis",
        "Matmarknad",
        "Matmässa",
        "Motormässa",
        "Övrig marknad",
        "Övrig mässa"
    ],

    "Mat & dryck": [
        "Bed & breakfast",
        "Café",
        "Dryckesmässa & marknad",
        "Gårdsbutik",
        "Gårdsförsäljning",
        "Matmässa & marknad",
        "Restaurang",
        "Övrigt"
    ],

    "Motor & fordon": [
        "Bilträffar, cruising & veteranfordon",
        "Karting",
        "Motocross & enduro",
        "Mässor & uppvisningar",
        "Racing & bana",
        "Rally",
        "RC Racing",
        "Speedway",
        "Övrigt"
    ],

    "Musik": [
        "Allsång & musikunderhållning",
        "Festival",
        "Klubb & DJ",
        "Konsert",
        "Kör & vokalt",
        "Övrigt"
    ],

    "Sport": [
        "Badminton",
        "Basket",
        "Bordtennis",
        "Cykel",
        "eSport",
        "Fotboll",
        "Friidrott",
        "Golf",
        "Gymnastik",
        "Handboll",
        "Innebandy",
        "Ishockey",
        "Kampsport",
        "Löpning",
        "Padel",
        "Simning",
        "Tennis",
        "Volleyboll",
        "Övrigt"
    ],

    "Övrigt": []
}};


const CATEGORY_COLORS = {{
    "Sport": "#2e7d32",
    "Musik": "#7434b5",
    "Kultur": "#f57c00",
    "Mat & dryck": "#9d1838",
    "Familj & barn": "#2196f3",
    "Marknad & mässa": "#e00068",
    "Övrigt": "#757575",
    "Motor & fordon": "#111111",
    "Häst & ridsport": "#795548",
}};


/*
 * Vita symboler i respektive huvudkategoris färg.
 * De visas både i filtret och på kartans stora nålar.
 */
const SUBCATEGORY_SYMBOLS = {{

    /* MUSIK */
    "Musik|Konsert": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/musik__konsert.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Musik|Festival": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/musik__festival.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Musik|Klubb & DJ": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/musik__klubb_and_dj.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Musik|Allsång & musikunderhållning": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/musik__allsang_and_musikunderhallning.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Musik|Kör & vokalt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/musik__kor_and_vokalt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Musik|Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/musik__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',

    /* KULTUR */
    "Kultur|Teater": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/kultur__teater.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Kultur|Konst & utställning": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/kultur__konst_and_utstallning.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Kultur|Film & bio": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/kultur__film_and_bio.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Kultur|Litteratur & författare": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/kultur__litteratur_and_forfattare.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Kultur|Föreläsning & samtal": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/kultur__forelasning_and_samtal.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Kultur|Museum & kulturarv": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/kultur__museum_and_kulturarv.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Kultur|Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/kultur__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',

    /* SPORT – GENERISK ÖVRIGT */
    "Sport|Övrigt": "★",

    /* MAT & DRYCK */
    "Mat & dryck|Restaurang": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__restaurang.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Mat & dryck|Café": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__cafe.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Mat & dryck|Bed & breakfast": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__bed_and_breakfast.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Mat & dryck|Gårdsbutik": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__gardsbutik.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Mat & dryck|Gårdsförsäljning": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__gardsforsaljning.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Mat & dryck|Matmässa & marknad": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__matmassa_and_marknad.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Mat & dryck|Dryckesmässa & marknad": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__dryckesmassa_and_marknad.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Mat & dryck|Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',

    /* FAMILJ & BARN */
    "Familj & barn|Babyrelaterat": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__babyrelaterat.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Barnbio": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__barnbio.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Barnteater": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__barnteater.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Pyssel & skapande": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__pyssel_and_skapande.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Lovaktiviteter": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__lovaktiviteter.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',

    /* MARKNAD & MÄSSA */
    "Marknad & mässa|Lokal marknad": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__lokal_marknad.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Loppis": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__loppis.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Matmarknad": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__matmarknad.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Julmarknad": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__julmarknad.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Övrig marknad": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__ovrig_marknad.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Matmässa": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__matmassa.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Husdjursmässa": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__husdjursmassa.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Jobbmässa": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__jobbmassa.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Fritidsmässa": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__fritidsmassa.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Motormässa": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__motormassa.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa|Övrig mässa": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__ovrig_massa.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Sagor & läsning": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__barnbio.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Småbarn & förskola": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__babyrelaterat.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Ungdom": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__lovaktiviteter.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Familjeaktivitet": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn|Barnteater & cirkus": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__barnteater.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Digital hjälp": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__digital_hjalp.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Föreningsaktivitet": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__foreningsaktivitet.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Hälsa & välmående": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__halsa_and_valmaende.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Natur & friluftsliv": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__natur_and_friluftsliv.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Näringsliv": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__naringsliv.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Religion & livsåskådning": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__religion_and_livsaskadning.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Samhälle & demokrati": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__samhalle_and_demokrati.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Språk & integration": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__sprak_and_integration.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt|Företag & nätverk": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__naringsliv.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|Bilträffar, cruising & veteranfordon": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__biltraffar_cruising_and_veteranfordon.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|Karting": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__karting.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|Motocross & enduro": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__motocross_and_enduro.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|Mässor & uppvisningar": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__massor_and_uppvisningar.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|Racing & bana": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__racing_and_bana.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|Rally": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__rally.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|RC Racing": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__rc_racing.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|Speedway": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__speedway.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon|Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport|Clinics, shower & uppvisningar": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__clinics_shower_and_uppvisningar.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport|Dressyr": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__dressyr.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport|Fälttävlan & distansritt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__falttavlan_and_distansritt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport|Galopp": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__galopp.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport|Hoppning": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__hoppning.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport|Ridskola & prova på": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__ridskola_and_prova_pa.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport|Trav": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__trav.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport|Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
}};


function sportSvg(body) {{
    return (
        '<svg viewBox="0 0 24 24" '
        + 'aria-hidden="true" '
        + 'focusable="false">'
        + body
        + '</svg>'
    );
}}


const SPORT_SYMBOLS = {{

    /* 1. FOTBOLL */
    "Fotboll": sportSvg(
        '<circle cx="12" cy="12" r="9"/>'
        + '<path d="M12 7l3 2-1 4h-4L9 9z"/>'
        + '<path d="M12 7V3M15 9l4-2M14 13l3 4M10 13l-3 4M9 9L5 7"/>'
    ),

    /* 2. INNEBANDY */
    "Innebandy": sportSvg(
        '<path d="M5 3l5 13c.6 1.7 2.2 2.8 4 2.8h3"/>'
        + '<path d="M14 18.8h5"/>'
        + '<circle cx="19" cy="16" r="2"/>'
        + '<circle cx="18.4" cy="15.4" r=".25"/>'
        + '<circle cx="19.6" cy="16.5" r=".25"/>'
    ),

    /* 3. HANDBOLL */
    "Handboll": sportSvg(
        '<circle cx="14" cy="9" r="5"/>'
        + '<path d="M3 21c1-5 3-8 7-10"/>'
        + '<path d="M8 21l3-6"/>'
        + '<path d="M14 4l1.5 10M10 6l8 6M10 12l8-6"/>'
    ),

    /* 4. ISHOCKEY */
    "Ishockey": sportSvg(
        '<path d="M6 3l4 13c.5 1.6 2 2.7 3.7 2.7H19"/>'
        + '<path d="M14 19h6"/>'
        + '<ellipse cx="7" cy="19" rx="3" ry="1.2"/>'
    ),

    /* 5. BASKET */
    "Basket": sportSvg(
        '<circle cx="12" cy="12" r="9"/>'
        + '<path d="M3 12h18M12 3v18"/>'
        + '<path d="M5.5 5.5c5 2 8 5 13 13"/>'
        + '<path d="M18.5 5.5c-5 2-8 5-13 13"/>'
    ),
    "Basketboll": sportSvg(
        '<circle cx="12" cy="12" r="9"/>'
        + '<path d="M3 12h18M12 3v18"/>'
        + '<path d="M5.5 5.5c5 2 8 5 13 13"/>'
        + '<path d="M18.5 5.5c-5 2-8 5-13 13"/>'
    ),

    /* 6. TENNIS */
    "Tennis": sportSvg(
        '<circle cx="10" cy="9" r="6"/>'
        + '<path d="M14 13l6 7"/>'
        + '<path d="M6 5c3 1 6 4 8 8"/>'
    ),

    /* 7. PADEL */
    "Padel": sportSvg(
        '<path d="M8 3c4-1 8 2 8 6 0 3-2 5-4 7l-2 2-5-5 1-2c1-2 0-5 2-8z"/>'
        + '<path d="M10 18l4 4"/>'
        + '<circle cx="10" cy="7" r=".5"/>'
        + '<circle cx="12" cy="9" r=".5"/>'
        + '<circle cx="9" cy="11" r=".5"/>'
        + '<circle cx="18.5" cy="5.5" r="2"/>'
    ),

    /* 8. GOLF */
    "Golf": sportSvg(
        '<path d="M8 3v15"/>'
        + '<path d="M8 4l8 3-8 3"/>'
        + '<circle cx="15" cy="19" r="2"/>'
        + '<path d="M4 21h16"/>'
    ),

    /* 9. FRIIDROTT */
    "Friidrott": sportSvg(
        '<circle cx="14" cy="4" r="2"/>'
        + '<path d="M11 8l3 3 4 1"/>'
        + '<path d="M14 11l-3 4-5 2"/>'
        + '<path d="M11 15l4 5"/>'
        + '<path d="M10 9L6 13"/>'
    ),

    /* 10. LÖPNING */
    "Löpning": sportSvg(
        '<path d="M3 15c4 0 6 1 9 3h7c1 0 2 1 2 2H9c-3 0-5-1-6-2z"/>'
        + '<path d="M7 15l2-5 3 4"/>'
        + '<path d="M13 18l3-4"/>'
    ),

    /* 11. CYKEL */
    "Cykel": sportSvg(
        '<circle cx="6" cy="17" r="4"/>'
        + '<circle cx="18" cy="17" r="4"/>'
        + '<path d="M6 17l4-7 4 7H6z"/>'
        + '<path d="M10 10h5l3 7"/>'
        + '<path d="M9 7h4"/>'
    ),
    "Cykling": sportSvg(
        '<circle cx="6" cy="17" r="4"/>'
        + '<circle cx="18" cy="17" r="4"/>'
        + '<path d="M6 17l4-7 4 7H6z"/>'
        + '<path d="M10 10h5l3 7"/>'
        + '<path d="M9 7h4"/>'
    ),

    /* 12. SIMNING */
    "Simning": sportSvg(
        '<circle cx="15" cy="6" r="2"/>'
        + '<path d="M4 13l5-3 5 3 4-2"/>'
        + '<path d="M2 17c2-1 4-1 6 0s4 1 6 0 4-1 8 0"/>'
        + '<path d="M2 21c2-1 4-1 6 0s4 1 6 0 4-1 8 0"/>'
    ),

    /* 13. RIDSPORT */
    "Ridsport": sportSvg(
        '<path d="M4 14l3-7 5-3 5 3 2 6-4 5H8z"/>'
        + '<path d="M12 4l2-2 2 3"/>'
        + '<circle cx="15" cy="8" r=".6"/>'
        + '<path d="M7 14l-2 7M16 15l2 6"/>'
    ),
    "Hästsport": sportSvg(
        '<path d="M4 14l3-7 5-3 5 3 2 6-4 5H8z"/>'
        + '<path d="M12 4l2-2 2 3"/>'
        + '<circle cx="15" cy="8" r=".6"/>'
        + '<path d="M7 14l-2 7M16 15l2 6"/>'
    ),

    /* 14. GYMNASTIK */
    "Gymnastik": sportSvg(
        '<circle cx="12" cy="4" r="2"/>'
        + '<path d="M12 6v6"/>'
        + '<path d="M12 8L5 5M12 8l7-3"/>'
        + '<path d="M12 12l-5 7M12 12l5 7"/>'
    ),

    /* 15. KAMPSPORT */
    "Kampsport": sportSvg(
        '<circle cx="12" cy="4" r="2"/>'
        + '<path d="M9 7h6l2 7-5 7-5-7z"/>'
        + '<path d="M9 9l-5 4M15 9l5 4"/>'
        + '<path d="M9 15h6"/>'
    ),

    /* 16. VOLLEYBOLL */
    "Volleyboll": sportSvg(
        '<circle cx="12" cy="12" r="9"/>'
        + '<path d="M12 3c3 3 4 6 3 9"/>'
        + '<path d="M15 12c-4 0-7 1-10 4"/>'
        + '<path d="M12 21c-1-4-3-7-7-9"/>'
        + '<path d="M19 7c-4 1-7 0-10-2"/>'
    ),

    /* 17. BADMINTON */
    "Badminton": sportSvg(
        '<path d="M6 4l8 8"/>'
        + '<path d="M9 3l6 6"/>'
        + '<path d="M4 7l6 6"/>'
        + '<path d="M14 12l6 6"/>'
        + '<path d="M17 15l3-1 1 3-1 3-3-1z"/>'
    ),

    /* 18. BORDTENNIS */
    "Bordtennis": sportSvg(
        '<circle cx="9" cy="9" r="6"/>'
        + '<path d="M13 13l7 7"/>'
        + '<circle cx="19" cy="6" r="2"/>'
    ),

    /* 19. MOTORSPORT */
    "Motorsport": sportSvg(
        '<path d="M4 15l2-5h12l2 5"/>'
        + '<path d="M8 10l2-4h5l3 4"/>'
        + '<path d="M3 15h18v3H3z"/>'
        + '<circle cx="7" cy="18" r="2"/>'
        + '<circle cx="17" cy="18" r="2"/>'
        + '<path d="M6 13h3M15 13h3"/>'
    ),

    /* 20. ESPORT */
    "eSport": sportSvg(
        '<path d="M6 8h12c2 0 4 5 4 8 0 2-1 3-3 3l-4-3H9l-4 3c-2 0-3-1-3-3 0-3 2-8 4-8z"/>'
        + '<path d="M7 11v5M4.5 13.5h5"/>'
        + '<circle cx="17" cy="12" r="1"/>'
        + '<circle cx="19" cy="15" r="1"/>'
    ),
    "E-sport": sportSvg(
        '<path d="M6 8h12c2 0 4 5 4 8 0 2-1 3-3 3l-4-3H9l-4 3c-2 0-3-1-3-3 0-3 2-8 4-8z"/>'
        + '<path d="M7 11v5M4.5 13.5h5"/>'
        + '<circle cx="17" cy="12" r="1"/>'
        + '<circle cx="19" cy="15" r="1"/>'
    )
}};


const CATEGORY_SYMBOLS = {{
    "Sport": "★",
    "Musik": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/musik__konsert.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Kultur": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/kultur__teater.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Mat & dryck": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/mat_and_dryck__restaurang.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Familj & barn": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/familj_and_barn__barnteater.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Marknad & mässa": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/marknad_and_massa__lokal_marknad.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/ovrigt__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Motor & fordon": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/motor_and_fordon__rally.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Häst & ridsport": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_glossy_repair_v2_4_3/hast_and_ridsport__hoppning.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
}};


function categorySymbol(category) {{
    return CATEGORY_SYMBOLS[category] || "●";
}}


/* RUNTMIGO_SPORT_GLOSSY_PNGS_V2_1 */
const RUNTMIGO_SPORT_GLOSSY_PNGS_V2_1 = {{
    "Badminton": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__badminton.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Basket": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__basket.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Bordtennis": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__bordtennis.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Cykel": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__cykel.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "eSport": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__esport.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Fotboll": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__fotboll.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Friidrott": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__friidrott.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Golf": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__golf.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Gymnastik": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__gymnastik.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Handboll": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__handboll.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Innebandy": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__innebandy.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Ishockey": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__ishockey.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Kampsport": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__kampsport.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Löpning": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__lopning.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Padel": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__padel.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Simning": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__simning.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Tennis": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__tennis.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Volleyboll": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__volleyboll.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Övrigt": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__ovrigt.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
    "Yoga": '<img class="runtmigo-glossy-pin runtmigo-sport-glossy-pin" src="../assets/icons/runtmigo_sport_glossy_fix_v2_1/sport__gymnastik.png" alt="" style="width:28px;height:34px;object-fit:contain;display:block;margin:auto;" />',
}};

function subcategorySymbol(category, subcategory) {{
    /* RUNTMIGO_SPORT_GLOSSY_PNGS_V2_1_RETURN */
    const runtmigoSportGlossy21 =
        (category === "Sport")
        ? RUNTMIGO_SPORT_GLOSSY_PNGS_V2_1[subcategory]
        : null;

    if (runtmigoSportGlossy21) {{
        return runtmigoSportGlossy21;
    }}

    /* RUNTMIGO_SAFE_ICONPILOT_V2_RALLY_SYMBOL */
    if (
        category === "Motor & fordon"
        && subcategory === "Rally"
    ) {{
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" aria-hidden="true" style="width:27px;height:27px;display:block"><g fill="none" stroke="#fff" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 36l6-14h26l6 14v12H13z"/><path d="M20 22l5-7h14l5 7"/><path d="M16 36h32"/><circle cx="21" cy="49" r="4"/><circle cx="43" cy="49" r="4"/><circle cx="24" cy="41" r="2.4" fill="#fff"/><circle cx="32" cy="41" r="2.4" fill="#fff"/><circle cx="40" cy="41" r="2.4" fill="#fff"/></g></svg>`;
    }}

    if (
        category === "Sport"
        && SPORT_SYMBOLS[subcategory]
    ) {{
        return SPORT_SYMBOLS[subcategory];
    }}

    return (
        SUBCATEGORY_SYMBOLS[
            `${{category}}|${{subcategory}}`
        ]
        || categorySymbol(category)
    );
}}


function eventMainCategory(event) {{
    /*
     * RUNTMIGO_MOTOR_HORSE_MAIN_V1
     * Exakta strukturella signaler – ingen titelbaserad gissning.
     */
    const runtmigoSportName =
        String(event.sport || "").trim();

    const runtmigoSubcategory =
        String(
            event.subcategory
            || event.underkategori
            || ""
        ).trim();

    if (
        event.motorsportBranch
        || runtmigoSportName === "Motorsport"
        || runtmigoSubcategory === "Motorsport"
        || runtmigoSubcategory === "Motormässa"
    ) {{
        return "Motor & fordon";
    }}

    if (
        event.ridsportBranch
        || event.equestrianBranch
        || runtmigoSportName === "Ridsport/Hästsport"
        || runtmigoSportName === "Ridsport"
        || runtmigoSportName === "Hästsport"
        || runtmigoSubcategory === "Ridsport/Hästsport"
        || runtmigoSubcategory === "Ridsport"
        || runtmigoSubcategory === "Hästsport"
    ) {{
        return "Häst & ridsport";
    }}


    const category =
        event.category
        || event.kategori
        || "";

    const typ =
        event.typ
        || "";


    /*
     * Bakåtkompatibilitet:
     * gamla Musik & konsert och Festival
     * hör nu hemma under Musik.
     */
    if (
        category === "Musik"
        || category === "Musik & konsert"
        || category === "Festival"
        || typ === "Musik"
        || typ === "Musik & konsert"
        || typ === "Festival"
    ) {{
        return "Musik";
    }}


    if (
        category
        && MAIN_CATEGORIES.includes(category)
    ) {{
        return category;
    }}


    if (event.sport) {{
        return "Sport";
    }}


    if (
        typ
        && MAIN_CATEGORIES.includes(typ)
    ) {{
        return typ;
    }}


    return "Övrigt";
}}


function eventSubcategory(event) {{
    /*
     * RUNTMIGO_MOTOR_HORSE_SUB_V1
     * Nationell motorsport kan redan bära exakt gren i motorsportBranch.
     */
    if (
        event.motorsportBranch
        && eventMainCategory(event) === "Motor & fordon"
    ) {{
        return String(event.motorsportBranch).trim();
    }}

    const runtmigoHorseBranch =
        event.ridsportBranch
        || event.equestrianBranch
        || "";

    if (
        runtmigoHorseBranch
        && eventMainCategory(event) === "Häst & ridsport"
    ) {{
        return String(runtmigoHorseBranch).trim();
    }}


    const main =
        eventMainCategory(event);

    const explicit =
        event.subcategory
        || event.underkategori
        || "";

    const sourceText =
        [
            explicit,
            event.typ,
            event.namn,
            event.category,
            event.kategori
        ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();


    /* SPORT */

    if (main === "Sport") {{

        const sport =
            event.sport
            || explicit
            || "";

        const SPORT_ALIASES = {{
            "Basketboll": "Basket",
            "Cykling": "Cykel",
            "Hästsport": "Ridsport",
            "E-sport": "eSport",
            "Esport": "eSport",
            "E-Sport": "eSport"
        }};

        return (
            SPORT_ALIASES[sport]
            || sport
        );
    }}


    /* MUSIK */

    if (main === "Musik") {{

        if (
            event.category === "Festival"
            || event.kategori === "Festival"
            || event.typ === "Festival"
            || explicit === "Festival"
        ) {{
            return "Festival";
        }}

        if (
            CATEGORY_SUBCATEGORIES[
                "Musik"
            ].includes(explicit)
        ) {{
            return explicit;
        }}

        if (/dj|klubb/.test(sourceText)) {{
            return "Klubb & DJ";
        }}

        if (
            /allsång|trubadur|musikunderhållning/.test(
                sourceText
            )
        ) {{
            return "Allsång & musikunderhållning";
        }}

        if (/kör|vokal/.test(sourceText)) {{
            return "Kör & vokalt";
        }}

        /*
         * Gamla genre-underkategorier som
         * Jazz & blues blir vanliga konserter.
         */
        return "Konsert";
    }}


    /* KULTUR */

    if (main === "Kultur") {{

        if (
            CATEGORY_SUBCATEGORIES[
                "Kultur"
            ].includes(explicit)
        ) {{
            return explicit;
        }}

        if (/teater/.test(sourceText)) {{
            return "Teater";
        }}

        if (
            /konst|utställ|vernissage/.test(
                sourceText
            )
        ) {{
            return "Konst & utställning";
        }}

        if (/film|bio/.test(sourceText)) {{
            return "Film & bio";
        }}

        if (
            /litteratur|författ|bok|poesi/.test(
                sourceText
            )
        ) {{
            return "Litteratur & författare";
        }}

        if (
            /föreläs|samtal|debatt/.test(
                sourceText
            )
        ) {{
            return "Föreläsning & samtal";
        }}

        if (
            /museum|kulturarv|histori/.test(
                sourceText
            )
        ) {{
            return "Museum & kulturarv";
        }}

        return explicit || "Övrigt";
    }}


    /* MAT & DRYCK */

    if (main === "Mat & dryck") {{

        if (
            CATEGORY_SUBCATEGORIES[
                "Mat & dryck"
            ].includes(explicit)
        ) {{
            return explicit;
        }}

        if (
            /bed.?and.?breakfast|b&b/.test(
                sourceText
            )
        ) {{
            return "Bed & breakfast";
        }}

        if (/gårdsförsälj/.test(sourceText)) {{
            return "Gårdsförsäljning";
        }}

        if (/gårdsbutik/.test(sourceText)) {{
            return "Gårdsbutik";
        }}

        if (
            /dryck|vin|öl|cider|whisky/.test(
                sourceText
            )
            &&
            /mässa|marknad/.test(sourceText)
        ) {{
            return "Dryckesmässa & marknad";
        }}

        if (
            /mat/.test(sourceText)
            &&
            /mässa|marknad/.test(sourceText)
        ) {{
            return "Matmässa & marknad";
        }}

        if (/café|cafe|fika/.test(sourceText)) {{
            return "Café";
        }}

        if (
            /restaurang|middag|lunch/.test(
                sourceText
            )
        ) {{
            return "Restaurang";
        }}

        return explicit;
    }}


    /* FAMILJ & BARN */

    if (main === "Familj & barn") {{

        if (
            CATEGORY_SUBCATEGORIES[
                "Familj & barn"
            ].includes(explicit)
        ) {{
            return explicit;
        }}

        if (
            /baby|bebis|spädbarn|babyrytmik/.test(
                sourceText
            )
        ) {{
            return "Babyrelaterat";
        }}

        if (/bio|film/.test(sourceText)) {{
            return "Barnbio";
        }}

        if (
            /teater|dockteater/.test(
                sourceText
            )
        ) {{
            return "Barnteater";
        }}

        if (
            /pyssel|skapande|skapa|verkstad/.test(
                sourceText
            )
        ) {{
            return "Pyssel & skapande";
        }}

        if (
            /lov|sportlov|höstlov|jullov|påsklov|sommarlov/.test(
                sourceText
            )
        ) {{
            return "Lovaktiviteter";
        }}

        /*
         * Äldre underkategorier behålls tills
         * datan senare klassificeras om.
         */
        return explicit;
    }}


    /* MARKNAD & MÄSSA */

    if (main === "Marknad & mässa") {{

        if (
            CATEGORY_SUBCATEGORIES[
                "Marknad & mässa"
            ].includes(explicit)
        ) {{
            return explicit;
        }}

        if (/julmarknad/.test(sourceText)) {{
            return "Julmarknad";
        }}

        if (
            /loppis|loppmarknad|loppmarknad/.test(
                sourceText
            )
        ) {{
            return "Loppis";
        }}

        if (
            /husdjur|hund|katt/.test(
                sourceText
            )
            &&
            /mässa/.test(sourceText)
        ) {{
            return "Husdjursmässa";
        }}

        if (
            /jobb|karriär|rekryter/.test(
                sourceText
            )
        ) {{
            return "Jobbmässa";
        }}

        if (
            /motor|bil|fordon/.test(
                sourceText
            )
            &&
            /mässa/.test(sourceText)
        ) {{
            return "Motormässa";
        }}

        if (
            /fritid|friluft|camping|cykel/.test(
                sourceText
            )
            &&
            /mässa/.test(sourceText)
        ) {{
            return "Fritidsmässa";
        }}

        if (
            /mat/.test(sourceText)
            &&
            /mässa/.test(sourceText)
        ) {{
            return "Matmässa";
        }}

        if (
            /mat/.test(sourceText)
            &&
            /marknad/.test(sourceText)
        ) {{
            return "Matmarknad";
        }}

        if (/mässa/.test(sourceText)) {{
            return "Övrig mässa";
        }}

        if (/marknad/.test(sourceText)) {{
            return "Lokal marknad";
        }}

        return explicit;
    }}


    /* ÖVRIGT */

    if (
        explicit
    ) {{
        return explicit;
    }}

    if (
        event.typ
        && !MAIN_CATEGORIES.includes(
            event.typ
        )
    ) {{
        return event.typ;
    }}

    return "";
}}


function populateFilters() {{
    typeFilter.innerHTML =
        '<option value="">Alla eventtyper</option>';

    MAIN_CATEGORIES.forEach(
        category => {{
            const option =
                document.createElement("option");

            option.value = category;
            option.textContent = category;

            typeFilter.appendChild(option);
        }}
    );

    updateSeriesFilter();
}}


function updateSubcategoryToggleText() {{
    const boxes = [
        ...subcategoryOptions.querySelectorAll(
            'input[type="checkbox"]'
        )
    ];

    const checked =
        boxes.filter(
            box => box.checked
        ).length;

    const total =
        boxes.length;

    if (total === 0 || checked === total) {{
        subcategoryToggle.textContent =
            "Alla underkategorier ▾";
    }} else if (checked === 0) {{
        subcategoryToggle.textContent =
            "Inga underkategorier ▾";
    }} else {{
        subcategoryToggle.textContent =
            `${{checked}} av ${{total}} underkategorier ▾`;
    }}
}}


function selectedSubcategories() {{
    return new Set(
        [
            ...subcategoryOptions.querySelectorAll(
                'input[type="checkbox"]:checked'
            )
        ].map(
            box => box.value
        )
    );
}}


function setAllSubcategories(
    checked
) {{
    subcategoryOptions
        .querySelectorAll(
            'input[type="checkbox"]'
        )
        .forEach(
            box => {{
                box.checked = checked;
            }}
        );
    rememberSubcategorySelection();
    updateSubcategoryToggleText();
    render();
}}



function eventSubcategoryColor(event) {{
    /* RUNTMIGO_SAFE_ICONPILOT_V2_COLORS */
    const runtmigoSafePilotMain =
        eventMainCategory(event);

    if (
        runtmigoSafePilotMain === "Motor & fordon"
    ) {{
        return "#111111";
    }}

    if (
        runtmigoSafePilotMain === "Häst & ridsport"
    ) {{
        return "#795548";
    }}

    /*
     * RUNTMIGO_MOTOR_HORSE_COLOR_V1
     * Samma huvudfärg inom kategorin; vit ikon kan skilja underkategorier.
     */
    const runtmigoMainForColor =
        eventMainCategory(event);

    if (
        runtmigoMainForColor === "Motor & fordon"
    ) {{
        return "#D84315";
    }}

    if (
        runtmigoMainForColor === "Häst & ridsport"
    ) {{
        return "#8D6E63";
    }}

    return (
        CATEGORY_COLORS[
            eventMainCategory(event)
        ]
        || "#202020"
    );
}}



let subcategorySelectionMode = "all";
let selectedSubcategoryKeys = new Set();
let lastSubcategoryCategory = null;


function rememberSubcategorySelection() {{
    const boxes = [
        ...subcategoryOptions.querySelectorAll(
            'input[type="checkbox"]'
        )
    ];

    selectedSubcategoryKeys =
        new Set(
            boxes
                .filter(
                    box => box.checked
                )
                .map(
                    box => box.value
                )
        );

    subcategorySelectionMode =
        (
            boxes.length > 0
            && selectedSubcategoryKeys.size
                === boxes.length
        )
            ? "all"
            : "custom";
}}


function updateSeriesFilter() {{

    const selectedCategory =
        typeFilter.value;


    if (
        selectedCategory
        !== lastSubcategoryCategory
    ) {{
        lastSubcategoryCategory =
            selectedCategory;

        /*
         * Om användaren uttryckligen har
         * avmarkerat alla underkategorier
         * ska det läget bevaras även när
         * huvudkategori byts.
         */
        const keepNoneSelected =
            (
                subcategorySelectionMode
                === "custom"
                && selectedSubcategoryKeys.size
                    === 0
            );

        if (!keepNoneSelected) {{
            subcategorySelectionMode =
                "all";

            selectedSubcategoryKeys =
                new Set();
        }}
    }}


    seriesFilter.innerHTML =
        '<option value=""></option>';

    subcategoryOptions.innerHTML =
        "";


    /*
     * Hämtar alla underkategorier för en viss huvudkategori.
     *
     * Sport är dynamiskt eftersom nya sporter kan tillkomma.
     * Övrigt är också dynamiskt eftersom den kategorin inte
     * har en fast underkategorilista.
     */
    function subcategoriesForCategory(category) {{

        const fixed =
            CATEGORY_SUBCATEGORIES[
                category
            ] || [];


        if (fixed.length > 0) {{
            return [...fixed].sort(
                (a, b) =>
                    a.localeCompare(
                        b,
                        "sv",
                        {{
                            sensitivity: "base"
                        }}
                    )
            );
        }}


        return [
            ...new Set(
                events
                    .filter(
                        event =>
                            eventMainCategory(
                                event
                            ) === category
                    )
                    .map(
                        event =>
                            eventSubcategory(
                                event
                            )
                    )
                    .filter(Boolean)
            )
        ].sort(
            (a, b) =>
                a.localeCompare(
                    b,
                    "sv"
                )
        );
    }}


    let rows = [];


    if (selectedCategory) {{

        rows =
            subcategoriesForCategory(
                selectedCategory
            )
            .map(
                subcategory => ({{
                    category:
                        selectedCategory,
                    subcategory:
                        subcategory
                }})
            );

    }} else {{

        MAIN_CATEGORIES.forEach(
            category => {{

                subcategoriesForCategory(
                    category
                ).forEach(
                    subcategory => {{

                        rows.push({{
                            category:
                                category,
                            subcategory:
                                subcategory
                        }});

                    }}
                );

            }}
        );
    }}


    /*
     * När Alla eventtyper visas grupperas listan i samma
     * ordning som huvudkategorierna. Inom varje kategori
     * används den fastställda ordningen.
     */

    let lastCategory = null;


    rows.forEach(
        row => {{

            if (
                !selectedCategory
                && row.category !== lastCategory
            ) {{

                const heading =
                    document.createElement(
                        "div"
                    );

                heading.className =
                    "subcategory-group-heading";

                heading.textContent =
                    row.category;

                subcategoryOptions.appendChild(
                    heading
                );

                lastCategory =
                    row.category;
            }}


            const label =
                document.createElement(
                    "label"
                );

            label.className =
                "subcategory-option";


            const box =
                document.createElement(
                    "input"
                );

            box.type =
                "checkbox";


            /*
             * Unik kombination av huvudkategori +
             * underkategori.
             */
            box.value =
                `${{row.category}}||${{row.subcategory}}`;

            box.checked =
                (
                    subcategorySelectionMode
                    === "all"
                )
                || selectedSubcategoryKeys.has(
                    box.value
                );


            const pin =
                document.createElement(
                    "span"
                );

            pin.className =
                "subcategory-option-dot";

            pin.style.setProperty(
                "--pin-color",
                CATEGORY_COLORS[
                    row.category
                ] || "#202020"
            );


            const symbol =
                document.createElement(
                    "span"
                );

            symbol.innerHTML =
                subcategorySymbol(
                    row.category,
                    row.subcategory
                );

            pin.appendChild(
                symbol
            );


            const text =
                document.createElement(
                    "span"
                );

            text.textContent =
                row.subcategory;


            box.addEventListener(
                "change",
                () => {{
                    rememberSubcategorySelection();
                    updateSubcategoryToggleText();
                    render();
                }}
            );


            label.appendChild(box);
            label.appendChild(pin);
            label.appendChild(text);

            subcategoryOptions.appendChild(
                label
            );
        }}
    );


    if (rows.length === 0) {{

        subcategoryToggle.disabled =
            true;

        subcategoryToggle.textContent =
            "Inga underkategorier ▾";

    }} else {{

        subcategoryToggle.disabled =
            false;

        updateSubcategoryToggleText();
    }}
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

    const chosenSubcategories =
        selectedSubcategories();

    const subcategoryBoxCount =
        subcategoryOptions.querySelectorAll(
            'input[type="checkbox"]'
        ).length;


    /*
     * Viktig regel:
     * Avmarkera alla underkategorier betyder exakt 0 event.
     */
    if (
        subcategoryBoxCount > 0
        && chosenSubcategories.size === 0
    ) {{
        return [];
    }}


    const controlledSubcategories =
        new Set(
            [
                ...subcategoryOptions.querySelectorAll(
                    'input[type="checkbox"]'
                )
            ].map(
                box => box.value
            )
        );


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
                    eventMainCategory(event)
                    !== type
                ) {{
                    return false;
                }}


                const eventSub =
                    eventSubcategory(
                        event
                    );

                const eventSubKey =
                    eventSub
                    ? (
                        `${{eventMainCategory(event)}}`
                        + `||`
                        + `${{eventSub}}`
                    )
                    : "";

                if (
                    subcategoryBoxCount > 0
                    && chosenSubcategories.size
                        < subcategoryBoxCount
                    && (
                        !eventSubKey
                        || !chosenSubcategories.has(
                            eventSubKey
                        )
                    )
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


                const eventKind =
                    eventSubcategory(event)
                    || eventMainCategory(event)
                    || event.sport
                    || event.typ
                    || "Event";


                const seriesText =
                    event.serie
                    ? `
                        <div class="arena-popup-series">
                            ${{event.serie}}
                        </div>
                    `
                    : "";


                const sourceName =
                    event.kalla
                    || "Officiell källa";


                const officialUrl =
                    event.url || "";


                const linkLabel =
                    "Officiell sida";


                const officialLink =
                    officialUrl
                    ? `
                        <div class="arena-popup-source">
                            <a
                                href="${{officialUrl}}"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                ${{linkLabel}} – ${{sourceName}} ↗
                            </a>
                        </div>
                    `
                    : "";


                const directionsUrl =
                    navigationUrl(
                        event.lat,
                        event.lon
                    );


                const directionsLink =
                    directionsUrl
                    ? `
                        <div class="arena-popup-directions">
                            <a
                                href="${{directionsUrl}}"
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                🧭 Visa mig vägen
                            </a>
                        </div>
                    `
                    : "";


                return `
                    <div class="arena-popup-event">

                        <div class="arena-popup-date">
                            ${{event.datum}}${{time}}
                        </div>

                        <div class="arena-popup-title">
                            ${{event.namn}}
                        </div>

                        <div class="arena-popup-kind">
                            ${{eventKind}}
                        </div>

                        ${{seriesText}}

                        ${{distanceText}}

                        ${{officialLink}}

                        ${{directionsLink}}

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


function navigationUrl(lat, lon) {{

    const latitude =
        Number(lat);

    const longitude =
        Number(lon);


    if (
        !Number.isFinite(latitude)
        || !Number.isFinite(longitude)
    ) {{
        return "";
    }}


    const destination =
        `${{latitude}},${{longitude}}`;


    const isAppleMobile =
        /iPhone|iPad|iPod/i.test(
            navigator.userAgent
        );


    if (isAppleMobile) {{

        return (
            "https://maps.apple.com/"
            + "?daddr="
            + encodeURIComponent(
                destination
            )
            + "&dirflg=d"
        );
    }}


    return (
        "https://www.google.com/maps/dir/"
        + "?api=1"
        + "&destination="
        + encodeURIComponent(
            destination
        )
        + "&travelmode=driving"
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

    return;


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


            const markerCategories =
                [
                    ...new Set(
                        eventsAtLocation
                            .map(
                                event =>
                                    eventMainCategory(
                                        event
                                    )
                            )
                            .filter(Boolean)
                    )
                ];


            const markerSubcategories =
                [
                    ...new Set(
                        eventsAtLocation
                            .map(
                                event =>
                                    eventSubcategory(
                                        event
                                    )
                            )
                            .filter(Boolean)
                    )
                ];


            const markerColors =
                [
                    ...new Set(
                        eventsAtLocation
                            .map(
                                event =>
                                    eventSubcategoryColor(
                                        event
                                    )
                            )
                            .filter(Boolean)
                    )
                ];


            let markerStyle = "";


            if (markerColors.length === 1) {{

                markerStyle =
                    `--marker-bg: ${{markerColors[0]}};`;

            }} else if (markerColors.length > 1) {{

                const stops =
                    markerColors
                        .map(
                            (color, index) => {{

                                const start =
                                    index
                                    * 100
                                    / markerColors.length;

                                const end =
                                    (index + 1)
                                    * 100
                                    / markerColors.length;

                                return (
                                    `${{color}} ${{start}}%, `
                                    + `${{color}} ${{end}}%`
                                );
                            }}
                        )
                        .join(", ");


                markerStyle =
                    `--marker-bg: conic-gradient(${{stops}});`;
            }}


            /* RUNTMIGO_MULTI_CATEGORY_GLOSSY_V2_4_3 */



            let markerSymbol = categorySymbol("Övrigt");


            if (
                markerCategories.length === 1
                && markerSubcategories.length === 1
            ) {{

                markerSymbol =
                    subcategorySymbol(
                        markerCategories[0],
                        markerSubcategories[0]
                    );

            }} else if (
                markerCategories.length === 1
            ) {{

                markerSymbol =
                    categorySymbol(
                        markerCategories[0]
                    );
            }}


            const countBadge =
                count > 1
                ? (
                    `<span class="arena-marker-count">`
                    + `${{count}}`
                    + `</span>`
                )
                : "";


            const icon =
                L.divIcon(
                    {{
                        className: "",

                        html:
                            (
                                `<div class="arena-marker" style="${{markerStyle}}">`
                                + `<div class="arena-marker-inner">`
                                + `<span class="arena-marker-symbol">`
                                + `${{markerSymbol}}`
                                + `</span>`
                                + `${{countBadge}}`
                                + `</div>`
                                + `</div>`
                            ),

                        iconSize: [
                            46,
                            58
                        ],

                        iconAnchor: [
                            23,
                            54
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
    () => {{
        updateSeriesFilter();
        render();
    }}
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

        applyPeriod(
            "today"
        );

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


applyPeriod("today");

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
