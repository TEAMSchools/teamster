# PM Outlier RLS Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the 11 Tableau RLS contract columns, describing the observer, to
`rpt_tableau__pm_outlier_detection`.

**Architecture:** The model already joins the observer's primary roster row as
of the round's end date (`srh`). Select the contract columns from it, add a
`left join` to `int_people__location_crosswalk` for the two location columns,
and declare the columns and their tests in the properties YAML.

**Tech Stack:** dbt (BigQuery), kipptaf project.

**Spec:** `docs/superpowers/specs/2026-11-12-pm-outlier-rls-contract-design.md`

## Global Constraints

- Contract columns keep their real source names; no aliases.
- Additive only: every existing output column stays, unchanged.
- No entity-abbreviation `case` on `home_business_unit_name`.
- Every test on this model is `config: severity: error`.
- Every new column has a `description:`; `mail`, `user_principal_name`,
  `sam_account_name`, `reports_to_mail`, `reports_to_sam_account_name` carry
  `config.meta.contains_pii: true`.
- All paths below are relative to the worktree
  `/workspaces/teamster/.claude/worktrees/kevinverhoff/feat/claude-pm-outlier-rls-contract`.

## Review Focus

- The crosswalk join fans out (a `location_name` mapping to 2 rows): the
  existing 4-column grain test catches it; run it.
- An observer location missing from the crosswalk yields a null
  `location_clean_name`: the `not_null` test catches it; prod has 0 today.
- A historical abbreviation (`TEAM`, `KCNA`, `MIA`, `KNJ`) reaching
  `home_business_unit_name`: the `accepted_values` test catches it.
- Row count changes after the edit: a `left join` must not drop rows; compare
  dev count with prod (4,249).

---

### Task 1: Contract columns, tests, and verification

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__pm_outlier_detection.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__pm_outlier_detection.yml`

**Interfaces:**

- Consumes: `srh` (`int_people__staff_roster_history`, the observer join already
  in the model); `int_people__location_crosswalk` (`location_name`,
  `location_clean_name`, `campus_name`).
- Produces: output columns `location_clean_name`, `campus_name`,
  `home_business_unit_name`, `home_department_name`, `job_function`,
  `job_title`, `mail`, `user_principal_name`, `sam_account_name`,
  `reports_to_mail`, `reports_to_sam_account_name`, all `string`.

- [ ] **Step 1: Declare the columns and tests in the YAML**

Add the 11 columns with `data_type: string` and descriptions saying each
describes the observer and which gate it drives (follow
`properties/rpt_tableau__schoolmint_grow_observation_details.yml` wording).
Tests, placed per the column-sorting rule (tested columns at the top):

```yaml
- name: location_clean_name
  data_tests:
    - not_null:
        config:
          severity: error
- name: home_business_unit_name
  data_tests:
    - not_null:
        config:
          severity: error
    - accepted_values:
        arguments:
          values:
            - TEAM Academy Charter School
            - KIPP Cooper Norcross Academy
            - KIPP Miami
            - KIPP Paterson
            - KIPP TEAM and Family Schools Inc.
        config:
          severity: error
```

Match the `arguments:` / `config:` nesting the file's existing tests use. Update
the model `description:` to say the contract columns describe the observer.

- [ ] **Step 2: Run the build to see the contract fail**

Run (from the worktree):
`uv run dbt build --select rpt_tableau__pm_outlier_detection --project-dir src/dbt/kipptaf --target dev --defer --favor-state --state /workspaces/teamster/src/dbt/kipptaf/target/prod 2>&1 | tail -n 30`
Expected: FAIL, contract mismatch listing the 11 missing columns.

- [ ] **Step 3: Add the columns in the SQL**

In the final select, after the existing `srh.*` observer columns: the 9 roster
columns from `srh` as plain columns; `lc.location_clean_name` and
`lc.campus_name` as their own group in join order (S6). Add after the `srh`
join:

```sql
left join
    {{ ref("int_people__location_crosswalk") }} as lc
    on srh.home_work_location_name = lc.location_name
```

- [ ] **Step 4: Run the build to see it pass**

Same command as Step 2. Expected: model `OK`, all tests `PASS` (grain,
`not_null` x2 plus the existing one, `accepted_values`).

- [ ] **Step 5: Confirm no row-count change**

Query the dev relation
(`zz_<user>_kipptaf_tableau.rpt_tableau__pm_outlier_detection`) with the
BigQuery MCP: `count(*)` must equal prod's 4,249, and
`countif(location_clean_name is null)` must be 0.

- [ ] **Step 6: Lint**

Run:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <the two files> </dev/null`
Expected: no lint issues (formatting-only issues are fixed by the commit hook).

- [ ] **Step 7: Commit**

```bash
git add -u
git commit -m "feat(dbt): gate pm outlier detection on the observer's RLS contract" -m "Refs #4663"
```

(End the message with the session's Co-Authored-By line.)
