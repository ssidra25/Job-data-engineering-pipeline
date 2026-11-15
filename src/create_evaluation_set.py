import csv
import json
from pathlib import Path

INPUT = Path("data/extracted_jobs.json")
OUTPUT = Path("data/manual_evaluation_review.csv")

FIELDS = [
    "company",
    "title",
    "location",
    "country",
    "remote_status",
    "employment_type",
    "salary",
    "role_category",
]

with INPUT.open(encoding="utf-8") as f:
    data = json.load(f)

jobs = data.get("jobs", data.get("Jobs", []))

if not isinstance(jobs, list):
    raise ValueError("Could not find the jobs list.")

hn_jobs = [
    job for job in jobs
    if isinstance(job, dict)
    and str(job.get("source", "")).lower() == "hackernews"
]

other_jobs = [
    job for job in jobs
    if isinstance(job, dict)
    and str(job.get("source", "")).lower() != "hackernews"
]

if len(hn_jobs) < 10 or len(other_jobs) < 10:
    raise ValueError(
        f"Not enough records: HN={len(hn_jobs)}, "
        f"other sources={len(other_jobs)}"
    )

selected = hn_jobs[:10] + other_jobs[:10]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

headers = [
    "record_number",
    "source",
    "source_url",
    "candidate_id",
    "description_summary",
    "extracted_evidence",
]

for field in FIELDS:
    headers.append("extracted_" + field)

for field in FIELDS:
    headers.append("manual_" + field)

headers.append("review_notes")

with OUTPUT.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()

    for number, job in enumerate(selected, start=1):
        row = {
            "record_number": number,
            "source": job.get("source"),
            "source_url": job.get("source_url"),
            "candidate_id": job.get("candidate_id"),
            "description_summary": job.get("description_summary"),
            "extracted_evidence": json.dumps(
                job.get("evidence") or {},
                ensure_ascii=False,
            ),
        }

        for field in FIELDS:
            row["extracted_" + field] = job.get(field)

        for field in FIELDS:
            row["manual_" + field] = ""

        row["review_notes"] = ""
        writer.writerow(row)

print("EVALUATION REVIEW FILE CREATED")
print("Hacker News records:", 10)
print("Other source records:", 10)
print("Total records:", len(selected))
print("Output:", OUTPUT)