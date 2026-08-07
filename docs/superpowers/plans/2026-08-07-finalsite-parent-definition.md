# Finalsite Parent Definition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redefine how `int_finalsite__student_contacts` selects a student's
parents — drop the Parent-1-household filter, guard both slots against picking
another student, rank candidates densely instead of capping at two — and add
warn tests that surface students with no parent or with more than two.

**Architecture:** The model currently picks `contact_1` from the relationship
flagged `primary`, then picks `contact_2` only from candidates co-resident with
`contact_1`. That coupling means a missing `primary` flag suppresses both slots.
The rewrite builds one `parent_candidates` set (flagged `primary` or
`financial`, related contact is an adult), ranks it, and numbers slots densely.
Household co-membership with the **student** becomes a sort key rather than a
gate.

**Tech Stack:** dbt (BigQuery), `uv` for all Python/dbt invocation, sqlfluff +
prettier via trunk, dbt unit tests and singular tests.

## Global Constraints

- Worktree is
  `/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition`.
  Every `git` call uses `git -C "$wt"`. Every dbt call uses
  `--project-dir "$wt/src/dbt/<project>"`. Set
  `wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition`
  once per shell.
- **Keep that shell variable lowercase.** `check-sensitive.sh` Rule 7 denies any
  Bash command that expands a non-allowlisted `$UPPER_CASE` variable — including
  one defined in the same command — and reports it as the misleading
  `Cannot access sensitive path`. `wt` works; `WT` gets the whole command
  blocked.
- Never run bare `python`/`dbt`. Always `uv run dbt ...`.
- The `finalsite` project is a **package**, not a standalone project. Build and
  test its models through a district project — use `kippnewark` throughout.
- Do not run `trunk fmt` or `trunk check` manually; the pre-commit hook formats
  and the pre-push hook blocks. Exception: after editing SQL, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd set to the worktree before the final push, because sqlfluff fires
  only at pre-push and in CI.
- Commit messages use conventional commits and end with `Refs #4768`.
- No student, parent, or contact names in any committed file, commit message, PR
  body, or issue comment. Counts and column names only.
- Design spec is
  `docs/superpowers/specs/2026-08-07-finalsite-parent-definition-design.md`.

---

## File Structure

| Path                                                                                  | Responsibility                                      |
| ------------------------------------------------------------------------------------- | --------------------------------------------------- |
| `src/dbt/finalsite/dbt_project.yml`                                                   | Declare `current_academic_year` var (default `0`)   |
| `src/dbt/finalsite/tests/stg_finalsite__contacts__no_stale_enrolled.sql`              | Warn: `enrolled` record stamped with a prior year   |
| `src/dbt/finalsite/tests/stg_finalsite__contact_relationships__single_primary.sql`    | Warn: a student holds more than one `primary`       |
| `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql`       | Parent candidate set, dense ranking, adult guard    |
| `.../properties/int_finalsite__student_contacts.yml`                                  | Slot-pattern test, descriptions, unit-test fixtures |
| `src/dbt/finalsite/tests/int_finalsite__student_contacts__enrolled_has_contact_1.sql` | Warn: current enrolled student with no `contact_1`  |
| `src/dbt/finalsite/tests/int_finalsite__student_contacts__no_extra_contacts.sql`      | Warn: any slot past `contact_2`                     |
| `src/dbt/kipptaf/models/marts/dimensions/dim_student_contact_persons.sql`             | Stop misfiling an unknown parent slot as emergency  |

---

## Task 1: Source-data warn tests

Independent of the model rewrite; lands first so the rewrite starts from a clean
build. Adds the `current_academic_year` var the first test needs.

**Files:**

- Modify: `src/dbt/finalsite/dbt_project.yml` (vars block, lines 33-36)
- Create:
  `src/dbt/finalsite/tests/stg_finalsite__contacts__no_stale_enrolled.sql`
