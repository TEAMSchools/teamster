# `dbt_utils.deduplicate` cost threshold implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record the measured cost threshold for `dbt_utils.deduplicate` in
`.claude/rules/dbt-sql.md`, and rewrite only the callers whose dedup input
clears it.

**Architecture:** The macro's BigQuery form packs the whole row into a struct
and adds shuffle hops. The replacement is a `row_number()` column in one CTE
filtered by `where rn = 1` in the next. The macro stays the repo default; the
ranked form is the documented exception above about 1M rows in the dedup input.
Each rewrite is proved value-identical against a prod snapshot before it ships.

**Tech Stack:** dbt (BigQuery adapter) via `uv run`, `dbt_utils` 1.4.1, BigQuery
MCP for measurement and proof, trunk for lint.

**Spec:**
`docs/superpowers/specs/2026-09-10-dbt-utils-deduplicate-threshold-design.md`

**Issue:** [#5252](https://github.com/TEAMSchools/teamster/issues/5252)

## Global Constraints

- Worktree is
  `/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule`.
  Every git call is `git -C <worktree>`; every file path is absolute under the
  worktree. Never touch the main checkout path.
- `QUALIFY` is banned in this repo. The replacement is always a named window
  column in one CTE filtered by `WHERE` in the next — never
  `qualify row_number() over (...) = 1`.
- Never `select * except (rn)` to drop the helper column. Enumerate the output
  columns instead.
- A filter that ran AFTER the macro (a soft-delete predicate, typically) shares
  the `WHERE` with `rn = 1`. It must NOT sit in the CTE that computes `rn` —
  that changes which row wins.
- Rewrite gate, both conditions required: dedup input above about 1,000,000 rows
  AND the model at 1 slot hour or more in the 7-day prod ranking.
- These are contract-enforced models and dbt Cloud CI builds `kipptaf` only, so
  every rewrite carries a value-level proof: 0 only-in-old, 0 only-in-new, 0
  differing.
- Never run bare `dbt`. Always `uv run dbt ... --project-dir <abs-path>`.
- Before pushing any `.sql`, `.yml`, or `.md`, run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  with cwd inside the worktree.
- Open files under `src/dbt/` with the Read tool, never `cat` — the directory's
  rules load on a Read path match and not on a Bash command string.

---

### Task 1: Size the five dedup inputs and freeze the rewrite list

The three cost-ranked candidates hold **five** dedup call sites, not three. All
five are sized before anything is rewritten.
`stg_illuminate__dna_assessments__students_assessments` is already measured at
4.16M rows and needs no sizing.

| Model                                           | Line | Input CTE              |
| ----------------------------------------------- | ---: | ---------------------- |
| `int_assessments__resolved_section_enrollments` |   31 | `internal_anchored`    |
| `int_assessments__resolved_section_enrollments` |  357 | `all_candidates`       |
| `fct_assessment_scores_enrollment_scoped`       |  216 | `iready_scores_raw`    |
| `fct_assessment_scores_enrollment_scoped`       |  271 | `star_scores_raw`      |
| `int_assessments__scaffold`                     |  131 | `internal_assessments` |

**Files:**

- Modify:
  `docs/superpowers/specs/2026-09-10-dbt-utils-deduplicate-threshold-design.md`
  (the Candidates table)

**Interfaces:**

- Consumes: nothing.
- Produces: a frozen rewrite list — the set of `(model, input CTE)` pairs whose
  input exceeds 1,000,000 rows. Tasks 3 and 4 consume it.

- [ ] **Step 1: Load the local dbt rules**

Invoke the `dbt-local-dev` skill. It covers `--defer` / `--favor-state` traps
and dev-schema naming that otherwise make a local compile disagree with prod.

- [ ] **Step 2: Compile the three models**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
uv run dbt compile \
  --project-dir $wt/src/dbt/kipptaf \
  --select int_assessments__resolved_section_enrollments \
           fct_assessment_scores_enrollment_scoped \
           int_assessments__scaffold
```

Compiled SQL lands under `$wt/src/dbt/kipptaf/target/compiled/kipptaf/models/`.

- [ ] **Step 3: Count the rows feeding each of the five dedup sites**

For each site, take the compiled SQL text from the top through the end of the
input CTE, drop everything after it, and append a count. The shape, for
`int_assessments__scaffold`, whose input CTE is `internal_assessments` — the CTE
bodies come verbatim from the compiled file, not typed by hand:

```sql
/* dedupsize scaffold_internal_assessments */
with
    assessment_region_scaffold as (/* compiled body */),
    school_to_region as (/* compiled body */),
    internal_assessments as (/* compiled body */)
select count(*) as dedup_input_rows
from internal_assessments
```

Run each through the BigQuery MCP `execute_sql` tool. Record all five counts.

- [ ] **Step 4: Apply the gate and freeze the list**

A site is rewritten only if `dedup_input_rows > 1000000` AND its model sits at 1
slot hour or more in the 7-day ranking. All three models already clear the
slot-hour condition (16.74, 12.91, 7.08), so in practice the row count decides.

- [ ] **Step 5: Record every result in the spec, including the skips**

Replace the Candidates table in the spec with one row per dedup site, carrying
the measured `dedup_input_rows` and a disposition of `rewrite` or
`measured, skipped`. Recording the skips is a deliverable, not bookkeeping — it
is what stops the next reader re-measuring them.

Keep the two sites already measured, so the table is the complete record:
`stg_illuminate__dna_assessments__students_assessments` at 4.16M rows
(`rewrite`) and `stg_schoolmint_grow__observations` at 125k rows
(`measured, skipped`).

- [ ] **Step 6: Lint and commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  docs/superpowers/specs/2026-09-10-dbt-utils-deduplicate-threshold-design.md </dev/null
git -C $wt add docs/superpowers/specs/2026-09-10-dbt-utils-deduplicate-threshold-design.md
git -C $wt commit -m "docs(dbt): size the five dedup inputs and freeze the rewrite list

Refs #5252

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Write the threshold into the dbt SQL rules

**Files:**

- Modify: `.claude/rules/dbt-sql.md` — insert a new `###` subsection immediately
  after `### dbt_utils.deduplicate order_by on BigQuery` (currently line 269),
  inside `## Row picking, dedup & surrogate keys`.

**Interfaces:**

- Consumes: nothing. Runs independently of Task 1.
- Produces: the documented rule every later rewrite cites.

- [ ] **Step 1: Insert the subsection**

Exact content to insert:

````markdown
### dbt_utils.deduplicate cost: ranked column above ~1M rows

The macro compiles on BigQuery to
`array_agg(original order by <expr> limit 1)[offset(0)]` grouped by the
partition key. That packs the whole row into a struct, inflates the input
shuffle, and pushes the aggregate past BigQuery's single-round-shuffle threshold
— so the plan gains `Repartition` stages that a window function never emits.

**Row count drives the penalty. Row width does not** — do not re-derive the
width hypothesis. Measured on prod tables, macro against ranked column, output
byte-identical in every pair (#5252):

|  Rows | Bytes/row | Macro / ranked slot time | Macro / ranked shuffle |
| ----: | --------: | -----------------------: | ---------------------: |
| 44.5M |       241 |                     6.6x |                   5.4x |
| 4.16M |        56 |                     4.6x |                   7.1x |
|  125k |      3629 |                     2.2x |                   1.7x |
|   18k |       195 |                     2.5x |         below 0.02 GiB |

The widest table shows the smallest penalty; the narrowest shows the largest
shuffle ratio.

**The default stays `dbt_utils.deduplicate()`** — it is one call, and `QUALIFY`
is banned here, so the window form always costs an extra CTE plus an `rn`
column. **Above about 1M rows in the dedup input, use the ranked-column form
instead:**

```sql
with
    row_numbered as (
        select
            <columns>,

            row_number() over (
                partition by <key> order by <expr> desc
            ) as rn,
        from {{ source(...) }}
    )

select <columns>,
from row_numbered
where rn = 1
```

Two traps when converting:

- A filter that ran AFTER the macro (a soft-delete predicate, typically) shares
  the `WHERE` with `rn = 1`. It must not sit in the CTE that computes `rn` — the
  window is evaluated before either predicate applies, so moving the filter up
  changes which row wins.
- Do not `select * except (rn)` to drop the helper column. Enumerate the output
  columns instead.
````

- [ ] **Step 2: Verify the heading level and placement**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
grep -n '^###\? ' $wt/.claude/rules/dbt-sql.md | sed -n '1,25p'
```

Expected: the new `### dbt_utils.deduplicate cost: ranked column above ~1M rows`
sits between `### dbt_utils.deduplicate order_by on BigQuery` and
`### Don't inline CASE expressions in generate_surrogate_key`, still under
`## Row picking, dedup & surrogate keys`. Heading levels increment by one
(markdownlint MD001).

- [ ] **Step 3: Lint**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  .claude/rules/dbt-sql.md </dev/null
```

Expected: no issues. A widened table cell trips markdownlint MD060 until the
commit-time fmt hook re-pads it — commit and let the hook fix it, do not
hand-align.

- [ ] **Step 4: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
git -C $wt add .claude/rules/dbt-sql.md
git -C $wt commit -m "docs(dbt): record the deduplicate cost threshold in the SQL rules

Refs #5252

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Rewrite `stg_illuminate__dna_assessments__students_assessments`

Already measured: 4.16M rows in the dedup input, 1.03 slot hours. Clears both
gate conditions. This task is the worked example every Task 4 rewrite follows.

**Files:**

- Modify:
  `src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__students_assessments.sql`

**Interfaces:**

- Consumes: the rule from Task 2.
- Produces: the rewrite shape and the proof-query shape that Task 4 reuses.

- [ ] **Step 1: Capture the old compiled SQL**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
uv run dbt compile --project-dir $wt/src/dbt/kipptaf \
  --select stg_illuminate__dna_assessments__students_assessments
cp $wt/src/dbt/kipptaf/target/compiled/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__students_assessments.sql \
  /workspaces/teamster/.claude/scratch/illuminate_old.sql
```

- [ ] **Step 2: Replace the model body**

The whole file becomes:

```sql
with
    row_numbered as (
        select
            student_assessment_id,
            student_id,
            assessment_id,
            date_taken,
            created_at,
            updated_at,
            version_id,

            row_number() over (
                partition by student_id, assessment_id
                order by updated_at desc, student_assessment_id desc
            ) as rn,
        from {{ source("illuminate_dna_assessments", "students_assessments") }}
    )

select
    student_assessment_id,
    student_id,
    assessment_id,
    date_taken,
    created_at,
    updated_at,
    version_id,
from row_numbered
where rn = 1
```

The seven columns are enumerated twice on purpose: no `except (rn)`. Plain
column refs come first, then a blank line, then the window function — sqlfluff
ST06 requires window functions last.

- [ ] **Step 3: Capture the new compiled SQL**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
uv run dbt compile --project-dir $wt/src/dbt/kipptaf \
  --select stg_illuminate__dna_assessments__students_assessments
cp $wt/src/dbt/kipptaf/target/compiled/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__students_assessments.sql \
  /workspaces/teamster/.claude/scratch/illuminate_new.sql
```

- [ ] **Step 4: Prove the two are value-identical**

Substitute the two captured compiled bodies for `<old compiled sql>` and
`<new compiled sql>` and run through the BigQuery MCP `execute_sql` tool:

```sql
with
    old as (<old compiled sql>),
    new as (<new compiled sql>),
    joined as (
        select
            to_json_string(o) as o_json,
            to_json_string(n) as n_json,
        from old as o
        full join new as n
            on o.student_id = n.student_id
            and o.assessment_id = n.assessment_id
    )

select
    countif(n_json is null) as only_in_old,
    countif(o_json is null) as only_in_new,
    countif(
        o_json is not null and n_json is not null and o_json != n_json
    ) as differing,
from joined
```

Expected: `only_in_old` 0, `only_in_new` 0, `differing` 0. Anything else stops
the task — do not commit a rewrite that changes values.

- [ ] **Step 5: Lint**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/illuminate/dlt/staging/stg_illuminate__dna_assessments__students_assessments.sql </dev/null
```

Expected: no issues. ST06 (column order) and CV03 (trailing commas) are the two
that fire on this shape.

- [ ] **Step 6: Build the model and its children**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
uv run dbt build --project-dir $wt/src/dbt/kipptaf \
  --select stg_illuminate__dna_assessments__students_assessments+
```

Expected: all models and tests pass. The contract on the staging model fails
loudly if a column name or type moved.

- [ ] **Step 7: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
git -C $wt add -u
git -C $wt commit -m "perf(illuminate): dedupe students_assessments with a row_number window

4.16M rows in the dedup input. Value-identical against prod: 0 only-in-old,
0 only-in-new, 0 differing.

Refs #5252

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Rewrite each remaining site on the frozen list

Run this task once per `(model, input CTE)` pair that Task 1 marked `rewrite`.
If Task 1 marked every site `measured, skipped`, skip this task entirely and say
so in the PR body.

**Files:**

- Modify: one of
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__resolved_section_enrollments.sql`,
  `src/dbt/kipptaf/models/marts/facts/fct_assessment_scores_enrollment_scoped.sql`,
  `src/dbt/kipptaf/models/assessments/intermediate/int_assessments__scaffold.sql`

**Interfaces:**

- Consumes: the frozen list from Task 1; the rewrite and proof shapes from
  Task 3.
- Produces: one rewritten dedup site per run, each with its proof recorded.

- [ ] **Step 1: Read the model and find the site**

Open the file with the Read tool, never `cat` — `src/dbt/` carries rules that
load on a Read path match and not on a Bash command string. Note three things at
the site: the input CTE's column list, the `partition_by` and `order_by`
verbatim, and **any filter applied to the macro's output downstream**.

- [ ] **Step 2: Capture the old compiled SQL**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
uv run dbt compile --project-dir $wt/src/dbt/kipptaf --select <model_name>
cp $wt/src/dbt/kipptaf/target/compiled/kipptaf/models/<path>/<model_name>.sql \
  /workspaces/teamster/.claude/scratch/<model_name>_old.sql
```

- [ ] **Step 3: Convert the site**

Add `row_number() over (partition by <partition_by> order by <order_by>) as rn`
to the input CTE as its last column, after a blank line following the plain
column refs. Delete the `dbt_utils.deduplicate` block. In the CTE that consumed
the macro's output, read from the input CTE and add `rn = 1` to its `WHERE`.

If Step 1 found a downstream filter on the macro's output, it joins `rn = 1` in
that same `WHERE` with `and`. It must not move into the CTE that computes `rn`.
Enumerate columns rather than using `except (rn)`.

- [ ] **Step 4: Capture the new compiled SQL**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
uv run dbt compile --project-dir $wt/src/dbt/kipptaf --select <model_name>
cp $wt/src/dbt/kipptaf/target/compiled/kipptaf/models/<path>/<model_name>.sql \
  /workspaces/teamster/.claude/scratch/<model_name>_new.sql
```

- [ ] **Step 5: Prove the two are value-identical**

Same shape as Task 3 Step 4, with the model's own key columns in the
`full join`:

```sql
with
    old as (<old compiled sql>),
    new as (<new compiled sql>),
    joined as (
        select
            to_json_string(o) as o_json,
            to_json_string(n) as n_json,
        from old as o
        full join new as n on o.<key> = n.<key>
    )

select
    countif(n_json is null) as only_in_old,
    countif(o_json is null) as only_in_new,
    countif(
        o_json is not null and n_json is not null and o_json != n_json
    ) as differing,
from joined
```

Expected: 0, 0, 0. Get the model's key from its properties YAML `unique`
combination-of-columns test. Anything nonzero stops the task.

- [ ] **Step 6: Lint and build**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
cd $wt && /workspaces/teamster/.trunk/tools/trunk check --force --no-fix \
  src/dbt/kipptaf/models/<path>/<model_name>.sql </dev/null
uv run dbt build --project-dir $wt/src/dbt/kipptaf --select <model_name>+
```

Expected: no lint issues; all models and tests pass.

- [ ] **Step 7: Commit**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
git -C $wt add -u
git -C $wt commit -m "perf(assessments): dedupe <model_name> with a row_number window

<N> rows in the dedup input. Value-identical against prod: 0 only-in-old,
0 only-in-new, 0 differing.

Refs #5252

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Correct the issue body

**Files:**

- Modify: issue #5252 body on GitHub (no repo file).

**Interfaces:**

- Consumes: the two corrections recorded in the spec.
- Produces: an issue whose premise matches what was measured.

- [ ] **Step 1: Fetch the true stored body**

```bash
GITHUB_TOKEN= gh api repos/TEAMSchools/teamster/issues/5252 --jq .body \
  > /workspaces/teamster/.claude/scratch/issue5252.md
```

Fetch with raw `gh api`, never `mcp__github__issue_read` — the read tools
entity-encode the body, and writing that back stores the entities for real.

- [ ] **Step 2: Edit the file to carry four corrections**

1. `stg_powerschool__pgfinalgrades` is not a caller. Its macro call lives in
   `src/dbt/powerschool/models/sis/staging/odbc/`, archived under #4442 and
   `+enabled: false`. Its 12.9 slot hours belong to the live `dlt/` model, which
   has no dedup. Remove it from the candidates table.
1. Six nodes, 14.3 slot hours total, are misattributed the same way: the
   `node_id` in the query comment carries only the model name and cannot tell
   the three ingestion variants apart.
1. The caller-list grep counts comment mentions. Replace it with
   `grep -rl -E "^[[:space:]]*(\{\{[[:space:]]*)?dbt_utils\.deduplicate\(" src/dbt/*/models --include='*.sql'`.
   Real total on current main: 116 callers, 108 live.
1. Amend the done-when: drop the "no caller above 10 slot hours" target. The
   macro swap cannot deliver it — on schoolmint the swap is worth about 1 of
   that model's 9.97 slot hours. Replace it with the spec's done-when.

Write one line per paragraph. GitHub renders every newline as a break, so
hard-wrapped prose displays as a ragged narrow column.

- [ ] **Step 3: Write the corrected body back**

Use `mcp__github__issue_write` with `method: update`, `issue_number: 5252`, and
`body` set to the edited file's contents. The write tools do not alter body
text; only the read tools encode. An issue-body `PATCH` via `gh api` is NOT on
this repo's `gh` allowlist, so do not reach for it.

Passing `labels` would REPLACE the full set and drop `dbt` / `perf` — omit the
field entirely.

- [ ] **Step 4: Verify the stored body matches intent**

```bash
GITHUB_TOKEN= gh api repos/TEAMSchools/teamster/issues/5252 --jq .body | head -40
```

Expected: the four corrections are present and no entity-encoding artifacts
(`&amp;`, `&#34;`) appeared. Verify through this raw GET, not
`mcp__github__issue_read` — the read tool encodes and will show phantom
corruption in a body that is stored clean.

---

### Task 6: Open the follow-up issue for the non-macro cost

**Files:**

- Create: a new GitHub issue, child of #5212.

**Interfaces:**

- Consumes: Task 1's measurements, which show how much of each model's cost the
  macro actually explained.
- Produces: the home for the cost this issue deliberately does not chase.

- [ ] **Step 1: Read the issue template**

Open `.github/ISSUE_TEMPLATE/feature_request.md` with the Read tool and match
its structure — plain-language sections first, a "For Claude" fold-out last. The
API applies no template on its own.

- [ ] **Step 2: Create the issue**

Title:
`perf(assessments): cut the non-deduplicate cost on the two assessment nodes above 10 slot hours`

Body covers: `int_assessments__resolved_section_enrollments` (16.74 slot hours)
and `fct_assessment_scores_enrollment_scoped` (12.91) stay above 10 after the
macro swap, because the macro was not their main cost. Cite Task 1's measured
dedup input sizes and the per-model share the swap removed. Parent: #5212. Label
`dbt` and `perf`.

Use `mcp__github__issue_write`. Then verify the returned title and body match
intent — malformed parameters succeed with the wrong payload.

- [ ] **Step 3: Link it under the parent**

Use `mcp__github__sub_issue_write` with `method: add`, `issue_number: 5212`, and
`sub_issue_id` set to the numeric `id` (not the `number`) returned by Step 2. A
`gh api` POST to the `sub_issues` endpoint is NOT on this repo's `gh` allowlist.

---

### Task 7: Open the pull request

**Files:**

- Create: a pull request from `cbini/perf/claude-deduplicate-threshold-rule`
  into `main`.

**Interfaces:**

- Consumes: every prior task's commits.
- Produces: the PR that ships the rule and the rewrites.

- [ ] **Step 1: Lint everything the branch touched**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
cd $wt && git diff --name-only origin/main...HEAD \
  | while read -r f; do [ -f "$f" ] && printf '%s\n' "$f"; done \
  | xargs /workspaces/teamster/.trunk/tools/trunk check --force --no-fix </dev/null
```

Expected: no issues. Filter to existing paths first — a `--force` check
hard-errors on a deleted file.

- [ ] **Step 2: Push**

```bash
wt=/workspaces/teamster/.worktrees/cbini/perf/claude-deduplicate-threshold-rule
git -C $wt push
```

- [ ] **Step 3: Open the PR**

Body from `.github/pull_request_template.md`, keeping every line the template
supplies and answering its prompts in place. Include `Closes #5252` so the PR
lands on the project boards, and state plainly which sites were rewritten and
which were measured and skipped. Never `gh project item-add` a PR.

- [ ] **Step 4: Handle CI and review**

Invoke `pr-ci-review` for CI state, and `superpowers:receiving-code-review`
before processing any `claude-review` findings. Post a per-finding verdict as a
PR comment.
