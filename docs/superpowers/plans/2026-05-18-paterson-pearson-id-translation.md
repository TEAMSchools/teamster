# Paterson Pearson ID Translation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all 440 Paterson Pearson assessment rows to the correct
`student_key` in `fct_assessment_scores_enrollment_scoped` by translating the
Paterson district SIS ID stored in `localstudentidentifier` to the canonical
KIPP `student_number` via PowerSchool's `prevstudentid`, and remove the
vestigial Pearson UUID crosswalk.

**Architecture:** Two sequential PRs both linked to issue #3882. Phase A adds
Paterson-specific intermediate models in the `kipppaterson` dbt project that
translate `localstudentidentifier` via a join to Paterson PowerSchool. Phase B
(a new branch off main, opened after Phase A merges and Dagster materializes the
new intermediates to prod) repoints kipptaf's union models to source the
translated intermediates and removes the now-unused crosswalk join.

**Tech Stack:** dbt-core, dbt-bigquery, BigQuery (warehouse), Dagster
(orchestrator), `uv` for Python tooling, dbt Cloud (CI).

---

## Why two PRs

kipptaf's `sources-kipppaterson.yml` resolves the `kipppaterson_pearson` schema
to plain prod (`kipppaterson_pearson`) for any non-dev target — including dbt
Cloud CI (`target=staging`). Adding a kipptaf source declaration that references
a new kipppaterson intermediate **deterministically fails kipptaf CI** until
that intermediate exists in prod. The intermediate only lands in prod after the
kipppaterson PR (Phase A) merges and Dagster materializes the new assets.
Established convention per [src/dbt/CLAUDE.md](../../../src/dbt/CLAUDE.md) →
"kipptaf source consumers of district columns".

---

## Phase A — kipppaterson intermediates

**Branch:** `cbini/fix/claude-paterson-pearson-id-translation` (already created,
linked to #3882, worktree at
`.worktrees/cbini/fix/claude-paterson-pearson-id-translation`).

**Files (Phase A):**

- Create:
  `src/dbt/kipppaterson/models/pearson/intermediate/int_pearson__njsla.sql`
- Create:
  `src/dbt/kipppaterson/models/pearson/intermediate/int_pearson__njsla_science.sql`
- Create:
  `src/dbt/kipppaterson/models/pearson/intermediate/properties/int_pearson__njsla.yml`
- Create:
  `src/dbt/kipppaterson/models/pearson/intermediate/properties/int_pearson__njsla_science.yml`

### Task A1: Create `int_pearson__njsla.sql`

**Files:**

- Create:
  `src/dbt/kipppaterson/models/pearson/intermediate/int_pearson__njsla.sql`

- [ ] **Step 1: Write the model SQL**

Path:
`.worktrees/cbini/fix/claude-paterson-pearson-id-translation/src/dbt/kipppaterson/models/pearson/intermediate/int_pearson__njsla.sql`

```sql
with
    raw as (select * from {{ ref("stg_pearson__njsla") }}),

    paterson_id_map as (
        select
            scf.prevstudentid as paterson_district_sis_id,
            s.student_number as kipp_student_number,
        from {{ ref("stg_powerschool__students") }} as s
        inner join {{ ref("stg_powerschool__studentcorefields") }} as scf
            on s.dcid = scf.studentsdcid
        where s.enroll_status in (0, 2, 3) and scf.prevstudentid is not null
    )

select
    raw.* except (localstudentidentifier),

    coalesce(
        m.kipp_student_number, raw.localstudentidentifier
    ) as localstudentidentifier,
from raw
left join paterson_id_map as m
    on raw.localstudentidentifier = m.paterson_district_sis_id
```

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation add src/dbt/kipppaterson/models/pearson/intermediate/int_pearson__njsla.sql
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation commit -m "feat(dbt/kipppaterson): add int_pearson__njsla with prevstudentid translation

