---
name: cube-ops
description:
  "Use when testing or diagnosing Cube outside the model files: verifying a
  measure backed by a new dbt column, testing row-level security locally,
  reading Cube Cloud diagnostic surfaces, or profiling Cube's BigQuery spend."
---

# cube-ops

## Profiling Cube's BigQuery spend

Query `region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT` with
`user_email = 'cube-cloud@teamster-332318.iam.gserviceaccount.com'`; attribute
per-mart via `regexp_extract_all(query, r'kipptaf_marts\.([a-z_]+)')`. Latency
pain shows in `total_slot_ms`, not bytes — view-chain recomputation is
compute-bound (#4464 moved the assessment star to tables for this).

## Diagnostic surfaces

- `/meta` returning `{"cubes": []}` ≠ model not deployed. With no matching
  `cube-*` group, access policies hide every cube — looks identical to an
  unpopulated branch. Compile a query via `/sql` to verify model presence before
  assuming the deployment is empty.
- **Empty `/meta` (or `WHERE (1 = 0)` / `rlsAccessDenied`) can also mean
  `resolveAccess` THREW and fail-closed to an empty context (`cube.js` `catch`),
  not that the viewer legitimately has no scope.** A BigQuery error inside
  `resolveAccess` (wrong billing project, missing `jobs.create`) default-denies
  EVERY viewer at once. Check Cube Cloud logs for
  `resolveAccess failed for <email>` before concluding it is an access-config
  problem. (Root-caused this session: `new BigQuery()` with no `projectId` /
  `credentials` billed the ambient-ADC project `cubejs-cloud`, where the
  identity lacked `jobs.create` — the data connection is fine because it is
  explicitly the `CUBEJS_DB_BQ_*` SA.)
- `/sql` compiles queries even against `public: false` members; `/load` enforces
  hiding. A `/load` 500 "You requested hidden member" with `/sql` succeeding =
  security-context delta, not a schema bug.
- `access_policy` default-deny (no `securityContext` group matches any policy on
  the view) manifests as `WHERE (1 = 0)` plus `rlsAccessDenied` in
  `sortedDimensions` of `/sql` output.
- **`/sql` reveals pre-aggregation coverage independent of access:** a covered
  query compiles to `FROM prod_pre_aggregations.<rollup>` (vs the fact view),
  and the access-deny `WHERE (1 = 0)` does not change the `FROM` — so you can
  confirm a query hits a rollup even as a default-denied viewer. A partitioned
  pre-agg has no base `prod_pre_aggregations.<name>` table (per-partition
  suffixes; the BQ staging table is dropped after load into Cube Store), so
  `count(*)` on it 404s — track builds via `JOBS_BY_PROJECT` for
  `cube-cloud@teamster-332318` instead.
- **Branch endpoints**: `/staging/<branch>/cubejs-api/v1` is the per-branch
  staging endpoint (stable, redeploys on push).
  `/user/<urlencoded-email>/<id>/cubejs-api/v1` is the per-developer Dev Mode
  endpoint. Only Dev Mode surfaces server `console.log` in the playground logs
  panel — staging has no log UI. Debug `cube.js` code paths on Dev Mode.
- **Branch staging configuration doesn't fully inherit from production.** Before
  diagnosing API errors on a branch staging env, verify the BigQuery connection
  variables (`CUBEJS_DB_TYPE`, `CUBEJS_DB_BQ_PROJECT_ID`,
  `CUBEJS_DB_BQ_CREDENTIALS`) are set on that environment. Also verify
  `dim_staff_cube_access` and `dim_staff_reporting_chain` exist in prod
  `kipptaf_marts` — branch staging reads prod, so identity resolution fails
  silently (default deny) if those models haven't been deployed yet.
- **Validate a cube against a Tableau dashboard from the workbook extract**:
  `unzip <workbook>.twbx`, then query `Data/Extracts/*.hyper` with
  `uv run --with tableauhyperapi python` (the data table is
  `"Extract"."Extract"`). Reproduce a Tableau categorical group (e.g. a
  Subject-Area "Literacy" bin) from its `<calculation class='categorical-bin'>`
  `<value>` list in the `.twb`. Cube side = the PR-branch fact joined to prod
  dims with the same filters.

## Testing Cube measures backed by new dbt columns

When a cube YAML references a column added in this branch (not yet in
`kipptaf_marts`), the playground errors: "Name X not found inside Y". To test
before merge:

1. Build in your dev schema:
   `uv run dbt run --select <model> --project-dir src/dbt/kipptaf --target dev`
   → creates `zz_<username>_kipptaf_marts.<model>`
2. Temporarily redirect the cube YAML to the dev schema — do NOT commit or push:
   - For `sql_table` cubes: change `sql_table: kipptaf_marts.<table>` to
     `sql_table: zz_<username>_kipptaf_marts.<table>`
   - For inline `sql:` cubes (e.g. `staff`, which LEFT JOINs
     `dim_staff_cube_access`): change the dataset reference(s) inside the `sql:`
     block. If `cube.js` also reads the same table directly (e.g.
     `dim_staff_cube_access` for identity resolution), redirect those queries
     too.
3. Test in the local dev server — launch the **`Cube: Dev Server`** VS Code task
   (`.vscode/tasks.json`; installs `src/cube/node_modules` if missing, then
   `npm --prefix src/cube run dev`). Hot-reloads on file save, no push required.
   **Claude CAN start the dev server** — run `npm run dev` with cwd `src/cube`
   as a BACKGROUNDED Bash call, redirect output to a log under
   `.claude/scratch/`, then poll that log for `is listening on 4000`. Only a
   FOREGROUND call fails (a server never exits, so it hangs to timeout); that is
   what the old "ask the user" guidance was working around. The VS Code task
   runs the identical command and injects no extra configuration, so prefer it
   only when the user wants the server visible in a terminal panel. Stop it with
   `pkill -f 'cubejs[-]server'` — the bracket is required, or the pattern
   matches the killing shell's own command line and kills it instead. Or
   commit+push for Cube Cloud Dev Mode.
4. Revert all dev-schema redirects to `kipptaf_marts.<table>` before committing.
   Verify with `grep -r "zz_" src/cube/` before pushing.

For **snowflake sub-dims** (cubes joined one-to-one from a parent), swap the
dataset reference on the sub-dim cube file, not the parent.

The security hook flags `zz_*` schemas as an access-control regression —
expected if you do commit the temporary change; acknowledge and revert.

**`zz_*` redirect — never `git add` the whole cubes/ dir while it's live.** When
a dev-schema redirect is in the working tree, staging with `git add -A`,
`git add .`, or `git add src/cube/model/cubes/` accidentally commits the
redirect. Name files explicitly in every `git add` while any cube YAML is
redirected.

**Never `bq cp` a dev-schema table into `kipptaf_marts` to unblock testing.**
`kipptaf_marts` is the live prod dataset read by all dashboards, the Cube
semantic layer, and dbt downstream models. Overwriting a mart table corrupts
prod for all consumers with no rollback path. Use the dev-schema redirect above
instead.

## Testing row-level security locally

RLS lives in per-view `access_policy` driven by the `securityContext` that
`resolveAccess` builds inside the auth hooks — so the setup below is REQUIRED to
exercise it; a plain dev server silently default-denies every gated view.

- **Testing RLS locally — SQL API is ground truth; the REST Playground also
  works in dev mode.** `checkSqlAuth` resolves identity from the connecting
  `user`: set `CUBEJS_PG_SQL_PORT` + `CUBEJS_SQL_USER`/`_PASSWORD`, connect via
  `psycopg` v3 (not `psycopg2` — see `scripts/cube_rls_matrix.py`) as the
  viewer's email in the SQL `user`, switch viewers per connection with no
  restart. (`CUBE_SQL_DEV_EMAIL=<viewer>` optionally pins every connection to
  one alias, overriding the connecting user — change + restart to switch.) It's
  the prod BI/Superset surface. Tesseract (`CUBEJS_TESSERACT_SQL_PLANNER`,
  default `true`) is the planner on both APIs and joining views is supported
  (multi-fact views); the old `JoinDefinitionStatic` note was a Playground
  observation, not a SQL-API limit — verified `student_days_view` /
  `staff_directory` / `student_assessment_scores_view` query cleanly.
  **`checkAuth` DOES run in dev mode (verified on Cube 1.6.59 and 1.7.14)** —
  the prior "REST skips auth in dev mode / needs `NODE_ENV=production`" claim
  was WRONG, and Cube's own
  `🔓 Authentication checks are disabled in developer mode` boot banner is
  misleading here: a signed `email` claim still resolves a full scope. To
  emulate over the REST Playground, paste `{"email": "<viewer>"}` into its
  Security Context editor and `resolveAccess` enriches it. Two gotchas: (1) a
  stale cached Playground token trips `checkAuth`'s `maxAge: "12h"` cap
  (`TokenExpiredError: maxAge exceeded`) — clear `localhost` local storage /
  re-save the context to re-mint a fresh token; (2) `resolveAccess` fail-closes
  to deny-all locally unless `CUBEJS_DB_BQ_CREDENTIALS` is set or the ADC
  fallback is present (a bare `JSON.parse("")` throws on the unset var). See
  #4526.
- **Dev mode downgrades an out-of-tier DENIAL to a quiet 0 rows — run the
  sign-off with auth ON**
  (`NODE_ENV=production CUBEJS_DEV_MODE=false npm run dev`). With auth on, a
  viewer requesting a member their tier excludes gets
  `You requested hidden member` (500) on REST and
  `Table or CTE with name '<view>' not found` on the SQL API; in dev mode both
  surfaces report 0 rows, which reads as a clean default-deny and is what makes
  a dev-mode matrix run falsely benign. **This is a MODE difference, not a Cube
  version difference** — verified across all four combinations of {1.6.59,
  1.7.14} × {dev, auth-on}, denial shape tracking the mode only (#4605). Scoped
  viewers return identical rows in both modes, so only the denial shape needs
  auth on.
- **Cube Cloud works via `contextToGroups` enrichment, not `checkAuth`
  (#4526).** Cube Cloud injects
  `{ cubeCloud: { username, groups, roles, userAttributes, meta, userCredentials }, iss: "cubecloud", exp }`
  with **no top-level `email`** until a Security Context is pasted — at which
  point the paste is merged into the top level and mirrored at
  `cubeCloud.userAttributes.email`. Observed on 1.7.14; do not trust the shape
  across versions. Symptom of enrichment not running: views hidden, only source
  tables, `WHERE (1 = 0)` — check the deployment log for
  `resolveAccess failed for` and that the BigQuery variables are set on **that**
  environment (branch environments do not inherit them).
- **Cube Cloud Explore's "Semantic SQL" tab IS a valid surface for testing the
  Cube Cloud path.** It accepts the SQL API dialect (dimensions bare,
  `MEASURE(measure)`, query the view not the cube) AND honors a pasted Security
  Context through `contextToGroups` — verified by pasting
  `{"email": "<viewer>"}` as an impersonator and getting the target's scope
  back. Do not assume "SQL" implies `checkSqlAuth`: that applies to the Postgres
  wire protocol on `CUBEJS_PG_SQL_PORT`, not this tab. Member names follow the
  view's `prefix:` settings, so a `prefix: true` join surfaces
  `<lastJoinPathSegment>_<member>` (`regions_region_name`,
  `dates_academic_year`).
- **The committed matrix tool is the RLS validation path** —
  `uv run scripts/cube_rls_matrix.py --viewers-file <local file>` opens one SQL
  connection per viewer email and runs the same query, so a scope difference is
  attributable to policy alone. Viewer emails are PII: pass them in, never
  hardcode, and summarize the output rather than pasting it anywhere external.
- **Emulation works on REST/MCP and on Cube Cloud** — locally, paste
  `{"email": "you@…", "act_as": "viewer@…"}` into the Playground security
  context (or sign the same payload); in Cube Cloud, paste
  `{"email": "viewer@…"}` and the caller is `cubeCloud.username`. Either way you
  need to be in `CUBE_IMPERSONATORS` on that deployment; unset = inert, and a
  caller not on the list keeps their own scope silently. Verified live on both
  surfaces: emulating a region-scoped viewer returns that region only.
- **The dev server always serves the MAIN checkout** — the `Cube: Dev Server`
  task runs `npm --prefix src/cube` from the workspace root, so branch changes
  to `cube.js` in a worktree are never exercised, and a worktree has no dotenv
  file anyway (gitignored). Check the branch out in the main checkout for local
  Cube work. Symptom of getting this wrong: every viewer returns 0 rows while
  ADC is healthy.
- **`CUBE_GROUP_MAP` cannot validate `row_level`** — it supplies `groups` only,
  not the `region_key` / `allowed_abbreviations` / `reportee_staff_keys` the
  filters interpolate, and it sits in the resolution path shared by both auth
  hooks, so it corrupts REST and SQL alike. No longer shipped in the example
  config; leave it unset (an older local copy may still carry it, with stale
  group names that deny everything).
- **Branch models aren't in prod.** Cubes + `resolveAccess` read
  `kipptaf_marts`. When the branch reworks a mart they read
  (`dim_staff_cube_access`, `dim_staff_reporting_chain`): build it to your dev
  schema (`dbt build --target dev --defer --select <models>`), RE-STAGE any
  changed Google-Sheets external first (`stage_external_sources --target dev`
  `ext_full_refresh: true`) or the staging model fails its contract on the stale
  external, then redirect ONLY the changed identity tables in `cube.js` + cube
  YAML to `zz_<user>_kipptaf_marts`. Do NOT redirect `dim_work_assignment_jobs`
  (the `staff` cube reads `job_function_code` from `dim_staff_cube_access`, not
  it; redirecting it breaks its surrogate-key join to prod
  `dim_staff_work_assignments`). Uncommitted scaffold — revert +
  `grep -r zz_ src/cube` before committing.
- **Validate location scoping with `student_days.count_students` over a date
  range.** It is unanchored and seasonal-safe — the fact carries a row for every
  enrolled calendar day including breaks, so it returns real numbers year-round
  and a 0 can only mean a scope denial. That is the query
  `scripts/cube_rls_matrix.py` ships as its default.
