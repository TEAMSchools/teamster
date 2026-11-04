# Cube Gap Catalog — Support

Part of the [Cube Connector Gap Catalog](2026-10-02-cube-gap-catalog.md). Refs
#5673. One section per core-set dashboard; tables and notes are the per-workbook
inventory extracted from the production .twb and classified against the dbt
marts and Cube model YAML as of 2026-10-02.

## Zendesk Dashboard (`zendesk_dashboard`)

- workbook: Zendesk Reporting | contentUrl `ZendeskReporting` | luid
  `7adabf6e-fa59-4d60-bca8-de3a67005a53` | project Production
- upstream datasources: `rpt_tableau__zendesk_tickets (kipptaf_tableau)`
  (embedded, this is the only datasource actually used by any worksheet);
  `federated.1n5zf3g1xijcyo1h7w9gk0dv86qp` (embedded) is an unused leftover
  "Sample - Superstore" template datasource with zero worksheet dependencies —
  flagged, not inventoried further.
- rpt_/source models in use (from datasource + SQL):
  `rpt_tableau__zendesk_tickets` (reads `source(zendesk, tickets)`,
  `int_zendesk__tickets__custom_fields_pivot`, `stg_zendesk__users`,
  `source(zendesk, groups)`, `stg_zendesk__ticket_metrics`,
  `stg_zendesk__ticket_audits__events`, `int_people__staff_roster`)
- published dashboards inventoried: Launch (navigation/landing page only — no
  worksheet zones, just logo/text/nav button; carries no data fields), Ticket
  Overview (all 4 worksheets: Agent, Category, Roster, View by
  Group/Region/Location)
- sheets excluded as hidden/scratch: 0 — no `hidden='true'` windows in the twb;
  all 4 worksheets are on the one data dashboard
- regions served by this dashboard overall: all (network-wide). Verified against
  the workbook: `rpt_tableau__zendesk_tickets.sql` has no region WHERE-clause
  (only `t.status != 'deleted'`), and the dashboard's quick filters are
  entity/site pickers (Assignee Legal Entity, Assignee Primary Site, Submitter
  Entity, Submitter Site), not a hard-coded single region — consistent with the
  Asana "network-wide" hint. Caveat: `submitter_entity` /
  `assignee_legal_entity` are KTAF-vs-Region flags (derived from
  `home_business_unit_name`; "KIPP TEAM and Family Schools Inc." = KTAF,
  anything else = "Region"), not canonical newark/camden/miami/paterson labels —
  see Notes.

### Measures

