# Focus ADDRESS Primary-Contact Anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Source the Focus ADDRESS feed's address and phone from the student's
primary contact instead of an arbitrary `households[safe_offset(0)]` pick.

**Architecture:** One kipptaf model changes. `rpt_focus__addresses` gains a
`primary_contact` CTE over `stg_finalsite__contact_relationships` filtered to
`is_primary`, then self-joins `stg_finalsite__contacts` on that contact's id and
projects the contact's address columns. Both new joins are `inner`, so students
with no primary contact are excluded rather than falling back.
`stg_finalsite__contacts` is not touched — its `address_*` columns keep meaning
"this contact's own address," which its two other consumers depend on.

**Tech Stack:** dbt (BigQuery), dbt unit tests, sqlfluff / markdownlint via
trunk, `uv` for all Python and dbt invocation.

Design spec:
`docs/superpowers/specs/2026-07-29-finalsite-focus-address-primary-contact-anchor-design.md`

## Global Constraints

- **Worktree:** all work happens in
  `/workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor`.
  Every `git` call uses `git -C <worktree>`; every `dbt` call uses
  `--project-dir <worktree>/src/dbt/kipptaf`. Never edit
  `/workspaces/teamster/src/...` for this work — that dirties `main`.
- **Branch:** `cbini/fix/claude-finalsite-address-primary-contact-anchor`,
  linked to issue #4613. Do not push to `main`.
- **Python and dbt:** always `uv run`, never bare `dbt` or `python`.
- **Fresh worktree needs `dbt deps`** before any build or test — a new worktree
  has no `dbt_packages/`.
- **Contract is unchanged.** The 12 output columns and their names and types
  stay exactly as they are. No column is added, removed, or renamed. The
  kippmiami `rpt_focus__addresses` wrapper is not modified.
- **The seven address fields must resolve to one household row.** Never select
  address components from different sources — that assembles an address that
  exists nowhere.
- **SQL conventions** (`src/dbt/CLAUDE.md`): trailing commas in `SELECT`, single
  quotes, 88-char lines, no `ORDER BY`, no `QUALIFY`, no subqueries against
  tables or CTEs, max one level of function nesting, `ON` predicates list the
  earlier-referenced table on the left (sqlfluff ST09).
- **Unit-test fixtures:** mirror the existing file's quoting exactly. Dict
  scalars are unquoted except strings that must not be type-coerced (`zip`,
  phone numbers, `student_id`), which stay quoted as they already are.
- **Do not run `trunk fmt`.** The pre-commit hook formats. Run
  `trunk check --force` only where this plan says to.

---

## File Structure

| File                                                                        | Change | Responsibility                                                           |
| --------------------------------------------------------------------------- | ------ | ------------------------------------------------------------------------ |
| `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql`            | Modify | Resolves the primary contact and projects that contact's address         |
| `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml` | Modify | Model and column descriptions, plus the `test_addresses_shape` unit test |

No new files. No other model, property file, or project config changes.

---

## Task 1: Anchor the address and phone on the student's primary contact

**Files:**

- Modify: `src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql`
  (whole file, currently 37 lines)
- Modify:
  `src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml`
  (model `description`, the `address` / `address2` / `city` / `state` /
  `zipcode` / `phone` column descriptions, and the `unit_tests` block)

**Interfaces:**

- Consumes: `stg_finalsite__contact_relationships` columns
  `finalsite_enrollment_id` (the student), `rel_id` (the related contact),
  `is_primary` (BOOLEAN, `true` or NULL, never `false`).
  `stg_finalsite__contacts` columns `finalsite_enrollment_id`, `address_1`,
  `address_2`, `city`, `state`, `zip`, `phone_1_number`, `status`.
- Produces: no interface change. `rpt_focus__addresses` keeps its 12 columns in
  `ADDRESS_LAYOUT` order, so the kippmiami wrapper and the SFTP transport config
  are unaffected.

- [ ] **Step 1: Install dbt packages in the worktree**

A fresh worktree has no `dbt_packages/`, and every later step fails without it.

Run:

```bash
uv run dbt deps --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor/src/dbt/kipptaf
```

Expected: reports installed packages, no error.

- [ ] **Step 2: Rewrite the `unit_tests` block to express the new behavior**

Replace the ENTIRE existing `unit_tests:` block at the bottom of
`src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml` with
this. It keeps the original student `enr-001` and the `applied`-status exclusion
case `enr-002`, moves the exported address and phone onto new primary-contact
rows, gives the students deliberately different address values that must NOT
appear in the output, and adds `enr-003` to prove the strict anchor excludes a
student with no primary relationship.

