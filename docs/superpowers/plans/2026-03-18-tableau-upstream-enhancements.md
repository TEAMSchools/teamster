# Tableau Upstream Enhancements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development
> (if subagents available) or superpowers:executing-plans to implement this
> plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add smart field categorization (READY/NEEDS WORK/LOD/SKIP) to
`scripts/tableau-extract-calcs.py` and extend the `/tableau-upstream` slash
command with categorized workflow UX and dbt DAG lineage tracing.

**Architecture:** Classification logic is added as pure helper functions in the
script (unit-testable). Output is restructured into grouped sections. The slash
command gains a categorized summary prompt, format-preference question,
LOD/NEEDS WORK handling, and a new Step 4b that uses the dbt MCP to trace column
lineage and recommend insertion points.

**Tech Stack:** Python 3.12, `pyyaml`, `defusedxml`, pytest — existing script
dependencies. dbt MCP server tools (`get_lineage_dev`, `get_node_details_dev`)
for lineage in the slash command (no new script dependencies).

---

## Specs

- [docs/superpowers/specs/2026-03-18-tableau-calc-field-categorization-design.md](../specs/2026-03-18-tableau-calc-field-categorization-design.md)
- [docs/superpowers/specs/2026-03-18-tableau-upstream-lineage-tracing-design.md](../specs/2026-03-18-tableau-upstream-lineage-tracing-design.md)

---

## File Map

| File                                          | Action | Responsibility                                                                                      |
| --------------------------------------------- | ------ | --------------------------------------------------------------------------------------------------- |
| `scripts/tableau-extract-calcs.py`            | Modify | Add `--model`/`-m` flag, classification helpers, LOD mart-matching, grouped output                  |
| `.claude/commands/tableau-upstream.md`        | Modify | Add categorized summary, output format preference, LOD/NEEDS WORK handling, Step 4b lineage tracing |
| `tests/scripts/test_tableau_extract_calcs.py` | Create | Unit tests for all new pure helper functions                                                        |

---

## Task 1: Add classification helper functions (pure logic)

**Files:**

- Modify: `scripts/tableau-extract-calcs.py` (after the `# ── Output` section
  comment, add a new `# ── Classification` section)
- Create: `tests/scripts/test_tableau_extract_calcs.py`

These functions have no I/O — test them first.

- [ ] **Step 1: Create the test file with a script import helper**

Create `tests/scripts/test_tableau_extract_calcs.py` (no `__init__.py` needed —
pytest discovers tests without it, consistent with the rest of `tests/`):

```python
import importlib.util
import pathlib

import pytest

# Load the script as a module (PEP 723 scripts aren't installable packages)
_SCRIPT = pathlib.Path(__file__).parents[2] / "scripts" / "tableau-extract-calcs.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("tableau_extract_calcs", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def script():
    return _load_script()
```

- [ ] **Step 2: Write failing tests for `extract_field_refs`**

Add to the test file:

```python
class TestExtractFieldRefs:
    def test_simple_refs(self, script):
        assert script.extract_field_refs("[GPA Y1] + [Credits]") == ["GPA Y1", "Credits"]

    def test_no_refs(self, script):
        assert script.extract_field_refs("'literal string'") == []

    def test_parameters_ref(self, script):
        # regex matches each [...] block: [Parameters] and [Min GPA] separately
        assert script.extract_field_refs("[Parameters].[Min GPA]") == ["Parameters", "Min GPA"]

    def test_lod_refs(self, script):
        refs = script.extract_field_refs("{FIXED [school_id] : SUM([absences])}")
        assert "school_id" in refs
        assert "absences" in refs

    def test_duplicate_refs_deduplicated(self, script):
        refs = script.extract_field_refs("[x] + [x]")
        assert refs.count("x") == 1
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_extract_calcs.py::TestExtractFieldRefs -v
```

Expected: `AttributeError: module ... has no attribute 'extract_field_refs'`

- [ ] **Step 4: Implement `extract_field_refs` in the script**

Add a new section
`# ── Classification ─────────────────────────────────────────────────────────`
after the `# ── Output` section, before `# ── Interactive mode`:

```python
import re  # add to the top-level imports

# ── Classification ───────────────────────────────────────────────────────────

_FIELD_REF_RE = re.compile(r"\[([^\]]+)\]")


def extract_field_refs(formula: str) -> list[str]:
    """Return unique [Field Name] references extracted from a Tableau formula."""
    seen: set[str] = set()
    refs = []
    for match in _FIELD_REF_RE.finditer(formula):
        ref = match.group(1)
        if ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_extract_calcs.py::TestExtractFieldRefs -v
```

Expected: all 5 pass.

- [ ] **Step 6: Write failing tests for `is_lod`, `is_skip`, and
      `classify_field`**

