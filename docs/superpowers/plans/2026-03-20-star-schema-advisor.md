# Star Schema Advisor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/tableau-analyze-workbook.py` (Tableau XML parser
outputting structured JSON) and `.claude/commands/star-schema-advisor.md` (slash
command guiding analysts from reporting view to dbt mart changes).

**Architecture:** A standalone Python script handles all Tableau XML parsing —
it reads a workbook (from a local file or Tableau Server), parses every
datasource field and its viz usage across worksheets, and emits JSON to stdout.
The slash command is a markdown prose document that Claude reads and follows; it
calls the script, reads the JSON alongside dbt models and mart YAML, classifies
every field, writes a shareable report, and applies approved mart changes. The
script is pure I/O; the command is pure reasoning. They share no state.

**Tech Stack:** Python 3.12+, `defusedxml>=0.7`, `requests>=2.32`,
`pyyaml>=6.0`, `zipfile` (stdlib), `uv run` inline script header. `pytest` for
tests.

**Spec:** `docs/superpowers/specs/2026-03-20-star-schema-advisor-design.md`

---

## File Map

| File                                             | Action | Responsibility                                               |
| ------------------------------------------------ | ------ | ------------------------------------------------------------ |
| `scripts/tableau-analyze-workbook.py`            | Create | Tableau XML parser; `--exposure` or `--file`; JSON to stdout |
| `tests/scripts/test_tableau_analyze_workbook.py` | Create | Unit + integration tests for all parsing functions           |
| `tests/scripts/fixtures/minimal.twb`             | Create | Single-datasource fixture for unit tests                     |
| `tests/scripts/fixtures/multi_datasource.twb`    | Create | Two-datasource fixture for deduplication test                |
| `.claude/commands/star-schema-advisor.md`        | Create | Slash command workflow (prose, not unit-tested)              |
| `docs/superpowers/star-schema-reports/.gitkeep`  | Create | Tracks the reports directory in git                          |

Note: no `tests/scripts/__init__.py` — pytest discovers files by path and no
other test subdirectory uses one. The `importlib.util` loader in tests does not
require it.

**Note on importing the script in tests:** The filename contains a hyphen, so it
cannot be imported with a normal `import` statement. Use `importlib.util` to
load it by path. See Task 1 for the pattern.

**Auth and extraction patterns to implement** (the branch
`origin/claude/feat/tableau-upstream-tool` will be deleted — use these
descriptions directly):

- **Auth**: prefer PAT via `TABLEAU_TOKEN_NAME` +
  `TABLEAU_PERSONAL_ACCESS_TOKEN`; fall back to username/password via `getpass`
  only when `--username` is passed and PAT vars are absent; raise `SystemExit`
  with a clear message if neither is available. Enforce HTTPS — raise
  `SystemExit` before sending credentials if the server URL does not start with
  `https://`. Call signout in a `finally` block (swallow `RequestException`; log
  to stderr when `TABLEAU_DEBUG` is set).
- **Zip extraction from memory**: server-downloaded workbooks arrive as raw
  `.twbx` bytes — wrap in `io.BytesIO`, open with `zipfile.ZipFile`, find the
  first `.twb` entry, read without extracting to disk. For local files use
  `zipfile.ZipFile(path)` for `.twbx` or `path.read_bytes()` for `.twb`.
- **Datasource deduplication**: track seen captions in a `set`; skip duplicates
  and the `"Parameters"` datasource (handled separately).
- **Internal field filtering**: skip any `column` element where `caption` is
  empty, `name` starts with `[:`, or `name` equals `[Number of Records]`.
- **Calc name resolution**: build a map of `Calculation_*` / `*(copy)_*` IDs to
  human captions; rewrite formula references via regex. Leave unrecognised refs
  unchanged.
- **Filter injection prevention**: strip `:` and `,` from user-supplied workbook
  names before passing to Tableau REST API filter params.

---

## Task 1: Script skeleton, argument parsing, and file/zip loading

**Files:**

- Create: `scripts/tableau-analyze-workbook.py`
- Create: `tests/scripts/__init__.py`
- Create: `tests/scripts/test_tableau_analyze_workbook.py`
- Create: `tests/scripts/fixtures/minimal.twb`

- [ ] **Step 1: Create the test fixture**

Create `tests/scripts/fixtures/minimal.twb`:

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2023.3' version='18.1'>
  <datasources>
    <datasource caption='rpt_tableau__test (kipptaf_tableau)' name='federated.abc'>
      <column caption='school_name' datatype='string' name='[school_name]' role='dimension' />
      <column caption='is_present' datatype='integer' name='[is_present]' role='measure' />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Overview'>
      <table><view><rows>[school_name]</rows></view></table>
    </worksheet>
  </worksheets>
</workbook>
```

- [ ] **Step 2: Write failing tests for file and zip loading**

Create `tests/scripts/test_tableau_analyze_workbook.py`:

```python
import importlib.util
import pathlib
import zipfile

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "tableau_analyze_workbook",
        pathlib.Path(__file__).parents[2] / "scripts" / "tableau-analyze-workbook.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_s = _load_script()


def test_extract_twb_bytes_from_twb():
    result = _s.extract_twb_bytes(FIXTURES / "minimal.twb")
    assert b"<workbook" in result


def test_extract_twb_bytes_from_twbx(tmp_path):
    twbx = tmp_path / "test.twbx"
    with zipfile.ZipFile(twbx, "w") as zf:
        zf.write(FIXTURES / "minimal.twb", "test.twb")
    result = _s.extract_twb_bytes(twbx)
    assert b"<workbook" in result
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: error loading the script (file does not exist yet).

