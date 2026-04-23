# Cube Infrastructure Implementation Plan

**Date:** 2026-04-23 **Issue:**
[#3591](https://github.com/TEAMSchools/teamster/issues/3591) **Spec:**
[2026-04-15-cube-infrastructure-design.md](../specs/2026-04-15-cube-infrastructure-design.md)

## Scope

Implements the infrastructure spec only — `src/cube/` scaffolding, `cube.js`
hooks, VS Code task, and `bridge_staff_hierarchy` dbt model. Cube YAML model
files (67 models across 12 domains) are addressed in a follow-up spec.

## Prerequisites

- ADC configured (`gcloud auth application-default login`) — already present in
  devcontainer
- Node.js available in devcontainer — confirm with `node --version`
- `dim_work_assignment_reporting_relationships` merged to main (done — PR #3676)

## Step 1 — `src/cube/` directory structure

Create the following files. The `model/cubes/` and `model/views/` directories
need a `.gitkeep` so they are tracked by git.

```text
src/cube/
  cube.js
  package.json
  .env.example
  .gitignore
  model/
    cubes/.gitkeep
    views/.gitkeep
  SETUP.md
```

## Step 2 — `package.json`

```json
{
  "name": "teamster-cube",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "cubejs-server"
  },
  "dependencies": {
    "@cubejs-backend/bigquery-driver": "1.6.38",
    "@cubejs-backend/server": "1.6.38",
    "googleapis": "171.4.0"
  }
}
```

## Step 3 — `.env.example`

Document every env var an engineer needs for local dev. Values shown are safe
defaults — never commit real secrets.

```bash
CUBEJS_DB_TYPE=bigquery
CUBEJS_DB_BQ_PROJECT_ID=teamster-332318
# CUBEJS_DB_BQ_CREDENTIALS omitted — uses ADC locally
CUBEJS_API_SECRET=local-dev-secret
CUBEJS_DEV_MODE=true
CUBEJS_CACHE_AND_QUEUE_DRIVER=memory

# Simulate group membership for local dev.
# JSON string mapping your email to a list of cube-* groups.
# Example: CUBE_GROUP_MAP={"you@apps.teamschools.org":["cube-network-detail","cube-access-student-data"]}
CUBE_GROUP_MAP=
```

## Step 4 — `.gitignore`

```gitignore
.env
node_modules/
.cubestore/
```

## Step 5 — `cube.js`

Three responsibilities in order: `contextToGroups`, `queryRewrite`,
`canSwitchSqlUser`. dbt Cloud metadata integration is configured in the Cube
Cloud UI — no `cube.js` code needed (see spec §1).

### 5a. dbt metadata integration

Configure in the **Cube Cloud UI**: Settings → Integrations → dbt Cloud, connect
to project `211862`. No code changes to `cube.js` are required.

Add to the exported config:

```javascript
schemaVersion: ({ securityContext }) => securityContext?.schemaVersion ?? "v1",
```

### 5b. `contextToGroups`

Returns `string[]` of `cube-*` group names for the requesting user.

```javascript
const groupCache = new Map(); // email → { groups, expiresAt }
const CACHE_TTL_MS = 5 * 60 * 1000;

contextToGroups: async ({ securityContext }) => {
  const email = securityContext?.email;
  if (!email) return [];

  // Local dev: CUBE_GROUP_MAP bypasses Directory API
  if (process.env.CUBE_GROUP_MAP) {
    const map = JSON.parse(process.env.CUBE_GROUP_MAP);
    return (map[email] ?? []).filter((g) => g.startsWith("cube-"));
  }

  // Check cache
  const cached = groupCache.get(email);
  if (cached && cached.expiresAt > Date.now()) return cached.groups;

  // Call Admin Directory API
  const { google } = require("googleapis");
  const auth = new google.auth.GoogleAuth({
    credentials: JSON.parse(
      Buffer.from(process.env.GOOGLE_DIRECTORY_SA_KEY, "base64").toString()
    ),
    scopes: ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"],
    clientOptions: { subject: "admin@apps.teamschools.org" },
  });
  const admin = google.admin({ version: "directory_v1", auth });

  let groups = [];
  let pageToken;
  do {
    const res = await admin.groups.list({ userKey: email, pageToken });
    groups = groups.concat(
      (res.data.groups ?? []).map((g) => g.email.split("@")[0])
    );
    pageToken = res.data.nextPageToken;
  } while (pageToken);

  const cubeGroups = groups.filter((g) => g.startsWith("cube-"));
  groupCache.set(email, { groups: cubeGroups, expiresAt: Date.now() + CACHE_TTL_MS });
  return cubeGroups;
},
```

### 5c. `queryRewrite`

Location filter priority: network → region → school → deny. Org-hierarchy filter
applied to staff cubes unless user has `cube-access-staff-all`.

```javascript
queryRewrite: (query, { securityContext }) => {
  const groups = securityContext?.groups ?? [];

  // Users without cube-access-student-data see no student cubes
  const STUDENT_CUBES = [
    "fct_student_attendance_daily",
    "fct_student_attendance_interventions",
    // ... full list populated during YAML implementation
  ];
  const hasStudentAccess = groups.includes("cube-access-student-data");
  if (!hasStudentAccess) {
    const filteredCubes = query.dimensions?.filter(
      (d) => !STUDENT_CUBES.some((c) => d.startsWith(c))
    );
    query = { ...query, dimensions: filteredCubes ?? [] };
  }

  // Location scope — evaluate in priority order
  const networkGroup = groups.find((g) => g.startsWith("cube-network-"));
  const regionGroup = groups.find((g) => /^cube-region-[^-]+-/.test(g));
  const schoolGroup = groups.find((g) => /^cube-school-[^-]+-/.test(g));

  let locationFilter = null;

  if (networkGroup) {
    // No location filter
  } else if (regionGroup) {
    const region = regionGroup.replace(/^cube-region-/, "").replace(/-(?:detail|summary)$/, "");
    locationFilter = {
      member: "dim_locations.region_key",
      operator: "equals",
      values: [region],
    };
  } else if (schoolGroup) {
    const slug = schoolGroup.replace(/^cube-school-/, "").replace(/-(?:detail|summary)$/, "");
    locationFilter = {
      member: "dim_locations.abbreviation",
      operator: "equals",
      values: [slug],
    };
  } else {
    // Default deny — no scope group
    return { ...query, filters: [{ member: "dim_locations.abbreviation", operator: "equals", values: [] }] };
  }

  const filters = [...(query.filters ?? [])];
  if (locationFilter) filters.push(locationFilter);

  // Org-hierarchy filter: inject segment defined in staff cube YAML
  const STAFF_CUBES = ["dim_staff", "fct_staff_attrition", "fct_staff_observations"];
  const touchesStaffCube = [...(query.dimensions ?? []), ...(query.measures ?? [])].some(
    (m) => STAFF_CUBES.some((c) => m.startsWith(c))
  );
  if (touchesStaffCube && !groups.includes("cube-access-staff-all")) {
    query.segments = [...(query.segments ?? []), "dim_staff.reporting_chain"];
  }

  return { ...query, filters };
},
```

!!! note "Staff cube list and segment" The full list of staff cubes and the
`reporting_chain` segment definition are populated during YAML implementation
(follow-up spec). The segment uses `SECURITY_CONTEXT.email` directly in its SQL
so BigQuery executes the subquery — Cube's REST API filter operators do not
support SQL subqueries. Example segment YAML:

    ```yaml
    segments:
      - name: reporting_chain
        sql: >
          {staff_key} IN (
            SELECT h.descendant_staff_key
            FROM kipptaf_marts.bridge_staff_hierarchy h
            JOIN kipptaf_marts.dim_staff s
              ON s.staff_key = h.ancestor_staff_key
            WHERE s.google_email = '{SECURITY_CONTEXT.email}'
          )
    ```

### 5d. `canSwitchSqlUser`

```javascript
canSwitchSqlUser: (current_user, new_user) =>
  current_user === "cube-superset-service" &&
  new_user.endsWith("@apps.teamschools.org"),
```

## Step 6 — `SETUP.md`

Brief engineer-facing guide. Three sections:

1. **Cube Cloud one-time setup** — reproduce the "Cube Cloud Setup" section from
   the spec verbatim
2. **Local dev** — `cp .env.example .env`, fill in `CUBE_GROUP_MAP`, run the VS
   Code task
3. **Warning** — do not use the Cube Playground Models tab in dev mode; it
   overwrites YAML files

## Step 7 — VS Code task

Add to `.vscode/tasks.json` `tasks` array:

```json
{
  "label": "Cube: Dev Server",
  "type": "shell",
  "command": "[ -d src/cube/node_modules ] || npm --prefix src/cube install && npm --prefix src/cube run dev",
  "presentation": {
    "reveal": "always",
    "panel": "dedicated",
    "focus": true
  },
  "problemMatcher": []
}
```

## Step 8 — `bridge_staff_hierarchy` dbt model

**Deferred.** Removed from this PR to keep scope focused on the cube
infrastructure scaffold (Steps 1–7). During implementation, investigation
revealed that `dim_staff_work_assignments.staff_key` is `NULL` for all
production rows due to a pre-existing OID vs. worker ID join mismatch in the
upstream intermediate model — meaning the bridge would only produce depth-0 rows
until that is resolved.

Tracked separately:

- **[#3729](https://github.com/TEAMSchools/teamster/issues/3729)** — fix
  `dim_staff_work_assignments.staff_key` (OID vs. worker ID join mismatch)
- `bridge_staff_hierarchy` model + exposure update to be added in a follow-on PR
  after #3729 is resolved

Staff cubes (`dim_staff`, `fct_staff_attrition`, etc.) and the `reporting_chain`
segment must wait for both of those before they can be added to the Cube
semantic layer.

## Validation

1. `npm --prefix src/cube install` — no errors
2. Start "Cube: Dev Server" VS Code task — Playground opens at `localhost:4000`
3. Set `CUBE_GROUP_MAP` to a network-detail user and confirm the Playground
   schema loads (no cubes yet — this validates connectivity and hook wiring)

## Out of scope

- Cube YAML model files — follow-up spec
- Pre-aggregations — follow-up spec
- Downstream integrations (Tableau, Superset, Streamlit) — follow-up spec
- Cube Cloud one-time setup — manual, performed in the Cube Cloud UI per the
  spec
- Google Group creation — separate IT admin task
