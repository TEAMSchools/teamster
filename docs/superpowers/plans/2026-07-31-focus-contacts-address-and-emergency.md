# Focus CONTACTS Address Resolution and Emergency Contacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve each Focus `CONTACTS` guardian address from that guardian's
own Finalsite household linkage instead of an arbitrary array position, then
append emergency-contact rows from the `emrg_1..4` custom-field slots.

**Architecture:** A new `finalsite` package intermediate,
`int_finalsite__contact_address_of_record`, applies the address-resolution rule
at contact grain. `int_finalsite__student_address_of_record` refactors onto it
so both Focus feeds share one rule. kipptaf reaches the new model through a
`union_relations` wrapper over four regional sources, and `rpt_focus__contacts`
joins it. A second, stacked branch then unions emergency-slot rows into
`rpt_focus__contacts` and re-derives `sort_order` over the combined set.

**Tech Stack:** dbt (BigQuery), `dbt_utils`, dbt unit tests, trunk (sqlfluff /
yamllint / markdownlint), `gh` CLI.

**Design spec:**
`docs/superpowers/specs/2026-07-31-focus-contacts-address-and-emergency-design.md`
— read it before Task 1. Every measured figure quoted below comes from it.

## Global Constraints

- Worktree for branch 1:
  `/workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record`
  (branch `cbini/fix/claude-focus-contacts-address-of-record`, already created).
  All Read / Edit / Write use paths under that worktree. All git commands use
  `git -C <worktree>`.
- Run `uv run dbt deps --project-dir <worktree>/src/dbt/kippmiami` once before
  the first dbt command — a fresh worktree has no `dbt_packages/`.
- Every dbt invocation is `uv run dbt`, never bare `dbt`.
- `--state` paths are absolute and point at the MAIN repo
  (`/workspaces/teamster/src/dbt/kippmiami/target/prod`), never the worktree.
- SQL follows `src/dbt/CLAUDE.md`: max one level of function nesting, no
  `ORDER BY`, no `QUALIFY`, no subqueries against tables or CTEs, no lateral
  column aliases, no `GROUP BY ALL`, no pass-through import CTEs, trailing
  commas in `SELECT`, single-quoted strings, 88-char lines, ST06 column ordering
  (plain refs by table in join order, then constants, simple functions, nested
  functions, logicals, `CASE`, window functions).
- Every new or modified model needs a `description:` on the model and on every
  column, plus a uniqueness test.
- PII columns (`address_1`, `address_2`, `city`, `zip`, phone, email, names)
  carry `config: meta: contains_pii: true`.
- Never emit real address, name, phone, or email values into a commit message,
  PR body, or issue comment. Validation output stays local.
