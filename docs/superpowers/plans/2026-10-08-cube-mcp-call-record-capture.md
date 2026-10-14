# Cube MCP call record, PR 1 (capture) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every `meta`, `load` and `sql` call on the Cube MCP server writes 1
JSON line to stderr that Cloud Run ships to Cloud Logging, ready for a sink to
route into BigQuery.

**Architecture:** An async context manager, `_recorded()`, wraps each tool body.
It mints a `cube_request_id`, resolves a `session_id`, and publishes the record
through a `ContextVar` so `_request()` can send `x-request-id` and add its
latency. On exit it builds 1 row from an explicit allowlist,
`CALL_RECORD_FIELDS`, and prints it to stderr. Any failure while writing is
swallowed.

**Tech Stack:** Python 3.13, `mcp` SDK 2.x (`MCPServer`), `httpx`, pytest. No
new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-01-cube-mcp-call-record-design.md`.
Its _Revision 2026-10-08_ section wins wherever it disagrees with a later
section.

**Worktree:**
`/workspaces/teamster/.claude/worktrees/cristinabaldor/feat/claude-cube-mcp-call-record`,
branch `cristinabaldor/feat/claude-cube-mcp-call-record`. Run every command from
that directory. `W` below means that path.

## Global Constraints

- Everything server-side stays in `src/cube/mcp/server.py`: the Dockerfile
  copies only that file, and the tests load it by path.
- New tool parameters are all optional, default `None`: `load` gets `question`,
  `session_id`, `assumptions`; `sql` gets `question`, `session_id`; `meta` gets
  `session_id`.
- The free-text switch is `CUBE_MCP_LOG_FREE_TEXT`. Only the exact value `true`
  (case-insensitive, trimmed) turns it on. It covers `question` and
  `assumptions` only. `query_json` and `error_message` always log.
- `question_provided` (bool) always logs: true when `question` is non-empty
  after trimming.
- Each log line is `{"event": "cube_mcp_call", "severity": "INFO", **row}`. The
  row's keys equal `CALL_RECORD_FIELDS` exactly, in that order.
- Never log response rows. `row_count` is `len(data)`; the rows themselves never
  reach the record.
- Each text field is cut at 10,000 characters.
- Keep each field's JSON type fixed, because the sink drops an entry whose type
  disagrees with the column. Absent means `null`. Never emit `""` for a missing
  string, and never emit an empty list: an empty array becomes `null`.
- A `session_id` that is not a valid UUID is replaced with a minted one and
  never logged.
- The tool's own result or exception passes through unchanged, except for the
  added top-level `session_id` key on success.
- The cached `meta` payload is never modified. `session_id` goes on a copy.
- Deploy sets `SERVER_SHA=${{ github.sha }}` and `CUBE_MCP_LOG_FREE_TEXT=false`.
  `SERVER_SHA` defaults to `local`.
- Tests: `uv run pytest tests/cube/test_mcp_server.py -v`. Never bare
  `uv run pytest`.

## Review Focus

1. **A huge query or Cube error text.** A filter listing thousands of student
   numbers must still produce 1 line under Cloud Logging's 256 KB entry limit.
   The 10,000-character cut on each text field does this. Test:
   `test_row_clips_long_text` (Task 2).
2. **A model passes junk as `session_id`** (free text, a name, a malformed
   UUID). The value must never appear in the log line. Test:
   `test_invalid_session_id_is_never_logged` (Task 4).
3. **The record fails to serialize or write.** The tool still returns its result
   unchanged. Test: `test_emit_failure_does_not_break_the_call` (Task 2) and
   `test_tool_returns_result_when_emit_raises` (Task 4).
4. **A call fails before the email resolves**, such as a missing OAuth claim.
   The record still writes with `email: null` and `outcome: error`, and the same
   exception object reaches the caller. Test:
   `test_error_before_email_is_recorded_and_reraised` (Task 4).
5. **`usedPreAggregations` in a shape the spec did not show**: missing, `{}`,
   entries without `preAggregationId`, or a multi-query `results` response. The
   summary must not raise and must give sensible values. Tests:
   `test_load_summary_*` (Task 1). The real shape is still unverified, because
   no pre-aggregation currently serves a query (#5557). Task 6 checks it on the
   first production rows.

---

### Task 1: Pure helpers for the call record

**Files:**

- Modify: `src/cube/mcp/server.py` (imports at the top; new block after
  `_with_default_timezone`, around line 291)
- Test: `tests/cube/test_mcp_server.py` (append)

**Interfaces:**

- Produces:
  - `CALL_RECORD_TEXT_LIMIT: int = 10_000`
  - `_clip(text: str | None) -> str | None`
  - `_resolve_session_id(raw: str | None) -> tuple[str, bool]`:
    `(session_id, minted)`
  - `_members_referenced(query: dict[str, Any]) -> list[str]`: sorted, unique
  - `_views_referenced(members: list[str]) -> list[str]`: sorted, unique
  - `_load_summary(payload: dict[str, Any]) -> dict[str, Any]` with keys
    `external` (`bool | None`), `used_pre_aggregations` (`list[str]`),
    `last_refresh_time` (`str | None`), `row_count` (`int`)

- [ ] **Step 1: Write the failing tests**

Append to `tests/cube/test_mcp_server.py`:

```python
def test_clip_cuts_long_text_and_passes_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    assert server._clip(None) is None
    assert server._clip("short") == "short"
    assert len(server._clip("x" * 20_000)) == server.CALL_RECORD_TEXT_LIMIT


def test_resolve_session_id_mints_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import uuid

    server = _load_server(monkeypatch)
    for raw in (None, "", "   "):
        session_id, minted = server._resolve_session_id(raw)
        assert minted is True
        assert str(uuid.UUID(session_id)) == session_id


def test_resolve_session_id_reuses_and_normalizes_a_valid_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    canonical = "1b4e28ba-2fa1-11d2-883f-0016d3cca427"
    for raw in (canonical, canonical.upper(), "{" + canonical + "}", f" {canonical} "):
        assert server._resolve_session_id(raw) == (canonical, False)


def test_resolve_session_id_replaces_a_non_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    session_id, minted = server._resolve_session_id("Student A's session")
    assert minted is True
    assert "Student" not in session_id


def test_members_referenced_walks_every_query_part(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["v.count_students"],
        "dimensions": ["v.school_name"],
        "segments": ["v.active"],
        "timeDimensions": [{"dimension": "v.dates_date_day", "granularity": "month"}],
        "filters": [
            {"member": "v.region", "operator": "equals", "values": ["Newark"]},
            {
                "or": [
                    {"member": "v.grade", "operator": "equals", "values": ["9"]},
                    {"and": [{"dimension": "v.is_iep", "operator": "set"}]},
                ]
            },
        ],
        "order": {"v.count_students": "desc"},
    }
    assert server._members_referenced(query) == [
        "v.active",
        "v.count_students",
        "v.dates_date_day",
        "v.grade",
        "v.is_iep",
        "v.region",
        "v.school_name",
    ]
    # Filter VALUES never appear: only member names.
    assert "Newark" not in server._members_referenced(query)