```python
class TestIsLod:
    def test_fixed(self, script):
        assert script.is_lod("{FIXED [school_id] : SUM([absences])}") is True

    def test_include(self, script):
        assert script.is_lod("{INCLUDE [dim] : AVG([val])}") is True

    def test_exclude(self, script):
        assert script.is_lod("{EXCLUDE [x] : MIN([y])}") is True

    def test_normal_formula(self, script):
        assert script.is_lod("IF [x] > 0 THEN 'yes' END") is False


class TestIsSkip:
    def test_username_only(self, script):
        assert script.is_skip("USERNAME()") is True

    def test_literal_only(self, script):
        assert script.is_skip("'some string'") is True

    def test_parameters_only(self, script):
        assert script.is_skip("[Parameters].[Min GPA]") is True

    def test_real_column_ref(self, script):
        assert script.is_skip("[actual_column]") is False

    def test_mixed_username_and_column(self, script):
        # USERNAME() mixed with real column ref is NOT skip
        assert script.is_skip("IF USERNAME() = 'x' THEN [gpa] END") is False


class TestClassifyField:
    def test_ready(self, script):
        result = script.classify_field("[gpa] + [credits]", {"gpa", "credits"})
        assert result == "READY"

    def test_needs_work(self, script):
        result = script.classify_field("[gpa] + [unknown_col]", {"gpa"})
        assert result == "NEEDS WORK"

    def test_lod(self, script):
        result = script.classify_field(
            "{FIXED [school_id] : SUM([absences])}", {"school_id", "absences"}
        )
        assert result == "LOD"

    def test_skip(self, script):
        result = script.classify_field("USERNAME()", set())
        assert result == "SKIP"

    def test_lod_beats_needs_work(self, script):
        # LOD check runs first — unresolved refs don't change the category
        result = script.classify_field("{FIXED [x] : SUM([y])}", set())
        assert result == "LOD"

    def test_no_known_columns_all_skip(self, script):
        result = script.classify_field("[Parameters].[x]", set())
        assert result == "SKIP"
```

- [ ] **Step 7: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_extract_calcs.py::TestIsLod tests/scripts/test_tableau_extract_calcs.py::TestIsSkip tests/scripts/test_tableau_extract_calcs.py::TestClassifyField -v
```

Expected: `AttributeError` for all three missing functions.

- [ ] **Step 8: Implement `is_lod`, `is_skip`, and `classify_field`**

Add to the `# ── Classification` section:

```python
_LOD_RE = re.compile(r"\{(FIXED|INCLUDE|EXCLUDE)\b", re.IGNORECASE)
_PARAMETERS_FULL_RE = re.compile(r"\[Parameters\]\.\[[^\]]*\]", re.IGNORECASE)


def is_lod(formula: str) -> bool:
    """Return True if the formula contains a Tableau LOD expression."""
    return bool(_LOD_RE.search(formula))


_PARAMETERS_FULL_RE = re.compile(r"\[Parameters\]\.\[[^\]]*\]", re.IGNORECASE)


def is_skip(formula: str) -> bool:
    """
    Return True if the formula has zero real column refs — only USERNAME(),
    bare literals, and/or [Parameters].* references.
    """
    # Erase the full [Parameters].[...] construct (both bracket pairs)
    stripped = _PARAMETERS_FULL_RE.sub("", formula)
    # Strip USERNAME() calls
    stripped = re.sub(r"\bUSERNAME\(\)", "", stripped, flags=re.IGNORECASE)
    # Strip string literals
    stripped = re.sub(r"'[^']*'", "", stripped)
    # Strip numeric literals
    stripped = re.sub(r"\b\d+(\.\d+)?\b", "", stripped)
    # Check whether any [Field] refs remain
    return not bool(_FIELD_REF_RE.search(stripped))


def classify_field(formula: str, known_columns: set[str]) -> str:
    """
    Classify a Tableau calculated field formula into one of four categories:
    READY, NEEDS WORK, LOD, or SKIP.

    Priority order: LOD → SKIP → ref resolution.
    """
    if is_lod(formula):
        return "LOD"
    if is_skip(formula):
        return "SKIP"
    refs = extract_field_refs(formula)
    known_lower = {c.lower() for c in known_columns}
    if all(r.lower() in known_lower for r in refs):
        return "READY"
    return "NEEDS WORK"
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_extract_calcs.py -v
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```bash
git add scripts/tableau-extract-calcs.py tests/scripts/test_tableau_extract_calcs.py
git commit -m "feat: add field classification helpers to tableau-extract-calcs"
```

---

## Task 2: Add YAML column loader and auto-detection

**Files:**

- Modify: `scripts/tableau-extract-calcs.py`
- Modify: `tests/scripts/test_tableau_extract_calcs.py`

- [ ] **Step 1: Write failing tests**

```python
import pathlib
import yaml  # add to test file imports

