# Cube `access_policy` Pivot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Cube row-level access control out of `cube.js`'s `queryRewrite`
into Cube-native per-view `access_policy` driven by a server-side-enriched
`securityContext`, deleting `queryRewrite`'s RLS half.

**Architecture:** Identity resolution (the two BigQuery reads) moves from
`contextToGroups` into the auth hooks (`checkAuth` for REST/MCP, `checkSqlAuth`
for the SQL API), which write the resolved access row + reporting-chain keys
into `securityContext`. Each view then declares `access_policy.row_level`
filters that interpolate those `securityContext` values. The staff detail
surface splits into an open `staff_directory` view and a gated `staff_pii` view
so the remit attaches only to sensitive fields. `member_level` field gating and
the dbt access models are unchanged.

**Tech Stack:** Cube (data model YAML + `cube.js`/`access.js` Node config),
BigQuery driver, `node --test` for pure JS, Python `psycopg2` over the Cube SQL
API for policy validation.

## Global Constraints

- Cube **≥ the version already pinned** in `src/cube/package.json`
  (`@cubejs-backend/server` — do not change the pin in this plan).
- `access_policy` semantics live in Cube data-model YAML; `securityContext`
  shaping lives in `cube.js`/`access.js`. Keep transformation OUT of cube `sql:`
  (thin shaping only).
- **PII stays local.** Never emit real staff/student field values to any
  external surface (PR, commit, logs). Validation output uses aggregate row
  counts + column-presence booleans, never row values.
- The dbt models `dim_staff_cube_access` and `dim_staff_reporting_chain`, the
  scope enums, and existing `member_level` field gating are **unchanged** by
  this plan.