def test_members_referenced_accepts_list_form_order_and_skips_junk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    query = {
        "measures": ["a.x", 7],
        "order": [["b.y", "asc"], "not-a-pair", []],
        "filters": ["not-a-dict"],
        "timeDimensions": [{"granularity": "day"}],
    }
    assert server._members_referenced(query) == ["a.x", "b.y"]
    assert server._members_referenced({}) == []


def test_views_referenced_takes_the_text_before_the_first_dot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    assert server._views_referenced(["b.y", "a.x", "a.z", "bare"]) == ["a", "b", "bare"]


def test_load_summary_reads_the_load_response_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    payload = {
        "data": [{"v.count": "1"}, {"v.count": "2"}],
        "external": True,
        "usedPreAggregations": {
            "prod_pre_aggregations.v_rollup_abc123": {
                "preAggregationId": "v.rollup",
                "targetTableName": "prod_pre_aggregations.v_rollup_abc123",
            }
        },
        "lastRefreshTime": "2026-10-08T03:00:00.000Z",
    }
    assert server._load_summary(payload) == {
        "external": True,
        "used_pre_aggregations": ["v.rollup"],
        "last_refresh_time": "2026-10-08T03:00:00.000Z",
        "row_count": 2,
    }


def test_load_summary_tolerates_missing_and_odd_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    assert server._load_summary({"data": []}) == {
        "external": None,
        "used_pre_aggregations": [],
        "last_refresh_time": None,
        "row_count": 0,
    }
    # An entry without preAggregationId falls back to its key.
    odd = {"data": [], "usedPreAggregations": {"some_table": "not-a-dict"}}
    assert server._load_summary(odd)["used_pre_aggregations"] == ["some_table"]
    assert server._load_summary({"usedPreAggregations": []})["used_pre_aggregations"] == []


def test_load_summary_combines_a_multi_query_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    payload = {
        "results": [
            {"data": [{"a": 1}], "external": True, "lastRefreshTime": "2026-10-08T03:00:00Z"},
            {"data": [{"a": 2}, {"a": 3}], "external": False, "lastRefreshTime": "2026-10-07T03:00:00Z"},
            "not-a-dict",
        ]
    }
    summary = server._load_summary(payload)
    assert summary["row_count"] == 3
    # Served by a pre-aggregation only if every part was.
    assert summary["external"] is False
    # The stalest refresh time: how old the oldest part of the answer is.
    assert summary["last_refresh_time"] == "2026-10-07T03:00:00Z"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run pytest tests/cube/test_mcp_server.py -v -k "clip or resolve_session or members_referenced or views_referenced or load_summary"`
Expected: FAIL with
`AttributeError: module 'cube_mcp_server' has no attribute '_clip'` (and
similar).

- [ ] **Step 3: Implement the helpers**

In `src/cube/mcp/server.py`, add to the imports (keep them alphabetical):

```python
import contextlib
import uuid
from collections.abc import AsyncIterator, Iterator
```

(`AsyncIterator` is already imported from `collections.abc`; extend that line.)

After `_with_default_timezone`, add:

```python
# Call record: 1 JSON line per tool call, written to stderr for Cloud Logging.
# Design and the sink that routes it to BigQuery: Refs #5613.
CALL_RECORD_TEXT_LIMIT = 10_000


def _clip(text: str | None) -> str | None:
    """Cut a text field so 1 record stays far under Cloud Logging's 256 KB
    entry limit."""
    if text is None:
        return None
    return text[:CALL_RECORD_TEXT_LIMIT]


def _resolve_session_id(raw: str | None) -> tuple[str, bool]:
    """Return `(session_id, minted)`. A value that is not a UUID is replaced
    and never echoed, so free text a model passes here never reaches the log."""
    with contextlib.suppress(ValueError):
        return str(uuid.UUID((raw or "").strip())), False
    return str(uuid.uuid4()), True


def _filter_members(filters: Any) -> Iterator[str]:
    """Yield the member of every filter, walking nested `and`/`or` groups.
    Filter values are never read."""
    if not isinstance(filters, list):
        return
    for item in filters:
        if not isinstance(item, dict):
            continue
        for group in ("and", "or"):
            yield from _filter_members(item.get(group))
        member = item.get("member") or item.get("dimension")
        if isinstance(member, str):
            yield member


def _members_referenced(query: dict[str, Any]) -> list[str]:
    """Every member a Cube query names, sorted and unique. Names only."""
    members: set[str] = set()
    for key in ("measures", "dimensions", "segments"):
        members.update(m for m in query.get(key) or [] if isinstance(m, str))
    for time_dimension in query.get("timeDimensions") or []:
        if isinstance(time_dimension, dict) and isinstance(
            time_dimension.get("dimension"), str
        ):
            members.add(time_dimension["dimension"])
    members.update(_filter_members(query.get("filters")))
    order = query.get("order")
    if isinstance(order, dict):
        members.update(k for k in order if isinstance(k, str))
    elif isinstance(order, list):
        members.update(
            pair[0]
            for pair in order
            if isinstance(pair, (list, tuple)) and pair and isinstance(pair[0], str)
        )
    return sorted(members)


def _views_referenced(members: list[str]) -> list[str]:
    return sorted({m.split(".", 1)[0] for m in members})


