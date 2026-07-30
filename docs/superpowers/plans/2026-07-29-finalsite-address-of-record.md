# Finalsite Student Address of Record Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the Focus `ADDRESS` feed's street address from the student's
own Finalsite household linkage, falling back to their primary contact's only
when the student's side is not decisive, and withhold an address entirely when
neither side resolves to exactly one complete address.

**Architecture:** Two new models in the `finalsite` source package —
`stg_finalsite__contact_households` (flattens the `households` array to one row
per contact-household, exactly parallel to the existing
`stg_finalsite__contact_relationships`) and
`int_finalsite__student_address_of_record` (applies the two-step resolution rule
and flags the residual). `kipptaf` gets a four-region `union_relations` wrapper
over the intermediate, and `rpt_focus__addresses` becomes a thin projection over
that wrapper instead of reading `stg_finalsite__contacts.address_*`
(`households[safe_offset(0)]`).

**Tech Stack:** dbt-core 1.11.x on BigQuery, `dbt_utils`, Dagster+ for
orchestration, `uv` for every Python/dbt invocation, trunk (sqlfluff / sqlfmt /
yamllint / markdownlint) for linting.

**Spec:**
`docs/superpowers/specs/2026-07-29-finalsite-address-of-record-design.md`

**Refs:** [#4613](https://github.com/TEAMSchools/teamster/issues/4613) (the
bug), [#4616](https://github.com/TEAMSchools/teamster/issues/4616) /
[#4617](https://github.com/TEAMSchools/teamster/issues/4617) (out-of-scope
follow-ups), [#4618](https://github.com/TEAMSchools/teamster/pull/4618) (the
Phase 2 draft PR, currently docs-only).

## Global Constraints

- **Address identity is `address_1`, `address_2`, `city`, `state`, `zip`** —
  five fields. `address_2` is included: an apartment difference is a different
  mailing address. `country` is NOT part of the identity.
- **"Complete" means `address_1`, `city`, `state`, and `zip` are all non-null.**
  `address_2` is not required; it is legitimately null.
- **Resolution order:** student's own households first; primary contact's
  households only if the student's side does not yield exactly one distinct
  complete address; otherwise emit no address and flag the student.
- **Every emitted address is complete by construction** — the rule only selects
  among complete candidates. Downstream needs no completeness filter of its own.
- **The phone comes from the primary contact**, not the student. The student's
  own `phone_1_number` is null for 1,497 of 1,498 enrolled Miami students while
  1,414 primary contacts carry one, and the kippmiami import-once gate never
  checked phone — a student-sourced phone would bake a permanently blank phone
  into Focus.
- **`int_finalsite__student_address_of_record` grain: one row per contact that
  has a `primary` relationship.** `relationships.primary` is a per-record
  singleton that is `true` or NULL (never `false`), and only child/student
  records carry it, so `where is_primary` selects exactly the student records.
- **SIS-agnostic** — no enrollment, status, or academic-year filter in the
  package layer. Receivers scope downstream.
- **Two PRs, package first** (`src/dbt/CLAUDE.md` → _kipptaf source consumers of
  district columns_). Shipping kipptaf first fails CI deterministically: the
  `zz_stg_*` staging copies would not carry the new model.
- **All `dbt` and `python` invocations go through `uv run`.** Never bare `dbt` /
  `python`.
- **Do not run `trunk fmt` or `trunk check` casually** — the pre-commit hook
  formats. But DO run `.trunk/tools/trunk check --force --no-fix </dev/null` on
  changed `.sql` / `.yml` / `.md` before pushing: sqlfluff, yamllint, and
  markdownlint fire only at pre-push and CI.
- **Staging-layer tests MUST set `config: severity: error`** — the project
  default is `warn`.
- **Generic tests require `arguments:` nesting** (dbt 1.11+).
- **Unit-test `given` / `expect` dict scalars are UNQUOTED**, except strings
  that would parse as numbers or have leading zeros (zips, `+1`-prefixed phones)
  — those must be quoted.

---

## Preconditions verified against `main`

These were confirmed at plan-writing time. Re-confirm cheaply before Task 1; if
any has drifted, stop and reconcile with the spec rather than coding around it.

- **The superseded primary-contact-anchor implementation is NOT on `main`.** It
  was reverted by `c2de7ab8a`; the branch
  `cbini/fix/claude-finalsite-address-primary-contact-anchor` now differs from
  `main` only by the spec file. So:
  - `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql` on `main`
    is the **pre-superseded** version — it reads
    `stg_finalsite__contacts.address_*` and `phone_1_number` directly, with **no
    `p1` self-join and no four-column completeness filter**. The spec's "the
    `p1` self-join and the four-column completeness filter both go away"
    describes the reverted branch state, not `main`. There is nothing to remove;
    the file is rewritten wholesale in Task 5.
  - The `src/dbt/kipptaf/CLAUDE.md` "finalsite→focus exception" paragraph
    already reads "kipptaf `rpt_focus__*` are desired-state". The spec's "doc
    reversion" is **already done**. No edit is needed there.
- **The kippmiami `#4320` completeness gate stays.**
  `src/dbt/kippmiami/models/extracts/focus/rpt_focus__addresses.sql` keeps its
  `address / city / state / zipcode is not null` anti-join guard — after this
  change it becomes the only such gate, which is what the spec intends. **Do not
  touch that file.**
- **`status = 'enrolled'` scoping is the Focus-extract convention.**
  `rpt_focus__demographics` filters `c.status = 'enrolled'`;
  `rpt_focus__contacts` joins the student's own `stg_finalsite__contacts` as
  `stu` for `stu.status = 'enrolled'`. The spec's three-join description
  (wrapper + lifecycle + id-attributes) omits it, but dropping it would widen
  the feed to accepted / in-progress / assigned-school students. Task 5
  therefore keeps a join to `stg_finalsite__contacts` **solely for `status`**.
  The spec's measured basis ("the 1,498-student enrolled Miami feed population")
  assumes this filter is present.
- **Spec deviation, already approved:** `primary_contact_phone` is added to
  `int_finalsite__student_address_of_record`. The spec argues the phone must be
  the primary contact's but lists no phone column on the intermediate and no
  phone source in `rpt_focus__addresses`. The intermediate already resolves the
  primary contact, so it is the cheapest correct home for it.
- **Spec internal inconsistency to reconcile at validation time, not invent:**
  the Measured-effect breakdown says **37** students have no `primary`
  relationship; the Scope-boundary section says **35**. Task 6 measures the real
  number; do not hard-code either.

---

## File Structure

### Phase 1 — `finalsite` package

| File                                                                                                | Responsibility                                                                                                                                               |
| --------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/dbt/finalsite/models/api/staging/stg_finalsite__contact_households.sql`                        | Flatten `contacts.households` to one row per (contact, household); normalize the address fields; derive `is_complete_address`.                               |
| `src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_households.yml`             | Contract columns, grain uniqueness test, `not_null` on both key columns, PII tags.                                                                           |
| `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql`            | Apply the two-step resolution rule; emit the resolved address, its source, the resolution status, the two candidate counts, and the primary contact's phone. |
| `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml` | Column docs, grain uniqueness, `accepted_values` on the two enum columns, the completeness-guarantee expression test, four unit tests, PII tags.             |
| `src/dbt/finalsite/CLAUDE.md`                                                                       | Add both models to the model-structure inventory.                                                                                                            |

### Phase 2 — `kipptaf`

| File                                                                                                    | Responsibility                                                                                 |
| ------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml`                                               | Declare the new package model as a Camden source.                                              |
| `src/dbt/kipptaf/models/finalsite/sources-kippmiami.yml`                                                | Same, Miami.                                                                                   |
| `src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml`                                               | Same, Newark.                                                                                  |
| `src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml`                                             | Same, Paterson.                                                                                |
| `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql`            | Four-region `union_relations` passthrough + `_dbt_source_project`.                             |
| `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_address_of_record.yml` | Wrapper description, grain tests, model-level `contains_pii`.                                  |
| `src/dbt/kipptaf/CLAUDE.md`                                                                             | Add the wrapper to the "Finalsite contact unions" inventory and record that it includes Miami. |
| `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql`                                        | Rewrite to project the wrapper; filter to resolved rows.                                       |
| `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml`                             | Updated descriptions + rewritten unit test.                                                    |
| `docs/reference/finalsite-focus-import.md`                                                              | Ops-facing: document the new "held back because Finalsite has more than one address" reason.   |

---

## Phase 1 — package PR (`finalsite`)

### Task 0: Branch setup

**Files:** none (git/gh only).

- [ ] **Step 1: Ask the user before creating anything**

Per `CLAUDE.md`, branch creation requires the user's decision. Ask, in one
message, and wait:

- Worktree or branch switch?
- Anchor the Phase 1 branch to
  [#4613](https://github.com/TEAMSchools/teamster/issues/4613) (the existing
  bug), or open a fresh issue, or no issue?

Do not proceed until answered. The auto-classifier cannot see `AskUserQuestion`
answers — after they answer, re-confirm their choice in plain text **in the same
turn as the git command**, or the write is denied.

- [ ] **Step 2: Create the branch (worktree form shown)**

Anchored to #4613:

```bash
gh issue develop 4613 --name cbini/feat/claude-finalsite-contact-households
git worktree add \
  /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contact-households \
  cbini/feat/claude-finalsite-contact-households
```

If the user declined an issue:

```bash
git worktree add -b cbini/feat/claude-finalsite-contact-households \
  /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contact-households \
  origin/main
```

- [ ] **Step 3: Install dbt packages in the new worktree**

A fresh worktree has no `dbt_packages/`.

```bash
uv run dbt deps \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contact-households/src/dbt/kippmiami
```

- [ ] **Step 4: Confirm the dev copy of the `contacts` external exists**

Package models have no resolvable vars standalone — everything is built through
a consuming district project-dir (`kippmiami`, the Focus consumer). The `dev`
target resolves the `finalsite` source to
`zz_<GITHUB_USER>_kippmiami_finalsite`; if that external is missing, stage your
own copy (personal schema — not classifier-blocked):

```bash
uv run dbt run-operation stage_external_sources \
  --args "select: finalsite.contacts" \
  --vars '{ext_full_refresh: true}' \
  --target dev \
  --project-dir /workspaces/teamster/.worktrees/cbini/feat/claude-finalsite-contact-households/src/dbt/kippmiami
```

> **Path discipline for every remaining step.** `WORKTREE` below means the
> absolute worktree path. Use `git -C "$WORKTREE"` for every git call and
> `--project-dir "$WORKTREE"/src/dbt/<project>` for every dbt call.
> Read/Edit/Write must target `"$WORKTREE"/<path>`, never
> `/workspaces/teamster/<path>` — editing the main checkout silently leaves the
> worktree unchanged and dirties `main`. IDE Pyright/SQL diagnostics on worktree
> files are false-positive-prone; trust `uv run` executed against the worktree.

---

### Task 1: `stg_finalsite__contact_households`

**Files:**

- Create:
  `src/dbt/finalsite/models/api/staging/stg_finalsite__contact_households.sql`
- Create:
  `src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_households.yml`
- Modify: `src/dbt/finalsite/CLAUDE.md` (the `api/staging` inventory line)

**Interfaces:**

- Consumes: `source("finalsite", "contacts")` — the Avro external. Relevant
  fields: `id` (STRING) and `households` (repeated
  `STRUCT<id, address_1, address_2, city, state, zip, country>`, all STRING).
- Produces, for Task 2: a table at grain
  `(finalsite_enrollment_id, household_id)` with columns
  `finalsite_enrollment_id STRING`, `household_id STRING`, `address_1 STRING`,
  `address_2 STRING`, `city STRING`, `state STRING`, `zip STRING`,
  `country STRING`, `is_complete_address BOOLEAN`.

- [ ] **Step 1: Write the model SQL**

Create
`"$WORKTREE"/src/dbt/finalsite/models/api/staging/stg_finalsite__contact_households.sql`:

```sql
with
    households_normalized as (
        -- the same normalization stg_finalsite__contacts applies to its scalar
        -- address columns: Finalsite emits empty strings (not null) and
        -- mixed-case states. Blank -> null; uppercase the state code.
        select
            c.id as finalsite_enrollment_id,

            h.id as household_id,
            h.country,

            nullif(trim(h.address_1), '') as address_1,
            nullif(trim(h.address_2), '') as address_2,
            nullif(trim(h.city), '') as city,
            nullif(upper(trim(h.state)), '') as state,
            nullif(trim(h.zip), '') as zip,
        from {{ source("finalsite", "contacts") }} as c
        cross join unnest(c.households) as h
    )

select
    finalsite_enrollment_id,
    household_id,
    address_1,
    address_2,
    city,
    state,
    zip,
    country,

    -- address_2 is legitimately null (no apartment line), so it is not part of
    -- completeness. Everything needed to mail a letter is.
    (
        address_1 is not null
        and city is not null
        and state is not null
        and zip is not null
    ) as is_complete_address,
from households_normalized
```

Notes for the implementer:

- `households` is an array on **every** contact record, students and adults
  alike. This model does not distinguish them; that happens in Task 2.
- Do **not** filter `where h.id is not null`. The `not_null` test in Step 2 is
  the intended loud failure if Finalsite ever emits one.
- The `nullif(upper(trim(...)))` nesting is copied verbatim from
  `stg_finalsite__contacts.sql:45`, which is the accepted precedent.
- ST06 column ordering: plain columns grouped by source table in join order (`c`
  then `h`, blank line between), then the nested functions; the logical
  (`is_complete_address`) goes last in the outer select.

- [ ] **Step 2: Write the properties YAML**

Create
`"$WORKTREE"/src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_households.yml`:

```yaml
models:
  - name: stg_finalsite__contact_households
    description:
      One row per (contact, household) — the households attached to each
      Finalsite contact, unnested from the `households` array. Every contact
      record carries households, students and adults alike, and a household
      carries only an id plus an address; membership has no roles. This is the
      only place per-household addresses are exposed — the `household_ids` array
      on `stg_finalsite__contacts` carries ids without addresses, and that
      model's scalar `address_*` columns are the first array element only.
      Address values carry the same blank-to-null and state-uppercasing
      normalization `stg_finalsite__contacts` applies.
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - finalsite_enrollment_id
              - household_id
          config:
            severity: error
    columns:
      - name: finalsite_enrollment_id
        data_type: string
        description:
          Finalsite contact UUID of the contact this household belongs to.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: household_id
        data_type: string
        description:
          Finalsite household UUID; unique within a contact. Shared across the
          contacts that belong to the same household.
        data_tests:
          - not_null:
              config:
                severity: error
      - name: address_1
        data_type: string
        description: Street address line 1; blank normalized to null.
        config:
          meta:
            contains_pii: true
      - name: address_2
        data_type: string
        description:
          Street address line 2 (apartment or unit); blank normalized to null.
          Legitimately null when the household has no unit line.
        config:
          meta:
            contains_pii: true
      - name: city
        data_type: string
        description: City; blank normalized to null.
        config:
          meta:
            contains_pii: true
      - name: state
        data_type: string
        description: State code, uppercased; blank normalized to null.
      - name: zip
        data_type: string
        description: ZIP code; blank normalized to null.
        config:
          meta:
            contains_pii: true
      - name: country
        data_type: string
        description:
          Country as Finalsite stores it, passed through unnormalized. Not part
          of the address identity used to compare households.
      - name: is_complete_address
        data_type: boolean
        description:
          Whether this household carries a mailable address — `address_1`,
          `city`, `state`, and `zip` all non-null. `address_2` is not required.
```

> **PII note:** `stg_finalsite__contacts` carries the same address columns
> **untagged**. That is a pre-existing gap and is out of scope here — do not
> retrofit it in this PR. New models get tagged correctly.

- [ ] **Step 3: Build the model and run its tests**

```bash
uv run dbt build \
  --select stg_finalsite__contact_households \
  --project-dir "$WORKTREE"/src/dbt/kippmiami \
  --target dev \
  --defer \
  --state target/prod
```

Expected: model builds; the uniqueness and two `not_null` tests PASS. A
contract-enforced model needs a real `dbt build` (not a `SELECT`) — the
`assert_columns_equivalent` check only runs inside the CTAS.

- [ ] **Step 4: Confirm the grain and row count against the spec**

The spec measured 8,440 rows with zero duplicate `(contact, household)` pairs
and zero null household ids. Query your dev table (dataset
`zz_<GITHUB_USER>_kippmiami_finalsite`) via the BigQuery MCP:

```sql
select
    count(*) as rows_total,
    count(distinct concat(finalsite_enrollment_id, '|', household_id)) as pairs,
    countif(household_id is null) as null_household_ids,
    countif(is_complete_address) as complete_rows,
from `teamster-332318`.zz_<GITHUB_USER>_kippmiami_finalsite.stg_finalsite__contact_households
```

Expected: `rows_total = pairs`, `null_household_ids = 0`. `rows_total` near
8,440 — Finalsite data moves, so treat a modest drift as normal and a large one
(say ±20%) as a signal to stop and re-measure the spec's other figures before
continuing.

- [ ] **Step 5: Update the package CLAUDE.md inventory**

In `"$WORKTREE"/src/dbt/finalsite/CLAUDE.md`, change the `api/staging` inventory
sentence from:

```text
`api/staging`: `stg_finalsite__contacts`,
`stg_finalsite__contact_relationships`. `sftp/staging`:
`stg_finalsite__status_report`.
```

to:

```text
`api/staging`: `stg_finalsite__contacts`,
`stg_finalsite__contact_relationships`,
`stg_finalsite__contact_households`. `sftp/staging`:
`stg_finalsite__status_report`.
```

- [ ] **Step 6: Lint the changed files**

```bash
cd "$WORKTREE" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/finalsite/models/api/staging/stg_finalsite__contact_households.sql \
  src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_households.yml \
  src/dbt/finalsite/CLAUDE.md </dev/null
```

The `trunk` binary lives only in the main repo (`.trunk/tools/` is gitignored),
so invoke it by absolute path with cwd set to the worktree. `--force` is
required — without it a committed file is diff-skipped and markdownlint/sqlfluff
under-report.

- [ ] **Step 7: Commit**

```bash
git -C "$WORKTREE" add -u
git -C "$WORKTREE" add \
  src/dbt/finalsite/models/api/staging/stg_finalsite__contact_households.sql \
  src/dbt/finalsite/models/api/staging/properties/stg_finalsite__contact_households.yml
git -C "$WORKTREE" commit -m "feat(dbt): flatten Finalsite contact households"
```

---

### Task 2: `int_finalsite__student_address_of_record`

**Files:**

- Create:
  `src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql`
- Create:
  `src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml`
- Modify: `src/dbt/finalsite/CLAUDE.md` (the `api/intermediate` inventory list)

**Interfaces:**

- Consumes:
  - `ref("stg_finalsite__contact_households")` from Task 1 — columns
    `finalsite_enrollment_id`, `address_1`, `address_2`, `city`, `state`, `zip`,
    `country`, `is_complete_address`.
  - `ref("stg_finalsite__contact_relationships")` — columns
    `finalsite_enrollment_id`, `rel_id`, `is_primary`.
  - `ref("stg_finalsite__contacts")` — columns `finalsite_enrollment_id`,
    `phone_1_number`.
- Produces, for Tasks 4 and 5: a table at grain `finalsite_enrollment_id` with
  columns `finalsite_enrollment_id STRING`, `student_candidate_count INT64`,
  `primary_contact_candidate_count INT64`, `address_source STRING` (nullable),
  `address_1 STRING`, `address_2 STRING`, `city STRING`, `state STRING`,
  `zip STRING`, `country STRING`, `primary_contact_phone STRING`,
  `resolution_status STRING`.
  - `address_source` ∈ {`student_household`, `primary_contact_household`, NULL}.
  - `resolution_status` ∈ {`student_household`, `primary_contact_household`,
    `ambiguous`}.
  - `address_source is not null` ⟺ the six address fields are populated and
    complete. This is the invariant `rpt_focus__addresses` filters on.

- [ ] **Step 1: Write the model SQL**

Create
`"$WORKTREE"/src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql`:

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

    address_candidates as (
        -- One row per (contact, distinct complete address). Address identity is
        -- the five mailing fields including address_2 — an apartment difference
        -- is a different mailing address. country is not part of the identity
        -- (Finalsite stores it unnormalized and no consumer reads it), so a
        -- single min() carries it through rather than letting it split one
        -- address into two candidates.
        select
            finalsite_enrollment_id,
            address_1,
            address_2,
            city,
            state,
            zip,

            min(country) as country,
        from {{ ref("stg_finalsite__contact_households") }}
        where is_complete_address
        group by finalsite_enrollment_id, address_1, address_2, city, state, zip
    ),

    candidate_counts as (
        select
            finalsite_enrollment_id,

            count(*) as candidate_count,
        from address_candidates
        group by finalsite_enrollment_id
    ),

    counted as (
        select
            spc.finalsite_enrollment_id,
            spc.primary_contact_id,

            coalesce(sc.candidate_count, 0) as student_candidate_count,
            coalesce(pcc.candidate_count, 0) as primary_contact_candidate_count,
        from student_primary_contacts as spc
        left join
            candidate_counts as sc
            on spc.finalsite_enrollment_id = sc.finalsite_enrollment_id
        left join
            candidate_counts as pcc
            on spc.primary_contact_id = pcc.finalsite_enrollment_id
    ),

    sourced as (
        -- The student's household linkage is a subset of their primary contact's
        -- and is the disambiguating signal, so it is tried first. Parents carry
        -- more household rows than students, so anchoring on the parent
        -- unconditionally would move the pick onto the record with more
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

    pc.phone_1_number as primary_contact_phone,

    coalesce(s.address_source, 'ambiguous') as resolution_status,
from sourced as s
left join
    address_candidates as a on s.address_contact_id = a.finalsite_enrollment_id
left join
    {{ ref("stg_finalsite__contacts") }} as pc
    on s.primary_contact_id = pc.finalsite_enrollment_id
```

Notes for the implementer:

- The `address_candidates` join cannot fan out: it is joined on the contact
  whose `candidate_count` is exactly 1. When `address_contact_id` is null
  (ambiguous), nothing matches and the address fields stay null.
- `ambiguous` covers both "more than one candidate" and "no complete address
  anywhere". The two candidate counts distinguish them, which is what an Ops
  worklist needs. Do not add a fourth `resolution_status` value.
- Students with **no** `primary` relationship are absent from this model
  entirely, not flagged. Representing them would need a student-versus-adult
  discriminator the package layer does not have. Tracked in
  [#4617](https://github.com/TEAMSchools/teamster/issues/4617).
- `min(country) as country` is a single aggregate over one column, so the
  "independent mins can pick from different rows" hazard does not apply.
- ST09: ON-clause predicates put the earlier-referenced alias on the left.

- [ ] **Step 2: Write the properties YAML with the four unit tests**

Create
`"$WORKTREE"/src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml`:

```yaml
models:
  - name: int_finalsite__student_address_of_record
    description:
      One row per Finalsite student record — the student's resolved address of
      record, or a flag when it cannot be resolved. Grain is
      `finalsite_enrollment_id` for contacts that carry a `primary`
      relationship, which is how a student record is identified without reaching
      for a SIS-specific field; contacts with no primary link are absent
      entirely. Resolution takes the student's own household linkage when it
      yields exactly one distinct complete address, falls back to their primary
      contact's household linkage when it does, and otherwise emits no address.
      Address identity is `address_1`, `address_2`, `city`, `state`, and `zip` —
      an apartment difference counts as a different address. Every emitted
      address is complete by construction, so consumers need no completeness
      filter of their own. SIS-agnostic — no enrollment, status, or
      academic-year scoping; receivers filter downstream.
    data_tests:
      - dbt_utils.expression_is_true:
          arguments:
            expression: |
              address_1 is null
              or (city is not null and state is not null and zip is not null)
          config:
            severity: error
    columns:
      - name: finalsite_enrollment_id
        data_type: string
        description: Finalsite contact UUID of the student; the grain.
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
          How the address was resolved — `student_household`,
          `primary_contact_household`, or `ambiguous`. `ambiguous` covers both a
          student whose records offer several competing complete addresses and
          one whose records hold no complete address at all; the candidate
          counts distinguish the two.
        data_tests:
          - accepted_values:
              arguments:
                values:
                  - student_household
                  - primary_contact_household
                  - ambiguous
              config:
                severity: error
      - name: address_source
        data_type: string
        description:
          Which record supplied the address — `student_household` or
          `primary_contact_household`. Null when no address was resolved; a
          non-null value guarantees the address fields are populated and
          complete.
        data_tests:
          - accepted_values:
              arguments:
                values:
                  - student_household
                  - primary_contact_household
              config:
                severity: error
      - name: student_candidate_count
        data_type: int64
        description:
          Number of distinct complete addresses on the student's own household
          linkage. One means the student's own records decide the address; more
          than one means the pick falls through to the primary contact; zero
          means the student is linked to no household with a mailable address.
      - name: primary_contact_candidate_count
        data_type: int64
        description:
          Number of distinct complete addresses on the primary contact's
          household linkage. Used only when the student's own count is not one.
      - name: address_1
        data_type: string
        description:
          Street address line 1 of the resolved address; null when unresolved.
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
        description: City of the resolved address; null when unresolved.
        config:
          meta:
            contains_pii: true
      - name: state
        data_type: string
        description:
          State code of the resolved address, uppercased; null when unresolved.
      - name: zip
        data_type: string
        description: ZIP code of the resolved address; null when unresolved.
        config:
          meta:
            contains_pii: true
      - name: country
        data_type: string
        description:
          Country of the resolved address as Finalsite stores it. Not part of
          the address identity, so it is carried through rather than compared.
      - name: primary_contact_phone
        data_type: string
        description:
          The primary contact's first phone number in E.164 form. A phone is a
          contact attribute rather than a household one, so it is independent of
          which household supplied the address, and it is populated even for an
          unresolved address. Sourced from the parent because student records
          almost never carry a phone.
        config:
          meta:
            contains_pii: true

unit_tests:
  - name: test_address_of_record_student_linkage_decisive
    description:
      A student whose own household linkage yields exactly one distinct complete
      address resolves from it, even though their primary contact carries two.
      Duplicate household rows carrying the same address collapse to one
      candidate, and an incomplete household is not a candidate at all.
    model: int_finalsite__student_address_of_record
    given:
      - input: ref('stg_finalsite__contact_relationships')
        rows:
          - { finalsite_enrollment_id: stu-1, rel_id: par-1, is_primary: true }
          - { finalsite_enrollment_id: par-1, rel_id: stu-1, is_primary: null }
      - input: ref('stg_finalsite__contact_households')
        format: sql
        rows: |
          select
            'stu-1' as finalsite_enrollment_id,
            'hh-1' as household_id,
            '123 Main St' as address_1,
            cast(null as string) as address_2,
            'Miami' as city,
            'FL' as state,
            '33101' as zip,
            'US' as country,
            true as is_complete_address
          union all
          select 'stu-1', 'hh-2', '123 Main St', null, 'Miami', 'FL', '33101',
            'US', true
          union all
          select 'stu-1', 'hh-3', '9 Nowhere Ln', null, 'Miami', 'FL', null,
            'US', false
          union all
          select 'par-1', 'hh-1', '123 Main St', null, 'Miami', 'FL', '33101',
            'US', true
          union all
          select 'par-1', 'hh-4', '400 Elsewhere Ave', null, 'Miami', 'FL',
            '33199', 'US', true
      - input: ref('stg_finalsite__contacts')
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
            primary_contact_phone: "+13055550101",
            resolution_status: student_household,
          }

  - name: test_address_of_record_primary_contact_fallback
    description:
      A student whose own linkage offers two competing complete addresses falls
      through to their primary contact, whose linkage yields exactly one.
    model: int_finalsite__student_address_of_record
    given:
      - input: ref('stg_finalsite__contact_relationships')
        rows:
          - { finalsite_enrollment_id: stu-2, rel_id: par-2, is_primary: true }
      - input: ref('stg_finalsite__contact_households')
        format: sql
        rows: |
          select
            'stu-2' as finalsite_enrollment_id,
            'hh-5' as household_id,
            '456 Oak Ave' as address_1,
            cast(null as string) as address_2,
            'Miami' as city,
            'FL' as state,
            '33102' as zip,
            'US' as country,
            true as is_complete_address
          union all
          select 'stu-2', 'hh-6', '789 Pine Rd', null, 'Miami', 'FL', '33105',
            'US', true
          union all
          select 'par-2', 'hh-7', '111 Palm Way', null, 'Miami', 'FL', '33103',
            'US', true
      - input: ref('stg_finalsite__contacts')
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
            primary_contact_phone: "+13055550102",
            resolution_status: primary_contact_household,
          }

  - name: test_address_of_record_both_sides_ambiguous
    description:
      When neither the student nor their primary contact resolves to exactly one
      complete address, no address is emitted and the row is flagged ambiguous.
      The student's two candidates differ only by apartment line, confirming
      `address_2` participates in the address identity.
    model: int_finalsite__student_address_of_record
    given:
      - input: ref('stg_finalsite__contact_relationships')
        rows:
          - { finalsite_enrollment_id: stu-3, rel_id: par-3, is_primary: true }
      - input: ref('stg_finalsite__contact_households')
        format: sql
        rows: |
          select
            'stu-3' as finalsite_enrollment_id,
            'hh-8' as household_id,
            '222 Bay St' as address_1,
            'Apt 1' as address_2,
            'Miami' as city,
            'FL' as state,
            '33106' as zip,
            'US' as country,
            true as is_complete_address
          union all
          select 'stu-3', 'hh-9', '222 Bay St', 'Apt 2', 'Miami', 'FL', '33106',
            'US', true
          union all
          select 'par-3', 'hh-8', '222 Bay St', 'Apt 1', 'Miami', 'FL', '33106',
            'US', true
          union all
          select 'par-3', 'hh-9', '222 Bay St', 'Apt 2', 'Miami', 'FL', '33106',
            'US', true
          union all
          select 'par-3', 'hh-10', '333 Gull Ct', null, 'Miami', 'FL', '33107',
            'US', true
      - input: ref('stg_finalsite__contacts')
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
            primary_contact_phone: "+13055550103",
            resolution_status: ambiguous,
          }

  - name: test_address_of_record_no_student_households
    description:
      A student linked to no household at all falls through to their primary
      contact, and a student whose only household is incomplete is flagged
      ambiguous with both candidate counts at zero.
    model: int_finalsite__student_address_of_record
    given:
      - input: ref('stg_finalsite__contact_relationships')
        rows:
          - { finalsite_enrollment_id: stu-4, rel_id: par-4, is_primary: true }
          - { finalsite_enrollment_id: stu-5, rel_id: par-5, is_primary: true }
      - input: ref('stg_finalsite__contact_households')
        format: sql
        rows: |
          select
            'par-4' as finalsite_enrollment_id,
            'hh-11' as household_id,
            '555 Coral Dr' as address_1,
            'Unit 7' as address_2,
            'Miami' as city,
            'FL' as state,
            '33104' as zip,
            'US' as country,
            true as is_complete_address
          union all
          select 'stu-5', 'hh-12', '666 Reef Ln', null, 'Miami', 'FL', null,
            'US', false
          union all
          select 'par-5', 'hh-13', null, null, 'Miami', 'FL', '33108', 'US',
            false
      - input: ref('stg_finalsite__contacts')
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
            primary_contact_phone: "+13055550104",
            resolution_status: primary_contact_household,
          }
        - {
            finalsite_enrollment_id: stu-5,
            student_candidate_count: 0,
            primary_contact_candidate_count: 0,
            address_source: null,
            address_1: null,
            address_2: null,
            city: null,
            state: null,
            zip: null,
            country: null,
            primary_contact_phone: "+13055550105",
            resolution_status: ambiguous,
          }
