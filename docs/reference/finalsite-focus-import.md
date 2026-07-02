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

The pipeline is **import-once**: each run sends only records that Focus does not
already have. Once a record has been imported, the pipeline never re-sends or
overwrites it. This keeps the imports small and — importantly — means the
pipeline never clobbers an edit made in Focus.

> **Finalsite is the source of truth only for the first import.** After a record
> lands in Focus, neither system automatically wins. The pipeline will not push
> later Finalsite changes over an existing Focus record, and it will not pull
> Focus changes back. Until a clearer process is defined, the enrollment team is
> expected to **keep the two systems aligned by hand** — a correction made after
> the initial import must be made in both Finalsite and Focus.

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

A withdrawal is recognized from a single Finalsite signal: **the last-attended
date** (`withdrawal_last_attended_date`). A student is treated as withdrawn only
when that date is populated and falls on or after the enrollment's start date.
When it is, the pipeline sends the end date together with the drop code.

The drop code itself comes from Finalsite's `fl_state_withdraw_codes_ss` field
as the full FLDOE label — e.g. `(W02) In District Transfer`. Focus's import
wants the short code (`W02`), not the label, so the pipeline looks the label up
in Focus's own withdrawal-code list and sends the matching short code in the
`DROP_CODE` column.

Like everything else, a withdrawal is a **one-time push**: it fills in an end
date and drop code only when Focus does not already have a withdrawal on that
enrollment. If Focus already shows the student as withdrawn, the pipeline leaves
it alone — a later change to the code or date must be made in Focus directly.

### Enrollment feed — enrolled students only

A student appears in the **Student Enrollment** file only once Finalsite has an
enrollment **start date** for them — that is, once they are actually enrolled.
Students who are still accepted, in progress, or only assigned a school (with no
start date yet) are held back and not sent until they enroll.

> **A student can be in Demographics, Address, and Contacts but not yet in
> Student Enrollment.** Those three files are sent as soon as the student has a
> minted ID; the enrollment record waits for the start date. This is expected —
> the enrollment flows to Focus once Finalsite records the start date.

### Enrollment start date — aligned to the first day of school

Finalsite often records an enrollment's start date as the **registration or
contract date**, which can fall weeks before school actually starts. Focus
records enrollments as of the **first day of school**. To make the two line up,
the pipeline raises any start date that falls before the first day up to the
first day of school; a start date already on or after the first day is left
unchanged (so a genuine mid-year enrollment keeps its real date).

The first day of school is read from **Focus's own attendance calendar** (the
earliest instructional day of the year), so it always matches what Focus expects
— for 2026-27 that is August 11, 2026. A school year with no calendar in Focus
yet leaves its start dates unchanged.

> **This is what lets the enrollment feed match cleanly.** Because the start
> date is aligned to Focus's first day, a student already enrolled in Focus is
> recognized as the same enrollment instead of being re-sent with a date that
> doesn't line up.

### How the pipeline knows Focus already has an enrollment

An enrollment counts as "already in Focus" when Focus has a record for the same
**student, school year, and start date** — the three values that mean the same
thing in both systems. Matched enrollments are not re-sent (see the exception
for withdrawals below).

School, grade, and entry code are **not** used to decide this. Focus stores its
own internal codes for them and translates the imported values on load, so they
never match on a literal comparison even when they describe the same school and
grade — comparing them would make every record look new.

The one thing that will still be sent for a matched enrollment is a **new
withdrawal**: if the extract now has an end date or drop code and the Focus
record has none, that exit is filled in (see Withdraw / drop codes above).

### What gets sent

Every feed follows the same import-once rule — a record is sent only when Focus
does not already have it, and nothing is ever overwritten:

- **Demographics** — a student's demographics are sent only if the student is
  not yet in Focus.
- **Student enrollment** — an enrollment is sent when it is new to Focus **and
  the student is enrolled** (has a start date); a withdrawal (end date + drop
  code) is filled in once when Focus has none yet.
- **Addresses and Contacts** — a student's address / contacts are sent only if
  Focus does not already have them for that student **and** the record is
  complete (a full address; a named contact). Blank or incomplete records are
  held back until populated (see below).

### Forward-moving enrollments are protected

A Finalsite contact is reused year to year (re-enrollment keeps the same
Finalsite ID and moves the start date forward). The pipeline ensures a **new
enrollment never carries a previous year's drop code or end date** — a
last-attended date before the current enrollment's start is treated as belonging
to the prior enrollment and is ignored.