class TestDetectModelFromCaption:
    def test_strips_schema_suffix(self, script):
        result = script.detect_model_from_caption(
            "rpt_tableau__gradebook_gpa_cumulative (kipptaf_tableau)"
        )
        assert result == "rpt_tableau__gradebook_gpa_cumulative"

    def test_no_suffix_returns_none(self, script):
        result = script.detect_model_from_caption("Some Other Data Source")
        assert result is None

    def test_whitespace_variations(self, script):
        result = script.detect_model_from_caption(
            "rpt_tableau__some_model  (kipptaf_tableau)"
        )
        assert result == "rpt_tableau__some_model"


class TestLoadModelColumns:
    def test_loads_column_names(self, script, tmp_path):
        yml = tmp_path / "properties" / "rpt_tableau__test.yml"
        yml.parent.mkdir()
        yml.write_text(
            "models:\n"
            "  - name: rpt_tableau__test\n"
            "    columns:\n"
            "      - name: student_id\n"
            "        data_type: int64\n"
            "      - name: gpa_y1\n"
            "        data_type: float64\n"
        )
        cols = script.load_model_columns("rpt_tableau__test", properties_dir=tmp_path / "properties")
        assert cols == {"student_id", "gpa_y1"}

    def test_returns_empty_set_when_file_missing(self, script, tmp_path):
        cols = script.load_model_columns("nonexistent", properties_dir=tmp_path)
        assert cols == set()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_extract_calcs.py::TestDetectModelFromCaption tests/scripts/test_tableau_extract_calcs.py::TestLoadModelColumns -v
```

Expected: `AttributeError` for both missing functions.

- [ ] **Step 3: Implement `detect_model_from_caption` and `load_model_columns`**

Add to the `# ── Classification` section:

```python
TABLEAU_PROPERTIES_DIR = pathlib.Path(
    "src/dbt/kipptaf/models/extracts/tableau/properties"
)

_KIPPTAF_TABLEAU_RE = re.compile(r"\s*\(kipptaf_tableau\)\s*$", re.IGNORECASE)


def detect_model_from_caption(caption: str) -> str | None:
    """
    Derive a dbt model name from a datasource caption.
    Returns None if the caption doesn't match the kipptaf_tableau pattern.
    """
    if not _KIPPTAF_TABLEAU_RE.search(caption):
        return None
    return _KIPPTAF_TABLEAU_RE.sub("", caption).strip()


def load_model_columns(
    model_name: str,
    properties_dir: pathlib.Path = TABLEAU_PROPERTIES_DIR,
) -> set[str]:
    """
    Load the set of column names from a dbt model's YAML properties file.
    Returns an empty set if the file does not exist.
    """
    yml_path = properties_dir / f"{model_name}.yml"
    if not yml_path.exists():
        return set()
    data = yaml.safe_load(yml_path.read_text())
    columns: set[str] = set()
    for model in data.get("models", []):
        for col in model.get("columns", []):
            if name := col.get("name"):
                columns.add(name)
    return columns
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_extract_calcs.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/tableau-extract-calcs.py tests/scripts/test_tableau_extract_calcs.py
git commit -m "feat: add model column loader and caption auto-detection"
```

---

## Task 3: Add LOD mart-matching logic

**Files:**

- Modify: `scripts/tableau-extract-calcs.py`
- Modify: `tests/scripts/test_tableau_extract_calcs.py`

- [ ] **Step 1: Write failing tests**

```python
class TestLoadMartColumns:
    def test_loads_from_directory(self, script, tmp_path):
        mart_dir = tmp_path / "properties"
        mart_dir.mkdir()
        (mart_dir / "fct_attendance.yml").write_text(
            "models:\n"
            "  - name: fct_attendance\n"
            "    columns:\n"
            "      - name: student_id\n"
            "      - name: absences\n"
        )
        result = script.load_mart_columns(marts_dir=mart_dir)
        assert result == {"fct_attendance": {"student_id", "absences"}}

    def test_empty_directory(self, script, tmp_path):
        result = script.load_mart_columns(marts_dir=tmp_path)
        assert result == {}


class TestRecommendMart:
    def test_branch_a_single_match(self, script):
        mart_cols = {
            "fct_attendance": {"student_id", "absences", "school_id"},
            "dim_students": {"student_id", "grade_level"},
        }
        result = script.recommend_mart(["school_id", "absences"], mart_cols)
        assert result == "fct_attendance"

    def test_branch_b_no_match(self, script):
        mart_cols = {
            "fct_attendance": {"student_id", "absences"},
        }
        result = script.recommend_mart(["map_score", "rit_score"], mart_cols)
        assert result is None

    def test_empty_refs(self, script):
        result = script.recommend_mart([], {"fct_attendance": {"absences"}})
        assert result is None

    def test_tie_broken_by_count(self, script):
        mart_cols = {
            "fct_attendance": {"school_id", "absences"},
            "dim_students": {"school_id"},
        }
        result = script.recommend_mart(["school_id", "absences"], mart_cols)
        assert result == "fct_attendance"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/scripts/test_tableau_extract_calcs.py::TestLoadMartColumns tests/scripts/test_tableau_extract_calcs.py::TestRecommendMart -v
```

