# Cube MCP REST Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `src/cube/mcp/server.py` a complete read-only wrapper over the
Cube REST API, with accurate descriptions and small default responses.

**Architecture:** One file, `server.py`, keeps every tool. New tools reuse
`_request` (auth, error, `Continue wait` polling). `cubesql` needs a streaming
reader, so it gets one small private helper beside `_request`. Trimming is two
pure functions, tested directly.

**Tech Stack:** Python 3.13, mcp SDK 2.0 `MCPServer`, httpx, PyJWT, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-cube-mcp-rest-coverage-design.md`

All paths below are relative to the worktree
`/workspaces/teamster/.claude/worktrees/cbini/feat/claude-cube-mcp-rest-coverage`.
Run every command from there with `uv run`. Use `git -C <worktree>` for git.

## Global Constraints

- Total tool wall-clock under 60 s; reuse `TIMEOUT_SECONDS = 55`.
- `stateless_http=True` stays; no tool keeps state between calls.
- Model guidance goes in tool docstrings, not `instructions=`.
- Every query-object tool passes its query through `_with_default_timezone`.
- No tool-side row limits. Cube's own limits apply.
- `canUseTransformedQuery` is never read to build a default response.
- No docstring names `cube-*` groups. Empty catalog / `WHERE (1 = 0)` causes: no
  `dim_staff_cube_access` row for the email, a `none` scope on that axis, or
  `resolveAccess` failing closed.
- Gateway source of truth: `src/cube/node_modules/@cubejs-backend/api-gateway`
  1.8.5 (`dist/src/gateway.js`, `dist/src/query.js`). Run `npm ci` in
  `src/cube/` (main checkout) if it is missing.
- Tests: `uv run pytest tests/cube/test_mcp_server.py -v`. Never bare `pytest`.
- Live probes (`tests/cube/test_zz_*.py`): load the server with the real
  `CUBE_REST_URL`/`CUBE_API_SECRET` from the conftest secrets, set
  `server.client = httpx.AsyncClient(base_url=server.CUBE_REST_URL, timeout=55)`
  (the lifespan does not run under pytest), and set `CUBE_USER_EMAIL` to the
  user's email. If conftest does not supply the Cube secrets, stop and ask the
  user rather than skipping the probe.

## Endpoint facts (from gateway 1.8.5)

| Tool              | Request                                                                    | Response                                                                                                                                 |
| ----------------- | -------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `sql`             | `POST /sql` `{"query": <obj>}`                                             | `{"sql": {"sql": [str, list], "preAggregations": [...], "external": bool, ...}}`                                                         |
| `sql` (SQL input) | `POST /sql` `{"query": <str>, "format": "sql"}`                            | `{"sql": <sql4sql result>}`; needs `sql` scope (default scopes include it)                                                               |
| `dry_run`         | `POST /dry-run` `{"query": <obj>}`                                         | `{queryType, normalizedQueries, queryOrder, transformedQueries, pivotQuery}`                                                             |
| `cubesql`         | `POST /cubesql` `{"query": <str>, "timezone", "throwContinueWait": true}`  | chunked NDJSON: first line `schema`/`lastRefreshTime`/`usedPreAggregations`, then `{"data": [...]}` lines; an error line carries `error` |
| `convert_query`   | `POST /convert-query` `{"input": "sql", "output": "rest", "query": <str>}` | rest query object (from native `rest4sql`)                                                                                               |
| `graphql_to_json` | `POST /graphql-to-json` `{"query": <str>, "variables": <obj>}`             | `{"jsonQuery": <obj>}`; on a parse error Cube returns `{"jsonQuery": null}` with HTTP 200                                                |

`CUBE_REST_URL` already ends in `/cubejs-api/v1`, so paths are `/sql`, not
`/v1/sql`, matching the existing `/load` and `/meta` calls.

## Review Focus

1. `graphql_to_json` gets `{"jsonQuery": null}` for a bad query: the tool must
   raise a clear error, not return `null` as if it worked. Test in Task 5.
2. `cubesql` stream with an `error` line partway through (or as the only line):
   the tool raises with Cube's message, not a JSON decode error or a silent
   partial result. Test in Task 4.
3. `cubesql` gets `Continue wait` on every attempt: the tool stops at the
   deadline with the same message shape `load` uses. Test in Task 4.
4. `sql` response with no `preAggregations` key (a query no rollup covers):
   trimmed response has `preAggregations: []`, no `KeyError`. Test in Task 2.
5. `dry_run` with a multi-query (`compareDateRange`) query: `transformedQueries`
   has several entries, and each one is summarized. Test in Task 3.

---

### Task 1: Fix stale access text and the `load` description

**Files:**

- Modify: `src/cube/mcp/server.py:10-27` (module docstring), `:68-75`
  (`UserEmailPrompt`), `:405-407` (`meta` docstring), `:442-530` (`load`
  docstring)
- Modify: `.claude/skills/cube-ops/SKILL.md` (line with `cube-*`)
- Test: `tests/cube/test_mcp_server.py`

**Interfaces:**

- Produces: `ACCESS_DENIED_CAUSES: str` module constant in `server.py`, the one
  sentence naming the three causes above. `meta` and `sql` docstrings embed it.
  Docstrings are literals, so the constant is for tests and error text only;
  write the same sentence into each docstring.

- [ ] **Step 1: Write the failing tests**

```python
def test_no_docstring_names_cube_groups(monkeypatch):
    server = _load_server(monkeypatch)
    texts = [server.__doc__, server.UserEmailPrompt.model_fields["email"].description]
    texts += [t.fn.__doc__ for t in server.mcp._tool_manager.list_tools()]
    for text in texts:
        assert "cube-*" not in (text or "")


