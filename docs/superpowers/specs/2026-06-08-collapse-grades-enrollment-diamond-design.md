# Collapse the `fct_grades_*` → `dim_student_enrollments` diamond

Issue: [#4145](https://github.com/TEAMSchools/teamster/issues/4145) Date:
2026-06-08

## Problem

`fct_grades_assignments` and `fct_grades_term` each carry two FK routes to
`dim_student_enrollments`:

- direct: `student_enrollment_key`
- traversed: `student_section_enrollment_key` →
  `dim_student_section_enrollments.student_enrollment_key`

This is the diamond path forbidden by `marts/CLAUDE.md` → "Strict-chain
traversal". The goal is to drop the direct FK so the only route to the
enrollment dim is through `dim_student_section_enrollments`.

## Why this is not a clean delete today

The two routes are computed by independent join logic, so the direct FK is not
redundant with the traversed one. Measured against prod `kipptaf_marts`:

```text
fct_grades_assignments (25,410,721 rows)
  direct == traversed         24,421,374  (96.1%)
  different stint (mismatch)       3,363  (0.013%)
  traversal NULL, direct set     985,984  (3.88%)   <- blocker
  FK fails to resolve                  0

fct_grades_term (262,188 rows)
  direct == traversed            260,319  (99.3%)
  different stint (mismatch)         895  (0.34%)
  traversal NULL, direct set         974  (0.37%)
  FK fails to resolve                  0
```

Dropping the direct FK today would strand the ~986K NULL-linkage assignment
rows: their section-enrollment parent has a NULL `student_enrollment_key`, so
traversal yields no enrollment.

## Root cause

A section enrollment (`cc` record) is a child of one school enrollment stint.
`dim_student_section_enrollments` resolves that parent with a **point** match —
`cc_dateenrolled >= entrydate and cc_dateenrolled < exitdate`. The blocker is
that **`cc_dateenrolled` precedes the stint's `entrydate`** for ~19.5K sections
(the section roster date is set before the official enrollment date), so the
point match drops them even though the section clearly belongs to — and uniquely
overlaps — that stint. The assignment/term dates fall inside the stint, so the
facts match and the dim does not. The school key is not a factor: a `cc` record
is tied to a single school, and `cc_schoolid == sections_schoolid` for 100% of
non-dropped `cc` records, so the dim's `sections_schoolid` scoping is
unambiguous and equals the fact's `cc_schoolid`.

Containment across all non-dropped section enrollments (655,718, grained on
`cc_dcid + _dbt_source_project`):

```text
fully contained in exactly one stint        624,063  (95.2%)
overlaps exactly one stint, not contained    28,967  (4.42%)
  - section starts before stint entrydate    19,538   <- the blocker
  - section ends after stint exitdate          9,568   (already point-matches)
overlaps more than one stint                    147  (0.022%)
overlaps no stint at all                      2,541  (0.39%)
```

So a section enrollment resolves to a **unique** school stint for 99.98% of
records (contained or single-overlap). This is not a dedup problem — it is a
resolution problem for ~19.5K sections whose roster date predates the stint.

## Design: resolve each section to its overlapping school stint

Change `dim_student_section_enrollments` to match the school stint the section
enrollment **overlaps**
(`entrydate < cc_dateleft and exitdate > cc_dateenrolled`, half-open) instead of
the point anchor on `cc_dateenrolled`. Keep the existing join keys
(`sections_schoolid`, `cc_yearid`, `_dbt_source_project`) — the school key needs
no change.

For 99.98% of sections this is a single match. Only **147** sections overlap
more than one stint, and they are overwhelmingly legitimate, not data quality:

```text
exactly one covering stint   127  genuine drop/re-enroll; cc_dateenrolled sits
                                  in one stint -> resolved to the stint it began
no covering stint             20  section enrolled during a withdrawal gap
                                  (18 short gaps, 2 are 122-year garbage)
```

Resolve each to the stint it began in, in priority order:

1. the stint **covering** `cc_dateenrolled`
   (`cc_dateenrolled >= entrydate and cc_dateenrolled < exitdate`) — unambiguous
   for the 127, else
2. the earliest overlapping stint (`entrydate asc`) — the 20 no-covering cases.

Add a `warn`-level singular test that counts non-dropped `cc` records
overlapping more than one stint (currently 147), so multi-overlap drift stays
visible rather than being silently resolved.

### Why this is safe for existing keys

A section contained in stint A overlaps only stint A (stints within a
student/school/year do not overlap each other), so all 624,063 contained
sections — and the 9,568 "ends-after" sections that already point-match —
resolve to the same stint as today. Their `student_enrollment_key` does not
change. Every key change is a **NULL → populated** transition (the ~19.5K
starts-before sections plus the 147 boundary-spanners, which were NULL because
the point match failed). No existing non-null key moves.

### Implementation notes

- Half-open intervals throughout per the date-range-join convention.
- Resolve the stint in a CTE at `cc` grain **before** the reporting-terms join,
  so the resolution cannot interact with term-join cardinality.
- The overlap match fans out only for the 147 boundary-spanners; collapse them
  with
  `dbt_utils.deduplicate(partition_by="cc_dcid, _dbt_source_project", order_by="is_covering desc, enr_entrydate asc")`
  — **not** `qualify row_number() = 1`. Precompute `is_covering` as a boolean
  column in the overlap-join CTE; do not inline a CASE into the surrogate-key
  inputs.
- `is_covering desc` → NULLS LAST by default; entrydate is non-null here, so the
  BigQuery `array_agg` NULLS-ordering restriction does not apply.
- The resolved row's enr attributes are authoritative including NULL — do not
  `coalesce` to a fallback row.
- Add the multi-overlap monitor as a singular `warn` test under
  `src/dbt/kipptaf/tests/` (counts non-dropped `cc` records overlapping >1
  enrollment stint; refs default to kipptaf, no `package:` needed). Baseline is
  147; the test exists for drift visibility, not to fail CI.

## Dropping the direct FK

After the dim change is verified, in both `fct_grades_assignments` and
`fct_grades_term`:

- remove the `student_enrollment_key` column from the SELECT (and its
  `student_enrollments` CTE / join where no longer otherwise needed);
- remove the column entry, its `foreign_key` constraint, and its `relationships`
  test from the model's properties YAML;
- update the model `description` (drop "FK to ... dim_student_enrollments ...").

Consumers reach the enrollment dim by traversing
`student_section_enrollment_key` → `dim_student_section_enrollments` →
`student_enrollment_key`.

## Consumer / blast radius

- **Cube**: no cube or view references either grade fact (`grep -rn` in
  `src/cube/` returns nothing). Dropping the facts' `student_enrollment_key`
  breaks no Cube model. The grade facts remain listed in `cube.yml` `depends_on`
  (the dependency exposure) but are not modeled.
- **Marts**: no other mart `ref()`s the two facts.
- **Dim hash change**: `dim_student_section_enrollments.student_enrollment_key`
  changes only NULL→populated. No existing non-null value moves, so no consumer
  keyed on a non-null value breaks. The dim's own `relationships` test to
  `dim_student_enrollments` stays valid (the new keys reference real enrollment
  rows).

## Residual / accepted

- **Stint-mismatch (0.013% / 0.34%)** — irreducible: a single section-grain dim
  row cannot carry a different enrollment per assignment due date. Accepted for
  grade reporting. The only reason to keep the direct FK would be a hard
  requirement for grade-time-exact enrollment attribution, which is not a
  current requirement.
- **2,541 orphan sections** (overlap no stint) stay NULL. They carry ~0
  assignments; ~1,400 have no enrollment record at all that year (pre-existing
  upstream gap), and ~1,140 are nonpositive-length sections handled separately
  in [#4146](https://github.com/TEAMSchools/teamster/issues/4146).

## Verification

Run against the PR-branch schema (`dbt_cloud_pr_<job>_<pr>_marts`):

1. **NULL linkage → ~0** — re-run the divergence query (direct vs traversed) for
   both facts; `traversal NULL, direct set` should drop from 985,984 / 974 to
   ~the orphan floor.
2. **Mismatch unchanged** — the ~0.013% / 0.34% stint-mismatch persists
   (documented residual).
3. **PK intact** — `dim_student_section_enrollments` stays unique on
   `student_section_enrollment_key` (the 147-row resolution collapses the
   overlap fan-out).
4. **No non-null hash drift** — count dim rows whose `student_enrollment_key`
   changed from one non-null value to a different non-null value; expect 0.
5. `dbt build --select state:modified+` green against staging.

## Out of scope

- **Nonpositive-length sections** (`cc_dateenrolled >= cc_dateleft`, 1,394
  records; 0 assignment grades, 47 term grades) and the 2 pre-2000 garbage
  sections — tracked in
  [#4146](https://github.com/TEAMSchools/teamster/issues/4146) as a
  staging-layer filter. Not gating this work.
- Aligning the assessment-scoped enrollment models (separate diamond, separate
  issue if needed).
- Any change to `dim_student_enrollments` itself.
- Per-assignment enrollment attribution (would require a fact-grain enrollment
  key, the opposite of this change).