- Create:
  `src/dbt/finalsite/tests/stg_finalsite__contact_relationships__single_primary.sql`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces: `var("current_academic_year")` available inside the `finalsite`
  package. Task 3 reads it.

- [ ] **Step 1: Declare the year var in the finalsite package**

The package has no `current_academic_year`, so
`{{ var("current_academic_year") }}` would fail to compile. `focus` and
`powerschool` declare it as `0` and let each district override; follow that.

Replace the `vars:` block at the end of `src/dbt/finalsite/dbt_project.yml`:

```yaml
vars:
  cloud_storage_uri_base: null
  bigquery_external_connection_name: null
  local_timezone: null
  current_academic_year: 0
```

All four district projects already set `current_academic_year: 2026`, so no
district change is needed.

- [ ] **Step 2: Write the stale-enrolled test**

Create `src/dbt/finalsite/tests/stg_finalsite__contacts__no_stale_enrolled.sql`:

```sql
{{ config(severity="warn") }}

-- Finalsite never rolls a graduated cohort off `enrolled` -- last year's
-- seniors keep that status indefinitely -- and separately, some students who
-- are still enrolled never get a current-year record created. Both surface as
-- an `enrolled` contact stamped with a prior school year. Warn, not error:
-- this is a standing Ops worklist inside Finalsite, and the count only falls
-- when someone corrects records at the source.
select
    finalsite_enrollment_id,
    status,
    school_year_start,
    grade_name,
from {{ ref("stg_finalsite__contacts") }}
where
    status = 'enrolled'
    and school_year_start < {{ var("current_academic_year") }}
```

- [ ] **Step 3: Write the single-primary test**

Create
`src/dbt/finalsite/tests/stg_finalsite__contact_relationships__single_primary.sql`:

```sql
{{ config(severity="warn") }}

-- `primary` is a per-student singleton in Finalsite. The old model surfaced a
-- violation as a duplicate contact_1 failing the uniqueness test; dense ranking
-- absorbs a second primary into contact_2 instead, so the condition is tested
-- at the source where it can be acted on. No student trips this today -- it
-- guards against regression rather than reporting a backlog.
select
    finalsite_enrollment_id,
    count(*) as primary_relationships,
from {{ ref("stg_finalsite__contact_relationships") }}
where is_primary
group by finalsite_enrollment_id
having count(*) > 1
```

- [ ] **Step 4: Run both tests against Newark**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
uv run dbt test \
  --project-dir "$wt/src/dbt/kippnewark" \
  --select stg_finalsite__contacts__no_stale_enrolled \
           stg_finalsite__contact_relationships__single_primary
```

Expected: `stg_finalsite__contacts__no_stale_enrolled` **WARN** with 303 rows.
`stg_finalsite__contact_relationships__single_primary` **PASS** with 0 rows.
Neither may ERROR — an error means the var did not resolve.

- [ ] **Step 5: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
git -C "$wt" add src/dbt/finalsite/dbt_project.yml src/dbt/finalsite/tests
git -C "$wt" commit -m "test(finalsite): warn on stale enrolled records and duplicate primaries

Refs #4768"
```

---

## Task 2: Rewrite parent selection

The core change. TDD: the existing unit test asserts the behaviour being
removed, so it is rewritten first and must fail before the model changes.

**Files:**

- Modify:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_contacts.sql`
- Modify:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_contacts.yml`

**Interfaces:**

- Consumes: nothing from Task 1.
- Produces: `contact_slot` values `contact_1`, `contact_2`, `contact_3`. Task 3
  tests these; Task 4 defends against them.

- [ ] **Step 1: Rewrite the `test_student_contacts_parent_2` unit test**

In `int_finalsite__student_contacts.yml`, replace the whole
`test_student_contacts_parent_2` unit test with the version below.

Three fixture changes matter. The model now reads `status` from
`stg_finalsite__contacts` for the adult guard, so every contact fixture needs
it. The model now refs `int_finalsite__contacts__households`, so that becomes a
`given` input. The model no longer reads `household_ids`, so it is dropped.

