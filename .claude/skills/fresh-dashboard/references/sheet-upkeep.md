# Sheet upkeep: status_crosswalk and exclude_ids

Both tabs live in the same `Finalsite` workbook as the goals tab (id in the
entry file), under the named ranges
`src_google_sheets__finalsite__status_crosswalk_v10` and
`src_google_sheets__finalsite__exclude_ids`. Their staging models are tables, so
an edit shows only after a rebuild. Hand edits back under the entry file's sheet
handoff contract. The goals tab is in [goals-sheet.md](goals-sheet.md).

## status_crosswalk: mapping a Finalsite status

The crosswalk maps each `(detailed_status, enrollment_type)` to the funnel goal
groups, for one year (`_dagster_partition_key`, column A). A pair Finalsite
emits that the crosswalk lacks is dropped silently by `latest_status_calc`'s
inner join. Find the gaps with check 1 in
[troubleshooting.md](troubleshooting.md).

- `detailed_status` is derived from the Finalsite date column name in
  `int_finalsite__status_report_unpivot` (`accepted_date` → `Accepted`). The
  status set is the 24 columns that model unpivots. A status Finalsite adds as a
  new column needs a model change first: the unpivot list, the `status_order`
  `CASE`, and the static list in
  `test_int_finalsite__status_order_matches_crosswalk_ranking`, all together.
- A missing row for an existing status (usually one `enrollment_type`) is a
  sheet edit. Copy the neighbouring row's structure, then put the mapping
  columns to SRE; they encode funnel judgment and cannot be derived.
- The staging model is `select *`, so sheet columns are model columns. The doc's
  _`status_crosswalk` column reference_ lists every column. The ones SRE
  decides, and how to ask:

| col     | column                                                                                                                                              | question to put to SRE                                                                           |
| ------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| **D**   | `detailed_status_ranking`                                                                                                                           | When a student hits several statuses, which wins? Has that priority changed?                     |
| **H**   | `qa_flag`                                                                                                                                           | Which statuses should be excluded from reporting as bad data this cycle?                         |
| **I-P** | `status_enrollment`, `status_group_numerator`, `status_group_denominator`, `conversion_metric_numerator_1..3`, `conversion_metric_denominator_1..2` | Which funnel bucket does each status roll into, and which conversion rates does it count toward? |

- If D changes, change the `status_order` `CASE` in
  `int_finalsite__status_report_unpivot` and the test's static list with it;
  `test_int_finalsite__status_order_matches_crosswalk_ranking` fails if they
  drift.
- `valid_detailed_status = false` and `qa_flag = true` both drop the row.
- At rollover, column A is replaced with the new year, never appended
  ([recruitment-year-rollover.md](recruitment-year-rollover.md), step 0d).

## exclude_ids: dropping a test record

`stg_finalsite__status_report` drops every `finalsite_enrollment_id` listed in
the sheet's `finalsite_student_id` column. A test or fake record counts on the
dashboard until its id is added.

- Get the Finalsite enrollment id from the user or SRE; don't guess it from a
  name. Treat the record as student data: keep names out of git and GitHub.
- The filter is `not in`, and the column has a `unique` test but no `not_null`
  test. A NULL id would make `not in` drop every row, so don't leave blank cells
  inside the range.
- After the paste, rebuild `stg_google_sheets__finalsite__exclude_ids` and the
  FRESH models downstream of `stg_finalsite__status_report`, then confirm the id
  no longer appears there.