def _load_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the pre-aggregation and size fields out of a `/v1/load` response.
    A multi-query response (`results`) is summarized across its parts: served
    by a pre-aggregation only if every part was, refreshed as of its stalest
    part. Rows are counted, never copied."""
    results = payload.get("results")
    parts = (
        [r for r in results if isinstance(r, dict)]
        if isinstance(results, list)
        else [payload]
    )
    externals = [p["external"] for p in parts if isinstance(p.get("external"), bool)]
    used: set[str] = set()
    for part in parts:
        entries = part.get("usedPreAggregations")
        if not isinstance(entries, dict):
            continue
        for table_name, info in entries.items():
            # The id is stable; the table name carries a hash that changes on
            # every rebuild.
            pre_aggregation_id = (
                info.get("preAggregationId") if isinstance(info, dict) else None
            )
            used.add(
                pre_aggregation_id
                if isinstance(pre_aggregation_id, str)
                else table_name
            )
    refresh_times = [
        p["lastRefreshTime"] for p in parts if isinstance(p.get("lastRefreshTime"), str)
    ]
    return {
        "external": all(externals) if externals else None,
        "used_pre_aggregations": sorted(used),
        "last_refresh_time": min(refresh_times) if refresh_times else None,
        "row_count": sum(
            len(p["data"]) for p in parts if isinstance(p.get("data"), list)
        ),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS,
including every pre-existing test.

- [ ] **Step 5: Commit**

```bash
git -C W add -u && git -C W add tests/cube/test_mcp_server.py
git -C W commit -m "feat(cube): add helpers that summarize a Cube MCP call without its rows"
```

End the message with the `Co-Authored-By` trailer from the session's attribution
reminder.

---

### Task 2: The record, its allowlist, and the stderr writer

**Files:**

- Modify: `src/cube/mcp/server.py` (imports; module settings near line 61; new
  block after Task 1's helpers)
- Test: `tests/cube/test_mcp_server.py` (append)

**Interfaces:**

- Consumes: everything Task 1 produces.
- Produces:
  - `SERVER_SHA: str`, `LOG_FREE_TEXT: bool`,
    `CALL_RECORD_EVENT = "cube_mcp_call"`
  - `CALL_RECORD_FIELDS: tuple[str, ...]` (the 21 names below, in order)
  - `class _CallRecord` (dataclass) with fields `tool`, `session_id`,
    `session_id_minted`, `question`, `assumptions`, `query`, `views`,
    `cube_request_id`, `ts`, `email`, `client`, `result`, `error`,
    `latency_ms: float`, and method `row() -> dict[str, Any]`
  - `_emit_call_record(record: _CallRecord) -> None`
  - `_current_call: ContextVar[_CallRecord | None]`
  - `_recorded(ctx, tool, *, session_id, question=None, assumptions=None, query=None, views=None)`:
    an async context manager yielding the `_CallRecord`
  - Test helpers `_call_records(capsys)` and
    `_stdio_server(monkeypatch, tmp_path, **env)`

- [ ] **Step 1: Write the failing tests**

Append to `tests/cube/test_mcp_server.py`:

```python
CALL_RECORD_ENVELOPE = {"event", "severity"}


def _call_records(capsys: pytest.CaptureFixture[str]) -> list[dict[str, Any]]:
    """Parse every call-record line the server wrote to stderr."""
    records = []
    for line in capsys.readouterr().err.splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and parsed.get("event") == "cube_mcp_call":
            records.append(parsed)
    return records


def _stdio_server(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **env: str
) -> ModuleType:
    """Load the server in stdio mode with an isolated meta cache and the
    call-record settings unset unless passed in `env`."""
    monkeypatch.setenv("CUBE_USER_EMAIL", "engineer@apps.teamschools.org")
    for name in ("AUTHKIT_DOMAIN", "PUBLIC_URL", "CUBE_MCP_LOG_FREE_TEXT", "SERVER_SHA"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    server = _load_server(monkeypatch)
    server._meta_memory_cache.clear()
    monkeypatch.setattr(server, "META_CACHE_DIR", tmp_path)
    return server


def _sample_record(server: ModuleType, **overrides: Any) -> Any:
    fields = {
        "tool": "load",
        "session_id": "1b4e28ba-2fa1-11d2-883f-0016d3cca427",
        "session_id_minted": False,
        "question": "How many students are enrolled?",
        "assumptions": "Current academic year",
        "query": {"measures": ["v.count_students"], "timezone": "UTC"},
        "email": "engineer@apps.teamschools.org",
        "result": {"data": [{"v.count_students": "5"}]},
    }
    fields.update(overrides)
    return server._CallRecord(**fields)


def test_row_keys_equal_the_allowlist_on_every_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    variants = [
        {},
        {"result": {"data": []}},
        {"result": None, "error": "boom"},
        {"tool": "meta", "query": None, "views": ["v"], "result": None},
        {"tool": "sql", "result": {"sql": {"sql": ["select 1", []]}}},
    ]
    for overrides in variants:
        row = _sample_record(server, **overrides).row()
        assert tuple(row) == server.CALL_RECORD_FIELDS


def test_row_outcome_and_load_fields(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    ok = _sample_record(server).row()
    assert ok["outcome"] == "ok"
    assert ok["row_count"] == 1
    assert ok["members_referenced"] == ["v.count_students"]
    assert ok["views_referenced"] == ["v"]
    assert json.loads(ok["query_json"]) == {"measures": ["v.count_students"], "timezone": "UTC"}

    assert _sample_record(server, result={"data": []}).row()["outcome"] == "empty"

    error = _sample_record(server, result=None, error="Cube POST /load 400: bad").row()
    assert error["outcome"] == "error"
    assert error["error_message"] == "Cube POST /load 400: bad"


def test_row_leaves_load_fields_null_on_meta_and_sql(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    meta_row = _sample_record(
        server, tool="meta", query=None, views=["b", "a"], result={"cubes": []}
    ).row()
    assert meta_row["views_referenced"] == ["a", "b"]
    assert meta_row["members_referenced"] is None
    assert meta_row["query_json"] is None
    for key in ("external", "used_pre_aggregations", "last_refresh_time", "row_count"):
        assert meta_row[key] is None
    assert _sample_record(server, tool="sql").row()["row_count"] is None


def test_row_never_emits_an_empty_list(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    row = _sample_record(server, tool="meta", query=None, views=None).row()
    assert row["views_referenced"] is None
    assert row["used_pre_aggregations"] is None
    assert not any(value == [] for value in row.values())


def test_row_drops_free_text_when_the_switch_is_off(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for env in ({}, {"CUBE_MCP_LOG_FREE_TEXT": "false"}, {"CUBE_MCP_LOG_FREE_TEXT": "yes"}):
        server = _stdio_server(monkeypatch, tmp_path, **env)
        row = _sample_record(server, error="echoed filter value").row()
        assert row["question"] is None
        assert row["assumptions"] is None
        assert row["question_provided"] is True
        # Always logged, whatever the switch says.
        assert row["query_json"] is not None
        assert row["error_message"] == "echoed filter value"


def test_row_keeps_free_text_when_the_switch_is_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path, CUBE_MCP_LOG_FREE_TEXT=" TRUE ")
    row = _sample_record(server).row()
    assert row["question"] == "How many students are enrolled?"
    assert row["assumptions"] == "Current academic year"


def test_row_question_provided_ignores_blank_text(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    for question in (None, "", "   "):
        assert _sample_record(server, question=question).row()["question_provided"] is False


def test_row_clips_long_text(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    server = _stdio_server(monkeypatch, tmp_path, CUBE_MCP_LOG_FREE_TEXT="true")
    huge = {"filters": [{"member": "v.student_number", "operator": "equals", "values": ["1" * 50_000]}]}
    row = _sample_record(
        server, query=huge, question="q" * 50_000, error="e" * 50_000
    ).row()
    for key in ("query_json", "question", "error_message"):
        assert len(row[key]) == server.CALL_RECORD_TEXT_LIMIT
    assert len(json.dumps(row)) < 256_000


def test_server_sha_defaults_to_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    assert _sample_record(server).row()["server_sha"] == "local"
    server = _stdio_server(monkeypatch, tmp_path, SERVER_SHA="abc123")
    assert _sample_record(server).row()["server_sha"] == "abc123"


def test_emit_writes_one_json_line_with_the_envelope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    server._emit_call_record(_sample_record(server))
    records = _call_records(capsys)
    assert len(records) == 1
    assert records[0]["severity"] == "INFO"
    assert set(records[0]) - CALL_RECORD_ENVELOPE == set(server.CALL_RECORD_FIELDS)


def test_emit_failure_does_not_break_the_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    record = _sample_record(server)

    def broken_row() -> dict[str, Any]:
        raise RuntimeError("serializer exploded")

    monkeypatch.setattr(record, "row", broken_row)
    server._emit_call_record(record)  # must not raise


def test_recorded_marks_errors_and_reraises_the_same_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    boom = ValueError("bad query")

    async def run() -> None:
        async with server._recorded(MagicMock(), "load", session_id=None, query={}):
            raise boom

    with pytest.raises(ValueError) as caught:
        asyncio.run(run())
    assert caught.value is boom
    [record] = _call_records(capsys)
    assert record["outcome"] == "error"
    assert record["error_message"] == "bad query"
    assert record["session_id_minted"] is True
    assert server._current_call.get() is None


def test_recorded_reads_the_client_user_agent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    ctx = MagicMock()
    ctx.headers = {"user-agent": "claude-ai/1.0"}

    async def run() -> None:
        async with server._recorded(ctx, "meta", session_id=None):
            pass

    asyncio.run(run())
    assert _call_records(capsys)[0]["client"] == "claude-ai/1.0"
    # A MagicMock ctx (no real headers) or stdio's None gives null, not junk.
    assert server._client_user_agent(MagicMock()) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run pytest tests/cube/test_mcp_server.py -v -k "row_ or emit or recorded or server_sha"`
Expected: FAIL with
`AttributeError: module 'cube_mcp_server' has no attribute '_CallRecord'` (and
similar).

- [ ] **Step 3: Implement the record**

Add to the imports:

```python
import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime
```

After `DEFAULT_QUERY_TIMEZONE`, add:

```python
# Deploy sets SERVER_SHA to the commit; stdio dev runs log "local".
SERVER_SHA = os.environ.get("SERVER_SHA", "").strip() or "local"
# Off unless the deploy sets "true". `question` and `assumptions` are free text
# staff type about students, and capturing them waits on People Operations
# sign-off (Refs #5613). `query_json` and `error_message` always log: they
# repeat values the warehouse already holds.
LOG_FREE_TEXT = os.environ.get("CUBE_MCP_LOG_FREE_TEXT", "").strip().lower() == "true"
```

After Task 1's `_load_summary`, add:

```python
CALL_RECORD_EVENT = "cube_mcp_call"
# The only keys a record may carry, in order. A test pins the logged keys to
# this tuple, so widening the payload is a deliberate edit here, matched in the
# dbt staging model's contract.
CALL_RECORD_FIELDS: tuple[str, ...] = (
    "cube_request_id",
    "ts",
    "tool",
    "session_id",
    "session_id_minted",
    "email",
    "client",
    "question",
    "question_provided",
    "assumptions",
    "query_json",
    "views_referenced",
    "members_referenced",
    "outcome",
    "error_message",
    "external",
    "used_pre_aggregations",
    "last_refresh_time",
    "row_count",
    "latency_ms",
    "server_sha",
)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _client_user_agent(ctx: Context) -> str | None:
    """The calling client's User-Agent, or None on stdio or outside a request."""
    with contextlib.suppress(Exception):
        headers = ctx.headers
        value = headers.get("user-agent") if headers is not None else None
        if isinstance(value, str):
            return value
    return None


