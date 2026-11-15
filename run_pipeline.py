import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def run_step(name, command):
    print(f"\n{'=' * 60}", flush=True)
    print(f"STARTING: {name}", flush=True)
    print(f"{'=' * 60}", flush=True)

    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=True
    )

    print(f"\nCOMPLETED: {name}", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Run the job data engineering pipeline."
    )

    parser.add_argument(
        "--skip-scraping",
        action="store_true",
        help="Use existing raw JSON files instead of scraping."
    )

    args = parser.parse_args()

    if not args.skip_scraping:
        scraper_steps = [
            ("Greenhouse scraping", "src/scrapers/greenhouse.py"),
            ("Lever scraping", "src/scrapers/lever.py"),
            ("Hacker News scraping", "src/scrapers/hackernews.py"),
        ]

        for name, script in scraper_steps:
            run_step(name, [sys.executable, script])
    else:
        print("Skipping scraping. Using existing raw files.")

    required_raw_files = [
        "greenhouse_airbnb.json",
        "greenhouse_databricks.json",
        "greenhouse_figma.json",
        "greenhouse_stripe.json",
        "lever_gopuff.json",
        "lever_palantir.json",
        "hackernews_2026-11.json",
    ]

    missing = [
        filename
        for filename in required_raw_files
        if not (PROJECT_ROOT / "raw" / filename).exists()
    ]

    if missing:
        raise FileNotFoundError(
            "Missing raw files: " + ", ".join(missing)
        )

    run_step(
        "Candidate preparation",
        [sys.executable, "prepare_candidates.py"]
    )

    run_step(
        "Gemini job extraction",
        [sys.executable, "extract_jobs.py"]
    )

    run_step(
        "Database and CSV export",
        [sys.executable, "src/storage/database.py"]
    )

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETED SUCCESSFULLY")
    print("=" * 60)
    print("Database: data/jobs.db")
    print("CSV export: data/jobs_export.csv")
    print("Extracted jobs: data/extracted_jobs.json")


if __name__ == "__main__":
    main()