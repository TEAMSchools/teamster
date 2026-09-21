# Miami Archive Terms and the PowerSchool Terms Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire Miami's frozen PowerSchool archive into `int_students__terms` so
its 492,482 null-`term` membership days resolve, by pushing the PowerSchool
conform down into the `powerschool` package as a union rather than a full join.

**Architecture:** A new package model `int_powerschool__terms_spine` stacks the
raw `terms` rows and the derived quarter rows with `union all`. The full join in
`int_students__terms` merges a matched raw record and its quarter into one row —
840 such rows today — and the union emits them as two, which is safe because no
consumer reads a merged row's two halves together. A kipptaf `union_relations`
wrapper unions that spine across all four districts, including the Miami
archive, which makes the archive's pre-cutover quarters reachable for the first
time. `int_students__terms` then becomes a projection of that wrapper unioned
with the Focus arm, floored at the SIS cutover year so the two arms are disjoint
by year.

**Tech Stack:** dbt (BigQuery), `dbt_utils.union_relations`, Dagster, dbt Cloud
CI, `uv`, trunk.

**Spec:**
[docs/superpowers/specs/2026-09-21-miami-archive-terms-design.md](../specs/2026-09-21-miami-archive-terms-design.md)

## Global Constraints

- **Worktree.** Every path is
  `/workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms/<path>`.
  Every git call is `git -C <that worktree>`. Never bare `git stash`.
- **Never push to `main`.** Feature-branch pushes and PR creation run on this
  session's own credentials.
- **`uv run` always.** Never bare `python`, `dbt`, or `dagster`.
- **dbt in a worktree:**
  `uv run dbt <cmd> --project-dir <worktree>/src/dbt/<project>`. A fresh
  worktree needs `uv run dbt deps --project-dir <worktree>/src/dbt/<project>`
  first, in its own Bash call.
- **`--target prod` builds go to the user.** `compile` and `parse` against prod
  are fine (no warehouse write). A `--target staging` build or
  `dbt clone --target staging` is a shared write needing the user's explicit
  authorization restated in plain text in the message immediately before the
  call, in its own Bash call.
- **Read, never `cat`, for files under `src/dbt/`** — the path-scoped rules load
  on a Read/Edit/Write path match and never on a Bash command string.
- **Lint before every push:**
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree. `--force` is required.
- **Two-PR cross-project rule.** The package model is consumed by kipptaf
  through `source()`, so PR A (package) merges and materializes in all four
  district prod datasets before PR B (kipptaf) is pushed.
- **Column order across the two union branches is positional.** The shared order
  is fixed, once, in Task 1, and is the exact final-select order of today's
  `int_students__terms` minus `_dbt_source_relation` and `_dbt_source_project`:

  ```text
  dcid, name, firstday, lastday, abbreviation, importmap, terminfo_guid,
  psguid, ip_address, whomodifiedtype, transaction_date, id, noofdays,
  yearlycredithrs, termsinyear, portion, autobuildbin, isyearrec,
  periods_per_day, days_per_cycle, attendance_calculation_code, sterms,
  suppresspublicview, whomodifiedid, fiscal_year, term, term_start_date,
  term_end_date, semester, is_current_term, schoolid, yearid, academic_year
  ```

  33 columns. Keeping this order is what makes Task 4 a straight projection.

- **`semester` on the raw branch is deliberately a typed null.**
  `stg_powerschool__terms` carries its own `semester`, but today's
  `powerschool_canonical` CTE does not project it — the output `semester` comes
  only from the quarter side. Preserving that is required for byte-identical NJ
  output.
- **`cast()` is an ST06 "simple target".** Interleaving `cast(null as <type>)`
  with plain column refs in one select list does NOT trip sqlfluff ST06 —
  today's Focus branch already interleaves them with no suppression. No
  `trunk-ignore` is needed for the union branches.
- **Commit messages** end with
  `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`. **PR
  bodies** end with
  `🤖 Generated with [Claude Code](https://claude.com/claude-code)`. PR bodies
  follow `.github/pull_request_template.md` and carry `Refs #5397`.
- **Hook hazard:** never write the bare token `env` in a commit message, PR
  body, issue comment, `AskUserQuestion`, or Bash `description`. Write
  "environment variable". If a `git commit -m` is blocked, Write the message to
  `<session scratchpad>/commit-msg-<slug>.txt` and use `git commit -F <path>`.

---

## File Structure

### PR A — the `powerschool` package

| File                                                                                      | Action | Responsibility                                                                          |
| ----------------------------------------------------------------------------------------- | ------ | --------------------------------------------------------------------------------------- |
| `src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms_spine.sql`            | Create | Full-grain term spine for one district: raw branch `union all` quarter branch, no join. |
| `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__terms_spine.yml` | Create | Description, the two `where`-scoped uniqueness tests, and the unit test.                |

`int_powerschool__terms.sql` is **not touched**, so
`int_powerschool__student_course_grades_spine` — which reads it at quarter grain
and separately unions a `Y1` row off `stg_powerschool__terms` — is untouched.
That is the whole reason this is a new model rather than a widening.

### PR B — kipptaf

