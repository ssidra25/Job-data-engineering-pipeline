import argparse
import csv
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


INPUT_FILE = Path("data/extracted_jobs.json")
DB_FILE = Path("data/jobs.db")
CSV_FILE = Path("data/jobs_export.csv")

FIELDS = [
    "company",
    "title",
    "location",
    "country",
    "remote_status",
    "employment_type",
    "salary",
    "role_category",
    "description_summary",
    "evidence",
]

def normalize(value):
    return " ".join(str(value or "").strip().lower().split())


def make_hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def get_source_id(job):
    identity = "|".join([
        normalize(job.get("source")),
        normalize(job.get("candidate_id")),
        normalize(job.get("source_url")),
        normalize(job.get("title")),
    ])
    return make_hash(identity)


def get_matching_canonical_id(conn, job, source):
    company = normalize(job.get("company"))
    title = normalize(job.get("title"))
    location = normalize(job.get("location"))

    # Without all three fields, do not attempt cross-source deduplication.
    if not company or not title or not location:
        return None

    rows = conn.execute("""
        SELECT canonical_id, company, title, location
        FROM canonical_jobs
    """).fetchall()

    matches = []

    for canonical_id, old_company, old_title, old_location in rows:
        if (
            normalize(old_company) == company
            and normalize(old_title) == title
            and normalize(old_location) == location
        ):
            existing_sources = {
                normalize(row[0])
                for row in conn.execute(
                    "SELECT DISTINCT source FROM job_sources WHERE canonical_id = ?",
                    (canonical_id,),
                ).fetchall()
            }

            # Never merge two postings from the same source.
            if normalize(source) not in existing_sources:
                matches.append(canonical_id)

    # Merge only when there is exactly one unambiguous match.
    if len(matches) == 1:
        return matches[0]

    return None


def get_canonical_id(conn, job, source_id):
    source = job.get("source")

    # An existing source URL keeps its original canonical ID on reruns.
    existing = conn.execute(
        "SELECT canonical_id FROM job_sources WHERE source_id = ?",
        (source_id,),
    ).fetchone()

    if existing:
        return existing[0]

    matched_id = get_matching_canonical_id(conn, job, source)

    if matched_id:
        return matched_id

    # Otherwise, preserve this vacancy as its own canonical record.
    return make_hash("unique|" + source_id)


def create_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS canonical_jobs (
            canonical_id TEXT PRIMARY KEY,
            company TEXT,
            title TEXT,
            location TEXT,
            country TEXT,
            remote_status TEXT,
            employment_type TEXT,
            salary TEXT,
            role_category TEXT,
            description_summary TEXT,
            evidence TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS job_sources (
            source_id TEXT PRIMARY KEY,
            canonical_id TEXT NOT NULL,
            candidate_id TEXT,
            source TEXT,
            source_url TEXT,
            snapshot TEXT,
            first_seen TEXT,
            last_seen TEXT,
            FOREIGN KEY(canonical_id)
                REFERENCES canonical_jobs(canonical_id)
        );

        CREATE TABLE IF NOT EXISTS change_history (
            change_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL,
            changed_at TEXT NOT NULL,
            field_name TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_job_sources_canonical
        ON job_sources(canonical_id);
    """)
    conn.commit()


def save_job(conn, job, now):
    source_id = get_source_id(job)
    canonical_id = get_canonical_id(conn, job, source_id)

    values = {}

    for field in FIELDS:
        value = job.get(field)

        if field == "evidence":
            value = json.dumps(
                value or {},
                ensure_ascii=False,
                sort_keys=True,
            )

        values[field] = value

    snapshot = json.dumps(
        values,
        ensure_ascii=False,
        sort_keys=True,
    )

    previous = conn.execute("""
        SELECT snapshot, first_seen
        FROM job_sources
        WHERE source_id = ?
    """, (source_id,)).fetchone()

    first_seen = previous[1] if previous else now

    if previous:
        old_values = json.loads(previous[0])

        for field in FIELDS:
            old_value = old_values.get(field)
            new_value = values.get(field)

            if old_value != new_value:
                conn.execute("""
                    INSERT INTO change_history
                    (source_id, changed_at, field_name, old_value, new_value)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    source_id,
                    now,
                    field,
                    json.dumps(old_value, ensure_ascii=False),
                    json.dumps(new_value, ensure_ascii=False),
                ))

    columns = [
        "canonical_id",
        *FIELDS,
        "created_at",
        "updated_at",
    ]

    insert_values = [
        canonical_id,
        *[values[field] for field in FIELDS],
        now,
        now,
    ]

    update_parts = []

    for field in FIELDS:
        if field == "evidence":
            update_parts.append("""
                evidence = CASE
                    WHEN canonical_jobs.evidence IS NULL
                         OR canonical_jobs.evidence = '{}'
                    THEN excluded.evidence
                    ELSE canonical_jobs.evidence
                END
            """)
        else:
            update_parts.append(
                f"{field} = COALESCE(canonical_jobs.{field}, excluded.{field})"
            )

    update_parts.append("updated_at = excluded.updated_at")

    placeholders = ", ".join(["?"] * len(columns))
    column_sql = ", ".join(columns)
    update_sql = ", ".join(update_parts)

    conn.execute(f"""
        INSERT INTO canonical_jobs ({column_sql})
        VALUES ({placeholders})
        ON CONFLICT(canonical_id) DO UPDATE SET {update_sql}
    """, insert_values)

    conn.execute("""
        INSERT INTO job_sources (
            source_id, canonical_id, candidate_id, source,
            source_url, snapshot, first_seen, last_seen
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            snapshot = excluded.snapshot,
            last_seen = excluded.last_seen
    """, (
        source_id,
        canonical_id,
        job.get("candidate_id"),
        job.get("source"),
        job.get("source_url"),
        snapshot,
        first_seen,
        now,
    ))