- Lint with
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <paths> </dev/null`,
  run with cwd set to the worktree.
- Address resolution rule, verbatim from the spec: candidates are households
  where `address_1 is not null`; identity is `address_1`, `address_2`, `city`,
  `state`, `zip` compared case- and punctuation-insensitively with ZIP truncated
  to 5; a contact resolves only when exactly one distinct address remains; the
  projected values are the RAW text from the lowest-`household_id` row.

---

## Branch 1 — #4651

### Task 1: `int_finalsite__contact_address_of_record`

**Files:**

- Create:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql`
- Create:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_address_of_record.yml`

**Interfaces:**

- Consumes: `int_finalsite__contacts__households` (`finalsite_enrollment_id`,
  `household_id`, `address_1`, `address_2`, `city`, `state`, `zip`, `country`,
  `is_complete_address`) and `stg_finalsite__contacts`
  (`finalsite_enrollment_id`, used as the contact spine).
- Produces: one row per `finalsite_enrollment_id` with columns
  `finalsite_enrollment_id` (string), `address_1`, `address_2`, `city`, `state`,
  `zip`, `country` (string), `is_complete_address` (boolean), `candidate_count`
  (int64), `resolution_status` (string, one of `resolved` / `ambiguous` /
  `no_street`). Tasks 2, 3, and 4 all depend on these exact names.

- [ ] **Step 1: Write the model SQL**

Create
`src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql`:

```sql
with
    households_stripped as (
        -- Any household carrying a street line is a candidate. Completeness is
        -- deliberately NOT a gate: an incomplete address is visibly wrong in
        -- Focus and can be corrected there, whereas withholding it is silent.
        -- Households with no street at all ARE excluded — Miami holds 94 such
        -- city/state/ZIP fragments, and each would otherwise count as its own
        -- candidate and manufacture ambiguity that is not real.
        select
            finalsite_enrollment_id,
            household_id,
            address_1,
            address_2,
            city,
            state,
            zip,
            country,
            is_complete_address,

            upper(city) as city_key,
            left(zip, 5) as zip_key,

            regexp_replace(address_1, r'[^A-Za-z0-9]', '') as address_1_stripped,
            regexp_replace(address_2, r'[^A-Za-z0-9]', '') as address_2_stripped,
        from {{ ref("int_finalsite__contacts__households") }}
        where address_1 is not null
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    candidate_households as (
        select
            finalsite_enrollment_id,
            household_id,
            address_1,
            address_2,
            city,
            state,
            zip,
            country,
            is_complete_address,
            city_key,
            zip_key,

            upper(address_1_stripped) as address_1_key,
            upper(address_2_stripped) as address_2_key,
        from households_stripped
    ),

    address_candidates as (
        -- One row per (contact, distinct address). The key normalizes case and
        -- punctuation so `123 Main St.` and `123 MAIN ST` are one address, and
        -- truncates ZIP+4 to five digits. Normalization is for GROUPING only —
        -- the projected address is the raw text from the lowest-household_id
        -- row, so Focus receives properly formatted values. country and
        -- is_complete_address are not part of the identity, so they come from
        -- that same canonical row rather than being aggregated across rows,
        -- which would blend values from different households.
        {{
            dbt_utils.deduplicate(
                relation="candidate_households",
                partition_by=(
                    "finalsite_enrollment_id, address_1_key, address_2_key,"
                    " city_key, state, zip_key"
                ),
                order_by="household_id asc",
            )
        }}
    ),

    candidate_counts as (
        select finalsite_enrollment_id, count(*) as candidate_count,
        from address_candidates
        group by finalsite_enrollment_id
    ),

    resolved_candidates as (
        -- Only a contact with exactly one distinct address gets an address at
        -- all. Two or more means Finalsite does not say which one to use, and
        -- the feed is import-once, so a guess would be permanent.
        select
            a.finalsite_enrollment_id,
            a.address_1,
            a.address_2,
            a.city,
            a.state,
            a.zip,
            a.country,
            a.is_complete_address,
        from address_candidates as a
        inner join
            candidate_counts as c
            on a.finalsite_enrollment_id = c.finalsite_enrollment_id
        where c.candidate_count = 1
    ),

    counted as (
        -- Spined on the full contact list so a contact with no street-bearing
        -- household still gets a row, with candidate_count 0.
        select
            c.finalsite_enrollment_id,

            r.address_1,
            r.address_2,
            r.city,
            r.state,
            r.zip,
            r.country,
            r.is_complete_address,
            r.finalsite_enrollment_id as resolved_contact_id,

            coalesce(cc.candidate_count, 0) as candidate_count,
        from {{ ref("stg_finalsite__contacts") }} as c
        left join
            candidate_counts as cc
            on c.finalsite_enrollment_id = cc.finalsite_enrollment_id
        left join
            resolved_candidates as r
            on c.finalsite_enrollment_id = r.finalsite_enrollment_id
    )

select
    finalsite_enrollment_id,
    address_1,
    address_2,
    city,
    state,
    zip,
    country,
    is_complete_address,
    candidate_count,

    case
        when resolved_contact_id is not null
        then 'resolved'
        when candidate_count = 0
        then 'no_street'
        else 'ambiguous'
    end as resolution_status,
from counted
```

- [ ] **Step 2: Write the properties file with unit tests**

Create
`src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_address_of_record.yml`:

```yaml
models:
  - name: int_finalsite__contact_address_of_record
    description:
      One row per Finalsite contact — students and adults alike — carrying that
      contact's resolved address, or nulls plus a flag when it cannot be
      resolved. A household is a candidate when it has a street line; an
      incomplete address is deliberately still a candidate, because an
      incomplete address is visibly wrong in a receiving system and can be
      corrected there, whereas withholding it is silent. Households with no
      street at all are excluded, since each would otherwise count as its own
      candidate and manufacture ambiguity. Address identity is `address_1`,
      `address_2`, `city`, `state`, and `zip` compared without regard to case or
      punctuation and with `zip` truncated to five digits, so the same address
      recorded two ways collapses to one candidate while a genuine apartment,
      city, state, or ZIP difference stays distinct. A contact resolves only
      when exactly one distinct address remains; the emitted values are the raw
      text from the lowest `household_id` in that group. SIS-agnostic — no
      enrollment, status, or academic-year scoping.
    data_tests:
      - dbt_utils.expression_is_true:
          arguments:
            expression: |
              (resolution_status = 'resolved' and address_1 is not null)
              or (
                  resolution_status != 'resolved'
                  and address_1 is null
                  and address_2 is null
                  and city is null
                  and state is null
                  and zip is null
              )
          config:
            severity: error
      - dbt_utils.expression_is_true:
          arguments:
            expression: |
              (resolution_status = 'resolved' and candidate_count = 1)
              or (resolution_status = 'no_street' and candidate_count = 0)
              or (resolution_status = 'ambiguous' and candidate_count > 1)
          config:
            severity: error
    columns:
      - name: finalsite_enrollment_id
        data_type: string
        description: Finalsite contact UUID; the grain.
        data_tests:
          - unique:
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: resolution_status
        data_type: string
        description:
          Why this contact does or does not have an address — `resolved`
          (exactly one distinct address), `ambiguous` (several, with nothing in
          Finalsite saying which to use), or `no_street` (no household carries a
          street line).
        data_tests:
          - accepted_values:
              arguments:
                values:
                  - resolved
                  - ambiguous
                  - no_street
              config:
                severity: error
          - not_null:
              config:
                severity: error
      - name: candidate_count
        data_type: int64
        description:
          Number of distinct addresses on this contact's household linkage after
          normalization. One resolves; zero means no household carries a street;
          more than one is ambiguous.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: address_1
        data_type: string
        description:
          Street address line 1 of the resolved address, as raw text; null when
          unresolved.
        config:
          meta:
            contains_pii: true
      - name: address_2
        data_type: string
        description:
          Street address line 2 (apartment or unit) of the resolved address.
          Legitimately null when the household has no unit line, and null
          whenever the address is unresolved.
        config:
          meta:
            contains_pii: true
      - name: city
        data_type: string
        description:
          City of the resolved address; null when unresolved, and possibly null
          on a resolved but incomplete address.
        config:
          meta:
            contains_pii: true
      - name: state
        data_type: string
        description:
          State code of the resolved address, uppercased upstream; null when
          unresolved, and possibly null on a resolved but incomplete address.
      - name: zip
        data_type: string
        description:
          ZIP code of the resolved address; null when unresolved, and possibly
          null on a resolved but incomplete address.
        config:
          meta:
            contains_pii: true
      - name: country
        data_type: string
        description:
          Country of the resolved address as Finalsite stores it. Not part of
          the address identity, so it is carried from the canonical household
          rather than compared.
      - name: is_complete_address
        data_type: boolean
        description:
          Whether the resolved address carries street, city, state, and ZIP. A
          resolved address may be incomplete — this flag is what makes that
          visible to consumers. Null when unresolved.

unit_tests:
  - name: test_contact_address_formatting_duplicates_collapse
    description:
      Two households recording the same address with different punctuation,
      case, and a ZIP+4 collapse to one candidate, so the contact resolves. The
      emitted values are the raw text of the lowest household_id, not the
      normalized key.
    model: int_finalsite__contact_address_of_record
    given:
      - input: ref("stg_finalsite__contacts")
        rows:
          - { finalsite_enrollment_id: con-1 }
      - input: ref("int_finalsite__contacts__households")
        format: sql
        rows: |
          select
            'con-1' as finalsite_enrollment_id,
            'hh-1' as household_id,
            '123 Main St.' as address_1,
            cast(null as string) as address_2,
            'Miami' as city,
            'FL' as state,
            '33101' as zip,
            'US' as country,
            true as is_complete_address
          union all
          select 'con-1', 'hh-2', '123 MAIN ST', null, 'MIAMI', 'FL',
            '33101-4402', 'US', true
    expect:
      rows:
        - {
            finalsite_enrollment_id: con-1,
            address_1: 123 Main St.,
            address_2: null,
            city: Miami,
            state: FL,
            zip: "33101",
            country: US,
            is_complete_address: true,
            candidate_count: 1,
            resolution_status: resolved,
          }

  - name: test_contact_address_real_differences_stay_ambiguous
    description:
      Households sharing a street line but differing by apartment or by city
      stay distinct candidates, so the contact is ambiguous and no address is
      emitted. This is the case an address_1-only key would wrongly collapse.
    model: int_finalsite__contact_address_of_record
    given:
      - input: ref("stg_finalsite__contacts")
        rows:
          - { finalsite_enrollment_id: con-2 }
          - { finalsite_enrollment_id: con-3 }
      - input: ref("int_finalsite__contacts__households")
        format: sql
        rows: |
          select
            'con-2' as finalsite_enrollment_id,
            'hh-3' as household_id,
            '222 Bay St' as address_1,
            'Apt 1' as address_2,
            'Miami' as city,
            'FL' as state,
            '33106' as zip,
            'US' as country,
            true as is_complete_address
          union all
          select 'con-2', 'hh-4', '222 Bay St', 'Apt 2', 'Miami', 'FL', '33106',
            'US', true
          union all
          select 'con-3', 'hh-5', '400 Palm Way', null, 'Miami', 'FL', '33101',
            'US', true
          union all
          select 'con-3', 'hh-6', '400 Palm Way', null, 'Hialeah', 'FL', '33012',
            'US', true
    expect:
      rows:
        - {
            finalsite_enrollment_id: con-2,
            address_1: null,
            address_2: null,
            city: null,
            state: null,
            zip: null,
            country: null,
            is_complete_address: null,
            candidate_count: 2,
            resolution_status: ambiguous,
          }
        - {
            finalsite_enrollment_id: con-3,
            address_1: null,
            address_2: null,
            city: null,
            state: null,
            zip: null,
            country: null,
            is_complete_address: null,
            candidate_count: 2,
            resolution_status: ambiguous,
          }

  - name: test_contact_address_incomplete_resolves_and_fragments_excluded
    description:
      A household with a street but no ZIP still resolves, flagged incomplete —
      completeness is not a gate. A household carrying only city and ZIP with no
      street is not a candidate, so a contact holding only fragments reports
      no_street. A contact with no household rows at all also reports no_street.
    model: int_finalsite__contact_address_of_record
    given:
      - input: ref("stg_finalsite__contacts")
        rows:
          - { finalsite_enrollment_id: con-4 }
          - { finalsite_enrollment_id: con-5 }
          - { finalsite_enrollment_id: con-6 }
      - input: ref("int_finalsite__contacts__households")
        format: sql
        rows: |
          select
            'con-4' as finalsite_enrollment_id,
            'hh-7' as household_id,
            '9 Nowhere Ln' as address_1,
            cast(null as string) as address_2,
            'Miami' as city,
            'FL' as state,
            cast(null as string) as zip,
            'US' as country,
            false as is_complete_address
          union all
          select 'con-4', 'hh-8', null, null, 'Miami', 'FL', '33101', 'US', false
          union all
          select 'con-5', 'hh-9', null, null, 'Miami', 'FL', '33108', 'US', false
    expect:
      rows:
        - {
            finalsite_enrollment_id: con-4,
            address_1: 9 Nowhere Ln,
            address_2: null,
            city: Miami,
            state: FL,
            zip: null,
            country: US,
            is_complete_address: false,
            candidate_count: 1,
            resolution_status: resolved,
          }
        - {
            finalsite_enrollment_id: con-5,
            address_1: null,
            address_2: null,
            city: null,
            state: null,
            zip: null,
            country: null,
            is_complete_address: null,
            candidate_count: 0,
            resolution_status: no_street,
          }
        - {
            finalsite_enrollment_id: con-6,
            address_1: null,
            address_2: null,
            city: null,
            state: null,
            zip: null,
            country: null,
            is_complete_address: null,
            candidate_count: 0,
            resolution_status: no_street,
          }
```

- [ ] **Step 3: Install packages in the worktree**

Run:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/kippmiami
```

Expected: packages installed, no error. Skip if already run.

- [ ] **Step 4: Run the unit tests**

Run:

```bash
uv run dbt test \
  --select int_finalsite__contact_address_of_record,test_type:unit \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/kippmiami \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: 3 unit tests PASS. If
`test_contact_address_formatting_duplicates_collapse` returns the `hh-2` values
instead of `hh-1`, the `order_by` in the deduplicate call is wrong. If `con-4`
comes back `no_street`, the `where address_1 is not null` filter was written as
`where is_complete_address`.

- [ ] **Step 5: Build the model against dev and check the counts**

Run:

```bash
uv run dbt build \
  --select int_finalsite__contact_address_of_record \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/kippmiami \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: model builds; `unique`, `not_null`, `accepted_values`, and both
`expression_is_true` tests pass.

Then query the dev table (BigQuery MCP, schema `zz_cbini_kippmiami_finalsite`)
and confirm against the spec:

```sql
select resolution_status, count(*) as n
from `teamster-332318.zz_cbini_kippmiami_finalsite.int_finalsite__contact_address_of_record`
group by 1
order by 1
```

Expected: one row per contact in `stg_finalsite__contacts` — 7,522 for Miami —
and the guardian-scoped feed slice resolving to 2,081 rows in Task 4. A total
that differs from `select count(*) from stg_finalsite__contacts` means the spine
join fanned out; compare against that query rather than a hardcoded number,
since Finalsite data moves.

- [ ] **Step 6: Lint**

Run:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_address_of_record.yml \
  </dev/null
```

Expected: no issues. Fix any sqlfluff ST06 ordering or line-length findings and
re-run.

- [ ] **Step 7: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record add \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_address_of_record.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record commit -m "feat(dbt): resolve a Finalsite contact address of record at contact grain

Refs #4651

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Refactor `int_finalsite__student_address_of_record`

**Files:**

- Modify:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql`
  (full rewrite of the CTE chain)
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml`
  (model description, one `expression_is_true` test, three column descriptions,
  one new column, all four unit tests)

**Interfaces:**

- Consumes: `int_finalsite__contact_address_of_record` from Task 1 —
  `finalsite_enrollment_id`, `candidate_count`, `address_1`, `address_2`,
  `city`, `state`, `zip`, `country`, `is_complete_address`.
- Produces: the same column set as today plus `is_complete_address` (boolean).
  `address_source`, `resolution_status`, `student_candidate_count`,
  `primary_contact_candidate_count`, and `primary_contact_phone` keep their
  existing names and meanings. `rpt_focus__addresses` reads `address_source`,
  the five address fields, and `primary_contact_phone` and must keep working
  unchanged.

- [ ] **Step 1: Update the existing unit tests to fail against the new rule**

The four unit tests in
`src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml`
currently mock `ref('int_finalsite__contacts__households')`. After the refactor
the model no longer reads that relation, so every `given` block must mock
`ref('int_finalsite__contact_address_of_record')` instead. Dedup behavior is no
longer this model's responsibility — Task 1 covers it — so these tests shrink to
the pick logic.

Replace the entire `unit_tests:` block with:

```yaml
unit_tests:
  - name: test_address_of_record_student_linkage_decisive
    description:
      A student whose own linkage resolves takes their own address, even though
      their primary contact's linkage is ambiguous.
    model: int_finalsite__student_address_of_record
    given:
      - input: ref("stg_finalsite__contact_relationships")
        rows:
          - { finalsite_enrollment_id: stu-1, rel_id: par-1, is_primary: true }
          - { finalsite_enrollment_id: par-1, rel_id: stu-1, is_primary: null }
      - input: ref("int_finalsite__contact_address_of_record")
        format: sql
        rows: |
          select
            'stu-1' as finalsite_enrollment_id,
            '123 Main St' as address_1,
            cast(null as string) as address_2,
            'Miami' as city,
            'FL' as state,
            '33101' as zip,
            'US' as country,
            true as is_complete_address,
            1 as candidate_count,
            'resolved' as resolution_status
          union all
          select 'par-1', null, null, null, null, null, null, null, 2,
            'ambiguous'
      - input: ref("stg_finalsite__contacts")
        rows:
          - { finalsite_enrollment_id: stu-1, phone_1_number: null }
          - { finalsite_enrollment_id: par-1, phone_1_number: "+13055550101" }
    expect:
      rows:
        - {
            finalsite_enrollment_id: stu-1,
            student_candidate_count: 1,
            primary_contact_candidate_count: 2,
            address_source: student_household,
            address_1: 123 Main St,
            address_2: null,
            city: Miami,
            state: FL,
            zip: "33101",
            country: US,
            is_complete_address: true,
            primary_contact_phone: "+13055550101",
            resolution_status: student_household,
          }

  - name: test_address_of_record_primary_contact_fallback
    description:
      A student whose own linkage is ambiguous falls through to their primary
      contact, whose linkage resolves.
    model: int_finalsite__student_address_of_record
    given:
      - input: ref("stg_finalsite__contact_relationships")
        rows:
          - { finalsite_enrollment_id: stu-2, rel_id: par-2, is_primary: true }
      - input: ref("int_finalsite__contact_address_of_record")
        format: sql
        rows: |
          select
            'stu-2' as finalsite_enrollment_id,
            cast(null as string) as address_1,
            cast(null as string) as address_2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zip,
            cast(null as string) as country,
            cast(null as bool) as is_complete_address,
            2 as candidate_count,
            'ambiguous' as resolution_status
          union all
          select 'par-2', '111 Palm Way', null, 'Miami', 'FL', '33103', 'US',
            true, 1, 'resolved'
      - input: ref("stg_finalsite__contacts")
        rows:
          - { finalsite_enrollment_id: stu-2, phone_1_number: null }
          - { finalsite_enrollment_id: par-2, phone_1_number: "+13055550102" }
    expect:
      rows:
        - {
            finalsite_enrollment_id: stu-2,
            student_candidate_count: 2,
            primary_contact_candidate_count: 1,
            address_source: primary_contact_household,
            address_1: 111 Palm Way,
            address_2: null,
            city: Miami,
            state: FL,
            zip: "33103",
            country: US,
            is_complete_address: true,
            primary_contact_phone: "+13055550102",
            resolution_status: primary_contact_household,
          }

  - name: test_address_of_record_both_sides_ambiguous
    description:
      When neither the student nor their primary contact resolves, no address is
      emitted and the row is flagged ambiguous.
    model: int_finalsite__student_address_of_record
    given:
      - input: ref("stg_finalsite__contact_relationships")
        rows:
          - { finalsite_enrollment_id: stu-3, rel_id: par-3, is_primary: true }
      - input: ref("int_finalsite__contact_address_of_record")
        format: sql
        rows: |
          select
            'stu-3' as finalsite_enrollment_id,
            cast(null as string) as address_1,
            cast(null as string) as address_2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zip,
            cast(null as string) as country,
            cast(null as bool) as is_complete_address,
            2 as candidate_count,
            'ambiguous' as resolution_status
          union all
          select 'par-3', null, null, null, null, null, null, null, 3,
            'ambiguous'
      - input: ref("stg_finalsite__contacts")
        rows:
          - { finalsite_enrollment_id: stu-3, phone_1_number: null }
          - { finalsite_enrollment_id: par-3, phone_1_number: "+13055550103" }
    expect:
      rows:
        - {
            finalsite_enrollment_id: stu-3,
            student_candidate_count: 2,
            primary_contact_candidate_count: 3,
            address_source: null,
            address_1: null,
            address_2: null,
            city: null,
            state: null,
            zip: null,
            country: null,
            is_complete_address: null,
            primary_contact_phone: "+13055550103",
            resolution_status: ambiguous,
          }

  - name: test_address_of_record_incomplete_address_is_emitted
    description:
      A student absent from the contact-address model entirely counts as zero
      candidates and falls through to their primary contact. A resolved but
      incomplete address is emitted rather than withheld, carrying
      is_complete_address false — the behavior change this refactor introduces.
    model: int_finalsite__student_address_of_record
    given:
      - input: ref("stg_finalsite__contact_relationships")
        rows:
          - { finalsite_enrollment_id: stu-4, rel_id: par-4, is_primary: true }
          - { finalsite_enrollment_id: stu-5, rel_id: par-5, is_primary: true }
      - input: ref("int_finalsite__contact_address_of_record")
        format: sql
        rows: |
          select
            'par-4' as finalsite_enrollment_id,
            '555 Coral Dr' as address_1,
            'Unit 7' as address_2,
            'Miami' as city,
            'FL' as state,
            '33104' as zip,
            'US' as country,
            true as is_complete_address,
            1 as candidate_count,
            'resolved' as resolution_status
          union all
          select 'stu-5', '666 Reef Ln', null, 'Miami', 'FL', null, 'US', false,
            1, 'resolved'
          union all
          select 'par-5', null, null, null, null, null, null, null, 0,
            'no_street'
      - input: ref("stg_finalsite__contacts")
        rows:
          - { finalsite_enrollment_id: par-4, phone_1_number: "+13055550104" }
          - { finalsite_enrollment_id: par-5, phone_1_number: "+13055550105" }
    expect:
      rows:
        - {
            finalsite_enrollment_id: stu-4,
            student_candidate_count: 0,
            primary_contact_candidate_count: 1,
            address_source: primary_contact_household,
            address_1: 555 Coral Dr,
            address_2: Unit 7,
            city: Miami,
            state: FL,
            zip: "33104",
            country: US,
            is_complete_address: true,
            primary_contact_phone: "+13055550104",
            resolution_status: primary_contact_household,
          }
        - {
            finalsite_enrollment_id: stu-5,
            student_candidate_count: 1,
            primary_contact_candidate_count: 0,
            address_source: student_household,
            address_1: 666 Reef Ln,
            address_2: null,
            city: Miami,
            state: FL,
            zip: null,
            country: US,
            is_complete_address: false,
            primary_contact_phone: "+13055550105",
            resolution_status: student_household,
          }
```

- [ ] **Step 2: Run the unit tests to verify they fail**

Run:

```bash
uv run dbt test \
  --select int_finalsite__student_address_of_record,test_type:unit \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/kippmiami \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: FAIL. The model still reads `int_finalsite__contacts__households`, so
the mocked `int_finalsite__contact_address_of_record` input is unused and the
tests produce empty or wrong output. A parse error naming an unused `given`
input is also an acceptable failure here.

- [ ] **Step 3: Rewrite the model SQL**

Replace the whole body of
`src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql`
with:

```sql
with
    student_primary_contacts as (
        -- One row per student record. `relationships.primary` is a per-record
        -- singleton that is true or NULL (never false), and only child/student
        -- records carry it, so a bare `where is_primary` selects exactly the
        -- student rows and `rel_id` is that student's Parent 1. A second primary
        -- on one student would surface as a duplicate and fail this model's
        -- uniqueness test, which is the intended loud failure. No SIS scoping —
        -- receivers filter to enrolled students downstream.
        select finalsite_enrollment_id, rel_id as primary_contact_id,
        from {{ ref("stg_finalsite__contact_relationships") }}
        where is_primary
    ),

    counted as (
        -- Candidate counting and address identity live in
        -- int_finalsite__contact_address_of_record, so both Focus feeds resolve
        -- an address by one rule. A contact absent from that model has no
        -- household rows at all, which counts as zero candidates.
        select
            spc.finalsite_enrollment_id,
            spc.primary_contact_id,

            coalesce(sa.candidate_count, 0) as student_candidate_count,
            coalesce(pa.candidate_count, 0) as primary_contact_candidate_count,
        from student_primary_contacts as spc
        left join
            {{ ref("int_finalsite__contact_address_of_record") }} as sa
            on spc.finalsite_enrollment_id = sa.finalsite_enrollment_id
        left join
            {{ ref("int_finalsite__contact_address_of_record") }} as pa
            on spc.primary_contact_id = pa.finalsite_enrollment_id
    ),

    sourced as (
        -- The student's household linkage is a subset of their primary
        -- contact's and is the disambiguating signal, so it is tried first.
        -- Parents carry more household rows than students, so anchoring on the
        -- parent unconditionally would move the pick onto the record with more
        -- competing addresses.
        select
            finalsite_enrollment_id,
            primary_contact_id,
            student_candidate_count,
            primary_contact_candidate_count,

            case
                when student_candidate_count = 1
                then 'student_household'
                when primary_contact_candidate_count = 1
                then 'primary_contact_household'
            end as address_source,
            case
                when student_candidate_count = 1
                then finalsite_enrollment_id
                when primary_contact_candidate_count = 1
                then primary_contact_id
            end as address_contact_id,
        from counted
    )

select
    s.finalsite_enrollment_id,
    s.student_candidate_count,
    s.primary_contact_candidate_count,
    s.address_source,

    a.address_1,
    a.address_2,
    a.city,
    a.state,
    a.zip,
    a.country,
    a.is_complete_address,

    pc.phone_1_number as primary_contact_phone,

    coalesce(s.address_source, 'ambiguous') as resolution_status,
from sourced as s
-- address_contact_id is only ever set to a contact whose candidate_count is
-- exactly 1, so this join cannot fan out; when it is null (an unresolved
-- address) nothing matches and the address fields stay null.
left join
    {{ ref("int_finalsite__contact_address_of_record") }} as a
    on s.address_contact_id = a.finalsite_enrollment_id
left join
    {{ ref("stg_finalsite__contacts") }} as pc
    on s.primary_contact_id = pc.finalsite_enrollment_id
```

- [ ] **Step 4: Update the model description, the completeness test, and column
      docs**

In the same properties file, make these four edits.

Replace the model `description:` with:

```yaml
description:
  One row per Finalsite student record — the student's resolved address of
  record, or a flag when it cannot be resolved. Grain is
  `finalsite_enrollment_id` for contacts that carry a `primary` relationship,
  which is how a student record is identified without reaching for a
  SIS-specific field; contacts with no primary link are absent entirely.
  Resolution takes the student's own household linkage when
  `int_finalsite__contact_address_of_record` resolves it to exactly one address,
  falls back to their primary contact's when it does, and otherwise emits no
  address. Address identity and the candidate rule live in that model, so this
  feed and the contact feed resolve addresses the same way. An emitted address
  is not guaranteed complete — check `is_complete_address`. SIS-agnostic — no
  enrollment, status, or academic-year scoping; receivers filter downstream.
```

Replace the model-level `dbt_utils.expression_is_true` `expression:` with:

```yaml
expression: |
  (address_source is not null and address_1 is not null)
  or (
      address_source is null
      and address_1 is null
      and address_2 is null
      and city is null
      and state is null
      and zip is null
  )
```

Replace the `address_source` description with:

```yaml
description:
  Which record supplied the address — `student_household` or
  `primary_contact_household`. Null when no address was resolved; a non-null
  value guarantees `address_1` is populated, but not that the rest of the
  address is.
```

Replace the `student_candidate_count` and `primary_contact_candidate_count`
descriptions with:

```yaml
- name: student_candidate_count
  data_type: int64
  description:
    Number of distinct addresses on the student's own household linkage, from
    `int_finalsite__contact_address_of_record`. One means the student's own
    records decide the address; anything else means the pick falls through to
    the primary contact. Zero means no household linked to the student carries a
    street line.
- name: primary_contact_candidate_count
  data_type: int64
  description:
    Number of distinct addresses on the primary contact's household linkage.
    Used only when the student's own count is not one.
```

Add this column entry immediately after the `country` column:

```yaml
- name: is_complete_address
  data_type: boolean
  description:
    Whether the resolved address carries street, city, state, and ZIP. An
    incomplete address is emitted rather than withheld, so consumers that
    require a mailable address must check this flag. Null when unresolved.
```

- [ ] **Step 5: Run the unit tests to verify they pass**

Run the same command as Step 2.

Expected: 4 unit tests PASS.

- [ ] **Step 6: Build and prove parity against prod**

Run:

```bash
uv run dbt build \
  --select int_finalsite__contact_address_of_record int_finalsite__student_address_of_record \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/kippmiami \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: both build, all data tests pass.

Then run this parity query (BigQuery MCP) and read it carefully:

```sql
with
    dev as (
        select
            finalsite_enrollment_id,
            format(
                '%T|%T|%T|%T|%T|%T', address_1, address_2, city, state, zip,
                address_source
            ) as tup
        from `teamster-332318.zz_cbini_kippmiami_finalsite.int_finalsite__student_address_of_record`
    ),
    prd as (
        select
            finalsite_enrollment_id,
            format(
                '%T|%T|%T|%T|%T|%T', address_1, address_2, city, state, zip,
                address_source
            ) as tup
        from `teamster-332318.kippmiami_finalsite.int_finalsite__student_address_of_record`
    )
select
    countif(p.finalsite_enrollment_id is null) as only_in_dev,
    countif(d.finalsite_enrollment_id is null) as only_in_prod,
    countif(d.tup != p.tup) as changed_rows,
    countif(d.tup != p.tup and p.tup like '%|NULL') as changed_from_unresolved,
    count(*) as total
from dev as d
full join prd as p using (finalsite_enrollment_id)
```

Expected: `only_in_dev` 0, `only_in_prod` 0, `changed_rows` 6, and all 6 of
those `changed_from_unresolved` — the students the normalization newly resolves.
Any row that changed from one resolved address to a different one is a refactor
bug; stop and diagnose before continuing.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml \
  </dev/null
```

Then:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record add \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record commit -m "refactor(dbt): resolve the student address of record from the shared contact model

Refs #4651

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Expose the new model to kipptaf

**Files:**

- Modify: `src/dbt/kipptaf/models/finalsite/sources-kippmiami.yml`
- Modify: `src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml`
- Modify: `src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml`
- Modify: `src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml`
- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__contact_address_of_record.sql`
- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__contact_address_of_record.yml`

**Interfaces:**

- Consumes: the four regional `int_finalsite__contact_address_of_record` sources
  created in Task 1.
- Produces: kipptaf-level `int_finalsite__contact_address_of_record` with every
  package column plus `_dbt_source_relation` and `_dbt_source_project`. Task 4
  joins it on `finalsite_enrollment_id`.

- [ ] **Step 1: Add the source entry to all four regional source files**

Append this block to the `tables:` list in each of the four files, changing
`kipp<region>` to match the file. For
`src/dbt/kipptaf/models/finalsite/sources-kippmiami.yml`:

```yaml
- name: int_finalsite__contact_address_of_record
  config:
    meta:
      dagster:
        group: finalsite
        asset_key:
          - kippmiami
          - finalsite
          - int_finalsite__contact_address_of_record
```

Repeat with `kippnewark`, `kippcamden`, and `kipppaterson` as the first
`asset_key` element in the respective files. Do not touch the `schema:`
expression — the `dev` / `staging` / prod branch is already present on all four.

- [ ] **Step 2: Write the union wrapper**

Create
`src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__contact_address_of_record.sql`:

```sql
-- All four regions are unioned here, matching
-- int_finalsite__student_address_of_record. Focus is the Miami consumer and the
-- NJ regions carry no Focus student id, so the `rpt_focus__*` filter on
-- `focus_student_id_prefixed` keeps their rows out of the Focus feeds.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippcamden_finalsite",
                        "int_finalsite__contact_address_of_record",
                    ),
                    source(
                        "kippmiami_finalsite",
                        "int_finalsite__contact_address_of_record",
                    ),
                    source(
                        "kippnewark_finalsite",
                        "int_finalsite__contact_address_of_record",
                    ),
                    source(
                        "kipppaterson_finalsite",
                        "int_finalsite__contact_address_of_record",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

- [ ] **Step 3: Write the wrapper properties file**

Create
`src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__contact_address_of_record.yml`:

```yaml
models:
  - name: int_finalsite__contact_address_of_record
    description:
      Network-wide union of the per-region Finalsite
      `int_finalsite__contact_address_of_record` models — one row per Finalsite
      contact with its resolved address, or a `resolution_status` explaining why
      it has none. Includes all four regions; Focus is the Miami consumer and
      the NJ regions carry no Focus student id, so the `rpt_focus__*` filter on
      `focus_student_id_prefixed` keeps their rows out of the Focus feeds.
      Column documentation lives on the package model. Carries
      `_dbt_source_relation` and the derived `_dbt_source_project`.
    config:
      meta:
        contains_pii: true
    columns:
      - name: finalsite_enrollment_id
        data_type: string
        description: Finalsite contact UUID; the grain.
        data_tests:
          - unique
          - not_null
```

- [ ] **Step 4: Verify the wrapper parses and resolves its columns**

Run:

```bash
uv run dbt compile \
  --select int_finalsite__contact_address_of_record \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/kipptaf \
  --target staging
```

Expected: compiles. Read
`<worktree>/src/dbt/kipptaf/target/compiled/kipptaf/models/finalsite/intermediate/int_finalsite__contact_address_of_record.sql`
and confirm the column list expanded — an EMPTY expansion still compiles clean
and means the `zz_stg_*` relations do not yet hold the model. That is expected
at this point and is what Task 5 fixes; re-read this file after Task 5.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/finalsite/sources-kippmiami.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml \
  src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__contact_address_of_record.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__contact_address_of_record.yml \
  </dev/null
```

Then:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record add \
  src/dbt/kipptaf/models/finalsite/sources-kippmiami.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml \
  src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__contact_address_of_record.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__contact_address_of_record.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record commit -m "feat(dbt): union the Finalsite contact address of record into kipptaf

Refs #4651

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Join the resolved address into `rpt_focus__contacts`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql:21-25,64-77`
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`
  (five column descriptions, the model description, and the unit test's
  `stg_finalsite__contacts` fixture)

**Interfaces:**

- Consumes: kipptaf `int_finalsite__contact_address_of_record` from Task 3.
- Produces: no contract change. The 50-column `CONTACTS_LAYOUT` output is
  unchanged in name, order, and type; only the values behind `address`,
  `address2`, `city`, `state`, and `zipcode` move.

- [ ] **Step 1: Change the address projection and add the join**

In `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql`, replace
lines 21-25:

```sql
    g.address_1 as address,
    g.address_2 as address2,
    g.city,
    g.state,
    g.zip as zipcode,
```

with:

```sql
    aor.address_1 as address,
    aor.address_2 as address2,
    aor.city,
    aor.state,
    aor.zip as zipcode,
```

Then add this join immediately after the `int_finalsite__contact_id_attributes`
join and before the second `stg_finalsite__contacts` join:

```sql
-- the guardian's own household linkage decides their address; array position
-- does not identify Finalsite's primary household. Unresolved keeps the row and
-- nulls the address — the feed is import-once, so a wrong address is permanent,
-- while the name, relationship, email, and phones are still worth sending.
left join
    {{ ref("int_finalsite__contact_address_of_record") }} as aor
    on rel.rel_id = aor.finalsite_enrollment_id
```

- [ ] **Step 2: Update the five address column descriptions**

In `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`,
replace the five address column descriptions:

```yaml
- name: address
  data_type: string
  description:
    Line 1 of the guardian's resolved address from
    `int_finalsite__contact_address_of_record`. Null when the guardian's
    household linkage does not resolve to exactly one address; the row is still
    sent.
- name: address2
  data_type: string
  description:
    Line 2 (apartment or unit) of the guardian's resolved address. Legitimately
    null when the household has no unit line, and null whenever the address is
    unresolved.
- name: city
  data_type: string
  description:
    City of the guardian's resolved address. Null when unresolved, and possibly
    null on a resolved but incomplete address.
- name: state
  data_type: string
  description:
    State of the guardian's resolved address. Null when unresolved, and possibly
    null on a resolved but incomplete address.
- name: zipcode
  data_type: string
  description:
    ZIP code of the guardian's resolved address. Null when unresolved, and
    possibly null on a resolved but incomplete address.
```

- [ ] **Step 3: Update the model description**

Replace the sentence `Phone slots \`CONTACT1__\` and \`CONTACT2__\` map the
guardian's two
phones;`... through the end of that sentence, and insert an address sentence. The model`description:`
becomes:

```yaml
description:
  One row per (student, guardian) reshaped into the Focus `CONTACTS` SFTP
  template layout. Fans out guardian contact rows from
  `stg_finalsite__contact_relationships` (adult relationship types — parent,
  guardian, grandparent, stepparent, relative, aunt/uncle) inner-joined to
  `stg_finalsite__contacts` for guardian attributes, gated to in-scope students
  via `int_finalsite__enrollment_lifecycle`. The student's Focus id
  (`student_id`) is inner-joined from `int_finalsite__contact_id_attributes`,
  excluding students without a minted Focus id. A second join to
  `stg_finalsite__contacts` on the student's own `finalsite_enrollment_id`
  restricts the feed to guardians of students whose own `status` is `enrolled` —
  the guardian's own status is not considered. The address comes from
  `int_finalsite__contact_address_of_record`, resolved from the guardian's own
  household linkage; a guardian whose linkage does not resolve keeps their row
  and gets a null address. Produces 50 columns in `CONTACTS_LAYOUT` order.
  `SORT_ORDER` ranks guardians per student by `is_primary desc` so the primary
  contact sorts first. Phone slots `CONTACT1_*` and `CONTACT2_*` map the
  guardian's two phones; `CONTACT3` through `CONTACT7` are always null. Focus
  column header casing is applied at transport time via
  `file_config.format.header_replacements`; dbt column names remain lowercase
  snake_case.
```

- [ ] **Step 4: Update the unit test fixtures**

The unit test's `stg_finalsite__contacts` rows currently supply the guardian
addresses. Remove `address_1`, `address_2`, `city`, `state`, and `zip` from the
three guardian rows (`enr-grd-pri`, `enr-grd-sec`, `enr-grd-003`) so they carry
only names, email, and phones, and add a new mocked input.

Add this `given` input after the `int_finalsite__contact_id_attributes` block:

```yaml
- input: ref("int_finalsite__contact_address_of_record")
  format: sql
  rows: |
    select
      'enr-grd-pri' as finalsite_enrollment_id,
      '100 Main St' as address_1,
      cast(null as string) as address_2,
      'Miami' as city,
      'FL' as state,
      '33101' as zip
    union all
    select 'enr-grd-sec', '200 Oak Ave', null, 'Miami', 'FL', '33102'
```

The `expect` rows keep their existing `address` / `address2` / `city` / `state`
/ `zipcode` values — the point of the test is that the layout is unchanged. Note
that `enr-grd-003` is deliberately absent from the new input; that guardian
belongs to a non-enrolled student and is excluded from the feed anyway.

- [ ] **Step 5: Run the whole Focus unit-test directory**

Run:

```bash
uv run dbt test \
  --select "test_type:unit,extracts.focus" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/kipptaf \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: PASS. Run the whole directory, not just this model — sibling Focus
models mock the same refs and a fixture change can break them.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml \
  </dev/null
```

Then:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record add \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record commit -m "fix(dbt): resolve the Focus CONTACT address from the guardian household linkage

Closes #4651

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Seed the staging copies and fix the stale address comment

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql:28-31`

**Interfaces:**

- Consumes: nothing new.
- Produces:
  `zz_stg_kipp{miami,newark,camden,paterson}_finalsite.int_finalsite__contact_address_of_record`
  in BigQuery, which dbt Cloud CI reads to resolve the Task 3 union's column
  list.

- [ ] **Step 1: Correct the now-false completeness comment**

In `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql`, replace
lines 28-31:

```sql
-- an unresolved address is withheld, not exported blank: the feed is
-- import-once with no overwrite path, so a blank or wrong address of record is
-- permanent. address_source is not null guarantees a complete address.
where stu.status = 'enrolled' and aor.address_source is not null
```

with:

```sql
-- an unresolved address is withheld, not exported blank: the feed is
-- import-once with no overwrite path, so a blank or wrong address of record is
-- permanent. address_source is not null guarantees a street line, not a
-- complete address — an incomplete one is exported for Ops to correct in Focus,
-- since a missing field is visible there in a way a wrong pick is not.
where stu.status = 'enrolled' and aor.address_source is not null
```

- [ ] **Step 2: Ask the user to authorize the staging builds**

STOP. These four commands write to shared `zz_stg_*` datasets. Ask the user to
authorize them by name before running:

> "Ready to seed the four `zz_stg_<district>_finalsite` staging copies by
> running
> `dbt build --select int_finalsite__contact_address_of_record --target staging`
> against kippmiami, kippnewark, kippcamden, and kipppaterson. Confirm?"

Wait for their answer. Do not run Step 3 without it.

- [ ] **Step 3: Build the new model into each district's staging schema**

Run once per district, substituting `kippmiami`, `kippnewark`, `kippcamden`,
`kipppaterson`:

```bash
uv run dbt build \
  --select int_finalsite__contact_address_of_record \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/<district> \
  --target staging
```

Expected: four successful builds. `dbt clone` is NOT an option here — the model
is absent from the prod manifest, so a clone skips it silently.

- [ ] **Step 4: Confirm the union now expands**

Re-run the Task 3 Step 4 compile and re-read the compiled SQL. Expected: the
column list is now populated with the package model's columns across all four
regional relations.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql </dev/null
```

Then:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record add \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record commit -m "docs(dbt): correct the ADDRESS feed completeness guarantee

Refs #4651

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Validate branch 1 against prod, update the ops doc, open the PR

**Files:**

- Modify: `docs/reference/finalsite-focus-import.md` (the "Blank addresses and
  nameless contacts are held back" section and the "What the enrollment team
  should watch for" list)

**Interfaces:**

- Consumes: everything from Tasks 1-5.
- Produces: PR against `main` closing #4651.

- [ ] **Step 1: Measure the feed against prod**

Build the extract into dev and compare it to the live prod view:

```bash
uv run dbt build \
  --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record/src/dbt/kipptaf \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Then run this comparison (BigQuery MCP), replacing the dev schema if it differs:

```sql
with
    dev as (
        select
            student_id,
            sort_order,
            format('%T|%T|%T|%T|%T', address, address2, city, state, zipcode)
            as tup
        from `teamster-332318.zz_cbini_kipptaf_extracts.rpt_focus__contacts`
    ),
    prd as (
        select
            student_id,
            sort_order,
            format('%T|%T|%T|%T|%T', address, address2, city, state, zipcode)
            as tup
        from `teamster-332318.kipptaf_extracts.rpt_focus__contacts`
    )
select
    count(*) as total_rows,
    countif(d.student_id is null) as only_in_prod,
    countif(p.student_id is null) as only_in_dev,
    countif(d.tup not like 'NULL|%') as rows_with_address,
    countif(
        d.tup != p.tup and d.tup not like 'NULL|%' and p.tup not like 'NULL|%'
    ) as address_values_changed,
    countif(d.tup not like 'NULL|%' and p.tup like 'NULL|%') as newly_enabled,
    countif(d.tup like 'NULL|%' and p.tup not like 'NULL|%') as newly_withheld
from dev as d
full join prd as p using (student_id, sort_order)
```

Expected, from the spec: `total_rows` 2,601, `only_in_prod` 0, `only_in_dev` 0,
`rows_with_address` 2,081, `address_values_changed` **0**, `newly_enabled` 42,
`newly_withheld` 436. A non-zero `address_values_changed` means an address moved
rather than being withheld — stop and diagnose. Small drift in the totals is
possible if Finalsite data moved since 2026-07-31; a change in
`address_values_changed` is not.

Keep this output local. Do not paste address values anywhere.

- [ ] **Step 2: Update the ops doc**

In `docs/reference/finalsite-focus-import.md`, replace the `- **Contacts**`
bullet in the "Blank addresses and nameless contacts are held back" section
with:

```markdown
- **Contacts** — a contact is sent only once it has a name. A nameless contact
  is skipped and flows once the name is filled in. A guardian's address is
  resolved the same way a student's is, but from the guardian's own households:
  when Finalsite links them to more than one address, the contact is still sent
  with the rest of their details and the address is left blank rather than
  guessed. Guardians are usually linked to more households than their children,
  so this is more common on the contact record than on the student.
```

In the same file, replace this sentence in the "What gets sent" list item for
Addresses and Contacts:

```markdown
- **Addresses and Contacts** — sent only once the student is **enrolled**, Focus
  does not already have the record for that student, **and** the record is
  complete (a full address; a named contact). For Contacts, it's the
  **student's** enrolled status that gates the feed, not the guardian contact's
  own. Blank or incomplete records are held back until populated (see below).
```

with:

```markdown
- **Addresses and Contacts** — sent only once the student is **enrolled**, Focus
  does not already have the record for that student, **and** Finalsite points to
  a single address for them (a named contact, for Contacts). For Contacts, it's
  the **student's** enrolled status that gates the feed, not the guardian
  contact's own. An address Finalsite cannot narrow to one is held back; a
  partial address is now sent rather than held, so it can be spotted and
  corrected in Focus.
```

Add this bullet to the "What the enrollment team should watch for" list, after
the duplicate-households bullet:

```markdown
- **A partial address now imports rather than waiting.** An address missing its
  city, state, or ZIP is sent to Focus so you can see and fix it there, instead
  of the student silently having no address. An address Finalsite cannot narrow
  down to one is still held back — that one cannot be guessed safely.
```

- [ ] **Step 3: Lint the doc and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/reference/finalsite-focus-import.md </dev/null
```

Then:

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record add \
  docs/reference/finalsite-focus-import.md
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record commit -m "docs: describe contact address resolution for the enrollment team

Refs #4651

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 4: Push and open the PR as a draft**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-focus-contacts-address-of-record push -u origin cbini/fix/claude-focus-contacts-address-of-record
```

Open the PR with `mcp__github__create_pull_request`, base `main`, `draft: true`,
body built from `.github/pull_request_template.md`. The body must state the
measured deltas from Step 1, note that editing four `sources-kipp*.yml` files
fans `state:modified+` across every kipptaf model reading finalsite, and record
that the four `zz_stg` staging copies were seeded in Task 5. Avoid `&` and `"`
in the title. Include `Closes #4651`.

- [ ] **Step 5: Wait for CI, then mark ready for review**

Poll both surfaces — dbt Cloud is a commit status, Trunk and CodeQL are check
runs:

```bash
gh pr checks <pr-number> --json name,bucket,state
```

When everything is green, fetch dbt Cloud warnings with
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)` and treat
warnings unchanged from `main` as pre-existing. Then mark the PR ready via
GraphQL `markPullRequestReadyForReview` so `claude-review` fires. Do not use the
REST `draft=false` PATCH — it silently no-ops.

---

## Branch 2 — #4652

### Task 7: Create the stacked branch and worktree

**Files:** none.

**Interfaces:**

- Consumes: branch 1's committed work.
- Produces: worktree
  `/workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency`
  on branch `cbini/feat/claude-focus-contacts-emergency`, based on branch 1.

- [ ] **Step 1: Ask the user to confirm the stacked branch**

STOP. Branch creation needs explicit consent in the immediately preceding
message, because the auto-classifier cannot see earlier approvals. Ask:

> "Ready to create the stacked branch
> `cbini/feat/claude-focus-contacts-emergency` off
> `cbini/fix/claude-focus-contacts-address-of-record` for #4652, with its own
> worktree. Confirm?"

- [ ] **Step 2: Create the linked branch and worktree**

```bash
gh issue develop 4652 \
  --name cbini/feat/claude-focus-contacts-emergency \
  --base cbini/fix/claude-focus-contacts-address-of-record
git fetch origin cbini/feat/claude-focus-contacts-emergency
git worktree add \
  /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency \
  cbini/feat/claude-focus-contacts-emergency
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency/src/dbt/kipptaf
```

Expected: branch created and linked to #4652, worktree checked out, packages
installed.

Every path in Tasks 8-10 is relative to this second worktree, not branch 1's.

---

### Task 8: Union emergency rows into `rpt_focus__contacts`

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql` (full
  restructure)

**Interfaces:**

- Consumes: kipptaf `int_finalsite__contact_custom_attributes` — columns
  `finalsite_enrollment_id`, and for each `N` in 1..4: `emrg_N_name_first_name`,
  `emrg_N_name_last_name`, `emrg_N_email`, `emrg_N_relationship_ss`,
  `emrg_N_relationship_txt`, `emrg_N_custody_yn`, `emrg_N_lives_with_yn`,
  `emrg_N_pickup_yn`, and `emrg_N_phone_{1,2,3}_{type,number}`.
  `emrg_N_name_middle_name` exists for N in 1..2 ONLY — slots 3 and 4 have no
  middle-name field in the pivot.
- Produces: the same 50 columns in the same order. No contract change.

- [ ] **Step 1: Restructure the model**

Rewrite `src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql` as a
`guardians` CTE, a four-branch `emergency_long` CTE, an `all_contacts` union
that assigns `sort_order`, and a final projection of the 50 layout columns.

The `guardians` CTE is the current query minus `sort_order`, plus two ordering
columns and the four flag columns as nulls:

```sql
with
    guardians as (
        select
            rel.relationship_id,
            rel.rel_type as student_relation,

            g.first_name,
            g.middle_name,
            g.last_name,
            g.email,
            g.phone_1_type as contact1_type,
            g.phone_1_number as contact1_value,
            g.phone_2_type as contact2_type,
            g.phone_2_number as contact2_value,

            ida.focus_student_id_prefixed as student_id,

            aor.address_1 as address,
            aor.address_2 as address2,
            aor.city,
            aor.state,
            aor.zip as zipcode,

            0 as contact_group,

            cast(null as string) as resides_with_stud,
            cast(null as string) as custody,
            cast(null as string) as emergency,
            cast(null as string) as pickup,
            cast(null as string) as contact3_type,
            cast(null as string) as contact3_value,

            if(rel.is_primary, 0, 1) as group_rank,
        from {{ ref("stg_finalsite__contact_relationships") }} as rel
        inner join
            {{ ref("stg_finalsite__contacts") }} as g
            on rel.rel_id = g.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on rel.finalsite_enrollment_id = l.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on rel.finalsite_enrollment_id = ida.finalsite_enrollment_id
            and ida.focus_student_id_prefixed is not null
        left join
            {{ ref("int_finalsite__contact_address_of_record") }} as aor
            on rel.rel_id = aor.finalsite_enrollment_id
        inner join
            {{ ref("stg_finalsite__contacts") }} as stu
            on rel.finalsite_enrollment_id = stu.finalsite_enrollment_id
            and stu.status = 'enrolled'
        where
            rel.rel_type in (
                'parent',
                'guardian',
                'grandparent',
                'stepparent',
                'relative',
                'aunt/uncle'
            )
    ),
```

`if(rel.is_primary, 0, 1)` returns NULL when `is_primary` is NULL, which would
sort last under `order by group_rank`. That is the existing behavior of
`order by rel.is_primary desc` and is intentional — do not "fix" it with a
`coalesce`.

The `emergency_long` CTE has four `union all` branches. Write branch 1 as shown
below, then produce branches 2, 3, and 4 by copying it whole and applying
exactly these substitutions — nothing else changes:

| Branch | Column prefix | `group_rank` literal | `middle_name` expression              |
| ------ | ------------- | -------------------- | ------------------------------------- |
| 1      | `emrg_1_`     | `1`                  | `a.emrg_1_name_middle_name`           |
| 2      | `emrg_2_`     | `2`                  | `a.emrg_2_name_middle_name`           |
| 3      | `emrg_3_`     | `3`                  | `cast(null as string) as middle_name` |
| 4      | `emrg_4_`     | `4`                  | `cast(null as string) as middle_name` |

`1 as contact_group` and `'Y' as emergency` stay literal in all four. Slots 3
and 4 have no `emrg_N_name_middle_name` field in the pivot, which is why their
`middle_name` is a cast null; moving it out of the plain-ref group and into the
simple-function group also keeps ST06 satisfied. `relationship_id` is `STRING`
in `stg_finalsite__contact_relationships`, so `cast(null as string)` unions
cleanly with the guardian branch.

Note that the file's existing
`-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus CONTACTS contract`
covers only the `select` on the line immediately after it. Keep it on the FINAL
projection, where the contract fixes the order, and order columns inside every
CTE properly: plain refs grouped by source table in join order, then constants,
then simple functions, then logicals.

```sql
    emergency_long as (
        -- Positional passthrough: emergency_N is the emrg_N custom-field set
        -- as-is. Finalsite emergency contacts are custom fields on the
        -- student's own record, not relationship rows, so they never reach the
        -- relationship-type filter above. The shape here mirrors
        -- int_finalsite__student_contacts, which cannot be ref'd — it excludes
        -- Miami to avoid double-counting against the PowerSchool branch of
        -- int_students__contacts.
        select
            a.emrg_1_name_first_name as first_name,
            a.emrg_1_name_middle_name as middle_name,
            a.emrg_1_name_last_name as last_name,
            a.emrg_1_email as email,
            a.emrg_1_phone_1_type as contact1_type,
            a.emrg_1_phone_1_number as contact1_value,
            a.emrg_1_phone_2_type as contact2_type,
            a.emrg_1_phone_2_number as contact2_value,
            a.emrg_1_phone_3_type as contact3_type,
            a.emrg_1_phone_3_number as contact3_value,

            ida.focus_student_id_prefixed as student_id,

            1 as contact_group,
            1 as group_rank,
            'Y' as emergency,

            cast(null as string) as relationship_id,
            cast(null as string) as address,
            cast(null as string) as address2,
            cast(null as string) as city,
            cast(null as string) as state,
            cast(null as string) as zipcode,

            coalesce(
                a.emrg_1_relationship_ss, a.emrg_1_relationship_txt
            ) as student_relation,

            if(a.emrg_1_lives_with_yn, 'Y', null) as resides_with_stud,
            if(a.emrg_1_custody_yn, 'Y', null) as custody,
            if(a.emrg_1_pickup_yn, 'Y', null) as pickup,
        from {{ ref("int_finalsite__contact_custom_attributes") }} as a
        inner join
            {{ ref("int_finalsite__enrollment_lifecycle") }} as l
            on a.finalsite_enrollment_id = l.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contact_id_attributes") }} as ida
            on a.finalsite_enrollment_id = ida.finalsite_enrollment_id
            and ida.focus_student_id_prefixed is not null
        inner join
            {{ ref("stg_finalsite__contacts") }} as stu
            on a.finalsite_enrollment_id = stu.finalsite_enrollment_id
            and stu.status = 'enrolled'
        where
            a.emrg_1_name_first_name is not null
            and a.emrg_1_name_first_name != ''

        union all

        -- ... repeat for emrg_2 (group_rank 2), emrg_3 (group_rank 3, null
        -- middle_name), emrg_4 (group_rank 4, null middle_name)
    ),
```

The `all_contacts` CTE unions the two, listing every column explicitly in both
branches (a `select *` inside a `UNION ALL` trips sqlfluff CV03), and derives
`sort_order`:

```sql
    all_contacts as (
        select
            student_id,
            relationship_id,
            student_relation,
            first_name,
            middle_name,
            last_name,
            email,
            contact1_type,
            contact1_value,
            contact2_type,
            contact2_value,
            contact3_type,
            contact3_value,
            address,
            address2,
            city,
            state,
            zipcode,
            resides_with_stud,
            custody,
            emergency,
            pickup,
            contact_group,
            group_rank,
        from guardians

        union all

        select
            student_id,
            relationship_id,
            student_relation,
            first_name,
            middle_name,
            last_name,
            email,
            contact1_type,
            contact1_value,
            contact2_type,
            contact2_value,
            contact3_type,
            contact3_value,
            address,
            address2,
            city,
            state,
            zipcode,
            resides_with_stud,
            custody,
            emergency,
            pickup,
            contact_group,
            group_rank,
        from emergency_long
    ),

    ranked as (
        -- Guardians hold ranks 1..N in their existing order, then emergency
        -- slots follow in emrg_1..4 order. Miami populates no
        -- emrg_N_priority_ss at all, so there is nothing to interleave on.
        -- relationship_id is the final tiebreak so two guardians sharing
        -- is_primary and both names get a stable rank between runs.
        select
            *,

            row_number() over (
                partition by student_id
                order by
                    contact_group asc,
                    group_rank asc,
                    last_name asc,
                    first_name asc,
                    relationship_id asc
            ) as sort_order,
        from all_contacts
    )
```

The final `SELECT` lists the 50 layout columns in `CONTACTS_LAYOUT` order —
identical to the current model's projection — reading from `ranked` instead of
the join chain, and keeps the existing
`-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus CONTACTS contract`
comment on the line above `select`.

- [ ] **Step 2: Build and check the row counts**

```bash
uv run dbt build \
  --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency/src/dbt/kipptaf \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: builds, and the
`dbt_utils.unique_combination_of_columns(student_id, sort_order)` test passes. A
failure there means `row_number()` is partitioned or ordered wrongly.

Then confirm the shape:

```sql
select
    countif(emergency is null) as guardian_rows,
    countif(emergency = 'Y') as emergency_rows,
    count(distinct if(emergency = 'Y', student_id, null)) as students_with_emergency,
    countif(emergency = 'Y' and contact3_value is not null) as emergency_third_phones,
    countif(emergency = 'Y' and address is not null) as emergency_rows_with_address,
    count(*) as total_rows
from `teamster-332318.zz_cbini_kipptaf_extracts.rpt_focus__contacts`
```

Expected: `guardian_rows` 2,601, `emergency_rows` 923, `students_with_emergency`
464, `emergency_rows_with_address` **0**, `total_rows` 3,524.

Also confirm the ordering rule holds — no emergency row may outrank a guardian
row for the same student:

```sql
with
    boundaries as (
        select
            student_id,
            max(if(emergency is null, sort_order, 0)) as last_guardian,
            min(if(emergency = 'Y', sort_order, 9999)) as first_emergency
        from `teamster-332318.zz_cbini_kipptaf_extracts.rpt_focus__contacts`
        group by student_id
    )
select countif(first_emergency < last_guardian) as violations
from boundaries
```

Expected: `violations` 0.

- [ ] **Step 3: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql </dev/null
```

Then:

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency add \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__contacts.sql
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency commit -m "feat(dbt): append Finalsite emergency contacts to the Focus CONTACTS feed

Refs #4652

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Document the emergency rows and add a unit test

**Files:**

- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml`

**Interfaces:**

- Consumes: Task 8's output columns.
- Produces: no schema change; documentation and one new unit test.

- [ ] **Step 1: Update the four flag column descriptions**

Replace the `resides_with_stud`, `custody`, `emergency`, and `pickup` column
descriptions:

```yaml
      - name: resides_with_stud
        data_type: string
        description:
          `Y` when the emergency contact is recorded as living with the student
          (`emrg_N_lives_with_yn`), else null. Always null on guardian rows — the
          relationship grain carries no equivalent field. Null in KIPP Miami
          today, where the emergency form does not collect it.
      - name: custody
        data_type: string
        description:
          `Y` when the emergency contact is recorded as having custody
          (`emrg_N_custody_yn`), else null. Always null on guardian rows. Null in
          KIPP Miami today, where the emergency form does not collect it.
      - name: emergency
        data_type: string
        description:
          `Y` on rows sourced from a Finalsite `emrg_N` emergency-contact slot,
          null on guardian rows. Derived, not sourced from a Finalsite field.
      - name: pickup
        data_type: string
        description:
          `Y` when the emergency contact is authorized for pickup
          (`emrg_N_pickup_yn`), else null. Always null on guardian rows. Null in
          KIPP Miami today, where the emergency form does not collect it. The
          separate `pickup_1..3` and `nonpickup_1..3` Finalsite blocks are
          deliberately not sourced — they are name-only, and `nonpickup` names
          people barred from pickup, which this layout cannot express.
```

- [ ] **Step 2: Update the `contact3_*`, `sort_order`, and model descriptions**

Replace the `contact3_type` and `contact3_value` descriptions:

```yaml
- name: contact3_type
  data_type: string
  description:
    Type label of the emergency contact's third phone (`emrg_N_phone_3_type`).
    Null on guardian rows, which carry two phones.
- name: contact3_value
  data_type: string
  description:
    Number of the emergency contact's third phone (`emrg_N_phone_3_number`).
    Null on guardian rows.
```

Replace the `sort_order` description:

```yaml
- name: sort_order
  data_type: int64
  description:
    Ordinal rank of this contact within the student. Guardian rows come first,
    ordered by `is_primary desc` then last and first name, with
    `relationship_id` as a stable tiebreak; emergency-slot rows follow in
    `emrg_1` through `emrg_4` order. KIPP Miami populates no
    `emrg_N_priority_ss`, so emergency rows are not interleaved by priority.
```

In the model `description:`, replace the sentence `Phone slots \`CONTACT1__\`
and \`CONTACT2__\` map the guardian's two phones; \`CONTACT3\` through
\`CONTACT7\` are always null.` with:

```text
      Emergency contacts are appended from the four `emrg_N` slots on
      `int_finalsite__contact_custom_attributes` — they are custom fields on the
      student's own record rather than relationship rows, so the relationship
      filter never sees them. Phone slots `CONTACT1_*` and `CONTACT2_*` map a
      guardian's two phones; an emergency row additionally fills `CONTACT3_*`
      from its third phone. `CONTACT4` through `CONTACT7` are always null.
```

Also change the opening sentence from `One row per (student, guardian)` to
`One row per (student, contact) — guardians plus emergency-contact slots —`.

- [ ] **Step 3: Add the emergency unit test**

Append this to the `unit_tests:` block:

```yaml
- name: test_contacts_guardians_then_emergency_slots
  description:
    One student with two guardians and two populated emergency slots. Guardians
    take SORT_ORDER 1 and 2 by is_primary then name; emergency slots take 3 and
    4 in emrg_N order. Emergency rows carry EMERGENCY `Y`, a null address, and a
    third phone; guardian rows carry a null EMERGENCY and no third phone. An
    emrg_3 slot with a blank first name produces no row.
  model: rpt_focus__contacts
  given:
    - input: ref("int_finalsite__enrollment_lifecycle")
      rows:
        - { finalsite_enrollment_id: enr-stu-001 }
    - input: ref("stg_finalsite__contact_relationships")
      rows:
        - {
            finalsite_enrollment_id: enr-stu-001,
            relationship_id: rel-001,
            rel_id: enr-grd-pri,
            rel_name: Alice Johnson,
            rel_type: parent,
            is_primary: true,
            is_financial: true,
            has_portal_access: true,
          }
        - {
            finalsite_enrollment_id: enr-stu-001,
            relationship_id: rel-002,
            rel_id: enr-grd-sec,
            rel_name: Bob Smith,
            rel_type: guardian,
            is_primary: false,
            is_financial: false,
            has_portal_access: false,
          }
    - input: ref("stg_finalsite__contacts")
      rows:
        - { finalsite_enrollment_id: enr-stu-001, status: enrolled }
        - {
            finalsite_enrollment_id: enr-grd-pri,
            first_name: Alice,
            middle_name: B,
            last_name: Johnson,
            email: alice@example.com,
            phone_1_type: Home,
            phone_1_number: "+13055550100",
            phone_2_type: Cell,
            phone_2_number: "+13055550101",
          }
        - {
            finalsite_enrollment_id: enr-grd-sec,
            first_name: Bob,
            middle_name: null,
            last_name: Smith,
            email: bob@example.com,
            phone_1_type: Work,
            phone_1_number: "+13055550200",
            phone_2_type: null,
            phone_2_number: null,
          }
    - input: ref("int_finalsite__contact_id_attributes")
      format: sql
      rows: |
        select
          'enr-stu-001' as finalsite_enrollment_id,
          '84002002002' as focus_student_id_prefixed
    - input: ref("int_finalsite__contact_address_of_record")
      format: sql
      rows: |
        select
          'enr-grd-pri' as finalsite_enrollment_id,
          '100 Main St' as address_1,
          cast(null as string) as address_2,
          'Miami' as city,
          'FL' as state,
          '33101' as zip
        union all
        select 'enr-grd-sec', '200 Oak Ave', null, 'Miami', 'FL', '33102'
    - input: ref("int_finalsite__contact_custom_attributes")
      format: sql
      rows: |
        select
          'enr-stu-001' as finalsite_enrollment_id,
          'Carla' as emrg_1_name_first_name,
          cast(null as string) as emrg_1_name_middle_name,
          'Reyes' as emrg_1_name_last_name,
          'carla@example.com' as emrg_1_email,
          'Aunt' as emrg_1_relationship_ss,
          cast(null as string) as emrg_1_relationship_txt,
          true as emrg_1_custody_yn,
          true as emrg_1_lives_with_yn,
          true as emrg_1_pickup_yn,
          'Cell' as emrg_1_phone_1_type,
          '+13055550301' as emrg_1_phone_1_number,
          'Home' as emrg_1_phone_2_type,
          '+13055550302' as emrg_1_phone_2_number,
          'Work' as emrg_1_phone_3_type,
          '+13055550303' as emrg_1_phone_3_number,
          'Dan' as emrg_2_name_first_name,
          cast(null as string) as emrg_2_name_middle_name,
          'Ortiz' as emrg_2_name_last_name,
          cast(null as string) as emrg_2_email,
          cast(null as string) as emrg_2_relationship_ss,
          'Neighbor' as emrg_2_relationship_txt,
          cast(null as bool) as emrg_2_custody_yn,
          cast(null as bool) as emrg_2_lives_with_yn,
          cast(null as bool) as emrg_2_pickup_yn,
          'Cell' as emrg_2_phone_1_type,
          '+13055550401' as emrg_2_phone_1_number,
          cast(null as string) as emrg_2_phone_2_type,
          cast(null as string) as emrg_2_phone_2_number,
          cast(null as string) as emrg_2_phone_3_type,
          cast(null as string) as emrg_2_phone_3_number,
          '' as emrg_3_name_first_name,
          cast(null as string) as emrg_3_name_last_name,
          cast(null as string) as emrg_3_email,
          cast(null as string) as emrg_3_relationship_ss,
          cast(null as string) as emrg_3_relationship_txt,
          cast(null as bool) as emrg_3_custody_yn,
          cast(null as bool) as emrg_3_lives_with_yn,
          cast(null as bool) as emrg_3_pickup_yn,
          cast(null as string) as emrg_3_phone_1_type,
          cast(null as string) as emrg_3_phone_1_number,
          cast(null as string) as emrg_3_phone_2_type,
          cast(null as string) as emrg_3_phone_2_number,
          cast(null as string) as emrg_3_phone_3_type,
          cast(null as string) as emrg_3_phone_3_number,
          cast(null as string) as emrg_4_name_first_name,
          cast(null as string) as emrg_4_name_last_name,
          cast(null as string) as emrg_4_email,
          cast(null as string) as emrg_4_relationship_ss,
          cast(null as string) as emrg_4_relationship_txt,
          cast(null as bool) as emrg_4_custody_yn,
          cast(null as bool) as emrg_4_lives_with_yn,
          cast(null as bool) as emrg_4_pickup_yn,
          cast(null as string) as emrg_4_phone_1_type,
          cast(null as string) as emrg_4_phone_1_number,
          cast(null as string) as emrg_4_phone_2_type,
          cast(null as string) as emrg_4_phone_2_number,
          cast(null as string) as emrg_4_phone_3_type,
          cast(null as string) as emrg_4_phone_3_number
  expect:
    format: sql
    rows: |
      select
        '84002002002' as student_id,
        'parent' as student_relation,
        1 as sort_order,
        'Alice' as first_name,
        'B' as middle_name,
        'Johnson' as last_name,
        -- ... every remaining layout column, in CONTACTS_LAYOUT order
      union all
      select '84002002002', 'guardian', 2, 'Bob', null, 'Smith', ...
```

The `expect` block MUST list all 50 output columns. dbt compares the fixture
against the model output with `except distinct` in both directions, so a shorter
column list fails on a column-count mismatch rather than narrowing the
comparison. Every unit test in this repo lists the full set, and the sibling
`int_finalsite__student_contacts` tests use `format: sql` for exactly this
reason — it is far more compact here than 4 x 50 dict keys.

Write the four expected rows as one `select ... union all ...`, the first branch
aliasing all 50 columns and the later branches positional. The column order is
the model's final `SELECT` order; copy the sequence from the existing
`test_contacts_two_guardians` expect rows in the same file. The asserted values:

| Column              | Row 1        | Row 2        | Row 3        | Row 4        |
| ------------------- | ------------ | ------------ | ------------ | ------------ |
| `student_id`        | 84002002002  | 84002002002  | 84002002002  | 84002002002  |
| `student_relation`  | parent       | guardian     | Aunt         | Neighbor     |
| `sort_order`        | 1            | 2            | 3            | 4            |
| `first_name`        | Alice        | Bob          | Carla        | Dan          |
| `middle_name`       | B            | null         | null         | null         |
| `last_name`         | Johnson      | Smith        | Reyes        | Ortiz        |
| `resides_with_stud` | null         | null         | Y            | null         |
| `custody`           | null         | null         | Y            | null         |
| `emergency`         | null         | null         | Y            | Y            |
| `pickup`            | null         | null         | Y            | null         |
| `address`           | 100 Main St  | 200 Oak Ave  | null         | null         |
| `address2`          | null         | null         | null         | null         |
| `city`              | Miami        | Miami        | null         | null         |
| `state`             | FL           | FL           | null         | null         |
| `zipcode`           | 33101        | 33102        | null         | null         |
| `email`             | alice@…      | bob@…        | carla@…      | null         |
| `contact1_type`     | Home         | Work         | Cell         | Cell         |
| `contact1_value`    | +13055550100 | +13055550200 | +13055550301 | +13055550401 |
| `contact2_type`     | Cell         | null         | Home         | null         |
| `contact2_value`    | +13055550101 | null         | +13055550302 | null         |
| `contact3_type`     | null         | null         | Work         | null         |
| `contact3_value`    | null         | null         | +13055550303 | null         |

Use the full email addresses from the `given` fixtures, not the elided forms
above. Every remaining column — `contact1_blocked` / `_unlisted` / `_callout`,
the same three for `contact2`, and all of `contact3_blocked` through
`contact7_unlisted` — is null in all four rows. Use `cast(null as string)` on
the first branch so BigQuery types each column, and bare `null` on the later
ones.

- [ ] **Step 4: Run the whole Focus unit-test directory**

```bash
uv run dbt test \
  --select "test_type:unit,extracts.focus" \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency/src/dbt/kipptaf \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Expected: all Focus unit tests PASS, including the pre-existing
`test_contacts_two_guardians`, whose expected `sort_order` values are unchanged
because it mocks no emergency slots.

- [ ] **Step 5: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml </dev/null
```

Then:

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency add \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__contacts.yml
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency commit -m "docs(dbt): document the Focus CONTACTS emergency rows and sort order

Closes #4652

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Validate branch 2, update the ops doc, open the stacked PR

**Files:**

- Modify: `docs/reference/finalsite-focus-import.md`

**Interfaces:**

- Consumes: Tasks 8 and 9.
- Produces: PR against `cbini/fix/claude-focus-contacts-address-of-record`
  closing #4652.

- [ ] **Step 1: Confirm the kippmiami wrapper needs no change**

The kippmiami wrapper
`src/dbt/kippmiami/models/extracts/focus/rpt_focus__contacts.sql` lists all 50
columns explicitly and its anti-join is on `student_id`. Adding rows changes
neither. Verify by building it:

```bash
uv run dbt build \
  --select rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency/src/dbt/kippmiami \
  --target dev \
  --defer --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: builds unchanged. Confirm the sendable set still excludes the students
Focus already holds and that emergency rows survive the name gate — every
emergency row has a first name by construction, so none should be dropped:

```sql
select
    countif(emergency = 'Y') as sendable_emergency_rows,
    count(*) as sendable_rows
from `teamster-332318.zz_cbini_kippmiami_extracts.rpt_focus__contacts`
```

Expected: `sendable_emergency_rows` close to 923, minus only the rows belonging
to the ~13 students already present in Focus.

- [ ] **Step 2: Update the ops doc**

Add this subsection to `docs/reference/finalsite-focus-import.md` immediately
after the "Blank addresses and nameless contacts are held back" section:

```markdown
### Emergency contacts

The Contacts file now carries the student's emergency contacts alongside their
parents and guardians. They come from the four emergency-contact slots on the
student's Finalsite record — not from the family relationships — and they are
sent after the guardians, in the order the slots appear in Finalsite. Each one
carries its name, relationship, email, and up to three phone numbers, and is
flagged in Focus as an emergency contact. Emergency contacts have no household
in Finalsite, so they arrive with no address; that is expected, not a gap.

The custody, pickup, and lives-with checkboxes are sent when Finalsite has them.
KIPP Miami's emergency form does not currently collect them, so those three
columns arrive blank today and will populate on their own if the form starts
asking.

> **Emergency contacts only reach a student Focus does not already have.** The
> import-once rule matches on the student, not the individual contact — once any
> contact for a student has been imported, none of that student's other contacts
> are ever sent, including emergency contacts added later. Add them in Focus
> directly for students already imported.
```

- [ ] **Step 3: Lint, commit, push, and open the stacked PR**

```bash
cd /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/reference/finalsite-focus-import.md </dev/null
```

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency add \
  docs/reference/finalsite-focus-import.md
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency commit -m "docs: describe Focus emergency contacts for the enrollment team

Refs #4652

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency push -u origin cbini/feat/claude-focus-contacts-emergency
```

Open the PR with `mcp__github__create_pull_request`, base
`cbini/fix/claude-focus-contacts-address-of-record`, body from
`.github/pull_request_template.md`, including `Closes #4652`. State in the body
that `claude-review` does not fire on a non-`main` base, that the PR cannot
merge until #4651's does, and that three of the four newly-populated layout
columns ship null in KIPP Miami because the emergency form does not collect
them.

- [ ] **Step 4: Rebase onto `main` after branch 1 merges**

Once #4651's PR is squash-merged, the stacked branch's base disappears. Retarget
it:

```bash
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency fetch origin main
git -C /workspaces/teamster/.worktrees/cbini/feat/claude-focus-contacts-emergency rebase origin/main
```

Resolve any conflict in `rpt_focus__contacts.sql` in favor of branch 2's
restructure with branch 1's address join retained, then force-push and change
the PR base to `main` with `mcp__github__update_pull_request`. Changing the base
to `main` also lets `claude-review` fire — toggle draft state via GraphQL
`convertPullRequestToDraft` then `markPullRequestReadyForReview` to trigger it.
