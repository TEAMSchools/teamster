# Cube Cloud Integration Design

**Date:** 2026-03-17 **Status:** Approved

## Overview

Integrate Cube Cloud Enterprise with the teamster repository so that cube and
view definitions live alongside dbt models in the same repo, are editable in VS
Code, and are deployed automatically by Cube Cloud via Git sync.

## Goals

- Cube model files (`src/cube/model/`) live in the teamster repo and go through
  the same PR/review process as dbt models
- Cube Cloud handles all deployment infrastructure (no self-hosted Docker/Cloud
  Run needed)
- Cube Cloud's dbt integration pulls metadata (descriptions, column types) from
  dbt Cloud project `211862` so documentation is not duplicated
- Developers can validate changes locally (Cube Core) before pushing to the Cube
  Cloud dev deployment for full Cloud feature testing

## Non-goals

- Self-hosted Cube deployment (Dockerfile, Cloud Run, GitHub Actions deploy
  workflow) — replaced entirely by Cube Cloud Git sync
- dbt Semantic Layer as Cube data source — Cube reads BigQuery `kipptaf_marts`
  directly; dbt integration is for metadata enrichment only
- New cube/view model work — this design covers the integration setup only;
  model expansion happens in subsequent PRs

## Repository Structure

```text
src/cube/
  cube.js                # Cube config: schemaPath, dbt Cloud integration,
                         #   contextToGroups, canSwitchSqlUser
  package.json           # @cubejs-backend/server dependency + dev script
  package-lock.json
  .env.example           # Required env vars for local development
  .gitignore
  model/
    cubes/               # Carried over from claude/feat/cube-semantic-layer:
      dim_dates.yml        dim_locations.yml  dim_seats.yml
      dim_staff.yml        dim_students.yml   dim_terms.yml
      fct_additional_earnings.yml             fct_attendance.yml
      fct_attendance_communications.yml       fct_attendance_interventions.yml
      fct_internal_assessments.yml            fct_microgoals.yml
      fct_staff_attrition.yml                 fct_staff_benefits_enrollments.yml
      fct_staff_terminations.yml              fct_state_assessments.yml
    views/               # Carried over:
      attendance_metrics.yml
      staff_information_metrics.yml
  SETUP.md               # Cube Cloud one-time setup + local dev guide
```

**Removed** from the feature branch (no longer needed):

- `Dockerfile`
- `docker-compose.yml`
- `.github/workflows/deploy-cube.yaml`

## Cube Cloud Setup (one-time)

Performed in the Cube Cloud UI (`app.cubecloud.dev`):

1. Connect the `TEAMSchools/teamster` GitHub repo
2. Set **Cube project path** to `src/cube/`
3. Set **production branch** to `main` — merges trigger automatic redeploy
4. Create a **dev deployment** — in Cube Cloud Enterprise, dev deployments are
   typically one per engineer (not one per feature branch). Each engineer points
   their dev deployment at their current feature branch and updates that mapping
   as they switch branches
5. Set environment variables per deployment (see below) — never committed to the
   repo

### Environment Variables

| Variable                   | Notes                                                                  |
| -------------------------- | ---------------------------------------------------------------------- |
| `CUBEJS_DB_TYPE`           | `bigquery`                                                             |
| `CUBEJS_DB_BQ_PROJECT_ID`  | `teamster-332318`                                                      |
| `CUBEJS_DB_BQ_CREDENTIALS` | `cube-bq-reader` SA key JSON, **base64-encoded** (`base64 < key.json`) |
| `CUBEJS_API_SECRET`        | Random 64-char string; use a separate value per deployment             |
| `CUBE_GROUP_MAP`           | Email→groups JSON string; can differ per deployment                    |
| `DBT_CLOUD_TOKEN`          | dbt Cloud service token (read-only scope)                              |
| `DBT_CLOUD_PROJECT_ID`     | `211862`                                                               |

The `cube-bq-reader` BigQuery service account defined in the feature branch's
SETUP.md can be reused — the required permissions are identical.

## cube.js Configuration

The non-dbt parts of `cube.js` carry over unchanged from the feature branch:

```js
module.exports = {
  schemaPath: "model",

  // dbt integration config — see note below

  contextToGroups: ({ securityContext }) => {
    const email = securityContext?.u?.mail;
    if (!email) return ["default"];
    const groupMap = JSON.parse(process.env.CUBE_GROUP_MAP || "{}");
    return groupMap[email] || ["default"];
  },

  canSwitchSqlUser: () => true,
};
```

