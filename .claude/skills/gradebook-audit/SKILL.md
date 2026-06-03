---
name: gradebook-audit
description: >-
  Use when any question or task touches the gradebook audit data model or its
  lineage. Triggers: explaining the model, listing refs/lineage/sources for the
  gradebook audit dashboard, adding flag rows for a new year, adding/removing a
  flag, adding a region, debugging a flag that isn't firing, or working on any
  model from int_tableau__gradebook_audit_* through
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

## Procedure: List refs, lineage, or sources for the gradebook audit dashboard

Do NOT search the codebase. Go directly to the exposure file:

`src/dbt/kipptaf/models/exposures/tableau.yml`

Find the exposure named `gradebook_audit` and read its `depends_on` list — that
is the authoritative answer. If no `gradebook_audit` exposure exists yet, fall
back to `gradebook_and_gpa_dashboard` and note the rename is pending.

Current `depends_on` list (update if the exposure changes):

- `rpt_tableau__assignment_checks`
- `rpt_tableau__gradebook_audit`
- `rpt_tableau__gradebook_es_comments`
- `rpt_tableau__gradebook_ms_hs_comments`

There is also a disabled exposure `gradebook_audit_teacher_report` — mention it
only if the user asks about disabled or archived workbooks.

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

After the user confirms they have pasted the rows into the sheet, immediately
run the **Validate flags after rollover** procedure below — do not wait to be
asked. The validation is always the next step after a rollover.

---

## Procedure: Validate flags after rollover

Run this after the user has added new rows to the sheet. First confirm the rows
have landed in the prod staging table, then tell the user to stage and rebuild
in their dev environment, then run the consistency checks.

**Step 1 — Check if new rows are in prod** (substitute `<new_year>`):

> **Note on timing:** BigQuery caches Google Sheets external tables and the
> cache can take anywhere from a few seconds to a few minutes to refresh after
> the sheet is edited. Before running the check, ask the user: **"Would you like
> me to set up a loop to check automatically every 5 minutes until the rows
> appear, or would you prefer to check manually?"**
>
> **If they say yes to the loop:** use the `loop` skill with a prompt that both
> checks for the rows AND — if they are found — immediately runs steps 2 and 3
> of this validation procedure in the same response. The user should not need to
> ask; when the data appears, Claude says "Rows are in prod! Running validation
> now…" and proceeds automatically.
>
> **If they prefer manual:** run the check below, and if rows are not visible
> yet wait a few minutes and retry. Do not proceed to staging until rows are
> visible.

```sql
SELECT DISTINCT region, school_level, academic_year,
    COUNT(*) AS row_count
FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
WHERE academic_year = <new_year>
GROUP BY 1, 2, 3
ORDER BY 1, 2
```

If the expected regions and row counts appear, the rows are in prod. Tell the
user: **"Rows are in prod — time to stage and rebuild in your dev
environment:"**

```bash
uv run dbt run-operation stage_external_sources \
  --args '{"select": "google_sheets.src_google_sheets__gradebook_flags"}' \
  --project-dir src/dbt/kipptaf

uv run dbt build \
  --select stg_google_sheets__gradebook_flags \
  --project-dir src/dbt/kipptaf
```

**Step 2 — Flag consistency check** — run this query and report any rows where
not all active regions have the flag at the same school level. Flags that exist
in Camden or Newark but not the other (for the same school level) are suspect.
Flags in Newark MS but not Paterson MS are also suspect (Paterson MS mirrors
Newark MS). HS gaps for Paterson are expected (no HS schools).

```sql
WITH flags AS (
    SELECT region, school_level, audit_flag_name
    FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
    WHERE academic_year = <new_year>
    GROUP BY 1, 2, 3
),
newark  AS (SELECT school_level, audit_flag_name FROM flags WHERE region = 'Newark'),
camden  AS (SELECT school_level, audit_flag_name FROM flags WHERE region = 'Camden'),
paterson AS (SELECT school_level, audit_flag_name FROM flags WHERE region = 'Paterson')

SELECT
    COALESCE(n.school_level, c.school_level, p.school_level) AS school_level,
    COALESCE(n.audit_flag_name, c.audit_flag_name, p.audit_flag_name) AS audit_flag_name,
    IF(n.audit_flag_name IS NOT NULL, 'Y', '-') AS newark,
    IF(c.audit_flag_name IS NOT NULL, 'Y', '-') AS camden,
    IF(p.audit_flag_name IS NOT NULL, 'Y', '-') AS paterson,
FROM newark n
FULL OUTER JOIN camden c USING (school_level, audit_flag_name)
FULL OUTER JOIN paterson p USING (school_level, audit_flag_name)
WHERE NOT (
    n.audit_flag_name IS NOT NULL
    AND c.audit_flag_name IS NOT NULL
    AND (
        COALESCE(n.school_level, c.school_level) = 'HS'
        OR p.audit_flag_name IS NOT NULL
    )
)
ORDER BY school_level, audit_flag_name
```

**What to look for in the results:**

- Any MS flag missing from one of Newark/Camden/Paterson MS → missing row, add
  it
- Any flag present in only one region → possible typo or intentional difference,
  ask the user
- HS flags missing from Paterson → expected, ignore
- ES flags: only `qt_es_comment_missing` should be present for all three regions

**Step 3 — Typo check** — flags that appear for only one region/school level are
the most likely typos:

```sql
SELECT audit_flag_name, school_level,
    STRING_AGG(region ORDER BY region) AS regions,
    COUNT(DISTINCT region) AS region_count
FROM `teamster-332318.kipptaf_google_sheets.stg_google_sheets__gradebook_flags`
WHERE academic_year = <new_year>
GROUP BY 1, 2
HAVING COUNT(DISTINCT region) = 1
ORDER BY school_level, audit_flag_name
```

Any row returned here is suspicious — a valid flag should appear in at least two
regions. Report all results to the user and ask them to confirm each one is
intentional or a typo.

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