```yaml
- name: test_student_contacts_parent_2
  description:
    Dense slot assignment. stu1 has a primary parent (con1), a financial
    stepparent sharing stu1's household (con2), and a financial parent in a
    different household (con3) -- yielding contact_1, contact_2, contact_3, with
    con3 ranked last because it shares no household with the student rather than
    being excluded. stu2 has no primary and two financial relationships --
    yielding contact_1 and contact_2, where the old rule yielded nothing. con6
    is a financial relationship to another STUDENT record and is excluded from
    stu2 entirely by the adult guard.
  model: int_finalsite__student_contacts
  given:
    - input: ref('stg_finalsite__contact_relationships')
      format: sql
      rows: |
        select
          'stu1' as finalsite_enrollment_id,
          'rel1' as relationship_id,
          'con1' as rel_id,
          'Jane Doe' as rel_name,
          'parent' as rel_type,
          true as is_primary,
          true as is_financial,
          false as is_parent2
        union all
        select
          'stu1', 'rel2', 'con2', 'John Doe', 'stepparent',
          cast(null as boolean), true, false
        union all
        select
          'stu1', 'rel3', 'con3', 'Jim Poe', 'parent',
          cast(null as boolean), true, false
        union all
        select
          'stu2', 'rel4', 'con4', 'Fay Ray', 'parent',
          cast(null as boolean), true, false
        union all
        select
          'stu2', 'rel5', 'con5', 'Gus Ray', 'parent',
          cast(null as boolean), true, false
        union all
        select
          'stu2', 'rel6', 'con6', 'Kid Ray', 'sibling',
          cast(null as boolean), true, false
    - input: ref('stg_finalsite__contacts')
      format: sql
      rows: |
        select
          'stu1' as finalsite_enrollment_id,
          'enrolled' as status,
          cast(null as string) as email,
          'Stu' as first_name,
          'One' as last_name,
          cast(null as string) as phone_1_number,
          cast(null as string) as phone_1_type,
          cast(null as string) as phone_2_number,
          cast(null as string) as phone_2_type,
          cast(null as string) as phone_3_number,
          cast(null as string) as phone_3_type,
          cast(null as string) as address_1,
          cast(null as string) as address_2,
          cast(null as string) as city,
          cast(null as string) as state,
          cast(null as string) as zip
        union all
        select
          'stu2', 'enrolled', cast(null as string), 'Stu', 'Two',
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string), cast(null as string)
        union all
        select
          'con1', 'not_in_workflow', 'jane@example.com', 'Jane', 'Doe',
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string), cast(null as string)
        union all
        select
          'con2', 'not_in_workflow', 'john@example.com', 'John', 'Doe',
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string), cast(null as string)
        union all
        select
          'con3', 'not_in_workflow', 'jim@example.com', 'Jim', 'Poe',
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string), cast(null as string)
        union all
        select
          'con4', 'not_in_workflow', 'fay@example.com', 'Fay', 'Ray',
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string), cast(null as string)
        union all
        select
          'con5', 'not_in_workflow', 'gus@example.com', 'Gus', 'Ray',
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string), cast(null as string)
        union all
        select
          'con6', 'enrolled', 'kid@example.com', 'Kid', 'Ray',
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string),
          cast(null as string), cast(null as string), cast(null as string)
    - input: ref('int_finalsite__contacts__households')
      format: sql
      rows: |
        select 'stu1' as finalsite_enrollment_id, 'hh1' as household_id
        union all
        select 'con1', 'hh1'
        union all
        select 'con2', 'hh1'
        union all
        select 'con3', 'hh2'
        union all
        select 'stu2', 'hh3'
        union all
        select 'con4', 'hh3'
        union all
        select 'con5', 'hh3'
        union all
        select 'con6', 'hh3'
    - input: ref('int_finalsite__contact_custom_attributes')
      rows: []
  expect:
    format: sql
    rows: |
      select
        'stu1' as finalsite_enrollment_id,
        'contact_1' as contact_slot,
        'con1' as finalsite_contact_id,
        'Jane Doe' as contact_name,
        'Jane' as contact_first_name,
        'Doe' as contact_last_name,
        'parent' as relationship
      union all
      select 'stu1', 'contact_2', 'con2', 'John Doe', 'John', 'Doe', 'stepparent'
      union all
      select 'stu1', 'contact_3', 'con3', 'Jim Poe', 'Jim', 'Poe', 'parent'
      union all
      select 'stu2', 'contact_1', 'con4', 'Fay Ray', 'Fay', 'Ray', 'parent'
      union all
      select 'stu2', 'contact_2', 'con5', 'Gus Ray', 'Gus', 'Ray', 'parent'
```

