import json
import re
from pathlib import Path

RAW_DIR = Path("raw")
OUTPUT_FILE = Path("data/candidates.json")

ROLE_PATTERN = re.compile(
    r"\b(data|analytics|analyst|machine learning|"
    r"ML engineer|AI engineer|data scientist|"
    r"data engineer|analytics engineer|"
    r"platform engineer|business intelligence|"
    r"BI engineer|MLOps|data platform)\b",
    re.IGNORECASE
)

US_PATTERN = re.compile(
    r"\b(United States|USA|U\.S\.A\.|U\.S\.|US)\b"
    r"|,\s*(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|"
    r"IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|"
    r"NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|"
    r"SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b",
    re.IGNORECASE
)


def has_role_keyword(text):
    return bool(ROLE_PATTERN.search(str(text or "")))


def has_us_location(text):
    return bool(US_PATTERN.search(str(text or "")))


candidates = []


# -------------------------
# GREENHOUSE
# -------------------------

for path in RAW_DIR.glob("greenhouse_*.json"):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for job in data.get("jobs", []):
        title = job.get("title", "")

        location_parts = []

        location = job.get("location", {})
        if isinstance(location, dict):
            location_parts.append(location.get("name", ""))

        for office in job.get("offices", []):
            if isinstance(office, dict):
                location_parts.append(office.get("name", ""))
                location_parts.append(office.get("location", ""))

        location_text = " ".join(
            str(part) for part in location_parts if part
        )

        if has_role_keyword(title) and has_us_location(location_text):
            candidates.append({
                "source": "greenhouse",
                "source_file": path.name,
                "source_id": str(job.get("id", "")),
                "company": job.get("company_name", ""),
                "title": title,
                "location": location_text,
                "url": job.get("absolute_url", ""),
                "description": job.get("content", ""),
                "raw_record": job
            })


# -------------------------
# LEVER
# -------------------------

for path in RAW_DIR.glob("lever_*.json"):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for job in data.get("jobs", []):
        title = job.get("text", "")
        country = job.get("country", "")
        categories = job.get("categories", {})

        location_text = ""
        if isinstance(categories, dict):
            location_text = str(categories.get("location", ""))

        if country.upper() == "US" and has_role_keyword(title):
            candidates.append({
                "source": "lever",
                "source_file": path.name,
                "source_id": str(job.get("id", "")),
                "company": path.stem.replace("lever_", ""),
                "title": title,
                "location": location_text,
                "url": job.get("hostedUrl", ""),
                "description": job.get("descriptionPlain", ""),
                "raw_record": job
            })


# -------------------------
# HACKER NEWS
# -------------------------

for path in RAW_DIR.glob("hackernews_*.json"):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    for comment in data.get("comments", []):
        text = comment.get("text", "")

        # Check the beginning of the comment for role and location clues.
        header = text[:700]

        if has_role_keyword(header) and has_us_location(header):
            candidates.append({
                "source": "hackernews",
                "source_file": path.name,
                "source_id": str(comment.get("comment_id", "")),
                "company": "",
                "title": "",
                "location": header[:500],
                "url": comment.get("source_url", ""),
                "description": text,
                "raw_record": comment
            })


OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(candidates, f, ensure_ascii=False, indent=2)


print("=" * 50)
print("PRELIMINARY FILTER RESULTS")
print("=" * 50)

for source in ["greenhouse", "lever", "hackernews"]:
    count = sum(1 for item in candidates if item["source"] == source)
    print(f"{source}: {count}")

print("-" * 50)
print("TOTAL CANDIDATES:", len(candidates))
print("Saved to:", OUTPUT_FILE)
