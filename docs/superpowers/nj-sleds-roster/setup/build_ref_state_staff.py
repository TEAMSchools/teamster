# docs/superpowers/nj-sleds-roster/setup/build_ref_state_staff.py
"""Project the NJ SLEDS Staff Management export down to audit columns only.

Keeps only the IDs/names/DOB/CDS slots the roster audit needs. The export's
SocialSecurityNumber column (NJSLEDS-masked, so not live PII) and all
HR/compensation fields are excluded as hygiene, not as a PII safeguard.
"""

import csv
import sys
from pathlib import Path

KEEP = [
    "LocalStaffIdentifier",
    "StaffMemberIdentifier",
    "FirstName",
    "MiddleName",
    "LastName",
    "DateofBirth",
    *[f"CountyCodeAssigned{i}" for i in range(1, 7)],
    *[f"DistrictCodeAssigned{i}" for i in range(1, 7)],
    *[f"SchoolCodeAssigned{i}" for i in range(1, 7)],
]


def main(in_path: str, out_path: str) -> None:
    with Path(in_path).open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
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
    print(f"wrote {count} staff rows ({len(KEEP)} cols, no SSN) to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
