# Tableau-truth validator, review revision: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Tableau-truth validator safe and right to run live on the DDI
Suite: fix the 5 blockers the independent review found, then build the compare,
explain, mapping, output and Asana-row changes the spec revision settled.

**Architecture:** The two scripts keep their split. `cube_validate_snapshot.py`
(Tableau side) learns raw captions, group cards, value lists for `(All)`,
listed-sheet exports, a new export order and a read-only `close`.
`cube_validate.py` (Cube side) learns two Cube routes per query, a trust rate,
per-batch error handling, fail labels, new mapping keys, richer digest and
drafts, and Asana rows keyed by caption. The `cube-dashboard` skill reorders the
session around a cheap default-state mapping loop. The DDI checks file is
corrected and committed last.

**Tech Stack:** Python 3.13, `tableauserverclient`, `tableauhyperapi` (per run,
`uv run --with`), `httpx` + `pyjwt` (Cube REST), `sqlglot`, `defusedxml`,
`pyyaml`, pytest.

**Spec:**
`docs/superpowers/specs/2026-10-09-cube-validate-tableau-truth-design.md`,
section "Revision 2026-10-13: independent review" (binding; it replaces earlier
sections on the same point). Evidence and reasoning for every decision:
`~/asana-sync/handoffs/5-cube-validate-review-findings.md` (section 7 is the
decision log; B1-B5, I1-I11 and M1-M7 refer to its sections 2-6). Where the two
differ, the spec revision wins.

## Global Constraints

- Branch: `cristinabaldor/feat/claude-cube-dashboard-tableau-truth`, main
  checkout. Never stage `.devcontainer/tpl/.env.tpl` (the user's own change).
  Stage named files only; never `git add -A`.
- Run tests with
  `uv run --with tableauhyperapi pytest <file>[::<test>] -q -p no:cacheprovider 2>&1 | tail -n 30`.
  Never bare `pytest`, never `uv run pytest` without a path. Baseline before
  Task 1: 173 pass across the two test files.
- Full suite after each task:
  `uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py tests/scripts/test_cube_validate_snapshot.py -q -p no:cacheprovider 2>&1 | tail -n 30`.
- Both scripts stay standalone (no PEP 723 header, no imports between them).
  Tests load them with `importlib`, registering `sys.modules[name]` before
  `exec_module` (`scripts/CLAUDE.md`).
- **The tool makes no delete call to Tableau** (spec revision, The session).
- Review project: only `ddc817c2-6bc7-4bca-8be9-e385f95b9ebc` (TEMP-CB). A
  review copy's name is `ZZ-REVIEW <YYYY-MM-DD> <HHMM> <workbook>`.
- Constants: `SMALL_CELL = 10`, `TRUST = 0.95`, `KEEP_SNAPSHOTS = 2`.
- Test fixtures are synthetic. No real student, school-staff or teacher value is
  committed, printed by a test, or written to a commit message. Snapshot data
  under `~/.cache/cube-validate/` is read for column names and aggregates only.
- Verdict order, strongest first: `fail`, `incomplete`, `fix_cube`,
  `fix_source`, `undecided`, `missing_member`, `pass`.
- Nothing in this plan runs against Tableau, Cube, BigQuery or Asana except Task
  35's read-only Asana listing. Task 36 is the user's to run.
- Credentialed runs happen only inside a throwaway `tests/test_zz_*.py`, deleted
  afterwards. Never call `op`.
- Before pushing markdown or YAML, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`.
- End every commit message with
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. The commit lines in
  each task show only the subject.
- Before Task 1, assemble every task's code in a scratch copy and run both test
  files once, as the previous plan's pre-flight did, so a name or signature
  mismatch between tasks surfaces before execution. Fix the plan text, not only
  the scratch copy.

### Interpretations of the spec, stated once

- **"Only mapped sheets" means the sheets listed under `sheets:`.** The first
  `open` needs something to export before any mapping exists, so a sheet may be
  listed as a stub (`{datasource: ...}`) that `map` (Task 20) fills in. `plan`
  prints each dashboard's sheets for the analyst to choose from. A forgotten
  copy still exposes only listed sheets and click sources.
- **`filter_ignored` judges sheets with measures and no table calculation.** A
  stub sheet judges nothing, so `export` refuses filtered states on a dashboard
  until one of its sheets is mapped (Task 2).
- **Cube's routes are compared at the precision Tableau shows**: both round to
  the shown decimals and must agree; a blank or raw cell compares almost
  exactly.
- **The route mismatch is built in**: `load_checks` adds the slug
  `cube-routes-disagree` (`fix: cube`) unless the checks file overrides it, so
  the checks file can attach `issue: 5883`.
- **A group shown as a dimension** (gap 4) is compared with one Cube query per
  bin, filtered to the bin's members; percent-of-total is rebuilt after the bins
  are merged.
- **The high-school section key regexes in the review are wrong-shaped.** An
  ES/MS label `G5 - <teacher> - 601` matches the review's HS pattern
  `" - ([^-]+ - \S+)$"` and captures `<teacher> - 601`, which would then be
  shown as the "key" in every output. Task 21's tests and Task 34's checks file
  use anchored patterns: `^(?!G\d+ - ).* - ([^-]+ - \S+)$` (HS) then
  `^G\d+ - .* - (\S+)$` (ES/MS).

### Confirmed with the user (2026-10-13)

Two mapping keys came from the last part of the review and were never confirmed
one by one. The user ruled on both:

- **Task 25 (diff measure): build it.**
- **Task 27 (`fixed:`): skip it.** `Avg. % Completion` stays unmapped with a
  link to the completion finding's issue. Record the skip in the ledger; every
  "if Task 27 shipped" branch in later tasks is not taken.

The reasoning behind each ruling:

1. **`fixed: [dims]` for `Avg. % Completion` (Task 27).** Three facts from the
   workbook make it harder than "a ratio per fixed group, averaged per mark":
   - Tableau's `AVG()` over a FIXED calculation averages over rows, so groups
     with more rows weigh more. Task 27 weights each group by its row count.
   - A FIXED calculation ignores the sheet's dimension filters (academic year,
     subject group, response type). Task 27 computes the group ratio under the
     datasource filters only, on both sides.
   - DDI's `% Completion` fixes its numerator on `is_pathways` and its
     denominator on `is_replacement`. One `fixed:` list cannot express that, so
     on DDI the trust gate would fail and the cells read `incomplete`.
     Recommendation: keep `Avg. % Completion` unmapped with a link to the
     completion finding's issue until the dashboard is fixed, and build Task 27
     only if another dashboard needs it. Gap 6's original verdict was the same.
2. **A measure that is the difference of two mapped measures, for the IEP / Gen
   Ed diff (Task 25).** The mechanism is generic and cheap. The open point is
   Cube's side of the two parts: the workbook splits on
   `CONTAINS([iep_status], 'SPED')`, and Cube has only the boolean
   `student_assessment_scores_view.is_iep`. Whether they select the same
   students is unverified; a difference shows up as a `fail` the analyst
   investigates, never as a false pass.

## Review Focus

1. **An uncaptioned field, a group bin and a blank value that Tableau ignores
   anyway.** `vf` drops an unknown field or value silently. Expected: the state
   is `filter_ignored`, never `ok`, whenever a mapped sheet exports what its
   parent exported. Pinned in Task 2
   (`test_only_mapped_sheets_without_table_calcs_judge_a_filter`) and checked
   live in Task 36.
2. **A key regex that captures a person's name.** Expected: an ES/MS label never
   matches the HS pattern, and a label no pattern matches is shown as "a label
   the key pattern does not match", never as itself. Pinned in Tasks 6 and 21.
3. **`(All)` on a caption whose values pass through a lookup with a gap**
   (Schoolid 5173). Expected: the state is `missing_member`, not compared
   against a narrower Cube universe. Pinned in Task 3.
4. **A crash after an hour of Cube queries.** Expected: any exception in one
   explain batch marks that batch `incomplete` with its message, the other
   batches finish, and `cells.jsonl` keeps every finished batch. Pinned in
   Task 16.
5. **A forgotten review copy.** Expected: `open` refuses while any of this
   tool's copies of the workbook is still in TEMP-CB, and `close` marks the
   session closed only once the copy is gone. Pinned in Task 7.

---

## Part A: blockers

### Task 1: a field with no stored caption keeps its raw name (B1)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`default_caption`,
  `_saved_filters`, `_card`)
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces: `caption_of(el, field: str) -> str` (the stored caption, else the
  raw field name). Removes `default_caption`.

- [ ] **Step 1: Write the failing test**

Replace the parametrized `test_default_caption` with:

```python
def test_a_field_with_no_stored_caption_keeps_its_raw_name():
    # Tableau shows an uncaptioned field under its raw name, and vf takes the
    # shown caption: a title-cased guess was ignored silently (all 6 DIBELS states).
    wb = snap.read_workbook(TWB)
    cards = {c.field: c for c in wb.filters}
    assert cards["grade_level"].caption == "grade_level"
    assert cards["region"].caption == "region"
    assert cards["school"].caption == "School Name"  # a stored caption wins
    saved = {f.field: f for f in wb.sheet_filters["Overview - Table"]}
    assert saved["iep_status"].caption == "iep_status"
```

In `test_filter_cards_carry_field_caption_and_default`, delete the line
`assert cards["grade_level"].caption == "Grade Level"  # Tableau's default`. In
`test_read_workbook_reads_each_sheets_saved_filters`, change `"Iep Status"` to
`"iep_status"` in all 3 places.

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -p no:cacheprovider 2>&1 | tail -n 30`
Expected: FAIL, `'Grade Level' == 'grade_level'`.

- [ ] **Step 3: Implement**

Replace `default_caption` with:

```python
def caption_of(el, field: str) -> str:
    """The caption Tableau shows for a column: its stored caption, else the raw
    field name. vf takes this caption, and ignores any other silently."""
    caption = el.get("caption") if el is not None else None
    return caption or field
```

In `_saved_filters`, replace the `caption = (...) or default_caption(name)`
statement with `caption = caption_of(el, name)`. In `_card`, replace the
`caption = (...) or default_caption(field)` statement with
`caption = caption_of(col, field)`. Then confirm nothing else calls it:
`rg -n default_caption scripts tests` must print nothing.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite (Global Constraints). Expected: all pass. State ids do not
change: `slug("grade_level")` and `slug("Grade Level")` are both `grade-level`.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "fix(cube): a field with no stored caption is filtered by its raw name"
```

### Task 2: only mapped sheets without table calculations judge a filter (B1)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`filter_ignored`, `export_state`,
  `_export_all`)
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces:
  - `judged_sheets(checks: dict) -> set[str]`
  - `unjudged(states: list[State], wb: Workbook, judged: set[str]) -> list[str]`
    (dashboards with filtered states and no judged sheet)
  - `filter_ignored(parent, current, covers_all, judged: set[str] | None = None) -> bool`
  - `export_state(..., dims_for, judged: set[str] | None = None) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
def test_only_mapped_sheets_without_table_calcs_judge_a_filter():
    parent = {"Mapped": b"a\r\n1\r\n", "Running": b"r\r\n5\r\n"}
    # A running sum changes between identical calls; the mapped sheet did not change.
    current = {"Mapped": b"a\r\n1\r\n", "Running": b"r\r\n6\r\n"}
    assert snap.filter_ignored(parent, current, False, judged={"Mapped"}) is True
    # Nothing to judge: the export cannot say the filter was ignored.
    assert snap.filter_ignored(parent, current, False, judged=set()) is False


def test_judged_sheets_are_mapped_and_free_of_table_calcs():
    checks = {
        "sheets": {
            "A": {"measures": {"M": {"cube": "x", "sql": "y"}}},
            "B": {
                "measures": {
                    "P": {"cube": "x", "sql": "y", "table_calc": "running_sum"}
                }
            },
            "C": {"datasource": "d"},  # a stub the map step has not filled in
        }
    }
    assert snap.judged_sheets(checks) == {"A"}


def test_filtered_states_need_a_judged_sheet_on_their_dashboard():
    wb = snap.read_workbook(TWB)
    default = snap.State("Overview")
    north = snap.State("Overview", filters=(("region", "North"),))
    assert snap.unjudged([default, north], wb, set()) == ["Overview"]
    assert snap.unjudged([default, north], wb, {"Overview - Table"}) == []
    assert snap.unjudged([default], wb, set()) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -p no:cacheprovider -k "judge" 2>&1 | tail -n 30`
Expected: FAIL, `unexpected keyword argument 'judged'` and no attribute
`judged_sheets`.

- [ ] **Step 3: Implement**

Replace `filter_ignored` and add the two helpers after it:

```python
def filter_ignored(
    parent: dict[str, bytes],
    current: dict[str, bytes],
    covers_all: bool,
    judged: set[str] | None = None,  # None judges every exported sheet
) -> bool:
    """A filter whose state exports exactly what its parent did, though it should not."""
    if covers_all:
        return False
    mine = {s: b for s, b in current.items() if judged is None or s in judged}
    if not mine or all(csv_rows(b) == 0 for b in mine.values()):
        return False
    return all(mine[s] == parent.get(s) for s in mine)


def judged_sheets(checks: dict) -> set[str]:
    """Sheets whose exports can show that a filter took effect: mapped (they carry
    measures) and free of table calculations, whose values change between
    identical calls."""
    return {
        name
        for name, s in (checks.get("sheets") or {}).items()
        if (s or {}).get("measures")
        and not any((m or {}).get("table_calc") for m in s["measures"].values())
    }


def unjudged(states, wb: Workbook, judged: set[str]) -> list[str]:
    """Dashboards with filtered states but no sheet that can judge them."""
    return sorted(
        {
            st.dashboard
            for st in states
            if (st.filters or st.params)
            and not st.click
            and not set(wb.dashboards.get(st.dashboard, [])) & judged
        }
    )
```

In `export_state`, add the parameter `judged: set[str] | None = None` after
`dims_for`, and pass it on:
`if filter_ignored(_read_state(snapdir, parent), data, covered, judged):`.

Replace `_export_all` with:

```python
def _export_all(session, m, snapdir, wb, checks, states) -> None:
    judged = judged_sheets(checks)
    bad = unjudged(states, wb, judged)
    if bad:
        raise SessionError(
            f"map a sheet on {', '.join(bad)} before exporting filtered states: "
            "only a mapped sheet without table calculations shows a filter took effect"
        )
    all_values = _value_maps(m, snapdir)
    dims_for = {
        s: list((v.get("dims") or {})) for s, v in (checks.get("sheets") or {}).items()
    }
    with Coverage(m, snapdir) as covers:
        # Parents first, so the filter-took-effect check has something to compare with.
        for state in sorted(states, key=lambda s: (len(s.filters), s.id)):
            session.check_refresh(m.workbook_luid, m.live_updated_at)
            m.states[state.id] = export_state(
                session, m, snapdir, wb, state, all_values, covers, dims_for, judged
            )
            write_manifest(snapdir / "manifest.json", m)
            print(f"  {state.id}: {m.states[state.id]['status']}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "fix(cube): only mapped sheets without table calcs judge an ignored filter"
```

### Task 3: `(All)` means the caption's full value list, on both sides (B2)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`Manifest`, `_open`,
  `_export_all`)
- Modify: `scripts/cube_validate.py` (`_own_filters`, `state_filters`,
  `state_where`, `_trust`, `explain_cells`, `_explain_batch`, `issue_drafts`,
  `write_outputs`, `run_compare`, `_explain`, `_drafts`)
- Test: both test files

**Interfaces:**

- Produces (snapshot): `Manifest.all_values: dict[str, list[str]]` (default
  `{}`), filled by `open` and, for older snapshots, by `export`.
- Produces (Cube side):
  - `Lists(all_values: dict[str, list[str]] = {}, groups: dict[str, dict] = {})`
    with `Lists.of(manifest: dict) -> Lists` and
    `Lists.expand(caption: str, value) -> str | list[str] | None` (None: an
    `(All)` with no recorded list)
  - `_own_filters(entry, defaults, lists=None)`
  - `state_filters(entry, checks, defaults=None, lists=None)`
  - `state_where(entry, checks, fields, sheet, public_only=False, defaults=None, lists=None)`
  - `explain_cells(..., sheet_filters=None, lists=None)`,
    `issue_drafts(..., sheet_filters=None, lists=None)`,
    `write_outputs(..., sheet_filters=None, lists=None)`

- [ ] **Step 1: Write the failing tests**

Snapshot side:

```python
def test_export_records_each_captions_values_in_the_manifest(tmp_path, demo_hyper):
    m = _coverage_manifest(tmp_path, demo_hyper)
    (tmp_path / "csv").mkdir()
    s = FakeSession(lambda sheet, f: b"Region,N\r\nAll,9\r\n")
    s.check_refresh = lambda luid, at: None
    wb = snap.read_workbook(TWB)
    checks = {"sheets": {"Overview - Table": {"measures": {"N": {"sql": "x"}}}}}
    snap._export_all(s, m, tmp_path, wb, checks, [snap.State("Overview")])
    saved = snap.read_manifest(tmp_path / "manifest.json")
    assert saved.all_values["Region"] == ["North", "South"]
```

Cube side:

```python
def test_all_means_every_value_the_snapshot_recorded(tmp_path):
    c = _checks(tmp_path)
    lists = cv.Lists({"Region": ["North", "South"]})
    entry = {"state": {"dashboard": "Overview", "filters": {"Region": cv.ALL}}}
    assert cv.state_filters(entry, c, lists=lists)[0] == [
        {"member": "demo.region", "operator": "equals", "values": ["North", "South"]}
    ]
    fields = {"Region": {"field": "region", "datasource": DS}}
    sheet = c["sheets"]["Overview - Table"]
    assert cv.state_where(entry, c, fields, sheet, lists=lists) == [
        "cast(region as string) in ('North', 'South')"
    ]


def test_all_without_a_value_list_cannot_be_told_to_cube(tmp_path):
    c = _checks(tmp_path)
    entry = {"state": {"dashboard": "Overview", "filters": {"Region": cv.ALL}}}
    assert cv.state_filters(entry, c) == ([], ["Region"])


def test_all_through_a_lookup_with_a_gap_is_a_missing_member(tmp_path):
    c = _checks(
        tmp_path,
        filters={
            "Schoolid": {"cube": "demo.abbreviation", "values": {"73258": "BOLD"}}
        },
    )
    entry = {"state": {"dashboard": "Overview", "filters": {"Schoolid": cv.ALL}}}
    lists = cv.Lists({"Schoolid": ["73258", "5173"]})
    assert cv.state_filters(entry, c, lists=lists) == ([], ["Schoolid"])


def test_explain_reads_all_as_the_value_list(tmp_path):
    c = _checks(tmp_path)
    states = {
        "s": {
            "state": {"dashboard": "Overview", "filters": {"Region": cv.ALL}},
            "status": "ok",
            "sheets": {},
        }
    }
    cell = cv.Cell(
        "Overview - Table", "s", {}, "Avg Score", "48.50", 48.5, 49.0, 40, "mismatch"
    )
    sqls = []

    def run(ds, sql):
        sqls.append(sql)
        return [{"m": 48.5}]

    fields = {"Region": {"field": "region", "datasource": DS}}
    cv.explain_cells(
        [cell], c, states, fields, run, lambda q: ([], []),
        lists=cv.Lists({"Region": ["North", "South"]}),
    )
    assert sqls and all("in ('North', 'South')" in s for s in sqls)
```

Update 2 existing tests:

- In `test_state_filters_translate_captions_all_and_blank`, remove
  `"School Name": cv.ALL` from the state's `filters` (the `(All)` case now has
  its own tests).
- In
  `test_saved_defaults_filter_cube_and_the_extract_unless_the_state_overrides`,
  replace the last assertion with:

```python
    lists = cv.Lists({"Region": ["North", "South"]})
    assert cv.state_filters(every, c, defaults, lists)[0] == [
        {"member": "demo.region", "operator": "equals", "values": ["North", "South"]}
    ]
```

- [ ] **Step 2: Run them to verify they fail**

Run both test files. Expected: FAIL, no attribute `Lists`; the snapshot test
fails on `all_values`.

- [ ] **Step 3: Implement the snapshot side**

Add to `Manifest`, after `sheet_filters`:

```python
    # Every value each filter caption can take, so (All) is an explicit list.
    all_values: dict[str, list[str]] = field(default_factory=dict)
```

In `_open`, after `m.sheet_filters = sheet_filter_map(...)` and before
`write_manifest`, add `m.all_values = _value_maps(m, snapdir)`. In the resume
branch, before its `write_manifest`, add
`resume.all_values = resume.all_values or _value_maps(resume, snapdir)`.

In `_export_all`, replace `all_values = _value_maps(m, snapdir)` with:

```python
    if not m.all_values:  # a snapshot opened before value lists were recorded
        m.all_values = _value_maps(m, snapdir)
    all_values = m.all_values
```

- [ ] **Step 4: Implement the Cube side**

After the `ALL`, `BLANK`, `TOTAL`, `MULTI` constants, add:

```python
@dataclass
class Lists:
    """What (All) and a group bin stand for, as the snapshot recorded them."""

    all_values: dict[str, list[str]] = field(default_factory=dict)
    groups: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def of(cls, manifest: dict) -> Lists:
        return cls(manifest.get("all_values") or {}, manifest.get("groups") or {})

    def expand(self, caption: str, value):
        """A filter value as the stored values it stands for. None: an (All) the
        snapshot has no list for, which Cube cannot be told."""
        if value == ALL:
            found = self.all_values.get(caption)
            return None if found is None else list(found)
        return value
```

Replace `_own_filters`:

```python
def _own_filters(
    entry: dict, defaults: dict | None, lists: Lists | None = None
) -> list[tuple[str, object]]:
    """A state's filters as Tableau applies them: saved defaults it keeps, its own
    filters, and its click (with Tableau's formatting removed), each expanded to
    the stored values it stands for."""
    lists = lists or Lists()
    st = entry["state"]
    own = dict(st.get("filters") or {})
    clicks = {c: norm_dim(v) for c, v in (entry.get("click_filters") or {}).items()}
    kept = [
        (c, list(v))
        for c, v in (defaults or {}).items()
        if c not in own and c not in clicks
    ]
    return [(c, lists.expand(c, v)) for c, v in [*kept, *own.items(), *clicks.items()]]
```

Replace `state_filters`:

```python
def state_filters(
    entry: dict, checks: dict, defaults: dict | None = None, lists: Lists | None = None
) -> tuple[list[dict], list[str]]:
    st = entry["state"]
    members = _caption_members(checks)
    out, missing = [], []
    for caption, value in _own_filters(entry, defaults, lists):
        member = members.get(caption)
        if value is None:
            missing.append(caption)
            continue
        # A lookup from the extract's value to Cube's (school id to abbreviation).
        lookup = (checks["filters"].get(caption) or {}).get("values")
        if lookup is not None and value != BLANK:
            wanted = value if isinstance(value, list) else [value]
            found = [lookup.get(str(v)) for v in wanted]
            if None in found:
                missing.append(caption)
                continue
            value = found if isinstance(value, list) else found[0]
        if member is None or value == []:
            missing.append(caption)
        elif isinstance(value, list):
            out.append(
                {
                    "member": member,
                    "operator": "equals",
                    "values": [str(v) for v in value],
                }
            )
        elif value == BLANK:
            out.append({"member": member, "operator": "notSet"})
        else:
            out.append({"member": member, "operator": "equals", "values": [str(value)]})
    for caption, value in (st.get("params") or {}).items():
        out += checks["param_filters"].get(caption, {}).get(value, [])
    return out, missing
```

In `state_where`, add the parameter `lists: Lists | None = None` after
`defaults`, call `_own_filters(entry, defaults, lists)`, and change the
`if not f:` guard to `if not f or value is None:`.

Thread `lists` through, keyword `lists=lists` at every call:

- `_trust(..., defaults=None, sheet_filters=None, lists=None)`: pass to
  `state_where`.
- `explain_cells(..., defaults=None, sheet_filters=None, lists=None)`: pass to
  `_trust` and `_explain_batch`.
- `_explain_batch(..., trusted, sides, lists=None)`: pass to `state_where` and
  `state_filters`.
- `issue_drafts(..., defaults=None, sheet_filters=None, lists=None)` and
  `write_outputs(..., defaults=None, sheet_filters=None, lists=None)`: pass on
  to `state_where` and `issue_drafts`.