@dataclass
class _CallRecord:
    """What 1 tool call did. Never holds response rows: `result` is read for
    counts and pre-aggregation fields only, in `row()`."""

    tool: str
    session_id: str
    session_id_minted: bool
    question: str | None = None
    assumptions: str | None = None
    query: dict[str, Any] | None = None
    views: list[str] | None = None
    cube_request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: str = field(default_factory=_utc_now)
    email: str | None = None
    client: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    latency_ms: float = 0.0

    def row(self) -> dict[str, Any]:
        """The logged row. Empty arrays become null, because the BigQuery sink
        cannot type a column from an empty array."""
        members = _members_referenced(self.query) if self.query is not None else []
        views = _views_referenced(members) if self.query is not None else sorted(self.views or [])
        summary: dict[str, Any] = (
            _load_summary(self.result)
            if self.tool == "load" and self.result is not None
            else {}
        )
        if self.error is not None:
            outcome = "error"
        elif summary.get("row_count") == 0:
            outcome = "empty"
        else:
            outcome = "ok"
        row = {
            "cube_request_id": self.cube_request_id,
            "ts": self.ts,
            "tool": self.tool,
            "session_id": self.session_id,
            "session_id_minted": self.session_id_minted,
            "email": self.email,
            "client": _clip(self.client),
            "question": _clip(self.question) if LOG_FREE_TEXT else None,
            "question_provided": bool(self.question and self.question.strip()),
            "assumptions": _clip(self.assumptions) if LOG_FREE_TEXT else None,
            "query_json": (
                _clip(json.dumps(self.query, sort_keys=True, default=str))
                if self.query is not None
                else None
            ),
            "views_referenced": views or None,
            "members_referenced": members or None,
            "outcome": outcome,
            "error_message": _clip(self.error),
            "external": summary.get("external"),
            "used_pre_aggregations": summary.get("used_pre_aggregations") or None,
            "last_refresh_time": summary.get("last_refresh_time"),
            "row_count": summary.get("row_count"),
            "latency_ms": round(self.latency_ms),
            "server_sha": SERVER_SHA,
        }
        return {key: row[key] for key in CALL_RECORD_FIELDS}


def _emit_call_record(record: _CallRecord) -> None:
    """Write 1 record to stderr as a JSON line. Cloud Run ships it to Cloud
    Logging as `jsonPayload`; stdout is the MCP transport in stdio mode. Cloud
    Run moves `severity` onto the log entry itself. A failure here never
    reaches the tool's caller."""
    with contextlib.suppress(Exception):
        line = {"event": CALL_RECORD_EVENT, "severity": "INFO", **record.row()}
        print(json.dumps(line, default=str), file=sys.stderr, flush=True)


# The record of the tool call in progress, so `_request` can tag Cube requests
# with its id and add its latency without threading it through every helper.
_current_call: ContextVar[_CallRecord | None] = ContextVar("_current_call", default=None)


