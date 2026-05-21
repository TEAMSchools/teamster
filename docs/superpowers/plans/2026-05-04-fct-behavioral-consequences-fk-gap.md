# `fct_behavioral_consequences` FK Hash-Drift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the 100% FK orphan rate on
`fct_behavioral_consequences.behavioral_incident_key → fct_behavioral_incidents.behavioral_incident_key`
by canonicalizing the second hash input across both facts.

**Architecture:** Add a `_dbt_source_project` column (the canonical region code,
derived from `_dbt_source_relation` via the existing `extract_code_location`
macro) to the two kipptaf cross-district union models —
`int_deanslist__incidents` and `int_deanslist__incidents__penalties` — then
change both facts to hash on `[incident_id, _dbt_source_project]` so producer
and consumer hash on identical inputs by construction. Closes #3724; advances
#3142 by 2 of ~73 union models.

**Tech Stack:** dbt (BigQuery), Jinja macros (`dbt_utils.union_relations`,
`dbt_utils.generate_surrogate_key`, `extract_code_location`), `kipptaf` dbt
project, dbt Cloud CI (Staging env, job id resolved at PR time).

**Branch:** `cbini/fix/claude-behavioral-incident-key-hash-drift` — work in the
worktree at
`/workspaces/teamster/.worktrees/cbini/fix/claude-behavioral-incident-key-hash-drift`.
Prepend `cd <worktree>` to every Bash call. Verify with
`git branch --show-current` before each commit.

**Spec:**
[`docs/superpowers/specs/2026-05-04-fct-behavioral-consequences-fk-gap-design.md`](../specs/2026-05-04-fct-behavioral-consequences-fk-gap-design.md).

**Pre-flight CLAUDE.md reads (subagents must do these before any work):**

- `/workspaces/teamster/CLAUDE.md`
- `/workspaces/teamster/src/dbt/CLAUDE.md`
- `/workspaces/teamster/src/dbt/kipptaf/CLAUDE.md`
- `/workspaces/teamster/src/dbt/kipptaf/models/marts/CLAUDE.md` (for fact tasks)

**Skills the subagent must invoke before starting work:**

- `Skill` with skill=`dbt:using-dbt-for-analytics-engineering` — required for
  any task that touches a `.sql` model.
- `Skill` with skill=`superpowers:verification-before-completion` — required
  before marking the final verification task complete.

**Anti-patterns to avoid (negation list — subagents otherwise re-introduce
these):**

- Do NOT inline `regexp_extract(_dbt_source_relation, r'(kipp\w+)_')` inside
  fact SQL. Use `_dbt_source_project` from the upstream union model.
- Do NOT rename `extract_code_location` to `extract_source_project` in
  `macros/utils.sql` — that rename belongs to #3142.
- Do NOT modify other call sites of `union_dataset_join_clause` — that mass
  replacement also belongs to #3142.
- Do NOT replace `union_dataset_join_clause` calls inside the two facts being
  modified. They join to enrollments (a different union model that does not yet
  have `_dbt_source_project`); leave the macro call alone.
- Do NOT add `_dbt_source_project` to any union model other than the two named
  here.
- Do NOT touch `int_deanslist__incidents__custom_fields__pivot`,
  `int_deanslist__incidents__actions`, `int_deanslist__incidents__attachments`,
  or `int_deanslist__incidents__custom_fields`.
- Do NOT add `_dbt_source_project` to staging-layer (`stg_*`) or district-level
  (`kippcamden_deanslist.*`, `kippnewark_deanslist.*`, `kippmiami_deanslist.*`)
  models. The column is added at the kipptaf-layer union models only.
- Do NOT change column ordering, descriptions, or tests on either fact's
  properties YAML beyond what each task specifies.
- Do NOT use `select distinct`, `qualify row_number()=1`, or
  `dbt_utils.deduplicate` anywhere in this plan — no deduplication is needed.

---

## File Structure