```yaml
unit_tests:
  - name: test_addresses_shape
    description:
      Verifies the 12-column ADDRESS layout for a single student — STUDENT_ID is
      sourced from int_finalsite__contact_id_attributes, the address and phone
      come from the student's primary contact rather than from the student's own
      record, and mailing columns are always null. The student rows carry
      different address values that must not appear in the output, proving the
      anchor. A second student has status 'applied' (not 'enrolled') and a
      minted Focus id, confirming the enrolled-only filter excludes them. A
      third student is enrolled with a minted Focus id and a complete address of
      their own, but no relationship flagged primary — confirming the strict
      anchor excludes them rather than falling back to their own address.
    model: rpt_focus__addresses
    given:
      - input: ref('stg_finalsite__contact_relationships')
        rows:
          - {
              finalsite_enrollment_id: enr-001,
              rel_id: enr-par-001,
              is_primary: true,
            }
          - {
              finalsite_enrollment_id: enr-002,
              rel_id: enr-par-002,
              is_primary: true,
            }
          - {
              finalsite_enrollment_id: enr-003,
              rel_id: enr-par-003,
              is_primary: null,
            }
      - input: ref('stg_finalsite__contacts')
        rows:
          - {
              finalsite_enrollment_id: enr-001,
              address_1: 999 Student St,
              address_2: null,
              city: Hialeah,
              state: FL,
              zip: "33010",
              phone_1_number: "+13055559999",
              status: enrolled,
            }
          - { finalsite_enrollment_id: enr-002, status: applied }
          - {
              finalsite_enrollment_id: enr-003,
              address_1: 888 Orphan Ave,
              address_2: null,
              city: Miami,
              state: FL,
              zip: "33103",
              phone_1_number: "+13055559888",
              status: enrolled,
            }
          - {
              finalsite_enrollment_id: enr-par-001,
              address_1: 123 Main St,
              address_2: Apt 4B,
              city: Miami,
              state: FL,
              zip: "33101",
              phone_1_number: "+13055550100",
              status: null,
            }
          - {
              finalsite_enrollment_id: enr-par-002,
              address_1: 456 Oak Ave,
              address_2: null,
              city: Miami,
              state: FL,
              zip: "33102",
              phone_1_number: "+13055550200",
              status: null,
            }
          - {
              finalsite_enrollment_id: enr-par-003,
              address_1: 789 Pine Rd,
              address_2: null,
              city: Miami,
              state: FL,
              zip: "33104",
              phone_1_number: "+13055550300",
              status: null,
            }
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

- [ ] **Step 3: Run the unit test to verify it fails**

The selector intersects the model with `test_type:unit` so ONLY the unit test
runs. A bare `--select rpt_focus__addresses` would also pull in the `unique` and
`not_null` data tests, which need the model materialized in the dev schema and
would error for an unrelated reason.

```bash
uv run dbt test --select "rpt_focus__addresses,test_type:unit" --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor/src/dbt/kipptaf
```

Expected: `test_addresses_shape` does NOT pass. Either failure mode is a valid
red state, and which one you get depends on how dbt validates the fixture:

- A compilation error naming `stg_finalsite__contact_relationships` as an input
  that is not a dependency of the model — the old model does not `ref()` it yet.
- Or an assertion diff, because the old model reads the student's own row, so
  `address` returns `999 Student St` rather than `123 Main St` and `enr-003`
  yields an unexpected extra row.

If it PASSES, stop — the fixture is not exercising the change and the assertions
need fixing before writing any model code.

- [ ] **Step 4: Rewrite the model**

Replace the ENTIRE contents of
`src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql` with:

```sql
with
    -- The student's address of record is their primary contact's address.
    -- `households[safe_offset(0)]` is an arbitrary array position, not
    -- Finalsite's primary-household designation — that designation is set in the
    -- UI and absent from every field the API exposes, so it cannot be
    -- reproduced. See #4613.
    --
    -- Parent 1 is the relationship Finalsite flags `primary`. That flag is a
    -- per-student singleton and is never `false` — it is `true` or NULL — so a
    -- bare `where is_primary` selects exactly the Parent 1 row. A second primary
    -- on one student would duplicate `student_id` and fail this model's `unique`
    -- test, which is the intended loud failure.
    primary_contact as (
        select finalsite_enrollment_id, rel_id,
        from {{ ref("stg_finalsite__contact_relationships") }}
        where is_primary
    )