| File                                                                                          | Action | Responsibility                                                          |
| --------------------------------------------------------------------------------------------- | ------ | ----------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms_spine.sql`            | Create | Four-district `union_relations` passthrough over the package spine.     |
| `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__terms_spine.yml` | Create | `materialized: table`, matching its retiring sibling.                   |
| `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`                                   | Modify | Add the spine table entry; remove the `int_powerschool__terms` entry.   |
| `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml`                                   | Modify | Same.                                                                   |
| `src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml`                                 | Modify | Same.                                                                   |
| `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml`                                    | Modify | Add the spine table entry; rewrite the false source description.        |
| `src/dbt/kipptaf/models/students/intermediate/int_students__terms.sql`                        | Modify | Collapse to two union branches: the spine wrapper and the Focus arm.    |
| `src/dbt/kipptaf/models/students/intermediate/properties/int_students__terms.yml`             | Modify | Rewrite the description and the ten "For Miami" column docs.            |
| `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms.sql`                  | Delete | Bare `select *` passthrough, zero remaining `ref()`s (#5162 exception). |
| `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__terms.yml`       | Delete | Goes with its model.                                                    |
| `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__terms.yml`            | Modify | Add `enabled: false`. Carries the `rn` window, so disable, not delete.  |

### Facts verified while writing this plan

Do not re-derive these.

- Every relation involved is a `BASE TABLE`, in all four district datasets and
  in `kipptaf_powerschool`. `dbt clone --target staging` is therefore
  metadata-cheap for the Task 7 seeding.
- The district `dbt_project.yml` sets `powerschool: +materialized: table` for
  the whole package, so the new spine materializes as a table per district with
  no per-model config.
- The package's `sis/intermediate/` has no `+contract` block, so the spine is
  not contract-enforced and needs no `data_type` column list.
- **Neither kipptaf wrapper has any tests.** Both properties files are four
  lines: `models: - name: <x>` / `config: materialized: table`. The spec's
  "disable its tests alongside" has nothing to act on — do not go looking for
  tests to disable.
- The three NJ `sources-kipp*.yml` files carry the
  `dev`/`staging`(`zz_stg_`)/prod schema branch. **`sources-kippmiami.yml` does
  not** — it is declared BQ-native with a plain `schema: kippmiami_powerschool`,
  so every target reads the prod archive directly. Miami needs no `zz_stg`
  seeding; only the three NJ districts do.
- `source()` references to the two old models exist in exactly two files, the
  two kipptaf wrappers themselves. Nothing else reads them.
- **Spec gap this plan fills:** spec change 3 names only
  `sources-kippmiami.yml`, but a four-district `union_relations` needs a
  `int_powerschool__terms_spine` table entry in **all four** source files or dbt
  fails at parse with "source not defined". Task 3 adds all four.

---

## Task 1: Package spine model (PR A)

**Files:**

- Create:
  `src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms_spine.sql`
- Create:
  `src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__terms_spine.yml`

**Interfaces:**

- Consumes: `ref("stg_powerschool__terms")` (28 raw columns, contract in
  `src/dbt/powerschool/models/sis/staging/properties/stg_powerschool__terms.yml`)
  and `ref("int_powerschool__terms")` (8 columns: `schoolid`, `yearid`,
  `academic_year`, `term`, `term_start_date`, `term_end_date`, `semester`,
  `is_current_term`).
- Produces: a relation named `int_powerschool__terms_spine` with the 33 columns
  in the Global Constraints order. Task 3 wraps it; Task 4 projects it. No other
  task may change that column list or order.

- [ ] **Step 1: Write the failing unit test**

Create
`src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__terms_spine.yml`
with the properties block and the unit test. The unit test is the real
deliverable of this step: it proves the union does not join, that the `rn` guard
drops a superseded raw row, and that an orphan quarter survives with no raw row
to match.

```yaml
models:
  - name: int_powerschool__terms_spine
    description: >-
      Full-grain term spine for one PowerSchool district -- one row per raw
      terms record and one row per derived quarter, stacked rather than joined.
      The raw branch is stg_powerschool__terms reduced to one row per school,
      year, and abbreviation; the quarter branch is int_powerschool__terms
      unchanged. A quarter therefore appears twice: once on its raw record,
      carrying abbreviation and the scheduling-window dates, and once on its
      derived record, carrying the term code and the grade-storage-window dates.
      The two windows routinely disagree, which is why no join between them is
      attempted and why every column belonging to the other branch is null.
      Consumers that want the quarter grain filter to term is not null;
      consumers that want the raw grain filter to term is null.
    data_tests:
      # Two tests, because the two branches key on different columns. Quarter
      # rows key on term and carry no abbreviation; raw rows key on
      # abbreviation and carry no term. One test over both would have to key
      # on a column that is null for half the model.
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - schoolid
              - yearid
              - term
          config:
            severity: error
            where: term is not null
      - dbt_utils.unique_combination_of_columns:
          arguments:
            combination_of_columns:
              - schoolid
              - yearid
              - abbreviation
          config:
            severity: error
            where: term is null
    columns:
      - name: schoolid
        description: The School_Number of the school the record belongs to.
      - name: yearid
        description: >-
          A number representing which school year the record belongs to, 35 for
          2025-2026.
      - name: academic_year
        description: The school year's starting year, so 2025 for 2025-2026.
      - name: term
        description: >-
          Quarter code -- Q1, Q2, Q3, or Q4. Null on every raw-branch row,
          including the raw record of a quarter.
      - name: term_start_date
        description: >-
          First calendar date of the quarter, from the grade-storage window.
          Null on raw-branch rows.
      - name: term_end_date
        description: >-
          Last calendar date of the quarter, from the grade-storage window. Null
          on raw-branch rows.
      - name: semester
        description: >-
          Semester the quarter falls in -- S1 for Q1 and Q2, S2 for Q3 and Q4.
          Null on raw-branch rows. The raw terms table's own semester column is
          deliberately not carried.
      - name: is_current_term
        description: >-
          Whether today falls within the quarter's date range. Null on
          raw-branch rows.
      - name: abbreviation
        description: >-
          The short code for the term as the raw terms table records it, so S1,
          Q1, or a year label. Null on quarter-branch rows.
      - name: name
        quote: true
        description: >-
          The common name for this term, so Semester 1 or Quarter 1. Null on
          quarter-branch rows.
      - name: firstday
        description: >-
          The first calendar date of the term from the scheduling window. Null
          on quarter-branch rows.
      - name: lastday
        description: >-
          The last calendar date of the term from the scheduling window. Null on
          quarter-branch rows.
      - name: isyearrec
        description: >-
          Flag indicating if the raw record is the year-long term. 1 = yes, 0 =
          no. Null on quarter-branch rows.
      - name: fiscal_year
        description: Fiscal year the term falls in. Null on quarter-branch rows.
      - name: dcid
        description: >-
          Unique identifier for the raw terms record. Null on quarter-branch
          rows.
      - name: id
        description: >-
          Sequential number generated by PowerSchool; not unique on its own.
          Used to pick the surviving row when a school, year, and abbreviation
          repeat. Null on quarter-branch rows.
      - name: importmap
        description: >-
          If importing, the code that relates to this term. Null on
          quarter-branch rows.
      - name: terminfo_guid
        description: >-
          Globally unique identifier for the raw row. Null on quarter-branch
          rows.
      - name: psguid
        description: >-
          Unique identifier for the row where applicable -- multi-tenant,
          Schoolnet, Pearson. Null on quarter-branch rows.
      - name: ip_address
        description: >-
          IP address of the client that initiated the transaction. Null on
          quarter-branch rows.
      - name: whomodifiedtype
        description: >-
          Type of user account that last modified the record. Null on
          quarter-branch rows.
      - name: transaction_date
        description: >-
          Date and time of the database transaction. Null on quarter-branch
          rows.
      - name: noofdays
        description: >-
          Calculated number of in-session days between the term's dates. Null on
          quarter-branch rows.
      - name: yearlycredithrs
        description: >-
          No longer used by PowerSchool; may still appear on reports. Null on
          quarter-branch rows.
      - name: termsinyear
        description: >-
          The number of scheduling terms this term takes up given the school's
          LCM of term lengths. Null on quarter-branch rows.
      - name: portion
        description: >-
          The fraction of a year the term takes, PowerSchool-internal. Null on
          quarter-branch rows.
      - name: autobuildbin
        description: >-
          Used when copying the master schedule. Null on quarter-branch rows.
      - name: periods_per_day
        description: >-
          Number of periods in a school day for this term. Null on
          quarter-branch rows.
      - name: days_per_cycle
        description: >-
          Number of days for a cycle for this term. Null on quarter-branch rows.
      - name: attendance_calculation_code
        description: >-
          Whether positive or negative attendance is used in this term -- 1 =
          negative, 2 = positive. Null on quarter-branch rows.
      - name: sterms
        description: >-
          Number of scheduling terms in a school year. Null on quarter-branch
          rows.
      - name: suppresspublicview
        description: >-
          Whether sections meeting for this term are hidden from the Public
          Portal and Mobile App. Null on quarter-branch rows.
      - name: whomodifiedid
        description: >-
          Internal id of the user who last modified the record. Null on
          quarter-branch rows.