Note the `expect` block lists only the seven columns under test. dbt unit tests
compare only the columns named in `expect`.

- [ ] **Step 2: Add `status` to the other unit test's fixture**

`test_student_contacts_phone_typed_slots` also mocks `stg_finalsite__contacts`
and will fail to compile once the model reads `status`. In that test's
`stg_finalsite__contacts` input, add `'not_in_workflow' as status,` immediately
after the `finalsite_enrollment_id` line, delete the
`array<string>[] as household_ids` line, and add a
`ref('int_finalsite__contacts__households')` input with `rows: []`.

- [ ] **Step 3: Run the unit tests to verify they fail**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
uv run dbt test \
  --project-dir "$wt/src/dbt/kippnewark" \
  --select int_finalsite__student_contacts
```

Expected: FAIL. `test_student_contacts_parent_2` fails because the current model
excludes `con3` and emits nothing for `stu2`. Compilation errors referencing
`status` or `int_finalsite__contacts__households` are also expected at this
point.

- [ ] **Step 4: Replace the parent CTEs in the model**

In `int_finalsite__student_contacts.sql`, delete the five CTEs
`contact_1_picked`, `primary_household_ids`, `contact_household_ids`,
`contact_2_candidates`, and `contact_2_ranked`, and replace `parent_picks` with
the block below. Everything from `parents_typed` onward is unchanged.

```sql
with
    parent_candidates as (
        -- A parent candidate is any relationship flagged `primary` or
        -- `financial` whose related contact is an ADULT. Finalsite marks adults
        -- with status `not_in_workflow`; every other status (enrolled, inquiry,
        -- waitlisted, ...) belongs to a student record, and a student is never
        -- a parent. This guard -- not `rel_type` -- is what keeps a co-resident
        -- sibling out of a parent slot, which matters because an adult sibling
        -- CAN legitimately be a guardian and must still qualify.
        select
            r.finalsite_enrollment_id,
            r.relationship_id,
            r.rel_id,
            r.rel_name,
            r.rel_type,

            coalesce(r.is_primary, false) as is_primary,
        from {{ ref("stg_finalsite__contact_relationships") }} as r
        inner join
            {{ ref("stg_finalsite__contacts") }} as rc
            on r.rel_id = rc.finalsite_enrollment_id
            and rc.status = 'not_in_workflow'
        where coalesce(r.is_primary, false) or coalesce(r.is_financial, false)
    ),

    candidates_sharing_student_household as (
        -- One row per (student, candidate) that co-belong to any household.
        -- grain projection: a pair sharing several households would otherwise
        -- repeat and fan out the rank below. Not a mask for upstream duplicates.
        select distinct
            c.finalsite_enrollment_id,
            c.rel_id,
        from parent_candidates as c
        inner join
            {{ ref("int_finalsite__contacts__households") }} as sh
            on c.finalsite_enrollment_id = sh.finalsite_enrollment_id
        inner join
            {{ ref("int_finalsite__contacts__households") }} as ch
            on c.rel_id = ch.finalsite_enrollment_id
            and sh.household_id = ch.household_id
    ),

    parent_picks as (
        -- Dense slot numbering: the `primary` relationship sorts first when one
        -- exists, then co-residents with the student, then an arbitrary but
        -- stable relationship_id. Household co-membership ORDERS candidates; it
        -- does not exclude them, so a non-resident parent still fills a slot.
        -- Numbering has no gaps, so a student with no `primary` still gets a
        -- populated contact_1 rather than starting at contact_2.
        select
            c.finalsite_enrollment_id,
            c.rel_id,
            c.rel_name,
            c.rel_type,

            concat(
                'contact_',
                cast(
                    row_number() over (
                        partition by c.finalsite_enrollment_id
                        order by
                            c.is_primary desc,
                            (s.rel_id is not null) desc,
                            c.relationship_id asc
                    ) as string
                )
            ) as contact_slot,
        from parent_candidates as c
        left join
            candidates_sharing_student_household as s
            on c.finalsite_enrollment_id = s.finalsite_enrollment_id
            and c.rel_id = s.rel_id
    ),