def test_load_docstring_lists_every_operator_and_field(monkeypatch):
    server = _load_server(monkeypatch)
    doc = server.load.__doc__
    for op in [
        "equals", "notEquals", "contains", "notContains", "startsWith",
        "notStartsWith", "endsWith", "notEndsWith", "in", "notIn", "gt", "gte",
        "lt", "lte", "set", "notSet", "inDateRange", "notInDateRange",
        "onTheDate", "beforeDate", "beforeOrOnDate", "afterDate",
        "afterOrOnDate", "measureFilter",
    ]:
        assert f"`{op}`" in doc, op
    for field in [
        "ungrouped", "responseFormat", "cacheMode", "compareDateRange",
        "joinHints", "subqueryJoins", "maskedMembers", "usedPreAggregations",
    ]:
        assert field in doc, field
```

Check how mcp SDK 2.0 lists registered tools before writing the first test
(`mcp._tool_manager` is the 1.x name). Use whatever accessor 2.0 exposes; if
none, list the tool functions by name (`server.meta`, `server.load`, ...).

- [ ] **Step 2: Run tests to verify they fail**

Run:
`uv run pytest tests/cube/test_mcp_server.py -k "cube_groups or every_operator" -v`
Expected: both FAIL (`cube-*` found; `notContains` missing).

- [ ] **Step 3: Rewrite the text**

- Module docstring: the email is the JWT security context; `cube.js` `checkAuth`
  → `resolveAccess` maps it to access from `dim_staff_cube_access`. Tools list
  gets all seven tools.
- `UserEmailPrompt` description: "Used as the JWT security context; Cube
  resolves your access from it."
- `meta` empty-catalog paragraph: the three causes.
- `load`: list all 24 operators; document the fields in the test; replace the
  single-date advice with `onTheDate` (keep `timeDimensions` + `dateRange` for
  ranges and granularity); recommend `responseFormat: "compact"` for large
  results; state the response carries `usedPreAggregations`; state row limits
  (default 10,000 with no `limit`, error above 50,000) and paging with
  `limit`/`offset` plus `total: true`. Keep every existing paragraph on grain,
  academic year, string numerics, PII, and timezone.
- `cube-ops/SKILL.md`: replace the `cube-*` line with the three causes. Read the
  file with the Read tool first.

Before writing the row-limit numbers, check that Cube Cloud does not override
them. Write a throwaway credentialed test (`tests/cube/test_zz_limit_probe.py`,
per `tests/CLAUDE.md`) that calls `server.load` with one dimension on a view
with more than 10,000 rows and no `limit`, then with `limit: 50001`. Print only
`len(result["data"])` and the error text, never row values. Delete the file
after. If the results are not 10,000 rows and a limit error, write the numbers
you observed and note them in the PR.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/cube/mcp/server.py tests/cube/test_mcp_server.py .claude/skills/cube-ops/SKILL.md
git -C <worktree> commit -m "fix(cube): correct Cube MCP access text and document every load option"
```

