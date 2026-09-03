# Subagent and Workflow gotchas

Injected on the first `Agent` or `Workflow` call in a session.

## Writing the dispatch prompt

- Subagents do not auto-invoke skills. Name the exact `Skill` calls the subagent
  must run before work (for example `Skill` with
  skill=`dbt:using-dbt-for-analytics-engineering` for a dbt review).
- For negation goals (remove X, no Y), list the anti-patterns explicitly.
  Subagents otherwise re-introduce familiar idioms (`dbt_utils.deduplicate`,
  `select distinct`, `qualify row_number()=1`).
- Edit-task dispatches must say "do the edits YOURSELF; do NOT dispatch
  sub-agents." Without it an agent may re-delegate, stall waiting on its
  children, and self-report progress that `git status` disproves.
- Tell subagents to run builds in the FOREGROUND. A subagent that backgrounds a
  long `dbt build` strands itself waiting on the notification and returns having
  written nothing. Never run two dbt subagents against one worktree at once:
  they share `target/` and corrupt the partial-parse manifest.
- Worktree dispatches spell out the absolute worktree path and mandate
  `git -C <worktree>` plus `uv run` from it. A subagent starts in the MAIN
  checkout, so bare edits hit `main`. State that IDE Pyright errors on worktree
  files (`reportMissingImports`, "not accessed", "not iterable") are expected
  false positives.
- Subagents name specific files in `git add`, never `-u`, `-A`, or `.`.
- Subagents cannot Write report files; the harness refuses with "Subagents
  should return findings as text". Have them return the report as final text and
  persist it to the scratchpad yourself.

## Model and effort

When a skill carries its own model-selection guidance (for example
subagent-driven-development), follow the skill; this table only binds its tiers
to models. The `Agent` tool accepts only `model`; effort is settable on Workflow
`agent()`, not `Agent`, so via `Agent` pass the model and drop the effort tier.

| Task                                 | Model    | Effort |
| ------------------------------------ | -------- | ------ |
| Mechanical, 1-2 files, precise brief | `haiku`  | omit   |
| Integration or debugging implementer | `sonnet` | high   |
| Review and re-review                 | `sonnet` | xhigh  |
| Design work                          | `opus`   | high   |
| Final whole-branch review            | `opus`   | xhigh  |
| None of the above                    | omit     | omit   |

## Verifying the result

- Subagents abandon multi-step tasks partway. Scope each dispatch to one file or
  one commit, and inspect the diff and `git log` before marking it complete.
- A subagent's "pre-existing failure" baseline is the working tree AS
  DISPATCHED, including your uncommitted edits. Check whether your own change
  caused the failure before accepting that framing.

## Workflow tool

- The `Workflow` orchestrator is unreliable for long fan-outs in this Codespace:
  runs stall, and a window reload can leave a prior run orphaned-but-alive,
  still spawning branches and worktrees. Prefer discrete main-loop `Agent`
  dispatches for multi-batch work. If you must run a Workflow, find and kill any
  leftover prior run after a reload first.
- A dead run's journal
  (`~/.claude/projects/<proj>/subagents/workflows/wf_<id>/journal.jsonl`) stops
  growing for about 2 minutes with no live `dbt` or agent processes.
- `isolation:'worktree'` dirs live at `.claude/worktrees/wf_<id>-N`, not the
  repo `.worktrees/`. Orphaned ones are left `locked`: `git worktree unlock`,
  then `remove --force`.
- `TaskStop` only sees tasks launched in the CURRENT session. A Workflow from a
  reloaded session is not in the registry; clean it at the process and worktree
  level.
- Concurrency cap is `min(16, cpu_cores-2)`, so 2 on the 4-core Codespace.
  Raising it needs a larger machine, whose restart kills in-flight runs.