```

- [ ] **Step 5: Run the unit tests to verify they pass**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
uv run dbt test \
  --project-dir "$wt/src/dbt/kippnewark" \
  --select int_finalsite__student_contacts
```

Expected: PASS for both unit tests.

- [ ] **Step 6: Replace `accepted_values` and update the descriptions**

Corrected mid-execution. The original plan said to add `- contact_3` to the
`accepted_values` list. That was wrong: it was based on a maximum of three
measured against currently enrolled students, but this model emits every student
record. 8 students across Camden and Newark have four parent slots, and dense
ranking has no upper bound at all.

In `int_finalsite__student_contacts.yml`, DELETE the whole `accepted_values`
data test on `contact_slot` and replace it with a `dbt_utils.expression_is_true`
test at `severity: error` asserting:

```text
regexp_contains(contact_slot, r'^(contact_[0-9]+|emergency_[1-4])$')
```

Parent slots stay unbounded; emergency slots stay bounded at four because they
are a positional passthrough of four fixed `emrg_N` custom-field sets. Follow
the argument syntax already used at
`src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__contacts__households.yml:22-30`.

Replace the `contact_slot` column description with:

```yaml
description:
  Which contact this row represents. Parent slots are numbered densely from
  `contact_1` with no fixed upper bound — as many as the student has qualifying
  adults — so `contact_1` is the top-ranked parent rather than strictly the
  `primary` relationship. `emergency_1` through `emergency_4` are the positional
  `emrg_N` custom-field sets.
```

Replace the model-level description's first sentence about `contact_1` and
`contact_2` with:

```yaml
description:
  SIS-agnostic long-format contact list for Finalsite student records — one row
  per (student, contact slot), grain `(finalsite_enrollment_id, contact_slot)`.
  Parent slots (`contact_1`, `contact_2`, `contact_3`) come from every
  relationship flagged `primary` or `financial` whose related contact is an
  adult (Finalsite status `not_in_workflow`), ranked by the `primary` flag, then
  by sharing a household with the student, then by `relationship_id`, and
  numbered densely. Household co-membership orders candidates rather than
  excluding them, so a non-resident parent still fills a slot. `emergency_1`
  through `emergency_4` are the `custom_attributes` `emrg_N` sets mapped
  positionally — `emergency_N` is `emrg_N` as-is, with no priority re-sort and
  no gap-filling. Sparse — a slot row is emitted only when that slot has data,
  so emergency slots may have gaps. Feeds the downstream PowerSchool/Focus
  contact receivers built on top of this model.
```

Also update the `is_household_member` column description, which currently claims
`contact_2` requires co-membership by construction. Replace its final
parenthetical with:
`(household co-membership now orders parent slots rather than gating them, so a parent slot implies nothing about co-residence)`.

- [ ] **Step 7: Build the model against Newark and check the distribution**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
uv run dbt build \
  --project-dir "$wt/src/dbt/kippnewark" \
  --select int_finalsite__student_contacts+
