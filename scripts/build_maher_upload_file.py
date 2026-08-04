#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Build a Salesforce Data Loader insert file for new Maher Fund disbursements.

Takes a disbursement roster (one row per award) and produces a load-ready CSV of
records that are NOT already in Salesforce, deduped against a live export of the
`stg_kippadb__kipp_aid` staging model. Every new record carries the
regexp-extractable `[MAHER_FUND|v1|type=...|doc=...]` marker tag appended to its
notes, so the round-trip (insert -> Airbyte sync -> staging parse) populates
`is_maher` / `fund_type` / `doc_type` automatically.

PII stays local: this writes student names/IDs/amounts only to local CSVs. Never
copy its output into a PR, issue, comment, or any external surface.

Defaults match the "Collab Roster" export schema (Salesforce ID given directly,
so no name resolution is needed). Override the --*-col flags for a roster with
different headers.

Workflow (see the `building-maher-upload-files` skill for the full runbook):
  1. Get the candidate student IDs:
        uv run scripts/build_maher_upload_file.py --input roster.csv --print-students
  2. Query LIVE staging for those students' existing Maher (student, amount)
     pairs and save as a 2-column CSV `student,amount` (the dedup export).
  3. Build the upload files (named <object>_<operation>_<yyyymmdd>.csv):
        uv run scripts/build_maher_upload_file.py \
            --input roster.csv \
            --existing-pairs existing_pairs.csv \
            --out-new   .claude/scratch/maher/kipp_aid__c_add_20260709.csv \
            --out-existing .claude/scratch/maher/kipp_aid__c_skip_20260709.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Salesforce picklist defaults — every Maher disbursement loads as Other/Approved.
DEFAULT_TYPE = "Other"
DEFAULT_STATUS = "Approved"
FUND_TYPES = {"Emergency", "Enrichment", "Unclassified"}

OUTPUT_COLUMNS = [
    "student__c",
    "amount__c",
    "date__c",
    "type__c",
    "status__c",
    "notes__c",
    "ref_student_name",
    "ref_school_year",
    "ref_funding_type",
    "ref_reason",
    "ref_project_code",
]

# Accepted source date formats, tried in order; output is always ISO (YYYY-MM-DD).
_DATE_FORMATS = ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d")


def parse_amount(raw: str | None) -> float | None:
    """'$1,234.50' / '1234.5' -> 1234.50; blanks / junk -> None."""
    if raw is None:
        return None
    s = raw.strip().replace("$", "").replace(",", "").replace('"', "")
    if s in ("", "None", "N/A", "#REF!", "-"):
        return None
    try:
        return round(float(s), 2)
    except ValueError:
        return None


def parse_date(raw: str | None) -> str | None:
    """Normalize a source date to ISO YYYY-MM-DD; None if unparseable/blank."""
    if not raw or not raw.strip():
        return None
    s = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def normalize_fund_type(raw: str | None) -> str:
    """Map the source Type column to an Emergency/Enrichment/Unclassified value."""
    if not raw or not raw.strip():
        return "Unclassified"
    t = raw.strip().title()
    return t if t in FUND_TYPES else "Unclassified"


def build_tag(fund_type: str, doc: str, version: str) -> str:
    """The bounded, versioned marker tag buried in notes__c."""
    return f"[MAHER_FUND|{version}|type={fund_type}|doc={doc}]"


def build_notes(reason: str, tag: str) -> str:
    """Original reason verbatim, blank line, then the tag on its own line."""
    reason = (reason or "").strip()
    return f"{reason}\n\n{tag}" if reason else tag


def dedup_key(student: str, amount: float) -> tuple[str, float]:
    return (student.strip(), round(amount, 2))


def load_existing_pairs(path: Path) -> set[tuple[str, float]]:
    """Load the live-staging dedup export: a CSV with columns student,amount."""
    pairs: set[tuple[str, float]] = set()
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        cols = {c.lower(): c for c in (reader.fieldnames or [])}
        s_col = cols.get("student") or cols.get("student__c")
        a_col = cols.get("amount") or cols.get("amount__c")
        if not s_col or not a_col:
            sys.exit(
                f"--existing-pairs {path} must have 'student' and 'amount' columns; "
                f"found {reader.fieldnames}"
            )
        for row in reader:
            amt = parse_amount(row[a_col])
            if row[s_col].strip() and amt is not None:
                pairs.add(dedup_key(row[s_col], amt))
    return pairs


