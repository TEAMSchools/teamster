# Graduation Pathway Scores Cron Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild `int_students__graduation_pathway_scores` twice a day on its
consumer's cron instead of on every upstream change.

**Architecture:** One properties-yml change. The dagster-dbt translator reads
`meta.dagster.automation_condition.cron_schedule` and swaps the default eager
table condition for `dbt_cron_automation_condition`. No SQL change.

**Tech Stack:** dbt properties YAML, Dagster automation conditions.

Spec:
`docs/superpowers/specs/2026-09-14-graduation-pathway-scores-cron-design.md`.
Issue: #5310, child of #5212.

## Global Constraints

- Cron is `0 3,16 * * *`, identical to `int_students__graduation_path_codes`.
  Same tick, no stagger.
- No change to the model SQL or its tests.
- Run dbt only as `uv run dbt`, from the worktree, with
  `--project-dir src/dbt/kipptaf`.

---

### Task 1: Add the cron automation condition

**Files:**

- Modify:
  `src/dbt/kipptaf/models/students/intermediate/properties/int_students__graduation_pathway_scores.yml:14-15`

**Interfaces:**

- Consumes: the `config:` block that already holds `materialized: table`.
- Produces: `config.meta.dagster.automation_condition.cron_schedule`, read by
  `get_automation_condition` in
  `src/teamster/libraries/dbt/dagster_dbt_translator.py`.

- [x] **Step 1: Edit the yml**

Replace lines 14-15:

```yaml
config:
  materialized: table
```

with:

```yaml
config:
  materialized: table
  meta:
    dagster:
      # Same tick as int_students__graduation_path_codes, its only
      # consumer. The eager table condition rebuilt this ~140 times a
      # day; the consumer reads it twice. Refs #5310
      automation_condition:
        cron_schedule: 0 3,16 * * *
```

- [x] **Step 2: Parse the project**

Run from the worktree root:

```bash
uv run dbt parse --project-dir src/dbt/kipptaf --no-partial-parse
```

Expected: exits 0 with no errors.

- [x] **Step 3: Confirm the manifest carries the cron**

```bash
python3 -c "import json; m=json.load(open('src/dbt/kipptaf/target/manifest.json')); print(m['nodes']['model.kipptaf.int_students__graduation_pathway_scores']['config']['meta'])"
```

Expected output contains `'cron_schedule': '0 3,16 * * *'`.

- [x] **Step 4: Lint**

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix src/dbt/kipptaf/models/students/intermediate/properties/int_students__graduation_pathway_scores.yml </dev/null
```

Expected: no issues.

- [x] **Step 5: Commit**

```bash
git add -u
git commit -m "perf(students): rebuild graduation_pathway_scores on its consumer's cron

Closes #5310

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

### Task 2: Open the pull request

- [x] **Step 1: Push and open the PR** with the body from
      `.github/pull_request_template.md`. Body includes `Closes #5310` and
      `Refs #5212`.
- [ ] **Step 2: After merge**, check the ranking from #5212 over a window that
      starts after the merge. Done when the model shows at or under 2 runs a day
      and under 2 slot hours over 7 days.
