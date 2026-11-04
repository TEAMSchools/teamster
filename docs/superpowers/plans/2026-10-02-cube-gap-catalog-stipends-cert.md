# Cube Gap Catalog — Stipends and Certification

Part of the [Cube Connector Gap Catalog](2026-10-02-cube-gap-catalog.md). Refs
#5673. One section per core-set dashboard; tables and notes are the per-workbook
inventory extracted from the production .twb and classified against the dbt
marts and Cube model YAML as of 2026-10-02.

## Certification Dashboard (`certification_dashboard`)

- workbook: NJ Certification Dashboard (Schools View) | contentUrl
  `NJCertificationDashboardSchoolsView` | luid
  `ed2976ea-0b3c-4afb-a5d9-7e7e83227e3b` (confirmed, matches task hint) |
  project Production
- upstream datasources (both embedded, not published datasources):
  `federated.0iqopey0sa8he01bxr9jd0g37st6` caption "rpt_tableau__staff_roster+
  (Multiple Connections)" — BigQuery `rpt_tableau__staff_roster` LEFT JOIN two
  tabs of a Google-Drive Excel file "Cert_export_to_tableau.xlsx" (`action_log`,
  `nj_cert_export`); and `federated.1hfgb240n80rhm137iro013yguag (copy)` caption
  "rpt_tableau__staff_roster+sheets_cert_export" — same BigQuery table LEFT JOIN
  a second copy of the same spreadsheet's `Sheet11` tab (same `cloudFileId`,
  i.e. the same underlying Google Sheet re-opened under a different connection
  name). Join key both sides: `rpt_tableau__staff_roster.df_employee_number` =
  sheet `Employee ID`.
- rpt_/source models in use: `rpt_tableau__staff_roster` (BigQuery,
  `teamster-332318.kipptaf_tableau.rpt_tableau__staff_roster`) for every staff
  roster/HR field; **no dbt model or Dagster-ingested source backs the
  cert-specific tabs** (`action_log`, `nj_cert_export`, `Sheet11`) — they are a
  hand-maintained Google Sheet pulled into Tableau directly via its own
  Drive-file connector, outside dbt/Dagster entirely.
- published dashboards inventoried (5) + standalone worksheet-views (2):
  Certification Dashboard, Steps for Certification, Effort Log, PRAXIS
  Intensives, Teacher Cert Roster, Info & Cert Tracking, Pension Checker
- sheets excluded as hidden/scratch: 7 — 3 whole dashboards present in the
  `.twb` but **absent from the server's published views list** (so excluded from
  scope per the ground rules): `Cert Roster`, `Roll`, `Update Links + Tracking`
  (note: `Update Links + Tracking`'s one zone, worksheet `Info & Cert Tracking`,
  IS separately published as its own standalone view, so that worksheet stays in
  scope via that route); plus 4 orphan worksheets wired into no dashboard and
  not published standalone: `Action Details`, `BAN 3.1 - Retention`,
  `Certification by Race/Ethnicity`, `Showing data as of`.
- regions served by this dashboard overall: **all 4 (not NJ-only — hint is
  wrong)**. The embedded row-level-security calc (`Permissions Group Filter`)
  branches on `legal_entity_name` for `TEAM Academy Charter School` (Newark +
  Paterson share this one legal entity), `KIPP Cooper Norcross Academy`
  (Camden), and `KIPP Miami` explicitly, with Tableau group membership checks
  for `KNJ-SG-Tableau All Staff MIA` / `All Staff KCNA` / `All Staff TEAM` /
  `All Staff KTAF`. "KIPP Miami" appears 144 times in the workbook XML (far more
  than cosmetic). The dashboard's name ("NJ Certification Dashboard") predates
  what the data now covers; it is row-level-security-gated per legal entity, not
  filtered out of scope.

### Measures

