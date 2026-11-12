# The AppSheet tagging loop

Achievement directors tag assessments in the AppSheet app; Marya Shukla runs QC.
The catalog goes out as `rpt_appsheet__assessments` (every Illuminate
assessment, prior tags included); edits land in a BigQuery table read as
`stg_google_appsheet__illuminate_assessments_extension`. Having a row there IS
`is_internal_assessment` — the tag is membership.

An "already tagged" error for an assessment missing from the app is a year
problem, not a tag problem: [item-bank-year.md](item-bank-year.md).

## What each tag field controls

| Field                            | Controls                                                                                                                                                                                                                           |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| row exists                       | `is_internal_assessment` / "normed": DKI + Module Dashboard display, the feeds, the star's internal branch                                                                                                                         |
| `module_type`, `module_sequence` | `module_code` (for example `UA3`); tag grouping; the DDI dashboard drops `module_type = 'WPP'`                                                                                                                                     |
| `administered_at`                | Overrides Illuminate's date: which week/term the assessment lands in everywhere                                                                                                                                                    |
| `subject`                        | Overrides Illuminate's subject area                                                                                                                                                                                                |
| `grade_level`                    | `illuminate_grade_level_id`; tag grouping; `is_replacement` (no grade tag means never a replacement)                                                                                                                               |
| `regions_assessed`               | Which regions' students are expected to take it (the scaffold fans on this); which regional group a copy sits in; canonical `regions_array`                                                                                        |
| `regions_report_card`            | Report-card eligibility for `mod_assessment` non-UA scopes and `mod_standards_domains`' report-card branch — and nothing else: untagged Unit Assessments pass the enrichment feed anyway, and `mod_standards` checks no region tag |
| `regions_progress_report`        | `mod_standards_domains`' progress-report branch                                                                                                                                                                                    |

The `regions_*` fields are comma-separated strings parsed two different ways:
`regions_assessed` is whitespace-stripped and split on `,` (empty elements
survive, so a trailing comma produces an empty-string region), but the
report-card feeds split `regions_report_card` and `regions_progress_report` on
the literal `' , '` with no stripping — a tag typed `Newark,Camden` would
silently drop off report cards. AppSheet writes the `' , '` form consistently (0
deviations across every populated tag, measured 2026-10-03), so this is a
hand-edit hazard, not a live defect. The row and the region fields fail
independently: a tagged assessment (`is_internal_assessment` true) can still
miss a report card on a region field alone. This table is the complete gate map
— report-card triage beyond the tags is [report-cards.md](report-cards.md)'s
job.

## Canonical grouping

Internal copies sharing
`(source, academic_year, scope, subject_area, module_code, grade_level_id)` and
the internal and Florida flags form a tag group. Within it, the copies tagged
for one region in `regions_assessed` form that region's group, named by its
lowest `assessment_id`; that ID is `canonical_assessment_id`. A copy tagged for
several regions sits in each region's group. Consequences:

- Each region's scores carry the title, date, and report card and progress
  report tags of its own first copy. A Camden copy created after Newark's keeps
  Camden's own date. The band set is the one on the tag group's first copy.
- Two copies tagged for the same region combine: multi-part assessments and
  alternate versions become one result per student.
- One mistagged copy (wrong module or grade) splits or merges a tag group, the
  instability behind [#5654]. A wrong module tag combines different tests for
  the regions tagged on both copies.
- Miami-only Florida copies (`regions_assessed` exactly `Miami`) form their own
  tag group. A Florida copy also tagged with another region falls into the New
  Jersey tag group, and sits in the group of each region it is tagged for.
- A tag edit that changes which copy is a region's first changes that region's
  `canonical_assessment_id`, which is a hash input in the assessment star:
  expect administration and score keys to churn on the next tick. Editing
  `regions_assessed` can do the same.

[#5654]: https://github.com/TEAMSchools/teamster/issues/5654

## After a tag fix

The edit lands in the staging table immediately, but nothing downstream moves
until the assessment star ticks (00:00, 10:00, 13:00, 15:00, 17:00 Eastern). The
DDI Suite Tableau extracts then refresh at 01:00 and 18:00 daily plus Friday
16:00, and the DeansList feeds deliver nightly at 01:25 — so a morning date fix
reaches the dashboard at the 18:00 refresh and the report card overnight, unless
someone runs the manual refresh push: materialize
`int_assessments__response_rollup` (plus `__scaffold` when expectations
changed), then the `ddi_suite` Tableau asset — preview Dagster mutations with
`confirm=False` and let the data team run them. A moved `administered_at`
re-buckets the same way everywhere: the DDI dashboard re-weeks the row and the
report-card feeds re-term it against the RT reporting terms (the term windows
typed `RT` in the reporting-terms sheet, per school) — a date no RT term
contains drops the row from the feeds.
