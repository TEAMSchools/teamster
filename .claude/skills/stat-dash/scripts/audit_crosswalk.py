"""Replay every crosswalk sheet row through the tiered matcher; counts only.

Usage: uv run python audit_crosswalk.py COMPILED_SQL

COMPILED_SQL is the compiled analysis
(target/compiled/kipptaf/analyses/state_assessment_tiered_crosswalk_match.sql).
The script swaps the matcher's flagged-rows filter for every row in the live
crosswalk sheet, then compares the rules' pick with the sheet's Student_Number.
It reads the sheet external under ADC and prints aggregates only.
"""

import re
import sys
from collections import Counter
from pathlib import Path

from google.cloud import bigquery

SHEET = (
    "`teamster-332318`.`kipptaf_google_sheets`."
    "`src_google_sheets__pearson__student_crosswalk`"
)
GAPS_FILTER = re.compile(
    r"\s+where\s+a\.academic_year >= 2017\s+"
    r"and \(e\.student_number is null or a\.student_number is null\)\s*\n"
)


def build_audit(compiled: str) -> str:
    match = GAPS_FILTER.search(compiled)
    if match is None:
        raise ValueError("flagged-rows filter not found; has the analysis changed?")
    matcher = (
        compiled[: match.start()]
        + f"\n        inner join {SHEET} as xw"
        + "\n            on a.student_test_uuid = xw.Student_Test_UUID\n"
        + compiled[match.end() :]
    )
    matcher = re.sub(r"\norder by bucket[^\n]*\s*$", "\n", matcher.rstrip() + "\n")
    # trunk-ignore(bandit/B608): input is the repo's own compiled analysis
    return f"""
with
    m as ({matcher}),
    xw as (select Student_Test_UUID, Student_Number, from {SHEET})
select
    case
        when m.student_test_uuid is null then 'not_in_model'
        when m.bucket = 'resolved' and m.proposed_student_number = xw.Student_Number
        then 'agrees'
        when m.bucket = 'resolved' then 'DISAGREES'
        when m.bucket in ('ambiguous', 'flagged_for_review') then m.bucket
        else 'no_pick'
    end as outcome,
    m.tiers,
from xw
left join m on xw.Student_Test_UUID = m.student_test_uuid
"""


def main(argv: list[str]) -> int:
    sql = build_audit(Path(argv[1]).read_text())
    rows = list(bigquery.Client(project="teamster-332318").query(sql).result())
    print(len(rows), "sheet rows")
    for (outcome, tiers), n in sorted(
        Counter((r["outcome"], r["tiers"]) for r in rows).items(), key=str
    ):
        print(f"{outcome}\t{tiers or '-'}\t{n}")
    return 1 if any(r["outcome"] == "DISAGREES" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