| metric                                                                                                   | agg                                                      | source field / formula (trimmed)                                                                                                                                                                                              | dashboards                                              | status                                                                                   | where                                                                                                          | regions                                                                                                                                                                      |
| -------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| # Teachers / Teacher Counter                                                                             | Sum                                                      | `[Calculation_332984960789143554]` "# Teachers", `[Calculation_797418616138440710]` "Teacher Counter" — row-count helpers (`1` constant summed, scoped by dashboard filters)                                                  | By School, Names Drill, BAN 3 - Retention               | mart-missing                                                                             | `nj_cert_export`/`Sheet11` tab joined to `rpt_tableau__staff_roster` (no dbt model)                            | all                                                                                                                                                                          |
| 2027 Cohort counter / 2027 Cohort Certified Counter / % 2027 certified                                   | Sum, User (ratio)                                        | `[year 2 counter (copy)_...]`, `[2026 Cohort Certified Counter (copy)_327073968188936195]`, `[Calculation_327073968189100036]` = `SUM([2027 Cohort Certified Counter])/(SUM([2027 Cohort counter])...`                        | BAN 1 - Y1 Teachers, BAN 1.2 - 2027 Teachers, By School | mart-missing                                                                             | same cert sheet                                                                                                | all                                                                                                                                                                          |
| 2028 Cohort counter / 2028 Cohort Certified Counter / not-certified-eligible-override / % 2028 certified | Sum, User                                                | `[Calculation_797418616138207237]`, `[Calculation_797418616134565891]`, `[2026 Cohort Certified Counter (copy)_2959709438388383745]`, `[Calculation_2959709438389510149]`/`[Calculation_934496981001703429]` (ratio variants) | BAN 2 - Y2 Teachers, BAN 2.2 - Y2 Teachers, By School   | mart-missing                                                                             | same cert sheet                                                                                                | all                                                                                                                                                                          |
| Not Eligible Counter / retention rate                                                                    | Sum, User                                                | `[Calculation_1566126820284817409]` "Not Eligible Counter", `[Calculation_1566126820285157378]` = `SUM([Not Eligible Counter])/SUM([Teacher Counter])`                                                                        | BAN 3 - Retention                                       | mart-missing                                                                             | same cert sheet                                                                                                | all                                                                                                                                                                          |
| Certified? donut split (Blue or Green Count)                                                             | Avg/Count                                                | `[Calculation_797418616125296641]` "Blue or Green Count" vs row count on `rpt_tableau__staff_roster` grain                                                                                                                    | Donut                                                   | mart-missing                                                                             | same cert sheet (`Certified?`/`Certified? (group)` dimension drives the split)                                 | all                                                                                                                                                                          |
| # Of Outstanding Praxis Exams                                                                            | measure (int)                                            | `[# Of Outstanding Praxis Exams]`, `[Calculation_789255886002147328]` "# Outstanding Praxis"                                                                                                                                  | Info & Cert Tracking                                    | mart-missing                                                                             | same cert sheet                                                                                                | all                                                                                                                                                                          |
| Primary Grade Level Taught                                                                               | None/ordinal (used as a drill attribute, not aggregated) | `rpt_tableau__staff_roster.primary_grade_level_taught`                                                                                                                                                                        | Roster Drill Down, Full Teacher Cert Roster             | mart-ready                                                                               | `rpt_tableau__staff_roster.sql` line 55 (`b.primary_grade_level_taught`); no Cube measure/dimension exposes it | all                                                                                                                                                                          |
| Effort Log entry count                                                                                   | Count                                                    | `[cnt:Timestamp:qk]` — `COUNT([Timestamp])` by `What are you logging? (group)` (Event)                                                                                                                                        | Action Count (Effort Log dashboard)                     | mart-missing                                                                             | `action_log` tab, no dbt model                                                                                 | all                                                                                                                                                                          |
| PRAXIS Intensive # Attendees                                                                             | Sum (shape-encoded)                                      | `[Calculation_1427359643048415233]` "# Attendees", `[Calculation_392376152287899654]` constant-1 helper                                                                                                                       | Intensive Attendance (PRAXIS Intensives dashboard)      | mart-missing                                                                             | cert sheet, Intensive-session fields, no dbt model                                                             | all                                                                                                                                                                          |
| TPAF/PERS pension flag                                                                                   | categorical derived measure (color/shape, not summed)    | `[Calculation_2692589673554894848]` "TPAF/PERS Flag" over `nj_cert_export.Cert Type` + `rpt_tableau__staff_roster.nj_pension_plan_name`                                                                                       | Pension Checker                                         | mart-missing (derivation) / `nj_pension_plan_name` itself is mart-ready (see Dimensions) | cert sheet calc; base column `rpt_tableau__staff_roster.nj_pension_plan_name`                                  | all — but the concept (NJ pension enrollment) is itself an NJ-specific program, so only meaningful for Newark/Camden/Paterson rows even though the field exists network-wide |

