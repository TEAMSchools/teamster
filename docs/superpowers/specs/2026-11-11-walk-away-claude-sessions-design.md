# Walk-away Claude Code sessions in the Codespace

## Why

A Claude Code session should keep working for about 2 hours while the laptop is
closed during travel, and be there to pick up afterward. The work is ordinary
dbt development plus one-offs such as Tableau workbook XML and ffmpeg video
slicing, all of which depend on this repo's Codespace: its credentials, `uv`
environment, hooks, skills, MCP servers, and files on disk.

## Goals

- A session started in the Codespace survives the VS Code connection dropping.
- The Codespace stays up for at least 2 hours after the laptop closes.
- The steps are written down where the team already looks for Codespace help.

## Non-goals

- Keeping the VS Code extension panel's session alive. Walk-away sessions use
  the terminal CLI.
- Runs longer than the Codespace idle timeout allows (4 hours at most).
- An always-on machine, or moving work to Claude Code cloud sessions.
- Installing ffmpeg.

## Anti-goals

- A new place for credentials that reach student data.
- A third-party devcontainer feature, wrapper script, or tmux config to
  maintain.

## Constraints

- `postCreate.sh` removes `sudo` as its last step, so a system package can only
  be installed there. An existing Codespace gets tmux by rebuilding the
  container after the change is on the checked-out branch.
- `.devcontainer/scripts/` is edit-protected. Claude drafts the change; the
  author applies, stages, and commits it.
- The Codespace idle timeout is a per-user GitHub setting (default 30 minutes,
  maximum 240) that an organization policy can cap.
- Whether a working agent in tmux resets the idle timer is unconfirmed. The
  design does not depend on it: a 240-minute timeout covers a 2-hour absence
  either way.

## Approaches

### A. tmux in the Codespace plus a longer idle timeout (chosen)

Run `claude` inside tmux in the Codespace terminal, and raise the idle timeout
so the Codespace outlives the absence. Small change, keeps every tool the work
needs. Bounded by the 4-hour timeout.

### B. Claude Code cloud sessions

Run on Anthropic-hosted infrastructure with no device or Codespace. Starts from
a fresh clone, so secrets, hooks, and most MCP servers would need rebuilding
there, and it does not suit ffmpeg on local files or the Tableau work.

### C. An always-on machine running the devcontainer

No idle timeout, so overnight runs work. The most setup, an ongoing cost, and a
new home for credentials that reach student data.

A was picked because the absences are about 2 hours and the work needs this
environment.

## Design

1. Add `tmux` to the existing `apt-get install` line in
   `.devcontainer/scripts/postCreate.sh`, next to `sshpass`.
2. Add a "Walking away from a session" section to `docs/guides/codespaces.md`,
   after "Subsequent sessions", covering:
   - the one-time setup: raise the idle timeout to 240 minutes in GitHub
     Codespaces settings;
   - starting a session: `tmux new -s claude`, then `claude` (or
     `claude --remote-control` to follow and answer prompts from a phone);
   - detaching, and reattaching with `tmux attach -t claude`;
   - the limits: terminal CLI only, and the Codespace still stops when the idle
     timeout runs out.

## Verification

After the change merges and the Codespace is rebuilt:

1. `tmux -V` prints a version.
2. Start a long task in a tmux `claude` session, close the laptop for an hour,
   reconnect, and confirm `tmux attach -t claude` shows the session still
   running. Record in the PR whether the Codespace stayed up on agent activity
   alone or on the raised timeout.

## Left to the builder

- Exact wording of the guide section.
- Whether the guide mentions Remote Control inline or as a one-line tip.
