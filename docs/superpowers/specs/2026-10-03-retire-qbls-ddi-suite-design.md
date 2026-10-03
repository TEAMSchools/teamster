# Retire QBLs and Power Standards from the DDI Suite — Design

Refs [#5656](https://github.com/TEAMSchools/teamster/issues/5656).

## Context

QBLs and Power Standards are a retired assessment program. They are not coming
back (confirmed 2026-09-30). The models built only for them, `rpt_tableau__qbl`
and `rpt_tableau__power_standards`, are already disabled, and so is
`rpt_tableau__ddi_audit`, which also read the QBL lookup.

Three things are still live:

- `rpt_tableau__ddi_dashboard` left-joins
  `stg_google_sheets__assessments__qbls_power_standards` and outputs `qbl` and
  `is_qbl`.
- `rpt_tableau__assessment_dashboard` outputs the placeholders
  `null as power_standard_goal` and `null as is_power_standard`.
- The staging model and its source,
  `src_google_sheets__assessments__qbls_power_standards`, still build. The
  source is a named range in the shared `Assessments` spreadsheet. Because it is
  an enabled Sheets source, Dagster still carries the asset
  `kipptaf/google/sheets/assessments/qbls_power_standards`.

The data is empty. In prod `rpt_tableau__ddi_dashboard`, academic years 2025 and
2026 (about 2.4M rows) have zero rows where `is_qbl` is true and zero non-null
`qbl` values.

The DDI Suite workbook still references all four columns. It is the production
Tableau workbook `6d82b643-59a8-4106-b2f9-97ddf7f638e7` with 8 live views, and
the `ddi_suite` exposure reads both models. It was inspected at the 2026-10-02
22:33 UTC revision, and 5 of its 8 live views touch QBL fields:

- **Parameters with a `QBLs` choice:** `Standard or QBL` (`[Parameter 9]`, a
  dropdown on O3 View and DKI View), `Mastery Type` (`[Parameter 3 1]`, on
  Mastery Over Time [Region] and [School]), and
  `Mastery Type - Parameter - Classroom` (on Mastery Over Time [Classroom]).
  None of them defaults to `QBLs`, and choosing it today shows an empty view.
- **Core calculations with a QBL branch:** `Is Mastery Int - Custom`,
  `Is Mastery Int - Custom - Classroom`, and `View by - O3 Standards`. Most
  Mastery Over Time, O3 and DKI worksheets depend on them.
- **QBL-only objects:** the calculation `QBL`, the worksheets
  `Region - QBL Mastery`, `School - QBL Mastery`, `Classroom - QBL Mastery` and
  `Classroom - QBL`, two hidden `QBLs` layout containers, three QBL filter
  cards, the action groups `Action (Qbl)` and
  `Action (Performance Bands - 3 Level,Qbl)`, the drill path
  `QBL, Response Type Code`, and the "all" `qbl` filters on seven title and
  roster sheets.
- **Visible QBL elements:** Show QBLs / Hide QBLs buttons in the header row of
  all three Mastery Over Time dashboards, the instruction "Use the dropdown to
  change between Standard and QBL mastery" on O3 and DKI, and the Landing Page
  copy "assessment, standard, and QBL mastery".
- **Power Standards:** the calculations `Power Standard Goal (%)` and
  `Power Standards - Diff from Goal` on the `assessment_dashboard` datasource.
  No worksheet uses either one.

If dbt drops a column while the workbook's embedded extracts still list it, the
extract refresh or the calculations that use it can fail. This design has not
verified which. That risk sets the order of the steps below.

## Goals

1. Nothing in dbt or Dagster reads the QBL lookup sheet.
2. The four retired columns are gone from both `rpt_` models.
3. The DDI Suite shows no QBL or Power Standards option, text, or object, and
   every remaining view works as it does today.
4. No step can break the production workbook. Each step is safe on its own and
   can be rolled back on its own.

## Non-goals

- Editing the `Assessments` spreadsheet or its named ranges. Four live lookups
  share that spreadsheet.
- Dropping BigQuery relations. Retired models and sources are disabled, never
  deleted (`.claude/rules/dbt-models.md`).
- The disabled models `rpt_tableau__ddi_audit`, `rpt_tableau__qbl` and
  `rpt_tableau__power_standards` stay as they are.
- Any other DDI Suite change.

## Design: three steps, in order

Each step has a different owner and reviewer, and each is gated on the one
before it.

### Step 1 — dbt PR 1: placeholder columns (owner reviews and merges)

Prod output does not change in this step. Only `rpt_tableau__ddi_dashboard`
changes.

`rpt_tableau__ddi_dashboard.sql`:

- Remove the
  `left join ... stg_google_sheets__assessments__qbls_power_standards as qbls`
  from the two union branches that have it. The ES/MS branch matches on
  `grade_level` and `qbls.qbl is not null`; the HS branch matches on neither.
- In those two branches, replace `qbls.qbl` with `cast(null as string) as qbl`,
  and replace `if(qbls.qbl is not null, true, false) as is_qbl` with
  `false as is_qbl`.
- In the third branch, replace `null as qbl` and `null as is_qbl` with the same
  typed placeholders, so all three branches agree.

`properties/rpt_tableau__ddi_dashboard.yml`: rewrite the `qbl` and `is_qbl`
descriptions to say the program is retired and the columns are constant
placeholders. Contract types and tests are unchanged.

The column names, order and types are the same as in prod, so the workbook sees
no change.

**Verification:**

- Build the model in dev with `--defer` against prod.
- By `academic_year`, dev and prod must match on `count(*)`, `countif(is_qbl)`
  and `count(qbl)`.
- `INFORMATION_SCHEMA.COLUMNS` for dev and prod must list the same names and
  types.
- dbt Cloud CI passes.

**Rollback:** revert the PR.

**Coordination:** PR #3576 edits the same SQL and YAML. Whichever PR merges
second resolves a small textual conflict.

### Step 2 — DDI Suite workbook cleanup (XML edit, owner opens in Desktop)

Follow the `tableau-workbook-xml` skill loop. This step changes no repo code.
The edited `.twbx` is the deliverable.

**Base:** download the production workbook fresh with `include_extract=True` and
record `updated_at`. Diff its worksheet and parameter lists against the
2026-10-02 inventory above, and reconcile any drift before editing.

**Edits:**

1. **Parameters**
   - Remove the `"QBLs"` member from `Mastery Type` and from
     `Mastery Type - Parameter - Classroom`.
   - Delete `Standard or QBL` (`[Parameter 9]`) and its dropdown zones on O3
     View and DKI View. Delete the "Use the dropdown to change between Standard
     and QBL mastery" text next to them.
   - `View by - O3 Standards` becomes its Standards branch only. Its formula is
     the Standards field directly, and it keeps its internal name, so the
     worksheets that use it are unchanged.
2. **Calculations**
   - Remove the `QBLs` branch from `Is Mastery Int - Custom` and from
     `Is Mastery Int - Custom - Classroom`.
   - Delete the `QBL` calculation, `Power Standard Goal (%)` and
     `Power Standards - Diff from Goal`.
3. **QBL-only objects:** delete everything below. Zones are also removed from
   all 12 `<devicelayout>` blocks.
   - The four QBL worksheets and their dashboard zones.
   - The two hidden `QBLs` containers and the three QBL filter cards.
   - Both `Action (…Qbl)` groups, any action whose source is a deleted sheet,
     and the deleted sheet names in the exclude lists of the five actions that
     list them.
   - The QBL drill path.
   - Mastery Roster's `qbl` filter and its `qbl` font-size rule.
   - The "all" `qbl` filters on the seven title and roster sheets.
4. **Visible buttons:** delete Show QBLs / Hide QBLs from the header flow of
   each Mastery Over Time dashboard. The title zone in that flow takes the freed
   width, so the remaining header button keeps its right-edge position.
5. **Landing Page copy:** remove "and QBL" from "assessment, standard, and QBL
   mastery". Keep the rest of the sentence.
6. **Datasources:** remove `qbl` and `is_qbl` (column and metadata record) from
   the `rpt_tableau__ddi_dashboard` datasource, and `power_standard_goal` and
   `is_power_standard` from the `rpt_tableau__assessment_dashboard` datasource.

**Verification:** each check is written before the edit and confirmed to fail on
the base.

- After the edit, the file contains no `qbl`, `is_qbl`, `QBLs`, `Qbl` or
  `power_standard` text in any case. The one exception is text that must stay
  for a reason documented in the hand-over.
- The worksheet list equals the base minus exactly the four QBL sheets. The
  dashboard list is unchanged. The parameter list equals the base minus
  `Standard or QBL`.
- Each remaining edited calculation is checked against its expected formula
  string.
- `check_twb.py --ref base.twb` passes. `check_geometry.py --baseline base.twb`
  passes for each of the five edited dashboards. Each assertion is
  mutation-tested per the skill.
- Repack with `repack.py`. Publish to a non-production project (the owner names
  it at publish time) as `ZZ-REVIEW <date> DDI Suite`, with `hidden_views` set
  so only the 8 live view names are visible. Record production's revision number
  first.
- Render base and edit for all 8 views. For Mastery Over Time, render once per
  remaining `Mastery Type` value; for Classroom, once per remaining
  `Mastery Type - Classroom` value. Read the crops of every edited region for
  `####`, clipped text, blank marks, overlaps and the header layout.
- Trigger an extract refresh on the review copy and confirm the job succeeds.
  That tests the reduced field list against the live tables.
- The owner opens the `.twbx` in Tableau Desktop and clicks through the
  dropdowns and the Mastery Over Time actions. This is the only check for
  hovers, clicks and Desktop validity.

**Production publish:** only after the owner names production as the target in a
typed message and confirms when asked "Are you sure?", per the skill.

**Rollback:** republish the recorded prior revision. That requires the same two
confirmations.

### Step 3 — dbt PR 2: drop the columns and disable the lookup (data engineer)

Open this PR only after Step 2 is live in production and the owner has confirmed
it works.

- `rpt_tableau__ddi_dashboard`: remove `qbl` and `is_qbl` from all three
  branches and from the properties YAML.
- `rpt_tableau__assessment_dashboard`: remove `power_standard_goal` and
  `is_power_standard` from the SQL and the properties YAML.
- `stg_google_sheets__assessments__qbls_power_standards`: add
  `config: enabled: false`, and add `enabled: false` to each of its tests. Keep
  the `.sql`.
- `sources-external.yml`: add `enabled: false` under the
  `src_google_sheets__assessments__qbls_power_standards` source's `config:`.
  Keep the entry. This is the same retirement as
  `src_google_sheets__gradebook_flags` (`fdf185aaeb`). The source drops out of
  `manifest["sources"]`, which removes its Dagster asset.
- `docs/launch/links.yml`: remove QBL from the DDI Suite description.

**Verification:**

- `rg -i 'qbl|power_standard' --glob '*.{sql,yml,md}'` returns only the disabled
  models, their YAML, and historical specs and plans.
- `dbt parse --no-partial-parse` succeeds. No enabled node depends on the
  disabled staging model or source.
- Build both `rpt_` models in dev. Row counts by `academic_year` match prod, and
  each schema equals prod minus exactly the dropped columns.
- After deploy, `kipptaf/google/sheets/assessments/qbls_power_standards` no
  longer appears in the kipptaf asset graph.
- After the first prod build that follows the merge, query Tableau for the DDI
  Suite refresh job's result. The Dagster refresh asset only queues the refresh
  and never checks whether it succeeded, so a green Dagster run is not evidence.

**Rollback:** revert the PR. That restores the placeholder columns and the
source with no Tableau publish needed.

## Risks

- **Extract refresh after the column drop (Step 3):** the test is the refresh of
  the review copy in Step 2 plus the post-merge refresh check. Reverting Step 3
  is the fallback.
- **Header layout after removing the buttons (Step 2):** `check_geometry.py`
  plus the rendered header crops.
- **Workbook drift between the inventory and the build:** the fresh pull and the
  list diff at the start of Step 2.
- **Desktop rejecting a file that Server accepted:** the owner's Desktop open
  before the production publish.

## Revision 2026-10-03 (planning)

Found while writing the implementation plan; supersedes the Step 2 and Step 3
text above where they differ.

- **Production publish moves to the owner, from Tableau Desktop.** A REST
  publish drops the workbook's embedded connection credentials (the
  `tableau-workbook-xml` skill's _What a publish drops_), which would break the
  DDI Suite's scheduled refreshes. Claude publishes only the review copy; the
  owner opens the edited `.twbx`, checks it, and publishes to production from
  Desktop with credentials embedded as today.
- **The extract-refresh check moves to the owner's Desktop session.** A refresh
  of the review copy would fail on the dropped credentials and prove nothing
  about the field list. Instead the owner runs a full extract refresh of both
  data sources in Desktop before publishing.
- **Text zones depend on the deleted parameter.** O3 View zone 76 and DKI View
  zone 59, and the titles of four DKI and O3 worksheets, print
  `<[Parameters].[Parameter 9]> Mastery`. They become the literal
  `Standards Mastery`, and the freed width of the deleted dropdown goes to that
  header. The instruction line appears under both O3 headers (zones 76 and 82,
  main and phone layouts); it is removed from both, and zone 82 keeps its
  `Assessment Mastery by <View By - Classroom>` header.
- **Hidden QBL containers hold more than the QBL sheets.** Mastery Over Time
  [Region] and [School] container 306 also holds an inner flow and an empty
  spacer (Region 373 and 375, School 309 and 311); all go with it.
- **The staging model has no tests**, so Step 3 adds only the model-level
  `enabled: false`.
- **O3 View fails `check_geometry.py` before any edit** (zone 156 overlaps zone
  3). The edited file must show exactly that failure and no other.
