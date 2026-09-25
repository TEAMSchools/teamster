---
paths:
  - ".claude/worktrees/**"
---

# Worktree mechanics

Loads on the first read under `.claude/worktrees/` from the main checkout only.
After `EnterWorktree`, or for Bash-only worktree work, read this file yourself.

## Setup

- A stacked `git worktree add -b <new> <abs-path> <parent>` sets the new
  branch's upstream to the parent, so a bare `git push` lands on someone else's
  branch. Run `git -C <worktree> branch --unset-upstream`, then
  `git -C <worktree> push -u origin <new>`.
- A fresh worktree has no `dbt_packages/`, so the first dbt command fails on
  missing `dbt_utils` or with "N package(s) specified in packages.yml, but only
  0 package(s) installed". Run
  `uv run dbt deps --project-dir <worktree>/src/dbt/<project>` before any
  `dbt build`/`test`/`compile`/`clone` there, in its own Bash call.
- A Codespace restart can delete `.claude/worktrees/` and desync refs. Invoke
  `resuming-a-branch`.

## Invocation

- cwd: after `EnterWorktree` `path`, the session's cwd is the worktree and
  persists across Bash calls. Without it, Bash cwd resets to the main checkout;
  put `cd <worktree> &&` in the SAME command. Keep `git -C <worktree>` and
  absolute paths either way (root _Never_): they survive a session that never
  entered, or left. On the wrong cwd, bare `git` commits to `main`, editing the
  main path dirties `main` so the worktree commit reports "nothing to commit",
  and `trunk check`, `pytest`, and `sed -i` report a false "clean".
- dbt: `uv run dbt ... --project-dir <worktree>/src/dbt/<project>`. Do not use
  `uv --directory <worktree> run dbt`: it sets cwd to the worktree root, where
  `dbt_project.yml` does not exist.
- Python from the main checkout:
  `VIRTUAL_ENV= uv --directory <worktree> run python <abs-script-path>`. Bare
  `uv run --active` reads the main repo's `.venv` and misses worktree-only
  changes. `uv --directory` resolves a relative script path under the worktree,
  so pass an absolute one.
- IDE Pyright diagnostics on worktree files resolve imports against the MAIN
  checkout. `unknown import` and `no parameter named X` on worktree-only changes
  are false positives. Trust `uv run` inside the worktree.
