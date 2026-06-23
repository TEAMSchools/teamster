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

| `scope_level`              | Visible staff rows                                   |
| -------------------------- | ---------------------------------------------------- |
| `network`                  | all staff (no filter)                                |
| `region`                   | staff whose `region_key` equals viewer's             |
| `school`                   | staff whose `abbreviation` equals viewer's           |
| `network_department_group` | staff whose `department_group` equals viewer's       |
| `region_department_group`  | staff in viewer's region **AND** viewer's dept group |
| `none`                     | nothing — default deny                               |

The compound `region_department_group` case **intersects** (AND) — a regional
director sees their department group within their region only.

`network` is the broadest grant and is **only ever set intentionally** by the
role/department mapping (e.g. CHIEF, special-access departments). A person who
fails to match any region/school does **not** fall through to `network` — they
resolve to `scope_level = 'none'` (or no row at all), which denies. This is the
reason `scope_key` uses an explicit `'network'` sentinel rather than NULL: a
NULL key must never be confusable with an unmatched fallthrough.

**Layer 2 — Detail visibility.** Which of the Layer-1 rows the viewer sees at
**detail / PII** level. A staff row `T` is shown at detail to viewer `V` when
**either** branch holds — an **OR**, not an AND:

- **`T` reports to `V`** — `T.staff_key ∈ V`'s downline
  (`dim_staff_reporting_chain`). True at **any** level, so a manager always sees
  their own reports even when they share `V`'s rank (a Dean and the Teachers
  reporting to them are both level 6). This is the "you can never be hidden from
  your own manager" guarantee.
- **`T` is below `V` in rank _and_ `V` holds a leadership grant** —
  `T.job_function_level > V.job_function_level` (numerically greater = lower
  rank; 1 = Chief, 6 = Teacher) **and**
  `V.staff_access_level = detail_below_rank`. This lets leadership roles (CHIEF,
  EDHOS, SL, DSO, ASL) see everyone below them within their scope — even outside
  their chain — for observation norming and resource sharing.

Same-level (and higher) peers who do **not** report to `V` satisfy neither
branch and are never shown at detail — that is what keeps Chiefs from seeing
other Chiefs and EDHOSs from seeing other EDHOSs. Rows in Layer 1 but not Layer
2 are visible at **summary** only.

`staff_access_level` selects the gate:

<!-- markdownlint-disable MD013 -->

| Value                    | Detail rows (within Layer-1 scope)                   | Roles                                |
| ------------------------ | ---------------------------------------------------- | ------------------------------------ |
| `detail_below_rank`      | `job_function_level` below viewer **OR** in downline | leadership (CHIEF/EDHOS/SL/DSO/ASL)  |
| `detail_reporting_chain` | in downline only                                     | managers and individual contributors |
| `detail`                 | every row in scope (ungated)                         | special-access departments only      |
| `none`                   | nothing                                              | default deny                         |

<!-- markdownlint-enable MD013 -->

`detail` is the deliberate exception — special-access departments (HR,
Executive, Data, …) need org-wide visibility regardless of rank or chain.

**Field-scope columns gate columns on top of Layer 2.** `staff_pii_scope`,
`staff_compensation_scope`, `staff_observations_scope` are **enums** over a
shared vocabulary:

<!-- markdownlint-disable MD013 -->

| Scope value       | Field is visible for…                                        |
| ----------------- | ------------------------------------------------------------ |
| `all`             | every row the viewer sees at detail (their Layer-2 set)      |
| `reporting_chain` | only the viewer's downline rows                              |
| `teaching_staff`  | only staff with `job_function_code IN ('TEACH','TIR')` (ASL) |
| `none`            | never                                                        |

<!-- markdownlint-enable MD013 -->

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
1. Assemble the current primary assignment from the marts star
   (dim_staff_work_assignments + dim_work_assignment_{jobs,
    organizational_units, locations, primary, status} + dim_staff),
    all is_current = true, is_primary_position = true,
    status_name != 'Terminated'. staff_key comes from
    dim_staff_work_assignments; google_email from dim_staff;
    job_function_code, department_name, location_key from the child dims.

2. If department_name ∈ special-access list (8 departments):
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

