# GitHub MCP gotchas

- **The mangling is on the READ side, not the write side.** `pull_request_read`
  / `issue_read` strip `<...>` tokens (e.g. `<role>`, `<col>`) — in prose,
  inside inline backticks, and inside fenced blocks — and entity-encode
  `&`→`&amp;`, `"`→`&#34;`, `'`→`&#39;`, `<=`→`&lt;=`, `>=`→`&gt;=` in the body
  they return. So a body read back through them shows phantom corruption even
  when storage is clean. Verify the TRUE stored body with raw
  `gh api repos/<owner>/<repo>/pulls/<n> --jq .body` (a GET — works via Bash,
  whereas `gh pr view` is denied) before re-writing to "fix" it.
- **The write tools do NOT alter body text** — verified 2026-09-02 by posting
  bare `<role>` / `<col>` tokens plus `&`, `"` and `'` through
  `add_issue_comment` in prose, a code span, and a fence: the stored body came
  back identical (probe recorded at PR #5105, comment 5515033123). `&` and `"`
  are safe in titles and code spans. An older note here claimed `issue_write` /
  `create_pull_request` strip and encode on write; that was the read tools
  misleading the observer.
- **Never round-trip a body through the MCP read tools into a write.** The read
  encodes, so writing that body back stores the entities for real, and the next
  round-trip double-encodes them (`&amp;` → `&amp;amp;`). Edit a PR body with
  `gh api -X PATCH repos/<owner>/<repo>/pulls/<n> -F body=@<file>`, sourcing the
  text from a raw GET or from your own draft.
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
- Editing a PR **body** — round-tripping a body fetched through the MCP read
  tools and back out through `mcp__github__update_pull_request` stores the
  read's entities for real. Edit cleanly via
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
