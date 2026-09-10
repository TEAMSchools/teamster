# Tableau MCP gotchas

Injected on the first `mcp__tableau__*` call. Everything here is about the MCP
server's own tools. Editing or publishing a workbook is a different job with its
own gate: **invoke the `tableau-workbook-xml` skill before writing any
`tableauserverclient` code**, and do not attempt a publish from memory. That
skill carries the checkers, the repack script, the non-production review-copy
publish, and the two typed confirmations a production publish requires.

Marks: **Verified** = observed against this server on the date given.
**Inferred** = reported by one project (#5230) without a controlled probe.

- **The MCP is read-only.** Verified 2026-09-09: all 19 tools in this deployment
  are `get-`, `list-`, `query-`, `search-` or `generate-pulse-*`. There is no
  publish, no workbook edit, no group mutation. Do not look for one. Workbook
  content can still be edited and republished from this Codespace with
  `tableauserverclient`; that is the skill's job, not the MCP's.
- **No tool returns calculated-field text.** Inferred (#5230). `get-workbook`
  and `list-workbooks` return workbook, view and datasource metadata, never the
  formula, and there is no Metadata API GraphQL passthrough. Row-level-security
  calculations cannot be audited from the MCP: checking which workbooks carry a
  branch, or searching for `USERNAME()` against a literal, happens outside it,
  by downloading the workbook through the skill.
- **Both metadata paths fail on an embedded extract.** Verified 2026-09-04
  against one embedded-extract luid; do not re-test that case:

  | Tool                      | Result                                        |
  | ------------------------- | --------------------------------------------- |
  | `get-datasource-metadata` | HTTP 500                                      |
  | `query-datasource`        | `Unable to retrieve data source information.` |

  `get-datasource-metadata` reaches the Metadata API only for published
  datasources, and even then returns field names, types and roles, not formulas.
  `query-datasource`'s inline `calculation` parameter is not a way round it.

- **`get-workbook` gives the workbook-to-table mapping.** Inferred (#5230). Its
  `upstreamDatasources` array returns each datasource's name, luid and type, and
  it worked for embedded extracts. That maps a workbook to its dbt model in one
  call, and it surfaced a second, stale datasource left attached by an
  incomplete repoint that is otherwise invisible without Desktop. Use it before
  asking the user to read the Data pane.
- **The MCP cannot test a persona.** `scripts/tableau-mcp-launch.sh`
  authenticates with one fixed personal access token from 1Password, with no
  per-user credential, so `get-view-data` and `query-datasource` return that
  identity's rows for every user of the MCP. A render or query through it cannot
  distinguish an applied row-level-security gate from a broken one. The probe
  that can is in the skill's `references/build-workflow.md`.
- **`search-content` ranks, `list-*` enumerates.** Inferred (#5230).
  `search-content` returns one ranked page of top matches, not every match. When
  completeness matters, use `list-workbooks` with a filter.
- **`401002: Invalid authentication credentials` on a Tableau session.** The
  cause is not established. #5230 saw it three times during scripted publishes
  and read it as one-active-session-per-token; this repo's Dagster resource
  (`src/teamster/libraries/tableau/CLAUDE.md`) attributes the same code to a
  sign-in race and recovers with a fresh sign-in. Both agree on the recovery.
  Two facts worth knowing before a scripted publish runs alongside MCP calls:
  the MCP holds a session on its token for the life of the server process, and
  the skill's publish template signs in through a `with` block that releases its
  session on exit. Whether the two use the same token is unverified here; if
  they do, an MCP call mid-publish is a plausible trigger.
