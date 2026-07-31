---
name: gradebook-audit
description: >-
  Use when any question or task touches the gradebook audit data model or its
  lineage. Triggers: explaining the model, listing refs/lineage/sources for the
  gradebook audit dashboard, adding/removing a flag, adding a region, debugging
  a flag that isn't firing, or working on rpt_tableau__gradebook_audit or
  rpt_gsheets__gradebook_audit_student_flags and their upstream models.
---

# Gradebook Audit Data Model

## Always read first

Before answering any question or making any change, read the reference doc. It
is the authoritative source for lineage, flag definitions, scaffold structure,
and configuration behavior. The spec covers AY 2026-2027 design decisions.

- Reference doc:
  [`docs/models/gradebook-audit-data-model.md`](../../../docs/models/gradebook-audit-data-model.md)
- Design spec:
  [`docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md`](../../../docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md)
- Implementation plan:
  [`docs/superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md`](../../../docs/superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md)

**Key gotcha:** `academic_year` stores the STARTING year. AY 2026-2027 =
`academic_year = 2026`. Confirm this with the user before generating any data.

---

## START HERE: making a change to this model

If you have been asked to change anything in this pipeline (add/remove/edit a
flag, add a region, change a threshold, refactor a model, or anything else), run
these steps **in order before editing any SQL**. Do not jump straight to a
procedure below — those are the _how_; this is the _what and whether_. This
matters most when you did not build this model: it forces the questions and the
impact checks a newcomer would otherwise miss.

1. **Clarify the change with the requester — do not assume.** Invoke the
   `superpowers:brainstorming` skill (`Skill` tool) and use it to pin down, one
   question at a time: exactly what should change, why, at which grain (student
   / section-category / teacher-quarter), which specific flag / region /
   threshold, and the expected effect on the dashboard output (more or fewer
   rows? a new column? changed boolean values? none — a pure refactor?). Do not
   edit until the change is unambiguous and the requester has confirmed the
   intended output effect.

2. **Read the reference doc** (required by "Always read first" above) so you
   know the current lineage, grain, and invariants before you reason about
   impact.

3. **Map the impact up- and downstream.** For every model you plan to touch,
   enumerate what feeds it and what consumes it — never edit against only the
   one file in front of you:

   - `mcp__dbt__get_model_parents` and `mcp__dbt__get_model_children` (or
     `mcp__dbt__get_lineage`) on each target model.
   - Cross-check against this skill's "List refs, lineage, or sources" procedure
     (the exposure file) and the reference doc's lineage diagram.
   - Invoke `dbt:using-dbt-for-analytics-engineering` (`Skill` tool) for the
     build-and-validate methodology.

4. **Flag the model-specific risks to the requester before implementing.** State
   which of these the change could break, and how you will check each:

   - the **4-row category floor** — every section × quarter must keep exactly 4
     `category_summary` rows;
   - **grain changes cascade** — a grain change in any scaffold breaks every
     downstream join and must be threaded through all consumers before a full
     chain build is valid;
   - **uniqueness tests and contracts** on every affected model;
   - the two **health columns** (`is_healthy_gradebook_all_flags` /
     `_excl_comments`) and the **broadcast** section-flag booleans — a
     new/removed flag usually has to thread into these;
   - **PII** — student-level data stays in
     `int_extracts__gradebook_audit_student_flags` and the gsheets report; it
     must never reach `rpt_tableau__gradebook_audit`;
   - the **layering rule** — reports (`rpt_`) must not read other reports;
     shared logic lives in the intermediate;
   - the **summer-toggle** state (see the rollover procedure);
   - both **exposures** — the Tableau workbook and the Google Sheet each consume
     an output of this pipeline.

5. **Implement** via the specific procedure below (add/remove/edit a flag, add a
   region, or the rollover), following the grain rules it gives.

6. **Validate, then get a review.** Build the affected models one at a time
   (never cascade a downstream build mid-refactor), confirm the checks that
   apply (uniqueness tests pass, the 4-row floor holds, and — for a refactor
   that should not change output — a byte-identical comparison of before/after),
   then invoke the `superpowers:requesting-code-review` skill (`Skill` tool)
   before opening or updating the PR.

**For a flag that is misbehaving** (firing when it shouldn't, or not firing when
it should) rather than a requested change, this is a bug, not a feature: use
"Debug a flag that isn't firing" below together with the
`superpowers:systematic-debugging` skill.

