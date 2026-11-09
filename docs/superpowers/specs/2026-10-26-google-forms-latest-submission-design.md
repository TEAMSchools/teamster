# Google Forms: one latest submission per respondent, subject, and administration

Issue: #5978 (Google Forms half; the Alchemer half shipped as #6125 / PR #6129).

## Intent

Survey reports count a person more than once when they resubmit a form. The
Alchemer archive already keeps one latest submission per respondent, per
subject, per administration. Google Forms does not:

- Its `round_rn` partitions on `respondent_email`. Family forms have no email,
  so every Miami Re-Commitment submission ranks alone: today only 18 of 2,257
  have `round_rn = 1`.
- It ignores the subject. Renewal Approval has one approver rating many staff,
  so 12,535 of 12,664 submissions rank below 1.
- `fct_survey_submissions` and `fct_survey_responses` keep every submission.

Success: every report reads the same latest-only rule from one place,
`int_surveys__survey_submissions`, and family submissions resolve to a student.

## Decisions

Made by the user:

- **The rule:** keep the latest submission per respondent, per subject, per
  administration. It applies to workflow forms too (Renewal Approval, Candidate
  Offer, Add student to Buckets).
- **Every report** gets the rule. It is decided once, in
  `int_surveys__survey_submissions`.
- **One shared subject model.** Every subject rule written today moves into it.
  A data-team-kept list of each form's subject question is deferred. Until it
  exists, a form gets a subject by adding a line of SQL to this model.
- The branch links to #5978, so merging closes it.
- `student_contact_person_key` stays null.

Made by Claude (the user agreed in conversation but said they do not know the
right answer):

- **A submission with no administration is not ranked.** Its `round_rn` is 1. A
  Google Forms submission whose date falls in no `SURVEY` window of
  `stg_google_sheets__reporting__terms` gets this treatment. This protects forms
  with no subject rule from collapsing. Example: Candidate Offer has 4,338
  submissions. All of them have no term. Ranked on respondent alone, they would
  collapse to 156.

## Approaches considered

1. **One shared subject model (chosen).** Each existing hard-coded rule moves
   into it, and the models that use a rule today read the shared model instead.
   It handles rules a bare question name cannot express: the number in brackets
   inside "Employee Name", and Miami's `8400` prefix.
2. **A data-team-kept list** (Google Sheet of form → subject question). Deferred
   because the rules need parsing logic a list cannot hold. The shared model is
   where a list would plug in later.
3. **Leave each rule where it is** and copy it into the ranking. Rejected: two
   copies of each rule drift.

## What exists today

Each subject rule lives in one consumer:

| Form                             | Rule today                                                                                                      | Where                                                                                          |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Manager Survey                   | 6-digit number in brackets, question `315a6c37` (abbreviation `subject_employee_number`)                        | `int_surveys__manager_survey_details`, projected by `int_surveys__manager_submission_subjects` |
| Renewal Approval Tool Processing | 6-digit number in brackets, question title "Employee Name" (abbreviation `employee_name`)                       | `int_surveys__renewal_responses_feed`                                                          |
| Miami Re-Commitment family form  | `family_respondent_number` answer, **no `8400` prefix**, via a window `max(...) over (partition by answer ...)` | `rpt_tableau__school_community_diagnostic`                                                     |

Prod counts (Google Forms submissions only):

| Form                                    | Submissions | No term | `round_rn = 1` now | `round_rn = 1` under the new rule | Subject resolves |
| --------------------------------------- | ----------- | ------- | ------------------ | --------------------------------- | ---------------- |
| Renewal Approval Tool Processing        | 12,664      | 8       | 129                | ~11,041                           | 12,662           |
| Manager Survey                          | 8,285       | 23      | 8,037              | ~8,059                            | 8,285            |
| Miami Re-Commitment                     | 2,257       | 0       | 18                 | ~1,964                            | 2,254            |
| Performance Management Score Change     | 53          | 0       | 34                 | 53                                | 50               |
| Candidate Offer Form                    | 4,338       | 4,338   | 156                | 4,338                             | —                |
| Add student to Buckets                  | 1,208       | 1,208   | 56                 | 1,208                             | —                |
| SCD Student / SCD Staff / Support, etc. | —           | —       | ≈ unchanged        | ≈ unchanged                       | —                |

"New rule" figures are a simulation with a `survey_response_id` tie-break; the
builder re-measures. The only Google Forms family form is the Re-Commitment
form, which is Miami-only, so its student numbers always take the `8400` prefix.
The NJ & Miami Family Survey is Alchemer-only and already resolved.

## Design

### 1. New model: `int_surveys__submission_subjects`

- Domain `int_` in `surveys/intermediate/` (`surveys` is in `DOMAIN_FOLDERS`).
- Grain: one row per Google Forms submission that has a subject or a respondent
  student. Keys `survey_id`, `survey_response_id`; uniqueness test at
  `severity: error`.
- Columns: `survey_id`, `survey_response_id`, `subject_employee_number` (int64),
  `respondent_student_number` (int64). Both value columns are tagged
  `contains_pii: true`.
- Reads `int_google_forms__form_responses` (question grain). It must **not**
  read `int_surveys__survey_responses`. That model reads
  `int_surveys__survey_submissions`, so reading it here would make a cycle.
