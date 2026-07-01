# docs/superpowers/nj-sleds-roster/setup/build_ref_state_student.py
"""Project the NJ SLEDS Student Submission export down to audit columns only.

Keeps only the IDs/names/DOB/attending-CDS/grade the course-roster audit needs
(for the student combination-error check and CDS cross-reference). All the
demographic and program fields the export carries -- race, gender, FRL, SPED,
homeless, health, language, etc. -- are dropped: the roster audit never needs
them and they should not land in BigQuery.
"""

import csv
import sys
from pathlib import Path

KEEP = [
    "LocalIdentificationNumber",
    "StateIdentificationNumber",
    "FirstName",
    "MiddleName",
    "LastName",
    "GenerationCodeSuffix",
    "DateOfBirth",
    "CountyCodeAttending",
    "DistrictCodeAttending",
    "SchoolCodeAttending",
    "GradeLevel",
]


def main(in_path: str, out_path: str) -> None:
    with Path(in_path).open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise SystemExit("export file is empty or has no header row")
        missing = [c for c in KEEP if c not in reader.fieldnames]
        if missing:
            raise SystemExit(f"export is missing expected columns: {missing}")
        count = 0
        with Path(out_path).open("w", newline="", encoding="utf-8") as out:
            writer = csv.DictWriter(out, fieldnames=KEEP, extrasaction="ignore")
            writer.writeheader()
            for row in reader:
                writer.writerow({c: row[c] for c in KEEP})
                count += 1
    print(f"wrote {count} student rows ({len(KEEP)} cols, audit-only) to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