Expected: `AttributeError` for both missing functions.

- [ ] **Step 3: Implement `load_mart_columns` and `recommend_mart`**

Add to the `# ── Classification` section:

```python
MARTS_PROPERTIES_DIR = pathlib.Path("src/dbt/kipptaf/models/marts/properties")


def load_mart_columns(
    marts_dir: pathlib.Path = MARTS_PROPERTIES_DIR,
) -> dict[str, set[str]]:
    """
    Scan all YAML files in the marts properties directory and return a mapping
    of {mart_name: set_of_column_names}.
    """
    result: dict[str, set[str]] = {}
    for yml_path in marts_dir.glob("*.yml"):
        data = yaml.safe_load(yml_path.read_text())
        for model in data.get("models", []):
            name = model.get("name")
            if not name:
                continue
            cols = {
                c["name"]
                for c in model.get("columns", [])
                if c.get("name")
            }
            result[name] = cols
    return result


def recommend_mart(
    refs: list[str], mart_columns: dict[str, set[str]]
) -> str | None:
    """
    Return the mart name with the most matching columns for the given refs.
    Returns None if no mart has any matching columns (Branch B).
    """
    if not refs:
        return None
    refs_lower = {r.lower() for r in refs}
    scores = {
        mart: len(refs_lower & {c.lower() for c in cols})
        for mart, cols in mart_columns.items()
    }
    best_mart = max(scores, key=scores.get, default=None)
    if best_mart is None or scores[best_mart] == 0:
        return None
    return best_mart
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/scripts/test_tableau_extract_calcs.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/tableau-extract-calcs.py tests/scripts/test_tableau_extract_calcs.py
git commit -m "feat: add LOD mart-matching logic to tableau-extract-calcs"
```

---

## Task 4: Add `--model` flag and wire classification through the script

**Files:**

- Modify: `scripts/tableau-extract-calcs.py`

This task connects all the new helpers to the actual script flow and
restructures the output.

- [ ] **Step 1: Add `--model`/`-m` argument to `argparse` in `main()`**

In `main()`, after the `--list-only` argument, add:

```python
parser.add_argument(
    "--model",
    "-m",
    metavar="MODEL",
    help=(
        "dbt model name for column cross-referencing "
        "(e.g. rpt_tableau__gradebook_gpa_cumulative). "
        "Auto-detected from datasource caption in --exposure mode if omitted."
    ),
)
```

- [ ] **Step 2: Add a `classify_fields` helper that enriches the field list**

Add to the `# ── Classification` section:

```python
def classify_fields(
    fields: list[dict],
    known_columns: set[str],
    mart_columns: dict[str, set[str]],
) -> list[dict]:
    """
    Return a copy of fields with 'category', 'unresolved_refs', and
    'lod_recommendation' keys added to each field dict.
    """
    result = []
    for f in fields:
        formula = f["formula"]
        category = classify_field(formula, known_columns)
        refs = extract_field_refs(formula)

        unresolved: list[str] = []
        lod_rec: dict | None = None

        if category == "NEEDS WORK":
            known_lower = {c.lower() for c in known_columns}
            unresolved = [r for r in refs if r.lower() not in known_lower]
        elif category == "LOD":
            # Only attempt Branch A if all refs resolve to known columns
            known_lower = {c.lower() for c in known_columns}
            resolvable_refs = [r for r in refs if r.lower() in known_lower]
            unresolved_lod = [r for r in refs if r.lower() not in known_lower]
            if unresolved_lod:
                # Branch B — refs unresolved, cannot match mart
                lod_rec = {"branch": "B", "mart": None, "unresolved_refs": unresolved_lod}
            else:
                mart = recommend_mart(refs, mart_columns)
                lod_rec = {"branch": "A" if mart else "B", "mart": mart}

        result.append(
            {**f, "category": category, "unresolved_refs": unresolved, "lod_rec": lod_rec}
        )
    return result
```

- [ ] **Step 3: Replace `print_results` with a grouped-output version**

Replace the existing `print_results` function with:

```python
def print_results(
    fields: list[dict],
    workbook_label: str,
    depends_on: list[str] | None = None,
    known_columns: set[str] | None = None,
    model_name: str | None = None,
) -> None:
    mart_columns = load_mart_columns() if known_columns is not None else {}
    classified = classify_fields(fields, known_columns or set(), mart_columns)

    ready = [f for f in classified if f["category"] == "READY"]
    needs_work = [f for f in classified if f["category"] == "NEEDS WORK"]
    lod = [f for f in classified if f["category"] == "LOD"]
    skip = [f for f in classified if f["category"] == "SKIP"]

    model_label = f" → {model_name}" if model_name else ""
    print(f"\n## Calculated Fields: {workbook_label}{model_label}\n")

    if known_columns is not None:
        print(
            f"**{len(fields)} fields: "
            f"{len(ready)} READY · {len(needs_work)} NEEDS WORK · "
            f"{len(lod)} LOD · {len(skip)} SKIP**\n"
        )
    else:
        print(f"Total: {len(fields)} calculated fields (no model loaded — unclassified)\n")

    if depends_on:
        print("### dbt models (from exposure depends_on)\n")
        for dep in depends_on:
            print(f"  - {dep}")
        print()

    if not fields:
        print("No user-created calculated fields found.\n")
        return

    # When unclassified (no model), print the original flat table
    if known_columns is None:
        print("| Field Name | Data Type | Formula |")
        print("|---|---|---|")
        for f in classified:
            formula = f["formula"].replace("\n", " ").replace("|", "\\|")
            print(f"| {f['name']} | {f['datatype']} | {formula} |")
        return

    # ── READY ──────────────────────────────────────────────────────────────
    if ready:
        print(f"### ✓ READY ({len(ready)})\n")
        print("| Field Name | Data Type | Formula |")
        print("|---|---|---|")
        for f in ready:
            formula = f["formula"].replace("\n", " ").replace("|", "\\|")
            print(f"| {f['name']} | {f['datatype']} | {formula} |")
        print()

    # ── NEEDS WORK ─────────────────────────────────────────────────────────
    if needs_work:
        print(f"### ⚠ NEEDS WORK ({len(needs_work)})\n")
        print("| Field Name | Data Type | Formula | Unresolved Refs |")
        print("|---|---|---|---|")
        for f in needs_work:
            formula = f["formula"].replace("\n", " ").replace("|", "\\|")
            unresolved = ", ".join(f["unresolved_refs"])
            print(f"| {f['name']} | {f['datatype']} | {formula} | {unresolved} |")
        print()

    # ── LOD ────────────────────────────────────────────────────────────────
    if lod:
        print(f"### 🔷 LOD — semantic layer candidates ({len(lod)})\n")
        for f in lod:
            formula = f["formula"].replace("\n", " ")
            rec = f["lod_rec"] or {}
            print(f"**{f['name']}** (`{f['datatype']}`)")
            print(f"  Formula: `{formula}`")
            if rec.get("branch") == "A" and rec.get("mart"):
                print(
                    f"  ⚠ LOD — semantic layer candidate\n"
                    f"  Suggested mart: {rec['mart']} — add a pre-aggregated measure here,\n"
                    f"  then reference it from the Tableau extract instead of computing inline."
                )
            else:
                unresolved = rec.get("unresolved_refs", [])
                unresolved_note = (
                    f" (refs unresolved: {', '.join(unresolved)})" if unresolved else ""
                )
                print(
                    f"  ⚠ LOD — semantic layer candidate{unresolved_note}\n"
                    f"  No existing mart match found. A new fact table may be needed.\n"
                    f"  Discuss with the data engineer before adding this to the extract."
                )
            print()

    # ── SKIP ───────────────────────────────────────────────────────────────
    if skip:
        print(f"### ✗ SKIP ({len(skip)})\n")
        print("| Field Name | Data Type | Reason |")
        print("|---|---|---|")
        for f in skip:
            reason = "USERNAME()/Parameters/literal only — no SQL equivalent"
            print(f"| {f['name']} | {f['datatype']} | {reason} |")
        print()
```

- [ ] **Step 4: Wire model loading into all three modes (`--file`, `--exposure`,
      `--workbook`, `run_interactive`)**

Add this helper function to the `# ── Classification` section (it must be
defined before `main()`):

```python
def _resolve_model_and_columns(
    model_arg: str | None, actual_caption: str | None, file_mode: bool
) -> tuple[str | None, set[str]]:
    """
    Return (model_name, known_columns) based on --model flag and mode.

    actual_caption is the full datasource caption from the XML (e.g.
    'rpt_tableau__gradebook_gpa_cumulative (kipptaf_tableau)'), NOT the
    --datasource substring filter. Auto-detection is only attempted in
    exposure/workbook mode (file_mode=False).
    """
    if model_arg:
        return model_arg, load_model_columns(model_arg)
    if actual_caption and not file_mode:
        model_name = detect_model_from_caption(actual_caption)
        if model_name:
            cols = load_model_columns(model_name)
            return model_name, cols
    return None, set()
```