```

Expected: build succeeds; the `unique_combination_of_columns` and
`expression_is_true` tests pass, including for the 8 students who have four
parent slots. If `expression_is_true` fails, the slot label is malformed —
inspect the failing values rather than widening the pattern.

- [ ] **Step 8: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
git -C "$wt" add src/dbt/finalsite/models/api/intermediate
git -C "$wt" commit -m "feat(finalsite): rank parent contacts densely and guard against student contacts

Refs #4768"
```

---

## Task 3: Slot-count warn tests

**Files:**

- Create:
  `src/dbt/finalsite/tests/int_finalsite__student_contacts__enrolled_has_contact_1.sql`
- Create:
  `src/dbt/finalsite/tests/int_finalsite__student_contacts__no_extra_contacts.sql`
- Create:
  `src/dbt/finalsite/tests/stg_finalsite__contact_relationships__caregiver_is_adult.sql`

**Interfaces:**

- Consumes: `var("current_academic_year")` from Task 1; densely-numbered
  `contact_slot` values from Task 2.
- Produces: nothing later tasks rely on.

- [ ] **Step 1: Write the zero-contact test**

Create
`src/dbt/finalsite/tests/int_finalsite__student_contacts__enrolled_has_contact_1.sql`:

```sql
{{ config(severity="warn") }}

-- A currently enrolled student with no parent slot at all. The model itself
-- stays SIS-agnostic and emits rows for every student record including
-- prospects and applicants, who legitimately have no parent on file yet -- so
-- the enrolled scope lives here, in the test, rather than in the model.
-- Every row is a Finalsite data-entry gap: a missing `primary`/`financial`
-- flag, or a parent whose own contact record is miskeyed with a student status
-- and therefore fails the adult guard.
select
    s.finalsite_enrollment_id,
    s.grade_name,
    s.school_year_start,
from {{ ref("stg_finalsite__contacts") }} as s
where
    s.status = 'enrolled'
    and s.school_year_start = {{ var("current_academic_year") }}
    and not exists (
        select 1
        from {{ ref("int_finalsite__student_contacts") }} as c
        where
            c.finalsite_enrollment_id = s.finalsite_enrollment_id
            and c.contact_slot = 'contact_1'
    )
```

- [ ] **Step 2: Write the extra-contacts test**

Create
`src/dbt/finalsite/tests/int_finalsite__student_contacts__no_extra_contacts.sql`:

```sql
{{ config(severity="warn") }}

-- A student with more parents than the two conventional slots. The wide
-- downstream receivers (contacts pivot, ParentSquare, DeansList, the contacts
-- bridge) all carry two parent columns, so anything past contact_2 is emitted
-- here but dropped before it reaches an extract. Warn so the count stays
-- visible; matching `contact_%` rather than a literal catches a fourth slot too.
select
    finalsite_enrollment_id,
    contact_slot,
from {{ ref("int_finalsite__student_contacts") }}
where
    contact_slot like 'contact\\_%'
    and contact_slot not in ('contact_1', 'contact_2')
```

- [ ] **Step 3: Run both tests against Newark**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
uv run dbt test \
  --project-dir "$wt/src/dbt/kippnewark" \
  --select int_finalsite__student_contacts__enrolled_has_contact_1 \
           int_finalsite__student_contacts__no_extra_contacts
```

Expected, corrected mid-execution against the built model: both tests PASS with
0 rows for `enrolled_has_contact_1` and WARN with 49 rows for
`no_extra_contacts`.

The original plan predicted 1 row for `enrolled_has_contact_1` — the student
whose parent's contact record carries `status = 'inquiry'` and so fails the
adult guard. Dense ranking makes that prediction wrong: that student's other
`financial` parent backfills `contact_1`, so the zero-contact test cannot see
the guard exclusion at all. Step 4 below adds a test that surfaces it directly.

The original 25 for `no_extra_contacts` counted currently-enrolled students; the
model is unscoped and the test counts rows, giving 49.

If `enrolled_has_contact_1` returns hundreds, the dense ranking is not working
and slots are still anchored on `primary`.

- [ ] **Step 4: Write the guard-exclusion test**

Added mid-execution. The adult guard drops any relationship whose related
contact carries a student status — normally correct, since a student is never a
parent. But a parent record miskeyed with a student status is dropped too, and
dense ranking then backfills the slot from another candidate, so the exclusion
is invisible. This test surfaces the miskeyed record directly instead of relying
on the zero-contact test as a proxy.

Create
`src/dbt/finalsite/tests/stg_finalsite__contact_relationships__caregiver_is_adult.sql`:

```sql
{{ config(severity="warn") }}