- `queryRewrite`'s **snapshot-anchor** block (`SNAPSHOT_CUBES` etc.) stays on
  this branch — it is removed by Track 1 (Tesseract, #4214/#4333), not here.
  This plan removes only the **RLS** half.
- Cube dev server is long-running; the implementer (not an automated step)
  starts it. Steps that need it say so and give the exact command.

---

## File Structure

- `src/cube/access.js` — **modify.** Row-filter builders (`studentRowFilters`,
  `staffScopeFilter`, `staffSensitiveFilters`) are removed (logic moves to
  YAML). Add `buildSecurityContext(row, reporteeStaffKeys)` — a pure function
  shaping the cached access row into the flat `securityContext` object the
  policies interpolate. `buildGroups` stays.
- `src/cube/access.test.js` — **modify.** Drop tests for the removed filter
  builders; add tests for `buildSecurityContext`.
- `src/cube/cube.js` — **modify.** Move the two BQ reads into a shared async
  `resolveAccess(email)` helper; call it from `checkAuth` (REST) and
  `checkSqlAuth` (SQL API), assigning the enriched `securityContext`. Delete the
  RLS branch of `queryRewrite` (student row filters + staff sensitive filters +
  student-member strip); keep the snapshot-anchor block and `canSwitchSqlUser`.
- `src/cube/model/views/staff/staff_detail.yml` — **delete**, replaced by:
- `src/cube/model/views/staff/staff_directory.yml` — **create.** Open directory
  fields; no `row_level`.
- `src/cube/model/views/staff/staff_pii.yml` — **create.** Sensitive fields;
  `access_policy.row_level` remit.
- `src/cube/model/views/students/*.yml`, `student_attendance/*.yml`,
  `student_assessments/*.yml` — **modify.** Add `access_policy.row_level`
  location filter under the `student` group.
- `docs/superpowers/plans/2026-07-07-cube-access-policy-pivot.md` — this plan.
- `src/cube/CLAUDE.md`, `docs/guides/cube.md`,
  `docs/superpowers/specs/2026-06-25-cube-access-reviewer-guide.md` — **modify**
  (docs, folded into the tasks that change behavior).

---

### Task 1: De-risking spike (gates the row-level design)

Prove the three risky `access_policy` mechanics on a throwaway model before
touching real views. **If any sub-check fails, the fallback in spec §R4
applies** (a thin residual `queryRewrite` for only the failing construct) —
record the outcome in the plan before proceeding to Task 5.

**Files:**

- Create (throwaway, deleted at end of task):
  `src/cube/model/cubes/_spike_access.yml`
- Test/harness: `.claude/scratch/spike_access_probe.py`

**Interfaces:**

- Produces: a recorded verdict (in the task's final commit message or a scratch
  note) for (a) array-valued `securityContext` interpolation, (b) nested
  `or`/`and` in `row_level`, (c) multi-policy `row_level` combination (AND vs
  OR). Task 5 consumes this verdict.

- [ ] **Step 1: Write the throwaway spike cube + two policies**

Create `src/cube/model/cubes/_spike_access.yml`:

```yaml
cubes:
  - name: _spike_access
    public: false
    sql: >
      SELECT 'k1' AS staff_key, 1 AS lvl UNION ALL SELECT 'k2' AS staff_key, 5
      AS lvl UNION ALL SELECT 'k3' AS staff_key, 9 AS lvl
    dimensions:
      - name: staff_key
        sql: staff_key
        type: string
        primary_key: true
        public: true
      - name: lvl
        sql: lvl
        type: number
        public: true
    measures:
      - name: n
        type: count
        public: true
    access_policy:
      # (a) array IN + (b) nested or/and, both from securityContext
      - group: spike_chain
        row_level:
          filters:
            - or:
                - member: _spike_access.staff_key
                  operator: equals
                  values: "{ securityContext.reportee_staff_keys }"
                - and:
                    - member: _spike_access.lvl
                      operator: gt
                      values: ["{ securityContext.job_function_level }"]
      # (c) second policy the same viewer also matches, to observe combination
      - group: spike_all
        row_level:
          filters:
            - member: _spike_access.lvl
              operator: gte
              values: ["1"]
```

Add both groups to the dev security context so the viewer matches them (see Step
3).

- [ ] **Step 2: Start the dev server (implementer action)**

Ask the implementer to run, from `src/cube`:

```bash
CUBEJS_DEV_MODE=true CUBEJS_TESSERACT_SQL_PLANNER=true \
CUBEJS_API_SECRET=devsecret CUBEJS_DB_BQ_PROJECT_ID=teamster-332318 \
CUBEJS_PG_SQL_PORT=15432 CUBEJS_SQL_USER=cube CUBEJS_SQL_PASSWORD=cube \
CUBE_SQL_DEV_EMAIL=cbaldor@apps.teamschools.org \
CUBE_GROUP_MAP='{"cbaldor@apps.teamschools.org":["spike_chain","spike_all"]}' \
npm run dev
```

Expected: server boots, model compiles (spike cube present in `/meta`).

- [ ] **Step 3: Probe via the SQL API**

`.claude/scratch/spike_access_probe.py` (needs the dev securityContext to carry
`reportee_staff_keys: ['k1']`, `job_function_level: 5` — inject via a dev-only
`checkSqlAuth` that returns these in `securityContext`; a temporary hard-coded
block is fine for the spike):

```python
import psycopg2
c = psycopg2.connect(host="localhost", port=15432, user="cube",
                     password="cube", dbname="cube", connect_timeout=15)
c.autocommit = True
cur = c.cursor()
cur.execute("SELECT staff_key, MEASURE(n) FROM _spike_access GROUP BY 1 ORDER BY 1")
print(cur.fetchall())
```

- [ ] **Step 4: Record the verdict**

Run:
`uv run --with psycopg2-binary python .claude/scratch/spike_access_probe.py`
Expected (if array IN + nested or/and + AND-combination all work): only `k1`
(chain) and rows with `lvl > 5` i.e. `k3`, intersected with `lvl >= 1` from the
second policy → `[('k1',1),('k3',1)]`. If the array filter errors or the row set
is wrong, note which construct failed.

- [ ] **Step 5: Delete the spike + commit the verdict**

```bash
rm src/cube/model/cubes/_spike_access.yml
git add -A
git commit -m "chore(cube): access_policy spike — record row_level verdict"
```

Put the verdict (works / which construct fails + chosen fallback) in the commit
body. **Do not proceed to Task 5's primary form if the array or nested-filter
check failed — use its fallback branch.**

#### Task 1 Verdict (recorded 2026-07-07)

Probed via the SQL API (Tesseract planner) against a throwaway `spike_access`
cube. Results:

- **(a) Array-valued `securityContext` interpolation — WORKS.** The unbracketed
  string form `values: "{ securityContext.reportee_staff_keys }"` expands to a
  correct `IN (...)` list. (Scalar interpolation uses the bracketed form
  `values: ["{ securityContext.x }"]`.)
- **(b) Nested `or`/`and` in `row_level` — WORKS.**
- **(c) Multi-policy combination — OR / UNION, not AND.** Two `access_policy`
  entries the same viewer matches are **unioned** (permissive), not intersected.
  The plan's original expectation (`[k1, k3]` via AND) was wrong; the two-policy
  probe returned all rows because the broad policy's union swallowed the narrow
  one.
- **(d) `conditions.if` with a `==` comparison — DOES NOT COMPILE.** Cube routes
  the `{ ... }` in `conditions.if` through a Python-expression parser that
  rejects `==`
  (`Unsupported Python multiple children node: Comp_opContext: ==`). Cube's
  documented `conditions.if` form is a bare **truthy reference**
  (`if: "{ userAttributes.is_full_time_employee }"`), never a comparison.
- **(e) `conditions.if` as a truthy reference — WORKS**, and **default-deny
  holds**: a truthy value applies the policy; a falsy/undefined value skips it,
  and when no policy on a cube matches, the query returns zero rows.

Spike artifact (not a real-view concern): a **leading-underscore cube name**
(`_spike_access`) breaks Tesseract's SQL-API alias resolution
(`_spike_access__staff_key` "member name not found"); renaming to `spike_access`
fixed it. Real cubes/views carry no leading underscore.

Still open (untestable on local Core): whether the **Cube Cloud** surface
exposes `securityContext.` or `userAttributes.` for interpolation. Local Core
dev uses `securityContext.` and it works; confirm on Cube Cloud Dev Mode /
staging and swap the token uniformly if Cloud requires `userAttributes.`.

**Consequence for Tasks 2 + 5 (revised design — canonical `group`-based, NOT the
`conditions.if` primary form and NOT the spec §R4 `queryRewrite` fallback):**
because `==` in `conditions.if` does not compile — and because Cube's documented
idiom for "different access level → different row filter" is distinct
**`group`s** (the `deals_view` `sales`/`sales_manager` example), with
`conditions.if` reserved for boolean overlays — the enum→policy branch moves
into `buildGroups` (which already emits HR-derived tier strings). `buildGroups`
emits one **scope-specific group per non-`none` enum value**:

- students: `student-region` / `student-school` / `student-network` (replacing
  the single `student` tier)
- staff PII: `staff-pii-reporting_chain` /
  `staff-pii-reporting_chain_or_below_rank` / `staff-pii-all_in_scope` /
  `staff-pii-teaching_staff` (replacing `staff-pii`)

Each Task 5 policy matches one such `group:` and carries its own
`member_level: { includes: "*" }` + `row_level`. A viewer's scope enum is a
single value, so they hold exactly one scope-group — the OR/union combination
(c) is a non-issue (only one policy is ever active), `none` scope emits no group
→ default-deny (e), and no `conditions.if` is used (avoiding (d)).
`buildSecurityContext` keeps the flat interpolation shape the plan's Task 2
already specifies (`region_key`, `location_abbreviation`, `department_group`,
`job_function_level`, `reportee_staff_keys`, …) — no boolean flags needed. Array

- nested `row_level` filters (a, b) express the staff remit. All RLS stays in
  `access_policy` with no residual `queryRewrite`. `member_level` field gating
  (which fields are PII) is unchanged in intent; it is now declared per
  scope-group.

---

### Task 2: `access.js` — `buildSecurityContext` (pure, unit-tested)

**Files:**

- Modify: `src/cube/access.js`
- Test: `src/cube/access.test.js`

**Interfaces:**

- Consumes: the cached access `row` (columns per `dim_staff_cube_access`) and
  `reporteeStaffKeys: string[]`.
- Produces: `buildSecurityContext(row, reporteeStaffKeys) -> object` with a flat
  shape the policies interpolate:
  `{ email, groups, student_location_scope, staff_pii_scope, region_key, location_abbreviation, department_group, job_function_level, reportee_staff_keys }`
  (null-safe; `groups` from `buildGroups`). Also still exports `buildGroups`.
- **Revised per the Task 1 verdict (canonical group-based RLS):** `buildGroups`
  is MODIFIED to emit one scope-specific group per non-`none` enum value —
  `student-<student_location_scope>` (`student-region`/`-school`/`-network`,
  replacing the single `student`) and `staff-pii-<staff_pii_scope>`
  (`staff-pii-all_in_scope`/`-reporting_chain`/`-reporting_chain_or_below_rank`/
  `-teaching_staff`, replacing `staff-pii`). `staff-directory` is still always
  emitted; the forward-compat `staff-compensation`/`-observations`/`-benefits`
  tiers stay flat (no view consumes them yet). Task 5 gates each policy on one
  of these `group:` strings — no `conditions.if` (which cannot compile `==`).

- [ ] **Step 1: Write the failing test + update the `buildGroups` tests**

Add to `src/cube/access.test.js` (uses the existing `require("./access")` alias
`a` in that file — the snippet below spells it `access` for clarity; match the
file's actual alias):

```javascript
test("buildSecurityContext flattens the access row + chain", () => {
  const row = {
    student_location_scope: "region",
    staff_pii_scope: "reporting_chain_or_below_rank",
    region_key: "R1",
    location_abbreviation: "ABC",
    department_group: "Operations",
    job_function_level: 5,
  };
  const ctx = access.buildSecurityContext(row, ["k1", "k2"]);
  assert.strictEqual(ctx.region_key, "R1");
  assert.strictEqual(ctx.job_function_level, 5);
  assert.deepStrictEqual(ctx.reportee_staff_keys, ["k1", "k2"]);
  assert.ok(ctx.groups.includes("staff-directory"));
  // Scope-specific student group (canonical group-based RLS), not "student".
  assert.ok(ctx.groups.includes("student-region"));
  assert.ok(ctx.groups.includes("staff-pii-reporting_chain_or_below_rank"));
});

test("buildSecurityContext is null-safe for an unresolved viewer", () => {
  const ctx = access.buildSecurityContext(null, []);
  assert.deepStrictEqual(ctx.groups, []);
  assert.deepStrictEqual(ctx.reportee_staff_keys, []);
});
```

Also UPDATE the existing `buildGroups` tests for the scope-specific names (the
`SL` fixture has `student_location_scope: "school"`,
`staff_pii_scope: "all_in_scope"`):

- The "SL gets the single student tier and staff directory+pii" test:
  `g.includes("student")` → `g.includes("student-school")`;
  `g.includes("staff-pii")` → `g.includes("staff-pii-all_in_scope")`.
- "staff_pii_scope none → directory but no pii tier": `!g.includes("staff-pii")`
  → `!g.some((x) => x.startsWith("staff-pii"))`.
- "student_location_scope none → no student tier": `!g.includes("student")` →
  `!g.some((x) => x.startsWith("student"))`.
- The compensation/observations/benefits assertions stay as-is (those tiers
  remain flat).

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test src/cube/access.test.js` Expected: FAIL —
`access.buildSecurityContext is not a function`.

- [ ] **Step 3: Modify `buildGroups`; implement `buildSecurityContext`; remove
      the dead filter builders**

In `src/cube/access.js`, delete `studentRowFilters`, `staffScopeFilter`,
`staffRemit`, `staffSensitiveFilters`, `locationScopeFilter`,
`departmentScopeFilter`, `DENY_FILTER`, and their exports (and delete every test
for them — the whole `studentRowFilters:` and `staffSensitiveFilters:` blocks in
`access.test.js`). Keep `isStudentMember`, `isStaffMember`, `STAFF_PII_MEMBERS`,
`STAFF_SENSITIVE_SCOPE_BY_MEMBER`. `email` is NOT a column on the access row, so
`buildSecurityContext` does not set it here — `resolveAccess` (Task 3) adds the
`email` to the context; leave it out of this pure function.

Modify `buildGroups` to emit scope-specific groups, and drop the `staff_pii`
entry from `STAFF_SENSITIVE_TIERS` (it is now handled explicitly):

```javascript
const STAFF_SENSITIVE_TIERS = [
  { scope: "staff_compensation_scope", group: "staff-compensation" },
  { scope: "staff_observations_scope", group: "staff-observations" },
  { scope: "staff_benefits_scope", group: "staff-benefits" },
];

function buildGroups(row) {
  if (!row) return [];
  const groups = [];

  // Student: one scope-specific group per non-none location scope
  // (student-region / student-school / student-network). Cube's canonical
  // group-based RLS — the group IS the row-level tier; each maps 1:1 to a view
  // access_policy. none → no group → default-deny.
  if (row.student_location_scope && row.student_location_scope !== "none") {
    groups.push(`student-${row.student_location_scope}`);
  }

  // Open staff directory for every resolved staff viewer.
  groups.push("staff-directory");

  // Staff PII: one scope-specific group per non-none pii scope, each carrying
  // its own row_level remit in staff_pii.yml.
  if (row.staff_pii_scope && row.staff_pii_scope !== "none") {
    groups.push(`staff-pii-${row.staff_pii_scope}`);
  }

  // Forward-compat sensitive tiers (no view consumes these yet) stay flat.
  for (const { scope, group } of STAFF_SENSITIVE_TIERS) {
    if (row[scope] && row[scope] !== "none") groups.push(group);
  }
  return groups;
}
```

Then add `buildSecurityContext`:

```javascript
function buildSecurityContext(row, reporteeStaffKeys) {
  return {
    groups: buildGroups(row),
    student_location_scope: row?.student_location_scope ?? "none",
    staff_pii_scope: row?.staff_pii_scope ?? "none",
    region_key: row?.region_key ?? null,
    location_abbreviation: row?.location_abbreviation ?? null,
    department_group: row?.department_group ?? null,
    job_function_level: row?.job_function_level ?? null,
    reportee_staff_keys: reporteeStaffKeys ?? [],
  };
}
```

Add `buildSecurityContext` to `module.exports` (and remove the deleted builders
from it: `studentRowFilters`, `staffSensitiveFilters`, `DENY_FILTER`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `node --test src/cube/access.test.js` Expected: PASS (new tests green;
removed-builder tests deleted).

- [ ] **Step 5: Commit**

```bash
git add src/cube/access.js src/cube/access.test.js
git commit -m "refactor(cube): access.js builds securityContext; drop row-filter builders"
```

---

### Task 3: `cube.js` — resolve identity in `checkAuth` + `checkSqlAuth` → `securityContext`

**Files:**

- Modify: `src/cube/cube.js`

**Interfaces:**

- Consumes: `access.buildSecurityContext` (Task 2); the existing `groupCache` +
  midnight-ET expiry; the two BQ read SQLs (already in `contextToGroups`).
- Produces: an enriched `securityContext` on every request (REST + SQL API)
  carrying the fields Task 5's policies interpolate. `contextToGroups` reduced
  to reading `securityContext.groups`.

- [ ] **Step 1: Extract a shared async `resolveAccess(email)`**

In `src/cube/cube.js`, factor the two BQ reads currently inside
`contextToGroups` into:

```javascript
async function resolveAccess(email) {
  if (!email) return access.buildSecurityContext(null, []);
  const cached = groupCache.get(email);
  if (cached && cached.expiresAt > Date.now()) return cached.ctx;

  // Local dev bypass (unchanged intent): CUBE_GROUP_MAP supplies groups only.
  if (process.env.NODE_ENV !== "production" && process.env.CUBE_GROUP_MAP) {
    const map = JSON.parse(process.env.CUBE_GROUP_MAP);
    const ctx = {
      ...access.buildSecurityContext(null, []),
      groups: map[email] ?? [],
    };
    groupCache.set(email, { ctx, expiresAt: nextMidnightEastern() });
    return ctx;
  }

  const { BigQuery } = require("@google-cloud/bigquery");
  const bq = new BigQuery();
  const [rows] = await bq.query({
    query:
      "SELECT * FROM `kipptaf_marts.dim_staff_cube_access` WHERE google_email = @email LIMIT 1",
    params: { email },
  });
  const row = rows[0] ?? null;
  let reporteeStaffKeys = [];
  if (row?.staff_key) {
    const [rc] = await bq.query({
      query:
        "SELECT reportee_staff_key FROM `kipptaf_marts.dim_staff_reporting_chain` WHERE manager_staff_key = @k",
      params: { k: row.staff_key },
    });
    reporteeStaffKeys = rc.map((r) => r.reportee_staff_key);
  }
  const ctx = access.buildSecurityContext(row, reporteeStaffKeys);
  groupCache.set(email, { ctx, expiresAt: nextMidnightEastern() });
  return ctx;
}
```

- [ ] **Step 2: Populate `securityContext` in both auth hooks**

Add `checkAuth` (REST/MCP) and rework `checkSqlAuth` (replace the dev-only stub
from Track 1) so both enrich the context:

```javascript
  checkAuth: async (req, auth) => {
    // auth is the decoded JWT payload; email is the only trusted claim.
    const email = auth?.email;
    req.securityContext = await resolveAccess(email);
  },

  checkSqlAuth: async (req, user) => {
    const email =
      (process.env.NODE_ENV !== "production" && process.env.CUBE_SQL_DEV_EMAIL) ||
      user;
    return { password: null, securityContext: await resolveAccess(email) };
  },
```

- [ ] **Step 3: Reduce `contextToGroups`**

Replace its body with a read of the resolved context:

```javascript
  contextToGroups: async ({ securityContext }) => securityContext?.groups ?? [],
```

- [ ] **Step 4: Verify it loads (implementer action)**

Restart the dev server (Task 1 Step 2 command). Run a `/meta` fetch with a JWT
`{email: "cbaldor@apps.teamschools.org"}`. Expected: `/meta` returns cubes (no
compile error); server logs show `resolveAccess` ran once (cache populated).

- [ ] **Step 5: Commit**

```bash
git add src/cube/cube.js
git commit -m "feat(cube): resolve access in checkAuth/checkSqlAuth into securityContext"
```

---

### Task 4: Split staff detail into `staff_directory` + `staff_pii`

**Files:**

- Delete: `src/cube/model/views/staff/staff_detail.yml`
- Create: `src/cube/model/views/staff/staff_directory.yml`
- Create: `src/cube/model/views/staff/staff_pii.yml`

**Interfaces:**

- Consumes: the `staff` cube (unchanged) exposing the directory fields + the six
  PII members (`personal_email`, `personal_cell_phone`, `birth_date`,
  `gender_identity`, `race`, `is_hispanic`) + `staff_key`, `job_function_level`,
  `job_function_code`, `department_group`.
- Produces: two views. `staff_directory` (no PII, open). `staff_pii` (PII + the
  join keys needed by its `row_level`, added in Task 5).

- [ ] **Step 1: Create `staff_directory.yml`**

Copy the current `staff_detail.yml` includes MINUS the six PII members and MINUS
the `staff-pii` policy block. Keep the
`cube-access-staff-data`/`staff-directory` open policy with
`member_level: { includes: "*" }` (no excludes needed — PII is simply absent).
No `row_level`.

- [ ] **Step 2: Create `staff_pii.yml`**

Include the six PII members + `staff_key` + the gating keys
(`job_function_level`, `job_function_code`, `department_group`) + the minimal
identity columns needed to make PII useful (e.g. `staff_key`, `full_name`). One
policy group `staff-pii`, `member_level: { includes: "*" }`. Leave `row_level`
empty for now (Task 5 fills it).

- [ ] **Step 3: Validate both compile (implementer action)**

Restart dev server; fetch `/meta`. Expected: both `staff_directory` and
`staff_pii` present; `staff_detail` gone.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/staff/
git commit -m "refactor(cube): split staff_detail into staff_directory + staff_pii"
```

---

### Task 5: Row-level `access_policy` on all gated views

> **SUPERSEDED BY THE TASK 1 VERDICT — read it before implementing.** The
> `conditions.if` "primary form" in Steps 1–2 below does NOT compile (`==` is
> unsupported). Use the **canonical group-based form**: each policy matches a
> scope-specific `group:` emitted by `buildGroups` (Task 2) — `student-region` /
> `student-school` / `student-network` on student views, `staff-pii-<scope>` on
> `staff_pii.yml` — with its own `member_level: { includes: "*" }` +
> `row_level`. No `conditions:` block. `network` scope → policy with no
> `row_level` (all rows); `none` → no group emitted → default-deny. The array-IN
> and nested `or`/`and` `row_level` filter shapes shown in Step 2 are correct
> and stay. This banner governs; the Step 1–2 `conditions` snippets are
> illustrative of the filters only.

**Files:**

- Modify: `src/cube/model/views/staff/staff_pii.yml`
- Modify: student/enrollment/attendance/assessment views under
  `src/cube/model/views/students/`, `student_attendance/`,
  `student_assessments/`

**Interfaces:**

- Consumes:
  `securityContext.{student_location_scope, region_key, location_abbreviation, staff_pii_scope, department_group, job_function_level, reportee_staff_keys}`
  (Task 3) and the Task 1 verdict.

- [ ] **Step 1: Add the student location `row_level` to every student-domain
      view**

Under the `student` group of each student/enrollment/attendance/assessment view,
add (three conditional policies, one per non-`none` scope):

```yaml
access_policy:
  - group: student
    conditions:
      - if: "{ securityContext.student_location_scope == 'region' }"
    member_level: { includes: "*" }
    row_level:
      filters:
        - member: locations.region_key
          operator: equals
          values: ["{ securityContext.region_key }"]
  - group: student
    conditions:
      - if: "{ securityContext.student_location_scope == 'school' }"
    member_level: { includes: "*" }
    row_level:
      filters:
        - member: locations.abbreviation
          operator: equals
          values: ["{ securityContext.location_abbreviation }"]
  - group: student
    conditions:
      - if: "{ securityContext.student_location_scope == 'network' }"
    member_level: { includes: "*" }
    # network: no row_level filter
```

(`none` grants no `student` group, so default-deny already applies — no policy
needed.)

- [ ] **Step 2: Add the staff PII remit `row_level` to `staff_pii.yml`**

**Primary form (use if Task 1's array + nested checks passed):** one `staff-pii`
policy per scope enum value, gated by `conditions`. Example for the two hardest:

```yaml
- group: staff-pii
  conditions:
    - if: "{ securityContext.staff_pii_scope == 'reporting_chain' }"
  member_level: { includes: "*" }
  row_level:
    filters:
      - member: staff.staff_key
        operator: equals
        values: "{ securityContext.reportee_staff_keys }"
- group: staff-pii
  conditions:
    - if:
        "{ securityContext.staff_pii_scope == 'reporting_chain_or_below_rank' }"
  member_level: { includes: "*" }
  row_level:
    filters:
      - or:
          - and:
              - member: staff.region_key # or department_group per remit
                operator: equals
                values: ["{ securityContext.region_key }"]
              - member: staff.job_function_level
                operator: gt
                values: ["{ securityContext.job_function_level }"]
          - member: staff.staff_key
            operator: equals
            values: "{ securityContext.reportee_staff_keys }"
```

Plus `all_in_scope` (location ∩ department) and `teaching_staff` (adds
`job_function_code IN ('TEACH','TIR')`) policies of the same shape.

**Fallback form (use if Task 1 showed array/nested filters do NOT
interpolate):** keep a minimal `queryRewrite` branch in `cube.js` that injects
ONLY the `reporting_chain*` chain-IN / rank filters for staff-PII queries, and
use `access_policy.row_level` for the location∩department scopes only. Record
which path was taken in the commit body.

- [ ] **Step 3: Validate the viewer matrix (implementer action)**

Restart the dev server. Run the validation harness (Task 7) for the staff-PII
scope viewers. Expected: row counts match the pre-pivot `queryRewrite` behavior
for each scope; open directory unaffected.

- [ ] **Step 4: Commit**

```bash
git add src/cube/model/views/
git commit -m "feat(cube): row_level access_policy for student + staff_pii views"
```

---

### Task 6: Delete `queryRewrite`'s RLS half

**Files:**

- Modify: `src/cube/cube.js`

**Interfaces:**

- Consumes: nothing new. Removes the student-member strip +
  `studentRowFilters`/`staffSensitiveFilters` calls.

- [ ] **Step 1: Remove the RLS branch, keep the snapshot-anchor block**

In `queryRewrite`, delete the student-member stripping and the
`access.studentRowFilters` / `access.staffSensitiveFilters` filter pushes.
**Keep** the `SNAPSHOT_CUBES` anchor-injection loop and `canSwitchSqlUser`
(Track 1 removes the snapshot block later). If nothing else remains in
`queryRewrite` besides the snapshot loop, leave the function with only that.

- [ ] **Step 2: Validate default-deny still holds (implementer action)**

Restart dev server. Query a student view as an **unresolved** email (no
`CUBE_GROUP_MAP` entry). Expected: `access_policy` default-deny returns zero
rows (no `student` group → no policy → denied). Confirms RLS now enforced by
policies, not `queryRewrite`.

- [ ] **Step 3: Commit**

```bash
git add src/cube/cube.js
git commit -m "refactor(cube): delete queryRewrite RLS half (moved to access_policy)"
```

---

### Task 7: Validation matrix + docs

**Files:**

- Create: `.claude/scratch/access_policy_validation.py` (harness, not committed
  to src)
- Modify: `src/cube/CLAUDE.md`,
  `docs/superpowers/specs/2026-06-25-cube-access-reviewer-guide.md`

**Interfaces:**

- Consumes: the running dev server + a set of dev securityContext profiles.

- [ ] **Step 1: Build the validation harness**

`.claude/scratch/access_policy_validation.py`: for each viewer profile (network
/ region / school / none; each staff_pii_scope enum), connect via the SQL API
and record **aggregate row counts + column presence** (never values) for
`staff_directory`, `staff_pii`, and a student view. Compare against the
pre-pivot `queryRewrite` counts captured from the #4269 branch.

- [ ] **Step 2: Run the matrix (implementer action)**

Run:
`uv run --with psycopg2-binary python .claude/scratch/access_policy_validation.py`
Expected: every profile's counts equal the pre-pivot baseline; directory open
for all staff; `staff_pii` scoped; `none` viewers denied.

- [ ] **Step 3: Update docs**

Update `src/cube/CLAUDE.md`'s security-model section (RLS now in
`access_policy`, resolution in `checkAuth`/`checkSqlAuth`,
`staff_directory`/`staff_pii` split) and the reviewer guide. Remove references
to `queryRewrite`-based RLS.

- [ ] **Step 4: Commit**

```bash
git add src/cube/CLAUDE.md docs/superpowers/specs/2026-06-25-cube-access-reviewer-guide.md
git commit -m "docs(cube): access_policy security model + reviewer guide"
```

---

## Self-Review

- **Spec coverage:** R1 → Task 3; R2 → Task 4; R3 → Task 5; R4 → Task 1; R5 →
  Task 6; R6 → Task 7. All covered.
- **Placeholders:** none — Task 5's contingency is two concrete forms (primary +
  fallback), gated by Task 1's recorded verdict, not a "TBD".
- **Type consistency:** `buildSecurityContext` shape (Task 2) matches the
  `securityContext.*` members interpolated in Task 5; `resolveAccess` (Task 3)
  returns that shape; `contextToGroups` reads `securityContext.groups`.
- **Open risk:** Cube Cloud `userAttributes` vs Core `securityContext`
  interpolation (spec R8 #2) — confirm in Task 1 which token the production
  surface exposes; if Cloud requires `userAttributes`, the interpolation strings
  change `securityContext.` → `userAttributes.` uniformly (mechanical).