| File                                                                                        | Responsibility                                                                                 | Change                                                                                                                                                  |
| ------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`            | Cross-district union of incidents + location_key resolution                                    | Wrap union in CTE; add `_dbt_source_project`                                                                                                            |
| `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql` | Cross-district union of incident penalties                                                     | Wrap union in CTE; add `_dbt_source_project`                                                                                                            |
| `src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql`                           | Parent fact for behavioral incidents                                                           | Replace `_dbt_source_relation` with `_dbt_source_project` in `behavioral_incident_key` hash input                                                       |
| `src/dbt/kipptaf/models/marts/facts/fct_behavioral_consequences.sql`                        | Child fact carrying penalty/consequence rows; FKs to parent fact via `behavioral_incident_key` | Replace `_dbt_source_relation` with `_dbt_source_project` in both surrogate-key hashes (`behavioral_consequence_key` PK + `behavioral_incident_key` FK) |

**Files NOT touched** (verified during plan authoring):

- Properties YAMLs for the two intermediates — neither enumerates
  `_dbt_source_relation` today; intermediates aren't contract-enforced
  (`config.contract.enforced` is false at this layer per
  `kipptaf/dbt_project.yml`), so adding a passthrough column doesn't require a
  YAML edit.
- Properties YAMLs for the two facts — column shape, types, contracts, and tests
  are unchanged. `behavioral_incident_key` and `behavioral_consequence_key`
  remain `STRING` PK/FK columns.
- `macros/utils.sql` — see anti-pattern list.

---

## Task 1: Add `_dbt_source_project` to `int_deanslist__incidents`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`

**Context:** Today the model is a single statement that joins
`dbt_utils.union_relations(...)` directly to
`stg_google_sheets__people__locations`. Wrap the union in a `union_relations`
CTE (matching the convention in
[`int_powerschool__teacher_grade_levels.sql`](../../src/dbt/kipptaf/models/powerschool/intermediate/int_powerschool__teacher_grade_levels.sql)),
then add `_dbt_source_project` derived from the existing `extract_code_location`
macro.

- [ ] **Step 1: Replace the file contents**

Replace the entire file with:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_deanslist", "int_deanslist__incidents"),
                    source("kippcamden_deanslist", "int_deanslist__incidents"),
                    source("kippmiami_deanslist", "int_deanslist__incidents"),
                ]
            )
        }}
    )

select
    u.*,

    {{ extract_code_location("u") }} as _dbt_source_project,

    loc.location_key,
from union_relations as u
left join
    {{ ref("stg_google_sheets__people__locations") }} as loc
    on u.school_id = loc.deanslist_school_id
    and not loc.is_pathways
    and loc.location_name <> 'KIPP Whittier Elementary'
