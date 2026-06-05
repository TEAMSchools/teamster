# Cube Security Redesign — HR-Derived Access with Reporting-Chain and Org-Level Gating

**Issue:** [#4102](https://github.com/TEAMSchools/teamster/issues/4102)
**Branch:** `cristinabaldor/feat/claude-cube-security-redesign`

## Summary

Move all Cube access control into Cube itself, with access derived automatically
from HR data. Two new dbt models become the source of truth for who can see
what, replacing manual Google Workspace group enrollment and the Google Admin
Directory API entirely:

- `dim_staff_cube_access` — one row per staff email; resolves each person to a
  scope tier, student/staff access levels, per-field visibility flags, and an
  org-rank level. Derived from role (`job_function_code` × `entity` ×
  `department_type`), with a department-level special-access override.
- `dim_staff_reporting_chain` — the transitive closure of the org tree (manager
  → every direct/indirect report), used to grant detail-level access to a
  manager's own downline.

`cube.js` is simplified: `contextToGroups` queries BigQuery (no Directory API),
`queryRewrite` reads scope and reporting-chain from the cache instead of parsing
group names, and all access gating lives in the dbt models.

This supersedes the boolean-only access model in the original draft of this
spec. The driving criteria come from two source-of-truth CSVs committed
alongside this spec:

- [`assets/cube_access_job_function_levels.csv`](assets/cube_access_job_function_levels.csv)
  — role-based mapping (22 rows)
- [`assets/cube_access_department_special.csv`](assets/cube_access_department_special.csv)
  — department special-access override (8 rows)

---

## Access model

### Two independent concerns

| Concern        | Controls                | Mechanism                                |
| -------------- | ----------------------- | ---------------------------------------- |
| Access level   | Which views and columns | view `access_policy` group membership    |
| Row visibility | Which rows              | `queryRewrite` filters from cache fields |

### The two-layer staff access model

For any viewer querying **staff data**, two filters compose:

**Layer 1 — Scope (summary breadth).** Which staff rows the viewer can see at
all, at summary level. Derived from `scope_level` + `scope_key` +
`department_group`:

| `scope_level`                | Visible staff rows                                   |
| ---------------------------- | ---------------------------------------------------- |
| `network`                    | all staff (no filter)                                |
| `region`                     | staff whose `region_key` equals viewer's             |
| `school`                     | staff whose `abbreviation` equals viewer's           |
| `network + department_group` | staff whose `department_group` equals viewer's       |
| `region + department_group`  | staff in viewer's region **AND** viewer's dept group |

The compound `region + department_group` case **intersects** (AND) — a regional
director sees their department group within their region only.

**Layer 2 — Detail (reporting-chain ∩ level).** Which of the Layer-1 rows the
viewer sees at **detail / PII** level. A staff row is shown at detail only if
**both**:

- it is in the viewer's downline (`reportee_email IN dim_staff_reporting_chain`
  for the viewer as manager), **AND**
- its `job_function_level` is strictly below the viewer's (numerically greater —
  1 = Chief is highest, 6 = Teacher is lowest).

Rows in Layer 1 but not Layer 2 are visible at **summary** only. The
`summary_reporting_chain` value of `staff_access_level` is exactly this pattern:
summary across the viewer's scope, detail on the viewer's chain.

The level gate is belt-and-suspenders: in the pure reporting-chain case a
downline report is already organizationally below the viewer, but the gate also
protects the dept-group and region scopes (where the viewer sees same- or
higher-level peers at summary and must never see them at detail) and guards
against reporting-chain data gaps.

**Field flags gate columns on top of Layer 2.** `has_staff_pii`,
`has_staff_compensation`, `has_staff_observations` are **tristate** (plus a
`none` value):

| Flag value        | Field is visible for…                                        |
| ----------------- | ------------------------------------------------------------ |
| `all`             | every staff row in scope (Layer 1)                           |
| `reporting_chain` | only the viewer's Layer-2 rows (chain ∩ level)               |
| `teaching_staff`  | only staff with `job_function_code IN ('TEACH','TIR')` (ASL) |
| `none` / `FALSE`  | never                                                        |