```

Notes for the implementer:

- `stg_finalsite__contact_households` is created in this PR, so dbt cannot
  introspect its schema — every fixture for it must use `format: sql`. Do not
  "fix" a fixture failure by building the model into your dev schema first: that
  makes the dict form pass locally while CI still fails.
- `stg_finalsite__contact_relationships` and `stg_finalsite__contacts` exist in
  prod and are mocked with scalar columns only, so dict form works for them.
- Every `expect` row lists every asserted column — dbt builds them as
  `UNION ALL` and does not null-fill omitted keys.
- The `is_primary: null` reverse-link row in the first test proves the
  `where is_primary` filter keeps parent records out of the grain.

- [ ] **Step 3: Run the unit tests and verify they fail for the right reason**

```bash
uv run dbt test \
  --select "int_finalsite__student_address_of_record,test_type:unit" \
  --project-dir "$WORKTREE"/src/dbt/kippmiami \
  --target dev \
  --defer \
  --state target/prod
```

Run this **before** Step 1's SQL exists if you are working strictly test-first;
expected FAIL is
`Compilation Error ... depends on a node named 'int_finalsite__student_address_of_record' which was not found`.
If the SQL is already written, expect all four to PASS here and treat any
failure as a real defect in the rule. Note `dbt build` no-ops on a unit-only
selector in dbt-core 1.11.x — use `dbt test`.

- [ ] **Step 4: Build the model and run its data tests**

```bash
uv run dbt build \
  --select int_finalsite__student_address_of_record \
  --project-dir "$WORKTREE"/src/dbt/kippmiami \
  --target dev \
  --defer \
  --state target/prod