-- trunk-ignore(sqlfluff/ST06): column order fixed by Focus ADDRESS contract
select
    ida.focus_student_id_prefixed as student_id,

    p1.address_1 as address,
    p1.address_2 as address2,
    p1.city,
    p1.state,
    p1.zip as zipcode,
    p1.phone_1_number as phone,

    cast(null as string) as mailing,
    cast(null as string) as mail_address,
    cast(null as string) as mail_address2,
    cast(null as string) as mail_city,
    cast(null as string) as mail_state,
from {{ ref("stg_finalsite__contacts") }} as c
-- inner joins, not left: a student with no primary contact gets no address row.
-- Per Ops a missing primary flag is a Finalsite data-entry gap to fix at the
-- source, not something to infer — matching int_finalsite__student_contacts.
inner join
    primary_contact as pc
    on c.finalsite_enrollment_id = pc.finalsite_enrollment_id
inner join
    {{ ref("stg_finalsite__contacts") }} as p1
    on pc.rel_id = p1.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__enrollment_lifecycle") }} as l
    on c.finalsite_enrollment_id = l.finalsite_enrollment_id
inner join
    {{ ref("int_finalsite__contact_id_attributes") }} as ida
    on c.finalsite_enrollment_id = ida.finalsite_enrollment_id
    and ida.focus_student_id_prefixed is not null
where c.status = 'enrolled'
```

The student's own row `c` is retained for the `status = 'enrolled'` filter and
as the join key to the relationship. Note `pc` is referenced before `p1`, so
`on pc.rel_id = p1.finalsite_enrollment_id` puts the earlier table on the left
as sqlfluff ST09 requires.

- [ ] **Step 5: Run the unit test to verify it passes**

```bash
uv run dbt test --select "rpt_focus__addresses,test_type:unit" --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor/src/dbt/kipptaf
```

Expected: `test_addresses_shape` PASSES. One row out, sourced from
`enr-par-001`; `enr-002` excluded by status and `enr-003` excluded by the strict
anchor.

- [ ] **Step 6: Update the model description**

In `properties/rpt_focus__addresses.yml`, replace the model-level `description:`
value with the text below. It must state the new source, the exclusions, and the
join path. Keep it as an unquoted multi-line scalar — do not introduce a `: `
(colon-space) sequence or start a line with a backtick, both of which break YAML
parsing.

```yaml
description:
  One row per in-scope Finalsite student reshaped into the Focus `ADDRESS` SFTP
  template layout. The address and phone columns are the student's PRIMARY
  CONTACT's, not the student record's own household values — array position does
  not identify Finalsite's primary household and the API does not expose that
  designation, so the primary contact (Parent 1) is the anchor instead. Students
  with no relationship flagged `primary`, and students whose primary contact has
  no address, are excluded rather than falling back to an arbitrary household.
  Joins `stg_finalsite__contacts` to `stg_finalsite__contact_relationships` to
  find the primary contact, back to `stg_finalsite__contacts` for that contact's
  address, to `int_finalsite__enrollment_lifecycle` (the in-scope filter; grain
  = `finalsite_enrollment_id`), then to `int_finalsite__contact_id_attributes`
  for the Focus student ID, excluding contacts without a minted Focus id.
  Produces 12 columns in `ADDRESS_LAYOUT` order. Focus column header casing
  (`STUDENT_ID`, `ADDRESS`, etc.) is applied at transport time via
  `file_config.format.header_replacements`; dbt column names remain lowercase
  snake_case. Mailing address columns are always null — Focus does not receive a
  separate mailing address from Finalsite.
```

- [ ] **Step 7: Update the six sourced column descriptions**

In the same file, replace each of these column `description:` values. The
current text says "from Finalsite," which no longer identifies which record the
value comes from.

```yaml
- name: address
  data_type: string
  description:
    Street address line 1 of the student's primary contact (`address_1` on the
    contact flagged `primary`).
- name: address2
  data_type: string
  description:
    Street address line 2 of the student's primary contact (`address_2`).
- name: city
  data_type: string
  description: City of the student's primary contact.
- name: state
  data_type: string
  description: State of the student's primary contact.
- name: zipcode
  data_type: string
  description: ZIP code of the student's primary contact (`zip`).
- name: phone
  data_type: string
  description:
    Primary phone number of the student's primary contact (`phone_1_number`).
    Sourced from the contact rather than the student record, whose own phone is
    null for nearly every student.