Variants collapsed: the 2027/2028 "BAN" tiles (`BAN 1`, `BAN 1.2`, `BAN 2`,
`BAN 2.2`, `BAN 3`, `BAN 3.1`) are the same handful of cohort-counter /
percent-certified calculations re-encoded as text tiles per cohort year and per
metric (count vs. rate); grouped above by cohort rather than listed as 6+
separate rows.

### Dimensions

| dimension                                                                                             | used as                              | status                   | where                                                                                                                                                                                                        | regions                                                                           |
| ----------------------------------------------------------------------------------------------------- | ------------------------------------ | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| location_description / Location Description (group)                                                   | rows, filter, color                  | cube-covered             | `staff_directory.locations_location_name` (`src/cube/model/views/staff/staff_directory.yml`, `join_path: staff_work_history.locations`)                                                                      | all                                                                               |
| job_title_description / Job Title (group)                                                             | rows, filter                         | cube-covered             | `staff_directory.position_title` / `job_code`                                                                                                                                                                | all                                                                               |
| legal_entity_name / Legal Entity                                                                      | filter, RLS                          | cube-covered             | `staff_directory.business_unit_name`                                                                                                                                                                         | all                                                                               |
| position_status                                                                                       | filter                               | cube-covered             | `staff_directory.status_name`                                                                                                                                                                                | all                                                                               |
| manager_name / manager_mail                                                                           | drill attribute                      | cube-covered             | `staff_directory.staff_manager_full_name` / `staff_manager_work_email` (join_path `staff_work_history.staff_manager`)                                                                                        | all                                                                               |
| userprincipalname                                                                                     | drill attribute, RLS match           | cube-covered             | `staff_directory.active_directory_username`                                                                                                                                                                  | all                                                                               |
| preferred_name / first_name / last_name / df_employee_number                                          | drill attribute                      | cube-covered             | `staff_directory.full_name`/`first_name`/`last_name`/`staff_key` or `staff_unique_id`                                                                                                                        | all                                                                               |
| personal_contact_personal_mobile                                                                      | tooltip/drill                        | cube-covered (PII-gated) | `staff_pii.personal_cell_phone` (`src/cube/model/views/staff/staff_pii.yml`)                                                                                                                                 | all                                                                               |
| home_department_description                                                                           | drill attribute                      | cube-covered             | `staff_directory.department_name`                                                                                                                                                                            | all                                                                               |
| nj_pension_plan_name                                                                                  | filter, color/shape                  | mart-ready               | `rpt_tableau__staff_roster.sql` line 51 (`b.nj_pension_plan_name`); not in `staff_directory` or `staff_pii`                                                                                                  | NJ only (program is NJ-specific; column is network-wide but non-NJ rows are null) |
| dso_mail / dso_preferred_name_lastfirst / school_leader_mail / school_leader_preferred_name_lastfirst | drill attribute                      | mart-ready               | `rpt_tableau__staff_roster.sql` lines 61-64, sourced from `int_people__leadership_crosswalk` (`src/dbt/kipptaf/models/people/intermediate/int_people__leadership_crosswalk.sql`); not on any Cube staff view | all                                                                               |
| Cert Tier / Cert Type / Certification Cohort / Certified? / Renewal Status (+ `(group)` variants)     | rows, filter, color, shape           | mart-missing             | `nj_cert_export`/`Sheet11` tab (Google Sheet), no dbt model                                                                                                                                                  | all                                                                               |
| Certification Manager / Certification Manager Email                                                   | rows, drill                          | mart-missing             | same cert sheet                                                                                                                                                                                              | all                                                                               |
| Certification Deadline / Issue Date / Provisional Enrollment Date Issued                              | drill attribute                      | mart-missing             | same cert sheet                                                                                                                                                                                              | all                                                                               |
| Endorsement / Co-Endorsment                                                                           | drill, filter                        | mart-missing             | same cert sheet                                                                                                                                                                                              | all                                                                               |
| Praxis Exams Req'd                                                                                    | tooltip                              | mart-missing             | same cert sheet                                                                                                                                                                                              | all                                                                               |
| Action Steps / Compliance Notes                                                                       | tooltip                              | mart-missing             | same cert sheet                                                                                                                                                                                              | all                                                                               |
| SPED Certified? / "ESL Certified?" (caption on `SPED Certified? (copy)_...`)                          | filter                               | mart-missing             | same cert sheet — note the caption/field-name mismatch (field literally named SPED, labeled ESL in one filter) is a workbook authoring inconsistency, not a data issue                                       | all                                                                               |
| Feed from New Cert Tracker / Cert Link / Links_Clean / Last Submitted Date                            | drill, lod                           | mart-missing             | same cert sheet                                                                                                                                                                                              | all                                                                               |
| What are you logging? / Event (group)                                                                 | cols, filter                         | mart-missing             | `action_log` tab                                                                                                                                                                                             | all                                                                               |
| Which intensive session did they attend? / Session                                                    | rows, filter                         | mart-missing             | cert sheet (PRAXIS Intensives data)                                                                                                                                                                          | all                                                                               |
| Date of Session                                                                                       | filter                               | mart-missing             | cert sheet                                                                                                                                                                                                   | all                                                                               |
| Programs (Parameter 1)                                                                                | filter (parameter, not a data field) | workbook-only            | Tableau parameter, no warehouse source                                                                                                                                                                       | n/a                                                                               |

