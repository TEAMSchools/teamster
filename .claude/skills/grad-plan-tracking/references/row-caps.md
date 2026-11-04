# Row-cap check

Each Reports tracker tab reads a fixed row range from the IMPORTRANGE Sources
sheet: `=QUERY(IMPORTRANGE(<source>, "<tab>!A1:AD<cap>"), ...)`. Because the
range is fixed, a source tab that outgrows its cap truncates silently instead of
erroring — see the doc's "Known issues, need to fix" for the mechanism and the
2026-09-28 case: all four NCA NJ Diploma tabs were raised from a 3,000-row cap
to 15,500 after the old cap silently dropped most 11th- and 12th-graders against
a roughly 9,400-row source tab.

Run this check after any large enrollment push, or whenever a school reports
students missing from a tab.

## What to compare

For each of the eight tabs on each of the three Reports trackers (KHS, NLH,
NCA), read the tab's cap and its source tab name out of the `A1` formula, then
count that source tab's rows (a value in column A, header included) on the
IMPORTRANGE Sources sheet. A tab is truncating when its source row count exceeds
its cap; treat anything within 5% of the cap as a near-miss that will hit the
cap on its next enrollment push.

## Recipe

When you run this, look up the source spreadsheet id from the
`rpt_gsheets__grad_plan_tracking` exposure's `url` field in
`src/dbt/kipptaf/models/exposures/google-sheets.yml`, rather than hardcoding the
id here. The three Reports tracker spreadsheet ids aren't in the repo; get them
from Teaching and Learning or the data team and keep them in the session
scratchpad as a two-column, header-less
`tracker_name<TAB>tracker_spreadsheet_id` file — they're a per-run input, not a
repo fact.

Auth is ADC: the `codespaces@teamster-332318.iam.gserviceaccount.com` service
account is already shared on all three trackers and the source sheet, so no
extra sharing is needed before running this.

```bash
uv run --with google-api-python-client --with google-auth python \
  <worktree>/.claude/skills/grad-plan-tracking/scripts/check_row_caps.py \
  <source_spreadsheet_id> <scratchpad>/grad_plan_trackers.tsv
```

It prints, per tracker tab: the source tab it reads, the cap, the source tab's
current row count, and whether that tab is fine, a near-miss, or truncating.

## Known traps

- **A blank or short tab is usually Data Capture not having been run**, not a
  cap problem. Rule that out first with the doc's known-issue diagnostic query
  before assuming a cap is the cause.
- Paterson and Miami never have trackers to check; see the doc's "Decisions."
