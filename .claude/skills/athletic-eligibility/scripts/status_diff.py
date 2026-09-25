"""Compare a compiled build of int_students__athletic_eligibility to prod.

Usage: status_diff.py COMPILED_SQL OUT_TSV

Prints status transitions by quarter and band (counts only), and writes one row
per student per changed quarter to OUT_TSV. The TSV holds student names; keep it
in the session scratchpad. Runs under ADC: `uv run python status_diff.py ...`.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

from google.cloud import bigquery

PROD = "`teamster-332318.kipptaf_students.int_students__athletic_eligibility`"
RPT = "`teamster-332318.kipptaf_extracts.rpt_gsheets__athletic_eligibility`"


def build_sql(compiled_sql: str) -> str:
    quarters = "\n  union all\n".join(
        # trunk-ignore(bandit/B608): q is 1-4 from range(); no outside input
        f"  select 'Q{q}' as quarter, p.student_number, p.grade_level,"
        f" p.q{q}_ae_status as old_status, n.q{q}_ae_status as new_status"
        f" from p inner join n using (student_number)"
        for q in range(1, 5)
    )
    # trunk-ignore(bandit/B608): compiled_sql is this repo's own compiled model
    return f"""
with n as ({compiled_sql}),
p as (select * from {PROD}),
r as (select student_number, region, school, student_name from {RPT}),
d as (
{quarters}
)
select r.region, r.school, d.grade_level, d.student_number, r.student_name,
  d.quarter, d.old_status, d.new_status
from d left join r using (student_number)
where coalesce(d.old_status, '-') != coalesce(d.new_status, '-')
"""


def main(argv: list[str]) -> int:
    compiled, out = Path(argv[1]), Path(argv[2])
    client = bigquery.Client(project="teamster-332318")
    rows = [dict(r) for r in client.query(build_sql(compiled.read_text())).result()]
    with out.open("w", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(
            [
                "region",
                "school",
                "grade_level",
                "student_number",
                "student_name",
                "quarter",
                "old_status",
                "new_status",
            ]
        )
        for r in rows:
            writer.writerow(r.values())
    transitions = Counter(
        (
            r["quarter"],
            "HS" if r["grade_level"] >= 9 else "MS",
            r["old_status"] or "(blank)",
            r["new_status"] or "(blank)",
        )
        for r in rows
    )
    for (quarter, band, old, new), n in sorted(transitions.items()):
        print(f"{quarter} {band}: {old} -> {new}: {n}")
    lost = {
        r["student_number"]
        for r in rows
        if (r["new_status"] or "").startswith("Ineligible")
        and not (r["old_status"] or "Ineligible").startswith("Ineligible")
    }
    print(f"students losing eligibility in any quarter: {len(lost)}")
    print(f"wrote {len(rows)} rows to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
