#!/bin/bash
# Blocks access to sensitive files and paths.
# Reads tool input as JSON from stdin (provided by Claude Code PreToolUse hooks).
# Scans ALL tool_input string fields to cover arbitrary tool schemas (MCP, etc.).
#
# Limitations: command-string checks are best-effort — bash is Turing-complete
# so obfuscated commands (base64, variable indirection, eval, etc.) cannot be
# caught by regex. Real security boundaries are file permissions (umask 077,
# chmod 700) and 1Password authentication.

deny() {
  echo '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "❌ Cannot access sensitive path"}}'
  exit 0
}

input=$(cat)

# Fail closed: a hook that is the sole enforcement layer must DENY anything it
# cannot understand rather than silently allow. Empty stdin, unparseable JSON,
# a non-object frame, or a missing/empty tool_name all fall through to deny.
if [[ -z ${input} ]] || ! jq -e 'type == "object"' >/dev/null 2>&1 <<<"${input}"; then
  deny
fi
tool_name=$(jq -r '.tool_name // ""' <<<"${input}")
# Normalize once: lowercase + strip all whitespace so a re-cased or padded
# tool_name cannot skip the case-sensitive gates below (pure parameter
# expansion — no subshell/pipeline).
tool_name=${tool_name,,}
tool_name=${tool_name//[[:space:]]/}
if [[ -z ${tool_name} ]]; then
  deny
fi

# Normalize path strings: collapse //, /./, resolve ../
_normalize() { sed -E ':a; s#//+#/#g; s#/\./#/#g; s#/[^/]+/\.\./#/#g; ta'; }

# Collect ALL string values from tool_input (covers MCP, NotebookEdit, any tool schema)
if [[ ${tool_name} == "agent" ]]; then
  path=$(jq -r '
    [.tool_input | to_entries[] | select(.key != "description") | .value | .. | strings] | join(" ")
  ' <<<"${input}")
else
  path=$(jq -r '
    [.tool_input | to_entries[] | .value | .. | strings] | join(" ")
  ' <<<"${input}")
fi

normalized=$(echo "${path}" | _normalize)

# Resolve symlinks for EVERY path-bearing string leaf that exists on disk (not
# just file_path) so a symlink to a sensitive target is caught regardless of
# which key holds it — path (Grep), pattern (Glob), MCP uri/localPath/source,
# nested objects, etc. Body content (content/new_string/old_string) is excluded:
# that is doc/code text, not a path the tool will open.
resolved=""
_cands=$(jq -r '
  [.tool_input | to_entries[] | select(.key | test("^(content|new_string|old_string)$") | not) | .value | .. | strings] | .[]
' <<<"${input}")
while IFS= read -r _cand; do
  [[ -n ${_cand} && -e ${_cand} ]] || continue
  _r=$(readlink -f "${_cand}" 2>/dev/null) || continue
  [[ -n ${_r} ]] && resolved+=" ${_r}"
done <<<"${_cands}"
[[ -n ${resolved} ]] && normalized="${normalized} ${resolved}"

# Strip quotes and backslashes for keyword matching (defeats quote-splitting bypass)
sanitized=${normalized//[\"\'\\]/}

# Path-bearing fields for infrastructure-path rules: named path keys collected
# recursively (any nesting depth) so MCP path keys (uri/url/localPath/source) are
# covered, while free-text fields like a SQL `sql` parameter are NOT — a dotted
# attribute such as record.key must not be mistaken for a cert/key file (Rule 1b).
path_only=$(jq -r '
  [.tool_input | .. | objects | (.file_path?, .command?, .path?, .pattern?, .uri?, .url?, .localPath?, .source?) | strings] | join(" ")
' <<<"${input}")
path_only=$(echo "${path_only}" | _normalize)
[[ -n ${resolved} ]] && path_only="${path_only} ${resolved}"
path_only=${path_only//[\"\'\\]/}

# All fields except Write/Edit body content (content, new_string, old_string)
# Used by Rules 1/1c: catches MCP sql/nested fields but skips doc content
if [[ ${tool_name} == "write" || ${tool_name} == "edit" ]]; then
  no_content=$(jq -r '
    [.tool_input | to_entries[] | select(.key | test("^(content|new_string|old_string)$") | not) | .value | .. | strings] | join(" ")
  ' <<<"${input}")
  no_content=$(echo "${no_content}" | _normalize)
  [[ -n ${resolved} ]] && no_content="${no_content} ${resolved}"
  no_content=${no_content//[\"\'\\]/}
else
  no_content=${sanitized}
fi

# ═══════════════════════════════════════════════════════════════════
# Section 1: All tools — path-based protection
# ═══════════════════════════════════════════════════════════════════

# 1. Sensitive file/directory patterns (case-insensitive). Credential files added
#    (#23): gcloud ADC application_default_credentials.json, git-credentials,
#    netrc, and the 1Password CLI config dir (.config/op). Dotenv templates
#    (.env.example/.sample/.template/.dist) are placeholder files, not secrets —
#    stripped from the dotenv branch only (#32); every other pattern still scans
#    the full corpus.
_env_scan=$(echo "${no_content}" | sed -E 's/\.env\.(example|sample|template|dist)([^a-zA-Z]|$)/\2/g')
if echo "${_env_scan}" | grep -qiE '\.env[.a-z]*' ||
  echo "${no_content}" | grep -qiE '(^|[ /])(\.ssh|\.kube|\.pem|\.key|\.cer|secrets\.json|credentials\.json|application_default_credentials\.json|\.git-credentials|\.netrc|secret-volume)([ /]|$)|(^|[ /])(\.?/)?env(/|[ ]|$)|\.config/op([ /]|$)|\.devcontainer/tpl/'; then
  deny
fi

# 1b. File-extension patterns scoped to path_only (named path keys incl. MCP
#     uri/url/localPath/source, recursive) — catches cert/key files under those
#     keys without scanning free-text fields like a SQL `sql` parameter, where a
#     dot-attribute such as record.key would otherwise false-positive.
if echo "${path_only}" | grep -qiE '\*?\.(cer|key|pem)([ /]|$)'; then
  deny
fi

# 1c. High-risk proc/dev paths — kept in all-tools scope (sandbox is ineffective
#     in Codespaces; hooks are the sole enforcement layer)
if echo "${no_content}" | grep -qE '/proc/[^[:space:]]*/environ|/proc/[^[:space:]]*/cmdline|/dev/fd/'; then
  deny
fi

# ═══════════════════════════════════════════════════════════════════
# Section 1d: Filesystem MCP — protected-config write guard
# ═══════════════════════════════════════════════════════════════════
# The filesystem MCP's mutating tools (write_file/edit_file/move_file/
# create_directory) are not Bash, so Rule 2 (Bash-only) never fires for them.
# Without this they could rewrite settings.json, the hook scripts, the
# .devcontainer/scripts, .git/hooks, or .trunk config — i.e. edit the sole
# enforcement layer. Scoped to the mutating tools only (read-only filesystem
# tools may read these paths). Path set = path + source + destination; body
# fields (content/edits) are excluded so a file body that mentions one of
# these paths does not false-positive. Pattern mirrors Rule 2.
if [[ ${tool_name} =~ ^mcp__filesystem__(write_file|edit_file|move_file|create_directory)$ ]]; then
  fs_target=$(jq -r '[.tool_input | (.path?, .source?, .destination?) | strings] | join(" ")' <<<"${input}")
  fs_target=$(echo "${fs_target}" | _normalize)
  fs_target=${fs_target//[\"\'\\]/}
  if echo "${fs_target}" | grep -qE '\.claude/(settings\.json|settings\.local\.json|hooks/[^[:space:]]*\.sh|shell-snapshots/)|\.devcontainer/scripts/|\.git/hooks/|\.trunk/(trunk\.yaml|config/)'; then
    deny
  fi
fi

# ═══════════════════════════════════════════════════════════════════
# Section 2: Bash only — command-pattern protection
# ═══════════════════════════════════════════════════════════════════
if [[ ${tool_name} == "bash" ]]; then

  # 2. Protected paths — Edit/Write handled by permissions.deny; Bash blocked here
  if echo "${path_only}" | grep -qE '\.claude/(settings\.json|settings\.local\.json|hooks/[^[:space:]]*\.sh|shell-snapshots/)|\.devcontainer/scripts/|\.git/hooks/|\.trunk/(trunk\.yaml|config/)'; then
    deny
  fi

  # 3. Environment variable / process memory leakage
  # declare: -x already listed; also block any -flag cluster containing p
  # (-p/-px/-xp dump variable definitions, equivalent to printenv/set)
  if echo "${sanitized}" | grep -qiE '\bprintenv\b|\bdeclare -x\b|\bdeclare[[:space:]]+-[a-zA-Z]*p[a-zA-Z]*\b|\bexport -p\b|\bcompgen\b|\btypeset([[:space:]]+-x|\b)|/proc/[^[:space:]]*/environ|/proc/[^[:space:]]*/cmdline|OP_SERVICE_ACCOUNT_TOKEN|OP_CONNECT_TOKEN|OP_SERVICE|ACCOUNT_TOKEN|\benviron\b|\bgetenv\b'; then
    deny
  fi

  # 3d. Catch bare `declare` (dumps all vars), but not `declare VAR=val` or `declare -flags`
  # trunk-ignore(shellcheck/SC2016): regex contains literal $\( for matching $(declare), not a command substitution
  if echo "${sanitized}" | grep -qE '(^|[;&|(`][[:space:]]*)declare([[:space:]]*$|[[:space:]]*[|>&;)`])|\$\(declare([[:space:]]|$|\))'; then
    deny
  fi

  # 3b. Catch `set` as a standalone command (dumps all vars), but not `set -flags`
  # trunk-ignore(shellcheck/SC2016): regex contains literal $\( for matching $(set), not a command substitution
  if echo "${sanitized}" | grep -qE '(^|[;&|(`][[:space:]]*)set([[:space:]]*$|[[:space:]]*[|>&;)`])|\$\(set([[:space:]]|$|\))'; then
    deny
  fi

  # 3c. Standalone `env` shell command — scoped to path/command only (not file content)
  if echo "${path_only}" | grep -qiE '\benv\b'; then
    deny
  fi

  # 4. 1Password CLI escalation — prevent using a leaked token to access the vault
  #    or mint new credentials. Verbs extended (#14): signin/account/user/
  #    service-account/connect and plural items.
  if echo "${sanitized}" | grep -qE '\bop\b.*\b(vault|item|items|read|run|document|inject|signin|account|user|service-account|connect)\b'; then
    deny
  fi

  # 5. Encoding-based bypass: a base64/hex decode feeding a shell interpreter.
  #    Newlines flattened to ; so a decode and the consuming interpreter on
  #    separate lines are caught (a pipe/`;` split across a newline previously
  #    evaded the line-oriented grep). Consumers now include eval (#15).
  _flat=${normalized//$'\n'/;}
  if echo "${_flat}" | grep -qiE '(base64[[:space:]]+(-d|--decode)|\bxxd\b|\bprintf[[:space:]]+[^|;&]*\\x).*(\||[;&]+).*(bash|sh|source|eval)'; then
    deny
  fi

  # 5a. Reverse order: a shell interpreter (bash/sh/source/eval, or the `.` dot
  #     builtin) consuming a process substitution <(...), here-string <<<, or
  #     command substitution $(...) that runs a decode (#15). Scans `sanitized`
  #     (quote/backslash-stripped) to keep the quote-split defense; these forms
  #     are same-line, so the newline-flattening (Rule 5) is not needed here.
  if echo "${sanitized}" | grep -qiE '\b(bash|sh|source|eval)\b.*(<\(|<<<|\$\().*(base64[[:space:]]+(-d|--decode)|\bxxd\b)|(^|[;&|][[:space:]]*)\.[[:space:]]+(<\(|\$\().*(base64[[:space:]]+(-d|--decode)|\bxxd\b)'; then
    deny
  fi

  # 5b. Python runtime string construction (exec/eval with chr/join/bytes/base64/codecs)
  if echo "${sanitized}" | grep -qiE '\b(exec|eval)[[:space:]]*\(.*\bchr[[:space:]]*\(|\b(exec|eval)[[:space:]]*\(.*\.join[[:space:]]*\(|\b(exec|eval)[[:space:]]*\(.*\bbytes[[:space:]]*\(|\b(exec|eval)[[:space:]]*\(.*base64\.b64decode|\b(exec|eval)[[:space:]]*\(.*codecs\.decode|\b(exec|eval)[[:space:]]*\(.*\.fromhex'; then
    deny
  fi

  # 5c. Python __import__ with sensitive modules (bypasses exec() requirement)
  if echo "${sanitized}" | grep -qiE '\b__import__[[:space:]]*\(.*\b(os|subprocess|shutil|pty|ctypes|socket|http|urllib|multiprocessing|signal)\b'; then
    deny
  fi

  # 5d. Python importlib bypass (avoids __import__ check)
  if echo "${sanitized}" | grep -qiE '\bimportlib\b.*\b(os|subprocess|shutil|pty|ctypes|socket|http|urllib|multiprocessing|signal)\b'; then
    deny
  fi

  # 7. Shell variable expansion — block $UPPER_CASE broadly, allowlist known-safe vars
  # Block ${!prefix*} (indirect expansion that enumerates variable names)
  if echo "${sanitized}" | grep -qE '\$\{![^}]*\}'; then
    deny
  fi
  # Strip allowed variable references, then deny if any $VAR remain
  safe='HOME|PATH|PWD|OLDPWD|USER|SHELL|TERM|LANG|LANGUAGE'
  # LC_* enumerated explicitly (not LC_[A-Z]+) so a secret-bearing name like
  # $LC_SECRET / $LC_CREDENTIALS is not swallowed by a wildcard (Finding 1).
  safe+='|LC_ALL|LC_CTYPE|LC_NUMERIC|LC_TIME|LC_COLLATE|LC_MONETARY|LC_MESSAGES|LC_PAPER|LC_NAME|LC_ADDRESS|LC_TELEPHONE|LC_MEASUREMENT|LC_IDENTIFICATION'
  safe+='|HOSTNAME|SHLVL|LOGNAME|TZ|TMPDIR|EDITOR|VISUAL|PAGER|DISPLAY'
  # XDG_* enumerated explicitly (not XDG_[A-Z_]+) so $XDG_SESSION_SECRET et al.
  # are not swallowed by a wildcard (Finding 1).
  safe+='|XDG_CONFIG_HOME|XDG_DATA_HOME|XDG_CACHE_HOME|XDG_STATE_HOME|XDG_RUNTIME_DIR|XDG_CONFIG_DIRS|XDG_DATA_DIRS|XDG_SESSION_ID|XDG_SESSION_TYPE|XDG_SESSION_CLASS'
  safe+='|PS[0-4]|IFS|PPID|UID|EUID|RANDOM|SECONDS|LINENO|_'
  safe+='|OSTYPE|MACHTYPE|HOSTTYPE|BASH_SOURCE|BASH_LINENO|BASH_REMATCH|BASHPID|BASH_VERSION|HISTSIZE|HISTCONTROL'
  # COMP_* enumerated explicitly (not COMP[A-Z_]*) so $COMP_TOKEN / $COMP_API_SECRET
  # are not swallowed by a wildcard (Finding 1).
  safe+='|COMPREPLY|COMP_WORDS|COMP_CWORD|COMP_LINE|COMP_POINT|COMP_KEY|COMP_TYPE|COMP_WORDBREAKS'
  safe+='|SHELLOPTS|BASHOPTS|DIRSTACK|PIPESTATUS|FUNCNAME|REPLY'
  safe+='|DAGSTER_HOME|DBT_PROFILES_DIR|DBT_PROJECT_DIR|DBT_CLOUD_ENVIRONMENT_TYPE|DBT_SEND_ANONYMOUS_USAGE_STATS'
  safe+='|GOOGLE_CLOUD_PROJECT|PYTHONDONTWRITEBYTECODE|PYTHONPATH|PYTHONHASHSEED'
  safe+='|TRUNK_TELEMETRY|UV_LINK_MODE|UV_RESOLUTION|UV_CACHE_DIR|VIRTUAL_ENV|NVM_DIR'
  safe+='|JAVA_HOME|GOPATH|GOROOT|CARGO_HOME|RUSTUP_HOME|NODE_PATH'
  safe+='|CI|GITHUB_WORKSPACE|GITHUB_REPOSITORY|GITHUB_REF|GITHUB_SHA|GITHUB_ACTIONS|GITHUB_ACTOR|GITHUB_OUTPUT|GITHUB_EVENT_NAME'
  safe+='|CODESPACES|CODESPACE_NAME|REMOTE_CONTAINERS'
  # Anchor the strip with a captured-and-re-emitted trailing non-identifier
  # boundary so a safe PREFIX cannot consume a longer secret var name
  # (e.g. $CI must strip, but $CI_SECRET / $USER_PASSWORD must not).
  stripped=$(echo "${sanitized}" | sed -E "s/\\$\\{?(${safe})\\}?([^A-Z0-9_]|\$)/\\2/g")
  # Match single-char uppercase too ($X), not just multi-char ($AWS_SECRET) — the
  # `*` quantifier instead of `+` (#27). Lowercase vars ($i / $file) stay ignored:
  # env-secret names are uppercase by convention and matching loop vars would
  # false-positive broadly. ($_ is on the safe list, so the `*` does not snag it.)
  if echo "${stripped}" | grep -qE '\$\{?[A-Z_][A-Z0-9_]*\}?'; then
    deny
  fi

fi

# ═══════════════════════════════════════════════════════════════════
# Section 3: BigQuery MCP — read-only enforcement
# ═══════════════════════════════════════════════════════════════════

# 8. BigQuery MCP read-only enforcement, gated on the mcp__bigquery__* prefix so
#    every SQL-capable tool is covered (execute_sql, forecast,
#    analyze_contribution, and any future tool), not just two named ones.
if [[ ${tool_name} == mcp__bigquery__* ]]; then
  # Write-statement denylist. Newlines flattened so UPDATE..SET split across
  # lines is caught (#12); INSERT no longer requires INTO (#11); TRUNCATE and
  # LOAD DATA added (#10). Verbs require a trailing space so column names like
  # delete_flag / merge_count do not false-positive.
  _bq_has_write() {
    # Newlines flattened to spaces via parameter expansion (no tr subshell).
    # Match each write verb on a word boundary (\b…\b) instead of requiring a
    # secondary keyword or a trailing space: GoogleSQL makes DELETE's FROM and
    # MERGE's INTO optional and lets /* */ comments replace the whitespace, so
    # `DELETE ds.t`, `MERGE ds.t …` and `DROP/**/TABLE t` must all still match.
    # \b…\b keeps read-query identifiers like delete_flag / merge_count /
    # create_ts from false-positiving (no boundary before the trailing _).
    echo "${1//$'\n'/ }" | grep -qiE '\bINSERT\b|\bUPDATE\b.*\bSET\b|\bDELETE\b|\bMERGE\b|\bEXPORT\b.*\bDATA\b|\bLOAD\b.*\bDATA\b|\bTRUNCATE\b|\bCREATE\b|\bDROP\b|\bALTER\b|\bGRANT\b|\bREVOKE\b|\bCALL\b'
  }
  case ${tool_name} in
  mcp__bigquery__execute_sql)
    # Whole arg is SQL: require a read statement at the start (allowlist) ...
    if ! echo "${sanitized}" | grep -qiE '^[[:space:]]*(SELECT|SHOW|DESCRIBE|WITH)\b'; then
      deny
    fi
    # ... and reject any embedded write statement.
    if _bq_has_write "${sanitized}"; then
      deny
    fi
    ;;
  mcp__bigquery__forecast | mcp__bigquery__analyze_contribution)
    # history_data / input_data accept a bare table-id OR a query, so requiring
    # a read prefix would wrongly deny a legitimate table-id (#28); reject only
    # embedded write statements.
    if _bq_has_write "${sanitized}"; then
      deny
    fi
    ;;
  mcp__bigquery__ask_data_insights)
    # Natural-language question + structured table refs; no raw-SQL field for a
    # caller to inject (server performs read-only NL->SQL). Intentionally not
    # SQL-gated — a denylist on prose would block words like "drop"/"deleted".
    : # no-op
    ;;
  *)
    # Unknown bigquery tool: conservatively reject obvious write statements
    # anywhere in its arguments.
    if _bq_has_write "${sanitized}"; then
      deny
    fi
    ;;
  esac
fi

# ═══════════════════════════════════════════════════════════════════
# Section 4: Outbound egress — secret-VALUE scan
# ═══════════════════════════════════════════════════════════════════
# Section 1 matches sensitive PATHS; this catches secret VALUES being SENT to a
# write-capable MCP tool (GitHub/Drive/Asana/Slack/... writes) or in a WebFetch
# URL, which would otherwise exfiltrate unscanned. Gated by a write-verb name
# pattern so read-only MCP tools (bigquery/dagster/dbt get_/list_/search_) are
# untouched. Scans the raw value corpus (${path}, before quote-strip/normalize)
# so op:// and "service_account" JSON survive. Regex mirrors check-output.sh —
# update BOTH if adding a token type.
if [[ ${tool_name} == webfetch ]] ||
  [[ ${tool_name} =~ ^mcp__.*(create|update|write|add|comment|upload|send|post|put|delete|append|insert|merge|push|reply) ]]; then
  if echo "${path}" | grep -qiE 'op://|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|PRIVATE KEY-----|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]+|goog_[a-zA-Z0-9_-]+|eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}|ops_eyJ[A-Za-z0-9_-]{50,}|AKIA[0-9A-Z]{16}|(postgres(ql)?|mysql|mongodb(\+srv)?)://[^[:space:]]+:[^[:space:]]+@|"type"[[:space:]]*:[[:space:]]*"service_account"|gh[pusor]_[A-Za-z0-9_]{36,}|github_pat_[A-Za-z0-9_]{22,}|xox[baprs]-[0-9A-Za-z-]{10,}|\b(sk|rk)_(live|test)_[0-9A-Za-z]{16,}|hooks\.slack\.com/services/[A-Za-z0-9/]+|aws_secret_access_key["[:space:]:=]+[A-Za-z0-9/+]{40}'; then
    deny
  fi
fi