def export_csv(conn):
    query = """
        SELECT
            c.canonical_id,
            c.company,
            c.title,
            c.location,
            c.country,
            c.remote_status,
            c.employment_type,
            c.salary,
            c.role_category,
            c.description_summary,
            c.evidence,
            GROUP_CONCAT(DISTINCT s.source_url) AS source_urls
        FROM canonical_jobs c
        LEFT JOIN job_sources s
            ON c.canonical_id = s.canonical_id
        GROUP BY c.canonical_id
        ORDER BY c.company, c.title
    """

    rows = conn.execute(query).fetchall()
    headers = [
        "canonical_id",
        "company",
        "title",
        "location",
        "country",
        "remote_status",
        "employment_type",
        "salary",
        "role_category",
        "description_summary",
        "evidence",
        "source_urls",
    ]

    with CSV_FILE.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)

    return len(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild database from the extracted JSON input.",
    )
    args = parser.parse_args()

    if not INPUT_FILE.exists():
        raise FileNotFoundError(f"Missing input: {INPUT_FILE}")

    with INPUT_FILE.open(encoding="utf-8") as file:
        data = json.load(file)

    jobs = data.get("jobs", data.get("Jobs", []))

    if not isinstance(jobs, list):
        raise ValueError("Expected a list under the 'jobs' key.")

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    CSV_FILE.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

        if args.rebuild:
            conn.execute("DROP TABLE IF EXISTS change_history")
            conn.execute("DROP TABLE IF EXISTS job_sources")
            conn.execute("DROP TABLE IF EXISTS canonical_jobs")
            conn.commit()

        create_tables(conn)

        processed = 0
        skipped = 0

        for job in jobs:
            if (
                not isinstance(job, dict)
                or not job.get("title")
                or not job.get("source_url")
            ):
                skipped += 1
                continue

            save_job(conn, job, now)
            processed += 1

        conn.commit()

        canonical_count = conn.execute(
            "SELECT COUNT(*) FROM canonical_jobs"
        ).fetchone()[0]

        source_count = conn.execute(
            "SELECT COUNT(*) FROM job_sources"
        ).fetchone()[0]

        history_count = conn.execute(
            "SELECT COUNT(*) FROM change_history"
        ).fetchone()[0]

        exported_count = export_csv(conn)

    print("\nDATABASE BUILD COMPLETED")
    print("Input records:", len(jobs))
    print("Processed records:", processed)
    print("Skipped records:", skipped)
    print("Canonical jobs:", canonical_count)
    print("Source records:", source_count)
    print("Change history records:", history_count)
    print("CSV rows:", exported_count)
    print("Database:", DB_FILE)
    print("CSV:", CSV_FILE)


if __name__ == "__main__":
    main()