# Strand-scores rollback runbook

This is the rollback plan for the strand-level-scores change (`Refs #4708`):
DIBELS subtest rows, i-Ready domain rows, and a unified `response_type` added to
`fct_assessment_scores_enrollment_scoped`, plus the matching Cube and
knowledge-base updates. It exists so that someone who was not part of the
original work can execute a full back-out and prove it worked. A rollback that
cannot be verified is not a rollback — that is why the verification step below
compares against a captured baseline rather than trusting the revert.

## What this change did

Commits on `anthonygwalters/feat/claude-assessment-strand-scores`, in
implementation order:

1. `91189e19b` — passes `illuminate_subject` through
   `int_iready__domain_unpivot`
1. `1814afb10` — adds DIBELS subtest rows and the discriminator plumbing for an
   8th surrogate-key input, to `fct_assessment_scores_enrollment_scoped`
1. `e8945d877` — adds i-Ready domain rows to the same fact
1. `b6abb3a76` — unifies `response_type` across every assessment source
1. `6a1f73277` and `6cce6dee0` — document the unified `response_type` vocabulary
   and the fact/upstream YAML
1. `78a8539d0` and `4d02fd27b` — update the Cube pre-aggregation and view
   description
1. `6f0528531` and `e137b2144` — update the Cube knowledge-base files

Two other commits on the branch are **not** part of the implementation and must
**not** be reverted: `a9f529336` (the pre-change baseline capture — the file
this runbook verifies against) and `ab89e53f5` (a plan-doc edit). Both are
docs-only commits with no effect on any built table or Cube model.

Net effect on production, relative to the `a9f529336` baseline:

- `fct_assessment_scores_enrollment_scoped` gained roughly 252,300 DIBELS
  subtest rows and roughly 1,139,444 i-Ready domain rows.
- `response_type` became non-nullable across four values (`standard`, `group`,
  `overall`, `not_taken`); every row that was previously `NULL` became `overall`
  or `not_taken`.
- The `assessment_score_key` (a `dbt_utils.generate_surrogate_key` hash) gained
  an 8th hash input. **Every vendor row's key value changed**, including STAR
  rows that gained no new data, and separately **every internal Illuminate
  `not_taken` row's key also changed** — roughly 1,072,971 rows — because the
  4th hash input flipped from `rr.response_type` (NULL) to
  `coalesce(rr.response_type, 'not_taken')`. Both are a pure key-value change,
  not a new/removed row.
- Cube's proficiency measures now exclude `not_taken` rows. Illuminate
  `pct_proficient` moved from 45.80% (baseline) to 49.54%.
- The Cube pre-aggregation was renamed from `proficiency_rollup` to
  `proficiency_rollup_v2`.
- Three files under `src/cube/mcp/project_knowledge/` changed
  (`assessment-cube-orchestrator.md`, `assessment-cube-reference.md`,
  `README.md`). Merging the PR does not publish any of them — they deploy by two
  distinct manual mechanisms: `assessment-cube-orchestrator.md` and
  `assessment-cube-reference.md` are re-uploaded as **project knowledge**, and
  the **Project instructions** text inside `README.md` is pasted into the
  claude.ai Project's custom-instructions field. See the merge-gate section
  below for both.

## Rollback steps

The `git revert` (step 1) and `git show <sha>^:...` (step 3) commands below name
individual commit SHAs, which are reachable from `main` only if the PR was
merged with a merge commit — per the root `CLAUDE.md`, PRs are squash merged, so
if that's what happened here, every command below fails with `bad object`;
revert the single squash commit instead, and read prior file versions from that
squash commit's parent (`git show <squash-sha>^:<path>`).

1. **Revert the implementation commits.** From `main` (post-merge), revert the
   ten implementation commits listed above, in reverse order, ending with
   `91189e19b`:

   ```bash
   git revert --no-commit e137b2144 6f0528531 4d02fd27b 78a8539d0 \
     6cce6dee0 6a1f73277 b6abb3a76 e8945d877 1814afb10 91189e19b
   git commit -m "revert: back out strand-level-scores change (Refs #4708)"
   ```

   Do not revert `a9f529336` or `ab89e53f5` — they carry the baseline this
   runbook checks against and the plan-doc trail; reverting them destroys the
   evidence needed for step 5.

