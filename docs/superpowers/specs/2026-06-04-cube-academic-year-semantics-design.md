# Cube Academic Year Semantics — Design Spec

**Issue:** #4084 **Branch:**
`cristinabaldor/feat/claude-cube-academic-year-semantics` **Date:** 2026-06-04

## Problem

Users refer to the same school year using conventions that anchor on different
calendar years: `academic_year = 2025` (start year) vs. `SY26` (end year). A
user holding "SY26" who filters on `2026` silently gets 2026–27 data. This
wrong-year mistake is observed in practice and is the motivation for this work.

## Goals

1. Add an unambiguous string label surface (`academic_year_label`) so consumers
   can filter without knowing the integer convention.
2. Improve descriptions on all `academic_year` members with the start-year/SY
   crosswalk so LLMs reading `/meta` understand the offset.
3. Swap attendance views off `dim_terms_academic_year` onto `dim_dates`
   (consolidation deferred from #4010).
4. Add a mandatory MCP resolver tool that translates any year phrasing to the
   canonical integer + label before a Cube query is built.

## Out of scope

- `academic_year_label` on `dim_student_enrollments` (enrollment views don't
  join through `dim_dates`; deferred).
- Changes to enrollment views.
- Changes to `dim_student_enrollments` cube.

---

## 1. Cube model changes

### 1a. `dim_dates` — new `academic_year_label` dimension

File: `src/cube/model/cubes/conformed/dates.yml`

Add after the existing `academic_year` dimension:

```yaml
- name: academic_year_label
  description: >-
    Full span label for the academic year (e.g. "2025-2026" for the year
    beginning July 2025). Use this as the canonical filter surface when querying
    by year — it is unambiguous regardless of SY vs. start-year notation.
    academic_year 2025 = academic_year_label "2025-2026" = SY26. The integer
    academic_year is retained for sort/group/math only.
  sql:
    CONCAT(CAST(academic_year AS STRING), '-', CAST(academic_year + 1 AS
    STRING))
  type: string
  public: true
```

### 1b. `dim_terms` — update `academic_year` description

File: `src/cube/model/cubes/conformed/terms.yml`

Add to the existing `academic_year` description:

> `academic_year 2025 = the 2025-26 school year = SY26. SY notation uses the END year; this integer uses the START year.`

---

## 2. Attendance view changes

### 2a. `attendance_summary.yml` and `attendance_detail.yml`

Files: `src/cube/model/views/attendance/attendance_summary.yml`,
`src/cube/model/views/attendance/attendance_detail.yml`

- In the `join_path: attendance.dim_terms` block: remove `academic_year` from
  `includes` (keep `semester`, `term_name`, `term_code`, `term_type`).
- In the `join_path: attendance.dim_dates` block: add `academic_year` and
  `academic_year_label` to `includes`.
- In `meta.folders`: remove `dim_terms_academic_year` from the `Term` folder;
  add `dim_dates_academic_year` and `dim_dates_academic_year_label` to the
  `Date` folder.

### 2b. `attendance.yml` cube — `is_latest_record` description

File: `src/cube/model/cubes/attendance/attendance.yml`

In the `is_latest_record` dimension description, replace the reference to
`dim_terms.academic_year` with `dim_dates.academic_year` or
`dim_dates.academic_year_label`.

---

## 3. MCP server changes

File: `src/cube/mcp/server.py`

### 3a. New tool: `resolve_academic_year`

Pure Python (no Cube API call). Accepts a single string argument — the raw year
phrasing from the user's request. Returns a JSON object:

```json
{
  "academic_year": 2025,
  "academic_year_label": "2025-2026",
  "school_year": "SY26",
  "interpreted_as": "2025-26 school year",
  "note": "Bare integer treated as start year (2025 = July 2025 – June 2026 = SY26)."
}
```

`note` is only present for bare-integer inputs.

**Parsing rules (in priority order):**

| Input pattern                 | Example                  | Resolution                                 |
| ----------------------------- | ------------------------ | ------------------------------------------ |
| `SY` + 2-digit year           | `SY26`                   | end year = 2026 → start = 2025             |
| `SY` + 4-digit year           | `SY2026`                 | end year = 2026 → start = 2025             |
| `AY` + 4-digit year           | `AY2025`                 | start year = 2025                          |
| `AY` + 2-digit year           | `AY25`                   | start = 2000 + digit                       |
| 4-digit + separator + 4-digit | `2025-2026`, `2025–2026` | start = first 4-digit                      |
| 4-digit + separator + 2-digit | `2025-26`, `2025–26`     | start = first 4-digit                      |
| 2-digit + separator + 2-digit | `25-26`                  | start = 2000 + first 2-digit               |
| bare 4-digit integer          | `2026`                   | start year (default, note added)           |
| bare 2-digit integer          | `26`                     | start = 2000 + digit (default, note added) |

### 3b. Updated `instructions=` block

- Remove the stale sentence referencing `dim_terms_academic_year` for attendance
  views.
- Add: "Attendance views now expose `dim_dates_academic_year` (integer) and
  `dim_dates_academic_year_label` (string, e.g. `2025-2026`) sourced from the
  date dimension."
- Add the mandatory resolver rule: "Before building any Cube query that involves
  a year value from the user's request, call `resolve_academic_year` with the
  raw year string the user provided. Use the returned `academic_year` integer
  for filters and grouping, and emit the `interpreted_as` value as a brief
  inline statement (e.g. 'Interpreting as the 2025–26 school year') before
  showing results. Do not pause, ask for confirmation, or wait for a reply —
  just state the interpretation and proceed. Do not skip this step even when the
  year seems unambiguous."

---

## 4. Tests

File: `tests/cube/test_mcp_server.py`

Add test cases for `resolve_academic_year` (pure Python, no Cube mock needed):

| Input         | Expected `academic_year` | Expected `academic_year_label` | `note` present? |
| ------------- | ------------------------ | ------------------------------ | --------------- |
| `"SY26"`      | 2025                     | `"2025-2026"`                  | no              |
| `"SY2026"`    | 2025                     | `"2025-2026"`                  | no              |
| `"2025-2026"` | 2025                     | `"2025-2026"`                  | no              |
| `"2025-26"`   | 2025                     | `"2025-2026"`                  | no              |
| `"25-26"`     | 2025                     | `"2025-2026"`                  | no              |
| `"2026"`      | 2026                     | `"2026-2027"`                  | yes             |
| `"2025"`      | 2025                     | `"2025-2026"`                  | yes             |
| `"26"`        | 2026                     | `"2026-2027"`                  | yes             |
| `"AY2025"`    | 2025                     | `"2025-2026"`                  | no              |
| `"AY25"`      | 2025                     | `"2025-2026"`                  | no              |

---

## Checklist (from issue #4084 follow-up comment)

- [ ] `attendance_summary.yml` — swap `dim_terms_academic_year` → `dim_dates`
- [ ] `attendance_detail.yml` — same
- [ ] `attendance.yml` — `is_latest_record` description updated
- [ ] `server.py` — `instructions=` AY note updated + `resolve_academic_year`
      tool added