unit_tests:
  - name: unit_terms_spine_stacks_without_joining
    description: >-
      That the two branches stack rather than match. School 1 year 30 has a
      quarter present on both sides, so it yields two rows, not one merged row
      -- if this ever collapses to one row the union has been turned back into a
      join. The superseded raw Q1 record with the higher id is dropped by the
      row_number guard, which is the only filtering this model does. School 2
      has a quarter with no raw record at all, the orphan case worth 1,752,966
      enrollment days in prod, and it survives because a union never attempts a
      match.
    model: int_powerschool__terms_spine
    given:
      - input: ref('stg_powerschool__terms')
        rows:
          # the year-long record
          - {
              dcid: 1000,
              id: 100,
              schoolid: 1,
              yearid: 30,
              academic_year: 2020,
              abbreviation: 20-21,
              firstday: 2020-09-01,
              lastday: 2021-06-18,
              isyearrec: 1,
            }
          # the raw Q1 record -- lower id, so this one survives
          - {
              dcid: 1001,
              id: 200,
              schoolid: 1,
              yearid: 30,
              academic_year: 2020,
              abbreviation: Q1,
              firstday: 2020-09-01,
              lastday: 2020-11-06,
              isyearrec: 0,
            }
          # a superseded duplicate of the same key -- dropped by rn = 1
          - {
              dcid: 1002,
              id: 201,
              schoolid: 1,
              yearid: 30,
              academic_year: 2020,
              abbreviation: Q1,
              firstday: 2020-09-02,
              lastday: 2020-11-07,
              isyearrec: 0,
            }
      - input: ref('int_powerschool__terms')
        rows:
          # same school, year, and quarter as the raw Q1 record above, on
          # disagreeing dates
          - {
              schoolid: 1,
              yearid: 30,
              academic_year: 2020,
              term: Q1,
              term_start_date: 2020-09-06,
              term_end_date: 2020-11-11,
              semester: S1,
              is_current_term: false,
            }
          # the orphan: no raw record carries this quarter
          - {
              schoolid: 2,
              yearid: 30,
              academic_year: 2020,
              term: Q2,
              term_start_date: 2020-11-12,
              term_end_date: 2021-01-29,
              semester: S1,
              is_current_term: false,
            }
    expect:
      rows:
        - {
            schoolid: 1,
            yearid: 30,
            academic_year: 2020,
            dcid: 1000,
            id: 100,
            abbreviation: 20-21,
            firstday: 2020-09-01,
            lastday: 2021-06-18,
            isyearrec: 1,
            term: null,
            term_start_date: null,
            term_end_date: null,
            semester: null,
            is_current_term: null,
          }
        - {
            schoolid: 1,
            yearid: 30,
            academic_year: 2020,
            dcid: 1001,
            id: 200,
            abbreviation: Q1,
            firstday: 2020-09-01,
            lastday: 2020-11-06,
            isyearrec: 0,
            term: null,
            term_start_date: null,
            term_end_date: null,
            semester: null,
            is_current_term: null,
          }
        - {
            schoolid: 1,
            yearid: 30,
            academic_year: 2020,
            dcid: null,
            id: null,
            abbreviation: null,
            firstday: null,
            lastday: null,
            isyearrec: null,
            term: Q1,
            term_start_date: 2020-09-06,
            term_end_date: 2020-11-11,
            semester: S1,
            is_current_term: false,
          }
        - {
            schoolid: 2,
            yearid: 30,
            academic_year: 2020,
            dcid: null,
            id: null,
            abbreviation: null,
            firstday: null,
            lastday: null,
            isyearrec: null,
            term: Q2,
            term_start_date: 2020-11-12,
            term_end_date: 2021-01-29,
            semester: S1,
            is_current_term: false,
          }
```

Notes on the fixture, so it is not "fixed" into failing:

- Fixture and `expect` rows deliberately list only the 14 columns the test
  asserts. dbt null-fills the rest on both sides, and this model's other 19
  columns are null in these fixtures, so they match. Do not expand to 33
  columns.
- Dict-format `given` needs the mocked relations to exist in the warehouse for
  schema introspection. Both `stg_powerschool__terms` and
  `int_powerschool__terms` are `BASE TABLE`s in every district dataset, so dict
  format works here.
- Dates are unquoted. yamllint `quoted-strings` flags quoted dates as redundant
  and fires at pre-push, not at the commit hook.
- `20-21` is unquoted and parses as a string, not a date or a number.

- [ ] **Step 2: Run the unit test to verify it fails**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run dbt deps --project-dir src/dbt/kippnewark
```

Then, in its own call:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run dbt parse --no-partial-parse --project-dir src/dbt/kippnewark 2>&1 | tail -n 20
```

Expected: FAIL. `dbt parse` errors because
`properties/int_powerschool__terms_spine.yml` declares a model and a unit test
for `int_powerschool__terms_spine`, and no such model exists — dbt reports an
unpatched/undefined model node.

- [ ] **Step 3: Write the model**

Create
`src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms_spine.sql`:

```sql
with
    terms_ranked as (
        select
            dcid,
            `name`,
            firstday,
            lastday,
            abbreviation,
            importmap,
            terminfo_guid,
            psguid,
            ip_address,
            whomodifiedtype,
            transaction_date,
            id,
            noofdays,
            yearlycredithrs,
            termsinyear,
            portion,
            autobuildbin,
            isyearrec,
            periods_per_day,
            days_per_cycle,
            attendance_calculation_code,
            sterms,
            suppresspublicview,
            whomodifiedid,
            fiscal_year,
            schoolid,
            yearid,
            academic_year,

            row_number() over (
                partition by schoolid, yearid, abbreviation order by id
            ) as rn,
        from {{ ref("stg_powerschool__terms") }}
    )

select
    dcid,
    `name`,
    firstday,
    lastday,
    abbreviation,
    importmap,
    terminfo_guid,
    psguid,
    ip_address,
    whomodifiedtype,
    transaction_date,
    id,
    noofdays,
    yearlycredithrs,
    termsinyear,
    portion,
    autobuildbin,
    isyearrec,
    periods_per_day,
    days_per_cycle,
    attendance_calculation_code,
    sterms,
    suppresspublicview,
    whomodifiedid,
    fiscal_year,
    cast(null as string) as term,
    cast(null as date) as term_start_date,
    cast(null as date) as term_end_date,
    cast(null as string) as semester,
    cast(null as bool) as is_current_term,
    schoolid,
    yearid,
    academic_year,
from terms_ranked
-- Defensive only: all 1,925 (schoolid, yearid, abbreviation) keys across the
-- three NJ districts are singletons today, and Miami's 193 archive rows are
-- singletons too. The guard keeps a duplicate raw record from doubling a
-- school year's raw rows.
where rn = 1

union all

-- Positional union: this list mirrors the raw branch column for column, with a
-- typed null where the quarter branch has no equivalent.
select
    cast(null as int64) as dcid,
    cast(null as string) as `name`,
    cast(null as date) as firstday,
    cast(null as date) as lastday,
    cast(null as string) as abbreviation,
    cast(null as string) as importmap,
    cast(null as string) as terminfo_guid,
    cast(null as string) as psguid,
    cast(null as string) as ip_address,
    cast(null as string) as whomodifiedtype,
    cast(null as timestamp) as transaction_date,
    cast(null as int64) as id,
    cast(null as int64) as noofdays,
    cast(null as float64) as yearlycredithrs,
    cast(null as int64) as termsinyear,
    cast(null as int64) as portion,
    cast(null as int64) as autobuildbin,
    cast(null as int64) as isyearrec,
    cast(null as int64) as periods_per_day,
    cast(null as int64) as days_per_cycle,
    cast(null as int64) as attendance_calculation_code,
    cast(null as int64) as sterms,
    cast(null as int64) as suppresspublicview,
    cast(null as int64) as whomodifiedid,
    cast(null as int64) as fiscal_year,
    term,
    term_start_date,
    term_end_date,
    semester,
    is_current_term,
    schoolid,
    yearid,
    academic_year,
from {{ ref("int_powerschool__terms") }}
```

- [ ] **Step 4: Run the unit test to verify it passes**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run dbt test --select int_powerschool__terms_spine --project-dir src/dbt/kippnewark --target dev 2>&1 | tail -n 25
```

Expected: the unit test `unit_terms_spine_stacks_without_joining` PASSES. The
two `dbt_utils.unique_combination_of_columns` data tests will FAIL or error here
because the model relation does not exist in the dev schema yet — that is
expected at this step; Step 5 builds it.

- [ ] **Step 5: Build the model into dev and run its data tests**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run dbt build --select int_powerschool__terms_spine --project-dir src/dbt/kippnewark --target dev --defer --favor-state --state /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms/src/dbt/kippnewark/target/prod 2>&1 | tail -n 25
```

Expected: PASS — 1 model built, 2 data tests and 1 unit test passing. If
`target/prod` is absent, the state path has no manifest; get one by running
`uv run dbt parse --target prod --project-dir src/dbt/kippnewark` first, or fall
back to building without `--defer` if the dev schema already carries the
upstreams.

- [ ] **Step 6: Prove the spine equals the full join it replaces**

This is the correctness gate for the whole PR, and it runs against prod through
the BigQuery MCP, not against a dev build. Compare the new spine's two halves
against the two halves of today's `int_students__terms`, per district. Run for
`kippnewark`, then repeat with the schema swapped for `kippcamden` and
`kipppaterson`.

```sql
with
    spine_quarters as (
        select schoolid, yearid, academic_year, term, term_start_date,
            term_end_date, semester,
        from `teamster-332318`.`zz_<user>_kippnewark_powerschool`.`int_powerschool__terms_spine`
        where term is not null
    ),

    live_quarters as (
        select schoolid, yearid, academic_year, term, term_start_date,
            term_end_date, semester,
        from `teamster-332318`.`kipptaf_students`.`int_students__terms`
        where term is not null and _dbt_source_project = 'kippnewark'
    )