| metric                          | agg                                                                                                | source field / formula (trimmed)                                                                                           | dashboards                                                              | status                                              | where                                                                            | regions |
| ------------------------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- | --------------------------------------------------- | -------------------------------------------------------------------------------- | ------- |
| Ticket Count                    | Count                                                                                              | `COUNT(*)` over `rpt_tableau__zendesk_tickets` (internal object-id count field)                                            | Agent, Category, Roster, View by Group/Region/Location                  | mart-ready                                          | `fct_support_tickets.support_ticket_key` (count of rows)                         | all     |
| 1st Reply - Bus. Hrs.           | Avg                                                                                                | `ROUND([reply_time_in_minutes_business]/60,1)`                                                                             | Agent, View by Group/Region/Location                                    | mart-ready                                          | `fct_support_tickets.business_minutes_to_first_reply` (divide by 60)             | all     |
| Solved - Bus. Day               | Avg                                                                                                | `ROUND([total_bh_minutes]/600,2)`                                                                                          | Agent, Roster (feeds # Days From Create), View by Group/Region/Location | mart-ready                                          | `fct_support_tickets.business_minutes_to_solve` (divide by 600)                  | all     |
| # Days From Create              | per-row calc (role=dimension/ordinal in Tableau, but computes a metric; also has a `Sum` instance) | `IF [Status]='Closed' THEN ROUND(Solved-Bus.Day,0) ELSEIF [Status]='Open' THEN DATEDIFF('day', Created(Display), TODAY())` | Roster                                                                  | mart-ready (needs case logic, not pure aggregation) | `fct_support_tickets.status` + `business_minutes_to_solve` + `created_timestamp` | all     |
| Percent of Total (ticket count) | table calc (`pcto`)                                                                                | percent-of-total of ticket count, tooltip/label text + range filter                                                        | Agent, Category, View by Group/Region/Location                          | workbook-only                                       | n/a — Tableau table calculation                                                  | all     |

Variants collapsed: "1st Reply - Bus. Hrs." and "Solved - Bus. Day" are each a
single calculated field reused identically across sheets (no per-sheet
variants). "Percent of Total" is the same table calc on 3 sheets.

### Dimensions

| dimension                                                                                                     | used as                                                                                                  | status                                                                                    | where                                                                                                                                                                                                                                                                        | regions                                                            |
| ------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| Assignee (`assignee`)                                                                                         | rows (Agent), row list (Roster), color/filter (View by), quick filter                                    | mart-ready                                                                                | `dim_staff` via `fct_support_tickets.assignee_staff_key` (staff name)                                                                                                                                                                                                        | all                                                                |
| Status (`ticket_status`, binned to Closed/Open)                                                               | underlies "Status + Tier"; standalone quick filter                                                       | mart-ready                                                                                | `fct_support_tickets.status` (raw value; Closed/Open binning is a workbook display recode)                                                                                                                                                                                   | all                                                                |
| Tech Tier (`tech_tier`)                                                                                       | underlies "Status + Tier"                                                                                | mart-ready                                                                                | `fct_support_tickets.tech_tier`                                                                                                                                                                                                                                              | all                                                                |
| Status + Tier (calc: `[Status] + ' ' + tech_tier`)                                                            | color + LOD on Agent, Category, Roster, View by; dashboard filter-action pivot                           | mart-ready                                                                                | concat of `fct_support_tickets.status` + `.tech_tier` (trivial display concat, no mart column for the combo itself)                                                                                                                                                          | all                                                                |
| Category (`category`)                                                                                         | underlies "Ticket Category"                                                                              | mart-ready                                                                                | `fct_support_tickets.category`                                                                                                                                                                                                                                               | all                                                                |
| Ticket Category (calc: `REPLACE(category,'__',' - ')`)                                                        | rows (Category sheet), quick filter                                                                      | mart-ready                                                                                | `fct_support_tickets.category` (display replace is trivial formatting)                                                                                                                                                                                                       | all                                                                |
| Ticket Subject (`ticket_subject`)                                                                             | row list (Roster), filter (filter-group 8) on Agent/Category/Roster/View by                              | mart-ready                                                                                | `fct_support_tickets.subject`                                                                                                                                                                                                                                                | all                                                                |
| Ticket Id (`ticket_id`)                                                                                       | row list + filter (Roster)                                                                               | mart-missing                                                                              | `rpt_tableau__zendesk_tickets.ticket_id` — raw ticket id is not exposed as a plain column on `fct_support_tickets` (only hashed into `support_ticket_key`)                                                                                                                   | all                                                                |
| Created At / "Created (Display)" / "Created At (copy)" (`created_at`)                                         | month/year grouping (Agent, Category, View by), day-trunc row list (Roster), quick filter (date range)   | mart-ready                                                                                | `fct_support_tickets.created_timestamp` / `created_date_key`                                                                                                                                                                                                                 | all                                                                |
| Solved At / "Solved At (Display)" / "Solved At (copy)" (`solved_at`)                                          | month/year grouping (Agent, Category, View by), day-trunc + year col (Roster), quick filter (date range) | mart-ready                                                                                | `fct_support_tickets.solved_timestamp` / `solved_date_key`                                                                                                                                                                                                                   | all                                                                |
| Group / "Zendesk Group" (calc: categorical-bin on `last_group`, null→"[Not Assigned]")                        | row list (Roster), quick filter (Agent sheet), one branch of "View by" param                             | mart-missing                                                                              | `rpt_tableau__zendesk_tickets.last_group` — not carried onto `fct_support_tickets` at all                                                                                                                                                                                    | all                                                                |
| Location (`location`)                                                                                         | one branch of "View by" param                                                                            | mart-missing                                                                              | `rpt_tableau__zendesk_tickets.location` — `fct_support_tickets.location_key` exists structurally but currently fails 100% of its `relationships` test against `dim_locations` pending a Zendesk-slug → canonical-location crosswalk (issue #3709), so it is not usable today | all                                                                |
| Submitter Entity (`submitter_entity`, = staff roster `home_business_unit_name`)                               | one branch of "View by" param, quick filter                                                              | mart-missing                                                                              | `rpt_tableau__zendesk_tickets.submitter_entity` — neither `fct_support_tickets` nor `dim_staff` carries legal-entity/business-unit attributes                                                                                                                                | all (KTAF-vs-Region flag, not a canonical region code — see Notes) |
| Submitter Site (`submitter_site`, = staff roster `home_work_location_name`)                                   | row list (Roster), quick filter                                                                          | mart-missing                                                                              | `rpt_tableau__zendesk_tickets.submitter_site` — not on `dim_staff`                                                                                                                                                                                                           | all                                                                |
| Assignee Legal Entity (`assignee_legal_entity`)                                                               | quick filter only                                                                                        | mart-missing                                                                              | `rpt_tableau__zendesk_tickets.assignee_legal_entity` — not on `dim_staff`                                                                                                                                                                                                    | all (KTAF-vs-Region flag)                                          |
| Assignee Primary Site (`assignee_primary_site`)                                                               | quick filter only                                                                                        | mart-missing                                                                              | `rpt_tableau__zendesk_tickets.assignee_primary_site` — not on `dim_staff`                                                                                                                                                                                                    | all                                                                |
| "View by" (calc, parameter-switched: Region→`submitter_entity` / Zendesk Group→`Group` / Location→`location`) | rows (View by Group/Region/Location sheet)                                                               | mart-missing (2 of 3 branches mart-missing; Location branch additionally has a broken FK) | see per-branch rows above                                                                                                                                                                                                                                                    | all                                                                |
| "View by" parameter control (`[Parameters].[Parameter 1]`)                                                    | dashboard parameter control, default "Zendesk Group"                                                     | workbook-only                                                                             | n/a — Tableau parameter, not a data field                                                                                                                                                                                                                                    | all                                                                |
| "Group Set" (dynamic Tableau Set: groups with ticket count > 25)                                              | quick-filter construct (not directly shelved on any of the 4 sheets)                                     | workbook-only                                                                             | n/a — live-recomputed Tableau Set                                                                                                                                                                                                                                            | all                                                                |

Dashboard filter-actions ("Action (Status + Tier, Assignee)", "...,Group)",
"...,View by)") are Tableau click-to-filter plumbing (auto-generated
`sheet_link` groups), not data fields — mentioned here, not scored.

### Notes

- **No Cube coverage at all.** `rg -l 'zendesk|ticket|support' src/cube/model`
  returns no cube or view referencing Zendesk/support-ticket data. Every row
  above is therefore mart-ready or mart-missing/workbook-only; there are no
  cube-covered rows in this inventory (see Verification).
- **Asana blockers confirmed, with one likely typo flagged as instructed.**
  `fct_support_tickets` (marts/facts) exists and backs most ticket-level
  measures and several dimensions. `fct_tableau_usage` does not exist anywhere
  in `src/dbt` — almost certainly a typo for `fct_support_tickets` in the Asana
  task. `dim_staff` exists but is a thin identity dim (name, DOB, demographics,
  contact, hire dates only) — it does **not** carry legal entity, work
  location/site, or department, so it cannot resolve the regional breakdown
  fields (`submitter_entity`, `submitter_site`, `assignee_legal_entity`,
  `assignee_primary_site`) that the "View by Group/Region/Location" sheet needs.
  This is a real, substantive blocker, not just a naming slip.
- **Population mismatch between the Tableau datasource and the mart.**
  `rpt_tableau__zendesk_tickets` left-joins submitter/assignee to staff roster
  (keeps every non-deleted ticket). `fct_support_tickets` **inner**-joins
  submitter to `int_people__staff_roster` ("Scoped to tickets submitted by
  active KIPP staff members" per its description) and excludes original-group
  bookkeeping fields entirely. Any Cube/mart build-out on `fct_support_tickets`
  would under-count tickets relative to what the dashboard shows today for
  submitters who aren't active staff (e.g. departed staff, non-staff
  submitters). Flagging as a scope decision for whoever builds the Cube cube,
  not a blocker on its own.
- **`location_key` is a structural dead end today.** It joins
  `int_zendesk__tickets__custom_fields_pivot.location` (a Zendesk custom-field
  slug) to `int_people__location_crosswalk.location_name` by literal string
  match; the mart's own properties.yml documents a 100% `relationships` test
  failure pending issue #3709. Treat "Location" as mart-missing, not mart-ready,
  until that crosswalk ships.
- **Judgment calls**: "Status + Tier" and "Ticket Category" are trivial string
  concatenation/replace on top of mart-ready raw columns; scored mart-ready
  rather than workbook-only since a Cube view could trivially reproduce the same
  derived dimension. "# Days From Create" needs branching case logic (not pure
  aggregation) but every input is mart-ready, so scored mart-ready with that
  caveat. The Tableau "Group" field is a categorical-bin over `last_group`
  purely for null-labeling ("[Not Assigned]"); scored on the underlying
  `last_group` field, which is mart-missing.
- Workbook has only 2 views total (Launch, Ticket Overview) and 4 worksheets;
  this is a small, single-purpose operational dashboard, not a multi-tab suite.

### Verification

- No cube-covered row exists to spot-check (confirmed via
  `rg -l 'zendesk|ticket|support' src/cube/model/cubes src/cube/model/views`
  returning nothing relevant to Zendesk/support tickets — the 3 files that
  matched "support" are unrelated assessment/attendance cubes using the word in
  prose).
- mart-ready spot-check: "Solved - Bus. Day" →
  `src/dbt/kipptaf/models/marts/facts/fct_support_tickets.sql` line 42:
  `tm.full_resolution_time_in_minutes_business as business_minutes_to_solve,`
  (Tableau's calc divides this same source value by 600 to convert minutes to
  business days).
- mart-missing spot-check: "Submitter Entity" →
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__zendesk_tickets.sql`
  line 59: `sx.home_business_unit_name as submitter_entity,` — confirmed absent
  from both `fct_support_tickets.sql` and `dim_staff.sql` (`dim_staff` only
  selects identity/demographic/contact/hire-date columns from
  `int_people__staff_roster_history`).
