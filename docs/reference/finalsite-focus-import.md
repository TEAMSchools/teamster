# Finalsite to Focus Import

How student enrollment data moves from **Finalsite** (admissions / enrollment)
into **Focus** (the SIS) for KIPP Miami, the decisions behind it, and the
limitations the enrollment team should know about.

This page is written for the enrollment / registrar team. It describes behavior,
not code — the technical implementation lives in the `rpt_focus__*` dbt models
and is validated by automated tests.

## What the pipeline does

Each scheduled run builds five files from current Finalsite data and delivers
them to Focus over SFTP, matching Focus's import templates:

| File               | Focus template       | Status                      |
| ------------------ | -------------------- | --------------------------- |
| Demographics       | `DEMOGRAPHICS`       | Active                      |
| Student Enrollment | `STUDENT_ENROLLMENT` | Active                      |
| Addresses          | `ADDRESS`            | Active                      |
| Contacts           | `CONTACTS`           | Active                      |
| Linked Students    | `LINKED_STUDENTS`    | Disabled for v1 (see below) |

The pipeline is **idempotent**: a run only sends records that are new to Focus
or have changed. A student whose Focus record already matches is not re-sent.
This keeps the imports small and avoids overwriting good data in Focus.

## Key design decisions

### Student ID — the `8400` prefix

Every student is sent to Focus with a student ID of `8400` followed by the
Finalsite-minted ID (for example, Finalsite `3003001` is sent as `84003003001`).
`8400` is the Florida district number, and the prefixed value matches the Focus
`students.student_id` exactly, which is how each record is matched to Focus.

> **A student needs a minted Finalsite ID to be sent.** If Finalsite has not yet
> minted a student ID for a contact, that student is not included in the import.
> Ensure the Finalsite ID is assigned before expecting the student to flow to
> Focus.

### Enrollment codes (entry)

The entry code is derived from grade level:

| Grade        | Enrollment code |
| ------------ | --------------- |
| Kindergarten | `E05`           |
| All others   | `E01`           |

The entry code reflects how the student **entered** and does not change when a
student withdraws — a withdrawal is expressed by the drop code and end date, not
by clearing the entry code.

### Withdraw / drop codes

When a student transfers out, the withdrawal reason recorded in Finalsite
(`fl_state_withdraw_codes_ss`) is translated into the matching Focus drop code
and sent in the `DROP_CODE` column along with the end date. Drop codes are only
sent for transfer-out records — a still-enrolled student never receives one.

### What counts as a change

- **Demographics** — a student is re-sent only if they are new to Focus or a
  populated field differs from what Focus currently holds. A field left blank in
  Finalsite is never treated as a change, so a blank value will not overwrite
  data already in Focus.
- **Student enrollment** — a record is re-sent only if it is new to Focus or its
  end date has changed.

### Codes import once

> **Entry and withdraw codes are written to Focus only once.** Once Focus holds
> an enrollment's entry code or drop code, the pipeline will not overwrite it on
> later runs. If a wrong code is imported the first time (for example, the wrong
> withdrawal reason), the correction must be made manually in Focus — re-running
> the pipeline will not fix it.

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

- **Addresses / Contacts / Linked Students "import once" is not yet active.**
  The Focus tables that track these links are currently empty, so this guard
  cannot be applied yet. It turns on automatically once those Focus modules hold
  data. (Tracked as requirement 1 of the project.)
- **Linked Students is turned off for v1.** The sibling-link file is not
  generated yet; the logic is in place and dormant.
- **Home language** is sent as the FLDOE language code (e.g. `EN`). This matches
  what Focus stores today, so language values will not churn on every run.
- **A few contacts have more than one withdrawal date recorded.** When multiple
  withdrawal dates are present on one contact, the pipeline uses the
  **earliest**. This affects a very small number of students; the registrar
  should confirm which date should win in those cases.

## What the enrollment team should watch for

- **Mint the Finalsite student ID** before expecting a student in Focus —
  records without one are skipped.
- **Corrections to entry or withdraw codes** after the first import must be made
  directly in Focus; the pipeline will not re-send them.
- **Flag students with multiple withdrawal dates** so the correct date can be
  confirmed.

## Questions or issues

For data questions or to report something that looks wrong in a Focus import,
contact the Data Team. Technical design history is tracked in the project's pull
requests and issues.