### Notes

- **Asana claim re-checked and found wrong, as flagged**: the sibling agent's
  read is correct. `rpt_tableau__staff_roster.sql`
  (`src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__staff_roster.sql`) is a
  general HR/staff extract (name, position, salary, demographics) built from
  `int_people__staff_roster` + `int_people__years_experience` +
  `int_people__leadership_crosswalk` — it is **not** cert-specific and is not
  solely the Staff Roster workbook's datasource: this Certification Dashboard
  workbook also reads it directly from BigQuery (`get-workbook`'s
  `upstreamDatasources` lists it by name, and the `.twb` relations confirm a
  literal `teamster-332318.kipptaf_tableau.rpt_tableau__staff_roster` table
  read). It supplies every roster/HR dimension on this dashboard but **zero** of
  the certification-specific content.
- **No cert mart exists today**, confirming the task hint. All certification
  logic (tiers, cohorts, Praxis, deadlines, action steps, compliance notes,
  effort log, intensive-session attendance) lives entirely in a hand-maintained
  Google Sheet (`Cert_export_to_tableau.xlsx`, tabs
  `nj_cert_export`/`Sheet11`/`action_log`) pulled straight into Tableau via its
  own Google-Drive file connector — bypassing Dagster/dbt ingestion entirely.
  There is a **separate, unrelated** intermediate model,
  `int_people__certification`
  (`src/dbt/kipptaf/models/people/intermediate/int_people__certification.sql`),
  that unpivots NJ + FL certification fields from
  `int_surveys__staff_information_survey_pivot` (a staff self-report survey). It
  has **zero downstream consumers** (`grep` of `models/` for its name turns up
  only its own properties YAML) and is not wired to this dashboard or to any
  `rpt_` extract — it reads as an abandoned or not-yet-finished start at the
  "cert mart," consistent with the Asana task being open/incomplete.
