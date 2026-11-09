# Rebuild the Alchemer survey archive with a real round_rn

Refs #6125. Blocks #5978.

## Intent

#5978 makes `round_rn = 1` mean the latest submission per respondent, per rated
person, per term, for every survey, and links family submissions to students.
Alchemer submissions are frozen in two archived tables
(`int_surveys__alchemer_submissions`, `int_surveys__alchemer_responses`) with
`round_rn` hardcoded to 1, or null on the Manager Survey archive arm. The 2022
NJ & Miami Family Survey is an Alchemer form. Alchemer rows must not be
recomputed downstream, so both fixes land in the archive: revive the models, fix
them, rebuild once in prod, and archive them again.

## Goals

- `round_rn` on Alchemer submissions: `row_number()` over survey, academic year,
  term, respondent, and rated person, ordered by `date_submitted desc`,
  `survey_response_id desc`. Exactly one row per partition gets 1.
- Respondent is `respondent_identifier` (employee number, else email). On the
  2022 family survey it is the resolved student number. A submission with no
  respondent identity ranks alone.
- Rated person is the `subject_df_employee_number` answer. Surveys without one
  partition on respondent alone.
- Manager Survey archive arm: `round_rn = 1`. Its effective response id already
  encodes respondent, subject, and term, so each row is its own partition.
- 2022 family survey: resolve the `student_number` answer. Prefix `8400` only
  when the submission has a non-null answer to any `miami_*` question. A
  presence test is wrong: every submission has `miami_*` question rows.
- Two new columns on `int_surveys__alchemer_submissions`:
  `respondent_student_number` and `subject_employee_number`. #5978 reads the
  student from here instead of re-deriving it.
- One PR, merged with the prod archive already rebuilt.

## Non-goals

- The Google Forms arm's ranking, the Miami Re-Commitment resolution, the fact
  filters, and the SCD demographics fix. All are #5978.
- Holding other columns to their September values. The rebuild accepts today's
  values from live inputs (roster history, terms sheet, directory aliases,
  manager details).

## Constraints

- The prod rebuild is a warehouse write. The user runs it from the worktree.
- `int_surveys__survey_submissions` unions the archive by position, so its
  Google Forms arm gains the two new columns as typed nulls in this PR (S17).
  `int_surveys__alchemer_responses` copies `round_rn` from submissions, so it
  rebuilds too.
- `respondent_student_number` is PII. Tag it `contains_pii: true`. GitHub gets
  counts only.

## Approaches

- A, picked: add the resolved student and rated person as archive columns. #5978
  reads them as-is, so nothing Alchemer-related is recomputed on any run. Cost:
  this PR also pads the live submissions model's column list.
- B: change only `round_rn` values. Smallest diff, but #5978 would re-derive the
  2022 family student from `int_surveys__alchemer_responses` on every run, which
  the user ruled out.
- A separate frozen table for family students was dropped: a second archive for
  two columns.

## Sequence

1. Re-enable both models and their tests. Point the two live survey models back
   to `ref()`.
2. In `int_surveys__alchemer_submissions`, add one pivot CTE over
   `source("alchemer", "base_alchemer__survey_results")` for the rated person,
   the student number answer, and whether any `miami_*` question was answered.
   Derive the resolved student and the rank from it.
3. Pad the Google Forms arm of `int_surveys__survey_submissions`.
4. The user rebuilds both tables in prod from the worktree.
5. Compare the rebuild with the September tables and post counts on the PR: rows
   only on one side, per-column changes by survey, and `round_rn` uniqueness per
   partition.
6. Disable both models again and point the live models back to `source()`.

## Drift measured before building

Today's model SQL, unchanged, against the frozen table: no rows gained or lost.
10 Self and Others and Manager Survey rows newly resolve an employee number, and
none lose one. 36 more change account name or UPN only. Every other column
matches. The user accepted these as corrections.

## Left to the builder

- Type of `respondent_student_number` (match `student_number` in
  `int_extracts__student_enrollments`).
- Whether a junk student number answer (not 5 or 6 digits) resolves to null, so
  the submission ranks alone, or stays as typed.
- Exact prod build command for the user.
