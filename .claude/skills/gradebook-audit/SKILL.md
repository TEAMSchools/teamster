---
name: gradebook-audit
description: >-
  Use when any question or task touches the gradebook audit data model or its
  lineage. Triggers: explaining the model, adding flag rows for a new year,
  adding/removing a flag, adding a region, debugging a flag that isn't firing,
  or working on any model from int_tableau__gradebook_audit_* through
  rpt_tableau__gradebook_audit.
---

# Gradebook Audit Data Model

## Overview

The gradebook audit Tableau dashboard monitors teacher gradebook compliance with
KIPP TAF grading policy. It is powered by `rpt_tableau__gradebook_audit` and
covers the current academic year.

**Always read first:**

- Reference doc:
  [`docs/reference/gradebook-audit-data-model.md`](../../docs/reference/gradebook-audit-data-model.md)
- Design spec (AY 2026-2027):
  [`docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md`](../../docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md)

Before answering any question or making any change, read the reference doc. It
is the authoritative source for lineage, flag definitions, and configuration
behavior.

## Quick reference

**Coverage (AY 2026-2027 after current implementation):**

| Region   | School level | Coverage                               |
| -------- | ------------ | -------------------------------------- |
| Camden   | MS, HS       | Full audit                             |
| Camden   | ES           | EOQ comments (`qt_es_comment_missing`) |
| Newark   | MS, HS       | Full audit                             |
| Newark   | ES           | EOQ comments (`qt_es_comment_missing`) |
| Paterson | MS           | Full audit                             |
| Paterson | ES           | EOQ comments (`qt_es_comment_missing`) |

**Three Google Sheets control behavior (no SQL change needed to toggle):**

| Sheet                                     | Purpose                                                                                      |
| ----------------------------------------- | -------------------------------------------------------------------------------------------- |
| `stg_google_sheets__gradebook_flags`      | Allowlist — a flag only fires if a row exists here                                           |
| `stg_google_sheets__gradebook_exceptions` | Suppression — permanently or temporarily removes specific rows (being disabled AY 2026-2027) |

The expectations source is migrating from
`stg_google_sheets__gradebook_expectations_assignments` (deprecated) to a
PS-native intermediate model (`int_powerschool__u_expectations[_unpivot]`).

**`academic_year` convention:** stores the STARTING year. AY 2026-2027 =
`academic_year = 2026`. Always confirm this with the user before generating
data.

---

## Procedure: Explain the data model

Read `docs/reference/gradebook-audit-data-model.md` before answering. Use it to
answer questions about lineage, flag definitions, scaffold structure, health
score formula, or configuration. If the user asks about AY 2026-2027 changes,
also read the spec doc.

---

## Procedure: Annual flags rollover

Ask these questions before generating anything:

1. **What is the new academic year?** (e.g. "AY 2027-2028" →
   `academic_year = 2027`)
2. **Are any flags being deprecated this year?** List them, or say none.
3. **Are any regions being added or removed?** Confirm coverage changes.
4. **Are any school levels changing for existing regions?** (e.g. adding HS to a
   region that only had MS before)

Once confirmed, run the following query against BigQuery (substitute
`<prior_year>` and `<new_year>`) and display the result as a tab-separated table
that the user can paste directly into the Google Sheet:

```sql
SELECT * FROM (

  -- Active regions: copy prior year, bump academic_year, exclude deprecated flags
  SELECT
    <new_year> AS academic_year,
    region,
    school_level,
    grade_level,
    code_type,
    code,
    audit_category,
    audit_flag_name,
    cte_grouping,
  FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
  WHERE region IN ('Newark', 'Camden')  -- update list if regions changed
    AND academic_year = <prior_year>
    AND audit_flag_name NOT IN (
      -- paste deprecated flag names here, or omit block if none
    )

  UNION ALL

  -- Paterson MS: mirror Newark MS
  SELECT
    <new_year> AS academic_year,
    'Paterson' AS region,
    school_level,
    grade_level,
    code_type,
    code,
    audit_category,
    audit_flag_name,
    cte_grouping,
  FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
  WHERE region = 'Newark'
    AND school_level = 'MS'
    AND academic_year = <prior_year>
    AND audit_flag_name NOT IN (
      -- same deprecated list
    )

  UNION ALL

  -- Paterson ES: EOQ comments only (Q3 and Q4)
  SELECT
    <new_year> AS academic_year,
    'Paterson' AS region,
    'ES' AS school_level,
    grade_level,
    code_type,
    code,
    audit_category,
    audit_flag_name,
    cte_grouping,
  FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
  WHERE region = 'Newark'
    AND school_level = 'ES'
    AND academic_year = <prior_year>
    AND code IN ('Q3', 'Q4')

)
ORDER BY region, school_level, code_type, code, audit_flag_name
```

