#!/bin/bash
# Generate prod manifests for dbt --defer
# Runs in parallel — dbt parse is CPU-only (no DB access)

toplevel="$(git rev-parse --show-toplevel)" || {
	echo "⚠️  post-merge: git rev-parse failed, prod manifests not updated" >&2
	exit 0
}
cd "${toplevel}" || {
	echo "⚠️  post-merge: cd failed, prod manifests not updated" >&2
	exit 0
}

# linked worktrees have no dbt_packages/ and defer to the main checkout's manifests
git_dir="$(git rev-parse --path-format=absolute --git-dir)"
common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
[[ ${git_dir} == "${common_dir}" ]] || exit 0

# trunk-ignore(shellcheck/SC1091): sourced file created at runtime by uv installer
source "${HOME}/.local/bin/env"

for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
	uv run dbt parse --target prod \
		--project-dir "src/dbt/${project}" \
		--profiles-dir .dbt \
		--target-path target/prod &
done
wait
