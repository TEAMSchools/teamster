# Codespace Sandbox Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the GitHub Codespaces dev environment with OS-level isolation
(tmpfs, capability drops, sudo removal), Claude Code sandbox mode, and
restructured hook protections.

**Architecture:** Three-layer defense model — OS hardening (container level),
Claude Code sandbox (bash subprocess isolation), and hooks (Claude tool-level
protection). Each rule lives in the strongest layer that covers it. Protected
files (`.devcontainer/scripts/`, `.claude/hooks/`) must be drafted for manual
application due to hook self-protection rules.

**Tech Stack:** devcontainer.json, bash (postCreate.sh, inject-secrets.sh, hook
scripts), Claude Code settings.json, Python (sftp/assets.py)

**Spec:**
[2026-03-20-codespace-sandbox-hardening-design.md](../specs/2026-03-20-codespace-sandbox-hardening-design.md)

---

## File Map

| File                                      | Action          | Task |
| ----------------------------------------- | --------------- | ---- |
| `.devcontainer/devcontainer.json`         | Modify          | 1    |
| `.gitignore`                              | Modify          | 2    |
| `src/teamster/libraries/sftp/assets.py`   | Modify          | 3    |
| `.claude/settings.json`                   | Modify (manual) | 4    |
| `.devcontainer/scripts/postCreate.sh`     | Modify (manual) | 5    |
| `.devcontainer/scripts/inject-secrets.sh` | Modify (manual) | 6    |
| `.claude/hooks/check-output.sh`           | Modify (manual) | 7    |
| `tests/hooks/test_output_scanner.sh`      | Modify (manual) | 7    |
| `.claude/hooks/check-sensitive.sh`        | Modify (manual) | 8    |
| `tests/hooks/test_sensitive_paths.sh`     | Modify (manual) | 8    |
| `tests/hooks/test_self_protection.sh`     | Modify (manual) | 8    |
| `tests/hooks/test_bypass_protection.sh`   | Modify (manual) | 8    |

**Manual application pattern:** For files in `.devcontainer/scripts/` and
`.claude/hooks/`, the hook self-protection rule blocks Edit/Write. Draft the
complete replacement to `/tmp/<filename>` and present it to the user with the
target path and line numbers. The user copies it into place.

---

### Task 1: devcontainer.json — tmpfs mount + capability drops

**Files:**

- Modify: `.devcontainer/devcontainer.json`

- [ ] **Step 1: Add mounts and runArgs to devcontainer.json**

Add `mounts` and `runArgs` keys. Insert after the `"features"` block (after line
8):

```jsonc
"mounts": [
  "type=tmpfs,destination=/etc/secret-volume,tmpfs-mode=0700,tmpfs-size=10485760"
],
"runArgs": [
  "--cap-drop=NET_RAW",
  "--cap-drop=SYS_PTRACE",
  "--cap-drop=NET_ADMIN"
],
// NOTE: SYS_ADMIN is NOT added — Codespaces silently strips --cap-add=SYS_ADMIN.
// bwrap runs in weaker nested sandbox mode. See spec Section 2.
```

- [ ] **Step 2: Verify JSON is valid**

Run: `cat .devcontainer/devcontainer.json | jq .`

Expected: valid JSON output with `mounts` and `runArgs` keys present.

- [ ] **Step 3: Commit**

Write commit message to `/tmp/commit-msg.txt` and run
`git commit -F /tmp/commit-msg.txt`.

---

### Task 2: .gitignore — add symlink names

**Files:**

- Modify: `.gitignore`

- [ ] **Step 1: Add secret-volume and dagster-tmp to .gitignore**

Append to the top of `.gitignore` (after line 3, before the toptal block):

```gitignore
secret-volume
dagster-tmp
```

- [ ] **Step 2: Verify entries are present**

Run: `grep -n 'secret-volume\|dagster-tmp' .gitignore`

