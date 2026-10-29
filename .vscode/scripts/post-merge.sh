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

# --all (the VS Code task) parses everything; the trunk post-merge action passes
# no args and parses only projects whose inputs the merge changed. git merge sets
# ORIG_HEAD to the pre-merge commit; without it, parse everything.
if [[ ${1-} == --all ]]; then
	changed="*"
else
	changed="$(git diff --name-only ORIG_HEAD HEAD 2>/dev/null)" || changed="*"
fi

needs_parse() {
	local project="$1" dir
	[[ ${changed} == "*" ]] && return 0
	[[ -f "src/dbt/${project}/target/prod/manifest.json" ]] || return 0
	# the dbt version and profiles feed every project
	grep -qE '^(uv\.lock|\.dbt/)' <<<"${changed}" && return 0
	for dir in "${project}" $(sed -n 's|^ *- local: \.\./||p' "src/dbt/${project}/packages.yml"); do
		grep -q "^src/dbt/${dir}/" <<<"${changed}" && return 0
	done
	return 1
}

for project in kipptaf kippnewark kippcamden kippmiami kipppaterson; do
	needs_parse "${project}" || continue
	uv run dbt parse --target prod \
		--project-dir "src/dbt/${project}" \
		--profiles-dir .dbt \
		--target-path target/prod &
done
wait
