import json
import time
from pathlib import Path

import requests


# Project root: DataEngineer
PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

COMPANIES = {
    "stripe": "stripe",
    "airbnb": "airbnb",
    "databricks": "databricks",
    "figma": "figma",
}


def scrape_greenhouse(company_name, board_token):
    """Fetch and save one company's public Greenhouse job board."""

    url = f"{BASE_URL}/{board_token}/jobs"
    params = {"content": "true"}

    headers = {
        "User-Agent": "DataEngineerTakeHome/1.0"
    }

    for attempt in range(3):
        try:
            print(f"\nFetching jobs for {company_name}...")

            response = requests.get(
                url,
                params=params,
                headers=headers,
                timeout=30
            )

            if response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"Rate limited. Waiting {wait_time} seconds.")
                time.sleep(wait_time)
                continue

            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if "json" not in content_type:
                raise ValueError(
                    f"Expected JSON but received: {content_type}"
                )

            data = response.json()

            if not isinstance(data, dict):
                raise ValueError("Unexpected API response format.")

            jobs = data.get("jobs")

            if not isinstance(jobs, list):
                raise ValueError("The response does not contain a jobs list.")

            output_file = RAW_DIR / f"greenhouse_{company_name}.json"

            with output_file.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=4, ensure_ascii=False)

            print(f"Company: {company_name}")
            print(f"Jobs collected: {len(jobs)}")
            print(f"Saved to: {output_file}")

            return data

        except (requests.RequestException, ValueError) as error:
            print(f"Attempt {attempt + 1} failed: {error}")

            if attempt < 2:
                time.sleep(2 ** attempt)

    print(f"Failed to scrape {company_name}.")
    return None

if __name__ == "__main__":
    for company_name, board_token in COMPANIES.items():
        try:
            scrape_greenhouse(company_name, board_token)
        except Exception as error:
            print(f"Failed: {company_name} - {error}")