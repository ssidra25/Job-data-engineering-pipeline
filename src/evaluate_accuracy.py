import csv
from pathlib import Path

INPUT = Path("data/manual_evaluation_review.csv")
OUTPUT = Path("reports/field_accuracy.csv")

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


def normalize(value):
    value = str(value or "").strip().lower()

    if value in ("", "null", "none", "n/a", "not specified"):
        return None

    return "".join(value.split())


with INPUT.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

results = []

for field in FIELDS:
    correct = 0
    reviewed = 0

    for row in rows:
        extracted = normalize(row.get("extracted_" + field))
        manual = normalize(row.get("manual_" + field))

        # Skip fields that have not been manually reviewed
        if manual is None and extracted is not None:
            continue

        reviewed += 1

        if extracted == manual:
            correct += 1

    accuracy = correct / reviewed * 100 if reviewed else 0

    results.append({
        "field": field,
        "correct": correct,
        "reviewed": reviewed,
        "accuracy_percent": round(accuracy, 2),
    })

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT.open("w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["field", "correct", "reviewed", "accuracy_percent"]
    )
    writer.writeheader()
    writer.writerows(results)

print("\nFIELD-LEVEL ACCURACY\n")

for result in results:
    print(
        result["field"],
        result["correct"], "/",
        result["reviewed"],
        "=",
        result["accuracy_percent"], "%"
    )

print("\nReport saved:", OUTPUT)