- `run_compare`: after reading the manifest, `lists = Lists.of(m)`; pass it to
  both `state_filters` calls.
- `_explain` and `_drafts`: pass `lists=Lists.of(m)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate_snapshot.py scripts/cube_validate.py tests/scripts/test_cube_validate.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "fix(cube): (All) filters both sides to the caption's recorded values"
```

### Task 4: group filter cards, Tableau side (B3)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`Workbook`, `read_workbook`,
  `plan_states`, `Manifest`, `Coverage._count`, `_open`, `_plan`)
- Modify: `tests/scripts/fixtures/cube_validate/review.twb` (one filter zone)
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces:
  - `Workbook.groups: dict[str, dict]`, keyed by caption:
    `{"datasource": str, "field": str, "bins": {bin: [members]}, "other": str}`
  - `Manifest.groups: dict[str, dict]`, keyed by caption:
    `{"datasource": str, "field": str, "bins": {bin: [members]}}`, the Other bin
    included with its members; only members the extract has are kept
  - `group_lists(wb: Workbook, m: Manifest, snapdir: Path) -> dict[str, dict]`
  - `value_lists(m: Manifest, snapdir: Path) -> dict[str, list[str]]` (the
    extract's values, and each group's bin names)

- [ ] **Step 1: Add a group filter card to the fixture**

In `review.twb`, inside the dashboard's outer zone, after the zone with
`id='12'`, add:

```xml
          <zone h='5000' id='13' mode='checkdropdown' name='Overview - Table' param='[federated.demo1].[Subject (group)]' type-v2='filter' w='10000' x='90000' y='90000' />
```

In `test_filter_cards_carry_field_caption_and_default`, add `"Subject (group)"`
to the expected set of card fields.

- [ ] **Step 2: Write the failing tests**

```python
def test_read_workbook_lists_groups_with_their_bins():
    g = snap.read_workbook(TWB).groups["Subject Group"]
    assert g == {
        "datasource": DS,
        "field": "subject",
        "bins": {"Literacy": ["English", "Writing"]},
        "other": "Other",
    }


def test_every_bin_of_a_group_card_is_a_must_state_other_included():
    must = _ids(_plan(), "must")
    assert {
        "overview--subject-group-literacy",
        "overview--subject-group-other",
        "overview--subject-group-all",  # its saved default is Literacy, not All
    } <= must


PAIR = {
    "datasource": DS,
    "field": "school",
    "bins": {"AB": ["Alpha", "Beta", "Nowhere"]},  # Nowhere is not in the extract
    "other": "Rest",
}


def test_group_lists_fill_the_other_bin_from_the_extract(tmp_path, demo_hyper):
    m = _coverage_manifest(tmp_path, demo_hyper)
    wb = snap.Workbook({}, [], [], [], {}, {"Pair": PAIR})
    out = snap.group_lists(wb, m, tmp_path)
    assert out["Pair"] == {
        "datasource": DS,
        "field": "school",
        "bins": {"AB": ["Alpha", "Beta"], "Rest": ["Delta", "Gamma"]},
    }


def test_value_lists_give_a_group_its_bin_names(tmp_path, demo_hyper):
    m = _coverage_manifest(tmp_path, demo_hyper)
    m.groups = {"Pair": {**PAIR, "bins": {"AB": ["Alpha", "Beta"], "Rest": []}}}
    assert snap.value_lists(m, tmp_path)["Pair"] == ["AB", "Rest"]


def test_coverage_expands_a_group_bin_to_its_members(tmp_path, demo_hyper):
    m = _coverage_manifest(tmp_path, demo_hyper)
    m.fields["Pair"] = {"field": "Pair (copy)", "datasource": DS}
    m.groups = {
        "Pair": {
            "datasource": DS,
            "field": "school",
            "bins": {"AB": ["Alpha", "Beta"], "Rest": ["Delta", "Gamma"]},
        }
    }
    with snap.Coverage(m, tmp_path) as covers:
        # Every North student is at Alpha or Beta.
        assert covers(
            snap.State("Overview", filters=(("Region", "North"), ("Pair", "AB")))
        )
        assert not covers(snap.State("Overview", filters=(("Pair", "AB"),)))
```

- [ ] **Step 3: Run them to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -p no:cacheprovider 2>&1 | tail -n 30`
Expected: FAIL, no attribute `groups` / `group_lists` / `value_lists`.

- [ ] **Step 4: Implement**

Add to `Workbook`: `groups: dict[str, dict] = field(default_factory=dict)`.

In `read_workbook`, inside the `for ds in root.iter("datasource")` loop, after
the `for c in ds.findall("column")` loop body records the column, read groups:

```python
    groups: dict[str, dict] = {}
    for ds in root.iter("datasource"):
        name = ds.get("name") or ""
        if ds.get("caption"):
            ds_caption[name] = ds.get("caption") or name
        for c in ds.findall("column"):
            col_name = (c.get("name") or "").strip("[]")
            columns[(name, col_name)] = c
            calc = c.find("calculation")
            if calc is not None and calc.get("class") == "categorical-bin":
                groups[caption_of(c, col_name)] = {
                    "datasource": ds.get("caption") or name,
                    "field": (calc.get("column") or "").strip("[]"),
                    "bins": {
                        _unquote(b.get("value") or ""): [
                            _unquote(v.text or "") for v in b.findall("value")
                        ]
                        for b in calc.findall("bin")
                    },
                    "other": _unquote(calc.get("default") or ""),
                }
```

and return
`Workbook(dashboards, filters, params, actions, sheet_filters, groups)`.

In `plan_states`, inside the filter-card loop, right after the person-level
`continue`, add:

```python
            g = wb.groups.get(c.caption)
            if g is not None:
                if not c.default_all:
                    add("must", "saved default is not All", filters=one(ALL))
                for b in [*g["bins"], *([g["other"]] if g["other"] else [])]:
                    add("must", "group bin", filters=one(b))
                continue
```

Add to `Manifest`: `groups: dict[str, dict] = field(default_factory=dict)`.

After `_value_maps`, add:

```python
def group_lists(wb: Workbook, m: Manifest, snapdir: Path) -> dict[str, dict]:
    """The workbook's groups the extracts can expand, with the Other bin filled in:
    every value of the column that no named bin lists."""
    out: dict[str, dict] = {}
    by_ds: dict[str, list[str]] = {}
    for caption, g in wb.groups.items():
        by_ds.setdefault(g["datasource"], []).append(caption)
    for ds, captions in by_ds.items():
        if ds not in m.extracts:
            continue
        with Hyper(Path(snapdir) / m.extracts[ds]["file"]) as h:
            cols = set(h.columns())
            captions = [c for c in captions if wb.groups[c]["field"] in cols]
            prof = profile(h, sorted({wb.groups[c]["field"] for c in captions}))
        for caption in captions:
            g = wb.groups[caption]
            present = {v for v, _ in prof[g["field"]] if v is not None}
            named = {v for members in g["bins"].values() for v in members}
            # A member the extract lacks filters nothing, and its missing Cube lookup
            # would make the whole bin a missing member.
            bins = {
                b: [v for v in members if v in present] for b, members in g["bins"].items()
            }
            if g["other"]:
                bins[g["other"]] = [
                    v for v, _ in prof[g["field"]] if v is not None and v not in named
                ]
            out[caption] = {"datasource": ds, "field": g["field"], "bins": bins}
    return out


def value_lists(m: Manifest, snapdir: Path) -> dict[str, list[str]]:
    """Every value each filter caption can take: the extract's values, and for a
    group its bin names, so vf can send (All)."""
    out = _value_maps(m, snapdir)
    for caption, g in m.groups.items():
        out[caption] = list(g["bins"])
    return out
```

In `_open`, replace `m.all_values = _value_maps(m, snapdir)` with
`m.groups = group_lists(wb, m, snapdir)` followed by
`m.all_values = value_lists(m, snapdir)`. In the resume branch, set
`resume.groups = resume.groups or group_lists(wb, resume, snapdir)` before
`resume.all_values = resume.all_values or value_lists(resume, snapdir)`. In
`_export_all`, use `value_lists` in place of `_value_maps`.

In `Coverage._count`, at the top of the `for caption, value in pairs:` loop:

```python
            g = self.m.groups.get(caption)
            if g is not None:
                if g["datasource"] != ds or g["field"] not in self.cols[ds]:
                    continue
                if value == ALL:
                    continue
                names = value if isinstance(value, list) else [value]
                members = [v for n in names for v in g["bins"].get(n, [])]
                listed = ", ".join(_sql_text(v) for v in members) or "null"
                conds.append(f'cast("{g["field"]}" as text) in ({listed})')
                continue
```

In `_plan`, keep the groups when it rebuilds the workbook for the chosen
dashboards: pass `wb.sheet_filters, wb.groups` as the last 2 arguments of
`Workbook(...)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py tests/scripts/fixtures/cube_validate/review.twb
git commit -m "fix(cube): plan every bin of a group filter card and record its members"
```

### Task 5: group captions expand to their members on the Cube side (B3)

**Files:**

- Modify: `scripts/cube_validate.py` (`Lists`, `state_where`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `Manifest.groups` (Task 4), `Lists` (Task 3).
- Produces: `Lists.expand` expands a group caption's bin (or list of bins, or
  `(All)`) to members; `Lists.column(caption: str) -> str | None` (a group's
  underlying extract column).

- [ ] **Step 1: Write the failing tests**

```python
GROUPS = {
    "Subject Group": {
        "datasource": DS,
        "field": "subject",
        "bins": {"Literacy": ["English", "Writing"], "Other": ["Math"]},
    }
}


def test_a_group_bin_filters_cube_and_the_extract_by_its_members(tmp_path):
    c = _checks(tmp_path, filters={"Subject Group": {"cube": "demo.subject"}})
    lists = cv.Lists({}, GROUPS)
    entry = {"state": {"dashboard": "Overview", "filters": {"Subject Group": "Literacy"}}}
    assert cv.state_filters(entry, c, lists=lists)[0] == [
        {"member": "demo.subject", "operator": "equals", "values": ["English", "Writing"]}
    ]
    fields = {"Subject Group": {"field": "Subject (group) (copy)", "datasource": DS}}
    sheet = c["sheets"]["Overview - Table"]
    assert cv.state_where(entry, c, fields, sheet, lists=lists) == [
        "cast(subject as string) in ('English', 'Writing')"
    ]
    every = {"state": {"dashboard": "Overview", "filters": {"Subject Group": cv.ALL}}}
    assert cv.state_filters(every, c, lists=lists)[0][0]["values"] == [
        "English",
        "Writing",
        "Math",
    ]


def test_a_saved_default_bin_expands_too(tmp_path):
    c = _checks(tmp_path, filters={"Subject Group": {"cube": "demo.subject"}})
    plain = {"state": {"dashboard": "Overview"}}
    out = cv.state_filters(plain, c, {"Subject Group": ["Literacy"]}, cv.Lists({}, GROUPS))
    assert out[0][0]["values"] == ["English", "Writing"]


def test_a_group_lookup_translates_each_member(tmp_path):
    c = _checks(
        tmp_path,
        filters={"Level": {"cube": "demo.abbreviation", "values": {"1": "A", "2": "B"}}},
    )
    lists = cv.Lists(
        {}, {"Level": {"datasource": DS, "field": "schoolid", "bins": {"ES": ["1", "2"]}}}
    )
    entry = {"state": {"dashboard": "Overview", "filters": {"Level": "ES"}}}
    assert cv.state_filters(entry, c, lists=lists)[0][0]["values"] == ["A", "B"]
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k group 2>&1 | tail -n 30`
Expected: FAIL, the bin name reaches Cube unexpanded.

- [ ] **Step 3: Implement**

Replace `Lists.expand` and add `Lists.column`:

```python
    def expand(self, caption: str, value):
        """A filter value as the stored values it stands for: a group's bins become
        their members. None: an (All) the snapshot has no list for."""
        g = self.groups.get(caption)
        if g is not None:
            bins = g["bins"]
            if value == ALL:
                return [v for members in bins.values() for v in members]
            names = value if isinstance(value, list) else [value]
            return [v for n in names for v in bins.get(n, [])]
        if value == ALL:
            found = self.all_values.get(caption)
            return None if found is None else list(found)
        return value

    def column(self, caption: str) -> str | None:
        """A group caption's underlying extract column."""
        g = self.groups.get(caption)
        return g["field"] if g is not None else None