@asynccontextmanager
async def _recorded(
    ctx: Context,
    tool: str,
    *,
    session_id: str | None,
    question: str | None = None,
    assumptions: str | None = None,
    query: dict[str, Any] | None = None,
    views: list[str] | None = None,
) -> AsyncIterator[_CallRecord]:
    """Record 1 tool call: yield its `_CallRecord`, then write it on the way
    out, success or failure. An exception is noted and re-raised unchanged."""
    resolved_session_id, minted = _resolve_session_id(session_id)
    record = _CallRecord(
        tool=tool,
        session_id=resolved_session_id,
        session_id_minted=minted,
        question=question,
        assumptions=assumptions,
        query=query,
        views=views,
        client=_client_user_agent(ctx),
    )
    token = _current_call.set(record)
    try:
        yield record
    except BaseException as exc:
        record.error = str(exc) or type(exc).__name__
        raise
    finally:
        _current_call.reset(token)
        _emit_call_record(record)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git -C W add -u
git -C W commit -m "feat(cube): write an allowlisted call record to stderr for each MCP call"
```

---

### Task 3: Tag Cube requests and time them

**Files:**

- Modify: `src/cube/mcp/server.py` (`_request`, around line 254)
- Test: `tests/cube/test_mcp_server.py` (append)

**Interfaces:**

- Consumes: `_current_call`, `_CallRecord.cube_request_id`,
  `_CallRecord.latency_ms` (Task 2).
- Produces: `_request` sends `x-request-id: <cube_request_id>` on every HTTP
  request while a call is recorded, "Continue wait" polls included, and adds its
  wall-clock milliseconds to `latency_ms`. Its signature is unchanged.

- [ ] **Step 1: Write the failing tests**

```python
class _FakeResponse:
    def __init__(self, body: dict[str, Any]) -> None:
        self.status_code = 200
        self.text = json.dumps(body)
        self._body = body

    def json(self) -> dict[str, Any]:
        return self._body


class _FakeClient:
    """Stands in for the httpx client: returns `bodies` in order and keeps the
    headers of every request."""

    def __init__(self, bodies: list[dict[str, Any]]) -> None:
        self.bodies = list(bodies)
        self.sent_headers: list[dict[str, str]] = []

    async def request(self, method: str, path: str, *, headers: dict[str, str], **kwargs: Any) -> _FakeResponse:
        del method, path, kwargs
        self.sent_headers.append(dict(headers))
        return _FakeResponse(self.bodies.pop(0))


