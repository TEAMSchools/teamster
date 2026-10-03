# Cube Gap Catalog — Observations

Part of the [Cube Connector Gap Catalog](2026-10-02-cube-gap-catalog.md). Refs
#5673. One section per core-set dashboard; tables and notes are the per-workbook
inventory extracted from the production .twb and classified against the dbt
marts and Cube model YAML as of 2026-10-02.

## Grow Dashboard (`grow_dashboard`)

- workbook: SchoolMint Grow Dashboard | contentUrl
  `SchoolMintGrowDashboard_17226096936880` | luid
  `b529ca04-3560-4cff-8898-fd0a65f3e994` | project Production
- upstream datasources (all embedded, none published separately):
  `rpt_tableau__schoolmint_grow_goals`,
  `rpt_tableau__schoolmint_grow_observation_details`,
  `rpt_tableau__teacher_observations`
- rpt_/source models in use (from datasource captions + SQL):
  `rpt_tableau__schoolmint_grow_goals`,
  `rpt_tableau__schoolmint_grow_observation_details`,
  `rpt_tableau__teacher_observations`. Upstream of the latter two:
  `int_performance_management__overall_scores`,
  `int_performance_management__observation_details`,
  `int_people__staff_roster_history`, `int_people__location_crosswalk`,
  `int_students__teacher_grade_levels`, `stg_google_sheets__reporting__terms`.
- published dashboards inventoried: Home, Microgoals, O3s, PM Details, PM
  Norming, PM Trends, Performance Management, Walkthrough Details, Walkthrough
  Trends, Walkthroughs (all 10 server views; none hidden)
- sheets excluded as hidden/scratch: 0 hidden dashboards. 8 worksheets exist in
  the .twb but are **not placed on any dashboard zone and are not server views**
  (`pulse_checker__*` x6, `pulsechecker ban1`/`ban2`) — WIP sheets for an
  "Outlier Observers" feature (titles reference "27 PM metrics", a PCA scatter
  plot). These map to the Asana-named `rpt_tableau__pm_outlier_detection`
  replacement target but are out of scope for this inventory since nothing
  displays them today.
- regions served by this dashboard overall: **all** (Newark/TEAM, Camden/KCNA,
  Miami, Paterson) — confirmed via the Home dashboard's RLS calcs
  (`RLS - Entity Gate`), which explicitly gate on all four
  `home_business_unit_name` values plus a KTAF all-access group. One dashboard
  (`Walkthroughs` → `walkthrough_met_goal`) is titled "MIA Phase Goals" but
  carries no business-unit filter restricting it to Miami — see Notes.

### Measures

| metric                                           | agg     | source field / formula (trimmed)                                                                                                                | dashboards                                                                                                                                                          | status        | where                                                                                                                                                                                                                                    | regions                                                                                                                              |
| ------------------------------------------------ | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Observation Score                                | avg     | `observation_score`                                                                                                                             | Walkthroughs (scores/top/bottom/met_goal/individual/BAN), Walkthrough Details (dept/grade/n_kids/observer/individual), PM Trends (timeline), PM Details (teammates) | mart-ready    | `fct_staff_observations.score`                                                                                                                                                                                                           | all                                                                                                                                  |
| Row Score / Indicator Score                      | avg     | `row_score` (per rubric measurement item)                                                                                                       | Walkthrough Details (all 5 sheets), Walkthrough Trends, PM Details (dept/grade/observers/teammates), PM Trends (rows_timeline)                                      | mart-ready    | `fct_staff_observation_scores.score_value`                                                                                                                                                                                               | all                                                                                                                                  |
| ETR Row Score / Self & Others (S&O) Row Score    | avg     | `{FIXED observation_id: AVG(IF [Rubric Row (group)]='ETR' and academic_year>=2024 then row_score...)}` (and S&O variant)                        | PM Norming (dept/bottom/top20/school/etr_so_bottom/etr_so_top20), PM Details (BAN, teammates)                                                                       | mart-ready\*  | `fct_staff_observation_scores.score_value` filtered via `dim_staff_observation_rubric_measurements.strand_name`                                                                                                                          | all                                                                                                                                  |
| Final Score                                      | avg     | `final_score` — FIXED per employee+academic_year (avg of PM2+PM3 rounds)                                                                        | PM Details (teammates, BAN), PM Norming (dept/grade)                                                                                                                | mart-missing  | `int_performance_management__overall_scores` (via `rpt_tableau__schoolmint_grow_observation_details`) — no mart/fact carries this yet                                                                                                    | all                                                                                                                                  |
| Final Tier / round(AVG(Final Tier))              | avg     | `final_tier` (tiered from Final Score)                                                                                                          | PM Details (teammates, BAN), PM Norming (dept/grade)                                                                                                                | mart-missing  | same as Final Score                                                                                                                                                                                                                      | all                                                                                                                                  |
| Tier / Overall Tier                              | avg     | `overall_tier` (per-observation)                                                                                                                | PM Details (teammates), PM Norming (race, etr_so_bottom, etr_so_top20)                                                                                              | mart-ready    | `fct_staff_observations.overall_rating` (renamed from `overall_tier`)                                                                                                                                                                    | all                                                                                                                                  |
| Observation Score (Group) / Rank (window calcs)  | usr     | `WINDOW_AVG(AVG(observation_score))`; `RANK(AVG(observation_score))`                                                                            | PM Details (dept/grade/observers)                                                                                                                                   | workbook-only | table calc layered on the mart-ready Observation Score; no new data                                                                                                                                                                      | all                                                                                                                                  |
| Jitter                                           | avg     | `RANDOM()`                                                                                                                                      | PM Norming (race_whisker)                                                                                                                                           | workbook-only | pure chart viz helper                                                                                                                                                                                                                    | all                                                                                                                                  |
| Has Observation (base completion flag)           | sum/avg | `{FIXED employee_number,type,period: MAX(is_observed)}`; PM variant `iif({FIXED employee_number: countd(observation_id)}>0,1,0)`                | O3s (BAN, tracking_location), Walkthroughs (BAN, tracking_location), Performance Management (tracking_BAN)                                                          | mart-ready    | existence of a row in `fct_staff_observations` joined to `dim_staff_observation_expectations` by staff/term/type                                                                                                                         | all                                                                                                                                  |
| Observations/Expected (completion %)             | usr     | `sum(Has Observation)/COUNTD(expected)`                                                                                                         | O3s (BAN, tracking_location), Walkthroughs (BAN, tracking_location)                                                                                                 | mart-ready    | count(`fct_staff_observations`) / count(`dim_staff_observation_expectations`), joined staff+term+type                                                                                                                                    | all                                                                                                                                  |
| % Observed (PM)                                  | usr     | `SUM(Observed Employees)/COUNTD(eligible)`                                                                                                      | Performance Management (tracking_location)                                                                                                                          | mart-ready    | same construction as above, PM term type                                                                                                                                                                                                 | all                                                                                                                                  |
| Is Observed                                      | max     | raw `is_observed` flag                                                                                                                          | Performance Management (tracking_table)                                                                                                                             | mart-ready    | existence in `fct_staff_observations`                                                                                                                                                                                                    | all                                                                                                                                  |
| Meeting Goal                                     | avg     | `IF {FIXED employee_number,type,code: MAX(observation_score)}>=0.83 THEN 1 ELSEIF job_title='Teacher in Residence' AND ...>=0.50 THEN 1 ELSE 0` | Walkthroughs (met_goal)                                                                                                                                             | mart-missing  | hardcoded threshold logic in the .twb calc only; lives nowhere in dbt                                                                                                                                                                    | flagged — title says "MIA Phase Goals \| Goal = 85%" but the calc hardcodes 0.83/0.50 and carries no business-unit filter; see Notes |
| Teachers with Microgoals                         | sum     | `{fixed employee_number: Max(is_assigned)}`                                                                                                     | Microgoals (BAN, tracking)                                                                                                                                          | mart-ready    | existence in `fct_staff_observation_goals` (countd teacher_staff_key)                                                                                                                                                                    | all                                                                                                                                  |
| % Assigned (pct_assigned_goals)                  | usr     | `Sum(Teachers with Microgoals)/COUNTD(employee_number)`                                                                                         | Microgoals (BAN, tracking)                                                                                                                                          | mart-missing  | numerator is mart-ready (`fct_staff_observation_goals`); denominator "teachers expected to receive Microgoals" population is not materialized anywhere. **This is the open Asana measure task `staff_observations.pct_assigned_goals`.** | all                                                                                                                                  |
| CNTD(employee_number) — teacher headcount        | ctd     | `employee_number`                                                                                                                               | O3s/Microgoals/Walkthrough/PM BANs, PM Norming (race)                                                                                                               | mart-ready    | `dim_staff` / `dim_staff_work_assignments` distinct count                                                                                                                                                                                | all                                                                                                                                  |
| CNTD(assignment_id) — microgoal assignment count | ctd     | `assignment_id`                                                                                                                                 | Microgoals (BAN, distribution, tracking_individual)                                                                                                                 | mart-missing  | `assignment_id` is dropped as join-only plumbing (R8) from `fct_staff_observation_goals`'s final select — no equivalent distinct-count column exposed                                                                                    | all                                                                                                                                  |
| CNTD(goal_name) — distinct Microgoals assigned   | ctd     | `goal_name`                                                                                                                                     | Microgoals (BAN, distribution)                                                                                                                                      | mart-ready    | `countd(staff_observation_goal_type_key)` on `fct_staff_observation_goals`, joined to `dim_staff_observation_goal_types.goal_name`                                                                                                       | all                                                                                                                                  |
| CNTD(observation_id)                             | ctd     | `observation_id`                                                                                                                                | O3_tracking_table, Walkthrough (tracking_table, rows_timeline, timeline)                                                                                            | mart-ready    | `countd(staff_observation_key)` on `fct_staff_observations`                                                                                                                                                                              | all                                                                                                                                  |
| Rank (Top 20 / Bottom 20)                        | usr     | `RANK(AVG(observation_score))`                                                                                                                  | PM Norming (bottom_20, top_20, etr_so_bottom, etr_so_top_20)                                                                                                        | workbook-only | table calc over mart-ready Observation Score                                                                                                                                                                                             | all                                                                                                                                  |