Expected: two matching lines.

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add secret-volume and dagster-tmp to gitignore"
```

---

### Task 3: SFTP transient file relocation

**Files:**

- Modify: `src/teamster/libraries/sftp/assets.py:180,312,334,338,454`

- [ ] **Step 1: Read the SFTP assets file**

Read `src/teamster/libraries/sftp/assets.py` around lines 178-182, 310-340, and
452-456 to confirm the five `./env/` references.

- [ ] **Step 2: Replace all five `./env/` references with `/tmp/dagster/`**

Use find-and-replace. All five occurrences use the pattern
`f"./env/{context.asset_key` — replace `./env/` with `/tmp/dagster/` in each.

Specific locations:

- Line 180: `build_sftp_file_asset` — `sftp_get` local path
- Line 312: `build_sftp_archive_asset` — `sftp_get` local path
- Line 334: `build_sftp_archive_asset` — `zipfile.extract` output path
- Line 338: `build_sftp_archive_asset` — extracted file path
- Line 454: `build_sftp_folder_asset` — `sftp_get` local path

- [ ] **Step 3: Verify no `./env/` references remain**

Run: `grep -n '\./env/' src/teamster/libraries/sftp/assets.py`

Expected: no output (all replaced).

- [ ] **Step 4: Run lint check**

Run: `trunk check src/teamster/libraries/sftp/assets.py`

Expected: no new issues.

- [ ] **Step 5: Commit**

```bash
git add src/teamster/libraries/sftp/assets.py
git commit -m "refactor: relocate SFTP transient files from ./env/ to /tmp/dagster/"
```

---

### Task 4: Claude Code sandbox configuration

**Files:**

- Modify: `.claude/settings.json` (manual — protected path)

- [ ] **Step 1: Read current settings.json**

Confirm the file structure and find the insertion point.

- [ ] **Step 2: Draft updated settings.json**

Add the `"sandbox"` key at the top level. Write complete updated file to
`/tmp/settings.json`. The sandbox block:

```json
"sandbox": {
  "enabled": true,
  "enableWeakerNestedSandbox": true,
  "filesystem": {
    "denyRead": [
      "~/.ssh",
      "~/.config/gcloud",
      "~/.kube",
      "/etc/secret-volume",
      "./secret-volume",
      "/proc/",
      "/dev/fd/",
      "./.devcontainer/tpl/",
      "./env/"
    ],
    "denyWrite": [
      "./.claude/settings.json",
      "./.claude/settings.local.json",
      "./.claude/hooks/",
      "./.claude/shell-snapshots/",
      "./.devcontainer/scripts/",
      "./.git/hooks/",
      "./.trunk/"
    ]
  }
}
```

- [ ] **Step 3: Present draft to user for manual application**

- [ ] **Step 4: Validate JSON**

Run: `cat .claude/settings.json | jq .`

Expected: valid JSON with `sandbox` block present.

- [ ] **Step 5: Commit**

Write commit message to `/tmp/commit-msg.txt` and run
`git commit -F /tmp/commit-msg.txt`.

---

### Task 5: postCreate.sh — bubblewrap, symlinks, sudo removal

**Files:**

- Modify: `.devcontainer/scripts/postCreate.sh` (manual — protected path)

- [ ] **Step 1: Read the current postCreate.sh**

- [ ] **Step 2: Draft the updated postCreate.sh to `/tmp/postCreate.sh`**

Three changes from current:

1. **Line 8:** Add `bubblewrap socat` to the apt install command:

   ```bash
   sudo apt-get -y install --no-install-recommends sshpass bubblewrap socat &&
   ```

2. **Remove lines 14 and 20:** `sudo mkdir -p /etc/secret-volume` and
   `sudo chmod 700 /etc/secret-volume` are no longer needed — the tmpfs mount in
   devcontainer.json handles creation, and the chown in the privileged sequence
   handles ownership.