**In each of the three `main()` modes**, the datasource caption must be resolved
from the actual XML before calling `_resolve_model_and_columns`. When a
`--datasource` filter is given, use `list_datasources()` to find the matching
caption:

```python
# After parse_calculated_fields(twb_bytes, args.datasource):
actual_caption = next(
    (s["caption"] for s in list_datasources(twb_bytes)
     if args.datasource and args.datasource.lower() in s["caption"].lower()),
    None,
)
model_name, known_columns = _resolve_model_and_columns(
    args.model, actual_caption, file_mode=bool(args.file)
)
print_results(fields, label, depends_on, known_columns or None, model_name)
```

Apply this pattern to all three modes: `--file`, `--exposure`, and `--workbook`.
The `depends_on` variable is already set correctly in each mode.

**In `run_interactive()`**, replace the final two lines with:

```python
model_name = detect_model_from_caption(chosen_caption)
known_columns = load_model_columns(model_name) if model_name else set()
print_results(fields, workbook_label, depends_on, known_columns or None, model_name)
```

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/scripts/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Smoke test interactively (no network — file mode)**

Create a minimal test fixture:

```bash
uv run python -c "
import zipfile, pathlib, io
twb = '''<workbook>
  <datasources>
    <datasource caption=\"rpt_tableau__test (kipptaf_tableau)\">
      <column caption=\"GPA Label\" datatype=\"string\" name=\"[GPA Label]\">
        <calculation class=\"tableau\" formula=\"IF [gpa] >= 3.5 THEN 'Honor Roll' ELSE 'Standard' END\" />
      </column>
      <column caption=\"Credits OK\" datatype=\"boolean\" name=\"[Credits OK]\">
        <calculation class=\"tableau\" formula=\"[earned_credits] >= [expected_credits]\" />
      </column>
      <column caption=\"Skip Me\" datatype=\"string\" name=\"[Skip Me]\">
        <calculation class=\"tableau\" formula=\"USERNAME()\" />
      </column>
    </datasource>
  </datasources>
</workbook>'''
buf = io.BytesIO()
with zipfile.ZipFile(buf, 'w') as zf:
    zf.writestr('test.twb', twb)
pathlib.Path('/tmp/test.twbx').write_bytes(buf.getvalue())
print('Written /tmp/test.twbx')
"
uv run scripts/tableau-extract-calcs.py --file /tmp/test.twbx -d test
```

Expected: flat unclassified table (no model loaded).

```bash
uv run scripts/tableau-extract-calcs.py --file /tmp/test.twbx -d test --model rpt_tableau__test
```

Expected: **0 READY** (no YAML file for this fake model) — all NEEDS WORK or
SKIP.

- [ ] **Step 7: Commit**

```bash
git add scripts/tableau-extract-calcs.py
git commit -m "feat: wire field classification and grouped output into tableau-extract-calcs"
```

---

## Task 5: Run trunk check and fix any lint issues

**Files:**

- Modify: `scripts/tableau-extract-calcs.py` (if needed)

- [ ] **Step 1: Run trunk check on the script**

```bash
uv run trunk check scripts/tableau-extract-calcs.py
```

- [ ] **Step 2: Fix any issues reported**

Common issues to watch for:

- `import re` must be in alphabetical order with other stdlib imports (between
  `pathlib` and `sys`)
- Line length violations (max 88 chars per `.sqlfluff` / trunk config) — wrap
  long lines

- [ ] **Step 3: Run tests again to confirm nothing broken**

```bash
uv run pytest tests/scripts/ -v
```

- [ ] **Step 4: Commit if any fixes were needed**

```bash
git add scripts/tableau-extract-calcs.py
git commit -m "fix: trunk lint issues in tableau-extract-calcs"
```

---

## Task 6: Update slash command — Spec 1 (categorization UX)

**Files:**

- Modify: `.claude/commands/tableau-upstream.md`

This task rewrites Step 3 and Step 5 of the slash command to use the categorized
output.

- [ ] **Step 1: Replace Step 3 in the slash command**

In `.claude/commands/tableau-upstream.md`, replace the entire
`## Step 3 — Extract calculated fields` section with:

````markdown
## Step 3 — Extract calculated fields

Run the script filtered to the chosen datasource (the `-d` flag does a
case-insensitive match; the `-m` flag loads the target model's columns for
classification):

```bash
uv run scripts/tableau-extract-calcs.py --exposure <name> -d <datasource_substring> -m <model_name>
```

The script prints a categorized summary. Present the counts and ask:

