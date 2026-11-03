# Suspension Google Sheet feed — design

Issue: #6245. Follow-up: #6246 (move onto the marts). Prerequisite for Miami
rows: #5790.

## Intent

A network-level stakeholder checks suspension letters for students with IEPs.
Today they download the OKRTS Dashboard "Entry Analysis" roster one school at a
time to see each suspension's date and length (Zendesk ticket 489137). A
standing feed puts every suspension in one place.

The Data Team owns the Sheet and the folder it lives in, and grants access one
person at a time. Each stakeholder reads their region through `IMPORTRANGE`
filtered on `region`. `IMPORTRANGE` is not access control; the per-person grant
is.

## Goals

- One row per suspension consequence (`incident_penalty_id`) in the window.
- Window: `academic_year >= current_academic_year - 1`. It moves forward at each
  July rollover with no code change.
- Every field the "EA - Referral - Roster" worksheet shows, in its rows, its
  tooltip, and its filters (list below).
- The suspension letters on file in DeansList, with upload dates.
- A `region` column for the per-region import.

## Non-goals

- Miami 2026-27 onward. Miami moved discipline to Focus; that gap is known.
- Miami 2025-26 in this change. The feed reads the student number the upstream
  models provide, so Miami fills in when #5790 lands, with no feed change.
- The incident `context` field.
- Non-suspension consequences.

## Anti-goals

- A per-extract Miami id remap. #5790 fixes it once, upstream.
- A feed whose suspension counts disagree with DeansList for NJ. Every NJ
  suspension in the window appears exactly once, including the few the
  dashboard's week-based join drops.

## Approaches

1. **Read what the OKRTS Dashboard reads (picked).** DeansList penalties,
   attachments, and roster assignments, plus the student enrollment extract. One
   small PR. Costs 3 layer rule A1 rows in `standard-baseline.tsv` under #5811,
   the same pattern `rpt_gsheets__historical_suspensions` and
   `rpt_gsheets__school_metrics_extract` follow.
2. **Marts first.** Fix Miami in the behavior marts, add the free-text, SSDS,
   and letter fields to marts, then build a thin feed. Cleanest under rule A2
   but about 2 PRs, and it changes Cube's suspension counts. Picked as the
   follow-up, #6246, after #5790.
3. **Mix.** Marts where they have the field, DeansList models for the rest.
   Dropped: most of approach 2's cost without approach 1's simplicity.

## Decided

- Model:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__suspensions.sql`,
  a view like other `rpt_` models, with an enforced contract and an `error`
  grain test on (`region`, `incident_penalty_id`).
- Rows: `int_deanslist__incidents__penalties` where `is_suspension`, matched to
  the student's enrollment for that academic year in the same region
  (`_dbt_source_project`).
- `iep_status` comes from that enrollment, the same field the dashboard uses.
- Columns:
  - Where and when: `region`, `school`, `academic_year`,
    `academic_year_display`.
  - Student: `student_number`, `student_name`, `grade_level`, `gender`,
    `homeroom_section`, `iep_status`, `ml_status`, `is_chronically_absent`,
    `is_tier3_4`.
  - Incident: `incident_id`, `created_date`, `entry_staff`, `referral_tier`,
    `category`, `admin_summary`, `reported_details`, `nj_state_reporting`,
    `ssds_incident_id`.
  - Consequence: `incident_penalty_id`, `penalty_name`, `suspension_type`,
    `start_date`, `end_date`, `num_days`.
  - Letters: `suspension_letters` (DeansList suspension letter attachments, name
    and upload date) and `other_uploads` (other uploaded files).

- PII: tag every student, free-text, and status column
  `config.meta.contains_pii: true`.
- Exposure: `rpt_gsheets__suspensions` in `models/exposures/google-sheets.yml`,
  kind `googlesheets`, with the Sheet URL.

## My calls (check these)

- All suspensions, whatever the referral tier. The dashboard hides the
  Non-Behavioral, Social Work, and Home Instruction Request tiers by default.
- `is_tier3_4` and `is_chronically_absent` follow
  `rpt_tableau__okrts_referrals`: current Tier 3/Tier 4 roster membership, and
  year-to-date ADA at or below 0.90.
- Letter columns reuse the dashboard's attachment-name list, split into
  suspension letters and other uploads.

## Left to the builder

- How to pick one enrollment stint when a student has 2 in the same year and
  region. The incident's school and date should decide it; the grain test and an
  NJ count reconciliation against `int_deanslist__incidents__penalties` confirm
  it.

## Left to the user

- The Sheet URL for the exposure, and the Sheet's connection to BigQuery.
