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

# Path-only fields for infrastructure-path rules (excludes content/new_string/old_string)
path_only=$(jq -r '
  [.tool_input.file_path, .tool_input.command, .tool_input.path, .tool_input.pattern] | map(select(. != null)) | join(" ")
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

# 1. Sensitive file/directory patterns (case-insensitive)
if echo "${no_content}" | grep -qiE '\.env[.a-z]*|(^|[ /])(\.ssh|\.kube|\.pem|\.key|\.cer|secrets\.json|credentials\.json|secret-volume)([ /]|$)|(^|[ /])(\.?/)?env(/|[ ]|$)|\.devcontainer/tpl/'; then
  deny
fi

# 1b. File-extension patterns scoped to no_content (all leaves except Write/Edit
#     body) — catches cert/key files under MCP keys (uri, localPath, source, ...)
#     while still exempting Python attribute access (e.g. asset.key) in written
#     code/doc content.
if echo "${no_content}" | grep -qiE '\*?\.(cer|key|pem)([ /]|$)'; then
  deny
fi

# 1c. High-risk proc/dev paths — kept in all-tools scope (sandbox is ineffective
#     in Codespaces; hooks are the sole enforcement layer)
if echo "${no_content}" | grep -qE '/proc/[^[:space:]]*/environ|/proc/[^[:space:]]*/cmdline|/dev/fd/'; then
  deny
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

  # 4. 1Password CLI escalation — prevent using a leaked token to access vault
  if echo "${sanitized}" | grep -qE '\bop\b.*\b(vault|item|read|run|document|inject)\b'; then
    deny
  fi

  # 5. Encoding-based bypass detection (base64/hex piped, chained, or process-substituted)
  if echo "${normalized}" | grep -qiE 'base64[[:space:]]+(-d|--decode).*(\||[;&]+).*(bash|sh|source)|\bxxd\b.*(\||[;&]+).*(bash|sh|source)|\bprintf[[:space:]]+.*\\x.*\|.*(bash|sh|source)'; then
    deny
  fi

  # 5a. Reverse order: bash/sh consuming process substitution or here-string with decode
  if echo "${sanitized}" | grep -qiE '\b(bash|sh)\b.*<\(.*base64[[:space:]]+(-d|--decode)|\b(bash|sh)\b.*<<<.*base64[[:space:]]+(-d|--decode)|\b(bash|sh)\b.*<\(.*\bxxd\b'; then
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
  safe+='|PS[0-4]|IFS|PPID|UID|EUID|RANDOM|SECONDS|LINENO'
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
  if echo "${stripped}" | grep -qE '\$\{?[A-Z_][A-Z0-9_]+\}?'; then
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
    # Newlines flattened to spaces via parameter expansion (no tr subshell)
    echo "${1//$'\n'/ }" | grep -qiE '\bINSERT[[:space:]]|\bUPDATE[[:space:]]+.*[[:space:]]+SET\b|\bDELETE[[:space:]]+FROM\b|\bMERGE[[:space:]]+INTO\b|\bEXPORT[[:space:]]+DATA\b|\bLOAD[[:space:]]+DATA\b|\bTRUNCATE[[:space:]]|\bCREATE[[:space:]]|\bDROP[[:space:]]|\bALTER[[:space:]]|\bGRANT[[:space:]]|\bREVOKE[[:space:]]|\bCALL[[:space:]]'
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