> Found **N calculated fields** in \<datasource\>:
>
> - ✓ **READY** (N) — all refs resolve to model columns; ready to translate
> - ⚠ **NEEDS WORK** (N) — one or more refs are unresolved; need mapping
> - 🔷 **LOD** (N) — fixed-level aggregates; semantic layer candidates
> - ✗ **SKIP** (N) — no SQL equivalent (USERNAME(), Parameters, literals)
>
> [Show the full categorized table from the script output]
>
> Which of these do you want to move upstream? You can say "all READY", "all of
> them", or name specific fields.
>
> Also — how would you like to work through the READY fields?
>
> 1. Walk through each one at a time for confirmation
> 2. Propose all READY fields at once as a diff — review together
> 3. Start with NEEDS WORK first — resolve unresolved refs before translating

Wait for the user's answer before continuing.
````

- [ ] **Step 2: Replace Step 5 in the slash command**

Replace the entire `## Step 5 — Translate and confirm each field` section with:

```markdown
## Step 5 — Translate and confirm each field

### NEEDS WORK fields — resolve refs first

Before translating, show all NEEDS WORK fields and their unresolved refs:

> These fields have references that don't match any column in \<model_name\>:
>
> - **\<Field Name\>**: unresolved refs: `[UnknownRef1]`, `[UnknownRef2]`
>
> Please tell me which dbt column each maps to. Once resolved, I'll include
> these alongside the READY fields.

Wait for the user's mapping before proceeding.

### READY and resolved fields — translation

For each field (in the order chosen in Step 3), propose the BigQuery SQL
translation before writing anything:

> **\<Field Name\>** (`<datatype>`):
>
> Tableau formula: `<original formula>`
>
> Proposed SQL: `<translated expression>`
>
> Does this look right? Any changes?

**Common Tableau → BigQuery SQL translations:**

| Tableau                     | BigQuery SQL                       |
| --------------------------- | ---------------------------------- |
| `IF … ELSEIF … ELSE … END`  | `CASE WHEN … THEN … ELSE … END`    |
| `ISNULL([x])`               | `x IS NULL`                        |
| `ZN([x])`                   | `COALESCE(x, 0)`                   |
| `STR([x])`                  | `CAST(x AS STRING)`                |
| `INT([x])`                  | `CAST(x AS INT64)`                 |
| `FLOAT([x])`                | `CAST(x AS FLOAT64)`               |
| `TODAY()`                   | `CURRENT_DATE()`                   |
| `NOW()`                     | `CURRENT_TIMESTAMP()`              |
| `DATEADD('day', N, [d])`    | `DATE_ADD(d, INTERVAL N DAY)`      |
| `DATEDIFF('day', [a], [b])` | `DATE_DIFF(b, a, DAY)`             |
| `DATETRUNC('month', [d])`   | `DATE_TRUNC(d, MONTH)`             |
| `DATEPART('year', [d])`     | `EXTRACT(YEAR FROM d)`             |
| `LEN([x])`                  | `LENGTH(x)`                        |
| `CONTAINS([x], 'y')`        | `x LIKE '%y%'`                     |
| `IIF(cond, a, b)`           | `IF(cond, a, b)`                   |
| `USERNAME()`                | _(skip — Tableau-only)_            |
| `{FIXED …}`                 | _(LOD — handled separately)_       |
| `[Parameters].[…]`          | _(skip — parameter, Tableau-only)_ |

### LOD fields — semantic layer handling

For each LOD field, present the script's recommendation and ask what to do:

> **\<Field Name\>** (`<datatype>`):
>
> Formula: `<formula>`
>
> \<Branch A: Suggested mart: fct*\*\> OR \<Branch B: No mart match — new model
> may be needed: fct*\* (grain: …, measures: …)\>
>
> Options:
>
> 1. Open a GitHub issue to track this semantic layer addition
> 2. Skip for now — leave it in Tableau

Wait for the user's choice per field before moving on.
```

- [ ] **Step 3: Verify the slash command reads cleanly**

Read the full file and confirm the step numbering is still correct (Steps 1–8).

- [ ] **Step 4: Run trunk check on the slash command**

```bash
uv run trunk check .claude/commands/tableau-upstream.md
```

Fix any markdown lint issues (fenced code block languages, table style, etc.).

- [ ] **Step 5: Commit**

```bash
git add .claude/commands/tableau-upstream.md
git commit -m "feat: add categorized field workflow to /tableau-upstream slash command"
```

---

## Task 7: Update slash command — Spec 2 (lineage tracing Step 4b)

**Files:**

- Modify: `.claude/commands/tableau-upstream.md`

This task inserts a new Step 4b between existing Step 4 and Step 5.

- [ ] **Step 1: Insert Step 4b after Step 4**

After the `## Step 4 — Identify the target dbt model` section and before
`## Step 5 — Translate and confirm each field`, insert:

````markdown
## Step 4b — Trace lineage and recommend insertion point