1. **Rebuild the fact table fully**, not incrementally, so no stale post-change
   rows survive a partial refresh:

   ```bash
   uv run dbt build --project-dir src/dbt/kipptaf \
     --select fct_assessment_scores_enrollment_scoped+ --full-refresh
   ```

   `--project-dir` is required — the model lives in `src/dbt/kipptaf`, and
   running `dbt` from the repo root without it errors immediately with no
   `dbt_project.yml` found (see `src/dbt/CLAUDE.md`). If this rollback is
   executed from a worktree rather than the main checkout, qualify the path with
   the worktree root instead: `--project-dir <worktree>/src/dbt/kipptaf`.

1. **Restore the prior claude.ai Project knowledge and instructions.** This is
   two distinct mechanisms, not one — do not treat it as "re-upload three
   files." The prior (pre-change) content for all three files is the parent of
   `6f0528531`. Retrieve all three, saving each to a file:

   ```bash
   git show 6f0528531^:src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md \
     > assessment-cube-orchestrator.md
   git show 6f0528531^:src/cube/mcp/project_knowledge/assessment-cube-reference.md \
     > assessment-cube-reference.md
   git show 6f0528531^:src/cube/mcp/project_knowledge/README.md \
     > README.md
   ```

   `src/cube/mcp/project_knowledge/README.md` documents the deployment split.
   Its **Setup (per Project)** section says: "Upload both `.md` files above as
   project knowledge in the shared claude.ai Project" — meaning
   `assessment-cube-orchestrator.md` and `assessment-cube-reference.md` only;
   `README.md` itself is never uploaded as project knowledge. Separately, its
   setup step 2 says to paste the text under **Project instructions** into the
   Project's custom-instructions field, and Task 8's change to `README.md`
   landed inside that Project-instructions section. So restoring the prior state
   means:

   1. Upload the two saved content files (`assessment-cube-orchestrator.md`,
      `assessment-cube-reference.md`) as **project knowledge**, replacing the
      current versions.
   1. Open the saved `README.md`, find its **Project instructions** section, and
      paste that text into the Project's custom-instructions field, replacing
      what is there now.

   Treating this as "re-upload three files" would put the wrong artifact
   (`README.md`) in as project knowledge and silently skip the
   custom-instructions paste — leaving the agent protocol stale even though the
   re-upload looks complete. That is the same silent-failure shape the
   merge-gate section warns about. The operator executing this step needs access
   to the shared claude.ai Project; if they don't have it, find whoever does
   before proceeding — this is not a step to work around. This is a manual step
   — it is not run by CI or by merging the revert PR. See the merge-gate section
   below for why this step's timing matters as much as the step itself.

1. **Rename the pre-aggregation back**, so Cube treats it as a new
   pre-aggregation and forces a clean rebuild rather than reusing partitions
   built under the `_v2` definition:

   ```text
   proficiency_rollup_v2 -> proficiency_rollup
   ```

   in `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`.
   Confirm the rebuild completes (see the pre-aggregation assertion below)
   before treating the rollback as done.

1. **Assert the restored table against the captured baseline**, using
   `docs/superpowers/plans/2026-08-28-strand-scores-baseline.md` — see the next
   section for what "restored" means and does not mean.

## What "restored" means: comparing against the baseline, not literals

The baseline file records production state at capture time
(`kipptaf_marts.fct_assessment_scores_enrollment_scoped` and
`kipptaf_marts.dim_assessment_administrations` /
`kipptaf_marts.dim_assessments`, joined). It also documents that production
itself is not static: the baseline's own cross-check section shows the fact
table moved **+193 rows** in under four hours during this work, with
per-category deltas running from -27 to +84 rows in mixed directions. Exact
row-count equality against the baseline is therefore the wrong test — it will
fail even on a fully correct rollback, purely from ordinary intraday ingestion.

Run the same three queries recorded in the baseline
(`Rows by source and response_type`, `Proficiency by source`, `FK health`)
against the rebuilt table and compare on these terms instead:

1. **Category set is identical.** The baseline records exactly 13
   `(assessment_type, response_type)` combinations, all with
   `response_type = <null>` except the four `illuminate` rows (`group`,
   `overall`, `standard`, plus its own `<null>`). A rolled-back table must show
   the same 13 combinations — no `not_taken` or extra `response_type` values, no
   DIBELS/i-Ready domain rows split out as their own categories.
1. **Per-source proportions are restored, not exact counts.** For each
   `assessment_type` in the baseline's "Rows by source and response_type" table,
   the rebuilt row count should be within roughly the same small drift band the
   baseline itself documents (a few dozen rows, not thousands) — not off by the
   ~252,300 (DIBELS) or ~1,139,444 (i-Ready) magnitudes this change introduced.
   A rebuilt fact still showing DIBELS/i-Ready row counts inflated by roughly
   those amounts means the revert did not fully take.
1. **`response_type IS NULL` count returns.** The baseline records 1,441,587
   total `NULL` rows (with the same drift caveat as above — the same-day
   known-good comparison put it at 1,441,444). A rolled-back table should show a
   `NULL` total in that neighborhood, not the near-zero-NULL state the
   unification produced (every row assigned to `overall` or `not_taken`).
1. **FK health holds.** The baseline records 0 orphans against
   `dim_assessment_administrations` on 14,569,370 rows. Re-run the same FK
   query; a rolled-back table should also show 0 orphans, confirming the revert
   didn't leave a partial/corrupt rebuild.

If any of these checks disagree by more than the baseline's own documented
drift, treat the rollback as incomplete and stop before touching the
pre-aggregation or the knowledge base.

## Pre-aggregation assertion

Assert the rebuilt `proficiency_rollup` pre-aggregation on **partition count =
12**, the figure the baseline records (one partition per academic year, 2015
through 2026 inclusive, read off the
`student_assessment_scores_proficiency_rollup <YYYYMMDD>_...` destination tables
in `prod_pre_aggregations`). Confirm the same 12 partitions rebuild after the
rename.

The baseline also records two candidate "build bytes" figures — a summed figure
across all 22 compute jobs including retries (~1.44 GiB), and a summed figure
across the 12 distinct per-partition byte values (~750.6 MiB). Treat both as
informational only, not a pass/fail gate: the baseline itself notes several
partitions were reprocessed 2-3 times in the batch it observed (retries, not
additional distinct work), so a rebuild's byte total will not reproduce either
figure exactly and there is no way to tell, from a single `JOBS_BY_PROJECT`
read, how much of either number was genuine recomputation versus retry noise.
Partition count is the load-bearing check because it answers the question that
actually matters for correctness — did every academic year's partition rebuild
under the reverted definition — while build bytes only speaks to cost and is
expected to vary run to run.

## What rollback does NOT undo

Rollback **does** restore the pre-change `assessment_score_key` values for every
row that survives the revert. `dbt_utils.generate_surrogate_key` is a
deterministic function of its inputs — it coalesces each input to a string,
joins with `-`, and hashes the result — so reverting to the same 7-input list,
over the same source rows with the same values, reproduces the original hashes
exactly. This includes DIBELS: Task 3 changed `module_code` from
`measure_standard` to the literal `'Composite'`, but on revert `module_code`
returns to `measure_standard` **and** the `measure_standard = 'Composite'`
filter comes back with it, so the value is `'Composite'` either way. i-Ready
(`subject`) and STAR are untouched. The warehouse genuinely returns to its prior
state.

What rollback cannot fix is an external system that **captured the 8-input key
values while the change was live** (a downstream export, a cached join, an
external reconciliation). Those values existed only during that window — they
are a snapshot of a mid-change state, not a permanent property of the warehouse.
After rollback they match nothing, because the rows they referred to now carry
their original 7-input keys again. Concretely:

- The exposure is bounded and specific: it is a mid-window snapshot problem,
  scoped to whatever external system persisted `assessment_score_key` between
  the forward merge and this rollback — not an irreversible property of
  surrogate-key hashing in general.
- If any consumer is known to have persisted `assessment_score_key` values
  during that window, that consumer needs a separate remediation (a re-sync
  against the rolled-back table) — it is not something re-running this runbook
  can fix.

