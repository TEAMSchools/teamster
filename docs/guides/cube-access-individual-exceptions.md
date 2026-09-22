# Cube Access: Individual Exceptions

This guide is for whoever maintains the `cube_access_individual_exceptions` tab
in the Cube access spreadsheet — granting a specific person access beyond what
their role or department normally provides. For the engineering design behind
this sheet, see
[`2026-07-29-cube-access-individual-exceptions-redesign.md`](../superpowers/plans/2026-07-29-cube-access-individual-exceptions-redesign.md).
For how to add or edit a Google Sheets source in general, see the
[Google Sheets & Forms guide](google-sheets.md).

## Identify people by their Google address

Every row is keyed on **`google_email`** — the person's KIPP Google address, the
same one they sign in to Cube with. Not their employee number.

That is deliberate: it lets you grant access to a **contractor or anyone else
who has a KIPP Google login but no employment record**. Those people appear in
no HR feed, so there is nothing to look an employee number up from, and before
this they could not be granted access at all.

Two things to get right:

- **Use the address exactly as they sign in**, and nothing else — not a personal
  address, not an alias. Capitalization and stray spaces are fine; they are
  cleaned up automatically.
- **The account has to exist and be active.** A typo, or the address of someone
  whose account has been deleted, grants nothing at all rather than failing
  loudly at the moment you type it. A validation check catches typos on the next
  pipeline run.

`requested_by` and `approved_by` are still employee numbers — those are staff
approving the grant, not the person receiving it.

## Students and staff are separate columns

A row says how far it reaches for each kind of data, in the same words the role
sheet uses:

- **`additional_student_location_scope`** — student data.
- **`additional_staff_location_scope`** — staff data.

Both take `network`, `region`, `school`, or `none`. They are independent, so you
can widen one without the other: `student = school` with `staff = none` gives
someone student data at one school and no extra staff visibility at all.

**No cell in this sheet is ever left blank.** Every column takes a word or a
date, so a request form can make each field required and nobody has to work out
whether an empty cell was deliberate.

**When you set both, they must be the same word.** A row carries a single
`additional_location_name`, so it cannot be a region for staff and a school for
students at the same time. To give someone different breadth per kind of data,
use two rows.

`network` is the widest value. There is no `all` — `all` belongs to
`staff_department_scope`, which is a different question (which departments, not
which locations).

## `additional_location_name`: a real name, or `all`, or `none`

Three cases, and the word always matches how much the row actually grants:

| this row's scope     | write                           |
| -------------------- | ------------------------------- |
| `region` or `school` | the exact region or school name |
| `network`            | `all`                           |
| `none` on both axes  | `none`                          |

`all` and `none` look like they ought to be one shared "not applicable" value,
and they are not — they are opposites. A `network` row reaches **every**
location, so `all` is literally true. A row that only changes a visibility
setting reaches **no** location, so `none` is literally true. A single
placeholder would be wrong on whichever of the two it didn't describe.

Validation checks all three. A real school name on a `network` row fails — it
reads as granting that one school while actually granting everything. An `all`
left behind on a row that names a real school fails. So does a visibility-only
row still claiming a location.

## One row per additional location

Each row can grant **one** additional location — a whole network, a named
region, or a named school. If someone needs access to two schools, add **two
rows** with the same Google address, one `additional_location_name` each — never
try to combine two locations into a single row.

**Example — access to two additional schools:**

| google_email                       | additional_student_location_scope | additional_staff_location_scope | additional_location_name | status |
| ---------------------------------- | --------------------------------- | ------------------------------- | ------------------------ | ------ |
| `example.one@apps.teamschools.org` | school                            | school                          | KIPP BOLD Academy        | active |
| `example.one@apps.teamschools.org` | none                              | school                          | KIPP THRIVE Academy      | active |

This person gets staff access at both schools, but student data only at KIPP
BOLD Academy — the second row's `additional_student_location_scope` is `none`.

## There is no "All" option

List every additional region or school as its own row — there is no shortcut
value that means "all of them." If someone genuinely needs access across the
**entire network**, set the scope columns to `network` on a single row instead
of listing every region.

