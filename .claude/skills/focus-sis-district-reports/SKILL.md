---
name: focus-sis-district-reports
description: >-
  Use when creating, editing, or debugging a Focus SIS District Report (Reports
  → District Reports): writing the report's SQL, choosing or wiring a variable
  type, resolving a Focus screen/field to its real database table and column,
  translating an external system's report (e.g. DeansList, PowerSchool) into
  native Focus SQL, or diagnosing a Validate error.
---

# Focus SIS District Reports

## Overview

Focus SIS District Reports are raw SQL (Focus runs PostgreSQL) published through
Reports → District Reports so staff can run them without database access. This
skill builds the report; `zendesk-help-articles` writes and publishes the
end-user help article for it.

See [`focus-schema-reference.md`](focus-schema-reference.md) for the full schema
cheat sheet (tables, join patterns, predicates, variable mechanics,
report-config options) and
[`district-report-template.sql`](district-report-template.sql) for a
ready-to-adapt starting skeleton.

## Workflow

1. **Map the request to real Focus tables.** Every Focus screen backs one or
   more tables (Student Enrollment → `student_enrollment`, Schedules →
   `schedule`, etc. — full map in the reference file). If the request translates
   a report from another system, map each of _its_ filters/columns to a Focus
   table+column, not the other way around.

2. **Ground every table/column name before writing SQL — don't guess.** In order
   of speed:
   - This repo already stages many Focus tables at
     `src/dbt/focus/models/staging/stg_focus__*.sql` — each `select`s the raw
     source columns, with the Focus name on the left of each `as`
     (`custom_9 as second_school`), so it's a free, accurate cross-check for
     anything already ingested (`students`, `schools`, `users`,
     `course_periods`, etc.). Read the model, not just its `properties.yml`.
   - `docs/superpowers/specs/references/focus-db-erd.md` is a full Focus DB ERD
     (table groups, PK/FK join keys, custom-field storage) covering tables that
     aren't staged in dbt yet — check it for anything the staging models don't
     cover before falling back to the Focus UI methods.
   - For anything not staged there, use Focus's own lookup methods: Student
     Field Setup UI, `all_fields.php`, browser Inspect Element on the field, or
     the `custom_fields` table (`column_name`, `source_class`, `type`).
   - For a table with no dbt model and no field-setup entry (e.g. a
     module-specific table like `positive_behaviors`), ask the user to paste a
     screenshot of the table's columns rather than guessing types/names.

3. **Track Confirmed vs. Verify separately as you go.** A column you read from a
   staging model, an official Focus doc, or a user-provided screenshot is
   Confirmed. A column you inferred from naming convention or a similar table is
   Verify — say so explicitly rather than presenting it with the same confidence
   as a confirmed one. Don't silently upgrade a guess to a fact because it looks
   plausible.

4. **Ask before building on a structural unknown**, not after. If a filter
   requires a lookup/roster/category table whose real shape you can't find by
   any of the methods above, stop and ask the user — a wrong guess here (wrong
   join column, wrong table) produces a report that looks fine and returns wrong
   or empty results, which is worse than asking.

5. **Write the query using the confirmed join/predicate patterns** in the
   reference file — especially the enrollment and schedule "active" filters,
   which are easy to under-specify (see reference file: naive `end_date IS NULL`
   misses students with a future end date and enrollment records that aren't the
   student's primary campus).

6. **Build variables**, not hardcoded values, for anything the report-runner
   should be able to change per run — see the variable-type and system-variable
   tables in the reference file. Remember: `{VARIABLE}` substitutes as raw,
   unquoted text — quote/cast it yourself in the SQL, and use
   `nullif('{VAR}', '')` to make a Text/Date variable optional.

7. **Validate in the Focus Edit panel before Save** — the Save button stays
   disabled until Validate passes. Multiple result sets in one report are
   semicolon-separated queries, each becoming its own dataset.

8. **When the report has real platform-limitation caveats** (e.g. Focus's report
   grid can't dynamically pivot a dimension into columns the way another tool's
   UI does), say so and offer the practical workaround (a long-format breakdown
   query, or the Chart checkbox for a simple aggregate chart) — don't silently
   ship a report that can't do what was asked.

9. **Once the SQL is solid**, offer to save it as a reference artifact (SQL +
   variables + a Confirmed/Verify status chip per fact) so the user can hand it
   off or revisit it later. It holds SQL and variables only, never result rows,
   which are student-level PII; keep it in the session scratchpad unless the
   user asks to commit it. If they also need an end-user help article, invoke
   `zendesk-help-articles` and carry over the facts it asks for: the Focus
   folder path, the report title, each variable's on-screen label, and the step
   8 caveats.

## Common mistakes

- Trusting a plausible-looking column/table name because it "sounds right" for
  Focus's naming convention, without checking a staging model, the docs, or the
  user.
- Filtering "currently enrolled" with only `end_date IS NULL` — misses
  future-dated end dates and doesn't exclude non-primary enrollment rows.
- Assuming a text/date variable is quoted for you — Focus substitutes it raw; an
  unguarded blank value breaks the query on a type mismatch.
- Presenting an unverified join as if it were confirmed, instead of flagging it
  and telling the user how to check it themselves.
- Building a wide pivot-by-category grid because the source report has one, when
  Focus's report grid doesn't support dynamic column pivoting — ship a
  long-format equivalent instead and say why.
