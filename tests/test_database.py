import sqlite3

from src.storage.database import create_tables, save_job


def make_job(source, candidate_id, url, title="Data Analyst"):
    return {
        "source": source,
        "candidate_id": candidate_id,
        "source_url": url,
        "company": "Example Company",
        "title": title,
        "location": "New York, NY",
        "country": "US",
        "remote_status": "on-site",
        "employment_type": "Full-time",
        "salary": "$100,000",
        "role_category": "data",
        "description_summary": "Analyze business data.",
        "evidence": {"title": title},
    }


def make_database(tmp_path):
    db_path = tmp_path / "test_jobs.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)
    return conn


def test_cross_source_duplicate_is_merged(tmp_path):
    conn = make_database(tmp_path)

    job1 = make_job(
        "greenhouse",
        "gh_101",
        "https://example.com/jobs/101",
    )

    job2 = make_job(
        "lever",
        "lever_202",
        "https://example.org/jobs/202",
    )

    save_job(conn, job1, "2026-11-15T10:00:00")
    save_job(conn, job2, "2026-11-15T10:01:00")
    conn.commit()

    canonical_count = conn.execute(
        "SELECT COUNT(*) FROM canonical_jobs"
    ).fetchone()[0]

    source_count = conn.execute(
        "SELECT COUNT(*) FROM job_sources"
    ).fetchone()[0]

    assert canonical_count == 1
    assert source_count == 2

    conn.close()


def test_different_vacancies_from_same_source_stay_separate(tmp_path):
    conn = make_database(tmp_path)

    job1 = make_job(
        "greenhouse",
        "gh_101",
        "https://example.com/jobs/101",
    )

    job2 = make_job(
        "greenhouse",
        "gh_102",
        "https://example.com/jobs/102",
    )

    save_job(conn, job1, "2026-11-15T10:00:00")
    save_job(conn, job2, "2026-11-15T10:01:00")
    conn.commit()

    canonical_count = conn.execute(
        "SELECT COUNT(*) FROM canonical_jobs"
    ).fetchone()[0]

    source_count = conn.execute(
        "SELECT COUNT(*) FROM job_sources"
    ).fetchone()[0]

    assert canonical_count == 2
    assert source_count == 2

    conn.close()


def test_salary_change_is_recorded(tmp_path):
    conn = make_database(tmp_path)

    job = make_job(
        "greenhouse",
        "gh_101",
        "https://example.com/jobs/101",
    )

    save_job(conn, job, "2026-11-15T10:00:00")

    updated_job = make_job(
        "greenhouse",
        "gh_101",
        "https://example.com/jobs/101",
    )
    updated_job["salary"] = "$120,000"

    save_job(conn, updated_job, "2026-11-15T11:00:00")
    conn.commit()

    changes = conn.execute("""
        SELECT field_name, old_value, new_value
        FROM change_history
    """).fetchall()

    assert len(changes) == 1
    assert changes[0][0] == "salary"
    assert changes[0][1] == '"$100,000"'
    assert changes[0][2] == '"$120,000"'

    conn.close()