### Student access

Independent of staff access. Governed by `student_access_level`
(`detail`/`summary`/`null`), `has_student_pii`, and the same Layer-1 location
scope. There is no reporting-chain concept for student data — a person with
`student_access_level = 'detail'` and region scope sees all students in their
region at detail.

### Survey access

`survey_access_level` (`detail`/`summary`/`null`) gates survey-domain views the
same way `student_access_level` gates student-domain views. Deferred to
whichever domain plan builds survey cubes; carried on `dim_staff_cube_access`
now so the column exists.

---

## Resolution order (`dim_staff_cube_access`)

Each active staff email resolves to exactly one access row:

```text
1. Look up the active, primary roster row by google_email
   (int_people__staff_roster, worker_status_code != 'Terminated',
    primary_indicator = true, google_email is not null).

2. If assigned_department_name ∈ special-access list (8 departments):
     → emit the special-access row verbatim.
       scope_level = network; all field flags are plain booleans → 'all' or 'none';
       staff_access_level = detail (no reporting-chain narrowing — these
       departments see all staff at detail network-wide).

3. Else:
     → emit the role-based row from the CASE on
       (job_function_code, entity, department_type).
       scope_level / staff_access_level / tristate flags / job_function_level
       per the job-function mapping.

4. No matching roster row, or null email:
     → no output row → contextToGroups returns [] → queryRewrite default-denies.
```

The department override **wins entirely** when it matches — it is uniformly
broader (network scope, mostly detail), so there is no field-by-field merge.

### Department match

Special-access `department` matches roster `assigned_department_name` by exact
string equality. Verified against current data — all 8 names resolve to active
staff (Executive, Data, Human Resources, Leadership Development, Teacher
Development, Accounting, Finance, Compliance).

---

## Source mappings (committed as CSVs)

### Role-based mapping — `job_function_code` × `entity` × `department_type`

The CASE key is the **3-part tuple**, because access varies by all three (e.g.
MGDIR differs by KTAF/Region and by instructional/non-instructional).
`job_function_level` is the org rank (1 = highest).

<!-- markdownlint-disable MD013 -->

| code  | entity | dept_type         | level | scope_level                | student | staff                   | stu_pii | staff_pii       | comp            | benefits | obs             | survey  |
| ----- | ------ | ----------------- | ----- | -------------------------- | ------- | ----------------------- | ------- | --------------- | --------------- | -------- | --------------- | ------- |
| CHIEF | —      | —                 | 1     | network                    | detail  | detail                  | TRUE    | all             | all             | none     | all             | detail  |
| EDHOS | —      | —                 | 2     | region                     | detail  | detail                  | TRUE    | all             | all             | none     | all             | detail  |
| SL    | —      | —                 | 4     | school                     | detail  | detail                  | TRUE    | all             | all             | none     | all             | detail  |
| DSO   | —      | —                 | 4     | school                     | detail  | detail                  | TRUE    | all             | all             | none     | all             | detail  |
| ASL   | —      | —                 | 5     | school                     | detail  | detail                  | TRUE    | teaching_staff  | teaching_staff  | none     | teaching_staff  | summary |
| DEAN  | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| SCOPS | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| NINST | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| TEACH | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| TIR   | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| MGDIR | KTAF   | instructional     | 3     | network                    | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| DIR   | KTAF   | instructional     | 4     | network + department_group | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| KTRGS | KTAF   | instructional     | 5     | network + department_group | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| MGDIR | KTAF   | non-instructional | 3     | network                    | summary | summary_reporting_chain | FALSE   | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| DIR   | KTAF   | non-instructional | 4     | network + department_group | summary | summary_reporting_chain | FALSE   | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| KTRGS | KTAF   | non-instructional | 5     | network + department_group | summary | summary_reporting_chain | FALSE   | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| MGDIR | Region | instructional     | 3     | region                     | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| DIR   | Region | instructional     | 4     | region + department_group  | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| KTRGS | Region | instructional     | 5     | region + department_group  | detail  | summary_reporting_chain | TRUE    | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| MGDIR | Region | non-instructional | 3     | region                     | summary | summary_reporting_chain | FALSE   | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| DIR   | Region | non-instructional | 4     | region + department_group  | summary | summary_reporting_chain | FALSE   | reporting_chain | reporting_chain | none     | reporting_chain | summary |
| KTRGS | Region | non-instructional | 5     | region + department_group  | summary | summary_reporting_chain | FALSE   | reporting_chain | reporting_chain | none     | reporting_chain | summary |