Refs #3882."
```

### Task A2: Create `int_pearson__njsla_science.sql`

**Files:**

- Create:
  `src/dbt/kipppaterson/models/pearson/intermediate/int_pearson__njsla_science.sql`

- [ ] **Step 1: Write the model SQL**

Path:
`.worktrees/cbini/fix/claude-paterson-pearson-id-translation/src/dbt/kipppaterson/models/pearson/intermediate/int_pearson__njsla_science.sql`

```sql
with
    raw as (select * from {{ ref("stg_pearson__njsla_science") }}),

    paterson_id_map as (
        select
            scf.prevstudentid as paterson_district_sis_id,
            s.student_number as kipp_student_number,
        from {{ ref("stg_powerschool__students") }} as s
        inner join {{ ref("stg_powerschool__studentcorefields") }} as scf
            on s.dcid = scf.studentsdcid
        where s.enroll_status in (0, 2, 3) and scf.prevstudentid is not null
    )

select
    raw.* except (localstudentidentifier),

    coalesce(
        m.kipp_student_number, raw.localstudentidentifier
    ) as localstudentidentifier,
from raw
left join paterson_id_map as m
    on raw.localstudentidentifier = m.paterson_district_sis_id
```

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation add src/dbt/kipppaterson/models/pearson/intermediate/int_pearson__njsla_science.sql
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation commit -m "feat(dbt/kipppaterson): add int_pearson__njsla_science with prevstudentid translation

Refs #3882."
```

### Task A3: Create properties yml for both intermediates

**Files:**

- Create:
  `src/dbt/kipppaterson/models/pearson/intermediate/properties/int_pearson__njsla.yml`
- Create:
  `src/dbt/kipppaterson/models/pearson/intermediate/properties/int_pearson__njsla_science.yml`

Per [src/dbt/CLAUDE.md](../../../src/dbt/CLAUDE.md) "All intermediate models
must have a uniqueness test." Both upstream staging models are unique on
`studenttestuuid` (verified: 44,533 / 44,533 NJSLA rows, 6,920 / 6,920 NJSLA
Science rows). The intermediate preserves grain, so `studenttestuuid` remains
the right key.

- [ ] **Step 1: Write `int_pearson__njsla.yml`**

Path:
`.worktrees/cbini/fix/claude-paterson-pearson-id-translation/src/dbt/kipppaterson/models/pearson/intermediate/properties/int_pearson__njsla.yml`

```yaml
models:
  - name: int_pearson__njsla
    description: |
      Paterson NJSLA assessment rows with `localstudentidentifier` translated
      from the Paterson district SIS ID to the canonical KIPP
      `student_number` via PowerSchool's `prevstudentid` lookup. Rows whose
      `localstudentidentifier` does not match any Paterson PS record fall
      through unchanged.
    columns:
      - name: studenttestuuid
        description: Pearson per-test-attempt UUID. Unique grain.
        data_tests:
          - unique
          - not_null
```

- [ ] **Step 2: Write `int_pearson__njsla_science.yml`**

Path:
`.worktrees/cbini/fix/claude-paterson-pearson-id-translation/src/dbt/kipppaterson/models/pearson/intermediate/properties/int_pearson__njsla_science.yml`

```yaml
models:
  - name: int_pearson__njsla_science
    description: |
      Paterson NJSLA Science assessment rows with `localstudentidentifier`
      translated from the Paterson district SIS ID to the canonical KIPP
      `student_number` via PowerSchool's `prevstudentid` lookup. Rows whose
      `localstudentidentifier` does not match any Paterson PS record fall
      through unchanged.
    columns:
      - name: studenttestuuid
        description: Pearson per-test-attempt UUID. Unique grain.
        data_tests:
          - unique
          - not_null
```

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation add src/dbt/kipppaterson/models/pearson/intermediate/properties/
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation commit -m "feat(dbt/kipppaterson): add properties yml for Pearson NJSLA intermediates

