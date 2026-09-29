"""Compare each grad-plan tracker tab's row cap against its source tab's row count.

Each Reports tracker tab holds a formula shaped like
`=QUERY(IMPORTRANGE("<source_url>", "<source_tab>!A1:AD<cap>"), ...)` in cell
A1. This reads that formula off every tab of every tracker, then counts rows
(a value in column A, header included) on the matching source tab.

Usage:
    uv run --with google-api-python-client --with google-auth python \
        check_row_caps.py <source_spreadsheet_id> <tracker_tsv_path>

<source_spreadsheet_id> is the IMPORTRANGE Sources sheet's id (see the
rpt_gsheets__grad_plan_tracking exposure in
src/dbt/kipptaf/models/exposures/google-sheets.yml for its url).

<tracker_tsv_path> is a two-column, header-less TSV of
`tracker_name<TAB>tracker_spreadsheet_id`, one row per Reports tracker (KHS,
NLH, NCA) -- a per-run input, kept in the session scratchpad rather than the
repo.

Auth is ADC; the codespaces@teamster-332318.iam.gserviceaccount.com service
account is already shared on the source sheet and all three trackers.
"""

from __future__ import annotations

import re
import sys

import google.auth
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
FORMULA_RE = re.compile(r'"([^"!]+)!A1:[A-Z]+(\d+)"')
NEAR_MISS_RATIO = 0.95


def read_trackers(path: str) -> list[tuple[str, str]]:
    with open(path, encoding="utf-8") as handle:
        pairs = [line.strip().split("\t", 1) for line in handle if line.strip()]
    return [(name, sheet_id) for name, sheet_id in pairs]


def tab_titles(sheets, spreadsheet_id: str) -> list[str]:
    meta = (
        sheets.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties.title")
        .execute()
    )
    return [s["properties"]["title"] for s in meta["sheets"]]


def a1_formula(sheets, spreadsheet_id: str, tab: str) -> str:
    result = (
        sheets.spreadsheets()
        .values()
        .get(
            spreadsheetId=spreadsheet_id,
            range=f"'{tab}'!A1",
            valueRenderOption="FORMULA",
        )
        .execute()
    )
    values = result.get("values", [[""]])
    return values[0][0] if values and values[0] else ""


def source_row_count(sheets, source_id: str, tab: str) -> int:
    result = (
        sheets.spreadsheets()
        .values()
        .get(spreadsheetId=source_id, range=f"'{tab}'!A:A")
        .execute()
    )
    return len(result.get("values", []))


def state(cap: int, rows: int) -> str:
    if rows > cap:
        return "TRUNCATING"
    if rows >= cap * NEAR_MISS_RATIO:
        return "near cap"
    return "fine"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2

    source_id, tracker_tsv = argv[1], argv[2]
    creds, _ = google.auth.default(scopes=SCOPES)
    sheets = build("sheets", "v4", credentials=creds)

    print(
        "tracker\ttab\tsource_tab\tcap\tsource_rows\tstate",
    )
    for tracker_name, tracker_id in read_trackers(tracker_tsv):
        for tab in tab_titles(sheets, tracker_id):
            formula = a1_formula(sheets, tracker_id, tab)
            match = FORMULA_RE.search(formula)
            if not match:
                print(f"{tracker_name}\t{tab}\t(no IMPORTRANGE formula found)")
                continue
            source_tab, cap_text = match.group(1), match.group(2)
            cap = int(cap_text)
            rows = source_row_count(sheets, source_id, source_tab)
            print(
                f"{tracker_name}\t{tab}\t{source_tab}\t{cap}\t{rows}\t"
                f"{state(cap, rows)}",
            )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
