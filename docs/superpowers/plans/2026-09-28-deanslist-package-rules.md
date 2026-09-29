# DeansList Package Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move referral-tier, bad-date, community-service, incentive, and
comm-log rules from kipptaf into the shared `src/dbt/deanslist` package, then
switch kipptaf consumers to the package columns.

**Architecture:** Two PRs. PR 1 edits only the package; after it deploys and
every district rebuilds, #5580 can merge. The spec put the four kipptaf
incentive source entries in PR 1; this plan moves them to PR 2 (Task 8), since
they are unreferenced until then and a PR 1 Miami entry would conflict with
#5580's rewrite of `sources-kippmiami.yml`. PR 2 is kipptaf-only, on a new
branch from `origin/main`, and reads the new columns that are by then in prod.

**Tech Stack:** dbt (BigQuery), dbt unit tests, sqlfluff/sqlfmt via trunk.

**Spec:** `docs/superpowers/specs/2026-09-28-deanslist-package-rules-design.md`

**Worktree:**
`/workspaces/teamster/.claude/worktrees/cbini/refactor/claude-deanslist-package-rules`
(branch `cbini/refactor/claude-deanslist-package-rules`, issue #5582). Every
path below is relative to it.

## Global Constraints

- Every dbt command: `uv run dbt ...`, `--target dev`, and
  `--defer --favor-state --state /workspaces/teamster/src/dbt/<district>/target/prod`
  (absolute path; the worktree has no `target/prod/`).
- Package models build through a consuming district:
  `--project-dir src/dbt/<district>`. Districts: `kippnewark`, `kippcamden`,
  `kipppaterson`, `kippmiami`.
- Date floor: package var `deanslist_min_valid_date: "2015-07-01"`.
- Tier values are exactly `Social Work`, `Non-Behavioral`, `Low`, `Middle`,
  `High`, `Other`, or null. Case-sensitive.
- `is_behavioral_referral` is `false`, never null, when `category` is null.
- Staging models are contract-enforced: every new column gets `data_type` and
  `description` in its properties yml.
- Package tests default to `severity: error`; the singular bad-date test sets
  `warn` explicitly.
- SQL rules from `.claude/rules/dbt-sql.md`: max one level of function nesting,
  no `cast` nested inside another function, no lateral column aliases, no
  `qualify`.
- No student-level values in commits, PR bodies, or comments. Counts only.
- Before pushing:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.

## Review Focus

- A `Tier 1` category with no `" - "` separator (Paterson's current format) must
  map to `Low`, not `Other`. Pinned in Task 1's unit test.
- A category like `SSW - ...` or `SSC - ...` must be `Social Work`, never fall
  to a tier branch. Pinned in Task 1's unit test.
- A `behavior` in a Community Service category whose prefix is not a number
  (e.g. `Community Service Other`) must give `cs_hours` null, not fail the
  build. Pinned in Task 3's check query.
- A penalty with a null `startdate` or empty string must not appear in the
  bad-date test. Pinned in Task 2's test SQL (`nullif` before cast).
- Two comm-log rows for the same student, year and reason on the same
  `call_date` must yield exactly one `is_latest_for_reason = true`. Pinned in
  Task 5's check query.

---

## PR 1: package

### Task 1: `referral_tier` and `is_behavioral_referral`

**Files:**

- Modify: `src/dbt/deanslist/models/intermediate/int_deanslist__incidents.sql`
- Modify:
  `src/dbt/deanslist/models/intermediate/properties/int_deanslist__incidents.yml`

**Interfaces:**

- Produces: `int_deanslist__incidents.referral_tier` (string, values above) and
  `int_deanslist__incidents.is_behavioral_referral` (boolean, never null). Both
  flow to `int_deanslist__incidents__penalties` via `i.*`.

- [ ] **Step 1: Write the failing unit test** in `int_deanslist__incidents.yml`,
      top-level `unit_tests:` block:

```yaml
unit_tests:
  - name: test_int_deanslist__incidents__referral_tier
    model: int_deanslist__incidents
    given:
      - input: ref('stg_deanslist__incidents')
        rows:
          - { incident_id: 1, category: SW - Counseling }
          - { incident_id: 2, category: SSC - Check In }
          - { incident_id: 3, category: Documentation of Call }
          - { incident_id: 4, category: TX - Medical }
          - { incident_id: 5, category: School Clinic }
          - { incident_id: 6, category: T1 - Disruption }
          - { incident_id: 7, category: Tier 1 Disruption }
          - { incident_id: 8, category: T2 - Defiance }
          - { incident_id: 9, category: Tier 3 Fighting }
          - { incident_id: 10, category: Skipped Detention }
          - { incident_id: 11, category: null }
      - input: ref('int_deanslist__incidents__custom_fields__pivot')
        rows:
          - { incident_id: -1 }
      - input: ref('stg_deanslist__users')
        rows:
          - { dl_user_id: "-1" }
    expect:
      rows:
        - {
            incident_id: 1,
            referral_tier: Social Work,
            is_behavioral_referral: false,
          }
        - {
            incident_id: 2,
            referral_tier: Social Work,
            is_behavioral_referral: false,
          }
        - {
            incident_id: 3,
            referral_tier: Non-Behavioral,
            is_behavioral_referral: false,
          }
        - {
            incident_id: 4,
            referral_tier: Non-Behavioral,
            is_behavioral_referral: false,
          }
        - {
            incident_id: 5,
            referral_tier: Non-Behavioral,
            is_behavioral_referral: false,
          }
        - { incident_id: 6, referral_tier: Low, is_behavioral_referral: true }
        - { incident_id: 7, referral_tier: Low, is_behavioral_referral: true }
        - {
            incident_id: 8,
            referral_tier: Middle,
            is_behavioral_referral: true,
          }
        - { incident_id: 9, referral_tier: High, is_behavioral_referral: true }
        - {
            incident_id: 10,
            referral_tier: Other,
            is_behavioral_referral: true,
          }
        - {
            incident_id: 11,
            referral_tier: null,
            is_behavioral_referral: false,
          }
```

- [ ] **Step 2: Run it and confirm it fails**

Run:
`uv run dbt test --select "int_deanslist__incidents,test_type:unit" --project-dir src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 30`

Expected: FAIL. `is_behavioral_referral` is not a column, and rows 3, 7 and 9
return `Other`.

- [ ] **Step 3: Implement.** Wrap the current select in a CTE `incidents`.
      Replace the `referral_tier` case with the spec section 1 table, in its
      order, matching on `left(category, 2)` / `left(category, 6)` and
      `category like 'Documentation%'`. Keep the two Miami branches, guarded by
      `'{{ project_name }}' = 'kippmiami'`. Final select:
      `select *, coalesce(referral_tier not in ('Social Work', 'Non-Behavioral'), false) as is_behavioral_referral, from incidents`.
      Add both columns to the yml with descriptions (what each tier means; the
      flag excludes Social Work, Non-Behavioral, and null category).

- [ ] **Step 4: Run the unit test again.** Same command. Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -u src/dbt/deanslist/models/intermediate/
git commit -m "feat(dbt): canonical referral_tier and is_behavioral_referral in deanslist package"
```

### Task 2: Bad dates

**Files:**

- Modify: `src/dbt/deanslist/dbt_project.yml` (`vars:`)
- Modify: `src/dbt/deanslist/models/staging/stg_deanslist__incidents.sql`
- Modify:
  `src/dbt/deanslist/models/intermediate/int_deanslist__incidents__penalties.sql`
- Create: `src/dbt/deanslist/tests/deanslist_dates_before_min_valid.sql`

**Interfaces:**

- Produces: var `deanslist_min_valid_date`. `close_ts_date`, `start_date`, and
  `end_date` are null below it. Column names and types unchanged.

- [ ] **Step 1: Write the singular test.** Header:
      `{{ config(severity="warn", meta={"dagster": {"ref": {"name": "stg_deanslist__incidents", "package": "deanslist"}}}) }}`.
      A `dates` CTE unions three branches over
      `{{ source("deanslist", "src_deanslist__incidents") }}`: `closets.date` as
      `close_ts_date`, and `unnest(penalties)` for `startdate` and `enddate`.
      Each branch outputs `incident_id` (`incidentid` cast to int64), a literal
      `field_name`, and `field_value` as `safe_cast(nullif(<raw>, '') as date)`.
      Final:
      `select incident_id, field_name, field_value, from dates where field_value < '{{ var("deanslist_min_valid_date") }}'`.

- [ ] **Step 2: Run it before adding the var, and confirm it errors on the
      missing var**

Run:
`uv run dbt test --select deanslist_dates_before_min_valid --project-dir src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 20`

Expected: compilation error naming `deanslist_min_valid_date`.

- [ ] **Step 3: Implement.**
  - Add `deanslist_min_valid_date: "2015-07-01"` under `vars:` in the package
    `dbt_project.yml`.
  - `stg_deanslist__incidents.sql` final select: `* except (close_ts_date)`,
    re-add
    `if(close_ts_date < '{{ var("deanslist_min_valid_date") }}', null, close_ts_date) as close_ts_date`.
  - `int_deanslist__incidents__penalties.sql` final select: same pattern for
    `start_date` and `end_date`.

- [ ] **Step 4: Run the test on Newark and Camden.** Same command, then with
      `kippcamden` in both paths. Expected: at least `WARN 8` on Newark (3
      close, 3 start, 2 end) and at least `WARN 7` on Camden (5 start, 2 end).
      The raw source can hold duplicate or inactive incidents that staging
      drops, so a higher count is fine. The count reports the raw typos, which
      is the point. If the count is 0, the test is reading cleaned data: fix it.

- [ ] **Step 5: Commit**

```bash
git add -u src/dbt/deanslist/
git add src/dbt/deanslist/tests/deanslist_dates_before_min_valid.sql
git commit -m "feat(dbt): null and warn on pre-2015 DeansList dates in the package"
```

### Task 3: `cs_hours`

**Files:**

- Modify: `src/dbt/deanslist/models/staging/stg_deanslist__behavior.sql`
- Modify:
  `src/dbt/deanslist/models/staging/properties/stg_deanslist__behavior.yml`

**Interfaces:**

- Produces: `stg_deanslist__behavior.cs_hours` (int64, nullable).

- [ ] **Step 1: Implement.** In `transformations`, add
      `left(nullif(behavior, ''), length(behavior) - 5) as behavior_hours_prefix`.
      In the final select, `* except (behavior_hours_prefix)` and
      `safe_cast(if(behavior_category in ('Community Service', 'Community Service Hours'), behavior_hours_prefix, null) as int64) as cs_hours`.
      Add `cs_hours` (`int64`) to the yml with a description.

- [ ] **Step 2: Build in Newark and check values**

Run:
`uv run dbt build --select stg_deanslist__behavior --project-dir src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 20`

Expected: PASS (contract holds). Then, with the BigQuery MCP on
`zz_cbini_kippnewark_deanslist.stg_deanslist__behavior`:
`select behavior_category, countif(cs_hours is not null), countif(cs_hours is null) ... group by 1`.
Expected: non-null only in the two Community Service categories, and the
non-numeric Community Service behaviors are null, not errors.

- [ ] **Step 3: Commit**

```bash
git add -u src/dbt/deanslist/models/staging/
git commit -m "feat(dbt): add cs_hours to stg_deanslist__behavior"
```

### Task 4: `int_deanslist__behavior_incentive_by_term`

**Files:**

- Create:
  `src/dbt/deanslist/models/intermediate/int_deanslist__behavior_incentive_by_term.sql`
- Create:
  `src/dbt/deanslist/models/intermediate/properties/int_deanslist__behavior_incentive_by_term.yml`

**Interfaces:**

- Consumes: `stg_deanslist__behavior` (`student_school_id`, `dl_school_id`,
  `academic_year`, `behavior`, `behavior_date`), `stg_deanslist__terms`
  (`school_id`, `academic_year`, `term_type`, `term_name`, `start_date_date`,
  `end_date_date`).
- Produces: columns `student_school_id`, `incentive_type`, `academic_year`,
  `term_name`, `start_date`, `end_date`, `school_id`, `behavior`, with the same
  names and types as the kipptaf model of the same name.

- [ ] **Step 1: Implement.**
  - CTE `incentive_behaviors`: `stg_deanslist__behavior` filtered to the four
    behaviors in spec section 4, plus `case behavior when ... end as term_type`
    mapping per the spec.
  - CTE `terms`: `stg_deanslist__terms` plus
    `concat('Q', right(term_name, 1)) as quarter_label`.
  - Final: inner join on `academic_year`, `dl_school_id = school_id`,
    `term_type`, and `behavior_date between start_date_date and end_date_date`.
    `incentive_type` is
    `if(b.behavior = 'Progress to Quarterly Incentive', concat(t.term_type, ' (Progress to Quarterly Incentive)'), t.term_type)`.
    `term_name` is `if(t.term_type = 'Quarters', t.quarter_label, t.term_name)`.
    `max(b.behavior) as behavior`, grouped by every other output column.
  - yml: model and column descriptions, and
    `dbt_utils.unique_combination_of_columns` on `student_school_id`,
    `incentive_type`, `academic_year`, `term_name`, `school_id` at model level.
    Prod holds this key: 77,495 rows, 77,495 distinct on 2026-09-28.

- [ ] **Step 2: Build in Newark**

Run:
`uv run dbt build --select int_deanslist__behavior_incentive_by_term --project-dir src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 20`

Expected: PASS, uniqueness test included.

- [ ] **Step 3: Prove parity with prod.** BigQuery MCP: the dev table
      `zz_cbini_kippnewark_deanslist.int_deanslist__behavior_incentive_by_term`
      `except distinct` the prod kipptaf model filtered to Newark rows, and the
      reverse. Filter the kipptaf side to Newark by joining its `school_id` to
      the dev table's distinct `school_id`s. Expected: 0 rows both ways.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/deanslist/models/intermediate/int_deanslist__behavior_incentive_by_term.sql src/dbt/deanslist/models/intermediate/properties/int_deanslist__behavior_incentive_by_term.yml
git commit -m "feat(dbt): add int_deanslist__behavior_incentive_by_term to the package"
```

### Task 5: `is_latest_for_reason`

**Files:**

- Modify: `src/dbt/deanslist/models/intermediate/int_deanslist__comm_log.sql`
- Modify:
  `src/dbt/deanslist/models/intermediate/properties/int_deanslist__comm_log.yml`

**Interfaces:**

- Produces: `int_deanslist__comm_log.is_latest_for_reason` (boolean).

- [ ] **Step 1: Implement.** Add to the select, last:
      `row_number() over (partition by cl.student_school_id, cl.academic_year, cl.reason order by cl.call_date desc, cl.call_date_time desc) = 1 as is_latest_for_reason`.
      Add the column to the yml with a description.

- [ ] **Step 2: Build in Newark and check the pick**

Run:
`uv run dbt build --select int_deanslist__comm_log --project-dir src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kippnewark/target/prod 2>&1 | tail -n 20`

Expected: PASS. Then with the BigQuery MCP:
`select count(*) from (select student_school_id, academic_year, reason, countif(is_latest_for_reason) as n from <dev table> group by 1, 2, 3) where n != 1`.
Expected: 0.

- [ ] **Step 3: Count cross-region collisions.** BigQuery MCP on the prod
      kipptaf `int_deanslist__comm_log`: the number of
      `(student_school_id, academic_year, reason)` keys found in more than one
      `_dbt_source_project`. Record the count (a number only) for the PR 1 body.

- [ ] **Step 4: Commit**

```bash
git add -u src/dbt/deanslist/models/intermediate/
git commit -m "feat(dbt): add is_latest_for_reason to int_deanslist__comm_log"
```

### Task 6: Build every district, verify, open PR 1

**Files:** none new.

- [ ] **Step 1: Build the changed package models in each district.** For each of
      `kippnewark`, `kippcamden`, `kipppaterson`, `kippmiami`, run it as its own
      Bash call:

`uv run dbt build --select stg_deanslist__incidents+ stg_deanslist__behavior+ int_deanslist__comm_log+ int_deanslist__behavior_incentive_by_term --project-dir src/dbt/<district> --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/<district>/target/prod 2>&1 | tail -n 30`

Expected: 0 errors. Warns allowed: the bad-date test in Newark and Camden only.
If a dev external source is missing, re-stage your own copy with
`stage_external_sources --target dev` (see `dbt-local-dev`).

- [ ] **Step 2: Re-run the tier diff against dev.** Use the spec section 1 query
      shape, with the dev
      `zz_cbini_<district>_deanslist.int_deanslist__incidents` tables as the new
      side and prod kipptaf as the old side. Expected: the five rows of the spec
      table, within new-data drift, and nothing else.

- [ ] **Step 3: Lint.**
      `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <every changed file> </dev/null`.
      Expected: no issues.

- [ ] **Step 4: Push and open PR 1.** Body from
      `.github/pull_request_template.md`. Include `Refs #5582`, the tier impact
      table, the comm-log collision count, a note that dbt Cloud CI does not
      build package models (the local builds above are the validation), and a
      heads-up line for the school-metrics sheet owner about the Documentation
      drop.

---

## Deploy gate (between the PRs)

### Task 7: Confirm every district rebuilt

- [ ] **Step 1:** After PR 1 merges, confirm each district's deploy ran:
      `gh run list --branch main` shows `deploy-prod-kipp<district>` success for
      all four.
- [ ] **Step 2:** For each district, `mcp__dagster__get_asset_materializations`
      on `<district>/deanslist/int_deanslist__incidents` shows a materialization
      after the deploy.
- [ ] **Step 3:** `INFORMATION_SCHEMA.COLUMNS` on each
      `kipp<district>_deanslist` dataset shows `is_behavioral_referral`,
      `cs_hours`, `is_latest_for_reason`, and the
      `int_deanslist__behavior_incentive_by_term` table exists.
- [ ] **Step 4:** Tell the user #5580 can resume: merge `origin/main`, then
      delete the two Miami branches of `referral_tier` from the package in #5580
      (spec section 1), and add `int_deanslist__behavior_incentive_by_term` to
      #5580's BQ-native `sources-kippmiami.yml`.

---

## PR 2: kipptaf

New branch from `origin/main` via the CLAUDE.md _Branches_ flow (PR 1's branch
is deleted on merge), linked to #5582.

### Task 8: Incentive wrapper and sources

**Files:**

- Modify: `src/dbt/kipptaf/models/deanslist/api/sources-kippnewark.yml`,
  `sources-kippcamden.yml`, `sources-kipppaterson.yml` (and
  `sources-kippmiami.yml` if #5580 has not already added it)
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__behavior_incentive_by_term.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/properties/int_deanslist__behavior_incentive_by_term.yml`

- [ ] **Step 1:** Add `int_deanslist__behavior_incentive_by_term` to each source
      file, matching the existing entries' `meta.dagster` block
      (`group: deanslist`,
      `asset_key: [<district>, deanslist, int_deanslist__behavior_incentive_by_term]`).
- [ ] **Step 2:** Replace the kipptaf model body with the same
      `union_relations` + `extract_source_project` shape as
      `int_deanslist__comm_log.sql`. Move the uniqueness test to the yml with
      `_dbt_source_project` added to the key.
- [ ] **Step 3:** Build it `--target dev`, then compare to prod kipptaf:
      `except distinct` both ways on the original 8 columns. Expected: 0 rows
      each way.

### Task 9: Remove the kipptaf date sanitize

**Files:**

- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql`
- Modify: both files' properties yml (delete the three `expression_is_true`
  tests that compare against `'2000-01-01'`)

- [ ] **Step 1:** Delete the `sanitized` CTEs; select from `union_relations`
      directly.
- [ ] **Step 2:** Build both plus `fct_behavioral_incidents` and
      `fct_behavioral_consequences` `--target dev`. Expected: the date-key
      relationships tests pass.

### Task 10: Tier consumers

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__okrts_referrals.sql`
- Modify:
  `src/dbt/kipptaf/models/topline/intermediate/int_topline__suspension_weekly.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__historical_suspensions.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__school_metrics_extract.sql`
- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__referral_suspension_rollup.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/branchingminds/rpt_branchingminds__behavior_incident.sql`

- [ ] **Step 1:** okrts: replace the tier `case` (currently around lines
      307-325) with `dli.referral_tier`, keeping the output name
      `referral_tier`.
- [ ] **Step 2:** Replace each
      `referral_tier not in ('Non-Behavioral', 'Social Work')` with
      `is_behavioral_referral` (using the same alias). Branching Minds:
      `(i.is_behavioral_referral or i.category is null)`.
- [ ] **Step 3:** Rollup: `'low'` → `'Low'` at both sites.
- [ ] **Step 4:** Build the six `--target dev`, then check
      `sum(referral_count_low) > 0` in the dev rollup. Expected: true.

### Task 11: `cs_hours` and comm-log consumers

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/google/sheets/rpt_gsheets__community_service_upload.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__community_service.sql`
- Modify:
  `src/dbt/kipptaf/models/students/intermediate/int_students__attendance_interventions.sql`
- Modify:
  `src/dbt/kipptaf/models/marts/facts/fct_student_attendance_interventions.sql`

- [ ] **Step 1:** Community service: read `b.cs_hours`. Tableau keeps
      `coalesce(b.cs_hours, 0)`.
- [ ] **Step 2:** Comm log: replace each `dbt_utils.deduplicate` CTE with a read
      of `int_deanslist__comm_log` filtered `where is_latest_for_reason`.
- [ ] **Step 3:** Build the four `--target dev`. Parity check: the gsheets
      upload `except distinct` prod both ways must be 0 rows; the interventions
      models may differ only by the Task 5 collision count.

### Task 12: Open PR 2

- [ ] **Step 1:** Lint every changed file with trunk (`--force --no-fix`).
- [ ] **Step 2:** Push, open the PR with `Closes #5582`, and watch dbt Cloud CI
      plus Trunk to green. Fetch CI warnings and compare them to main before
      declaring done (`pr-ci-review`).

## Revision 2026-09-28: drop the incentive model

Per the spec's revision of the same date:

- Task 4 is reverted: the package model and its yml are deleted from PR 1.
- Task 6 and Task 7 drop `int_deanslist__behavior_incentive_by_term` from their
  selections and checks; #5580 no longer adds it to `sources-kippmiami.yml`.
- Task 8 becomes: switch `int_topline__deanslist_incentives_weekly` and
  `rpt_tableau__okrts_behavior` to `stg_deanslist__behavior` bucketed by
  calendar week and quarter (date-range quarter lookup for Sunday-dated awards),
  then disable the kipptaf `int_deanslist__behavior_incentive_by_term` and its
  tests. Verify AY2025 flags are populated and current-year flags match prod
  except Friday-dated Progress awards.
