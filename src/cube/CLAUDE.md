# CLAUDE.md — `src/cube/`

Cube semantic layer. BigQuery driver; cubes read from `kipptaf_marts` tables
produced by [`src/dbt/kipptaf/`](../dbt/kipptaf/). Setup, env vars, and Cube
Cloud deployment: [`docs/guides/cube.md`](../../docs/guides/cube.md).

Authoring conventions, view access policies, and the `cube.js` security model
load from `.claude/rules/cube-authoring.md` on the first read of a model file or
`cube.js`. Local testing, row-level-security verification, diagnostics, and
spend profiling: invoke the `cube-ops` skill.

## Layout

```text
src/cube/
  cube.js                   # Auth, group resolution, queryRewrite, sql-user gating
  package.json              # Cube server + bigquery driver + googleapis
  .env.example              # Hook-blocked for Claude — but its local values are
                            # documented verbatim in docs/guides/cube.md, so read
                            # them there instead of asking the user to paste
  access.js                 # Pure access + emulation logic (unit-tested)
  access.test.js            # node --test
  cube.test.js              # node --test — hook tests, CUBE_GROUP_MAP-stubbed
  model/
    cubes/
      <domain>/<name>.yml   # Fact and dim cubes — private at cube level
      conformed/            # Shared dims joined from multiple fact cubes
    views/
      <domain>/<name>.yml   # Analyst-facing views — the only public surface
```

One cube or view per file. Filename matches `name:`. New cubes go under
`cubes/<domain>/`; cross-domain shared dims (dates, regions, locations, terms,
school_calendars) go in `cubes/conformed/`.

## MCP access (cube)

The `cube` MCP wraps Cube Cloud's REST API. Auth path that works:

- Mint HS256 JWT locally per request from `CUBE_API_SECRET` (1P:
  `op://Data Team/Cube Cloud REST API/credential`).
- The **entire JWT payload is `securityContext`** — top-level `email` claim
  flows into `cube.js`'s `checkAuth`, which resolves it via `resolveAccess` into
  the enriched `securityContext` every view's `access_policy` reads. Not nested
  under `u`/`securityContext`/`userContext`.
- `Authorization` header is raw token — **no `Bearer` prefix** (Cube Cloud
  Metadata API exception per docs is a footnote, not the norm).
- Cube Cloud "Personal Core Data API Token" (PAT) returns 403 against `/meta`
  even with the right format — labeled "for SQL API connections" and behaves
  that way. JWT-from-secret is the only reliable path.
- Cube SQL API `SET sql_user TO '...'` does NOT persist across MCP `execute_sql`
  calls (each call = fresh Postgres connection). REST is the right abstraction
  for stateless tool calls.

## Operational notes

- **Never use the Cube Playground Models tab.** It overwrites YAML in
  `model/cubes/` and `model/views/` with auto-generated content, discarding
  hand-authored definitions.
- **No manual deploy command.** Production redeploys are triggered by merges to
  `main` in Cube Cloud; do not propose a deploy step.
- **`CUBEJS_API_SECRET` is deployment-wide; every OTHER variable is
  per-environment.** Confirmed in the Cube Cloud console (2026-08-06): a branch
  environment shows the SAME generated API secret as production, while
  `CUBEJS_DB_BQ_*` and other config are separately editable per environment. So
  a token minted for a branch staging endpoint is verified by PRODUCTION's
  `checkAuth` against the same secret — it is mechanically a production
  credential, and a holder can claim any `email` and read all of
  `kipptaf_marts`. The bypass sits at signature verification, upstream of
  `resolveAccess` and every `access_policy`, so no view or policy change
  mitigates it. **Never hand a branch endpoint or a branch-minted token to
  anyone outside the network** — external access needs a SEPARATE DEPLOYMENT,
  which gets its own generated secret. The corollary is legitimate and useful:
  pointing a branch's `CUBEJS_DB_BQ_PROJECT_ID` at a sandbox project tests the
  model against synthetic data with zero YAML changes (every `sql_table:` is
  project-unqualified, and `resolveAccess` reads the same project), which stays
  internal-only precisely because the branch cannot carry its own credential.
