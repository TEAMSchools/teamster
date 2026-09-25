# Finalsite Address Pick Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve a Finalsite address of record by picking the best candidate
household instead of withholding when several exist, cutting KIPP Miami students
with no address anywhere from 158 to 46.

**Architecture:** Two independently revertable commits. The first teaches
`int_finalsite__contact_address_of_record` to pick a winner among a contact's
street-bearing households. The second reorders
`int_finalsite__student_address_of_record` to prefer Parent 1's household,
widens its spine so a student without a Parent 1 still resolves, and reports
whether the address was picked.

**Tech Stack:** dbt 1.11 on BigQuery, `dbt_utils`, sqlfluff / markdownlint via
trunk, BigQuery MCP for validation.

**Spec:** `docs/superpowers/specs/2026-08-01-finalsite-address-pick-design.md` —
read it before Task 1.

## Global Constraints

- Worktree is
  `/workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick` on
  branch `cbini/fix/claude-finalsite-address-pick`. Every `Read` / `Edit` /
  `Write` must use that absolute path. Editing `/workspaces/teamster/<path>`
  silently dirties `main`.
- Every git call is
  `git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick ...`.
- Every dbt call is `uv run dbt ... --project-dir <worktree>/src/dbt/<project>`.
  Never `uv --directory`.
- Every dev build adds
  `--target dev --defer --favor-state --state /workspaces/teamster/src/dbt/<project>/target/prod`.
  `--favor-state` is mandatory — a stale personal dev copy silently shadows
  `--defer` and produces wrong numbers.
- Never `--target prod`. `--target staging` is classifier-blocked and needs
  explicit user authorization in the immediately preceding turn.
- `finalsite` is a source-system package with no resolvable vars standalone.
  Build its models through a consuming district:
  `--project-dir <worktree>/src/dbt/kippmiami`.
- Run `uv run dbt deps --project-dir <worktree>/src/dbt/kippmiami` once before
  the first build in this worktree.
- Lint before every commit, from inside the worktree, with both flags:
  `cd <worktree> && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix <paths> </dev/null`.
- `git add` names files explicitly. Never `-u`, `-A`, or `.`.
- Commit trailer on every commit:
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`.
- No PII in any commit message, PR body, or issue comment. Counts and column
  names only.
- Pick order is `is_complete_address desc, household_id asc` — in that order,
  everywhere. `desc` on a boolean is safe inside `dbt_utils.deduplicate`'s
  `array_agg`; only explicit `asc nulls last` / `desc nulls first` are rejected
  by BigQuery.

## File Structure

| File                                                                                         | Responsibility                                          | Task |
| -------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ---- |
| `src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql`     | Pick the winning household per contact                  | 1    |
| `.../properties/int_finalsite__contact_address_of_record.yml`                                | Status vocabulary, invariants, unit tests               | 1    |
| `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql`     | Spine, tier order, picked flag                          | 2    |
| `.../properties/int_finalsite__student_address_of_record.yml`                                | Status values, new column, grain description            | 2    |
| `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql` | Force `state:modified` so CI rebuilds the union wrapper | 2    |
| `src/dbt/finalsite/CLAUDE.md`                                                                | Model-summary prose for both models                     | 2    |
| `docs/reference/finalsite-focus-import.md`                                                   | Ops-facing description of the new behavior              | 3    |

---

### Task 1: Pick the winning household in the contact model

**Files:**

- Modify:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql`
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_address_of_record.yml`

**Interfaces:**

- Consumes: `int_finalsite__contacts__households` (columns
  `finalsite_enrollment_id`, `household_id`, `address_1`, `address_2`, `city`,
  `state`, `zip`, `country`, `is_complete_address`) and
  `stg_finalsite__contacts` (`finalsite_enrollment_id`).
- Produces: the same nine output columns in the same order —
  `finalsite_enrollment_id`, `address_1`, `address_2`, `city`, `state`, `zip`,
  `country`, `is_complete_address`, `candidate_count`, `resolution_status`. No
  column added or removed. `resolution_status` gains the value `picked` and
  loses `ambiguous`. Task 2 reads `candidate_count` and `resolution_status`.

- [ ] **Step 1: Update the three unit tests that assert `ambiguous`**

In `properties/int_finalsite__contact_address_of_record.yml`, three unit tests
currently expect a null address with `resolution_status: ambiguous`. Each now
expects the picked winner. Make exactly these edits.

Rename `test_contact_address_formatting_variants_stay_distinct` to
`test_contact_address_formatting_variants_pick_lowest_household_id`, replace its
`description`, and replace its `expect` block:

```yaml
- name: test_contact_address_formatting_variants_pick_lowest_household_id
  description:
    Exact matching is deliberate, so two households recording the same address
    with different punctuation, case, and a ZIP+4 remain two distinct
    candidates. Both are equally complete, so the tiebreak falls to the lowest
    `household_id` and that row's raw text is emitted.