select
    (select count(*) from spine_quarters) as spine_rows,
    (select count(*) from live_quarters) as live_rows,
    (
        select count(*)
        from (
            select * from spine_quarters
            except distinct
            select * from live_quarters
        )
    ) as in_spine_not_live,
    (
        select count(*)
        from (
            select * from live_quarters
            except distinct
            select * from spine_quarters
        )
    ) as in_live_not_spine
```

Expected: `spine_rows = live_rows`, both `except distinct` counts `0`. Repeat
with `where term is null` against the raw-column projection (`dcid`, `name`,
`firstday`, `lastday`, `abbreviation`, `isyearrec`, `id`, `fiscal_year`,
`schoolid`, `yearid`, `academic_year`) for the raw half. `is_current_term` is
excluded from both comparisons: it is computed from `current_date()` and the two
relations were built at different times.

If any count is non-zero, STOP and report the diff rather than adjusting the
model to match.

- [ ] **Step 7: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms_spine.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__terms_spine.yml </dev/null 2>&1 | tail -n 20
```

Expected: `✔ No issues`. Fix anything reported; suppress only with
`trunk-ignore(linter/rule): reason` on the preceding line.

- [ ] **Step 8: Commit and open PR A**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && git add src/dbt/powerschool/models/sis/intermediate/int_powerschool__terms_spine.sql src/dbt/powerschool/models/sis/intermediate/properties/int_powerschool__terms_spine.yml && git commit -F - <<'EOF'
feat(dbt): add a full-grain PowerSchool terms spine

Stacks the raw terms records and the derived quarter records with union all
rather than joining them.

Measured against prod, the two shapes are equivalent in VALUES but not in ROWS.
The quarter side is 926 rows under both shapes with a symmetric difference of 0,
and the raw side is 1,925 rows under both with a symmetric difference of 0. But
the full join in int_students__terms collapses a matched raw record and its
quarter into a single row carrying both halves, and there are 840 such rows today
(kippnewark 548, kippcamden 276, kipppaterson 16). The spine emits them as two
rows, so NJ output grows from 2,011 rows to 2,851.

That is safe on the grain: no row carries both a null dcid and a null term, and
both uniqueness keys hold over the full branch sets rather than only the subsets
they are tested on today -- 0 duplicate keys on (schoolid, yearid, abbreviation)
across all 1,925 raw rows and 0 on (schoolid, yearid, term) across all 926
quarter rows.

int_powerschool__terms is unchanged, so
int_powerschool__student_course_grades_spine is untouched.

Refs #5397

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

Then push and open the PR with `mcp__github__create_pull_request`, body from
`.github/pull_request_template.md`, `Refs #5397` in the body, ending with the
`🤖 Generated with [Claude Code](https://claude.com/claude-code)` line. Keep
every template line and answer its prompts in place.

Flag in the PR body that kipptaf dbt Cloud CI will select no models — CI is
scoped to the kipptaf project, so a green CI run here is not evidence about this
change. The verification that matters is Step 6.

---

## Task 2: PR A merge, prod materialization, and the Miami archive rebuild

This task is mostly the user's. It is a separate task because PR B cannot be
pushed until the Miami spine relation exists in
`kippmiami_powerschool.int_powerschool__terms_spine`.

**Files:** none changed by this task.

**Interfaces:**

- Consumes: PR A, merged.
- Produces: `int_powerschool__terms_spine` as a `BASE TABLE` in all four of
  `kippnewark_powerschool`, `kippcamden_powerschool`,
  `kipppaterson_powerschool`, `kippmiami_powerschool`.

- [ ] **Step 1: Squash merge PR A after review**

Hand the merge to the user.

- [ ] **Step 2: Confirm the three NJ districts materialized the spine in prod**

Dagster picks up the new asset on deploy. Verify rather than assume:

```sql
select table_schema, table_name, table_type
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.TABLES
where
    table_name = 'int_powerschool__terms_spine'
    and table_schema like 'kipp%_powerschool'
order by table_schema
```

Expected: three rows (`kippcamden`, `kippnewark`, `kipppaterson`), each
`BASE TABLE`. Miami is absent at this step and arrives in Step 3.

If a district is missing after the deploy tick, check the asset's condition
evaluation with `mcp__dagster__get_asset_condition_evaluations` before launching
anything by hand.

- [ ] **Step 3: Hand the Miami archive rebuild to the user**

This is a prod build of a district project and a `packages.yml` edit, so it is
the user's to run. Give them this, verbatim:

> The Miami archive needs a rebuild to produce `int_powerschool__terms_spine`
> and to refresh `int_powerschool__terms`, which is frozen at 72 rows and short
> 16 quarters worth 86,213 membership days. The recipe is in
> `src/dbt/kippmiami/CLAUDE.md`: re-include the `powerschool` package in
> `src/dbt/kippmiami/packages.yml`, restore the `powerschool:` block in
> `src/dbt/kippmiami/dbt_project.yml` with `+materialized: table`, the ODBC
> staging variant, and the 16 post-hooks (the 8400 Focus prefix on
> `student_number`, the `yearid > 35` row deletes on 14 staging models, and the
> `date_value >= '2026-07-01'` delete on `stg_powerschool__calendar_day`), run
> the build, then remove the package again. Recover the exact block from git
> history — it has been re-added and removed four times, most recently for
> #5260.

Ask them to confirm when it completes.

- [ ] **Step 4: Verify the Miami spine and the refreshed quarters**

```sql
select
    countif(term is not null) as quarter_rows,
    countif(term is null) as raw_rows,
    count(*) as total_rows,
    min(academic_year) as min_year,
    max(academic_year) as max_year,
from `teamster-332318`.`kippmiami_powerschool`.`int_powerschool__terms_spine`
```

Expected: `raw_rows = 193` (the archive's raw terms count, all singleton keys),
`quarter_rows = 88` — the 72 the frozen relation held plus the 16 that #5396's
fallback logic produces on a rebuild. If `quarter_rows` is still 72, the rebuild
ran against a stale package and the fallback branch did not apply; do not
proceed to PR B.

- [ ] **Step 5: Confirm `packages.yml` is clean again**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && git -C /workspaces/teamster status --short src/dbt/kippmiami/ && grep -n 'powerschool' /workspaces/teamster/src/dbt/kippmiami/packages.yml /workspaces/teamster/src/dbt/kippmiami/dbt_project.yml
```

Expected: no `powerschool` entry in either file, and a clean working tree.
Leaving the package in place makes the next Miami build re-run the whole
archive.

---

## Task 3: kipptaf spine wrapper and the four source entries (PR B)

**Files:**

- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms_spine.sql`
- Create:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__terms_spine.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml` (after
  line 1069)
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml` (lines 3-20
  and after line 148)

**Interfaces:**

- Consumes: `source("<district>_powerschool", "int_powerschool__terms_spine")`
  for all four districts — the 33-column relation Task 1 produced.
- Produces: `ref("int_powerschool__terms_spine")` in kipptaf, with those 33
  columns plus `_dbt_source_relation` (from `union_relations`) and
  `_dbt_source_project`. Task 4 projects it.

- [ ] **Step 1: Add the source table entry to all four source files**

Each entry follows the existing block shape exactly. For
`sources-kippnewark.yml`, append after the `int_powerschool__terms` entry
(currently lines 1061-1069):

```yaml
- name: int_powerschool__terms_spine
  config:
    meta:
      dagster:
        group: powerschool
        asset_key:
          - kippnewark
          - powerschool
          - int_powerschool__terms_spine
```

Repeat in `sources-kippcamden.yml`, `sources-kipppaterson.yml`, and
`sources-kippmiami.yml`, swapping the first `asset_key` element to that
district. In `sources-kippmiami.yml` the entry goes after
`int_powerschool__calendar_week` (currently ends line 148).

- [ ] **Step 2: Rewrite the `sources-kippmiami.yml` source description**

Replace the current description (lines 3-20), which asserts terms are
deliberately absent because Focus covers the whole archive range. New text:

```yaml
description: >-
  Miami's PowerSchool archive (final ODBC pull 2026-07-01; Miami's SIS moved to
  Focus). Permanent history source for stored grades, attendance, the course
  enrollments they hang off (#5193), section teachers (#5260), terms (#5397),
  and the calendars the network calendar models read — 15 permanent tables in
  total. Enrollment stints are deliberately absent: Focus is Miami's sole
  enrollment source across all years, so unioning the archive's stints
  double-counts every row. Terms and calendars are the opposite case, and that
  is why they are here — int_students__terms, int_students__calendar_day and
  int_students__calendar_week all floor their Focus branch at the SIS cutover
  year, so the archive covers the pre-AY2026 years Focus does not. Rebuilt from
  the frozen externals with the 8400 Focus prefix on student_number and an
  AY2025 bound applied (#5012). The dataset must not be dropped. Declared
  BQ-native (plain schema, no target branch) so every target reads the prod
  tables directly.
```

- [ ] **Step 3: Write the wrapper model**

Create
`src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms_spine.sql`,
mirroring the retiring `int_powerschool__terms` wrapper exactly, with Miami
added and no header comment:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "int_powerschool__terms_spine"
                    ),
                    source(
                        "kippcamden_powerschool", "int_powerschool__terms_spine"
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "int_powerschool__terms_spine",
                    ),
                    source(
                        "kippmiami_powerschool", "int_powerschool__terms_spine"
                    ),
                ]
            )
        }}
    )

