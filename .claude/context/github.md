# GitHub MCP gotchas

- **Neither the read nor the write tools mangle body text. Escaped characters in
  a read result are transport encoding, not corruption.** `pull_request_read` /
  `issue_read` render `<`, `>` and `&` as the JSON escapes `\u003c`, `\u003e`
  and `\u0026`, and a double quote as `\"`. Those decode losslessly, so a body
  that looks corrupted in a read result is NOT corrupted: do not rewrite one to
  "fix" it, and do not read an escaped token as a dropped one.
- Verified 2026-09-16 on PR #5350 (comment 5702796794): `<role>`, `<col>`,
  `<notatag>`, `<zz>`, `<br>`, `<strong>`, `<=`, `>=`, `&`, `&&` and both quote
  styles, each in prose, an inline code span and a fenced block, posted with
  `gh api` and read back with `issue_read` `method=get_comments`. Every token
  came back at identical count and decoded to the raw `--jq .body` bytes; zero
  HTML entities (`&amp;`, `&#34;`, `&#39;`, `&lt;`, `&gt;`) appeared anywhere.
  Nothing is stripped and nothing is entity-encoded. The write side was verified
  separately 2026-09-02 at PR #5105, comment 5515033123; `&` and `"` are safe in
  titles and code spans.
- Read the TRUE stored body with raw
  `gh api repos/<owner>/<repo>/pulls/<n> --jq .body` (a GET — works via Bash,
  whereas `gh pr view` is denied) when you need exact bytes to diff, since it
  skips the JSON escaping. Edit a body with
  `gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>`, sourcing the
  text from a raw GET or your own draft; `-F body=@<file>` also avoids
  shell-quoting trouble on large markdown.
- **Never hard-wrap body text.** GitHub renders every single newline in a PR
  body, issue body, or comment as a line break, so 80-column prose displays as a
  ragged narrow column (verified: PR #4933's body renders 69 forced breaks
  mid-sentence). Write one line per paragraph and let it reflow. The repo's
  prettier `proseWrap: always` governs `.md` files in the checkout only —
  nothing formats a GitHub body, so wrapping there is never automatic.
- `mcp__github__pull_request_review_write` `method=create` requires the FULL
  40-char `commitID` — an abbreviated SHA fails with "Could not coerce value ...
  to GitObjectID".
- `mcp__github__search_issues` returns full issue **bodies** — a broad query
  (bare model/column name) overflows the context budget and dumps to a file.
  Narrow with `in:title`, a label, or `state:open`.
- Pass `minimal_output: true` on every `mcp__github__*` read unless you need a
  field it drops.

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
- Editing a PR **body** —
  `gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>` takes the
  text from a file, which beats passing a long markdown body inline.
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
