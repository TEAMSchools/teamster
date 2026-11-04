# Cube MCP: complete read-only coverage of the Cube REST API

Issue: [#5930](https://github.com/TEAMSchools/teamster/issues/5930)

## Intent

The Cube MCP server (`src/cube/mcp/server.py`) is the way claude.ai users and
data-team Codespaces reach Cube. Today it wraps 3 endpoints (`/v1/meta`,
`/v1/load`, `/v1/sql`) and its tool descriptions have drifted from the live API.
Charlie wants it to be a feature-complete wrapper over every read-only Cube REST
endpoint, with descriptions that match what the API actually does and responses
small enough to fit a model's context.

## Goals

- Every read-only Cube REST endpoint is reachable through an MCP tool.
- Every tool description matches the live API: accepted fields, operators, and
  response shape.
- No tool returns tens of KB of Cube internals by default.
- Row-level access is identical on every tool: each call carries the caller's
  own signed token through `checkAuth` → `resolveAccess`.

## Non-goals (decided by Charlie, 2026-10-15)

- `POST /v1/pre-aggregations/jobs`. It starts rollup builds, and each
  `proficiency_rollup` build scans the full scores fact per partition. Any
  claude.ai user could trigger spend with it.
- `GET/POST /v1/subscribe`. It is a WebSocket stream and does not fit
  request/response tool calls.
- `/readyz`, `/livez`. Deployment health checks for operators, not analysts.
- Cube Cloud Metadata API (`/v1/entities*`, `/v1/data-sources`). It needs a
  token with a different scope than the one `_mint_token` signs.
- `POST /v1/pre-aggregations/can-use`. It takes a `transformedQuery` from Cube
  internals, not a user query. `dry_run` and the trimmed `sql` cover the same
  question.
- The SQL API's Postgres-wire endpoint (`CUBEJS_PG_SQL_PORT`). It authenticates
  through `checkSqlAuth` with a username and password. Wrapping it would need
  either the `__user` super-user switch (the server could act as anyone) or
  per-user SQL credentials that do not exist. `SET sql_user` also does not
  persist across stateless tool calls. The SQL API dialect stays reachable
  through `cubesql` below.
- `DELETE /v1/running-query/{requestId}` (query cancel). It changes state in
  Cube, and its 1.8.5 handler does not check that the query belongs to the
  caller. Deferred to
  [#5933](https://github.com/TEAMSchools/teamster/issues/5933), which also
  carries the request-id plumbing it would need.

## Anti-goals

- A new tool that bypasses the caller's row-level access, or that runs as any
  identity other than the caller's email.
- A default response large enough to crowd a model's context, which is the
  problem the `sql` tool has today.
- A tool description that names a member, group, or field the live API does not
  have.

## Constraints

- Total tool wall-clock stays under 60 seconds (Claude Code's per-tool timeout).
  The existing `TIMEOUT_SECONDS = 55` deadline and `Continue wait` polling apply
  to every new data tool.
- `stateless_http=True` stays. No tool may depend on session state between
  calls.
- Model guidance goes in per-tool docstrings, not `instructions=`, because the
  claude.ai connector drops `instructions=` (#4473).
- Queries keep the UTC timezone default (`_with_default_timezone`) unless the
  caller passes a timezone.
- After deploy, claude.ai users must refresh the connector to see new tools and
  descriptions. The PR says so.
- Verified against `@cubejs-backend/api-gateway` 1.8.5, the version
  `src/cube/package-lock.json` pins. Cube Cloud's running version is not
  verified.

## Tools

| Tool              | Endpoint                   | Status                                |
| ----------------- | -------------------------- | ------------------------------------- |
| `meta`            | `GET /v1/meta`             | unchanged                             |
| `load`            | `POST /v1/load`            | description expanded                  |
| `sql`             | `POST /v1/sql` (or `GET`)  | default response trimmed; `full` flag |
| `dry_run`         | `POST /v1/dry-run`         | new                                   |
| `cubesql`         | `POST /v1/cubesql`         | new                                   |
| `convert_query`   | `POST /v1/convert-query`   | new                                   |
| `graphql_to_json` | `POST /v1/graphql-to-json` | new                                   |

### `load`

Behavior unchanged. The description documents every field in `querySchema`
(`dist/src/query.js`): `measures`, `dimensions`, `filters` (including `or`/`and`
groups), `timeDimensions` (including `compareDateRange`), `segments`, `order`,
`limit`, `offset`, `total`, `timezone`, `ungrouped`, `responseFormat`
(`default`/`compact`/`columnar`), `cacheMode`
(`stale-if-slow`/`stale-while-revalidate`/`must-revalidate`/`no-cache`),
`joinHints`, `subqueryJoins`, and `maskedMembers`. It lists all 24 filter
operators. It recommends `responseFormat: "compact"` for large results and
replaces the single-date advice with `onTheDate`. It states Cube's row limits
(default 10,000 with no `limit`, error above 50,000, from
`CUBEJS_DB_QUERY_DEFAULT_LIMIT`/`CUBEJS_DB_QUERY_LIMIT`) and says to page with
`limit`/`offset` plus `total: true`. Confirm Cube Cloud does not override the
defaults before writing the numbers into the description.

The response already carries `usedPreAggregations`; the description says so.

### `sql`

Default response is a trimmed object:

- the compiled SQL string and its parameters (`sql.sql`)
- `external`
- the ids of the pre-aggregations the query would use
  (`preAggregations[].preAggregationId`)

The trimmed response does not use `canUseTransformedQuery` (decided by Charlie).
The 1.8.5 gateway marks that field dev/Playground-only
(`getSqlQueriesInternal`), so building on it works against Cube's intent. The
description sends "why didn't this use a pre-aggregation?" questions to
`dry_run`, which always returns the matching detail.

`full: true` returns Cube's raw payload unchanged. The description states both
shapes and states that a query served by a rollup compiles to
`FROM prod_pre_aggregations.<rollup>`.

### `dry_run`

Wraps `/v1/dry-run`. Returns `queryType`, `normalizedQueries`, `queryOrder`,
`pivotQuery`, and `transformedQueries` (Cube's per-query pre-aggregation
matching checks). The description says when to prefer it over `sql`: checking a
query's validity and normalization without compiling SQL, and finding out why a
query did or did not match a pre-aggregation.

Claude's call: `dry_run` gets the same trim and `full` flag as `sql`. `dryRun`
returns raw `canUseTransformedQuery` objects without `sanitizeSqlQuery`, so by
default `transformedQueries` comes back as a summary, not Cube's full objects.

### `cubesql`

Wraps `/v1/cubesql`: SQL API dialect over REST (`MEASURE()`, query the view not
the cube). Cube streams newline-delimited JSON; the first object carries
`schema`, `lastRefreshTime`, and `usedPreAggregations`, and later objects carry
`data` chunks. The tool reads the whole stream within the deadline and returns
one object. It carries the same PII guidance as `load`.

Claude's calls:

- Row limits (decided by Charlie): the tool imposes none and reads the whole
  stream. Cube's own limits apply, as they do for `load`. The description tells
  callers to page with `LIMIT`/`OFFSET`.
- Long-running queries: send `throwContinueWait: true` and re-send the SQL on
  `Continue wait` inside the 55-second deadline. This is the same pattern `load`
  uses, since its polling also re-sends the full query.

### `convert_query`

Wraps `/v1/convert-query` with `input: "sql"`, `output: "rest"`. Turns a SQL API
query into a REST query object that `load` accepts.

### `graphql_to_json`

Wraps `/v1/graphql-to-json`. Turns a Cube GraphQL query into a REST query
object.

## Text fixes

- Remove every `cube-*` Workspace group reference (`server.py` module docstring,
  `UserEmailPrompt` field description, `meta` and `sql` docstrings,
  `.claude/skills/cube-ops/SKILL.md`). Name the real causes of an empty catalog
  or `WHERE (1 = 0)`: no `dim_staff_cube_access` row for the email, a `none`
  scope on that axis, or `resolveAccess` failing closed.
- Correct the `sql` response shape in its description.
- `src/cube/mcp/CLAUDE.md`: drop "`/sql` is GET-only"; update the Tools list.

## Testing

Each tool gets a test in `tests/cube/test_mcp_server.py` against a mocked HTTP
transport, asserting the method, path, body, and `Authorization` header it
sends. Plus:

- the trimmed `sql` response for a recorded sample payload is under 5 KB
- `cubesql` assembles a multi-chunk newline-delimited response into one result
- no tool docstring contains `cube-*`

## Left to the builder

- Python names and signatures for the new tools, and the shape of the
  `transformedQueries` summary in the trimmed `dry_run` response.
- GET versus POST where Cube accepts both.
- Whether to run the `eval/` harness on the new descriptions.

## Open, to verify during the build

- Whether `/v1/cubesql` answers catalog queries (`information_schema`,
  `pg_catalog`). If not, its description says so and points schema questions to
  `meta`.