### Address and contact formatting

Household address values are cleaned before they go to Focus so the imports stay
consistent:

- A blank or space-only field (street, city, state, zip) is normalized to
  **truly empty**, not a stray space.
- The **state is upper-cased** (e.g. `fl` becomes `FL`).

This is formatting only — whether a record is complete enough to send is covered
next.

### Blank addresses and nameless contacts are held back

Because addresses and contacts are import-once, an incomplete record sent now
would be locked in — a student imported with a blank address would keep that
empty address in Focus even after a real one is entered, because import-once
never sends them again. To prevent that, the pipeline **holds a record back
until it is complete**:

- **Addresses** — a student's address is sent only once street, city, state, and
  ZIP are all present. A student with a blank or partial address is skipped that
  run and flows the first run the full address exists in Finalsite.
- **Contacts** — a contact is sent only once it has a name. A nameless contact
  is skipped and flows once the name is filled in.

> **A student can be enrolled in Focus with no address yet.** That is expected
> when Finalsite has no complete address for them — enter the address in
> Finalsite and it flows on the next run. (Demographics is not held back this
> way; a student's demographics import as soon as the student is new to Focus.)

## Where to make corrections

After the initial import, **the pipeline never overwrites Focus** — so any
correction you make in Focus sticks. The trade-off is that the pipeline also
won't carry a later Finalsite correction into Focus. Until a clearer sync
process exists, treat the two systems as independent after the first import and
harmonize them by hand:

| Field                          | After initial import                                                        |
| ------------------------------ | --------------------------------------------------------------------------- |
| Demographics (all fields)      | Sent once. A Focus edit sticks; a later Finalsite change is **not** pushed. |
| Entry code (`ENROLLMENT_CODE`) | Sent once (derived from grade). A wrong code must be fixed in Focus.        |
| Withdraw code / end date       | Filled once when Focus has none. A later change must be made in Focus.      |
| Address, contacts              | Sent once. A Focus edit sticks.                                             |

**Correct after the first import in both systems.** Fix the record in Focus so
Focus is right today, and update Finalsite too so the two stay aligned — the
pipeline will not reconcile them for you.

## Known limitations

> **Finalsite holds current enrollment only — not history.** Finalsite tracks a
> student's current enrollment state, not a multi-year history. The pipeline can
> send the current enrollment (and a re-enrollment shows up as a new start
> date), but it cannot send or backfill a prior year's enrollment as a separate
> record. Focus retains prior years from earlier imports; Finalsite is not the
> system of record for enrollment history.

- **Home language** is sent as the FLDOE language code (e.g. `EN`), matching
  what Focus stores.
- **A withdrawal depends on the last-attended date being set in Finalsite.** If
  `withdrawal_last_attended_date` is blank, the student is treated as still
  enrolled and no end date or drop code is sent — even if other withdrawal notes
  exist in Finalsite. Make sure the last-attended date is recorded when a
  student withdraws.
- **No changes flow after the first import.** Because every feed is import-once,
  a later Finalsite edit will not reach Focus and a Focus edit will not reach
  Finalsite. The two systems are kept aligned manually.

## What the enrollment team should watch for

- **Mint the Finalsite student ID** before expecting a student in Focus —
  records without one are skipped.
- **An enrollment needs a start date.** A student reaches Focus's Student
  Enrollment file only once Finalsite has an enrollment start date; accepted or
  in-progress students wait until they enroll (they can still appear in
  Demographics, Address, and Contacts in the meantime).
- **A complete address is required before it imports.** A student with a blank
  or partial address in Finalsite gets no address in Focus — by design, since an
  empty one would lock in. Enter the full street/city/state/ZIP in Finalsite and
  it flows next run; likewise a contact needs a name before it is sent.
- **Set the last-attended date** in Finalsite when a student withdraws — it is
  what triggers the end date and drop code being sent.
- **Corrections after the first import are manual.** A wrong entry code, drop
  code, or demographic field must be fixed in Focus, and the same fix made in
  Finalsite to keep the systems aligned — the pipeline won't resend it.

## Questions or issues

For data questions or to report something that looks wrong in a Focus import,
contact the Data Team. Technical design history is tracked in the project's pull
requests and issues.
