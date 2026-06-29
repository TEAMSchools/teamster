---
name: building-maher-upload-files
description:
  Use when preparing a Salesforce Data Loader insert file for new Maher Fund
  disbursements from a roster or spreadsheet, deduped against existing
  KIPP_Aid__c records. Covers the dedup query, the marker tag, and the post-load
  sync.
---

# Building Maher Fund upload files

## Overview

Maher Fund disbursements are loaded into Salesforce as `KIPP_Aid__c` records.
This skill produces a **Data Loader-ready insert CSV of only the records that
are NOT already in Salesforce**, deduped against a live export of the
`stg_kippadb__kipp_aid` dbt model, with the regexp-extractable
`[MAHER_FUND|v1|type=...|doc=...]` marker tag appended to each record's notes so
the round-trip (insert → Airbyte sync → staging parse) populates `is_maher` /
`fund_type` / `doc_type` automatically.

The work is done by
[`scripts/build_maher_upload_file.py`](../../../scripts/build_maher_upload_file.py).
This skill is the runbook around it.

**PII stays local.** Rosters and the output files contain student names, IDs,
and amounts. Keep every file under `.claude/scratch/` (or another local path);
never paste rows into a PR, issue, comment, Slack, or any external surface.

## When to use

- A new batch of Maher disbursements (e.g. a "Collab Roster" export) needs to be
  loaded into Salesforce.
- You have a spreadsheet of awards and need to know which are new vs already
  loaded.

Not for: the historical 9-tab reconciliation (that was a one-time backfill); use
`.claude/scratch/maher/reconcile.py` as the reference for that.

## Input

A roster CSV, one row per award. The script defaults to the **Collab Roster**
schema, where the Salesforce Contact ID is given directly (no name resolution
needed):

| Field used                         | Default source column                    |
| ---------------------------------- | ---------------------------------------- |
| `student__c`                       | `Salesforce ID`                          |
| `amount__c`                        | `Total Disbursement`                     |
| `date__c`                          | `Approval Date`                          |
| tag `type=` and `ref_funding_type` | `Type` (Emergency/Enrichment)            |
| tag `doc=` and `ref_project_code`  | `Project Code`                           |
| `notes__c` body and `ref_reason`   | `1st Reason for Funding`                 |
| `ref_school_year`                  | `FiscalYear`                             |
| `ref_student_name`                 | `Alumni First Name` + `Alumni Last Name` |

If the roster has different headers, override the `--*-col` flags (run the
script with `--help` to see them). For a roster that gives names instead of
Salesforce IDs, resolve IDs first via `int_kippadb__roster` (see
`reconcile.py`'s resolver) — the script itself does not resolve names.

## Workflow

### 1. Get the candidate student IDs

```bash
uv run scripts/build_maher_upload_file.py --input <roster>.csv --print-students
```

### 2. Export the dedup set from LIVE staging

Dedup is on `(student__c, amount)`. Query the **live** staging model — not a
stale build (see Common mistakes). Filter to the candidate students to keep the
result bounded, or pull all Maher pairs. The BigQuery MCP truncates at 50 rows,
so pack with `STRING_AGG`:

```sql
select string_agg(concat(student, ',', format('%.2f', amount)), '\n') as packed
from `kipptaf_kippadb.stg_kippadb__kipp_aid`
where is_maher and student is not null
```

Save the result to a CSV with a `student,amount` header — this is the
`--existing-pairs` file.

### 3. Build the upload files

Write the output files under `.claude/scratch/` so PII stays local — relative
paths are resolved from the current directory (the repo root), so name them
explicitly:

```bash
uv run scripts/build_maher_upload_file.py \
  --input <roster>.csv \
  --existing-pairs .claude/scratch/maher/existing_pairs.csv \
  --out-new .claude/scratch/maher/maher_upload_new_records.csv \
  --out-existing .claude/scratch/maher/maher_upload_already_in_sf.csv
```

The script prints input / new / already-in-SF counts (plus a `skipped` line only
when rows lack a Salesforce ID or amount), the funding-type split, and the
new-record dollar total. Review them. It warns if any new record is
`Unclassified` (blank/unknown `Type`) — confirm the source before loading.

### 4. Hand off for loading

Give the user the new-records file
(`.claude/scratch/maher/maher_upload_new_records.csv`). They load it via
Salesforce Data Loader as an **insert** on `KIPP_Aid__c`, mapping each `*__c`
column to the matching field. The `ref_*` columns are for human review — leave
them unmapped.

### 5. Post-load: sync and re-parse

After the user confirms the load:

1. Trigger the kippadb Airbyte sync (the twice-daily `KIPP_Aid__c` incremental),
   or wait for the next scheduled run.
2. Rematerialize the `kipptaf/kippadb/stg_kippadb__kipp_aid` Dagster asset so
   the new records surface with parsed `is_maher` / `fund_type`.

## The marker tag

```text
[MAHER_FUND|v1|type=<Emergency|Enrichment|Unclassified>|doc=<Project Code>]
```

- Appended to `notes__c`: the reason verbatim, a blank line, then the tag.
- `v1` versions the format; `|` separates fields, `=` separates key/value.
- Extraction lives in `stg_kippadb__kipp_aid` (`regexp_extract` on the tag).

## Output columns

`student__c`, `amount__c`, `date__c` (ISO `YYYY-MM-DD`), `type__c` (`Other`),
`status__c` (`Approved`), `notes__c` (reason + tag), then reference-only
`ref_student_name`, `ref_school_year`, `ref_funding_type`, `ref_reason`,
`ref_project_code`.

## Common mistakes

| Mistake                                                                                             | Fix                                                                                                                             |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| Deduping against a **stale** staging build (records loaded today aren't in a build from last night) | Confirm staging is fresh first — check the asset's last materialization, or rematerialize before exporting the dedup set.       |
| Running with no dedup file                                                                          | The script errors unless you pass `--existing-pairs` or explicitly `--no-dedup`. Don't reach for `--no-dedup` to "make it run". |
| Loading before reviewing the printed summary                                                        | Always read the counts and the Unclassified warning before handing off.                                                         |
| Two awards to the same student for the **same amount** in one batch                                 | They share one dedup key — only one will be detected as a duplicate. Spot-check same-student same-amount rows.                  |
| Pasting roster/output rows into a PR or comment                                                     | PII stays local. Reference counts and column names, not values.                                                                 |
