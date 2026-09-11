# Strand-scores rollback runbook

This is the rollback plan for the strand-level-scores change (`Refs #4708`):
DIBELS subtest rows, i-Ready domain rows, and a unified `response_type` added to
`fct_assessment_scores_enrollment_scoped`, plus the matching Cube and
knowledge-base updates. It exists so that someone who was not part of the
original work can execute a full back-out and prove it worked. A rollback that
cannot be verified is not a rollback — that is why the verification step below
compares against a captured baseline rather than trusting the revert.

## What this change did

The change ships as **two pull requests merged in order**, not one. That split
is deliberate and it is what this runbook's ordering depends on. See _Why two
merges_ below for the reason.

1. **The dbt PR** (#4710, branch
   `anthonygwalters/feat/claude-assessment-strand-scores`) — the fact model, the
   i-Ready domain unpivot, both properties files, and this plan/spec/baseline
   set. It adds the DIBELS subtest and i-Ready domain rows and makes
   `response_type` non-nullable. It changes no Cube file, so no measure
   definition moves with it.
1. **The Cube PR** (branch
   `cristinabaldor/feat/claude-assessment-strand-scores-cube`, based on the dbt
   branch) — `student_assessment_scores.yml`,
   `student_assessment_scores_view.yml`, and the three
   `src/cube/mcp/project_knowledge/` files. It excludes `not_taken` from the
   proficiency measures, renames the pre-aggregation, and carries the claude.ai
   Project merge gate.

Both merge squashed, so each lands on `main` as exactly one commit. Record the
two squash SHAs at merge time — this runbook calls them `<cube-squash>` and
`<dbt-squash>`, and every command below needs them. The individual branch
commits are not reachable from `main` after a squash merge.

**Why two merges.** Cube Cloud redeploys automatically on merge to `main`, while
the fact rebuilds hours later on the Dagster schedule, so a single merge always
puts the new Cube model in front of the old fact for a period. Measured
2026-09-10 on a local dev server, the new Cube model against the then-current
production fact returned exactly 0 for DIBELS, i-Ready, STAR and all five NJ/FL
state sources — 1.32M rows, silently. Merging the dbt half first, letting the
fact rebuild, then merging the Cube half removes that window: the renamed
pre-aggregation gets built against the correct fact on its very first build.

The measure filters additionally use `IS DISTINCT FROM 'not_taken'` rather than
`!= 'not_taken'`, so a null `response_type` counts rather than vanishing. That
guard is what makes the ordering recoverable rather than merely correct, and it
matters most **here** — a rollback re-introduces the null-`response_type` fact
while the Cube model may still be deployed, which is the same window from the
other side.

Net effect on production, relative to the `a9f529336` baseline:

- `fct_assessment_scores_enrollment_scoped` gained roughly 269,600 DIBELS
  subtest rows and roughly 1,207,200 i-Ready domain rows (counted 2026-09-10 on
  a dev-schema build of the branch; the 2026-08-28 estimates of 252,300 and
  1,139,444 predate the i-Ready FY27 partitions landing on 2026-09-01).
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
- Cube's proficiency measures now exclude `not_taken` rows. Measured 2026-09-10
  on a local dev server, global unfiltered `pct_proficient` moved from 45.66% to
  48.24%, and the Illuminate-only rate from 46.17% to 49.73%. The 45.80% →
  49.54% pair recorded on 2026-08-28 was Illuminate-only rather than global, and
  has drifted since; use the pairs above.
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

Every command below names `<cube-squash>` and `<dbt-squash>`, the two squash
commits the merges produced. Find them on `main` with
`git log --oneline --grep '#4710'` and by the Cube PR's number, or from each
PR's merge event. If either merge was landed with a merge commit rather than a
squash, use that merge commit's SHA in the same positions.

**Revert the Cube merge before the dbt merge.** The reverse of the merge order
is not a preference here: reverting the dbt half first restores a fact whose
`response_type` is null on every non-Illuminate row while the Cube measures are
still live, which is the same window the split exists to avoid. The
`IS DISTINCT FROM` guard keeps that from zeroing anything, but the
pre-aggregation still holds new-vocabulary partitions over old-vocabulary data
until it rebuilds. Reverting the Cube half first avoids the state entirely.

1. **Revert the Cube merge**, then the dbt merge, in that order:

   ```bash
   git revert --no-commit <cube-squash>
   git commit -m "revert: back out strand-scores Cube changes (Refs #4708)"
   git revert --no-commit <dbt-squash>
   git commit -m "revert: back out strand-scores fact changes (Refs #4708)"
   ```

   Two commits, not one — they can be raised as two PRs, and the Cube revert can
   ship alone if the fact turns out to be fine. Merge the Cube revert and let
   Cube Cloud redeploy before merging the dbt revert.

   Reverting the dbt merge also reverts this runbook, the spec, the plan and the
   baseline capture, since all four ship in the dbt PR. **Take copies of
   `docs/superpowers/plans/2026-08-28-strand-scores-baseline.md` and this file
   before running the dbt revert** — step 5 verifies against the baseline, and
   the revert removes it from the tree. Reading them back out of the reverted
   commit works too (`git show <dbt-squash>:<path>`), but only if you know to.

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
   files." All three files ship in the **Cube** PR, so their prior (pre-change)
   content is the parent of `<cube-squash>`. Retrieve all three, saving each to
   a file:

   ```bash
   git show <cube-squash>^:src/cube/mcp/project_knowledge/assessment-cube-orchestrator.md \
     > assessment-cube-orchestrator.md
   git show <cube-squash>^:src/cube/mcp/project_knowledge/assessment-cube-reference.md \
     > assessment-cube-reference.md
   git show <cube-squash>^:src/cube/mcp/project_knowledge/README.md \
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

1. **Confirm the pre-aggregation rebuilt under its old name.** Reverting the
   Cube merge already restores `proficiency_rollup_v2 -> proficiency_rollup` in
   `src/cube/model/cubes/student_assessments/student_assessment_scores.yml`, so
   there is no rename to make by hand — that was a separate step only while the
   two halves shipped as one PR. The rename still does its job on the way back:
   Cube treats `proficiency_rollup` as a new pre-aggregation and builds it
   clean, rather than reusing partitions built under the `_v2` definition.

   What does need checking is the **timing**. Do not treat the rollback as done
   until the rebuild completes (see the pre-aggregation assertion below). Until
   it does, queries are served from whatever `proficiency_rollup` partitions
   already exist, which are the pre-change ones — correct for a rollback, but
   only by coincidence, and mixed with freshly-built partitions as the refresh
   sweeps. Every measure read goes through this pre-aggregation rather than the
   fact (verified 2026-09-10 via the Cube `/sql` endpoint), so a green fact
   table is not evidence that consumers see rolled-back numbers.

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
