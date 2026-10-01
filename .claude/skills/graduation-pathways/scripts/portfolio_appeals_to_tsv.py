"""Turn NJDOE portfolio appeal decision PDFs into PowerSchool Quick Import TSVs.

Replaces the Portfolio Converter Excel workbook (PowerQuery) and the NJ
Portfolio Appeal Upload Template sheet. Reads each region's decision PDF, keeps
students whose appeal was Approved per subject, maps the State Student
Identifier to the PowerSchool student number through BigQuery, and writes
`<Region> - ELA.tsv` and `<Region> - Math.tsv`.

Usage (from the repo root; the PDFs hold student names, so keep them and the
output in the session scratchpad):

    uv run --with pdfplumber python \
        .claude/skills/graduation-pathways/scripts/portfolio_appeals_to_tsv.py \
        --pdf Newark=<newark.pdf> --pdf Camden=<camden.pdf> --out <dir>

Prints counts only, never names or ids. Exits non-zero on anything a person
must look at: an outcome other than Approved/NA, a state id that does not
resolve, or one that resolves to a different region than its PDF.
"""

import argparse
import collections
import pathlib
import re
import sys

import pdfplumber
from google.cloud import bigquery

SUBJECTS = {"ELA": 2, "Math": 3}  # PDF column index per subject
# Expected start of each header cell; a layout change stops the run rather than
# silently swapping ELA and Math.
HEADER = ("Student Name", "State Student", "ELA", "Mathematics")
REGIONS = {"Newark", "Camden"}
KNOWN_OUTCOMES = {"Approved", "NA"}
SID = re.compile(r"^\d{10}$")

LOOKUP_SQL = """
select state_studentnumber, student_number, region, academic_year,
from `teamster-332318`.kipptaf_extracts.int_extracts__student_enrollments
where state_studentnumber in unnest(@sids) and rn_year = 1
"""


def read_pdf(path: pathlib.Path) -> tuple[list[tuple[str, dict[str, str]]], int]:
    """Return (state id, {subject: outcome}) per data row, and the count of
    tables whose header does not match HEADER."""
    rows = []
    bad_headers = 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                header = [(c or "").strip() for c in table[0]] if table else []
                if len(header) != len(HEADER) or not all(
                    h.startswith(e) for h, e in zip(header, HEADER, strict=True)
                ):
                    bad_headers += 1
                    continue
                for cells in table[1:]:
                    sid = (cells[1] or "").strip()
                    if not SID.match(sid):
                        continue
                    outcomes = {
                        s: (cells[i] or "").strip() for s, i in SUBJECTS.items()
                    }
                    rows.append((sid, outcomes))
    return rows, bad_headers


def lookup(sids: list[str]) -> dict[str, tuple[int, str]]:
    """Map state id to (student_number, region) from each student's latest year."""
    client = bigquery.Client(project="teamster-332318")
    job = client.query(
        LOOKUP_SQL,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ArrayQueryParameter("sids", "STRING", sids)]
        ),
    )
    latest: dict[str, tuple[int, int, str]] = {}
    for r in job.result():
        prev = latest.get(r.state_studentnumber)
        if prev is None or r.academic_year > prev[0]:
            latest[r.state_studentnumber] = (
                r.academic_year,
                r.student_number,
                r.region,
            )
    return {sid: (sn, region) for sid, (_, sn, region) in latest.items()}


def write_tsv(path: pathlib.Path, subject: str, student_numbers: list[int]) -> None:
    # Match the files PowerSchool has accepted: tab-separated, LF, no final newline.
    lines = [f"Student Number\tS_NJ_STU_X.Graduation_Pathway_{subject}"]
    lines += [f"{sn}\tN" for sn in student_numbers]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--pdf",
        action="append",
        required=True,
        metavar="REGION=PATH",
        help="Region name (Newark or Camden) and its decision PDF. Repeat per region.",
    )
    parser.add_argument("--out", required=True, type=pathlib.Path)
    args = parser.parse_args()

    problems = 0
    outputs: dict[pathlib.Path, tuple[str, list[int]]] = {}
    for spec in args.pdf:
        region, _, path = spec.partition("=")
        if region not in REGIONS or not path:
            parser.error(f"--pdf must be REGION=PATH with REGION in {sorted(REGIONS)}")
        rows, bad_headers = read_pdf(pathlib.Path(path))
        print(f"== {region}: {len(rows)} students in the PDF")
        if bad_headers:
            print(f"  STOP: {bad_headers} table(s) with an unexpected header")
            problems += 1

        outcomes = collections.Counter(o for _, per in rows for o in per.values())
        unknown = set(outcomes) - KNOWN_OUTCOMES
        if unknown:
            print(f"  STOP: outcome values not handled: {sorted(unknown)}")
            problems += 1

        dupes = [s for s, n in collections.Counter(s for s, _ in rows).items() if n > 1]
        if dupes:
            print(f"  STOP: {len(dupes)} state ids appear more than once")
            problems += 1

        ids = lookup([s for s, _ in rows])
        missing = [s for s, _ in rows if s not in ids]
        wrong_region = [s for s, _ in rows if s in ids and ids[s][1] != region]
        if missing:
            print(f"  STOP: {len(missing)} state ids have no PowerSchool student")
            problems += 1
        if wrong_region:
            print(f"  STOP: {len(wrong_region)} state ids belong to another region")
            problems += 1

        for subject in SUBJECTS:
            approved = [
                ids[s][0]
                for s, per in rows
                if per[subject] == "Approved" and s in ids and ids[s][1] == region
            ]
            outputs[args.out / f"{region} - {subject}.tsv"] = (subject, approved)
            print(f"  {subject}: {len(approved)} approved")

    if problems:
        # Remove every earlier output so a short or stale file cannot be imported.
        for region in REGIONS:
            for subject in SUBJECTS:
                (args.out / f"{region} - {subject}.tsv").unlink(missing_ok=True)
        print(f"{problems} problem(s): no files written; fix before importing")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    for out, (subject, approved) in outputs.items():
        write_tsv(out, subject, approved)
        print(f"wrote {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
