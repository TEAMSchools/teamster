# Focus discipline in the network behavior marts — design

Refs #5118. Written 2026-11-04. Supersedes the "Proposed approach" in the #5118
body where they differ; the differences are listed under _What changed since
#5118_.

## Why

Miami moved discipline from DeansList to Focus at the start of the 2026 school
year (SY2026-27). No dbt model reads Focus discipline, so Miami drops out of
every network behavior number from 2026 forward. As of 2026-11-04 Focus holds
2,609 Miami referrals and 408 consequence records, including 39 out-of-school
and 4 in-school suspensions.

`fct_behavioral_incidents` and `fct_behavioral_consequences` already exist to be
the shared behavior model, but they read DeansList only, and no dashboard,
sheet, or Cube cube reads them yet. Every behavior report reads DeansList
intermediates directly. This project makes the two marts cover all four regions
and is the foundation for a later move: repointing those reports to read the
marts (filed as follow-ons, below).

There is no deadline. The work ships over a few weeks in three PRs.

## Who builds what

An engineer builds PRs 1 to 3 below: ingestion, the `focus` package models, the
kipptaf domain models, and the two facts. The engineer's work stops at the
marts. Reporting views (`rpt_*`), dashboards, sheets, and Cube are the
follow-ons at the end of this document, built separately once the marts are
live. The one exception is a column rename in
`rpt_branchingminds__behavior_incident` that keeps it compiling (PR 3).

Two decisions are still open (see _Open decisions_). Neither blocks PR 1 or
PR 2.

## Goals

- Both facts carry Miami Focus rows from SY2026-27 on, beside unchanged
  DeansList rows for Newark, Camden, Paterson, and Miami's history.
- Focus referrals land in the tier vocabulary NJ reports already use: `Low`,
  `Middle`, `High`, `Social Work`, `Non-Behavioral`.
- Focus suspensions are typed from Focus's own action configuration, so a bus
  suspension never counts as a school suspension.
- The mart columns describe behavior, not DeansList, so follow-on reports can
  move onto them without caring which system a row came from.

## Non-goals

- A network-wide behavior taxonomy shared across systems (option B in the
  conversation). Filed as a follow-on.
- Any change to a reporting view (`rpt_*`), dashboard, sheet, or Cube model,
  except the BranchingMinds compile fix in PR 3. Follow-ons.
- Days actually served (from Focus attendance). The marts report days assigned,
  as they do for DeansList today. Follow-on.
- Florida's state incident layer (`discipline_incidents`, SESIR fields). It
  still holds 2 test-looking rows. Follow-on.
- Changing NJ's DeansList logic, including the penalty-name CASE that types
  DeansList suspensions. #5118 proposed replacing it with a sheet; under the
  chosen taxonomy option NJ stays as it is.
- The DeansList behavior points log (`stg_deanslist__behavior`) and comm log.

## Anti-goals

These would make the project a failure even if it builds:

- NJ counts change. Row counts per region and year must match prod before the
  change; the only intended value change is the Miami archive tier fix below.
- A bus suspension, or any action Focus does not type as ISS/OSS, counts as a
  suspension.
- A Focus referral silently disappears from tier counts because its code is not
  mapped. Unmapped codes must stay visible.
- Free-text staff narrative (reason for referral, admin comments, action notes,
  "administered by") reaches kipptaf or the marts.

## Constraints

- Repo layering (`.claude/rules/dbt-architecture.md`): single-source decoding
  lives in the `focus` package; cross-region logic lives in kipptaf; marts read
  domain `int_` models only.
- kipptaf CI reads district models from the shared `zz_stg_*` copies. A new
  package model reaches kipptaf CI only after it builds in prod and is cloned to
  staging (see _Rollout steps outside the PRs_).
- Mart rules (`.claude/rules/dbt-marts.md`, `models/marts/CLAUDE.md`):
  source-agnostic column names, strict-chain FKs, `error`-only tests on marts,
  FK edges declared under `config.meta.foreign_key`.
- PII handling per `.claude/rules/ferpa-pii.md`.

## Approaches

### Taxonomy

