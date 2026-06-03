# Cube Security Redesign — Declarative Access Control with HR-Derived Groups

**Issue:** [#4102](https://github.com/TEAMSchools/teamster/issues/4102)
**Branch:** `cristinabaldor/feat/claude-cube-security-redesign`

## Summary

Move all Cube access control into Cube itself, with group membership derived
automatically from HR data. A single dbt model — `dim_staff_cube_access` —
becomes the source of truth for who can see what, replacing manual Google
Workspace group enrollment entirely. The Google Admin Directory API is
eliminated. `cube.js` is simplified: `contextToGroups` queries BigQuery,
`queryRewrite` reads location scope from the cache instead of parsing group
names, and all access-level gating (including PII and staff-all) lives in the
dbt model as boolean columns.

## What we're changing from now

The current model has two issues this redesign addresses:

**1. Group names encode two things at once.** A name like
`cube-region-newark-detail` conflates location scope (Newark) and access level
(detail). These are independent dimensions managed by two separate mechanisms
after this redesign.

**2. Group membership is maintained manually.** When someone becomes a regional
director, someone in Tech manually enrolls them in a Google Workspace group. The
Google Admin Directory API is called at query time to resolve memberships,
adding a runtime dependency, caching complexity, and an IT bottleneck. PII and
staff-all grants live in the same system, with no audit trail beyond group
membership history.

After this redesign: a dbt model derived from the existing staff roster view
determines access level (summary/data/PII) and location scope (network/region/
school) for every staff member. `contextToGroups` reads that model from
BigQuery. `queryRewrite` location logic is unchanged in behavior — only its data
source changes. All Google Workspace `cube-*` groups are retired.

---

## Access model

### Two independent dimensions

| Dimension      | Controls                | Mechanism                                               |
| -------------- | ----------------------- | ------------------------------------------------------- |
| Access level   | Which views and columns | `access_policy` group membership                        |
| Location scope | Which rows              | `access_policy` `row_level` filter via `userAttributes` |

### Access level groups

Three groups cover student data access. Staff access uses two existing groups
unchanged.

| Group                         | Views                  | Columns                   |
| ----------------------------- | ---------------------- | ------------------------- |
| `cube-access-student-summary` | Summary views only     | All non-PII members       |
| `cube-access-student-detail`  | Detail + summary views | All non-PII members       |
| `cube-access-student-pii`     | Detail + summary views | All members including PII |

Summary views list all three groups in their `access_policy`. Detail views list
only `cube-access-student-detail` and `cube-access-student-pii`. A user in
`cube-access-student-summary` cannot query a detail view.

Multi-group OR semantics work correctly: a user with both
`cube-access-student-detail` and `cube-access-student-pii` gets PII-level access
(the union of both policies).

### Location scope

Location filtering stays in `queryRewrite`. Cube's `access_policy` `row_level`
filter operators are all scalar — `equals`, `contains` (LIKE), date operators.
There is no array-containment operator, so a `scope_keys` ARRAY column cannot be
matched against a scalar user attribute in YAML. `queryRewrite` handles
arbitrary JS logic and already implements the three-tier hierarchy correctly;
the only change is that it reads location scope from the BigQuery-populated
cache instead of parsing Google Group names.

The cache object is extended to carry location fields alongside groups:

| Cache field          | Type   | Value                                  |
| -------------------- | ------ | -------------------------------------- |
| `location_scope`     | STRING | `'network'`, `'region'`, or `'school'` |
| `location_scope_key` | STRING | e.g. `'newark'` or `'NCA'`             |

`queryRewrite` reads these fields and injects the same WHERE clause filters it
does today — network (no filter), region (`region_key` equals), school
(`abbreviation` equals), or default deny when `location_scope` is null.

Multi-location staff (e.g. coaches covering multiple schools) are out of scope
for v1 — handled by assigning the broadest applicable scope in
`dim_staff_cube_access`.

---

## Changes required

### 1. dbt: new model `dim_staff_cube_access`

One row per staff email. Built on top of the existing staff roster view (which
already carries location), extended with manually-curated boolean columns for
access level and PII. This is the single source of truth for all Cube access —
no Google Group lookup is needed at all.

All columns are derived from role — no manual grants or seed files needed.

Columns:

| Column                 | Type    | Description                                                          |
| ---------------------- | ------- | -------------------------------------------------------------------- |
| `staff_google_email`   | STRING  | Primary key — matches the email claim in the JWT                     |
| `student_access_level` | STRING  | `'detail'`, `'summary'`, or `null` — access to student data views    |
| `staff_access_level`   | STRING  | `'detail'`, `'summary'`, or `null` — access to staff data views      |
| `student_pii`          | BOOLEAN | Can see student PII columns (names, DOB, IDs) in detail views        |
| `staff_pii`            | BOOLEAN | Can see staff PII columns (personal contact info, etc.)              |
| `staff_compensation`   | BOOLEAN | Can see compensation data                                            |
| `staff_benefits`       | BOOLEAN | Can see benefits data                                                |
| `location_scope`       | STRING  | `'network'`, `'region'`, or `'school'` — derived from staff roster   |
| `location_scope_key`   | STRING  | The specific key value (see table above) — derived from staff roster |

Logic is derived entirely from the staff roster view (role, primary job code,
location assignment). Exact derivation rules to be confirmed with the staff data
pipeline owner (open question 1), but the shape is:

- `student_access_level`: `'detail'` for principals, APs, regional leads,
  central office analysts; `'summary'` for teachers and school-level
  instructional staff; `null` for staff with no student data need
- `staff_access_level`: `'detail'` for HR, talent, regional leads, network
  leadership; `'summary'` for principals and school ops; `null` for most staff
- `student_pii`: true for roles that need to identify individual students (e.g.
  counselors, principals, data team)
- `staff_pii`, `staff_compensation`, `staff_benefits`: true for HR, payroll, and
  relevant leadership roles
- `location_scope` / `location_scope_key`: derived from primary location
  assignment — central office → network; regional role → region + key; school
  role → school + abbreviation

### 3. `cube.js`: revise `contextToGroups`

Replace the Google Admin Directory API call with a BigQuery query against
`dim_staff_cube_access`. Return access-level group names; inject location scope
key into the security context.

```javascript
contextToGroups: async ({ securityContext }) => {
  const email =
    securityContext?.email ??
    securityContext?.cubeCloud?.userAttributes?.email;
  if (!email) return [];

  // Check cache (keep midnight-ET expiry — BigQuery has cost, not just latency)
  const cached = groupCache.get(email);
  if (cached && cached.expiresAt > Date.now()) return cached.groups;

  const { BigQuery } = require('@google-cloud/bigquery');
  const bq = new BigQuery();
  const [rows] = await bq.query({
    query: `
      SELECT student_access_level, can_access_pii, can_access_staff_all,
             location_scope, location_scope_key
      FROM kipptaf_marts.dim_staff_cube_access
      WHERE staff_email = @email
      LIMIT 1
    `,
    params: { email },
  });

  const groups = [];

  if (rows.length) {
    const { student_access_level, can_access_pii, can_access_staff_all } = rows[0];

    if (student_access_level === 'detail') {
      groups.push('cube-access-student-detail');
    } else if (student_access_level === 'summary') {
      groups.push('cube-access-student-summary');
    }

    if (can_access_pii) groups.push('cube-access-student-pii');
    if (can_access_staff_all) groups.push('cube-access-staff-all');
  }

  // Store location scope fields in cache alongside groups
  if (rows.length) {
    const { location_scope, location_scope_key } = rows[0];
    groupCache.set(email, {
      groups,
      location_scope: location_scope ?? null,
      location_scope_key: location_scope_key ?? null,
      expiresAt: nextMidnightEastern(),
    });
  } else {
    groupCache.set(email, { groups, expiresAt: nextMidnightEastern() });
  }

  return groups;
},
```

Default deny: if `location_scope_key` is null (no matching row in
`dim_staff_cube_access`), `queryRewrite` injects the existing empty `IN ()`
filter — same behavior as today.

### 2. `cube.js`: revise `queryRewrite` — read location from cache

Replace the `networkGroup` / `regionGroup` / `schoolGroup` group-name parsing
with direct reads from the cache fields populated above:

```javascript
queryRewrite: (query, { securityContext }) => {
  const email = securityContext?.email ?? ...;
  const cached = email ? groupCache.get(email) : null;
  const groups = cached?.expiresAt > Date.now() ? cached.groups : [];
  const locationScope = cached?.location_scope ?? null;
  const locationKey = cached?.location_scope_key ?? null;

  // ... (student cube member-stripping — unchanged) ...

  let locationFilter = null;
  if (locationScope === 'network') {
    // no filter
  } else if (locationScope === 'region') {
    locationFilter = {
      member: 'dim_locations.region_key',
      operator: 'equals',
      values: [locationKey],
    };
  } else if (locationScope === 'school') {
    locationFilter = {
      member: 'dim_locations.abbreviation',
      operator: 'equals',
      values: [locationKey],
    };
  } else {
    // default deny
    return { ...query, filters: [{ member: 'dim_locations.abbreviation', operator: 'equals', values: [] }] };
  }
  // ... rest unchanged
```

The logic is identical to today; only the source of `locationScope` /
`locationKey` changes from group-name parsing to cache fields.

### 3. View YAMLs: add `cube-access-student-summary` group

Summary views gain a new `cube-access-student-summary` policy block (same
`member_level` as `cube-access-student-detail`, no PII exclusions). Detail views
are unchanged — `cube-access-student-summary` is not listed there, so summary-
only users cannot query detail views.

Updated summary view pattern:

```yaml
access_policy:
  # No PII tier — view contains no direct student identifiers.
  - group: cube-access-student-summary
    member_level:
      includes: "*"
  - group: cube-access-student-detail
    member_level:
      includes: "*"
  - group: cube-access-student-pii
    member_level:
      includes: "*"
```

### 4. `queryRewrite`: remove group-name parsing for location

Remove:

- `networkGroup` / `regionGroup` / `schoolGroup` regex resolution from group
  names
- `locationFilter` construction from parsed group names

Retain:

- `STUDENT_CUBES` member-stripping (unchanged — still enforced in `queryRewrite`
  as a defense-in-depth layer alongside `access_policy` group gating)
- Snapshot anchor injection (unchanged)
- Staff reporting chain segment injection (unchanged)
- Default-deny empty `IN ()` filter (unchanged behavior, now triggered by null
  cache fields rather than absence of scope group)

### 5. Google Workspace group cleanup

Once the redesign is live and validated, all `cube-*` Google Workspace groups
can be retired — access is fully managed through `dim_staff_cube_access`. No
Google groups are needed after cutover.

---

## What stays the same

- `access_policy` in view YAMLs for column-level PII gating — same pattern, same
  group names; only the source of group membership changes
- Cubes remain `public: false`; views remain the only public surface
- Cache TTL (midnight ET) — now covers the BigQuery row only; Google Admin API
  call is eliminated entirely
- `canSwitchSqlUser` — unchanged
- Staff reporting chain via `queryRewrite` segment — unchanged until
  `manager_email_path` is available on `dim_staff`

---

## Open questions

1. **`dim_staff_cube_access` role logic** — confirm which column(s) on the staff
   roster view best determine `student_access_level`. Job title,
   primary_job_code, or a combination? The derived logic should be reviewed with
   whoever owns the staff data pipeline before the model is built.

2. **Multi-location staff** — coaches or itinerant staff who cover multiple
   schools are out of scope for v1. `dim_staff_cube_access` assigns one
   `location_scope_key` per person; multi-location support requires OR'd filters
   in `queryRewrite` and is deferred to a follow-up.

3. **Rollout safety** — `contextToGroups` and `queryRewrite` changes deploy
   together as one Cube Cloud push. The `cube-access-student-summary` view YAML
   addition is additive and safe to deploy independently beforehand. Google
   Workspace group retirement should wait until the new system has been in
   production for at least one full school day and confirmed via spot-checks.

---

## Implementation sequence

1. Build `dim_staff_cube_access` dbt model (confirm role logic per open question
   1 first)
2. Add `cube-access-student-summary` to summary view `access_policy` blocks —
   additive, safe to deploy independently
3. Update `cube.js`: revise `contextToGroups` to query BigQuery; revise
   `queryRewrite` to read location from cache fields instead of group names
4. Validate in Dev Mode with test emails at each scope tier (network, region,
   school, summary-only, no access)
5. Deploy to production; confirm access spot-checks for each tier
6. Retire all `cube-*` Google Workspace groups