### Dimensions

| dimension                                                                | used as                | status       | where                                                                                                                                                                                                   | regions |
| ------------------------------------------------------------------------ | ---------------------- | ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Teammate / Observer Name / Manager                                       | row/filter             | mart-ready   | `dim_staff.full_name` via `fct_staff_observations.teacher_staff_key`/`observer_staff_key`; manager via `dim_staff_reporting_chain`                                                                      | all     |
| Location (`location_clean_name`)                                         | row/filter             | mart-ready   | `dim_locations.location_clean_name`                                                                                                                                                                     | all     |
| home_business_unit_name / Region                                         | filter                 | mart-ready   | `dim_regions`/`dim_locations`                                                                                                                                                                           | all     |
| home_department_name                                                     | row (dept comparison)  | mart-ready\* | `dim_staff_work_assignments` (not individually verified column name)                                                                                                                                    | all     |
| Job Title                                                                | row/filter             | mart-ready\* | `dim_staffing_positions` / `dim_staff_work_assignments`                                                                                                                                                 | all     |
| Grade Band                                                               | filter                 | mart-ready   | `dim_staff_observation_expectations.position_title` / roster `home_work_location_grade_band`                                                                                                            | all     |
| Grade Taught                                                             | row (grade comparison) | mart-missing | computed in `rpt_tableau__schoolmint_grow_observation_details`/`__teacher_observations` from `int_students__teacher_grade_levels` (highest count of students taught, per PowerSchool) — not in any mart | all     |
| Number Of Kids (class size)                                              | row                    | mart-missing | `rpt_tableau__teacher_observations` only (observer-entered dropdown) — not in any mart                                                                                                                  | all     |
| race_ethnicity_reporting                                                 | row/filter             | mart-ready\* | `dim_staff.race` + `is_hispanic` (split fields; Tableau's single reporting category isn't an exact 1:1 match — verify mapping)                                                                          | all     |
| Measurement Name                                                         | row/filter             | mart-ready   | `dim_staff_observation_rubric_measurements.name`                                                                                                                                                        | all     |
| Strand Name                                                              | row/filter             | mart-ready   | `dim_staff_observation_rubric_measurements.strand_name`                                                                                                                                                 | all     |
| Microgoal (goal_name) / goal_type_name / bucket_name                     | row/filter             | mart-ready   | `dim_staff_observation_goal_types` (`goal_name`, `goal_type`, `bucket_name`)                                                                                                                            | all     |
| tracking_code / tracking_rubric / tracking_type / tracking_academic_year | filter                 | mart-ready   | `dim_terms` (`code`/`name`/`type`/`academic_year`) via `dim_staff_observation_expectations.term_key`                                                                                                    | all     |
| Term Code / Academic Year                                                | filter                 | mart-ready   | `dim_terms` / `fct_staff_observations.academic_year`                                                                                                                                                    | all     |
| Type (observation type: O3/Walkthrough/PM)                               | filter                 | mart-ready   | `dim_staff_observation_types` (`name`/`abbreviation`)                                                                                                                                                   | all     |
| Code / Period (weekly period label, O3 & Walkthrough only)               | row/filter             | mart-missing | ad hoc weekly bucketing built in `rpt_tableau__teacher_observations`; no equivalent in `dim_terms` or any mart                                                                                          | all     |
| current_assignment_status                                                | filter                 | mart-ready\* | likely `dim_staff_status` (not individually verified)                                                                                                                                                   | all     |
| pm_round_eligible                                                        | filter                 | mart-missing | custom leave-adjusted CASE logic (`recent_leave` CTE) in `rpt_tableau__schoolmint_grow_observation_details`; close to but not the same as `dim_staff_observation_expectations.is_current`               | all     |
| Observed At / Assignment Date                                            | detail                 | mart-ready   | `fct_staff_observations.observed_timestamp` / `fct_staff_observation_goals.assignment_date`                                                                                                             | all     |

### Notes

- **No observations/performance-management cube exists at all**
  (`src/cube/model/cubes/` has only `conformed`, `courses`, `staff`,
  `student_assessments`, `students`). Every row above that is `cube-covered`
  would be zero — confirmed by grepping `src/cube/model/` for "schoolmint",
  "observation", "microgoal", "walkthrough": the only hit is a one-line comment
  in `staff_reporting_relationships.yml` saying this cube is "retained for
  future fact cubes (observations, gradebook, ...)". So **0 measures and 0
  dimensions are cube-covered**; this dashboard's entire Cube-connector gap is
  "build the cube," not "fix a mismatch."
