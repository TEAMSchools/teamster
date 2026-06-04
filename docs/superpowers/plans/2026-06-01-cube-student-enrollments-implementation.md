# Cube Student Enrollments Implementation Plan

> **Status: COMPLETE** — implemented in PR #4116 alongside Plan 0.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the `student_enrollments` cube through two consumer views
(`student_enrollments_detail`, `student_enrollments_summary`) to enable
headcount and demographic questions — including ELL, IEP, and meal eligibility
status — without routing through a fact table.

**Prerequisite:** Plan 0 complete. `student_enrollments`, `students`, and
`locations` cubes exist at their post-rename names.

**Architecture:** The `student_enrollments` cube uses a boundary-union spine
that inlines ELL, IEP, and meal eligibility status directly. The three
standalone status cubes (`student_ell_status`, `student_iep_status`,
`student_meal_eligibility_status`) were removed — status is now always resolved
point-in-time from the spine. Every enrollment date maps to exactly one spine
row (no gaps). Status dimensions are exposed on the enrollment views directly
via the `student_enrollments` join path, not via separate join paths to status
cubes.

**Grain:** One row per non-overlapping status interval within an enrollment
stint. `count_students` (count_distinct on `student_enrollment_key`) is always
the correct headcount regardless of how many spine rows a given enrollment fans
into. A student who transfers between schools mid-year has two enrollment
records; filter to a specific `academic_year` + location for clean
per-school-per-year counts.

**Tech Stack:** Cube YAML (`src/cube/model/`), Python (`pytest`, `pyyaml`)

**Spec:** `docs/superpowers/specs/2026-04-17-cube-model-yaml-design.md`

---

## Task 1: Rewrite `student_enrollments` cube with boundary-union spine

Replaces the cross-join + GREATEST/LEAST approach with a boundary-union that
collects every date boundary across ELL, IEP, and meal status tables, builds
non-overlapping intervals via `LEAD()`, then resolves each status point-in-time.
Removes the three standalone status cubes.

**Files:**

- Modify: `src/cube/model/cubes/students/student_enrollments.yml`
- Delete: `src/cube/model/cubes/students/student_ell_status.yml`
- Delete: `src/cube/model/cubes/students/student_iep_status.yml`
- Delete: `src/cube/model/cubes/students/student_meal_eligibility_status.yml`

- [x] **Step 1: Replace the cube SQL with the boundary-union spine**

The spine collects all date boundaries from ELL, IEP, meal, and enrollment
tables, builds non-overlapping intervals, and resolves each status point-in-time
via `BETWEEN` lookups. See the committed `student_enrollments.yml` for the full
SQL.

- [x] **Step 2: Delete the standalone status cubes**

```bash
git rm src/cube/model/cubes/students/student_ell_status.yml
git rm src/cube/model/cubes/students/student_iep_status.yml
git rm src/cube/model/cubes/students/student_meal_eligibility_status.yml
```

- [x] **Step 3: Commit**

```bash
git add src/cube/model/cubes/students/student_enrollments.yml
git commit -m "fix(cube): repair student_enrollments spine — boundary-union replaces GREATEST/LEAST"
```

---

## Task 2: Create `student_enrollments_detail` view

Detail view exposing enrollment attributes, status dimensions, and student PII
(gated). Status fields (ELL, IEP, meal) come from the `student_enrollments` join
path directly — no separate status cube join paths needed.

**Files:**

- Create: `src/cube/model/views/students/student_enrollments_detail.yml`

- [x] **Step 1: Write the view file**

Key points:

- Status dimensions (`is_ell`, `is_iep`, `iep_classification`,
  `is_meal_eligible`, etc.) included under `join_path: student_enrollments` —
  they're inlined on the spine
- PII gating: student name/DOB/identifiers in `excludes` under `detail-access`;
  restored by `cube-access-student-pii`
- No separate `student_ell_status` / `student_iep_status` /
  `student_meal_eligibility_status` join paths

- [x] **Step 2: Commit**

```bash
git add src/cube/model/views/students/student_enrollments_detail.yml
git commit -m "feat(cube): add student_enrollments_detail view"
```

---

## Task 3: Create `student_enrollments_summary` view

Summary view for aggregate headcounts and demographic breakdowns. No direct
student identifiers. Status dimensions exposed as aggregate breakdown
dimensions.

**Files:**

- Create: `src/cube/model/views/students/student_enrollments_summary.yml`

- [x] **Step 1: Write the view file**

- [x] **Step 2: Run the full cube test suite**

```bash
uv run pytest tests/cube/ -v
```

Expected: all PASS.

- [x] **Step 3: Commit**

```bash
git add src/cube/model/views/students/student_enrollments_summary.yml
git commit -m "feat(cube): add student_enrollments_summary view"
```

---

## Validation in Cube Cloud

**Check 1 — Zero null-enrollment rows in attendance:**

Query `student_attendance_detail` or `student_attendance_summary` for AY2025
grouped by `regions_region_name`. No null region rows should appear — the
boundary-union spine covers every attendance date.

**Check 2 — Status dimensions work as filters:**

Query `student_enrollments_summary.count_students` filtered to
`student_enrollments_is_iep = true` and `academic_year = 2025`. Should return
IEP-enrolled students without fan-out.

**Check 3 — Headcount is stable:**

Query `student_enrollments_summary.count_students` grouped by `academic_year`.
Counts should match known enrollment figures — `count_students` uses
`count_distinct` on `student_enrollment_key` so spine fan-out doesn't inflate
the number.
