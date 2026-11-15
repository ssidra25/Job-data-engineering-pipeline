import json
import time
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = "https://api.lever.co/v0/postings"

COMPANIES = {
    "palantir": "palantir",
    "gopuff": "gopuff",
}


def scrape_lever(company_name, site_name):

    url = f"{BASE_URL}/{site_name}"

    params = {
        "mode": "json"
    }

    headers = {
        "User-Agent": "DataEngineerTakeHome/1.0",
        "Accept": "application/json"
    }

    for attempt in range(3):

        try:
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

            jobs = response.json()

            if not isinstance(jobs, list):
                raise ValueError("Unexpected API response format")

            output = {
                "company": company_name,
                "source": "lever",
                "total_jobs": len(jobs),
                "jobs": jobs
            }

            output_file = RAW_DIR / f"lever_{company_name}.json"

            with open(output_file, "w", encoding="utf-8") as file:
                json.dump(output, file, indent=2, ensure_ascii=False)

            print(f"Company - {company_name}")
            print(f"Jobs collected - {len(jobs)}")
            print(f"Saved to - {output_file}")

            return output

        except requests.RequestException as error:
            if attempt == 2:
                raise

            time.sleep(2 ** attempt)

    raise RuntimeError(f"Could not collect jobs for {company_name}")


if __name__ == "__main__":

    for company_name, site_name in COMPANIES.items():

        try:
            scrape_lever(company_name, site_name)

        except Exception as error:
            print(f"Failed: {company_name} - {error}")