**Example — three additional regions** (instead of one row saying "all
regions"):

| google_email                       | additional_student_location_scope | additional_staff_location_scope | additional_location_name          |
| ---------------------------------- | --------------------------------- | ------------------------------- | --------------------------------- |
| `example.two@apps.teamschools.org` | region                            | region                          | KIPP Cooper Norcross Academy      |
| `example.two@apps.teamschools.org` | region                            | region                          | KIPP Miami                        |
| `example.two@apps.teamschools.org` | region                            | region                          | KIPP TEAM and Family Schools Inc. |

**Example — literally everything** (one row, not one per region):

| google_email                         | additional_student_location_scope | additional_staff_location_scope | additional_location_name |
| ------------------------------------ | --------------------------------- | ------------------------------- | ------------------------ |
| `example.three@apps.teamschools.org` | network                           | network                         | all                      |

## The two things a row can do

A row can do either or both of the following. A row that does neither is inert
(it exists in the sheet but grants nothing).

1. **Grant a location** (`additional_student_location_scope` /
   `additional_staff_location_scope` / `additional_location_name`) — this is
   **additive**. It adds the named location on top of the person's normal
   access; it never takes away anything they already have.
2. **Override a sensitive-field visibility setting** (`staff_department_scope`,
   `staff_pii_scope`, `staff_compensation_scope`, `staff_observations_scope`,
   `staff_benefits_scope`) — this **replaces** the person's normal setting for
   that field.

If a person has multiple rows for their location grants, put any visibility
overrides on **only one** of those rows and write `inherit` on the other rows —
the sheet will fail validation if two of a person's active rows each set any
override column. It does not matter whether the two rows agree, or whether they
set the same column: a second row carrying any value other than `inherit` in any
of the five columns fails the check.

### `inherit` versus `none` on the override columns

Each of the five override columns takes one of two "do nothing much" values, and
they are opposites. Read this twice:

- **`inherit`** leaves the person's normal setting alone. This is almost always
  what you want, and it is what goes on every override column you are not
  deliberately changing.
- **`none`** replaces their normal setting with "see nothing", which **takes
  away** access their role would otherwise give them.

Both are spelled out on purpose. An empty cell used to mean `inherit`, which
made "I did not touch this" and "I meant to revoke this" impossible to tell
apart by looking at the sheet.

`none` is a real tool — it is how you revoke someone's visibility below their
role's default — just rarely what you want.

## Granting staff access takes three columns, not one

`additional_staff_location_scope` on its own gets someone the **staff
directory** — the roster, employment and work-contact fields, for everyone in
the locations you named. It does **not** get them personal emails, cell numbers,
birth dates, or demographics. Those live behind a second gate.

Sensitive staff fields need all three of these on the same person:

| column                            | write                              |
| --------------------------------- | ---------------------------------- |
| `additional_staff_location_scope` | `network`, `region`, or `school`   |
| `staff_pii_scope`                 | `all_in_scope` or `teaching_staff` |
| `staff_department_scope`          | `all`                              |

Miss any one of the three and the person sees no sensitive fields at all. Two of
the three is the easy mistake, and it does not fail loudly at the moment you
type it — the next pipeline run turns a data test red instead.

`staff_department_scope` is the one people forget. For someone with no
employment record it starts at `none`, so unless you write `all` on their row
the department half of the gate stays shut. `own_group` does not work for them
either: with no job, they are in no department, so "their own group" is empty.

Someone who already has an employment record usually has a department setting
from their role, so for them a location grant plus `staff_pii_scope` is often
enough — but write `staff_department_scope` explicitly if you are unsure.

## What a contractor sees with no grants at all

A row that grants no location and overrides no setting leaves a contractor
seeing **nothing** — not even the staff directory. That is deliberate. The
directory is open to employees because the network publishes it to staff; a
person with no employment record reaches it only when you give them a staff
location above.

## Lifecycle: status, grant_date, expiry_date

- **`status`** — `active`, `expired`, or `revoked`. Only `active` rows (that
  have also reached their `grant_date` and haven't passed their `expiry_date`)
  actually apply.
- **`grant_date`** — the date the row starts applying. Required; use today's
  date for "right away." A future date means the grant doesn't take effect until
  that day arrives.
- **`expiry_date`** — the date the row stops applying. Required; write
  `9999-12-31` for a grant that never expires. Prefer a real date — access that
  expires on its own cannot be forgotten about.
- **To end a grant early**, set `status` to `revoked` rather than deleting the
  row — this keeps the row for audit history while making it stop applying
  immediately.

**Example — a row that has already expired, alongside a still-active one:**

| google_email                        | additional_location_name | status | expiry_date       |
| ----------------------------------- | ------------------------ | ------ | ----------------- |
| `example.four@apps.teamschools.org` | KIPP Sunrise Academy     | active | 2025-06-30 (past) |
| `example.four@apps.teamschools.org` | KIPP Seek Academy        | active | 2026-12-31        |

Only the KIPP Seek Academy grant is currently in effect — the Sunrise row is
kept for history but doesn't grant anything once its `expiry_date` has passed.

## Audit columns

`business_justification`, `requested_by`, `approved_by`, and `notes` are for
your own record-keeping — they document why a grant was made and who approved
it, but nothing in the pipeline reads them to decide access. Fill them in on
every row so the sheet stays a usable audit trail on its own.

**Example — a fully filled-in row:**

| google_email                        | additional_student_location_scope | additional_staff_location_scope | additional_location_name     | business_justification                            | requested_by | approved_by | grant_date | expiry_date | status | notes                            |
| ----------------------------------- | --------------------------------- | ------------------------------- | ---------------------------- | ------------------------------------------------- | ------------ | ----------- | ---------- | ----------- | ------ | -------------------------------- |
| `example.five@apps.teamschools.org` | region                            | region                          | KIPP Cooper Norcross Academy | Covering the Camden data audit through September. | 034521       | 011200      | 2026-07-01 | 2026-09-01  | active | Requested by Finance leadership. |