select ur.*, {{ extract_source_project("ur") }} as _dbt_source_project,

from union_relations as ur
```

- [ ] **Step 4: Write the wrapper properties file**

Create
`src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__terms_spine.yml`:

```yaml
models:
  - name: int_powerschool__terms_spine
    config:
      materialized: table
```

No uniqueness test and no column docs, matching the sibling wrapper it replaces
and the repo's treatment of pure `union_relations` passthroughs. The grain
guarantee lives on the package model (Task 1) and on `int_students__terms` (Task
5). Flag this in the PR body as a deliberate choice so a reviewer can push back
rather than read it as an omission.

- [ ] **Step 5: Verify the union expands to a real column list**

A dev-target compile expands to nothing, because `union_relations` resolves
columns from the source relation's `INFORMATION_SCHEMA` and the dev schema holds
no copy. Compile against `staging`, which resolves the same relations dbt Cloud
CI reads. This is a compile, not a warehouse write, so it needs no
authorization.

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run dbt compile --select int_powerschool__terms_spine --target staging --project-dir src/dbt/kipptaf 2>&1 | tail -n 20
```

Then read the compiled SQL:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && grep -c 'cast(null as' src/dbt/kipptaf/target/compiled/kipptaf/models/powerschool/intermediate/int_powerschool__terms_spine.sql; grep -o 'from `teamster-332318`\.`[a-z_]*`' src/dbt/kipptaf/target/compiled/kipptaf/models/powerschool/intermediate/int_powerschool__terms_spine.sql | sort -u
```

Expected: `grep -c 'cast(null as'` returns a number greater than 0, and the
`from` list names all four district datasets. An empty expansion still compiles
clean, so the grep is the actual check. If the compile errors with
`source not defined`, a source entry from Step 1 is missing.

- [ ] **Step 6: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms_spine.sql src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__terms_spine.yml src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml src/dbt/kipptaf/models/powerschool/sources-kippmiami.yml </dev/null 2>&1 | tail -n 20
```

Expected: `✔ No issues`.

- [ ] **Step 7: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && git add -u && git add src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms_spine.sql src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__terms_spine.yml && git commit -F - <<'EOF'
feat(dbt): wrap the four-district PowerSchool terms spine

Adds the kipptaf union_relations wrapper over int_powerschool__terms_spine and
the four source table entries it needs. Miami is in the union for the first
time: its frozen archive carries terms back to its first school year, which is
exactly the range int_students__terms floors its Focus branch out of.

Refs #5397

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 4: Rewrite `int_students__terms`

**Files:**

- Modify: `src/dbt/kipptaf/models/students/intermediate/int_students__terms.sql`
  (all 256 lines; the model drops to roughly 105)

**Interfaces:**

- Consumes: `ref("int_powerschool__terms_spine")` from Task 3 — 33 columns plus
  `_dbt_source_relation` and `_dbt_source_project`. Also the three unchanged
  Focus inputs: `ref("int_focus__schools")`,
  `ref("stg_google_sheets__people__locations")`,
  `ref("stg_focus__marking_periods")`.
- Produces: the same 35 output columns in the same order the model has today, so
  no consumer changes. Task 5 documents them; Task 6 removes what this task
  stops reading.

- [ ] **Step 1: Replace the file**

Write the whole model. The three Focus CTEs are unchanged except the floor and
its comment; everything from `powerschool_quarters` down is replaced by the two
union branches.

```sql
with
    focus_schools as (
        select s.id as focus_school_id, loc.powerschool_school_id as schoolid,
        from {{ ref("int_focus__schools") }} as s
        inner join
            {{ ref("stg_google_sheets__people__locations") }} as loc
            on s.school_number = loc.focus_school_id
    ),

    focus_marking_periods as (
        select
            mp._dbt_source_relation,
            mp._dbt_source_project,
            mp.type,
            mp.title,
            mp.short_name,
            mp.start_date,
            mp.end_date,
            mp.quarter_semester,
            mp.is_within_dates,

            mp.syear as academic_year,

            fs.schoolid,
        from {{ ref("stg_focus__marking_periods") }} as mp
        inner join focus_schools as fs on mp.school_id = fs.focus_school_id
        -- Progress periods have no PowerSchool `terms` equivalent. The 2026
        -- floor is the SIS cutover year: before it the frozen PowerSchool
        -- archive owns Miami's terms, and Focus carries a full
        -- year/semester/quarter set for 2 schools in every syear back to 1980,
        -- which would fabricate history here. Both filters stay in this model
        -- rather than in staging, because 321 report card grade rows point at
        -- pre-2018 marking periods and flooring the staging model orphans them.
        where mp.type in ('year', 'semester', 'quarter') and mp.syear >= 2026
    ),

    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            schoolid,
            academic_year,

            title as `name`,
            short_name as abbreviation,
            start_date as firstday,
            end_date as lastday,

            if(`type` = 'year', 1, 0) as isyearrec,

            academic_year - 1990 as yearid,
            academic_year + 1 as fiscal_year,

            if(`type` = 'quarter', short_name, null) as term,
            if(`type` = 'quarter', start_date, null) as term_start_date,
            if(`type` = 'quarter', end_date, null) as term_end_date,
            if(`type` = 'quarter', quarter_semester, null) as semester,
            if(`type` = 'quarter', is_within_dates, null) as is_current_term,
        from focus_marking_periods
    )

select
    _dbt_source_relation,
    dcid,
    `name`,
    firstday,
    lastday,
    abbreviation,
    importmap,
    terminfo_guid,
    psguid,
    ip_address,
    whomodifiedtype,
    transaction_date,
    id,
    noofdays,
    yearlycredithrs,
    termsinyear,
    portion,
    autobuildbin,
    isyearrec,
    periods_per_day,
    days_per_cycle,
    attendance_calculation_code,
    sterms,
    suppresspublicview,
    whomodifiedid,
    fiscal_year,
    term,
    term_start_date,
    term_end_date,
    semester,
    is_current_term,
    schoolid,
    yearid,
    _dbt_source_project,
    academic_year,
from {{ ref("int_powerschool__terms_spine") }}

union all

select
    _dbt_source_relation,
    cast(null as int64) as dcid,
    `name`,
    firstday,
    lastday,
    abbreviation,
    cast(null as string) as importmap,
    cast(null as string) as terminfo_guid,
    cast(null as string) as psguid,
    cast(null as string) as ip_address,
    cast(null as string) as whomodifiedtype,
    cast(null as timestamp) as transaction_date,
    cast(null as int64) as id,
    cast(null as int64) as noofdays,
    cast(null as float64) as yearlycredithrs,
    cast(null as int64) as termsinyear,
    cast(null as int64) as portion,
    cast(null as int64) as autobuildbin,
    isyearrec,
    cast(null as int64) as periods_per_day,
    cast(null as int64) as days_per_cycle,
    cast(null as int64) as attendance_calculation_code,
    cast(null as int64) as sterms,
    cast(null as int64) as suppresspublicview,
    cast(null as int64) as whomodifiedid,
    fiscal_year,
    term,
    term_start_date,
    term_end_date,
    semester,
    is_current_term,
    schoolid,
    yearid,
    _dbt_source_project,
    academic_year,
from focus_conformed
```

