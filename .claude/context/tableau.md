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
Never run it without the user naming the workbook and the change. Dry-run into
`TEMP-CB` (`ddc817c2-6bc7-4bca-8be9-e385f95b9ebc`, owned by the same account as
the gated workbooks) with `PublishMode.CreateNew` first.

**A publish drops five pieces of server-side state that are NOT in the `.twb`.**
Restore every one or the overwrite silently degrades the workbook. Learned on
SchoolMint Grow 2026-09-04, the fifth one the hard way:

| Dropped                          | Restore with                                          |
| -------------------------------- | ----------------------------------------------------- |
| **Embedded connection creds**    | **see below — this one breaks the extract refresh**   |
| Desktop's published-sheet choice | `item.hidden_views = [...]` **at publish time**       |
| Workbook owner                   | `wb.owner_id = ...` then `workbooks.update(wb)`       |
| Workbook tags                    | `wb.tags = {...}` then `workbooks.update(wb)`         |
| Per-view tags                    | `v.tags = {...}` then `views.update(v)`, one per view |

**Embedded credentials are the dangerous one, because the failure is silent and
delayed.** A publish that omits them leaves a workbook that looks perfectly
healthy — every view renders, because the datasources are embedded `.hyper`
extracts and nothing needs to authenticate to read them. The first thing that
needs credentials is the next **extract refresh**, which fails hours later with:

```text
Tableau needs an unexpired OAuth refresh token to connect to the data.
```

That is what a publish of `SchoolMint Grow Dashboard` at 17:08:58 did on
2026-09-04: refresh failed at 18:33:07 having succeeded for the previous 30
days. Nothing in the workbook metadata shows it — `populate_connections` still
reports `embed_password=True` and the right service-account username, because
that field records intent, not a live token.

`workbooks.publish()` takes a `connections` sequence of `ConnectionItem`, and
`workbooks.update_connection(workbook_item, connection_item)` exists (populate
connections first). **Neither is verified to restore BigQuery OAuth** — the
`update_connection` docstring covers server address, port, username and
password, and says nothing about OAuth tokens. So until someone tests it, treat
the reliable fix as re-embedding from Desktop (republish with _Embed password_
checked) or on Server via the workbook's Data Connections page.

**Therefore: after any publish to these workbooks, trigger a refresh and confirm
it succeeds before calling the job done.** Checking metadata is not enough; that
is precisely the check that missed this.

`hidden_views` is the load-bearing one. Which sheets Desktop published lives on
the server, not in the file, so a REST publish exposes every sheet the `.twb`
marks visible — on Grow that was 4 extra views including two dashboards built on
legacy gates. Read the live view list first and pass the difference.

Tags matter because `entra-ready` is the permissions inventory: an overwrite
without the restore drops the workbook out of it with no error.

Extract refresh schedules and workbook permissions are **not** affected —
Production is `LockedToProject`, so permission rules are inherited and survived
intact (6 before, 6 after). An in-place Overwrite keeps the same LUID and
`content_url`, so bookmarks and embeds survive; assert both after publishing,
because a name mismatch silently creates a NEW workbook instead. Rollback is the
prior revision (25 retained on Grow) — record the latest revision number before
publishing.

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