3. **After line 106 (after `wait`):** Append the privileged sequence:

   ```bash
   # transfer tmpfs ownership to vscode
   sudo chown vscode:vscode /etc/secret-volume

   # inject secrets
   .devcontainer/scripts/inject-secrets.sh

   # create convenience symlinks
   ln -sf /etc/secret-volume /workspaces/teamster/secret-volume
   ln -sf /etc/secret-volume/.env /workspaces/teamster/env/.env
   mkdir -p /tmp/dagster
   ln -sf /tmp/dagster /workspaces/teamster/dagster-tmp

   # remove sudo — must be last privileged step
   sudo rm -f /usr/local/bin/sudo /usr/bin/sudo
   ```

- [ ] **Step 3: Present draft to user for manual application**

- [ ] **Step 4: Verify the file was applied**

Run: `head -10 .devcontainer/scripts/postCreate.sh` and
`tail -15 .devcontainer/scripts/postCreate.sh`

Expected: bubblewrap/socat in apt install, privileged sequence at end.

- [ ] **Step 5: Commit**

Write commit message to `/tmp/commit-msg.txt` and run
`git commit -F /tmp/commit-msg.txt`.

---

### Task 6: inject-secrets.sh — remove sudo, update paths

**Files:**

- Modify: `.devcontainer/scripts/inject-secrets.sh` (manual — protected path)

- [ ] **Step 1: Read the current inject-secrets.sh**

- [ ] **Step 2: Draft the updated inject-secrets.sh to
      `/tmp/inject-secrets.sh`**

Changes:

1. Replace the sudo block for secret file installation:

   ```bash
   # before (remove):
   sudo chown root:root "${TMP_SECRET}"
   sudo chmod 600 "${TMP_SECRET}"
   sudo mv -f "${TMP_SECRET}" "/etc/secret-volume/${tpl}"

   # after:
   install -m 600 "${TMP_SECRET}" "/etc/secret-volume/${tpl}"
   ```

2. Change `.env` write target from `env/.env` to `/etc/secret-volume/.env`.

3. Remove `env/.env.tmp` references from cleanup trap.

- [ ] **Step 3: Present draft to user for manual application**

- [ ] **Step 4: Verify the file was applied**

Run: `grep -n 'sudo' .devcontainer/scripts/inject-secrets.sh`

Expected: no sudo references remain.

- [ ] **Step 5: Commit**

Write commit message to `/tmp/commit-msg.txt` and run
`git commit -F /tmp/commit-msg.txt`.

---

### Task 7: check-output.sh — remove Edit from matcher

**Files:**

- Modify: `.claude/hooks/check-output.sh` (manual — protected path)
- Modify: `tests/hooks/test_output_scanner.sh` (manual)

- [ ] **Step 1: Draft updated check-output.sh to `/tmp/check-output.sh`**

The only change is on line 9 — remove `Edit|` from the matcher regex:

```bash
# before (line 9):
[[ ! ${tool_name} =~ ^(Bash|Read|Edit|Grep|NotebookEdit|WebFetch|WebSearch|mcp__.*)$ ]] && exit 0

# after:
[[ ! ${tool_name} =~ ^(Bash|Read|Grep|NotebookEdit|WebFetch|WebSearch|mcp__.*)$ ]] && exit 0
```

- [ ] **Step 2: Draft updated test_output_scanner.sh to
      `/tmp/test_output_scanner.sh`**

Add after line 90 (after the existing Write test):

```bash
check_output "Edit tool output not scanned" clean Edit "op://vault/item/field"
```

- [ ] **Step 3: Present both drafts to user for manual application**

- [ ] **Step 4: Run hook tests to verify**

Run: `bash tests/hooks/test_output_scanner.sh`

