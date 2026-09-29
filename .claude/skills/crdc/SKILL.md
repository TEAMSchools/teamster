---
name: crdc
description: >-
  Use when any task touches KTAF's Civil Rights Data Collection (CRDC) for OCR:
  starting a new cycle or its kickoff doc, the internal collection sheet, the
  student-numbers or SCED crosswalk tabs of the CRDC sheet, running or checking
  rpt_tableau__crdc_roster or the CRDC Dashboard workbook, entering numbers on
  the OCR submission site or answering its quality flags, OCR's list of changed
  data elements, the fall snapshot date, nonbinary reporting, or Paterson's
  first CRDC. Triggers: "CRDC", "OCR civil rights data", "crdc_dashboard"
  exposure, stg_google_sheets__crdc__student_numbers,
  stg_google_sheets__crdc__sced_code_crosswalk.
---

# CRDC

The reference doc is
[crdc-data-model.md](../../../docs/models/crdc-data-model.md). Read its "Terms"
and "Steps" sections (stop at "Outputs") before any task, and its "Known issues,
need to fix" before trusting a count.

## Rules for every task

- The Drive is the record for each cycle; the repo holds none of it. Kickoff
  docs, collection sheets, dates, counts, and rosters live in the Workspace
  shared drive, folder `CRDC`, one subfolder per cycle (`CRDC SY21-22`,
  `CRDC SY23-24`, then `CRDC SY25-26`). Anything generated for a cycle (a date
  table, a TSV of counts, a flag log) goes in the session scratchpad and then
  into that subfolder, never into a commit.
- A cycle is named for the school year it reports, which is the year before the
  one in progress. In dbt that is `current_academic_year - 1`; retention alone
  reads `current_academic_year`.
- Camden, Newark, and Paterson each file as a district, and each reports all its
  schools as one school. Miami files its own CRDC: out of scope for every task
  here.
- The `src_crdc__student_numbers` tab, the collection sheet's ARRS raw-data tab,
  and every roster row are student-level PII. They stay in the terminal and the
  session scratchpad. CRDC totals become public record, but commits, PRs, and
  issues still get only aggregates with no cell under 10.
- The public doc names no one but the owner (Anthony Walters) and carries no
  Drive links, file ids, or emails. Owners appear there by role.
- No Tableau MCP call without telling the user it costs a lot of tokens and
  getting a yes. Check counts in the warehouse first
  (`kipptaf_tableau.rpt_tableau__crdc_roster`, a view).
- Open questions for the data team lead (compliance lead, discipline owner,
  Paterson system access, nonbinary reporting, which new optional items to
  answer) are asked, not answered. When a cycle starts, ask each one still open
  in the reference doc's "Open questions" before drafting the kickoff doc. Do
  not pick an answer on their behalf; list them in the kickoff doc until
  settled.

## Route by task

| Task                                                                               | Read                                                      |
| ---------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Start a cycle, write the kickoff doc, owners, milestones                           | [kickoff.md](references/kickoff.md)                       |
| Set up or chase the collection sheet; what each department fills in                | [collection-sheet.md](references/collection-sheet.md)     |
| Tag students, update the SCED crosswalk, refresh the workbook, a count looks wrong | [model-and-workbook.md](references/model-and-workbook.md) |
| Enter numbers on the OCR site, answer a quality flag, certify                      | [ocr-entry.md](references/ocr-entry.md)                   |
| OCR published changes; roll the code and sheet to the next cycle                   | [rollover.md](references/rollover.md)                     |

## Files in the CRDC folder

| Title                                                    | What it is                                                                    |
| -------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `CRDC SY2023-2024` (Doc, per cycle)                      | Kickoff doc: purpose, owner table, reference dates, milestones                |
| `SY23-24 CRDC Data Submission` (Sheet, per cycle)        | Collection sheet, one tab per OCR section                                     |
| `CRDC` (Sheet)                                           | dbt source: tabs `src_crdc__student_numbers`, `src_crdc__sced_code_crosswalk` |
| `CRDC Data Elements` (Sheet)                             | Element list worked from OCR's form                                           |
| `CRDC Dashboard.twb`                                     | Older copy of the workbook; the live one is on Tableau Server (Production)    |
| `CRDC - Rolling Data Collection Protocol Proposal` (Doc) | Unfinished proposal; the doc keeps what still fits                            |
| OCR form PDFs                                            | One set per cycle                                                             |

Search for these by title with the Drive tools; ask the user when a search
returns more than one match.
