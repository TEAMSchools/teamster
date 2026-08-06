# Asana MCP conventions

The "TEAMster" project is the canonical tracker for engineering work. Tasks are
named `#NNNN | title` (NNNN = GitHub issue or PR number) — parse to map Asana ↔
GitHub. The Type custom field tags each task `Issue`, `Pull Request`, or
`Ad Hoc`. PR tasks are subtasks of their issue task (parent resolved via
`Closes/Fixes/Refs #N` in the PR body).

- `create_tasks` `html_notes` only accepts this tag allowlist: `body`, `strong`,
  `em`, `u`, `s`, `code`, `ol`, `ul`, `li`, `a`, `blockquote`, `pre`, `h1`,
  `h2`, `hr/`, `img`. `<p>` and `<br>` are rejected with "XML is invalid" —
  structure content with headings + lists, no paragraph tags.
- `create_tasks.custom_fields` is a JSON-encoded string, not a nested object:
  `"{\"<field_gid>\":\"<option_gid>\"}"`.
- `search_tasks` rejects this workspace's custom-field GIDs
  (`Not a valid search parameter`). Paginate with `get_tasks` and filter
  client-side.
- `get_tasks.completed_since` requires a full ISO 8601 datetime. Pass a
  far-future date (`"2030-01-01T00:00:00Z"`) to list only incomplete tasks.
- `update_tasks` supports `parent` for re-parenting; `null` flattens.
- Pagination cursors return as `next_page.offset` — pass to `get_tasks.offset`
  until null.
- **VS Code extension swallows `create_task_preview*` widgets.** Use
  `create_tasks` directly.
- Resolve GitHub-login → Asana email via
  `search_objects(resource_type: "user")`. Workspace spans three email domains
  (`teamschools.org`, `kippteamandfamily.org`, `kippnj.org`).
