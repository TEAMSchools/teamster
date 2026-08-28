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