- **A. Map Focus into the existing NJ tier vocabulary (chosen).** A small Google
  Sheet maps each Focus discipline code to `Low` / `Middle` / `High` /
  `Social Work` / `Non-Behavioral`. NJ is untouched. Behavior categories stay as
  each system labels them. Smaller and sooner; cannot compare a category such as
  fighting across regions.
- **B. Full network taxonomy, as #5118 proposed.** A network category and tier
  for every code in every region, with over 200 DeansList category rows in a
  culture-team sheet. Enables cross-region category comparison, but changes NJ
  labels and needs culture-team review before launch. Deferred to a follow-on.

### Delivery

- **1. Focus package first, then kipptaf, in 3 PRs (chosen).** Follows the
  layering rules and keeps CI simple; waits for a prod build between PRs, which
  the timeline allows.
- **2. Same models, one PR.** One review, but needs the new package models
  seeded into shared staging before CI passes, and the teacher-code load must
  still run in prod first.
- **3. Everything in kipptaf.** Simplest CI, but puts Focus decoding outside the
  `focus` package and leaves kippmiami without a decoded referral model.
  Rejected.

## What changed since #5118

1. **No year split.** `int_students__sis_cutover` was deleted (#5397), and
   Miami's DeansList tables are a frozen archive ending 2026-06-03 (#5580). The
   union takes every DeansList row and every Focus row; the two never overlap.
2. **The two Focus code fields do different jobs.** 88% of referrals carry one
   of two tier codes in `discipline_code` (112 "Tier 1 - Corrective Tile", 111
   "Tier 2 - Admin Support"), and 97% of those also carry a `teacher_code`
   naming the behavior. So tier comes from `discipline_code` and category from
   `teacher_code`. #5118's "which field wins" question goes away.
3. **`referral_teacher_codes` is now on the critical path.** Category labels
   need it. The ingestion change exists on the unmerged branch
   `claude-focus-referral-teacher-codes` (2 commits).
4. **Days assigned.** The mart's `days_assigned` holds DeansList's assigned
   days; Focus "Length of Action" is also assigned days. Lengths vary (39 OSS
   records, 170 days), so the earlier "always 10 days" worry no longer applies.
5. **Miami's archive tiers are still wrong.** DeansList tier logic moved into
   the package (#5586), but Miami's frozen tables kept the old mapping: Miami T2
   (physical attack, weapon, assault) reads `Middle`. Fixed in kipptaf.
6. **Nothing reads the marts yet.** #5118 said every report reads them; none
   does. Column and key changes are cheap now and will not be later.
7. **Extend, don't add.** #5118 proposed a new
   `int_students__behavior_incidents`; `int_students__behavioral_incidents`
   already exists at that grain. It becomes the combined model.

## Design

### Data flow

```text
Focus (dlt) ─► focus package (kippmiami)                  kipptaf
  discipline_referrals ─┐
  referral_codes        ├─► int_focus__discipline_referrals ─► passthrough ─┐
  referral_teacher_codes┘                                                   │
  custom_field_log_entries ─► int_focus__discipline_referral_actions ─► passthrough ─┐
  referral_actions ─────────┘                                                   │    │
                                                                                ▼    ▼
DeansList (4 regions, Miami frozen) ─► int_deanslist__incidents ─► int_students__behavioral_incidents ─► fct_behavioral_incidents
                                       int_deanslist__incidents__penalties ─► int_students__behavioral_consequences ─► fct_behavioral_consequences
Google Sheet: Focus discipline code ─► referral tier ─┘
```

### PR 1 — load `referral_teacher_codes` (Dagster)

- Cherry-pick the 2 commits from
  `origin/anthonygwalters/feat/claude-focus-referral-teacher-codes`
  (`8e2e8b6753` adds the table to the kippmiami Focus dlt config; `8369d5d884`
  repoints the stale `#4865` note in `stg_focus__discipline_referrals.yml` to
  #5118). This design doc merges on its own PR first.
- After merge, materialize the new asset in prod once so the table exists for
  PR 2.

### PR 2 — `focus` package models (build in kippmiami)

**`stg_focus__referral_teacher_codes`** — one row per teacher code: id, title,
and whatever ordering/active columns the table carries. Source declared in the
package's BigQuery source file. Unique key test at `error`.

**`int_focus__discipline_referrals`** — one row per referral. Reads
`stg_focus__discipline_referrals` and decodes:

- `discipline_code` → `referral_codes` title (join on `id`; `code` is not
  unique).
- `teacher_code` → teacher-code title.
- `context` → option label (custom field decode, scoped by `source_class`).
- the network student number, via the same Focus student mapping
  `int_focus__student_enrollment_roster` uses (`network_student_number`).
- the Focus school number (`int_focus__schools.school_number`), so kipptaf can
  reach `location_key`.

It carries `entry_date`, `creation_date`, `syear`, `staff_id`, and the
`dismissed` / `processed` flags. `entry_date` is the incident date: staff
backdate it (it precedes `creation_date` on 149 rows, by up to 14 days, and
never follows it), while `referral_date` is never populated and `refer_date`
almost never. It carries none of the free-text columns. The model is tagged
`contains_pii: true` (student-level discipline).

Every non-deleted referral counts, including dismissed ones, which show through
`status`. `merged_referral_id`, `incomplete`, and `returned` are unused today (0
merged, the other two always null). A `warn` test on the model flags any row
where `merged_referral_id` is set or `incomplete = 'Y'`, so a change in Focus
usage surfaces before it double-counts or counts drafts.

**`int_focus__discipline_referral_actions`** — one row per action record. Reads
`stg_focus__custom_field_log_entries` directly, filtered to
`source_class = 'SISDisciplineReferral'` and the "Action Record(s)" field (id
763), where `source_id` is the referral id. Do not reuse
`int_focus__custom_field_log__unpivot`: it is built for student logs and names
`source_id` `student_id`. Slot mapping, from `custom_field_log_columns`:

| Slot         | Meaning             | Output                               |
| ------------ | ------------------- | ------------------------------------ |
| `log_field1` | Resultant Action    | `referral_actions.id` → title, flags |
| `log_field2` | Date Decided        | `decided_date`                       |
| `log_field3` | Date Begins         | `start_date`                         |
| `log_field4` | Date Ends           | `end_date`                           |
| `log_field5` | Length of Action    | `days_assigned`                      |
| `log_field7` | Administered by     | **not projected** (staff free text)  |
| `log_field8` | Action Record Notes | **not projected** (free text)        |

Typing from `referral_actions`, never from the action title:

| Rule                           | `suspension_type` | `is_suspension` | `is_reportable` |
| ------------------------------ | ----------------- | --------------- | --------------- |
| `type = 'OSS'`                 | `OSS`             | true            | true            |
| `type = 'ISS'`                 | `ISS`             | true            | true            |
| other `state_code` not `D`     | null              | false           | true            |
| `state_code = 'D'`             | null              | false           | false           |
| action id null (orphan record) | null              | false           | false           |

`Bus - Suspension (BB2)` is `state_code = 'D'`, so it lands in the fourth row.

The field id and slot numbers are business-rule literals: comment them (S20) and
add a singular test that the slot titles for field 763 still read as above. It
lands at `warn` and flips to `error` once it passes in prod.

Tests on both int models: unique key at `error`.

### PR 3 — kipptaf

**Sources and passthroughs.** Add the two package models to
`models/focus/sources-kippmiami.yml` (region schema pattern) and add
`int_focus__discipline_referrals` / `int_focus__discipline_referral_actions`
passthroughs in `models/focus/intermediate/`, matching `int_focus__ada.sql`.
Re-declare `contains_pii: true` on each passthrough.

**Tier sheet.** A new Google Sheet tab read by
`stg_google_sheets__focus__discipline_code_crosswalk`, following
`stg_google_sheets__focus__language_code_crosswalk`:

| Column                  | Notes                                                    |
| ----------------------- | -------------------------------------------------------- |
| `discipline_code_id`    | string key (Focus `referral_codes.id`)                   |
| `discipline_code_title` | for the editor; not a key                                |
| `referral_category`     | `Low`, `Middle`, `High`, `Social Work`, `Non-Behavioral` |
| `notes`                 | free text for the editor                                 |

Seed it from the 62 live `referral_codes`, with counts, pre-filled by rule: 112
→ `Low`, 111 → `Middle`, `sesir = 1` codes → `High`, "School Counselor Referral"
codes → `Social Work`, "Incident Report/Accident Report" → `Non-Behavioral`,
remaining local codes by title. Who reviews the pre-fill, and whether PR 3 waits
for that review, is _Open decision 2_. Put the tab in a new spreadsheet of its
own, not in the existing Focus crosswalk spreadsheet: every tab in a shared
spreadsheet refreshes when any one of them changes. Staging tests at `error`:
`unique` and `not_null` on `discipline_code_id`; `not_null` and
`accepted_values` on `referral_category`.

**`int_students__behavioral_incidents`** — rebuilt as the combined model, one
row per student incident, two branches with the same enumerated columns (S17):

| Column                      | DeansList branch                                                      | Focus branch                                                                                                                                                                                                        |
| --------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `source_system`             | `'deanslist'`                                                         | `'focus'`                                                                                                                                                                                                           |
| `incident_id`               | `incident_id`                                                         | `referral_id`                                                                                                                                                                                                       |
| `_dbt_source_project`       | as today                                                              | `'kippmiami'` (from the passthrough)                                                                                                                                                                                |
| `student_number`            | `student_school_id`                                                   | network student number                                                                                                                                                                                              |
| `location_key`              | via `deanslist_school_id` (as today)                                  | via `focus_school_id` on the locations sheet                                                                                                                                                                        |
| `referring_employee_number` | DeansList user email → roster (as today, moved here from the fact)    | Focus `staff_id` → `int_focus__users` → roster, by `ein`, then `staff_number_identifier_local`, then `e_mail_address` against `google_email` (the #5118 path; `int_students__course_sections` shows the join shape) |
| `incident_date`             | `issue_ts_date`                                                       | `entry_date`                                                                                                                                                                                                        |
| `creation_date`             | `create_ts_date`                                                      | `creation_date`                                                                                                                                                                                                     |
| `academic_year`             | `create_ts_academic_year`                                             | `syear`                                                                                                                                                                                                             |
| `category`                  | `category`                                                            | teacher-code title; else the discipline-code title when it is not 111/112                                                                                                                                           |
| `infraction_description`    | `infraction`                                                          | discipline-code title                                                                                                                                                                                               |
| `context`                   | `context`                                                             | decoded context label                                                                                                                                                                                               |
| `status`                    | `status`                                                              | `Dismissed`, `Processed`, or `Open`                                                                                                                                                                                 |
| `referral_category`         | package `referral_tier`, with the Miami fix                           | sheet value; `Unmapped` when no row                                                                                                                                                                                 |
| `is_behavioral_referral`    | not `Social Work` / `Non-Behavioral`                                  | same rule (so `Unmapped` counts)                                                                                                                                                                                    |
| `is_referral`               | as today                                                              | true                                                                                                                                                                                                                |
| `is_active`                 | as today (always true: DeansList staging keeps only active incidents) | true (Focus deletes never reach staging)                                                                                                                                                                            |
| `close_date`                | `close_ts_date`                                                       | null                                                                                                                                                                                                                |
| `return_date`               | `return_date_date`                                                    | null                                                                                                                                                                                                                |
| `location`                  | as today (BranchingMinds reads it)                                    | null                                                                                                                                                                                                                |

The Miami archive relabel: in the DeansList branch, rows with
`_dbt_source_project = 'kippmiami'` get a corrected `referral_category` from
their DeansList category tier. The mapping is _Open decision 1_; the proposed
default is `T2` → `High` and `T4` → `Middle`, with `T1` and `T3` unchanged. It
is a small commented `case` on `_dbt_source_project` and the tier; the archive
never changes, so it does not belong in the sheet.

The model stops being a `select i.*` passthrough. Its other consumer,
`rpt_branchingminds__behavior_incident`, reads `issue_ts_date`, which this model
renames to `incident_date`. Change that one column reference in the extract and
nothing else. Its NJ filter keeps Focus rows out, and its output must not
change. This is the only reporting-view edit in the project.

Tests: unique on (`source_system`, `incident_id`, `_dbt_source_project`) at
`error`; `referral_category <> 'Unmapped'` at `warn`, with a description saying
to add the code to the sheet. Unit tests on the Focus branch: tier from sheet,
`Unmapped` fallback, category fallback order, and the Miami archive relabel.

**`int_students__behavioral_consequences`** (new) — one row per consequence, two
branches: DeansList from `int_deanslist__incidents__penalties` (keeps its
penalty-name CASE and API flags; rows with a null `incident_penalty_id` dropped,
as the fact does today), Focus from the action passthrough. Columns:
`source_system`, `incident_id`, `consequence_id` (`incident_penalty_id` /
action-record id), `_dbt_source_project`, `type` (penalty name / action title),
`suspension_type`, `start_date`, `end_date`, `days_assigned`, `periods_assigned`
(null for Focus), `is_suspension`, `is_reportable`, and the incident's
`student_number` and `academic_year` for the enrollment join. Unique key test at
`error`. Unit test: OSS, ISS, a bus suspension, and an orphan action record.

**Facts.** Both facts read the combined models and keep their grain.

- Keys: `behavioral_incident_key` hashes (`source_system`, `incident_id`,
  `_dbt_source_project`); `behavioral_consequence_key` adds `consequence_id`.
  This changes every existing hash, which is acceptable because no consumer
  reads them, and follows the branch-namespacing rule in
  `.claude/rules/dbt-sql.md`.
- `fct_behavioral_incidents` gains `incident_date_key` (FK to `dim_dates`) and
  `is_behavioral_referral`. It drops `category_tier`, a DeansList-only code that
  `referral_category` now covers, and `is_active`, which is true on every row.
  The staff join moves upstream (above); the fact reads
  `referring_employee_number` and hashes `referring_staff_key` as today. The
  fact's staff-email `dbt_utils.deduplicate` cannot move into a domain `int_`
  unchanged (rule A5): reuse an existing one-row-per-email roster lookup, or
  declare a `standard_exempt` with the reason.
- Both facts then read domain models only, which fixes their two A1 rows in
  `src/dbt/kipptaf/standard-baseline.tsv` (#5809); delete those rows.
- `fct_behavioral_consequences` keeps its columns.
- The `student_enrollment_key` pick (latest stint in the academic year) is
  unchanged and applies to both branches.
- Descriptions lose "from DeansList"; source column pointers go in
  `config.meta.source_column`.
- Regenerate `docs/reference/marts-data-models.md` with
  `scripts/generate_marts_reference.py`.

### Rollout steps outside the PRs

- After PR 1 merges: materialize the `referral_teacher_codes` asset in prod.
- After PR 2 merges and kippmiami builds: clone the 2 new package models into
  `zz_stg_kippmiami_focus` so kipptaf CI can read them (shared staging write).
- Before PR 3's CI: stage the new sheet external with `--target staging` (shared
  staging write).
- Create the Google Sheet, its tab, and its named range, and share it with the
  reviewer from _Open decision 2_.

## Open decisions

The project owner decides both before PR 3 merges. PR 1 and PR 2 can proceed
without them.

### 1. Miami archive tiers

Miami's DeansList archive tiers do not line up with NJ's. Today the archive
reads:

| Miami tier | What it holds                                                      | Rows  | Archive today | Proposed |
| ---------- | ------------------------------------------------------------------ | ----- | ------------- | -------- |
| `T1`       | sexual battery only                                                | 3     | `High`        | `High`   |
| `T2`       | mostly physical attack, assault or threat, weapons, sexual assault | 154   | `Middle`      | `High`   |
| `T3`       | the everyday bucket                                                | 3,724 | `Low`         | `Low`    |
| `T4`       | phones, bullying, harassment, uniform, vaping                      | 414   | `Low`         | `Middle` |

The proposed column follows where NJ already puts the same behaviors: assaults,
weapons, and fights at `High`; phones and vape possession at `Middle`. A
tier-level mapping cannot fix one gap: Miami `T3` holds some behaviors NJ calls
`High`, such as fighting. That needs a mapping per category, which is the
network taxonomy follow-on. The choices are the proposed column, `T2` only, or
no relabel.

### 2. Tier sheet reviewer

The sheet maps 62 Focus discipline codes to a tier. The 2 tier codes (111, 112)
cover 88% of referrals and map by rule. The judgment calls are the remaining
codes, which cover about 12%. The `Unmapped` warn test catches a code missing
from the sheet, not a code given the wrong tier. Open: who in Miami reviews the
pre-fill, and whether PR 3 waits for that sign-off. Proposed: PR 3 waits.

## Acceptance criteria

- Both facts return Miami Focus rows for academic year 2026. Focus referrals
  missing from the incident fact are only those with no enrollment match, and
  that count is reported in the PR.
- For Newark, Camden, Paterson, and Miami before 2026, row counts per region and
  year match prod before the change. Column values match except key hashes and
  the Miami archive relabel.
- Miami 2026 OSS and ISS counts in the consequence fact equal the
  `referral_actions`-typed counts in Focus staging. No bus suspension has
  `is_suspension = true`.
- FK population on Focus rows: `location_key`, `student_enrollment_key`, and
  `referring_staff_key` each checked per `models/marts/CLAUDE.md`; anything
  under 99% populated is explained in the PR.
- No free-text column reaches kipptaf.
- Expected, not a defect: until the follow-ons repoint them, the existing
  reports keep the old Miami archive tiers, so they and the marts disagree on
  Miami tiers before 2026.
- `rpt_branchingminds__behavior_incident` output is unchanged.
- An unmapped Focus discipline code shows as `Unmapped` and trips the warn test.

## Follow-ons to file

This is the reporting-view work, outside the engineer's scope. The project owner
files these after this design is approved, on project board #4 with Tier, PR
batch, and Driver set. Each repointing issue moves its reports onto the marts.

1. Suspensions Google Sheets: `rpt_gsheets__suspensions`,
   `rpt_gsheets__historical_suspensions`, `rpt_gsheets__school_metrics_extract`.
2. OKRTS dashboard: `rpt_tableau__okrts_referrals`,
   `rpt_tableau__suspension_over_time`, `rpt_tableau__home_instruction`,
   `rpt_tableau__home_instruction_queue`.
3. `rpt_tableau__consequence_dashboard` and
   `rpt_tableau__school_culture_dashboard_nj`.
4. `rpt_tableau__hs_early_warning_dashboard` (Miami's HS rows are dark today).
5. Topline and MTSS: `int_topline__suspension_weekly`,
   `int_deanslist__referral_suspension_rollup` and its consumers.
6. BranchingMinds: `rpt_branchingminds__behavior_incident` onto the mart, and
   `rpt_branchingminds__behavior_incident_detail`.
7. Cube behavior cubes over the two facts (gap catalog, #5673).
8. Network behavior taxonomy (option B).
9. Days served from Focus attendance.
10. Florida state incident (SESIR) layer.

## Decided in conversation

- Extend the existing two facts; no new marts.
- Taxonomy option A.
- Delivery approach 1, three PRs, no deadline.
- Anchor on #5118; the spec PR and PRs 1 and 2 say `Refs #5118`, PR 3 closes it.
- An engineer builds PRs 1 to 3, through the marts. Reporting views are out of
  scope.
- Follow-ons cover the dashboards and the reports that read DeansList models
  directly, not the outbound files sent to DeansList.

## Calls made in this design (check these)

- Tier comes from `discipline_code`, category from `teacher_code`.
- Days assigned only; days served deferred.
- The Miami archive relabel lives in SQL, not sheet rows; its mapping is open.
- The BranchingMinds column rename is the one reporting-view edit, because the
  build breaks without it.
- The tier sheet gets its own spreadsheet.
- No effective dating on the sheet; Focus adds a new code id when a code's
  meaning changes.
- `Unmapped` counts as a behavioral referral.
- Focus `status` derived from the dismissed / processed flags; dismissed
  referrals stay in the counts, as non-deleted DeansList incidents do.
- Merged and draft referrals: no filter today (none exist); a `warn` test
  watches for them.
- Drop `category_tier` and `is_active` from the incident fact; add
  `incident_date_key` and `is_behavioral_referral`.
- Namespace both key branches with `source_system`, accepting hash churn.
- The staff resolution moves from the fact into the combined incident model.

## Left to the builder

- The `referral_teacher_codes` column set, once loaded.
- How to decode `context` (existing custom-field decode machinery or a direct
  option join).
- Exact column names inside the package models, within repo conventions.
- Whether `decided_date` is worth carrying past the package model.
- Unit-test fixtures and the test-only checks in each PR.