- Rules, keyed by question abbreviation:
  - `subject_employee_number`, `employee_name` → the 6-digit number in brackets
    in the answer. This covers Manager Survey, Renewal Approval, and, for free,
    Performance Management Score Change.
  - `family_respondent_number` on the Re-Commitment form → the answer with the
    `8400` prefix (Miami's PowerSchool-to-Focus prefix), only when the answer is
    a 5- or 6-digit number. This matches the Alchemer rule in
    `int_surveys__alchemer_submissions`.
- Each literal gets an S20 comment.

### 2. `int_surveys__survey_submissions`: re-rank the Google Forms arm

- Left join the subjects model. Fill `subject_employee_number` and
  `respondent_student_number` from it, which replaces the `TODO(#5978)` nulls.
- Build `rank_respondent` and `rank_subject` with the same composition as
  `int_surveys__alchemer_submissions`:
  - `rank_respondent` = `respondent_student_number`, else
    `respondent_identifier`, else `survey_response_id`.
  - `rank_subject` = `subject_employee_number`.
  - Cast once each, in a CTE (S9).
- `round_rn` becomes a `row_number()` over
  `survey_title, academic_year, term_code, rank_respondent, rank_subject`,
  ordered by `date_submitted desc, survey_response_id desc`. It replaces the
  `dense_rank()`, which gave ties more than one 1. Partitioning by title, not
  form id, matches the Alchemer arm (Claude's call). Only Career Launch AY2024
  `KFWD` has two form ids in one window (126 submissions), and by title a person
  counts once across both copies.
- A submission with a null `term_code` gets `round_rn = 1` (unranked).
- Output `rank_respondent` and `rank_subject` from both arms (the Alchemer
  source already has them), tagged PII. Add a uniqueness test on
  `survey_title, academic_year, term_code, rank_respondent, rank_subject` where
  `round_rn = 1 and term_code is not null`, at `severity: error`.
- The ranking is the business rule, not dup-masking. Declare
  `standard_exempt: {A5: ...}` if `dbt-layer-check` flags it.

### 3. Facts keep only the latest submission

- `fct_survey_submissions`: every arm (staff, manager, student, family) filters
  `round_rn = 1`.
- `fct_survey_responses` follows through its existing inner join to
  `fct_survey_submissions`. No change is needed there; verify it.
- Manager arm: read `subject_employee_number` straight from
  `int_surveys__survey_submissions`. Both arms now carry it: Google Forms from
  the new model, the Alchemer archive from PR #6129. Disable
  `int_surveys__manager_submission_subjects` (retire = disable) once nothing
  reads it.
- Family arm: replace the `TODO(#5978)` comment on `student_contact_person_key`
  with the reason it stays null. Family forms identify the student, not the
  contact.

### 4. Consumers read the shared rule

- `int_surveys__renewal_responses_feed`: take `subject_employee_number` from the
  subjects model instead of its own regex. **Keep its own `rn_approval` and
  `rn_level_approval`, and do not filter to `round_rn = 1`.** The "Overridden
  Approval" labels compare each submission to the earlier ones, so this feed
  needs the full history. Its latest-only logic already agrees with the shared
  rule.
- `int_surveys__manager_survey_details`, Google Forms arm: take the subject from
  the subjects model instead of its regex. **Keep its own
  `dbt_utils.deduplicate`** (Claude's call). Its partition already is
  respondent, subject, and term. It assigns terms differently: any `MGR1`/`MGR2`
  window by date, with no title match. And it collapses null-term repeats, which
  the shared rule leaves unranked. Swapping in the shared `round_rn = 1` would
  change both, outside this scope. Parity check: row counts before and after
  must be identical.
- `rpt_tableau__school_community_diagnostic`:
  - Drop the `family_responses` window CTE.
  - Join `int_surveys__survey_submissions` on `survey_id, survey_response_id`
    for `respondent_student_number`, which carries the `8400` prefix from both
    arms.
  - Join enrollments on that column.
  - Add `round_rn = 1` to the Google Forms and Alchemer arm. The PowerSchool
    InfoSnap arm is untouched.
  - The model lacks a uniqueness test (#5990), so add one in this PR.
  - Reading the domain `int_` is an A2 edge: `fct_survey_submissions` exposes
    keys only. Note it in the PR.
- `rpt_tableau__survey_responses` keeps every row and passes `round_rn` through
  unchanged (user's decision). Its Tableau workbook does the latest-only
  filtering. The builder checks whether the workbook filters on `round_rn = 1`,
  and reports the result in the PR. The re-rank changes which rows that filter
  keeps.
- `rpt_tableau__survey_links` and `rpt_tableau__survey_completion` already
  filter `round_rn = 1` and change behavior through the re-rank alone.

## Goals, non-goals, anti-goals

- Goal: one latest submission per respondent, subject, and administration in
  every report; Miami Re-Commitment families resolve to students.
- Non-goal: the data-team list of subject questions; resolving the student on
  Add student to Buckets; `student_contact_person_key`.
- Anti-goal: dropping workflow submissions that have no administration
  (Candidate Offer, Add student to Buckets, Ops scoring forms). The rule must
  not collapse them.
- Anti-goal: changing the Alchemer archive, which is frozen.

## Risks for the builder to check

- **Windowed surveys with no term.** `windowed_survey_has_term` warns on 67
  submissions: Support Survey 30, Manager 23, Renewal 8, Staff Info 4, Intent 1,
  KTAF Support 1. Under this design those submissions are never ranked. Before
  shipping, report how many of the 67 repeat a respondent and subject within the
  same form and school year. If any do, stop and bring the count to the user
  before opening the PR (Claude's call); do not add a fallback ranking on your
  own.
- `item_abbreviation` in `int_google_forms__form_responses` should match the
  `question_shortname` values used above. Confirm this before keying on it.
- The re-rank changes which submissions `rpt_tableau__survey_completion` counts.
  Compare its row count before and after.
- Re-measure every figure in the counts table on the branch build.

## Left to the builder

CTE names, test placement, the dbt unit test that pins the ranking rule (for
example: an unranked null-term row, a two-subject approver, and a family row
with no email), and the order of commits.
