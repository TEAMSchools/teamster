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

Both take `network`, `region`, `school`, or `none` (a blank cell means `none`).
They are independent, so you can widen one without the other —
`student = school` with `staff = none` gives someone student data at one school
and no extra staff visibility at all.

**When you set both, they must be the same word.** A row carries a single
`additional_location_name`, so it cannot be a region for staff and a school for
students at the same time. To give someone different breadth per kind of data,
use two rows.

`network` is the widest value. There is no `all` — `all` belongs to
`staff_department_scope`, which is a different question (which departments, not
which locations).

## When to leave `additional_location_name` blank

Leave it blank **only** when the scope is `network`, because `network` already
means every location and there is nothing left to name. For `region` or `school`
the name is required, and a blank one fails validation on the next pipeline run
rather than silently granting nothing.

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
| `example.three@apps.teamschools.org` | network                           | network                         | _(leave blank)_          |

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
overrides on **only one** of those rows and leave the rest blank on the other
rows — the sheet will fail validation if two of a person's active rows disagree
on the same setting.

## Lifecycle: status, grant_date, expiry_date

- **`status`** — `active`, `expired`, or `revoked`. Only `active` rows (that
  have also reached their `grant_date` and haven't passed their `expiry_date`)
  actually apply.
- **`grant_date`** — the date the row starts applying. Leave blank for
  "immediately." A future date means the grant doesn't take effect until that
  day arrives.
- **`expiry_date`** — the date the row stops applying. Leave blank for "never
  expires."
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