- [ ] **Step 4: Create the script skeleton**

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "defusedxml>=0.7",
#   "requests>=2.32",
#   "pyyaml>=6.0",
# ]
# ///

import argparse
import io
import json
import pathlib
import zipfile

import defusedxml.ElementTree as ET
import requests
import yaml

EXPOSURES_PATH = pathlib.Path("src/dbt/kipptaf/models/exposures/tableau.yml")
TABLEAU_API_VERSION = "3.20"


def extract_twb_bytes(path: pathlib.Path) -> bytes:
    """Return raw .twb XML bytes from a .twbx zip or a plain .twb file."""
    if path.suffix == ".twbx":
        with zipfile.ZipFile(path) as zf:
            twb_name = next(n for n in zf.namelist() if n.endswith(".twb"))
            return zf.read(twb_name)
    return path.read_bytes()


def extract_twb_bytes_from_bytes(raw: bytes) -> bytes:
    """Extract .twb XML bytes from in-memory .twbx bytes."""
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        twb_name = next(n for n in zf.namelist() if n.endswith(".twb"))
        return zf.read(twb_name)


def parse_workbook(twb_bytes: bytes) -> dict:
    """Parse .twb XML and return the full analysis dict."""
    return {"datasources": []}  # implemented in later tasks


def _fetch_from_server(exposure_name: str) -> bytes:
    raise NotImplementedError  # implemented in Task 8


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze a Tableau workbook and emit field usage JSON."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--exposure", metavar="NAME")
    source.add_argument("--file", metavar="PATH", type=pathlib.Path)
    args = parser.parse_args()

    twb_bytes = (
        extract_twb_bytes(args.file) if args.file else _fetch_from_server(args.exposure)
    )
    print(json.dumps(parse_workbook(twb_bytes), indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/tableau-analyze-workbook.py tests/scripts/
git commit -m "feat(tableau): scaffold tableau-analyze-workbook with file/zip loading"
```

---

## Task 2: Datasource listing and deduplication

**Files:**

- Modify: `scripts/tableau-analyze-workbook.py`
- Modify: `tests/scripts/test_tableau_analyze_workbook.py`
- Create: `tests/scripts/fixtures/multi_datasource.twb`

- [ ] **Step 1: Create the multi-datasource fixture**

Create `tests/scripts/fixtures/multi_datasource.twb`:

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2023.3' version='18.1'>
  <datasources>
    <!-- First datasource -->
    <datasource caption='rpt_tableau__alpha (kipptaf_tableau)' name='federated.aaa'>
      <column caption='school_name' datatype='string' name='[school_name]' role='dimension' />
    </datasource>
    <!-- Second datasource -->
    <datasource caption='rpt_tableau__beta (kipptaf_tableau)' name='federated.bbb'>
      <column caption='student_id' datatype='integer' name='[student_id]' role='dimension' />
    </datasource>
    <!-- Per-worksheet duplicate of first — should be deduplicated -->
    <datasource caption='rpt_tableau__alpha (kipptaf_tableau)' name='federated.aaa'>
      <column caption='school_name' datatype='string' name='[school_name]' role='dimension' />
    </datasource>
    <!-- Parameters datasource — should be skipped -->
    <datasource caption='Parameters' name='Parameters'>
      <column caption='Param1' datatype='integer' name='[Parameter 1]' param-domaintype='range' />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
```

- [ ] **Step 2: Write failing tests**

Add to `tests/scripts/test_tableau_analyze_workbook.py`:

```python
def test_list_datasources_deduplicates():
    twb_bytes = (FIXTURES / "multi_datasource.twb").read_bytes()
    sources = _s.list_datasources(twb_bytes)
    captions = [s["caption"] for s in sources]
    # Duplicates and Parameters removed
    assert len(sources) == 2
    assert "rpt_tableau__alpha (kipptaf_tableau)" in captions
    assert "rpt_tableau__beta (kipptaf_tableau)" in captions
    assert not any("Parameters" in c for c in captions)


def test_list_datasources_includes_field_count():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    sources = _s.list_datasources(twb_bytes)
    assert sources[0]["n_fields"] > 0
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: 2 FAIL — `list_datasources` not defined.

- [ ] **Step 4: Implement `list_datasources`**

Add to `scripts/tableau-analyze-workbook.py`:

```python
def _is_internal(column) -> bool:
    name = column.get("name", "")
    caption = column.get("caption", "")
    return not caption or name.startswith("[:") or name == "[Number of Records]"


def list_datasources(twb_bytes: bytes) -> list[dict]:
    """List unique non-Parameters datasources with field counts."""
    root = ET.fromstring(twb_bytes)
    seen: set[str] = set()
    sources = []
    for ds in root.findall(".//datasources/datasource"):
        caption = ds.get("caption") or ds.get("name", "")
        if caption == "Parameters" or caption in seen:
            continue
        seen.add(caption)
        n_fields = sum(1 for col in ds.findall("column") if not _is_internal(col))
        sources.append({"caption": caption, "n_fields": n_fields})
    return sources
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/tableau-analyze-workbook.py tests/scripts/
git commit -m "feat(tableau): add datasource listing with deduplication"
```

---

## Task 3: Field extraction — all columns, calculated fields, and LOD detection

**Files:**

- Modify: `scripts/tableau-analyze-workbook.py`
- Modify: `tests/scripts/test_tableau_analyze_workbook.py`
- Modify: `tests/scripts/fixtures/minimal.twb` (add calc field and LOD examples)

- [ ] **Step 1: Extend the fixture with calculated fields and a LOD**

Replace `tests/scripts/fixtures/minimal.twb`:

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2023.3' version='18.1'>
  <datasources>
    <datasource caption='rpt_tableau__test (kipptaf_tableau)' name='federated.abc'>
      <!-- Plain dimension -->
      <column caption='school_name' datatype='string' name='[school_name]' role='dimension' />
      <!-- Plain measure -->
      <column caption='is_present' datatype='integer' name='[is_present]' role='measure' />
      <!-- Calculated field, no LOD -->
      <column caption='Attendance Rate' datatype='real' name='[Calculation_111]' role='measure'>
        <calculation class='tableau' formula='SUM([is_present]) / COUNT([student_number])' />
      </column>
      <!-- Calculated field with embedded LOD -->
      <column caption='School Avg' datatype='real' name='[Calculation_222]' role='measure'>
        <calculation class='tableau' formula='{ FIXED [school_id] : AVG([is_present]) }' />
      </column>
      <!-- Internal fields — must be filtered -->
      <column name='[:Measure Names]' datatype='string' />
      <column name='[Number of Records]' datatype='integer' />
    </datasource>
  </datasources>
  <worksheets>
    <worksheet name='Overview'>
      <table><view><rows>[school_name]</rows></view></table>
    </worksheet>
  </worksheets>
</workbook>
```

- [ ] **Step 2: Write failing tests**

Add to `tests/scripts/test_tableau_analyze_workbook.py`:

```python
def test_extract_fields_plain_column():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    ds = root.find(".//datasources/datasource")
    fields = _s._extract_fields(ds)
    names = [f["name"] for f in fields]
    assert "school_name" in names
    assert "is_present" in names


def test_extract_fields_excludes_internal():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    ds = root.find(".//datasources/datasource")
    fields = _s._extract_fields(ds)
    names = [f["name"] for f in fields]
    assert ":Measure Names" not in names
    assert "Number of Records" not in names


def test_extract_fields_calc_field():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    ds = root.find(".//datasources/datasource")
    fields = _s._extract_fields(ds)
    rate = next(f for f in fields if f["name"] == "Attendance Rate")
    assert rate["is_calculated"] is True
    assert "is_present" in rate["formula"]
    assert rate["contains_lod"] is False


def test_extract_fields_lod_detection():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    ds = root.find(".//datasources/datasource")
    fields = _s._extract_fields(ds)
    school_avg = next(f for f in fields if f["name"] == "School Avg")
    assert school_avg["contains_lod"] is True
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: 4 FAIL — `_extract_fields` not defined.

- [ ] **Step 4: Implement `_extract_fields`**

Add to `scripts/tableau-analyze-workbook.py`:

```python
import re

_FIELD_REF_RE = re.compile(r"\[([^\]]+)\]")
_LOD_RE = re.compile(r"\{\s*(FIXED|INCLUDE|EXCLUDE)\b", re.IGNORECASE)


def _build_calc_name_map(datasource) -> dict[str, str]:
    """Map opaque Calculation_* names to human captions."""
    name_map: dict[str, str] = {}
    for column in datasource.findall("column"):
        raw_name = column.get("name", "")
        caption = column.get("caption", "")
        name = raw_name.strip("[]")
        if caption and (name.startswith("Calculation_") or "(copy)_" in name):
            name_map[name] = caption
    return name_map


def _resolve_calc_refs(formula: str, name_map: dict[str, str]) -> str:
    def _sub(m: re.Match) -> str:
        key = m.group(1)
        return f"[{name_map[key]}]" if key in name_map else m.group(0)
    return _FIELD_REF_RE.sub(_sub, formula)


def _extract_fields(datasource) -> list[dict]:
    """Extract all user-visible fields from a datasource element."""
    name_map = _build_calc_name_map(datasource)
    fields = []
    for column in datasource.findall("column"):
        if _is_internal(column):
            continue
        calc = column.find("calculation[@class='tableau']")
        is_calculated = calc is not None
        formula: str | None = None
        contains_lod = False
        if calc is not None:
            formula = _resolve_calc_refs(calc.get("formula", ""), name_map)
            contains_lod = bool(_LOD_RE.search(formula))
        fields.append(
            {
                "name": column.get("caption") or column.get("name", "").strip("[]"),
                "datatype": column.get("datatype", "unknown"),
                "formula": formula,
                "is_calculated": is_calculated,
                "contains_lod": contains_lod,
                "viz_usage": [],  # populated in Task 4
            }
        )
    return fields
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/tableau-analyze-workbook.py tests/scripts/
git commit -m "feat(tableau): add field extraction with LOD detection"
```

---

## Task 4: Viz usage extraction (dimension vs measure role per worksheet)

**Files:**

- Modify: `scripts/tableau-analyze-workbook.py`
- Modify: `tests/scripts/test_tableau_analyze_workbook.py`
- Modify: `tests/scripts/fixtures/minimal.twb` (add mark encoding example)

> **Note on Tableau XML structure:** The exact XPath for mark encodings varies
> across Tableau versions. Before implementing, run:
>
> ```bash
> uv run scripts/tableau-analyze-workbook.py --exposure <any_exposure> 2>/dev/null \
>   | uv run python -c "import sys,json; print(json.load(sys.stdin))" || true
> ```
>
> Or examine a real workbook manually:
>
> The fixture below reflects the most common Tableau XML structure. If real
> workbooks differ, update the fixture to match and adjust the XPath
> accordingly.

- [ ] **Step 1: Extend the fixture with worksheet viz usage**

Replace `tests/scripts/fixtures/minimal.twb` with a version that includes both
dimension and measure usage. The key elements to add inside `<worksheet>`:

```xml
<worksheets>
  <worksheet name='Overview'>
    <table>
      <view>
        <datasources>
          <datasource name='federated.abc' />
        </datasources>
        <!-- Dimension shelf -->
        <rows>[school_name]</rows>
        <cols />
        <!-- Filter -->
        <filter class='categorical'>
          <field>[school_name]</field>
        </filter>
      </view>
      <!-- Mark encoding for measures -->
      <panes>
        <pane>
          <mark class='Bar' />
          <encodings>
            <text>
              <field>[is_present]</field>
              <aggregation>SUM</aggregation>
            </text>
          </encodings>
        </pane>
      </panes>
    </table>
  </worksheet>
  <worksheet name='Trend'>
    <table>
      <view>
        <datasources><datasource name='federated.abc' /></datasources>
        <rows>[school_name]</rows>
      </view>
      <panes>
        <pane>
          <encodings>
            <text>
              <field>[is_present]</field>
              <aggregation>AVG</aggregation>
            </text>
          </encodings>
        </pane>
      </panes>
    </table>
  </worksheet>
</worksheets>
```

- [ ] **Step 2: Write failing tests**

Add to `tests/scripts/test_tableau_analyze_workbook.py`:

```python
def test_extract_viz_usage_dimension():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    usage = _s._extract_viz_usage(root, "federated.abc")
    # school_name should appear as dimension in Overview
    school_entries = usage.get("school_name", [])
    assert any(e["role"] == "dimension" for e in school_entries)


def test_extract_viz_usage_measure_with_aggregation():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    usage = _s._extract_viz_usage(root, "federated.abc")
    present_entries = usage.get("is_present", [])
    assert any(e["role"] == "measure" and e["aggregation"] == "SUM" for e in present_entries)
    assert any(e["role"] == "measure" and e["aggregation"] == "AVG" for e in present_entries)


def test_extract_viz_usage_multiple_worksheets():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    usage = _s._extract_viz_usage(root, "federated.abc")
    present_entries = usage.get("is_present", [])
    worksheets = {e["worksheet"] for e in present_entries}
    assert "Overview" in worksheets
    assert "Trend" in worksheets
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: 3 FAIL — `_extract_viz_usage` not defined.

- [ ] **Step 4: Implement `_extract_viz_usage`**

Add to `scripts/tableau-analyze-workbook.py`:

```python
def _field_name_from_ref(ref: str) -> str | None:
    """Extract the bare field name from a Tableau shelf reference like [school_name]
    or SUM([is_present]). Returns None for empty or system refs."""
    m = _FIELD_REF_RE.search(ref)
    if not m:
        return None
    name = m.group(1)
    if name.startswith(":") or name == "Number of Records":
        return None
    return name


def _extract_viz_usage(root, datasource_name: str) -> dict[str, list[dict]]:
    """Return a mapping of field name → list of {worksheet, role, aggregation}
    by parsing all worksheets that reference the given datasource."""
    usage: dict[str, list[dict]] = {}

    def _record(field_name: str, worksheet: str, role: str, aggregation: str | None):
        usage.setdefault(field_name, []).append(
            {"worksheet": worksheet, "role": role, "aggregation": aggregation}
        )

    for ws in root.findall(".//worksheets/worksheet"):
        ws_name = ws.get("name", "")
        view = ws.find("table/view")
        if view is None:
            continue

        # Check if this worksheet uses our datasource
        ds_refs = {ds.get("name") for ds in view.findall("datasources/datasource")}
        if datasource_name not in ds_refs:
            continue

        # Dimension shelves: rows, cols, pages
        for shelf in ("rows", "cols", "pages"):
            text = view.findtext(shelf) or ""
            for ref in _FIELD_REF_RE.findall(text):
                name = _field_name_from_ref(f"[{ref}]")
                if name:
                    _record(name, ws_name, "dimension", None)

        # Filters
        for f in view.findall("filter"):
            field_ref = f.findtext("field") or ""
            name = _field_name_from_ref(field_ref)
            if name:
                _record(name, ws_name, "dimension", None)

        # Mark encodings (measures with aggregations)
        for encoding_parent in ws.findall(".//encodings"):
            for enc in encoding_parent:
                field_el = enc.find("field")
                agg_el = enc.find("aggregation")
                if field_el is None:
                    continue
                name = _field_name_from_ref(field_el.text or "")
                if name and agg_el is not None:
                    _record(name, ws_name, "measure", agg_el.text)

    return usage
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/tableau-analyze-workbook.py tests/scripts/
git commit -m "feat(tableau): add viz usage extraction (dimension/measure roles per worksheet)"
```

---

## Task 5: Parameters and standalone LOD expressions

**Files:**

- Modify: `scripts/tableau-analyze-workbook.py`
- Modify: `tests/scripts/test_tableau_analyze_workbook.py`
- Create: `tests/scripts/fixtures/params_lods.twb`

- [ ] **Step 1: Create the params/LODs fixture**

Create `tests/scripts/fixtures/params_lods.twb`:

```xml
<?xml version='1.0' encoding='utf-8' ?>
<workbook source-build='2023.3' version='18.1'>
  <datasources>
    <datasource caption='Parameters' name='Parameters'>
      <!-- Discrete parameter (fixed list) -->
      <column caption='Academic Year' datatype='integer' name='[Parameter 1]'
              param-domaintype='list' role='measure' type='quantitative'>
        <aliases>
          <alias key='2023' value='2023' />
          <alias key='2024' value='2024' />
          <alias key='2025' value='2025' />
        </aliases>
      </column>
      <!-- Range parameter -->
      <column caption='Min Attendance' datatype='real' name='[Parameter 2]'
              param-domaintype='range' role='measure' type='quantitative'>
        <range granularity='0.01' max='1.0' min='0.0' />
      </column>
    </datasource>
    <datasource caption='rpt_tableau__test (kipptaf_tableau)' name='federated.abc'>
      <!-- Standalone LOD expression -->
      <column caption='School Avg Attendance' datatype='real' name='[Calculation_999]'
              role='measure'>
        <calculation class='tableau'
                     formula='{ FIXED [school_id] : AVG([is_present]) }' />
      </column>
      <column caption='is_present' datatype='integer' name='[is_present]' role='measure' />
    </datasource>
  </datasources>
  <worksheets />
</workbook>
```

- [ ] **Step 2: Write failing tests**

Add to `tests/scripts/test_tableau_analyze_workbook.py`:

```python
def test_extract_parameters_discrete():
    twb_bytes = (FIXTURES / "params_lods.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    params_ds = next(
        ds for ds in root.findall(".//datasources/datasource")
        if (ds.get("caption") or ds.get("name", "")) == "Parameters"
    )
    params = _s._extract_parameters(params_ds)
    academic = next(p for p in params if p["name"] == "Academic Year")
    assert academic["value_type"] == "discrete"
    assert 2024 in academic["allowed_values"]


def test_extract_parameters_range():
    twb_bytes = (FIXTURES / "params_lods.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    params_ds = next(
        ds for ds in root.findall(".//datasources/datasource")
        if (ds.get("caption") or ds.get("name", "")) == "Parameters"
    )
    params = _s._extract_parameters(params_ds)
    min_att = next(p for p in params if p["name"] == "Min Attendance")
    assert min_att["value_type"] == "range"
    assert min_att["min"] == "0.0"
    assert min_att["max"] == "1.0"


def test_extract_lod_expressions():
    twb_bytes = (FIXTURES / "params_lods.twb").read_bytes()
    root = _s.ET.fromstring(twb_bytes)
    ds = next(
        ds for ds in root.findall(".//datasources/datasource")
        if "rpt_tableau" in (ds.get("caption") or "")
    )
    lods = _s._extract_lod_expressions(ds)
    assert any("School Avg Attendance" in l["name"] for l in lods)
    assert any("FIXED" in l["formula"] for l in lods)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: 3 FAIL.

- [ ] **Step 4: Implement parameters and LOD extraction**

Add to `scripts/tableau-analyze-workbook.py`:

```python
def _extract_parameters(params_datasource) -> list[dict]:
    """Extract parameters from the Parameters datasource element."""
    results = []
    for col in params_datasource.findall("column"):
        caption = col.get("caption", "")
        if not caption:
            continue
        datatype = col.get("datatype", "unknown")
        domain_type = col.get("param-domaintype", "")
        if domain_type == "range":
            range_el = col.find("range")
            results.append(
                {
                    "name": caption,
                    "datatype": datatype,
                    "value_type": "range",
                    "min": range_el.get("min") if range_el is not None else None,
                    "max": range_el.get("max") if range_el is not None else None,
                }
            )
        else:
            allowed = [
                int(a.get("key")) if datatype == "integer" else a.get("key")
                for a in col.findall("aliases/alias")
            ]
            results.append(
                {
                    "name": caption,
                    "datatype": datatype,
                    "value_type": "discrete",
                    "allowed_values": allowed,
                }
            )
    return results


def _extract_lod_expressions(datasource) -> list[dict]:
    """Extract standalone named LOD calculated fields from a datasource."""
    name_map = _build_calc_name_map(datasource)
    lods = []
    for col in datasource.findall("column"):
        if _is_internal(col):
            continue
        calc = col.find("calculation[@class='tableau']")
        if calc is None:
            continue
        formula = _resolve_calc_refs(calc.get("formula", ""), name_map)
        if _LOD_RE.search(formula):
            lods.append(
                {
                    "name": col.get("caption") or col.get("name", "").strip("[]"),
                    "formula": formula,
                }
            )
    return lods
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/tableau-analyze-workbook.py tests/scripts/
git commit -m "feat(tableau): add parameter and LOD expression extraction"
```

---

## Task 6: JSON assembly and integration test

**Files:**

- Modify: `scripts/tableau-analyze-workbook.py`
- Modify: `tests/scripts/test_tableau_analyze_workbook.py`

- [ ] **Step 1: Write failing integration test**

Add these imports at the top of `tests/scripts/test_tableau_analyze_workbook.py`
alongside the existing ones:

```python
import json
import subprocess
```

Then add the tests:

```python
def test_parse_workbook_returns_full_structure():
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    result = _s.parse_workbook(twb_bytes)
    assert "datasources" in result
    assert len(result["datasources"]) == 1
    ds = result["datasources"][0]
    assert "caption" in ds
    assert "fields" in ds
    assert "parameters" in ds
    assert "lod_expressions" in ds
    # Plain field should have viz_usage populated
    school = next(f for f in ds["fields"] if f["name"] == "school_name")
    assert len(school["viz_usage"]) > 0


def test_parse_workbook_calc_field_viz_usage():
    """Calculated fields are referenced on shelves by internal name, not caption.
    parse_workbook must map the internal name back to the caption for the lookup."""
    twb_bytes = (FIXTURES / "minimal.twb").read_bytes()
    result = _s.parse_workbook(twb_bytes)
    ds = result["datasources"][0]
    rate = next((f for f in ds["fields"] if f["name"] == "Attendance Rate"), None)
    # Attendance Rate is on a shelf in the fixture — viz_usage must not be empty
    assert rate is not None
    assert len(rate["viz_usage"]) > 0


def test_cli_outputs_valid_json():
    result = subprocess.run(
        [
            "uv", "run",
            "scripts/tableau-analyze-workbook.py",
            "--file", str(FIXTURES / "minimal.twb"),
        ],
        capture_output=True,
        text=True,
        cwd=FIXTURES.parents[2],
    )
    data = json.loads(result.stdout)
    assert "datasources" in data
```

**Note:** also extend `tests/scripts/fixtures/minimal.twb` to place
`[Calculation_111]` (the Attendance Rate field) on a worksheet shelf so
`test_parse_workbook_calc_field_viz_usage` can assert non-empty `viz_usage`. Add
it to the `<rows>` or as a mark encoding in the Overview worksheet.

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py::test_parse_workbook_returns_full_structure -v
```

Expected: FAIL — `parse_workbook` returns empty `{"datasources": []}`.

- [ ] **Step 3: Implement `parse_workbook`**

Replace the placeholder `parse_workbook` in
`scripts/tableau-analyze-workbook.py`:

```python
def parse_workbook(twb_bytes: bytes) -> dict:
    """Parse .twb XML and return the full analysis dict."""
    root = ET.fromstring(twb_bytes)
    seen: set[str] = set()
    datasources = []

    # Find the Parameters datasource if present
    params_ds = None
    for ds in root.findall(".//datasources/datasource"):
        caption = ds.get("caption") or ds.get("name", "")
        if caption == "Parameters":
            params_ds = ds
            break

    for ds in root.findall(".//datasources/datasource"):
        caption = ds.get("caption") or ds.get("name", "")
        if caption == "Parameters" or caption in seen:
            continue
        seen.add(caption)

        ds_name = ds.get("name", "")
        fields = _extract_fields(ds)
        viz_usage = _extract_viz_usage(root, ds_name)

        # Attach viz_usage to each field.
        # Calculated fields are referenced on shelves by their opaque internal name
        # (e.g. "Calculation_111"), not their human caption ("Attendance Rate").
        # Build an inverse map: caption → internal name so we can look up correctly.
        calc_name_map = _build_calc_name_map(ds)  # internal → caption
        inv_map = {caption: internal for internal, caption in calc_name_map.items()}
        for field in fields:
            # For calc fields, look up by internal name; for plain fields by caption
            lookup_key = inv_map.get(field["name"], field["name"])
            field["viz_usage"] = viz_usage.get(lookup_key, [])

        datasources.append(
            {
                "caption": caption,
                "fields": fields,
                "parameters": _extract_parameters(params_ds) if params_ds else [],
                "lod_expressions": _extract_lod_expressions(ds),
            }
        )

    return {"datasources": datasources}
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: all PASS.

- [ ] **Step 5: Smoke-test the CLI manually**

```bash
uv run scripts/tableau-analyze-workbook.py --file tests/scripts/fixtures/minimal.twb
```

Expected: valid JSON printed to stdout with the correct structure.

- [ ] **Step 6: Commit**

```bash
git add scripts/tableau-analyze-workbook.py tests/scripts/
git commit -m "feat(tableau): wire parse_workbook and complete JSON assembly"
```

---

## Task 7: Tableau Server fetch mode (`--exposure`)

**Files:**

- Modify: `scripts/tableau-analyze-workbook.py`
- Modify: `tests/scripts/test_tableau_analyze_workbook.py`

> **Before implementing:** Read `src/teamster/libraries/tableau/resources.py` to
> get the exact env var names (`TABLEAU_SERVER_ADDRESS`, `TABLEAU_SITE_ID`,
> `TABLEAU_TOKEN_NAME`, `TABLEAU_PERSONAL_ACCESS_TOKEN`). Implement the auth and
> download flow using the patterns described in the preamble above.

- [ ] **Step 1: Write a failing test using a mock**

Add to `tests/scripts/test_tableau_analyze_workbook.py`:

```python
from unittest.mock import MagicMock, patch


def test_fetch_from_server_calls_correct_endpoint(monkeypatch):
    # Read src/teamster/libraries/tableau/resources.py to get the real var names,
    # then monkeypatch them here.
    monkeypatch.setenv("TABLEAU_SERVER_ADDRESS", "https://tableau.example.com")
    monkeypatch.setenv("TABLEAU_SITE_ID", "site")
    # Add the remaining required credential variables (names from resources.py)

    fake_twbx = (FIXTURES / "minimal.twb").read_bytes()

    with patch.object(_s.requests, "post") as mock_post, \
         patch.object(_s.requests, "get") as mock_get:
        # Sign-in response
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"credentials": {"token": "tok", "site": {"id": "siteid"}}},
        )
        # Workbook list response (match exposure LSID from tableau.yml)
        exposures = _s.yaml.safe_load(
            (pathlib.Path("src/dbt/kipptaf/models/exposures/tableau.yml")).read_text()
        )
        first_exposure = next(
            e for e in exposures["exposures"]
            if e.get("meta", {}).get("lsid")
        )
        lsid = first_exposure["meta"]["lsid"]
        exposure_name = first_exposure["name"]

        mock_get.return_value = MagicMock(
            status_code=200, content=fake_twbx
        )

        result = _s._fetch_from_server(exposure_name)
        assert b"<workbook" in result
        # Verify download URL contained the LSID
        download_url = mock_get.call_args[0][0]
        assert lsid in download_url
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py::test_fetch_from_server_calls_correct_endpoint -v
```

Expected: FAIL — `_fetch_from_server` raises `NotImplementedError`.

- [ ] **Step 3: Implement `_fetch_from_server`**

Implement the auth + download flow using the patterns described in the preamble.
Key steps:

1. Load `EXPOSURES_PATH`, find the exposure by name, read its `meta.lsid`
2. Read credentials from the environment variables defined in
   `TableauServerResource`
3. POST to the sign-in endpoint → get token + site ID
4. GET the workbook download endpoint using the LSID
5. If the response content is a `.twbx` (zip), call
   `extract_twb_bytes_from_bytes`; otherwise return the content directly

- [ ] **Step 4: Run all tests**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/tableau-analyze-workbook.py tests/scripts/
git commit -m "feat(tableau): add Tableau Server fetch mode via exposure name"
```

