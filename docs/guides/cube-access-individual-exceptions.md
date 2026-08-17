# Cube Access: Individual Exceptions

This guide is for whoever maintains the `cube_access_individual_exceptions` tab
in the Cube access spreadsheet — granting a specific person access beyond what
their role or department normally provides. For the engineering design behind
this sheet, see
[`2026-07-29-cube-access-individual-exceptions-redesign.md`](../superpowers/plans/2026-07-29-cube-access-individual-exceptions-redesign.md).
For how to add or edit a Google Sheets source in general, see the
[Google Sheets & Forms guide](google-sheets.md).

## One row per additional location

Each row can grant **one** additional location — a whole network, a named
region, or a named school. If someone needs access to two schools, add **two
rows** with the same employee number, one `additional_location_name` each —
never try to combine two locations into a single row.

**Example — access to two additional schools:**

| employee_number | additional_location_type | additional_location_name | include_student_data | status |
| --------------- | ------------------------ | ------------------------ | -------------------- | ------ |
| 045678          | school                   | KIPP BOLD Academy        | TRUE                 | active |
| 045678          | school                   | KIPP THRIVE Academy      | FALSE                | active |

This person gets staff access at both schools, but student data only at KIPP
BOLD Academy (the second row's `include_student_data` is FALSE).

## There is no "All" option

List every additional region or school as its own row — there is no shortcut
value that means "all of them." If someone genuinely needs access across the
**entire network**, use `additional_location_type = network` on a single row
instead of listing every region.

**Example — three additional regions** (instead of one row saying "all
regions"):

| employee_number | additional_location_type | additional_location_name          |
| --------------- | ------------------------ | --------------------------------- |
| 056789          | region                   | KIPP Cooper Norcross Academy      |
| 056789          | region                   | KIPP Miami                        |
| 056789          | region                   | KIPP TEAM and Family Schools Inc. |

**Example — literally everything** (one row, not one per region):

| employee_number | additional_location_type | additional_location_name |
| --------------- | ------------------------ | ------------------------ |
| 012345          | network                  | _(leave blank)_          |

## The two things a row can do

A row can do either or both of the following. A row that does neither is inert
(it exists in the sheet but grants nothing).

1. **Grant a location** (`additional_location_type` / `additional_location_name`
   / `include_student_data`) — this is **additive**. It adds the named location
   on top of the person's normal access; it never takes away anything they
   already have.
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

| employee_number | additional_location_name | status | expiry_date       |
| --------------- | ------------------------ | ------ | ----------------- |
| 090123          | KIPP Sunrise Academy     | active | 2025-06-30 (past) |
| 090123          | KIPP Seek Academy        | active | 2026-12-31        |

Only the KIPP Seek Academy grant is currently in effect — the Sunrise row is
kept for history but doesn't grant anything once its `expiry_date` has passed.

## Audit columns

`business_justification`, `requested_by`, `approved_by`, and `notes` are for
your own record-keeping — they document why a grant was made and who approved
it, but nothing in the pipeline reads them to decide access. Fill them in on
every row so the sheet stays a usable audit trail on its own.

**Example — a fully filled-in row:**

| employee_number | additional_location_type | additional_location_name     | business_justification                            | requested_by | approved_by | grant_date | expiry_date | status | notes                            |
| --------------- | ------------------------ | ---------------------------- | ------------------------------------------------- | ------------ | ----------- | ---------- | ----------- | ------ | -------------------------------- |
| 023456          | region                   | KIPP Cooper Norcross Academy | Covering the Camden data audit through September. | 034521       | 011200      | 2026-07-01 | 2026-09-01  | active | Requested by Finance leadership. |
