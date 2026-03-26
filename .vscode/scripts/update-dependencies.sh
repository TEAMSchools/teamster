#!/bin/bash

set -euo pipefail

# trunk-ignore(shellcheck/SC1091): sourced at runtime
source "${HOME}/.local/bin/env"

GITHUB_USER="${GITHUB_USER:-$(gh api user --jq .login 2>/dev/null)}"
BRANCH="${GITHUB_USER}/chore/update-dependencies-$(date +%Y-%m-%d)"

echo "Creating branch: ${BRANCH}"
git checkout -b "${BRANCH}"

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
  dbt deps --upgrade "--project-dir=src/dbt/${project}"
done

echo -e "\n\033[1;34m▶ Committing changes\033[0m"
git add -A
git commit -m "chore: update dependencies"

echo -e "\n\033[1;32m✔ All dependencies updated and committed\033[0m"
