#!/bin/bash
# Generate prod manifests for Power User --defer
# Runs in parallel — dbt parse is CPU-only (no DB access)

cd "$(git rev-parse --show-toplevel)" || exit 0

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
  uv run dbt parse --target prod \
    --project-dir "src/dbt/${project}" \
    --profiles-dir .dbt \
    --target-path target/prod &
done
wait
