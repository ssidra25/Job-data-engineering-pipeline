import json
import re
import time
import requests

from pathlib import Path
from typing import Optional, Literal
from pydantic import BaseModel, Field


# ==========================================
# 1. PATHS AND SETTINGS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = BASE_DIR / "data" / "candidates.json"
OUTPUT_FILE = BASE_DIR / "data" / "extracted_jobs.json"
ERROR_FILE = BASE_DIR / "reports" / "extraction_errors.txt"

MODEL = "gemini-3.5-flash-lite"
BATCH_SIZE = 5
MAX_RETRIES = 3


# ==========================================
# 2. PYDANTIC SCHEMAS
# ==========================================

class ExtractedJob(BaseModel):
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None

    remote_status: Literal[
        "remote",
        "hybrid",
        "on-site",
        "unknown"
    ] = "unknown"

    employment_type: Optional[str] = None
    salary: Optional[str] = None

    role_category: Literal[
        "data",
        "analytics",
        "machine_learning",
        "platform_engineering"
    ]

    description_summary: Optional[str] = None

    evidence: dict[str, Optional[str]] = Field(
        default_factory=dict
    )


class CandidateResult(BaseModel):
    candidate_id: str
    jobs: list[ExtractedJob] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    results: list[CandidateResult]


# ==========================================
# 3. LOAD API KEY
# ==========================================

env_file = BASE_DIR / ".env"

if not env_file.exists():
    raise FileNotFoundError(".env file not found")

api_key = None

for line in env_file.read_text(
    encoding="utf-8"
).splitlines():

    if line.startswith("GEMINI_API_KEY="):
        api_key = line.split("=", 1)[1].strip()
        break

if not api_key:
    raise ValueError("GEMINI_API_KEY missing from .env")


API_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{MODEL}:generateContent"
)


# ==========================================
# 4. LOAD CANDIDATES AND EXISTING PROGRESS
# ==========================================

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"Candidate file not found: {INPUT_FILE}"
    )

with open(INPUT_FILE, encoding="utf-8") as f:
    candidates = json.load(f)

OUTPUT_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

ERROR_FILE.parent.mkdir(
    parents=True,
    exist_ok=True
)

if OUTPUT_FILE.exists():

    state = json.loads(
        OUTPUT_FILE.read_text(encoding="utf-8")
    )

else:

    state = {
        "processed_candidate_ids": [],
        "jobs": [],
        "input_tokens": 0,
        "output_tokens": 0
    }


processed = set(state["processed_candidate_ids"])


# ==========================================
# 5. PREPARE REMAINING CANDIDATES
# ==========================================

remaining = []

for item in candidates:

    candidate_id = (
        f'{item["source"]}:'
        f'{item["source_file"]}:'
        f'{item["source_id"]}'
    )

    if candidate_id not in processed:

        remaining.append(
            (candidate_id, item)
        )


# ==========================================
# 6. GEMINI EXTRACTION FUNCTION
# ==========================================