Three things not to change while writing this:

- The 35-column order is today's order exactly. Do not re-sort it to put the
  keys first; a consumer reading positionally would break, and it makes the diff
  reviewable.
- `_dbt_source_project` is selected THROUGH from the spine wrapper, never
  re-derived with `extract_source_project()`. That macro belongs only on the
  `union_relations` view that creates `_dbt_source_relation`.
- No `full join`, no `coalesce(p.x, q.x)`. If a reviewer asks why the arms are
  not reconciled: measured on prod, the quarter side is 926 rows and the raw
  side 1,925 rows in both the old and new shape, with a symmetric difference of
  0 over every compared column. The old shape additionally MERGED 840 matched
  pairs into single rows; the new shape emits two rows each, so NJ output grows
  2,011 to 2,851. No consumer reads a merged row's two halves together, and both
  uniqueness keys hold over the full branch sets.

- [ ] **Step 2: Compile and check the output column list**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run dbt compile --select int_students__terms --target staging --project-dir src/dbt/kipptaf 2>&1 | tail -n 15
```

Expected: compiles clean. Then confirm both union branches project 35 columns
and the two lists align positionally by reading the compiled file at
`src/dbt/kipptaf/target/compiled/kipptaf/models/students/intermediate/int_students__terms.sql`.

- [ ] **Step 3: Confirm the column set did not drift**

```sql
select column_name, data_type, ordinal_position
from `teamster-332318`.`kipptaf_students`.INFORMATION_SCHEMA.COLUMNS
where table_name = 'int_students__terms'
order by ordinal_position
```

Expected: 35 columns. Compare name, type, and position against the compiled
select list from Step 2. Any difference is a defect in Step 1, not an intended
change — this model has 8 consumers.

- [ ] **Step 4: Lint**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/students/intermediate/int_students__terms.sql </dev/null 2>&1 | tail -n 20
```

Expected: `✔ No issues`. ST06 does not fire on the interleaved
`cast(null as ...)` and plain columns in the Focus branch — sqlfluff buckets
`cast()` as a simple target, and today's model already interleaves them with no
suppression. Do not add a `trunk-ignore` pre-emptively.

- [ ] **Step 5: Commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && git add -u && git commit -F - <<'EOF'
fix(dbt): serve Miami's pre-cutover terms from the PowerSchool archive

Replaces the raw-terms / quarters full join with a projection of the new
four-district spine, and moves the Focus branch's floor from syear 2018 to the
SIS cutover year 2026. The archive now supplies Miami's quarters for every year
before the cutover, which is where the 492,482 null-term membership days were.

The full join is gone rather than rewired. Measured on prod, the two shapes
carry the same values -- 926 quarter rows and 1,925 raw rows on both, symmetric
difference 0 -- but not the same rows: the join merged 840 matched pairs into
single rows, and the union emits two rows each, so NJ output grows from 2,011 to
2,851. No consumer reads a merged row's two halves together, and both uniqueness
keys hold over the full branch sets.

Refs #5397

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 5: Rewrite the `int_students__terms` documentation

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__terms.yml`
  (model description lines 3-19, and 12 column descriptions)

**Interfaces:**

- Consumes: the model Task 4 produced. No SQL change.
- Produces: nothing downstream. This task exists separately because the current
  descriptions make four factual claims the change falsifies, and a reviewer can
  approve Task 4 while rejecting wording.

- [ ] **Step 1: Replace the model description**

Replace lines 3-19 (`description: >-` through
`term is not null at the call site.`) with:

```yaml
description: >-
  SIS-agnostic school-year, semester, and quarter spine, at full grain (one row
  per school and per term record). Unions the per-district PowerSchool terms
  spine for all four regions with Miami's Focus marking periods conformed inline
  to the PowerSchool terms vocabulary. PowerSchool is the source of record
  before the SIS cutover year, Miami included -- its frozen archive supplies
  terms back to its first school year -- and Focus supplies Miami from the
  cutover year on, so the two arms are disjoint by year and nothing is
  reconciled between them. The quarter-only columns (term, term_start_date,
  term_end_date, semester, is_current_term) are populated only on quarter rows,
  and the raw-terms columns (dcid, name, firstday, lastday, id, and the
  PowerSchool bookkeeping fields) only on the rows that come from the raw terms
  table. A quarter therefore appears as two rows, one carrying its abbreviation
  and scheduling-window dates and one carrying its term code and
  grade-storage-window dates; the two windows routinely disagree, and no
  consumer reads both halves on one row. On the PowerSchool arm the quarter rows
  resolve their dates from termbins where termbins carries the quarter and from
  the raw terms table's own quarter row where it does not; on the Focus arm they
  are derived from Focus's quarter-type marking periods. Consumers that need
  only the quarter grain filter to term is not null at the call site.
```

- [ ] **Step 2: Fix the model-level test comment**

The comment above `data_tests:` (lines 21-25) says quarter rows key on term
"which int_powerschool__terms supplies". Replace that clause so it names the
spine, and keep the rest as is. Both tests keep their existing
`combination_of_columns` and `where` clauses — the grain is unchanged, so do not
touch the keys.

- [ ] **Step 3: Replace the ten "For Miami" column clauses**

Each row below is an exact substring replacement. The claims are all wrong the
same way: Miami now has PowerSchool rows too, so the distinction is Focus rows
against PowerSchool rows, not Miami against everyone.

| Column          | Replace this text                                                                                                                                                               | With this                                                                                                                                                     |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `schoolid`      | `For Miami, resolved from Focus's internal school id`                                                                                                                           | `On Focus rows, resolved from Focus's internal school id`                                                                                                     |
| `yearid`        | `For Miami, no Focus source; derived as academic_year - 1990`                                                                                                                   | `On Focus rows, no Focus equivalent exists; derived as academic_year - 1990`                                                                                  |
| `academic_year` | `For Miami, from Focus syear.`                                                                                                                                                  | `On Focus rows, from Focus syear.`                                                                                                                            |
| `abbreviation`  | `For Miami, from Focus short_name.`                                                                                                                                             | `On Focus rows, from Focus short_name. Null on the spine's quarter rows.`                                                                                     |
| `isyearrec`     | `For Miami, derived from Focus's marking period type.`                                                                                                                          | `On Focus rows, derived from Focus's marking period type. Null on the spine's quarter rows.`                                                                  |
| `fiscal_year`   | `For Miami, no Focus source; derived as academic_year + 1, matching the archive's own convention.`                                                                              | `On Focus rows, derived as academic_year + 1, matching the archive's own convention. Null on the spine's quarter rows.`                                       |
| `term`          | `For PowerSchool, taken from the matching int_powerschool__terms quarter row, not from this row's own abbreviation. For Miami, from Focus's quarter-type marking periods only.` | `On the PowerSchool arm, carried by the spine's own quarter rows, which hold no abbreviation. On Focus rows, from Focus's quarter-type marking periods only.` |
| `dcid`          | `Null for Miami -- Focus has no equivalent internal surrogate exposed here.`                                                                                                    | `Null on Focus rows -- Focus has no equivalent internal surrogate exposed here -- and null on the spine's quarter rows.`                                      |
| `id`            | `Null for Miami.`                                                                                                                                                               | `Null on Focus rows and on the spine's quarter rows.`                                                                                                         |
| `portion`       | `Null for Miami.`                                                                                                                                                               | `Null on Focus rows and on the spine's quarter rows.`                                                                                                         |