```

Expected: builds; `unique`, `not_null`, both `accepted_values`, and the
`expression_is_true` completeness guarantee all PASS.

- [ ] **Step 5: Measure the resolution distribution against the spec**

Query your dev table via the BigQuery MCP:

```sql
select
    resolution_status,
    count(*) as students,
    countif(address_1 is not null) as with_address,
from
    `teamster-332318`.zz_<GITHUB_USER>_kippmiami_finalsite.int_finalsite__student_address_of_record
group by resolution_status
```

Expected shape: `with_address` equals `students` for the two resolved statuses
and is 0 for `ambiguous`. This model is unscoped (all Finalsite student records,
not just enrolled Miami), so the totals will exceed the spec's 1,498 — the
enrolled-scoped comparison happens in Task 6. What must hold here is the
invariant, not the counts.

- [ ] **Step 6: Update the package CLAUDE.md inventory**

In `"$WORKTREE"/src/dbt/finalsite/CLAUDE.md`, add a bullet to the
`api/intermediate models:` list, after the `int_finalsite__enrollment_lifecycle`
bullet:

```markdown
- `int_finalsite__student_address_of_record` — one row per student record (a
  contact carrying a `primary` relationship) with the resolved address of
  record: the student's own household linkage when it yields exactly one
  distinct complete address, else their primary contact's when it does, else no
  address and an `ambiguous` flag. Also carries the primary contact's phone,
  since student records almost never hold one.