### Department special-access override

Applies regardless of `job_function_code`; network scope; flags are plain
booleans → `all` / `none`.

| department             | student | staff  | stu_pii | staff_pii | comp | benefits | obs  | survey |
| ---------------------- | ------- | ------ | ------- | --------- | ---- | -------- | ---- | ------ |
| Executive              | detail  | detail | all     | all       | all  | all      | all  | detail |
| Data                   | detail  | detail | all     | all       | all  | all      | all  | detail |
| Human Resources        | summary | detail | none    | all       | all  | all      | all  | detail |
| Leadership Development | summary | detail | none    | all       | all  | none     | all  | detail |
| Teacher Development    | detail  | detail | none    | all       | none | none     | all  | detail |
| Accounting             | detail  | detail | none    | all       | all  | all      | none | detail |
| Finance                | detail  | detail | none    | all       | all  | all      | none | detail |
| Compliance             | detail  | detail | none    | all       | all  | all      | none | detail |

<!-- markdownlint-enable MD013 -->

---

## Changes required

### 1. dbt model: `dim_staff_reporting_chain`

**Path:**
`src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql`

Transitive closure of the org tree. Grain: one row per
`(manager_email, reportee_email)`. Verified against current data: 7,005 pairs,
maximum depth 7, no cycles, terminates cleanly (2 null-manager roots at the
top).

| Column           | Type   | Description                                          |
| ---------------- | ------ | ---------------------------------------------------- |
| `manager_email`  | STRING | A staff member at or above the reportee in the tree  |
| `reportee_email` | STRING | The direct or indirect report                        |
| `depth`          | INT64  | Hops from manager to reportee (0 = self, 1 = direct) |

- **Edge source:** `int_people__staff_roster` self-reference,
  `reports_to_google_email → google_email`. Email-to-email so it joins directly
  to the JWT email claim — no surrogate-key round-trips. (Chosen over
  `dim_work_assignment_reporting_relationships`, which is keyed on `staff_key`
  and carries per-assignment SCD2 fan-out.)
- **Filter:** active staff (`worker_status_code != 'Terminated'`), non-null
  `google_email`, `primary_indicator = true`.
- **Self-pair included** (`manager_email = reportee_email`, `depth = 0`) so a
  single `reportee_email IN (...)` filter lets a manager see their own row too.
- **PK:** composite `(manager_email, reportee_email)` — composite uniqueness
  test. `depth` is the minimum hop count if multiple paths exist.
- **Recursion:** recursive CTE with a `depth < 20` cycle backstop (data is a
  clean tree; the cap is defensive only).

### 2. dbt model: `dim_staff_cube_access`

**Path:** `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`

One row per active staff `google_email`. Verified 1:1 on email for active,
non-null-email staff (1,466 emails, exactly one primary assignment each).