```

Leave `student_id` and the five `mail_*` / `mailing` descriptions untouched —
their sourcing has not changed.

- [ ] **Step 8: Run the whole focus unit-test directory**

Sibling models mock the same refs, so a change here can break their fixtures.
Run the directory, not just this model.

```bash
uv run dbt build --select "test_type:unit,extracts.focus" --target dev \
  --defer --state /workspaces/teamster/src/dbt/kipptaf/target/prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor/src/dbt/kipptaf
```

Expected: all unit tests in `extracts/focus` PASS. `rpt_focus__contacts`,
`rpt_focus__demographics`, `rpt_focus__linked_students`, and
`rpt_focus__student_enrollment` are untouched and should be unaffected — if one
fails, read its error before changing anything, because the likely cause is a
pre-existing failure rather than this change.

- [ ] **Step 9: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor add src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor commit -m "fix(dbt): anchor the Focus ADDRESS feed on the student's primary contact" -m "Sources address and phone from the contact Finalsite flags primary instead of an arbitrary households[safe_offset(0)] pick. Students with no primary relationship are excluded rather than falling back." -m "Refs #4613" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

Expected: the pre-commit `trunk fmt` hook reformats and the commit succeeds. If
the hook rejects the message on a keyword false positive, write the message to
`.claude/scratch/commit-msg.txt` with the Write tool (after `rm -f` on any stale
copy) and use `git commit -F`.

---

## Task 2: Validate the measured effect against production

The spec predicts specific numbers. This task confirms them against real data
before the change ships, because the unit test only proves shape, not scale.

**Files:** none modified. This task produces evidence only.

**Interfaces:**

- Consumes: the Task 1 model.
- Produces: confirmed row counts to put in the PR body.

- [ ] **Step 1: Compile the model against prod**

`dbt compile --target prod` performs no warehouse write and is not blocked.

```bash
uv run dbt compile --select rpt_focus__addresses --target prod \
  --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor/src/dbt/kipptaf
```

Expected: compiles clean. The compiled SQL lands at
`<worktree>/src/dbt/kipptaf/target/compiled/kipptaf/models/extracts/focus/rpt_focus__addresses.sql`
with every `ref()` resolved to a prod relation.

- [ ] **Step 2: Read the compiled SQL and confirm the refs resolved to prod**

Read the compiled file. Confirm the `from` and `join` clauses point at
`kipptaf_finalsite.*` prod relations and NOT at any `zz_` dev or staging schema.
A `zz_` reference means the wrong target was used and the counts in the next
step would be meaningless.

- [ ] **Step 3: Count the new output and compare to the current extract**

Run this via the BigQuery MCP, substituting the compiled SQL for
`{compiled_sql}`. It counts the new row set and the live extract side by side.

```sql
with new_feed as (
    {compiled_sql}
),

current_feed as (
    select student_id, address, address2, city, state, zipcode, phone,
    from `teamster-332318`.kipptaf_extracts.rpt_focus__addresses
)

select
    (select count(*) from new_feed) as new_rows,
    (select count(*) from current_feed) as current_rows,
    (select count(distinct student_id) from new_feed) as new_distinct_students,
    (
        select count(*)
        from new_feed as n
        inner join current_feed as c on n.student_id = c.student_id
        where n.address = c.address and n.zipcode = c.zipcode
    ) as address_unchanged,
    (
        select count(*)
        from new_feed as n
        inner join current_feed as c on n.student_id = c.student_id
        where n.address != c.address or n.zipcode != c.zipcode
    ) as address_changed,
    (
        select count(*)
        from new_feed as n
        left join current_feed as c on n.student_id = c.student_id
        where c.student_id is null
    ) as only_in_new,
    (
        select count(*)
        from current_feed as c
        left join new_feed as n on c.student_id = n.student_id
        where n.student_id is null
    ) as only_in_current,
    (select countif(phone is not null) from new_feed) as new_phones_populated,
    (select countif(phone is not null) from current_feed) as current_phones_populated