- Blockers named in Asana (`fct_staff_roster`, `dim_staff`, `dim_locations`,
  `dim_adp_positions`) — confirms: `fct_staff_roster` and `dim_adp_positions` do
  not exist anywhere in `src/dbt`. `dim_staff` and `dim_locations` exist as
  marts but this workbook does not read either directly — it reads the
  `rpt_tableau__staff_roster` extract, which itself is built from
  `int_people__staff_roster` (not `dim_staff`). A future cert mart would most
  naturally join cert data to `dim_staff`/`dim_locations`, which is presumably
  the blocker's intent, but today's workbook has no such dependency.
- Regions: corrected from the "NJ only" hint to **all four regions**, gated
  per-legal-entity by the embedded row-level-security calculation (see header
  section). Miami-specific program nuance (Florida vs NJ certification rules) is
  folded into the same `Cert Type`/`Cert Tier` free-text fields rather than
  modeled as a separate dimension — worth flagging if a cert mart is ever built,
  since NJ and FL certification regimes are not equivalent.
- `Pension Checker` and `Info & Cert Tracking` are published as **standalone
  worksheet views** (no dashboard wrapper), consistent with Tableau publishing a
  subset of a workbook's sheets directly.
- Excluded-as-not-published dashboards (`Cert Roster`, `Roll`,
  `Update Links + Tracking`) appear to be working/admin views (a raw-counts
  roster, an "as of" roll-forward sheet, and an update-tracking sheet) kept in
  the source `.twb` for the dashboard author but not exposed to end users.
- No PII values were queried or included anywhere in this file — field names,
  model names, and counts only.

### Verification

- cube-covered spot-check: `location_description` → `staff_directory` view,
  `locations_location_name` member, file
  `src/cube/model/views/staff/staff_directory.yml` (join_path
  `staff_work_history.locations`, `includes: location_name`).
- mart-ready spot-check: `primary_grade_level_taught` → column defined at
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__staff_roster.sql` line
  55 (`b.primary_grade_level_taught as primary_grade_level_taught`), confirmed
  present in its contract at
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__staff_roster.yml`
  (column `primary_grade_level_taught`, `data_type: int64`); absent from every
  Cube staff cube/view.
- mart-missing spot-check: `Cert Tier` (and the whole certification-content
  column family: `Certified?`, `Renewal Status`, `Praxis Exams Req'd`,
  `Action Steps`, `Compliance Notes`, cohort counters) — no `rpt_` or `int_`
  model in `src/dbt/kipptaf/models` defines any of these; `rg -l` for each
  across `src/dbt/kipptaf/models` returns nothing. Source is the external Google
  Sheet `Cert_export_to_tableau.xlsx`, read by Tableau's own
  `cloudfile:googledrive-excel-direct` connector (`.twb` connection block,
  `cloudFileId='1KPtoqSkjxjWZX2uwpGCP3RBTb206g0Ow3ild00BdnG0'`), never ingested
  through Dagster/dbt.

## Stipend and Bonus Dashboard (`stipend_and_bonus_dashboard`)

- workbook: Stipend and Bonus Dashboard | contentUrl
  `StipendandBonusDashboard_17278875605220` | luid
  `35484db7-cd5b-4834-828a-5bfc645a09c6` (confirmed, matches expected) | project
  Production
- upstream datasources: `rpt_tableau__stipend_and_bonus_app` (embedded, single
  federated datasource backing all sheets)