-- A relationship flagged as a caregiver whose related contact does NOT carry
-- Finalsite's adult status. Almost always this is correct and the related
-- person really is a student -- a sibling flagged `financial`, say -- and the
-- model's adult guard drops it as intended. The rows worth acting on are the
-- inverse: an adult whose own contact record was miskeyed with a student
-- status, whose relationship the guard then discards silently, because dense
-- ranking backfills the slot from another candidate and nothing else reports
-- the loss. Warn: each row is a Finalsite record to inspect, not a build
-- failure.
select
    r.finalsite_enrollment_id,
    r.rel_id,
    r.rel_type,
    c.status as related_contact_status,
    c.grade_name as related_contact_grade,
from {{ ref("stg_finalsite__contact_relationships") }} as r
inner join
    {{ ref("stg_finalsite__contacts") }} as c
    on r.rel_id = c.finalsite_enrollment_id
where
    (coalesce(r.is_primary, false) or coalesce(r.is_financial, false))
    and c.status != 'not_in_workflow'
```

Run it:

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
uv run dbt test \
  --project-dir "$wt/src/dbt/kippnewark" \
  --select stg_finalsite__contact_relationships__caregiver_is_adult
```

Expected: **WARN** with a small number of rows — 1 for Newark on the current
load. A large count means the guard is excluding far more than intended and the
`not_in_workflow` assumption needs re-examining before merge.

- [ ] **Step 5: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
git -C "$wt" add src/dbt/finalsite/tests
git -C "$wt" commit -m "test(finalsite): warn on missing, excess, and discarded parent contacts

Refs #4768"
```

---

## Task 4: Downstream misclassification guard

`dim_student_contact_persons` splits rows into parents and emergency contacts
with complementary predicates. A `contact_3` row satisfies
`not in ('contact_1', 'contact_2')` and would be recorded as an emergency
contact, keyed by student plus slot instead of by person identity. No existing
test catches it.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/marts/dimensions/dim_student_contact_persons.sql:57`

**Interfaces:**

- Consumes: `contact_slot` values from Task 2.
- Produces: nothing.

- [ ] **Step 1: Make the emergency branch explicit**

At line 57, replace:

```sql
        where contact_slot not in ('contact_1', 'contact_2')
```

with:

```sql
        where contact_slot like 'emergency\\_%'
```

Leave the parent branch at line 38 as `in ('contact_1', 'contact_2')`. A
`contact_3` row then matches neither branch and is dropped, consistent with the
other wide receivers — extending them is out of scope per the spec.

Update the CTE comment directly above `emergency_persons` to say the branch is
matched positively so an unrecognised parent slot is dropped rather than
misfiled.

- [ ] **Step 2: Build the dimension and verify no parent slot leaked**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
uv run dbt build \
  --project-dir "$wt/src/dbt/kipptaf" \
  --select dim_student_contact_persons bridge_student_contacts
```

Expected: both build and their tests pass.

- [ ] **Step 3: Confirm no `contact_` slot reached the emergency branch**

Run this against the built dimension using the BigQuery MCP:

```sql
select count(*) as leaked_parent_slots
from `teamster-332318.<your_dev_schema>_marts.dim_student_contact_persons`
where contact_slot like 'contact%'
```

Expected: 0. The parent branch keys on `person_identity` and does not carry
`contact_slot` into the emergency-shaped output, so any row matching here means
the predicate change did not take.

- [ ] **Step 4: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
git -C "$wt" add src/dbt/kipptaf/models/marts/dimensions/dim_student_contact_persons.sql
git -C "$wt" commit -m "fix(kipptaf): match emergency contact slots positively

Refs #4768"
```

