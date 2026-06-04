# Cube Academic Year Semantics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the silent off-by-one academic year bug by adding an unambiguous
`academic_year_label` string dimension, swapping attendance views off
`dim_terms` onto `dim_dates`, and adding a mandatory MCP resolver tool that
translates any year phrasing to the canonical integer + label before a Cube
query is built.

**Architecture:** Cube YAML changes (new dimension + description updates + view
rewiring) are independent of the MCP server change (new `resolve_academic_year`
tool + updated `instructions=`). Tests for the resolver are pure Python — no
Cube API mock needed.

**Tech Stack:** Cube YAML, Python 3.13, FastMCP (`mcp>=1.2`), pytest

---

## Files touched

| File                                                     | Change                                                   |
| -------------------------------------------------------- | -------------------------------------------------------- |
| `src/cube/model/cubes/conformed/dates.yml`               | Add `academic_year_label` dimension                      |
| `src/cube/model/cubes/conformed/terms.yml`               | Update `academic_year` description                       |
| `src/cube/model/cubes/attendance/attendance.yml`         | Update `is_latest_record` description                    |
| `src/cube/model/views/attendance/attendance_summary.yml` | Swap `dim_terms` → `dim_dates` for AY; add label         |
| `src/cube/model/views/attendance/attendance_detail.yml`  | Same                                                     |
| `src/cube/mcp/server.py`                                 | Add `resolve_academic_year` tool; update `instructions=` |
| `tests/cube/test_mcp_server.py`                          | Add resolver test cases                                  |

---

## Task 1: Add `academic_year_label` to `dim_dates`

**Files:**

- Modify: `src/cube/model/cubes/conformed/dates.yml`

- [ ] **Step 1: Add the new dimension after `academic_year`**

In `src/cube/model/cubes/conformed/dates.yml`, insert after the closing line of
the `academic_year` dimension block (after `public: true` on line ~27, before
the `fiscal_year` dimension):

```yaml
- name: academic_year_label
  description: >-
    Full span label for the academic year (e.g. "2025-2026" for the year
    beginning July 2025). Use this as the canonical filter surface when querying
    by year — it is unambiguous regardless of SY vs. start-year notation.
    academic_year 2025 = academic_year_label "2025-2026" = SY26. The integer
    academic_year is retained for sort/group/math only.
  sql: >-
    CONCAT(CAST(academic_year AS STRING), '-', CAST(academic_year + 1 AS
    STRING))
  type: string
  public: true
```

- [ ] **Step 2: Commit**

```bash
git add src/cube/model/cubes/conformed/dates.yml
git commit -m "feat(cube): add academic_year_label dimension to dim_dates"
```

---

## Task 2: Update `academic_year` description in `dim_terms`

**Files:**

- Modify: `src/cube/model/cubes/conformed/terms.yml`

- [ ] **Step 1: Update the description**

In `src/cube/model/cubes/conformed/terms.yml`, replace the `academic_year`
dimension description (lines ~53–58):

```yaml
- name: academic_year
  description: >-
    KIPP academic year (July start) this term falls within. Calendar year in
    which the academic year begins (e.g., 2025 for the 2025–26 school year) —
    opposite of typical FY conventions where FY2025 ends in 2025. academic_year
    2025 = the 2025-26 school year = SY26. SY notation uses the END year; this
    integer uses the START year.
  sql: academic_year
  type: number
  public: true
```

- [ ] **Step 2: Commit**

```bash
git add src/cube/model/cubes/conformed/terms.yml
git commit -m "feat(cube): add SY crosswalk note to dim_terms academic_year description"
```

---

## Task 3: Update `is_latest_record` description in `attendance.yml`

**Files:**

- Modify: `src/cube/model/cubes/attendance/attendance.yml`

- [ ] **Step 1: Update the description**

In `src/cube/model/cubes/attendance/attendance.yml`, find the `is_latest_record`
dimension (around line 211). Replace the sentence:

```
Use as a filter (is_latest_record = true) with dim_terms.academic_year
```

with:

```
Use as a filter (is_latest_record = true) with dim_dates.academic_year or
dim_dates.academic_year_label
```

The full updated description block should read:

```yaml
- name: is_latest_record
  description: >-
    TRUE on the most recent attendance row per student enrollment (partitioned
    by student × district × academic year × entry date). For completed academic
    years this is the last instructional day on record; for the current year it
    is the most recent day with data.

    Use as a filter (is_latest_record = true) with dim_dates.academic_year or
    dim_dates.academic_year_label to get year-end CA status for year-over-year
    comparisons — one terminal snapshot per enrollment, no date filter required.

    Do not combine with a date_key filter — use exactly one or the other.

    Transfer student note: a student who transfers intra-district mid-year
```

(Leave the remainder of the description unchanged.)

- [ ] **Step 2: Commit**

```bash
git add src/cube/model/cubes/attendance/attendance.yml
git commit -m "feat(cube): update is_latest_record description to reference dim_dates"
```

---

## Task 4: Rewire `attendance_summary.yml`

**Files:**

- Modify: `src/cube/model/views/attendance/attendance_summary.yml`

- [ ] **Step 1: Move `academic_year` out of `dim_terms` block, add both to
      `dim_dates` block**

Find the `join_path: attendance.dim_dates` block (around line 61). Add
`academic_year` and `academic_year_label` to its `includes`:

```yaml
- join_path: attendance.dim_dates
  prefix: true
  includes:
    - academic_year
    - academic_year_label
    - date_day
    - month_number
    - month_name
    - quarter_number
    - school_week_start_date
```

Find the `join_path: attendance.dim_terms` block (around line 107). Remove
`academic_year` from its `includes` — keep the rest:

```yaml
- join_path: attendance.dim_terms
  prefix: true
  includes:
    - semester
    - term_name
    - term_code
    - term_type
```

- [ ] **Step 2: Update `meta.folders`**

Find the `Date` folder in `meta.folders`. Add `dim_dates_academic_year` and
`dim_dates_academic_year_label` as the first two entries:

```yaml
- name: Date
  members:
    - dim_dates_academic_year
    - dim_dates_academic_year_label
    - dim_dates_date_day
    - dim_dates_month_number
    - dim_dates_month_name
    - dim_dates_quarter_number
    - dim_dates_school_week_start_date
```

Find the `Term` folder. Remove `dim_terms_academic_year`:

```yaml
- name: Term
  members:
    - dim_terms_semester
    - dim_terms_term_name
    - dim_terms_term_code
    - dim_terms_term_type
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/attendance/attendance_summary.yml
git commit -m "feat(cube): swap attendance_summary AY from dim_terms to dim_dates"
```

---

## Task 5: Rewire `attendance_detail.yml`

**Files:**

- Modify: `src/cube/model/views/attendance/attendance_detail.yml`

- [ ] **Step 1: Move `academic_year` out of `dim_terms` block, add both to
      `dim_dates` block**

Find the `join_path: attendance.dim_dates` block (around line 78). Add
`academic_year` and `academic_year_label` to its `includes`:

```yaml
- join_path: attendance.dim_dates
  prefix: true
  includes:
    - academic_year
    - academic_year_label
    - date_day
    - month_number
    - month_name
    - quarter_number
    - school_week_start_date
    - day_of_week_name
    - is_weekday
```

Find the `join_path: attendance.dim_terms` block (around line 135). Remove
`academic_year` from its `includes` — keep the rest:

```yaml
- join_path: attendance.dim_terms
  prefix: true
  includes:
    - semester
    - term_name
    - term_code
    - term_type
```

- [ ] **Step 2: Update `meta.folders`**

Find the `Date` folder in `meta.folders`. Add `dim_dates_academic_year` and
`dim_dates_academic_year_label` as the first two entries:

```yaml
- name: Date
  members:
    - dim_dates_academic_year
    - dim_dates_academic_year_label
    - attendance_date
    - dim_dates_date_day
    - dim_dates_month_number
    - dim_dates_month_name
    - dim_dates_quarter_number
    - dim_dates_school_week_start_date
    - dim_dates_day_of_week_name
    - dim_dates_is_weekday
```

Find the `Term` folder. Remove `dim_terms_academic_year`:

```yaml
- name: Term
  members:
    - dim_terms_semester
    - dim_terms_term_name
    - dim_terms_term_code
    - dim_terms_term_type
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/model/views/attendance/attendance_detail.yml
git commit -m "feat(cube): swap attendance_detail AY from dim_terms to dim_dates"
```

---

## Task 6: Add `resolve_academic_year` tool and update `instructions=`

