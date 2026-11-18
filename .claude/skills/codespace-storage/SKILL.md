---
name: codespace-storage
description:
  'Use when the Codespace is low on disk or storage, `df` shows `/workspaces` or
  `/` near full, a user asks what is taking up space or what is safe to delete,
  `~/.cache/uv` exists, or uv warns "Failed to hardlink files; falling back to
  full copy".'
---

# Codespace storage

`/` (overlay, holds `/home/vscode`) and `/workspaces` (loop device) are separate
filesystems that report the same disk. uv hardlinks package files from
`/workspaces/.uv-cache` into every `.venv`, so the same bytes appear under
several paths. Report first; delete only what the user picks.

## Measure

- `df -h /workspaces` is the only true total. Re-run it after each cleanup step.
- `du -sh a b c` in ONE call counts a hardlinked file once, under the first path
  listed. Separate `du` calls count it once per path. Quote a group's savings as
  "at most" one `du` of the parent folder, never a sum of per-item `du` values.
- `uv cache dir` names the live cache. Anything else named `uv` under `~/.cache`
  is not live.
- Unused part of the live cache (link count 1, so no `.venv` shares it):
  `find /workspaces/.uv-cache/archive-v0 -type f -links 1 -printf '%s\n' | awk '{s+=$1} END {print s/1e9 " GB"}'`

## What to report, and what each action frees

| Item                          | Action                                              | Frees                                                                     |
| ----------------------------- | --------------------------------------------------- | ------------------------------------------------------------------------- |
| `~/.cache/uv`                 | Find the cause first (below), then `rm -rf`         | All of it                                                                 |
| `/workspaces/.uv-cache`       | `uv cache clean`                                    | Only the link-count-1 part. `.venv` files survive; next sync re-downloads |
| Same, gentler                 | `uv cache prune`                                    | Only dangling entries. Old versions uv still indexes stay. Measure        |
| `~/.npm`                      | `npm cache clean --force` AND `rm -rf ~/.npm/_npx`  | `npm cache clean` skips `_npx` (MCP server packages)                      |
| `~/.cache/trunk`              | `trunk cache clean --all`                           | Tools re-download on next lint                                            |
| `~/.vscode-remote/extensions` | Delete the older of two same-name version folders   | Confirm which version VS Code runs first                                  |
| `~/.claude/projects`          | Ask. Session transcripts; deleting drops history    | Up to its size                                                            |
| A worktree `.venv`            | `rm -rf <worktree>/.venv`; rebuilt on next `uv run` | Less than its `du`: shared files stay                                     |

## Worktrees

Removable = merged into a freshly fetched `origin/main` AND
`git status --porcelain` empty. Removal deletes gitignored files without a
warning, so list them with `git -C <worktree> status --porcelain --ignored` and
name any that are not rebuildable (`.claude/scratch/` notes, local data). Use
`git worktree remove` (no `--force`), then `git worktree prune`. Leave the
branches alone.

## `~/.cache/uv` exists: something runs uv without the container's settings

`containerEnv` sets `UV_CACHE_DIR` and `UV_LINK_MODE`, but trunk actions get
neither (see `.vscode/CLAUDE.md`). uv then uses `~/.cache/uv` on the other
filesystem and copies every file into the `.venv`. Before deleting it:

1. Search transcripts for the warning:
   `rg -l 'Failed to hardlink' ~/.claude/projects` (slow; run in background).
   The surrounding tool result or pasted text names the command.
2. Check whether a `.venv` holds copies: pick one package at the same version in
   two venvs and compare `stat -c '%i %h'` on one of its files. Different inodes
   mean at least one is a copy. Link count 1 alone proves nothing once the cache
   has been cleaned.
3. Fix the caller to export both settings, then delete the folder. A copied
   `.venv` stays copied until deleted and re-synced, and the re-sync frees space
   only if the live cache already holds those versions. Into an empty cache it
   re-downloads them, so the net change is near zero.

Naming `.trunk/` config, `.git/hooks`, or `.devcontainer/scripts` in Bash is
hook-blocked. Read them, or write a probe script to `.claude/scratch/`.
