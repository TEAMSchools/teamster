# Overgrad Catch-Up Pull Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each Overgrad list pull lands every `id` exactly once and includes
every record edited during the pull.

**Architecture:** After the full pull, the asset pulls again with
`updated_after` set to the pull's start time minus 1 second, then merges both
pulls by `id`, keeping the newer `updated_at`. `OvergradResource.list()` learns
to pass caller `params` through.

**Tech Stack:** Python 3.13, Dagster, requests, pytest.

**Spec:** `docs/superpowers/specs/2026-10-28-overgrad-catch-up-pull-design.md`

## Global Constraints

- Catch-up applies only to `students`, `admissions`, `followings`. `schools`,
  `custom_fields`, and the partitioned `universities` path are unchanged.
- `updated_after = start - 1 second`, where `start = datetime.now(UTC)` taken
  immediately before the full pull.
- Format: UTC ISO 8601 with milliseconds and `Z`, e.g.
  `2026-10-28T18:52:15.906Z`. Never send an offset; the API ignores it.
- Compare `updated_at` as parsed datetimes (`datetime.fromisoformat`), not
  strings.
- No dbt changes.
- Run tests with `uv run pytest <file>` from the worktree root; never bare
  `uv run pytest`.

## Review Focus

1. The same `id` appears twice inside the full pull itself (the #5852 incident):
   the merged output holds one copy, the newer one.
2. The catch-up returns an older copy than the full pull (impossible in theory,
   but cheap to guard): the full pull's newer copy wins.
3. A record has `updated_at: None` (the schema allows it): it loses to any dated
   copy and does not raise.
4. A caller passes `params`: `list()` keeps them on every page and does not
   mutate the caller's dict.
5. The catch-up returns nothing: the output equals the full pull.

---

### Task 1: `list()` passes caller params through

**Files:**

- Modify: `src/teamster/libraries/overgrad/resources.py` (`list()`)
- Test: `tests/resources/test_resource_overgrad.py`

**Interfaces:**

- Produces:
  `OvergradResource.list(path: str, *args: str, **kwargs) -> list[dict]`, where
  `kwargs["params"]` (optional dict) is merged with `limit` and `page` on every
  request.

- [ ] **Step 1: Write the failing test** `test_list_passes_params_through`.
      Reuse `_FakeResponse` with `total_pages=2`. The fake `_request` records a
      copy of each `params` it receives. Call
      `resource.list(path="admissions", params={"updated_after": "2026-10-28T18:00:00.000Z"})`
      with a dict the test keeps a reference to. Assert:

  ```python
  assert [p["updated_after"] for p in seen] == ["2026-10-28T18:00:00.000Z"] * 2
  assert [p["page"] for p in seen] == [1, 2]
  assert all(p["limit"] == resource.page_limit for p in seen)
  assert caller_params == {"updated_after": "2026-10-28T18:00:00.000Z"}
  ```

- [ ] **Step 2: Run it and confirm it fails**

  Run: `uv run pytest tests/resources/test_resource_overgrad.py -k params -q`
  Expected: FAIL, because `updated_after` is missing from the request params.

- [ ] **Step 3: Implement.** In `list()`, build
      `{**kwargs.pop("params", {}), "limit": self.page_limit}` as a new dict
      (`pop`, per `src/teamster/CLAUDE.md` kwargs forwarding).

- [ ] **Step 4: Run the whole file and confirm it passes**

  Run: `uv run pytest tests/resources/test_resource_overgrad.py -q` Expected:
  all pass.

- [ ] **Step 5: Commit**
      `fix(overgrad): pass caller params through OvergradResource.list`

### Task 2: Catch-up pull and merge in the asset

**Files:**

- Modify: `src/teamster/libraries/overgrad/assets.py`
- Test: `tests/assets/test_assets_overgrad_catch_up.py` (new, offline)

**Interfaces:**

- Consumes: Task 1's `list(path=..., params=...)`.
- Produces: `merge_by_id(full: list[dict], catch_up: list[dict]) -> list[dict]`
  in `teamster.libraries.overgrad.assets`, a module-level function.
  `CATCH_UP_ENDPOINTS = {"students", "admissions", "followings"}`.

- [ ] **Step 1: Write the failing merge tests** in the new file, each calling
      `merge_by_id` with records shaped `{"id": int, "updated_at": str | None}`:

  - `test_merge_dedupes_within_full_pull`: full has id 1 at `...T10:00:00.000Z`
    and at `...T11:00:00.000Z`. Result: one id 1, with `T11`.
  - `test_merge_catch_up_newer_wins`: full id 1 `T10`, catch-up id 1 `T11`.
    Result: `T11`.
  - `test_merge_full_newer_wins`: full id 1 `T11`, catch-up id 1 `T10`. Result:
    `T11`.
  - `test_merge_adds_catch_up_only_record`: full ids `[1]`, catch-up ids `[2]`.
    Result ids sorted: `[1, 2]`.
  - `test_merge_none_updated_at_loses`: full id 1 `None`, catch-up id 1 `T10`.
    Result: `T10`, and no exception.
  - `test_merge_empty_catch_up`: result equals full (same ids and values).

- [ ] **Step 2: Write the failing asset test**
      `test_catch_up_pull_params_and_merge`. Subclass `OvergradResource` as in
      `tests/assets/test_assets_overgrad_dynamic_partitions.py`. Its `list()`
      records each call's `params` and returns
      `[{"id": 1, "updated_at": "2026-10-28T10:00:00.000Z", "university": {"id": 99}}]`
      on the first call and
      `[{"id": 1, "updated_at": "2026-10-28T11:00:00.000Z", "university": {"id": 99}}, {"id": 2, "updated_at": "2026-10-28T11:00:00.000Z", "university": {"id": 99}}]`
      on the second. Materialize `followings` with `mem_io_manager`, capturing
      `before = datetime.now(UTC)` and `after` around it. Assert:

  ```python
  assert len(calls) == 2
  assert calls[0] is None  # full pull sends no params
  ts = calls[1]["updated_after"]
  assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z", ts)
  parsed = datetime.fromisoformat(ts)
  assert before - timedelta(seconds=1, milliseconds=1) <= parsed <= after - timedelta(seconds=1)
  assert record_count metadata == 2
  ```

  Add `test_no_catch_up_for_schools`: materializing `schools` calls `list()`
  once.

- [ ] **Step 3: Run them and confirm they fail**

  Run: `uv run pytest tests/assets/test_assets_overgrad_catch_up.py -q`
  Expected: FAIL on the `merge_by_id` import.

- [ ] **Step 4: Implement `merge_by_id`.** Iterate `full` then `catch_up` into a
      dict keyed on `id`, replacing an entry only when the incoming `updated_at`
      parses later. A `None` `updated_at` sorts as `datetime.min` with UTC
      tzinfo.

- [ ] **Step 5: Wire the asset.** In the unpartitioned branch of `_asset`: when
      `name in CATCH_UP_ENDPOINTS`, take `start` before
      `overgrad.list(path=name)`, then call `overgrad.list` again with
      `params={"updated_after": <start - 1s formatted>}` and set
      `data = merge_by_id(full, catch_up)`. Format with
      `.isoformat(timespec="milliseconds").replace("+00:00", "Z")`. Add the
      comment
      `# shortcut: an edit during the catch-up pull itself waits for the next run; close it with a second pass if that gap ever matters`.
      University-ID registration and the schema check run on the merged `data`,
      unchanged.

- [ ] **Step 6: Run both test files and confirm they pass**

  Run:
  `uv run pytest tests/assets/test_assets_overgrad_catch_up.py tests/assets/test_assets_overgrad_dynamic_partitions.py tests/resources/test_resource_overgrad.py -q`
  Expected: all pass.

- [ ] **Step 7: Confirm the code locations still load**

  Run:
  `uv run dagster definitions validate -m teamster.code_locations.kippnewark.definitions 2>&1 | tail -n 5`
  (needs the dbt manifest; see `src/teamster/CLAUDE.md`). Expected: valid.

- [ ] **Step 8: Commit**
      `fix(overgrad): catch-up pull after full pull, merge by id` with
      `Closes #5852` in the body.
