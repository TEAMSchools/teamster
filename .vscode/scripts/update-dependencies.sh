#!/bin/bash

set -euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced at runtime
source "${HOME}/.local/bin/env"

REPO_ROOT="$(git rev-parse --show-toplevel)"
GITHUB_USER="${GITHUB_USER:-$(gh api user --jq .login 2>/dev/null)}"
BRANCH="${GITHUB_USER}/chore/update-dependencies-$(date +%Y-%m-%d)"
WORKTREE="${REPO_ROOT}/.worktrees/${BRANCH}"

# --- create branch + worktree ---
if [[ -d ${WORKTREE} ]]; then
  echo "Reusing existing worktree: ${WORKTREE}"
else
  if git show-ref --verify --quiet "refs/heads/${BRANCH}"; then
    echo "Adding worktree for existing branch: ${BRANCH}"
    git worktree add "${WORKTREE}" "${BRANCH}"
  else
    echo "Creating branch + worktree: ${BRANCH}"
    git worktree add -b "${BRANCH}" "${WORKTREE}"
  fi
fi

cd "${WORKTREE}"

# --- update dependencies ---
echo -e "\n\033[1;34m▶ uv lock --upgrade\033[0m"
uv lock --upgrade

echo -e "\n\033[1;34m▶ uv sync\033[0m"
uv sync

echo -e "\n\033[1;34m▶ trunk upgrade\033[0m"
trunk upgrade -y

DBT_PROJECTS=(
  amplify
  deanslist
  edplan
  finalsite
  iready
  overgrad
  pearson
  powerschool
  renlearn
  titan
  kippcamden
  kippmiami
  kippnewark
  kipppaterson
  kipptaf
)

for project in "${DBT_PROJECTS[@]}"; do
  echo -e "\n\033[1;34m▶ dbt deps --upgrade (${project})\033[0m"
  uv run dbt deps --upgrade "--project-dir=src/dbt/${project}"
done

# --- commit ---
echo -e "\n\033[1;34m▶ Committing changes\033[0m"
git add -u
git commit -m "chore: update dependencies"

echo -e "\n\033[1;34m▶ Pushing to origin\033[0m"
git push -u origin "${BRANCH}"

echo -e "\n\033[1;32m✔ All dependencies updated, committed, and pushed\033[0m"