---

## Task 8: Slash command

**Files:**

- Create: `.claude/commands/star-schema-advisor.md`

> **Note:** `.claude/` is a read-only path for Edit/Write tools (hook
> protection). Draft the file content here and apply it manually, or ask the
> user to apply it. The file must be staged and committed manually as well.

- [ ] **Step 1: Draft the command content**

The command file must implement the full 8-step workflow from the spec. Write
`.claude/commands/star-schema-advisor.md` with the following content:

````markdown
# /star-schema-advisor

Guide an analyst through triaging a single Tableau reporting-view datasource
into dims, facts, semantic layer candidates, BI migration targets, and skips.
Apply approved dbt mart changes and write a persistent report for
`/cube-measure-generator`.

---

## Step 1 — Source the workbook

Ask the analyst:

> "Do you have a local `.twb`/`.twbx` file, or should I pull from Tableau
> Server? (Note: do not place workbook files inside the repository — they must
> not be committed.)"

- **Local file:** ask for the path.
- **Tableau Server:** read `src/dbt/kipptaf/models/exposures/tableau.yml` and
  list all exposures as a numbered list (`name` + `label`). Ask the analyst to
  pick one. Validate: re-prompt if the selection is out of range or
  unrecognised.

Before proceeding, check `docs/superpowers/star-schema-reports/` for existing
reports matching this exposure name. If any are found, show them and ask:

> "I found existing reports for this workbook:
>
> - ✓ `<filename>`
>
> Remaining datasources: `<list>`. Pick up where you left off?"

---

## Step 2 — Run the extraction script

```bash
uv run scripts/tableau-analyze-workbook.py --exposure <name>
# or
uv run scripts/tableau-analyze-workbook.py --file <path>
```
````

Parse the JSON output. If the workbook has multiple datasources, list them all
with field counts and ask which to start with. Hold the JSON in memory for the
session — do not re-run the script when looping to the next datasource.

Report filename convention (always include a datasource slug):
`<exposure-name>-<datasource-slug>-<YYYY-MM-DD>.md`

---

## Step 3 — Read the reporting view

Map the datasource caption to the dbt model name: strip everything from the
first space or `(` onward. Example:
`"rpt_tableau__attendance_dashboard (kipptaf_tableau)"` →
`rpt_tableau__attendance_dashboard`

Read:

- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__<name>.sql`
- `src/dbt/kipptaf/models/extracts/tableau/properties/rpt_tableau__<name>.yml`

Note columns already present to avoid duplicate promotion.

---

## Step 4 — Read existing marts

Scan all `src/dbt/kipptaf/models/marts/properties/*.yml` files and build a
lookup: column name → mart model name.

When processing a second or later datasource in the same session, mart files may
already have been modified by Step 7 of an earlier datasource. The re-scan will
pick these up since edits are on disk. Label these hits **"Already in marts
(promoted this session)"** — distinct from **"Already in marts"** (present
before this session started).

Include the matched mart name in the Notes column so the analyst can verify the
grain.

For fields that do **not** match by name, do a secondary check using the dbt MCP
`get_node_details_dev` tool on the rpt model. Use the compiled SQL to find the
source expression for each unmatched field. If it is a direct column reference
(no calculation), check whether that upstream column name matches any mart
column and flag the hit as **"Possible match — verify alias"** with the mart
name and upstream column name. If it is a calculation, leave it unmatched — it
likely belongs in the semantic layer.

---

## Step 5 — Classify every field

Apply these rules to every field in the datasource JSON.

For plain columns aggregated in viz, also add them to the Semantic Layer Queue —
one entry per aggregation type. A column SUM'd in one sheet and AVG'd in another
gets two queue entries, not an "Ambiguous" verdict. Reserve **Ambiguous** only
for fields used as both a dimension AND a measure across worksheets.

For LOD fields (`contains_lod: true` or standalone LOD expressions), classify as
**Semantic layer — review grain** and add to the LOD subsection of the Semantic
Layer Queue. The analyst decides whether the logic belongs in dbt (pre-agg) or
Cube (measure), or both.

| Condition                                                            | Verdict                                             |
| -------------------------------------------------------------------- | --------------------------------------------------- |
| Column name matches an existing mart column                          | **Already in marts**                                |
| Plain column, dimension role in viz (rows/cols/filters/pages)        | **→ dim**                                           |
| Plain column, aggregated one way in viz                              | **→ fact** + queue Cube measure                     |
| Plain column, aggregated multiple ways in viz                        | **→ fact** + queue one Cube measure per aggregation |
| Calculated field, measure role in viz                                | **→ semantic layer**                                |
| Calculated field, dimension role (simple: date trunc, string concat) | **→ dim**                                           |
| Calculated field, dimension role (complex business logic)            | **→ semantic layer**                                |
| Plain or calculated field in both dimension and measure roles        | **Ambiguous — analyst decision**                    |
| `contains_lod: true` OR standalone LOD expression                    | **Semantic layer — review grain**                   |
| Parameter reference                                                  | **Recreate in BI (dynamic filter)**                 |
| Formula uses `USERNAME()` or other server-side function              | **Skip / investigate**                              |
| Formatting / display-only label                                      | **Recreate in BI**                                  |

---

## Step 6 — Write and display the report

Write
`docs/superpowers/star-schema-reports/<exposure-name>-<datasource-slug>-<YYYY-MM-DD>.md`
using the report structure below. Display it inline in chat.

Then ask:

> "Report written to `docs/superpowers/star-schema-reports/<filename>`. Please
> review the Field Verdicts table — override any verdict by editing the file
> directly or telling me the changes in chat. Say 'go ahead' when ready."

**Wait for confirmation before writing any dbt files.**

### Report structure

```markdown
# Star Schema Analysis: <Workbook Label>

**Date:** YYYY-MM-DD **Reporting view:** `rpt_tableau__<name>` **Source:**
<exposure name or file path> **Datasource analyzed:** <caption>

---

## Field Verdicts

| Field | Datatype | Viz Usage | Aggregation | Verdict | Notes |
| ----- | -------- | --------- | ----------- | ------- | ----- |

---

## Fields Requiring Analyst Decision

| Field | Dimension Usage | Measure Usage | Proposed Verdict |
| ----- | --------------- | ------------- | ---------------- |

---

## Proposed Mart Changes

### Additions to existing models

### New models required

---

## Semantic Layer Queue

| Field | Source Model | Viz Aggregation | Tableau Formula |
| ----- | ------------ | --------------- | --------------- |

### LOD Expressions — Analyst Review Required

LOD expressions encode aggregation grain logic. For each, the analyst decides:
push to dbt (pre-agg), Cube measure, or both.

| Field | Formula | Grain | Recommended approach |
| ----- | ------- | ----- | -------------------- |

---

## BI Migration Notes

### LOD Expressions

> Full analyst review table is in `## Semantic Layer Queue` above. Raw formulas
> only.

| Field | Formula |
| ----- | ------- |

### Parameters

> Do not port values directly — recreate as dynamic user-facing filters in Cube.

| Name | Datatype | Type | Tableau values (reference only) | Suggested Cube approach |
| ---- | -------- | ---- | ------------------------------- | ----------------------- |

### Display / Formatting Labels

| Field | Tableau Formula |
| ----- | --------------- |

### Skip / Investigate

| Field | Reason |
| ----- | ------ |
```

---

## Step 7 — Apply approved changes

Write all dbt changes but **do not stage or commit anything**. After writing,
list every file modified or created:

> "I've updated the following files — review them with `git diff` before
> staging: [list]. The report file is ready to commit now as an audit trail."

**Adding to an existing mart:**

- Add column to SQL `SELECT` following `src/dbt/CLAUDE.md` column ordering
  (plain refs → simple functions → nested functions → logicals → CASE → window)
- Add entry to properties YAML: `name`, `data_type`, optional `description`
- `.sqlfluff` style: trailing commas, single quotes, max 88 chars

**Creating a new mart:**

- Draft `dim_<name>.sql` / `fct_<name>.sql` with skeleton `SELECT` + `WITH`
- Include surrogate key: `dbt_utils.generate_surrogate_key([<grain_cols>])` —
  propose the grain columns to the analyst before writing
- Properties YAML: `contract: enforced: true`, simple `unique:` test on the
  surrogate key column (not `dbt_utils.unique_combination_of_columns`)
- Surface the full draft for analyst review before writing

**Prepare manifest then validate:**

```bash
uv run dagster-dbt project prepare-and-package \
  --file src/teamster/code_locations/kipptaf/__init__.py
```

Then via dbt MCP:

```text
dbt show --select <model_name> --limit 5
```

> **Note:** `dbt show` requires a live BigQuery connection (GCP credentials via
> `.devcontainer/scripts/inject-secrets.sh`). `prepare-and-package` works
> without credentials and should always be run. If credentials are unavailable,
> skip `dbt show` and tell the analyst to run it manually after injecting
> secrets.

---

## Step 8 — Wrap up

Report:

- Files modified or created
- Fields skipped and why
- Confirm `## Semantic Layer Queue` section is populated

If the workbook has remaining datasources not yet analyzed:

> "This workbook has N more datasource(s) not yet analyzed:
>
> - `rpt_tableau__foo` — 22 fields
>
> Continue to the next one, or stop here?"

If continuing, loop back to Step 3. Do not re-run the script.

When all datasources are complete, give a consolidated session summary:

> "All datasources analyzed. Here's everything changed this session:
>
> **Mart changes** (unstaged — review with `git diff` before staging):
>
> - `<model>`: added `<col1>`, `<col2>`
>
> **New models drafted** (if any): `<model>.sql` + YAML — review before staging
>
> **Reports written** (commit these now):
>
> - `<report-filename>`
>
> **Semantic layer fields queued:** N fields total — run
> `/cube-measure-generator` pointing at any report file when ready."

````markdown
- [ ] **Step 2: Apply the file manually**

Draft presented above — apply to `.claude/commands/star-schema-advisor.md`
manually (hook blocks Write on `.claude/` paths). Then stage and commit:

```bash
git add .claude/commands/star-schema-advisor.md
git commit -m "feat: add /star-schema-advisor slash command"
```
````

---

## Task 9: Reports directory and final validation

**Files:**

- Create: `docs/superpowers/star-schema-reports/.gitkeep`

- [ ] **Step 1: Create the directory and gitkeep**

```bash
mkdir -p docs/superpowers/star-schema-reports
touch docs/superpowers/star-schema-reports/.gitkeep
```

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest tests/scripts/test_tableau_analyze_workbook.py -v
```

Expected: all PASS.

- [ ] **Step 3: Validate the Dagster definitions still load**

```bash
uv run dagster definitions validate \
  -m teamster.code_locations.kipptaf.definitions
```

Expected: `Validation successful`.

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/star-schema-reports/.gitkeep
git commit -m "chore: add star-schema-reports directory for per-run reports"
```