---

## Task 5: Full-region verification and push

**Files:** none modified.

- [ ] **Step 1: Build the model in all three cutover regions**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
for p in kippnewark kippcamden kipppaterson; do
  echo "=== $p"
  uv run dbt build --project-dir "$wt/src/dbt/$p" \
    --select int_finalsite__student_contacts+
done
```

Expected: all three succeed. `kippmiami` has the `api` layer enabled but is not
a contacts-cutover region; it is not built here.

- [ ] **Step 2: Confirm the per-region slot distribution**

Query the built tables and compare against the spec's audit table. Scope to
`status = 'enrolled'` and `school_year_start = 2026`:

| Region   | Students | 1 slot | 2 slots | 3 slots |
| -------- | -------- | ------ | ------- | ------- |
| Newark   | 6,786    | 3,682  | 3,079   | 25      |
| Camden   | 2,163    | 1,264  | 840     | 7       |
| Paterson | 879      | 539    | 297     | 0       |

Newark should have 0 students with no slot except the single guard exclusion;
Camden and Paterson have 52 and 43 respectively, which predate this change.

- [ ] **Step 3: Lint the changed SQL**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
cd "$wt" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  $(git -C "$wt" diff --name-only origin/main...HEAD | grep -E '\.(sql|yml|md)$') \
  </dev/null
```

Run in the background — a `--force` check over this many files takes more than
two minutes, and its progress output contains no result lines, so a grep of
partial output reads as a false clean. Only interpret the result after the
command exits.

Expected: no sqlfluff or markdownlint issues. If the trunk binary is missing,
fall back to `~/.cache/trunk/launcher/trunk`.

- [ ] **Step 4: Push and open the PR**

```bash
wt=/workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-parent-definition
git -C "$wt" push -u origin cbini/feat/claude-finalsite-parent-definition
```

Open the PR with `.github/pull_request_template.md` as the body and
`Closes #4768` in it. Do not name any student or contact in the PR body — cite
counts and column names only.

---

## Self-Review

**Spec coverage.** Section 1 (no student-scope filter) is satisfied by not
adding one — Task 2 leaves the model emitting all student records, and the
enrolled scope appears only inside the Task 3 test. Section 2 → Task 1 Step 2.
Section 3 → Task 2 Step 4. Section 4 → the
`inner join ... and rc.status = 'not_in_workflow'` in Task 2 Step 4, with the
no-carve-out consequence asserted in Task 3 Step 3. Section 5 → Tasks 1 and 3,
plus the slot-pattern test in Task 2 Step 6. Section 6 → Task 4. Section 7 →
Task 2 Steps 1 and 2.

**One deviation from the spec, deliberate.** Section 4 says the guard "folds
into the join the model already performs in `parents_typed`". It cannot: the
guard has to run before ranking, or a student contact would consume a rank and
shift every slot below it. The plan applies the guard in `parent_candidates` and
leaves the `parents_typed` join alone, so the model joins
`stg_finalsite__contacts` twice. The spec's intent — one condition, no
`not exists` — is preserved.

**Placeholder scan.** The only placeholder is `<your_dev_schema>` in Task 4 Step
3, which is the implementer's own dbt target schema and cannot be known in
advance.

**Type consistency.** `contact_slot` is a string everywhere, produced by
`concat('contact_', cast(row_number() ... as string))` in Task 2 and matched as
`contact\_%` / `emergency\_%` in Tasks 3 and 4. The backslash escapes the
underscore, which is a single-character wildcard in BigQuery `LIKE`; without it
`contact_1` and a hypothetical `contactX1` both match.
`int_finalsite__contacts__households` exposes `finalsite_enrollment_id` and
`household_id`, matching its use in Task 2 Step 4 and in the unit-test fixture.