| Column                   | Type   | Description                                                                    |
| ------------------------ | ------ | ------------------------------------------------------------------------------ |
| `staff_google_email`     | STRING | PK — matches JWT email claim                                                   |
| `job_function_code`      | STRING | From roster (CHIEF/EDHOS/SL/…)                                                 |
| `job_function_level`     | INT64  | Org rank 1–6 (CASE on `job_function_code`)                                     |
| `entity`                 | STRING | `KTAF` / `Region` (CASE)                                                       |
| `department_type`        | STRING | `instructional` / `non-instructional` (CASE on department)                     |
| `department_group`       | STRING | Rollup of `assigned_department_name` (CASE)                                    |
| `scope_level`            | STRING | network / region / school / network+department_group / region+department_group |
| `scope_key`              | STRING | region_key, school abbreviation, or NULL (network)                             |
| `student_access_level`   | STRING | `detail` / `summary` / NULL                                                    |
| `staff_access_level`     | STRING | `detail` / `summary_reporting_chain` / NULL                                    |
| `has_student_pii`        | BOOL   | Student PII columns                                                            |
| `has_staff_pii`          | STRING | tristate: all / reporting_chain / teaching_staff / none                        |
| `has_staff_compensation` | STRING | tristate                                                                       |
| `has_staff_benefits`     | STRING | tristate (all rows `none` today; column kept for forward-compat)               |
| `has_staff_observations` | STRING | tristate                                                                       |
| `survey_access_level`    | STRING | `detail` / `summary` / NULL                                                    |

- **Derivation:** department special-access override (CASE on
  `assigned_department_name`) takes precedence; otherwise the role-based CASE on
  `(job_function_code, entity, department_type)`. Both mappings live in-SQL as
  CASE statements (not seeds), sourced from the committed CSVs.
- **`department_group` and `department_type`** are CASE statements on
  `assigned_department_name`. The exact rollup is owned by the data team — see
  open question 1.

### 3. `cube.js`: `contextToGroups`

Replace the Google Admin Directory API call with two BigQuery reads (cached to
midnight ET — BigQuery has cost, not just latency):

```javascript
contextToGroups: async ({ securityContext }) => {
  const email =
    securityContext?.email ??
    securityContext?.cubeCloud?.userAttributes?.email;
  if (!email) return [];

  // Local dev bypass unchanged (NODE_ENV !== "production" && CUBE_GROUP_MAP).

  const cached = groupCache.get(email);
  if (cached && cached.expiresAt > Date.now()) return cached.groups;

  const { BigQuery } = require("@google-cloud/bigquery");
  const bq = new BigQuery();

  const [[accessRows], [reporteeRows]] = await Promise.all([
    bq.query({
      query: `
        SELECT
          student_access_level, staff_access_level, survey_access_level,
          has_student_pii, has_staff_pii, has_staff_compensation,
          has_staff_benefits, has_staff_observations,
          scope_level, scope_key, department_group, job_function_level
        FROM kipptaf_marts.dim_staff_cube_access
        WHERE staff_google_email = @email
        LIMIT 1`,
      params: { email },
    }),
    bq.query({
      query: `
        SELECT reportee_email
        FROM kipptaf_marts.dim_staff_reporting_chain
        WHERE manager_email = @email`,
      params: { email },
    }),
  ]);

  const row = accessRows[0] ?? null;
  const groups = buildGroups(row); // emits cube-access-* group names

  groupCache.set(email, {
    groups,
    row, // full access row retained for queryRewrite
    reporteeEmails: reporteeRows.map((r) => r.reportee_email),
    expiresAt: nextMidnightEastern(),
  });

  return groups;
},
```

`buildGroups(row)` emits the view-policy group names from the resolved row:
`cube-access-student-detail` / `-summary` / `-pii`, `cube-access-staff-detail` /
`-summary` / `-pii` / `-compensation` / `-observations`, per the access levels
and flags. No Google groups are read.

### 4. `cube.js`: `queryRewrite`

Replace group-name parsing with cache reads. The cached `row` and
`reporteeEmails` drive every filter.

- **Student cubes:** strip dims/measures unless `student_access_level` is set;
  inject the location filter from `scope_level` / `scope_key` (network = none,
  region = `region_key` equals, school = `abbreviation` equals); default-deny
  empty `IN ()` when no row. Detail/summary + PII column gating is enforced by
  the view `access_policy` groups.
- **Staff cubes:** inject the **Layer-1 scope filter** (including
  `region + department_group` as an AND of two equals filters), then the
  **Layer-2 detail filter** (`staff_google_email IN reporteeEmails` AND
  `job_function_level > viewer.job_function_level`) that governs which rows
  expose PII/comp/observation columns per the tristate flags.
- **Snapshot anchor** logic and `canSwitchSqlUser` unchanged.