```

- [ ] **Step 7: Lint the changed files**

```bash
cd "$WORKTREE" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml \
  src/dbt/finalsite/CLAUDE.md </dev/null
```

- [ ] **Step 8: Commit**

```bash
git -C "$WORKTREE" add -u
git -C "$WORKTREE" add \
  src/dbt/finalsite/models/api/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/finalsite/models/api/intermediate/properties/int_finalsite__student_address_of_record.yml
git -C "$WORKTREE" commit -m "feat(dbt): resolve the Finalsite student address of record"
```

- [ ] **Step 9: Push and open the package PR**

```bash
git -C "$WORKTREE" push -u origin cbini/feat/claude-finalsite-contact-households
```

Open the PR with `mcp__github__create_pull_request`, body from
`.github/pull_request_template.md`, and `Refs #4613` in the body (not `Closes` —
#4613 closes with the Phase 2 PR, which is what actually changes the feed).

Expected CI: **`dbt Cloud` goes green trivially, not as validation.** dbt Cloud
CI builds only the `kipptaf` project, and this PR touches neither a kipptaf
model nor a kipptaf-consumed source column set, so it selects zero models (~30s
no-op). The real exercise of these models is Dagster's dbt step on the branch
deployment. Confirm the Dagster deploy check runs green —
`dagster-cloud-deploy / deploy` emits one same-named check-run **per code
location** (~5); wait for all of them.