def extract_batch(batch):

    records = []

    for candidate_id, item in batch:

        records.append({
            "candidate_id": candidate_id,
            "source": item["source"],
            "company_hint": item.get("company", ""),
            "title_hint": item.get("title", ""),
            "location_hint": item.get("location", ""),
            "source_url": item.get("url", ""),
            "posting_text": str(
                item.get("description", "")
            )[:12000]
        })


    prompt = """
You are a strict job posting extraction system.

TASK:
Extract eligible jobs from the supplied records.

ELIGIBILITY:
1. Include only data, analytics, machine learning,
   or platform engineering roles.
2. The job must be located in the United States
   or explicitly remote within the United States.
3. Exclude jobs located outside the United States.
4. Do not assume a job is US-based because the
   company is American.
5. Hacker News comments may contain multiple jobs.
   Extract each eligible role separately.
6. Do not invent missing information.
7. Use null when information is not stated.
8. Return an empty jobs list when no eligible job exists.

EVIDENCE:
1. Provide a short exact supporting text snippet
   for every non-null extracted field.
2. Never invent evidence.
3. Evidence values may be null if no supporting
   snippet is available.

ROLE CATEGORY:
Choose exactly one:
data, analytics, machine_learning,
platform_engineering

REMOTE STATUS:
Choose exactly one:
remote, hybrid, on-site, unknown

Return valid JSON only.

Use this exact structure:

{
  "results": [
    {
      "candidate_id": "exact input candidate ID",
      "jobs": [
        {
          "company": null,
          "title": null,
          "location": null,
          "country": "US",
          "remote_status": "unknown",
          "employment_type": null,
          "salary": null,
          "role_category": "data",
          "description_summary": null,
          "evidence": {}
        }
      ]
    }
  ]
}

IMPORTANT:
- Include exactly one result for every input candidate.
- Preserve the exact candidate_id.
- Do not include markdown.
- Do not include explanations.
- Do not add trailing commas.

INPUT RECORDS:

""" + json.dumps(
        records,
        ensure_ascii=False
    )


    # --------------------------------------
    # API REQUEST WITH RETRIES
    # --------------------------------------

    response = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            response = requests.post(
                API_URL,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "contents": [{
                        "parts": [{
                            "text": prompt
                        }]
                    }],
                    "generationConfig": {
                        "temperature": 0,
                        "responseMimeType": "application/json"
                    }
                },
                timeout=120
            )

            response.raise_for_status()
            break

        except requests.RequestException:

            if attempt == MAX_RETRIES:
                raise

            wait_seconds = 10 * attempt

            print(
                f"API retry {attempt}/{MAX_RETRIES}. "
                f"Waiting {wait_seconds} seconds..."
            )

            time.sleep(wait_seconds)


    # --------------------------------------
    # PARSE GEMINI RESPONSE
    # --------------------------------------

    result = response.json()

    output_text = (
        result["candidates"][0]
        ["content"]["parts"][0]["text"]
    )

    # Remove trailing commas before closing
    # JSON objects and arrays.

    cleaned_text = re.sub(
        r",\s*([}\]])",
        r"\1",
        output_text
    )

    parsed_json = json.loads(cleaned_text)

    parsed = ExtractionResponse.model_validate(
        parsed_json
    )

    # --------------------------------------
    # VERIFY ALL CANDIDATE IDS
    # --------------------------------------

    expected_ids = {
        candidate_id
        for candidate_id, item in batch
    }

    returned_ids = [
        result.candidate_id
        for result in parsed.results
    ]

    if len(returned_ids) != len(set(returned_ids)):
        raise ValueError(
            "Gemini returned duplicate candidate IDs"
        )

    if set(returned_ids) != expected_ids:
        raise ValueError(
            "Gemini response candidate IDs do not "
            "match the input batch"
        )

    usage = result.get("usageMetadata", {})

    input_tokens = usage.get(
        "promptTokenCount", 0
    )

    output_tokens = usage.get(
        "candidatesTokenCount", 0
    )

    return parsed, input_tokens, output_tokens


# ==========================================
# 7. PROCESS BATCHES
# ==========================================

print("=" * 50)
print("GEMINI JOB EXTRACTION")
print("=" * 50)

print("Total candidates:", len(candidates))
print("Already processed:", len(processed))
print("Remaining:", len(remaining))


for start in range(
    0,
    len(remaining),
    BATCH_SIZE
):

    batch = remaining[
        start:start + BATCH_SIZE
    ]

    batch_number = (
        start // BATCH_SIZE + 1
    )

    total_batches = (
        len(remaining) + BATCH_SIZE - 1
    ) // BATCH_SIZE

    print(
        f"\nProcessing batch "
        f"{batch_number} of {total_batches}"
    )

    try:

        extracted, input_tokens, output_tokens = (
            extract_batch(batch)
        )

        batch_jobs = []

        for candidate_result in extracted.results:

            original_item = next(
                item
                for candidate_id, item in batch
                if candidate_id ==
                candidate_result.candidate_id
            )

            for job in candidate_result.jobs:

                job_data = job.model_dump()

                batch_jobs.append({

                    "candidate_id":
                        candidate_result.candidate_id,

                    "source":
                        original_item["source"],

                    "source_url":
                        original_item.get("url", ""),

                    **job_data
                })


        # Save only after the whole batch validates.

        state["jobs"].extend(batch_jobs)

        for candidate_id, item in batch:

            state["processed_candidate_ids"].append(
                candidate_id
            )

            processed.add(candidate_id)


        state["input_tokens"] += input_tokens
        state["output_tokens"] += output_tokens

        OUTPUT_FILE.write_text(
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        print("Batch completed.")
        print("Jobs extracted:", len(state["jobs"]))
        print(
            "Processed candidates:",
            len(state["processed_candidate_ids"])
        )


    except Exception as error:

        with open(
            ERROR_FILE,
            "a",
            encoding="utf-8"
        ) as f:

            f.write(
                f"Batch starting at {start}: "
                f"{repr(error)}\n"
            )

        print("Batch failed:", repr(error))
        print("Moving to next batch.")


    time.sleep(2)


# ==========================================
# 8. FINAL SUMMARY
# ==========================================

print("\n" + "=" * 50)
print("EXTRACTION SUMMARY")
print("=" * 50)

print(
    "Total candidates:",
    len(candidates)
)

print(
    "Processed candidates:",
    len(state["processed_candidate_ids"])
)

print(
    "Remaining candidates:",
    len(candidates) -
    len(state["processed_candidate_ids"])
)

print(
    "Extracted jobs:",
    len(state["jobs"])
)

print(
    "Input tokens:",
    state["input_tokens"]
)

print(
    "Output tokens:",
    state["output_tokens"]
)

print(
    "Output file:",
    OUTPUT_FILE
)

print(
    "Error log:",
    ERROR_FILE
)
