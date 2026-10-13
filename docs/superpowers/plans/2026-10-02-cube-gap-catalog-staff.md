# Cube Gap Catalog — Staff

Part of the [Cube Connector Gap Catalog](2026-10-02-cube-gap-catalog.md). Refs
#5673. One section per core-set dashboard; tables and notes are the per-workbook
inventory extracted from the production .twb and classified against the dbt
marts and Cube model YAML as of 2026-10-02.

## Staff Roster (`staff_roster`)

- workbook: Staff Roster | contentUrl `StaffRoster` | luid
  `6e0915eb-9a46-4971-8e97-6e0749066b9f` | project Production
- upstream datasources: `rpt_tableau__staff_roster (kipptaf_tableau)` —
  embedded, single federated datasource for every sheet (plus a local
  `Parameters` pseudo-datasource for two string parameters). No other datasource
  in the workbook.
- rpt_/source models in use: `rpt_tableau__staff_roster` (reads
  `int_people__staff_roster`, `int_people__years_experience`,
  `int_people__leadership_crosswalk`). **This settles the Asana discrepancy
  noted in the task prompt: `rpt_tableau__staff_roster` is this workbook's
  (Staff Roster) datasource, confirmed via `get-workbook` `upstreamDatasources`.
  If the NJ Certification Dashboard's Asana task also claims it as its model,
  that claim is either wrong or describes a second, separate consumer of the
  same rpt\_ model — Staff Roster is a real, confirmed consumer.**
- published dashboards inventoried: **Staff Roster**, **Additional Info
  (protected)** — these are the only two entries in the Tableau Server
  `get-workbook` views list (`StaffRoster/sheets/StaffRosterdisabled`,
  `StaffRoster/sheets/AdditionalInfoprotected`). The `.twb` additionally
  contains 5 more `<dashboard>` elements with no `hidden='true'` flag anywhere
  in `<windows>` — **Manager Audit**, **Staff Demographics**, **Updated
  Preferred Race & Gender**, **Work Assignments**, **Work Assignments_archive**
  — but none of them appear as a server view. Per the task's "when in doubt,
  include it and flag" rule, all 7 are inventoried below, with the 5
  non-server-published ones flagged `[not a published server view]` in their row
  notes.
- sheets excluded as hidden/scratch: 5 — `DSO-School View`,
  `Demographics-Job Group`, `Demographics-managers`, `Years Teaching`,
  `Years with KIPP NJ`. Each exists as a `<worksheet>` in the `.twb` but is not
  placed in any dashboard's `<zones>`, so it is unreachable from any published
  or unpublished dashboard — true orphan/scratch sheets.
- regions served by this dashboard overall: **all** (network-wide including
  CMO/KTAF). No region/district filter exists anywhere in the workbook; the only
  entity-like filter is on `legal_entity_name` ("Entity"), and per
  `src/dbt/kipptaf/CLAUDE.md` that column takes values for every region PLUS
  `KIPP TEAM and Family Schools Inc.` (KTAF/CMO) — confirmed network-wide
  including CMO, not merely assumed from the task hint.

### Measures

| metric                                                    | agg                                                          | source field / formula (trimmed)                                                                     | dashboards                                                                                                     | status        | where                                                                                                                                                                                                                                                                                                                                          | regions |
| --------------------------------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Staff headcount (`Number of Records`)                     | Sum/Min (dedup for labels)                                   | `[Number of Records]` = `1` per row                                                                  | Staff Roster, Additional Info (protected), Staff Demographics, Work Assignments, Manager Audit [not published] | cube-covered  | `staff_work_history.count_employees` (count_distinct staff_key) via `staff_directory` view — **grain caveat**: Tableau counts rows in the ADP-sourced roster extract (one row per person as of refresh), Cube's measure counts distinct `staff_key` within a date-filtered SCD2 period slice; same meaning, different underlying grain/filters | all     |
| % of Total by Gender / Race-Ethnicity                     | `PERCENT_OF_TOTAL` table calc (`pcto:sum:Number of Records`) | table calc over `Number of Records`, partitioned by Gender/Race Ethnicity Reporting                  | Staff Demographics, Updated Preferred Race & Gender [not published]                                            | workbook-only | pure Tableau display calc over the already-available headcount measure; no warehouse metric needed to reproduce it                                                                                                                                                                                                                             | all     |
| Count of staff with a manager (`cnt:manager_name`)        | Count (non-null)                                             | `COUNT([manager_name])`, compared implicitly against total headcount to find staff missing a manager | Manager Audit [not published]                                                                                  | mart-ready    | `dim_staff_work_history.manager_staff_key` (surfaced as `staff_work_history.staff_manager` join in Cube) — a `COUNT(manager_staff_key)` vs `count_employees` gap would reproduce this audit                                                                                                                                                    | all     |
| Years at KIPP (`years_at_kipp_total`)                     | none (per-row attribute, not aggregated)                     | `rpt_tableau__staff_roster.years_at_kipp_total`                                                      | Staff Roster                                                                                                   | mart-missing  | `src/dbt/kipptaf/models/people/intermediate/int_people__years_experience.years_at_kipp_total`, read into `rpt_tableau__staff_roster` — not in `dim_staff`/Cube                                                                                                                                                                                 | all     |
| Tenure (`DATEDIFF('year', Hire Date, today/termination)`) | none (calc field, role=dimension but numeric)                | `DATEDIFF("year", IFNULL([rehire_date],[original_hire_date]), IFNULL([termination_date],TODAY()))`   | Staff Roster, Additional Info (protected)                                                                      | workbook-only | derived client-side from cube-covered `staff.original_hire_date`/`rehire_date`, but `termination_date` (needed for terminated staff) has no Cube/mart home — see Dimensions                                                                                                                                                                    | all     |

### Dimensions

