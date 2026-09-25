---
name: collegeboard-id-crosswalk
description:
  Use when College Board AP, SAT, or PSAT scores are dropped, new score files
  land, College Board IDs are missing from or unresolved in an ID crosswalk,
  scores for a student are not showing up, stg_collegeboard__ap / __sat / __psat
  has not picked up a new file, or the AP codes/course-crosswalk sheets need
  auditing.
---

# College Board ID crosswalk

College Board score files identify students by a College Board ID. A Google
Sheet crosswalk maps each ID to a PowerSchool `student_number`, and a score
whose ID is not in the crosswalk never reaches a report. This skill finds the
unmapped IDs, matches them to students, hands the matches to the user to paste,
checks the paste, and then hands off to the `carat-dashboard` skill for the
pipeline check and the KIPP Forward summary.

## Two ID spaces, two crosswalks

AP IDs and SAT/PSAT IDs are different College Board ID spaces: the same student
has one of each, and they never match. Each has its own crosswalk tab and its
own match query. Never look up an SAT or PSAT ID in the AP crosswalk, or the
reverse.

| Test      | Crosswalk tab                        | Staging model                                       | Runbook                                          |
| --------- | ------------------------------------ | --------------------------------------------------- | ------------------------------------------------ |
| AP        | `src_collegeboard__ap_id_crosswalk`  | `stg_google_sheets__collegeboard__ap_id_crosswalk`  | [references/ap.md](references/ap.md)             |
| SAT, PSAT | `src_collegeboard__sat_id_crosswalk` | `stg_google_sheets__collegeboard__sat_id_crosswalk` | [references/sat-psat.md](references/sat-psat.md) |

Both tabs are in one workbook, with the AP codes and course-crosswalk tabs:
<https://docs.google.com/spreadsheets/d/1dmPEB3lVBwNhcGANh1H8_D42nK3zIrFFE0rBFZQBuxE>.

## PII — read this before running anything

Match results include student names, DOB, and gender, so the root CLAUDE.md PII
rule applies to them. Keep them in chat and the session scratchpad; never write
a real name or DOB to a committed file. The codes, course-tagging, and lineage
checks carry no PII.

## Why crosswalk gaps happen (say this to the user)

A College Board ID can be missing from a crosswalk for two reasons: a first-time
tester (no ID ever existed to add), or a student with a second College Board
account (College Board's merge process is too tedious for KTAF to pursue — the
fix is just adding the new ID as another mapping to the same `student_number`).
Both resolve identically: add the row. Say this when presenting results so a
"new" ID doesn't read as something having gone wrong.

## Handing rows to the user

Every paste reaches the user in one shape:

1. The destination: the workbook link above plus the exact tab name.
2. A tab-separated file in the session scratchpad,
   `College_Board_ID<tab>PowerSchool_Student_Number`, no header, handed over as
   a clickable path to open in VS Code, select all, copy, and paste below the
   last filled row. Never in chat: the chat panel turns tabs into spaces.
3. Review tables (Tier C/D, `flagged_for_review`, `no_match`) in chat as
   markdown, never in the paste file.

After the paste, confirm the crosswalk staging model's row count rose by the
number of rows handed over, then reconcile: no generated pair missing, no
`College_Board_ID` duplicated, none mapped to a different `student_number` than
generated. The Google Sheets sensor rebuilds the staging model on its own after
an edit; there is no manual step.

## Pipeline QA after a crosswalk update

Once the crosswalk staging model reconciles, invoke the `carat-dashboard` skill
and follow its `references/official-scores-qa.md`. It ends in a three-part
report: what changed and when it reached prod, a draft for KIPP Forward, and a
before/after preview of the metrics the dashboard tracks.