Column order in the output must match the sheet:
`academic_year, region, school_level, grade_level, code_type, code, audit_category, audit_flag_name, cte_grouping`.
The `grade_level` column will be blank for all rows — that is correct.

After pasting, the user must stage the external table and rebuild staging:

```bash
uv run dbt run-operation stage_external_sources \
  --args '{"select": "google_sheets.src_google_sheets__gradebook_flags"}' \
  --project-dir src/dbt/kipptaf

uv run dbt build \
  --select stg_google_sheets__gradebook_flags \
  --project-dir src/dbt/kipptaf
```

---

## Procedure: Add a new flag

1. **Sheet first:** add a row to `stg_google_sheets__gradebook_flags` with the
   flag name, region, school_level, code, code_type, audit_category, and
   cte_grouping. Stage and rebuild the staging model. Verify the flag appears in
   staging data before touching SQL.
2. **SQL second:** add the boolean column to the appropriate model in the
   lineage (see reference doc for which model owns each flag type). Add it to
   the UNPIVOT list in `int_tableau__gradebook_audit_flags.sql`. Update the
   properties YAML.
3. Build only the modified model, then verify the flag appears in
   `rpt_tableau__gradebook_audit`.

---

## Procedure: Remove a flag

1. **Sheet first:** delete the row(s) for the flag from
   `stg_google_sheets__gradebook_flags`. Stage and rebuild staging. The flag
   will stop firing immediately — no SQL change needed for the dashboard.
2. **SQL cleanup (separate step):** once the sheet row is gone, remove the
   boolean column from the source model, remove it from the UNPIVOT list in
   `int_tableau__gradebook_audit_flags.sql`, and update the properties YAML. Do
   this as a separate commit so the sheet change is reviewable independently.

---

## Procedure: Add a new region

1. Add rows to `stg_google_sheets__gradebook_flags` for the new region (mirror
   an existing region at the same school level). Stage and rebuild.
2. If the region needs expectations data, add rows to
   `stg_google_sheets__gradebook_expectations_assignments` OR ensure the
   PS-native `int_powerschool__u_expectations[_unpivot]` model covers the region
   (requires the U_EXPECTATIONS plugin deployed to that PS instance).
3. No SQL changes needed in the scaffold if the region's PS data already flows
   through `base_powerschool__sections` — verify by checking that new sections
   appear in the teacher scaffold after the sheet changes.

---

## Procedure: Debug a flag that isn't firing

Ask the user which flag, which region/school level, and which quarter.

Check in this order:

1. **Is there a row in `stg_google_sheets__gradebook_flags`?** A flag only fires
   if a matching allowlist row exists. Query:

   ```sql
   SELECT * FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
   WHERE audit_flag_name = '<flag_name>'
     AND region = '<region>'
     AND academic_year = <year>
   ```

2. **Is the boolean `true` in the source model?** Find which model computes the
   flag (reference doc flag inventory) and query it directly.

3. **Is the section in the scaffold?** Check
   `int_tableau__gradebook_audit_teacher_scaffold` for the section/quarter
   combination.

4. **Is there an active exception row suppressing it?** Check
   `stg_google_sheets__gradebook_exceptions` for matching `view_name` / `cte` /
   `audit_flag_name` keys.

---

## Procedure: Work on a model in the lineage

Before modifying any model, read the reference doc section for that model to
understand its grain, joins, and downstream consumers. Key rules:

- **Build one model at a time** — never cascade downstream during a structural
  refactor. Downstream models may reference columns being removed.
- **Sheet changes deactivate flags immediately** — SQL cleanup is a separate
  later step.
- The scaffolds are the base; everything downstream inherits their grain. A
  grain change in the scaffold (e.g. week → quarter) cascades to all downstream
  join conditions.