```

```yaml
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
        candidate_count: 2,
        resolution_status: picked,
      }
```

Rename `test_contact_address_null_field_is_a_distinct_candidate` to
`test_contact_address_completeness_wins_over_household_id`, and replace its
`description` and `expect`:

```yaml
- name: test_contact_address_completeness_wins_over_household_id
  description:
    A null field groups as its own value rather than matching a populated one,
    so two households on the same street where one carries a ZIP and the other
    does not are two distinct candidates. The complete one wins regardless of
    `household_id` order.
```

```yaml
expect:
  rows:
    - {
        finalsite_enrollment_id: con-7,
        address_1: 55 Coral Way,
        address_2: null,
        city: Miami,
        state: FL,
        zip: "33134",
        country: US,
        is_complete_address: true,
        candidate_count: 2,
        resolution_status: picked,
      }
```

Rename `test_contact_address_real_differences_stay_ambiguous` to
`test_contact_address_real_differences_pick_lowest_household_id`, and replace
its `description` and `expect`:

```yaml
- name: test_contact_address_real_differences_pick_lowest_household_id
  description:
    Households sharing a street line but differing by apartment or by city stay
    distinct candidates. Both are complete, so the lowest `household_id` wins
    and its address is emitted rather than withheld.
```

```yaml
expect:
  rows:
    - {
        finalsite_enrollment_id: con-2,
        address_1: 222 Bay St,
        address_2: Apt 1,
        city: Miami,
        state: FL,
        zip: "33106",
        country: US,
        is_complete_address: true,
        candidate_count: 2,
        resolution_status: picked,
      }
    - {
        finalsite_enrollment_id: con-3,
        address_1: 400 Palm Way,
        address_2: null,
        city: Miami,
        state: FL,
        zip: "33101",
        country: US,
        is_complete_address: true,
        candidate_count: 2,
        resolution_status: picked,
      }
```

Leave `test_contact_address_incomplete_resolves_and_fragments_excluded`
untouched — its `resolved` and `no_street` cases are unchanged.

ZIP values are quoted because they are leading-digit strings that yamllint's
`octal-values` rule would otherwise flag. Everything else stays unquoted per the
repo's `quoted-strings` rule.

- [ ] **Step 2: Add a unit test proving completeness beats a lower id**

The existing `con-7` case has the complete household at the lower id, so it
passes under either ordering. Add a case where the two disagree. Append this
unit test after the last one in the file:

```yaml
- name: test_contact_address_completeness_beats_lower_household_id
  description:
    When the lower `household_id` is the incomplete one, completeness still
    decides. This is the case that distinguishes the real ordering from a plain
    lowest-id pick.
  model: int_finalsite__contact_address_of_record
  given:
    - input: ref("stg_finalsite__contacts")
      rows:
        - { finalsite_enrollment_id: con-8 }
    - input: ref("int_finalsite__contacts__households")
      format: sql
      rows: |
        select
          'con-8' as finalsite_enrollment_id,
          'hh-20' as household_id,
          '7 Sunset Dr' as address_1,
          cast(null as string) as address_2,
          cast(null as string) as city,
          cast(null as string) as state,
          cast(null as string) as zip,
          'US' as country,
          false as is_complete_address
        union all
        select 'con-8', 'hh-21', '8 Sunrise Dr', null, 'Miami', 'FL',
          '33101', 'US', true
  expect:
    rows:
      - {
          finalsite_enrollment_id: con-8,
          address_1: 8 Sunrise Dr,
          address_2: null,
          city: Miami,
          state: FL,
          zip: "33101",
          country: US,
          is_complete_address: true,
          candidate_count: 2,
          resolution_status: picked,
        }
```

- [ ] **Step 3: Run the unit tests to verify they fail**

```bash
uv run dbt test \
  --select "test_type:unit,int_finalsite__contact_address_of_record" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: FAIL. The four picked-address cases fail because the model still nulls
the address and reports `ambiguous`. If any of them PASSES, stop — the fixture
is not exercising what it claims.

- [ ] **Step 4: Rewrite the model to pick a winner**

Replace the whole of
`src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql`
with:

```sql
with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    candidate_households as (
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
        from {{ ref("int_finalsite__contacts__households") }}
        where address_1 is not null
    ),

    address_candidates as (
        -- One row per (contact, distinct address). Address identity is an
        -- exact match on the five mailing fields — no case-folding, no
        -- punctuation-stripping, no ZIP+4 truncation. Two spellings of the
        -- same address therefore stay distinct candidates and are counted
        -- separately, which is what makes candidate_count meaningful.
        {{
            dbt_utils.deduplicate(
                relation="candidate_households",
                partition_by=(
                    "finalsite_enrollment_id, address_1, address_2, city,"
                    " state, zip"
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

    picked_address as (
        -- The address of record is the BEST candidate, not the only one. A
        -- complete address beats an incomplete one; ties fall to the lowest
        -- household_id so the pick is stable between runs. Withholding was
        -- worse than choosing: a blank address in an import-once feed is
        -- permanent and silent, while a wrong one is visible and correctable
        -- in the receiving system.
        {{
            dbt_utils.deduplicate(
                relation="address_candidates",
                partition_by="finalsite_enrollment_id",
                order_by="is_complete_address desc, household_id asc",
            )
        }}
    ),

    counted as (
        -- Spined on the full contact list so a contact with no street-bearing
        -- household still gets a row, with candidate_count 0.
        select
            c.finalsite_enrollment_id,

            p.address_1,
            p.address_2,
            p.city,
            p.state,
            p.zip,
            p.country,
            p.is_complete_address,

            coalesce(cc.candidate_count, 0) as candidate_count,
        from {{ ref("stg_finalsite__contacts") }} as c
        left join
            candidate_counts as cc
            on c.finalsite_enrollment_id = cc.finalsite_enrollment_id
        left join
            picked_address as p
            on c.finalsite_enrollment_id = p.finalsite_enrollment_id
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
        when candidate_count = 0
        then 'no_street'
        when candidate_count = 1
        then 'resolved'
        else 'picked'
    end as resolution_status,
from counted
```

`address_candidates` no longer needs a `trunk-ignore(sqlfluff/ST03)` because
`candidate_counts` references it normally. `candidate_households` keeps its
ignore — it is still reached only through the macro.

- [ ] **Step 5: Run the unit tests to verify they pass**