def test_request_sends_the_call_id_on_every_poll(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    fake = _FakeClient([{"error": "Continue wait"}, {"error": "Continue wait"}, {"data": []}])
    monkeypatch.setattr(server, "client", fake)

    async def no_sleep(_seconds: float) -> None:
        return None

    # Replace the server module's `asyncio` name only, never the real
    # `asyncio.sleep` the test's own event loop uses.
    from types import SimpleNamespace

    monkeypatch.setattr(server, "asyncio", SimpleNamespace(sleep=no_sleep))

    async def run() -> None:
        async with server._recorded(MagicMock(), "load", session_id=None, query={}) as record:
            record.result = await server._request(
                "POST", "/load", email="engineer@apps.teamschools.org", poll=True, json={}
            )

    asyncio.run(run())
    [logged] = _call_records(capsys)
    ids = {h["x-request-id"] for h in fake.sent_headers}
    assert len(fake.sent_headers) == 3
    assert ids == {logged["cube_request_id"]}
    assert isinstance(logged["latency_ms"], int)


def test_request_without_a_recorded_call_sends_no_request_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    fake = _FakeClient([{"data": []}])
    monkeypatch.setattr(server, "client", fake)
    asyncio.run(server._request("GET", "/meta", email="engineer@apps.teamschools.org"))
    assert "x-request-id" not in fake.sent_headers[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
`uv run pytest tests/cube/test_mcp_server.py -v -k "request_sends or request_without"`
Expected: `test_request_sends_the_call_id_on_every_poll` FAILS with
`KeyError: 'x-request-id'`.

- [ ] **Step 3: Implement**

Replace the body of `_request` from `headers = ...` to the end with:

```python
    call = _current_call.get()
    headers = {"Authorization": _mint_token(email)}
    if call is not None:
        # Cube stamps this onto the BigQuery job as the `cube_request_id`
        # label, which joins a call record to its job's cost and SQL.
        headers["x-request-id"] = call.cube_request_id
    deadline = time.monotonic() + TIMEOUT_SECONDS
    started = time.monotonic()
    try:
        while True:
            response = await client.request(method, path, headers=headers, **kwargs)
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Cube {method} {path} {response.status_code}: {response.text}"
                )
            body = response.json()
            if poll and isinstance(body, dict) and body.get("error") == "Continue wait":
                if time.monotonic() + 1 >= deadline:
                    raise RuntimeError(
                        f"Cube {method} {path} did not complete within "
                        f"{TIMEOUT_SECONDS}s ('Continue wait' polling)"
                    )
                await asyncio.sleep(1)
                continue
            return body
    finally:
        if call is not None:
            call.latency_ms += (time.monotonic() - started) * 1000
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git -C W add -u
git -C W commit -m "feat(cube): tag Cube requests with the call id and time them"
```

---

### Task 4: Wire the record into `meta`, `load` and `sql`

**Files:**

- Modify: `src/cube/mcp/server.py` (`meta`, `load`, `sql`; new helper
  `_meta_payload`)
- Modify: `tests/cube/test_mcp_server.py`: 2 existing asserts (Step 1) and new
  tests (append)

**Interfaces:**

- Consumes: `_recorded`, `_call_records`, `_stdio_server` (Task 2).
- Produces:
  - `meta(ctx, views=None, force_refresh=False, session_id=None)`
  - `load(ctx, query, question=None, session_id=None, assumptions=None)`
  - `sql(ctx, query, question=None, session_id=None)`
  - Every successful response gains a top-level `session_id: str`.
  - `_meta_payload(email: str, views: list[str] | None, force_refresh: bool) -> dict[str, Any]`:
    the old `meta` body, unchanged in behavior.

- [ ] **Step 1: Update the 2 existing tests the new `session_id` key breaks**

In `test_meta_cache_corruption_deletes_cache_file_and_refetches`, replace

```python
    assert result == {"cubes": []}
```

with

```python
    assert result["cubes"] == []
```

In `test_meta_in_memory_cache_skips_disk_read_on_repeat_calls`, replace

```python
    assert first == second == {"cubes": [{"name": "x"}]}
```

with

```python
    assert first["cubes"] == second["cubes"] == [{"name": "x"}]
```

and replace

```python
    assert third == {"cubes": [{"name": "x"}]}
```

with

```python
    assert third["cubes"] == [{"name": "x"}]
```

- [ ] **Step 2: Write the failing tests**

```python
def _fake_cube(server: ModuleType, monkeypatch: pytest.MonkeyPatch, body: dict[str, Any]) -> None:
    async def fake_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        return body

    monkeypatch.setattr(server, "_request", fake_request)


def test_each_tool_logs_one_allowlisted_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": [{"v.count": "1"}], "cubes": [], "sql": {}})
    ctx = MagicMock()
    asyncio.run(server.meta(ctx))
    asyncio.run(server.load(ctx, {"measures": ["v.count"]}))
    asyncio.run(server.sql(ctx, {"measures": ["v.count"]}))
    records = _call_records(capsys)
    assert [r["tool"] for r in records] == ["meta", "load", "sql"]
    for record in records:
        assert set(record) - CALL_RECORD_ENVELOPE == set(server.CALL_RECORD_FIELDS)
        assert record["outcome"] == "ok"
        assert record["email"] == "engineer@apps.teamschools.org"


def test_load_logs_empty_and_the_query_sent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": []})
    asyncio.run(server.load(MagicMock(), {"measures": ["v.count"]}))
    [record] = _call_records(capsys)
    assert record["outcome"] == "empty"
    assert record["row_count"] == 0
    # The logged query is the one sent, UTC default included.
    assert json.loads(record["query_json"])["timezone"] == "UTC"


def test_load_never_logs_response_rows(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path, CUBE_MCP_LOG_FREE_TEXT="true")
    marker = "ROW-MARKER-7f3c"
    _fake_cube(server, monkeypatch, {"data": [{"v.full_name": marker}, {"v.full_name": marker}]})
    asyncio.run(server.load(MagicMock(), {"dimensions": ["v.full_name"]}))
    err = capsys.readouterr().err
    assert marker not in err
    [record] = [json.loads(line) for line in err.splitlines() if "cube_mcp_call" in line]
    assert record["row_count"] == 2


def test_tools_return_and_reuse_a_session_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": [], "cubes": []})
    ctx = MagicMock()
    first = asyncio.run(server.meta(ctx))
    second = asyncio.run(server.load(ctx, {"measures": ["v.count"]}, session_id=first["session_id"]))
    assert second["session_id"] == first["session_id"]
    records = _call_records(capsys)
    assert [r["session_id_minted"] for r in records] == [True, False]
    assert records[0]["session_id"] == records[1]["session_id"]


def test_invalid_session_id_is_never_logged(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": []})
    junk = "Student A asked about attendance"
    result = asyncio.run(server.load(MagicMock(), {"measures": ["v.count"]}, session_id=junk))
    assert result["session_id"] != junk
    assert junk not in capsys.readouterr().err


def test_meta_cache_never_holds_a_session_id(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"cubes": [{"name": "v"}]})
    ctx = MagicMock()
    first = asyncio.run(server.meta(ctx))
    second = asyncio.run(server.meta(ctx, views=["v"]))
    third = asyncio.run(server.meta(ctx))
    assert len({first["session_id"], second["session_id"], third["session_id"]}) == 3
    for (_email, _scope), (_expires, payload) in server._meta_memory_cache.items():
        assert "session_id" not in payload
    for cache_file in tmp_path.glob("cube-meta-*.json"):
        assert "session_id" not in json.loads(cache_file.read_text(encoding="utf-8"))["payload"]


def test_question_and_assumptions_follow_the_switch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for switch, expect_text in (("false", False), ("true", True)):
        server = _stdio_server(monkeypatch, tmp_path, CUBE_MCP_LOG_FREE_TEXT=switch)
        _fake_cube(server, monkeypatch, {"data": []})
        asyncio.run(
            server.load(
                MagicMock(),
                {"measures": ["v.count"]},
                question="How many?",
                assumptions="This year",
            )
        )
        [record] = _call_records(capsys)
        assert record["question_provided"] is True
        assert (record["question"] == "How many?") is expect_text
        assert (record["assumptions"] == "This year") is expect_text


def test_error_before_email_is_recorded_and_reraised(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    missing = server.MissingUserEmailError("no email")

    async def no_email(_ctx: object) -> str:
        raise missing

    monkeypatch.setattr(server, "_get_user_email", no_email)
    with pytest.raises(server.MissingUserEmailError) as caught:
        asyncio.run(server.sql(MagicMock(), {"measures": ["v.count"]}))
    assert caught.value is missing
    [record] = _call_records(capsys)
    assert record["email"] is None
    assert record["outcome"] == "error"
    assert record["error_message"] == "no email"


def test_cube_error_is_recorded_and_reraised(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)

    async def failing_request(*args: object, **kwargs: object) -> dict[str, Any]:
        del args, kwargs
        raise RuntimeError("Cube POST /load 400: Unknown member v.nope")

    monkeypatch.setattr(server, "_request", failing_request)
    with pytest.raises(RuntimeError, match="Unknown member"):
        asyncio.run(server.load(MagicMock(), {"measures": ["v.nope"]}))
    [record] = _call_records(capsys)
    assert record["outcome"] == "error"
    assert record["members_referenced"] == ["v.nope"]


def test_tool_returns_result_when_emit_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": [{"v.count": "3"}]})

    def broken_print(*args: object, **kwargs: object) -> None:
        raise OSError("stderr closed")

    monkeypatch.setattr("builtins.print", broken_print)
    result = asyncio.run(server.load(MagicMock(), {"measures": ["v.count"]}))
    assert result["data"] == [{"v.count": "3"}]


def test_tool_schemas_expose_the_new_optional_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import inspect

    server = _load_server(monkeypatch)
    expected = {
        "meta": {"session_id"},
        "load": {"question", "session_id", "assumptions"},
        "sql": {"question", "session_id"},
    }
    for name, params in expected.items():
        signature = inspect.signature(getattr(server, name))
        for param in params:
            assert signature.parameters[param].default is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: the new tests
FAIL (no record lines, `KeyError: 'session_id'`, unexpected keyword
`session_id`). The 2 edited tests PASS.

- [ ] **Step 4: Implement**

Part 1: move the body of `meta` after `scope = _meta_scope_key(views)` into a
new helper directly above `meta`:

```python
async def _meta_payload(
    email: str, views: list[str] | None, force_refresh: bool
) -> dict[str, Any]:
    """The `meta` catalog for `email`, filtered to `views` when given, served
    from cache when fresh."""
    scope = _meta_scope_key(views)
    if scope == "all":
        return await _fetch_full_meta(email, force_refresh)

    cached = _read_meta_cache(email, scope, force_refresh)
    if cached is not None:
        return cached
    full_payload = await _fetch_full_meta(email, force_refresh)
    wanted = set(views or [])
    payload = {
        **full_payload,
        "cubes": [
            dict(c) for c in full_payload.get("cubes", []) if c.get("name") in wanted
        ],
    }
    _write_meta_cache(email, scope, payload)
    return payload
```

Part 2: change `meta`'s signature and body (keep the existing docstring and add
the paragraph shown, just before the paragraph that starts "Cached per"):

```python
@mcp.tool()
async def meta(
    ctx: Context,
    views: list[str] | None = None,
    force_refresh: bool = False,
    session_id: str | None = None,
) -> dict[str, Any]:
    """...existing text...

    Session: every cube response carries a `session_id`. Pass it back as
    `session_id` on every later cube call in this conversation.

    ...existing "Cached per" paragraph...
    """
    async with _recorded(ctx, "meta", session_id=session_id, views=views) as record:
        record.email = await _get_user_email(ctx)
        payload = await _meta_payload(record.email, views, force_refresh)
    # A copy: the cached payload is shared by every caller for an hour.
    return {**payload, "session_id": record.session_id}
```

Part 3: change `load` (add the paragraph at the end of its docstring):

```python
@mcp.tool()
async def load(
    ctx: Context,
    query: dict[str, Any],
    question: str | None = None,
    session_id: str | None = None,
    assumptions: str | None = None,
) -> dict[str, Any]:
    """...existing text...

    Every call is recorded for the data team, never with the result rows. Pass
    `question`: the person's question, verbatim, and the same text on every
    call made for it. If an earlier cube response in this conversation gave you
    a `session_id`, pass it. Pass `assumptions`: the interpretive choices you
    made turning the question into this query.
    """
    sent = _with_default_timezone(query)
    async with _recorded(
        ctx,
        "load",
        session_id=session_id,
        question=question,
        assumptions=assumptions,
        query=sent,
    ) as record:
        record.email = await _get_user_email(ctx)
        result = await _request(
            "POST", "/load", json={"query": sent}, email=record.email, poll=True
        )
        record.result = result
    return {**result, "session_id": record.session_id}
```

Part 4: change `sql` (add the paragraph at the end of its docstring):

```python
@mcp.tool()
async def sql(
    ctx: Context,
    query: dict[str, Any],
    question: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """...existing text...

    Every call is recorded for the data team. Pass `question`: the person's
    question, verbatim, and the same text on every call made for it. If an
    earlier cube response in this conversation gave you a `session_id`, pass
    it.
    """
    sent = _with_default_timezone(query)
    async with _recorded(
        ctx, "sql", session_id=session_id, question=question, query=sent
    ) as record:
        record.email = await _get_user_email(ctx)
        result = await _request(
            "GET", "/sql", params={"query": json.dumps(sent)}, email=record.email
        )
    return {**result, "session_id": record.session_id}
```

`sql` does not set `record.result`, so its row's load fields stay null.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/cube/test_mcp_server.py -v` Expected: all PASS.

- [ ] **Step 6: Smoke-test the real server in stdio mode**

The unit tests mock `ctx`. This checks that `MCPServer` still builds the tool
schemas with the new parameters and that a real `Context` passes through
`_client_user_agent`.

```bash
cd W && CUBE_REST_URL=https://example.invalid/cubejs-api/v1 CUBE_API_SECRET=x \
  uv run --with 'mcp>=2.0' --with httpx --with pyjwt python -c '
import asyncio, importlib.util
spec = importlib.util.spec_from_file_location("s", "src/cube/mcp/server.py")
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
tools = asyncio.run(s.mcp.list_tools())
for t in tools:
    print(t.name, sorted(t.input_schema["properties"]))
'
```

Expected:

```text
meta ['force_refresh', 'session_id', 'views']
load ['assumptions', 'query', 'question', 'session_id']
sql ['query', 'question', 'session_id']
```

If `list_tools` or `input_schema` has a different name in the installed SDK,
read `.venv/lib/python3.13/site-packages/mcp/server/mcpserver/server.py` for the
current one; do not guess.

- [ ] **Step 7: Commit**

```bash
git -C W add -u
git -C W commit -m "feat(cube): record every meta, load and sql call with a session id"
```

---

### Task 5: Deploy settings, sink guide, and the server's CLAUDE.md

**Files:**

- Modify: `.github/workflows/deploy-cube-mcp.yaml:84`
- Modify: `docs/guides/cube.md` (new section at the end)
- Modify: `src/cube/mcp/CLAUDE.md` (_Files_ list and _When to edit_)

**Interfaces:**

- Consumes: the setting names `SERVER_SHA` and `CUBE_MCP_LOG_FREE_TEXT`, and the
  log filter `jsonPayload.event="cube_mcp_call"` (Task 2).
- Produces: nothing code consumes.

- [ ] **Step 1: Deploy workflow**

In `.github/workflows/deploy-cube-mcp.yaml`, extend `--set-env-vars` on line 84:

```yaml
--set-env-vars=TRANSPORT=http,CUBE_REST_URL=${{ vars.CUBE_REST_URL
}},AUTHKIT_DOMAIN=${{ vars.AUTHKIT_DOMAIN }},PUBLIC_URL=${{ vars.PUBLIC_URL
}},SERVER_SHA=${{ github.sha }},CUBE_MCP_LOG_FREE_TEXT=false \
```

Above the `gcloud run deploy` line, under the existing comment, add:

```yaml
# CUBE_MCP_LOG_FREE_TEXT stays false until People Operations approves
# storing question text (Refs #5613). Turning it on is this 1 value.
```

- [ ] **Step 2: Check the dataset location before writing the guide**

Run through the BigQuery MCP (`execute_sql_readonly`):

```sql
select schema_name, location
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.SCHEMATA
where schema_name in ('kipptaf_marts', 'kipptaf_extracts')
```

Expected: `location` is `US`. If it differs, use that value in Step 3's
`location`.

- [ ] **Step 3: Sink guide**

Append to `docs/guides/cube.md`:

````markdown
## MCP call record

The Cube MCP server writes 1 JSON line per tool call to stderr. Cloud Run ships
it to Cloud Logging, and a log sink routes it into BigQuery. The server code and
its field allowlist are in `src/cube/mcp/server.py` (`CALL_RECORD_FIELDS`).

The sink is set up once, by someone with admin on both `teamster-mcp` and
`teamster-332318`. Create it before the server change deploys: a sink routes
only entries written after it exists.

1. Create the dataset, with rows expiring after 730 days:

   ```bash
   bq query --project_id=teamster-332318 --use_legacy_sql=false '
   create schema `teamster-332318.cube_mcp_logs`
   options (
       location = "US",
       default_partition_expiration_days = 730,
       description = "Cube MCP call records routed from Cloud Logging"
   )'
   ```

2. Create the sink:

   ```bash
   gcloud logging sinks create cube-mcp-calls \
     bigquery.googleapis.com/projects/teamster-332318/datasets/cube_mcp_logs \
     --project=teamster-mcp \
     --use-partitioned-tables \
     --log-filter='resource.type="cloud_run_revision" AND resource.labels.service_name="cube-mcp" AND jsonPayload.event="cube_mcp_call"'
   ```

3. Read the sink's writer identity:

   ```bash
   gcloud logging sinks describe cube-mcp-calls --project=teamster-mcp \
     --format='value(writerIdentity)'
   ```

4. Let it write to the dataset. Paste the whole identity from step 3; it already
   starts with `serviceAccount:`. `bq add-iam-policy-binding` accepts only
   tables and views, so the grant is SQL:

   ```bash
   bq query --project_id=teamster-332318 --use_legacy_sql=false '
   grant `roles/bigquery.dataEditor`
   on schema `teamster-332318.cube_mcp_logs`
   to "<writer identity>"'
   ```

The first routed entry creates table `run_googleapis_com_stderr`, partitioned by
day on `timestamp`. Each field lands under the `jsonPayload` record.

!!! warning "Free text is off"

    `CUBE_MCP_LOG_FREE_TEXT` is `false` in the deploy workflow, so `question`
    and `assumptions` are logged empty. Turn it on only with People Operations
    approval, in a PR that links it.
````

Before committing, check the gcloud flags against the installed CLI. Ask the
user to run this if the permission check blocks it:
`gcloud logging sinks create --help | grep -E "use-partitioned-tables|log-filter"`.
Both flags must appear. If either is missing, fix the command from the help
text.

- [ ] **Step 4: Server CLAUDE.md**

In `src/cube/mcp/CLAUDE.md`, under _When to edit_, add:

```markdown
- A field in the call record: edit `CALL_RECORD_FIELDS` and `_CallRecord.row()`
  in `server.py`. `tests/cube/test_mcp_server.py` pins the logged keys to that
  tuple, and the dbt staging model `stg_cube__mcp_calls` must match it. Keep
  each field's JSON type fixed, with `null` for absent, never `""` or `[]`: the
  BigQuery sink drops an entry whose type disagrees with its column. Sink setup:
  `docs/guides/cube.md`, _MCP call record_.
```

- [ ] **Step 5: Lint**

```bash
cd W && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  .github/workflows/deploy-cube-mcp.yaml docs/guides/cube.md src/cube/mcp/CLAUDE.md \
  src/cube/mcp/server.py tests/cube/test_mcp_server.py </dev/null
```

Expected: `No issues`. Fix anything reported; for formatting only, run
`trunk fmt` on the same files.

- [ ] **Step 6: Commit**

```bash
git -C W add -u
git -C W commit -m "feat(cube): deploy the MCP call record with free text off and document its sink"
```

---

### Task 6: Check that the new tool text does not hurt query building

**Files:** none changed. This is a measurement.

- [ ] **Step 1: Read the harness instructions**

Read `src/cube/mcp/eval/README.md` for the exact run command and how to point it
at a server file.

- [ ] **Step 2: Run the existing eval on `main` and on this branch**

Use the same prompts, reps and model for both runs. The harness is unchanged.
This compares the tool descriptions only; the logging itself has no
model-visible effect beyond the `session_id` key in responses.

- [ ] **Step 3: Compare**

The branch passes if every family's score is within the `main` run's Wilson
interval. If a family drops outside it, stop and report the family, both scores
and both intervals. Do not reword the descriptions to chase the number without
the user.

- [ ] **Step 4: Record the result for the PR body**

Keep the per-family scores and intervals. They go in the PR's _Reviewer Notes_.

---

### Task 7: Open the PR

- [ ] **Step 1: Run the suite once more**

Run: `uv run pytest tests/cube/test_mcp_server.py -v 2>&1 | tail -n 30`
Expected: all PASS.

- [ ] **Step 2: Push and open the PR**

Push the branch. Open the PR with `mcp__github__create_pull_request`, base
`main`, body from `.github/pull_request_template.md`. The body includes:

- `Refs #5613` (not `Closes`: PR 2, the dbt model, follows).
- Under _Reviewer Notes_: free text is off by default and gated on People
  Operations; the sink is created by hand from `docs/guides/cube.md` before
  merge; the eval comparison from Task 6; this PR must merge after #5495's PR
  (Task 8).
- No PII values anywhere in the body.

- [ ] **Step 3: After the first production rows arrive (post-merge)**

Check 3 things against the sink table and note them on #5613 for PR 2:

1. Whether `jsonPayload.ts` and `jsonPayload.last_refresh_time` landed as STRING
   or TIMESTAMP.
2. Whether a real `usedPreAggregations` entry carries `preAggregationId` (needs
   a query a pre-aggregation serves; #5557).
3. Whether the BigQuery job label `cube_request_id` equals the logged id or
   carries a suffix (needs `bigquery.jobs.listAll` on `teamster-332318`).

---

### Task 8: Rebase onto #5495 once it merges

#5495's work (`cristinabaldor/feat/claude-cube-project-knowledge-drain`) edits
the same `load` body and docstrings. This PR merges after it.

- [ ] **Step 1: Merge `origin/main` into this branch after #5495 lands**

Invoke `resuming-a-branch` first. Expect conflicts in `load` and its docstring,
and in `tests/cube/test_mcp_server.py`.

- [ ] **Step 2: Resolve `load` so the empty-result note and the record agree**

Keep both changes. The record's `outcome` must use #5495's definition of empty,
which also counts 1 all-null-or-zero row on an ungrouped query. Extract the test
out of `_with_empty_result_note` into a helper both use:

```python
def _is_empty_result(payload: dict[str, Any], query: dict[str, Any]) -> bool:
    """`data: []`, or the single all-null-or-zero row Cube returns for an
    ungrouped query over an empty slice."""
    data = payload.get("data")
    return isinstance(data, list) and (
        not data
        or (
            len(data) == 1
            and isinstance(data[0], dict)
            and not _groups_rows(query)
            and all(_is_null_or_zero(v) for v in data[0].values())
        )
    )
```

Rewrite the first branch of `_with_empty_result_note` to call it. In
`_CallRecord.row()`, replace `elif summary.get("row_count") == 0:` with:

```python
        elif (
            self.tool == "load"
            and self.result is not None
            and self.query is not None
            and _is_empty_result(self.result, self.query)
        ):
```

The `load` body becomes:

```python
        result = await _request(
            "POST", "/load", json={"query": sent}, email=record.email, poll=True
        )
        record.result = result
    # The record reads the raw result; the note is for the model only.
    return {**_with_empty_result_note(result, query), "session_id": record.session_id}
```

- [ ] **Step 3: Add the test that pins the shared definition**

```python
def test_ungrouped_all_null_row_logs_as_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    server = _stdio_server(monkeypatch, tmp_path)
    _fake_cube(server, monkeypatch, {"data": [{"v.count": None}]})
    result = asyncio.run(server.load(MagicMock(), {"measures": ["v.count"]}))
    assert "note" in result
    [record] = _call_records(capsys)
    assert record["outcome"] == "empty"
```

- [ ] **Step 4: Run, lint, commit, push**

Run the full `tests/cube/test_mcp_server.py`, then Task 5 Step 5's lint, then
commit and push.