- rpt_/source models in use: `rpt_tableau__stipend_and_bonus_app` (live/current
  workflow state — the dashboard's only live source), feeding from
  `stg_google_appsheet__stipend_and_bonus__output` (AppSheet staging),
  `rpt_appsheet__stipend_app_roster`, and `int_people__staff_roster` /
  `int_people__location_crosswalk`. A separate dbt snapshot,
  `snapshot_stipend_and_bonus__output`
  (`src/dbt/kipptaf/snapshots/google_appsheet.yml`), feeds the workbook's
  History dashboard but is **`config.enabled: false`** — disabled, so History's
  data (if ever surfaced) is frozen/stale.
- published dashboards inventoried: **Home**, **Approval Status** (confirmed
  live Tableau Server views via `list-views`, 2 of 2)
- sheets excluded as hidden/scratch: 5, across 2 dashboards that exist in the
  .twb but are **not published server-side views** (confirmed absent from
  `list-views` filtered to this workbook — not merely tab-hidden) and 1 orphan
  sheet:
  - Dashboard **History** (sheets `history`, `history_title`) — reads the
    disabled snapshot above.
  - Dashboard **HR Download** (sheets `hr_download`, `download_title`).
  - Sheet **`pay code audit`** — standalone, not placed on any dashboard's
    `<zones>`.
  - No in-scope dashboard (Home, Approval Status) has a hidden-dashboard flag; 3
    worksheets (`download_title`, `location_status`, `status_title`) carry
    `hidden='true'` on their `<window>` element, but that is a Tableau-Desktop
    authoring-tab toggle (hide this sheet's own tab since it's only used
    embedded in a dashboard), not an end-user visibility flag —
    `location_status` is a fully in-scope, visible Approval Status zone.
- regions served by this dashboard overall: **all**
  (newark/camden/miami/paterson
  - KTAF network office) — confirmed via the workbook's own RLS formulas:
    `home_business_unit_name` covers `TEAM Academy Charter School` (Newark),
    `KIPP Cooper Norcross Academy` (Camden), `KIPP Miami`, `KIPP Paterson`, and
    `KIPP TEAM and Family Schools Inc.` (KTAF); the RLS Location Gate enumerates
    schools across all four regions. Matches the "network-wide ops" hint.

### Measures

| metric                                   | agg                                                                           | source field / formula (trimmed)           | dashboards                                                     | status       | where                                                                                                                                                                                                                                                                   | regions |
| ---------------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------ | -------------------------------------------------------------- | ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Amount                                   | Sum                                                                           | `[amount]` (raw dollar amount, no formula) | Approval Status (stipend_BAN big-number, stipend_detail table) | mart-ready   | `fct_work_assignment_additional_earnings.rate_amount` could compute a $ total, but that fact is ADP's post-payroll additionalRemunerations feed, not the AppSheet approval-workflow amount — semantics are adjacent, not identical; porting needs a grain/meaning check | all     |
| Approved (count)                         | Sum of `IIF([first_approval]='Approved',1,0)`                                 | caption "Approved"                         | Approval Status (stipend_BAN KPI tile)                         | mart-missing | `rpt_tableau__stipend_and_bonus_app.first_approval` (no mart carries approval-workflow status)                                                                                                                                                                          | all     |
| Pending (count)                          | Sum of `IIF([first_approval]='Pending',1,0)`                                  | caption "Pending"                          | Approval Status (stipend_BAN)                                  | mart-missing | same as above                                                                                                                                                                                                                                                           | all     |
| Not Approved (count)                     | Sum of `IIF([first_approval]='Not Approved',1,0)`                             | caption "Not Approved"                     | Approval Status (stipend_BAN)                                  | mart-missing | same as above                                                                                                                                                                                                                                                           | all     |
| % Approved                               | derived ratio: `SUM(Approved)/(SUM(Approved)+SUM(Pending)+SUM(Not Approved))` | caption "% Approved"                       | Approval Status (stipend_BAN)                                  | mart-missing | depends entirely on the 3 workflow-status measures above                                                                                                                                                                                                                | all     |
| Employee Number (distinct staff)         | CountD                                                                        | `[employee_number]`                        | Approval Status (stipend_BAN)                                  | mart-missing | Cube's `staff_directory.count_employees` is the matching distinct-staff pattern, but no cube/mart joins staff to stipend events, so "distinct staff with a stipend" can't be computed outside the rpt_ model today                                                      | all     |
| Event Id (distinct stipend/bonus events) | CountD                                                                        | `[event_id]`                               | Approval Status (stipend_BAN, location_status heatmap)         | mart-missing | `rpt_tableau__stipend_and_bonus_app.event_id` / `stg_google_appsheet__stipend_and_bonus__output.event_id` — no mart at this grain                                                                                                                                       | all     |

Variants collapsed: the 3 approval-state counts and the % Approved ratio are
grouped as one family (all built on `first_approval`); Amount appears
identically on both stipend_BAN and stipend_detail (same field, same status).

### Dimensions

| dimension                                                                  | used as                                                               | status       | where                                                                                                                                                                           | regions |
| -------------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Location (`location_clean_name`)                                           | rows (location_status), filter                                        | cube-covered | `staff_directory` view, `locations_location_name` (join `staff_work_history.locations`) — name differs but meaning matches                                                      | all     |
| Business Unit (`home_business_unit_name`)                                  | filter (quick-filter instance)                                        | cube-covered | `staff_directory.business_unit_name`                                                                                                                                            | all     |
| Department (`home_department_name`)                                        | filter (quick-filter instance)                                        | cube-covered | `staff_directory.department_name`                                                                                                                                               | all     |
| Teammate (`teammate`, staff full name)                                     | rows (stipend_detail)                                                 | cube-covered | `staff_directory.full_name`                                                                                                                                                     | all     |
| Approval (`first_approval`)                                                | rows/cols, filter                                                     | mart-missing | `rpt_tableau__stipend_and_bonus_app.first_approval` — workflow state, no mart                                                                                                   | all     |
| Stipend (Display) (calc mapping `pay_code` → friendly label, 22-way `IIF`) | rows (stipend_detail), text                                           | mart-missing | calc lives only in the Tableau workbook; backing `pay_code` is in `stg_google_appsheet__stipend_and_bonus__output` / `rpt_tableau__stipend_and_bonus_app`, no mart decode table | all     |
| Pay Code (`pay_code`)                                                      | input to Stipend (Display) calc; not separately shelved in-scope      | mart-missing | same model as above                                                                                                                                                             | all     |
| Payment Date (`payment_date`, stored as string)                            | filter, rows                                                          | mart-missing | `rpt_tableau__stipend_and_bonus_app.payment_date`                                                                                                                               | all     |
| Company Code (`company_code`)                                              | rows (stipend_detail)                                                 | mart-ready   | `dim_staff_work_assignments.payroll_group_code` (not currently exposed on any cube view)                                                                                        | all     |
| Description (`description`, free-text reason for stipend/bonus)            | rows (stipend_detail)                                                 | mart-missing | `rpt_tableau__stipend_and_bonus_app.description`; sensitive free text — field name only                                                                                         | all     |
| Submitter (`submitter`)                                                    | rows (stipend_detail)                                                 | mart-missing | `rpt_tableau__stipend_and_bonus_app.submitter`                                                                                                                                  | all     |
| Stipend Type (`stipend_type`)                                              | input to Stipend (Display) calc only; not separately shelved in-scope | mart-missing | same model                                                                                                                                                                      | all     |

Excluded from this table (RLS/security dependency columns only, never shelved on
an in-scope sheet — no `<column-instance>` in stipend_BAN, stipend_detail, or
location_status): `job_function`, `job_title`, `mail`, `sam_account_name`,
`user_principal_name`, `reports_to_mail`, `reports_to_sam_account_name`, and the
five `Calculation_*` RLS/Permissions fields (`Permissions`, `RLS - Entity Gate`,
`RLS - Location Gate`, `RLS - Role Gate`, `RLS - Comp Peer Row`) — these
implement the row-level-security formula, not a displayed metric.

### Notes

- **Two of the workbook's four dashboards are not published.** `get-workbook`
  and `list-views` both return only Home and Approval Status; History and HR
  Download exist in the downloaded `.twb` (with real data fields — payment
  history, position IDs, snapshot audit columns) but are absent from the
  server's view list entirely, and no dashboard action/navigate button in the
  workbook reaches them from a published view. Treated as out of scope per the
  task's hidden-dashboard rule, but flagged since they are not dead weight —
  they contain real sensitive fields (position_id, teammate, edited_by/
  edited_at audit trail) that would need classification if ever republished.
  History's underlying snapshot is additionally disabled in dbt, so even if
  republished it would show frozen data.
- **Home dashboard carries no metrics.** Its two zones (`app_link`, `help_link`)
  are static text/navigate-action tiles ("Stipend and Bonus App", "Help Guide")
  with no measures and only incidental dimension dependencies (the same
  RLS-required identity columns as every sheet).
- **No compensation/stipend Cube exists** (confirmed: no cube or view file under
  `src/cube/model/` matches "stipend", "bonus", "compensation", or
  "additional_earning"). Every workflow-specific measure (approval counts,
  event/stipend grain) is therefore `mart-missing`, not merely `cube-missing` —
  there is no mart at the right grain either, only the `rpt_` extract itself.
  This matches the Asana task's note that `fct_stipends` doesn't exist.
- **Asana-named blockers reconciled**: `fct_stipends` does not exist (confirmed
  — the live app model reads `stg_google_appsheet__stipend_and_bonus__output`
  directly, not any `fct_` table). `dim_staff` is not actually the join target
  in `rpt_tableau__stipend_and_bonus_app.sql` — it joins
  `int_people__staff_roster` (an intermediate, pre-dim_staff identity roster)
  and `rpt_appsheet__stipend_app_roster`. `fct_additional_earnings` appears to
  mean `fct_work_assignment_additional_earnings`, which is a different source
  (ADP payroll earnings, SCD2) covering only the `Amount` measure, not the
  approval-workflow fields.
- **Salary/stipend sensitivity**: `amount`, `description`, `submitter`, and
  `teammate`/staff identity columns are compensation-adjacent; per task
  instructions only field/model names are recorded here, no values were queried.
- Judgment call: `% Approved`'s Tableau `aggregation='User'` derivation was
  treated as a measure (wraps three real sub-metrics), not excluded as a display
  calc, per Step 2 guidance on ratio/windowed calcs.

### Verification

- cube-covered spot-check: `src/cube/model/views/staff/staff_directory.yml`,
  `cubes.staff_work_history` join block, member `business_unit_name` (line 29) —
  matches the workbook's `home_business_unit_name` filter dimension by meaning
  (legal entity / business unit), confirmed via
  `fct_work_assignment_additional_earnings` lineage back to ADP HR data.
- mart-ready spot-check:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_work_assignments.yml`,
  column `payroll_group_code` (line 94) — matches the workbook's `Company Code`
  dimension (`[company_code]`, sourced in
  `rpt_tableau__stipend_and_bonus_app.sql` from
  `r.payroll_group_code as company_code`).
- mart-missing spot-check:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__stipend_and_bonus_app.sql`
  — the entire approval-workflow surface (`first_approval`, `second_approval`,
  `event_id`, `amount`-as-requested) is projected straight from
  `stg_google_appsheet__stipend_and_bonus__output`; no intervening `fct_`/`dim_`
  mart exists for this grain, confirmed by
  `find src/dbt/kipptaf/models/marts -iname "*stipend*"` returning nothing.