---

## Configurable thresholds

These values are hardcoded in SQL. When the user asks to change a threshold,
find the location below and update the literal.

| Threshold                                                                                                                                            | Current value | Location                                                                                |
| ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------- | --------------------------------------------------------------------------------------- |
| `min_graded_percent` — minimum fraction of expected assignments that must be scored for an assignment to pass the `percent_graded_min_not_met` check | `0.90` (90%)  | `invalid_assign_check` CTE in `int_powerschool__gradebook_assignment_scores_rollup.sql` |

To change `min_graded_percent`: update the literal `0.90` in the
`invalid_assign_check` CTE (`if(assign_percent_graded < 0.90, true, false)`).

---

## Procedure: List refs, lineage, or sources for the gradebook audit dashboard

Do NOT search the codebase. Go directly to the exposure file:

`src/dbt/kipptaf/models/exposures/tableau.yml`

Find the exposure named `gradebook_audit` and read its `depends_on` list — that
is the authoritative answer.

Current `depends_on` list (update if the exposure changes):

- `rpt_tableau__gradebook_audit`

There is also a disabled exposure `gradebook_audit_teacher_report` — mention it
only if the user asks about disabled or archived workbooks.

The companion student-flags Google Sheet has its own separate exposure in
`src/dbt/kipptaf/models/exposures/google-sheets.yml`, named
`rpt_gsheets__gradebook_audit_student_flags` — check there if asked about the
gsheets side rather than the Tableau side.

---

## Procedure: Explain the data model

Read the reference doc and answer from it. For AY 2026-2027 changes, also read
the spec doc.

---

## Procedure: Explain why a specific filter, column, or threshold exists

Some logic in this lineage has no recoverable business rationale — it was
inherited from an earlier model version and even the original author couldn't
reconstruct the "why" on review. Don't guess at a plausible-sounding reason and
present it as fact.

