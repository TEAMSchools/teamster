---
paths:
  - ".worktrees/**"
---

# Worktree mechanics

Loads on the first read under `.worktrees/`. For Bash-only worktree work
(`git -C`, `uv run`), read this file yourself before starting.

- Every git call is `git -C <worktree>`. Bare `git` from the main repo commits
  to `main`.
- Every file path is `/workspaces/teamster/.worktrees/<branch>/<path>`, never
  `/workspaces/teamster/<path>`. Editing the main path dirties `main`, and the
  worktree commit then reports "nothing to commit".
- dbt: `uv run dbt ... --project-dir <worktree>/src/dbt/<project>`. Do not use
  `uv --directory <worktree> run dbt`: it sets cwd to the worktree root, where
  `dbt_project.yml` does not exist.
- Python from the main repo:
  `VIRTUAL_ENV= uv --directory <worktree> run python <abs-script-path>`. Bare
  `uv run --active` reads the main repo's `.venv` and misses worktree-only
  changes. `uv --directory` resolves a relative script path under the worktree,
  so pass an absolute one.
- Bash cwd persistence is version-dependent. Prefix `pwd &&`, and put
  `cd <worktree> &&` in the SAME command or use absolute paths. `trunk check`,
  `pytest`, and `sed -i` resolve from cwd and report a false "clean" on the
  wrong checkout.
- IDE Pyright diagnostics on worktree files resolve imports against the MAIN
  checkout. `unknown import` and `no parameter named X` on worktree-only changes
  are false positives. Trust `uv run` inside the worktree.
- Read/Edit of worktree files and Bash `cd <worktree>` re-inject that worktree's
  CLAUDE.md files (about 40KB) on every call. `git -C <worktree>`,
  `uv run dbt --project-dir <abs-worktree>` from the main cwd, and `Write` do
  not. For a large multi-file refactor, delegate the edits to subagents and
  verify with `git -C <worktree> diff`. Without subagents, `Write` a Python
  script to `.claude/scratch/`, run it by absolute path from the main cwd,
  assert each anchor matches exactly once, and abort otherwise.
- `git worktree add` with a relative path resolves against the shell cwd, which
  drifts after a `cd`. Pass an absolute path
  (`git worktree add /workspaces/teamster/.worktrees/<branch> <branch>`) or it
  nests one worktree inside another.
- A stacked `git worktree add -b <new> <abs-path> <parent>` sets the new
  branch's upstream to the parent, so a bare `git push` lands on someone else's
  branch. Run `git -C <worktree> branch --unset-upstream`, then
  `git -C <worktree> push -u origin <new>`.
- A Codespace restart can delete `.worktrees/` and desync refs. Invoke
  `resuming-a-branch`.