- [ ] **Step 4: Replace the two `int_powerschool__terms` source references**

`term_start_date` and `term_end_date` both say
`sourced from int_powerschool__terms for PowerSchool`. That model still exists
in the package but is no longer what this model reads. Replace with
`sourced from int_powerschool__terms_spine on the PowerSchool arm` in both.

- [ ] **Step 5: Replace the `_dbt_source_relation` and `_dbt_source_project`
      docs**

`_dbt_source_relation` currently says it "takes whichever side of the full join
supplied the row". There is no full join. Replace its description with:

```yaml
- name: _dbt_source_relation
  description: >-
    Source relation, passed through from the source union view. Every row
    reports the district relation it came from, including a quarter the raw
    terms table never carried.
```

`_dbt_source_project` says it is "resolved from _dbt_source_relation for the
PowerSchool branch". It is not resolved here on either arm — both select the
materialized column through. Replace with:

```yaml
- name: _dbt_source_project
  description:
    District code location, passed through from the source union view on both
    arms.
```

- [ ] **Step 6: Verify no stale claim survives**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && grep -n -i -e 'for miami' -e 'null for miami' -e 'full join' -e 'frozen archive contributes' -e "Miami's first real enrollment" -e 'int_powerschool__terms$' -e 'int_powerschool__terms ' src/dbt/kipptaf/models/students/intermediate/properties/int_students__terms.yml
```

Expected: no output. Any hit is a passage Steps 1 through 5 missed.

- [ ] **Step 7: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/students/intermediate/properties/int_students__terms.yml </dev/null 2>&1 | tail -n 20
```

Expected: `✔ No issues`. Then:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && git add -u && git commit -F - <<'EOF'
docs(dbt): correct the int_students__terms grain and provenance docs

The description claimed the frozen archive contributes no Miami rows, that the
Focus branch floors at Miami's first enrollment year, and that a column takes
whichever side of a full join supplied the row. All three are now false. Ten
column docs also said "For Miami" where the real distinction is Focus rows
against PowerSchool rows.

Refs #5397

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 6: Retire the two old kipptaf wrappers

**Files:**

- Delete:
  `src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms.sql`
- Delete:
  `src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__terms.yml`
- Modify:
  `src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__terms.yml`
- Modify: `src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml`,
  `sources-kippcamden.yml`, `sources-kipppaterson.yml` — remove the
  `int_powerschool__terms` table entries

**Interfaces:**

- Consumes: nothing. Task 4 removed the last `ref()` to both models.
- Produces: nothing. This is the cleanup half of the change and is deliberately
  its own task: a reviewer can ship Tasks 3 through 5 and defer this.

The two models get different treatment, and the difference is the rule, not a
preference.

- [ ] **Step 1: Confirm both have zero remaining references**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && grep -rn -e 'int_powerschool__terms"' -e "int_powerschool__terms'" -e 'stg_powerschool__terms"' -e "stg_powerschool__terms'" src/dbt/kipptaf/models/ | grep -v terms_spine
```

Expected: no output. A hit means some consumer still reads a wrapper and this
task cannot proceed. Note that `int_powerschool__terms` also exists in the
`powerschool` package — the package model stays, and this grep is scoped to
`src/dbt/kipptaf/models/` so it does not see it.

- [ ] **Step 2: Delete the `int_powerschool__terms` wrapper**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && git rm src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__terms.sql src/dbt/kipptaf/models/powerschool/intermediate/properties/int_powerschool__terms.yml
```

Deleted, not disabled. This is the #5162 exception in
`.claude/rules/dbt-models.md`: a kipptaf `select *` union passthrough over
district sources with no remaining `ref()` is deleted outright, source entries
included. It holds no logic, and the district relations it read stay in place.

- [ ] **Step 3: Remove its three source entries**

Delete the `int_powerschool__terms` table entry from `sources-kippnewark.yml`
(currently lines 1061-1069), `sources-kippcamden.yml`, and
`sources-kipppaterson.yml`. Leave every other entry alone, and do not touch
`sources-kippmiami.yml` — it never had one.

- [ ] **Step 4: Disable `stg_powerschool__terms`, do not delete it**

Replace the contents of
`src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__terms.yml`
with:

```yaml
models:
  - name: stg_powerschool__terms
    config:
      enabled: false
      materialized: table
```

It is disabled rather than deleted because it is not a bare passthrough — it
carries the `row_number()` dedup window that moved to the package spine, so the
#5162 exception does not reach it and the default rule applies: retiring a model
is a disable, and the prod relation stays in place.

There are no tests to disable alongside it. Both retiring wrappers' properties
files are four lines of `config` only. Do not go looking for tests here, and do
not add `enabled: false` to a `data_tests` block that does not exist.

Also delete the stale header comment from
`src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__terms.sql`, which
claims Miami is absent from the union because Focus covers the whole PowerSchool
archive range. The SQL itself stays, since a disabled model keeps its file.

- [ ] **Step 5: Verify what actually disappeared from the graph**

A count from the YAML diff does not say which dbt nodes went away.

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run dbt parse --no-partial-parse --target staging --project-dir src/dbt/kipptaf 2>&1 | tail -n 10
```

Expected: parses clean with no
`Model depends on a source named ... which was not found` error. Then confirm
the disable landed:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run --with dbt-common python -c "import json; m=json.load(open('src/dbt/kipptaf/target/manifest.json')); print('disabled:', [k for k in m['disabled'] if 'stg_powerschool__terms' in k]); print('in nodes:', [k for k in m['nodes'] if k.endswith('stg_powerschool__terms') or k.endswith('int_powerschool__terms')])"
```

Expected: `stg_powerschool__terms` appears under `disabled`, and neither model
name appears in `nodes`.

- [ ] **Step 6: Lint and commit**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/powerschool/staging/properties/stg_powerschool__terms.yml src/dbt/kipptaf/models/powerschool/staging/stg_powerschool__terms.sql src/dbt/kipptaf/models/powerschool/sources-kippnewark.yml src/dbt/kipptaf/models/powerschool/sources-kippcamden.yml src/dbt/kipptaf/models/powerschool/sources-kipppaterson.yml </dev/null 2>&1 | tail -n 20
```

Expected: `✔ No issues`. Then:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && git add -u && git commit -F - <<'EOF'
refactor(dbt): retire the superseded kipptaf terms wrappers

int_powerschool__terms is deleted -- a select * union passthrough with no
remaining ref, per the #5162 exception. stg_powerschool__terms is disabled
instead, because it carries the row_number dedup window that moved into the
package spine, so the default retire-is-a-disable rule applies.

Refs #5397

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
EOF
```

---

## Task 7: Seed the NJ staging copies, push, and open PR B

**Files:** none changed.

**Interfaces:**

- Consumes: Tasks 3 through 6, committed.
- Produces: PR B, with dbt Cloud CI able to resolve
  `int_powerschool__terms_spine` in the three NJ `zz_stg_*` datasets.

- [ ] **Step 1: Explain why CI needs seeding, then ask**

kipptaf `sources-kipp*` resolve to the `zz_stg_*` staging copies under
`target=staging`, which is what dbt Cloud CI reads. PR A's merge materialized
the spine in each district's PROD dataset; it did not create the staging copy.
Without seeding, CI fails deterministically on
`Not found: Table ... zz_stg_kippnewark_powerschool.int_powerschool__terms_spine`.

`dbt clone --target staging` recreates shared `zz_stg_*` relations that CI and
other developers read, so it needs the user's authorization in the turn
immediately before the call. Ask for it, naming the three datasets and the one
model. Miami needs nothing: `sources-kippmiami.yml` has a plain BQ-native schema
with no target branch, so every target already reads the prod archive.

- [ ] **Step 2: Clone the spine into the three NJ staging datasets**

