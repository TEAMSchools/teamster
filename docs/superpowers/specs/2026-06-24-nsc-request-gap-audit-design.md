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

| Model                        | Role                                      | Key fields used                                                                                                                             |
| ---------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `int_kippadb__roster`        | Alum universe (KTC-tracked)               | `contact_id`, `contact_graduation_year`, `contact_advising_provider`, `contact_actual_hs_graduation_date`, `contact_expected_hs_graduation` |
| `stg_nsc__student_tracker`   | Existing NSC pull records                 | `contact_id`, `record_found_y_n`                                                                                                            |
| `stg_kippadb__term`          | Salesforce postsecondary terms            | `enrollment` (FK to enrollment), `verified_by_nsc` (date), `term_end_date`, `nsc_enrollment_end`                                            |
| `stg_kippadb__enrollment`    | Bridges term to contact                   | `id` (term FK target), `student` (contact id)                                                                                               |
| `int_nsc__enrollment_stints` | Derived NSC stints (completion flag only) | `contact_id`, `derived_status`                                                                                                              |

### Join paths and grains

`int_kippadb__roster` is grained one row per `student_number` (its `unique` key)
— the KTC-tracked roster (`ktc_status is not null`, grades 8–12, most recent
undergrad enrollment), with `contact_*` fields left-joined from
`base_kippadb__contact`. The audit aggregates the roster to one row per
`contact_id`, dropping rows with a NULL `contact_id` (non-alumni / no Salesforce
contact). Sourcing the roster instead of raw `base_kippadb__contact` scopes the
universe to KTC-tracked alumni from the start.

`stg_kippadb__term` has **no** direct contact FK. A term reaches its contact
through its enrollment: `term.enrollment = enrollment.id`, and
`enrollment.student` is the contact id. `stg_nsc__student_tracker.contact_id` is
the canonical mixed-case Salesforce contact id recovered in staging, and joins
directly to `int_kippadb__roster.contact_id`.

## Universe

Include an alum when all of these hold:

```text
contact_actual_hs_graduation_date IS NOT NULL   -- actually graduated HS
AND contact_graduation_year <= 2026             -- current_academic_year + 1
AND (
  contact_graduation_year <= 2022
  OR (contact_graduation_year > 2022 AND contact_advising_provider IS NULL)
)
```

Rationale: alumni who graduated high school in 2022 or earlier are tracked by
KTAF directly via NSC; alumni who graduated after 2022 are tracked by an
external advising provider unless none is assigned (then KTAF tracks them).

The two leading guards scope the universe to **actual HS graduates** through the
class of 2026. Without them, the `> 2022 when advising_provider IS NULL` branch
sweeps in the entire current grade 8–12 roster that has no provider assigned
(~4,100 current students, HS classes 2027–2030), for whom an NSC postsecondary
request is premature. `contact_actual_hs_graduation_date IS NOT NULL` is the
substantive filter; the year cap is a redundant guard.

Alumni with a NULL `contact_graduation_year` satisfy neither inner branch and
are excluded (empty in current data).

## Per-alum signals

Computed once per `contact_id`:

- `has_nsc_record` — the contact appears in `stg_nsc__student_tracker` with
  `record_found_y_n = 'Y'`.
- `has_verified_terms` — the contact has at least one `stg_kippadb__term` row
  (via its enrollment) where `verified_by_nsc IS NOT NULL`. `verified_by_nsc` is
  a **date** (the NSC verification date), not a boolean — a non-null value means
  the term was NSC-verified.
- `latest_verified_term_end` —
  `max(coalesce(term_end_date, safe.parse_date('%Y%m%d', substr(nsc_enrollment_end, 1, 8))))`
  over the contact's NSC-verified terms. `term_end_date` is a DATE and is the
  primary anchor; `nsc_enrollment_end` is a `%Y%m%d` STRING (some values carry a
  trailing `.0` float artifact, hence `substr(..., 1, 8)`) used only as a
  fallback. This is the anchor for the suggested NSC search start.
- `completed_college` —
  `int_nsc__enrollment_stints.derived_status = 'Graduated'` for the contact (or
  a Salesforce terminal status). Used as a flag, never a filter.

These two presences come from **different sources** — `stg_nsc__student_tracker`
(the raw NSC pull echo) and Salesforce verified terms — and a contact can have
one without the other. The gap classification below resolves the overlap with
explicit precedence.

## Gap classification (alum grain — one row per alum)

Each universe alum is assigned exactly one `gap_type` by precedence (verified
terms first, then tracker presence):

| Precedence | `gap_type`        | Condition                                                                       | `suggested_search_from`    |
| ---------- | ----------------- | ------------------------------------------------------------------------------- | -------------------------- |
| 1          | `forward_gap`     | `has_verified_terms` and the latest verified term has ended                     | `latest_verified_term_end` |
| 2          | `unverified_only` | no verified terms, but in `stg_nsc__student_tracker` (`record_found_y_n = 'Y'`) | HS graduation date         |
| 3          | `no_nsc_record`   | no verified terms and not in the tracker                                        | HS graduation date         |

HS graduation date =
`coalesce(contact_actual_hs_graduation_date, contact_expected_hs_graduation)`.

A `forward_gap` alum whose latest verified term has **not** ended (currently
enrolled per the verified record) is not a gap and is excluded. In the current
data every verified-terms alum in the universe has already ended their latest
verified term, so none are excluded on this basis.

## Output columns

One row per gap alum:

- `contact_id`
- `contact_graduation_year`
- `contact_advising_provider`
- `gap_type`
- `suggested_search_from`
- `is_stale_6mo` — `latest_verified_term_end` more than 6 months before
  `current_date('America/New_York')`. NULL for non-`forward_gap` rows.
- `is_stale_prior_ay` — `latest_verified_term_end` before the start of the
  current academic year (`var('current_academic_year')`, July 1 of that year).
  NULL for non-`forward_gap` rows.
- `completed_college_flag` — NSC/SF shows degree completion.

Both staleness flags are reported side by side and labeled, per request — they
are informational, not filters.

## Edge cases and confirmations

- **NULL `contact_graduation_year`** — excluded; count reported separately
  (empty in current data).
- **`forward_gap` with no parseable term end** — a small number of verified-term
  alumni have neither a `term_end_date` nor a parseable `nsc_enrollment_end`.
  They are still `forward_gap` but cannot anchor a search-from; fall back to the
  HS graduation date and flag them.
- **`unverified_only`** — alum searched but nothing verified into Salesforce
  terms; treated as its own gap type rather than dropped, since it represents a
  real follow-up need.
- **`completed_college`** — kept in the output (flagged), not filtered, so the
  user decides per row whether further searching is warranted.

## Validation (observed against prod, 2026-06-24)

Universe = 2,406 actual HS graduates (classes through 2025; no class-of-2026
contact has a recorded HS graduation date yet). Buckets (mutually exclusive, by
precedence):

- `forward_gap` — 1,552 (1,502 stale > 6 months, 1,470 before AY2025 start; none
  currently enrolled)
- `no_nsc_record` — 740
- `unverified_only` — 114

`completed_college` flagged: 268. Grad-year split: ≤2022 = 2,161; 2023–2026
= 245.

(Before the HS-graduate guards, the literal rule returned 7,359 contacts, of
which ~4,100 were current grade 8–12 students — see Universe.)

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
