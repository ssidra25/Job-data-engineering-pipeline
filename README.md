# Job Postings Data Engineering Pipeline

## 1. Project Overview

This project implements a data engineering pipeline that collects job postings from multiple sources, filters relevant opportunities, extracts structured information using an LLM, and stores the results in a SQLite database.

The pipeline focuses on Data, Machine Learning, Analytics, and Platform Engineering roles located in the United States, including eligible US-remote positions.

## 2. Data Sources

The pipeline collects job postings from three sources:

| Source | Collection Method |
|---|---|
| Greenhouse | Public job board API |
| Lever | Public job postings API |
| Hacker News | Playwright browser-based collection |

### Source-specific notes

- Greenhouse: Collected postings from Stripe, Airbnb, Databricks, and Figma.
- Lever: Collected postings from Palantir and GoPuff. Plaid returned HTTP 404, so GoPuff was used as a substitute.
- Hacker News: Collected comments from the November 2026 hiring thread.

## 3. Pipeline Architecture

The pipeline consists of the following stages:

1. **Data Collection:** Collect raw job postings from Greenhouse, Lever, and Hacker News.
2. **Raw Data Storage:** Save collected responses as JSON files.
3. **Candidate Preparation:** Filter postings for relevant technical and analytical roles and US location requirements.
4. **LLM Extraction:** Use Gemini 3.5 Flash-Lite to extract structured job information.
5. **Data Validation:** Validate extracted records using structured fields and Pydantic.
6. **Deduplication:** Identify matching postings and maintain canonical job records with their source references.
7. **Change Tracking:** Record changes to job information over time.
8. **Database Storage:** Store canonical jobs and source records in SQLite.
9. **CSV Export:** Export structured job records for analysis.

## 4. Technologies Used

- Python
- SQLite
- Pydantic
- Google Gemini API
- Playwright
- Requests
- BeautifulSoup
- Pytest
- CSV and JSON

## 5. Extraction Results

| Metric | Result |
|---|---:|
| Raw postings collected | 3,481 |
| Candidate postings prepared | 156 |
| Candidates processed by LLM | 156 |
| Successfully extracted jobs | 130 |
| Canonical jobs in database | 130 |
| Source records in database | 130 |

## 6. LLM Extraction Cost

The extraction pipeline used Gemini 3.5 Flash-Lite.

- Input tokens: 229,541
- Output tokens: 36,529
- Total tokens: 266,070
- Estimated total API cost: $0.16018
- Estimated cost per extracted job: $0.00123

Detailed calculations are available in:

`reports/llm_cost_analysis.md`

## 7. Manual Evaluation

A sample of 20 extracted job records was manually checked against the original postings.

The sample included:
- 10 Hacker News records
- 10 records from other sources

Eight fields were evaluated:

- Company
- Title
- Location
- Country
- Remote status
- Employment type
- Salary
- Role category

The reported field-level accuracy was 100% across the 160 evaluated fields.

Detailed results are available in:

`reports/field_accuracy.csv`

## 8. Database and Output Files

The pipeline uses SQLite for structured storage.

Important output files:

| File | Description |
|---|---|
| `data/jobs.db` | SQLite database |
| `data/jobs_export.csv` | Structured job export |
| `data/extracted_jobs.json` | LLM extraction output |
| `data/candidates.json` | Filtered candidate postings |
| `reports/field_accuracy.csv` | Manual evaluation results |
| `reports/llm_cost_analysis.md` | LLM cost analysis |

## 9. Testing

Pytest is used to test important database functionality.

The current database tests cover:

- Cross-source duplicate merging
- Keeping different vacancies from the same source separate
- Recording salary changes in change history

Test command:

```bash
python -m pytest tests/test_database.py -v
```

## 10. Limitations and Future Improvements

- Expand source coverage to additional job boards.
- Improve extraction accuracy for salary and employment type.
- Add more comprehensive pagination for Hacker News collection.
- Expand the manually labeled evaluation dataset.
- Improve automated monitoring and change detection.
- Optimize the pipeline for larger weekly ingestion volumes.