Refs #3882."
```

### Task A4: Local build and test

- [ ] **Step 1: Refresh prod manifest (if stale)**

Required so `--defer --state=target/prod` resolves correctly. Per
[src/dbt/CLAUDE.md](../../../src/dbt/CLAUDE.md) "Dev `--defer` for unstaged
externals" — `--state` is relative to `--project-dir`.

```bash
uv run dbt parse \
    --target prod \
    --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation/src/dbt/kipppaterson \
    --target-path target/prod
```

Expected: completes without error.

- [ ] **Step 2: Build the two new intermediates against dev target**

```bash
uv run dbt build \
    --select int_pearson__njsla int_pearson__njsla_science \
    --target dev \
    --defer \
    --state target/prod \
    --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation/src/dbt/kipppaterson
```

Expected: 2 models materialized successfully. Tests pass: `unique` and
`not_null` on `studenttestuuid` for both models.

- [ ] **Step 3: Verify translation correctness in dev**

Run against the dev BigQuery schema (substitute `<user>` for your dev username):

```sql
with paterson_int as (
    select
        cast(localstudentidentifier as string) as resolved_id,
        count(*) as n,
    from `teamster-332318.zz_<user>_kipppaterson_pearson.int_pearson__njsla`
    group by resolved_id
)

select
    sum(if(paterson_int.resolved_id between '10000' and '10499', n, 0))
      as n_remaining_district_sis,
    sum(if(paterson_int.resolved_id not between '10000' and '10499', n, 0))
      as n_resolved_to_kipp_student_number,
from paterson_int;
```

Expected: `n_remaining_district_sis = 8` (the orphans, no `prevstudentid`
match), `n_resolved_to_kipp_student_number >= 316` (rest of the NJSLA rows).

### Task A5: Push branch and open Phase A PR

- [ ] **Step 1: Push the branch**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-id-translation push -u origin cbini/fix/claude-paterson-pearson-id-translation
```

Expected: branch pushed, trunk-check-pre-push runs and reports `No issues`.

- [ ] **Step 2: Open the PR**

```bash
gh pr create \
    --title "fix(dbt/kipppaterson): add Pearson NJSLA intermediates with prevstudentid translation" \
    --body "$(cat <<'EOF'
## Summary

Adds two kipppaterson intermediate models that translate Paterson Pearson `localstudentidentifier` from the Paterson district SIS ID stored in `prevstudentid` to the canonical KIPP `student_number`.

Phase A of the two-PR sequence for #3882. Phase B (kipptaf wiring + crosswalk removal) opens on a new branch after this PR merges and Dagster materializes the new intermediates in prod.

## Test plan

- [ ] Local `uv run dbt build` of both intermediates against `target=dev` passes
- [ ] Uniqueness + not_null tests on `studenttestuuid` pass
- [ ] dbt Cloud CI green
- [ ] After merge, confirm Dagster materializes `kipppaterson/pearson/int_pearson__njsla` and `kipppaterson/pearson/int_pearson__njsla_science` to prod
- [ ] Phase B PR opens after prod materialization completes

Refs #3882.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL returned. CI starts.

- [ ] **Step 3: Wait for CI green and review approval, then merge (squash)**

Per [CLAUDE.md](../../../CLAUDE.md) "Pull requests: Squash merge."

---

## Gate: Phase A merged, Dagster materializes new intermediates

**Do not start Phase B until both:**

1. Phase A PR is merged into main.
2. Dagster has materialized `kipppaterson/pearson/int_pearson__njsla` and
   `kipppaterson/pearson/int_pearson__njsla_science` to prod. Verify via:

```sql
select table_name, table_type
from `teamster-332318.kipppaterson_pearson.INFORMATION_SCHEMA.TABLES`
where table_name in ('int_pearson__njsla', 'int_pearson__njsla_science');
```

Expected: 2 rows returned.

---

## Phase B — kipptaf wiring + crosswalk removal

**Branch:** create new from main, name
`cbini/fix/claude-paterson-pearson-kipptaf-wiring`, link to #3882 via
`gh issue develop --name`. Per [CLAUDE.md](../../../CLAUDE.md) "Worktree"
pattern.

**Files (Phase B):**

- Modify: `src/dbt/kipptaf/models/pearson/sources-kipppaterson.yml`
- Modify: `src/dbt/kipptaf/models/pearson/staging/stg_pearson__njsla.sql`
- Modify:
  `src/dbt/kipptaf/models/pearson/staging/stg_pearson__njsla_science.sql`
- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`
- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__pearson__student_crosswalk.yml`
- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml`

