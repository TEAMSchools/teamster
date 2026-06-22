# Staff PII gate on `staff_detail` — design

Issue: [#4236](https://github.com/TEAMSchools/teamster/issues/4236)

## Problem

The `staff_detail` Cube view exposes identifiable, row-level staff data behind a
single `cube-access-staff-data` access tier. Anyone cleared to see the staff
roster sees every field, including personal contact details, date of birth, and
demographics. We need a "see staff but not their personal/sensitive data" tier
so that those fields are restricted to a smaller, explicitly-provisioned group.

## Goal

Add a `cube-access-staff-pii` sub-tier to `staff_detail`, mirroring the existing
student two-tier `access_policy` pattern, so six personal/sensitive fields are
visible only to members of that group.

## Non-goals

- **Small-cell / low-n suppression** of aggregate demographic breakdowns. That
  is a value-dependent, post-aggregation problem that Cube `access_policy`
  cannot express, and it spans far more than this view (survey, performance, and
  compensation breakdowns). Tracked separately in
  [#4237](https://github.com/TEAMSchools/teamster/issues/4237).
- **Gating staff-directory info.** Names, `staff_unique_id`, work/Google email,
  Active Directory username, and manager identifiers stay visible to all
  `cube-access-staff-data` users. They are already internally visible (Outlook
  profiles) and seen by no outside party.
- **`staff_summary`** changes. Its `gender_identity` / `race` / `is_hispanic`
  are deidentified aggregate breakdowns, not row-level identifiers.

## Gated fields

These six move behind `cube-access-staff-pii` (excluded from
`cube-access-staff-data`):

| Field                 | Why                     |
| --------------------- | ----------------------- |
| `personal_email`      | Personal contact        |
| `personal_cell_phone` | Personal contact        |
| `birth_date`          | Date of birth           |
| `gender_identity`     | Demographic (row-level) |
| `race`                | Demographic (row-level) |
| `is_hispanic`         | Demographic (row-level) |

## Approach

Follow the established student two-tier pattern (see
`student_enrollments_detail.yml`): one `cube-access-staff-data` block with
`includes: "*"` and an `excludes:` list, plus a `cube-access-staff-pii` block
with `includes: "*"`. A user in both groups gets the union (full access).

A rejected alternative was splitting `staff_detail` into two separate views (PII
/ non-PII). That duplicates the entire view definition and diverges from the
student convention; the two-block policy is simpler and consistent.

### Access-policy behavior

- `cube-access-staff-pii` member → sees all fields.
- `cube-access-staff-data` member (not PII) → sees all fields except the six.
- Member of both → union → all fields.
- The existing `locations` scope filter in `cube.js` `queryRewrite` is unchanged
  and continues to apply to both tiers.

## Change set

### 1. `src/cube/model/views/staff/staff_detail.yml`

Replace the single `access_policy` block with two:

```yaml
access_policy:
  # Non-PII staff tier: roster/employment structure without personal or
  # sensitive data. Personal contact, DOB, and demographics are gated to
  # cube-access-staff-pii. Work-directory info (names, work/google email,
  # AD username, manager contacts) stays visible — already internally public.
  - group: cube-access-staff-data
    member_level:
      includes: "*"
      excludes:
        - personal_email
        - personal_cell_phone
        - birth_date
        - gender_identity
        - race
        - is_hispanic
  - group: cube-access-staff-pii
    member_level:
      includes: "*"
```

### 2. `src/cube/model/cubes/staff/staff.yml`

Re-comment the dimensions to reflect the actual tiers. Current comments are
inconsistent: the demographic dimensions are uncommented, while directory
identifiers are mislabeled `# PII —`.

| Fields                                                                                                               | New comment                                                                                                  |
| -------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| `personal_email`, `personal_cell_phone`                                                                              | `# Gated to cube-access-staff-pii — personal contact.`                                                       |
| `birth_date`                                                                                                         | `# Gated to cube-access-staff-pii — date of birth.`                                                          |
| `gender_identity`, `race`, `is_hispanic`                                                                             | `# Demographic — gated to cube-access-staff-pii in staff_detail; aggregate-only breakdown in staff_summary.` |
| `staff_unique_id`, `full_name`, `first_name`, `last_name`, `work_email`, `google_email`, `active_directory_username` | `# Staff-directory identifier — visible to all cube-access-staff-data (internally public).`                  |

`staff_work_history.yml` has no PII comments and needs no change.

### 3. `src/cube/CLAUDE.md`

Update the "Staff views" access-policy note (currently says to add a
`cube-access-staff-pii` sub-tier "only if a see-staff-but-not-PII need arises")
to document the now-implemented two-tier pattern, matching how the student
detail/summary split is described.

### No `cube.js` change

`contextToGroups` resolves a requester's `cube-*` group membership dynamically,
so the new group name is picked up automatically. PII sub-tiers are enforced
entirely in view YAML — confirmed that `cube.js` references no PII-tier group in
code (only a comment).

## Rollout prerequisite

The `cube-access-staff-pii` Google Workspace group must be created and members
enrolled before or with this deploy. Group membership is direct-only (Admin
Directory API; no transitive resolution). **On merge, any
`cube-access-staff-data` user not also in the new group loses the six fields.**
Group provisioning is an admin task outside this repo and must be coordinated.

## Testing / verification

- Validate the branch in Cube Cloud Dev Mode (Data Model → Dev Mode → add branch
  by name) — branch staging envs are not auto-created from pushes.
- Confirm via `/sql` (or `meta` + `load`) that a `cube-access-staff-pii` context
  resolves all members and a `cube-access-staff-data`-only context excludes the
  six fields. `/sql` compiles even against hidden members; `/load` enforces
  hiding, so verify with `load`.
- Confirm `staff_summary` is unaffected.