- [ ] **Step 10: Wait for merge, then for prod materialization**

Phase 2 cannot start until `int_finalsite__student_address_of_record` exists as
a prod relation in all four district datasets
(`kipp{camden,miami,newark,paterson}_finalsite`). After the squash merge, wait
for Dagster to materialize it, then confirm:

```sql
select table_schema, table_name
from `teamster-332318`.region-us.INFORMATION_SCHEMA.TABLES
where table_name = 'int_finalsite__student_address_of_record'
```

Expected: four rows, one per district dataset. **Stop here** if fewer — Phase 2
will fail deterministically.

---

## Phase 2 — kipptaf PR ([#4618](https://github.com/TEAMSchools/teamster/pull/4618))

Phase 2 lands on `cbini/fix/claude-finalsite-address-primary-contact-anchor`,
which already carries the spec and is open as draft PR #4618. Its worktree is
`/workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor`
— call it `WT2` below. Before starting:

```bash
git -C "$WT2" fetch origin main && git -C "$WT2" merge origin/main --no-edit
uv run dbt deps --project-dir "$WT2"/src/dbt/kipptaf
```

The PR title still names the superseded approach ("anchor the Focus ADDRESS feed
on the student primary contact"). Retitle it in Task 6.

### Task 3: kipptaf sources and the union wrapper

**Files:**

- Modify: `src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml`
- Modify: `src/dbt/kipptaf/models/finalsite/sources-kippmiami.yml`
- Modify: `src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml`
- Modify: `src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml`
- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql`
- Create:
  `src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_address_of_record.yml`
- Modify: `src/dbt/kipptaf/CLAUDE.md` (the "Finalsite contact unions" section)

**Interfaces:**

- Consumes: the Task 2 package model, now materialized in all four district
  datasets, via
  `source("<region>_finalsite", "int_finalsite__student_address_of_record")`.
- Produces, for Task 5: a kipptaf view
  `int_finalsite__student_address_of_record` with the same twelve columns as the
  package model, plus `_dbt_source_relation` (from `union_relations`) and
  `_dbt_source_project`. Grain remains `finalsite_enrollment_id`, globally
  unique across regions.

- [ ] **Step 1: Add the source entry to all four region files**

Append this block to the `tables:` list in each of the four
`sources-kipp<region>.yml` files, substituting that file's region for
`kippcamden` in the `asset_key` list:

```yaml
- name: int_finalsite__student_address_of_record
  config:
    meta:
      dagster:
        group: finalsite
        asset_key:
          - kippcamden
          - finalsite
          - int_finalsite__student_address_of_record
```

The `asset_key` first element is the district code location — `kippcamden`,
`kippmiami`, `kippnewark`, `kipppaterson` respectively. All four files already
carry the `staging` → `zz_stg_` schema branch, so no schema edit is needed.

Verify each write landed as intended (a malformed nested block can be accepted
silently):

```bash
grep -c "int_finalsite__student_address_of_record" \
  "$WT2"/src/dbt/kipptaf/models/finalsite/sources-kipp*.yml
```

Expected: `2` per file (the `name:` and the `asset_key` leaf).

- [ ] **Step 2: Write the union wrapper**

Create
`"$WT2"/src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql`:

```sql
-- All four regions are unioned here, including Miami — following
-- int_finalsite__contact_id_attributes rather than
-- int_finalsite__student_contacts. The latter excludes Miami to avoid
-- double-counting contacts against the PowerSchool branch of
-- int_students__contacts; no equivalent risk exists for an address model, and
-- Focus is the Miami consumer.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippcamden_finalsite",
                        "int_finalsite__student_address_of_record",
                    ),
                    source(
                        "kippmiami_finalsite",
                        "int_finalsite__student_address_of_record",
                    ),
                    source(
                        "kippnewark_finalsite",
                        "int_finalsite__student_address_of_record",
                    ),
                    source(
                        "kipppaterson_finalsite",
                        "int_finalsite__student_address_of_record",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
```

- [ ] **Step 3: Write the wrapper properties YAML**

Create
`"$WT2"/src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_address_of_record.yml`:

```yaml
models:
  - name: int_finalsite__student_address_of_record
    description:
      Network-wide union of the per-region Finalsite
      `int_finalsite__student_address_of_record` models — one row per Finalsite
      student record with its resolved address of record, or an `ambiguous` flag
      when neither the student's nor their primary contact's household linkage
      yields exactly one complete address. Includes all four regions; Focus is
      the Miami consumer and the NJ regions carry no Focus student id, so the
      `rpt_focus__*` filter on `focus_student_id_prefixed` keeps their rows out
      of the Focus feeds. Column documentation lives on the package model.
      Carries `_dbt_source_relation`.
    config:
      meta:
        contains_pii: true
    columns:
      - name: finalsite_enrollment_id
        data_type: string
        description: Finalsite contact UUID of the student; the grain.
        data_tests:
          - unique
          - not_null
```

Notes for the implementer:

- `config.meta.contains_pii` does **not** travel through `source()`, so the
  wrapper re-declares it. Model level suffices for a `select *` passthrough.
- Per `src/dbt/kipptaf/CLAUDE.md`, kipptaf-level union views are functionally
  intermediates: no contract block, no `materialized: table`. The grain tests
  here mirror `int_finalsite__contact_id_attributes.yml`, which is the direct
  precedent.

- [ ] **Step 4: Seed the staging copies (hand to the user)**

`union_relations` resolves its column list at compile time from the source
relations' `INFORMATION_SCHEMA`. Under `--target staging` (what dbt Cloud CI
uses) the sources point at `zz_stg_<district>_finalsite`, which will not yet
hold the new model — the wrapper would compile to an empty column expansion and
every downstream reference would fail.

`dbt clone --target staging` recreates shared `zz_stg_*` relations, so it is
classifier-blocked and **must be run by the user**. Give them this, one per
district:

```bash
uv run dbt clone \
  --select int_finalsite__student_address_of_record \
  --target staging \
  --state target/prod \
  --full-refresh \
  --project-dir src/dbt/kippcamden
```

Repeat with `--project-dir src/dbt/kippmiami`, `src/dbt/kippnewark`,
`src/dbt/kipppaterson`. Serialize them — running all four in parallel exhausts
BigQuery's `INFORMATION_SCHEMA` rate quota.

- [ ] **Step 5: Confirm the wrapper expands to real columns**

```bash
uv run dbt compile \
  --select int_finalsite__student_address_of_record \
  --project-dir "$WT2"/src/dbt/kipptaf \
  --target staging
```

Then read
`"$WT2"/src/dbt/kipptaf/target/compiled/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql`
and confirm the twelve model columns are listed per region branch. **An empty
expansion still compiles clean** — reading the compiled SQL is the only check
that catches it. If columns are missing, Step 4's seeding did not take.

- [ ] **Step 6: Update the kipptaf CLAUDE.md union inventory**

In `"$WT2"/src/dbt/kipptaf/CLAUDE.md`, under `### Finalsite contact unions`,
change the opening sentence from:

```text
`int_finalsite__student_contacts` / `int_finalsite__contact_id_attributes` are
kipptaf `union_relations` views over per-region finalsite sources.
```

to:

```text
`int_finalsite__student_contacts` / `int_finalsite__contact_id_attributes` /
`int_finalsite__student_address_of_record` are kipptaf `union_relations` views
over per-region finalsite sources.
```

Then extend the "Union CUTOVER regions, not merely api-enabled ones" bullet's
last sentence so the Miami-inclusion rule covers both models:

```text
`int_finalsite__contact_id_attributes` and
`int_finalsite__student_address_of_record` DO include Miami — Focus consumes
them, and the `rpt_focus__*` filter `focus_student_id_prefixed is not null`, so
Newark rows (null prefix) never reach the Focus feeds.
```

- [ ] **Step 7: Lint and commit**

```bash
cd "$WT2" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/finalsite/sources-kippcamden.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippmiami.yml \
  src/dbt/kipptaf/models/finalsite/sources-kippnewark.yml \
  src/dbt/kipptaf/models/finalsite/sources-kipppaterson.yml \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_address_of_record.yml \
  src/dbt/kipptaf/CLAUDE.md </dev/null
```

```bash
git -C "$WT2" add -u
git -C "$WT2" add \
  src/dbt/kipptaf/models/finalsite/intermediate/int_finalsite__student_address_of_record.sql \
  src/dbt/kipptaf/models/finalsite/intermediate/properties/int_finalsite__student_address_of_record.yml
git -C "$WT2" commit -m "feat(dbt): union the Finalsite address of record network-wide"
```

Do **not** push yet — bundle with Task 5 so dbt Cloud CI runs once against the
complete change. A push mid-run cancels and restarts the dbt job.

---

### Task 4: Rework `rpt_focus__addresses`

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql` (full
  rewrite of the `from`/`join`/`where` block and the address column sources)
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml`
  (model + column descriptions, and the unit test replaced)

**Interfaces:**

- Consumes: `ref("int_finalsite__student_address_of_record")` from Task 3
  (`finalsite_enrollment_id`, `address_1`, `address_2`, `city`, `state`, `zip`,
  `primary_contact_phone`, `address_source`); `ref("stg_finalsite__contacts")`
  (`finalsite_enrollment_id`, `status`) — the kipptaf-level union view, used
  **only** for the enrolled filter; `ref("int_finalsite__enrollment_lifecycle")`
  (`finalsite_enrollment_id`); `ref("int_finalsite__contact_id_attributes")`
  (`finalsite_enrollment_id`, `focus_student_id_prefixed`).
- Produces: unchanged 12-column `ADDRESS_LAYOUT` contract — `student_id`,
  `address`, `address2`, `city`, `state`, `zipcode`, `phone`, `mailing`,
  `mail_address`, `mail_address2`, `mail_city`, `mail_state`. The contract does
  not change; only the rows and the values behind `address*` / `phone` do. The
  kippmiami wrapper needs no edit.

- [ ] **Step 1: Rewrite the unit test first, and watch it fail**

Replace the entire `unit_tests:` block at the bottom of
`"$WT2"/src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml`
with:

```yaml
unit_tests:
  - name: test_addresses_shape
    description:
      Verifies the 12-column ADDRESS layout for a single student — STUDENT_ID
      comes from int_finalsite__contact_id_attributes, the address columns and
      the phone come from int_finalsite__student_address_of_record, and the
      mailing columns are always null. A second student is enrolled with a
      resolved address but has status applied, confirming the enrolled-only
      filter excludes them. A third is enrolled with an unresolved (ambiguous)
      address, confirming unresolved rows are withheld rather than exported
      blank.
    model: rpt_focus__addresses
    given:
      - input: ref('int_finalsite__student_address_of_record')
        format: sql
        rows: |
          select
            'enr-001' as finalsite_enrollment_id,
            '123 Main St' as address_1,
            'Apt 4B' as address_2,
            'Miami' as city,
            'FL' as state,
            '33101' as zip,
            '+13055550100' as primary_contact_phone,
            'student_household' as address_source
          union all
          select 'enr-002', '456 Oak Ave', null, 'Miami', 'FL', '33102',
            '+13055550200', 'primary_contact_household'
          union all
          select 'enr-003', null, null, null, null, null, '+13055550300', null
      - input: ref('stg_finalsite__contacts')
        rows:
          - { finalsite_enrollment_id: enr-001, status: enrolled }
          - { finalsite_enrollment_id: enr-002, status: applied }
          - { finalsite_enrollment_id: enr-003, status: enrolled }
      - input: ref('int_finalsite__enrollment_lifecycle')
        rows:
          - { finalsite_enrollment_id: enr-001 }
          - { finalsite_enrollment_id: enr-002 }
          - { finalsite_enrollment_id: enr-003 }
      - input: ref('int_finalsite__contact_id_attributes')
        format: sql
        rows: |
          select
            'enr-001' as finalsite_enrollment_id,
            '84004004004' as focus_student_id_prefixed
          union all
          select 'enr-002', '84004004005'
          union all
          select 'enr-003', '84004004006'
    expect:
      rows:
        - {
            student_id: "84004004004",
            address: 123 Main St,
            address2: Apt 4B,
            city: Miami,
            state: FL,
            zipcode: "33101",
            phone: "+13055550100",
            mailing: null,
            mail_address: null,
            mail_address2: null,
            mail_city: null,
            mail_state: null,
          }
```

`int_finalsite__student_address_of_record` is created in this same PR, so its
fixture must use `format: sql` — dict form would fail introspection.

Run it:

```bash
uv run dbt test \
  --select "rpt_focus__addresses,test_type:unit" \
  --project-dir "$WT2"/src/dbt/kipptaf \
  --target staging
```

Expected: FAIL. The model still reads `c.address_1` / `c.phone_1_number` from
`stg_finalsite__contacts`, which the fixture no longer supplies, so the failure
is a compilation or column error naming those columns.

- [ ] **Step 2: Rewrite the model SQL**

Replace the entire contents of
`"$WT2"/src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql` with:

```sql
-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus ADDRESS contract
select
    ida.focus_student_id_prefixed as student_id,

    aor.address_1 as address,
    aor.address_2 as address2,
    aor.city,
    aor.state,
    aor.zip as zipcode,
    aor.primary_contact_phone as phone,

    cast(null as string) as mailing,
    cast(null as string) as mail_address,
    cast(null as string) as mail_address2,
    cast(null as string) as mail_city,
    cast(null as string) as mail_state,
from {{ ref("int_finalsite__student_address_of_record") }} as aor
inner join
    {{ ref("stg_finalsite__contacts") }} as stu
    on aor.finalsite_enrollment_id = stu.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on aor.finalsite_enrollment_id = l.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on aor.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
-- an unresolved address is withheld, not exported blank: the feed is
-- import-once with no overwrite path, so a blank or wrong address of record is
-- permanent. address_source is not null guarantees a complete address.
where stu.status = 'enrolled' and aor.address_source is not null
```

Notes for the implementer:

- `stg_finalsite__contacts` is joined **only** for `status`. That mirrors
  `rpt_focus__contacts`, which joins the student's own contact record as `stu`
  for the same reason. Dropping it would widen the feed to accepted /
  in-progress / assigned-school students.
- No completeness filter here. The intermediate emits only complete addresses;
  the kippmiami `#4320` anti-join gate stays as the single remaining guard.
- Every join is on `finalsite_enrollment_id`, which is a globally unique UUID,
  so no `_dbt_source_project` predicate is needed.

- [ ] **Step 3: Run the unit test again**

```bash
uv run dbt test \
  --select "rpt_focus__addresses,test_type:unit" \
  --project-dir "$WT2"/src/dbt/kipptaf \
  --target staging
```

Expected: PASS, 1 row returned (`enr-001` only).

If the dict fixture for `stg_finalsite__contacts` fails introspection, the
`zz_stg_kipptaf_finalsite` copy is missing — add `--defer --state target/prod`
to the command rather than converting the fixture to `format: sql`.

- [ ] **Step 4: Run the whole `extracts.focus` unit-test directory**

Sibling models mock the same `ref()`s, so a single-model run misses breakage CI
will catch.

```bash
uv run dbt test \
  --select "test_type:unit,extracts.focus" \
  --project-dir "$WT2"/src/dbt/kipptaf \
  --target staging
```

Expected: all PASS. `rpt_focus__contacts` / `_demographics` still mock
`stg_finalsite__contacts` for their own columns — those fixtures are untouched
by this change and must stay green.

- [ ] **Step 5: Update the model and column descriptions**

In the `models:` block of
`"$WT2"/src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml`:

Replace the model `description:` with:

```yaml
description:
  One row per enrolled Finalsite student whose address of record resolved,
  reshaped into the Focus `ADDRESS` SFTP template layout. Joins
  `int_finalsite__student_address_of_record` to
  `int_finalsite__enrollment_lifecycle` (the in-scope filter; grain =
  `finalsite_enrollment_id`), to `stg_finalsite__contacts` for the student's
  enrolled status, and to `int_finalsite__contact_id_attributes` for the Focus
  student ID, excluding contacts without a minted Focus id. Students whose
  address could not be resolved to a single complete household address are
  withheld rather than exported blank — the feed is import-once, so a blank or
  wrong address would be permanent. Produces 12 columns in `ADDRESS_LAYOUT`
  order. Focus column header casing (`STUDENT_ID`, `ADDRESS`, etc.) is applied
  at transport time via `file_config.format.header_replacements`; dbt column
  names remain lowercase snake_case. Mailing address columns are always null —
  Focus does not receive a separate mailing address from Finalsite.
```

Replace these five column descriptions (leave `data_type` and `data_tests`
untouched):

```yaml
- name: address
  data_type: string
  description:
    Street address line 1 of the student's resolved address of record.
- name: address2
  data_type: string
  description:
    Street address line 2 (apartment or unit) of the student's resolved address
    of record; null when the household has no unit line.
- name: city
  data_type: string
  description: City of the student's resolved address of record.
- name: state
  data_type: string
  description: State code of the student's resolved address of record.
- name: zipcode
  data_type: string
  description: ZIP code of the student's resolved address of record.
- name: phone
  data_type: string
  description:
    The student's primary contact's first phone number. A phone is a contact
    attribute rather than a household one, and student records almost never
    carry one.
```

- [ ] **Step 6: Lint and commit**

```bash
cd "$WT2" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql \
  src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml </dev/null
```

sqlfluff ST06 is suppressed on the first line only; the trailing-comma (CV03),
88-char, and ST09 rules still apply.

```bash
git -C "$WT2" add -u
git -C "$WT2" commit -m "fix(dbt): source the Focus ADDRESS feed from the resolved address of record"
```

---

### Task 5: Ops documentation

**Files:**

- Modify: `docs/reference/finalsite-focus-import.md` (two sections)

**Interfaces:** none — prose only. This is the Ops-facing explanation of why a
student may now get no Focus address for a reason other than a blank one.

- [ ] **Step 1: Extend the hold-back section**

In `"$WT2"/docs/reference/finalsite-focus-import.md`, in the
`### Blank addresses and nameless contacts are held back` section, replace the
**Addresses** bullet:

```markdown
- **Addresses** — a student's address is sent only once street, city, state, and
  ZIP are all present. A student with a blank or partial address is skipped that
  run and flows the first run the full address exists in Finalsite.
```

with:

```markdown
- **Addresses** — a student's address is sent only once Finalsite points to
  exactly one complete address for them. Two things can hold it back. The
  address may be **incomplete** — street, city, state, and ZIP must all be
  present. Or Finalsite may hold **more than one** address for the student: the
  pipeline reads the households the student is linked to, falls back to the
  households their primary contact is linked to when the student's own linkage
  is not decisive, and sends nothing when neither narrows to one. Either way the
  student is skipped that run and flows the first run Finalsite resolves to a
  single complete address.
```

Leave the **Contacts** bullet that follows it untouched.

Then replace the admonition that closes the section:

```markdown
> **A student can be enrolled in Focus with no address yet.** That is expected
> when Finalsite has no complete address for them — enter the address in
> Finalsite and it flows on the next run. (Demographics is not held back for
> completeness this way; a student's demographics import as soon as the student
> is enrolled in Finalsite and new to Focus.)
```

with:

```markdown
> **A student can be enrolled in Focus with no address yet.** That is expected
> when Finalsite has no complete address for them, or when it has several and
> none is marked as the one to use. Fix it in Finalsite — fill in the missing
> address, or retire the household the family no longer lives at — and it flows
> on the next run. (Demographics is not held back this way; a student's
> demographics import as soon as the student is enrolled in Finalsite and new to
> Focus.)
```

- [ ] **Step 2: Extend the enrollment-team watch list**

In the `## What the enrollment team should watch for` section, replace:

```markdown
- **A complete address is required before it imports.** A student with a blank
  or partial address in Finalsite gets no address in Focus — by design, since an
  empty one would lock in. Enter the full street/city/state/ZIP in Finalsite and
  it flows next run; likewise a contact needs a name before it is sent.
```

with:

```markdown
- **One complete address is required before it imports.** A student whose
  Finalsite address is blank or partial gets no address in Focus — by design,
  since an empty one would lock in. So does a student Finalsite links to more
  than one address, where there is no way to tell which one to send. Enter the
  full street/city/state/ZIP, or retire the household the family has moved out
  of, and it flows next run; likewise a contact needs a name before it is sent.
- **Duplicate households are the common cause of a missing address.** A family
  with two live household records in Finalsite — usually an old address and a
  current one — cannot be resolved automatically, because Finalsite does not
  record which of the two came first. Retiring the stale household fixes it for
  that family.
```

- [ ] **Step 3: Lint and commit**

markdownlint (MD001 heading increments, MD029 ordered lists, MD036
pseudo-headings, MD040 fence languages) fires only at pre-push and CI, not the
pre-commit `fmt` hook.

```bash
cd "$WT2" && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/reference/finalsite-focus-import.md </dev/null
```

```bash
git -C "$WT2" add -u
git -C "$WT2" commit -m "docs: explain why a Finalsite address can be held back as unresolved"
```

---

### Task 6: Validate against prod, then ship

**Files:** none (validation, PR metadata, and CI only).

- [ ] **Step 1: Compile the extract against prod and measure the real effect**

`--target prod` **builds** are classifier-blocked; `compile` is not (no
warehouse write).

```bash
uv run dbt compile \
  --select rpt_focus__addresses int_finalsite__student_address_of_record \
  --project-dir "$WT2"/src/dbt/kipptaf \
  --target prod
```

Reading the compiled SQL confirms every `ref()` resolved against prod schemas.
Then run this self-contained query against prod via the BigQuery MCP — it
applies the same three predicates the extract does, giving the enrolled-Miami
basis the spec measured:

```sql
with
    aor as (
        select
            aor.finalsite_enrollment_id,
            aor.resolution_status,
            aor.student_candidate_count,
            aor.primary_contact_candidate_count,
        from `teamster-332318`.kipptaf_finalsite.int_finalsite__student_address_of_record as aor
        inner join
            `teamster-332318`.kipptaf_finalsite.stg_finalsite__contacts as stu
            on aor.finalsite_enrollment_id = stu.finalsite_enrollment_id
        inner join
            `teamster-332318`.kipptaf_finalsite.int_finalsite__contact_id_attributes as ida
            on aor.finalsite_enrollment_id = ida.finalsite_enrollment_id
            and ida.focus_student_id_prefixed is not null
        where stu.status = 'enrolled'
    )

select
    resolution_status,
    count(*) as students,
    countif(student_candidate_count = 0 and primary_contact_candidate_count = 0)
        as no_complete_address_anywhere,
from aor
group by resolution_status
```

Compare to the spec's Measured-effect table (1,498-student enrolled Miami
basis): **1,291 exported** (1,275 `student_household` + 16
`primary_contact_household`), **147 `ambiguous`**, of which **23** hold no
complete address anywhere. Also count the enrolled students **absent** from the
model (no `primary` relationship) — the spec says 37 in one place and 35 in
another; report the measured number and reconcile the spec text rather than
picking one.