Special-access `department` matches the current assignment's `department_name`
(from `dim_work_assignment_organizational_units`, `assignment_type = 'home'`) by
exact string equality. Verified against current data — all 8 names resolve to
active staff (Executive, Data, Human Resources, Leadership Development, Teacher
Development, Accounting, Finance, Compliance). Note `Accounting and Compliance`
(1 active) is **not** matched by either `Accounting` or `Compliance` under exact
equality — it falls to the role-based path; see the data-quality follow-up.

---

## Source mappings

The canonical reference for job groupings and their org levels is the
**[job groupings explorer](https://teamschools.github.io/job_groupings/website/explorer.html)**.
The two tables below are the access criteria derived from it. They are
**materialized as Google Sheets crosswalks** (matching the repo's lookup-table
convention — there are no dbt seeds; hand-maintained lookups are `GOOGLE_SHEETS`
external sources → `stg_google_sheets__*_crosswalk` staging models). The data
team edits the sheet; `stage_external_sources --target staging`

- `dbt build` re-stage. `dim_staff_cube_access` joins the crosswalks — the
  tables below are the authoritative content, not in-SQL `CASE` blocks. See
  [§ Source layer](#source-layer--built-entirely-from-marts) and open
  question 1.

### Role-based mapping — `job_function_code` × `entity` × `department_type`

The CASE key is the **3-part tuple**, because access varies by all three (e.g.
MGDIR differs by KTAF/Region and by instructional/non-instructional).
`job_function_level` is the org rank (1 = highest).

<!-- markdownlint-disable MD013 -->

Column headers map to model columns: `student` = `student_access_level`, `staff`
= `staff_access_level`, `stu_pii` = `student_pii_scope`, `staff_pii` =
`staff_pii_scope`, `comp` = `staff_compensation_scope`, `benefits` =
`staff_benefits_scope`, `obs` = `staff_observations_scope`.

| code  | entity | dept_type         | level | scope_level              | student | staff                  | stu_pii | staff_pii       | comp            | benefits | obs             |
| ----- | ------ | ----------------- | ----- | ------------------------ | ------- | ---------------------- | ------- | --------------- | --------------- | -------- | --------------- |
| CHIEF | —      | —                 | 1     | network                  | detail  | detail_below_rank      | all     | all             | all             | none     | all             |
| EDHOS | —      | —                 | 2     | region                   | detail  | detail_below_rank      | all     | all             | all             | none     | all             |
| SL    | —      | —                 | 4     | school                   | detail  | detail_below_rank      | all     | all             | all             | none     | all             |
| DSO   | —      | —                 | 4     | school                   | detail  | detail_below_rank      | all     | all             | all             | none     | all             |
| ASL   | —      | —                 | 5     | school                   | detail  | detail_below_rank      | all     | teaching_staff  | teaching_staff  | none     | teaching_staff  |
| DEAN  | —      | —                 | 6     | school                   | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| SCOPS | —      | —                 | 6     | school                   | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| NINST | —      | —                 | 6     | school                   | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| TEACH | —      | —                 | 6     | school                   | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| TIR   | —      | —                 | 6     | school                   | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| MGDIR | KTAF   | instructional     | 3     | network                  | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| DIR   | KTAF   | instructional     | 4     | network_department_group | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| KTRGS | KTAF   | instructional     | 5     | network_department_group | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| MGDIR | KTAF   | non-instructional | 3     | network                  | summary | detail_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| DIR   | KTAF   | non-instructional | 4     | network_department_group | summary | detail_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| KTRGS | KTAF   | non-instructional | 5     | network_department_group | summary | detail_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| MGDIR | Region | instructional     | 3     | region                   | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| DIR   | Region | instructional     | 4     | region_department_group  | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| KTRGS | Region | instructional     | 5     | region_department_group  | detail  | detail_reporting_chain | all     | reporting_chain | reporting_chain | none     | reporting_chain |
| MGDIR | Region | non-instructional | 3     | region                   | summary | detail_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| DIR   | Region | non-instructional | 4     | region_department_group  | summary | detail_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |
| KTRGS | Region | non-instructional | 5     | region_department_group  | summary | detail_reporting_chain | none    | reporting_chain | reporting_chain | none     | reporting_chain |

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

### Source layer — built entirely from marts

Both new models are assembled **intra-mart** from the existing work-assignment
dimensional star, filtered to each staff member's **current primary**
assignment. They do **not** `ref()` `int_people__staff_roster` —
`marts/CLAUDE.md` forbids `ref()`-ing staging/intermediate/reporting _into_
marts and explicitly permits intra-mart refs (e.g.
`fct_staff_attrition → dim_staff_status`), so the marts path is the blessed one.

The star (all keyed on `work_assignment_key`, all filtered `is_current = true`,
joined to the current primary assignment):

<!-- markdownlint-disable MD013 -->

| Source mart                                   | Supplies                                                        |
| --------------------------------------------- | --------------------------------------------------------------- |
| `dim_staff_work_assignments`                  | `staff_key` ↔ `work_assignment_key`, `is_current`               |
| `dim_staff`                                   | `google_email`, person attributes                               |
| `dim_work_assignment_jobs`                    | `job_function_code` (see prereq below), position                |
| `dim_work_assignment_organizational_units`    | `department_name`, `business_unit_name` (`type='home'`)         |
| `dim_work_assignment_locations`               | `location_key` → `dim_locations` (`region_key`, `abbreviation`) |
| `dim_work_assignment_primary`                 | `is_primary_position`                                           |
| `dim_work_assignment_status`                  | `status_name` (active filter)                                   |
| `dim_work_assignment_reporting_relationships` | `manager_staff_key` (per assignment)                            |

<!-- markdownlint-enable MD013 -->

This is the same set the `staff_work_history` Cube already SCD2-intersects — a
proven assembly pattern. **Current role only:** access reflects the person's
present position, never employment history; every join filters
`is_current = true` and the primary assignment (`is_primary_position = true`).
Active filter: `status_name != 'Terminated'` (keeps staff on Leave in their
role). `staff_key` stays `generate_surrogate_key([employee_number])`, identical
to `dim_staff`.

#### Prerequisite: `job_function_code` on `dim_work_assignment_jobs`

PR [#4182](https://github.com/TEAMSchools/teamster/pull/4182) propagated only
the job-function **label** (`coalesce(longname, shortname)`) up to the roster
(`job_function`) and to `dim_work_assignment_jobs` (`job_function_description`).
The stable **code** (`job_function_code__code_value` — `CHIEF`/`SL`/`TEACH`/…)
stops at `int_adp_workforce_now__workers__work_assignments`. Add it to
`dim_work_assignment_jobs` as `job_function_code` (passthrough select; **not** a
`generate_surrogate_key` input → no `work_assignment_job_key` hash churn). All
access keys use the code, not the free-text label.

### 1. dbt model: `dim_staff_reporting_chain`

**Path:**
`src/dbt/kipptaf/models/marts/dimensions/dim_staff_reporting_chain.sql`

Transitive closure of the **current** org tree. Grain: one row per
`(manager_staff_key, reportee_staff_key)`. Closure stats (pairs / max depth) to
be re-verified against the marts edge set at build time; the org is a clean tree
(no cycles) terminating at org-root managers.

<!-- markdownlint-disable MD013 -->

| Column               | Type   | Description                                          |
| -------------------- | ------ | ---------------------------------------------------- |
| `manager_staff_key`  | STRING | A staff member at or above the reportee in the tree  |
| `reportee_staff_key` | STRING | The direct or indirect report                        |
| `depth`              | INT64  | Hops from manager to reportee (0 = self, 1 = direct) |

<!-- markdownlint-enable MD013 -->

- **Key on `staff_key`, not email.** Google emails are reused (a departed
  employee's address can be reassigned to a new hire), so email is unsafe as a
  stable identity key. `staff_key` —
  `generate_surrogate_key([employee_number])`, the same surrogate `dim_staff`
  uses — is stable for the life of an employee record. Email is used in exactly
  one place: the JWT-boundary lookup in `contextToGroups` (see §3).
- **Edge source (marts, current only):** `dim_staff_work_assignments`
  (`is_current`) joined to `dim_work_assignment_primary`
  (`is_current, is_primary_position`) and
  `dim_work_assignment_reporting_relationships` (`is_current`) yields the
  current reportee→manager edge set
  `(swa.staff_key AS reportee_staff_key, rr.manager_staff_key)`. Both sides are
  already `staff_key` (the reporting dim carries `manager_staff_key`;
  `dim_staff_work_assignments` carries the reportee `staff_key`) — no re-hashing
  needed. Filtering to `is_current` makes the closure reflect today's org only.
- **Self-pair included** (`manager_staff_key = reportee_staff_key`, `depth = 0`)
  so a single `reportee_staff_key IN (...)` filter lets a manager see their own
  row too.
- **PK:** composite `(manager_staff_key, reportee_staff_key)` — composite
  uniqueness test. `depth` is the minimum hop count if multiple paths exist.
- **Recursion:** recursive CTE over the current edge set with a `depth < 20`
  cycle backstop (data is a clean tree; the cap is defensive only).
- **Hash discipline:** `staff_key` here must hash identically to
  `dim_staff.staff_key` (single input `employee_number`). Per `marts/CLAUDE.md`,
  any change to that composition must migrate producer and all consumers
  together.

### 2. dbt model: `dim_staff_cube_access`

**Path:** `src/dbt/kipptaf/models/marts/dimensions/dim_staff_cube_access.sql`

One row per active staff `staff_key`. Verified 1:1 on `staff_key` for active
primary staff (1,526 rows as of 2026-06-23, 1:1, 0 null).

<!-- markdownlint-disable MD013 -->

| Column                     | Type   | Description                                                                                                                             |
| -------------------------- | ------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `staff_key`                | STRING | PK — `generate_surrogate_key([employee_number])`, matches `dim_staff`                                                                   |
| `google_email`             | STRING | Resolve-only lookup for the JWT boundary; populated from the active+primary row so a recycled address can't resolve to a stale identity |
| `job_function_code`        | STRING | From `dim_work_assignment_jobs` (prereq) — CHIEF/EDHOS/SL/…                                                                             |
| `job_function_level`       | INT64  | Org rank 1–6 (from role crosswalk)                                                                                                      |
| `entity`                   | STRING | `KTAF` / `Region` — derived from `business_unit_name` (`KIPP TEAM and Family Schools Inc.` → KTAF, else Region)                         |
| `department_type`          | STRING | `instructional` / `non-instructional` (from rollup crosswalk)                                                                           |
| `department_group`         | STRING | Rollup of `department_name` (from rollup crosswalk)                                                                                     |
| `scope_level`              | STRING | `network` / `region` / `school` / `network_department_group` / `region_department_group` / `none` (deny)                                |
| `scope_key`                | STRING | sentinel `'network'`, a `region_key` (resolved via `dim_locations`), a school `abbreviation`, or `'none'` — never NULL                  |
| `student_access_level`     | STRING | `detail` / `summary` / `none`                                                                                                           |
| `staff_access_level`       | STRING | `detail` / `detail_below_rank` / `detail_reporting_chain` / `none` (see Layer 2)                                                        |
| `student_pii_scope`        | STRING | enum: `all` / `none` (future `own_roster` deferred)                                                                                     |
| `staff_pii_scope`          | STRING | enum: `all` / `reporting_chain` / `teaching_staff` / `none`                                                                             |
| `staff_compensation_scope` | STRING | enum (same vocabulary)                                                                                                                  |
| `staff_benefits_scope`     | STRING | enum (all rows `none` today; column kept for forward-compat)                                                                            |
| `staff_observations_scope` | STRING | enum (same vocabulary)                                                                                                                  |

<!-- markdownlint-enable MD013 -->

- **Derivation:** join the department special-access crosswalk on
  `department_name` (takes precedence when matched); otherwise join the
  role-based crosswalk on `(job_function_code, entity, department_type)`. The
  override wins entirely when matched (no field-by-field merge). Mappings are
  Google Sheets crosswalks (see [§ Source mappings](#source-mappings)), not
  in-SQL `CASE`.
- **`department_group` and `department_type`** come from the department rollup
  crosswalk keyed on `department_name`. The exact rollup is owned by the data
  team — see open question 1.
- **`entity`** is derived in-model from `business_unit_name` (from
  `dim_work_assignment_organizational_units`):
  `KIPP TEAM and Family Schools Inc.` → `KTAF`, all other business units →
  `Region`. It only affects the MGDIR / DIR / KTRGS role rows.
- **`scope_key` for region scope** is resolved by joining the current
  assignment's `location_key` (`dim_work_assignment_locations`) to
  `dim_locations` for `region_key` (an opaque surrogate) and the school
  `abbreviation`. An unresolved location → `scope_level = 'none'`.
- **No-access sentinel:** the three `*_access_level` columns emit the string
  `'none'` (never NULL) when a role grants no access to that domain — `'none'`
  reads as an intentional denial, NULL as missing data. Any crosswalk non-match
  must coalesce to `'none'`. A person with no resolvable row at all is a
  different case: no row is emitted, and `contextToGroups` default-denies.
- **Default-deny population (intentional).** Some active+primary staff resolve
  to `scope_level = 'none'` or emit no row by design: NULL `job_function` (~27
  active+primary, 2026-06-23), NULL `google_email` (~52 — cannot be resolved by
  the JWT boundary at all), `INTRN` (level 7, no role-table row, ~42), and the
  unmatched `Accounting and Compliance` department. These are denied until their
  source HR records are corrected — tracked by the data-quality issue (see
  [§ Implementation sequence](#implementation-sequence)).

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
day. `buildGroups(row)` emits the view-policy group names from the resolved row.
**To avoid the `member_level` intersection trap (see § View pattern), staff
column visibility resolves to exactly ONE composite group per viewer** — not
additive per-field groups — so each view matches a single `access_policy` block.
Student tiers stay `cube-access-student-detail` / `-summary` / `-pii`. No Google
groups are read.

### 4. `cube.js`: `queryRewrite`

Replace group-name parsing with cache reads. The cached `row` and
`reporteeStaffKeys` drive every filter.

- **Student cubes:** strip dims/measures unless `student_access_level` is
  `detail`/`summary`; inject the location filter by `scope_level` (`network` =
  no filter, `region` = `region_key` equals `scope_key`, `school` =
  `abbreviation` equals `scope_key`); default-deny empty `IN ()` when
  `scope_level` is `none` or there is no row. Detail/summary + PII column gating
  is enforced by the view `access_policy` groups.
- **Staff cubes:** inject the **Layer-1 scope filter** (including
  `region_department_group` as an AND of two equals filters), then the **Layer-2
  detail filter** per the viewer's `staff_access_level`:
  - `detail_below_rank` → `staff.staff_key IN reporteeStaffKeys` **OR**
    `staff.job_function_level > viewer.job_function_level`;
  - `detail_reporting_chain` → `staff.staff_key IN reporteeStaffKeys`;
  - `detail` → no Layer-2 filter (all scope rows).

  Column visibility for the all/none scopes is handled by the single composite
  `access_policy` block; `queryRewrite` handles **rows** (Layer-1 + Layer-2) and
  the **row-conditional columns** — when a `reporting_chain` / `teaching_staff`
  sensitive column (comp/obs/pii) is requested, narrow the result rows to the
  downline (or `job_function_code IN ('TEACH','TIR')` for `teaching_staff`). The
  staff cube and detail view expose `staff_key` and `job_function_level` for
  these filters.

- **Snapshot anchor** logic and `canSwitchSqlUser` unchanged.

### 5. Cube renames, schema test, view policies (original issue scope)

Per [#4102](https://github.com/TEAMSchools/teamster/issues/4102). **Status:**
the cube/view renames (`dim_` / `fct_` → domain-prefixed) already landed on
`main`; the cube _names_ are clean. Remaining:

- Add `tests/cube/test_cube_schema.py` enforcing no `dim_` / `fct_` prefix on
  cube names (does not exist yet).
- Split view `access_policy` into the tier groups, resolved as **one composite
  block per viewer** (see § View pattern — avoids the `member_level`
  intersection bug).
- Drop the `STUDENT_CUBES` / `STAFF_CUBES` static arrays; add `isStaffMember`
  (`isStudentMember` already exists in `cube.js`).

### 5a. No new Cubes for the access models

`dim_staff_cube_access` and `dim_staff_reporting_chain` are read by `cube.js` as
raw BigQuery tables — they _are_ the access policy. They get **no**
`src/cube/model/` cube or view definition (exposing them as queryable Cubes
would subject them to the very policies they encode). The only Cube-side dbt
wiring is adding both to `cube_semantic_layer.depends_on` in
`src/dbt/kipptaf/models/exposures/cube.yml`, per `marts/CLAUDE.md` (every mart
Cube consumes must appear there). No new data cubes are introduced — the staff /
student cubes and `staff_detail` / `staff_summary` views already exist on
`main`.

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

### The `member_level` intersection constraint — and the two-axis resolution

`member_level` `access_policy` blocks **intersect, not union** (the #4102
Finding, from PR #3755): a viewer in two blocks gets the intersection of their
`includes` lists — often empty. So emitting separate `-pii` / `-compensation` /
`-observations` groups per viewer would give a multi-entitled viewer _fewer_
columns, or none. We resolve this on **two axes**:

- **Column visibility (all/none scopes)** → **one composite `access_policy`
  block per viewer.** `contextToGroups` resolves the viewer's full staff-column
  set into a single group; each view carries one block per composite tier. This
  is #4102's own stated implication ("one resolved role … one `includes` list")
  and is the only way to avoid the intersection.
- **Row visibility (location scope + the Layer-2 detail gate)** →
  **`queryRewrite`.** `access_policy` cannot express per-row rules; this lives
  in `queryRewrite` regardless.

The `reporting_chain` and `teaching_staff` scopes are **row-conditional column
visibility** (comp for downline rows only; comp/obs for TEACH/TIR rows only) —
not expressible in a static `access_policy`. The composite block simply
_includes_ those columns; `queryRewrite` then narrows the query's **rows** to
the downline (or `job_function_code IN ('TEACH','TIR')`) when such a column is
requested. **The composite block does not harm reporting-chain visibility** —
chain enforcement is a row filter, and the single-block column model leaves it
intact.

Tradeoff (unchanged): requesting a `reporting_chain` field restricts the whole
query's rows to the viewer's downline — a manager gets their team's comp, not
comp spread across their wider summary scope. This matches "show me my team's
comp." Confirm with the data team that every scope value reduces to a single
composite tier + the row filter.

---

## Open questions

1. **`department_group` / `department_type` rollup** — the mapping from the 41
   `department_name` values into department groups and the
   instructional/non-instructional split is owned by the data team and lives in
   the **department rollup crosswalk** (Google Sheet). Seed it with the
   special-access departments handled; the data team fills the remaining rollup
   before the model ships. (`entity` is NOT in this rollup — it derives in-model
   from `business_unit_name`.)

2. **`job_function_code` availability** — RESOLVED. PR #4182 propagated only the
   label; the prerequisite adds `job_function_code` (the ADP `code_value`) to
   `dim_work_assignment_jobs`. Code values verified in prod (2026-06-23):
   CHIEF/EDHOS/SL/DSO/ASL/DEAN/SCOPS/NINST/TEACH/TIR/MGDIR/DIR/KTRGS, plus INTRN
   (no role-table row → denied). The role crosswalk keys on these codes.

3. **Tristate row restriction** — the resolution above (group + `queryRewrite`
   row filter) restricts the staff result set when a `reporting_chain` /
   `teaching_staff` sensitive field is requested. Confirm with the data team
   that this single-query restriction is acceptable (a viewer gets their
   downline rows when querying comp, not their full scope) before implementing
   `cube.js` staff gating.

4. **Multi-location / itinerant staff** — coaches covering multiple schools get
   one `scope_key`; multi-location support is deferred to a follow-up.

---

## Implementation sequence

1. **Prereq:** add `job_function_code` to `dim_work_assignment_jobs`
   (passthrough; no hash change) + properties yml.
2. **Crosswalks:** create the Google Sheet (data team fills the rollup), declare
   the `GOOGLE_SHEETS` sources in `google/sheets/sources-external.yml`, build
   the `stg_google_sheets__people__cube_access_*` staging models, add the
   exposure in `google-sheets.yml`.
3. Build `dim_staff_reporting_chain` (recursive closure over current/primary
   marts edges).
4. Build `dim_staff_cube_access` (marts star → department override crosswalk →
   role crosswalk → `dim_locations` for `region_key`); add both new dims to
   `exposures/cube.yml` `depends_on`.
5. Add the tier `access_policy` blocks (one composite block per viewer;
   additive, safe to deploy independently).
6. Rewrite `cube.js`: `contextToGroups` (two BigQuery reads, one composite staff
   group) and `queryRewrite` (scope + Layer-2 detail gate (below-OR-downline /
   downline / ungated by `staff_access_level`) + row-conditional columns); add
   `isStaffMember`; drop the static arrays.
7. Add `tests/cube/test_cube_schema.py`.
8. Document the reporting-chain gate in `src/cube/CLAUDE.md` and the staff view
   YAML (the #4092 deliverable).
9. Validate in Dev Mode with test emails at each tier (network/region/school,
   summary-only, manager with reportees, special-access department, no access);
   confirm a pii+comp viewer sees both columns (intersection fix).
10. Deploy to production; spot-check each tier.
11. Retire all `cube-*` Google Workspace groups.
12. File the data-quality issue (diagnostic query, aggregate counts only — no
    PII) for staff whose current assignment can't resolve a role.
