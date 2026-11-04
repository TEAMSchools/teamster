# Legal-Entity-Derived Student RLS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bind Cube student row-level security to the legal entity that employs
a staff member, not to the physical location of their desk.

**Architecture:** `dim_staff_cube_access` currently reads `region_key` from the
staff member's work location (`dim_work_assignment_locations` →
`dim_locations`). Replace that with a join from the employing
`business_unit_name` to `dim_regions.legal_entity`, which already carries the
same five strings 1:1 with region. Because region and legal entity are 1:1, the
resulting value is still a region key and the view policies keep filtering
`locations_region_key` — only the security-context field is renamed, to
`legal_entity_region_key`, so the boundary cannot be mistaken for a desk
attribute again. KTAF's own legal entity enrolls no students, so a KTAF employee
holding any student scope resolves to `network`.

**Tech Stack:** dbt (BigQuery), Cube 1.7.x (`access.js` / `cube.js` / view
`access_policy`), `node --test`, `scripts/cube_rls_matrix.py`.

**Spec:** [issue #4535](https://github.com/TEAMSchools/teamster/issues/4535),
plus the 2026-09-23 re-measurement recorded in _Measured baseline_ below.

## Global Constraints

- Branch: `cristinabaldor/fix/claude-cube-legal-entity-rls`, checked out in the
  main checkout (the Cube dev server only ever serves the main checkout).
- Viewer emails and staff names are PII. They may appear in the terminal, in
  `#data_team`, and in files under the session scratchpad. They must never reach
  a commit, a PR body, an issue comment, or any other outbound surface.
- `dim_staff_cube_access` is a view mart: `contract: enforced: true` and
  `materialized: view` are inherited from `dbt_project.yml`. Do not restate
  them.
- Every new column needs a `description:` in
  `models/marts/dimensions/properties/dim_staff_cube_access.yml`. Columns
  carrying per-column `data_tests:` sort to the top of the `columns:` list.
- SQL follows `.claude/rules/dbt-sql.md`: no `QUALIFY`, no `ORDER BY`, no
  subqueries, max one level of function nesting, no lateral column aliases, ST06
  select ordering (plain refs by join order → constants → simple functions →
  nested → logicals → `case` → window).
- Run `uv run`, never bare `dbt` or `python`.
- Lint before pushing:
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
- Do not push to `main`. Commit and push the feature branch yourself.

## Measured baseline

Re-measured 2026-09-23 against prod, and reproduced live over the Cube SQL API
with auth on (`NODE_ENV=production CUBEJS_DEV_MODE=false`, Cube 1.7.43). These
are the numbers every task's verification compares against.

Network student population: **27,160** — Camden 5,395 · Miami 3,912 · Newark
16,954 · Paterson 899.

`dim_regions` already carries the employer strings, 1:1 with region:

| region   | `legal_entity`                    | `business_unit_code` | locations |
| -------- | --------------------------------- | -------------------- | --------- |
| Newark   | TEAM Academy Charter School       | `TEAM`               | 18        |
| Camden   | KIPP Cooper Norcross Academy      | `KCNA`               | 7         |
| Miami    | KIPP Miami                        | `KIPP_MIAMI`         | 10        |
| Paterson | KIPP Paterson                     | `KPAT`               | 3         |
| TAF      | KIPP TEAM and Family Schools Inc. | `KIPP_TAF`           | 1         |

All 1,573 current primary-assignment staff resolve through that join: zero NULL
`business_unit_name`, zero unmatched.

Populations this change moves:

| population                                     | count | today        | after     |
| ---------------------------------------------- | ----: | ------------ | --------- |
| KTAF staff, role scope `school`, desk = office |     5 | 0 rows       | 27,160    |
| KTAF staff, role scope `region`, desk = office |     3 | 5,395–16,954 | 27,160    |
| Miami staff, scope `region`, desk unresolved   |     1 | 0 rows       | 3,912     |
| Miami staff, scope `school`, desk unresolved   |     9 | 0 rows       | 0 rows    |
| Newark-employed, Paterson desk, scope `none`   |     1 | 0 rows       | 0 rows    |
| everyone else                                  | 1,554 | unchanged    | unchanged |

The 9 Miami `school`-scoped viewers stay denied on purpose: school scope needs a
location abbreviation, which an employer cannot supply. Task 4 surfaces them
instead of leaving them silent.

The 8 KTAF viewers are the reason the KTAF override is load-bearing rather than
cosmetic. Derive the key from the employer with no override and they resolve to
the TAF region, whose single location enrolls nobody — Poole and Marrer would go
from partial access to zero.

**The staff-PII remit is unaffected.** Every KTAF viewer whose
`staff_location_scope` is not `network` has `staff_pii_scope = 'none'`, so
`buildGroups` emits no `staff-pii-*` group for them and `allowed_abbreviations`
is never interpolated. That is what lets one key serve both axes instead of
forcing a second column.

## Decisions taken

The issue left three questions open. Answers, so a reviewer does not reopen
them:

- **Keep the enum value `region`; do not rename it to `legal_entity`.** The enum
  names a _breadth_ — one region's worth of students — and that stays true. What
  was wrong is the attribute the breadth was measured from, and renaming the
  _key_ to `legal_entity_region_key` fixes exactly that. Renaming the enum would
  mean editing the `cube_access_role` and `cube_access_department_override`
  Google Sheets, the `accepted_values` tests, the `student-region` group name in
  `buildGroups`, and four view policies, for no security gain. **The sheets are
  therefore untouched by this change**, which removes the issue's fourth
  affected surface.
- **No KTAF staff are region or school scoped.** Zero of 149 sit at a school;
  all four office rooms enrol nobody. Task 2 resolves any granted KTAF scope to
  `network`. `none` is preserved, because it is a decision about the role rather
  than the desk — one viewer (an intern in finance) is in that state today.
- **An unresolved employer defaults to deny, and now says so.** `entity`
  resolves to `unknown`, which matches only `any` role rows. The error-severity
  test in Task 1 catches an unmatched business unit, and the warn-severity test
  in Task 4 surfaces the nine viewers whose `school` scope cannot resolve a
  location — previously a silent denial indistinguishable from a correct one.

## Review Focus

Five failure modes the change implies that no single task's happy path
exercises. Each has a test pinned to the task that owns the code.

1. **A half-finished rename reopens the Cube Cloud paste vector.** If any view
   still interpolates `securityContext.region_key` after `buildSecurityContext`
   stops returning it, `Object.assign` cannot overwrite a pasted value for that
   field and a console user supplies their own region. Pinned to Task 3, step 9
   (repo-wide grep asserting zero survivors).
2. **An unmatched `business_unit_name` must deny, not grant.** A new ADP org
   unit, or a renamed one, yields a NULL join and must resolve to
   `entity = 'unknown'` — which matches only `any` role rows, never the
   entity-specific grants. Pinned to Task 1, step 1.
3. **A KTAF viewer whose role maps to `none` must stay `none`.** The override is
   about location, not about whether a student scope was granted at all. Pinned
   to Task 2, step 1.
4. **`region` scope with a NULL key must deny, not match NULL locations.**
   `computeAllowedAbbreviations` already guards this with `== null`; the rename
   must not turn it into a `===` identity check against the new field. Pinned to
   Task 3, step 5.
5. **The contract must reject a stale `region_key` reference.** Renaming the
   mart column while a consumer still selects it fails at build, not at parse.
   Pinned to Task 1, step 7 (`dbt build` of the model and its children).

## File Structure

| file                                                                           | responsibility after this change                                                                                               |
| ------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`            | Derives `legal_entity`, `legal_entity_region_key` and `entity` from the `dim_regions` join; applies the KTAF network override. |
| `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml` | Column contract, descriptions, and the three new data tests.                                                                   |
| `src/cube/access.js`                                                           | `buildSecurityContext` returns `legal_entity_region_key` in place of `region_key`.                                             |
| `src/cube/cube.js`                                                             | `resolveAccess` passes `row.legal_entity_region_key` into `computeAllowedAbbreviations`.                                       |
| `src/cube/access.test.js`                                                      | Unit coverage for the renamed field and the null-key deny.                                                                     |
| `src/cube/cube.test.js`                                                        | Context field-list assertion and the paste-overwrite tests updated to the new name.                                            |
| `src/cube/model/views/students/*.yml` (3 files)                                | `student-region` policy interpolates the renamed field.                                                                        |
| `src/cube/model/views/student_assessments/student_assessment_scores_view.yml`  | Same, against its unprefixed `region_key` member.                                                                              |
| `.claude/rules/cube-authoring.md`                                              | Records that the student boundary is employer-derived.                                                                         |

---

### Task 1: Derive the legal-entity key and entity from `dim_regions`

Replaces the desk-derived `region_key` and the five-string `entity` CASE with a
single join. Student scope is untouched here — Task 2 owns the override — so
this task alone moves the 1 Miami `region`-scoped viewer and nobody else.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql:34-84` and
  `:133-193`
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml:59-63`
  and `:77-88`

**Interfaces:**

- Consumes: `dim_regions.legal_entity`, `dim_regions.business_unit_code`,
  `dim_regions.region_key` (existing columns, no change needed).
- Produces: `dim_staff_cube_access.legal_entity` (STRING),
  `dim_staff_cube_access.legal_entity_region_key` (STRING, nullable),
  `dim_staff_cube_access.entity` (STRING, unchanged domain
  `[KTAF, Region, unknown]`). The column `region_key` no longer exists. Task 3
  consumes `legal_entity_region_key`.

- [ ] **Step 1: Write the failing tests in the properties YAML**

Add to the model-level `data_tests:` block in
`src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml`,
below the existing `expression_is_true`:

```yaml
# An employing business unit that does not match dim_regions.legal_entity
# must deny, not fall through to a grant: 'unknown' matches only the
# entity-agnostic 'any' role rows. Zero rows today across 1,573 staff, so
# a hit means ADP added or renamed an org unit and dim_regions has not
# caught up.
- dbt_utils.expression_is_true:
    arguments:
      expression: |
        entity != 'unknown' or legal_entity_region_key is null
    config:
      severity: error
```

Replace the `region_key` column entry (currently lines 59-63) with these two,
placed at the top of the `columns:` list because they carry tests:

```yaml
- name: legal_entity_region_key
  data_type: string
  description: >-
    Region key of the legal entity EMPLOYING this viewer, resolved by joining
    business_unit_name to dim_regions.legal_entity — not the region of the desk
    they sit at. This is the student row-level security boundary: FERPA binds
    student-record access to the employing LEA, and region maps 1:1 to legal
    entity, so the value is still joinable to dim_locations.region_key. NULL
    when the employing business unit does not match a known legal entity, which
    denies.
  data_tests:
    - not_null:
        config:
          severity: warn

- name: legal_entity
  data_type: string
  description: >-
    Legal name of the employing entity, straight from the work assignment's home
    organizational unit. Carried for debugging and for the dim_regions join that
    produces legal_entity_region_key and entity.
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd /workspaces/teamster && uv run dbt build --select dim_staff_cube_access --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod 2>&1 | tail -n 25
```

Expected: FAIL with a contract error naming `legal_entity_region_key` and
`legal_entity` as declared-but-missing. It must be `build`, not `parse` — dbt
compares the built relation's schema to the YAML at run time, so `parse` checks
neither the contract nor the new test's column reference and would pass.

- [ ] **Step 3: Add the `dim_regions` join to `current_assignment`**

In `dim_staff_cube_access.sql`, replace the `current_assignment` CTE's select
list and join block (lines 34-84) with:

```sql
    current_assignment as (
        select
            pd.staff_key,

            s.google_email,

            j.job_function_code,

            o.department_name,
            o.business_unit_name as legal_entity,

            loc.abbreviation as location_abbreviation,

            r.region_key as legal_entity_region_key,

            -- FERPA binds student-record access to the employing LEA, so the
            -- scope key comes from business_unit_name, never from the desk:
            -- all 149 KTAF staff sit in a per-city office room that enrolls no
            -- students. A business unit dim_regions does not know resolves to
            -- 'unknown', a deny sentinel matching only entity-agnostic 'any'
            -- role rows. business_unit_code is matched rather than the legal
            -- name because codes outlive rebrands.
            case
                when r.region_key is null
                then 'unknown'
                when r.business_unit_code = 'KIPP_TAF'
                then 'KTAF'
                else 'Region'
            end as entity,
        from primary_deduped as pd
        inner join {{ ref("dim_staff") }} as s on pd.staff_key = s.staff_key
        left join
            {{ ref("dim_work_assignment_jobs") }} as j
            on pd.work_assignment_key = j.work_assignment_key
            and j.is_current
        left join
            {{ ref("dim_work_assignment_organizational_units") }} as o
            on pd.work_assignment_key = o.work_assignment_key
            and o.is_current
            and o.assignment_type = 'home'
        left join
            {{ ref("dim_work_assignment_locations") }} as wal
            on pd.work_assignment_key = wal.work_assignment_key
            and wal.is_current
        left join
            {{ ref("dim_locations") }} as loc on wal.location_key = loc.location_key
        left join
            {{ ref("dim_regions") }} as r
            on o.business_unit_name = r.legal_entity
    ),
```

`dim_locations` stays joined: `location_abbreviation` is the viewer's school for
`school` scope, and no employer can supply it.

- [ ] **Step 4: Carry the new columns through `enriched` and `matched`**

In the `enriched` CTE, replace `ca.region_key,` with:

```sql
            ca.legal_entity,
            ca.legal_entity_region_key,
```

In the `matched` CTE, replace `e.region_key,` with:

```sql
            e.legal_entity,
            e.legal_entity_region_key,
```

- [ ] **Step 5: Update the final SELECT**

Replace `region_key,` in the final select list with:

```sql
    legal_entity,
    legal_entity_region_key,
```

- [ ] **Step 6: Verify it compiles and the column list is right**

```bash
cd /workspaces/teamster && uv run dbt compile --select dim_staff_cube_access --project-dir src/dbt/kipptaf 2>&1 | tail -n 15
```

Expected: PASS, no `region_key` in the compiled select list. Confirm with:

```bash
grep -c "region_key" src/dbt/kipptaf/target/compiled/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql
```

Expected: exactly 2 (the `legal_entity_region_key` alias and the `r.region_key`
source reference); zero bare `loc.region_key`.

- [ ] **Step 7: Build the model and its children into your dev schema**

```bash
cd /workspaces/teamster && uv run dbt build --select dim_staff_cube_access+ --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod 2>&1 | tail -n 30
```

Expected: PASS on the model, on both new tests, and on every child. A child
still selecting `region_key` fails here, which is the point — the contract only
catches it at build.

- [ ] **Step 8: Confirm the derivation against the measured baseline**

Run through the BigQuery MCP, substituting your dev schema:

```sql
select entity, count(*) as staff, countif(legal_entity_region_key is null) as unresolved
from `teamster-332318.zz_<username>_kipptaf_marts.dim_staff_cube_access`
group by 1 order by 1
```

Expected: `KTAF` 149, `Region` 1,424, no `unknown` row, 0 unresolved.

- [ ] **Step 9: Lint and commit**

```bash
cd /workspaces/teamster && .trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml </dev/null
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml
git commit -m "fix(dbt): derive the cube access scope key from the employing legal entity

Refs #4535"
```

---

### Task 2: Resolve KTAF employees to network student scope

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`
  (the `matched` CTE and the final select)
- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml`
  (`student_location_scope` description and a new model-level test)

**Interfaces:**

- Consumes: `entity` and the role-mapped scope from Task 1's `matched` CTE.
- Produces: `dim_staff_cube_access.student_location_scope` (STRING, domain
  unchanged `[network, region, school, none]`), now guaranteed to be `network`
  or `none` for every `entity = 'KTAF'` row.

- [ ] **Step 1: Write the failing test**

Add to the model-level `data_tests:` block in the properties YAML:

```yaml
# KTAF's own legal entity enrolls no students, so a role-mapped region or
# school scope would resolve to an empty allow-list and deny outright —
# measured as 5 KTAF viewers at zero rows and 3 capped to one city. KTAF
# staff serve the whole network, so any granted student scope is network.
# 'none' is preserved: it is a decision about the role, not the desk.
- dbt_utils.expression_is_true:
    arguments:
      expression: |
        entity != 'KTAF' or student_location_scope in ('network', 'none')
    config:
      severity: error
```

- [ ] **Step 2: Run it to verify it fails**

```bash
cd /workspaces/teamster && uv run dbt build --select dim_staff_cube_access --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod 2>&1 | tail -n 20
```

Expected: FAIL with 8 failing rows on the new `expression_is_true`.

- [ ] **Step 3: Rename the role-derived column in `matched`**

In the `matched` CTE, change the student-scope coalesce alias so the raw role
value is available to the next CTE. A lateral alias cannot be referenced in the
same select list, so the override needs its own CTE.

```sql
            coalesce(
                ovr.student_location_scope, rp.student_location_scope, 'none'
            ) as role_student_location_scope,
```

- [ ] **Step 4: Add the `resolved` CTE after `matched`**

```sql
    resolved as (
        select
            * except (role_student_location_scope),

            case
                when entity != 'KTAF'
                then role_student_location_scope
                when role_student_location_scope = 'none'
                then 'none'
                else 'network'
            end as student_location_scope,
        from matched
    )
```

- [ ] **Step 5: Point the final SELECT at `resolved`**

Change the final `from matched` to `from resolved`. The select list already
names `student_location_scope`, so nothing else moves.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
cd /workspaces/teamster && uv run dbt build --select dim_staff_cube_access --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod 2>&1 | tail -n 20
```

Expected: PASS on every test.

- [ ] **Step 7: Confirm the scope distribution matches the baseline**

```sql
select entity, student_location_scope, count(*) as staff
from `teamster-332318.zz_<username>_kipptaf_marts.dim_staff_cube_access`
group by 1, 2 order by 1, 2
```

Expected: `KTAF` / `network` 148, `KTAF` / `none` 1, and no `KTAF` row at
`region` or `school`. Region rows unchanged from the baseline table.

- [ ] **Step 8: Update the `student_location_scope` description**

Replace its `description:` with:

```yaml
description: >-
  Student data location breadth — network, region, school, or none. The only
  gating on student data: a viewer with a non-none scope sees every student view
  and all fields, including PII. Region and school scopes are bounded by
  legal_entity_region_key and location_abbreviation respectively. A KTAF viewer
  granted any scope resolves to network, because KTAF's own legal entity enrolls
  no students; a KTAF viewer mapped to none stays none.
```

- [ ] **Step 9: Lint and commit**

```bash
cd /workspaces/teamster && .trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml </dev/null
git add src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml
git commit -m "fix(dbt): resolve KTAF employees to network student scope

Refs #4535"
```

---

### Task 3: Repoint the security context and the view policies

The rename and the policy edits must land in one commit. A view interpolating a
field `buildSecurityContext` no longer returns is the documented Cube Cloud
paste vector, not merely a broken filter.

**Files:**

- Modify: `src/cube/access.js:187`
- Modify: `src/cube/cube.js:153`
- Modify: `src/cube/access.test.js`
- Modify: `src/cube/cube.test.js` (the `region_key` assertions at :474, :821,
  :841-852, :874-878, :895-905, :1143)
- Modify:
  `src/cube/model/views/students/student_attendance_enrollment_daily_view.yml:277`
- Modify:
  `src/cube/model/views/students/student_attendance_enrollment_periods_view.yml:226`
- Modify:
  `src/cube/model/views/students/student_section_enrollments_view.yml:152`
- Modify:
  `src/cube/model/views/student_assessments/student_assessment_scores_view.yml:272`

**Interfaces:**

- Consumes: `dim_staff_cube_access.legal_entity_region_key` from Task 1.
- Produces: `securityContext.legal_entity_region_key` (string or null). The key
  `securityContext.region_key` no longer exists on the returned object.
  `computeAllowedAbbreviations(locationScope, regionKey, locationAbbreviation, universe)`
  keeps its signature — only its caller's argument changes.

- [ ] **Step 1: Write the failing unit tests**

Append to `src/cube/access.test.js`:

```javascript
test("buildSecurityContext exposes legal_entity_region_key, not region_key", () => {
  const ctx = a.buildSecurityContext(
    { staff_key: "S1", legal_entity_region_key: "R1" },
    [],
  );
  assert.strictEqual(ctx.legal_entity_region_key, "R1");
  assert.ok(
    !("region_key" in ctx),
    "region_key must not survive: a field no longer returned here cannot be overwritten on the Cube Cloud paste path",
  );
});

test("buildSecurityContext defaults legal_entity_region_key to null", () => {
  const ctx = a.buildSecurityContext(null, []);
  assert.strictEqual(ctx.legal_entity_region_key, null);
});
```

- [ ] **Step 2: Run them to verify they fail**

```bash
cd /workspaces/teamster/src/cube && node --test access.test.js 2>&1 | tail -n 20
```

Expected: FAIL — `ctx.legal_entity_region_key` is `undefined` and `region_key`
is still present.

- [ ] **Step 3: Rename the field in `access.js`**

In `buildSecurityContext` (line 187), replace:

```javascript
    region_key: row?.region_key ?? null,
```

with:

```javascript
    // The EMPLOYING legal entity's region, not the desk's. Student policies
    // interpolate this against locations_region_key; region maps 1:1 to legal
    // entity, so the value is still a region key.
    legal_entity_region_key: row?.legal_entity_region_key ?? null,
```

- [ ] **Step 4: Update the `cube.js` caller**

In `resolveAccess` (line 153), replace `row?.region_key,` with:

```javascript
      row?.legal_entity_region_key,
```

Leave `loadUniverses` alone — its `r.region_key` is `dim_locations.region_key`,
the location's own region, which is the correct right-hand side of the
comparison.

- [ ] **Step 5: Write the null-key deny test**

`computeAllowedAbbreviations` already guards a null key with `== null`. Pin it
so the rename cannot quietly turn it into an identity check. Append to
`src/cube/access.test.js`:

```javascript
test("computeAllowedAbbreviations: region scope with a null key denies, and does not match null-region locations", () => {
  const universe = [
    { abbreviation: "A", region_key: "R1" },
    { abbreviation: "Orphan", region_key: null },
  ];
  assert.deepStrictEqual(
    a.computeAllowedAbbreviations("region", null, null, universe),
    [],
  );
  assert.deepStrictEqual(
    a.computeAllowedAbbreviations("region", undefined, null, universe),
    [],
  );
});
```

- [ ] **Step 6: Update the four view policies**

In each of the four view files, change the `student-region` policy's
interpolation:

```yaml
values: ["{ securityContext.legal_entity_region_key }"]
```

The `member:` stays as it is —`locations_region_key` in the three student views,
bare `region_key` in `student_assessment_scores_view` (it joins `locations`
unprefixed). Those are view members, not context fields.

- [ ] **Step 7: Update the `cube.test.js` assertions**

Replace every `region_key` occurrence that refers to the **security context**
(lines 474, 821, 841-852, 874-878, 895-905, and the field-list array at 1143)
with `legal_entity_region_key`. Leave line 441 alone — that is a mocked
`dim_locations` row from `loadUniverses`, where `region_key` is correct.

- [ ] **Step 8: Run the full Cube test suite**

```bash
cd /workspaces/teamster/src/cube && node --test access.test.js cube.test.js 2>&1 | tail -n 20
```

Expected: PASS, zero failures.

- [ ] **Step 9: Assert no stale interpolation survives**

```bash
cd /workspaces/teamster && grep -rn "securityContext.region_key" src/cube --include=*.yml --include=*.js | grep -v node_modules
```

Expected: **no output**. Any hit is the paste vector from Review Focus item 1.

- [ ] **Step 10: Lint and commit**

```bash
cd /workspaces/teamster && .trunk/tools/trunk check --force --no-fix \
  src/cube/access.js src/cube/cube.js src/cube/access.test.js src/cube/cube.test.js \
  src/cube/model/views/students/student_attendance_enrollment_daily_view.yml \
  src/cube/model/views/students/student_attendance_enrollment_periods_view.yml \
  src/cube/model/views/students/student_section_enrollments_view.yml \
  src/cube/model/views/student_assessments/student_assessment_scores_view.yml </dev/null
git add -u src/cube
git commit -m "fix(cube)!: bind student RLS to the employing legal entity

Refs #4535"
```

---

### Task 4: Surface viewers whose school scope cannot resolve

Nine Miami-employed viewers hold `school` scope with a NULL
`location_abbreviation`. They already default-deny, indistinguishably from a
correct deny. This makes them visible without changing what they can see.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml`

**Interfaces:**

- Consumes: `student_location_scope` and `location_abbreviation`.
- Produces: no new columns; one warn-severity model-level test.

- [ ] **Step 1: Write the test**

Add to the model-level `data_tests:` block:

```yaml
# A school student scope whose location does not resolve grants nothing:
# the policy filters on a NULL abbreviation and the viewer is denied every
# row, which looks exactly like a correct deny at the Cube surface. Warn,
# not error — the rows are a real upstream gap in the work-assignment
# location (9 Miami-employed viewers as of 2026-09-23), so this surfaces
# them for Ops rather than blocking a deploy.
- dbt_utils.expression_is_true:
    arguments:
      expression: |
        student_location_scope != 'school'
        or location_abbreviation is not null
    config:
      severity: warn
```

- [ ] **Step 2: Run it and confirm it warns with the expected count**

```bash
cd /workspaces/teamster && uv run dbt build --select dim_staff_cube_access --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod 2>&1 | tail -n 20
```

Expected: WARN with 9 rows, build green.

- [ ] **Step 3: Lint and commit**

```bash
cd /workspaces/teamster && .trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml </dev/null
git add src/dbt/kipptaf/models/marts/dimensions/properties/dim_staff_cube_access.yml
git commit -m "test(dbt): warn when a school student scope has no location

Refs #4535"
```

---

### Task 5: Verify end to end over the SQL API, then document

The unit tests prove the wiring. Only the matrix proves the access change, and
it is the repo's sign-off surface.

**Files:**

- Modify: `.claude/rules/cube-authoring.md` (the _View access policies_ section)
- Temporary, never committed: dev-schema redirect in `src/cube/cube.js`

- [ ] **Step 1: Point `resolveAccess` at your dev-schema copy of the mart**

In `src/cube/cube.js`, change the two `kipptaf_marts.dim_staff_cube_access`
references (the `loadUniverses` department query at line 59 and the identity
query at line 137) to `zz_<username>_kipptaf_marts.dim_staff_cube_access`. Leave
`dim_locations` and `dim_staff_reporting_chain` on `kipptaf_marts` — this branch
does not change them.

- [ ] **Step 2: Start the server with auth on**

```bash
cd /workspaces/teamster/src/cube && NODE_ENV=production CUBEJS_DEV_MODE=false npm run dev > /tmp/cube-server.log 2>&1 &
```

Poll `/tmp/cube-server.log` for `is listening on 4000`. Stop it later with
`pkill -f 'cubejs[-]server'` — the bracket is required.

- [ ] **Step 3: Run the matrix over the affected viewers**

Write the 9 affected emails (the 8 KTAF viewers and the 1 Miami `region`-scoped
viewer) to a file under the session scratchpad — never `.claude/scratch/`, never
the repo.

```bash
cd /workspaces/teamster && uv run scripts/cube_rls_matrix.py \
  --viewers-file <scratchpad>/viewers-4535.txt --password local-dev-sql
```

Expected, against the baseline table: all 8 KTAF viewers return four regions
totalling 27,160, and the Miami `region`-scoped viewer returns Miami 3,912. Zero
viewers at 0 rows.

- [ ] **Step 4: Run a regression check on unaffected viewers**

Add three Region-entity viewers — one `school`-scoped, one `region`-scoped, one
`none` — and a network-scoped control to the file and re-run.

Expected: byte-identical output to the same run on `main`. A Region viewer's
scope must not move.

- [ ] **Step 5: Revert the redirect and prove it is gone**

```bash
cd /workspaces/teamster && git checkout src/cube/cube.js && grep -rn "zz_" src/cube --include=*.js --include=*.yml | grep -v node_modules
```

Expected: no output.

Task 3's rename is already committed, so `git checkout` restores it along with
everything else in HEAD — it is not lost. Confirm with
`grep -n "legal_entity_region_key" src/cube/cube.js`, which must return one hit:
the `computeAllowedAbbreviations` argument.

- [ ] **Step 6: Record the boundary in the authoring rules**

In `.claude/rules/cube-authoring.md`, in the _View access policies_ section,
replace the `student-region` description in the student-views bullet with:

```markdown
`student-region` (`row_level` on the region key of the viewer's EMPLOYING legal
entity, `securityContext.legal_entity_region_key` — never their desk's region;
FERPA binds student records to the employing LEA, and region maps 1:1 to legal
entity so the filtered member is still `locations_region_key`)
```

Add to the same bullet list:

```markdown
- **A KTAF employee is always network-scoped on student data.** KTAF's own legal
  entity enrolls no students and all 149 of its staff sit in a per-city office
  room, so a role-mapped `region` or `school` scope resolved to an empty
  allow-list and denied outright. `dim_staff_cube_access` resolves any granted
  KTAF scope to `network`; a KTAF viewer mapped to `none` stays `none`.
```

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster && .trunk/tools/trunk check --force --no-fix \
  .claude/rules/cube-authoring.md </dev/null
git add .claude/rules/cube-authoring.md
git commit -m "docs(cube): record the legal-entity student RLS boundary

Refs #4535"
```

- [ ] **Step 8: Push and open the PR**

```bash
cd /workspaces/teamster && git push -u origin cristinabaldor/fix/claude-cube-legal-entity-rls
```

Body from `.github/pull_request_template.md`, with `Closes #4535`. Summarize the
matrix result in counts only — no viewer emails, no names.
