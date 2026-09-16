---
name: trunk-lint
description:
  "Use before pushing any SQL, YAML, or markdown change, when a
  trunk/sqlfluff/markdownlint CI check fails, when adding a trunk-ignore
  suppression, or when running trunk inside a worktree: covers the trunk binary
  path, --force checks, merge-commit hook skips, concurrent-run false failures,
  and the markdownlint rules (MD001/MD029/MD040/MD060) that fire only at
  push/CI."
---

# trunk-lint

- **Trunk linting/formatting**: Do not run `trunk fmt` or `trunk check` manually
  — `trunk-fmt-pre-commit` formats at commit time and `trunk-check-pre-push`
  blocks bad pushes, both in the main repo and in worktrees (`core.hooksPath` is
  shared). **Pre-commit hook runs `fmt` only**; sqlfluff/yamllint and other
  check-only linters fire at `pre-push` and in CI. If a session reports "trunk
  clean" on a SQL/YAML change based on commit hooks alone, run
  `.trunk/tools/trunk check --force <files>` to verify before claiming the
  change is lint-clean. A clean pre-PUSH `trunk-check-pre-push` is not
  sufficient either — it is git-diff-scoped (no `--force`) and can MISS a
  sqlfluff violation (e.g. ST06) on already-committed lines that CI's full check
  flags, so a push succeeds and CI still fails on lint; `trunk check --force`
  the changed SQL before pushing. Run from inside the worktree —
  `trunk check --force <abs-worktree-paths>` from the main repo silently returns
  "no applicable linters". The `trunk` binary lives only in the main repo
  (`.trunk/tools/` is gitignored, absent in worktrees) — invoke the absolute
  path `/workspaces/teamster/.trunk/tools/trunk` with cwd set to the worktree;
  relative paths run from the main repo check the main-repo copies, not your
  worktree edits. A `--force` check over
  `git diff --name-only origin/main...HEAD` hard-errors with
  `'<path>' does not exist` when the PR deletes files — filter to existing paths
  first.

- **A merge commit skips the pre-commit trunk hook** ("Merge detected. Skipping
  trunk"), so lint introduced while resolving conflicts goes straight to a red
  CI check. `trunk check --force` the conflicted files before committing a
  merge.

- **`.trunk/tools/` is gitignored and lazily populated** — the `trunk` symlink
  there does not exist until trunk has run once, so on a cold Codespace the
  documented path above fails with "No such file or directory". Fall back to
  `~/.cache/trunk/launcher/trunk`, which is always present; the first run
  creates the `.trunk/tools/trunk` symlink.

- **A `--force` check over ~10 files takes >2 minutes — background it.** Its
  progress spinner emits no result lines, so grepping interim output returns
  nothing and reads as a false "clean". Only interpret the output after the run
  exits.

- **Two concurrent trunk runs produce spurious `✖ N failures`.** A `FAILURES`
  block names a TOOL plus a `.trunk/out/*.yaml` and no rule — that is the linter
  crashing (e.g. `grype`), not a finding. Distinct from `✖ N unformatted files`
  (the pre-commit `fmt` hook fixes those) and from real lint issues, which name
  `file:line` + rule. Re-run single-instance before chasing one.

- **Linter**: Suppress with `trunk-ignore(linter/rule): reason` (e.g.
  `# trunk-ignore(bandit/B603): static argv, no shell`) on the line immediately
  before the flagged line — not linter-native disable syntax. Wrapping the
  reason onto extra comment lines silently breaks the suppression (trunk only
  honors the directive on the adjacent line), and CI also flags it with
  `trunk/ignore-does-nothing`. Binary:
  `/workspaces/teamster/.trunk/tools/trunk`.

- **Markdown**: Always specify a language on fenced code blocks (MD040). Use
  `text` only when no real language applies.

- **Markdown headings**: increment by one level (markdownlint MD001). `#` title
  goes directly to `##` — never jump to `###`.

- **Backtick identifiers in markdown prose**: trunk-fmt reads unbackticked
  `snake_case` / `glob_*` tokens as emphasis and mangles them (`attendance_day`
  → `attendance*day`). Wrap model/table/column names in backticks in docs,
  specs, and plans.

- **Nested triple-backticks in markdown**: when a fenced block contains a
  heredoc with its own ``` examples, promote the outer fence to 4-backticks so
  trunk-fmt doesn't mangle the structure.

- **Markdown ordered lists broken by code fences (MD029)**: a numbered list
  whose items are separated by fenced code blocks fails markdownlint MD029 —
  `trunk fmt` renumbers items sequentially (1, 2, 3), but each fence restarts
  the list so an item numbered >1 is invalid. Use `1.` for every item. Fires at
  CI only.

- **Widening a markdown table cell trips markdownlint MD060** (table column
  style) until `trunk fmt` re-pads the table. Commit and let the fmt hook fix it
  — don't hand-align.
