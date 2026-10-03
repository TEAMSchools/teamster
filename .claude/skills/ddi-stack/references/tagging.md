# The AppSheet tagging loop

Achievement directors tag assessments in the AppSheet app; Marya Shukla runs QC.
The catalog goes out as `rpt_appsheet__assessments` (every Illuminate
assessment, prior tags included); edits land in a BigQuery table read as
`stg_google_appsheet__illuminate_assessments_extension`. Having a row there IS
`is_internal_assessment` — the tag is membership.

## What each tag field controls

| Field                            | Controls                                                                                                   |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| row exists                       | `is_internal_assessment` / "normed": DKI + Module Dashboard display, the feeds, the star's internal branch |
| `module_type`, `module_sequence` | `module_code` (for example `UA3`); canonical grouping; the DDI dashboard drops `module_type = 'WPP'`       |
| `administered_at`                | Overrides Illuminate's date: which week/term the assessment lands in everywhere                            |
| `subject`                        | Overrides Illuminate's subject area                                                                        |
| `grade_level`                    | `illuminate_grade_level_id`; canonical grouping; `is_replacement` (no grade tag means never a replacement) |
| `regions_assessed`               | Which regions' students are expected to take it (the scaffold fans on this); canonical `regions_array`     |
| `regions_report_card`            | Report-card eligibility for `mod_assessment` non-UA scopes and `mod_standards_domains`' report-card branch |
| `regions_progress_report`        | `mod_standards_domains`' progress-report branch                                                            |

`regions_*` are comma-separated strings; whitespace is stripped and the split
array keeps empty elements, so a trailing comma produces an empty-string region.

## Canonical grouping

Internal members sharing
`(academic_year, scope, subject_area, module_code, grade_level_id)` group under
the lowest member `assessment_id`. Consequences:

- One mistagged copy (wrong module or grade) splits or merges a group — the
  instability behind [#5654].
- The grouping ignores region, so same-attribute assessments from different
  regions merge — the Newark-CRQ-linked-to-Miami defect ([#5653]).
- A tag edit changes `canonical_assessment_id`s, which are hash inputs in the
  assessment star: expect administration and score keys to churn on the next
  tick.

[#5653]: https://github.com/TEAMSchools/teamster/issues/5653
[#5654]: https://github.com/TEAMSchools/teamster/issues/5654

## After a tag fix

Nothing moves until the star ticks. For a same-day need, run the manual refresh
push ([triage.md](triage.md)); otherwise the next tick picks it up.