### Task B0: Create Phase B worktree

- [ ] **Step 1: Create issue-linked branch**

```bash
gh issue develop 3882 --name cbini/fix/claude-paterson-pearson-kipptaf-wiring
```

Expected: branch created on remote.

- [ ] **Step 2: Create worktree**

```bash
git worktree add /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring cbini/fix/claude-paterson-pearson-kipptaf-wiring
```

Expected: worktree at the named path tracking the remote branch.

### Task B1: Declare the new intermediates as kipptaf sources

**Files:**

- Modify: `src/dbt/kipptaf/models/pearson/sources-kipppaterson.yml`

- [ ] **Step 1: Read the current file**

Path:
`.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring/src/dbt/kipptaf/models/pearson/sources-kipppaterson.yml`

The file currently declares 6 tables under `kipppaterson_pearson`. Add two new
table entries for the intermediates. Place them alphabetically — after
`stg_pearson__njgpa` and before `stg_pearson__njsla` for `int_pearson__njsla`,
and after `stg_pearson__njsla` and before `stg_pearson__njsla_science` for
`int_pearson__njsla_science`. Use the same Dagster asset key convention as the
surrounding entries.

- [ ] **Step 2: Add the two table entries**

Insert directly under `tables:` so the file ends up containing (in addition to
the existing 6 entries):

```yaml
- name: int_pearson__njsla
  config:
    meta:
      dagster:
        group: pearson
        asset_key:
          - kipppaterson
          - pearson
          - int_pearson__njsla
- name: int_pearson__njsla_science
  config:
    meta:
      dagster:
        group: pearson
        asset_key:
          - kipppaterson
          - pearson
          - int_pearson__njsla_science
```

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring add src/dbt/kipptaf/models/pearson/sources-kipppaterson.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring commit -m "feat(dbt/kipptaf): declare Paterson Pearson intermediates as sources

Refs #3882."
```

### Task B2: Repoint the NJSLA union to the translated intermediate

**Files:**

- Modify: `src/dbt/kipptaf/models/pearson/staging/stg_pearson__njsla.sql`

- [ ] **Step 1: Edit the file**

Replace the existing content. The file currently reads:

```sql
{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", "stg_pearson__njsla"),
            source("kippcamden_pearson", "stg_pearson__njsla"),
            source("kipppaterson_pearson", "stg_pearson__njsla"),
        ]
    )
}}
```

Change the Paterson source to point at the intermediate:

```sql
{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", "stg_pearson__njsla"),
            source("kippcamden_pearson", "stg_pearson__njsla"),
            source("kipppaterson_pearson", "int_pearson__njsla"),
        ]
    )
}}
```

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring add src/dbt/kipptaf/models/pearson/staging/stg_pearson__njsla.sql
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring commit -m "fix(dbt/kipptaf): source Paterson NJSLA from translated intermediate

Refs #3882."
```

### Task B3: Repoint the NJSLA Science union to the translated intermediate

**Files:**

- Modify:
  `src/dbt/kipptaf/models/pearson/staging/stg_pearson__njsla_science.sql`

- [ ] **Step 1: Edit the file**

The file currently reads:

```sql
{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", "stg_pearson__njsla_science"),
            source("kippcamden_pearson", "stg_pearson__njsla_science"),
            source("kipppaterson_pearson", "stg_pearson__njsla_science"),
        ]
    )
}}
```

Change the Paterson source to the intermediate:

```sql
{{
    dbt_utils.union_relations(
        relations=[
            source("kippnewark_pearson", "stg_pearson__njsla_science"),
            source("kippcamden_pearson", "stg_pearson__njsla_science"),
            source("kipppaterson_pearson", "int_pearson__njsla_science"),
        ]
    )
}}
```

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring add src/dbt/kipptaf/models/pearson/staging/stg_pearson__njsla_science.sql
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring commit -m "fix(dbt/kipptaf): source Paterson NJSLA Science from translated intermediate

Refs #3882."
```

### Task B4: Remove the crosswalk join from `int_pearson__all_assessments`

**Files:**

- Modify:
  `src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql`

- [ ] **Step 1: Edit the file**

Two changes:

1. In the final SELECT, replace:

```sql
coalesce(x.student_number, u.localstudentidentifier) as localstudentidentifier,
```

with:

```sql
u.localstudentidentifier,
```

2. At the bottom of the file, remove the `LEFT JOIN` block:

```sql
left join
    {{ ref("stg_google_sheets__pearson__student_crosswalk") }} as x
    on u.studenttestuuid = x.student_test_uuid
```

The file now ends after the `from union_relations as u` line.

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring add src/dbt/kipptaf/models/pearson/intermediate/int_pearson__all_assessments.sql
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring commit -m "refactor(dbt/kipptaf): drop vestigial Pearson crosswalk join

Refs #3882."
```

### Task B5: Disable the crosswalk staging model

**Files:**

- Modify:
  `src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__pearson__student_crosswalk.yml`

- [ ] **Step 1: Edit the file**

The file currently reads:

```yaml
models:
  - name: stg_google_sheets__pearson__student_crosswalk
    columns:
      - name: Student_Test_UUID
        data_type: string
      - name: Student_Number
        data_type: int64
```

Change to:

```yaml
models:
  - name: stg_google_sheets__pearson__student_crosswalk
    config:
      enabled: false
    columns:
      - name: Student_Test_UUID
        data_type: string
      - name: Student_Number
        data_type: int64
```

- [ ] **Step 2: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring add src/dbt/kipptaf/models/google/sheets/staging/properties/stg_google_sheets__pearson__student_crosswalk.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring commit -m "chore(dbt/kipptaf): disable vestigial Pearson crosswalk staging model

Refs #3882."
```

### Task B6: Remove the crosswalk source entry from `sources-external.yml`

**Files:**

- Modify: `src/dbt/kipptaf/models/google/sheets/sources-external.yml`

- [ ] **Step 1: Locate the source entry**

Grep the file for the `pearson__student_crosswalk` entry:

```bash
grep -n "pearson__student_crosswalk" /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring/src/dbt/kipptaf/models/google/sheets/sources-external.yml
```

Expected: one match identifying the start of the source entry block.

- [ ] **Step 2: Delete the entry**

Remove the entire `- name: src_google_sheets__pearson__student_crosswalk` block
from `tables:`, including its `external:`, `config:`, and `columns:` children.
Adjacent table entries stay.

- [ ] **Step 3: Commit**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring add src/dbt/kipptaf/models/google/sheets/sources-external.yml
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring commit -m "chore(dbt/kipptaf): remove vestigial Pearson crosswalk source entry

Refs #3882."
```

### Task B7: Local build and dbt tests

- [ ] **Step 1: Refresh prod manifest**

```bash
uv run dbt parse \
    --target prod \
    --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring/src/dbt/kipptaf \
    --target-path target/prod
```

Expected: completes without error.

- [ ] **Step 2: Build the affected kipptaf models against dev target**

```bash
uv run dbt build \
    --select stg_pearson__njsla stg_pearson__njsla_science int_pearson__all_assessments \
    --target dev \
    --defer \
    --state target/prod \
    --project-dir /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring/src/dbt/kipptaf
```

Expected: 3 models built, tests pass.

### Task B8: Pre-merge verification — Paterson resolution

- [ ] **Step 1: Run in BigQuery**

Substitute `<user>` for your dev username:

