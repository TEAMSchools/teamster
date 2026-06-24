# NSC Request Gap Audit — Design

Refs: [#4261](https://github.com/TEAMSchools/teamster/issues/4261)

## Goal

Identify alumni for whom we need to submit further NSC (National Student
Clearinghouse) requests to fill postsecondary tracking gaps, and for each one
suggest a date to start the NSC search from.

Immediate deliverable: a one-off ad-hoc query, results written to local scratch.
This document captures the full logic so the analysis can later be promoted to a
permanent audit model (candidate: `qa_kippadb__nsc_gaps`).

## Sources

| Model                        | Role                                          | Key fields used                                                                                                                             |
| ---------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `int_kippadb__roster`        | Alum universe (KTC-tracked)                   | `contact_id`, `contact_graduation_year`, `contact_advising_provider`, `contact_actual_hs_graduation_date`, `contact_expected_hs_graduation` |
| `stg_nsc__student_tracker`   | Existing NSC pull records                     | `contact_id`, `record_found_y_n`                                                                                                            |
| `stg_kippadb__term`          | Salesforce postsecondary terms                | `student` (contact FK), `verified_by_nsc`, `term_end_date`, `nsc_enrollment_end`                                                            |
| `int_nsc__enrollment_stints` | Derived NSC stints (for completion flag only) | `contact_id`, `derived_status`                                                                                                              |

Note `stg_kippadb__term.student` is the contact id FK (joins to
`int_kippadb__roster.contact_id`). `stg_nsc__student_tracker.contact_id` is the
canonical mixed-case Salesforce contact id recovered in staging.

`int_kippadb__roster` is grained one row per `student_number` (its `unique` key)
— the KTC-tracked roster (`ktc_status is not null`, grades 8–12, most recent
undergrad enrollment), with `contact_*` fields left-joined from
`base_kippadb__contact`. The audit aggregates the roster to one row per
`contact_id`, dropping rows with a NULL `contact_id` (non-alumni / no Salesforce
contact). Sourcing the roster instead of raw `base_kippadb__contact` scopes the
universe to KTC-tracked alumni from the start.

## Universe

Include an alum when either branch holds:

```text
contact_graduation_year <= 2022
OR (contact_graduation_year > 2022 AND contact_advising_provider IS NULL)
```

Rationale: alumni who graduated high school in 2022 or earlier are tracked by
KTAF directly via NSC; alumni who graduated after 2022 are tracked by an
external advising provider unless none is assigned (then KTAF tracks them).

Alumni with a NULL `contact_graduation_year` satisfy neither branch and are
excluded. The analysis reports that excluded count separately so we can confirm
the exclusion is intended before acting on the list.

## Per-alum signals

Computed once per `contact_id`:

- `has_nsc_record` — the contact appears in `stg_nsc__student_tracker` with
  `record_found_y_n = 'Y'`.
- `latest_verified_term_end` —
  `max(coalesce(term_end_date, nsc_enrollment_end))` over the contact's
  `stg_kippadb__term` rows where `verified_by_nsc = true`. This is the anchor
  for the suggested NSC search start.
- `completed_college` —
  `int_nsc__enrollment_stints.derived_status = 'Graduated'` for the contact (or
  a Salesforce terminal status). Used as a flag, never a filter.

The "NSC verified column" referenced in the request is `term.verified_by_nsc`.
The end-date anchor prefers `term_end_date` and falls back to
`nsc_enrollment_end`.

## Gap classification (alum grain — one row per alum)

| `gap_type`        | Condition                                                       | `suggested_search_from`    |
| ----------------- | --------------------------------------------------------------- | -------------------------- |
| `no_nsc_record`   | not in `stg_nsc__student_tracker` (no `record_found_y_n = 'Y'`) | HS graduation date         |
| `unverified_only` | in the tracker, but no `verified_by_nsc` terms                  | HS graduation date         |
| `forward_gap`     | has `verified_by_nsc` terms, latest verified term has ended     | `latest_verified_term_end` |

HS graduation date =
`coalesce(contact_actual_hs_graduation_date, contact_expected_hs_graduation)`.

An alum matches exactly one `gap_type`. An alum with verified terms whose latest
term has **not** ended (currently enrolled per the verified record) is not a gap
and is excluded from the output.

## Output columns

One row per gap alum:

- `contact_id`
- `contact_graduation_year`
- `contact_advising_provider`
- `gap_type`
- `suggested_search_from`
- `is_stale_6mo` — `latest_verified_term_end` more than 6 months before
  `current_date('America/New_York')`. NULL/false for non-`forward_gap` rows.
- `is_stale_prior_ay` — `latest_verified_term_end` before the start of the
  current academic year (`var('current_academic_year')`). NULL/false for
  non-`forward_gap` rows.
- `completed_college_flag` — NSC/SF shows degree completion.

Both staleness flags are reported side by side and labeled, per request — they
are informational, not filters.

## Edge cases and confirmations

- **NULL `contact_graduation_year`** — excluded; count reported separately.
- **`unverified_only`** — alum searched but nothing verified into Salesforce
  terms; treated as its own gap type rather than dropped, since it represents a
  real follow-up need.
- **`completed_college`** — kept in the output (flagged), not filtered, so the
  user decides per row whether further searching is warranted.
- **Verified-term source assumption** — `term.verified_by_nsc` is the
  authoritative "NSC verified" flag and `term_end_date` (fallback
  `nsc_enrollment_end`) is the term end. To be confirmed against profiled data
  before the query is finalized.

## PII handling

The query touches alum names, contact ids, and graduation dates (PII). Results
stay in `.claude/scratch/` and the terminal. No alum-identifying values go into
the issue, PR, commits, or any external surface — only aggregate counts and
column-name references.

## Productionization notes (future)

If promoted to `qa_kippadb__nsc_gaps`:

- Lives under `src/dbt/kipptaf/models/kippadb/qa/` alongside
  `qa_kippadb__duplicate_enrollments`.
- Needs a uniqueness test on `contact_id`.
- The staleness comparisons (`current_date`, `current_academic_year`) make it
  time-varying; anchor to a table materialization if a refreshing asset check is
  wanted.
- A reporting view (`rpt_gsheets__*`) would sit between the QA model and any
  Google Sheet Ops uses to drive submissions.
