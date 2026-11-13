# Tableau RLS contract on `rpt_tableau__pm_outlier_detection`

Issue: [#4663](https://github.com/TEAMSchools/teamster/issues/4663). Parent
design:
`docs/superpowers/specs/2026-07-30-tableau-rls-entra-migration-design.md`
(Section 1, the contract; "`rpt_tableau__pm_outlier_detection` is deferred").

## Intent

The SchoolMint Grow Dashboard is gated, but it cannot gate on this model's rows
because the model was dropped from the RLS contract work in July over two grain
defects. Both defects are fixed on `main` (`3379da59f0`), and prod grain is
unique, so the remaining work is the contract itself.

## Decision: gate on the observer

Each row is one observer, one PM round, and one teacher the observer scored. The
outlier flags and PCs describe the observer's scoring, so the contract columns
describe the observer. Teacher attributes keep their `teacher_*` names and are
not gated.

Consequences, accepted:

- A teacher sees no rows through Tier 1; the observer and the observer's manager
  do.
- Observers based in Rooms (central office) fall outside the location gate, so
  school leaders do not see them. Prod has 14 such observer-rounds of 997.
- The Tier 5 AP branch admits only rows whose person is a Teacher. No observer
  in prod holds an AP title, so this costs APs nothing in practice.

## Approaches

- **Observer, as of the round (chosen).** Contract columns from the observer's
  primary roster row at the round's end date, which the model already joins.
  Matches the sibling extracts, which gate on the person's roster row at the
  event.
- **Observer, current roster.** Gates a coach who changed schools by today's
  school. Rejected: diverges from the other twelve extracts.
- **Tier 1 on both observer and teacher.** Needs `teacher_mail`-style columns
  and a one-off `Permissions` calc. Rejected: the design keeps the calc
  identical across workbooks.

## Design

- Add the 11 contract columns from `srh` (the observer's roster row):
  `home_business_unit_name`, `home_department_name`, `job_function`,
  `job_title`, `mail`, `user_principal_name`, `sam_account_name`,
  `reports_to_mail`, `reports_to_sam_account_name`; and `location_clean_name`,
  `campus_name` from a `left join` to `int_people__location_crosswalk` on
  `srh.home_work_location_name = lc.location_name`.
- Additive only. The existing `observer_*` and `teacher_*` columns stay, so the
  current workbook keeps working.
- No entity-abbreviation `case`. The abbreviations predate 2021 and this model
  starts at AY2023; `accepted_values` below catches one if it appears.
- Tests, all `severity: error`: `not_null` on `location_clean_name` and
  `home_business_unit_name`; `accepted_values` on `home_business_unit_name` for
  the 5 entity names (`TEAM Academy Charter School`,
  `KIPP Cooper Norcross Academy`, `KIPP Miami`, `KIPP Paterson`,
  `KIPP TEAM and Family Schools Inc.`). Prod has 0 null locations today.
- Every new column gets a `description:`; the identity and manager columns get
  `contains_pii: true`.

## Out of scope

- The workbook's `Permissions` calc (done in Tableau).
- AY2026 rows: the model holds AY2023 to AY2025 only, an upstream gap in the
  outlier script's output.

## Left to the builder

Column order within the select list (follow S6), and description wording.