**dbt integration config — confirm before implementing:** The exact `cube.js`
API for dbt Cloud integration must be verified against the
[Cube dbt integration docs](https://cube.dev/docs/product/configuration/data-modeling/dynamic-data-models/dbt)
for the version in use. Two likely options:

- **Option A — dbt Cloud API** (preferred): Cube fetches the compiled manifest
  directly from dbt Cloud at startup. The config key may be `dbt.cloud` or a
  similar block accepting `serviceToken` and `projectId`. Uses `DBT_CLOUD_TOKEN`
  and `DBT_CLOUD_PROJECT_ID` env vars.

- **Option B — local manifest**: Cube reads a `manifest.json` generated by
  `dbt compile` or `dbt build`. The config key is a path reference (exact key
  TBD from docs). Requires the manifest to be generated before starting Cube;
  the manifest is **not** committed to the repo.

For local development, Option B is simpler (no API token needed) — run
`uv run dbt compile --project-dir src/dbt/kipptaf` first to generate the
manifest, then start Cube. Confirm the path resolution with Cube docs.

## Local Development Workflow

Two levels, each suited to different stages of iteration:

### Level 1 — Cube Core (`localhost:4000`)

Fast feedback for YAML syntax, measure/dimension definitions, and basic query
shapes. No push needed.

```bash
cd src/cube
cp .env.example .env   # minimum required values:
                       #   CUBEJS_DB_TYPE=bigquery
                       #   CUBEJS_DB_BQ_PROJECT_ID=teamster-332318
                       #   CUBEJS_API_SECRET=<any string>
                       #   CUBEJS_DEV_MODE=true        # enables Playground UI
                       #   CUBEJS_CACHE_AND_QUEUE_DRIVER=memory  # CubeStore binary is incompatible with the devcontainer; use in-memory queue instead
                       #   DBT_PROJECT_PATH=../dbt/kipptaf  # for local manifest
gcloud auth application-default login   # ADC handles BigQuery auth locally
npm install
npm run dev            # opens Cube Core Playground at localhost:4000
```

> **Warning:** Do not use the Playground's built-in model editor (the Models
> tab). In dev mode Cube treats it as a live editor and will overwrite your YAML
> files. Edit in VS Code only.

### Level 2 — Cube Cloud dev deployment

Full Cube Cloud UI (Playground, SQL runner, access policy testing). Requires a
push.

1. Push your feature branch
2. Cube Cloud dev deployment picks it up automatically
3. Log into `app.cubecloud.dev`, select the dev deployment
4. Use Playground/SQL runner against real BigQuery data via the Cloud SA

## Day-to-Day Development Cycle

1. Create a feature branch (`yourname/feat/description`)
2. Edit `src/cube/model/` YAML files in VS Code
3. Validate locally with `npm run dev` (Level 1)
4. Push branch → Cube Cloud dev deployment updates
5. Test in Cube Cloud UI against production BigQuery data (Level 2)
6. Open PR → merge to `main` → production deployment updates automatically

## dbt Exposure

`src/dbt/kipptaf/models/exposures/cube.yml` needs two updates when the model
files are carried over:

1. **Add `url:`** once the Cube Cloud deployment URL is known
2. **Expand `depends_on`** to include all 16 carried-over cube models — the
   current file lists only 8; the 8 missing are: `fct_additional_earnings`,
   `fct_attendance_communications`, `fct_attendance_interventions`,
   `fct_internal_assessments`, `fct_staff_attrition`,
   `fct_staff_benefits_enrollments`, `fct_staff_terminations`,
   `fct_state_assessments`

Per `src/dbt/kipptaf/CLAUDE.md`: every external tool consuming kipptaf data must
list all `depends_on` models in its exposure. Three mart models that exist in
the repo — `dim_assessment_goals`, `dim_state_assessment_benchmarks`,
`fct_student_course_enrollments` — are intentionally **not** in this list
because no cube model file reads them. They will be added to the exposure when
corresponding cube models are built.

The `url:` field is required by the exposure convention but cannot be populated
until the Cube Cloud deployment URL is known. It must be added before or in the
same PR that wires up Cube Cloud (not deferred indefinitely).

```yaml
exposures:
  - name: cube_semantic_layer
    label: Cube Semantic Layer
    type: ml
    url: https://<org>.cubecloud.dev # add once known
    owner:
      name: Data Team
    depends_on:
      - ref("dim_dates")
      - ref("dim_locations")
      - ref("dim_seats")
      - ref("dim_staff")
      - ref("dim_students")
      - ref("dim_terms")
      - ref("fct_additional_earnings")
      - ref("fct_attendance")
      - ref("fct_attendance_communications")
      - ref("fct_attendance_interventions")
      - ref("fct_internal_assessments")
      - ref("fct_microgoals")
      - ref("fct_staff_attrition")
      - ref("fct_staff_benefits_enrollments")
      - ref("fct_staff_terminations")
      - ref("fct_state_assessments")
```

## Out of Scope / Future Work

- Pre-aggregations for `fct_attendance` and `fct_internal_assessments`
- Additional views for internal assessments, state assessments, staffing
- `fct_observations` once the pm-observations star schema model lands
- Tableau semantic layer sync in `cube.js`