Only after the user authorizes it, and restating that consent in plain text in
the same turn. One district per Bash call, never compounded with a `dbt deps`
step — a compounded shared write gets denied where the bare one goes through.

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && uv run dbt clone --select int_powerschool__terms_spine --target staging --state src/dbt/kippnewark/target/prod --full-refresh --project-dir src/dbt/kippnewark 2>&1 | tail -n 15
```

Repeat for `kippcamden` and `kipppaterson`, each in its own call. Every prod
relation here is a `BASE TABLE`, so each clone is metadata-cheap.

Expected per call:
`1 of 1 OK cloned relation ... zz_stg_<district>_powerschool.int_powerschool__terms_spine`.

- [ ] **Step 3: Confirm all four relations resolve under the staging target**

```sql
select table_schema, table_name, table_type
from `teamster-332318`.`region-us`.INFORMATION_SCHEMA.TABLES
where
    table_name = 'int_powerschool__terms_spine'
    and (
        table_schema like 'zz_stg_kipp%_powerschool'
        or table_schema = 'kippmiami_powerschool'
    )
order by table_schema
```

Expected: four rows — the three `zz_stg_*` copies plus `kippmiami_powerschool`.

- [ ] **Step 4: Lint everything on the branch once more**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix $(git diff --name-only origin/main...HEAD) </dev/null 2>&1 | tail -n 25
```

Expected: `✔ No issues`. The commit hook is not a substitute — committed files
are skipped without `--force`, and markdownlint under-reports.

- [ ] **Step 5: Push**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && git push 2>&1 | tail -n 5
```

- [ ] **Step 6: Open PR B**

Use `mcp__github__create_pull_request`. Body from
`.github/pull_request_template.md`: keep every line the template supplies and
answer its prompts in place. Include `Refs #5397`, and end with
`🤖 Generated with [Claude Code](https://claude.com/claude-code)`.

Four things the body must state, because a reviewer cannot derive them from the
diff:

1. The full join is replaced by `union all`. The two shapes carry the same
   values — 926 quarter rows and 1,925 raw rows on both, symmetric difference 0
   over every compared column — but not the same rows: the full join merges 840
   matched raw-plus-quarter pairs into single rows, and the union emits two rows
   each, growing NJ output from 2,011 to 2,851. Safe on two measurements. Both
   uniqueness keys hold over the full branch sets, not just the subsets they are
   tested on today — 0 duplicate keys on `(schoolid, yearid, abbreviation)`
   across all 1,925 raw rows and 0 on `(schoolid, yearid, term)` across all 926
   quarter rows. And no consumer reads a merged row's two halves together: of 9
   consumers, 5 read quarter-side columns only, 2 raw-side only, and 2 read both
   families in separate single-sided `union all` branches.
2. The Focus arm's floor moves from `syear >= 2018` to a literal `2026`. The
   literal is deliberate rather than a read of `int_students__sis_cutover`: the
   cutover already happened, so 2026 is a historical fact, and a Focus backfill
   reaching further back must not move this model's floor.
3. The kipptaf spine wrapper carries no uniqueness test, matching the sibling
   wrapper it replaces; the grain guarantee lives on the package spine and on
   `int_students__terms`.
4. The three NJ `zz_stg_*` copies were seeded in Step 2, so CI can resolve the
   new source.

Then check the returned PR title and body match what you intended — a malformed
parameter succeeds with the wrong payload.

- [ ] **Step 7: Watch CI**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-miami-archive-terms && gh pr checks <pr-number> --json name,bucket,state
```

`state:modified+` pulls this model's whole descendant graph into the run, so
expect unrelated pre-existing warn tests as noise. Before treating any
`severity: error` failure as caused by this change, query prod for the same
count. For anything else about CI triage, invoke `pr-ci-review`; before
processing `claude-review` findings, invoke `superpowers:receiving-code-review`
and post a per-finding verdict as a PR comment.

---

## Task 8: Verify the recovered days after PR B merges

**Files:** none changed.

**Interfaces:**

- Consumes: PR B, merged and materialized in prod.
- Produces: the number that closes issue #5397.

- [ ] **Step 1: Count Miami's remaining null-term membership days**

```sql
select
    academic_year,
    count(*) as membership_days,
    countif(term is null) as null_term_days,
    countif(semester is null) as null_semester_days,
from `teamster-332318`.`kipptaf_students`.`int_students__attendance_daily`
where _dbt_source_project = 'kippmiami' and is_membership_day
group by academic_year
order by academic_year
```

Expected: `null_term_days` falls from 492,482 to about 511 network-wide for
Miami. Those 511 are the residual the source-data correction in Phase C fixes,
not a defect in this change.

If the count is still in the hundreds of thousands, check which side is missing
before touching any model: query
`kippmiami_powerschool.int_powerschool__terms_spine` for `quarter_rows` (Task 2
Step 4 expected 88) and check whether the Miami archive rebuild actually
refreshed.

- [ ] **Step 2: Confirm nothing regressed in the three NJ districts**

```sql
select
    _dbt_source_project,
    countif(term is null) as null_term_days,
    count(*) as membership_days,
from `teamster-332318`.`kipptaf_students`.`int_students__attendance_daily`
where is_membership_day
group by _dbt_source_project
order by _dbt_source_project
```

Expected: the three NJ districts' `null_term_days` are unchanged from their
pre-merge values. Capture those before the merge so there is something to
compare against. The orphan quarters are the sole source of `term` and
`semester` for 1,752,966 NJ enrollment days, so a regression here is large and
obvious rather than subtle.

- [ ] **Step 3: Report on the issue and close it**

Comment on #5397 with the before and after counts and the residual 511. Terms
are reference data, so these aggregates carry no PII and go out as numbers.

State plainly which of the issue's three named decisions dissolved rather than
being decided: the Focus-over-archive precedence rule (decision 1) never needed
to exist once Focus stopped serving pre-cutover terms, and the 511 residual days
(decision 3) are a source-data correction rather than a model change.

---

## Phase C: the 511 residual days and the dlt revival

Not in this plan, and not in either PR. The spec's change 8 covers correcting
the 511 days on the PowerSchool server and doing a final sync, which needs
Miami's decommissioned PowerSchool Dagster assets revived through dlt. That is
an ingestion change with its own design surface, its own credentials, and no
overlap with the modeling work above.

- [ ] **Step 1: Open a separate issue for it**

After Task 8 reports the residual count, open a `fix` issue for the source
correction plus the dlt revival, matching `.github/ISSUE_TEMPLATE/bug_report.md`
— plain-language sections first, a "For Claude" fold-out last. Label it with the
conventional-commit type, `powerschool` as the source system, and `dagster`.
Link it from #5397 and from the spec.

Do not begin the work in this plan's branch. Do not close #5397 on its account
either: the 492,482 days this plan recovers are the issue's subject, and the 511
are a different defect that happens to have surfaced in the same diagnosis.

---

## Self-Review

Run against the spec after the plan is written, before committing it.

**Spec coverage.** All 8 designed changes map to a task: change 1 to Task 1,
change 2 to Task 3, change 3 to Task 3 (widened from one source file to four),
change 4 to Task 4, change 5 to Task 6, change 6 to Task 5, change 7 to Task 2,
change 8 to Phase C. The spec's Sequencing maps to Tasks 1, 2, and 7; its
Testing to Tasks 1, 4, and 8; its Risks to the model-description rewrite in Task
5 Step 1.

**Two spec corrections this plan makes, deliberately.** Change 3 named only
`sources-kippmiami.yml`, but a four-district `union_relations` needs the spine
declared in all four source files or dbt fails at parse — Task 3 Step 1 adds all
four. Change 5 said to "disable its tests alongside", and neither retiring
wrapper has any tests — Task 6 Step 4 says so explicitly so nobody hunts for
them.

**Type consistency.** The 33-column spine contract is fixed once, in Global
Constraints, and Tasks 1, 3, and 4 all reference that one list. Types come from
`stg_powerschool__terms.yml` verbatim for the 28 raw columns, and from
`int_powerschool__terms` for the 5 quarter columns. The model name is
`int_powerschool__terms_spine` in every task; the package model
`int_powerschool__terms` is never modified and is named as such wherever it
appears.