A modest drift is expected (Finalsite data moves, and the Miami
duplicate-household cleanup may have progressed). A large one — say `ambiguous`
well above 200, or `exported` below 1,100 — means stop and re-derive before
merging. This design is a deliberate trade, not a strict improvement: it
eliminates all 164 arbitrary picks production exports today, adds 32 students
production misses, and withholds 147 it cannot resolve (~115 net fewer rows
reaching Focus). Withholding is recoverable; a wrong import-once guess is not.

- [ ] **Step 2: Retitle and un-draft the PR**

The PR title still names the superseded approach.

```bash
gh api -X PATCH repos/TEAMSchools/teamster/pulls/4618 \
  -f title='fix(dbt): resolve the Focus ADDRESS feed from the student address of record'
```

Rewrite the body from `.github/pull_request_template.md` with `Closes #4613`,
and note the Phase 1 package PR number as a merged prerequisite. Edit the body
via `gh api -X PATCH ... -F body=@<file>` (raw, no re-encoding) rather than
`mcp__github__update_pull_request`, which double-encodes existing entities.
Avoid `&`, `"`, and `<...>` tokens in the title and in code spans — the GitHub
MCP write tools strip and entity-encode them.

- [ ] **Step 3: Push once and wait for CI**

Check dbt Cloud is in a terminal state before pushing — a push mid-run cancels
and restarts it.

