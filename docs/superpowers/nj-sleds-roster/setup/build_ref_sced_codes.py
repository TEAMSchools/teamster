# docs/superpowers/nj-sleds-roster/setup/build_ref_sced_codes.py
"""Flatten the NJSLEDS SCED xlsx (two code sheets) into one CSV for BigQuery."""

import csv
import sys
from pathlib import Path

import openpyxl

SHEETS = {
    "Prior-to-Secondary Codes": "prior_to_secondary",
    "Secondary Codes": "secondary",
}
HEADER_ROW = 5  # codes start on row 6; row 5 is the header


def main(xlsx_path: str, out_path: str) -> None:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    rows: list[tuple[str, ...]] = []
    for sheet_name, level in SHEETS.items():
        ws = wb[sheet_name]
        for r in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
            sced_code, subject_area, course_identifier = r[0], r[1], r[2]
            if subject_area is None or course_identifier is None:
                continue
            rows.append(
                (
                    level,
                    str(sced_code).strip(),
                    str(subject_area).strip().zfill(2),
                    str(course_identifier).strip().zfill(3),
                    str(r[3] or "").strip(),
                    str(r[4] or "").strip(),
                )
            )
    out = Path(out_path)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "sced_level",
                "sced_code",
                "subject_area",
                "course_identifier",
                "subject_area_name",
                "sced_course_name",
            ]
        )
        writer.writerows(rows)
    print(f"wrote {len(rows)} SCED rows to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
