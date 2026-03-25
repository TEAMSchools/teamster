#!/usr/bin/env bash
# Pre-commit hook: verify new extract SQL files have complete YML property files.
# Called by Trunk as a custom action (git_hooks: [pre-commit]).
# Safe to run standalone — exits 0 when no extract SQL files are staged.

set -euo pipefail

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Resolve the repository root relative to this script's location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
DEFERRALS_FILE="${SCRIPT_DIR}/../.yml-sync-deferrals.json"
GENERATE_SCRIPT="${SCRIPT_DIR}/dbt-extracts-yml-generate.py"

# ---------------------------------------------------------------------------
# Collect staged extract SQL files
# ---------------------------------------------------------------------------

# All staged/added/modified SQL files under any extracts/ directory.
mapfile -t staged_sql < <(
  git -C "${REPO_ROOT}" diff --cached --name-only --diff-filter=ACM |
    grep -E '^src/dbt/[^/]+/models/extracts/.+\.sql$' || true
)

if [[ ${#staged_sql[@]} -eq 0 ]]; then
  exit 0
fi

# ---------------------------------------------------------------------------
# Deferral helpers (pure bash wrappers around uv run python)
# ---------------------------------------------------------------------------

# Writes exit code of the inner python call to a temp variable DEFER_RESULT.
# 0 = deferred (skip), 1 = not deferred (check).
# Prints a status line to stderr for transparency.
# Usage: check_deferral <model_name>; then test $DEFER_RESULT
DEFER_RESULT=0
check_deferral() {
  local model_name="$1"
  DEFER_RESULT=1

  # If no deferrals file, nothing is deferred.
  if [[ ! -f ${DEFERRALS_FILE} ]]; then
    return 0
  fi

  uv run python -c "
import json, sys
from pathlib import Path

path = Path('${DEFERRALS_FILE}')
deferrals = json.loads(path.read_text())
model = '${model_name}'

if model not in deferrals:
    sys.exit(1)  # not deferred

entry = deferrals[model]
mode = entry.get('mode', 'next')

if mode == 'next':
    # 'next' means skip exactly this commit, then remove the deferral.
    del deferrals[model]
    path.write_text(json.dumps(deferrals, indent=2) + '\n')
    print(f'[dbt-extract-yml-check] Deferral consumed for {model!r} (mode=next)', file=sys.stderr)
    sys.exit(0)  # deferred

if mode == 'count':
    remaining = entry.get('remaining', 0)
    if remaining > 0:
        deferrals[model]['remaining'] = remaining - 1
        path.write_text(json.dumps(deferrals, indent=2) + '\n')
        print(f'[dbt-extract-yml-check] Deferral consumed for {model!r} (remaining={remaining - 1})', file=sys.stderr)
        sys.exit(0)  # still deferred
    else:
        # Exhausted — remove and re-check.
        del deferrals[model]
        path.write_text(json.dumps(deferrals, indent=2) + '\n')
        print(f'[dbt-extract-yml-check] Deferral expired for {model!r}', file=sys.stderr)
        sys.exit(1)  # not deferred

# Unknown mode — treat as not deferred.
sys.exit(1)
" >/dev/null 2>&1 && DEFER_RESULT=0 || DEFER_RESULT=1
}

# ---------------------------------------------------------------------------
# YML completeness check
# ---------------------------------------------------------------------------

# Sets YML_COMPLETE_RESULT to 0 (complete) or 1 (incomplete).
# Usage: check_yml_complete <yml_path>; then test $YML_COMPLETE_RESULT
YML_COMPLETE_RESULT=0
check_yml_complete() {
  local yml_path="$1"
  YML_COMPLETE_RESULT=1

  uv run python -c "
import sys
from pathlib import Path

path = Path('${yml_path}')
if not path.exists():
    sys.exit(1)

text = path.read_text()

has_data_type = 'data_type:' in text
has_unique = 'unique:' in text or 'unique_combination_of_columns' in text

sys.exit(0 if (has_data_type and has_unique) else 1)
" && YML_COMPLETE_RESULT=0 || YML_COMPLETE_RESULT=1
}

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

blocked=()

for rel_path in "${staged_sql[@]}"; do
  abs_sql="${REPO_ROOT}/${rel_path}"
  model_name="$(basename "${abs_sql}" .sql)"

  # Determine the expected YML location:
  #   <extracts-subdir>/properties/<model_name>.yml
  sql_dir="$(dirname "${abs_sql}")"
  yml_path="${sql_dir}/properties/${model_name}.yml"
  yml_rel="$(dirname "${rel_path}")/properties/${model_name}.yml"

  # ------------------------------------------------------------------
  # Is this a newly added (A) SQL file or a modified (M) one?
  # ------------------------------------------------------------------
  is_new=false
  git -C "${REPO_ROOT}" diff --cached --name-only --diff-filter=A |
    grep -qF "${rel_path}" && is_new=true || true

  if [[ ${is_new} == "true" ]]; then
    # NEW SQL FILE — enforce YML completeness.

    # Check deferral first.
    check_deferral "${model_name}"
    if [[ ${DEFER_RESULT} -eq 0 ]]; then
      continue
    fi

    # No YML at all → block.
    if [[ ! -f ${yml_path} ]]; then
      blocked+=("${model_name}|${rel_path}|missing")
      continue
    fi

    # YML exists — is it also newly staged?
    yml_newly_staged=false
    git -C "${REPO_ROOT}" diff --cached --name-only --diff-filter=A |
      grep -qF "${yml_rel}" && yml_newly_staged=true || true

    if [[ ${yml_newly_staged} == "true" ]]; then
      # Staged alongside SQL — check completeness.
      check_yml_complete "${yml_path}"
      if [[ ${YML_COMPLETE_RESULT} -ne 0 ]]; then
        blocked+=("${model_name}|${rel_path}|incomplete")
        continue
      fi
    fi
    # YML exists and is not newly staged (pre-existing) → pass.

  else
    # MODIFIED SQL FILE — friendly reminder only (non-blocking).
    echo ""
    echo "  💡 Friendly reminder: check downstream models for impact based on your"
    echo "     changes to '${model_name}'. Build the current model + downstream with:"
    echo "       dbt build --select ${model_name}+"
    echo ""
  fi
done

# ---------------------------------------------------------------------------
# Report blocked models and exit
# ---------------------------------------------------------------------------

if [[ ${#blocked[@]} -eq 0 ]]; then
  exit 0
fi

echo ""
echo "  ❌ The following extract models need complete YML property files:"
echo ""

for entry in "${blocked[@]}"; do
  model_name="${entry%%|*}"
  rest="${entry#*|}"
  sql_rel="${rest%%|*}"
  reason="${rest##*|}"

  if [[ ${reason} == "missing" ]]; then
    reason_label="(no YML found)"
  else
    reason_label="(YML missing data_type: or uniqueness test)"
  fi

  echo "    ${model_name}  ${reason_label}"
  echo "      Generate: uv run ${GENERATE_SCRIPT} ${REPO_ROOT}/${sql_rel}"
  echo "      Defer:    uv run ${GENERATE_SCRIPT} --defer ${REPO_ROOT}/${sql_rel}"
  echo "                Options: --defer-until=next | --defer-for=<N>"
  echo ""
done

exit 1
