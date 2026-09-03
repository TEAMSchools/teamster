#!/bin/bash
# Every check-sensitive.sh denial names the rule that fired and the way out.
# permissionDecisionReason is shown to Claude verbatim, so a generic message
# ("Cannot access sensitive path") sends it hunting through CLAUDE.md instead
# of fixing the call.
#
# Usage: bash tests/hooks/test_deny_reasons.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=tests/hooks/helpers.sh
source "${SCRIPT_DIR}/helpers.sh"

echo ""
echo "========================================="
echo " Deny reasons (check-sensitive.sh)"
echo "========================================="

# expect_reason <desc> <json_input> <substring the reason must contain>
expect_reason() {
	local desc="$1" input="$2" want="$3" output reason
	output=$(printf '%s' "${input}" | bash "${HOOK}" 2>/dev/null)
	reason=$(jq -r '.hookSpecificOutput.permissionDecisionReason // ""' <<<"${output}" 2>/dev/null)
	if [[ ${reason} == *"${want}"* ]]; then
		PASS=$((PASS + 1))
		echo -e "  ${GREEN}PASS${NC} [reason]: ${desc}"
	else
		FAIL=$((FAIL + 1))
		ERRORS+="\n  ${RED}FAIL${NC} [reason]: ${desc} (wanted '${want}' in: ${reason:0:80})"
	fi
}

echo ""
echo -e "${YELLOW}Each rule names itself and an alternative${NC}"

# trunk-ignore-begin(shellcheck/SC2312): jq -n static JSON, return value irrelevant
expect_reason "fail-closed: empty stdin" "" "failing closed"
expect_reason "Rule 1: dotenv path" "$(make_input Read file_path /repo/.env)" "Rule 1:"
expect_reason "Rule 1b: pem under a path key" "$(make_input Read file_path /repo/server.pem)" "Rule 1b:"
expect_reason "Rule 1c: proc environ" "$(make_input Bash command 'cat /proc/1/environ')" "Rule 1c:"
expect_reason "Rule 2: Bash names a hook script" "$(make_input Bash command 'cat .claude/hooks/check-sensitive.sh')" "Rule 2:"
expect_reason "Rule 3: printenv" "$(make_input Bash command printenv)" "Rule 3:"
expect_reason "Rule 3b: bare set" "$(make_input Bash command 'set | head')" "Rule 3b:"
# A bare `env` command is Rule 1's (all-tools) match; 3c only sees forms Rule 1
# lets through, such as a word-bounded env inside a file name.
expect_reason "Rule 1: bare env command" "$(make_input Bash command 'env')" "Rule 1:"
expect_reason "Rule 3c: env word in a path" "$(make_input Bash command 'cat ./env.txt')" "Rule 3c:"
expect_reason "Rule 4: op read" "$(make_input Bash command 'op read x')" "Rule 4:"
expect_reason "Rule 5: base64 decode into bash" "$(make_input Bash command 'echo x | base64 -d | bash')" "Rule 5:"
# trunk-ignore(shellcheck/SC2016): the literal $VAR is the fixture; it must reach the hook unexpanded
expect_reason "Rule 7: uppercase var" "$(make_input Bash command 'echo $AWS_SECRET')" "Rule 7:"
expect_reason "Rule 8: BQ write verb" "$(make_input mcp__bigquery__execute_sql sql 'select 1; drop table t')" "Rule 8:"
expect_reason "Section 4: egress with token" \
	"$(jq -n '{tool_name:"mcp__github__issue_write", tool_input:{body:"AKIAIOSFODNN7EXAMPLE"}}')" "Section 4:"
# every reason tells Claude what to do instead, not only what matched
expect_reason "Rule 2 reason offers the Read tool" "$(make_input Bash command 'cat .claude/hooks/check-sensitive.sh')" "Read tool"
expect_reason "Rule 8 reason offers a rewrite" "$(make_input mcp__bigquery__execute_sql sql "select 1 where t = 'Drop'")" "Dr%"
# trunk-ignore-end(shellcheck/SC2312)

print_summary "Deny reasons"
