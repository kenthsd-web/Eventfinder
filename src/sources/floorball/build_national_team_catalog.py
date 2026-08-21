import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).resolve().parents[3]
OUT = BASE_DIR / "data" / "floorball_national_teams.json"

SERIES = {
    "Allsvenskan Dam Norra": 44031,
    "Allsvenskan Dam Södra": 44032,
    "Allsvenskan Herr": 44034,
    "Division 1 Herr Mellersta": 44037,
    "Division 1 Herr Norra": 44041,
    "Division 1 Herr Södra Götaland": 44039,
    "Division 1 Herr Södra Svealand": 44036,
    "Division 1 Herr Västra Götaland": 44038,
    "Division 1 Herr Östra": 44035,
}

SEASON = 44


def main():
    result = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for serie, competition_id in SERIES.items():
            page = browser.new_page()

            target = (
                "https://api.innebandy.se/v2/api/"
                f"competitions/{competition_id}/standings"
            )

            captured = []

            def handle_response(response):
                if response.url == target:
                    try:
                        captured.append(response.json())
                    except Exception:
                        pass

            page.on("response", handle_response)

            page.goto(
                "https://stats.innebandy.se/"
                f"sasong/{SEASON}/serie/{competition_id}/serietabell",
                wait_until="networkidle",
                timeout=60000,
            )

            page.wait_for_timeout(1000)

            if not captured:
                print(f"{serie}: INGEN DATA")
                page.close()
                continue

            data = captured[-1]
            rows = data.get("StandingsRows", [])

            teams = sorted({
                row.get("TeamName", "").strip()
                for row in rows
                if row.get("TeamName")
            })

            result[serie] = teams

            print(f"{serie}: {len(teams)} lag")
            for team in teams:
                print("  ", team)

            page.close()

        browser.close()

    OUT.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print("KLART")
    print("Fil:", OUT)


if __name__ == "__main__":
    main()