### 5. Cube renames, schema test, view policies (original issue scope)

Per [#4102](https://github.com/TEAMSchools/teamster/issues/4102):

- Drop `dim_` / `fct_` prefixes (`dim_staff` → `staff`, etc.); update all join
  references in YAML.
- Add `tests/cube/test_cube_schema.py` enforcing no `dim_` / `fct_` prefix on
  cube names.
- Split view `access_policy` into `-summary` / `-detail` / `-pii` group tiers.
- Replace `STUDENT_CUBES` / `STAFF_CUBES` static arrays with `isStudentMember` /
  `isStaffMember` prefix helpers.

### 6. Google Workspace group cleanup

After the redesign is live and validated (at least one full school day in
production, spot-checked per tier), retire all `cube-*` Google Workspace groups.
Access is then fully managed through the two dbt models.

---

## Design risk: per-row column masking

The tristate flags require column visibility that **depends on which row** —
e.g. compensation visible only for the viewer's reporting-chain rows, or PII
visible only for teaching staff. Cube's view `access_policy` gates columns
**globally per group**, not per-row. A group either includes a member for the
whole result set or excludes it.

This cannot be expressed in `access_policy` alone. Options for the
implementation plan to evaluate:

1. **Split rows by tier in `queryRewrite`** — not possible in a single query;
   rejected.
2. **Mask sensitive columns to NULL in the mart/view SQL** based on a
   request-time predicate. Cube cannot inject per-row SQL predicates into column
   expressions, so this would require materializing the masking in dbt against a
   viewer context — not feasible per-request. Rejected.
3. **Two view variants per staff domain** — a summary view (no sensitive
   columns) gated by Layer-1 scope, and a detail view (sensitive columns) whose
   `queryRewrite` filter restricts rows to the Layer-2 set (chain ∩ level). A
   viewer querying the detail view only ever gets their chain∩level rows, so the
   "column visible only for those rows" requirement is satisfied structurally —
   the columns live on a view that only returns the eligible rows. **Recommended
   starting point.**

The `teaching_staff` tier (ASL sees comp/obs for TEACH/TIR only) is a row
predicate on `job_function_code`, expressible as a `queryRewrite` filter on the
detail view. The plan must confirm option 3 covers all three tristate values
before committing.

---

## Open questions

1. **`department_group` and `department_type` rollup** — the exact CASE mapping
   from the 43 `assigned_department_name` values into department groups and the
   instructional/non-instructional split is owned by the data team. Draft the
   CASE skeleton with the special-access departments handled; the data team
   fills the remaining rollup before the model ships.

2. **`job_function_code` availability** — the column is being added to
   `int_people__staff_roster` (expected end of day 2026-06-05). The models
   assume it is present. Confirm the exact code values match the CSV
   (CHIEF/EDHOS/SL/DSO/ASL/DEAN/SCOPS/NINST/TEACH/TIR/MGDIR/DIR/KTRGS) before
   building.

3. **Per-row column masking** — confirm the two-view approach (design risk
   above) covers all tristate cases, or design an alternative, before
   implementing `cube.js` staff gating.

4. **Multi-location / itinerant staff** — coaches covering multiple schools get
   one `scope_key`; multi-location support is deferred to a follow-up.

---

## Implementation sequence

1. Build `dim_staff_reporting_chain` (recursive closure).
2. Build `dim_staff_cube_access` (department override → role CASE; confirm
   `job_function_code` values and department rollup first).
3. Add `-summary` / `-detail` / `-pii` tiers to view `access_policy` blocks
   (additive; safe to deploy independently).
4. Rewrite `cube.js`: `contextToGroups` (two BigQuery reads) and `queryRewrite`
   (scope + chain∩level filters); add `isStudentMember` / `isStaffMember`
   helpers.
5. Apply cube renames and add `tests/cube/test_cube_schema.py`.
6. Validate in Dev Mode with test emails at each tier (network/region/school,
   summary-only, manager with reportees, special-access department, no access).
7. Deploy to production; spot-check each tier.
8. Retire all `cube-*` Google Workspace groups.
