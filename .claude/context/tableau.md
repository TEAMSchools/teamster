# Tableau MCP gotchas

**The MCP is read-only.** Every tool is a `get-`/`list-`/`query-`/`search-`.
There is no publish, no workbook edit, no group mutation — do not look for an
MCP tool that does it.

That is a limit of the MCP, not of this Codespace. Workbook content **can** be
edited and republished here with `tableauserverclient`; see _Publishing back_
below, and
[the workbook-editing guide](../../docs/guides/tableau-workbook-editing.md) for
the full recipe with worked code. Group membership and Server admin remain
user-side.

**No tool returns calculated-field formulas.** `get-workbook` and
`list-workbooks` return workbook, view, and datasource metadata — never the calc
text. There is no Metadata API GraphQL passthrough either. Practical effect:
**you cannot audit RLS `Permissions` calcs from here.** Checking which workbooks
carry a given branch, or searching for `USERNAME()` compared against a literal,
has to be done outside the MCP.

Verified 2026-09-04 against an embedded extract luid — do not re-test:

| Tool                      | Result on an embedded datasource              |
| ------------------------- | --------------------------------------------- |
| `get-datasource-metadata` | HTTP 500                                      |
| `query-datasource`        | `Unable to retrieve data source information.` |

`get-datasource-metadata` reaches the Metadata API only for **published**
datasources, and only for fields/parameters (name, dataType, description, role)
— still not formulas. Every gated workbook uses an embedded extract, so neither
tool reaches them at all. `query-datasource`'s inline `calculation` field is
therefore no back door either.

**Reading and writing calc text is possible from the Codespace, but the recipe
does not live here.** `tableauserverclient` is already a project dependency and
the same PAT the MCP uses is in 1Password, so a workbook can be downloaded,
parsed, edited and republished. That path has real traps — a publish drops five
pieces of server-side state including the embedded connection credentials, and
the credential failure is silent until the next extract refresh.

Do not attempt a publish from memory. Read
`docs/guides/tableau-workbook-editing.md` first; it carries the worked code, the
five parsing traps, and the post-publish restore steps. Tracked in
[#5157](https://github.com/TEAMSchools/teamster/issues/5157).

**`get-workbook` DOES give the workbook-to-table mapping.** Its
`upstreamDatasources` array returns each datasource's `name`, `luid`, and
`datasourceType`, and it works for **embedded** extracts — so the dbt model
behind a gated workbook is one call away, and a second, stale datasource left
attached by an incomplete repoint shows up here. Use it before asking the user
to read the Data pane in Desktop.

**Row-level security is invisible to the MCP.** `scripts/tableau-mcp-launch.sh`
authenticates with the shared service PAT `Tableau Server PAT - Dagster` (Data
Team vault) — the same one Dagster's Tableau refresh assets use. So
`get-view-data` and `query-datasource` return that service identity's rows, not
any particular person's. They cannot test a persona; use _Preview as User_ in
Desktop. See the Tableau permissions guide,
`docs/guides/tableau-permissions.md`.

**`search-content` ranks, `list-*` enumerates.** `search-content` returns a
single ranked page of top matches, not every match — do not treat its output as
an exhaustive inventory. Use `list-workbooks` with a `filter` when you need
completeness.