**Files:**

- Modify: `src/cube/mcp/server.py`

- [ ] **Step 1: Add the resolver function and tool**

Add `import re` to the imports block at the top of `server.py` (after
`import os`).

Then, after the `mcp = FastMCP(...)` block and before the `client = httpx...`
line, add:

```python
def _resolve_academic_year(raw: str) -> dict[str, int | str]:
    """Translate any year phrasing to canonical academic_year int + label.

    Returns a dict with academic_year (int), academic_year_label (str),
    school_year (str), interpreted_as (str), and optionally note (str)
    for bare-integer inputs.
    """
    s = raw.strip()
    start: int | None = None
    note: str | None = None

    # SY + 2-digit: SY26 → end=2026 → start=2025
    m = re.fullmatch(r"[Ss][Yy](\d{2})", s)
    if m:
        start = 2000 + int(m.group(1)) - 1

    # SY + 4-digit: SY2026 → end=2026 → start=2025
    if start is None:
        m = re.fullmatch(r"[Ss][Yy](\d{4})", s)
        if m:
            start = int(m.group(1)) - 1

    # AY + 4-digit: AY2025 → start=2025
    if start is None:
        m = re.fullmatch(r"[Aa][Yy](\d{4})", s)
        if m:
            start = int(m.group(1))

    # AY + 2-digit: AY25 → start=2025
    if start is None:
        m = re.fullmatch(r"[Aa][Yy](\d{2})", s)
        if m:
            start = 2000 + int(m.group(1))

    # 4-digit separator 4-digit: 2025-2026 or 2025–2026
    if start is None:
        m = re.fullmatch(r"(\d{4})[-–](\d{4})", s)
        if m:
            start = int(m.group(1))

    # 4-digit separator 2-digit: 2025-26 or 2025–26
    if start is None:
        m = re.fullmatch(r"(\d{4})[-–](\d{2})", s)
        if m:
            start = int(m.group(1))

    # 2-digit separator 2-digit: 25-26
    if start is None:
        m = re.fullmatch(r"(\d{2})[-–](\d{2})", s)
        if m:
            start = 2000 + int(m.group(1))

    # bare 4-digit integer: treated as start year
    if start is None:
        m = re.fullmatch(r"(\d{4})", s)
        if m:
            start = int(m.group(1))
            note = (
                f"Bare integer treated as start year "
                f"({start} = July {start} – June {start + 1} = SY{(start + 1) % 100:02d})."
            )

    # bare 2-digit integer: treated as start year
    if start is None:
        m = re.fullmatch(r"(\d{2})", s)
        if m:
            start = 2000 + int(m.group(1))
            note = (
                f"Bare integer treated as start year "
                f"({start} = July {start} – June {start + 1} = SY{(start + 1) % 100:02d})."
            )

    if start is None:
        raise ValueError(f"Cannot parse year from {raw!r}")

    end = start + 1
    label = f"{start}-{end}"
    sy = f"SY{end % 100:02d}"
    result: dict[str, int | str] = {
        "academic_year": start,
        "academic_year_label": label,
        "school_year": sy,
        "interpreted_as": f"{start}-{end % 100:02d} school year",
    }
    if note is not None:
        result["note"] = note
    return result


@mcp.tool()
async def resolve_academic_year(ctx: Context, raw: str) -> dict[str, int | str]:
    """Translate any year phrasing to the canonical Cube academic_year integer
    and label.

    Call this BEFORE building any Cube query that involves a year value from
    the user's request. Pass the raw year string exactly as the user typed it.

    Handles: SY26, SY2026, AY2025, AY25, 2025-2026, 2025–2026, 2025-26,
    25-26, bare 2025, bare 26. Bare integers default to start-year with a
    note field explaining the assumption.

    Returns: academic_year (int for Cube filters), academic_year_label (str,
    e.g. "2025-2026", for Cube filters when using the label dimension),
    school_year (str, e.g. "SY26"), interpreted_as (str — echo this to the
    user before showing results), and note (str, only for bare integers).
    """
    return _resolve_academic_year(raw)
```

- [ ] **Step 2: Update the `instructions=` block**

In the `mcp = FastMCP(...)` call, replace the academic year paragraph:

```python
        "Academic year convention: an academic_year value of 2025 means the "
        "2025–26 school year (July 2025 – June 2026), not the year ending in "
        "2025. This is the opposite of typical fiscal-year conventions where "
        "FY2025 ends in 2025. When a user says 'this year' or 'current year', "
        "use the academic_year value whose start year matches the current "
        "calendar year (e.g. if today is May 2026, current academic_year = "
        "2025). In attendance views, the academic year is exposed as "
        "dim_terms_academic_year (sourced from the term dimension, not the "
        "fact).\n\n"
```

with:

```python
        "Academic year convention: an academic_year value of 2025 means the "
        "2025–26 school year (July 2025 – June 2026), not the year ending in "
        "2025. This is the opposite of typical fiscal-year conventions where "
        "FY2025 ends in 2025. When a user says 'this year' or 'current year', "
        "use the academic_year value whose start year matches the current "
        "calendar year (e.g. if today is May 2026, current academic_year = "
        "2025). In attendance views, the academic year is exposed as "
        "dim_dates_academic_year (integer) and dim_dates_academic_year_label "
        "(string, e.g. '2025-2026'), both sourced from the date dimension.\n\n"
        "REQUIRED: Before building any Cube query that involves a year value "
        "from the user's request, call resolve_academic_year with the raw year "
        "string the user provided (e.g. 'SY26', '2025-26', '2026'). Use the "
        "returned academic_year integer for numeric filters/grouping, or "
        "academic_year_label for the label dimension. Emit the interpreted_as "
        "value as a brief inline statement (e.g. 'Interpreting as the 2025-26 "
        "school year') before showing results — do not pause or ask for "
        "confirmation, just state it and proceed. Do not skip this step even "
        "when the year seems unambiguous.\n\n"
```

- [ ] **Step 3: Commit**

```bash
git add src/cube/mcp/server.py
git commit -m "feat(cube): add resolve_academic_year MCP tool and update instructions"
```

---

## Task 7: Write tests for `resolve_academic_year`

**Files:**

- Modify: `tests/cube/test_mcp_server.py`

- [ ] **Step 1: Add the test cases**

Add the following after the last existing test in
`tests/cube/test_mcp_server.py`:

```python
@pytest.mark.parametrize(
    ("raw", "expected_year", "expected_label", "expected_sy", "has_note"),
    [
        ("SY26", 2025, "2025-2026", "SY26", False),
        ("SY2026", 2025, "2025-2026", "SY26", False),
        ("sy26", 2025, "2025-2026", "SY26", False),  # case-insensitive
        ("AY2025", 2025, "2025-2026", "SY26", False),
        ("AY25", 2025, "2025-2026", "SY26", False),
        ("ay2025", 2025, "2025-2026", "SY26", False),  # case-insensitive
        ("2025-2026", 2025, "2025-2026", "SY26", False),
        ("2025–2026", 2025, "2025-2026", "SY26", False),  # em-dash
        ("2025-26", 2025, "2025-2026", "SY26", False),
        ("2025–26", 2025, "2025-2026", "SY26", False),  # em-dash
        ("25-26", 2025, "2025-2026", "SY26", False),
        ("2026", 2026, "2026-2027", "SY27", True),
        ("2025", 2025, "2025-2026", "SY26", True),
        ("26", 2026, "2026-2027", "SY27", True),
    ],
)
def test_resolve_academic_year(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected_year: int,
    expected_label: str,
    expected_sy: str,
    has_note: bool,
) -> None:
    server = _load_server(monkeypatch)
    result = server._resolve_academic_year(raw)
    assert result["academic_year"] == expected_year
    assert result["academic_year_label"] == expected_label
    assert result["school_year"] == expected_sy
    assert ("note" in result) == has_note


def test_resolve_academic_year_raises_on_unparseable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = _load_server(monkeypatch)
    with pytest.raises(ValueError, match="Cannot parse year"):
        server._resolve_academic_year("not-a-year")
```

- [ ] **Step 2: Run the tests**

```bash
uv run pytest tests/cube/test_mcp_server.py -v
```

Expected: all new `test_resolve_academic_year*` tests pass. If any fail, check
the regex patterns in `_resolve_academic_year` — the order of pattern matching
matters (more specific patterns must come before less specific ones).

- [ ] **Step 3: Commit**

```bash
git add tests/cube/test_mcp_server.py
git commit -m "test(cube): add resolve_academic_year test cases"
```
