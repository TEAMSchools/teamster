# Hook hardening — issue #4091 implementation plan

Tracked by [#4091](https://github.com/TEAMSchools/teamster/issues/4091). Covers
the two security hooks that are the **sole** enforcement layer in Codespaces
(the sandbox is ineffective): `.claude/hooks/check-sensitive.sh` (PreToolUse)
and `.claude/hooks/check-output.sh` (PostToolUse).

All findings were empirically reproduced against the live hooks before planning
(Phase 1 of systematic-debugging). Fixtures are secret-shaped and stay local
(`.claude/scratch/`), never on external surfaces.

## Status

| Batch | Findings                                                                                  | State                                      |
| ----- | ----------------------------------------------------------------------------------------- | ------------------------------------------ |
| 1     | Fail-closed defaults + `tool_name` normalization (#6, #8, #9, #26)                        | Done — commit `a8c8e0233`, suite 7/7 green |
| 2     | Unanchored safe-var strip (#4) + `declare` dump forms (#5)                                | In progress                                |
| 3     | BigQuery gate invert (#3, #10–#13)                                                        | Planned                                    |
| 4     | Scan-all-leaves (#1) + symlink resolution for every path (#2)                             | Planned                                    |
| 5     | MCP secret-value egress (#22) + outbound URL scan / doc reconcile (#21); folds in #6e/#20 | Planned                                    |

## Sequencing principle

Ascending blast radius. Isolated regex tweaks first; the shared path-corpus
rework as a pair; the new egress capability last. Batches 2, 3, 4 are mutually
independent; 4 internally couples #1+#2; 5 is independent but riskiest.

Every batch reuses the Batch-1 workflow: reproduce → failing tests in
`tests/hooks/` → patch a scratch copy → validate the full suite via the
`HOOK`/`OUTPUT_HOOK` env override → hand off `cp` + manual commit (hooks are
protected files) → verify against the real patched hooks.

Each batch is one commit, PR body `Refs #4091` (not `Closes`) until the final
batch closes the issue.

## Batch 2 — #4 + #5 (Section 2; near-zero risk)

### #4 — unanchored safe-var strip (`check-sensitive.sh`, Rule 7)

The allowlist strip has no right boundary, so a var whose name merely _starts_
with a safe prefix is partially stripped and its `$` lost: `$CI_SECRET` →
`_SECRET`, `$USER_PASSWORD` → `_PASSWORD`, both reaching ALLOW.

Fix: anchor the strip with a captured-and-re-emitted trailing non-identifier
boundary so a safe prefix cannot consume a longer secret var name:

```text
s/\$\{?(${safe})\}?([^A-Z0-9_]|$)/\2/g
```

`$CI` (end-of-token) still strips and allows; `$CI_SECRET` (continues with `_`,
an identifier char) fails the boundary, is not stripped, and is denied.

### #5 — `declare` dump forms (`check-sensitive.sh`, Rule 3)

Rule 3 matches only `declare -x`. The dump-equivalent forms `declare -p`, bare
`declare`, and `declare -px` fall through to ALLOW.

Fix: add a flag-cluster-containing-`p` pattern to Rule 3
(`\bdeclare[[:space:]]+-[a-zA-Z]*p[a-zA-Z]*`) and a standalone-`declare` matcher
mirroring Rule 3b's bare-`set` logic. Leave `readonly -p` / `local -p` alone —
issue verification refuted those.

### Tests (Batch 2)

Append to `tests/hooks/test_env_protection.sh`:

- Deny: `$CI_SECRET`, `$USER_PASSWORD`, `$PATH_TO_SECRET`, `declare -p`, bare
  `declare`, `declare -px`, `declare` piped/after-separator.
- Allow (controls): `$CI`, `$PATH`, `${HOME}` still pass; `declare foo=bar`,
  `declare -a arr`, `declare -r CONST=1` not denied; `declare -x` still denied.

## Batch 3 — #3 BigQuery gate invert (Section 3; self-contained)

Gate on the `mcp__bigquery__*` prefix instead of two named tools; invert the
DROP/DELETE denylist to a per-statement read-keyword **allowlist** (must begin
`SELECT|SHOW|DESCRIBE|WITH`, no separator into a non-read verb); default-deny
unknown SQL-capable `mcp__bigquery__*` tools. Closes #3, #10–#13 and is immune
to new GoogleSQL verbs.

Prerequisite: inspect the real arg schemas of `forecast`, `ask_data_insights`,
`analyze_contribution` (some take a bare table-id, not SQL) so the allowlist
does not over-block legitimate non-SQL args (#28).

## Batch 4 — #1 + #2 path-corpus rework (paired)

Both change how paths are collected, so they share the same lines.

- #1: run the `\.(cer|key|pem)` extension check against `no_content` (all string
  leaves, already excludes Write/Edit body) instead of `path_only`, so cert/key
  files under MCP keys (`uri`, nested `localPath`, `source`) are caught while
  the `asset.key`-in-code false positive stays avoided.
- #2: resolve symlinks (`readlink -f`) for every path-bearing field that exists
  on disk — Grep `path`, Glob `pattern`, MCP path keys — not just `file_path`.

Highest regression risk of the code batches (every Section-1 rule reads this
corpus). Mandatory full-suite run plus false-positive controls (`asset.key` /
`config.key` in Write content, benign relative paths) before hand-off.

## Batch 5 — #21 + #22 egress scanning (new capability; last)

- #22: add an all-tools (non-Bash) secret-**value** scan to `check-sensitive.sh`
  reusing `check-output.sh`'s secret regex, gated to write-capable MCP tools, so
  secret values cannot exfiltrate to GitHub / Drive / Asana unscanned.
- #21: the WebFetch/MCP URL + query-string scanner documented in
  `.claude/CLAUDE.md` does not exist in code — implement it (scan URL paths /
  query strings for sensitive keywords) or delete the doc claim. Decision
  required.
- Folds in #6e/#20 (`check-output.sh` reads only `.tool_response`; a payload-key
  drift re-opens passthrough) via a schema fallback.

Largest design and false-positive surface; may split #21 from #22. Open
question: duplicate the secret regex across both hooks or factor a sourced
snippet (hooks are currently standalone for speed and robustness).

## Cross-cutting

- Test blind spots #24/#25 fold into whichever batch touches the relevant rule.
- Minor findings (#27–#34) are addressed opportunistically inside the batch that
  already edits the same code region; none warrant a standalone batch.