State this to any stakeholder asking whether rollback is a full undo: it is, for
the data shape, the fact/Cube behavior, and the key values themselves — the
warehouse's `assessment_score_key` values return to exactly what they were
pre-change. The gap is narrower: any external system that captured 8-input key
values during the live window holds a snapshot that matches neither the
pre-change nor the post-rollback state.

## The merge gate

The claude.ai Project update — both the project-knowledge upload and the
custom-instructions paste (rollback step 3, or the corresponding forward update
when this change originally merged) — must **precede** the model merge, not
follow it, and needs a named owner in the PR before merge.
`fct_assessment_scores_enrollment_scoped` rebuilds on the cron
`0 0,10,13,15,17 * * *` — the data change lands within hours of a merge, with
nothing in CI or the merge process gating it against the Project's state.

This is two mechanisms, both gated the same way: uploading
`assessment-cube-orchestrator.md` and `assessment-cube-reference.md` as project
knowledge, and pasting `README.md`'s **Project instructions** section into the
Project's custom-instructions field. Both must land before (or together with)
the merge — a partial update, where one lands and the other doesn't, leaves the
agent working from a stale protocol exactly as if neither had been done.

If either half lags behind the merge (or, on rollback, behind the revert), every
agent following the published guidance queries against a schema the guidance no
longer describes correctly. Concretely, on the forward path: an agent following
pre-change guidance during the gap between merge and the Project update would
query for a data shape that no longer exists, and the established failure mode
for this class of mismatch is a silent zero-row result for i-Ready, DIBELS, STAR
and both state score sources — not an error, just no rows. The same risk applies
symmetrically to the rollback: a Project update that lags a revert leaves the
guidance describing the unified `response_type` model against a fact table that
has already reverted to the pre-change shape.

Name an owner for both halves of the Project update in the PR body (either the
merge PR or the revert PR) before merging. Do not treat "someone will do it
after merge" as a plan.

## Saved-consumer audit (prerequisite, not follow-up)

Per #4708 follow-up 3: Superset charts, Tableau workbooks built on the Cube SQL
API, direct Cube API callers, and ad-hoc BigQuery queries against
`kipptaf_marts.fct_assessment_scores_enrollment_scoped` cannot be enumerated
from this repository. No dbt exposure covers this fact table's downstream
consumers, and none of the four consumer classes above are visible from `src/` —
they live inside Cube, Superset, and Tableau, outside the repo's lineage.

Because these consumers cannot be enumerated, they cannot be individually
notified or gated. The only available mitigation is an announcement to the
consumer audience (analytics/BI channel, or whatever channel reaches Superset
and Tableau builders and ad-hoc BigQuery users) stating that `response_type`,
row counts, and `assessment_score_key` values for this fact table are changing
on a stated date. This announcement is a **prerequisite** to merging the forward
change and to executing this rollback — not a follow-up to either — because a
saved chart or workbook with a hardcoded `response_type IS NULL` filter, or a
persisted `assessment_score_key` join, breaks silently in both directions (merge
and rollback) without it.

## Outstanding human steps

These three steps cannot be completed by an agent and must be tracked as
explicit action items before merge:

1. **Cube Cloud branch staging deployment.** `src/cube/CLAUDE.md` requires
   validating a `proficiency_rollup_v2`-style pre-aggregation build against a
   Cube Cloud branch staging deployment before merge, per the incident record
   for #4460. This has not been done as part of this runbook and must be
   completed, by a human with Cube Cloud access, before the forward change (or
   its revert, if the renamed pre-aggregation needs the same validation) is
   merged.
1. **claude.ai Project update.** A named owner must, in the shared claude.ai
   Project: (a) upload `assessment-cube-orchestrator.md` and
   `assessment-cube-reference.md` as project knowledge (forward: the versions
   this change introduces; rollback: the prior versions at `6f0528531^`), and
   (b) paste the corresponding `README.md` **Project instructions** text into
   the Project's custom-instructions field. Both halves, timed to precede the
   corresponding model merge or revert per the merge-gate section above.
1. **Consumer announcement.** A human with access to the analytics/BI consumer
   audience must send the saved-consumer announcement described above, before
   merge, since the audience it targets cannot be reached through any
   repo-visible mechanism.
