# Tableau MCP gotchas

**Read-only server.** Every tool is a `get-`/`list-`/`query-`/`search-`. There
is no publish, no workbook edit, no group mutation. Anything that changes
Tableau Server is user-side work in Desktop or the Server admin UI — do not look
for a tool that does it.

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

**To read or write calc text, go around the MCP — this works from the Codespace
and is verified.** Do not tell the user calc auditing needs Desktop.

`tableauserverclient` is already a project dependency, and the same PAT the MCP
uses is at `op://Data Team/Tableau Server PAT - Dagster` (`hostname`, `site id`,
`username`, `credential`). Run it under pytest so the `tests/conftest.py`
fixture is available, per `tests/CLAUDE.md`:

```python
import tableauserverclient as tsc

auth = tsc.PersonalAccessTokenAuth(pat_name, pat_value, site_id=site)
srv = tsc.Server(host, use_server_version=True)
srv.auth.sign_in(auth)
srv.workbooks.download(wb_id, filepath=dest, include_extract=False)
```

**Do not pass `http_options={"verify": False}`.** `tableau.kipp.org` presents a
valid GoDaddy-issued `*.kipp.org` certificate that validates against the default
trust store — verified 2026-09-04 — so disabling verification only exposes the
PAT for no reason. The `http://SAC-RPT-01/` URLs in MCP responses are the
server's internal name, not the endpoint to call.

`include_extract=False` keeps a gated workbook to tens of KB and still carries
every calculation. The `.twbx` is a zip; the `.twb` inside is the XML, and the
gates are readable with `zipfile` plus `ElementTree` (or `tableaudocumentapi`,
`uv run --with tableaudocumentapi`, whose `Field.calculation` has a working
`@calculation.setter` that round-trips through `Workbook.save_as`). Verified
2026-09-04 on Manager Survey Rollup: 481 `ISMEMBEROF` occurrences, all five
gates, and the worksheet-to-datasource bindings that reveal whether a stale
datasource is actually read.

Two cautions. In `Permissions` the helper gates appear as internal ids
(`[Calculation_2368471220768063489]`), not captions, so resolve them via each
`<column>`'s `caption` attribute. And a gate's `USERNAME() = [field]` clauses
are correct Tier 1 — only `USERNAME() = '<literal>'` is a by-name grant, so
match the literal form or you will count 51 grants where there are none.

**Publishing back is destructive and outward-facing** —
`workbooks.publish(..., mode=Overwrite)` replaces a live Production workbook.
Never run it without the user naming the workbook and the change.

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
Desktop. See
[the Tableau permissions guide](../../docs/guides/tableau-permissions.md).

**`search-content` ranks, `list-*` enumerates.** `search-content` returns a
single ranked page of top matches, not every match — do not treat its output as
an exhaustive inventory. Use `list-workbooks` with a `filter` when you need
completeness.