```

In `state_where`, after `lists = lists or Lists()` (add that line at the top if
absent), change the column lookup to
`f = lists.column(caption) or (fields.get(caption) or {}).get("field") or dims_sql.get(caption)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "fix(cube): a group caption filters Cube and the extract by its bin's members"
```

### Task 6: privacy guard for name columns and keyed labels (B4)

**Files:**

- Modify: `scripts/cube_validate.py` (`load_checks`, `tableau_key`,
  `masked_key`, `_own_filters`, `state_filters`, `state_where`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `PERSON_WORDS: tuple[str, ...]` (same words as the snapshot script's
    `PERSON_FIELD`) and `PERSON_SQL` (a regex searching SQL for them)
  - `_key_text(dim: Dim, value: str) -> str | None` (the key inside a label;
    None when the pattern misses; the value itself when the dimension has no
    key)
  - `_keyed_dims(checks: dict) -> dict[str, Dim]`
  - `_own_filters(entry, defaults, lists=None, keyed=None)`: click values on a
    keyed caption become their key

- [ ] **Step 1: Write the failing tests**

Add a loader for the snapshot script near the top of the test file, after
`cv = _load()`:

```python
def _load_snapshot():
    path = Path(__file__).parents[2] / "scripts" / "cube_validate_snapshot.py"
    spec = importlib.util.spec_from_file_location("cube_validate_snapshot", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cube_validate_snapshot"] = mod
    spec.loader.exec_module(mod)
    return mod
```

Tests:

```python
SECTION = {
    "cube": "demo.identifier",
    "sql": "section_number",
    "key": r"^G\d+ - .* - (\S+)$",
}


def _with_section(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["dims"]["Section Number"] = dict(SECTION)
    return cv.load_checks(_write(tmp_path, d))


def test_both_scripts_agree_on_the_name_columns():
    snap = _load_snapshot()
    assert snap.PERSON_FIELD.pattern == "(" + "|".join(cv.PERSON_WORDS) + ")$"


def test_a_dimension_or_filter_reading_a_name_column_must_say_who_it_names(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["dims"]["Teacher"] = {
        "cube": None,
        "sql": "teacher_name",
    }
    with pytest.raises(cv.CheckError, match="name column"):
        cv.load_checks(_write(tmp_path, d))
    d["sheets"]["Overview - Table"]["dims"]["Teacher"]["person"] = "a teacher"
    cv.load_checks(_write(tmp_path, d))
    d["filters"]["Teacher"] = {"cube": None, "sql": "teacher_name"}
    with pytest.raises(cv.CheckError, match="name column"):
        cv.load_checks(_write(tmp_path, d))


def test_a_keyed_dimension_shows_only_its_key(tmp_path):
    c = _with_section(tmp_path)
    cell = cv.Cell(
        "Overview - Table",
        "s",
        {"Section Number": "G5 - Teacher, A - 501"},
        "Avg Score",
        "48.50",
        48.5,
        47.0,
        40,
        "mismatch",
        verdict="fail",
    )
    assert cv.masked_key(cell, c) == {"Section Number": "501"}
    text = cv.digest_markdown("Demo", [cell], c)
    assert "Teacher, A" not in text and "501" in text
    odd = cv.Cell(
        "Overview - Table", "s", {"Section Number": "Teacher, A"}, "Avg Score",
        "1", 1, 2, 40, "mismatch", verdict="fail",
    )
    assert cv.masked_key(odd, c) == {
        "Section Number": "a label the key pattern does not match"
    }


def test_a_clicked_label_filters_by_its_key_and_never_reaches_a_draft(tmp_path):
    c = _with_section(tmp_path)
    c["mismatches"]["dup"] = {
        "title": "fix(cube): x", "what": "y", "fix": "cube", "labels": [],
        "related": [], "where": "tableau",
    }
    entry = {
        "state": {"dashboard": "Overview"},
        "click_filters": {"Section Number": "G5 - Teacher, A - 501"},
    }
    assert cv.state_filters(entry, c)[0] == [
        {"member": "demo.identifier", "operator": "equals", "values": ["501"]}
    ]
    cell = cv.Cell(
        "Overview - Table", "s", {}, "Avg Score", "48.50", 48.5, 47.0, 40,
        "mismatch", verdict="fix_cube", explained_by=["dup"],
    )
    states = {"s": {**entry, "status": "ok", "sheets": {}}}
    body = cv.issue_drafts("Demo", [cell], c, states, {})["dup"]
    assert "Teacher, A" not in body and "'501'" in body
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider 2>&1 | tail -n 30`
Expected: FAIL, no attribute `PERSON_WORDS`; the label reaches the digest.

- [ ] **Step 3: Implement**

After `FIX_SIDES`, add:

```python
# Name columns. Same words as cube_validate_snapshot.PERSON_FIELD: a dimension or
# filter reading one must say who it names (person:), so outputs show a label.
PERSON_WORDS = ("lastfirst", "student_name", "first_name", "last_name", "teacher_name")
PERSON_SQL = re.compile(rf"\b({'|'.join(PERSON_WORDS)})\b")
```

In `load_checks`, after `sheets` are built, add:

```python
    for name, s in raw["sheets"].items():
        for c, d in (s.get("dims") or {}).items():
            if PERSON_SQL.search(d.get("sql") or "") and not d.get("person"):
                raise CheckError(
                    f"{name} / {c}: its sql reads a name column; add person: "
                    "(true for a student, or a label such as 'a teacher')"
                )
    for c, f in (raw.get("filters") or {}).items():
        if PERSON_SQL.search(f.get("sql") or "") and not f.get("person"):
            raise CheckError(f"filter {c}: its sql reads a name column; add person:")
```

Add before `tableau_key`:

```python
def _key_text(dim: Dim, value: str) -> str | None:
    """The join key inside a displayed label (Tableau shows a section as
    "G5 - <teacher> - 501"; the key is 501). None when the pattern misses."""
    if not dim.key:
        return value
    m = re.search(dim.key, value)
    if not m:
        return None
    return m.group(1) if m.groups() else m.group(0)


def _keyed_dims(checks: dict) -> dict[str, Dim]:
    return {c: d for s in checks["sheets"].values() for c, d in s.dims.items() if d.key}
```

Replace `tableau_key`:

```python
def tableau_key(sheet: SheetMap, caption: str, value) -> str:
    """The join key in a value Tableau shows: the dimension's key pattern, if any,
    then its alias lookup."""
    dim = sheet.dims.get(caption)
    if dim is not None and isinstance(value, str):
        found = _key_text(dim, value)
        value = value if found is None else found
        if dim.values:
            value = dim.values.get(value.strip(), value)
    return norm_dim(value)
```

Replace `masked_key`:

```python
UNKEYED = "a label the key pattern does not match"


def masked_key(c: Cell, checks: dict) -> dict[str, str]:
    """A cell's key as outputs may show it: a person as their label, a keyed
    label as its key only."""
    sheet = checks["sheets"].get(c.sheet)
    dims = sheet.dims if sheet else {}
    out = {}
    for d, v in c.key.items():
        dim = dims.get(d)
        if dim is not None and dim.person:
            out[d] = dim.person if isinstance(dim.person, str) else "a student"
        elif dim is not None and dim.key and v != TOTAL:
            out[d] = _key_text(dim, v) or UNKEYED
        else:
            out[d] = v
    return out
```

In `_own_filters`, add the parameter `keyed: dict[str, Dim] | None = None` and
build `clicks` as:

```python
    keyed = keyed or {}

    def click_value(c, v):
        if c in keyed:
            v = _key_text(keyed[c], v) or v
        return norm_dim(v)

    clicks = {c: click_value(c, v) for c, v in (entry.get("click_filters") or {}).items()}
```

In `state_filters` and `state_where`, call
`_own_filters(entry, defaults, lists, _keyed_dims(checks))`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "fix(cube): keyed labels show their key only, and name columns need person"
```

### Task 7: no deletes; `close` is read-only (B5)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`Session.sweep`, `Session.close`,
  `STALE_COPY`, `_open`, `_close`)
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces:
  - `Session.review_copies(workbook: str) -> list` (this tool's copies of the
    workbook in the review project, by exact name format)
  - `open_guard(session: Session, workbook: str) -> None` (raises `SessionError`
    naming each copy and its URL)
  - `close` returns 1 and leaves the manifest open while the copy is still
    there; 0 and `closed: true` once it is gone.
- Removes: `Session.sweep`, `Session.close`, `STALE_COPY`.

- [ ] **Step 1: Write the failing tests**

Add `import contextlib` to the test file's imports. Replace
`test_sweep_deletes_only_old_review_copies`,
`test_close_confirms_the_copy_is_gone` and
`test_close_raises_with_the_luid_when_the_copy_survives` with:

```python
def _copies():
    def wb(id_, name):
        return SimpleNamespace(
            id=id_, name=name, project_id=snap.TEMP_CB, created_at=None,
            webpage_url=f"https://tableau.example/#/workbooks/{id_}",
        )

    return [
        wb("a", "ZZ-REVIEW 2026-10-07 0800 DDI Suite"),
        wb("b", "ZZ-REVIEW 2026-10-09 1100 DDI Suite"),
        wb("c", "My Draft"),
        # Other work uses the prefix too, and this tool copies other workbooks.
        wb("d", "ZZ-REVIEW 2026-09-09 Survey Dashboard dept gate"),
        wb("e", "ZZ-REVIEW 2026-10-07 0800 Attendance Dashboard"),
    ]


def test_the_tool_never_deletes_anything_on_tableau():
    assert ".delete(" not in _SCRIPT.read_text()


def test_review_copies_lists_only_this_tools_copies_of_the_workbook(monkeypatch):
    s, _ = _session(monkeypatch, _copies())
    assert [w.id for w in s.review_copies("DDI Suite")] == ["a", "b"]


def test_open_refuses_while_a_review_copy_of_the_workbook_remains(monkeypatch):
    s, _ = _session(monkeypatch, _copies())
    with pytest.raises(snap.SessionError, match="ZZ-REVIEW 2026-10-07 0800 DDI Suite"):
        snap.open_guard(s, "DDI Suite")
    clear, _ = _session(monkeypatch, [])
    snap.open_guard(clear, "DDI Suite")


def test_close_waits_until_the_analyst_deletes_the_copy(monkeypatch, tmp_path):
    snap.write_manifest(tmp_path / "manifest.json", _manifest())  # copy-1
    left = [
        SimpleNamespace(
            id="copy-1", name="ZZ-REVIEW 2026-10-09 1200 Demo",
            project_id=snap.TEMP_CB, webpage_url="https://tableau.example/#/1",
        )
    ]
    auth = SimpleNamespace(sign_in=lambda a: contextlib.nullcontext())
    monkeypatch.setattr(snap, "_server", lambda: (SimpleNamespace(auth=auth), "pat"))
    monkeypatch.setattr(snap, "_workbooks_in", lambda server, project: list(left))
    monkeypatch.setattr(snap, "latest_snapshot", lambda workbook: tmp_path)
    checks = tmp_path / "checks.yml"
    checks.write_text(f"workbook: Demo\nreview_project_luid: {snap.TEMP_CB}\n")
    assert snap.main(["close", str(checks)]) == 1
    assert snap.read_manifest(tmp_path / "manifest.json").closed is False
    left.clear()
    assert snap.main(["close", str(checks)]) == 0
    assert snap.read_manifest(tmp_path / "manifest.json").closed is True
```

- [ ] **Step 2: Run them to verify they fail**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py -q -p no:cacheprovider 2>&1 | tail -n 30`
Expected: FAIL, `.delete(` found in the script, no attribute `review_copies`.

- [ ] **Step 3: Implement**

Delete `STALE_COPY`, `Session.sweep` and `Session.close`. Add to `Session`:

```python
    def review_copies(self, workbook: str) -> list:
        """This tool's review copies of the workbook still in the review project.
        Matched by the exact name publish gives them; other ZZ-REVIEW copies are
        other work's."""
        mine = re.compile(
            rf"^{re.escape(REVIEW_PREFIX)}\d{{4}}-\d{{2}}-\d{{2}} \d{{4}} {re.escape(workbook)}$"
        )
        return [w for w in _workbooks_in(self.server, self.project) if mine.match(w.name or "")]
```

After the `Session` class, add:

```python
def open_guard(session: Session, workbook: str) -> None:
    """Refuse to publish while an earlier review copy is still in the project. The
    tool deletes nothing on Tableau; the analyst deletes each copy by hand."""
    left = session.review_copies(workbook)
    if left:
        listed = "\n".join(f"  {w.name}: {w.webpage_url}" for w in left)
        raise SessionError(
            "delete these review copies in Tableau first (project TEMP-CB), "
            f"then run close and open again:\n{listed}"
        )
```

In `_open`, replace
`print("swept:", session.sweep(checks["workbook"]) or "nothing")` with
`open_guard(session, checks["workbook"])`.

Replace `_close`:

```python
def _close(a) -> int:
    """Read-only: the session closes once the analyst has deleted the copy."""
    checks = _load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    m = read_manifest(snapdir / "manifest.json")
    if not m.copy_luid:
        raise SessionError("this snapshot has no review copy; open a new session")
    server, auth = _server()
    with server.auth.sign_in(auth):
        session = Session(server, checks["review_project_luid"])
        left = [w for w in session.review_copies(checks["workbook"]) if w.id == m.copy_luid]
    if left:
        print(
            "delete the review copy in Tableau, then run close again:\n"
            f"  {left[0].name}: {left[0].webpage_url}"
        )
        return 1
    m.closed = True
    write_manifest(snapdir / "manifest.json", m)
    for p in (snapdir / "live.twbx", snapdir / "review.twbx"):
        p.unlink(missing_ok=True)
    print(f"closed: review copy {m.copy_luid} is gone")
    return 0
```

Update the module docstring's `close` line to
`close <checks.yml>   (read-only: closes once the copy is deleted by hand)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass. `FakeWorkbooks.delete` stays in the test
fake; the script never calls it.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "fix(cube): the tool deletes nothing on Tableau; close waits for a manual delete"
```

---

## Part B: planning and the session

These ride right after the blockers: they share the snapshot script and each is
small.

### Task 8: export only listed sheets, and expose only those (I7)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`review_copy`,
  `build_review_twbx`, `export_state`, `_export_all`, `_open`, `_plan`)
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces:
  - `listed_sheets(checks: dict) -> set[str]` (raises `SessionError` when
    `sheets:` is empty)
  - `review_copy(twb_text, dashboards, sheets: set[str] | None = None) -> str`
  - `build_review_twbx(live_twbx, out_dir, dashboards, listed: set[str] | None = None)`
  - `export_state(..., judged=None, listed: set[str] | None = None) -> dict`
  - `plan.yml` gains `sheets: {dashboard: [sheet, ...]}` for the analyst to list
    from.

- [ ] **Step 1: Write the failing tests**

```python
def test_review_copy_exposes_only_the_listed_sheets():
    out = snap.review_copy(TWB, ["Overview"], sheets={"Overview - Detail"})
    assert "<window class='worksheet' name='Overview - Detail' />" in out
    assert "<window class='worksheet' hidden='true' name='Overview - Table' />" in out


def test_a_state_exports_only_listed_sheets(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    s = FakeSession(lambda sheet, f: b"Region,N\r\nAll,9\r\n")
    entry = snap.export_state(
        s, _manifest(), tmp_path, wb, snap.State("Overview"), {}, NEVER, {},
        listed={"Overview - Detail"},
    )
    assert list(entry["sheets"]) == ["Overview - Detail"]


def test_a_click_exports_its_source_even_when_unlisted(tmp_path):
    (tmp_path / "csv").mkdir()
    wb = snap.read_workbook(TWB)
    s = FakeSession(lambda sheet, f: b"Title,Score\r\nT1,80\r\nT2,20\r\n")
    state = snap.State("Overview", click=("Table to Detail", "largest"))
    entry = snap.export_state(
        s, _manifest(), tmp_path, wb, state, {}, NEVER,
        {"Overview - Table": ["Title"]}, listed={"Overview - Detail"},
    )
    assert s.calls[0][0] == "Overview - Table"  # the click's source
    assert list(entry["sheets"]) == ["Overview - Detail"]


def test_open_needs_the_sheets_to_export_listed():
    with pytest.raises(snap.SessionError, match="sheets:"):
        snap.listed_sheets({})
    assert snap.listed_sheets({"sheets": {"A": {"datasource": "d"}}}) == {"A"}
```

- [ ] **Step 2: Run them to verify they fail**

Run the snapshot test file. Expected: FAIL, unexpected keyword `sheets` /
`listed`.

- [ ] **Step 3: Implement**

Add before `review_copy`:

```python
def listed_sheets(checks: dict) -> set[str]:
    """The sheets a session exports and exposes: those under `sheets:` (a stub
    entry is enough before mapping). Others, the student-level ones above all,
    stay hidden on the review copy and are never exported."""
    listed = set(checks.get("sheets") or {})
    if not listed:
        raise SessionError(
            "list the sheets to export under sheets: in the checks file; "
            "plan.yml lists each dashboard's sheets"
        )
    return listed
```

In `review_copy`, add the parameter `sheets: set[str] | None = None` and change
`sheets = [s for d in dashboards for s in wb.dashboards[d]]` to:

```python
    exposed = [
        s for d in dashboards for s in wb.dashboards[d] if sheets is None or s in sheets
    ]
```

then use `exposed` in place of `sheets` for `_expose`, the `still hidden` check
and the `other windows changed` check (rename the local only; the click-filter
stripping is unchanged).

In `build_review_twbx`, add the parameter `listed: set[str] | None = None`, read
the workbook from `base` before building the copy, and expose the listed sheets
plus each click action's source sheet:

```python
    wb0 = read_workbook(base)
    sheets = None
    if listed is not None:
        sheets = set(listed) | {
            a.source_sheet
            for a in wb0.actions
            if a.kind == "filter" and a.dashboard in dashboards
        }
    review = review_copy(base, dashboards, sheets)
```

and compute `keep` as
`set(dashboards) | {s for d in dashboards for s in wb.dashboards[d] if sheets is None or s in sheets}`.

In `export_state`, add the parameter `listed: set[str] | None = None` after
`judged`, and select sheets as:

```python
    def wanted(s: str) -> bool:
        return listed is None or s in listed

    sheets = [s for s in wb.dashboards[state.dashboard] if wanted(s)]
```

and, in the click branch,
`sheets = [s for s in wb.dashboards[action.target] if s not in action.exclude and wanted(s)]`.

In `_export_all`, compute `listed = listed_sheets(checks)` at the top and pass
`listed=listed` to `export_state`. In `_open`, compute
`listed = listed_sheets(checks)` before downloading, and pass it to
`build_review_twbx(live, snapdir, checks["dashboards"], listed)`.

In `_plan`, add to `doc`, first key:
`"sheets": {d: list(s) for d, s in wb.dashboards.items()},`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass. The Task 3 export test already passes a
`sheets:` entry.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): export and expose only the sheets the checks file lists"
```

### Task 9: export order: default view, roots, parameters, clicks, cross-cuts (I8)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`_export_all`)
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces:
  - `root_captions(checks: dict, fields: dict) -> set[str]`
  - `export_rank(state: State, roots: set[str]) -> tuple`

- [ ] **Step 1: Write the failing test**

```python
def test_export_order_puts_tree_roots_before_cross_cuts():
    fields = {
        "Region": {"field": "region", "datasource": DS},
        "IEP": {"field": "iep_status", "datasource": DS},
    }
    checks = {"trees": {DS: {"region": ["region", "school"]}}}
    roots = snap.root_captions(checks, fields)
    assert roots == {"Region"}
    states = [
        snap.State("Overview", filters=(("IEP", "No IEP"),)),
        snap.State("Overview", click=("Table to Detail", "largest")),
        snap.State("Overview", filters=(("Region", "North"), ("School Name", "A"))),
        snap.State("Overview", params=(("Group By", "Teacher"),)),
        snap.State("Overview", filters=(("Region", "North"),)),
        snap.State("Overview"),
    ]
    ordered = sorted(states, key=lambda s: snap.export_rank(s, roots))
    assert [s.id for s in ordered] == [
        "overview--default",
        "overview--region-north",
        "overview--group-by-teacher",
        "overview--click-table-to-detail-largest",
        "overview--iep-no-iep",
        "overview--region-north--school-name-a",
    ]
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate_snapshot.py::test_export_order_puts_tree_roots_before_cross_cuts -q -p no:cacheprovider 2>&1 | tail -n 30`
Expected: FAIL, no attribute `root_captions`.

- [ ] **Step 3: Implement**

Add before `_export_all`:

```python
def root_captions(checks: dict, fields: dict) -> set[str]:
    """Captions whose field tops a tree in the checks file."""
    firsts = {
        (ds, levels[0])
        for ds, t in (checks.get("trees") or {}).items()
        for levels in (t or {}).values()
        if levels
    }
    return {c for c, f in fields.items() if (f["datasource"], f["field"]) in firsts}


def export_rank(state: State, roots: set[str]) -> tuple:
    """Default view, tree roots, parameters, clicks, then cross-cuts; descent
    states after their parents. A session cut short still reaches the roots."""
    if state.click:
        kind = 3
    elif not state.filters:
        kind = 2 if state.params else 0
    elif len(state.filters) == 1:
        kind = 1 if state.filters[0][0] in roots else 4
    else:
        kind = 5
    return (kind, len(state.filters), state.id)
```

In `_export_all`, compute `roots = root_captions(checks, m.fields)` and sort
with `key=lambda s: export_rank(s, roots)`. Replace the sort's comment with
`# Parents first, roots before cross-cuts (export_rank).`

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): export the default view and tree roots before cross-cuts"
```

### Task 10: cross-cuts and blanks are sampled; `--resume` skips ignored states (M5, M1, M2)

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`plan_states`, `pending`,
  `_open`, `main`)
- Test: `tests/scripts/test_cube_validate_snapshot.py`

**Interfaces:**

- Produces:
  - `plan_states`: a cross-cut's largest value is `must`, its other values
    `optional`; every blank-value state is `optional`.
  - `pending(states, manifest, retry_ignored: bool = False) -> list[State]`
  - `open --resume --retry-ignored`

- [ ] **Step 1: Write the failing tests**

```python
def test_a_cross_cut_exports_its_largest_value_and_keeps_the_rest_optional():
    items = _plan()
    assert "overview--iep-status-no-iep" in _ids(items, "must")  # 72 students
    assert "overview--iep-status-has-iep" in _ids(items, "optional")


def test_blank_states_wait_for_the_live_check():
    assert "overview--iep-status-blank" in _ids(_plan(), "optional")


def test_resume_reexports_missing_and_failed_states_only():
    m = _manifest()
    done, ignored, failed = (
        snap.State("Overview", filters=(("Region", v),))
        for v in ("North", "South", "East")
    )
    m.states = {
        done.id: {"status": "ok"},
        ignored.id: {"status": "filter_ignored"},
        failed.id: {"status": "export_failed"},
    }
    new = snap.State("Overview")
    assert snap.pending([done, ignored, failed, new], m) == [failed, new]
    assert snap.pending([done, ignored, failed, new], m, retry_ignored=True) == [
        ignored,
        failed,
        new,
    ]
```

Delete `test_a_resumed_session_exports_only_what_is_missing_or_not_ok` (the new
test replaces it). In
`test_must_includes_default_params_tree_top_crosscuts_years_and_clicks`, replace
the 2 lines asserting `iep-status-has-iep` and `iep-status-blank` are must with
`assert "overview--iep-status-no-iep" in must`. In
`test_a_cross_cut_with_many_values_is_sampled_not_split`, replace the last
assertion with `assert "overview--iep-status-no-iep" in _ids(items, "must")`.

- [ ] **Step 2: Run them to verify they fail**

Run the snapshot test file. Expected: FAIL, `has-iep` is must; `pending` takes
no `retry_ignored`.

- [ ] **Step 3: Implement**

In `plan_states`, change the blank-value line to:

```python
            if any(v is None for v, _ in prof):
                add(
                    "optional",
                    "blank value; must once the live check confirms vf Null filters",
                    filters=one(BLANK),
                )
```

and the plain cross-cut branch (`elif c.field in t.cross_cuts:`) to:

```python
            elif c.field in t.cross_cuts:
                # The profile lists values largest first.
                for i, v in enumerate(named):
                    if i == 0:
                        add("must", "cross-cut, largest value", filters=one(v))
                    else:
                        add(
                            "optional",
                            "cross-cut; compare proposes it when the largest value mismatches",
                            filters=one(v),
                        )
```

Replace `pending`:

```python
def pending(
    states: list[State], manifest: Manifest, retry_ignored: bool = False
) -> list[State]:
    """States a resumed session still has to export: missing or failed ones, and
    ignored ones only on request (their caption is wrong until it is fixed)."""
    redo = {"export_failed"} | ({"filter_ignored"} if retry_ignored else set())
    return [
        st
        for st in states
        if (e := manifest.states.get(st.id)) is None or e.get("status") in redo
    ]
```

In `main`, for `open`, add
`s.add_argument("--retry-ignored", action="store_true", help="with --resume, export filter_ignored states again")`.
In `_open`, call
`pending(_states_for(checks, a.states), resume, a.retry_ignored)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate_snapshot.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): sample cross-cuts and blanks; resume skips ignored states"
```

---

## Part C: compare and explain

### Task 11: ask Cube by both routes; a disagreement is a Cube mismatch (I11, gap 13)

**Files:**

- Modify: `scripts/cube_validate.py` (`Cell`, `load_checks`, `compare_export`,
  `_cube_values`, `_cube_at`, `_explain_batch`, `explain_cells`,
  `coverage_markdown`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `ROUTES = "cube-routes-disagree"` and `ROUTES_MISMATCH` (title, what,
    `fix: cube`); `load_checks` merges the checks file's own entry for the slug
    over it, so `issue:` can be attached.
  - `Cell.cube_alone: float | None = None`, `Cell.rollups_alone: list[str]`,
    `Cell.routes: bool = False`
  - `Answer(fact: dict, alone: dict, students: dict, rollups: list[str], rollups_alone: list[str])`,
    raw values keyed by grain key (table calculations are applied by the caller)
  - `cube_query(sheet, grain, measures, filters) -> dict`
  - `_by_key(rows, sheet, grain) -> dict[tuple, dict]`
  - `_ask_cube(sheet, grain, measures, load, filters, student) -> dict[str, Answer]`
  - `_compare_grain(sheet, state_id, grain, totals, rows, dims, measures, load, filters, student) -> list[Cell]`
  - `routes_agree(fact, alone, shown) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
def _two_routes(fact, alone):
    def load(q):
        is_alone = "demo.count_students" not in q["measures"]
        if not q["dimensions"]:
            return [], []
        row = {
            "demo.school": "Alpha",
            "demo.avg_score": str(alone if is_alone else fact),
            "demo.count_students": "20",
            "demo.pct_complete": "0.8",
        }
        return [row], (["rollup"] if is_alone else [])

    return load


def test_cubes_two_routes_are_both_asked_and_a_split_is_a_mismatch(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,48.50\r\n")
    cells = cv.compare_export(sheet, "s1", export, _two_routes(48.5, 47.0), [], [], c)
    (alpha,) = cells
    assert (alpha.status, alpha.routes) == ("mismatch", True)
    assert (alpha.cube, alpha.cube_alone, alpha.rollups_alone) == (48.5, 47.0, ["rollup"])
    assert "alone 47" in alpha.reason


def test_routes_that_agree_at_the_shown_precision_are_fine(tmp_path):
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,48.50\r\n")
    cells = cv.compare_export(sheet, "s1", export, _two_routes(48.5, 48.501), [], [], c)
    assert [(x.status, x.routes) for x in cells] == [("match", False)]


def test_explain_blames_cube_for_a_route_split(tmp_path):
    c = _checks(tmp_path)
    states = {"s": {"state": {"dashboard": "Overview"}, "status": "ok", "sheets": {}}}
    cell = cv.Cell(
        "Overview - Table", "s", {}, "Avg Score", "48.50", 48.5, 48.5, 40,
        "mismatch", cube_alone=47.0, routes=True,
    )
    cv.explain_cells([cell], c, states, {}, lambda ds, sql: [{"m": 48.5}], lambda q: ([], []))
    assert (cell.verdict, cell.explained_by) == ("fix_cube", [cv.ROUTES])


def test_the_route_mismatch_is_built_in_and_takes_an_issue(tmp_path):
    c = _checks(tmp_path, mismatches={cv.ROUTES: {"issue": 5883}})
    m = c["mismatches"][cv.ROUTES]
    assert (m["fix"], m["issue"]) == ("cube", 5883) and m["title"].startswith("fix(cube)")


def test_coverage_counts_queries_by_cube_route():
    states = {s: {"state": {"dashboard": "D"}, "status": "ok"} for s in ("a", "b")}

    def cell(state, school):
        return cv.Cell(
            "S", state, {"School": school}, "M", "1", 1, 1, 20, "match",
            rollups=[], rollups_alone=["r1"],
        )

    text = cv.coverage_markdown(states, [cell("a", "x"), cell("a", "y"), cell("b", "x")])
    assert "- raw / r1: 2" in text
```

In `test_compare_matches_rows_and_totals`, replace the queries assertion with
`assert len(cube.queries) == 4 and cube.queries[2]["dimensions"] == []` (each
grain now asks twice: with the student count, then alone).

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, unexpected keyword `cube_alone`, no
attribute `ROUTES`.

- [ ] **Step 3: Implement**

Add to `Cell`, after `why`:

```python
    cube_alone: float | None = None  # Cube's value when the measure is asked alone
    rollups_alone: list[str] = field(default_factory=list)
    routes: bool = False  # Cube's two routes disagree at the shown precision
```

After `fix_sides`, add:

```python
ROUTES = "cube-routes-disagree"
ROUTES_MISMATCH = {
    "title": "fix(cube): a rollup and the fact table answer the same query differently",
    "what": (
        "Cube gives one number when the measure is asked alone, as people ask "
        "(often served by a rollup), and another when the student count is asked "
        "with it (read from the fact table)."
    ),
    "fix": "cube",
}
```

In `load_checks`, right after `mismatches = raw.get("mismatches") or {}`, add:

```python
    # Built in: the checks file may add issue:, labels: or related: to it.
    mismatches[ROUTES] = {**ROUTES_MISMATCH, **(mismatches.get(ROUTES) or {})}
```

Add before `compare_export`:

```python
@dataclass
class Answer:
    """Cube's raw values for one measure at one grain, by both routes."""

    fact: dict[tuple, float | None]  # asked with the student count
    alone: dict[tuple, float | None]  # the measure alone, as people ask
    students: dict[tuple, int | None]
    rollups: list[str]
    rollups_alone: list[str]


def cube_query(sheet, grain, measures, filters) -> dict:
    return {
        "measures": sorted({m for m in measures if m}),
        "dimensions": [sheet.dims[d].cube for d in grain],
        "filters": filters,
        "limit": CUBE_LIMIT,
    }


def _by_key(rows, sheet, grain) -> dict[tuple, dict]:
    return {tuple(norm_dim(r.get(sheet.dims[d].cube)) for d in grain): r for r in rows}


def _ask_cube(sheet, grain, measures, load, filters, student) -> dict[str, Answer]:
    """Each measure's raw values at the grain by both of Cube's routes: with the
    student count (read from the fact) and alone (often served by a rollup)."""
    if not measures:
        return {}
    members = [sheet.measures[m].cube for m in measures]
    rows, rollups = load(cube_query(sheet, grain, [*members, student], filters))
    alone_rows, rollups_alone = load(cube_query(sheet, grain, members, filters))
    fact, alone = _by_key(rows, sheet, grain), _by_key(alone_rows, sheet, grain)
    return {
        m: Answer(
            {k: _num(r.get(sheet.measures[m].cube)) for k, r in fact.items()},
            {k: _num(r.get(sheet.measures[m].cube)) for k, r in alone.items()},
            {k: _int(r.get(student)) for k, r in fact.items()},
            list(rollups),
            list(rollups_alone),
        )
        for m in measures
    }


def routes_agree(fact, alone, shown: Shown | None) -> bool:
    """Whether Cube's two routes give the same number at the precision Tableau shows."""
    if fact is None or alone is None:
        return (fact or 0.0) == (alone or 0.0)
    if shown is None or shown.decimals is None:
        return matches_raw(fact, alone)
    return round(fact, shown.decimals) == round(alone, shown.decimals)
```

Replace `compare_export` with:

```python
def compare_export(
    sheet, state_id, export, load, filters, missing, checks
) -> list[Cell]:
    cols = export.columns
    # No header at all: compare at every mapped dimension Cube has, so its rows still show.
    dims = (
        [c for c in cols if c in sheet.dims]
        if cols
        else [d for d in sheet.dims if sheet.dims[d].cube]
    )
    measures = (
        [c for c in cols if c in sheet.measures] if cols else list(sheet.measures)
    )
    cells = [
        Cell(sheet.name, state_id, {}, c, None, None, None, None, "not_comparable",
             "unmapped column")
        for c in cols
        if c not in sheet.dims and c not in sheet.measures
    ]
    if missing:
        # Cube cannot express a filter the dashboard applies: a missing member.
        reason = f"filter {', '.join(missing)} has no Cube member"
        return cells + [
            Cell(sheet.name, state_id, {}, m, None, None, None, None, "missing_member",
                 reason)
            for m in measures
        ]
    # A dimension showing "*" is an attribute (ATTR) of a coarser mark, never part
    # of the mark's grain: leave it out, and compare at the remaining dimensions.
    attrs = [d for d in dims if any(r.get(d) == MULTI for r in export.rows)]
    dims = [d for d in dims if d not in attrs]
    groups: dict[tuple[str, ...], list[dict]] = {}
    for r in export.rows:
        groups.setdefault(tuple(d for d in dims if r.get(d) == TOTAL), []).append(r)
    if not groups:
        groups[()] = []
    every = filters + hard_filters(checks, sheet.datasource)
    for totals, rows in groups.items():
        grain = [d for d in dims if d not in totals]
        cells += _compare_grain(
            sheet, state_id, grain, totals, rows, dims, measures, load, every,
            checks["student_count"],
        )
    return cells


def _compare_grain(
    sheet, state_id, grain, totals, rows, dims, measures, load, filters, student
) -> list[Cell]:
    """One grain's cells: each Tableau row against Cube, then Cube's extra slices."""

    def cell(key, m, status, reason="", shown=None, tableau=None, cube=None, n=None, **kw):
        return Cell(sheet.name, state_id, key, m, shown, tableau, cube, n, status,
                    reason, **kw)

    blocked = [d for d in grain if sheet.dims[d].cube is None]
    if blocked:
        reason = f"dimension {', '.join(blocked)} has no Cube member"
        return [
            cell({d: r.get(d, "") for d in dims}, m, "missing_member", reason,
                 shown=r.get(m))
            for r in rows
            for m in measures
        ]
    asked = [m for m in measures if sheet.measures[m].cube]
    raw = _ask_cube(sheet, grain, asked, load, filters, student)
    answers = {
        m: Answer(
            apply_calc(sheet.measures[m], a.fact, sheet.measures[m].scale),
            apply_calc(sheet.measures[m], a.alone, sheet.measures[m].scale),
            a.students, a.rollups, a.rollups_alone,
        )
        for m, a in raw.items()
    }
    fixed = {d: TOTAL for d in totals}
    out, seen = [], set()
    for r in rows:
        k = tuple(tableau_key(sheet, d, r.get(d)) for d in grain)
        key = {**{d: r.get(d, "") for d in grain}, **fixed}
        for m in measures:
            meas, text = sheet.measures[m], r.get(m)
            shown = parse_shown(text, meas.round)
            a = answers.get(m)
            if a is None:
                out.append(cell(key, m, "missing_member", "measure has no Cube member",
                                shown=text))
            elif shown is None and (text or "").strip():
                out.append(cell(key, m, "not_comparable", "value does not parse",
                                shown=text))
            elif k not in a.fact:
                out.append(cell(key, m, "mismatch",
                                "Tableau shows this slice; Cube does not", shown=text,
                                tableau=shown and shown.value, rollups=a.rollups,
                                rollups_alone=a.rollups_alone))
            else:
                seen.add(k)
                v, alone = a.fact.get(k), a.alone.get(k)
                split = not routes_agree(v, alone, shown)
                ok = not split and matches_shown(v, shown)
                reason = (
                    f"Cube's routes disagree: alone {_fmt(alone)}, with the student "
                    f"count {_fmt(v)}" if split else ""
                )
                out.append(cell(key, m, "match" if ok else "mismatch", reason,
                                shown=text, tableau=shown and shown.value, cube=v,
                                n=a.students.get(k), rollups=a.rollups,
                                rollups_alone=a.rollups_alone, cube_alone=alone,
                                routes=split))
    for k in sorted({k for a in answers.values() for k in a.fact} - seen):
        vals = {m: a.fact.get(k) for m, a in answers.items()}
        if all(v in (None, 0) for v in vals.values()):
            continue
        key = {**dict(zip(grain, k, strict=True)), **fixed}
        for m, v in vals.items():
            a = answers[m]
            out.append(cell(key, m, "mismatch", "Cube has this slice; Tableau does not",
                            cube=v, n=a.students.get(k), rollups=a.rollups,
                            rollups_alone=a.rollups_alone))
    return out
```

Replace `_cube_values` and `_cube_at`:

```python
def _cube_values(rows, sheet, meas, grain) -> dict:
    raw = {k: _num(r.get(meas.cube)) for k, r in _by_key(rows, sheet, grain).items()}
    return apply_calc(meas, raw, meas.scale)


def _cube_at(load, sheet, meas, grain, filters, student=None) -> dict:
    rows, _ = load(cube_query(sheet, grain, [meas.cube, student], filters))
    return _cube_values(rows, sheet, meas, grain)
```

In `_explain_batch`, replace the inline `q = {...}` with
`q = cube_query(sheet, grain, [meas.cube, checks["student_count"]], base)`.

In `explain_cells`, add a branch before `elif c.status == "mismatch":`:

```python
        elif c.status == "mismatch" and c.routes:
            c.explained_by = [ROUTES]
            c.verdict = cell_verdict(c, sides, sheet.measures[c.measure])
```

In `coverage_markdown`, before the final `return`, add:

```python
    routes = {
        (c.sheet, c.state, _grain(c)[0]): (
            ", ".join(c.rollups) or "raw",
            ", ".join(c.rollups_alone) or "raw",
        )
        for c in cells
        if c.status in ("match", "mismatch")
    }
    if routes:
        lines += [
            "",
            "Cube routes, by query (with the student count / alone):",
            *(f"- {w} / {a}: {n}" for (w, a), n in Counter(routes.values()).most_common()),
        ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): ask Cube by both routes and treat a split as a Cube mismatch"
```

### Task 12: a blank cell matches a Cube null or 0, everywhere (M6)

**Files:**

- Modify: `scripts/cube_validate.py` (`_compare_grain`, `_reproduces`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces: `matches_cell(value, text, round_to=None) -> bool`

- [ ] **Step 1: Write the failing test**

```python
def test_a_blank_cell_matches_a_cube_null_or_zero_in_compare_and_explain(tmp_path):
    assert cv.matches_cell(None, "") and cv.matches_cell(0.0, " ")
    assert not cv.matches_cell(0.5, "")
    assert cv.matches_cell(0.3624, "36.24%")
    c, sheet = _sheet(tmp_path)
    export = cv.read_export(b"School Name,Avg Score\r\nAlpha,\r\n")
    cells = cv.compare_export(
        sheet, "s1", export, FakeCube({"Alpha": _row(0)}, _row(0)), [], [], c
    )
    assert [x.status for x in cells] == ["match"]
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k blank_cell 2>&1 | tail -n 30`
Expected: FAIL, no attribute `matches_cell`.

- [ ] **Step 3: Implement**

After `matches_raw`, add:

```python
def matches_cell(value: float | None, text: str | None, round_to: int | None = None) -> bool:
    """A Cube or extract value against a Tableau cell. A blank cell matches a null
    or 0: Tableau leaves both empty."""
    if not (text or "").strip():
        return value in (None, 0.0)
    return matches_shown(value, parse_shown(text, round_to))
```

In `_compare_grain`, change `ok = not split and matches_shown(v, shown)` to
`ok = not split and matches_cell(v, text, meas.round)`. Replace the body of
`_reproduces` with `return matches_cell(value, c.shown, meas.round)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "fix(cube): a blank Tableau cell matches a null or 0 in compare and explain"
```

### Task 13: warn when an ignored saved filter would hide rows (M3, gap 5)

**Files:**

- Modify: `scripts/cube_validate.py` (`run_compare`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `ignored_filter_leaks(saved, entry, checks, fields, sheet, run_extract, defaults=None, lists=None) -> list[tuple[str, int]]`
    (caption, rows in the slice that fail it), for ignored saved filters the
    extract has a column for
  - `run_compare(checks, snapdir, load, extracts, redo=False, warn=print)`

- [ ] **Step 1: Write the failing test**

Add a helper for the snapshot folders the `run_compare` tests build, and use it
in this test:

```python
def _snapdir(tmp_path, csv=b"School Name,Avg Score\r\nAlpha,48.50\r\n", **manifest):
    snapdir = tmp_path / "snap"
    (snapdir / "csv").mkdir(parents=True)
    (snapdir / "csv" / "n.csv").write_bytes(csv)
    m = {
        "workbook": "Demo",
        "extracts": {},
        "fields": {},
        "states": {
            "n": {
                "state": {"id": "n", "dashboard": "Overview"},
                "status": "ok",
                "click_filters": {},
                "sheets": {"Overview - Table": {"file": "csv/n.csv", "rows": 1}},
            }
        },
        **manifest,
    }
    (snapdir / "manifest.json").write_text(json.dumps(m))
    return snapdir


def test_compare_warns_when_an_ignored_saved_filter_would_hide_rows(tmp_path):
    c = _checks(tmp_path, filters=SAVED_MAP, ignore_sheet_filters=["Pct Done", "Score"])
    snapdir = _snapdir(tmp_path, sheet_filters={"Overview - Table": SAVED})
    sqls, warned = [], []

    def extracts(ds, sql):
        sqls.append(sql)
        return [{"n": 3}]

    cube = FakeCube({"Alpha": _row(48.5)}, _row(0))
    cv.run_compare(c, snapdir, cube, extracts, warn=warned.append)
    assert warned == ["n / Overview - Table: 3 rows in this slice fail the ignored filter Score"]
    assert "not coalesce((score >= 0.75), false)" in sqls[0]
    # The FIXED-LOD filter has no extract column, so it is never counted.
    assert not any("Calculation_8" in s for s in sqls)
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k ignored_saved 2>&1 | tail -n 30`
Expected: FAIL, unexpected keyword `warn`.

- [ ] **Step 3: Implement**

Add before `run_compare`:

```python
def ignored_filter_leaks(
    saved, entry, checks, fields, sheet, run_extract, defaults=None, lists=None
) -> list[tuple[str, int]]:
    """Rows in the state's slice that an ignored saved filter would have hidden.
    ignore_sheet_filters is safe only while this is 0; a FIXED-LOD filter has no
    extract column, so the checks file links its issue instead."""
    ignored = set(checks["ignore_sheet_filters"])
    if not ignored:
        return []
    kept = [f for f in saved if f["caption"] not in ignored]
    where = state_where(entry, checks, fields, sheet, defaults=defaults, lists=lists)
    where += sheet_conditions(kept, entry, checks)[0]
    plain = {**checks, "ignore_sheet_filters": []}
    out = []
    for f in saved:
        if f["caption"] not in ignored or f.get("calculated"):
            continue
        cond = sheet_conditions([f], entry, plain)[0]
        if not cond:
            continue
        fails = f"not coalesce(({' and '.join(cond)}), false)"
        sql = (
            # trunk-ignore(bandit/B608): SQL over the dashboard's own extract; names come from the workbook
            f"select count(*) as n from `{EXTRACT_TABLE}` where "
            + " and ".join(f"({w})" for w in [*where, fails])
        )
        n = int(run_extract(sheet.datasource, sql)[0]["n"])
        if n:
            out.append((f["caption"], n))
    return out
```

In `run_compare`, add the parameter `warn: Callable[[str], None] = print`, and
replace the body of the `for sheet_name, meta in e["sheets"].items():` loop
after the unmapped-sheet branch with:

```python
            export = read_export((snapdir / meta["file"]).read_bytes())
            saved = (m.get("sheet_filters") or {}).get(sheet_name, [])
            kept = sheet_defaults(dflt, saved)
            try:
                _, sheet_cube, sheet_missing = sheet_conditions(saved, e, checks)
                filters, missing = state_filters(e, checks, kept, lists)
                cells += compare_export(
                    sheet, sid, export, load, filters + sheet_cube,
                    missing + sheet_missing, checks,
                )
            except CubeError as err:
                cells.append(
                    Cell(sheet_name, sid, {}, "", None, None, None, None,
                         "not_comparable", f"Cube error: {err}")
                )
            try:
                for cap, n in ignored_filter_leaks(
                    saved, e, checks, m["fields"], sheet, extracts, kept, lists
                ):
                    warn(f"{sid} / {sheet_name}: {n} rows in this slice fail the ignored filter {cap}")
            except Exception as err:  # noqa: BLE001 - the check only warns
                warn(f"{sid} / {sheet_name}: could not check the ignored saved filters: {err}")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass. Existing `run_compare` tests ignore only
the calculated `Pct Done`, so they make no count query.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): warn when an ignored saved filter would hide rows in a slice"
```

### Task 14: a calculated filter card carries its own SQL (I4, gap 7)

**Files:**

- Modify: `scripts/cube_validate.py` (`state_where`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces: `filters.<caption>.sql` (checks file) is preferred over the
  manifest's field in `state_where`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_calculated_filter_card_uses_its_own_sql(tmp_path):
    tutored = "case when tutoring_nj then 'Tutored' else 'Not Tutored' end"
    c = _checks(tmp_path, filters={"NJ Tutoring": {"cube": None, "sql": tutored}})
    fields = {"NJ Tutoring": {"field": "Calculation_1545649496779657216", "datasource": DS}}
    entry = {"state": {"dashboard": "Overview", "filters": {"NJ Tutoring": "Tutored"}}}
    assert cv.state_where(entry, c, fields, c["sheets"]["Overview - Table"]) == [
        f"cast({tutored} as string) = 'Tutored'"
    ]
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k calculated_filter_card 2>&1 | tail -n 30`
Expected: FAIL, the condition names `Calculation_1545649496779657216`.

- [ ] **Step 3: Implement**

In `state_where`, change the column lookup to:

```python
        f = (
            (checks["filters"].get(caption) or {}).get("sql")
            or lists.column(caption)
            or (fields.get(caption) or {}).get("field")
            or dims_sql.get(caption)
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a calculated filter card filters the extract by its own sql"
```

### Task 15: trust is a rate over every state (I6)

**Files:**

- Modify: `scripts/cube_validate.py` (`Cell`, `_trust`, `explain_cells`,
  `_explain_batch`, `issue_drafts`, `coverage_markdown`, `write_outputs`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `TRUST = 0.95`
  - `Cell.reproduces: bool | None = None` (set by explain on every judged cell)
  - `_slice(entry, sname, checks, fields, defaults=None, sheet_filters=None, lists=None, public_only=False) -> tuple[list[str], list[dict]]`
    (extract conditions, Cube filters) for one sheet in one state
  - `_extract_measure(sheet, meas, grain, where, run) -> dict` (values by key,
    table calculation applied)
  - `_trust(...) -> dict[tuple, float]` (the rate per sheet, measure, grain)
  - `coverage_markdown(states, cells, checks=None) -> str`

- [ ] **Step 1: Write the failing tests**

```python
def _many_states(n):
    return {
        f"s{i:02d}": {
            "state": {"dashboard": "Overview", "filters": {"Region": f"R{i:02d}"}},
            "status": "ok",
            "sheets": {},
        }
        for i in range(n)
    }


def _rate_cells(states):
    return [
        cv.Cell(
            "Overview - Table", s, {"School Name": "Alpha"}, "Avg Score", "48.50",
            48.5, 47.0 if s == "s00" else 48.5, 20,
            "mismatch" if s == "s00" else "match",
        )
        for s in states
    ]


def test_trust_is_a_rate_over_every_state(tmp_path):
    c = _checks(tmp_path)
    states = _many_states(20)
    cells = _rate_cells(states)

    def run(ds, sql):
        return [{"g0": "Alpha", "m": 10.0 if "'R19'" in sql else 48.5}]

    cv.explain_cells(cells, c, states, FIELDS, run, lambda q: ([], []))
    assert cells[0].verdict == "fail"  # 19 of 20 states reproduce: 95%, trusted
    assert cells[19].reproduces is False and cells[1].reproduces is True
    text = cv.coverage_markdown(states, cells, c)
    assert "Cells the extract SQL does not reproduce: 1" in text and "s19" in text


def test_a_measure_reproduced_below_the_rate_is_incomplete(tmp_path):
    c = _checks(tmp_path)
    states = _many_states(2)
    cells = _rate_cells(states)

    def run(ds, sql):
        return [{"g0": "Alpha", "m": 10.0 if "'R01'" in sql else 48.5}]

    cv.explain_cells(cells, c, states, FIELDS, run, lambda q: ([], []))
    assert cells[0].verdict == "incomplete" and "50%" in cells[0].why
```

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, no attribute `reproduces`.

- [ ] **Step 3: Implement**

Add to `Cell`, after `routes`:
`reproduces: bool | None = None  # the extract SQL gives Tableau's value`.

Add `TRUST = 0.95` next to `SMALL_CELL`. Add before `_trust`:

```python
def _slice(
    entry, sname, checks, fields, defaults=None, sheet_filters=None, lists=None,
    public_only=False,
) -> tuple[list[str], list[dict]]:
    """One sheet's slice in a state, on both sides: the state's filters, the
    dashboard defaults the sheet keeps, and the sheet's saved filters."""
    sheet = checks["sheets"][sname]
    saved = (sheet_filters or {}).get(sname, [])
    dflt = sheet_defaults((defaults or {}).get(entry["state"]["dashboard"]), saved)
    saved_where, saved_cube, _ = sheet_conditions(saved, entry, checks)
    where = state_where(entry, checks, fields, sheet, public_only, dflt, lists)
    cube = (
        state_filters(entry, checks, dflt, lists)[0]
        + hard_filters(checks, sheet.datasource)
        + saved_cube
    )
    return where + saved_where, cube


def _extract_measure(sheet, meas, grain, where, run) -> dict:
    rows = run(sheet.datasource, extract_sql(sheet, meas, list(grain), where))
    return apply_calc(meas, extract_values(rows, len(grain)), 1.0)
```

Replace `_trust`:

```python
def _trust(
    cells, checks, states, fields, run_extract, defaults=None, sheet_filters=None,
    lists=None,
) -> dict[tuple, float]:
    """The share of each (sheet, measure, grain)'s comparable cells, over every
    state, that the extract SQL reproduces. Sets each judged cell's `reproduces`;
    explain still checks every mismatched cell on its own."""
    pools: dict[tuple, dict[str, list[Cell]]] = {}
    for c in cells:
        if c.status in ("match", "mismatch") and (c.shown or "").strip():
            key = (c.sheet, c.measure, _grain(c)[0])
            pools.setdefault(key, {}).setdefault(c.state, []).append(c)
    out = {}
    for (sname, mname, grain), by_state in pools.items():
        sheet = checks["sheets"][sname]
        meas = sheet.measures[mname]
        hits = []
        for state, mine in sorted(by_state.items()):
            where, _ = _slice(states[state], sname, checks, fields, defaults,
                              sheet_filters, lists)
            try:
                ext = _extract_measure(sheet, meas, grain, where, run_extract)
            except Exception:  # noqa: BLE001 - SQL the extract cannot run reproduces nothing
                ext = {}
            for c in mine:
                c.reproduces = _reproduces(ext.get(_key(c, grain, sheet)), c, meas)
                hits.append(c.reproduces)
        out[(sname, mname, grain)] = sum(hits) / len(hits)
    return out
```

In `explain_cells`, add `c.reproduces = None` to the per-cell reset.

In `_explain_batch`, replace the trust check and the slice computation (from
`if not trusted.get(...)` through the `ext = apply_calc(...)` statement) with:

```python
    rate = trusted.get((sname, mname, grain), 0.0)
    if rate < TRUST:
        for c in batch:
            c.verdict = "incomplete"
            c.why = (
                f"extract SQL reproduces {rate:.0%} of this measure's cells at this "
                f"grain; {TRUST:.0%} needed"
            )
        return
    where, base = _slice(states[state], sname, checks, fields, defaults,
                         sheet_filters, lists)
    ext = _extract_measure(sheet, meas, grain, where, run_extract)
```

and compute `live_v` as
`_extract_measure(sheet, meas, grain, where, live.rows)`. Delete the now-unused
`sql` local; the variants still receive `where` and `base`.

In `issue_drafts`, replace the lines from `entry = states[first.state]` through
`where += sheet_conditions(saved, entry, checks)[0]` with:

```python
        where, _ = _slice(
            states[first.state], first.sheet, checks, fields, defaults,
            sheet_filters, lists, public_only=True,
        )
```

Replace `coverage_markdown`'s signature with
`def coverage_markdown(states, cells, checks=None) -> str:` and add, before the
routes section:

```python
    bad = _coarsest([c for c in cells if c.reproduces is False])
    if bad:
        lines += ["", f"Cells the extract SQL does not reproduce: {len(bad)}"]
        for c in bad[:50]:
            where = _where_text(c, checks) if checks else "a cell"
            small = "" if (c.n_students or 0) >= SMALL_CELL else " (small cell)"
            lines.append(f"- {c.state}: {c.sheet} / {c.measure}, {where}{small}")
```

In `write_outputs`, call `coverage_markdown(states, cells, checks)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass, the replay included (its planted bad
mapping reproduces 0%).

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): trust extract SQL at 95% of every state's cells, and list the rest"
```

### Task 16: any error marks only its batch incomplete; cells are written as batches finish (I4)

**Files:**

- Modify: `scripts/cube_validate.py` (`explain_cells`, `_explain`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  `explain_cells(..., lists=None, on_batch: Callable[[], None] | None = None)`

- [ ] **Step 1: Write the failing test**

```python
def test_any_error_in_a_batch_leaves_only_that_batch_incomplete(tmp_path):
    c = _checks(tmp_path)
    states = {"s": {"state": {"dashboard": "Overview"}, "status": "ok", "sheets": {}}}
    cells = [
        cv.Cell("Overview - Table", "s", {"School Name": "Alpha"}, "Avg Score",
                "48.50", 48.5, 49.0, 40, "mismatch"),
        cv.Cell("Overview - Table", "s", {}, "Avg Score", "48.50", 48.5, 48.5, 40,
                "match"),
    ]

    def no_table(ds, sql):
        raise cv.CheckError("datasource 'x' is not captioned 'rpt_x (dataset)'")

    live = cv.Live(rows=no_table, modified=lambda ds: None,
                   cube_now=lambda q: ([{"demo.avg_score": "49.0"}], None))

    def run(ds, sql):
        return [{"g0": "Alpha", "m": 48.5}] if "group by" in sql else [{"m": 48.5}]

    written = []
    cv.explain_cells(cells, c, states, {}, run, lambda q: ([], []), live,
                     on_batch=lambda: written.append(1))
    assert cells[0].verdict == "incomplete" and cells[0].why.startswith("CheckError")
    assert cells[1].verdict == "pass" and written == [1]
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k any_error 2>&1 | tail -n 30`
Expected: FAIL, unexpected keyword `on_batch` (and the `CheckError` escapes).

- [ ] **Step 3: Implement**

In `explain_cells`, add the parameter
`on_batch: Callable[[], None] | None = None` and replace the
`except CubeError as err:` block with:

```python
        except Exception as err:  # noqa: BLE001 - one batch's failure blames nobody
            # A query Cube or the warehouse cannot answer, or SQL the extract cannot
            # run, leaves only its own cells undecided.
            label = "Cube error" if isinstance(err, CubeError) else type(err).__name__
            for c in batch:
                c.verdict, c.why = "incomplete", f"{label}: {err}"[:300]
        if on_batch is not None:
            on_batch()
```

In `_explain`, pass
`on_batch=lambda: write_cells(snapdir / "cells.jsonl", cells)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass;
`test_a_cube_error_marks_its_cells_incomplete_and_explain_goes_on` still sees
the `Cube error` prefix.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "fix(cube): any error leaves only its batch incomplete; explain saves as it goes"
```

### Task 17: a fail names both numbers and whether rows or the formula differ (I1, I3)

**Files:**

- Modify: `scripts/cube_validate.py` (`Cell`, `_explain_batch`, `explain_cells`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `Cell.live: float | None`, `Cell.live_students: int | None`,
    `Cell.cube_students: int | None`, `Cell.gap: str` (`"row gap"`,
    `"formula gap"`, or `""` when nothing live was read)
  - `counts_sql(sheet, grain, where, student) -> str` and
    `extract_counts(rows, n_grain) -> dict[tuple, int]`
  - checks key `student_column` (default `student_number`): the extract column
    the live student count reads.

- [ ] **Step 1: Write the failing tests**

```python
def _fail_with_counts(tmp_path, live_n, cube_n):
    c = _checks(tmp_path)
    cell = cv.Cell(
        "Overview - Table", "s", {}, "Avg Score", "48.50", 48.5, 49.0, 40, "mismatch"
    )
    states = {"s": {"state": {"dashboard": "Overview"}, "status": "ok", "sheets": {}}}

    def rows(ds, sql):
        return [{"n": live_n}] if "as n" in sql and "as m" not in sql else [{"m": 48.0}]

    live = cv.Live(
        rows=rows,
        modified=lambda ds: dt.datetime(2026, 10, 9, 10, tzinfo=dt.UTC),
        cube_now=lambda q: (
            [{"demo.avg_score": "49.0", "demo.count_students": str(cube_n)}],
            dt.datetime(2026, 10, 9, 11, tzinfo=dt.UTC),
        ),
    )
    cv.explain_cells(
        [cell], c, states, {}, lambda ds, sql: [{"m": 48.5}], lambda q: ([], []), live
    )
    return cell


def test_a_fail_with_different_student_counts_is_a_row_gap(tmp_path):
    cell = _fail_with_counts(tmp_path, live_n=41, cube_n=40)
    assert (cell.verdict, cell.gap) == ("fail", "row gap")
    assert (cell.live, cell.live_students, cell.cube_students) == (48.0, 41, 40)
    assert cell.why.startswith("row gap: Cube 49, live table 48")
    assert "students: Cube 40, live table 41" in cell.why


def test_a_fail_with_equal_student_counts_is_a_formula_gap(tmp_path):
    cell = _fail_with_counts(tmp_path, live_n=40, cube_n=40)
    assert cell.gap == "formula gap" and cell.why.startswith("formula gap")
```

`test_fresh_cube_that_differs_from_the_live_table_fails` keeps passing: the
refresh times stay in the reason.

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, unexpected keyword / no attribute
`gap`.

- [ ] **Step 3: Implement**

Add to `Cell`, after `reproduces`:

```python
    live: float | None = None  # the same SQL on the live rpt_ table
    live_students: int | None = None
    cube_students: int | None = None
    gap: str = ""  # "row gap" (student counts differ) or "formula gap"
```

After `extract_values`, add:

```python
def counts_sql(sheet, grain, where, student) -> str:
    sel = [f"{sheet.dims[d].sql} as g{i}" for i, d in enumerate(grain)]
    sel.append(f"count(distinct {student}) as n")
    # trunk-ignore(bandit/B608): SQL over the dashboard's own extract or rpt_ table; names come from the checks file
    sql = f"select {', '.join(sel)} from `{EXTRACT_TABLE}`"
    if where:
        sql += " where " + " and ".join(f"({w})" for w in where)
    if grain:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(grain)))
    return sql


def extract_counts(rows, n_grain) -> dict[tuple, int | None]:
    return {
        tuple(norm_dim(r[f"g{i}"]) for i in range(n_grain)): _int(r.get("n"))
        for r in rows
    }
```

In `explain_cells`, add `c.live = c.live_students = c.cube_students = None` and
`c.gap = ""` to the per-cell reset.

In `_explain_batch`, inside `if live is not None:`, add after `cube_now = ...`:

```python
        student_col = checks.get("student_column", "student_number")
        live_n = extract_counts(
            live.rows(sheet.datasource, counts_sql(sheet, grain, where, student_col)),
            len(grain),
        )
        cube_n = {
            k: _int(r.get(checks["student_count"]))
            for k, r in _by_key(crows, sheet, grain).items()
        }
```

and initialise `live_n, cube_n = {}, {}` next to `live_v, cube_now, ...`.
Replace the whole `if c.verdict == "fail" and cube_at and table_at:` block at
the end of the cell loop with:

```python
        if c.verdict != "fail" or live is None:
            continue
        c.live = None if live_v is None else live_v.get(k)
        c.live_students, c.cube_students = live_n.get(k), cube_n.get(k)
        if cube_at and table_at and cube_at < table_at:
            c.verdict = "incomplete"
            c.why = (
                f"Cube's data (refreshed {cube_at:%Y-%m-%d %H:%M}) is older than the live "
                f"table (built {table_at:%Y-%m-%d %H:%M}); re-run explain after Cube refreshes"
            )
            continue
        c.gap = "row gap" if c.live_students != c.cube_students else "formula gap"
        c.why = (
            f"{c.gap}: Cube {_fmt(c.cube)}, live table {_fmt(c.live)}; students: "
            f"Cube {c.cube_students}, live table {c.live_students}"
        )
        if cube_at and table_at:
            c.why += (
                f" (Cube refreshed {cube_at:%Y-%m-%d %H:%M}, the live table built "
                f"{table_at:%Y-%m-%d %H:%M})"
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a fail records the live value and student counts, labelled row or formula gap"
```

### Task 18: `fix: accepted` for a difference an owner will not fix

**Files:**

- Modify: `scripts/cube_validate.py` (`FIX_SIDES`, `load_checks`,
  `cell_verdict`, `_explain_batch`, `_SIDE_TITLES`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces: `FIX_SIDES` gains `"accepted"`; `load_checks` requires `issue:` on
  an accepted mismatch; its cells are `pass` with `why` naming the issue; the
  digest lists them under "Accepted differences"; no draft (it has `issue:`).

- [ ] **Step 1: Write the failing tests**

```python
def test_an_accepted_difference_needs_its_issue(tmp_path):
    with pytest.raises(cv.CheckError, match="accepted needs issue"):
        _checks(tmp_path, mismatches={"offgrade": {"title": "x", "what": "y", "fix": "accepted"}})


def test_an_accepted_difference_passes_and_names_its_issue(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["mismatches"] = {
        "offgrade": {"title": "fix(cube): x", "what": "y", "fix": "accepted", "issue": 5885}
    }
    d["sheets"]["Overview - Table"]["measures"]["Avg Score"]["variants"] = [
        {"explains": ["offgrade"], "sql": "avg(score) + 0.5"}
    ]
    c = cv.load_checks(_write(tmp_path, d))
    states = {"s": {"state": {"dashboard": "Overview"}, "status": "ok", "sheets": {}}}
    cell = cv.Cell(
        "Overview - Table", "s", {}, "Avg Score", "48.50", 48.5, 49.0, 40, "mismatch"
    )

    def run(ds, sql):
        return [{"m": 49.0 if "+ 0.5" in sql else 48.5}]

    cv.explain_cells([cell], c, states, {}, run, lambda q: ([], []))
    assert cell.verdict == "pass" and "#5885" in cell.why
    assert "## Accepted differences" in cv.digest_markdown("Demo", [cell], c)
```

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, `fix must be one of`.

- [ ] **Step 3: Implement**

Change `FIX_SIDES` to
`("cube", "dashboard", "source", "undecided", "accepted")`. In `load_checks`,
after the `fix must be one of` check, add:

```python
        if m["fix"] == "accepted" and not m.get("issue"):
            raise CheckError(f"mismatch {name}: fix accepted needs issue: (the ruling)")
```

`cell_verdict` already returns `pass` when no stronger side explains the cell.
In `_explain_batch`, right after `c.verdict = cell_verdict(c, sides, meas)`,
add:

```python
        accepted = [n for n in c.explained_by if n in sides.get("accepted", frozenset())]
        if c.verdict == "pass" and accepted:
            c.why = "accepted difference, see " + ", ".join(
                f"#{checks['mismatches'][n]['issue']}" for n in accepted
            )
```

Add `("accepted", "Accepted differences")` as the last entry of `_SIDE_TITLES`.
`_issue_labels` and `_ANSWERS` need no entry: an accepted mismatch always has
`issue:`, so it never gets a draft.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): fix: accepted passes a difference an owner ruled on"
```

### Task 19: the descent stops at Cube's last level; a mismatching cross-cut gets its other values (M4, M5)

**Files:**

- Modify: `scripts/cube_validate.py` (`next_states`, `run_compare`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  `next_states(states, status, trees, cross_cuts, fields, children, members: set[str] | None = None) -> list[dict]`
  (`members`: captions with a Cube member; None keeps every level)

- [ ] **Step 1: Write the failing tests**

```python
def test_the_descent_stops_at_the_last_level_cube_can_express():
    trees = {DS: {"region": ["region", "school", "grade_level"]}}
    states = {"n": _entry({"Region": "North", "School Name": "Alpha"})}
    out = cv.next_states(
        states, {"n": "mismatch"}, trees, CROSS, FIELDS, children,
        members={"Region", "School Name", "IEP"},
    )
    # Grade Level has no Cube member: the gap is split by the cross-cut instead.
    assert [s["filters"].get("Grade Level") for s in out] == [None]
    assert out[0]["filters"]["IEP"] == "No IEP"


def test_a_mismatching_cross_cut_value_brings_in_its_other_values():
    def kids(ds, where, f):
        return [("No IEP", 25), ("Has IEP", 12), ("Tiny", 3), (None, 40)]

    states = {"x": _entry({"IEP": "No IEP"})}
    out = cv.next_states(states, {"x": "mismatch"}, TREES, CROSS, FIELDS, kids)
    assert [s["filters"]["IEP"] for s in out] == ["Has IEP"]
    assert cv.next_states(states, {"x": "match"}, TREES, CROSS, FIELDS, kids) == []
```

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, unexpected keyword `members`; no
promotion.

- [ ] **Step 3: Implement**

In `next_states`, add the parameter `members: set[str] | None = None`. Right
after `ds, levels = path`, truncate the tree at its first level Cube cannot
express:

```python
        # The descent stops at the last level with a Cube member: a deeper state
        # could only end missing_member.
        if members is not None:
            usable = []
            for f in levels:
                if caption_of.get((ds, f)) not in members:
                    break
                usable.append(f)
            levels = usable or levels[:1]
```

At the end of `next_states`, before `return out`, add:

```python
    # A cross-cut exports its largest value first; when that mismatches, its other
    # values are proposed, to see whether the gap follows the flag.
    for sid, e in sorted(states.items()):
        st = e["state"]
        fs = st.get("filters") or {}
        if (
            e.get("status") != "ok"
            or status.get(sid) != "mismatch"
            or st.get("params")
            or st.get("click")
            or len(fs) != 1
        ):
            continue
        ((cap, _),) = fs.items()
        f = fields.get(cap)
        if not f or f["field"] not in cross_cuts.get(f["datasource"], []):
            continue
        for v, n in children(f["datasource"], [], f["field"]):
            if v is not None and n >= SMALL_CELL:
                add({"dashboard": st["dashboard"], "filters": {cap: v}})
```

In `run_compare`, pass `members=set(_caption_members(checks))` to `next_states`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): stop the descent at Cube's last level; promote a mismatching cross-cut"
```

---

## Part D: mapping

### Task 20: a `map` step drafts `sheets:` from headers, formulas and Cube members (I2, I9)

**Files:**

- Modify: `scripts/cube_validate.py` (`CubeClient`, new functions, `main`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `CubeClient.meta() -> list[str]` (every member name in `/v1/meta`)
  - `column_formulas(twb_text: str) -> dict[str, dict]`, caption to
    `{"datasource", "field", "formula"}`
  - `header_column(header: str, formulas: dict) -> tuple[str, dict | None]`
  - `candidates(field: str, caption: str, members: list[str]) -> list[str]`
  - `draft_map(snapdir: Path, members: list[str]) -> dict` (sheet to column to
    `{"kind", "formula", "field", "datasource", "cube_candidates"}`)
  - CLI `cube_validate.py map <checks>` writes `<snapshot>/map.yml`. It needs
    `CUBE_API_SECRET`, so it runs inside the throwaway pytest like `compare`.

- [ ] **Step 1: Write the failing tests**

```python
FIXTURE_TWB = (
    Path(__file__).parent / "fixtures" / "cube_validate" / "review.twb"
).read_text(encoding="utf-8")


def test_column_formulas_and_headers_find_the_workbook_column():
    cols = cv.column_formulas(FIXTURE_TWB)
    assert cols["Pct Done"]["formula"] == "{FIXED [school]: SUM([score])}"
    assert cols["School Name"] == {"datasource": DS, "field": "school", "formula": None}
    assert cv.header_column("Avg. Pct Done", cols)[0] == "Pct Done"
    assert cv.header_column("Mystery", cols) == ("Mystery", None)


def test_candidates_match_the_field_or_the_caption():
    members = ["demo.school", "demo.grade_level", "demo.avg_score"]
    assert cv.candidates("school", "School Name", members) == ["demo.school"]
    assert cv.candidates("Calculation_1", "Grade Level", members) == ["demo.grade_level"]


def test_draft_map_lists_each_exported_column_with_its_formula(tmp_path):
    snapdir = _snapdir(tmp_path, csv=b"School Name,Avg. Pct Done\r\nAlpha,1\r\n")
    (snapdir / "review.twb").write_text(FIXTURE_TWB, encoding="utf-8")
    col = cv.draft_map(snapdir, ["demo.school"])["Overview - Table"]
    assert col["School Name"]["kind"] == "dimension"
    assert col["School Name"]["cube_candidates"] == ["demo.school"]
    assert col["Avg. Pct Done"]["kind"] == "measure"
    assert "FIXED" in col["Avg. Pct Done"]["formula"]


def test_cube_client_reads_the_member_list():
    class Http:
        def get(self, url, headers):
            return FakeResponse(
                {"cubes": [{"measures": [{"name": "v.m"}], "dimensions": [{"name": "v.d"}]}]}
            )

    client = cv.CubeClient("https://cube/api", SECRET, "me@example.org", http=Http())
    assert client.meta() == ["v.d", "v.m"]
```

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, no attribute `column_formulas`.

- [ ] **Step 3: Implement**

Add to `CubeClient`:

```python
    def meta(self) -> list[str]:
        """Every member name this identity can see, for drafting a mapping."""
        r = self._http().get(f"{self.url}/meta", headers={"Authorization": self._token()})
        body = r.json()
        return sorted(
            x["name"]
            for c in body.get("cubes", [])
            for kind in ("measures", "dimensions")
            for x in c.get(kind, [])
        )
```

After `write_outputs`, add:

```python
# Tableau names an aggregated column "<prefix><caption>" in an export header.
AGG_PREFIXES = (
    "Avg. ", "Sum of ", "Distinct count of ", "Count of ", "% of Total ",
    "Running Sum of ", "Max. ", "Min. ", "Median of ",
)
_AGG = re.compile(r"\b(AVG|SUM|COUNTD?|MIN|MAX|MEDIAN|TOTAL|WINDOW_\w+)\(", re.I)


def column_formulas(twb_text: str) -> dict[str, dict]:
    """Each workbook column by caption, with its datasource, field and formula."""
    import defusedxml.ElementTree as SafeET

    out: dict[str, dict] = {}
    for ds in SafeET.fromstring(twb_text).iter("datasource"):
        source = ds.get("caption") or ds.get("name") or ""
        for col in ds.findall("column"):
            name = (col.get("name") or "").strip("[]")
            calc = col.find("calculation")
            out.setdefault(
                col.get("caption") or name,
                {
                    "datasource": source,
                    "field": name,
                    "formula": calc.get("formula") if calc is not None else None,
                },
            )
    return out


def header_column(header: str, formulas: dict) -> tuple[str, dict | None]:
    """The workbook column behind an exported header, after Tableau's prefix."""
    if header in formulas:
        return header, formulas[header]
    for p in AGG_PREFIXES:
        if header.startswith(p) and header[len(p):] in formulas:
            return header[len(p):], formulas[header[len(p):]]
    return header, None


def candidates(field: str, caption: str, members: list[str]) -> list[str]:
    """Cube members whose short name is the field or the caption: a draft only."""
    want = {field.lower(), _slug(caption).replace("-", "_")}
    return [m for m in members if m.split(".", 1)[-1] in want]


def draft_map(snapdir: Path, members: list[str]) -> dict:
    """A draft of sheets: for the analyst to edit, from each exported sheet's
    header, the workbook's formula for each column, and Cube's members."""
    snapdir = Path(snapdir)
    formulas = column_formulas((snapdir / "review.twb").read_text(encoding="utf-8"))
    m = json.loads((snapdir / "manifest.json").read_text())
    headers: dict[str, list[str]] = {}
    for _, e in sorted(m["states"].items()):
        if e.get("status") != "ok":
            continue
        for sheet, meta in e["sheets"].items():
            if sheet not in headers:
                headers[sheet] = read_export((snapdir / meta["file"]).read_bytes()).columns
    out: dict[str, dict] = {}
    for sheet, cols in headers.items():
        out[sheet] = {}
        for h in cols:
            name, col = header_column(h, formulas)
            formula = col["formula"] if col else None
            prefixed = name != h
            out[sheet][h] = {
                "kind": "measure" if prefixed or _AGG.search(formula or "") else "dimension",
                "formula": formula,
                "field": col["field"] if col else None,
                "datasource": col["datasource"] if col else None,
                "cube_candidates": candidates(col["field"] if col else name, name, members),
            }
    return out


def _map(a) -> int:
    checks = load_checks(a.checks)
    snapdir = latest_snapshot(checks["workbook"])
    draft = draft_map(snapdir, _client().meta())
    (snapdir / "map.yml").write_text(yaml.safe_dump(draft, sort_keys=False, allow_unicode=True))
    print(f"map draft: {len(draft)} sheets -> {snapdir / 'map.yml'}")
    return 0
```

In `main`, add `sub.add_parser("map").add_argument("checks")` and `"map": _map`
to the dispatch dict. Add the line
`uv run --with tableauhyperapi scripts/cube_validate.py map <checks.yml>` to the
module docstring.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a map step drafts sheets from headers, formulas and Cube members"
```

### Task 21: a dimension mapped to several Cube members, with key patterns tried in order (I5)

**Files:**

- Modify: `scripts/cube_validate.py` (`Dim`, `load_checks`, `_caption_members`,
  `_key_text`, `_keyed_dims`, `masked_key`, `cube_query`, `_by_key`,
  `_compare_grain`, `_trust`, `_explain_batch`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `Dim.cube: str | tuple[str, ...] | None`; `Dim.keys: tuple[str, ...]`
    replaces `Dim.key` (YAML `key:` still loads, as a 1-item `keys`)
  - `cube_members(dim: Dim) -> list[str]`
  - `cube_key(row: dict, dim: Dim) -> str` (several members join with " - ", as
    the extract expression does)
  - `Keys(keys, multi: list[int])` with `find(k: tuple) -> list[tuple]`: the
    exact key, else every key whose multi-member positions end with the shown
    value
  - `_multi(sheet, grain) -> list[int]`

- [ ] **Step 1: Write the failing tests**

```python
SECTION_KEYS = [r"^(?!G\d+ - ).* - ([^-]+ - \S+)$", r"^G\d+ - .* - (\S+)$"]


def _sections(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["dims"]["Section"] = {
        "cube": ["demo.course_title", "demo.identifier"],
        "sql": "course_name || ' - ' || section_number",
        "keys": SECTION_KEYS,
    }
    c = cv.load_checks(_write(tmp_path, d))
    return c, c["sheets"]["Overview - Table"]


def _section_cube(pairs):
    def load(q):
        return [
            {"demo.course_title": t, "demo.identifier": i, "demo.avg_score": "48.5",
             "demo.count_students": "20"}
            for t, i in pairs
        ], []

    return load


def test_the_es_label_never_matches_the_hs_key_pattern(tmp_path):
    _, sheet = _sections(tmp_path)
    dim = sheet.dims["Section"]
    assert cv._key_text(dim, "Teacher, A - English 100 - 501") == "English 100 - 501"
    assert cv._key_text(dim, "G5 - Teacher, B - 601") == "601"


def test_a_section_joins_on_course_and_section_or_on_the_section_alone(tmp_path):
    c, sheet = _sections(tmp_path)
    export = cv.read_export(
        b'Section,Avg Score\r\n"Teacher, A - English 100 - 501",48.50\r\n'
        b'"G5 - Teacher, B - 601",48.50\r\n'
    )
    load = _section_cube([("English 100", "501"), ("ELA 5", "601")])
    cells = cv.compare_export(sheet, "s1", export, load, [], [], c)
    assert [x.status for x in cells] == ["match", "match"]


def test_a_short_key_matching_two_cube_rows_is_not_comparable(tmp_path):
    c, sheet = _sections(tmp_path)
    export = cv.read_export(b'Section,Avg Score\r\n"G5 - Teacher, B - 601",48.50\r\n')
    load = _section_cube([("ELA 5", "601"), ("Math 5", "601")])
    cells = cv.compare_export(sheet, "s1", export, load, [], [], c)
    assert [(x.status, x.reason) for x in cells] == [
        ("not_comparable", "the shown key matches several Cube rows")
    ]
```

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, `Dim` has no `keys`.

- [ ] **Step 3: Implement**

Replace `Dim`:

```python
@dataclass(frozen=True)
class Dim:
    # One Cube member, several (joined with " - " to match `sql`), or none.
    cube: str | tuple[str, ...] | None
    sql: str
    # Identifies a person: outputs show "a student", or this label, in place of values.
    person: bool | str = False
    # Regexes tried in order; the first that matches gives the join key inside the
    # displayed text (Tableau shows a section as "G5 - <teacher> - 501"; the key is 501).
    keys: tuple[str, ...] = ()
    # Tableau aliases to stored values ("K" for grade 0), applied after the key.
    values: dict | None = None
```

In `load_checks`, build each dimension as:

```python
        dims = {
            c: Dim(
                tuple(d["cube"]) if isinstance(d.get("cube"), list) else d.get("cube"),
                d.get("sql") or "",
                d.get("person", False),
                tuple(d.get("keys") or ([d["key"]] if d.get("key") else [])),
                {str(k): str(v) for k, v in (d.get("values") or {}).items()} or None,
            )
            for c, d in (s.get("dims") or {}).items()
        }
```

Replace `_key_text`, and update its two neighbours to read `keys`:

```python
def _key_text(dim: Dim, value: str) -> str | None:
    """The join key inside a displayed label: the first key pattern that matches.
    None when none does; the value itself when the dimension has no pattern."""
    if not dim.keys:
        return value
    for pattern in dim.keys:
        if m := re.search(pattern, value):
            return m.group(1) if m.groups() else m.group(0)
    return None
```

In `_keyed_dims` and `masked_key`, change `d.key` / `dim.key` to `d.keys` /
`dim.keys`. In `_caption_members`, keep only single members:
`if isinstance(d.cube, str)`.

Add after `cube_query`, and change `cube_query` and `_by_key` to use them:

```python
def cube_members(dim: Dim) -> list[str]:
    if dim.cube is None:
        return []
    return list(dim.cube) if isinstance(dim.cube, tuple) else [dim.cube]


def cube_key(row: dict, dim: Dim) -> str:
    """A Cube row's value for a dimension; several members join with " - ", as the
    dimension's extract expression does."""
    ms = cube_members(dim)
    if len(ms) == 1:
        return norm_dim(row.get(ms[0]))
    return " - ".join(norm_dim(row.get(m)) for m in ms)


def _multi(sheet, grain) -> list[int]:
    return [i for i, d in enumerate(grain) if len(cube_members(sheet.dims[d])) > 1]


class Keys:
    """Row keys at a grain, joinable by a Tableau key: exactly, or, where a
    multi-member dimension shows only its last member (an ES/MS section label
    has no course), by the keys that end with it."""

    def __init__(self, keys, multi: list[int]):
        self.all, self.multi = set(keys), multi
        self.short: dict[tuple, list[tuple]] = {}
        for h in self.all if multi else ():
            self.short.setdefault(self._short(h), []).append(h)

    def _short(self, h: tuple) -> tuple:
        return tuple(
            v.rsplit(" - ", 1)[-1] if i in self.multi else v for i, v in enumerate(h)
        )

    def find(self, k: tuple) -> list[tuple]:
        if k in self.all:
            return [k]
        return sorted(self.short.get(k, []))
```

```python
def cube_query(sheet, grain, measures, filters) -> dict:
    return {
        "measures": sorted({m for m in measures if m}),
        "dimensions": [m for d in grain for m in cube_members(sheet.dims[d])],
        "filters": filters,
        "limit": CUBE_LIMIT,
    }


def _by_key(rows, sheet, grain) -> dict[tuple, dict]:
    return {tuple(cube_key(r, sheet.dims[d]) for d in grain): r for r in rows}
```

In `_compare_grain`, after `answers = {...}`, build
`index = Keys({k for a in answers.values() for k in a.fact}, _multi(sheet, grain))`,
and at the top of the row loop resolve the key:

```python
        hits = index.find(tuple(tableau_key(sheet, d, r.get(d)) for d in grain))
        seen.update(hits)
        k = hits[0] if len(hits) == 1 else None
```

Then insert a branch before the Tableau-only branch, and widen that branch to a
missing key:

```python
            elif len(hits) > 1:
                out.append(cell(key, m, "not_comparable",
                                "the shown key matches several Cube rows", shown=text))
            elif k is None or k not in a.fact:
```

and drop the `seen.add(k)` in the matched branch (the resolved hits are already
in `seen`).

In `_trust`, after computing `ext` for a state, build
`index = Keys(ext, _multi(sheet, grain))` and look cells up with:

```python
            for c in mine:
                hits = index.find(_key(c, grain, sheet))
                value = ext.get(hits[0]) if len(hits) == 1 else None
                c.reproduces = _reproduces(value, c, meas)
                hits_all.append(c.reproduces)
```

(rename the rate list to `hits_all` so the two names do not clash). In
`_explain_batch`, after `ext = ...`, build
`index = Keys(ext, _multi(sheet, grain))` and at the top of the cell loop
resolve:

```python
        k0 = _key(c, grain, sheet)
        hits = index.find(k0)
        k = hits[0] if len(hits) == 1 else k0
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass, the old single `key:` test included.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a dimension can join on several Cube members with ordered key patterns"
```

### Task 22: a dimension mapped to a Cube time dimension at a granularity

**Files:**

- Modify: `scripts/cube_validate.py` (`Dim`, `load_checks`, `cube_members`,
  `cube_query`, `cube_key`, `_caption_members`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces: `Dim.granularity: str | None = None`; YAML
  `cube: {time: <view>.date_day, granularity: week}`. A time dimension goes in
  the query's `timeDimensions`, and its key reads `<member>.<granularity>`.

- [ ] **Step 1: Write the failing test**

```python
def test_a_week_dimension_asks_cube_for_a_time_granularity(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["dims"]["Week"] = {
        "cube": {"time": "demo.date_day", "granularity": "week"},
        "sql": "week_start_monday",
    }
    c = cv.load_checks(_write(tmp_path, d))
    sheet = c["sheets"]["Overview - Table"]
    asked = []

    def load(q):
        asked.append(q)
        return [
            {"demo.date_day.week": "2026-10-05T00:00:00.000", "demo.avg_score": "48.5",
             "demo.count_students": "20"}
        ], []

    export = cv.read_export(b"Week,Avg Score\r\n10/5/2026,48.50\r\n")
    cells = cv.compare_export(sheet, "s1", export, load, [], [], c)
    assert [x.status for x in cells] == ["match"]
    assert asked[0]["dimensions"] == []
    assert asked[0]["timeDimensions"] == [
        {"dimension": "demo.date_day", "granularity": "week"}
    ]
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k week_dimension 2>&1 | tail -n 30`
Expected: FAIL, the dict reaches `dimensions`.

- [ ] **Step 3: Implement**

Add `granularity: str | None = None` as the last field of `Dim`. In
`load_checks`, before building each `Dim`, unpack a time mapping:

```python
            cube = d.get("cube")
            granularity = None
            if isinstance(cube, dict):
                cube, granularity = cube["time"], cube["granularity"]
```

and pass `cube` (as before, a list becomes a tuple) and
`granularity=granularity`. Replace `cube_query` and `cube_key`:

```python
def cube_query(sheet, grain, measures, filters) -> dict:
    q = {
        "measures": sorted({m for m in measures if m}),
        "dimensions": [
            m
            for d in grain
            if not sheet.dims[d].granularity
            for m in cube_members(sheet.dims[d])
        ],
        "filters": filters,
        "limit": CUBE_LIMIT,
    }
    times = [
        {"dimension": sheet.dims[d].cube, "granularity": sheet.dims[d].granularity}
        for d in grain
        if sheet.dims[d].granularity
    ]
    if times:
        q["timeDimensions"] = times
    return q


def cube_key(row: dict, dim: Dim) -> str:
    """A Cube row's value for a dimension: a time dimension at its granularity, or
    several members joined with " - ", as the extract expression does."""
    if dim.granularity:
        return norm_dim(row.get(f"{dim.cube}.{dim.granularity}"))
    ms = cube_members(dim)
    if len(ms) == 1:
        return norm_dim(row.get(ms[0]))
    return " - ".join(norm_dim(row.get(m)) for m in ms)
```

In `_caption_members`, also skip time dimensions
(`if isinstance(d.cube, str) and not d.granularity`): a week caption filters
through a date range, which no state uses yet.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): map a dimension to a Cube time dimension at a granularity"
```

### Task 23: `attr: true`, and filters under one sheet (M7, gap 2)

**Files:**

- Modify: `scripts/cube_validate.py` (`Dim`, `SheetMap`, `load_checks`,
  `compare_export`, `hard_filters`, `_slice`, `state_where`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `Dim.attr: bool = False` (a known attribute; the `*` rule stays the
    fallback)
  - `SheetMap.cube_filters: list[dict]`, `SheetMap.extract_filters: list[dict]`
  - `hard_filters(checks: dict, sheet: SheetMap, public_only: bool = False) -> list[dict]`
    (was `(checks, datasource)`; strips the `datasource` and `private` keys, and
    drops private filters when `public_only`)

- [ ] **Step 1: Write the failing tests**

```python
def test_a_known_attribute_leaves_the_grain(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["dims"]["Title"] = {
        "cube": "demo.title", "sql": "title", "attr": True,
    }
    c = cv.load_checks(_write(tmp_path, d))
    cube = FakeCube({"Alpha": _row(48.5)}, _row(0))
    export = cv.read_export(b"School Name,Title,Avg Score\r\nAlpha,T1,48.50\r\n")
    cv.compare_export(c["sheets"]["Overview - Table"], "s1", export, cube, [], [], c)
    assert cube.queries[0]["dimensions"] == ["demo.school"]


def test_a_sheet_carries_its_own_filters_on_both_sides(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["cube_filters"] = [
        {"member": "demo.grade_band", "operator": "equals", "values": ["HS"]}
    ]
    d["sheets"]["Overview - Table"]["extract_filters"] = [{"sql": "school_level = 'HS'"}]
    c = cv.load_checks(_write(tmp_path, d))
    sheet = c["sheets"]["Overview - Table"]
    assert {"member": "demo.grade_band", "operator": "equals", "values": ["HS"]} in (
        cv.hard_filters(c, sheet)
    )
    entry = {"state": {"dashboard": "Overview"}}
    assert "school_level = 'HS'" in cv.state_where(entry, c, {}, sheet)


def test_hard_filters_never_send_private_or_datasource_keys(tmp_path):
    private = {"member": "demo.is_test", "operator": "equals", "values": ["false"],
               "private": True, "datasource": DS}
    c = _checks(tmp_path, cube_filters=[private])
    sheet = c["sheets"]["Overview - Table"]
    assert cv.hard_filters(c, sheet) == [
        {"member": "demo.is_test", "operator": "equals", "values": ["false"]}
    ]
    assert cv.hard_filters(c, sheet, public_only=True) == []
```

Update `test_hard_filters_apply_per_datasource` to call
`cv.hard_filters(c, c["sheets"]["Overview - Table"])`.

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, unexpected keyword `attr` and
`hard_filters` signature errors.

- [ ] **Step 3: Implement**

Add `attr: bool = False` as the last field of `Dim`, and pass
`attr=bool(d.get("attr"))` in `load_checks`. Add to `SheetMap`:

```python
    cube_filters: list[dict] = field(default_factory=list)
    extract_filters: list[dict] = field(default_factory=list)
```

and build it in `load_checks` as
`SheetMap(name, s.get("datasource", ""), dims, measures, list(s.get("cube_filters") or []), list(s.get("extract_filters") or []))`.

In `compare_export`, change the attribute line to
`attrs = [d for d in dims if sheet.dims[d].attr or any(r.get(d) == MULTI for r in export.rows)]`
and the hard filters to `hard_filters(checks, sheet)`. Replace `hard_filters`:

```python
def hard_filters(checks: dict, sheet: SheetMap, public_only: bool = False) -> list[dict]:
    """The dashboard's hard Cube filters for one sheet: the datasource's, then the
    sheet's own. Only Cube's keys are sent."""
    every = [
        f for f in checks["cube_filters"] if f.get("datasource") in (None, sheet.datasource)
    ] + list(sheet.cube_filters)
    return [
        {k: v for k, v in f.items() if k not in ("datasource", "private")}
        for f in every
        if not (public_only and f.get("private"))
    ]
```

In `_slice`, call `hard_filters(checks, sheet, public_only)`. In `state_where`,
loop the extract filters over
`[*checks["extract_filters"], *sheet.extract_filters]`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): attr: true, and Cube and extract filters under one sheet"
```

### Task 24: Cube filters and an extract condition on one measure

**Files:**

- Modify: `scripts/cube_validate.py` (`Measure`, `_measure`, `extract_sql`,
  `_variant`, `_ask_cube`, `_explain_batch`; removes `_cube_at` and
  `_cube_values`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `Measure.cube_filters: list[dict]`, `Measure.where: str | None` (limits
    every aggregate of the measure's own SQL, as a variant's `where` does)
  - `_cube_queries(sheet, meas, grain, filters, student=None) -> list[dict]`
  - `_cube_measure(sheet, meas, grain, filters, ask, student=None) -> tuple[dict, dict]`
    (values with the table calculation applied, student counts); `ask(q)`
    returns rows
  - `_ask_cube` asks once per distinct set of measure filters.

- [ ] **Step 1: Write the failing test**

```python
IEP_ONLY = [{"member": "demo.is_iep", "operator": "equals", "values": ["true"]}]


def test_a_measure_carries_its_own_cube_filters_and_extract_condition(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["measures"]["IEP Score"] = {
        "cube": "demo.avg_score", "sql": "avg(score)", "round": 2,
        "cube_filters": IEP_ONLY, "where": "iep_status like '%SPED%'",
    }
    c = cv.load_checks(_write(tmp_path, d))
    sheet = c["sheets"]["Overview - Table"]
    asked = []

    def load(q):
        asked.append(q)
        iep = any(f.get("member") == "demo.is_iep" for f in q["filters"])
        return [{"demo.school": "Alpha", "demo.avg_score": "40" if iep else "48.5",
                 "demo.count_students": "20"}], []

    export = cv.read_export(b"School Name,Avg Score,IEP Score\r\nAlpha,48.50,40.00\r\n")
    cells = cv.compare_export(sheet, "s1", export, load, [], [], c)
    assert [x.status for x in cells] == ["match", "match"]
    assert len(asked) == 4  # 2 filter sets, each by both routes
    sql = cv.extract_sql(sheet, sheet.measures["IEP Score"], [], [])
    assert "iep_status LIKE '%SPED%'" in sql and "IF(" in sql.upper()
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k own_cube_filters 2>&1 | tail -n 30`
Expected: FAIL, `Measure` takes no `cube_filters`.

- [ ] **Step 3: Implement**

Add to `Measure`, last:

```python
    cube_filters: list[dict] = field(default_factory=list)  # Cube filters for this measure alone
    where: str | None = None  # an extract condition for this measure alone
```

and pass `list(m.get("cube_filters") or [])` and `m.get("where")` as the last 2
arguments in `_measure`.

In `extract_sql`, apply the measure's own condition before building the select:

```python
def _own_sql(meas) -> tuple[str | None, str | None, str | None]:
    """The measure's SQL, with every aggregate limited by its own `where`."""
    if not meas.where:
        return meas.sql, meas.num, meas.den
    return tuple(_filtered(s, meas.where) if s else None for s in (meas.sql, meas.num, meas.den))
```

and in `extract_sql` replace the measure part of `sel` with:

```python
    sql_, num, den = _own_sql(meas)
    sel += [f"{sql_} as m"] if sql_ else [f"{num} as m_num", f"{den} as m_den"]
```

In `_variant`, pass `where=meas.where` to both `Measure(...)` constructions, and
compute the Cube side with
`cube = _cube_measure(sheet, meas, grain, base + v["cube_filters"], lambda q: load(q)[0], student)[0] if v.get("cube_filters") else None`.

Replace `_cube_values` and `_cube_at` with:

```python
def _cube_queries(sheet, meas, grain, filters, student=None) -> list[dict]:
    """The Cube queries behind one measure at a grain, its own filters on top."""
    return [cube_query(sheet, grain, [meas.cube, student], filters + meas.cube_filters)]


def _cube_measure(sheet, meas, grain, filters, ask, student=None) -> tuple[dict, dict]:
    """A measure's Cube values (its table calculation applied) and student counts."""
    (q,) = _cube_queries(sheet, meas, grain, filters, student)
    by = _by_key(ask(q), sheet, grain)
    values = apply_calc(meas, {k: _num(r.get(meas.cube)) for k, r in by.items()}, meas.scale)
    counts = {k: _int(r.get(student)) for k, r in by.items()} if student else {}
    return values, counts
```

In `_explain_batch`, replace the Cube part of the live block (the
`crows, cube_at = live.cube_now(...)`, `cube_now = ...` and `cube_n = ...`
statements) with:

```python
        refreshed = []

        def ask_now(q):
            rows_, at = live.cube_now(q)
            refreshed.append(at)
            return rows_

        cube_now, cube_n = _cube_measure(
            sheet, meas, grain, base, ask_now, checks["student_count"]
        )
        cube_at = refreshed[-1] if refreshed else None
```

Replace `_ask_cube` with a version that asks once per filter set:

```python
def _ask_cube(sheet, grain, measures, load, filters, student) -> dict[str, Answer]:
    """Each measure's raw values at the grain by both of Cube's routes: with the
    student count (read from the fact) and alone (often served by a rollup). One
    pair of queries per distinct set of measure filters."""
    by_filters: dict[str, list[str]] = {}
    for m in measures:
        key = json.dumps(sheet.measures[m].cube_filters, sort_keys=True)
        by_filters.setdefault(key, []).append(m)
    out: dict[str, Answer] = {}
    for key, ms in by_filters.items():
        f = filters + json.loads(key)
        members = [sheet.measures[m].cube for m in ms]
        rows, rollups = load(cube_query(sheet, grain, [*members, student], f))
        alone_rows, rollups_alone = load(cube_query(sheet, grain, members, f))
        fact, alone = _by_key(rows, sheet, grain), _by_key(alone_rows, sheet, grain)
        for m in ms:
            cube = sheet.measures[m].cube
            out[m] = Answer(
                {k: _num(r.get(cube)) for k, r in fact.items()},
                {k: _num(r.get(cube)) for k, r in alone.items()},
                {k: _int(r.get(student)) for k, r in fact.items()},
                list(rollups),
                list(rollups_alone),
            )
    return out
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a measure can carry its own Cube filters and extract condition"
```

### Task 25 (confirmed 2026-10-13): a measure that is the difference of two mapped measures

The user confirmed this task on 2026-10-13 (see _Confirmed with the user_).

**Files:**

- Modify: `scripts/cube_validate.py` (`Measure`, `_measure`, `load_checks`,
  `_ask_cube`, `_compare_grain`, `_extract_measure`, `_cube_queries`,
  `_cube_measure`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `Measure.diff: tuple[str, str] | None` (YAML `diff: [A, B]`: A minus B, both
    plain measures on the same sheet; no `cube:` or variants of its own)
  - `_minus(a: dict, b: dict) -> dict` (None where either side is None)
  - `_has_cube(sheet, meas) -> bool`

- [ ] **Step 1: Write the failing test**

```python
def test_a_difference_of_two_measures_is_compared_and_reproduced(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    ms = d["sheets"]["Overview - Table"]["measures"]
    for name, flag, cond in (("IEP", "true", "is_iep"), ("Gen Ed", "false", "not is_iep")):
        ms[name] = {
            "cube": "demo.avg_score", "sql": "avg(score)", "round": 2,
            "cube_filters": [{"member": "demo.is_iep", "operator": "equals", "values": [flag]}],
            "where": cond,
        }
    ms["Diff"] = {"diff": ["IEP", "Gen Ed"], "round": 2}
    c = cv.load_checks(_write(tmp_path, d))
    sheet = c["sheets"]["Overview - Table"]

    def load(q):
        iep = {"member": "demo.is_iep", "operator": "equals", "values": ["true"]} in q["filters"]
        return [{"demo.school": "Alpha", "demo.avg_score": "40" if iep else "48.5",
                 "demo.count_students": "20"}], []

    export = cv.read_export(b"School Name,Diff\r\nAlpha,-8.50\r\n")
    assert [x.status for x in cv.compare_export(sheet, "s1", export, load, [], [], c)] == ["match"]

    def run(ds, sql):
        return [{"g0": "Alpha", "m": 48.5 if "NOT" in sql.upper() else 40.0}]

    ext = cv._extract_measure(sheet, sheet.measures["Diff"], ("School Name",), [], run)
    assert ext == {("Alpha",): -8.5}


def test_a_diff_must_name_two_plain_measures_on_its_sheet(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["measures"]["Diff"] = {"diff": ["Avg Score", "Nope"]}
    with pytest.raises(cv.CheckError, match="diff names 2 plain measures"):
        cv.load_checks(_write(tmp_path, d))
```

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, `give sql, or num and den`.

- [ ] **Step 3: Implement**

Add `diff: tuple[str, str] | None = None` as the last field of `Measure`, pass
`tuple(m["diff"]) if m.get("diff") else None` in `_measure`, and let a diff
stand in for SQL: change the first check to
`if not m.get("sql") and not (m.get("num") and m.get("den")) and not m.get("diff"):`
with the message `give sql, num and den, or diff`. In `load_checks`, after each
sheet's `measures` are built:

```python
        for c, meas in measures.items():
            if not meas.diff:
                continue
            parts = [measures.get(x) for x in meas.diff]
            if len(meas.diff) != 2 or any(p is None or p.diff for p in parts):
                raise CheckError(f"{name} / {c}: diff names 2 plain measures on this sheet")
            if meas.variants:
                raise CheckError(f"{name} / {c}: a diff measure takes no variants")
```

Add the helpers:

```python
def _minus(a: dict, b: dict) -> dict:
    return {
        k: None if a.get(k) is None or b.get(k) is None else a[k] - b[k]
        for k in a.keys() | b.keys()
    }


def _has_cube(sheet, meas) -> bool:
    if meas.diff:
        return all(sheet.measures[x].cube for x in meas.diff)
    return meas.cube is not None
```

In `_compare_grain`, use
`asked = [m for m in measures if _has_cube(sheet, sheet.measures[m])]`.

In `_ask_cube`, ask the parts and build each difference from them: rename the
parameter `measures` to `wanted`, start with
`measures = list(dict.fromkeys(x for m in wanted for x in (sheet.measures[m].diff or (m,))))`,
and before returning:

```python
    for m in wanted:
        d = sheet.measures[m].diff
        if d:
            a, b = out[d[0]], out[d[1]]
            out[m] = Answer(
                _minus(a.fact, b.fact), _minus(a.alone, b.alone), a.students,
                sorted({*a.rollups, *b.rollups}),
                sorted({*a.rollups_alone, *b.rollups_alone}),
            )
    return {m: out[m] for m in wanted}
```

Give the extract and Cube helpers a diff branch, first thing in each:

```python
    # in _extract_measure
    if meas.diff:
        a, b = (_extract_measure(sheet, sheet.measures[x], grain, where, run) for x in meas.diff)
        return _minus(a, b)

    # in _cube_queries
    if meas.diff:
        return [q for x in meas.diff for q in _cube_queries(sheet, sheet.measures[x], grain, filters, student)]

    # in _cube_measure
    if meas.diff:
        (a, n), (b, _) = (
            _cube_measure(sheet, sheet.measures[x], grain, filters, ask, student)
            for x in meas.diff
        )
        return _minus(a, b), n
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): a measure can be the difference of two mapped measures"
```

### Task 26: a group shown as a dimension is compared bin by bin (gap 4)

**Files:**

- Modify: `scripts/cube_validate.py` (`compare_export`, `_compare_grain`,
  `extract_sql`, `counts_sql`, `_extract_measure`, `_variant`, `_trust`,
  `_explain_batch`, `issue_drafts`, `run_compare`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `Lists.groups` (Tasks 4 and 5).
- Produces:
  - `compare_export(..., checks, lists: Lists | None = None)`
  - `_ask_by_bin(sheet, grain, measures, load, filters, student, lists) -> dict[str, Answer]`
  - `_dim_sql(sheet, d, lists=None) -> str` (a group becomes a CASE over its
    bins' members)
  - `extract_sql(sheet, meas, grain, where, lists=None)`,
    `counts_sql(sheet, grain, where, student, lists=None)`,
    `_extract_measure(sheet, meas, grain, where, run, lists=None)`

- [ ] **Step 1: Write the failing test**

```python
BANDS = {
    "Band (group)": {
        "datasource": DS,
        "field": "band",
        "bins": {"Low": ["1", "2"], "High": ["3"]},
    }
}


def test_a_group_dimension_asks_cube_once_per_bin(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["dims"]["Band (group)"] = {"cube": "demo.band", "sql": "band"}
    c = cv.load_checks(_write(tmp_path, d))
    sheet = c["sheets"]["Overview - Table"]
    lists = cv.Lists({}, BANDS)

    def load(q):
        (vals,) = [f["values"] for f in q["filters"] if f.get("member") == "demo.band"]
        return [{"demo.avg_score": "40" if vals == ["1", "2"] else "60",
                 "demo.count_students": "20"}], []

    export = cv.read_export(b"Band (group),Avg Score\r\nLow,40.00\r\nHigh,60.00\r\n")
    cells = cv.compare_export(sheet, "s1", export, load, [], [], c, lists)
    assert [x.status for x in cells] == ["match", "match"]
    sql = cv.extract_sql(sheet, sheet.measures["Avg Score"], ["Band (group)"], [], lists=lists)
    assert "case when cast(band as string) in ('1', '2') then 'Low'" in sql
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k group_dimension 2>&1 | tail -n 30`
Expected: FAIL, `compare_export` takes no `lists`.

- [ ] **Step 3: Implement**

Add after `_ask_cube`:

```python
def _ask_by_bin(sheet, grain, measures, load, filters, student, lists) -> dict[str, Answer]:
    """Answers at a grain holding a group dimension: one set of queries per bin,
    filtered to its members, since counts and rates do not add up across members.
    Raw values: the caller rebuilds table calculations after the bins merge."""
    i = next((i for i, d in enumerate(grain) if d in lists.groups), None)
    if i is None:
        return _ask_cube(sheet, grain, measures, load, filters, student)
    d, rest = grain[i], [*grain[:i], *grain[i + 1:]]
    out: dict[str, Answer] = {}
    for b, members in lists.groups[d]["bins"].items():
        if not members:
            continue
        only = {"member": sheet.dims[d].cube, "operator": "equals",
                "values": [str(v) for v in members]}
        part = _ask_by_bin(sheet, rest, measures, load, [*filters, only], student, lists)
        for m, a in part.items():
            o = out.setdefault(m, Answer({}, {}, {}, [], []))
            for mine, theirs in ((o.fact, a.fact), (o.alone, a.alone), (o.students, a.students)):
                mine.update({(*k[:i], norm_dim(b), *k[i:]): v for k, v in theirs.items()})
            o.rollups = sorted({*o.rollups, *a.rollups})
            o.rollups_alone = sorted({*o.rollups_alone, *a.rollups_alone})
    return out


def _dim_sql(sheet, d, lists=None) -> str:
    """A dimension's extract SQL; a group becomes a CASE over its bins' members."""
    sql = sheet.dims[d].sql
    g = (lists.groups if lists else {}).get(d)
    if not g:
        return sql
    whens = " ".join(
        f"when cast({sql} as string) in ({', '.join(_sql_lit(v) for v in members)}) "
        f"then {_sql_lit(b)}"
        for b, members in g["bins"].items()
        if members
    )
    return f"case {whens} end"
```

Add the parameter `lists=None` to `compare_export` and pass it to
`_compare_grain(..., student, lists)`; in `_compare_grain`, add the parameter
`lists=None` and call
`raw = _ask_by_bin(sheet, grain, asked, load, filters, student, lists or Lists())`.

In `extract_sql` and `counts_sql`, add the parameter `lists=None` and build each
grain column as `f"{_dim_sql(sheet, d, lists)} as g{i}"`. In `_extract_measure`,
add `lists=None` and pass it to `extract_sql` (and to the diff branch's
recursion, if Task 25 shipped). Pass `lists` at every call site: `_variant` (add
the parameter), `_trust` and `_explain_batch` (`_extract_measure`, `counts_sql`,
`_variant`), `issue_drafts` (`extract_sql`), and `run_compare`
(`compare_export(..., checks, lists)`).

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): compare a group shown as a dimension bin by bin"
```

### Task 27 (skipped, user ruling 2026-10-13): `fixed:`, a ratio per fixed group averaged per mark

The user ruled on 2026-10-13 to skip this task: `Avg. % Completion` stays
unmapped. It stays here for a later dashboard that needs `fixed:`.

**Files:**

- Modify: `scripts/cube_validate.py` (`Measure`, `_measure`, `_extract_measure`,
  `_ask_cube`, `_cube_measure`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `Measure.fixed: list[dict]` (each `{cube, sql}`),
    `Measure.weight: str | None` (a Cube count of the extract's rows); a fixed
    measure needs `num`, `den`, `fixed` and `weight`, and its `cube:` is the
    ratio member
  - `fixed_sql(sheet, meas, grain, where, ds_where, lists=None) -> str`
  - `_datasource_where(checks, sheet) -> list[str]` (the extract filters for the
    datasource and the sheet: what a FIXED calculation still sees)
  - `_cube_fixed(sheet, meas, grain, filters, hard, ask) -> dict`
  - `_extract_measure(..., lists=None, ds_where=())`

- [ ] **Step 1: Write the failing test**

```python
def test_a_fixed_ratio_is_averaged_over_the_marks_rows(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Overview - Table"]["measures"]["Avg Done"] = {
        "cube": "demo.pct_complete",
        "num": "count(distinct if(is_complete = 1, student_number, null))",
        "den": "count(distinct student_number)",
        "fixed": [{"cube": "demo.grade_level", "sql": "grade_level"}],
        "weight": "demo.count_assigned",
    }
    c = cv.load_checks(_write(tmp_path, d))
    sheet = c["sheets"]["Overview - Table"]
    meas = sheet.measures["Avg Done"]
    sql = cv.fixed_sql(sheet, meas, ["School Name"], ["region = 'North'"], ["not is_test"])
    # The group ratio sees only the datasource filters; the mark's rows see the state's.
    inner = sql[sql.index("join (") : sql.index(") as f")]
    assert "not is_test" in inner and "region = 'North'" not in inner
    assert "avg(f.fixed_r) as m" in sql

    def ask(q):
        if q["dimensions"] == ["demo.grade_level"]:  # the ratio per fixed group
            return [{"demo.grade_level": "5", "demo.pct_complete": "0.5"},
                    {"demo.grade_level": "6", "demo.pct_complete": "1.0"}]
        return [  # the mark's row count per group
            {"demo.school": "Alpha", "demo.grade_level": "5", "demo.count_assigned": "30"},
            {"demo.school": "Alpha", "demo.grade_level": "6", "demo.count_assigned": "10"},
        ]

    out = cv._cube_fixed(sheet, meas, ["School Name"], [], [], ask)
    assert out == {("Alpha",): pytest.approx((30 * 0.5 + 10 * 1.0) / 40)}
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k fixed_ratio 2>&1 | tail -n 30`
Expected: FAIL, `Measure` takes no `fixed`.

- [ ] **Step 3: Implement**

Add to `Measure`, last: `fixed: list[dict] = field(default_factory=list)` and
`weight: str | None = None`; pass `list(m.get("fixed") or [])` and
`m.get("weight")` in `_measure`, and reject an incomplete one:

```python
    if m.get("fixed") and not (m.get("num") and m.get("den") and m.get("weight")):
        raise CheckError(f"{where} / {caption}: fixed needs num, den and weight")
```

Add:

```python
def _datasource_where(checks, sheet) -> list[str]:
    """The extract filters a FIXED calculation still sees: the datasource's and
    the sheet's hard filters, never the state's or the saved dimension filters."""
    return [
        f["sql"]
        for f in [*checks["extract_filters"], *sheet.extract_filters]
        if f.get("datasource") in (None, sheet.datasource)
    ]


def fixed_sql(sheet, meas, grain, where, ds_where, lists=None) -> str:
    """Tableau's AVG over a FIXED ratio: the ratio per fixed group under the
    datasource filters only, averaged over the mark's rows, so a group with more
    rows weighs more."""
    keys = [f["sql"] for f in meas.fixed]
    inner = (
        f"select {', '.join(f'{k} as fixed_k{i}' for i, k in enumerate(keys))}, "
        f"(1.0 * ({meas.num})) / nullif(({meas.den}), 0) as fixed_r "
        f"from `{EXTRACT_TABLE}`"
    )
    if ds_where:
        inner += " where " + " and ".join(f"({w})" for w in ds_where)
    inner += " group by " + ", ".join(str(i + 1) for i in range(len(keys)))
    on = " and ".join(f"({k}) is not distinct from f.fixed_k{i}" for i, k in enumerate(keys))
    sel = [f"{_dim_sql(sheet, d, lists)} as g{i}" for i, d in enumerate(grain)]
    sel.append("avg(f.fixed_r) as m")
    # trunk-ignore(bandit/B608): SQL over the dashboard's own extract or rpt_ table; names come from the checks file
    sql = f"select {', '.join(sel)} from `{EXTRACT_TABLE}` join ({inner}) as f on {on}"
    if where:
        sql += " where " + " and ".join(f"({w})" for w in where)
    if grain:
        sql += " group by " + ", ".join(str(i + 1) for i in range(len(grain)))
    return sql


def _cube_fixed(sheet, meas, grain, filters, hard, ask) -> dict:
    """Cube's side of a FIXED ratio averaged per mark: the ratio per fixed group
    under the hard filters only, weighted by the group's row count in the mark."""
    fixed = [f["cube"] for f in meas.fixed]
    ratio_q = {"measures": [meas.cube], "dimensions": fixed,
               "filters": hard + meas.cube_filters, "limit": CUBE_LIMIT}
    ratio = {tuple(norm_dim(r.get(m)) for m in fixed): _num(r.get(meas.cube)) for r in ask(ratio_q)}
    weight_q = cube_query(sheet, grain, [meas.weight], filters + meas.cube_filters)
    weight_q["dimensions"] += [m for m in fixed if m not in weight_q["dimensions"]]
    sums: dict[tuple, list[float]] = {}
    for r in ask(weight_q):
        k = tuple(cube_key(r, sheet.dims[d]) for d in grain)
        x = ratio.get(tuple(norm_dim(r.get(m)) for m in fixed))
        w = _num(r.get(meas.weight)) or 0.0
        if x is None or not w:
            continue  # Tableau's AVG skips a null ratio
        s = sums.setdefault(k, [0.0, 0.0])
        s[0] += w * x
        s[1] += w
    return {k: s[0] / s[1] for k, s in sums.items() if s[1]}
```

Wire them in:

- `_extract_measure`: add `ds_where=()`; when `meas.fixed`, run
  `fixed_sql(sheet, meas, grain, where, ds_where, lists)` and return
  `extract_values(rows, len(grain))`. `_trust` and `_explain_batch` pass
  `ds_where=_datasource_where(checks, sheet)`.
- `_cube_measure`: when `meas.fixed`, return
  `_cube_fixed(sheet, meas, grain, filters, [], ask), {}`. `filters` already
  holds the hard filters at this point, so the ratio query gets `[]` plus the
  measure's own; pass `hard_filters(checks, sheet)` instead where `checks` is in
  reach (`_explain_batch` passes it through a new `hard=` keyword).
- `_ask_cube`: answer a fixed measure with
  `v = _cube_fixed(sheet, meas, grain, filters, hard, lambda q: load(q)[0])` and
  `Answer(v, v, {}, [], [])`: one route only, since the weight query always
  reads the fact. Add a `hard` parameter, passed from `_compare_grain` (which
  gets it from `compare_export` as `hard_filters(checks, sheet)`) through
  `_ask_by_bin` and its recursion.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): fixed: compares a FIXED ratio averaged over a mark's rows"
```

---

## Part E: outputs and follow-up

### Task 28: Investigate rows split by gap, with runnable SQL (I1, I3)

**Files:**

- Modify: `scripts/cube_validate.py` (`digest_markdown`, `write_outputs`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - `digest_markdown(workbook, cells, checks, states=None, fields=None, defaults=None, sheet_filters=None, lists=None) -> str`
  - `_typical_gap(cells) -> str` (the median of |Cube - Tableau| / |Tableau|)
  - `_investigate_sql(c, checks, states, fields, defaults, sheet_filters, lists) -> list[str]`

- [ ] **Step 1: Write the failing test**

```python
def test_investigate_rows_split_by_gap_with_runnable_sql(tmp_path):
    c, cells, states = _explained(tmp_path)
    fail = cells[2]
    fail.key, fail.tableau, fail.cube, fail.gap = {"School Name": "Beta"}, 9.0, 8.0, "row gap"
    text = cv.digest_markdown("Demo", cells, c, states, {})
    assert "### Row gaps" in text and "typical gap 11.1%" in text
    assert "from `EXTRACT_TABLE`" in text
    assert "from `teamster-332318.kipptaf_tableau.rpt_demo`" in text
```

- [ ] **Step 2: Run it to verify it fails**

Run:
`uv run --with tableauhyperapi pytest tests/scripts/test_cube_validate.py -q -p no:cacheprovider -k investigate_rows 2>&1 | tail -n 30`
Expected: FAIL, `digest_markdown` takes 3 positional arguments.

- [ ] **Step 3: Implement**

Add `import statistics` to the imports. Add before `digest_markdown`:

````python
def _typical_gap(cells) -> str:
    """The median gap between Cube and Tableau, relative to what Tableau shows: a
    0.3% shortfall everywhere reads differently from a 20-point cell."""
    rel = [
        abs(c.cube - c.tableau) / abs(c.tableau)
        for c in cells
        if c.cube is not None and c.tableau
    ]
    return f"{statistics.median(rel):.1%}" if rel else "unknown"


def _investigate_sql(c, checks, states, fields, defaults, sheet_filters, lists) -> list[str]:
    """The trusted extract SQL for a fail cell, and the same SQL on the live table."""
    sheet = checks["sheets"][c.sheet]
    where, _ = _slice(states[c.state], c.sheet, checks, fields, defaults,
                      sheet_filters, lists, public_only=True)
    sql = extract_sql(sheet, sheet.measures[c.measure], list(_grain(c)[0]), where, lists=lists)
    try:
        live = sql.replace(f"`{EXTRACT_TABLE}`", f"`{live_table(sheet.datasource)}`")
    except CheckError as err:
        live = f"-- {err}"
    return [
        "", "  Over the extract (what Tableau showed):", "", "  ```sql", f"  {sql}",
        "  ```", "", "  Over the live table:", "", "  ```sql", f"  {live}", "  ```",
    ]
````

If Task 25 shipped, `_investigate_sql` prints one pair of blocks per part of a
`diff` measure; if Task 27 shipped, it builds a `fixed` measure's SQL with
`fixed_sql`.

Change `digest_markdown`'s signature to the one above and replace its
`fails = ...` block with:

```python
    fails = _coarsest([c for c in cells if c.verdict == "fail"])
    if fails:
        lines += ["", "## Investigate"]
        for gap, title in (
            ("row gap", "Row gaps: Cube and the live table count different students"),
            ("formula gap", "Formula gaps: the same students, a different value"),
            ("", "No live check"),
        ):
            mine = [c for c in fails if c.gap == gap]
            if not mine:
                continue
            lines += ["", f"### {title}", ""]
            by: dict[tuple, list[Cell]] = {}
            for c in mine:
                by.setdefault((c.sheet, c.measure), []).append(c)
            for (sheet, measure), cs in sorted(by.items(), key=lambda x: -len(x[1])):
                lines.append(f"- {sheet} / {measure}: {len(cs)} cells, typical gap {_typical_gap(cs)}")
                lines += [f"  - {_example(c, checks)}" for c in cs[:3]]
                if states is not None:
                    lines += _investigate_sql(cs[0], checks, states, fields or {},
                                              defaults, sheet_filters, lists)
```

In `write_outputs`, call
`digest_markdown(workbook, cells, checks, states, fields, defaults, sheet_filters, lists)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): Investigate rows group fails by gap and print SQL to run"
```

### Task 29: every draft carries a "Check it yourself" block

**Files:**

- Modify: `scripts/cube_validate.py` (`issue_drafts`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Consumes: `_slice` (Task 15), `_cube_queries` (Task 24).
- Produces: `_public_filters(filters: list[dict], checks: dict) -> list[dict]`
  (a person's values become their label)

- [ ] **Step 1: Write the failing tests**

```python
def test_a_draft_carries_a_check_it_yourself_block(tmp_path):
    c, cells, states = _explained(tmp_path)
    body = cv.issue_drafts("Demo", cells, c, states, {})["dup"]
    assert "## Check it yourself" in body and "lastRefreshTime" in body
    assert '"demo.avg_score"' in body
    assert "`teamster-332318.kipptaf_tableau.rpt_demo`" in body


def test_check_it_yourself_hides_person_values(tmp_path):
    c, cells, states = _explained(tmp_path)
    c["filters"]["Student"] = {"cube": "demo.student", "person": True}
    states["s"]["state"]["filters"] = {"Student": "Real Name"}
    body = cv.issue_drafts("Demo", cells, c, states, {})["dup"]
    assert "Real Name" not in body and '"a student"' in body
```

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, no "Check it yourself".

- [ ] **Step 3: Implement**

Add before `issue_drafts`:

```python
def _public_filters(filters: list[dict], checks: dict) -> list[dict]:
    """Cube filters fit to leave the terminal: a person's values become their label."""
    members = _caption_members(checks)
    label = {members[c]: lab for c, lab in _person_captions(checks).items() if c in members}
    return [
        {**f, "values": [label[f["member"]]]} if f.get("member") in label and f.get("values") else f
        for f in filters
    ]


_CHECK_YOURSELF = (
    "Both queries below read live data, so they agree once the fix is in. Before "
    "you compare them, check that Cube's `lastRefreshTime` (in its `/load` answer) "
    "is not older than the table's last-modified time; if either is behind, wait "
    "and run both again. The dashboard's numbers above are evidence, not the test. "
    "A fix inside the Tableau workbook is checked only by the analyst's next export."
)
```

In `issue_drafts`, replace `where, _ = _slice(...)` with
`where, cube_filters = _slice(...)` (same arguments), and after
`query = extract_sql(...)` add:

```python
        cube_qs = _cube_queries(sheet, meas, grain, _public_filters(cube_filters, checks))
        try:
            live_sql = query.replace(f"`{EXTRACT_TABLE}`", f"`{live_table(sheet.datasource)}`")
        except CheckError as err:
            live_sql = f"-- {err}"
```

Insert these lines into `body`, right before `"## Where",`:

````python
            "## Check it yourself",
            "",
            _CHECK_YOURSELF,
            "",
            "Cube `/load`:",
            "",
            "```json",
            *(json.dumps({"query": q}, indent=2) for q in cube_qs),
            "```",
            "",
            "The same measure on the live table:",
            "",
            "```sql",
            live_sql,
            "```",
            "",
````

and change the "For Claude" note to:
`f"> Checks file `.claude/skills/cube-dashboard/checks/{_slug(workbook)}.yml`, mismatch `{s}`. A builder verifies with 'Check it yourself'; the analyst's follow-up run confirms the cells turn `pass`."`

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): each issue draft tells a builder how to check the fix live"
```

### Task 30: `export --for <mismatch>`, and `latest.json` replaces a dashboard's entries

**Files:**

- Modify: `scripts/cube_validate_snapshot.py` (`_states_for`, `_open`,
  `_export`, `main`)
- Modify: `scripts/cube_validate.py` (`write_latest`)
- Test: both test files

**Interfaces:**

- Produces:
  - `states_for_mismatch(workbook: str, mismatch: str, root: Path = SNAPSHOT_ROOT) -> list[State]`
    (from the newest snapshot whose cells name the mismatch)
  - `_states_for(checks, path, mismatch=None)`; `export <checks> --for <slug>`
  - `write_latest` drops every entry whose `dashboard` is this workbook before
    adding the run's rows.

- [ ] **Step 1: Write the failing tests**

Snapshot side (add `import json` to the test file's imports):

```python
def test_export_for_a_mismatch_lists_the_states_behind_its_cells(tmp_path):
    old = tmp_path / "demo" / "2026-10-09T2236"
    new = tmp_path / "demo" / "2026-10-14T1000"  # a fresh session, nothing compared yet
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    north = snap.State("Overview", filters=(("Region", "North"),))
    m = _manifest()
    m.states = {
        north.id: {"state": north.as_dict(), "status": "ok"},
        "overview--default": {"state": snap.State("Overview").as_dict(), "status": "ok"},
    }
    snap.write_manifest(old / "manifest.json", m)
    (old / "cells.jsonl").write_text(
        json.dumps({"state": north.id, "explained_by": ["dup"]}) + "\n"
        + json.dumps({"state": "overview--default", "explained_by": []}) + "\n"
    )
    assert snap.states_for_mismatch("Demo", "dup", tmp_path) == [north]
    with pytest.raises(snap.SessionError, match="nope"):
        snap.states_for_mismatch("Demo", "nope", tmp_path)
```

Cube side:

```python
def test_a_run_replaces_every_entry_for_its_dashboard(tmp_path):
    p = tmp_path / "latest.json"
    p.write_text(json.dumps({
        "888": {"verdict": "pass", "dashboard": "Demo"},  # a corrected row id
        "999": {"verdict": "fail", "dashboard": "Other"},
    }))
    cv.write_latest(p, "Demo", "2026-10-14", {"111": {"verdict": "pass"}})
    assert sorted(json.loads(p.read_text())) == ["111", "999"]
```

- [ ] **Step 2: Run them to verify they fail**

Run both test files. Expected: FAIL, no attribute `states_for_mismatch`; `888`
survives.

- [ ] **Step 3: Implement**

Snapshot side, after `_states_for`:

```python
def states_for_mismatch(workbook: str, mismatch: str, root: Path = SNAPSHOT_ROOT) -> list[State]:
    """The states behind a mismatch's cells, from the newest snapshot that explained
    it, so a follow-up exports only those."""
    base = Path(root) / slug(workbook)
    dirs = sorted((p for p in base.iterdir() if p.is_dir()), reverse=True) if base.exists() else []
    for snapdir in dirs:
        path = snapdir / "cells.jsonl"
        if not path.exists():
            continue
        cells = [json.loads(line) for line in path.read_text().splitlines() if line]
        ids = sorted({c["state"] for c in cells if mismatch in (c.get("explained_by") or [])})
        if ids:
            m = read_manifest(snapdir / "manifest.json")
            return [State.from_dict(m.states[i]["state"]) for i in ids if i in m.states]
    raise SessionError(f"no snapshot under {base} has cells explained by {mismatch}")
```

Give `_states_for` a `mismatch: str | None = None` parameter that returns
`states_for_mismatch(checks["workbook"], mismatch)` when set. In `main`, give
`export` the option
`s.add_argument("--for", dest="mismatch", help="export the states behind a mismatch's cells")`,
and in `_export` call `_states_for(checks, a.states, a.mismatch)`.

Cube side, in `write_latest`, right after reading `data`:

```python
    # A run replaces its dashboard's entries, so a corrected row id leaves none stale.
    data = {gid: r for gid, r in data.items() if r.get("dashboard") != workbook}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass; `test_write_latest_merges_rows` keeps
its entry, which names no dashboard.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate_snapshot.py scripts/cube_validate.py tests/scripts/test_cube_validate.py tests/scripts/test_cube_validate_snapshot.py
git commit -m "feat(cube): export --for a mismatch; latest.json replaces a dashboard's rows"
```

---

## Part F: Asana rows

### Task 31: rows keyed by dashboard, sheet and caption, with `rows_deferred:`

**Files:**

- Modify: `scripts/cube_validate.py` (`load_checks`, `row_results`,
  `write_outputs`)
- Test: `tests/scripts/test_cube_validate.py`

**Interfaces:**

- Produces:
  - checks file: `rows: {gid: {dashboard, sheet, measure | dimension}}` (or a
    list of those), `rows_deferred: {gid: reason}`, `asana_task: <gid>`
  - `load_checks` returns `rows` as `{gid: [target, ...]}` and `rows_deferred`
  - `row_results(cells, checks, states=None) -> dict[str, dict]`: a measure row
    takes the worst of its sheet's cells for that measure; a dimension row the
    worst of every cell grouped by that dimension.

- [ ] **Step 1: Update the fixtures and write the failing tests**

In `CHECKS`, replace `"rows": {"111": ["demo.avg_score"]}` with:

```python
    "rows": {"111": {"dashboard": "Overview", "sheet": "Overview - Table", "measure": "Avg Score"}},
```

In `REPLAY`, replace `rows` with:

```python
    "rows": {
        gid: {"dashboard": "Replay", "sheet": "Sheet", "measure": m}
        for gid, m in (
            ("1", "% Complete"), ("2", "% Completion"), ("3", "Students Tested"),
            ("4", "Students Assessed"), ("5", "Avg Score"),
        )
    },
```

In `test_row_results_take_the_worst_cell_of_the_rows_members`, pass
`rows={"111": {"dashboard": "Overview", "sheet": "Overview - Table", "measure": "Avg Score"}, "222": {"dashboard": "Overview", "sheet": "Overview - Table", "measure": "% Complete"}}`.
Replace `test_load_checks_rows_must_name_mapped_members` with:

```python
def test_rows_name_dashboard_sheet_and_a_mapped_caption(tmp_path):
    with pytest.raises(cv.CheckError, match="Nope is not mapped"):
        _checks(tmp_path, rows={"111": {"dashboard": "Overview", "sheet": "Overview - Table", "measure": "Nope"}})
    with pytest.raises(cv.CheckError, match="Cube members no longer key a row"):
        _checks(tmp_path, rows={"111": ["demo.avg_score"]})
    with pytest.raises(cv.CheckError, match="both checked and deferred"):
        _checks(tmp_path, rows_deferred={"111": "lives on the Landing Page"})
    with pytest.raises(cv.CheckError, match="needs a reason"):
        _checks(tmp_path, rows_deferred={"333": ""})


def test_two_rows_on_one_member_are_judged_on_their_own_sheets(tmp_path):
    d = json.loads(json.dumps(CHECKS))
    d["sheets"]["Other - Table"] = d["sheets"]["Overview - Table"]
    d["rows"] = {
        "111": {"dashboard": "Overview", "sheet": "Overview - Table", "measure": "Avg Score"},
        "222": {"dashboard": "Overview", "sheet": "Other - Table", "measure": "Avg Score"},
    }
    c = cv.load_checks(_write(tmp_path, d))

    def cell(sheet, verdict):
        return cv.Cell(sheet, "s", {}, "Avg Score", "1", 1, 1, 20, "match", verdict=verdict)

    rows = cv.row_results([cell("Overview - Table", "pass"), cell("Other - Table", "fail")], c)
    assert (rows["111"]["verdict"], rows["222"]["verdict"]) == ("pass", "fail")


def test_a_dimension_row_passes_only_when_every_cell_grouped_by_it_passes(tmp_path):
    row = {"dashboard": "Overview", "sheet": "Overview - Table", "dimension": "School Name"}
    c = _checks(tmp_path, rows={"444": row})

    def cell(key, verdict):
        return cv.Cell("Overview - Table", "s", key, "Avg Score", "1", 1, 1, 20, "match",
                       verdict=verdict)

    cells = [
        cell({"School Name": "Alpha"}, "pass"),
        cell({"School Name": "Beta"}, "undecided"),
        cell({"School Name": "All"}, "fail"),  # a total is not grouped by the school
        cell({}, "fail"),
    ]
    assert cv.row_results(cells, c)["444"]["verdict"] == "undecided"
```

- [ ] **Step 2: Run them to verify they fail**

Run the Cube-side test file. Expected: FAIL, the old member-keyed validation.

- [ ] **Step 3: Implement**

Replace the `rows` validation in `load_checks` (the `members = {...}` /
`for gid, ms in ...` block) with a call to:

```python
def _rows(raw: dict, sheets: dict) -> tuple[dict[str, list[dict]], dict[str, str]]:
    """Asana rows keyed by caption. Two rows can share a Cube member, so each names
    its dashboard, sheet, and a measure or dimension caption mapped there."""
    out: dict[str, list[dict]] = {}
    dashboards = raw.get("dashboards")
    for gid, targets in (raw.get("rows") or {}).items():
        targets = targets if isinstance(targets, list) else [targets]
        for t in targets:
            if not isinstance(t, dict) or not t.get("dashboard"):
                raise CheckError(
                    f"row {gid}: name dashboard, sheet, and measure or dimension "
                    "(Cube members no longer key a row)"
                )
            if dashboards and t["dashboard"] not in dashboards:
                raise CheckError(f"row {gid}: {t['dashboard']} is not a listed dashboard")
            s = sheets.get(t.get("sheet"))
            if s is None:
                raise CheckError(f"row {gid}: sheet {t.get('sheet')} is not mapped")
            if ("measure" in t) == ("dimension" in t):
                raise CheckError(f"row {gid}: give a measure or a dimension")
            caption = t.get("measure") or t.get("dimension")
            if caption not in (s.measures if "measure" in t else s.dims):
                raise CheckError(f"row {gid}: {caption} is not mapped on {t['sheet']}")
        out[str(gid)] = targets
    deferred = {str(k): v for k, v in (raw.get("rows_deferred") or {}).items()}
    for gid, why in deferred.items():
        if not (isinstance(why, str) and why.strip()):
            raise CheckError(f"row {gid}: rows_deferred needs a reason")
        if gid in out:
            raise CheckError(f"row {gid} is both checked and deferred")
    return out, deferred
```

and return `"rows": rows, "rows_deferred": deferred` from `load_checks`, with
`rows, deferred = _rows(raw, sheets)`.

Replace `row_results`:

```python
def _in_row(c: Cell, t: dict, states: dict | None) -> bool:
    if c.sheet != t["sheet"]:
        return False
    if states is not None:
        dash = ((states.get(c.state) or {}).get("state") or {}).get("dashboard")
        if dash != t["dashboard"]:
            return False
    if "measure" in t:
        return c.measure == t["measure"]
    return c.key.get(t["dimension"], TOTAL) != TOTAL


def row_results(cells, checks, states=None) -> dict[str, dict]:
    by_cell = _members(checks)
    out = {}
    for gid, targets in checks["rows"].items():
        mine = [
            c for c in cells if c.verdict and any(_in_row(c, t, states) for t in targets)
        ]
        reopen = sorted(
            {
                mm
                for c in mine
                if c.verdict == "missing_member" and (c.sheet, c.measure) in by_cell
                for mm in by_cell[(c.sheet, c.measure)].missing_members
            }
        )
        out[gid] = {
            "verdict": worst(c.verdict for c in mine),
            "cells": len(mine),
            "by_verdict": dict(Counter(c.verdict for c in mine)),
            "mismatches": sorted({n for c in mine for n in c.explained_by}),
            "reopen_for": reopen,
        }
    return out
```

In `write_outputs`, call `row_results(cells, checks, states)`.

- [ ] **Step 4: Run the tests to verify they pass**

Run the full suite. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/cube_validate.py tests/scripts/test_cube_validate.py
git commit -m "feat(cube): Asana rows name their dashboard, sheet and caption"
```

---

## Part G: the runbook

### Task 32: rewrite the `cube-dashboard` skill around the new session order

**Files:**

- Modify: `.claude/skills/cube-dashboard/SKILL.md` (open it with the Read tool)
- Modify: `scripts/CLAUDE.md` (the 2 catalog rows; open it with the Read tool)

No code, so no test cycle. The check is lint plus a read-through against the
spec revision.

- [ ] **Step 1: Replace everything below the front matter of `SKILL.md`**

Keep the front matter as it is. Replace the body with:

````markdown
# cube-dashboard

Truth is what Tableau shows. A review copy of the workbook is published to
TEMP-CB, each state a person can reach is exported, Cube is compared with each
export, and SQL over the dashboard's own extract explains each gap. Design:
`docs/superpowers/specs/2026-10-09-cube-validate-tableau-truth-design.md`; its
last revision section is binding.

## Running a step that needs credentials

`open`, `export`, `close`, `map`, `compare` and `explain` need the Tableau PAT
or `CUBE_API_SECRET`. Only the pytest secrets fixture provides them. Write this
throwaway file, change `ARGS`, run it, and delete it after the session:

```python
# tests/test_zz_cube_validate.py: throwaway, never committed
import importlib.util
import sys
from pathlib import Path

CHECKS = ".claude/skills/cube-dashboard/checks/<dashboard>.yml"
ARGS = ("cube_validate_snapshot", ["open", CHECKS])


def _load(name):
    path = Path(__file__).parents[1] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_step():
    script, argv = ARGS
    mod = _load(script)
    try:
        assert mod.main(argv) == 0
    except BaseException:
        # A failed open or export must not leave the copy unnoticed: close
        # prints its name and URL for the analyst to delete.
        if script == "cube_validate_snapshot" and argv[0] in ("open", "export"):
            mod.main(["close", CHECKS])
        raise
```

Run:
`uv run --with tableauhyperapi pytest tests/test_zz_cube_validate.py -s --tb=short`.
`--tb=short` keeps credentials out of a traceback.

## Validating a dashboard

Run on a weekday between 9 AM and 5 PM New York time, not Friday: the scheduled
Tableau refreshes share the PAT.

1. **Header.** Create `checks/<dashboard>.yml` with `workbook`, `workbook_luid`,
   `review_project_luid` (TEMP-CB, `ddc817c2-6bc7-4bca-8be9-e385f95b9ebc`),
   `dashboards`, `student_count`, `scope: {filter: <region caption>}` and
   `asana_task` (the dashboard's Asana task id).
2. **Plan.** `cube_validate_snapshot.py plan <checks>`. Show the analyst the
   trees, the borderline pairs, the must, optional and skipped states, and each
   dashboard's sheets. Save their edits as `trees`, `cross_cuts`,
   `accept_nesting` and `states`. List the sheets to compare under `sheets:` as
   stubs (`<sheet>: {datasource: <caption>}`). Never list a student-level sheet
   (one with a name column such as `Lastfirst`).
3. **Open the default view only.** `open <checks> --states <file>`, the file
   holding only the default state. Only the listed sheets and click sources are
   exposed on the copy. `open` refuses while an earlier copy of the workbook is
   still in TEMP-CB.
4. **Map.** `cube_validate.py map <checks>` writes `<snapshot>/map.yml`: each
   exported column with its workbook formula and candidate Cube members. Draft
   `sheets:` from it; the formula decides the SQL
   (`COUNT([x]) / TOTAL(COUNT([x]))` is a share of rows, not of students). The
   analyst approves the mapping. See _Mapping keys_.
5. **Compare the default view.** `compare <checks>`. Fix the mapping and run
   `compare --redo` until the default view's mismatches are real gaps.
6. **Asana rows.** List the dashboard task's measure rows from Asana (read
   only). Sort each into `rows:` (dashboard, sheet, and the measure or dimension
   caption, mapped on a listed dashboard) or `rows_deferred:` with a reason
   (unmapped, lives on an unlisted dashboard, or no Cube member). Map a gap, or
   add its dashboard, before exporting. Show the analyst both lists. Nothing in
   Asana is renamed or edited.
7. **Live checks**, the first time a workbook is validated: _Live checks_.
8. **Export the rest.** `export <checks>`, then `compare`. While
   `next_states.yml` is not empty:
   `export <checks> --states <snapshot>/next_states.yml`, then compare again.
9. **Close.** `close <checks>` prints the copy's name and URL. The analyst
   deletes it in Tableau; run `close` again until it says the copy is gone.
   Always, including after a failure. The tool deletes nothing on Tableau.
10. **Explain.** `cube_validate.py explain <checks>`. It saves `cells.jsonl` as
    each batch finishes, so a crash keeps the work done.
11. **Report.** `cube_validate.py drafts <checks>` (no secret). Read the digest
    and the coverage report.

## Live checks

On the default view, before the first full export of a workbook:

- An uncaptioned field filters by its raw name: export one value of
  `dibels_most_recent_composite` (DDI); its mapped sheets must change.
- A group bin name filters its group: `Subject Area (group)` = `Mathematics`.
- `vf(<caption>, "Null")` filters a blank (Is Foundations). Until it does, blank
  states stay optional.
- The high-school section key reproduces: after `compare` and `explain`, the
  Teacher sheet's HS cells are not `incomplete`.
- Both Cube routes run: the coverage report lists queries under "Cube routes".

A `filter_ignored` state means its check failed: fix the caption or value, then
`open --resume --retry-ignored`.

## Mapping keys

Under `sheets.<sheet>`: `datasource` (the extract's caption), `dims` and
`measures`, keyed by the column caption Tableau exports. Optional `cube_filters`
and `extract_filters` apply to that sheet only, on top of the top-level ones.

- **Dimension:** `cube` (a member; a list of members, joined with " - " to match
  `sql`; `{time: <member>, granularity: week}`; or none when Cube lacks it) and
  `sql`. `keys:` regexes tried in order, each with one group around the join
  key; anchor each so a label of another shape never matches, because the
  captured text is shown in every output. `values:` Tableau aliases to stored
  values. `attr: true` for a known attribute. `person: true` for a student
  column, or `person: a teacher` for staff; `load_checks` requires it when `sql`
  reads a name column.
- **Measure:** `cube`, then `sql` or `num` and `den`. `round: <n>` when the
  export shows a plain number rounded to n decimals. `scale` multiplies Cube's
  value. `table_calc: percent_of_total` or `running_sum`. `cube_filters` and
  `where`: Cube filters and an extract condition for this measure alone.
  `missing_members` and `variants` explain gaps.

At the top level:

- `filters`: `{caption: {cube: member}}` for filter cards not shown as a column;
  `values:` maps extract values to Cube's; `sql:` gives a calculated card's
  extract expression; add `person:` here too.
- `cube_filters` and `extract_filters`: the dashboard's hard filters on each
  side, optionally per `datasource`. Mark test-record filters `private: true` so
  they never reach a draft.
- `param_filters` and `param_where`: what a parameter value filters, on each
  side. Leave a parameter out when it only changes what a sheet shows.
- `ignore_sheet_filters`: saved filters Cube cannot express. `compare` warns
  when an ignored filter would hide rows in a slice. A FIXED-LOD filter cannot
  be counted; link its issue in a comment.
- `rows`, `rows_deferred`, `asana_task`: the Asana rows (step 6).
- `mismatches`: below.

## Reading the results

- **`filter_ignored` state:** Tableau ignored the `vf` caption or value
  silently. Fix it, then export that state again.
- **`incomplete`, "extract SQL reproduces N%":** the mapping's SQL is wrong for
  some cells; the coverage report lists them. Fix the mapping. Never file this
  as a Cube issue.
- **`fail`:** a gap nothing explains yet, labelled **row gap** (Cube and the
  live table count different students) or **formula gap** (the same students, a
  different value). The digest's Investigate section prints the extract SQL and
  the same SQL on the live `rpt_` table, ready to run.
- **`cube-routes-disagree`:** Cube answers the same query differently with and
  without the student count, usually a rollup gap. Built in, `fix: cube`; give
  it `issue:` once filed.
- **Variants:** `sql`, `num` and `den`, or `where` on the dashboard side;
  `cube_filters` for "Cube without these rows". A cell is explained only when
  one variant accounts for its whole gap.
- **`fix:`** says who fixes a mismatch: `cube`, `dashboard` (add `where: rpt`
  for the model), `source`, `undecided` (the domain owner decides), or
  `accepted` (an owner ruled it will not be fixed; needs `issue:`; its cells
  pass with a note and the Asana row is not reopened).
- **Limit:** Cube reads its own fact table, not the `rpt_` table. A fail says
  Cube differs from the dashboard's formula on the live `rpt_` table; which dbt
  model is at fault is the analyst's next query. Both sides wrong the same way
  is out of scope by design.

## Filing

1. For each draft and each "Investigate" row, search the repo's issues, open and
   closed, with the GitHub MCP. List the matches beside it.
2. A match that is the same problem becomes the entry's `issue:`; a related one
   goes in `related:`.
3. Show the analyst the full list of drafts before filing anything. File only
   the ones they pick, with the title, labels and body from the draft.
4. Write each new `issue:` into the checks file and commit it. The analyst runs
   `~/asana-sync/sync.py`.

## Following up ("follow up on <dashboard>")

The analyst owns runs. A builder verifies their own fix with the draft's "Check
it yourself" block; the follow-up run confirms it.

1. Read each filed issue's state, labels and comments. A closed issue gets
   `closed_on`. On an undecided issue, the label `fix-cube` or `fix-dashboard`,
   or a comment starting with the word, sets `fix`; a ruling not to fix sets
   `fix: accepted`.
2. Open a new session (default view only), then
   `export <checks> --for <mismatch>` for each mismatch: it exports only the
   states behind that mismatch's cells.
3. `compare`, `explain`, `drafts`. `drafts` replaces every `latest.json` entry
   for the dashboard.

A `rows:` change needs `drafts` only. A new measure mapping needs
`compare --redo` and `explain`, no export, when its column was already exported.

## Timing

The extract is a snapshot; Cube reads current data. When Cube differs from
Tableau but equals the same SQL run on the live `rpt_` table, the gap is only
the extract's age: `explain` marks it `pass` with a timing note. When Cube's
data is older than the live table, the cell is `incomplete`: re-run `explain`
after Cube refreshes. `explain` reads BigQuery through ADC as well as Cube.

## Rules

- Snapshots hold student-level rows. They stay in `~/.cache/cube-validate/`.
  Never commit them, and never paste row values outside the terminal or
  `#data_team`.
- The checks file is committed, so `states:` never holds a person's name.
- Review copies go to TEMP-CB only, named `ZZ-REVIEW <date> <time> <workbook>`.
  The tool deletes nothing on Tableau; the analyst deletes each copy.
````

- [ ] **Step 2: Update the script catalog**

In `scripts/CLAUDE.md`, replace the 2 rows' purpose text:

- `cube_validate.py`: "Compare Cube with a Tableau dashboard's own exports:
  `map` drafts the sheet mapping from headers, formulas and Cube members,
  `compare` diffs each exported sheet with Cube by both of Cube's routes and
  proposes the next descent level, `explain` judges gaps with SQL over the
  extract (trusted at 95% of cells) and checks timing against the live `rpt_`
  table, `drafts` writes the digest, issue drafts and `latest.json`. Runbook:
  the `cube-dashboard` skill."
- `cube_validate_snapshot.py`: "The Tableau side of the same check: `plan`
  proposes states from the workbook and extract, `open` publishes a `ZZ-REVIEW`
  copy to TEMP-CB exposing only the listed sheets and exports states, `export`
  adds states (`--for` a mismatch's), `close` confirms the analyst deleted the
  copy; the tool deletes nothing on Tableau. Credentialed steps run inside a
  throwaway pytest. Runbook: the `cube-dashboard` skill."

- [ ] **Step 3: Lint**

Run, from `/workspaces/teamster`:
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md </dev/null`
Expected: no issues. Fix any finding (formatting is the commit hook's).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/cube-dashboard/SKILL.md scripts/CLAUDE.md
git commit -m "docs(cube): the runbook maps on the default view first and never deletes"
```

---

## Part H: the DDI checks file

The checks file stays untracked until Task 35 commits it. Every step here is
offline: it reads the 2026-10-09 snapshot
(`~/.cache/cube-validate/ddi-suite/2026-10-09T2236/`) for column names and
aggregates only.

### Task 33: re-plan the DDI states offline with the new rules

**Files:**

- Modify: `.claude/skills/cube-dashboard/checks/ddi_suite.yml`
  (`accept_nesting`, `trees`, `cross_cuts`, `states`)

- [ ] **Step 1: Build an offline workbook from the snapshot**

In your session scratchpad (`<scratch>` below), zip the snapshot's `base.twb`
and extracts into a `.twbx` that `plan --twbx` can read:

```bash
uv run python - <<'EOF'
import zipfile
from pathlib import Path

snap = Path.home() / ".cache/cube-validate/ddi-suite/2026-10-09T2236"
out = Path("<scratch>/ddi-offline.twbx")
with zipfile.ZipFile(out, "w") as z:
    z.write(snap / "base.twb", "DDI Suite.twb")
    for h in (snap / "extract").glob("*.hyper"):
        z.write(h, f"Data/Extracts/{h.name}")
print(out)
EOF
```

- [ ] **Step 2: Edit the trees, then plan**

In the checks file, remove `team` from the `region` tree and delete the 2
`accept_nesting` entries that name `team` (the descent stops at the last level
with a Cube member, and `team` has none). Then run:

`uv run --with tableauhyperapi scripts/cube_validate_snapshot.py plan .claude/skills/cube-dashboard/checks/ddi_suite.yml --twbx <scratch>/ddi-offline.twbx --out <scratch>/plan.yml`

Expected: a must, optional and skipped count, and `<scratch>/plan.yml`.

- [ ] **Step 3: Check the plan against the spec**

Read `<scratch>/plan.yml` and confirm each of these before copying anything:

- The 5 uncaptioned filter fields appear under their raw names:
  `dibels_most_recent_composite`, `head_of_school`, `is_sipps`,
  `nj_student_tier`, `state_test_proficiency`.
- Every bin of `Subject Area (group)` (CCR, Literacy, Mathematics, Science,
  Social Studies, Other) and of `School Level (School)` (ES, HS, MS, Other) is a
  must state, plus each group's `(All)`.
- Each cross-cut has exactly one must state, its largest value; the rest are
  optional.
- No blank-value state is must.
- `NJ Tutoring` has a must state per value.

If any check fails, stop and report it: the code, not the checks file, is wrong.

- [ ] **Step 4: Copy the plan into the checks file**

Replace `states:` with the plan's `must` list (drop each entry's `why`). Replace
`cross_cuts:` with the plan's. Keep the checks file's own comments.

- [ ] **Step 5: Validate offline**

Run
`uv run --with tableauhyperapi scripts/cube_validate.py drafts .claude/skills/cube-dashboard/checks/ddi_suite.yml --out <scratch>/drafts`.
Expected: it loads the checks file and writes a digest to `<scratch>/drafts`
(the old snapshot's cells; the verdicts do not matter here). A `CheckError` is a
checks-file mistake: fix it.

No commit: the file is still untracked.

### Task 34: correct the DDI mappings

**Files:**

- Modify: `.claude/skills/cube-dashboard/checks/ddi_suite.yml` (`filters`,
  `ignore_sheet_filters`, `sheets`)

- [ ] **Step 1: Captions and filters**

- Rename `scope.filter` and every `filters:` key whose card is uncaptioned to
  its raw name (only the 5 fields of Task 33; `Region` and the rest keep their
  stored captions).
- Add
  `NJ Tutoring: {cube: null, sql: "case when tutoring_nj then 'Tutored' else 'Not Tutored' end"}`.
- Give `Schoolid`'s `values:` the anchor `&schools`, and add
  `School Level (School): {cube: student_assessment_scores_view.abbreviation, values: *schools}`.
- List the `School Level (School)` members the extract has but `&schools` lacks:
  read the snapshot's `review.twb` bins (Task 4's `read_workbook(...).groups`)
  and the extract's distinct `schoolid` values (Task 4's `profile`). For each,
  add its abbreviation, found the way the existing entries were: the extract's
  `school` value for that id, matched to Cube's `abbreviation`. An id with no
  single abbreviation (as 5173 spans several schools) stays out, and its bin
  states report a missing member.

- [ ] **Step 2: Saved filters**

Set `ignore_sheet_filters` to `["% Completion", "Is Normed Scope"]`. Above it,
replace the comment with: `Is Normed Scope` hides nothing today (every default
row is normed) and `compare` warns if that changes; `% Completion` is a
FIXED-LOD filter `compare` cannot count, so the comment links the completion
finding's issue. Find that issue with the GitHub MCP (search the repo's issues
for the DDI completion finding); if none is filed, say so to the user in the
task report rather than inventing a number.

- [ ] **Step 3: Sheets**

- **Band Distribution, `% of Students`:**
  `cube: student_assessment_scores_view.count_scored`,
  `sql: count(student_number)`, `table_calc: percent_of_total`. Update the
  sheet's comment: a share of rows, verified to reproduce all 5 band percentages
  on the 2026-10-09 extract.
- **Teacher, `Section Number`:**

  ```yaml
  Section Number:
    cube:
      - student_assessment_scores_view.course_title
      - student_assessment_scores_view.identifier
    sql: "course_name || ' - ' || section_number"
    # HS labels read "<teacher> - <course> - <section>"; ES/MS labels read
    # "G<grade> - <teacher> - <section>". Anchored so neither pattern can
    # capture a teacher's name.
    keys:
      - "^(?!G\\d+ - ).* - ([^-]+ - \\S+)$"
      - "^G\\d+ - .* - (\\S+)$"
  ```

  `Teacher Name` stays unmapped: never a dimension.

- **Standard Band Distribution, `Performance Band (group)`:** map it
  (`cube: student_assessment_scores_view.performance_band_label_number`,
  `sql: performance_band_number`); the manifest's groups compare it bin by bin.
- **Assessments Over Time:** add `Module Type (group)`
  (`cube: student_assessment_scores_view.module_type`, `sql: module_type`). If
  Task 25 shipped, add the IEP and Gen Ed parts and their difference:

  ```yaml
  Avg. % Mastery - IEP:
    cube: student_assessment_scores_view.pct_proficient
    sql: avg(case when is_mastery then 1.0 when not is_mastery then 0.0 end)
    where: "strpos(iep_status, 'SPED') > 0"
    cube_filters:
      - member: student_assessment_scores_view.is_iep
        operator: equals
        values: ["true"]
  Avg. % Mastery - Gen Ed:
    cube: student_assessment_scores_view.pct_proficient
    sql: avg(case when is_mastery then 1.0 when not is_mastery then 0.0 end)
    # Tableau's NOT CONTAINS on a blank status is blank, so a blank stays out.
    where: "strpos(iep_status, 'SPED') = 0"
    cube_filters:
      - member: student_assessment_scores_view.is_iep
        operator: equals
        values: ["false"]
  "% Mastery - IEP Diff from GenEd":
    diff: [Avg. % Mastery - IEP, Avg. % Mastery - Gen Ed]
  ```

  If Task 27 shipped and the user chose to map `Avg. % Completion`, add it on
  Summary and Assessments Over Time with `fixed:` and `weight:` per Task 27;
  otherwise keep the comment that it is unmapped and link the completion
  finding's issue.

- Keep only the 6 mapped sheets under `sheets:` (Network Overview, Summary,
  Teacher, Band Distribution, Standard Band Distribution, Assessments Over
  Time). No student distribution sheet is listed.

- [ ] **Step 4: Validate offline**

Run the Task 33 Step 5 command again. Expected: no `CheckError`.

No commit yet.

### Task 35: mismatches, Asana rows, and committing the checks file

**Files:**

- Modify: `.claude/skills/cube-dashboard/checks/ddi_suite.yml` (`mismatches`,
  `rows`, `rows_deferred`, `asana_task`)

- [ ] **Step 1: Mismatches**

```yaml
mismatches:
  # Built in; this attaches the filed issue (rollup build range, 2026-10-13).
  cube-routes-disagree:
    issue: 5883
  # Off-grade scores: the dashboard counts them under the enrolled grade, Cube's
  # fact drops them. A variant ties cells to it once the live run shows which.
  off-grade-scores:
    title: "fix(cube): off-grade assessment scores are dropped from the fact"
    what: >-
      Students who sat another grade's assessment count on the dashboard under
      their enrolled grade; Cube's fact leaves those rows out.
    fix: undecided
    issue: 5885
```

Copy the title from #5885 itself (read it with the GitHub MCP) so the two match.

- [ ] **Step 2: Asana rows (read-only)**

With the Asana MCP, find the "DDI Suite" dashboard task and list its measure
rows (15 expected). Set `asana_task:` to its id. Sort the rows as the spec's
"The first DDI run" says:

- `rows:` Mastery (Summary, `Mastery`), Percent Correct (Summary,
  `Avg. Percent Correct`), Student Count / % of Students (Band Distribution,
  `Distinct count of Student Number` and `% of Students`), Performance Band
  (Band Distribution, dimension `Performance Band Number`), Schoolid / Section
  Number (Teacher, dimension `Section Number`). Add % Mastery IEP / Gen Ed diff
  only if Task 25 shipped, and % Completion only if Task 27 shipped and the user
  mapped it.
- `rows_deferred:` with these reasons: headline "Mastery rate" (Mastery Over
  Time [School], second run with the week mapping); Mastery rate by IEP / Gen Ed
  (DKI and O3 views, second run); % Complete this week (Landing Page, second
  run); Goals, Microgoals, i-Ready lessons, Walkthrough mastery, Tutoring bucket
  (no Cube member yet); and IEP / Gen Ed diff or % Completion when their task
  did not ship.

Every row of the 15 lands in exactly one list. Show the user both lists before
Step 4.

- [ ] **Step 3: Validate and lint**

Run the Task 33 Step 5 command, then
`/workspaces/teamster/.trunk/tools/trunk check --force --no-fix .claude/skills/cube-dashboard/checks/ddi_suite.yml </dev/null`.
Expected: no `CheckError`, no lint issues. Then grep the file for anything
person-level:
`rg -n -i "lastfirst|teacher_name|student_name" .claude/skills/cube-dashboard/checks/ddi_suite.yml`
must print nothing.

- [ ] **Step 4: Commit the checks file**

```bash
git add .claude/skills/cube-dashboard/checks/ddi_suite.yml
git commit -m "chore(cube): commit the DDI Suite checks file with the review's corrections"
```

---

## Part I: live checks before the full export (the user's to run)

### Task 36: the live smoke checks

The executor stops before this task and hands it to the user: it publishes a
review copy and reads Cube with the user's credentials. Run on a weekday between
9 AM and 5 PM New York time, not Friday.

- [ ] **Step 1: Open the default view.** Write `<scratch>/default.yml` holding
      only `- {id: module-dashboard--default, dashboard: Module Dashboard}`, and
      run `open` with `--states <scratch>/default.yml` through the throwaway
      pytest in the skill.
- [ ] **Step 2: Map and compare the default view.** `map`, then `compare`;
      confirm the mapping with the analyst.
- [ ] **Step 3: The 5 checks.** Export these states with `export --states`, and
      read each result:
  - `dibels_most_recent_composite` = its largest value: status `ok`, not
    `filter_ignored`.
  - `Subject Area (group)` = `Mathematics`: status `ok`, and the Summary sheet
    shows Mathematics modules.
  - `Is Foundations` = `(Blank)`: status `ok`. If `filter_ignored`, blank states
    stay optional.
  - After `compare` and `explain`, the Teacher sheet's HS cells are not
    `incomplete`.
  - The coverage report lists queries under "Cube routes".
- [ ] **Step 4: Close.** Run `close`, delete the copy in Tableau, and run
      `close` again until it reports the copy gone.

Then, and only then, the full export (Task 21 of the previous plan) resumes.
