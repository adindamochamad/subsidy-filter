"""Run every extract/sql/*.sql file against BigQuery.

Dry-runs via `bq query --dry_run` first, logs byte cost, and refuses
anything estimated above MAX_BYTES_PER_QUERY. Use --dry-run-only to
stop before any billed job.
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

from google.cloud import bigquery

from classify.config import BQ_LOCATION, GCP_PROJECT, MAX_BYTES_PER_QUERY

ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "extract" / "sql"
RAW_DIR = ROOT / "data" / "raw"

# (sql filename, output csv). Order is the documented extract order.
QUERIES = (
    ("daily_activity.sql", "daily_activity.csv"),
    ("monthly_net_demand.sql", "monthly_net_demand.csv"),
    ("daily_top_receivers.sql", "daily_top_receivers.csv"),
)

OPTIONAL_QUERIES = (
    ("burst_coverage.sql", "burst_coverage.csv"),
)

ALL_NAMED = {name: csv for pair in (QUERIES + OPTIONAL_QUERIES) for name, csv in [pair]}

BYTES_RE = re.compile(r"will process ([\d,]+) bytes", re.IGNORECASE)


def _read_sql(name: str) -> str:
    path = SQL_DIR / name
    sql = path.read_text(encoding="utf-8")
    if "block_date" not in sql.split("WHERE", 1)[-1]:
        raise SystemExit(f"REFUSE: {name} has no block_date filter in WHERE")
    if re.search(r"SELECT\s+\*", sql, re.IGNORECASE):
        raise SystemExit(f"REFUSE: {name} uses SELECT *")
    return sql


def dry_run_bq(name: str, sql: str) -> int:
    """Call `bq query --dry_run` and return estimated bytes."""
    cmd = [
        "bq",
        "query",
        "--dry_run",
        "--use_legacy_sql=false",
        f"--location={BQ_LOCATION}",
        f"--project_id={GCP_PROJECT}",
        "--nouse_cache",
    ]
    print(f"\n== dry-run {name} ==", flush=True)
    print(" ".join(cmd), "<", name, flush=True)
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    print(out.strip(), flush=True)
    if proc.returncode != 0:
        raise SystemExit(f"bq dry-run failed for {name} (exit {proc.returncode})")
    match = BYTES_RE.search(out)
    if not match:
        raise SystemExit(f"Could not parse byte estimate from bq output for {name}")
    nbytes = int(match.group(1).replace(",", ""))
    gb = nbytes / 1_000_000_000
    print(f"ESTIMATE {name}: {nbytes:,} bytes ({gb:.3f} GB)", flush=True)
    if nbytes > MAX_BYTES_PER_QUERY:
        cap_gb = MAX_BYTES_PER_QUERY / 1_000_000_000
        raise SystemExit(
            f"REFUSE: {name} estimated {gb:.3f} GB > {cap_gb:.0f} GB cap. "
            "Not running. Narrow the block_date filter or drop columns."
        )
    return nbytes


def run_query(name: str, sql: str, dest: Path) -> None:
    client = bigquery.Client(project=GCP_PROJECT, location=BQ_LOCATION)
    job_config = bigquery.QueryJobConfig(use_query_cache=False)
    job = client.query(sql, job_config=job_config)
    result = job.result()
    field_names = [field.name for field in result.schema]
    dest.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with dest.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(field_names)
        for row in result:
            writer.writerow([row[name] for name in field_names])
            row_count += 1
    billed = job.total_bytes_billed or job.total_bytes_processed or 0
    print(
        f"WROTE {dest.relative_to(ROOT)} ({row_count} rows, "
        f"billed {billed:,} bytes)",
        flush=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run-only",
        action="store_true",
        help="Print byte estimates and exit. No billed query.",
    )
    parser.add_argument(
        "--only",
        metavar="SQL_FILE",
        help="Run a single extract/sql file (e.g. burst_coverage.sql).",
    )
    args = parser.parse_args()

    if args.only:
        if args.only not in ALL_NAMED:
            known = ", ".join(sorted(ALL_NAMED))
            raise SystemExit(f"Unknown --only {args.only!r}. Known: {known}")
        query_list = [(args.only, ALL_NAMED[args.only])]
    else:
        query_list = list(QUERIES)

    estimates: list[tuple[str, int]] = []
    loaded: list[tuple[str, str, Path]] = []
    for sql_name, csv_name in query_list:
        sql = _read_sql(sql_name)
        nbytes = dry_run_bq(sql_name, sql)
        estimates.append((sql_name, nbytes))
        loaded.append((sql_name, sql, RAW_DIR / csv_name))

    print("\n== dry-run summary ==", flush=True)
    total = 0
    for name, nbytes in estimates:
        print(f"  {name:28s}  {nbytes:15,} bytes  ({nbytes / 1_000_000_000:.3f} GB)")
        total += nbytes
    print(f"  {'TOTAL (if all run)':28s}  {total:15,} bytes  ({total / 1_000_000_000:.3f} GB)")

    if args.dry_run_only:
        print("\nDry-run only. No billed query was submitted.", flush=True)
        return 0

    print("\n== running queries ==", flush=True)
    for sql_name, sql, dest in loaded:
        print(f"\nSTART {sql_name} -> {dest.relative_to(ROOT)}", flush=True)
        run_query(sql_name, sql, dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
