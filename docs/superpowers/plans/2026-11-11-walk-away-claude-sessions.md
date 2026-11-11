# Walk-away Claude Code Sessions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Claude Code CLI session in the Codespace keeps running for about 2
hours with the laptop closed, and the steps are in the Codespaces guide.

**Architecture:** tmux is installed by the devcontainer's `postCreate.sh` and
holds the `claude` CLI process across VS Code disconnects. The author's GitHub
idle-timeout setting keeps the Codespace itself up. No scripts, config files, or
wrappers.

**Tech Stack:** devcontainer (`postCreate.sh`, apt), tmux, MkDocs.

**Spec:**
`docs/superpowers/specs/2026-11-11-walk-away-claude-sessions-design.md`

## Global Constraints

- Worktree:
  `/workspaces/teamster/.claude/worktrees/anthonygwalters/chore/claude-devcontainer-tmux`,
  branch `anthonygwalters/chore/claude-devcontainer-tmux`. No issue; the PR body
  carries no `Closes`/`Refs`.
- `.devcontainer/scripts/` is edit-protected: Claude presents the final
  replacement block; the author applies, stages, and commits it.
- `sudo` is removed at the end of `postCreate.sh`, so tmux only arrives through
  a container rebuild.
- No third-party devcontainer feature, wrapper script, tmux config, or ffmpeg.
- Idle timeout: 240 minutes (the GitHub maximum).

## Review Focus

Each of these is covered by a line in the guide section (Task 1, Step 3), since
none can be exercised by an automated test:

- An organization policy caps the idle timeout below 240 minutes: the guide
  tells the reader to check the value that was actually saved.
- The Codespace stops anyway (timeout reached, or stopped by hand): the tmux
  session is gone; the guide says to resume the conversation with
  `claude --resume`.
- The reader starts `tmux` from the VS Code panel's session and expects that
  session to persist: the guide says only the terminal CLI session survives.
- A second `tmux new -s claude` fails with "duplicate session": the guide gives
  `tmux attach -t claude` as the way back in.
- The Codespace bills for the full idle window: the guide says to stop the
  Codespace when the work is done.

---

### Task 1: Install tmux and document the workflow

**Files:**

- Modify (author applies): `.devcontainer/scripts/postCreate.sh:18`
- Modify: `docs/guides/codespaces.md` (new section after "Subsequent sessions",
  before "Container Internals")

- [ ] **Step 1: Hand the author the `postCreate.sh` change**

Final text of line 18:

```bash
	sudo apt-get -y install --no-install-recommends sshpass tmux &&
```

The author applies it in the worktree, then runs
`git -C <worktree> add .devcontainer/scripts/postCreate.sh` and commits with
`chore(devcontainer): install tmux`.

- [ ] **Step 2: Confirm the change landed**

Run: `git -C <worktree> log --oneline -1 -- .devcontainer/scripts/postCreate.sh`
Expected: the `chore(devcontainer): install tmux` commit.

- [ ] **Step 3: Add `## Walking away from a session` to
      `docs/guides/codespaces.md`**

Plain language, numbered steps, under 40 lines. It must say:

1. What it is for: a Claude Code session that keeps working with the laptop
   closed, for up to 4 hours.
2. One-time setup: GitHub → Settings → Codespaces → Default idle timeout → 240
   minutes; reopen the page to confirm the saved value (an org policy can cap
   it).
3. Start: open a terminal, `tmux new -s claude`, then `claude`. Tip:
   `claude --remote-control` lets you follow and answer prompts from the Claude
   mobile app.
4. Leave: `Ctrl-b` then `d` to detach, or just close the laptop.
5. Come back: `tmux attach -t claude`.
6. Limits, as a `!!! warning` admonition: only the terminal session persists,
   not the VS Code panel's; when the Codespace stops the tmux session ends, so
   use `claude --resume` to reopen the conversation; stop the Codespace when
   done, since it bills while idle.

- [ ] **Step 4: Lint and build the docs**

Run, with cwd in the worktree:

```bash
/workspaces/teamster/.trunk/tools/trunk check --force --no-fix docs/guides/codespaces.md </dev/null
uv run mkdocs build --strict 2>&1 | tail -n 15
```

Expected: `No issues`, and a build with no warnings naming
`guides/codespaces.md`.

- [ ] **Step 5: Commit, push, open the PR**

```bash
git -C <worktree> add -u
git -C <worktree> commit -m "docs(codespaces): document walk-away Claude sessions"
git -C <worktree> push
```

PR title `chore(devcontainer): tmux for walk-away Claude sessions`, body from
`.github/pull_request_template.md`. Note in the body that existing Codespaces
need a rebuild to get tmux.

### Task 2: Verify in a rebuilt Codespace (author, after merge)

**Files:** none.

- [ ] **Step 1: Rebuild**

Pull `main` in the main checkout, then run **Codespaces: Rebuild Container**.
Sign-ins stored outside `/workspaces` (GCloud application default login) need
redoing afterward, per the guide's "After the Codespace opens".

- [ ] **Step 2: Check the install**

Run: `tmux -V` Expected: `tmux 3.x`.

- [ ] **Step 3: One-hour walk-away test**

Set the idle timeout to 240 minutes. In a terminal: `tmux new -s claude`,
`claude`, start a task that runs several minutes, detach, close the laptop for
an hour. Reconnect and run `tmux attach -t claude`. Expected: the session is
there with the finished task.

- [ ] **Step 4: Record the result**

Comment on the PR whether the session survived, and whether the Codespace was
still inside its idle window or had been kept alive past it.
