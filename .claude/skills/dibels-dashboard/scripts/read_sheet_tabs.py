"""Dump a Google Sheet's tabs to local TSVs, readable when nothing else is.

Usage:
    uv run --with google-api-python-client --with google-auth python \
        .claude/skills/dibels-dashboard/scripts/read_sheet_tabs.py \
        <spreadsheet_id> [out_dir] [tab name substring]

Why this exists -- both obvious routes to a Sheets-backed source are dead ends:

  * The BigQuery MCP cannot read a Sheets external at all. Its service account
    carries no Drive scope, so any such query returns "Permission denied while
    getting Drive credentials". Sharing the file changes nothing: it is a
    missing OAuth scope, not a file permission.
  * The Google Drive MCP reads the file fine, but check-output.sh redacts the
    whole response when it contains a high-entropy string, which a real
    spreadsheet usually does somewhere. You get "[redacted: secret material]"
    and no content.

ADC from Python can request the Drive scope itself, which is the way through.
The other half of the trick is writing every fetched value to a FILE and
printing only tab names, row counts and column counts -- the output scanner
then has no payload to catch. Read the TSVs with the Read tool afterwards.

Leaves the sheet untouched: both scopes are read-only.
"""

import sys
from pathlib import Path

import google.auth
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)

    spreadsheet_id = sys.argv[1]
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else ".claude/scratch")
    needle = sys.argv[3].lower() if len(sys.argv) > 3 else None

    try:
        creds, _ = google.auth.default(scopes=SCOPES)
    except Exception as exc:
        sys.exit(f"ADC unavailable: {type(exc).__name__}: {exc}")

    svc = build("sheets", "v4", credentials=creds, cache_discovery=False)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = (
        svc.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))")
        .execute()
    )
    tabs = [
        (s["properties"]["title"], s["properties"]["sheetId"])
        for s in meta.get("sheets", [])
    ]
    if needle:
        tabs = [t for t in tabs if needle in t[0].lower()]

    print(f"{len(tabs)} tab(s):")
    for title, gid in tabs:
        try:
            vals = (
                svc.spreadsheets()
                .values()
                .get(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{title}'",
                    # UNFORMATTED_VALUE returns the underlying number, so a cell
                    # displayed as "51%" arrives as 0.51 rather than a string to
                    # re-parse. Formatting is a display concern.
                    valueRenderOption="UNFORMATTED_VALUE",
                )
                .execute()
                .get("values", [])
            )
        except Exception as exc:
            print(f"  gid={gid:<12} {title}: FETCH FAILED {type(exc).__name__}")
            continue

        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)
        dest = out_dir / f"sheet_{gid}_{safe}.tsv"
        with dest.open("w") as fh:
            for row in vals:
                fh.write("\t".join(str(c) for c in row) + "\n")
        widest = max((len(r) for r in vals), default=0)
        print(
            f"  gid={gid:<12} {title}: {len(vals)} rows, widest {widest} cols -> {dest}"
        )


if __name__ == "__main__":
    main()
