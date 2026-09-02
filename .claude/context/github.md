# GitHub MCP gotchas

- **GitHub MCP write tools HTML-sanitize body text**: `issue_write`,
  `add_issue_comment`, `update_pull_request`, and `create_pull_request` strip
  `<...>` tokens (e.g. `<role>`, `<col>`) — **even inside inline backticks**.
  Use `{placeholder}` braces or a fenced code block (fenced blocks preserve `<`,
  `<=`, `>=`). Read the stored body back and verify after writing. They also
  entity-encode `&`→`&amp;` and `"`→`&#34;` (not strip) — harmless in rendered
  prose but rendered literally inside code spans and in titles, so avoid `&` /
  `"` in PR/issue titles and code spans (use "and" / single quotes). Corollary:
  the encoding is RE-APPLIED on every write, so round-tripping a fetched body
  back through `update_pull_request` double-encodes what is already there
  (`&amp;` → `&amp;amp;`). Edit a PR body with
  `gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>` instead.
- **The `mcp__github__*` read tools also sanitize on OUTPUT**:
  `pull_request_read` / `issue_read` strip `<...>` and encode `'`→`&#39;` in the
  body they return, so a just-written body read back through them shows phantom
  corruption even when the stored body is intact (likely why the "even inside a
  fence" stripping above reads worse than it stores). Verify the TRUE stored
  body with raw `gh api repos/<owner>/<repo>/pulls/<n> --jq .body` (a GET —
  works via Bash, whereas `gh pr view` is denied) before re-writing to "fix"
  apparent corruption.
- `mcp__github__pull_request_review_write` `method=create` requires the FULL
  40-char `commitID` — an abbreviated SHA fails with "Could not coerce value ...
  to GitObjectID".
- `mcp__github__search_issues` returns full issue **bodies** — a broad query
  (bare model/column name) overflows the context budget and dumps to a file.
  Narrow with `in:title`, a label, or `state:open`.

## `gh`-via-Bash allowlist details

The root CLAUDE.md names the allowed `gh` subcommands; the mechanics live here.

- `gh issue develop` — linked branch creation; `mcp__github__create_branch` does
  not link branches to issues.
- `gh project item-edit --id <ITEM_ID> --project-id <PROJECT_ID> --field-id <FIELD_ID> --single-select-option-id <OPTION_ID>`
  — ProjectV2 field mutations (Status / Tier / Driver / etc.) aren't exposed by
  `mcp__github__*`. To unset a field value (any type), replace the value flag
  with `--clear`. No output on success — verify via `gh api graphql` querying
  the item's `fieldValues`. `gh project item-list` JSON also omits ProjectV2
  custom fields whose names contain spaces (e.g. `PR batch`); single-word custom
  fields (`Driver`, `Tier`, `Status`) do appear. Use the same `fieldValues`
  GraphQL query to read the omitted ones.
- `gh project item-add <PROJECT_NUMBER> --owner <OWNER> --url <ISSUE_URL>` —
  adds an issue/PR to a ProjectV2 board. No `mcp__github__*` equivalent. Combine
  with `gh project item-edit` to set fields after add.
- `gh api graphql` ProjectV2 `items(first: N)` is capped at 100. Paginate with
  `pageInfo.endCursor` for boards with >100 items.
- `gh pr checks <n> --json name,bucket,state` — combined commit statuses + check
  runs for CI poll loops (Monitor); no single `mcp__github__*` tool covers both
  surfaces.
- `gh run *` — Actions run inspection/control; no MCP coverage.
- `gh workflow *` — Actions workflow inspection/dispatch; no MCP coverage.
- `gh repo edit` — repo settings; `gh repo create/view/list` have MCP
  equivalents and are not on this list.
- Editing an existing comment — `mcp__github__add_issue_comment` only creates.
  Use `gh api -X PATCH repos/<owner>/<repo>/issues/comments/<id> -f body='...'`.
  For large bodies (tables, multi-paragraph), write the body to a file and pass
  `-F body=@<file>` instead of inline `-f body='...'` (avoids shell-quoting on
  big markdown). Same `-F body=@<file>` trick applies to `create_pull_request` /
  comment creation via `gh api`.
- Editing a PR **body** — round-tripping a fetched body through
  `mcp__github__update_pull_request` double-encodes existing entities (it
  re-applies the `&`→`&amp;` encoding). Edit cleanly via
  `gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>` (raw, no
  re-encoding).
- Replying to a PR inline review comment in-thread —
  `mcp__github__add_issue_comment` posts top-level PR comments only, not thread
  replies. Use
  `gh api -X POST repos/<owner>/<repo>/pulls/<pr>/comments/<id>/replies -f body='...'`.
- `gh api repos/<owner>/<repo>/contents/<path>?ref=<sha> -H 'Accept: application/vnd.github.raw'`
  — read a third-party file at a pinned SHA (for the verify-behavior-from-source
  rule above). The `--jq .content | base64 -d` form is hook-blocked as an
  encoding bypass.
- `gh api -X POST repos/<owner>/<repo>/labels -f name=... -f color=... -f description=...`
  — no `mcp__github__*` label-create tool.
- `gh api -X POST repos/<owner>/<repo>/issues/<n>/labels -f 'labels[]=<name>'` —
  additive label add. `mcp__github__issue_write` with `labels` REPLACES the full
  set; passing one label drops the rest.
- GitHub Search API caps at 5 OR/AND/NOT operators per query (422 otherwise).
  Loop per-term via `gh api -X GET search/issues -f q='...'` for larger searches
  — without `-X GET`, `-f` turns the request into a POST and 404s.
  `search/issues` also requires `is:issue` or `is:pull-request` in `q` — 422
  "Query must include..." otherwise.
- `gh api` reporting `unexpected end of JSON input` means an empty response
  body, not a bad request — re-run with `-i` to see the HTTP status. A 500 on
  `POST /pulls` is usually a GitHub incident; check
  `githubstatus.com/api/v2/incidents/unresolved.json` before bisecting.