```bash
git -C "$WT2" push
```

Then mark ready for review so `claude-review` fires (it triggers on `opened` /
`ready_for_review` only, never on `synchronize` — it will **not** re-run after a
fix push).

- [ ] **Step 4: Confirm both CI surfaces**

A PR's CI lives on two disjoint surfaces. dbt Cloud is a commit **status**;
Trunk / CodeQL / `claude` are **check runs**.

```bash
gh pr checks 4618 --json name,bucket,state
```

Expected: dbt Cloud `Build - CI (Modified)` green with `state:modified+`
selecting the four sources, the wrapper, `rpt_focus__addresses`, and its unit
tests. Editing a `sources-kipp*.yml` marks the whole source `state:modified`, so
the rebuild fans out across every kipptaf model reading finalsite — expect a
wide run and treat pre-existing warn-level test noise as such.

After it passes, fetch warnings before declaring done:
`mcp__dbt__get_job_run_error(run_id=<ci_run>, warning_only=true)`. Local
`relationships` warnings absent from CI are stale-dev `--defer` drift; ignore.
Warnings unchanged from `main` are pre-existing — search for an existing tracker
before filing.

- [ ] **Step 5: Process review feedback**

Invoke `superpowers:receiving-code-review` **before** acting on any
`claude-review` finding. That bot asserts repo conventions that are not always
enforced — verify each claim, including its `file:line` citations, with
`git grep` against existing models before complying or replying.