- The Asana task's named blockers (`fct_observations`, `fct_microgoals`,
  `fct_performance_evaluations`, `dim_staff`, `dim_locations`,
  `dim_observation_rubrics`) are **stale names**. The marts that actually ship
  today are `fct_staff_observations`, `fct_staff_observation_scores`,
  `fct_staff_observation_goals`, `dim_staff`, `dim_locations`,
  `dim_staff_observation_rubrics` (+
  `dim_staff_observation_rubric_measurements`, `dim_staff_observation_types`,
  `dim_staff_observation_goal_types`, `dim_staff_observation_expectations`).
  These cover observation scoring and microgoal assignment well (12/20 measures,
  15/19 dimensions mart-ready) — the real remaining gaps are narrower than Asana
  implies: (1) PM `final_score`/`final_tier` (PM2/PM3 round averaging), (2) the
  microgoal "% Assigned" denominator population (the explicitly open
  `staff_observations.pct_assigned_goals` task), (3)
  `grade_taught`/`number_of_kids` teacher-context attributes, (4) the ad hoc
  weekly `code`/`period` bucketing for O3/Walkthrough, and (5) the
  leave-adjusted `pm_round_eligible` flag.
- **ETR/S&O row-score grouping** (strand name → "ETR" vs "S&O" category) is a
  hardcoded Tableau `IF...IN(...)` grouping, not a materialized column anywhere.
  `dim_staff_observation_rubric_measurements.strand_name` has the raw strand
  names needed to rebuild the grouping, so this is marked mart-ready with a
  caveat rather than mart-missing — but the mapping itself needs to be
  re-authored (in Cube or dbt) from the Tableau calc, not just referenced.
- **Discrepancy worth flagging to the business owner**: `walkthrough_met_goal`'s
  title says "MIA Phase Goals... Goal = 85%" but the underlying calc hardcodes
  `>=0.83` (83%) for most staff and `>=0.50` for Teachers in Residence, and the
  worksheet carries no `home_business_unit_name` filter — so today it silently
  applies an undocumented Miami-labeled threshold to every region's walkthrough
  scores. Confirm intent before porting this measure into Cube.
- `rpt_tableau__teacher_observations` (O3s + Walkthroughs) and
  `rpt_tableau__schoolmint_grow_observation_details` (PM + Norming) both draw
  from the same underlying
  `fct_staff_observations`/`fct_staff_observation_scores` grain, differentiated
  only by `dim_staff_observation_types` — i.e., the three datasources this
  workbook embeds are largely the same fact table sliced three ways, which is
  good news for a single unified Cube.
- RLS/permission fields (`RLS - Entity Gate`, `RLS - Location Gate`,
  `RLS - Role Gate`, `Permissions`/`User_test`, `Lockbox`, `Program Filter`,
  `No Null Term Filters`) and multi-field `Action (...)` dashboard-click-filter
  combiners are access-control/interactivity plumbing, not metrics — excluded
  from the tables above by design.
- 47 worksheets are in scope (sum of each dashboard's zone count = 47, verified
  against the parsed `<dashboards>` XML); the 8 `pulse_checker*` sheets (not
  zoned, not server views) are out of scope per Step 0 but noted above since
  they map directly to the Asana-named `rpt_tableau__pm_outlier_detection` work.
- `home_department_name`, `job_title`, `current_assignment_status`, and
  `race_ethnicity_reporting` mart locations are marked `mart-ready*` (asterisk)
  because I located the field conceptually on a staff dimension/roster model but
  did not individually open every dim YAML to confirm the exact column name —
  flagged for verification during actual Cube build, not a blocker to
  classification.

### Verification

- **cube-covered spot-check**: none exist to check — confirmed by
  `find src/cube/model -iname "*observ*"` returning only
  `staff_reporting_relationships.yml`, which contains a single comment line
  (`# ... Retained for future fact cubes (observations, gradebook, ...)`) and no
  actual cube.
- **mart-ready spot-check**: `Row Score` →
  `/workspaces/teamster/src/dbt/kipptaf/models/marts/facts/properties/fct_staff_observation_scores.yml`,
  column `score_value` ("Numeric score assigned to this measurement item"), PK
  `generate_surrogate_key(["sd.observation_id", "sd.measurement_id"])`.
- **mart-missing spot-check**: `Final Score`/`Final Tier` → traced via
  `grep -n "final_score\|final_tier" src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__schoolmint_grow_observation_details.sql`
  to `os.final_score`/`os.final_tier` sourced
  `from {{ ref("int_performance_management__overall_scores") }} as os` — an
  intermediate model, with no corresponding column on `fct_staff_observations`
  or any other mart file under `src/dbt/kipptaf/models/marts/`.

## Coaching Conversation Tool (`coaching_conversation_tool`)

- workbook: Coaching Conversation Tool | contentUrl `CoachingConversationTool` |
  luid `db88d328-0d54-4dac-8003-6197841e1432` (verified, matches hint) | project
  Production
- upstream datasources: `rpt_tableau__schoolmint_grow_observation_details`
  (embedded, single datasource for the whole workbook)
