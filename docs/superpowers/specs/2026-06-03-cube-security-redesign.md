# Cube Security Redesign — HR-Derived Access with Reporting-Chain and Org-Level Gating

**Issue:** [#4102](https://github.com/TEAMSchools/teamster/issues/4102)
**Branch:** `cristinabaldor/feat/claude-cube-security-redesign`

## Summary

Move all Cube access control into Cube itself, with access derived automatically
from HR data. Two new dbt models become the source of truth for who can see
what, replacing manual Google Workspace group enrollment and the Google Admin
Directory API entirely:

- `dim_staff_cube_access` — one row per staff member (keyed on `staff_key`);
  resolves each person to a scope tier, student/staff access levels, per-field
  visibility flags, and an org-rank level. Derived from role
  (`job_function_code` × `entity` × `department_type`), with a department-level
  special-access override.
- `dim_staff_reporting_chain` — the transitive closure of the org tree (manager
  → every direct/indirect report), keyed on `staff_key`, used to grant
  detail-level access to a manager's own downline.

Identity keys on `staff_key` (a stable surrogate of `employee_number`)
throughout. The JWT email claim is used in exactly one place — a boundary lookup
that resolves email → `staff_key` — because Google emails are reused and are
unsafe as a persistent identity key.

`cube.js` is simplified: `contextToGroups` queries BigQuery (no Directory API),
`queryRewrite` reads scope and reporting-chain from the cache instead of parsing
group names, and all access gating lives in the dbt models.

This supersedes the boolean-only access model in the original draft of this
spec. The driving criteria are the two mapping tables in
[§ Source mappings](#source-mappings) below — the role-based mapping (22 rows)
and the department special-access override (8 rows).

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

- it is in the viewer's downline
  (`reportee_staff_key IN dim_staff_reporting_chain` for the viewer as manager),
  **AND**
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

**Field-scope columns gate columns on top of Layer 2.** `staff_pii_scope`,
`staff_compensation_scope`, `staff_observations_scope` are **enums** over a
shared vocabulary:

| Scope value       | Field is visible for…                                        |
| ----------------- | ------------------------------------------------------------ |
| `all`             | every staff row in scope (Layer 1)                           |
| `reporting_chain` | only the viewer's Layer-2 rows (chain ∩ level)               |
| `teaching_staff`  | only staff with `job_function_code IN ('TEACH','TIR')` (ASL) |
| `none`            | never                                                        |

The `_scope` suffix (not `has_`) signals these are visibility tiers, not
booleans. `all` / `none` are spelled identically across every `*_scope` column;
`reporting_chain` / `teaching_staff` are staff-domain tiers.

### Student access

Independent of staff access. Governed by `student_access_level`
(`detail`/`summary`/`none`), `student_pii_scope`, and the same Layer-1 location
scope. There is no reporting-chain concept for student data — a person with
`student_access_level = 'detail'` and region scope sees all students in their
region at detail.

`student_pii_scope` is an enum (`all` / `none` in v1). It is modeled as a scope
rather than a boolean to leave room for a future `own_roster` tier — limiting
teachers to PII for their own students — which is deferred until student section
enrollments are built out.

### Survey access — out of scope

Survey results access is **deferred to a separate plan**. Unlike student access,
surveys are scoped (some roles are limited by department), and that model needs
its own design. `dim_staff_cube_access` does **not** carry a survey column in
v1; the survey plan adds it when survey cubes are built. The job groupings
explorer carries a survey-access value per role — it is ignored for now.

---

## Resolution order (`dim_staff_cube_access`)

The model has one row per active primary staff member, keyed on `staff_key`
(`generate_surrogate_key([employee_number])`). `google_email` is carried as a
populated lookup column so `contextToGroups` can resolve the JWT claim. Each row
resolves as:

```text
1. Source the active, primary roster row
   (int_people__staff_roster, worker_status_code != 'Terminated',
    primary_indicator = true). Set staff_key from employee_number;
    carry google_email for the boundary lookup.

2. If assigned_department_name ∈ special-access list (8 departments):
     → emit the special-access row verbatim.
       scope_level = network; every *_scope is unconditional 'all' or 'none';
       staff_access_level = detail (no reporting-chain narrowing — these
       departments see all staff at detail network-wide).

3. Else:
     → emit the role-based row from the CASE on
       (job_function_code, entity, department_type).
       scope_level / staff_access_level / *_scope columns / job_function_level
       per the job-function mapping.

4. JWT email matches no row (terminated, recycled-to-nobody, contractor,
   service account), or the row has a null email:
     → no resolution → contextToGroups returns [] → queryRewrite default-denies.
```

The department override **wins entirely** when it matches — it is uniformly
broader (network scope, mostly detail), so there is no field-by-field merge.

### Department match

Special-access `department` matches roster `assigned_department_name` by exact
string equality. Verified against current data — all 8 names resolve to active
staff (Executive, Data, Human Resources, Leadership Development, Teacher
Development, Accounting, Finance, Compliance).

---

## Source mappings

The canonical reference for job groupings and their org levels is the
**[job groupings explorer](https://teamschools.github.io/job_groupings/website/explorer.html)**.
The two tables below are the access criteria derived from it; when the explorer
changes, update these tables (and the CASE statements) to match.

### Role-based mapping — `job_function_code` × `entity` × `department_type`

The CASE key is the **3-part tuple**, because access varies by all three (e.g.
MGDIR differs by KTAF/Region and by instructional/non-instructional).
`job_function_level` is the org rank (1 = highest).

<!-- markdownlint-disable MD013 -->

Column headers map to model columns: `student` = `student_access_level`, `staff`
= `staff_access_level`, `stu_pii` = `student_pii_scope`, `staff_pii` =
`staff_pii_scope`, `comp` = `staff_compensation_scope`, `benefits` =
`staff_benefits_scope`, `obs` = `staff_observations_scope`.

| code  | entity | dept_type         | level | scope_level                | student | staff                   | stu_pii | staff_pii       | comp            | benefits | obs             |
| ----- | ------ | ----------------- | ----- | -------------------------- | ------- | ----------------------- | ------- | --------------- | --------------- | -------- | --------------- |
| CHIEF | —      | —                 | 1     | network                    | detail  | detail                  | all     | all             | all             | none     | all             |
| EDHOS | —      | —                 | 2     | region                     | detail  | detail                  | all     | all             | all             | none     | all             |
| SL    | —      | —                 | 4     | school                     | detail  | detail                  | all     | all             | all             | none     | all             |
| DSO   | —      | —                 | 4     | school                     | detail  | detail                  | all     | all             | all             | none     | all             |
| ASL   | —      | —                 | 5     | school                     | detail  | detail                  | all     | teaching_staff  | teaching_staff  | none     | teaching_staff  |
| DEAN  | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| SCOPS | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| NINST | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| TEACH | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| TIR   | —      | —                 | 6     | school                     | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| MGDIR | KTAF   | instructional     | 3     | network                    | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| DIR   | KTAF   | instructional     | 4     | network + department_group | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| KTRGS | KTAF   | instructional     | 5     | network + department_group | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| MGDIR | KTAF   | non-instructional | 3     | network                    | summary | summary_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| DIR   | KTAF   | non-instructional | 4     | network + department_group | summary | summary_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| KTRGS | KTAF   | non-instructional | 5     | network + department_group | summary | summary_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| MGDIR | Region | instructional     | 3     | region                     | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| DIR   | Region | instructional     | 4     | region + department_group  | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| KTRGS | Region | instructional     | 5     | region + department_group  | detail  | summary_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| MGDIR | Region | non-instructional | 3     | region                     | summary | summary_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| DIR   | Region | non-instructional | 4     | region + department_group  | summary | summary_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| KTRGS | Region | non-instructional | 5     | region + department_group  | summary | summary_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |

### Department special-access override

Applies regardless of `job_function_code`; network scope. Every `*_scope` value
is the unconditional `all` / `none` (never `reporting_chain` / `teaching_staff`)
— these departments see the field for all rows in scope or not at all. Same
column-header mapping as the role table above.

| department             | student | staff  | stu_pii | staff_pii | comp | benefits | obs  |
| ---------------------- | ------- | ------ | ------- | --------- | ---- | -------- | ---- |
| Executive              | detail  | detail | all     | all       | all  | all      | all  |
| Data                   | detail  | detail | all     | all       | all  | all      | all  |
| Human Resources        | summary | detail | none    | all       | all  | all      | all  |
| Leadership Development | summary | detail | none    | all       | all  | none     | all  |
| Teacher Development    | detail  | detail | none    | all       | none | none     | all  |
| Accounting             | detail  | detail | none    | all       | all  | all      | none |
| Finance                | detail  | detail | none    | all       | all  | all      | none |
| Compliance             | detail  | detail | none    | all       | all  | all      | none |

<!-- markdownlint-enable MD013 -->

---

## Changes required

### 1. dbt model: `dim_staff_reporting_chain`

**Path:**
`src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql`

Transitive closure of the org tree. Grain: one row per
`(manager_staff_key, reportee_staff_key)`. Verified against current data: 7,005
pairs, maximum depth 7, no cycles, terminates cleanly (org-root managers at the
top).

| Column               | Type   | Description                                          |
| -------------------- | ------ | ---------------------------------------------------- |
| `manager_staff_key`  | STRING | A staff member at or above the reportee in the tree  |
| `reportee_staff_key` | STRING | The direct or indirect report                        |
| `depth`              | INT64  | Hops from manager to reportee (0 = self, 1 = direct) |

- **Key on `staff_key`, not email.** Google emails are reused (a departed
  employee's address can be reassigned to a new hire), so email is unsafe as a
  stable identity key. `staff_key` —
  `generate_surrogate_key([employee_number])`, the same surrogate `dim_staff`
  uses — is stable for the life of an employee record. Email is used in exactly
  one place: the JWT-boundary lookup in `contextToGroups` (see §3).
- **Edge source:** `int_people__staff_roster` self-reference,
  `reports_to_employee_number → employee_number`, each hashed to `staff_key` via
  the single-input `generate_surrogate_key` matching `dim_staff`. (Chosen over
  `dim_work_assignment_reporting_relationships`, which carries per-assignment
  SCD2 fan-out.)
- **Filter:** active staff (`worker_status_code != 'Terminated'`),
  `primary_indicator = true`. `employee_number` is non-null and 1:1 for active
  primary rows (verified: 1,490 rows, 1,490 distinct, 0 null).
- **Self-pair included** (`manager_staff_key = reportee_staff_key`, `depth = 0`)
  so a single `reportee_staff_key IN (...)` filter lets a manager see their own
  row too.
- **PK:** composite `(manager_staff_key, reportee_staff_key)` — composite
  uniqueness test. `depth` is the minimum hop count if multiple paths exist.
- **Recursion:** recursive CTE over the
  `employee_number → reports_to_employee_number` edge with a `depth < 20` cycle
  backstop (data is a clean tree; the cap is defensive only); hash to
  `staff_key` after the closure.
- **Hash discipline:** `staff_key` here must hash identically to
  `dim_staff.staff_key` (single input `employee_number`). Per `marts/CLAUDE.md`,
  any change to that composition must migrate producer and all consumers
  together.

### 2. dbt model: `dim_staff_cube_access`

**Path:** `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`

One row per active staff `staff_key`. Verified 1:1 on `employee_number` for
active primary staff (1,490 rows, 1,490 distinct, 0 null).

| Column                     | Type   | Description                                                                                                                             |
| -------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `staff_key`                | STRING | PK — `generate_surrogate_key([employee_number])`, matches `dim_staff`                                                                   |
| `google_email`             | STRING | Resolve-only lookup for the JWT boundary; populated from the active+primary row so a recycled address can't resolve to a stale identity |
| `job_function_code`        | STRING | From roster (CHIEF/EDHOS/SL/…)                                                                                                          |
| `job_function_level`       | INT64  | Org rank 1–6 (CASE on `job_function_code`)                                                                                              |
| `entity`                   | STRING | `KTAF` / `Region` (CASE)                                                                                                                |
| `department_type`          | STRING | `instructional` / `non-instructional` (CASE on department)                                                                              |
| `department_group`         | STRING | Rollup of `assigned_department_name` (CASE)                                                                                             |
| `scope_level`              | STRING | network / region / school / network+department_group / region+department_group                                                          |
| `scope_key`                | STRING | region_key, school abbreviation, or NULL (network)                                                                                      |
| `student_access_level`     | STRING | `detail` / `summary` / `none`                                                                                                           |
| `staff_access_level`       | STRING | `detail` / `summary_reporting_chain` / `none`                                                                                           |
| `student_pii_scope`        | STRING | enum: `all` / `none` (future `own_roster` deferred)                                                                                     |
| `staff_pii_scope`          | STRING | enum: `all` / `reporting_chain` / `teaching_staff` / `none`                                                                             |
| `staff_compensation_scope` | STRING | enum (same vocabulary)                                                                                                                  |
| `staff_benefits_scope`     | STRING | enum (all rows `none` today; column kept for forward-compat)                                                                            |
| `staff_observations_scope` | STRING | enum (same vocabulary)                                                                                                                  |

- **Derivation:** department special-access override (CASE on
  `assigned_department_name`) takes precedence; otherwise the role-based CASE on
  `(job_function_code, entity, department_type)`. Both mappings live in-SQL as
  CASE statements (not seeds), sourced from the committed CSVs.
- **`department_group` and `department_type`** are CASE statements on
  `assigned_department_name`. The exact rollup is owned by the data team — see
  open question 1.
- **No-access sentinel:** the three `*_access_level` columns emit the string
  `'none'` (never NULL) when a role grants no access to that domain — `'none'`
  reads as an intentional denial, NULL as missing data. Any CASE fall-through
  must coalesce to `'none'`. A person with no resolvable row at all is a
  different case: no row is emitted, and `contextToGroups` default-denies.

### 3. `cube.js`: `contextToGroups`

Replace the Google Admin Directory API call with BigQuery reads (cached to
midnight ET — BigQuery has cost, not just latency). **Email is used only here**,
to resolve the JWT claim to a stable `staff_key`; everything downstream keys on
`staff_key`. The access read is filtered to the active+primary row, so a
recycled email cannot resolve to a departed employee's identity.

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

  // 1. Resolve email → staff_key + access row (active+primary row only).
  const [accessRows] = await bq.query({
    query: `
      SELECT
        staff_key,
        student_access_level, staff_access_level,
        student_pii_scope, staff_pii_scope, staff_compensation_scope,
        staff_benefits_scope, staff_observations_scope,
        scope_level, scope_key, department_group, job_function_level
      FROM kipptaf_marts.dim_staff_cube_access
      WHERE google_email = @email
      LIMIT 1`,
    params: { email },
  });
  const row = accessRows[0] ?? null;

  // 2. Reporting chain keyed on the resolved staff_key (not email).
  let reporteeStaffKeys = [];
  if (row?.staff_key) {
    const [reporteeRows] = await bq.query({
      query: `
        SELECT reportee_staff_key
        FROM kipptaf_marts.dim_staff_reporting_chain
        WHERE manager_staff_key = @staffKey`,
      params: { staffKey: row.staff_key },
    });
    reporteeStaffKeys = reporteeRows.map((r) => r.reportee_staff_key);
  }

  const groups = buildGroups(row); // emits cube-access-* group names

  groupCache.set(email, {
    groups,
    row, // full access row retained for queryRewrite (carries staff_key)
    reporteeStaffKeys,
    expiresAt: nextMidnightEastern(),
  });

  return groups;
},
```

The two reads are now sequential (the chain read needs the resolved
`staff_key`), but both hit small tables on the cached path once per user per
day. `buildGroups(row)` emits the view-policy group names from the resolved row:
`cube-access-student-detail` / `-summary` / `-pii`, `cube-access-staff-detail` /
`-summary` / `-pii` / `-compensation` / `-observations`, per the access levels
and flags. No Google groups are read.

### 4. `cube.js`: `queryRewrite`

Replace group-name parsing with cache reads. The cached `row` and
`reporteeStaffKeys` drive every filter.

- **Student cubes:** strip dims/measures unless `student_access_level` is set;
  inject the location filter from `scope_level` / `scope_key` (network = none,
  region = `region_key` equals, school = `abbreviation` equals); default-deny
  empty `IN ()` when no row. Detail/summary + PII column gating is enforced by
  the view `access_policy` groups.
- **Staff cubes:** inject the **Layer-1 scope filter** (including
  `region + department_group` as an AND of two equals filters), then the
  **Layer-2 detail filter** (`staff.staff_key IN reporteeStaffKeys` AND
  `job_function_level > viewer.job_function_level`) that governs which rows
  expose PII/comp/observation columns per the `*_scope` columns. The staff cube
  and detail view expose `staff_key` for this filter.
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

## View pattern: align with the existing detail/summary split

The student domain already implements the detail/summary pattern this design
relies on. Confirmed against
[`attendance_detail.yml`](../../../src/cube/model/views/attendance/attendance_detail.yml)
and
[`attendance_summary.yml`](../../../src/cube/model/views/attendance/attendance_summary.yml):

- **`attendance_detail`** is a separate view that exposes row-level identifiers
  (`student_key`, `full_name`, `birth_date`, `*_student_identifier`). Its
  `access_policy` has **two tiers**: `cube-access-student-data` with
  `member_level.excludes` listing the PII members, and `cube-access-student-pii`
  with `includes: "*"`.
- **`attendance_summary`** is a separate view that simply **omits** the
  identifier columns (no `student_key` / `full_name`) and carries demographic
  fields as aggregate breakdowns only. Single `cube-access-student-data` tier,
  `includes: "*"`, no PII tier needed because the columns aren't present.

The staff domain follows the same shape: a `staff_detail` view (row-level, with
sensitive columns) and a `staff_summary` view (no row-level identifiers or
sensitive HR columns). The student tiers map directly onto the new group names
from `dim_staff_cube_access` (`cube-access-student-detail` / `-summary` /
`-pii`); the staff tiers add `cube-access-staff-detail` / `-summary` / `-pii` /
`-compensation` / `-observations`.

### What this pattern covers — and the one gap it does not

The attendance pattern gates **columns globally per group**: with
`cube-access-student-pii`, a viewer sees the PII columns for **every** row the
query returns; without it, for none. That is exactly right for the student PII
scope (`student_pii_scope`) and for any **all-or-nothing** staff scope (`all` /
`none`) — these are whole-column grants and map cleanly onto an `excludes:`
tier.

The gap is the **`reporting_chain` and `teaching_staff` scope values**, which
require a sensitive column visible **for some rows and not others in the same
result set** (comp for downline rows only; comp/obs for TEACH/TIR rows only).
`access_policy` `excludes:`/`includes:` is whole-column and cannot express this.

**Resolution — row restriction, not column masking.** Rather than mask columns
per-row, restrict the **rows** so the column grant is correct for the whole set:

- A viewer whose `staff_compensation_scope = 'reporting_chain'` gets the
  `cube-access-staff-compensation` group (comp columns visible) **and** a
  `queryRewrite` row filter limiting the staff result to their Layer-2 set
  (`staff.staff_key IN reporteeStaffKeys` AND level-below). Comp is then
  correctly visible for exactly the rows returned.
- A viewer whose `staff_compensation_scope = 'teaching_staff'` (ASL) gets the
  comp group plus a `queryRewrite` filter
  `job_function_code IN ('TEACH','TIR')`.

This reuses the proven attendance mechanism (group → column grant) and adds the
row filter in `queryRewrite` — the same place location scope is already
injected. The tradeoff: a viewer cannot, in one query, see comp for their
downline **and** non-comp summary rows for their wider scope — they get the
row-restricted detail set when comp is requested. The plan must confirm this
single-query restriction is acceptable to the data team (it matches how a
manager would naturally query "my team's comp"), and that all three scope values
reduce to a group + row-filter pair.

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

3. **Tristate row restriction** — the resolution above (group + `queryRewrite`
   row filter) restricts the staff result set when a `reporting_chain` /
   `teaching_staff` sensitive field is requested. Confirm with the data team
   that this single-query restriction is acceptable (a viewer gets their
   chain∩level rows when querying comp, not their full scope) before
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