```

- [ ] **Step 2: Compile and inspect**

Run from the worktree root:

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-behavioral-incident-key-hash-drift
uv run dbt compile --select int_deanslist__incidents --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: compile succeeds. Open
`src/dbt/kipptaf/target/compiled/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql`
and confirm the `_dbt_source_project` SELECT line reads literally
`regexp_extract(u._dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,`.

- [ ] **Step 3: Build and verify column values**

```bash
uv run dbt build --select int_deanslist__incidents --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: 1 model built, all attached tests pass.

Then via the BigQuery MCP tool, run:

```sql
select distinct _dbt_source_project
from `teamster-332318.zz_<your-username>_kipptaf_deanslist.int_deanslist__incidents`
order by 1
```

Expected: exactly three rows — `kippcamden`, `kippmiami`, `kippnewark`. No
NULLs, no other values. If you don't know your dev schema name, run
`uv run dbt debug --project-dir src/dbt/kipptaf --target dev` and look for
`schema:` under your profile.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents.sql
git commit -m "$(cat <<'EOF'
feat(dbt): add _dbt_source_project to int_deanslist__incidents

Surfaces the canonical kipp* project code from _dbt_source_relation as a
materialized column so downstream consumers can hash and join on a stable
identifier across union-relation models. Incrementally advances #3142.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add `_dbt_source_project` to `int_deanslist__incidents__penalties`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql`

**Context:** Today the file is a single bare `dbt_utils.union_relations(...)`
call. Wrap in a CTE, then SELECT all columns plus `_dbt_source_project`.

- [ ] **Step 1: Replace the file contents**

Replace the entire file with:

```sql
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_deanslist", "int_deanslist__incidents__penalties"
                    ),
                    source(
                        "kippcamden_deanslist", "int_deanslist__incidents__penalties"
                    ),
                    source(
                        "kippmiami_deanslist", "int_deanslist__incidents__penalties"
                    ),
                ]
            )
        }}
    )

select
    *,

    {{ extract_code_location("union_relations") }} as _dbt_source_project,
from union_relations
```

- [ ] **Step 2: Compile and inspect**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-behavioral-incident-key-hash-drift
uv run dbt compile --select int_deanslist__incidents__penalties --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: compile succeeds. Compiled SQL contains
`regexp_extract(union_relations._dbt_source_relation, r'(kipp\w+)_') as _dbt_source_project,`.

- [ ] **Step 3: Build and verify column values**

```bash
uv run dbt build --select int_deanslist__incidents__penalties --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: 1 model built, all attached tests pass.

BigQuery MCP query:

```sql
select distinct _dbt_source_project
from `teamster-332318.zz_<your-username>_kipptaf_deanslist.int_deanslist__incidents__penalties`
order by 1
```

Expected: exactly three rows — `kippcamden`, `kippmiami`, `kippnewark`.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/deanslist/api/intermediate/int_deanslist__incidents__penalties.sql
git commit -m "$(cat <<'EOF'
feat(dbt): add _dbt_source_project to int_deanslist__incidents__penalties

Same canonicalization as the parent incidents intermediate, so child fact
fct_behavioral_consequences can hash its FK to fct_behavioral_incidents on
identical inputs. Incrementally advances #3142.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Switch `fct_behavioral_incidents.behavioral_incident_key` to `_dbt_source_project`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql` (the
  `behavioral_incident_key` SELECT, currently at lines 35–36)

**Context:** Only the second hash input changes. `incident_id` stays.
`i._dbt_source_relation` becomes `i._dbt_source_project`.

- [ ] **Step 1: Edit the surrogate-key call**

Replace exactly this block (lines 35–36 in the current file):

```sql
    {{ dbt_utils.generate_surrogate_key(["i.incident_id", "i._dbt_source_relation"]) }}
    as behavioral_incident_key,
```

With:

```sql
    {{ dbt_utils.generate_surrogate_key(["i.incident_id", "i._dbt_source_project"]) }}
    as behavioral_incident_key,
```

Leave every other line untouched. Do NOT modify the `student_enrollment_key` or
`referring_staff_key` blocks. Do NOT modify the `union_dataset_join_clause` call
on the enrollments join.

- [ ] **Step 2: Compile**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-behavioral-incident-key-hash-drift
uv run dbt compile --select fct_behavioral_incidents --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: compile succeeds. Compiled SQL shows
`to_hex(md5(cast(coalesce(cast(i.incident_id as string), '_dbt_utils_surrogate_key_null_') || '-' || coalesce(cast(i._dbt_source_project as string), '_dbt_utils_surrogate_key_null_') as string)))`
(or the equivalent `to_hex(md5_*)` form generated by
`dbt_utils.generate_surrogate_key`).

- [ ] **Step 3: Build (this rebuilds the fact view) and inspect row count**

```bash
uv run dbt build --select fct_behavioral_incidents --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: 1 model built, all attached tests pass. Row count vs prod should match
within ±0% (this fact is a view; the change is hash-only — no rows added or
dropped).

BigQuery MCP query:

```sql
select
  (select count(*) from `teamster-332318.kipptaf_marts.fct_behavioral_incidents`) as prod_rows,
  (select count(*) from `teamster-332318.zz_<your-username>_kipptaf_marts.fct_behavioral_incidents`) as dev_rows
```

Expected: `prod_rows = dev_rows` exactly.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_behavioral_incidents.sql
git commit -m "$(cat <<'EOF'
fix(dbt): hash fct_behavioral_incidents.behavioral_incident_key on _dbt_source_project

Uses the canonical project code instead of the raw _dbt_source_relation
(which carries the source TABLE name and therefore differs from the child
fact's relation string). Half of #3724.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Switch `fct_behavioral_consequences` surrogate keys to `_dbt_source_project`

**Files:**

- Modify: `src/dbt/kipptaf/models/marts/facts/fct_behavioral_consequences.sql`
  (lines 17–28)

**Context:** Both hashes on this fact change — the PK
(`behavioral_consequence_key`) and the FK to the parent
(`behavioral_incident_key`). Both swap `p._dbt_source_relation` for
`p._dbt_source_project`.

- [ ] **Step 1: Edit both surrogate-key calls**

Replace exactly this block (lines 17–28 in the current file):

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "p.incident_id",
                "p.incident_penalty_id",
                "p._dbt_source_relation",
            ]
        )
    }} as behavioral_consequence_key,

    {{ dbt_utils.generate_surrogate_key(["p.incident_id", "p._dbt_source_relation"]) }}
    as behavioral_incident_key,
```

With:

```sql
    {{
        dbt_utils.generate_surrogate_key(
            [
                "p.incident_id",
                "p.incident_penalty_id",
                "p._dbt_source_project",
            ]
        )
    }} as behavioral_consequence_key,

    {{ dbt_utils.generate_surrogate_key(["p.incident_id", "p._dbt_source_project"]) }}
    as behavioral_incident_key,
```

Leave the rest of the file (CTE, joins,
`where p.incident_penalty_id is not null`, etc.) untouched. Do NOT touch the
`union_dataset_join_clause` call on the enrollments join.

- [ ] **Step 2: Compile**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-behavioral-incident-key-hash-drift
uv run dbt compile --select fct_behavioral_consequences --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: compile succeeds.

- [ ] **Step 3: Build the fact and run its tests**

```bash
uv run dbt build --select fct_behavioral_consequences --project-dir src/dbt/kipptaf --target dev --defer --state src/dbt/kipptaf/target/prod/
```

Expected: 1 model built, all attached tests pass — including the
previously-failing `relationships` test on
`behavioral_incident_key → fct_behavioral_incidents.behavioral_incident_key`.

If the relationships test still warns/errors, **stop and diagnose**: query both
facts and confirm hash inputs actually agree. Do not paper over with `--exclude`
or by relaxing the test.

- [ ] **Step 4: Commit**

```bash
git add src/dbt/kipptaf/models/marts/facts/fct_behavioral_consequences.sql
git commit -m "$(cat <<'EOF'
fix(dbt): hash fct_behavioral_consequences keys on _dbt_source_project

Aligns behavioral_incident_key inputs with fct_behavioral_incidents so the
relationships test passes — the parent and child were previously hashing
two different table-name strings for the same logical incident, producing
100% orphans. Closes #3724.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Cross-fact hash equality verification

**Files:** none (read-only check).

**Context:** Confirm the producer and consumer now produce identical hashes for
the same logical incident. Catches typos in either Task 3 or Task 4 (e.g., a
stray remaining `_dbt_source_relation`).

- [ ] **Step 1: Sample a handful of (incident_id, project) tuples from both
      facts**

BigQuery MCP query against your dev schema (explicit hash equality check):

```sql
select
  count(*) as n_consequence_keys,
  countif(p.behavioral_incident_key is null) as n_orphan_keys
from (
  select distinct behavioral_incident_key
  from `teamster-332318.zz_<your-username>_kipptaf_marts.fct_behavioral_consequences`
) c
left join (
  select distinct behavioral_incident_key
  from `teamster-332318.zz_<your-username>_kipptaf_marts.fct_behavioral_incidents`
) p
  using (behavioral_incident_key)
```

Expected: `n_orphan_keys = 0`. (Pre-fix: `n_orphan_keys = n_consequence_keys`.
The exact count of `n_consequence_keys` should be near 212,694 ± natural growth
since 2026-04-22.)

- [ ] **Step 2: Confirm `_dbt_source_project` propagates onto the fact**

```sql
select distinct _dbt_source_project
from `teamster-332318.zz_<your-username>_kipptaf_deanslist.int_deanslist__incidents__penalties`
```

Expected: 3 values (`kippnewark`, `kippcamden`, `kippmiami`). If any NULL
appears, Task 2 introduced a regression — stop.

- [ ] **Step 3: No commit (verification-only task)**

If both checks pass, proceed to Task 6.

---

## Task 6: Run the full downstream test suite for both facts

**Files:** none (CI dry run).

**Context:** Catch any test regressions on either fact (uniqueness, not_null,
other relationships). The two intermediates feed only these two facts via the
deanslist domain, but the facts may have additional FKs (date dims, location
dim, staff dim) whose tests should still pass.

- [ ] **Step 1: Build both intermediates and both facts plus their tests**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-behavioral-incident-key-hash-drift
uv run dbt build \
  --select int_deanslist__incidents int_deanslist__incidents__penalties fct_behavioral_incidents fct_behavioral_consequences \
  --project-dir src/dbt/kipptaf \
  --target dev \
  --defer \
  --state src/dbt/kipptaf/target/prod/
```

Expected: 4 models built, all attached tests pass.

- [ ] **Step 2: Inspect any warnings**

If any test warns rather than errors, copy the warning text and verify it is
unrelated to this change (e.g., pre-existing dim_dates range gaps from #3719).
If a warning references `behavioral_incident_key`, `behavioral_consequence_key`,
or `_dbt_source_project`, treat as a failure and diagnose.

- [ ] **Step 3: Trunk check**

```bash
/workspaces/teamster/.trunk/tools/trunk check --ci
```

Expected: exit 0. If sqlfluff flags anything, fix per `.trunk/config/.sqlfluff`
rules and re-stage.

- [ ] **Step 4: No commit if everything's clean**

If trunk check made formatting changes, commit them as a separate
`chore: trunk fmt fixes` commit.

---

## Task 7: Push and open PR

**Files:** none (git/GH operations).

- [ ] **Step 1: Verify branch state**

```bash
cd /workspaces/teamster/.worktrees/cbini/fix/claude-behavioral-incident-key-hash-drift
git branch --show-current
git log --oneline origin/main..HEAD
```

Expected: branch is `cbini/fix/claude-behavioral-incident-key-hash-drift`. Five
commits since `origin/main`: spec, two intermediates, two facts (a sixth if Task
6 produced a trunk fmt commit).

- [ ] **Step 2: Push**

```bash
git push -u origin cbini/fix/claude-behavioral-incident-key-hash-drift
```

- [ ] **Step 3: Open PR via `mcp__github__create_pull_request`**

Title: `fix(dbt): align behavioral_incident_key hash inputs across both facts`

Body (use the `.github/pull_request_template.md` skeleton — fill in summary
referencing #3724 and #3142):

```markdown
## Summary

- Adds `_dbt_source_project` to `int_deanslist__incidents` and
  `int_deanslist__incidents__penalties` (2 of ~73 cross-district union models
  for #3142).
- Switches `fct_behavioral_incidents.behavioral_incident_key`,
  `fct_behavioral_consequences.behavioral_incident_key`, and
  `fct_behavioral_consequences.behavioral_consequence_key` to hash on
  `_dbt_source_project` instead of `_dbt_source_relation`. Producer and consumer
  now hash identical inputs by construction.

Closes #3724. Incrementally advances #3142.

## Hash churn

Per `src/dbt/CLAUDE.md` reason #1 (values unify). All three keys above change.
Marts are views — no incremental concerns. The FK was 100% broken pre-fix so no
downstream consumer was meaningfully relying on the prior hash.

## Test plan

- [x] `dbt build --select int_deanslist__incidents+ int_deanslist__incidents__penalties+ fct_behavioral_incidents fct_behavioral_consequences --target dev`
      — all tests pass locally.
- [x] `relationships` test on
      `fct_behavioral_consequences.behavioral_incident_key` returns 0 failures.
- [x] `_dbt_source_project` resolves to exactly `kippnewark` / `kippcamden` /
      `kippmiami` on both intermediates.
- [ ] dbt Cloud CI build succeeds on this branch.
```

- [ ] **Step 4: Wait for CI, then verify the relationships test in CI**

After CI completes, query the PR-branch schema
(`dbt_cloud_pr_70403104388001_<pr_num>_marts`) via BigQuery MCP:

```sql
select count(*) as n_orphans
from `teamster-332318.dbt_cloud_pr_70403104388001_<pr_num>_marts.fct_behavioral_consequences` c
left join `teamster-332318.dbt_cloud_pr_70403104388001_<pr_num>_marts.fct_behavioral_incidents` p
  using (behavioral_incident_key)
where p.behavioral_incident_key is null
```

Expected: `n_orphans = 0`. If non-zero, do not merge — diagnose.

---

## Spec coverage check

| Spec acceptance item                                    | Implementing task |
| ------------------------------------------------------- | ----------------- |
| `_dbt_source_project` on both intermediates             | Tasks 1, 2        |
| Both facts hash on `[incident_id, _dbt_source_project]` | Tasks 3, 4        |
| `relationships` test passes in CI                       | Tasks 4 + 7       |
| No other test regressions on either fact                | Task 6            |
| #3142 progress: 2 of ~73 union models                   | Tasks 1, 2        |
| Cross-fact hash equality verified                       | Task 5            |