```

Expected, allowing small drift because the `contacts` asset repulls daily:

- `new_distinct_students` equals `new_rows` — no grain fan-out from a duplicate
  `primary` relationship. **If these differ, stop and report it**; it means the
  singleton assumption does not hold and the `unique` test will fail in CI.
- `new_rows` near 1,377 and `current_rows` near 1,406.
- `address_changed` near 60, `only_in_new` near 13, `only_in_current` near 42.
- `new_phones_populated` near 1,414 against `current_phones_populated` near 1.

Note the counts here are against the kipptaf desired-state view, which is not
gated by the kippmiami completeness filter, so they will not match the spec's
table exactly. The spec's numbers already account for that gate. What matters is
the direction and rough magnitude, plus the grain check.

- [ ] **Step 4: Record the numbers**

Write the observed counts to `.claude/scratch/4613-validation.md` for use in the
PR body. Do not put any address or phone VALUE in that file or anywhere external
— these are PII. Counts and column names only.

---

## Task 3: Lint, push, and open the pull request

**Files:** none modified.

**Interfaces:**

- Consumes: the Task 1 commit and Task 2 evidence.
- Produces: an open PR referencing #4613.

- [ ] **Step 1: Lint the changed files with `--force`**

The pre-push hook is git-diff-scoped and can miss a sqlfluff violation on
committed lines that CI flags. `--force` is required. The `trunk` binary exists
only in the main repo, so call it by absolute path with cwd set to the worktree.

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/extracts/focus/rpt_focus__addresses.sql src/dbt/kipptaf/models/extracts/focus/properties/rpt_focus__addresses.yml docs/superpowers/plans/2026-07-29-finalsite-focus-address-primary-contact-anchor.md </dev/null
```

Expected: no issues. Fix any sqlfluff finding by adjusting the SQL to the
conventions in Global Constraints — do NOT add a `trunk-ignore` beyond the ST06
one the file already carries without first confirming the rule genuinely cannot
be satisfied.

- [ ] **Step 2: Commit the plan document if it is not yet committed**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor add docs/superpowers/plans/2026-07-29-finalsite-focus-address-primary-contact-anchor.md
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor commit -m "docs: add the Focus ADDRESS primary-contact anchor implementation plan" -m "Refs #4613" -m "Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

Skip if already committed.

- [ ] **Step 3: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-finalsite-address-primary-contact-anchor push -u origin cbini/fix/claude-finalsite-address-primary-contact-anchor
```

Expected: the `trunk-check-pre-push` hook passes and the branch pushes.

- [ ] **Step 4: Open the PR**

Use `.github/pull_request_template.md` as the body structure. Write the body to
a file and pass it with `-F body=@<file>` rather than inline, to avoid shell
quoting problems and the GitHub MCP's HTML sanitization of `<` tokens.

The body must state plainly:

- What changed and why array position was never a valid source.
- That the anchor resolves 11 of 167 ambiguous students, and that roughly 150
  remain an arbitrary pick — this is a semantic fix, not an accuracy fix.
- The coverage change, including that 35 students are dropped for having no
  primary relationship and 7 for having a primary contact with no address.
- That the phone now populates roughly 1,414 records that were permanently blank
  under import-once.
- `Refs #4613`.

Do not include any address or phone value.

```bash
GITHUB_TOKEN= gh api -X POST repos/TEAMSchools/teamster/pulls \
  -f title='fix(dbt): anchor the Focus ADDRESS feed on the student primary contact' \
  -f head=cbini/fix/claude-finalsite-address-primary-contact-anchor \
  -f base=main \
  -F body=@.claude/scratch/4613-pr-body.md
```

- [ ] **Step 5: Verify the stored PR body**

The GitHub API round-trip can mangle body text. Read it back raw and confirm it
matches intent.

```bash
GITHUB_TOKEN= gh api repos/TEAMSchools/teamster/pulls/<pr_number> --jq .body
```

Expected: the body reads as written, with no stripped tokens.

- [ ] **Step 6: Report CI state**

Check BOTH surfaces — they are disjoint. dbt Cloud is a commit status; Trunk,
CodeQL, and `claude` are check runs.

```bash
GITHUB_TOKEN= gh pr checks <pr_number> --json name,bucket,state
```

Report the result. Do not claim the PR is green until every check reaches a
terminal state. `claude-review` fires only on `opened` / `ready_for_review`, so
do not wait for a re-review after any later fix push.

---

## Notes for the implementer

- **This is a kipptaf-only change.** dbt Cloud CI builds kipptaf, so
  `state:modified+` will select `rpt_focus__addresses` and genuinely exercise
  it. No cross-project staging seeding or `zz_stg` clone is needed — no column
  is added and no `source()` column set changes.
- **Expect a `relationships` or row-count warning locally that CI does not
  show.** Local `--defer` against a stale dev copy is a known source of false
  positives in this repo. Trust CI over a local warning of that shape.
- **If the `unique` test on `student_id` fails**, a student has two
  relationships flagged `primary`. That is real upstream data corruption, not a
  bug in this model — the loud failure is intentional. Report it rather than
  adding a tiebreak or a dedupe.
