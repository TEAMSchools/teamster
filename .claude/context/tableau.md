# Tableau MCP gotchas

**Read-only server.** Every tool is a `get-`/`list-`/`query-`/`search-`. There
is no publish, no workbook edit, no group mutation. Anything that changes
Tableau Server is user-side work in Desktop or the Server admin UI — do not look
for a tool that does it.

**No tool returns calculated-field formulas.** `get-workbook` and
`list-workbooks` return workbook and view metadata (name, description, project,
owner, contained views) — never the calc text. There is no Metadata API GraphQL
passthrough either. Practical effect: **you cannot audit RLS `Permissions` calcs
from here.** Checking which workbooks carry a given branch, or searching for
`USERNAME()` compared against a literal, has to be done by a human in Desktop.
Ask the user for the list rather than trying to derive it.

`get-datasource-metadata` does reach the Metadata API, but only for **published
datasources**, and only for fields/parameters (name, dataType, description,
role) — still not formulas. The permission-gated workbooks each use an
**embedded** extract, so this tool cannot reach them at all.

**No workbook-to-table mapping.** Nothing links a workbook to the dbt model
behind it. To identify the model for a gated workbook, read the datasource name
in Desktop and match it by hand against
`src/dbt/kipptaf/models/extracts/tableau/`.

**Row-level security is invisible to the MCP.** `scripts/tableau-mcp-launch.sh`
authenticates with the shared service PAT `Tableau Server PAT - Dagster` (Data
Team vault) — the same one Dagster's Tableau refresh assets use. So
`get-view-data` and `query-datasource` return that service identity's rows, not
any particular person's. They cannot test a persona; use _Preview as User_ in
Desktop. See
[the Tableau permissions guide](../../docs/guides/tableau-permissions.md).

**`search-content` ranks, `list-*` enumerates.** `search-content` returns a
single ranked page of top matches, not every match — do not treat its output as
an exhaustive inventory. Use `list-workbooks` with a `filter` when you need
completeness.