Expected: all tests pass, including the new Edit test.

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/check-output.sh tests/hooks/test_output_scanner.sh
git commit -m "chore: remove Edit from output scanner matcher"
```

---

### Task 8: check-sensitive.sh — restructure by tool type

**Files:**

- Modify: `.claude/hooks/check-sensitive.sh` (manual — protected path)
- Modify: `tests/hooks/test_bypass_protection.sh` (manual)
- Modify: `tests/hooks/test_sensitive_paths.sh` (manual)

This is the largest task. The hook is restructured from a flat rule list into
three tool-type sections. Rule 6 is removed entirely. Rules 1/1b/2 remain
applied to ALL tools (including Bash) — the verification gate in Task 10
determines whether they can be removed from Bash scope later.

- [ ] **Step 1: Draft the restructured check-sensitive.sh to
      `/tmp/check-sensitive.sh`**

Reorganize the script into three sections. All regex patterns stay identical —
only the structure changes:

**Key structural changes:**

- **Rule 6** (`/proc/*/`, `/dev/fd/`) — **removed entirely** (lines 119-122)
- **Rules 3, 3b, 3c, 4, 5, 5a-5d, 7** — **wrapped in
  `if [[ ${tool_name} == "Bash" ]]; then ... fi`**
- **Rules 1, 1b, 2** — **unchanged**, still apply to ALL tools (including Bash)
  pending the verification gate
- **Rule 8** — **unchanged**, already scoped to `mcp__bigquery__*`

Section structure:

```bash
# ═══════════════════════════════════════════════════════════════════
# Section 1: All tools — path-based protection
# ═══════════════════════════════════════════════════════════════════
# Rule 1: Sensitive file/directory patterns (unchanged)
# Rule 1b: File-extension patterns (unchanged)
# Rule 2: Hook self-protection (unchanged)

# ═══════════════════════════════════════════════════════════════════
# Section 2: Bash only — command-pattern protection
# ═══════════════════════════════════════════════════════════════════
if [[ ${tool_name} == "Bash" ]]; then
  # Rule 3/3b/3c: Env var leakage (same regex)
  # Rule 4: 1Password CLI (same regex)
  # Rule 5/5a-5d: Encoding bypass (same regex)
  # Rule 7: $VAR expansion (same regex)
fi

# ═══════════════════════════════════════════════════════════════════
# Section 3: BigQuery MCP — read-only enforcement
# ═══════════════════════════════════════════════════════════════════
# Rule 8: (unchanged)
```

- [ ] **Step 2: Draft updated test_bypass_protection.sh to
      `/tmp/test_bypass_protection.sh`**

Remove the "Pattern 6: Broad /proc access" section (lines 126-136) and the
"/dev/fd/ bypass" section (lines 138-143). These rules no longer exist in the
hook.

Also add tests confirming Bash-only rules do NOT fire for file tools:

```bash
# ─── Tool-type scoping: Bash-only rules don't fire for file tools ──────
echo ""
echo -e "${YELLOW}Tool-type scoping: Bash-only rules for file tools${NC}"

expect_allow "Read file named printenv" Read file_path "/tmp/printenv-results.txt"
expect_allow "Read file named op-docs" Read file_path "/tmp/op-vault-docs.txt"
expect_allow "Grep for printenv in code" Grep pattern "printenv"
```

- [ ] **Step 3: Draft updated test_sensitive_paths.sh to
      `/tmp/test_sensitive_paths.sh`**

Add regression tests confirming Rules 1/1b still apply to Bash (since the
verification gate hasn't passed yet):

```bash
# ─── Bash path protection (retained pending verification gate) ──────
echo ""
echo -e "${YELLOW}Bash path protection (retained pending verification gate)${NC}"

expect_deny "bash cat .env" Bash command "cat .env"
expect_deny "bash cat secret-volume" Bash command "cat /etc/secret-volume/token"
expect_deny "bash cat .devcontainer/tpl/" Bash command "cat .devcontainer/tpl/template"
```

- [ ] **Step 4: Present all drafts to user for manual application**

- [ ] **Step 5: Run all hook tests**

Run: `bash tests/hooks/run_all.sh`

Expected: all 6 test suites pass. Rule 6 tests are removed, tool-type scoping
tests pass, all other tests unchanged.

- [ ] **Step 6: Commit**

```bash
git add .claude/hooks/check-sensitive.sh tests/hooks/
git commit -m "refactor: restructure check-sensitive.sh by tool type, remove Rule 6"
```

---

### Task 9: Container rebuild + verification

This task requires a container rebuild to test OS-level changes (Tasks 1, 5, 6).

> **Important:** `devcontainer.json` changes (`mounts`, `runArgs`) are applied
> at container creation time and must be on the branch the Codespace is checked
> out to. The rebuild will NOT pick up changes from the feature branch if the
> Codespace is on `main`. Merge the PR first (or check out the feature branch),
> then do a **Full Rebuild** from the VS Code command palette.

- [ ] **Step 1: Merge PR and rebuild the codespace**

Merge the PR to `main`, then rebuild via VS Code command palette:
`Codespaces: Full Rebuild Container` (not just "Rebuild Container").

- [ ] **Step 2: Verify tmpfs mount**

Run: `mount | grep secret-volume`

Expected: `tmpfs on /etc/secret-volume type tmpfs (rw,...,size=10240k,mode=700)`

- [ ] **Step 3: Verify ownership**

Run: `ls -la /etc/ | grep secret-volume`

Expected: `drwx------ ... vscode vscode ... secret-volume`

- [ ] **Step 4: Verify sudo is removed**

Run: `command -v sudo`

Expected: no output (sudo not found).

- [ ] **Step 5: Verify symlinks**

Run: `ls -la secret-volume dagster-tmp env/.env`

Expected: all three are symlinks pointing to their targets.

- [ ] **Step 6: Verify inject-secrets.sh ran successfully**

Run: `ls -la /etc/secret-volume/`

Expected: `.env` and any template-based secrets present with mode 600.

- [ ] **Step 7: Verify bubblewrap is installed**

Run: `bwrap --version`

Expected: version string output.

- [ ] **Step 8: Confirm bwrap runs in weaker nested mode**

Run: `bwrap --ro-bind / / -- echo "bwrap works"`

Expected: fails with "No permissions to create new namespace" — this is correct.
Codespaces silently strips `--cap-add=SYS_ADMIN`, so full sandbox mode is
unavailable. Claude Code falls back to `enableWeakerNestedSandbox` mode
automatically. Verify via `/sandbox` in the Claude Code CLI.

---

### Task 10: Sandbox verification gate

This task determines whether Rules 1/1b/2 can be removed from Bash scope.
Requires the Claude Code CLI (`npm install -g @anthropic-ai/claude-code`).

- [ ] **Step 1: Enable sandbox via CLI**

Run `claude` in terminal, then type `/sandbox` to confirm sandbox is active.

- [ ] **Step 2: Test sandbox denyRead paths**

In the Claude Code CLI, attempt to read each denied path via bash:

```bash
cat ~/.ssh/id_rsa
cat ~/.config/gcloud/application_default_credentials.json
cat ~/.kube/config
cat /etc/secret-volume/.env
cat /proc/self/environ
cat /dev/fd/0
cat .devcontainer/tpl/.env.tpl
cat secret-volume/.env
cat env/.env
```

Expected: all return "Permission denied" or similar sandbox error.

- [ ] **Step 3: Test sandbox denyWrite paths**

```bash
touch .claude/settings.json.test
touch .claude/hooks/test
touch .devcontainer/scripts/test
touch .git/hooks/test
touch .trunk/test
```

Expected: all return "Permission denied" or similar sandbox error.

- [ ] **Step 4: Record results and decide**

If ALL paths are blocked → Rules 1/1b/2 can be removed from Bash scope in a
follow-up PR.

If ANY path is NOT blocked → Rules 1/1b/2 remain for Bash. Document which paths
failed.

- [ ] **Step 5: Run full hook test suite**

Run: `bash tests/hooks/run_all.sh`

Expected: all suites pass.

---

### Task 11: Audit — verify no stale env/.env references

- [ ] **Step 1: Search for hardcoded env/.env references**

Run:
`grep -r 'env/\.env' --include='*.py' --include='*.sh' --include='*.json' --include='*.yaml' --include='*.yml' .`

Expected: only the symlink creation in `postCreate.sh` and `.gitignore` entries.

- [ ] **Step 2: Search for ./env/ references in Python code**

Run: `grep -rn '\./env/' --include='*.py' .`

Expected: no matches (all replaced in Task 3).
