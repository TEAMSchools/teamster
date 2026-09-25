---
name: resuming-a-branch
description:
  Use before resuming work on an existing branch, merging origin/main into a
  branch, resolving a merge conflict (especially lockfile/version-only
  conflicts), diagnosing a CI failure in a file the branch never touched,
  recovering after a Codespace restart desynced git refs or deleted worktrees,
  or reverting experimental code so a PR is docs-only.
---

# resuming-a-branch

- **`git merge-tree` reads the committed tip, not the index** — a staged-but-
  uncommitted conflict resolution still reports CONFLICT. Commit first, then
  verify with `git merge-tree --write-tree --name-only origin/main <branch>`.

- **A version-only dependency conflict resolves by taking main's blobs whole**:
  `git checkout origin/main -- <manifest> <lockfile>`, then run the installer
  and confirm it leaves the lockfile unchanged (proof main's pair is coherent).
  Both files end byte-identical to main, so the conflict cannot recur. Do NOT
  hand-merge a lockfile.

- **Git resuming**: Before resuming work on an existing branch, merge `main`:
  `git fetch origin main && git merge origin/main`.

- **A CI failure in a file your branch never touched usually means `main`
  moved** — run `git log <merge-base>..origin/main` before diagnosing. A clean
  prod baseline does NOT rule this out — CI builds `--full-refresh` against
  deferred upstreams, so prod passing and CI failing is the expected shape.
  Check git before the warehouse; it is one command and decisive.

- **A mid-session Codespace restart can delete `.worktrees/` and desync local
  git refs** (stale `main`, `git ls-remote <branch>` empty for a live branch, a
  HEAD that reads as the pre-session commit yet holds merged content). Trust
  GitHub over local git for ground truth: `gh api .../branches/main` and
  `gh api .../pulls/<n>` (`merged` / `merge_commit_sha`), then re-fetch and
  recreate any lost worktree off `origin/main`.

- **Reverting experimental code to a docs-only PR**:
  `git checkout origin/main -- <file>` restores main's CURRENT blob, which can
  differ from the branch's merge-base and leak main's advancement into the
  three-dot PR diff. Restore to the merge-base instead —
  `git checkout $(git merge-base origin/main HEAD) -- <file>` — then verify with
  `git diff --stat origin/main...HEAD`.
