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

## What the hooks cover

- `trunk-fmt-pre-commit` formats at commit time and `trunk-check-pre-push`
  blocks bad pushes, in the main repo and in worktrees (`core.hooksPath` is
  shared). Do not run `trunk fmt` or `trunk check` as a routine.
- The pre-commit hook runs `fmt` only. sqlfluff, yamllint, and other check-only
  linters fire at pre-push and in CI, so a clean commit is not lint-clean.
- The pre-push check is git-diff-scoped (no `--force`) and can miss a sqlfluff
  violation (e.g. ST06) on already-committed lines that CI's full check flags:
  the push succeeds and CI fails.
- A merge commit skips the pre-commit hook ("Merge detected. Skipping trunk"),
  so lint introduced while resolving conflicts goes straight to a red CI check.

## Checking before you claim lint-clean

- Run
  `/workspaces/teamster/.trunk/tools/trunk check --force --no-fix <files> </dev/null`
  on changed SQL, YAML, and markdown before pushing, and on conflicted files
  before committing a merge.
- Over `git diff --name-only origin/main...HEAD`, filter to existing paths
  first: a PR that deletes files hard-errors with `'<path>' does not exist`.
- A `--force` check over ~10 files takes >2 minutes; background it. Its progress
  spinner emits no result lines, so grepping interim output reads as a false
  "clean". Interpret the output only after the run exits.
- Two concurrent trunk runs produce spurious `✖ N failures`. A `FAILURES` block
  that names a TOOL plus a `.trunk/out/*.yaml` and no rule is the linter
  crashing (e.g. `grype`), not a finding. Real lint issues name `file:line` and
  a rule; `✖ N unformatted files` is fixed by the fmt hook. Re-run
  single-instance before chasing one.

## Binary path and worktrees

- `.trunk/tools/` is gitignored and lazily populated in every checkout: the
  `trunk` symlink does not exist until trunk has run once there, so on a cold
  Codespace the path above fails with "No such file or directory". Fall back to
  `~/.cache/trunk/launcher/trunk`, which is always present; the first run
  creates the symlink.
- Run with cwd inside the worktree, calling the main repo's absolute binary
  path. `trunk check --force <abs-worktree-paths>` from the main repo silently
  returns "no applicable linters", and relative paths from the main repo check
  the main-repo copies, not your worktree edits.

## Suppressions

- `trunk-ignore(linter/rule): reason` (e.g.
  `# trunk-ignore(bandit/B603): static argv, no shell`) on the line immediately
  before the flagged line, never linter-native disable syntax. Wrapping the
  reason onto extra comment lines silently breaks the suppression, and CI flags
  it with `trunk/ignore-does-nothing`.

## Markdown rules

- Always give fenced code blocks a language (MD040); `text` only when no real
  language applies.
- Headings increment by one level (MD001): `#` goes directly to `##`.
- Backtick `snake_case` / `glob_*` identifiers in prose: trunk-fmt reads them as
  emphasis and mangles them (`attendance_day` → `attendance*day`).
- A fenced block containing its own ``` examples needs a 4-backtick outer fence,
  or trunk-fmt mangles the structure.
- A numbered list whose items are separated by fenced code blocks fails MD029:
  each fence restarts the list. Use `1.` for every item. Fires at CI only.
- Widening a table cell trips MD060 (table column style) until `trunk fmt`
  re-pads the table. Commit and let the fmt hook fix it; don't hand-align.