Note `claude-review` may leave two comments (a "Reviewing…" stub and the
findings) or edit the stub in place minutes **after** the check-run reports
`success`. Fetch all issue comments and read the newest/longest; gate on the
comment's `updated_at` growing, not on the check-run conclusion.

- [ ] **Step 6: Merge and verify the feed**

Squash merge. `mergeable_state: blocked` with all checks green means it is
awaiting the CODEOWNERS review approval for `src/dbt/` (analytics-engineers),
not a CI failure.

After merge and the next Dagster materialization, confirm the kippmiami extract:

```sql
select count(*) as rows_to_import
from `teamster-332318`.kippmiami_extracts.rpt_focus__addresses
```

This is the import-once anti-join output, so it counts only students Focus does
not already have an address for — a small number, and zero once the backlog
clears. Sanity-check that every row has a non-null `address`, `city`, `state`,
and `zipcode`.

---

## Out of scope

Do not expand into these; each has its own tracker.

- Retiring duplicate household records in Finalsite (~150 families hold two live
  household rows). This is the real fix for the residual 147 and belongs with
  Miami ops.
- Asserting the `is_primary` singleton at its source —
  [#4616](https://github.com/TEAMSchools/teamster/issues/4616).
- Students with no `primary` relationship, who are absent from the model rather
  than flagged — [#4617](https://github.com/TEAMSchools/teamster/issues/4617).
- Whether `household_1_id` still earns its place in the
  `stg_finalsite__contacts` contract. This design leaves that model's scalar
  `address_*` columns with no consumer in the Focus address path, which
  strengthens the case for revisiting them — but `rpt_focus__contacts` and
  `int_finalsite__student_contacts.household_address` still read them, so they
  stay.
- Retrofitting `contains_pii` onto `stg_finalsite__contacts`' address columns.
- The kippmiami `#4320` completeness gate, and the kipptaf CLAUDE.md
  "finalsite→focus exception" paragraph — both already correct on `main`.