```sql
select
    regexp_extract(_dbt_source_relation, r'`(kipp[^_]+)_powerschool`')
      as resolved_district,
    count(*) as n_rows,
from `teamster-332318.zz_<user>_kipptaf_pearson.int_pearson__all_assessments` as p
left join
    `teamster-332318.kipptaf_powerschool.stg_powerschool__students` as s
    on cast(s.student_number as string) = p.localstudentidentifier
where p._dbt_source_relation like '%paterson%'
group by resolved_district;
```

Expected output:

| resolved_district | n_rows |
| ----------------- | -----: |
| `kipppaterson`    |    432 |
| (NULL)            |      8 |

No `kippnewark`, `kippcamden`, or `kippmiami` rows should appear.

### Task B9: Pre-merge verification — Newark / Camden unchanged

- [ ] **Step 1: Run in BigQuery**

```sql
select
    p._dbt_source_relation,
    count(*) as n_rows,
    countif(p.localstudentidentifier != prev.localstudentidentifier)
      as n_changed,
from `teamster-332318.zz_<user>_kipptaf_pearson.int_pearson__all_assessments` as p
inner join
    `teamster-332318.kipptaf_pearson.int_pearson__all_assessments` as prev
    on p.studenttestuuid = prev.studenttestuuid
where p._dbt_source_relation not like '%paterson%'
group by p._dbt_source_relation;
```

Expected: `n_changed = 0` for every Newark and Camden source relation.

### Task B10: Push branch and open Phase B PR

- [ ] **Step 1: Push**

```bash
git -C /workspaces/teamster/.worktrees/cbini/fix/claude-paterson-pearson-kipptaf-wiring push -u origin cbini/fix/claude-paterson-pearson-kipptaf-wiring
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create \
    --title "fix(dbt/kipptaf): wire Paterson Pearson translated intermediates; remove crosswalk" \
    --body "$(cat <<'EOF'
## Summary

Repoints kipptaf's NJSLA and NJSLA Science union models to source Paterson rows from the new `kipppaterson.int_pearson__<assessment>` intermediates (added in #3882's Phase A PR), removes the vestigial Pearson UUID crosswalk join from `int_pearson__all_assessments`, and disables the crosswalk staging model + Google Sheet source.

Phase B of the two-PR sequence for #3882.

## Test plan

- [ ] Local `uv run dbt build` of `stg_pearson__njsla`, `stg_pearson__njsla_science`, `int_pearson__all_assessments` against `target=dev` passes
- [ ] All Paterson Pearson rows in `int_pearson__all_assessments` resolve to `kipppaterson` PowerSchool (432 rows) or remain orphan (8 rows, tracked in #3956)
- [ ] No Paterson Pearson rows resolve into Newark / Camden / Miami PowerSchool
- [ ] Newark and Camden Pearson `localstudentidentifier` values unchanged vs. prod
- [ ] dbt Cloud CI green

Closes #3882.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL. CI starts.

- [ ] **Step 3: Wait for CI green and review approval, then merge (squash)**

---

## Acceptance criteria (recapped from spec)

- [ ] Phase A: 2 new `int_pearson__<assessment>` models exist in kipppaterson
      (NJSLA + NJSLA Science) with passing uniqueness tests.
- [ ] Phase B: The 2 kipptaf-level union models source the translated
      intermediates for Paterson.
- [ ] Phase B: `int_pearson__all_assessments` no longer references the
      crosswalk.
- [ ] Phase B: `stg_google_sheets__pearson__student_crosswalk` is disabled.
- [ ] Phase B: `pearson__student_crosswalk` source entry removed in
      `sources-external.yml`.
- [ ] After both PRs merge and Dagster materializes prod: 432 Paterson Pearson
      rows that previously FKed into Newark `student_key`s now FK into Paterson
      `student_key`s.
- [ ] 8 Paterson Pearson orphans remain orphans (tracked in #3956, not
      blocking).
- [ ] Newark and Camden Pearson row counts and `student_key` resolution
      unchanged.
