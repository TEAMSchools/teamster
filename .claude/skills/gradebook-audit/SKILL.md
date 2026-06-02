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

## Always read first

Before answering any question or making any change, read the reference doc. It
is the authoritative source for lineage, flag definitions, scaffold structure,
and configuration behavior. The spec covers AY 2026-2027 design decisions.

- Reference doc:
  [`docs/reference/gradebook-audit-data-model.md`](../../docs/reference/gradebook-audit-data-model.md)
- Design spec:
  [`docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md`](../../docs/superpowers/specs/2026-05-14-gradebook-audit-ay2627-design.md)
- Implementation plan:
  [`docs/superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md`](../../docs/superpowers/plans/2026-05-14-gradebook-audit-ay2627-revamp.md)

**Key gotcha:** `academic_year` stores the STARTING year. AY 2026-2027 =
`academic_year = 2026`. Confirm this with the user before generating any data.

---

## Procedure: Explain the data model

Read the reference doc and answer from it. For AY 2026-2027 changes, also read
the spec doc.

---

## Procedure: Annual flags rollover

Ask before generating anything:

1. What is the new academic year? (e.g. "AY 2027-2028" → `academic_year = 2027`)
2. Are any flags being deprecated this year?
3. Are any regions being added or removed?
4. Are any school levels changing for existing regions?

Then run this query (substitute `<prior_year>`, `<new_year>`, deprecated flag
list, and active region list based on the answers):

```sql
SELECT * FROM (

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
  WHERE region IN ('Newark', 'Camden')
    AND academic_year = <prior_year>
    AND audit_flag_name NOT IN ( /* deprecated flags, or omit if none */ )

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
    AND audit_flag_name NOT IN ( /* same deprecated list */ )

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

Display the result as a tab-separated table in the chat — the user copies it and
pastes directly into the sheet. Column order must be:
`academic_year, region, school_level, grade_level, code_type, code, audit_category, audit_flag_name, cte_grouping`.
`grade_level` will be blank for all rows — that is correct.

After the user pastes, they stage and rebuild:

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

1. **Sheet first:** add the row to `stg_google_sheets__gradebook_flags`. Stage
   and rebuild staging. Verify the flag appears in the staging table before
   writing any SQL.
2. **SQL second:** add the boolean column to the source model (see reference doc
   flag inventory for which model owns each flag type), add it to the UNPIVOT
   list in `int_tableau__gradebook_audit_flags.sql`, and update the properties
   YAML.
3. Build only the modified model. Verify the flag appears in
   `rpt_tableau__gradebook_audit`.

---

## Procedure: Remove a flag

1. **Sheet first:** delete the row from `stg_google_sheets__gradebook_flags`.
   Stage and rebuild. The flag stops firing immediately — no SQL needed yet.
2. **SQL cleanup (separate commit):** remove the boolean column from the source
   model, remove it from the UNPIVOT list in
   `int_tableau__gradebook_audit_flags.sql`, and update the YAML.

---

## Procedure: Add a new region

1. Add rows to `stg_google_sheets__gradebook_flags` mirroring an existing region
   at the same school level. Stage and rebuild.
2. For expectations data: add rows to
   `stg_google_sheets__gradebook_expectations_assignments` (legacy) OR ensure
   the PS-native `int_powerschool__u_expectations[_unpivot]` covers the region
   (requires the U_EXPECTATIONS plugin deployed to that PS instance — scripts at
   [TEAMSchools/ps-plugins](https://github.com/TEAMSchools/ps-plugins)).
3. No SQL changes needed if the region's PS data flows through
   `base_powerschool__sections` — verify by checking sections appear in the
   teacher scaffold after the sheet changes.

---

## Procedure: Recover category grades or course grades after academic year rollover

**Trigger phrases:** "we lost category grades", "dashboard is blank after
summer", "no grades showing", "category grades disappeared", "current year
rolled over but data isn't there yet"

**What happens:** In July, the dbt `current_academic_year` variable is bumped
(e.g., 2025 → 2026). PowerSchool has no grade records for the new year yet.
`int_tableau__gradebook_audit_student_scaffold` then looks for data that doesn't
exist and the dashboard goes blank.

**File:**
`src/dbt/kipptaf/models/extracts/tableau/intermediate/int_tableau__gradebook_audit_student_scaffold.sql`

**Two flips to recover (switch to prior-year data):**

1. Direct JOIN to `int_powerschool__category_grades` in the
   `student_category_scaffold` branch — change the yearid join condition:

   ```sql
   -- change this:
   and cg.yearid = {{ var("current_academic_year") - 1990 }}
   -- to this:
   and cg.yearid = {{ var("current_academic_year") - 1991 }}
   ```

2. Both UNION branches — change the `quarter_course_grades` join filter from
   current year to prior year:

   ```sql
   -- change this:
   and qg.grades_type = 'current_year'
   -- to this:
   and qg.grades_type = 'last_year'
   ```

**When to flip back:** once the new academic year's grade data starts appearing
in PowerSchool (typically when teachers start entering grades in Q1), revert
both changes: `- 1991` → `- 1990` and `'last_year'` → `'current_year'`.

Build and verify after each flip:

```bash
uv run dbt build \
  --select int_tableau__gradebook_audit_student_scaffold \
  --project-dir src/dbt/kipptaf \
  --defer \
  --state src/dbt/kipptaf/target/prod
```

---

## Procedure: Debug a flag that isn't firing

Ask: which flag, region, school level, and quarter.

Check in order:

1. **Row in `stg_google_sheets__gradebook_flags`?** A flag only fires if a
   matching allowlist row exists.
2. **Boolean `true` in the source model?** Find which model computes the flag
   (reference doc flag inventory) and query it directly.
3. **Section in the scaffold?** Check
   `int_tableau__gradebook_audit_teacher_scaffold` for the section/quarter
   combination.
4. **Active exception row?** Check `stg_google_sheets__gradebook_exceptions` for
   a matching `view_name` / `cte` / `audit_flag_name` key.

---

## Procedure: Work on a model in the lineage

Read the reference doc section for the specific model before touching it. Key
rules from the implementation plan:

- **Build one model at a time** — never cascade downstream mid-refactor.
- **Sheet changes deactivate flags immediately** — SQL cleanup is a separate
  later step.
- A grain change in the scaffolds cascades to all downstream join conditions.
  Downstream models must be updated before a full chain build is valid.