For each READY field (and NEEDS WORK fields once their refs are resolved), use
the dbt MCP to find the best place in the pipeline to add the calculation.

**For each field:**

1. Call `get_lineage_dev` on the target Tableau extract model to get the
   upstream DAG. If it returns empty or fails, note "all inputs at extract
   layer" and skip to Step 5 for this field.

2. Call `get_node_details_dev` on each upstream node to get compiled SQL.

3. For each of the field's `[Field]` refs, scan the compiled SQL to find the
   closest-to-extract model where that column appears in a named SELECT
   expression.

   **Wildcard/`union_relations` models:** If a model's compiled SQL contains
   wildcard expansions (`ar.*`, `SELECT *`, macro-generated column lists), it
   cannot be scanned reliably. Fall back to querying BigQuery
   `INFORMATION_SCHEMA.COLUMNS`:

   ```sql
   select column_name
   from `teamster-332318`.<schema>.INFORMATION_SCHEMA.COLUMNS
   where table_name = '<model_name>'
   order by ordinal_position
   ```

   Use the result to determine whether the column is available at that layer.
   See `src/dbt/kipptaf/CLAUDE.md` ("Selecting from models that use
   `dbt_utils.star()`") for background.

4. Identify the **recommended insertion point**: the closest-to-extract model
   (earliest in a breadth-first traversal from the extract) where _all_ input
   columns are simultaneously present.

5. Present the result:

   > **\<Field Name\>** — lineage trace:
   >
   > ```
   > rpt_tableau__<model>
   >   ← <intermediate_model>  ← recommended (all inputs here)
   >     ← <staging_model_a>
   >     ← <staging_model_b>
   > ```
   >
   > All input columns (`col_a`, `col_b`) are available at
   > `<intermediate_model>`. Draft SQL at that layer:
   >
   > ```sql
   > <translated expression using column names at that layer>,
   > ```
   >
   > Add here, push further upstream, or keep in the Tableau extract?

6. **If pushing upstream:** Call `get_node_details_dev` on the next upstream
   node. Re-derive column names using alias resolution:
   - Look for `<upstream_name> as col_name` in the intermediate model's compiled
     SQL to find the upstream alias
   - If no alias found, name is the same at the upstream layer
   - If the model uses wildcard expansion, query `INFORMATION_SCHEMA.COLUMNS` on
     the upstream model to confirm the column exists under the same name
     Re-draft SQL and repeat the question.

7. **If keeping in the extract:** Proceed to Step 5 for this field with the
   original column names.

**Grouping:** When multiple fields share the same recommended insertion point,
present them together as a group for the initial recommendation. The
push-upstream decision is per-field — handle them individually if the analyst
wants to split them.

**When no better insertion point is found:** Skip the trace and note "All inputs
are only available at the extract layer — adding here is correct."
````

- [ ] **Step 2: Run trunk check**

```bash
uv run trunk check .claude/commands/tableau-upstream.md
```

Fix any issues.

- [ ] **Step 3: Read the full slash command and verify step flow**

Steps should be: 1 → 2 → 3 → 4 → 4b → 5 → 6 → 7 → 8. Confirm no gaps or
duplicate section headers.

- [ ] **Step 4: Commit**

```bash
git add .claude/commands/tableau-upstream.md
git commit -m "feat: add Step 4b lineage tracing to /tableau-upstream slash command"
```

---

## Task 8: End-to-end smoke test

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/scripts/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Smoke test the script with the fabricated fixture**

```bash
# First create the test model YAML so classification works
mkdir -p /tmp/test_properties
cat > /tmp/test_properties/rpt_tableau__test.yml << 'EOF'
models:
  - name: rpt_tableau__test
    columns:
      - name: gpa
        data_type: float64
      - name: earned_credits
        data_type: int64
      - name: expected_credits
        data_type: int64
EOF

uv run scripts/tableau-extract-calcs.py --file /tmp/test.twbx -d test --model rpt_tableau__test
```

Expected: **0 READY, 2 NEEDS WORK, 0 LOD, 1 SKIP** — the `--model` flag uses
`TABLEAU_PROPERTIES_DIR` by default, so `rpt_tableau__test.yml` won't be found
and `known_columns` will be empty, making `gpa`, `earned_credits`, and
`expected_credits` unresolvable. This confirms the script runs end-to-end
without crashing. To test actual READY classification, run against a real model
from `src/dbt/kipptaf/models/extracts/tableau/properties/` with `--exposure`.

- [ ] **Step 3: Validate Dagster definitions still parse**

```bash
uv run dagster definitions validate -m teamster.code_locations.kipptaf.definitions
```

Expected: no errors (the script changes don't touch Dagster code).

- [ ] **Step 4: Final commit if needed**

If any fixes were made:

```bash
git add -p
git commit -m "fix: end-to-end smoke test fixes"
```