### Task 2: Trim `sql` and accept SQL API input

**Files:**

- Modify: `src/cube/mcp/server.py` (`sql` tool)
- Test: `tests/cube/test_mcp_server.py`
- Create: `tests/cube/fixtures/cube_sql_response.json` (recorded sample)

**Interfaces:**

- Produces: `_trim_sql(body: dict[str, Any]) -> dict[str, Any]`, returning
  `{"sql": <body["sql"]["sql"]>, "external": <body["sql"].get("external")>, "preAggregations": [<preAggregationId>, ...]}`.
- Produces:
  `sql(ctx, query: dict[str, Any] | str, full: bool = False) -> dict[str, Any]`.
  A `str` query is SQL API SQL: `POST /sql` with
  `{"query": query, "format": "sql"}`, returned unchanged (it is already small).
  A `dict` query: `POST /sql` with `{"query": _with_default_timezone(query)}`,
  trimmed unless `full`.

Spec deviation, flagged for the user's review: the spec missed `format: "sql"`
on `/v1/sql` (compile a SQL API query to warehouse SQL). It is read-only and
belongs to "every read-only endpoint," so `sql` takes it.

- [ ] **Step 1: Record the fixture**

Call the live `mcp__claude_ai_Cube__sql` tool with the 2026-10-15 sample query
(`student_assessment_scores_view.avg_percent_correct`, `pct_proficient`, the
spec's filters). Save the raw response to
`tests/cube/fixtures/cube_sql_response.json`. Before saving, check it holds no
PII values: it is compiled SQL plus member names, but filter values land in the
params list; replace any student or staff identifier with `"Student A"`.

- [ ] **Step 2: Write the failing tests**

```python
FIXTURES = Path(__file__).parent / "fixtures"


def test_trim_sql_is_small_and_keeps_sql_and_preaggs(monkeypatch):
    server = _load_server(monkeypatch)
    raw = json.loads((FIXTURES / "cube_sql_response.json").read_text())
    trimmed = server._trim_sql(raw)
    assert len(json.dumps(trimmed)) < 5_000
    assert trimmed["sql"] == raw["sql"]["sql"]
    assert trimmed["preAggregations"] == [
        p["preAggregationId"] for p in raw["sql"].get("preAggregations", [])
    ]
    assert "canUseTransformedQuery" not in json.dumps(trimmed)


def test_trim_sql_without_preaggregations(monkeypatch):
    server = _load_server(monkeypatch)
    trimmed = server._trim_sql({"sql": {"sql": ["SELECT 1", []]}})
    assert trimmed["preAggregations"] == []


def test_sql_posts_object_query_and_trims(monkeypatch):
    ...  # fake _request records (method, path, kwargs); returns the fixture
    # assert ("POST", "/sql") and kwargs["json"] == {"query": {..., "timezone": "UTC"}}
    # assert result == server._trim_sql(fixture)
    # full=True: result == fixture


def test_sql_posts_sql_string_with_format_sql(monkeypatch):
    ...  # sql(ctx, "SELECT MEASURE(x.count) FROM x")
    # assert kwargs["json"] == {"query": "SELECT MEASURE(x.count) FROM x", "format": "sql"}
```

Update `test_load_and_sql_send_utc_timezone_by_default`: `sql` now sends `json`,
not `params`, so read `sent[1]["json"]["query"]["timezone"]`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/cube/test_mcp_server.py -k sql -v` Expected: FAIL
(`_trim_sql` not defined).

- [ ] **Step 4: Implement `_trim_sql` and the new `sql`**

Docstring: both input kinds; trimmed shape and the `full` shape; a rollup query
compiles to `FROM prod_pre_aggregations.<rollup>`; "why didn't this use a
pre-aggregation?" goes to `dry_run`; `WHERE (1 = 0)` means one of the three
access causes. Drop the wrong `{"status", "query_type"}` shape.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git -C <worktree> add src/cube/mcp/server.py tests/cube/test_mcp_server.py tests/cube/fixtures/cube_sql_response.json
git -C <worktree> commit -m "feat(cube): trim Cube MCP sql response and accept SQL API input"
```

### Task 3: Add `dry_run`

**Files:**

- Modify: `src/cube/mcp/server.py`
- Test: `tests/cube/test_mcp_server.py`

**Interfaces:**

- Produces:
  `_summarize_transformed_query(tq: dict[str, Any] | None) -> dict[str, Any] | None`.
  Keeps the scalar fields that explain a pre-aggregation match (booleans, member
  lists such as `leafMeasures`, `sortedDimensions`, `timeDimensions`,
  `measures`, `ungrouped`, `hasNoTimeDimensionsWithoutGranularity`,
  `allFiltersWithinSelectedDimensions`, `isAdditive`), and drops
  `granularityHierarchies` and any value over 1 KB once serialized. Read one
  real `transformedQueries` entry (Step 1) to pick the exact keys.
- Produces:
  `dry_run(ctx, query: dict[str, Any], full: bool = False) -> dict[str, Any]`.
  `POST /dry-run` with `{"query": _with_default_timezone(query)}`. Unless
  `full`, replace `transformedQueries` with the summaries.

- [ ] **Step 1: Capture a real `transformedQueries` entry**

Run a throwaway credentialed test (`tests/cube/test_zz_dry_run_probe.py`, per
`tests/CLAUDE.md`) that calls `server.dry_run` on the Task 2 sample query with
`full=True` and prints
`json.dumps(result["transformedQueries"][0], indent=1)[:4000]`. Delete the file
after. If the server cannot reach Cube from pytest, use the key names in
`@cubejs-backend/schema-compiler`'s
`PreAggregations.transformQueryToCanUseForm`.

- [ ] **Step 2: Write the failing tests**

```python
def test_dry_run_posts_query_and_summarizes(monkeypatch):
    big = {"leafMeasures": ["v.m"], "granularityHierarchies": {"x": ["y"] * 5000}}
    body = {"queryType": "regularQuery", "normalizedQueries": [{}],
            "queryOrder": [{}], "pivotQuery": {}, "transformedQueries": [big]}
    ...  # fake _request returns body; records call
    # assert ("POST", "/dry-run"), json == {"query": {..., "timezone": "UTC"}}
    # assert "granularityHierarchies" not in result["transformedQueries"][0]
    # assert result["transformedQueries"][0]["leafMeasures"] == ["v.m"]
    # full=True: result == body


def test_dry_run_summarizes_every_query_in_multi_query(monkeypatch):
    ...  # transformedQueries == [big, big]; both summarized


def test_summarize_transformed_query_handles_none(monkeypatch):
    server = _load_server(monkeypatch)
    assert server._summarize_transformed_query(None) is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/cube/test_mcp_server.py -k dry_run -v` Expected: FAIL
(`dry_run` not defined).

- [ ] **Step 4: Implement**

Docstring: validates and normalizes a query without compiling SQL; the place to
ask why a query did or did not match a pre-aggregation; `full=True` for Cube's
raw objects.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git -C <worktree> add src/cube/mcp/server.py tests/cube/test_mcp_server.py
git -C <worktree> commit -m "feat(cube): add dry_run tool to the Cube MCP server"
```

### Task 4: Add `cubesql`

**Files:**

- Modify: `src/cube/mcp/server.py`
- Test: `tests/cube/test_mcp_server.py`

**Interfaces:**

- Produces: `_parse_cubesql_stream(text: str) -> dict[str, Any]`. Splits on
  newlines, skips blank lines, `json.loads` each. Returns
  `{"schema": ..., "lastRefreshTime": ..., "usedPreAggregations": ..., "data": [<all rows, in order>]}`
  (keys absent from the stream are omitted). Any line with an `error` key:
  return `{"error": <that value>}` and stop.
- Produces:
  `cubesql(ctx, query: str, timezone: str | None = None) -> dict[str, Any]`.
  `POST /cubesql` with
  `{"query": query, "timezone": timezone or DEFAULT_QUERY_TIMEZONE, "throwContinueWait": True}`.
  Loop until the deadline: parse the body with `_parse_cubesql_stream`; if the
  result's `error == "Continue wait"`, sleep 1 s and resend; any other `error`
  raises `RuntimeError(f"Cube POST /cubesql: {error}")`; else return.
- Change: `_request` gains `raw: bool = False`. When `raw`, it returns
  `response.text` instead of `response.json()` and skips the `Continue wait`
  check. `cubesql` does its own polling on the parsed result. Keep the HTTP
  error branch for both.

Read the whole response body (`response.text`). httpx buffers it; no streaming
reader is needed, because the tool returns one object anyway.

- [ ] **Step 1: Write the failing tests**

```python
STREAM = (
    '{"schema":[{"name":"c","column_type":"Int64"}],"lastRefreshTime":"t","usedPreAggregations":{}}\n'
    '{"data":[["1"],["2"]]}\n'
    '{"data":[["3"]]}\n'
)


def test_parse_cubesql_stream_assembles_chunks(monkeypatch):
    server = _load_server(monkeypatch)
    out = server._parse_cubesql_stream(STREAM)
    assert out["data"] == [["1"], ["2"], ["3"]]
    assert out["schema"][0]["name"] == "c"


def test_parse_cubesql_stream_error_line(monkeypatch):
    server = _load_server(monkeypatch)
    out = server._parse_cubesql_stream('{"schema":[]}\n{"error":"boom"}\n')
    assert out == {"error": "boom"}


def test_cubesql_posts_sql_with_utc_and_continue_wait(monkeypatch):
    ...  # fake _request(method, path, *, email, raw, json) records; returns STREAM
    # assert ("POST", "/cubesql"), raw is True
    # assert json == {"query": "SELECT 1", "timezone": "UTC", "throwContinueWait": True}


def test_cubesql_polls_on_continue_wait_then_returns(monkeypatch):
    ...  # first call returns '{"error":"Continue wait"}\n', second STREAM
    # monkeypatch asyncio.sleep to a no-op; assert 2 calls and data has 3 rows


def test_cubesql_raises_at_deadline(monkeypatch):
    ...  # always Continue wait; monkeypatch time.monotonic to jump past
    # the deadline; pytest.raises(RuntimeError, match="did not complete")


def test_cubesql_raises_cube_error(monkeypatch):
    ...  # returns '{"error":"Table not found"}\n';
    # pytest.raises(RuntimeError, match="Table not found")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cube/test_mcp_server.py -k cubesql -v` Expected: FAIL
(`_parse_cubesql_stream` not defined).

- [ ] **Step 3: Implement**

Docstring: SQL API dialect over REST; `MEASURE(<measure>)` for measures; query
views, not cubes; `GROUP BY` the dimensions; no tool-side row limit, so page
with `LIMIT`/`OFFSET`; numeric values come back as strings; same PII paragraph
as `load`; the three access causes for an empty result.

- [ ] **Step 4: Verify catalog queries live**

Throwaway credentialed test (`tests/cube/test_zz_cubesql_probe.py`): call
`server.cubesql` with
`SELECT table_name FROM information_schema.tables LIMIT 5`. Print only the
result keys and row count, not values. Delete the file after.

- If it returns rows: add one docstring line saying catalog queries work.
- If it errors: add one docstring line saying they do not, and to use `meta` for
  schema questions.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git -C <worktree> add src/cube/mcp/server.py tests/cube/test_mcp_server.py
git -C <worktree> commit -m "feat(cube): add cubesql tool to the Cube MCP server"
```

### Task 5: Add `convert_query` and `graphql_to_json`

**Files:**

- Modify: `src/cube/mcp/server.py`
- Test: `tests/cube/test_mcp_server.py`

**Interfaces:**

- Produces: `convert_query(ctx, sql: str) -> dict[str, Any]`.
  `POST /convert-query` with `{"input": "sql", "output": "rest", "query": sql}`;
  returns Cube's body.
- Produces:
  `graphql_to_json(ctx, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]`.
  `POST /graphql-to-json` with `{"query": query, "variables": variables or {}}`.
  Returns `body["jsonQuery"]`. If it is `None`, raise
  `RuntimeError("Cube could not parse the GraphQL query")`.

- [ ] **Step 1: Write the failing tests**

```python
def test_convert_query_posts_sql_to_rest(monkeypatch):
    ...  # assert ("POST", "/convert-query"),
    # json == {"input": "sql", "output": "rest", "query": "SELECT 1"}


def test_graphql_to_json_returns_json_query(monkeypatch):
    ...  # fake returns {"jsonQuery": {"measures": ["v.m"]}}
    # assert result == {"measures": ["v.m"]}
    # assert json == {"query": "{ cube { v { m } } }", "variables": {}}


def test_graphql_to_json_raises_on_null(monkeypatch):
    ...  # fake returns {"jsonQuery": None}
    # pytest.raises(RuntimeError, match="could not parse")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
`uv run pytest tests/cube/test_mcp_server.py -k "convert_query or graphql" -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Docstrings: each says the result is a REST query object to pass to `load`,
`sql`, or `dry_run`.

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git -C <worktree> add src/cube/mcp/server.py tests/cube/test_mcp_server.py
git -C <worktree> commit -m "feat(cube): add convert_query and graphql_to_json tools to the Cube MCP server"
```

### Task 6: Update docs, auth test, and the `instructions=` string

**Files:**

- Modify: `src/cube/mcp/CLAUDE.md` (Files list, Cube REST quirks)
- Modify: `src/cube/mcp/server.py` (`instructions=` names the new tools in one
  sentence; `test_module_loads` asserts all seven exist)
- Test: `tests/cube/test_mcp_server.py`

- [ ] **Step 1: Write the failing test**

```python
def test_every_tool_sends_minted_token(monkeypatch):
    # Patch server.client with an httpx.AsyncClient(transport=httpx.MockTransport(handler)).
    # handler records request.headers["Authorization"] and returns a minimal valid
    # body per path (/sql -> fixture, /dry-run -> body, /cubesql -> STREAM text,
    # /convert-query -> {}, /graphql-to-json -> {"jsonQuery": {}}, /load -> {"data": []}).
    # Call each tool once; assert every recorded header == server._mint_token(email)
    # and has no "Bearer " prefix.
```

This is the one transport-level test; the per-tool tests above fake `_request`.
Extend `test_module_loads` to assert `dry_run`, `cubesql`, `convert_query`,
`graphql_to_json`.

- [ ] **Step 2: Run, implement, rerun**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected after edits: all
PASS.

`src/cube/mcp/CLAUDE.md`: Files list names all seven tools; replace the "`/sql`
is GET-only" bullet with: `/sql` and `/dry-run` accept POST with a JSON body;
`/cubesql` returns newline-delimited JSON, not one object; `/graphql-to-json`
returns `{"jsonQuery": null}` with HTTP 200 on a parse error. Read the file with
the Read tool first.

- [ ] **Step 3: Lint and commit**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/cube/mcp/server.py src/cube/mcp/CLAUDE.md tests/cube/test_mcp_server.py .claude/skills/cube-ops/SKILL.md </dev/null
git -C <worktree> add src/cube/mcp/server.py src/cube/mcp/CLAUDE.md tests/cube/test_mcp_server.py
git -C <worktree> commit -m "docs(cube): document new Cube MCP tools and REST quirks"
```

PR body notes: claude.ai users must refresh the connector after deploy; the
`sql` SQL-input deviation from the spec; the observed row limits; the
catalog-query result from Task 4.
