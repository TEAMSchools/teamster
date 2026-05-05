#!/bin/bash

# persist 1Password token for on-demand use (conftest.py reads this at test time)
echo "${OP_SERVICE_ACCOUNT_TOKEN}" >/etc/secret-volume/.op-token
chmod 600 /etc/secret-volume/.op-token

# revoke 1Password tokens from future interactive shells
grep -qF 'OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' /home/vscode/.bashrc ||
  echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
grep -qF 'OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' /home/vscode/.profile ||
  echo 'export OP_SERVICE_ACCOUNT_TOKEN=revoked-after-injection' >>/home/vscode/.profile
grep -qF 'OP_CONNECT_TOKEN=revoked-after-injection' /home/vscode/.bashrc ||
  echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >>/home/vscode/.bashrc
grep -qF 'OP_CONNECT_TOKEN=revoked-after-injection' /home/vscode/.profile ||
  echo 'export OP_CONNECT_TOKEN=revoked-after-injection' >>/home/vscode/.profile

set +euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

uv self update # reliable enough to not pin a version
uv tool upgrade --all
uv sync --frozen --all-groups

# install trunk tools
/workspaces/teamster/trunk install --verbose

# heal trunk state (drift from worktree pushes + orphaned caches from removed worktrees)
/workspaces/teamster/.trunk/tools/trunk git-hooks sync 2>/dev/null || true
hooks_path=$(git -C /workspaces/teamster config --get core.hooksPath 2>/dev/null) || hooks_path=
main_cache=
[[ -n ${hooks_path} ]] && main_cache=$(dirname "${hooks_path}")
for h in /home/vscode/.cache/trunk/repos/*/; do
  [[ -n ${main_cache} ]] && [[ ${h%/} == "${main_cache}" ]] && continue
  src=$(grep -hE 'workspaces/teamster' "${h}logs/daemon.log" 2>/dev/null |
    grep -oE '/workspaces/teamster[^ "]*\.trunk' | sort -u | head -1)
  # only delete when we have a confirmed-missing source path; skip empty-log dirs
  # (those may be active daemons that just rotated their logs)
  if [[ -n ${src} ]] && [[ ! -d ${src} ]]; then
    rm -rf "${h}" 2>/dev/null || true
  fi
done
/workspaces/teamster/.trunk/tools/trunk cache prune 2>/dev/null || true