def read_rows(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def require_col(rows: list[dict], col: str, flag: str) -> None:
    if rows and col not in rows[0]:
        sys.exit(
            f"column {col!r} (from {flag}) not found in input; "
            f"available columns: {list(rows[0].keys())}"
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True, type=Path, help="source roster CSV")
    p.add_argument(
        "--existing-pairs",
        type=Path,
        help="dedup export from live staging: CSV with columns student,amount",
    )
    p.add_argument(
        "--no-dedup",
        action="store_true",
        help="skip dedup (treat every row as new) — emits a loud warning",
    )
    p.add_argument(
        "--out-new",
        type=Path,
        default=None,
        help="records to insert (default: kipp_aid__c_add_<yyyymmdd>.csv)",
    )
    p.add_argument(
        "--out-existing",
        type=Path,
        default=None,
        help="records already in Salesforce (default: kipp_aid__c_skip_<yyyymmdd>.csv)",
    )
    p.add_argument(
        "--print-students",
        action="store_true",
        help="print distinct student IDs from --input (for the dedup query) and exit",
    )
    p.add_argument("--tag-version", default="v1")
    p.add_argument("--type-value", default=DEFAULT_TYPE, help="type__c picklist value")
    p.add_argument(
        "--status-value", default=DEFAULT_STATUS, help="status__c picklist value"
    )
    # Column mapping — defaults match the Collab Roster export schema.
    p.add_argument("--id-col", default="Salesforce ID")
    p.add_argument("--amount-col", default="Total Disbursement")
    p.add_argument("--date-col", default="Approval Date")
    p.add_argument("--type-col", default="Type")
    p.add_argument("--doc-col", default="Project Code")
    p.add_argument("--reason-col", default="1st Reason for Funding")
    p.add_argument("--year-col", default="FiscalYear")
    p.add_argument("--first-name-col", default="Alumni First Name")
    p.add_argument("--last-name-col", default="Alumni Last Name")
    args = p.parse_args(argv)

    # Upload artifacts follow <object>_<operation>_<yyyymmdd>.csv.
    today = datetime.now().strftime("%Y%m%d")
    if args.out_new is None:
        args.out_new = Path(f"kipp_aid__c_add_{today}.csv")
    if args.out_existing is None:
        args.out_existing = Path(f"kipp_aid__c_skip_{today}.csv")

    rows = read_rows(args.input)
    if not rows:
        sys.exit(f"no rows in {args.input}")
    require_col(rows, args.id_col, "--id-col")
    require_col(rows, args.amount_col, "--amount-col")

    if args.print_students:
        seen = []
        for r in rows:
            sid = (r.get(args.id_col) or "").strip()
            if sid and sid not in seen:
                seen.append(sid)
        print("\n".join(seen))
        return 0

    if args.no_dedup:
        existing: set[tuple[str, float]] = set()
        print("WARNING: --no-dedup set; every row treated as NEW (no SF dedup).")
    elif args.existing_pairs:
        existing = load_existing_pairs(args.existing_pairs)
    else:
        sys.exit("provide --existing-pairs <dedup export> or --no-dedup explicitly")

    new_records: list[dict] = []
    already: list[dict] = []
    skipped_no_id: list[dict] = []
    skipped_no_amount: list[dict] = []
    fund_counts: Counter = Counter()

    for r in rows:
        sid = (r.get(args.id_col) or "").strip()
        amt = parse_amount(r.get(args.amount_col))
        if not sid:
            skipped_no_id.append(r)
            continue
        if amt is None:
            skipped_no_amount.append(r)
            continue

        fund_type = normalize_fund_type(r.get(args.type_col))
        doc = (r.get(args.doc_col) or "").strip()
        reason = (r.get(args.reason_col) or "").strip()
        first = (r.get(args.first_name_col) or "").strip()
        last = (r.get(args.last_name_col) or "").strip()
        record = {
            "student__c": sid,
            "amount__c": f"{amt:.2f}",
            "date__c": parse_date(r.get(args.date_col)) or "",
            "type__c": args.type_value,
            "status__c": args.status_value,
            "notes__c": build_notes(
                reason, build_tag(fund_type, doc, args.tag_version)
            ),
            "ref_student_name": f"{first} {last}".strip(),
            "ref_school_year": (r.get(args.year_col) or "").strip(),
            "ref_funding_type": fund_type,
            "ref_reason": reason,
            "ref_project_code": doc,
        }
        if dedup_key(sid, amt) in existing:
            already.append(record)
        else:
            new_records.append(record)
            fund_counts[fund_type] += 1

    def write(path: Path, records: list[dict]) -> None:
        with path.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            w.writeheader()
            w.writerows(records)

    write(args.out_new, new_records)
    write(args.out_existing, already)

    total_amt = sum(float(rec["amount__c"]) for rec in new_records)
    print(f"input rows:         {len(rows)}")
    print(f"new (upload):       {len(new_records)}  -> {args.out_new}")
    print(f"already in SF:      {len(already)}  -> {args.out_existing}")
    if skipped_no_id:
        print(f"skipped (no SF ID): {len(skipped_no_id)}")
    if skipped_no_amount:
        print(f"skipped (no amount):{len(skipped_no_amount)}")
    print(f"funding_type (new): {dict(fund_counts)}")
    print(f"amount total (new): ${total_amt:,.2f}")
    if fund_counts.get("Unclassified"):
        print(
            "NOTE: some new records are Unclassified — confirm the source Type "
            "column before loading."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