1. Search the reference doc first. Filters/columns with a known-undocumented
   rationale are called out there explicitly (e.g. `section_quarter_count >= 2`
   in `int_extracts__course_schedule_by_term` — see that model's section). Check
   the inline SQL comment at the derivation site too; a documented gap is noted
   in both places.
2. If the reference doc is silent, check git history yourself before answering:
   `git log -S'<column or literal>' -- <path>` to find the introducing commit,
   then read its message and diff. Check the PR that introduced it
   (`gh pr list --search` / `mcp__github__search_pull_requests`) for comment
   discussion.
3. Report what you find precisely — a commit message describing _what_ the code
   does is not the same as a business _why_. If you only find the mechanical
   description, say so plainly rather than inferring a rationale from what the
   filter happens to exclude today.
4. If this produces a new finding (no rationale exists, and it wasn't already
   documented), add it to the reference doc — a short paragraph at the relevant
   model's section stating what's known, what's not, and the introducing commit
   — plus a one-line comment at the derivation site in the SQL pointing back to
   the doc. This keeps the gap from being re-investigated from scratch next
   time.

---

## Procedure: Add a new flag

`stg_google_sheets__gradebook_flags` is disabled — no sheet step needed. Since
the July 2026 teacher/student split there are no UNPIVOT lists — every flag is a
hardcoded boolean column, and which model it lives in depends on its grain. Per
the split's design goal, do NOT add a "reason" column explaining why a flag
fired — flags stay aggregated booleans.

**Student-level flag** (per student × section × quarter, like
`qt_percent_grade_greater_100`/`qt_grade_70_comment_missing`):

1. Add the boolean column to `int_extracts__gradebook_audit_student_flags.sql`
   (in its main `select`, alongside the two existing `qt_*` flags) — the flag is
   computed once here, where both reports read it. Then add it to
   `rpt_gsheets__gradebook_audit_student_flags.sql`'s final filter
   (`where qt_percent_grade_greater_100 or qt_grade_70_comment_missing or <new_flag>`),
   and to that report's projected column list.
2. Add a matching `has_<flag>` boolean to `rpt_tableau__gradebook_audit.sql`'s
   `student_flags_aggregate` CTE (`countif(<new_flag>) > 0 as has_<flag>`) —
   this CTE reads `int_extracts__gradebook_audit_student_flags` — and thread it
   through `with_section_flags` (broadcast) and `health_calc` (both health
   columns, unless it's specifically excluded from one like
   `has_grade_below_70_no_comment` is from
   `is_healthy_gradebook_excl_comments`).
3. Update the properties YAML for all three models
   (`int_extracts__gradebook_audit_student_flags`,
   `rpt_gsheets__gradebook_audit_student_flags`,
   `rpt_tableau__gradebook_audit`).
4. Build in dependency order — `int_extracts__gradebook_audit_student_flags`
   first, then `rpt_gsheets__gradebook_audit_student_flags` and
   `rpt_tableau__gradebook_audit` (both read the int).

**Category-level flag** (per section × quarter × category, like
`not_enough_assignments`):

1. Add the boolean to `rpt_tableau__gradebook_audit.sql`'s `category_summary`
   CTE (populated on `category_summary` rows; null it on the `assignment_detail`
   branch of `combined`, matching the existing null-placeholder pattern).
2. Thread it into `health_calc`'s `logical_or(...)` for both health columns
   (unless deliberately excluded from one).
3. Update the properties YAML.
4. Build `rpt_tableau__gradebook_audit`.

Either way, verify the row-count floor is unaffected (still exactly 4
`category_summary` rows per section × quarter) and check
`is_healthy_gradebook_all_flags`/`_excl_comments` pick up the new flag
correctly.

---

## Procedure: Remove a flag

`stg_google_sheets__gradebook_flags` is disabled — no sheet step needed.

1. Remove the boolean column from wherever it's computed
   (`int_extracts__gradebook_audit_student_flags`'s main `select` for a
   student-level flag, `rpt_tableau__gradebook_audit`'s `category_summary` CTE
   for a category-level one).
2. Remove it from every place it's threaded through: the gsheets model's final
   filter and projected columns (if student-level), `student_flags_aggregate` /
   `with_section_flags` (if student-level), and both `health_calc`
   `logical_or(...)` expressions.
3. Update the properties YAML for the affected model(s).
4. Build the modified models.

---

## Procedure: Add a new region

1. Ensure the **KIPP NJ Gradebook Audit** PS plugin is deployed to the new
   region's PowerSchool instance and the `U_EXPECTATIONS` table is populated.
   Plugin source and update instructions:
   [TEAMSchools/ps-plugins](https://github.com/TEAMSchools/ps-plugins)
2. Verify `int_powerschool__u_expectations_qtd_unpivot` returns rows for the new
   region.
3. No flag sheet changes needed — the flag columns in
   `rpt_tableau__gradebook_audit` apply to all regions. The only exclusions,
   applied in `category_join`'s `WHERE` clause (and matched in
   `int_extracts__gradebook_audit_student_flags`'s own filters, which both
   reports inherit), are `_dbt_source_project != 'kippmiami'` and
   `school_level_alt != 'ES'` (MS/HS only). Confirm sections for the new region
   appear in `rpt_tableau__gradebook_audit`.

---

## Procedure: Work on the gradebook audit dashboard after academic year rollover

**Trigger phrases:** "we have swapped academic years on the database and I need
to make edits to the gradebook audit dashboard before the start of the school
year", "the database rolled over to the new year but school hasn't started yet
and I need data to work on the dash", "I need to work on the gradebook audit
views this summer"

**Scope — this is the data-team dbt toggle only.** Updating the assignment
_expectations_ for the new year is a separate task owned by the academics team,
done in PowerSchool via the `U_EXPECTATIONS` plugin — not a dbt change. For
that, see "Start-of-year procedure" (Step 1) in the
[reference doc](../../../docs/models/gradebook-audit-data-model.md), which
carries the plugin repo link and ownership. The steps below cover only the
dbt-side year / grade-source toggle.

**What's happening:** In July, the data engineering team bumps
`current_academic_year` (e.g., 2025 → 2026). At that point:

- The scaffold filters to `academic_year = 2026`, but PowerSchool has no
  sections or enrollments for the new year yet — the scaffold returns no rows.
- Even if sections existed, quarter course grades for the prior year live in
  `stg_powerschool__storedgrades` (archived), not
  `base_powerschool__final_grades` (which only holds live/active grades for the
  current year).

Both problems must be fixed together. Changing only the scaffold year or only
the `grades_type` will still produce no data.

**Files to edit** (as of the July 2026 intermediate extraction — the student
grade/comment toggle points moved out of
`rpt_gsheets__gradebook_audit_student_flags` into the new
`int_extracts__gradebook_audit_student_flags`, which the gsheets report now
reads; the gsheets report itself no longer carries any toggle):

- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_audit.sql`
- `src/dbt/kipptaf/models/students/intermediate/int_extracts__gradebook_audit_student_flags.sql`
- `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__u_expectations_qtd_unpivot.sql`
- `src/dbt/kipptaf/models/extracts/tableau/rpt_tableau__gradebook_es_comments.sql`

**Four changes to make:**

1. In `rpt_tableau__gradebook_audit` — change the year filter in
   `category_join`'s `WHERE` clause (1 occurrence, marked
   `/* summer toggle: see skill */`):

   ```sql
   -- change this:
   s.academic_year = {{ var("current_academic_year") }}
   -- to this:
   s.academic_year = {{ var("current_academic_year") - 1 }}
   ```

2. In `int_extracts__gradebook_audit_student_flags` — change both occurrences
   (marked `/* summer toggle: see skill */`): the outer `academic_year` filter,
   and the `quarter_course_grades` join's `grades_type` filter:

   ```sql
   -- change this:
   s.academic_year = {{ var("current_academic_year") }}
   -- to this:
   s.academic_year = {{ var("current_academic_year") - 1 }}
   ```

   ```sql
   -- change this:
   and qg.grades_type = 'current_year'
   -- to this:
   and qg.grades_type = 'last_year'
   ```

   This routes the grade lookup to `stg_powerschool__storedgrades` (prior-year
   archived quarter grades) instead of `base_powerschool__final_grades` (empty
   until teachers start entering grades for the new year).

3. In `int_powerschool__u_expectations_qtd_unpivot` — change both occurrences
   (one filters `int_powerschool__calendar_week`, marked
   `-- summer toggle: see skill`; one stamps the output `academic_year` column,
   marked `/* summer toggle: see skill */`):

   ```sql
   -- change this (appears 2 times):
   {{ var("current_academic_year") }}
   -- to this:
   {{ var("current_academic_year") - 1 }}
   ```

   This model has no `academic_year` column upstream (`U_EXPECTATIONS` reflects
   whatever's currently live in PowerSchool, not a specific year) — its
   `academic_year` is a literal stamped on every row.
   `rpt_tableau__gradebook_audit` joins to it on `academic_year` among other
   keys; leaving this model at `current_academic_year` while
   `rpt_tableau__gradebook_audit` is toggled to `- 1` breaks that join and
   silently drops all `category_summary`/ `assignment_detail` rows.

4. In `rpt_tableau__gradebook_es_comments` — change the year filter (1
   occurrence, marked `-- summer toggle: see skill`):

   ```sql
   -- change this:
   s.academic_year = {{ var("current_academic_year") }}
   -- to this:
   s.academic_year = {{ var("current_academic_year") - 1 }}
   ```

   **No `grades_type`/`storedgrades` fallback here, unlike the other three
   files** — this was tried and reverted. The other files audit MS/HS grades
   (or, for `u_expectations_qtd_unpivot`, aren't grade-sourced at all), and
   `stg_powerschool__storedgrades` genuinely has MS/HS archived Q-term data for
   the prior year, so a union+fallback pattern gives correct results there.
   `es_comments` only needs comments for ES schools, and
   `stg_powerschool__storedgrades` has **no Q-term data at all for ES schools in
   academic years 2021, 2024, or 2025** (confirmed empty via direct query — only
   2020/2022/2023 exist). Adding the same union pattern here doesn't add safety;
   it silently shows every comment as missing instead of falling back to real
   data, because the fallback source has nothing to fall back to. The
   single-source join works today because `base_powerschool__final_grades` still
   holds live prior-year data even after the academic-year var rolls over
   (confirmed empirically: AY2025 rows were still present after the var bumped
   to 2026).

   If this toggle ever stops returning real comments (i.e.
   `base_powerschool__final_grades` gets cleared for the prior year before the
   new year's data is ready), do NOT reflexively re-add a
   `stg_powerschool__storedgrades` union to fix it — first confirm whether the
   ES archival gap has actually been backfilled:

   ```sql
   select schoolid, academic_year, count(*) as n
   from `teamster-332318`.kipptaf_powerschool.stg_powerschool__storedgrades
   where storecode_type = 'Q'
     and schoolid in (73255, 73257, 73259, 179901, 73256, 73254) -- non-Sumner ES schools
   group by 1, 2
   order by 1, 2 desc
   ```

   If the target prior year is still missing from the results, there is no real
   fallback data source available; escalate instead of shipping a change that
   silently reports every comment as missing.

Build and verify after all four changes:

```bash
uv run dbt build \
  --select int_powerschool__u_expectations_qtd_unpivot \
    int_extracts__gradebook_audit_student_flags \
    rpt_gsheets__gradebook_audit_student_flags rpt_tableau__gradebook_audit \
    rpt_tableau__gradebook_es_comments \
  --project-dir src/dbt/kipptaf \
  --defer \
  --state target/prod
```

`int_extracts__gradebook_audit_student_flags` must be in the `--select` list
(not just the two reports) — it now holds the student toggle, and `--defer`
would otherwise read the un-toggled prod copy.

**When to revert:** once the new school year starts and teachers begin entering
grades in PowerSchool (typically Q1), revert all changes:
`current_academic_year - 1` → `current_academic_year` in all four files, and
`'last_year'` → `'current_year'` in
`int_extracts__gradebook_audit_student_flags`.

---

## Procedure: Debug a flag that isn't firing

Ask: which flag, region, school level, and quarter.

First establish which flag: `has_grade_above_100` /
`has_grade_below_70_no_comment` (student-level, aggregated from
`int_extracts__gradebook_audit_student_flags`), `not_enough_assignments`
(category-level), or one of the two health columns
(`is_healthy_gradebook_all_flags` / `is_healthy_gradebook_excl_comments`).

Check in order:

1. **Boolean `true` at its source?** Student-level: query
   `int_extracts__gradebook_audit_student_flags` directly for the
   student/section/quarter — it is unfiltered (one row per scoped enrollment,
   flag `true` or `false`), so it shows whether the grade/comment computation
   fired. (`rpt_gsheets__gradebook_audit_student_flags` is the same rows
   filtered to flagged-only, so absence there just means no flag fired.)
   Category-level: query `rpt_tableau__gradebook_audit` filtered to
   `row_type = 'category_summary'` for the section/quarter/category.
2. **In scope at all?** Two silent exclusion rules apply in `category_join`'s
   `WHERE` (`rpt_tableau__gradebook_audit`) and matched in
   `int_extracts__gradebook_audit_student_flags`'s own filters:
   - `_dbt_source_project != 'kippmiami'` — Miami is excluded at source (AY
     2026-2027 onward)
   - `school_level_alt != 'ES'` — ES is excluded everywhere; ES is handled
     separately by `rpt_tableau__gradebook_es_comments`
3. **For a student-level flag, did it survive the aggregation into
   `rpt_tableau__gradebook_audit`?** `student_flags_aggregate` groups
   `int_extracts__gradebook_audit_student_flags` to
   `_dbt_source_project, sectionid, quarter` — if the flagged row exists in the
   int but `has_<flag>` still reads `false` on the teacher-side report, check
   the join in `with_section_flags` (on
   `_dbt_source_project, sectionid, quarter`) for a key mismatch, not the flag
   logic itself.
4. **Row-count floor intact?** Every section × quarter should have exactly 4
   `category_summary` rows (one per W/H/F/S). If fewer, the
   `int_powerschool__u_expectations_qtd_unpivot` join in `category_join` is
   probably missing a category for that region/school_level/quarter — check that
   model directly, not the flag logic.
5. **Is the affected student/course/quarter one of the known ambiguous-dedup
   cases in `int_extracts__course_enrollments_by_term`?** (Inherited by
   `int_extracts__gradebook_audit_student_flags`, which reads it — and thus by
   both reports downstream.) Its `enrollments` CTE picks one section per
   student/course/quarter with a `row_number()` tiebreaker that is frequently a
   true tie (see reference doc) — when it is, the teacher/section actually in
   scope for that student that quarter is arbitrary and can differ from what
   you'd expect from PowerSchool. Query the model directly for that
   student/course/quarter to check whether more than one candidate section
   exists before assuming the flag logic itself is wrong.

`stg_google_sheets__gradebook_flags` is disabled — do not check the allowlist
sheet. `stg_google_sheets__gradebook_exceptions` is also disabled — do not check
for exception rows.
