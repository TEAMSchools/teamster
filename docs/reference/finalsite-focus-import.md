# Finalsite to Focus Import

How student enrollment data moves from **Finalsite** (admissions / enrollment)
into **Focus** (the SIS) for KIPP Miami, the decisions behind it, and the
limitations the enrollment team should know about.

This page is written for the enrollment / registrar team. It describes behavior,
not code — the technical implementation lives in the `rpt_focus__*` dbt models
and is validated by automated tests.

## What the pipeline does

Each **nightly** run (3 a.m.) builds four files from current Finalsite data and
delivers them to Focus over SFTP, matching Focus's import templates:

| File               | Focus template       | Status |
| ------------------ | -------------------- | ------ |
| Demographics       | `DEMOGRAPHICS`       | Active |
| Student Enrollment | `STUDENT_ENROLLMENT` | Active |
| Addresses          | `ADDRESS`            | Active |
| Contacts           | `CONTACTS`           | Active |

The pipeline is **idempotent**: a run only sends what Focus needs — records that
are new, plus (for the feeds that allow updates) records that changed. A student
whose Focus record already matches is not re-sent. This keeps the imports small
and avoids overwriting good data in Focus.

## Key design decisions

### Student ID — minted in Finalsite

Finalsite mints a new, auto-incrementing **6-digit student ID for every new
contact**. That ID is what identifies the student in Focus, and the pipeline
reads it straight from the contact record.

> **A student needs a minted Finalsite ID to be sent.** If Finalsite has not yet
> minted an ID for a contact, that student is not included in the import. Make
> sure the ID is assigned before expecting the student to flow to Focus.

Focus stores the ID with a fixed `8400` district prefix, so the 6-digit
Finalsite ID becomes a 10-digit Focus `student_id` (e.g. `303197` →
`8400303197`). The pipeline applies that prefix, and the prefixed value is what
each record matches on in Focus.

### Enrollment codes (entry)

The entry code is derived from grade level:

| Grade        | Enrollment code |
| ------------ | --------------- |
| Kindergarten | `E05`           |
| All others   | `E01`           |

The entry code reflects how the student **entered** and does not change when a
student withdraws — a withdrawal is expressed by the drop code and end date, not
by clearing the entry code. It is written to Focus **once**; because it's
derived from grade, the pipeline never resends it, so a wrong entry code must be
corrected manually in Focus.

### Withdraw / drop codes

When a student transfers out, Finalsite records the withdrawal reason in its
`fl_state_withdraw_codes_ss` field as the full FLDOE label — e.g.
`(W02) In District Transfer`. Focus's import wants the short code (`W02`), not
the label, so the pipeline looks the label up in Focus's own withdrawal-code
list and sends the matching short code in the `DROP_CODE` column along with the
end date. Drop codes are only sent for transfer-out records — a still-enrolled
student never receives one. Unlike the entry code, the drop code **updates on
change**: if the withdrawal reason in Finalsite changes, the next run resends
the corrected code.

### What counts as a change

- **Demographics** — a student is re-sent only if they are new to Focus or a
  populated field differs from what Focus currently holds. A field left blank in
  Finalsite is never treated as a change, so a blank value will not overwrite
  data already in Focus.
- **Student enrollment** — a record is re-sent only if it is new to Focus, its
  end date has changed, or its withdraw code has changed.
- **Addresses and Contacts** — a student's address / contacts are sent only if
  Focus does not already have one for that student (import once); once Focus has
  them, the pipeline does not resend or overwrite.

### Forward-moving enrollments are protected

A Finalsite contact is reused year to year (re-enrollment keeps the same
Finalsite ID and moves the start date forward). The pipeline ensures a **new
enrollment never carries a previous year's drop code or end date** — a
withdrawal dated before the current enrollment's start is treated as belonging
to the prior enrollment and is ignored.

## Known limitations

> **Finalsite holds current enrollment only — not history.** Finalsite tracks a
> student's current enrollment state, not a multi-year history. The pipeline can
> send the current enrollment (and a re-enrollment shows up as a new start
> date), but it cannot send or backfill a prior year's enrollment as a separate
> record. Focus retains prior years from earlier imports; Finalsite is not the
> system of record for enrollment history.

- **Home language** is sent as the FLDOE language code (e.g. `EN`). This matches
  what Focus stores today, so language values will not churn on every run.
- **A few contacts have more than one withdrawal date recorded.** A contact can
  carry up to three withdrawal-date fields — `mid_year_withdrawal_date`,
  `summer_withdraw_date`, and `not_enrolling_date`. When more than one is set,
  the pipeline uses the **earliest**. This affects a very small number of
  students; the registrar should confirm which date should win in those cases.

## What the enrollment team should watch for

- **Mint the Finalsite student ID** before expecting a student in Focus —
  records without one are skipped.
- **A wrong entry code** after the first import must be fixed directly in Focus
  — the pipeline won't resend it. (A wrong withdraw code self-corrects on the
  next run once fixed in Finalsite.)
- **Flag students with multiple withdrawal dates** so the correct date can be
  confirmed.

## Questions or issues

For data questions or to report something that looks wrong in a Focus import,
contact the Data Team. Technical design history is tracked in the project's pull
requests and issues.