| dimension                                                                                                                                   | used as                                                                  | status                     | where                                                                                                                                                                                                                                       | regions |
| ------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | -------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Department (`home_department_description`)                                                                                                  | filter, column                                                           | cube-covered               | `staff_work_history.department_name`                                                                                                                                                                                                        | all     |
| Job Title (`job_title_description`)                                                                                                         | filter, column                                                           | cube-covered               | `staff_work_history.position_title`                                                                                                                                                                                                         | all     |
| Job Group (`[Job Title (group)]`, Tableau "Create Group" bucket)                                                                            | filter, column                                                           | workbook-only              | ad hoc Tableau grouping of job titles; `staff_cube_access.job_function_code`/`job_function_level` is a different, coarser taxonomy — not a drop-in replacement                                                                              | all     |
| Position Status (`position_status`)                                                                                                         | filter, column                                                           | cube-covered               | `staff_work_history.status_name`                                                                                                                                                                                                            | all     |
| Position Status (group) (categorical-bin)                                                                                                   | filter                                                                   | workbook-only              | same caveat as Job Group — ad hoc bucket                                                                                                                                                                                                    | all     |
| Entity (`legal_entity_name`)                                                                                                                | filter, column                                                           | cube-covered               | `staff_work_history.business_unit_name` (KTAF vs Region split documented in `src/dbt/kipptaf/CLAUDE.md`)                                                                                                                                    | all     |
| Location (`location_description`)                                                                                                           | filter, column                                                           | cube-covered               | `staff_work_history.locations.location_name` (`locations_location_name` on `staff_directory`)                                                                                                                                               | all     |
| Manager (`manager_name`)                                                                                                                    | column, audit key                                                        | cube-covered               | `staff_directory.staff_manager_full_name` (via `staff_work_history.staff_manager` join)                                                                                                                                                     | all     |
| Original Hire Date (`original_hire_date`)                                                                                                   | filter, column                                                           | cube-covered               | `staff.original_hire_date`                                                                                                                                                                                                                  | all     |
| Rehire Date (`rehire_date`)                                                                                                                 | column                                                                   | cube-covered               | `staff.rehire_date`                                                                                                                                                                                                                         | all     |
| Termination Date (`termination_date`)                                                                                                       | column (feeds Tenure/Hire Date calcs)                                    | mart-missing               | `rpt_tableau__staff_roster.termination_date` (ADP `worker_termination_date` via `int_people__staff_roster`); closest mart proxy is `status_name = 'Terminated'` + `effective_end_date` on `dim_staff_work_history`, not an exact substitute | all     |
| Is Teacher? (calc on `job_title_description`)                                                                                               | filter, column                                                           | workbook-only              | built from cube-covered `staff_work_history.position_title`; no equivalent boolean flag in Cube/marts                                                                                                                                       | all     |
| Associate Id (`associate_id`)                                                                                                               | filter, column, search key                                               | mart-missing               | `rpt_tableau__staff_roster.associate_id` (ADP `worker_id`, via `int_people__staff_roster`) — not on `dim_staff`                                                                                                                             | all     |
| Df Employee Number (`df_employee_number`)                                                                                                   | column, search key                                                       | mart-missing               | `rpt_tableau__staff_roster.df_employee_number` (ADP `employee_number`) — `dim_staff` exposes only the hashed `staff_key`/`staff_unique_id`, not this raw id                                                                                 | all     |
| First Name / Last Name (legal, `first_name`/`last_name`)                                                                                    | column, search key                                                       | mart-missing               | `rpt_tableau__staff_roster.first_name`/`last_name` (ADP legal name) — Cube's `staff.first_name`/`last_name` are explicitly _preferred_ name only (see note below)                                                                           | all     |
| Preferred First / Preferred Last / Preferred Name                                                                                           | column                                                                   | cube-covered               | `staff.first_name` / `staff.last_name` / `staff.full_name` (Cube's name dimensions are documented as preferred-name)                                                                                                                        | all     |
| Email (`userprincipalname`)                                                                                                                 | search key                                                               | cube-covered (approximate) | closest match `staff.work_email` or `staff.active_directory_username`; field-name/source alignment not independently verified                                                                                                               | all     |
| Personal Mobile (`personal_contact_personal_mobile`)                                                                                        | search key                                                               | cube-covered               | `staff_pii.personal_cell_phone` (PII-gated view)                                                                                                                                                                                            | all     |
| Program Memberships (`memberships`)                                                                                                         | column, filter input                                                     | mart-missing               | `rpt_tableau__staff_roster.memberships`, via `int_people__staff_roster` — no Cube/mart equivalent                                                                                                                                           | all     |
| Is Leader/Teacher Development Program (`is_leader_development_program`, `is_teacher_development_program`)                                   | filter input (via parameter calc)                                        | mart-missing               | same source as above — not in Cube/marts                                                                                                                                                                                                    | all     |
| In Development Program (calc)                                                                                                               | filter                                                                   | workbook-only              | built from the two mart-missing flags plus `memberships` and a parameter                                                                                                                                                                    | all     |
| Benefits Eligibility Class Description                                                                                                      | column                                                                   | mart-missing               | `rpt_tableau__staff_roster.benefits_eligibility_class_description` (ADP), via `int_people__staff_roster` — not in Cube/marts                                                                                                                | all     |
| Is Management (`is_management`)                                                                                                             | column                                                                   | cube-covered               | `staff_work_history.is_management_position`                                                                                                                                                                                                 | all     |
| Race Ethnicity Reporting (`race_ethnicity_reporting`)                                                                                       | filter, column                                                           | cube-covered (approximate) | `staff.race` (staff_pii) — meaning match (racial category for reporting), field name differs; not independently confirmed to share derivation logic                                                                                         | all     |
| Gender — updated/self-reported (`gender_identity`)                                                                                          | filter, column                                                           | cube-covered               | `staff.gender_identity` (staff_pii)                                                                                                                                                                                                         | all     |
| Gender — legacy (`gender`)                                                                                                                  | column (older "Gender" worksheet, distinct field from `gender_identity`) | mart-missing               | plain ADP gender code predating the "Updated Preferred Gender" initiative; Cube only exposes the coalesced `gender_identity`, not a raw-ADP-only code                                                                                       | all     |
| Worker Category Description (`worker_category_description`)                                                                                 | column                                                                   | cube-covered               | `staff_work_history.worker_type`                                                                                                                                                                                                            | all     |
| Full Name (calc, `IFNULL(preferred_name, last+', '+first)`)                                                                                 | column                                                                   | workbook-only              | built from cube-covered name fields                                                                                                                                                                                                         | all     |
| Search Everything / Search Filter / Status Filter / Start Date / Permissions Group Filter (`ISMEMBEROF(...)`) / Updated both fields / Blank | parameter, filter, or security-scaffolding calc                          | workbook-only              | pure Tableau parameter/filter/security plumbing — Permissions Group Filter in particular gates the "Additional Info" dashboard by AD group membership, not row-level data access                                                            | n/a     |

### Notes

- Single embedded datasource (`rpt_tableau__staff_roster`) feeds all 7
  dashboards and all 18 worksheets — there is no second datasource to reconcile.
- Judgment call: the workbook carries two independently-tracked name pairs
  (legal `first_name`/`last_name` vs. `preferred_first`/`preferred_last`). Only
  the preferred pair has a Cube counterpart (`staff.first_name` is documented as
  preferred-name only), so legal name is marked mart-missing even though a
  same-named column exists on `dim_staff`/Cube — this is a **meaning** mismatch
  (legal vs. preferred), not a true cube-covered match. Same logic applied to
  `gender` (legacy ADP code) vs. `gender_identity` (coalesced/self-reported) —
  only the latter is cube-covered.
- "Job Group" / "Position Status (group)" are Tableau's native **group** feature
  (`calc_class="categorical-bin"`, no stored formula) — these bucket raw values
  ad hoc inside the workbook and have no dbt/Cube equivalent to check against;
  flagged workbook-only rather than guessed into a mart match.
- `Race, Ethnicity & Gender` worksheet is excluded from the Measures/ Dimensions
  tables beyond what's already listed — it reuses the same `gender`,
  `race_ethnicity_reporting`, `position_status`, `legal_entity_name`,
  `location_description`, `job_title_description`,
  `benefits_eligibility_class_description`, `is_management`,
  `original_hire_date` dimensions already rows above plus the same headcount
  measure; collapsed per the "group near-identical variants" instruction.
- 5 dashboards (`Manager Audit`, `Staff Demographics`,
  `Updated Preferred Race & Gender`, `Work Assignments`,
  `Work Assignments_archive`) exist in the `.twb` but are **not** in the Tableau
  Server `get-workbook` views list for this workbook — they may be retained in
  the file for authoring/history purposes (note the `_archive` suffix on one)
  without ever having been published as separate server views, or
  published-then-unpublished. Flagging as a genuine gap rather than guessing;
  worth a follow-up if this inventory feeds a go/no-go decision that counts
  dashboards.
- PII caveat: `Manager Audit`, `Staff Job Roster`, and the
  `Additional Info (protected)` dashboards surface identifying fields (associate
  id, employee number, legal/preferred name, personal mobile) gated in Cube's
  `staff_pii` view by remit-scoped row-level security; the Tableau side gates
  `Additional Info (protected)` only by an AD-group `ISMEMBEROF` calc
  (`Permissions Group Filter`), a materially different access model than Cube's
  remit-based RLS.

### Verification

- cube-covered spot-check: `Department` (`home_department_description`) —
  `src/cube/model/cubes/staff/staff_work_history.yml` line 110, measure/dim
  `department_name` (`sql: department_name`, `public: true`), surfaced on the
  `staff_directory` view (`src/cube/model/views/staff/staff_directory.yml` line
  103).
- mart-ready spot-check: `Count of staff with a manager` audit measure —
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_work_history.sql` produces
  `manager_staff_key` (FK to `dim_staff.staff_key`), documented in
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_history.yml`
  lines 57-71.
- mart-missing spot-check: `Associate Id` / `Df Employee Number` —
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__staff_roster.sql` lines
  2-3 (`b.employee_number as df_employee_number`, `b.worker_id as associate_id`,
  from `int_people__staff_roster`); neither column appears in
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff.yml`.

## Staff Attrition Dashboard (`staff_attrition_dashboard`)

- workbook: Attrition Dashboard | contentUrl `AttritionDashboard` | luid
  `5bf99669-00bb-4906-b2b4-79f2976ac3a4` | project Production
- upstream datasources: `rpt_tableau__staff_attrition_details (kipptaf_tableau)`
  (embedded, federated — primary), `int_people__staff_roster (kipptaf_people)`
  (embedded, listed on the workbook but NOT referenced by any field on the
  published dashboard's 9 in-scope worksheets — unused leftover datasource)
- rpt_/source models in use (from datasource + field lineage):
  `rpt_tableau__staff_attrition_details` ← `int_people__staff_attrition_details`
  ← `int_people__staff_roster_history` (legacy ADP+Dayforce roster-history
  chain). Separately, marts now ship `fct_staff_attrition` ←
  `dim_work_assignment_status` / `dim_work_assignment_primary` /
  `dim_work_assignment_jobs` (ADP-only work-assignment dims) — **this dashboard
  does NOT read that newer mart**; see Notes.
- published dashboards inventoried: `Attrition Dashboard` (the only one
  published as a server View for this workbook — confirmed via `list-views`
  filtered to this workbook id, which returns exactly one view). Zones:
  `% Attrition`, `% Terminated & % Resigned`, `% Terminated Detailed`, `Bars!`,
  `Feedback`, `Help guide`, `Quick Hits (last 2 years)`, `Year Over Year`,
  `attrition explanation`.
- sheets excluded as hidden/scratch: 7 — `Departure Reason`,
  `Retention by Manager`, `Retention by PM Score`,
  `Retention by Race/Ethnicity`, `Retention by Year`,
  `Retention by Years at KIPP`, `Retention by role`. All 7 are exclusive to
  `Attrition Protocol View`, a dashboard present in the `.twb` but **not**
  published as a server View (only `Attrition Dashboard` is — verified via
  `mcp__tableau__list-views`). `Attrition Dashboard - Archive (to delete)` is
  likewise unpublished but introduces no worksheet beyond the live dashboard, so
  nothing further excluded there.
- regions served by this dashboard overall: `all` (network-wide). No hard region
  filter found in the workbook; the `Entity` dimension (KTAF vs. Region, from
  `business_unit_home_name`) lets a viewer slice but does not restrict the
  underlying data. Access is instead gated by a Tableau-native `ISMEMBEROF()`
  group-permission calc (`Drilldown Permissions` / `Aggregate Permissions`) — a
  server AD-group check, unrelated to Cube's RLS.

### Measures

| metric                                                                                                                                          | agg                              | source field / formula (trimmed)                                                                                                                                                                                               | dashboards                                                                                     | status       | where                                                                                                                                                                                                                                                                                                                                                                                         | regions |
| ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Headcount in scope / Retention Counter                                                                                                          | SUM / COUNT                      | `Retention Counter` = `IF is_attrition=1 THEN 0 ELSE 1`; `"1"` = literal 1 (row marker); `cnt:rpt_tableau__staff_attrition_details` = row count                                                                                | % Attrition, % Terminated & % Resigned, % Terminated Detailed, Bars!, Quick Hits               | mart-ready   | `rpt_tableau__staff_attrition_details.is_attrition` (row count / negation)                                                                                                                                                                                                                                                                                                                    | all     |
| Attrition rate (% Attrition)                                                                                                                    | ratio                            | `Total Attrition` = `is_attrition / {FIXED academic_year: SUM("1")}`; `Attrition Counter` = `-is_attrition` (sign-flip tooltip helper)                                                                                         | % Attrition, Bars! (via Level-of-Detail=Attrition/Retained split), Year Over Year (cumulative) | mart-ready   | `rpt_tableau__staff_attrition_details.is_attrition` (ratio computed in Tableau FIXED LOD, not warehouse)                                                                                                                                                                                                                                                                                      | all     |
| % breakdown by status category (Termination / Resignation / Non-Renew / Other / Retained), incl. "All Terminations"/"All Resignations" roll-ups | SUM, pcto (% of total)           | `Termination Counter`, `Resignation Counter`, `Non-Renew Counter`, `Other Counter` = `IF is_attrition=1 AND [Status Reason (group)]='X' THEN -1 ELSE 0`; combined into `All Terminations Counter` / `All Resignations Counter` | % Terminated & % Resigned, % Terminated Detailed, Bars! (parameter-driven), Quick Hits         | mart-missing | raw `termination_reason` lives on `rpt_tableau__staff_attrition_details.sql` (from `int_people__staff_attrition_details.termination_reason`, ultimately ADP `assignment_status_reason` via `int_people__staff_roster_history`), but the Termination/Resignation/Non-Renew/Other bucketing (`Status Reason (group)`) is a Tableau-native Group with no formula captured and no mart equivalent | all     |
| Resignation sub-split: Regrettable vs. Not Regrettable                                                                                          | SUM                              | `Resignation - Regrettable Counter` / `Resignation - Not Regrettable Counter` = text-match on `termination_reason` containing "Regrettable"/"Not Regrettable"                                                                  | % Terminated & % Resigned, % Terminated Detailed (tooltip-only)                                | mart-missing | same `termination_reason` column; regrettable/not-regrettable split exists only as Tableau string matching, no mart column                                                                                                                                                                                                                                                                    | all     |
| Drilldown N Count (Sizing)                                                                                                                      | FIXED LOD COUNT(employee_number) | `{FIXED academic_year, [Show me...], [Show me...2nd Level] : COUNT(employee_number)}`                                                                                                                                          | Bars! (mark-size encoding)                                                                     | mart-ready   | `rpt_tableau__staff_attrition_details.employee_number` (distinct count, groupable by any breakdown dim already in the mart)                                                                                                                                                                                                                                                                   | all     |
| Cumulative attrition rate by month (Year-over-Year trend)                                                                                       | cumulative SUM                   | `cum:sum(Total Attrition)` over `MIN(termination_date)`, colored by `academic_year`                                                                                                                                            | Year Over Year                                                                                 | mart-missing | inputs (`is_attrition`, `termination_date`) are mart-ready on `rpt_tableau__staff_attrition_details.sql`; the month-over-month cumulative-% curve itself is a Tableau table calc with no mart or Cube equivalent                                                                                                                                                                              | all     |
| Program Filter (Leader/Teacher Development Program membership)                                                                                  | boolean flag used as filter      | `Program Filter` = `IF [Parameters].[Programs]='No Program' THEN TRUE ELSEIF ...(is_leader_development_program OR is_teacher_development_program)...`                                                                          | all 4 chart sheets (filter)                                                                    | mart-ready   | `rpt_tableau__staff_attrition_details.is_leader_development_program` / `is_teacher_development_program` (raw mart columns; Tableau only adds the parameter-driven IF)                                                                                                                                                                                                                         | all     |
| `fct_staff_attrition` mart measures (NOT used by this dashboard)                                                                                | —                                | `is_attrition` by `type` (foundation / nj_compliance / recruitment), `termination_reason`, `cutoff_date`                                                                                                                       | none — informational                                                                           | n/a          | `src/dbt/kipptaf/models/marts/facts/fct_staff_attrition.sql` — a parallel, newer ADP-work-assignment-only attrition definition with 3 academic-year-window methodologies; different grain and lineage than what the dashboard reads                                                                                                                                                           | n/a     |

Variants collapsed into rows above: `Attrition Counter`, `Counter (copy 2)` (=
Retention Counter), the per-reason `-1/0` counters, and the
regrettable/not-regrettable split are all sign-flipped SUM variants of the same
two underlying facts (`is_attrition`, `termination_reason`) — counted once each
above rather than per Tableau field name.

### Dimensions

| dimension                                                                              | used as                                                   | status                                         | where                                                                                                                                                                                                                                                               | regions |
| -------------------------------------------------------------------------------------- | --------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Academic Year (`academic_year`)                                                        | rows/cols, filter, color                                  | cube-covered                                   | `src/cube/model/cubes/staff/staff_work_history.yml` → `dates` join; exposed as `dates_academic_year` on `staff_directory.yml` / `staff_pii.yml`                                                                                                                     | all     |
| Entity / Legal Entity Name (display) (KTAF vs. Region, from `business_unit_home_name`) | filter, rows                                              | cube-covered                                   | `staff_work_history.business_unit_name`, exposed on `staff_directory.yml` (name differs slightly — raw business unit name vs. the workbook's KTAF-coalesced display calc)                                                                                           | all     |
| Status / Retained or Attrition / Status Reason (group)                                 | color, cols, filter                                       | cube-covered (by meaning, coarser granularity) | `staff_work_history.status_name` / `status_reason`, exposed on `staff_directory.yml`; Cube's `status_reason` is the raw ADP reason text, not pre-bucketed into Termination/Resignation/Non-Renew/Other like the workbook's Tableau Group                            | all     |
| Home Work Location Name / Location                                                     | filter, breakdown ("Show me...")                          | cube-covered                                   | `staff_work_history.locations` join → `locations_location_name` on `staff_directory.yml`                                                                                                                                                                            | all     |
| Department Home Name                                                                   | breakdown ("Show me...")                                  | cube-covered                                   | `staff_work_history.department_name`, exposed on `staff_directory.yml`                                                                                                                                                                                              | all     |
| Race/Ethnicity Reporting                                                               | breakdown ("Show me...")                                  | cube-covered (by meaning)                      | `staff.race`, exposed on `staff_pii.yml` (PII-gated; workbook's "reporting" category may bucket differently than Cube's raw `race`)                                                                                                                                 | all     |
| Gender Identity                                                                        | breakdown ("Show me...")                                  | cube-covered                                   | `staff.gender_identity`, exposed on `staff_pii.yml` (PII-gated)                                                                                                                                                                                                     | all     |
| Job Title                                                                              | detail, tooltip                                           | cube-covered (by meaning)                      | `staff_work_history.position_title`, exposed on `staff_directory.yml` (free-text position title; not the same value set as the workbook's job_title but same concept)                                                                                               | all     |
| Job Group / Primary Job (group)                                                        | breakdown ("Show me...")                                  | mart-missing                                   | Tableau-native Group over `job_title` on `rpt_tableau__staff_attrition_details`; no mart or Cube "job group" bucketing exists (Cube's closest fields, `job_function_code`/`job_function_level`, are a different classification scheme from `dim_staff_cube_access`) | all     |
| Program membership flags (Leader/Teacher Development Program)                          | filter                                                    | mart-ready                                     | `rpt_tableau__staff_attrition_details.is_leader_development_program` / `is_teacher_development_program`                                                                                                                                                             | all     |
| Memberships (free-text)                                                                | tooltip/detail                                            | mart-ready                                     | `rpt_tableau__staff_attrition_details.memberships`                                                                                                                                                                                                                  | all     |
| Years at KIPP (`year_at_kipp`)                                                         | tooltip                                                   | mart-ready                                     | `int_people__staff_attrition_details.year_at_kipp` (carried through to the rpt model)                                                                                                                                                                               | all     |
| Termination Date                                                                       | cols (Year Over Year)                                     | mart-ready                                     | `rpt_tableau__staff_attrition_details.termination_date`                                                                                                                                                                                                             | all     |
| Show me... / Show me...2nd Level (parameter-driven dimension swap)                     | rows (Bars!)                                              | workbook-only                                  | Tableau Parameter-driven `IF`/`ELSEIF` field switch (chooses among race/ethnicity, job group, location, etc. at view time); mechanism itself has no mart/Cube equivalent, though each underlying field it can switch to is covered individually above               | all     |
| Level of Detail / Level of Detail Parameter                                            | rows/cols breakdown switch                                | workbook-only                                  | Tableau Parameter (`% Attrition` vs. detailed Status view); pure display-mode toggle                                                                                                                                                                                | all     |
| Weird BOY Numbers Blocker / Remove future years                                        | filter (data-quality guard)                               | workbook-only                                  | Tableau calcs guarding against partial-year and future-year display artifacts; no warehouse equivalent needed                                                                                                                                                       | all     |
| Drilldown Permissions / Aggregate Permissions                                          | row-level filter                                          | workbook-only                                  | Tableau `ISMEMBEROF('KNJ-SG-Tableau ...')` AD-group check — Tableau-native RLS, structurally parallel to but entirely separate from Cube's `cube.js` group-based access model                                                                                       | all     |
| Hover - Help / Hover - Feedback / Hover - Calc (static help text)                      | text (Feedback, Help guide, attrition explanation sheets) | workbook-only                                  | Literal string constants for the dashboard's help/feedback/explanation tooltip panels                                                                                                                                                                               | n/a     |

### Notes

- **Two attrition pipelines coexist and disagree in grain and lineage.** This
  dashboard's `is_attrition` comes from `int_people__staff_attrition_details`
  (legacy, reads `int_people__staff_roster_history`, which itself unions
  pre-2021 Dayforce and ADP). The newer `fct_staff_attrition` mart (one row per
  employee x academic_year x attrition_type: foundation/nj_compliance/
  recruitment) is ADP-only and intentionally excludes pre-2021 NJ Dayforce-era
  staff (tracked at #3744). The task-prompt hint that "marts DO ship
  `fct_staff_attrition`" is correct, but it is **not** what feeds this dashboard
  today — porting to Cube/the new mart would need a decision on which attrition
  definition (and termination-reason taxonomy) is canonical.
- Cube's `staff` / `staff_work_history` cubes expose **no rate/ratio measure at
  all** — only `count_employees` (count_distinct). Every percentage shown on
  this dashboard (% Attrition, % Terminated, % Resigned, cumulative YoY curve)
  is computed client-side in Tableau (FIXED LOD divisions, `pcto` table calcs,
  cumulative table calcs), not in the warehouse or Cube.
- The "(group)" suffixed dimensions (`Legal Entity Name (display) (group)`,
  `Primary Job (group)`, `Primary Site (group)`, `Primary Ethnicity (group)`,
  `Status (group)`, `Status Reason (group)`) are Tableau-native Groups (created
  via the Desktop "Create Group" UI) — no `<calculation>` formula is stored for
  them in the `.twb`, so their bucketing rules are invisible outside Tableau.
  This is the single biggest hidden-logic risk for any migration.
- `int_people__staff_roster (kipptaf_people)` is attached to the workbook as a
  second datasource but no field from it appears on any in-scope worksheet —
  likely a leftover from an earlier iteration of the dashboard.
- Excluded `Attrition Protocol View` worksheets (Retention by Manager/PM
  Score/Race-Ethnicity/Year/Years-at-KIPP/role, Departure Reason) reference
  additional mart fields not covered above (`overall_tier`, `overall_score` from
  `int_performance_management__overall_scores`, manager-rollup `% attrition`
  FIXED-LOD calcs) — out of scope since that dashboard isn't published as a
  server View, but worth a follow-up pass if it turns out to still be in active
  use internally despite not being server-published.
- Asana: per task prompt, the Asana "Attrition Dashboard" task (Staff section)
  has empty notes — no `rpt_` list or LSID recorded there. Flagged as an Asana
  documentation gap; this inventory's `rpt_tableau__staff_attrition_details`
  LSID-equivalent is the workbook luid `5bf99669-00bb-4906-b2b4-79f2976ac3a4`.

### Verification

- cube-covered spot-check: `src/cube/model/views/staff/staff_directory.yml`,
  `join_path: staff_work_history` includes block — `status_name`,
  `status_reason`, `business_unit_name`, `department_name` are all listed there
  (lines ~23-33), confirmed against `staff_work_history.yml`'s dimension
  definitions (`status_name`/`status_reason` descriptions explicitly mention
  "termination reason — Resignation, Non-Renewal").
- mart-ready spot-check:
  `src/dbt/kipptaf/models/extracts/tableau/ rpt_tableau__staff_attrition_details.sql`
  line 4-5 selects `l.is_attrition` and `l.termination_date` straight from
  `int_people__staff_attrition_details` with no transformation — exactly the
  columns the workbook's `Total Attrition` / `Attrition Counter` /
  `Year Over Year` cumulative calcs aggregate.
- mart-missing spot-check: the Termination/Resignation/Non-Renew/Other breakdown
  used on `% Terminated Detailed` is driven by `[Status Reason (group)]`, which
  has no `<calculation>` element in the `.twb` (a true Tableau Group) and no
  corresponding categorized column anywhere under
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__staff_attrition_details.sql`
  or its parent `int_people__staff_attrition_details.sql` — only the raw
  `termination_reason` free-text column exists upstream.

## Staff Demographic Explorer (`staff_demographic_explorer`)

- workbook: Staff Demographic Explorer | contentUrl `StaffDemographicExplorer` |
  luid `fc15566f-0bcf-453c-aaed-04fbee94d7d7` | project The Brass
- upstream datasources: `rpt_tableau__staff_roster (kipptaf_tableau)` (embedded
  extract of the published BQ table
  `teamster-332318.kipptaf_tableau.rpt_tableau__staff_roster`, used by both
  in-scope dashboards), `yoy_race_ethnciity_salary-20221201` (embedded CSV,
  "State of People Data 2022" — only feeds out-of-scope sheets Donuts / Gender
  Changes over Time / Race-Ethnicity Changes over Time on the excluded "Manager
  Audit" dashboard; not used by the published views)
- rpt_/source models in use: `rpt_tableau__staff_roster` (reads
  `int_people__staff_roster`, `int_people__years_experience`,
  `int_people__leadership_crosswalk`)
- published dashboards inventoried: `Staff Demographics Explorer` (server view
  `StaffDemographicsExplorer`), `Staff Demographics Explorer v2` (server view
  `StaffDemographicsExplorerv2`)
- sheets excluded as hidden/scratch: 19 — these belong to 5 workbook dashboards
  (`Manager Audit`, `Staff Demographics`, `Staff Roster`,
  `Updated Preferred Race & Gender`, `Work Assignments`) that exist in the .twb
  but are NOT in the server's published views list for this contentUrl (only 2
  of 7 workbook dashboards are published views) — treated as hidden-on-server
  per the ground rules. Names: Department Counts, Donuts, Gender, Gender Changes
  over Time, Job Counts, Life Experience, Manager_Audit_Sheet, "Race, Ethnicity
  & Gender", Race/Ethnicity, Race/Ethnicity Changes over Time, Staff Job Roster,
  Staff Roster - Counts, Staff Roster - Table, Tracking List, Updated Gender,
  Updated Race/Ethnicity, Work Experience, Years Teaching, Years with KIPP NJ.
- regions served by this dashboard overall: all (network-wide).
  `legal_entity_name` (`business_unit_name`) is a selectable Cut-By and filter
  dimension, not a fixed scope — confirmed network-wide per `kipptaf/CLAUDE.md`:
  "`entity` (KTAF vs Region) derives from `business_unit_name`". No
  region/district filter restricts the data source itself; the only global
  filter is a `position_status` context filter excluding null and `"Terminated"`
  (active + on-leave staff only).

### Measures

| metric               | agg                        | source field / formula (trimmed)                                                                  | dashboards       | status        | where                                                                                                       | regions |
| -------------------- | -------------------------- | ------------------------------------------------------------------------------------------------- | ---------------- | ------------- | ----------------------------------------------------------------------------------------------------------- | ------- |
| Headcount            | Sum                        | `[Number of Records]` = literal `1` per staff row                                                 | both             | cube-covered  | `staff_directory.count_employees` / `staff_pii.count_employees` (count_distinct on `staff_key`)             | all     |
| % of Total Headcount | PCTO (table calc over Sum) | Tableau `PERCENT_OF_TOTAL` wrapping `SUM([Number of Records])`, scoped to the current Cut-By pane | both             | cube-covered  | same as above — ratio is a Tableau-side computation over `count_employees`, no separate Cube measure needed | all     |
| Jitter               | table calc                 | `Index()` — horizontal scatter offset for the Explorer V2 dot/beeswarm layout                     | Explorer V2 only | workbook-only | n/a (pure layout/placement helper, not a metric)                                                            | n/a     |

### Dimensions

| dimension                                                    | used as                                                                           | status        | where                                                                                                                                                                 | regions |
| ------------------------------------------------------------ | --------------------------------------------------------------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Legal Entity (`legal_entity_name` / `Business Unit (group)`) | Cut-By option (cols) + quick filter (Explorer V2)                                 | cube-covered  | `staff_directory.business_unit_name`                                                                                                                                  | all     |
| Job Group (`Job Title (group)` over `job_title_description`) | Cut-By option                                                                     | cube-covered* | `staff_directory.position_title` (*the Tableau "group" bucketing on top of the raw title is workbook-side only — Cube exposes the raw title, not the manual grouping) | all     |
| Location (`location_description`)                            | Cut-By option                                                                     | cube-covered  | `staff_directory.locations_location_name`                                                                                                                             | all     |
| Department (`home_department_description`)                   | Cut-By option                                                                     | cube-covered  | `staff_directory.department_name`                                                                                                                                     | all     |
| Gender (`gender_identity`)                                   | Cut-By option + Show-me option (incl. "Race/Ethnicity + Gender" concat)           | cube-covered  | `staff_pii.gender_identity` — PII-gated, remit-scoped view (not on open `staff_directory`)                                                                            | all     |
| Race/Ethnicity (`race_ethnicity_reporting`)                  | Cut-By option + Show-me option (incl. "Race/Ethnicity + Gender" concat)           | cube-covered  | `staff_pii.race` (`dim_staff.race = sh.race_ethnicity_reporting`) — PII-gated, remit-scoped                                                                           | all     |
| Year Hired (`original_hire_date`, year-extracted)            | Cut-By option                                                                     | cube-covered  | `staff_directory.original_hire_date` / `staff_pii.original_hire_date` — year split is a Tableau calc, not reproduced in Cube                                          | all     |
| Annual Salary (binned `base_salary`)                         | Cut-By option                                                                     | mart-ready    | `fct_work_assignment_compensation.annual_wage` (no Cube cube/view reads this mart; binning is Tableau-side)                                                           | all     |
| Is Manager (`is_management`)                                 | Cut-By option                                                                     | cube-covered  | `staff_directory.is_management_position`                                                                                                                              | all     |
| KIPP Alumni Status (`alumni_status`)                         | Cut-By option + Show-me option                                                    | mart-missing  | `rpt_tableau__staff_roster.sql` (`b.alumni_status`, sourced from `int_people__staff_roster`); no mart surfaces it                                                     | all     |
| Life Experience (`community_grew_up`)                        | Show-me option                                                                    | mart-missing  | `rpt_tableau__staff_roster.sql` (`b.community_grew_up`) / `int_people__staff_roster_history.sql`                                                                      | all     |
| Professional Experience (`community_professional_exp`)       | Show-me option                                                                    | mart-missing  | `rpt_tableau__staff_roster.sql` (`b.community_professional_exp`) / `int_people__staff_roster_history.sql`                                                             | all     |
| Education Level (`level_of_education`)                       | Show-me option                                                                    | mart-missing  | `rpt_tableau__staff_roster.sql` (`b.level_of_education`) / `int_people__staff_roster_history.sql`                                                                     | all     |
| Position Status (`position_status`)                          | global context filter (hidden quick-filter control), excludes null + "Terminated" | cube-covered  | `staff_work_history.status_name` (view description: filter `status_name = 'Active'` for current roster)                                                               | all     |

### Notes

- This is a single parameter-driven "explorer" dashboard duplicated as v1
  (`dev_demographics_bar`, a stacked/marimekko-style bar) and v2 (`Explorer V2`,
  a dot/beeswarm chart) — both read the same two parameters ("Cut By" and "Show
  me...") and the same underlying fields, so measures/dimensions are reported
  once and tagged "both" rather than duplicated per sheet.
- The `Cut By` and `Show me...` Tableau parameters are each backed by one big
  `IF/ELSEIF` calculated field (`Calculation_2819534906330173440` /
  `Calculation_884112934722793472`) that swaps in a different underlying column
  per parameter value. Each branch is reported as its own dimension row above
  rather than treating the calc field itself as one dimension, per the
  instruction to classify by meaning.
- A second-level "Cut By (2nd Level)" parameter exists in the .twb
  (`Cut By (copy)_...`) mirroring the same branch list, used only for a
  drill-down sub-axis — not listed separately since it reuses the identical
  underlying fields already in the table above.
- `gender_identity` and `race_ethnicity_reporting` are currently shown on this
  OPEN Tableau dashboard with no row-level remit scoping. A Cube migration would
  put them behind `staff_pii`'s remit-gated access policies
  (`staff-pii-all_in_scope` / `-teaching_staff` / `-reporting_chain` /
  `-reporting_chain_or_below_rank`) — current Tableau viewers of this workbook
  may be a broader audience than any one `staff_pii` scope covers. Flagging for
  product/access review, not resolving here.
- Per task hint, staff demographics (race, ethnicity, gender identity) do sit
  behind the `staff_pii` Cube view's remit, confirmed by reading
  `src/cube/model/views/staff/staff_pii.yml` / `staff_directory.yml` and
  `dim_staff.sql` (`sh.race_ethnicity_reporting as race`).
- `alumni_status`, `community_grew_up`, `community_professional_exp`, and
  `level_of_education` exist only in `int_people__staff_roster_history` /
  `int_people__staff_roster` (intermediate layer) and the
  `rpt_tableau__staff_roster` extract itself — no `dim_*`/`fct_*` mart currently
  carries them, so they are `mart-missing` rather than `mart-ready`.
- "Annual Salary" is `mart-ready`, not `cube-covered`:
  `fct_work_assignment_compensation` (mart) carries `annual_wage` from
  `base_remuneration__annual_rate_amount__amount_value`, but no Cube cube/view
  currently reads that mart (grepped `src/cube/model/` for the model name — no
  hits).
- Asana task "Staff Demographic Explorer" (Staff section) has empty notes, no
  `rpt_` list, and no LSID — confirmed documentation gap; this inventory's
  `rpt_tableau__staff_roster` / workbook luid above should backfill it.
- `yoy_race_ethnciity_salary-20221201` embedded CSV datasource is dead weight
  for the two published views — included in "upstream datasources" per the
  workbook metadata but excluded from measures/dimensions since no in-scope
  worksheet references it.

### Verification

- cube-covered spot-check: `src/cube/model/views/staff/staff_pii.yml` exposes
  `race` (view line ~42, sourced from `staff_work_history.staff` join) and
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff.sql` line 30
  (`sh.race_ethnicity_reporting as race`) confirms the dashboard's
  `race_ethnicity_reporting` field maps exactly to this Cube measure.
- mart-ready spot-check:
  `src/dbt/kipptaf/models/marts/facts/fct_work_assignment_compensation.sql` line
  44 (`annual_rate as annual_wage`) is the mart column that could serve the
  dashboard's "Annual Salary" cut-by with simple aggregation, but no Cube
  cube/view currently reads this mart.
- mart-missing spot-check:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__staff_roster.sql` line
  47 (`b.alumni_status`) is the `rpt_` model the "KIPP Alumni Status"
  cut-by/show-me field reads today; it has no mart equivalent.

## Finance & Accounting Tools (Finance Accounting Tools Resources) (`finance_and_accounting_tools`)

- workbook: Finance & Accounting Tools & Resources | contentUrl
  `FinanceAccountingToolsResources` | luid
  `c29963fb-8516-4148-b43f-cddc0f2b4093` | project `TEMP-KV`
- upstream datasources (all embedded, none published separately):
  `rpt_tableau__finance_accounting_people_model`,
  `rpt_tableau__staff_attrition_details`,
  `rpt_tableau__adp_pension_and_benefits_enrollments`
- rpt_/source models in use: `rpt_tableau__finance_accounting_people_model` (->
  `int_people__annual_historic_data`, `int_people__years_experience`,
  `stg_adp_workforce_now__additional_earnings_report`),
  `rpt_tableau__staff_attrition_details` (->
  `int_people__staff_attrition_details`, `int_students__teacher_grade_levels`,
  `int_performance_management__overall_scores`),
  `rpt_tableau__adp_pension_and_benefits_enrollments` (->
  `stg_adp_workforce_now__pension_and_benefits_enrollments`,
  `int_people__staff_roster`)
- published dashboards inventoried: `Attrition` (Attrition By Job, Attrition
  Overall), `Job View` (Aggregations by Job Title, Historic Records (Jobs)),
  `Staff Records` (Current Records, Historic Records (ind)),
  `Teacher Salaries by Year Dash` (Salaries by Year, Salaries by Year chart);
  plus 3 worksheets published standalone (no wrapping dashboard object):
  `View Roster By Year`, `Staff Counts by Year`, `Benefits Enrollments`
- sheets excluded as hidden/scratch: 0 — no `<window hidden='true'>` entries in
  the .twb; all 11 worksheets are referenced by a dashboard zone or published
  standalone
- regions served by this dashboard overall: all (network-wide) with a gap — see
  Notes

**BLOCKED/flag**: the `Attrition` dashboard exists in the downloaded .twb
(`<dashboard name='Attrition'>`, windows entry
`class='dashboard' name='Attrition'`, not hidden) but does **not** appear in
`mcp__tableau__get-workbook`'s `views` list (which returns only 6 views: Teacher
Salaries by Year Dash, View Roster By Year, Staff Counts by Year, Staff Records,
Job View, Benefits Enrollments). Per instructions, included and flagged rather
than dropped — treat the two Attrition worksheets below as unverified against
the live server until someone confirms the published state.

### Measures

| metric                                             | agg                                                    | source field / formula (trimmed)                                                                                      | dashboards                                                                                                                            | status        | where                                                                                                                                                                                                                                                                                  | regions                                                                                        |
| -------------------------------------------------- | ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| Employee count (headcount)                         | Count (row) / CountD(employee_number)                  | internal-object-id Count; `ctd:employee_number`                                                                       | Aggregations by Job Title, Staff Counts by Year, Salaries by Year (tooltip)                                                           | cube-covered  | `staff.staff_work_history.count_employees` (count_distinct staff_key) via `staff_directory` view — note: workbook's plain row-Count variant double-counts concurrent assignments unless filtered to primary position; Cube's measure already assumes `is_primary_position=true` filter | all (network-wide), minus Paterson-grouping gap (see Notes)                                    |
| Avg Annual Salary                                  | Avg                                                    | `annual_salary` (`avg:annual_salary:qk`)                                                                              | Aggregations by Job Title, Salaries by Year, Salaries by Year chart, Current/Historic Records, View Roster By Year (row-level)        | mart-ready    | `fct_work_assignment_compensation.annual_wage` (new comp mart; current rpt_ source is `rpt_tableau__finance_accounting_people_model.annual_salary`, sourced from `int_people__annual_historic_data.historic_salary`)                                                                   | all (network-wide); salary values themselves — field/model names only, no values reported here |
| Avg Additional Earnings Summed                     | Avg                                                    | `additional_earnings_summed` (`avg:additional_earnings_summed:qk`)                                                    | Aggregations by Job Title, Salaries by Year, Salaries by Year chart, Current Records, Historic Records (ind)                          | mart-ready    | `fct_work_assignment_additional_earnings.rate_amount` (new mart, not yet wired into the rpt_ source, which still sums `stg_adp_workforce_now__additional_earnings_report.gross_pay`)                                                                                                   | all (network-wide)                                                                             |
| Avg Is Manager (% managers)                        | Avg                                                    | `is_manager` (`avg:is_manager:qk`)                                                                                    | Aggregations by Job Title                                                                                                             | cube-covered  | `staff_work_history.is_management_position` on `staff_directory` (boolean, `avg()` gives % managers)                                                                                                                                                                                   | all (network-wide)                                                                             |
| Attrition rate                                     | Avg(is_attrition) / Sum(is_attrition)÷Sum(Denominator) | `is_attrition`; `Calculation_3239214095177486336` (`Denominator`=1) ÷ `SUM(IIF([Denominator]=0,NULL,[is_attrition]))` | Attrition By Job, Attrition Overall                                                                                                   | mart-ready    | `fct_staff_attrition.is_attrition` (boolean, one row per employee x academic_year x attrition methodology — foundation/nj_compliance/recruitment); no Cube measure exists on this mart                                                                                                 | all (network-wide; mart notes pre-2021 NJ Dayforce-era staff excluded)                         |
| Employee count (attrition population)              | Count (row)                                            | internal-object-id Count on `rpt_tableau__staff_attrition_details`                                                    | Attrition By Job, Attrition Overall                                                                                                   | mart-ready    | `fct_staff_attrition` row count by `academic_year` (denominator population), not the same headcount measure as `staff_directory.count_employees`                                                                                                                                       | all (network-wide)                                                                             |
| Total Years Teaching (raw)                         | None (feeds "Teaching Year" dimension)                 | `years_teaching_total`                                                                                                | Salaries by Year, Salaries by Year chart                                                                                              | mart-missing  | `rpt_tableau__finance_accounting_people_model.years_teaching_total` <- `int_people__years_experience`                                                                                                                                                                                  | all                                                                                            |
| Years at KIPP (current)                            | None (row-level)                                       | `years_at_kipp_total_current`                                                                                         | Current Records, Historic Records (ind), View Roster By Year                                                                          | mart-missing  | `rpt_tableau__finance_accounting_people_model.years_at_kipp_total_current` <- `int_people__years_experience`                                                                                                                                                                           | all                                                                                            |
| Most Recent PM Score / Tier                        | None (row-level)                                       | `most_recent_pm_score`, `overall_tier`                                                                                | Current Records, Historic Records (ind/Jobs), View Roster By Year, Attrition By Job/Overall (tooltip, `overall_score`/`overall_tier`) | mart-missing  | `rpt_tableau__finance_accounting_people_model` / `rpt_tableau__staff_attrition_details` <- `int_performance_management__overall_scores`; no performance-management mart or cube found in this repo                                                                                     | all                                                                                            |
| Last Year Business Unit / Job Title / Salary (YoY) | `LAG()` window, no aggregation                         | `last_year_business_unit`, `last_year_job_title`, `last_year_salary`                                                  | Current Records, Historic Records (ind)                                                                                               | mart-missing  | `rpt_tableau__finance_accounting_people_model` (`lag(...) over (partition by employee_number order by academic_year desc)`) — window-function logic, no mart or cube equivalent                                                                                                        | all                                                                                            |
| Original Salary Upon Hire                          | None                                                   | `original_salary_upon_hire`                                                                                           | Current Records, Historic Records (ind/Jobs), View Roster By Year                                                                     | workbook-only | field is hardcoded `null` in `rpt_tableau__finance_accounting_people_model.sql` (`null as original_salary_upon_hire`) — no live data; flagged, not a real metric today                                                                                                                 | n/a                                                                                            |
| Is Currently Certified NJ Only                     | None                                                   | `is_currently_certified_nj_only`                                                                                      | Current Records                                                                                                                       | workbook-only | field is hardcoded `null` in `rpt_tableau__finance_accounting_people_model.sql` — no live data                                                                                                                                                                                         | n/a                                                                                            |
| Rn Curr (row-pick helper)                          | None                                                   | `rn_curr` (row_number over employee_number/academic_year/status)                                                      | Salaries by Year, Salaries by Year chart                                                                                              | workbook-only | dedup/filter plumbing (picks current-year row per employee), not a displayed metric — excluded per instructions, listed for completeness                                                                                                                                               | n/a                                                                                            |

### Dimensions

| dimension                                                                                                             | used as                                            | status                       | where                                                                                                                                                                        | regions                                                                                             |
| --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Academic Year                                                                                                         | rows/cols, filter                                  | cube-covered                 | `staff_work_history.dates.academic_year` via `staff_directory` (`dates_academic_year`)                                                                                       | all                                                                                                 |
| Fiscal Year (`academic_year`+1)                                                                                       | cols (Staff Counts by Year)                        | workbook-only                | derived label (`Calculation_1188950350101082112`); underlying `academic_year` is cube-covered, the +1 shift is a display-only relabeling                                     | all                                                                                                 |
| Business Unit / Legal Entity                                                                                          | filter, rows, "Cut By" option                      | cube-covered                 | `staff_work_history.business_unit_name` via `staff_directory`                                                                                                                | all (network-wide), see Paterson-grouping gap in Notes                                              |
| Business Unit (group) — KCNA/KIPP Miami/KTAF/TEAM bins                                                                | cols (Staff Counts by Year)                        | mart-ready                   | binned in Tableau only (`categorical-bin` on `business_unit`); no equivalent grouped dimension in Cube or marts                                                              | KCNA=Camden, KIPP Miami=Miami, TEAM=Newark, KTAF=network office — **no Paterson bucket**, see Notes |
| Location / Home Work Location                                                                                         | filter, rows                                       | cube-covered                 | `locations.location_name` via `staff_directory` (`locations_location_name`)                                                                                                  | all                                                                                                 |
| Home Department / Department Home Name                                                                                | filter, rows, "Cut By" option                      | cube-covered                 | `staff_work_history.department_name` via `staff_directory`                                                                                                                   | all                                                                                                 |
| Job Title (+ "Job Title (teacher filter)" copy)                                                                       | rows, filter                                       | cube-covered (meaning match) | `staff_work_history.position_title` / `job_code` via `staff_directory` — workbook's ADP-sourced `job_title` is the same upstream concept                                     | all                                                                                                 |
| Position Status                                                                                                       | text/filter                                        | cube-covered                 | `staff_work_history.status_name` via `staff_directory`                                                                                                                       | all                                                                                                 |
| Current Status (group: Active-or-Inactive / Terminated)                                                               | filter, rows                                       | mart-ready                   | Tableau-side `categorical-bin` on `current_status`; `status_name`/`status_reason` exist on `staff_work_history` but this specific 2-bucket grouping isn't replicated in Cube | all                                                                                                 |
| Is Manager / Is Management Position                                                                                   | filter                                             | cube-covered                 | `staff_work_history.is_management_position` via `staff_directory`                                                                                                            | all                                                                                                 |
| Gender / Gender Identity                                                                                              | filter, "Cut By" option, tooltip                   | cube-covered (PII-gated)     | `staff.gender_identity` via `staff_pii` view (`staff-pii-*` access tiers) — not in the open `staff_directory` tier                                                           | all                                                                                                 |
| Race/Ethnicity Reporting                                                                                              | filter, "Cut By" option, tooltip                   | cube-covered (PII-gated)     | `staff.race` via `staff_pii` view                                                                                                                                            | all                                                                                                 |
| Original Hire Date / Rehire Date                                                                                      | rows (detail)                                      | cube-covered                 | `staff.original_hire_date`, `staff.rehire_date` via `staff_directory`                                                                                                        | all                                                                                                 |
| Termination Date                                                                                                      | rows (detail)                                      | mart-ready                   | `dim_staff_work_assignments.termination_date` (not exposed on any Cube view yet)                                                                                             | all                                                                                                 |
| Employee Number                                                                                                       | grain / identifier on every roster sheet           | mart-ready (hashed)          | not exposed raw in marts or Cube (R2 strips KIPP-specific ids); surfaces only as `staff.staff_key` (surrogate) / `staff_unique_id`                                           | all                                                                                                 |
| Legal/Preferred First & Last Name                                                                                     | rows (detail)                                      | cube-covered                 | `staff.full_name` / `first_name` / `last_name` via `staff_directory` (preferred-name grain; legal name is not separately exposed in Cube)                                    | all                                                                                                 |
| Name Search (concatenated search string)                                                                              | filter helper                                      | workbook-only                | Tableau calc concatenating preferred+legal names for a search box; display/filter mechanic only                                                                              | n/a                                                                                                 |
| Cut By (parameter-driven dimension swap: Business Unit / Location / Home Department / Race-Ethnicity / Gender / none) | rows (Aggregations by Job Title, Attrition By Job) | workbook-only                | Tableau parameter-driven `IF`/`ELSEIF` swap between already-covered dimensions above; not a distinct field                                                                   | n/a                                                                                                 |
| Plan Type / Plan Name / Coverage Level                                                                                | rows, text (Benefits Enrollments)                  | mart-ready                   | `fct_staff_benefits_enrollments.plan_type` / `plan_name` / `coverage_level` (new mart; no Cube view yet — Asana's `staff_benefits` cube task is open)                        | all (network-wide; no region filter observed on this sheet)                                         |
| Effective Date / Enrollment Start-End                                                                                 | rows (Benefits Enrollments)                        | mart-ready                   | `fct_staff_benefits_enrollments.start_date` / `end_date`                                                                                                                     | all                                                                                                 |
| Legal Entity Name (benefits sheet)                                                                                    | rows, filter                                       | cube-covered                 | same ADP legal-entity concept as Business Unit above, via `int_people__staff_roster` in the rpt_ source; `staff_work_history.business_unit_name` in Cube                     | all                                                                                                 |
| Primary Site / Primary On-site Department / Primary Job (benefits sheet)                                              | tooltip                                            | cube-covered                 | `staff_directory` locations/department/job_title equivalents                                                                                                                 | all                                                                                                 |
| Termination Reason                                                                                                    | tooltip (Attrition sheets)                         | mart-ready                   | `fct_staff_attrition.termination_reason`                                                                                                                                     | all                                                                                                 |

### Notes

- **Regional coverage gap**: the workbook's "Business Unit (group)" Tableau bin
  (used on Staff Counts by Year) maps raw `business_unit` values into exactly 4
  buckets — KCNA (Camden), KIPP Miami, KTAF (network office), TEAM (Newark) —
  with no bucket for Paterson. Cube's conformed `regions` cube carries all 5
  canonical region names (Camden, Miami, Newark, Paterson, TAF), so this is a
  workbook-side gap, not a data gap: Paterson rows likely still appear in the
  view (grouped under an unmatched/null bucket or passed through raw) but are
  invisible in this specific grouped breakdown. Flagged per task instructions
  rather than assumed network-wide without caveat.
- **Asana context**: the Asana "Finance Tools" task (Staff section) has empty
  notes — no `rpt_` list, no LSID — confirmed as a documentation gap; this
  inventory is the first lineage record for this workbook found during this
  pass.
- **No compensation/attrition/benefits Cube coverage**: grepped `src/cube/model`
  for "attrition", "compensation", "annual_wage", "benefits_enrollment",
  "additional_earnings" — zero matches. All three new marts
  (`fct_work_assignment_compensation`,
  `fct_work_assignment_additional_earnings`, `fct_staff_benefits_enrollments`)
  and the existing `fct_staff_attrition` mart are unexposed. This matches the
  task's Asana note that `staff_compensation` / `staff_additional_earnings` /
  `staff_benefits` Cube tasks are open/incomplete, and confirms via
  `.claude/rules/cube-authoring.md` that `staff-compensation`,
  `staff-observations`, `staff-benefits` are reserved group names in `access.js`
  with no view wired yet.
- **Salary/comp sensitivity**: per task instructions, no salary, additional-
  earnings, or compensation **values** were queried or recorded anywhere in this
  file — field and model names only.
- **Attrition dashboard discrepancy**: see BLOCKED/flag above — the `Attrition`
  dashboard is in the downloaded .twb but absent from the live `get-workbook`
  views list. Included and flagged rather than silently dropped.
- **Dead/placeholder fields**: `original_salary_upon_hire` and
  `is_currently_certified_nj_only` are both hardcoded `null` in
  `rpt_tableau__finance_accounting_people_model.sql` — they exist as columns the
  dashboard could display but currently carry no data.
- **Excluded as pure plumbing**: `rn_curr` (row-number dedup helper), "Name
  Search" (concatenated search-box string), and the "Cut By" parameter swap are
  workbook-side display/filter mechanics, not distinct metrics — listed once
  each for completeness per instructions, not duplicated across every sheet that
  uses them.
- **Grain variants collapsed**: `annual_salary` and `additional_earnings_summed`
  appear both as aggregated (Avg) measures on the chart/summary sheets and as
  plain per-row values on the four detail-roster sheets (Current Records,
  Historic Records (ind/Jobs), View Roster By Year) — collapsed into one row
  each per instructions rather than repeated per sheet.

### Verification

- cube-covered spot-check: `src/cube/model/views/staff/staff_directory.yml`
  (lines 20-33) exposes `count_employees` from
  `src/cube/model/cubes/staff/staff_work_history.yml` (lines 168-176,
  `count_employees`, `type: count_distinct`, `sql: staff_key`) — matches the
  workbook's headcount-by-job-title/business-unit measure in meaning (distinct
  employee count), even though the workbook's raw `Count` derivation on
  Aggregations by Job Title counts rows rather than distinct employees.
- mart-ready spot-check: `fct_staff_attrition.is_attrition` — column declared in
  `src/dbt/kipptaf/models/marts/facts/properties/fct_staff_attrition.yml` (lines
  70-74), boolean, one row per `employee_number` x `academic_year` x `type`
  (attrition methodology) — a simple `avg()`/`sum()` over this column reproduces
  the Attrition By Job / Attrition Overall rate measures; no Cube measure reads
  this mart today.
- mart-missing spot-check: `years_at_kipp_total_current` and
  `years_teaching_total` are produced in
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__finance_accounting_people_model.sql`
  (lines 48, 55) by joining `int_people__years_experience` — no mart exposes
  tenure/years-teaching today, so this logic lives only in the `rpt_` extract.