- rpt_/source models in use: `rpt_tableau__schoolmint_grow_observation_details`
  (the only one — matches Asana's named replacement target). Its own sources:
  `int_people__staff_roster_history`, `int_people__staff_roster`,
  `int_people__location_crosswalk`, `stg_google_sheets__reporting__terms`,
  `int_performance_management__overall_scores`,
  `int_performance_management__observation_details`,
  `int_students__teacher_grade_levels`,
  `int_adp_workforce_now__employee_memberships_by_year`
- published dashboards inventoried: `Coaching Conversation Tool` (the single
  server view; matches `get-workbook`'s one-entry `views` list)
- sheets excluded as hidden/scratch: 3 — `coaching_convo_BAN` (worksheet defined
  but placed on neither dashboard; orphaned), `Easy Download`,
  `Easy Download (2)` (both only on `Dashboard 2`, a second dashboard in the
  .twb not returned by `get-workbook`'s views list — no `hidden='true'` marker
  exists in the XML for either dashboard/window, but the server content API
  lists only one published view, so `Dashboard 2` is treated as not
  server-published; **flagged** per instructions since `showTabs: true` means it
  could in principle surface as a tab — recommend the dashboard owner confirm)
- regions served by this dashboard overall: **all** (network-wide staff
  performance management) — confirmed via the workbook's own RLS calcs
  (`RLS - Entity Gate` / `RLS - Location Gate` / `RLS - Role Gate` /
  `Permissions`), which explicitly enumerate all four regions' business units
  (TEAM Academy Charter School = Newark, KIPP Cooper Norcross Academy = Camden,
  KIPP Miami, KIPP Paterson) and every school location, gated by AD group
  membership + self/manager/role tiers. No region is excluded; access is
  row-level per viewer, not dashboard-scoped.

### Measures

| metric                    | agg               | source field / formula (trimmed)                                                                                                                                                                         | dashboards                                                                                                  | status        | where                                                                                                                                                                                                                                                                                                               | regions |
| ------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Observation Score         | Avg (FIXED LOD)   | `{FIXED [observation_id]:AVG([observation_score])}`                                                                                                                                                      | coaching_term_table                                                                                         | mart-ready    | `fct_staff_observations.score` (already 1 row/observation_id; plain AVG equivalent)                                                                                                                                                                                                                                 | all     |
| Observation Score (group) | Avg / CountD      | `[observation_score]` avg; `[observation_id]` CountD                                                                                                                                                     | coaching_overall_table, coaching_term_table (filter/context)                                                | mart-ready    | `fct_staff_observations.score` / `staff_observation_key`                                                                                                                                                                                                                                                            | all     |
| Tier (overall_tier)       | Avg               | `od.overall_tier` — tier bucket of observation_score (3.495/2.745/1.745 cutoffs)                                                                                                                         | coaching_term_table                                                                                         | mart-ready    | `fct_staff_observations.overall_rating`                                                                                                                                                                                                                                                                             | all     |
| Row Score                 | Avg               | `od.row_score` / `os.value_score`, per rubric-row (indicator) measurement                                                                                                                                | coaching_row_table                                                                                          | mart-ready    | `fct_staff_observation_scores.score_value` (join via `staff_observation_rubric_measurement_key` → `dim_staff_observation_rubric_measurements.strand_name`/`name`)                                                                                                                                                   | all     |
| ETR Row Score             | Avg (FIXED LOD)   | `{FIXED [observation_id]: AVG(IF [Rubric Row (group)]='ETR' and academic_year>=2024 then [row_score] ELSE [etr_score] END)}` — blends current SchoolMint Grow row_score with archived etr_score pre-2024 | coaching_overall_table, coaching_term_table                                                                 | mart-missing  | no mart computes this blended/archive-aware average; current-year half is `fct_staff_observation_scores.score_value`, archive half (`etr_score`) lives only in `int_performance_management__observation_details` (intermediate, archive branch) — rpt model: `rpt_tableau__schoolmint_grow_observation_details.sql` | all     |
| Self & Others Row Score   | Avg (FIXED LOD)   | same pattern as ETR Row Score, strand `S&O` / archive `so_score`                                                                                                                                         | coaching_overall_table, coaching_term_table                                                                 | mart-missing  | same as above — `etr_score`/`so_score` only in `int_performance_management__observation_details`; rpt model: `rpt_tableau__schoolmint_grow_observation_details.sql`                                                                                                                                                 | all     |
| Final Score               | Avg               | `os.final_score` — avg of PM2/PM3 `observation_score` (current) union archive final_score                                                                                                                | coaching_overall_table                                                                                      | mart-missing  | `int_performance_management__overall_scores` (intermediate only; no mart exposes final_score/final_tier)                                                                                                                                                                                                            | all     |
| Final Tier                | Avg               | `os.final_tier` — tier bucket of final_score, same cutoffs as overall_tier                                                                                                                               | coaching_overall_table                                                                                      | mart-missing  | `int_performance_management__overall_scores`                                                                                                                                                                                                                                                                        | all     |
| Is Observed               | (dependency only) | `is_observed` = 1 if observation_id not null                                                                                                                                                             | all 4 data sheets (column dependency; not found encoded on rows/cols/text/color/size in any in-scope sheet) | workbook-only | listed `tooltip-only`-equivalent / unused-encoding; not a displayed metric in the published dashboard                                                                                                                                                                                                               | all     |

Variants note: ETR/Self & Others Row Score and Final Score/Final Tier appear
identically on both `coaching_overall_table` ("past scores and tiers," grouped
by academic year) and `coaching_term_table` ("scores and tiers by term," grouped
by term) — same measures, different time grain; collapsed to one row each above.

### Dimensions

| dimension                                                                              | used as                                                                       | status        | where                                                                                                                                                                                                                                                                          | regions |
| -------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------- |
| Academic Year                                                                          | row/dashboard filter (all 5 sheets)                                           | mart-ready    | `fct_staff_observations.academic_year`                                                                                                                                                                                                                                         | all     |
| Term Code                                                                              | row/dashboard filter                                                          | mart-ready    | `fct_staff_observations.term_key` → `dim_terms.code`                                                                                                                                                                                                                           | all     |
| Business Unit (home_business_unit_name)                                                | dashboard filter                                                              | mart-ready    | staff work assignment → `dim_regions.business_unit_name`/`legal_entity` (via `dim_staff`/`dim_locations` chain)                                                                                                                                                                | all     |
| Location (location_clean_name)                                                         | dashboard filter                                                              | mart-ready    | `fct_staff_observations.location_key` → `dim_locations.location_clean_name`                                                                                                                                                                                                    | all     |
| Teammate                                                                               | dashboard filter, row grouping                                                | mart-ready    | `fct_staff_observations.teacher_staff_key` → `dim_staff` (formatted name)                                                                                                                                                                                                      | all     |
| Manager                                                                                | dimension (RLS / display)                                                     | mart-ready    | `dim_staff.manager` / reports-to chain                                                                                                                                                                                                                                         | all     |
| Job Title / Job Function                                                               | dimension (RLS role gate)                                                     | mart-ready    | `dim_staff.job_title` / `job_function`                                                                                                                                                                                                                                         | all     |
| Observation Type / Abbreviation                                                        | filter, grouping                                                              | mart-ready    | `fct_staff_observations.staff_observation_type_key` → `dim_staff_observation_types`                                                                                                                                                                                            | all     |
| Measurement Name                                                                       | filter, row grouping (coaching_row_table rows)                                | mart-ready    | `dim_staff_observation_rubric_measurements.name`                                                                                                                                                                                                                               | all     |
| Strand Name                                                                            | filter, row grouping                                                          | mart-ready    | `dim_staff_observation_rubric_measurements.strand_name`                                                                                                                                                                                                                        | all     |
| Rubric Strand (group) — "ETR"/"S&O"/"Coach Comments"/"Pre-2023 Self & Others Comments" | calculated bin over `measurement_name`, drives which FIXED-LOD branch is used | workbook-only | large hand-maintained `categorical-bin` calc (~90 named values) spanning both current and legacy/archive measurement-name spellings; no mart equivalent groups current+archive names this way (mart `strand_name` only covers current SchoolMint Grow rubric, not the archive) | all     |
| Locked                                                                                 | RLS release-gate input, not displayed as a metric                             | mart-ready    | `fct_staff_observations.is_locked`                                                                                                                                                                                                                                             | all     |
| Lockbox Date                                                                           | RLS release-gate input                                                        | mart-ready    | `stg_google_sheets__reporting__terms.lockbox_date` (not yet on a mart; terms are intermediate/staging only) → mart-ready via upstream, not mart-missing, since a simple term lookup suffices                                                                                   | all     |
| Measurement Comments                                                                   | text display (coaching_convo_comments)                                        | mart-ready    | `fct_staff_observation_scores.text_box_content` / `response_text` (field-name only; contents are free text, handle per PII rules if ever surfaced outside Tableau)                                                                                                             | all     |
| Teammate (exclude null)                                                                | filter helper calc                                                            | workbook-only | trivial `IFNULL`-style display calc, no mart equivalent needed                                                                                                                                                                                                                 | all     |
| Permissions / RLS gates (4 boolean calcs)                                              | row-level security, not displayed                                             | workbook-only | Tableau-native RLS; a Cube cube would need `row_level_security` filters wired to these same AD-group/business-unit/location rules — no cube exists today                                                                                                                       | all     |

### Notes

- No `observations` Cube cube exists (confirmed again here: no cube/view file
  under `src/cube/model/` references `fct_staff_observations`,
  `fct_staff_observation_scores`, or `dim_staff_observation_*`). Every measure
  here is at best `mart-ready`, never `cube-covered`.
- The Asana-listed blocker names (`fct_observations`, `dim_staff`,
  `dim_locations`, `dim_observation_rubrics`) are stale; the real marts are
  `fct_staff_observations`, `fct_staff_observation_scores`,
  `dim_staff_observation_rubrics`, `dim_staff_observation_rubric_measurements`,
  plus the generic `dim_staff` / `dim_locations` / `dim_regions` / `dim_terms`
  for roster and reference attributes. Confirmed via
  `src/dbt/kipptaf/models/marts/{facts,dimensions}/`.
- **`final_score`/`final_tier` and the archive-aware ETR/S&O row scores have NO
  mart at all** — they live only in `int_performance_management__overall_scores`
  and inside the `rpt_tableau__schoolmint_grow_observation_details` SQL itself
  (as Tableau FIXED-LOD calcs reading `etr_score`/`so_score`, which only the
  archive branch populates). Building a Cube connector for this dashboard would
  require either (a) a new mart wrapping
  `int_performance_management__overall_scores`, or (b) porting the FIXED-LOD
  blend logic into dbt — the bigger lift of the two gaps found.
- **How far back the data goes**: not fully determinable from SQL alone. The
  rpt_ model's second UNION branch applies no `academic_year` filter, so it
  carries the full history in `int_performance_management__observation_details`,
  which itself is
  `current SchoolMint Grow (stg_schoolmint_grow__observations, is_published) UNION ALL stg_performance_management__observation_details_archive`
  (archive sourced from an external Avro/GCS table,
  `src_performance_management__observation_details_archive`). The existence of a
  dedicated legacy archive table is consistent with the launch page's
  "2018-present" claim, but no file states the archive's earliest
  `academic_year` value — confirming the exact boundary would need a BigQuery
  row query (out of scope: no PII risk in an aggregate min(academic_year), but
  it was not run here per the "parse once" scope of this pass; recommend a
  follow-up `select min(academic_year)` against
  `int_performance_management__observation_details_archive`/`stg_performance_management__observation_details_archive`
  if the exact start year needs to be pinned down).
- The workbook's "Rubric Strand" bin is the single largest piece of Tableau-only
  logic: it re-maps ~90 historical/legacy measurement-name strings (several
  terminology eras of the same rubric) onto 4 canonical strands (ETR, S&O, Coach
  Comments, Pre-2023 S&O Comments). The mart's `strand_name` only covers the
  current rubric's own strand labels — it does not backfill the archive era's
  differently-worded measurement names into the same buckets. Porting this
  dashboard to Cube would need that bin logic moved into dbt (most likely as a
  new column on `dim_staff_observation_rubric_measurements` or a dedicated
  crosswalk model), not just a Cube view over the existing mart.
- Excluded calcs not counted as metrics: the 4 boolean RLS gate calculations
  (`Permissions`, `RLS - Entity/Location/Role/Release Gate`) are access-control
  plumbing, not displayed data — flagged `workbook-only` under Dimensions
  because a Cube migration would need to reimplement equivalent
  `row_level_security` rules, not because they're calculable from a mart column.
- `coaching_convo_BAN` (a "Big Ass Number" style worksheet, likely "Employees
  with Observations") is defined in the .twb but placed on neither dashboard —
  treated as scratch/orphaned and excluded from the measure inventory, though
  its one measure (`Calculation_1125055535464185861`, "Employees with
  Observations", `{fixed [employee_number]: Max([is_observed])}`) would map to a
  `mart-ready` COUNT/MAX over `fct_staff_observations.staff_observation_key`
  distinct `teacher_staff_key` if it were ever surfaced.

### Verification

- cube-covered: **none found** — spot-check performed by grepping
  `src/cube/model/cubes/**/*.yml` and `views/**/*.yml` for any reference to
  `fct_staff_observation`, `dim_staff_observation`, or
  `rpt_tableau__schoolmint_grow`; zero matches. No row in the
  Measures/Dimensions tables above can be marked cube-covered.
- mart-ready spot-check: **Row Score** →
  `src/dbt/kipptaf/models/marts/facts/fct_staff_observation_scores.sql`, column
  `score_value` (aliased from `os.value_score` in the model's `scores` CTE),
  joined to the observation via `staff_observation_key` and to the rubric/strand
  via `staff_observation_rubric_measurement_key`.
- mart-missing spot-check: **Final Score** → no mart file in
  `src/dbt/kipptaf/models/marts/{facts,dimensions}/` selects `final_score`;
  confirmed by `grep -rl "final_score" src/dbt/kipptaf/models/marts/` returning
  only `fct_grades_assignments.sql` (an unrelated gradebook model whose
  `final_score` is a different, course-grade concept). The real source is
  `src/dbt/kipptaf/models/performance_management/intermediate/int_performance_management__overall_scores.sql`,
  line 12 (`final_score`) / lines 14-23 (`final_tier` CASE expression).

## Teacher Development Dashboard (`teacher_development_dashboard`)

- workbook: Teacher Development Dashboard | contentUrl
  `TeacherDevelopmentDashboard_16994705799120` | luid
  `8977a813-36c8-48df-8a61-479f374ae78a` (verified — matches the expected luid
  given in the task) | project Production
- upstream datasources: `rpt_tableau__teacher_development` (single embedded
  federated datasource; no published/shared datasource)
- rpt_/source models in use: `rpt_tableau__teacher_development` (direct extract)
  → upstream `int_performance_management__observations`,
  `int_performance_management__observation_details`,
  `int_performance_management__teacher_development` (archive union branch),
  `int_performance_management__overall_scores`, `int_people__staff_roster`,
  `int_people__staff_roster_history`, `int_students__teacher_grade_levels`
- published dashboards inventoried: Details, Heat Map, Snapshots, Year in
  Review, Home (Home is a nav/landing page — image, title text, and
  navigate-to-dashboard buttons only; zero worksheet zones, so it contributes no
  measures/dimensions)
- sheets excluded as hidden/scratch: 5 — `heat_map_school` (standalone
  worksheet, not placed in any dashboard zone — orphaned/scratch, not hidden at
  the window level) plus 4 title-text worksheets with no datasource dependencies
  (`details_title`, `heat_map_title`, `snapshots_title`, `yoy_title` — pure
  caption text, no fields). None of the 5 real dashboards (Details/Heat
  Map/Snapshots/Year in Review/Home) are server-hidden.
- regions served by this dashboard overall: **Newark, Camden, Miami** (no
  Paterson). Evidence: the row-level-security calc `Permissions Group Filter`
  (on every data worksheet) enumerates exactly three `[entity]` values —
  `TEAM Academy Charter School`, `KIPP Cooper Norcross Academy`, `KIPP Miami` —
  and its school-based-staff branch lists only Newark/Camden/Miami school names.
  No Paterson entity or location appears anywhere in the filter or the workbook.
  This tracks the task hint: the dashboard covers the TDT
  (Teacher-Development-Tool) rubric used by TiR/New Lead programs, which are not
  yet run in Paterson.

### Measures

| metric                                     | agg       | source field / formula (trimmed)                                                                                                                                             | dashboards                                   | status       | where                                                                                                                                                      | regions                   |
| ------------------------------------------ | --------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| # Teammates                                | CountD    | `employee_number`                                                                                                                                                            | Heat Map, Year in Review                     | mart-ready   | `fct_staff_observations.teacher_staff_key` (CountD)                                                                                                        | all (Newark/Camden/Miami) |
| # Observations                             | CountD    | `observation_id`                                                                                                                                                             | Heat Map, Year in Review                     | mart-ready   | `fct_staff_observations.staff_observation_key` (CountD / row count)                                                                                        | all                       |
| Evidence                                   | Sum / Avg | `IIF([row_score]=1,1,0)`-sibling calc on the score row: `IIF([row_score]>=2,1,0)`                                                                                            | Heat Map                                     | mart-ready   | `fct_staff_observation_scores.score_value >= 2` (flag, then sum/avg)                                                                                       | all                       |
| % Evidence                                 | Avg       | `{fixed [observation_id]: sum([Evidence])/COUNT([row_score])}` — core rubric-completion rate per observation                                                                 | Heat Map, Snapshots, Details, Year in Review | mart-ready   | `fct_staff_observation_scores.score_value` grouped by `staff_observation_key`, joined to `fct_staff_observations`                                          | all                       |
| % Evidence by Month                        | Avg       | Same as % Evidence but `fixed [observation_id],[strand_name]`                                                                                                                | Details                                      | mart-ready   | `fct_staff_observation_scores.score_value` + `dim_staff_observation_rubric_measurements.strand_name`                                                       | all                       |
| Opportunity                                | Avg       | `IIF([row_score]=1,1,0)` — rate of rows scored exactly 1 (growth-needed)                                                                                                     | Heat Map                                     | mart-ready   | `fct_staff_observation_scores.score_value = 1` (flag, avg)                                                                                                 | all                       |
| Growth Area Count                          | Sum       | `{ FIXED [observation_id] : COUNTD([growth_area]) }`; `growth_area` itself = `max(if(measurement_name like '%Grow%', measurement_dropdown_selection, null))` per observation | Snapshots                                    | mart-missing | `rpt_tableau__teacher_development.sql` (`smg_glows_grows` CTE, lines 2–36) — the Glow/Grow measurement-name classification is not materialized on any mart | all                       |
| Pm1 / Pm2 (variants: PM1, PM2 term rounds) | Avg       | `max(case when term_code='PM1' then observation_score end)` (and PM2)                                                                                                        | Year in Review                               | mart-ready   | `fct_staff_observations.score` filtered/grouped by `dim_terms.term_code` ('PM1'/'PM2') and `staff_observation_type_key`                                    | all                       |
| Smg Etr Pm1 / Pm2 (variants: PM1, PM2)     | Avg       | `avg(row_score)` where `observation_type_abbreviation in ('PM','PMS')` and `measurement_name not like '%S&O%'`, by term                                                      | Year in Review                               | mart-ready   | `fct_staff_observation_scores.score_value` + `dim_staff_observation_rubric_measurements.name` (exclude `%S&O%`) joined via `dim_terms.term_code`           | all                       |

Excluded as internal-only inputs (never independently shelved, only feed the
calcs above): raw `row_score` (basis for Evidence/% Evidence/Opportunity);
`tir_etr_pm1/2/3`, `tir_so_pm1/2/3`, `tir_pm1/2/3` (the .8/.2 blended TiR score
columns exist in `rpt_tableau__teacher_development.sql` but are not referenced
by any Measure Names filter on any of the 4 data dashboards).

### Dimensions

| dimension                                                     | used as                                                                                                   | status        | where                                                                                                                                                                          | regions |
| ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------- |
| Teammate (observed staff name)                                | row/detail                                                                                                | mart-ready    | `dim_staff.full_name` via `fct_staff_observations.teacher_staff_key`                                                                                                           | all     |
| Observer Name                                                 | row/detail, filter                                                                                        | mart-ready    | `dim_staff.full_name` via `fct_staff_observations.observer_staff_key`                                                                                                          | all     |
| Observer Team (TDT / NTNC)                                    | row/detail, filter                                                                                        | mart-ready    | derived `if(department_name='Teacher Development','TDT','NTNC')` off `dim_staff_work_assignments` department, simple case not yet materialized                                 | all     |
| Entity (business unit / region)                               | filter                                                                                                    | mart-ready    | `dim_locations` / `dim_regions` via `fct_staff_observations.location_key`                                                                                                      | all     |
| Location (school)                                             | row/detail, filter                                                                                        | mart-ready    | `dim_locations.location_clean_name` via `location_key`                                                                                                                         | all     |
| Job Title                                                     | filter                                                                                                    | mart-ready    | `dim_work_assignment_jobs` via `dim_staff_work_assignments`                                                                                                                    | all     |
| Measurement Name                                              | row, filter, action source                                                                                | mart-ready    | `dim_staff_observation_rubric_measurements.name`                                                                                                                               | all     |
| Microgoal Month (`strand_name`)                               | row, filter, action source                                                                                | mart-ready    | `dim_staff_observation_rubric_measurements.strand_name`                                                                                                                        | all     |
| TiR/New Lead (`rubric_name`)                                  | filter                                                                                                    | mart-ready    | `dim_staff_observation_rubrics.name`                                                                                                                                           | all     |
| Observed At / Week Start                                      | row, color (month/day/week grains)                                                                        | mart-ready    | `fct_staff_observations.observed_date_key` / `observed_timestamp`; week grain = `date_trunc(..., week(monday))`, not yet a mart column but a 1-line derivation off the date FK | all     |
| Academic Year                                                 | filter, column header                                                                                     | mart-ready    | `fct_staff_observations.academic_year`                                                                                                                                         | all     |
| Employee Number                                               | filter (also feeds # Teammates)                                                                           | mart-ready    | `dim_staff.staff_unique_id` / `teacher_staff_key`                                                                                                                              | all     |
| Row Score (group) — "Met"/"Not Met"                           | shape encoding on Details grid                                                                            | mart-ready    | 1-line bin on `fct_staff_observation_scores.score_value` (2–3→Met, 1→Not Met); not yet materialized                                                                            | all     |
| Glow Area / Glow Notes, Growth Area / Growth Notes            | row/detail text columns                                                                                   | mart-missing  | `rpt_tableau__teacher_development.sql` `smg_glows_grows` CTE — Glow/Grow classification by `measurement_name LIKE '%Glow%'/'%Grow%'` has no mart equivalent                    | all     |
| Observation Subject, Observation Grade                        | (column-dependency only; not seen shelved in the 4 data dashboards beyond Details' implicit detail grain) | mart-missing  | sourced from `int_performance_management__observations.observation_course` / `observation_grade`; not projected on `fct_staff_observations` today                              | all     |
| Glow / Grow (formatted note display: area + "Note: " + notes) | shape/text concat helper                                                                                  | workbook-only | Tableau display calc wrapping Glow Area/Notes and Growth Area/Notes                                                                                                            | n/a     |
| Up to Week                                                    | filter (gates to weeks ≤ today)                                                                           | workbook-only | `iif([week_start]<=TODAY(),[week_start],null)` — display/filter convenience                                                                                                    | n/a     |
| Permissions Group Filter                                      | row-level security filter on every data worksheet                                                         | workbook-only | Tableau user-group RLS calc (see regions note above)                                                                                                                           | n/a     |

### Notes

- This workbook has exactly one datasource and one upstream rpt_ model
  (`rpt_tableau__teacher_development`), so every measure/dimension traces back
  to the same extract; "mart-ready" status reflects that the raw inputs now live
  on `fct_staff_observations` / `fct_staff_observation_scores` /
  `dim_staff_observation_rubric*` marts (shipped after this rpt_ model was
  built), but the specific aggregations (FIXED-per-observation rates, PM-term
  pivots, Glow/Grow-by-measurement-name) aren't materialized as columns or views
  yet — they'd need a new reporting layer (or Cube measures) over the marts.
- No Cube measure or dimension covers anything on this dashboard — confirmed no
  `*observation*` cube exists under `src/cube/model/cubes/`, and the `staff`
  cube family (`staff.yml`, `staff_work_history.yml`, etc.) has no join path to
  an observation fact, so none of these rows can be `cube-covered` without a new
  observations cube.
- "% Evidence" is the dashboard's core KPI (rubric-row completion rate per
  observation) and appears with 4 near-identical FIXED-LOD variants across
  worksheets; grouped into 2 rows above (plain % Evidence, and the by-month
  variant used only in Details).
- "Growth Area Count" is the only measure classified `mart-missing` — it depends
  on text-matching `measurement_name` against `%Glow%`/`%Grow%` to decide which
  dropdown response is "the" glow/grow area for an observation, logic that lives
  only in the rpt_ SQL today.
- Judgment call: `Row Score (group)`, `Observer Team`, and `Week Start` are
  marked `mart-ready` rather than `mart-missing` because each is a single
  `CASE`/`date_trunc` away from an already-materialized mart column, not a
  multi-step derivation like the Glow/Grow classification.
- `Home` dashboard contributes nothing measure/dimension-wise — it's pure
  navigation (title, logo image, buttons to the other 4 dashboards).

### Verification

- mart-ready spot-check: "# Observations" → `fct_staff_observations.yml`
  declares `staff_observation_key` as the surrogate PK
  (`src/dbt/kipptaf/models/marts/facts/properties/fct_staff_observations.yml`,
  generated from `o.observation_id`), so `CountD(observation_id)` in the
  workbook is exactly `COUNT(staff_observation_key)` / `CountD` on that column.
- mart-missing spot-check: "Growth Area Count" → confirmed by reading
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__teacher_development.sql`
  lines 2–36 (`smg_glows_grows` CTE): `growth_area` is
  `max(if(od.measurement_name like '%Grow%', od.measurement_dropdown_selection, null))`
  per `observation_id` — this exact classification does not appear in
  `dim_staff_observation_rubric_measurements.yml` or any other mart properties
  file.
- cube-covered spot-check (negative result, confirmed):
  `find src/cube/model/cubes -iname "*observation*"` returned no files, and
  `src/cube/model/cubes/staff/*.yml` (staff, staff_work_history,
  staff_reporting_relationships, staff_cube_access, staff_manager,
  staff_lead_teacher, staff_homeroom_teacher) expose staff attributes with no
  join to an observation fact — so zero rows in this inventory can be
  `cube-covered` as things stand.

## Leader PM Dashboard (Leadership Development) (`leader_pm_dashboard`)

- workbook: Leadership Development | contentUrl
  `LeadershipDevelopment_17017220456180` | luid
  `8f8b058f-2408-470d-95b0-681d6c8b65f4` | project Production
- upstream datasources: `rpt_tableau__leadership_development (kipptaf_tableau)`
  (embedded) — the ONLY datasource; every worksheet reads it
- rpt_/source models in use: `rpt_tableau__leadership_development` (its own
  upstreams: `rpt_appsheet__leadership_development_roster`,
  `stg_google_appsheet__leadership_development__active_users`,
  `stg_google_appsheet__leadership_development__output`,
  `stg_google_sheets__performance_management__leadership_development_metrics`,
  `int_people__staff_roster`, `int_people__location_crosswalk`)
- published dashboards inventoried: Completion Tracking, Overall Results,
  Competencies, Narrative Questions, Domains (these 5 exactly match the server's
  `get-workbook` views list)
- sheets excluded: 2 legacy dashboards present in the .twb but **absent from the
  server's view list** — `Completion Tracking 23-24`, `Overall Results 23-24`
  (prior-year archived copies, superseded by the current-year dashboards of the
  same name minus suffix; not hidden in the XML, just not published as tabs).
  Also 5 pure-text title worksheets with zero fields (`*_title`) and 2 orphan
  worksheets referenced by no dashboard zone (`9box`,
  `detailed_results_table (2)` — their `repository-location` points at a
  different workbook, `LeadershipDevelopment24-25Preview`/ `-MOYedit`, i.e.
  leftover scratch copies from an edit session).
- regions served by this dashboard overall: **all** (Newark/`TEAM`,
  Camden/`KCNA`, Miami/`MIA`, Paterson, plus KTAF-entity) — the
  `home_business_unit_name` filter is `level-members` with
  `ui-enumeration='all'` (no hard-coded region restriction), and the mart's
  `accepted_values` test lists all 4 regions +
  `KIPP TEAM and Family Schools Inc.`. Row-level security (not a region filter)
  narrows what any one viewer sees.

### ⚠️ ASANA / LIFECYCLE FLAG — read before acting on anything below

1. **No Asana task exists** for this dashboard in the Data Marts + Semantic
   Layer project — coverage gap, confirmed by this inventory (searched by
   dashboard name / workbook luid with no hit given to this agent; flag for
   whoever triages the gap catalog).
2. **The entire source model is disabled and archived.**
   `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__leadership_development.yml`
   carries `config.enabled: false` and this description verbatim: "Archive only,
   disabled 2026-07-30. Leadership Development moved to Lattice. This fed
   Tableau workbook 8f8b058f-2408-470d-95b0-681d6c8b65f4, which is archive only;
   any remaining extract refresh is a Tableau-side schedule, not Dagster." (Refs
   #4627)
3. **Recommendation implied by the above**: this is very likely NOT a candidate
   for new Cube coverage — the system of record moved to Lattice. Every
   "mart-missing" status below should be read as "logic existed here, now
   frozen/archived," not as a build backlog item.

### Measures

| metric                              | agg            | source field / formula (trimmed)                                                                                                  | dashboards                                                        | status       | where                                                                                                | regions |
| ----------------------------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------------ | ---------------------------------------------------------------------------------------------------- | ------- |
| PM score (competency/domain rating) | Avg            | `Column Value (Int)`: `IF REGEXP_MATCH([column_value], '^[0-9]+$') THEN INT([column_value]) ELSE NULL END`                        | Competencies, Domains                                             | mart-missing | `rpt_tableau__leadership_development.column_value` (cast to int; **source model archived/disabled**) | all     |
| Self-completion rate                | Avg (0/1 flag) | `round_completion_self`: BOY needs ≥2 self response rows, MOY/EOY need ≥3 (computed upstream in the rpt_ SQL, not a Tableau calc) | Completion Tracking (`group_completion`, `individual_completion`) | mart-missing | `rpt_tableau__leadership_development.round_completion_self` (archived/disabled)                      | all     |
| Manager-completion rate             | Avg (0/1 flag) | `round_completion_manager`: BOY needs ≥2 self rows, MOY/EOY need ≥10 manager-rating rows                                          | Completion Tracking (`group_completion`, `individual_completion`) | mart-missing | `rpt_tableau__leadership_development.round_completion_manager` (archived/disabled)                   | all     |

Variants collapsed: `round_completion_self` / `round_completion_manager` each
appear twice (once per worksheet, `group_completion` cut-by-group vs
`individual_completion` per-person), identical formula — one row each above.

No tooltip-only numeric measures found. `Overall Results` and
`Narrative Questions` display raw `column_value` as **text**, not an aggregated
measure (role=dimension, derivation=none) — listed under Dimensions instead.

### Dimensions

| dimension                                                            | used as                                                           | status                                                                                                                                               | where                                                                                                                                                   | regions |
| -------------------------------------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------- |
| Teammate (`preferred_name_lastfirst`)                                | row header, all 5 dashboards                                      | cube-covered                                                                                                                                         | `src/cube/model/views/staff/staff_directory.yml` → `full_name` (via `staff_work_history.staff`)                                                         | all     |
| Manager (`manager`)                                                  | row header (Completion Tracking, Competencies, Domains)           | cube-covered                                                                                                                                         | `staff_directory.yml` → `staff_manager_full_name` (via `staff_work_history.staff_manager`)                                                              | all     |
| Location (`location_clean_name`)                                     | filter + `Cut By` dimension option                                | cube-covered                                                                                                                                         | `staff_directory.yml` → `locations_location_name` (via `staff_work_history.locations`)                                                                  | all     |
| Business Unit / Entity (`home_business_unit_name`)                   | filter + `Cut By` dimension option                                | cube-covered                                                                                                                                         | `staff_directory.yml` → `business_unit_name`, defined in `src/cube/model/cubes/staff/staff_work_history.yml:119`                                        | all     |
| Department (`home_department_name`)                                  | filter + `Cut By` dimension option                                | cube-covered (approximate — verify `department_name` grain matches `home_department_name`)                                                           | `staff_directory.yml` → `department_name`                                                                                                               | all     |
| Job Title (`job_title`)                                              | filter + `Cut By` dimension option                                | cube-covered (approximate — PM field is free-text `job_title`, cube exposes `position_title`/`job_code`; same meaning, unverified exact grain match) | `staff_directory.yml` → `position_title` (`staff_work_history.yml:87`)                                                                                  | all     |
| Academic Year (`academic_year`)                                      | filter                                                            | cube-covered (approximate — PM cycle year vs. employment-record year; verify semantics before reuse)                                                 | `staff_directory.yml` → `staff_work_history.dates.academic_year`                                                                                        | all     |
| Term (BOY/MOY/EOY)                                                   | row/col header, all 5 dashboards                                  | mart-missing                                                                                                                                         | `rpt_tableau__leadership_development.term` (archived/disabled)                                                                                          | all     |
| Type (Competencies / Domains / Narrative Questions / Goals)          | filter (`Type (group)`), gates which rows show on which dashboard | mart-missing                                                                                                                                         | `rpt_tableau__leadership_development.type` (joined from `stg_google_sheets__performance_management__leadership_development_metrics`; archived/disabled) | all     |
| Description (competency/domain/goal label)                           | col header / text                                                 | mart-missing                                                                                                                                         | `rpt_tableau__leadership_development.description` (archived/disabled)                                                                                   | all     |
| Column Name (pivot key, e.g. `rating_moy`, `manager_notes_eoy`)      | filter (mostly ETL/pivot plumbing, not a reporting field)         | mart-missing, workbook-only in practice                                                                                                              | `rpt_tableau__leadership_development.column_name` (archived/disabled)                                                                                   | all     |
| Assignment Status / Active                                           | filter                                                            | mart-missing                                                                                                                                         | `rpt_tableau__leadership_development.assignment_status` / `.active` (archived/disabled)                                                                 | all     |
| PM response text (raw `column_value`, un-aggregated)                 | text display (Overall Results, Narrative Questions)               | mart-missing                                                                                                                                         | `rpt_tableau__leadership_development.column_value` (archived/disabled)                                                                                  | all     |
| Cut By (parameter: Location/Entity/Department/Job Title/All)         | parameter-driven row axis                                         | workbook-only                                                                                                                                        | Tableau parameter + calc switching between the cube-covered dims above                                                                                  | all     |
| Display Name (`name - dept - location` concat)                       | row label                                                         | workbook-only                                                                                                                                        | concat of `preferred_name_lastfirst` + `home_department_name` + `location_clean_name`                                                                   | all     |
| Notes (tooltip, `column_value` where `column_name` contains "notes") | tooltip-only                                                      | workbook-only                                                                                                                                        | derived from `column_name`/`column_value` (archived/disabled underlying fields)                                                                         | all     |

### Notes

- **Judgment call**: statuses above treat "cube-covered" generously for staff
  attributes (location/department/business unit/job title/manager/academic year)
  because `staff_directory` genuinely exposes the same real-world concept, even
  though no PM-specific cube exists and field names don't match 1:1. Flagged
  three as "approximate" where grain/semantics weren't verified against actual
  query results (no row-level querying was done per the no-PII rule).
- **Excluded from the tables above**: 5 row-level-security gating calculations
  present on every worksheet (`RLS - Subject Is Senior Leader`,
  `RLS - Entity Gate`, `RLS - Location Gate`, `RLS - Role Gate`,
  `Permissions`/`User_test`) — these are access-control predicates, not
  reporting dimensions, so they're omitted as pure infrastructure rather than
  padding the table.
- **Excluded as formatting/layout helpers**: the 5 `*_title` worksheets (zero
  fields — pure text captions) and the `Parameter 1` control itself (the literal
  parameter object; its effect is captured as the "Cut By" row).
- The 2 non-published legacy dashboards (`Completion Tracking 23-24`,
  `Overall Results 23-24`) were inventoried for completeness but excluded from
  all counts below — they're prior-year frozen copies no longer served.
- Biggest uncertainty isn't classification — it's **whether this dashboard
  should be in the Cube Connector Gap Catalog at all**, given it's archive-only
  and the real system of record (Lattice) is outside this codebase entirely.
  Recommend the catalog owner confirm with whoever filed #4627 before treating
  any row here as backlog.

### Verification

- **cube-covered spot check**: `Business Unit / Entity` row →
  `src/cube/model/views/staff/staff_directory.yml` includes `business_unit_name`
  from `staff_work_history` (join_path `staff_work_history`), and the measure
  itself is defined at `src/cube/model/cubes/staff/staff_work_history.yml:119`
  (`sql: business_unit_name`).
- **mart-ready spot check**: **none found.** Every PM-domain-specific
  measure/dimension lives only on the disabled
  `rpt_tableau__leadership_development` extract (not in `models/marts/`), and
  every staff-attribute dimension is already cube-covered via `staff_directory`
  — so no row in this inventory lands in the middle "mart has it, cube doesn't"
  tier. Noting the gap explicitly rather than forcing a row into this status.
- **mart-missing spot check**: `PM score` row → source logic lives in
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__leadership_development.sql`
  (the `pivot` CTE unnesting `rating_moy`/`rating_eoy`/etc. from
  `stg_google_appsheet__leadership_development__output`), confirmed disabled via
  `config.enabled: false` in
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__leadership_development.yml`.
