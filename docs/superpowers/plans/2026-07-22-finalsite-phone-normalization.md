# Finalsite Contact Phone Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize Finalsite contact phone numbers to a canonical E.164 form
for all consumers, and format them to DeansList's "numbers or x" rule in the
DeansList extract — de-garbling mojibake and salvaging malformed values without
dropping anything.

**Architecture:** A `clean_phone()` macro (finalsite package) normalizes each
phone to E.164 (US `+1…`, international preserved, extensions appended) or
passes through the de-garbled original; it is applied to the four phone columns
in `int_finalsite__student_contacts`, so every downstream consumer inherits
clean phones. `rpt_deanslist__family_contacts` then strips its phone columns to
`[0-9x]`.

**Tech Stack:** dbt (BigQuery), Jinja macro, dbt unit tests, trunk.

## Global Constraints

- Work in the worktree
  `/workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization`.
  Every `git`, `dbt`, Read/Edit/Write path targets that worktree.
- Issue [#4498](https://github.com/TEAMSchools/teamster/issues/4498). Spec:
  `docs/superpowers/specs/2026-07-22-finalsite-phone-normalization-design.md`.
- The `clean_phone` E.164 logic below is already verified against BigQuery (14
  representative cases pass) — implement it verbatim; do not redesign the regex.
- Never emit NULL for a non-null input in `clean_phone` — unparseable values
  pass through de-garbled so they stay visible.
- SQL follows `src/dbt/CLAUDE.md` (BigQuery dialect, trailing commas, single
  quotes, ST06 column order). Prefer inline `regexp_extract` over
  `extract_code_location` is NOT relevant here.
- `uv run` for all dbt. `int_finalsite__student_contacts` is a finalsite
  **package** model — build/test it through a consuming district (`kippnewark`)
  with `--defer`. Run `uv run dbt deps` in each project-dir first.
- PII stays local — spot-check phone values only in the terminal, never in the
  PR/issue/commit.

---

## File structure

- Create: `src/dbt/finalsite/macros/clean_phone.sql` — the E.164 normalization
  macro (single source of truth, reusable).
- Modify:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql`
  — wrap the final union in an `all_contacts` CTE and apply `clean_phone()` to
  `phone_mobile` / `phone_home` / `phone_work` / `phone_primary`.
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml`
  — add a unit test covering the phone normalization.
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`
  — strip `HomePhone` / `WorkPhone` / `CellPhone` to `[0-9x]`.
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml`
  — add phone assertions to the unit test.

---

## Task 1: `clean_phone` macro + apply in `int_finalsite__student_contacts`

**Files:**

- Create: `src/dbt/finalsite/macros/clean_phone.sql`
- Modify:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql`
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml`

**Interfaces:**

- Produces: `clean_phone(column)` — a Jinja macro emitting a STRING expression.
  Given a raw phone column, returns E.164 (`+1XXXXXXXXXX`, international
  `+<cc>…`, extension `…x<ext>`) when confidently parseable, else the de-garbled
  original. Never NULL for a non-null input.
- `int_finalsite__student_contacts` keeps its 18-column output; only the four
  phone columns' values change.

- [ ] **Step 1: Create the macro**

Create `src/dbt/finalsite/macros/clean_phone.sql` with exactly:

```sql
{% macro clean_phone(column) %}
    {#-
      Normalize a raw phone to E.164:
        - US (bare 10, +1, or 11-digit leading 1, NANP-valid) -> +1XXXXXXXXXX
        - explicit international (+<cc!=1> or 011<cc>)         -> +<cc><national>
        - explicit x/ext extension                            -> append x<ext>
      Anything not confidently parseable passes through the de-garbled original
      (control chars stripped). Never returns NULL for a non-null input.
    -#}
    {%- set degarbled -%}
        trim(regexp_replace({{ column }}, r'[^\x20-\x7E]', ''))
    {%- endset -%}
    {%- set ext -%}
        regexp_extract(
            {{ degarbled }}, r'(?i)(?:ext\.?|extension|x)\s*(\d{1,6})\s*$'
        )
    {%- endset -%}
    {%- set main -%}
        regexp_replace(
            {{ degarbled }}, r'(?i)\s*(?:ext\.?|extension|x)\s*\d{1,6}\s*$', ''
        )
    {%- endset -%}
    {%- set digits -%} regexp_replace({{ main }}, r'\D', '') {%- endset -%}
    coalesce(
        case
            when
                regexp_contains({{ main }}, r'^\s*\+')
                and not regexp_contains({{ main }}, r'^\s*\+\s*1')
                and length({{ digits }}) between 8 and 15
            then '+' || {{ digits }}
            when
                starts_with({{ digits }}, '011')
                and length({{ digits }}) between 11 and 18
            then '+' || substr({{ digits }}, 4)
            when
                length({{ digits }}) = 10
                and regexp_contains({{ digits }}, r'^[2-9]\d{2}[2-9]\d{6}$')
            then '+1' || {{ digits }}
            when
                length({{ digits }}) = 11
                and starts_with({{ digits }}, '1')
                and regexp_contains(
                    substr({{ digits }}, 2), r'^[2-9]\d{2}[2-9]\d{6}$'
                )
            then '+1' || substr({{ digits }}, 2)
        end
        || if({{ ext }} is not null, 'x' || {{ ext }}, ''),
        {{ degarbled }}
    )
{% endmacro %}
```

The `coalesce(<case> || <ext-suffix>, degarbled)` returns the de-garbled
original whenever the CASE is NULL (BigQuery `NULL || x` is NULL), giving the
passthrough behavior without re-evaluating the CASE.

- [ ] **Step 2: Wrap the union and apply the macro in the model**

In
`src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql`,
replace the final two-branch `SELECT … UNION ALL SELECT …` (the tail after the
`emergency as (…)` CTE) with an `all_contacts` CTE plus a normalizing final
select. The two union branches keep their existing 18 columns unchanged; only
the final select changes:

```sql
    ),

    all_contacts as (
        select
            finalsite_enrollment_id,
            contact_slot,
            finalsite_contact_id,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email,
            phone_mobile,
            phone_home,
            phone_work,
            phone_daytime,
            phone_primary,
            home_address,
            is_pickup,
            is_custodial,
            is_household_member,
            is_emergency,
        from contact_1

        union all

        select
            finalsite_enrollment_id,
            contact_slot,
            finalsite_contact_id,
            contact_name,
            contact_first_name,
            contact_last_name,
            relationship,
            email,
            phone_mobile,
            phone_home,
            phone_work,
            phone_daytime,
            phone_primary,
            home_address,
            is_pickup,
            is_custodial,
            is_household_member,
            is_emergency,
        from emergency
    )

select
    finalsite_enrollment_id,
    contact_slot,
    finalsite_contact_id,
    contact_name,
    contact_first_name,
    contact_last_name,
    relationship,
    email,
    phone_daytime,
    home_address,
    is_pickup,
    is_custodial,
    is_household_member,
    is_emergency,

    {{ clean_phone("phone_mobile") }} as phone_mobile,
    {{ clean_phone("phone_home") }} as phone_home,
    {{ clean_phone("phone_work") }} as phone_work,
    {{ clean_phone("phone_primary") }} as phone_primary,
from all_contacts
```

(`phone_daytime` is always NULL upstream, so it is left as a plain passthrough
column, not cleaned. The four cleaned phones sort last per ST06 — plain columns
first, then function-wrapped columns.)

- [ ] **Step 3: Add the failing unit test**

Append to
`src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml`
(top-level `unit_tests:` key). It drives a `contact_1` row whose Cell phone is
garbled and whose Home phone is a bare-10; both must normalize to E.164. The
emergency input is mocked empty.

```yaml
unit_tests:
  - name: test_student_contacts_phone_normalization
    description:
      A contact_1 row with a control-char-garbled cell phone and a bare-10 home
      phone normalizes both to E.164 (+1XXXXXXXXXX).
    model: int_finalsite__student_contacts
    given:
      - input: ref("stg_finalsite__contact_relationships")
        format: sql
        rows: |
          select
            "stu1" as finalsite_enrollment_id,
            "rel1" as relationship_id,
            "con1" as rel_id,
            "Jane Doe" as rel_name,
            "parent" as rel_type,
            true as is_primary,
            true as is_financial
      - input: ref("stg_finalsite__contacts")
        format: sql
        rows: |
          select
            "con1" as finalsite_enrollment_id,
            "jane@example.com" as email,
            "Jane" as first_name,
            "Doe" as last_name,
            code_points_to_string([8234])
              || "+1 (862) 300" || code_points_to_string([8209]) || "7240"
              || code_points_to_string([8236]) as phone_1_number,
            "Cell" as phone_1_type,
            "(929) 225-5670" as phone_2_number,
            "Home" as phone_2_type,
            cast(null as string) as phone_3_number,
            cast(null as string) as phone_3_type,
            cast(null as string) as address_1,
            cast(null as string) as address_2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zip
      - input: ref("int_finalsite__contact_custom_attributes")
        rows: []
    expect:
      format: sql
      rows: |
        select
          "stu1" as finalsite_enrollment_id,
          "contact_1" as contact_slot,
          "con1" as finalsite_contact_id,
          "Jane Doe" as contact_name,
          "Jane" as contact_first_name,
          "Doe" as contact_last_name,
          "parent" as relationship,
          "jane@example.com" as email,
          cast(null as string) as phone_daytime,
          cast(null as string) as home_address,
          cast(null as boolean) as is_pickup,
          cast(null as boolean) as is_custodial,
          cast(null as boolean) as is_household_member,
          false as is_emergency,
          "+18623007240" as phone_mobile,
          "+19292255670" as phone_home,
          cast(null as string) as phone_work,
          "+18623007240" as phone_primary
```

(`phone_primary` in the `contact_1` branch is `phone_1_number` — the garbled
cell — so it normalizes to `+18623007240` too. Use `format: sql` for `expect` to
control column types precisely; list all 18 output columns.)

- [ ] **Step 4: Install deps and run the unit test — expect FAIL**

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization/src/dbt/kippnewark

uv run dbt test \
  --select "int_finalsite__student_contacts,test_type:unit" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization/src/dbt/kippnewark \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kippnewark/target/prod
```

Expected before Steps 1-2 are applied: FAIL (phones not normalized). After Steps
1-2: run again → PASS. (Author the test first, watch it fail against the
unmodified model, then apply the macro + model change and watch it pass.)

- [ ] **Step 5: Run the unit test — expect PASS**

Re-run the Step 4 `dbt test` command. Expected: `PASS=1`.

- [ ] **Step 6: Build the model against prod data and spot-check**

```bash
uv run dbt build \
  --select int_finalsite__student_contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization/src/dbt/kippnewark \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippnewark/target/prod
```

Expected: builds; existing tests pass. Then via the BigQuery MCP, query the
dev-built table
(`zz_<user>_kippnewark_finalsite.int_finalsite__student_contacts`) for a handful
of previously-garbled emergency rows and confirm `phone_mobile` etc. are now
`+1…` / passthrough (PII stays in the terminal). Confirm row count is unchanged
vs prod.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization \
  && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/finalsite/macros/clean_phone.sql \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml \
  </dev/null

git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization \
  add src/dbt/finalsite/macros/clean_phone.sql \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml

git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization \
  commit -m "feat(finalsite): normalize contact phones to E.164 via clean_phone

Refs #4498"
```

---

## Task 2: DeansList "numbers or x" formatting

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`
- Modify:
  `src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml`

**Interfaces:**

- Consumes: `int_finalsite__student_contacts.phone_home` / `phone_work` /
  `phone_mobile`, now E.164 (from Task 1, via the kipptaf union).
- Produces: `HomePhone` / `WorkPhone` / `CellPhone` containing only digits and
  `x` (leading US `1` kept, extensions kept).

- [ ] **Step 1: Apply the strip in the final select**

In
`src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql`,
change the three phone projections in the final `SELECT` from plain passthrough
to a `[0-9x]` strip (one level of nesting — `lower` inside `regexp_replace` — is
allowed):

```sql
    regexp_replace(lower(c.phone_home), r'[^0-9x]', '') as `HomePhone`,
    regexp_replace(lower(c.phone_work), r'[^0-9x]', '') as `WorkPhone`,
    regexp_replace(lower(c.phone_mobile), r'[^0-9x]', '') as `CellPhone`,
```

Leave the other columns unchanged. Note the ST06 order: these become
function-wrapped columns, so they must sort after the plain-column projections
(`StudentID`, `ParentFirstName`, `ParentLastName`) — reorder the final `SELECT`
so the three phones, `Email` passthrough, `Relationship`, and the
`cast(null …) Language` follow the plain columns, phones grouped with the other
function/expression columns. Confirm the exact ordering with `trunk check` in
Step 4 and adjust to satisfy ST06.

- [ ] **Step 2: Add phone assertions to the unit test**

In
`src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml`,
edit the existing `test_family_contacts_emergency_numbering` unit test: give the
`int_finalsite__student_contacts` mock input E.164-shaped phones and assert the
stripped output. In the mock's `contact_1` row set
`phone_home = '+19292255670'`, `phone_mobile = '+18623007240x216'`; in the
`expect` rows for that student set `HomePhone: 9292255670`,
`CellPhone: 18623007240x216` (unquoted — digits/`x` only), `WorkPhone: null`.
Update the other expect rows' phone columns to the stripped form to match.

- [ ] **Step 3: Run the rpt unit tests — expect PASS after Step 1**

```bash
uv run dbt test \
  --select "rpt_deanslist__family_contacts,test_type:unit" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization/src/dbt/kipptaf \
  --target dev --defer \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: `PASS` for both unit tests. (Run once before Step 1's SQL edit to see
the phone assertions fail, then after to see them pass.)

- [ ] **Step 4: Build the rpt against prod data, lint**

```bash
uv run dbt build \
  --select rpt_deanslist__family_contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod

cd /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization \
  && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml \
  </dev/null
```

Expected: builds; tests pass (the `ParentLastName` warn is still expected).
Query the dev-built view and confirm `HomePhone`/`WorkPhone`/`CellPhone` contain
only `[0-9x]` (no `+`, parens, spaces).

- [ ] **Step 5: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization \
  add src/dbt/kipptaf/models/extracts/deanslist/rpt_deanslist__family_contacts.sql \
  src/dbt/kipptaf/models/extracts/deanslist/properties/rpt_deanslist__family_contacts.yml

git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-phone-normalization \
  commit -m "feat(deanslist): format phones to numbers-or-x from E.164 canonical

Refs #4498"
```

---

## Post-implementation

- Push and open a PR (`.github/pull_request_template.md` body, `Closes #4498`).
- The `int_finalsite__student_contacts` change is value-only → kipptaf dbt Cloud
  CI compiles unchanged; the `rpt_deanslist__family_contacts` change is
  CI-exercised. After CI passes, fetch warnings
  (`get_job_run_error(warning_only=true)`) — the `ParentLastName` warn is
  expected.
- Post-merge, district `int_finalsite__student_contacts` tables rebuild via
  Dagster automation; normalized phones then flow to all consumers.

## Self-review

- **Spec coverage:** E.164 macro (Task 1 Step 1), applied at
  `int_finalsite__student_contacts` on the four phone columns (Task 1 Step 2),
  never-NULL passthrough (macro `coalesce`), DeansList `[0-9x]` strip (Task 2
  Step 1), unit tests both layers, value-only rollout — all covered.
- **No placeholders:** macro and both model edits are complete, BQ-verified SQL.
- **Type consistency:** `clean_phone` returns STRING; phone columns stay STRING;
  DeansList outputs STRING. Macro arg name is `column` throughout.