```bash
uv run dbt test \
  --select "test_type:unit,int_finalsite__contact_address_of_record" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: PASS, 5 tests.

- [ ] **Step 6: Update the two model-level invariants**

In `properties/int_finalsite__contact_address_of_record.yml`, replace the whole
`data_tests:` block on the model (currently lines 19-41) with:

```yaml
data_tests:
  - dbt_utils.expression_is_true:
      arguments:
        expression: |
          (resolution_status != 'no_street' and address_1 is not null)
          or (
              resolution_status = 'no_street'
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
          or (resolution_status = 'picked' and candidate_count > 1)
      config:
        severity: error
```

The first invariant inverts deliberately: previously only `resolved` carried an
address, now everything except `no_street` does.

- [ ] **Step 7: Update the status column and model descriptions**

Replace the `resolution_status` column block:

```yaml
- name: resolution_status
  data_type: string
  description:
    Why this contact does or does not have an address — `resolved` (exactly one
    distinct address, no judgment applied), `picked` (several distinct
    addresses, the most complete one chosen and ties broken by the lowest
    `household_id`), or `no_street` (no household carries a street line).
    `picked` is the audit signal — it marks every address the pipeline chose
    rather than read unambiguously.
  data_tests:
    - accepted_values:
        arguments:
          values:
            - resolved
            - picked
            - no_street
        config:
          severity: error
    - not_null:
        config:
          severity: error
```

Replace the `candidate_count` description text with:

```yaml
description:
  Number of distinct addresses on this contact's household linkage. One resolves
  outright; zero means no household carries a street; more than one means the
  emitted address was picked from among them.
```

In the model `description:`, replace the sentence beginning
`A contact resolves only when exactly one distinct address remains;` through the
end of that sentence with:

```text
      A contact with at least one candidate always emits an address: the most
      complete one, with ties broken by the lowest `household_id`. The emitted
      values are the raw text of the winning household.
```

Also replace the earlier clause
`so two spellings of the same address stay distinct candidates and the contact is withheld rather than guessed at`
with
`so two spellings of the same address stay distinct candidates and are counted separately`.

- [ ] **Step 8: Build the model and confirm the status distribution**

```bash
uv run dbt build \
  --select int_finalsite__contact_address_of_record \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: PASS with both `expression_is_true` invariants, `unique`, `not_null`,
and `accepted_values` green.

Then, with `mcp__bigquery__execute_sql` against your dev schema (find it via
`INFORMATION_SCHEMA.SCHEMATA`, it follows `zz_cbini_kippmiami_finalsite`):

```sql
select resolution_status, count(*) as contacts
from `teamster-332318.zz_cbini_kippmiami_finalsite.int_finalsite__contact_address_of_record`
group by resolution_status
order by contacts desc
```

Expected against the prod baseline of 4,729 `resolved` / 511 `ambiguous` / 2,282
`no_street`: `resolved` 4,729, `picked` 511, `no_street` 2,282. The `resolved`
and `no_street` counts must be **unchanged** — only the `ambiguous` bucket is
renamed and now carries addresses. Any movement between `resolved` and
`no_street` means the candidate logic changed, which it must not.

- [ ] **Step 9: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_address_of_record.yml \
  </dev/null
```

Fix anything reported and re-run until clean.

- [ ] **Step 10: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick add \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__contact_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contact_address_of_record.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick commit -m "fix(finalsite): pick the best candidate household for a contact address

Refs #4680

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Reorder and widen the student model

**Files:**

- Modify:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql`
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml`
- Modify:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql`
- Modify: `src/dbt/finalsite/CLAUDE.md`

**Interfaces:**

- Consumes: Task 1's `int_finalsite__contact_address_of_record` — columns
  `finalsite_enrollment_id`, `candidate_count`, `resolution_status`,
  `address_1`, `address_2`, `city`, `state`, `zip`, `country`,
  `is_complete_address`. Also `stg_finalsite__contacts`
  (`finalsite_enrollment_id`, `status`, `phone_1_number`) and
  `stg_finalsite__contact_relationships` (`finalsite_enrollment_id`, `rel_id`,
  `is_primary`).
- Produces: today's columns plus one new `is_picked_address` (`boolean`).
  `resolution_status` values become `primary_contact_household`,
  `student_household`, `unresolved`. `rpt_focus__addresses` continues to filter
  on `address_source is not null`, which is unchanged in meaning.

- [ ] **Step 1: Write the failing unit test for Parent 1 precedence**

Append to the `unit_tests:` block in
`properties/int_finalsite__student_address_of_record.yml`:

```yaml
- name: test_address_of_record_primary_contact_wins_over_student
  description:
    When the student's own household and their Parent 1's household both resolve
    to different addresses, Parent 1 wins. The student's own linkage is only a
    fallback.
  model: int_finalsite__student_address_of_record
  given:
    - input: ref("stg_finalsite__contacts")
      rows:
        - {
            finalsite_enrollment_id: stu-10,
            status: enrolled,
            phone_1_number: null,
          }
        - {
            finalsite_enrollment_id: par-10,
            status: not_in_workflow,
            phone_1_number: "+13055551000",
          }
    - input: ref("stg_finalsite__contact_relationships")
      rows:
        - {
            finalsite_enrollment_id: stu-10,
            rel_id: par-10,
            rel_type: parent,
            is_primary: true,
          }
    - input: ref("int_finalsite__contact_address_of_record")
      format: sql
      rows: |
        select
          'stu-10' as finalsite_enrollment_id,
          '1 Student Way' as address_1,
          cast(null as string) as address_2,
          'Miami' as city,
          'FL' as state,
          '33101' as zip,
          'US' as country,
          true as is_complete_address,
          1 as candidate_count,
          'resolved' as resolution_status
        union all
        select 'par-10', '2 Parent Ave', null, 'Miami', 'FL', '33102', 'US',
          true, 1, 'resolved'
  expect:
    rows:
      - {
          finalsite_enrollment_id: stu-10,
          student_candidate_count: 1,
          primary_contact_candidate_count: 1,
          address_source: primary_contact_household,
          address_1: 2 Parent Ave,
          address_2: null,
          city: Miami,
          state: FL,
          zip: "33102",
          country: US,
          is_complete_address: true,
          primary_contact_phone: "+13055551000",
          resolution_status: primary_contact_household,
          is_picked_address: false,
        }
```

BigQuery `UNION ALL` is positional, so every branch must carry all ten values in
the same order as the aliased first branch. A missing leading value shifts every
column and fails on a type mismatch.

- [ ] **Step 2: Write the failing unit test for a student with no Parent 1**

Append:

```yaml
- name: test_address_of_record_no_primary_resolves_from_own_household
  description:
    A student with no Parent 1 still resolves from their own household. The old
    `where is_primary` spine dropped these students entirely even when their own
    address was unambiguous.
  model: int_finalsite__student_address_of_record
  given:
    - input: ref("stg_finalsite__contacts")
      rows:
        - {
            finalsite_enrollment_id: stu-11,
            status: enrolled,
            phone_1_number: null,
          }
    - input: ref("stg_finalsite__contact_relationships")
      rows:
        - {
            finalsite_enrollment_id: stu-11,
            rel_id: aunt-11,
            rel_type: aunt/uncle,
            is_primary: null,
          }
    - input: ref("int_finalsite__contact_address_of_record")
      format: sql
      rows: |
        select
          'stu-11' as finalsite_enrollment_id,
          '3 Own St' as address_1,
          cast(null as string) as address_2,
          'Miami' as city,
          'FL' as state,
          '33103' as zip,
          'US' as country,
          true as is_complete_address,
          1 as candidate_count,
          'resolved' as resolution_status
  expect:
    rows:
      - {
          finalsite_enrollment_id: stu-11,
          student_candidate_count: 1,
          primary_contact_candidate_count: 0,
          address_source: student_household,
          address_1: 3 Own St,
          address_2: null,
          city: Miami,
          state: FL,
          zip: "33103",
          country: US,
          is_complete_address: true,
          primary_contact_phone: null,
          resolution_status: student_household,
          is_picked_address: false,
        }
```

- [ ] **Step 3: Update the three existing unit tests**

Every `expect` row must gain `is_picked_address` — dbt does not null-fill
omitted keys, and an uneven `expect` fails with a column-count mismatch.

Two of these fixtures also mock the OLD contact model, where `ambiguous` meant a
null address. That combination is now impossible: any contact with
`candidate_count >= 1` carries an address. Leaving them would test behavior the
upstream model can no longer produce, so they need real values, not just a new
key.

**`test_address_of_record_student_linkage_decisive`** asserts
`student_household` while its Parent 1 (`par-1`) has `candidate_count: 2`. Under
Parent-1-first that parent now wins, so the test no longer demonstrates what its
name says. Repurpose it into the fallback case. Rename to
`test_address_of_record_student_fallback_when_primary_has_none`, replace the
description with "A student resolves from their own household when their Parent
1 has no street-bearing household at all.", change the `par-1` fixture branch to
`select 'par-1', null, null, null, null, null, null, null, 0, 'no_street'`, and
change the expect row's `primary_contact_candidate_count` to `0`, keeping
`address_source: student_household` and adding `is_picked_address: false`.

**`test_address_of_record_primary_contact_fallback`** already expects
`primary_contact_household`, which stays correct. But its `stu-2` branch carries
`candidate_count: 2` with a null address. Make it consistent and make the test
earn its place by proving `picked` propagates: change the `par-2` branch to
`select 'par-2', '111 Palm Way', null, 'Miami', 'FL', '33103', 'US', true, 2, 'picked'`,
change `primary_contact_candidate_count` to `2` in the expect row, and add
`is_picked_address: true`. Rename it to
`test_address_of_record_picked_flag_propagates` and update the description to
"When the winning household was itself picked from several, the student row
reports `is_picked_address`."

**`test_address_of_record_both_sides_ambiguous`** — rename to
`test_address_of_record_no_address_anywhere`, reword the description to say
neither the student nor their Parent 1 has a street-bearing household, set both
fixture branches to `candidate_count: 0` / `'no_street'`, change
`resolution_status: ambiguous` to `resolution_status: unresolved`, and add
`is_picked_address: null`.

**`test_address_of_record_incomplete_address_is_emitted`** — add
`is_picked_address: false` to both expect rows. Then verify each row's
`address_source` still matches Parent-1-first: any row whose fixture gives the
primary contact `candidate_count >= 1` must now expect
`primary_contact_household`. Change the ones that do not match, and adjust the
asserted address to the parent's.

- [ ] **Step 4: Run the tests to verify they fail**

```bash
uv run dbt test \
  --select "test_type:unit,int_finalsite__student_address_of_record" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: FAIL — `is_picked_address` does not exist yet, so the model output has
fewer columns than the fixtures.

- [ ] **Step 5: Rewrite the model**

Replace the whole of
`src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql`
with:

```sql
with
    student_records as (
        -- A student record is a contact carrying a workflow status. Adults sit
        -- at 'not_in_workflow'. This replaces a `where is_primary` spine, which
        -- defined a student as someone with a designated Parent 1 and so
        -- dropped every student without one — even when that student's own
        -- household resolved cleanly.
        select finalsite_enrollment_id,
        from {{ ref("stg_finalsite__contacts") }}
        where status != 'not_in_workflow'
    ),

    student_primary_contacts as (
        -- `relationships.primary` is a per-record singleton that is true or
        -- NULL, never false. A second primary on one student surfaces as a
        -- duplicate and fails this model's uniqueness test, which is the
        -- intended loud failure.
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
            s.finalsite_enrollment_id,

            spc.primary_contact_id,

            sa.resolution_status as student_resolution_status,

            pa.resolution_status as primary_contact_resolution_status,

            coalesce(sa.candidate_count, 0) as student_candidate_count,
            coalesce(pa.candidate_count, 0) as primary_contact_candidate_count,
        from student_records as s
        left join
            student_primary_contacts as spc
            on s.finalsite_enrollment_id = spc.finalsite_enrollment_id
        left join
            {{ ref("int_finalsite__contact_address_of_record") }} as sa
            on s.finalsite_enrollment_id = sa.finalsite_enrollment_id
        left join
            {{ ref("int_finalsite__contact_address_of_record") }} as pa
            on spc.primary_contact_id = pa.finalsite_enrollment_id
    ),

    sourced as (
        -- Parent 1's household is the address of record; the student's own is
        -- the fallback. The reverse order used to be correct because a parent
        -- carries more households and the old rule withheld on any ambiguity —
        -- once the contact model picks a winner, the parent's larger household
        -- count costs nothing. The student tier must stay: some students hold
        -- an address while their Parent 1 holds none.
        select
            finalsite_enrollment_id,
            primary_contact_id,
            student_candidate_count,
            primary_contact_candidate_count,

            case
                when primary_contact_candidate_count >= 1
                then 'primary_contact_household'
                when student_candidate_count >= 1
                then 'student_household'
            end as address_source,
            case
                when primary_contact_candidate_count >= 1
                then primary_contact_id
                when student_candidate_count >= 1
                then finalsite_enrollment_id
            end as address_contact_id,
            case
                when primary_contact_candidate_count >= 1
                then primary_contact_resolution_status
                when student_candidate_count >= 1
                then student_resolution_status
            end as winning_resolution_status,
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

    coalesce(s.address_source, 'unresolved') as resolution_status,

    s.winning_resolution_status = 'picked' as is_picked_address,
from sourced as s
-- address_contact_id is only ever set to a contact that has at least one
-- candidate, so this join cannot fan out; when it is null (no address anywhere)
-- nothing matches and the address fields stay null.
left join
    {{ ref("int_finalsite__contact_address_of_record") }} as a
    on s.address_contact_id = a.finalsite_enrollment_id
left join
    {{ ref("stg_finalsite__contacts") }} as pc
    on s.primary_contact_id = pc.finalsite_enrollment_id
```

`is_picked_address` is null when nothing resolved, because
`winning_resolution_status` is null there — that is intended and the unit test
asserts it.

- [ ] **Step 6: Run the tests to verify they pass**

```bash
uv run dbt test \
  --select "test_type:unit,int_finalsite__student_address_of_record" \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: PASS, 6 tests.

- [ ] **Step 7: Update the properties YAML**

Replace the `resolution_status` column block:

```yaml
- name: resolution_status
  data_type: string
  description:
    Which record supplied the address — `primary_contact_household`,
    `student_household`, or `unresolved` when neither the student's Parent 1 nor
    the student themselves has a street-bearing household. Parent 1 is tried
    first; the student's own linkage is the fallback.
  data_tests:
    - accepted_values:
        arguments:
          values:
            - primary_contact_household
            - student_household
            - unresolved
        config:
          severity: error
    - not_null:
        config:
          severity: error
```

Add this column block immediately after `address_source`:

```yaml
- name: is_picked_address
  data_type: boolean
  description:
    Whether the winning household was chosen from several candidates rather than
    read unambiguously, carried through from the contact model's `picked`
    status. Null when no address resolved. This is the audit signal for an
    import-once feed — it marks every address the pipeline decided rather than
    found.
```

Replace the `student_candidate_count` description:

```yaml
description:
  Number of distinct addresses on the student's own household linkage, from
  `int_finalsite__contact_address_of_record`. One or more means the student's
  own records can supply an address; it is used only when the primary contact
  has none. Zero means no household linked to the student carries a street line.
```

Replace the `primary_contact_candidate_count` description:

```yaml
description:
  Number of distinct addresses on the primary contact's household linkage. One
  or more makes the primary contact's household the address of record.
```

Replace the model `description:` sentences describing grain and resolution with:

```text
      One row per Finalsite student record — the student's resolved address of
      record, or a flag when it cannot be resolved. Grain is
      `finalsite_enrollment_id` for contacts carrying a workflow status, which
      is how a student record is identified without reaching for a SIS-specific
      field; adult contacts sit at `not_in_workflow` and are absent. Resolution
      takes the primary contact's household when
      `int_finalsite__contact_address_of_record` gives them one, falls back to
      the student's own when it does, and otherwise emits no address. Address
      identity, candidate counting, and the pick rule live in that model, so
      this feed and the contact feed resolve addresses the same way. An emitted
      address is not guaranteed complete — check `is_complete_address` — and may
      have been picked from several, which `is_picked_address` reports.
      SIS-agnostic — no enrollment, status, or academic-year scoping beyond
      excluding non-student contacts; receivers filter downstream.
```

- [ ] **Step 8: Force the kipptaf union wrapper to rebuild**

`dbt_utils.union_relations` resolves its column list at compile time from the
source relations' `INFORMATION_SCHEMA`. A new column does not reach the kipptaf
wrapper unless the wrapper is itself `state:modified` — and a properties-YAML
change does not mark a model modified, only a `.sql` edit does.

Add this comment as the first line of
`src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql`:

```sql
-- is_picked_address added upstream in #4680; this comment forces state:modified
-- so CI rebuilds the union and picks up the new column.
```

- [ ] **Step 9: Update the package CLAUDE.md**

In `src/dbt/finalsite/CLAUDE.md`, replace the
`int_finalsite__contact_address_of_record` and
`int_finalsite__student_address_of_record` bullets with:

```markdown
- `int_finalsite__contact_address_of_record` — one row per Finalsite contact
  (students and adults alike) carrying that contact's resolved address. A
  household is a candidate once it has a street line — completeness is
  deliberately not required. A contact with several candidates gets the most
  complete one, ties broken by lowest `household_id`, flagged `picked`; only a
  contact with no street-bearing household at all gets no address.
- `int_finalsite__student_address_of_record` — one row per student record (a
  contact carrying a workflow status; adults sit at `not_in_workflow`) with the
  resolved address of record: their primary contact's household when
  `int_finalsite__contact_address_of_record` gives them one, else the student's
  own, else no address and an `unresolved` flag. Also carries the primary
  contact's phone, since student records almost never hold one.
```

- [ ] **Step 10: Build the chain and check the stranded count**

```bash
uv run dbt build \
  --select int_finalsite__contact_address_of_record \
    int_finalsite__student_address_of_record \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick/src/dbt/kippmiami \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kippmiami/target/prod
```

Expected: PASS, including `unique` on `finalsite_enrollment_id`.

Then:

```sql
select
    resolution_status,
    countif(is_picked_address) as picked,
    count(*) as students
from `teamster-332318.zz_cbini_kippmiami_finalsite.int_finalsite__student_address_of_record`
group by resolution_status
order by students desc
```

Expected: three statuses only. `unresolved` should be far smaller than today's
`ambiguous` count. If `unresolved` is larger, the tier logic is inverted.

- [ ] **Step 11: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/finalsite/CLAUDE.md \
  </dev/null
```

- [ ] **Step 12: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick add \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/finalsite/CLAUDE.md
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick commit -m "fix(finalsite): prefer the primary contact household and widen the student spine

Refs #4680

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Validate against production, document, and open the PR

**Files:**

- Modify: `docs/reference/finalsite-focus-import.md`

**Interfaces:**

- Consumes: Tasks 1 and 2.
- Produces: a PR against `main` closing #4680.

- [ ] **Step 1: Build the full Focus chain into dev**

The kipptaf union wrappers read all four districts via `source()`, and
`source()` is not `--defer`-eligible — so each district's package models must
exist in your dev schema before the kipptaf build will compile. Install packages
once per district, then build.

```bash
wt=/workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick
for d in kippmiami kippcamden kippnewark kipppaterson; do
  uv run dbt deps --project-dir "$wt/src/dbt/$d"
  uv run dbt build \
    --select int_finalsite__contact_address_of_record \
      int_finalsite__student_address_of_record \
    --project-dir "$wt/src/dbt/$d" \
    --target dev --defer --favor-state \
    --state "/workspaces/teamster/src/dbt/$d/target/prod"
done
```

Then the kipptaf layer:

```bash
uv run dbt build \
  --select int_finalsite__contact_address_of_record \
    int_finalsite__student_address_of_record \
    rpt_focus__addresses rpt_focus__contacts \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick/src/dbt/kipptaf \
  --target dev --defer --favor-state \
  --state /workspaces/teamster/src/dbt/kipptaf/target/prod
```

Report every command's PASS / ERROR counts.

- [ ] **Step 2: Run the safety bar at the kipptaf layer**

Compare your dev kipptaf `rpt_focus__addresses` — the desired-state model, where
this change actually lands — against the deployed
`teamster-332318.kipptaf_extracts.rpt_focus__addresses`:

```sql
select
    countif(p.student_id is null) as newly_gaining,
    countif(d.student_id is null) as newly_losing,
    countif(
        d.student_id is not null
        and p.student_id is not null
        and (
            d.address != p.address
            or coalesce(d.zipcode, '~') != coalesce(p.zipcode, '~')
            or coalesce(d.city, '~') != coalesce(p.city, '~')
        )
    ) as address_changed,
from `teamster-332318.zz_cbini_kipptaf_extracts.rpt_focus__addresses` as d
full outer join
    `teamster-332318.kipptaf_extracts.rpt_focus__addresses` as p
    on d.student_id = p.student_id
```

Expected: `newly_losing` **0**, `address_changed` at most **113**. A
`newly_losing` above zero is a defect — stop and report it rather than
explaining it away.

Do NOT run this against the kippmiami wrapper. The kippmiami
`models/extracts/sources.yml` entry for `kipptaf_extracts` carries no
target-conditional schema, so the wrapper always reads **prod**
`kipptaf_extracts` regardless of target. A dev build of it silently compares
prod against prod and reports a clean no-op.

- [ ] **Step 3: Confirm the stranded count landed at 46**

The stranded count needs the Miami sendable set, which only the kippmiami
wrapper produces — and per Step 2 that wrapper reads prod. Get the true
post-change number by taking the wrapper's compiled SQL
(`src/dbt/kippmiami/target/compiled/.../rpt_focus__contacts.sql` and
`rpt_focus__addresses.sql`), replacing the `kipptaf_extracts` references with
your `zz_cbini_kipptaf_extracts` dev relations, and running the result as CTEs
inside this query:

```sql
with
    sendable as (
        -- paste the rewritten rpt_focus__contacts compiled SQL here
        select student_id, address from ...
    ),
    addresses as (
        -- paste the rewritten rpt_focus__addresses compiled SQL here
        select student_id from ...
    ),
    grouped as (
        select student_id, max(if(address is not null, 1, 0)) as has_addr
        from sendable
        group by student_id
    ),
    no_addr as (select student_id from grouped where has_addr = 0)
select
    (select count(*) from no_addr) as no_addressed_contact,
    (
        select count(*)
        from no_addr as n
        left join addresses as a on n.student_id = a.student_id
        left join
            (
                select distinct cast(student_id as string) as student_id
                from `teamster-332318.kippmiami_focus.stg_focus__students_join_address`
            ) as f
            on n.student_id = f.student_id
        where a.student_id is null and f.student_id is null
    ) as truly_stranded
```

Expected: `truly_stranded` **46**, down from a prod baseline of 158. Report the
actual number. If it differs materially, report it and stop — do not adjust the
expectation to match the output.

- [ ] **Step 4: Update the ops doc**

In `docs/reference/finalsite-focus-import.md`, four passages in the "Blank
addresses and nameless contacts are held back" section now describe behavior the
pipeline no longer has. Make these exact replacements.

Replace the sentence
`To prevent that, the pipeline **holds a student's address record back when it cannot tell which address to send**.`
with:

```text
To prevent that, the pipeline **holds a student's address record back only when
Finalsite has no usable address for them at all**.
```

Replace the whole **Addresses** bullet with:

```markdown
- **Addresses** — a student's address comes from the households their Parent 1
  is linked to, falling back to the households the student is linked to when
  Parent 1 has none. When Finalsite points to several addresses, the pipeline
  sends the most complete one rather than sending nothing. A household with no
  street line is not treated as an address at all; a household that has a street
  but is missing its city, state, or ZIP **is** sent, so the gap is visible in
  Focus and can be fixed there. A student gets no address only when neither they
  nor their Parent 1 has a household carrying a street line, and flows the first
  run Finalsite gives either of them one.
```

Replace the whole **Contacts** bullet with:

```markdown
- **Contacts** — a contact is sent only once it has a name. A nameless contact
  is skipped and flows once the name is filled in. A guardian's address is
  resolved from the guardian's own households only, with no fallback: when
  Finalsite links them to several addresses the most complete one is sent, and
  the address is left blank only when none of their households carries a street
  line. The contact goes out with the rest of their details either way.
```

Replace the blockquote beginning
`**A student can be enrolled in Focus with no address yet.**` with:

```markdown
> **A student can be enrolled in Focus with no address yet.** That is expected
> when Finalsite holds no street address for them or for their Parent 1. Fix it
> in Finalsite — fill in the missing address, or retire the household the family
> no longer lives at — and it flows on the next run. (Demographics is not held
> back this way; a student's demographics import as soon as the student is
> enrolled in Finalsite and new to Focus.)
```

The old blockquote blamed "several and none is marked as the one to use" and a
missing Parent 1. Neither is a reason for a blank address any more — several
resolves by picking, and a student with no Parent 1 now resolves from their own
household.

Finally, grep the file for `ambiguous`, `more than one address`, and `several`
to catch any remaining prose asserting the withhold behavior, and fix what you
find. Leave the "Emergency contacts" subsection alone — it landed in #4652 and
is unrelated.

- [ ] **Step 5: Lint the doc**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick && \
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/reference/finalsite-focus-import.md </dev/null
```

- [ ] **Step 6: Commit and push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick add \
  docs/reference/finalsite-focus-import.md
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick commit -m "docs: describe address picking for the enrollment team

Refs #4680

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-pick push
```

- [ ] **Step 7: Open the PR**

Base `main`. Body from `.github/pull_request_template.md`, including
`Closes #4680`. Write the body to a file and post it with
`gh api -X POST repos/TEAMSchools/teamster/pulls -F body=@<file> -f title=... -f head=... -f base=main`
— the `mcp__github__*` write tools strip angle-bracket tokens and entity-encode
ampersands and quotes. Avoid `&` and `"` in the title.

State in the body: the measured before/after stranded counts, the `newly_losing`
and `address_changed` numbers from Step 2, that the 113 address changes are the
expected consequence of the tier reorder, that the `is_picked_address` column
addition required forcing the kipptaf union wrapper `state:modified`, and that
the remaining 46 students are Finalsite data gaps needing Ops cleanup rather
than a pipeline change.

Read the stored body back with
`gh api repos/TEAMSchools/teamster/pulls/<n> --jq .body` and confirm it is
intact.

- [ ] **Step 8: Flag the staging-seed requirement to the user**

`is_picked_address` is a column ADD on a package model that kipptaf unions. dbt
Cloud CI reads `zz_stg_<district>_finalsite` copies, which will not carry the
new column until each district's staging copy is rebuilt. That rebuild is
`dbt build --select int_finalsite__student_address_of_record --target staging`
per district, which recreates shared `zz_stg` relations and is
classifier-blocked without explicit user authorization naming the operation.

Do not attempt it. Report to the user that CI will fail with
`Name is_picked_address not found` until they authorize the four staging builds,
and give them the exact commands.
