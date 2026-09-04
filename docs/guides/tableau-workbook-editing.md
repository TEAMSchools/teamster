# Editing Tableau Workbooks Programmatically

How to read, audit, and change calculated fields in a published Tableau workbook
from a Codespace — including republishing to Production without silently
degrading the workbook.

This is the mechanical companion to `docs/guides/tableau-permissions.md`
(landing in #4673), which describes what the row-level-security calculations
mean, and to the build reference at
`docs/superpowers/plans/2026-07-31-tableau-workbook-remediation.md`, which
carries the paste-ready text of every gate.

!!! tip "Working with Claude Code"

    This page is written to be pasted wholesale into a Claude Code session as
    context before asking it to read or change a calculation. In this repo it also
    loads automatically: `.claude/context/tableau.md` carries the condensed
    version and is injected on the first Tableau MCP call.

Exercised on 2026-09-04 against `tableau.kipp.org` / site `KIPPNJ`: audited the
RLS calculations in all 11 permission-gated workbooks, then deleted a dead
calculated field from `SchoolMint Grow Dashboard` and republished Production.

That publish also **broke the workbook's next extract refresh**, because it
dropped the embedded connection credentials and the verification checked only
metadata. Both facts are in this page: the recipe works, and the credentials
step is the one that is easy to miss and expensive to miss. Read _A publish
drops five pieces of server-side state_ before publishing anything.

---

## The MCP cannot do this

The Tableau MCP (`@tableau/mcp-server`) is **read-only**. Every tool is a `get-`
/ `list-` / `query-` / `search-`: no publish, no workbook edit, no group
mutation, and **no tool returns calculated-field formulas**. Verified against an
embedded-extract luid:

| Tool                      | Result on an embedded datasource              |
| ------------------------- | --------------------------------------------- |
| `get-datasource-metadata` | HTTP 500                                      |
| `query-datasource`        | `Unable to retrieve data source information.` |

`get-datasource-metadata` reaches the Metadata API only for **published**
datasources, and even then returns field names and roles, never formulas. Every
gated workbook uses an **embedded** extract, so it cannot reach them at all.
`query-datasource`'s inline `calculation` parameter is not a back door either —
it fails on the same datasources.

Do not go looking for an MCP tool that edits a workbook. Calculation text lives
in the `.twb` XML, so the job is to fetch the file.

The MCP is still the right tool for **inventory and lineage**. `get-workbook`
returns `upstreamDatasources` with each datasource's name, luid and type, and it
works for embedded extracts — so it maps a workbook to its dbt model in one
call, and it reveals a stale datasource left attached by an incomplete repoint.

## Stack

- **`tableauserverclient`** (TSC) — already a dependency (`>=0.25`, resolves to
  0.41). No install needed.
- **`tableaudocumentapi`** (optional) via `uv run --with tableaudocumentapi`.
  Its `Field.calculation` has a working `@calculation.setter` that round-trips
  through `Workbook.save_as`. Good for rewriting one formula; it cannot delete a
  field, so field removal is raw XML.
- `zipfile` and `ElementTree` from the standard library for everything else.

## Credentials — run under pytest

The PAT is the same one the MCP and Dagster use:
`op://Data Team/Tableau Server PAT - Dagster`, with fields `hostname`,
`site id`, `username`, and `credential`.

A plain `uv run python` gets no secrets. Write a throwaway
`tests/**/test_zz_*.py`, run `uv run pytest <path> -s`, then delete it — the
autouse session fixture in `tests/conftest.py` loads 1Password secrets. See
[tests/CLAUDE.md](https://github.com/TEAMSchools/teamster/blob/main/tests/CLAUDE.md).
Do not call `op` from Bash; it is hook-blocked. Calling it through `subprocess`
from inside the test file is fine.

**Delete the throwaway in the same session and never commit it.** No workflow
runs pytest in CI, so the risk is a live workbook-publishing path sitting in the
test tree rather than one that fires automatically — but that is reason enough.

```python
import os
import subprocess
from pathlib import Path

import tableauserverclient as tsc


def _op(field: str) -> str:
    token = Path("/etc/secret-volume/.op-token").read_text().strip()
    return subprocess.run(
        ["op", "read", f"op://Data Team/Tableau Server PAT - Dagster/{field}"],
        capture_output=True,
        text=True,
        env={**os.environ, "OP_SERVICE_ACCOUNT_TOKEN": token},
        check=True,
    ).stdout.strip()


auth = tsc.PersonalAccessTokenAuth(
    _op("username"), _op("credential"), site_id=_op("site id")
)
srv = tsc.Server(_op("hostname"), use_server_version=True)
srv.auth.sign_in(auth)
```

!!! warning "Do not disable TLS verification"

    `tableau.kipp.org` serves a valid GoDaddy-issued `*.kipp.org` certificate that
    validates against the default trust store. Passing
    `http_options={"verify": False}` only exposes the PAT. The `http://SAC-RPT-01/`
    URLs that appear in MCP responses are the server's internal name, not the
    endpoint to call — that mismatch is what tempts people into disabling
    verification.

## Reading the calculations

```python
p = srv.workbooks.download(wb_id, filepath=dest, include_extract=False)
```

`include_extract=False` drops a gated workbook from tens of MB to tens of KB and
**still carries every calculation**. Use it for all read-only work.

The `.twbx` is a zip; the `.twb` inside is the XML. Formulas live in
`<column><calculation formula='...'/></column>`.

```python
import zipfile
from xml.etree import ElementTree

z = zipfile.ZipFile(p)
text = z.read(next(n for n in z.namelist() if n.endswith(".twb"))).decode("utf-8")
root = ElementTree.fromstring(text)

for col in root.iter("column"):
    calc = col.find("calculation")
    if calc is not None and calc.get("formula"):
        print(col.get("caption"), "->", calc.get("formula"))
```

A workbook downloaded without extracts can come back as a bare `.twb` rather
than a `.twbx` when it has no extract at all. Guard with `zipfile.is_zipfile(p)`
and fall back to reading the file directly.

### Five traps

1. **`srv.workbooks.get()` returns the first 100 only.** This site has ~450
   workbooks, so a gated workbook is often not on page one. A first pass that
   falls through to `wbs[0]` will cheerfully audit an unrelated workbook in
   `Archive` and report success. Always `list(tsc.Pager(srv.workbooks))`. Same
   applies to `groups`, `users`, `views` and `jobs`.

1. **Internal names are not captions, and they mislead.** A field captioned
   `Permissions` had the internal name `[User_test (copy)]`; one captioned
   `RLS - Role Gate` was `[RLS - Entity Gate (copy)_1662461611803287552]`. These
   are duplication artifacts. Always resolve through the `caption` attribute,
   never the `name`.

1. **Line endings are CRLF.** A regex ending `</column>\n` matches nothing. Use
   `\r?\n`.

1. **Filter column references need three layers stripped.** A filter references
   `[federated.0ax76c...].[none:User_test (copy):nk]`. To recover the column,
   take the segment after `].[`, then strip a leading `none:` and a trailing
   `:nk` / `:qk` / `:ok`. Splitting on `.` does not work — the datasource name
   contains dots.

1. **`USERNAME() = [field]` is a correct self/manager clause.** Only
   `USERNAME() = '<literal>'` is an individual by-name grant, and the literal
   form is often wrapped: `lower(USERNAME()) = 'someone'`. A naive
   `USERNAME\(\)\s*=\s*'` pattern misses those and undercounts silently. Use
   something tolerant such as `USERNAME\(\)[^'\n]{0,24}=\s*'([^']+)'`.

### Where a gate is attached

A **datasource-wide** filter — Desktop's _Apply to Worksheets → All Using This
Data Source_ — appears as a `<filter>` under a **`shared-view`** element. Not
under a `<worksheet>`, and not as a `<datasource><filter>`. Sheet-local filters
are under `<worksheet>`.

Build a parent map and walk ancestors to tell them apart:

```python
parent = {child: p for p in root.iter() for child in p}
```

Miss this and you will conclude a correctly-gated workbook is wide open.

Tableau **ANDs** every filter that reaches a mark, so a sheet-local filter can
only narrow access, never widen it past a datasource-wide one. If a sheet-local
field was written to grant _broader_ access, it does not work — that is a real
defect and it is invisible in the UI.

## Publishing

### Never publish a no-extract download

A file downloaded with `include_extract=False` has no data. Publishing it strips
the extracts off a live workbook. For any publish, download with
`include_extract=True`, edit the `.twb` **inside** the package, and repackage
copying every other entry byte-for-byte:

**Read every payload before you open the output archive.** `writestr` mutates
the `ZipInfo` object it is handed, and those objects back the source archive's
central directory, so writing progressively invalidates `zin`. A read later in
the same loop fails with `zipfile.BadZipFile: Bad magic number for file header`
on the second or third entry — which reads like a corrupt download rather than a
bug in your loop, because every entry reads fine individually.

```python
payloads = {n: zin.read(n) for n in zin.namelist()}
payloads[twb_name] = edited.encode("utf-8")

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        fresh = zipfile.ZipInfo(item.filename, date_time=item.date_time)
        fresh.compress_type = item.compress_type
        fresh.external_attr = item.external_attr
        fresh.create_system = item.create_system
        zout.writestr(fresh, payloads[item.filename])
```

Then assert every non-`.twb` entry is SHA-identical to the source before going
near the server. Note the SHA check does **not** catch the mutation bug above —
it passes either way — so use the fresh-`ZipInfo` form regardless.

### Pass `skip_connection_check=True`

Without it, every publish fails:

```text
403132: Forbidden
<workbook name> failed to establish a connection to your datasource.
```

The server probes the connection at publish time and there is no embedded
credential to probe with. The extracts are self-contained, so skipping the probe
is safe — but the error reads like a permissions problem rather than a missing
argument, which sends you looking in the wrong place.

### Dry-run first

`TEMP-CB` (`ddc817c2-6bc7-4bca-8be9-e385f95b9ebc`) is owned by the same account
as the gated workbooks. Publish there with `PublishMode.CreateNew` under a
clearly temporary name, open it, confirm it renders, then do the real one.

!!! warning "`Overwrite` and `CreateNew` fail differently on credentials"

    Both lose the credential, but they present differently, so neither result
    tells you about the other:

    | Mode | `embed_password` after | Symptom |
    | --- | --- | --- |
    | `CreateNew` | flips to **`False`** | views **stop rendering**, `400074 ExportViewException` |
    | `Overwrite` | stays **`True`** | views render fine; the next **extract refresh** fails hours later |

    So a dry-run into `TEMP-CB` that renders correctly does **not** prove an
    `Overwrite` will keep working, and an `Overwrite` that renders correctly does
    not prove the credential survived. Only a refresh does.

### A publish drops five pieces of server-side state

None of these live in the `.twb`. Restore every one, or the workbook silently
degrades:

| Dropped                          | Restore with                                       |
| -------------------------------- | -------------------------------------------------- |
| **Embedded connection creds**    | **see the warning below — breaks extract refresh** |
| Desktop's published-sheet choice | `item.hidden_views = [...]` **at publish time**    |
| Workbook owner                   | `wb.owner_id = ...` then `workbooks.update(wb)`    |
| Workbook tags                    | `wb.tags = {...}` then `workbooks.update(wb)`      |
| Per-view tags                    | `v.tags = {...}` then `views.update(v)`, per view  |

!!! danger "Embedded credentials fail silently, hours later"

    A publish that omits embedded connection credentials leaves a workbook that
    looks perfectly healthy. Every view renders, because the datasources are
    embedded `.hyper` extracts and reading them authenticates against nothing.
    The first thing that needs credentials is the next **extract refresh**, which
    fails with `Tableau needs an unexpired OAuth refresh token to connect to the
    data.`

    This happened to `SchoolMint Grow Dashboard` on 2026-09-04: published at
    17:08:58, refresh failed at 18:33:07 after 30 days of clean refreshes. No
    metadata check catches it — `populate_connections` still reports
    `embed_password=True` with the correct service-account username, because that
    field records intent rather than a live token.

    **`publish(connections=...)` cannot carry them for BigQuery** — tested
    2026-09-04, and having the service-account key does not help. A BigQuery
    `<connection>` has no `server` attribute at all (its identity is
    `CATALOG='teamster-332318'` plus `schema`), the REST API reports
    `server_address=''`, and TSC raises
    `ValueError: Connection must have a server address` before it will serialise
    one. Passing `embed_password=True` without a password serialises but emits no
    `connectionCredentials` element, so it carries nothing.

    The reliable fix is re-embedding from Desktop (republish with _Embed
    password_ checked) or on Server via the workbook's Data Connections page.

    **After any publish, trigger a refresh and confirm it succeeds.** Metadata
    verification is not sufficient — that is exactly the check that missed this.

!!! tip "The durable fix is in the connection attributes — tracked in #5157"

    Each BigQuery connection carries `workgroup-auth-mode='prompt'`, which is why
    the credential lives on the workbook and dies with a publish, alongside
    `server-oauth='server-custom'` — a custom OAuth client that already exists at
    server level. Pointing these connections at a server- or site-level saved
    credential instead of prompting leaves a publish nothing to strip, across all
    11 gated workbooks. It is a Tableau admin plus Desktop change, filed as
    [#5157](https://github.com/TEAMSchools/teamster/issues/5157).

    Until that lands, **publish and then re-embed by hand** is the accepted
    recipe. The manual step is the price of editing calculations
    programmatically, and the trade is worth it — but the refresh check is not
    optional, because a missed re-embed fails silently.

**`hidden_views` is the one that bites.** Which sheets Desktop chose to publish
is server-side state absent from the file, so a REST publish exposes every sheet
the `.twb` marks visible. On `SchoolMint Grow Dashboard` the file marked 13
visible where Production published 9 — a naive overwrite would have exposed two
dashboards built on legacy permission gates. Read the live view list with
`populate_views` **before** publishing, and pass the difference.

Tags matter because `entra-ready` is the permissions inventory that the
permissions guide keys off. Losing it drops the workbook out of the inventory
with no error.

### What is not affected

Extract refresh schedules and workbook permissions survive. `Production` is
`LockedToProject`, so permission rules are inherited rather than per-workbook —
verified as 6 rules before and 6 after. An in-place `Overwrite` keeps the same
LUID and `content_url`, so bookmarks and embeds survive.

### Assert the overwrite was in place

`Overwrite` matches on name plus project. If the name is off by one character it
silently creates a **new** workbook instead of replacing the old one:

```python
pub = srv.workbooks.publish(item, path, mode=tsc.Server.PublishMode.Overwrite)
assert pub.id == expected_id, "overwrite created a NEW workbook"
assert pub.content_url == pre_content_url
```

### Rollback

Workbook revisions. Call `srv.workbooks.populate_revisions(wb)` and read
`wb.revisions` — `SchoolMint Grow Dashboard` had 25 retained. **Record the
latest revision number before publishing** so you know what to restore.

A revision restore rolls back the calculation but **not** an extract refresh. If
you refreshed an extract in the same sitting, check field references after
restoring rather than assuming the revision is self-contained.

## The sequence that worked

1. Download with `include_extract=False`; find and read the target calculation.
1. Record pre-state: id, name, project, owner, `show_tabs`, `content_url`,
   workbook tags, per-view tags, permission-rule count, latest revision, **and
   `populate_connections` output for every connection**.
1. Download again with `include_extract=True`.
1. Edit the `.twb` text with targeted surgery, then assert: the target is gone
   or changed, **zero lines added** if you only meant to delete, every other
   permission field still present, and the XML still parses.
1. Repackage; assert non-`.twb` entries are SHA-identical.
1. Publish `CreateNew` to `TEMP-CB` and inspect it.
1. Publish `Overwrite` to Production with `hidden_views`; assert id and
   `content_url` are unchanged.
1. Restore owner, workbook tags, and per-view tags.
1. Re-embed the connection credentials, then re-download and diff every recorded
   attribute against pre-state.
1. **Trigger an extract refresh and confirm it finishes `Success`.** This is the
   only step that proves the credentials survived, and it is the one the
   2026-09-04 publish skipped.

## Before you publish

Publishing overwrites a live dashboard. Steps 1 through 6 above are safe and
reversible; step 7 is neither, and a copy in `TEMP-CB` costs one extra upload.
Claude should not run step 7 without the workbook and the change named
explicitly in a human's own message.

Check whether a worksheet you are about to orphan is embedded on **another
dashboard** before deleting a field that filters it. Two dashboards commonly
reference the same worksheet objects rather than copies, and removing a filter
widens access.

Row-level security is invisible from here regardless: the shared service PAT
returns that service identity's rows, so `get-view-data` and `query-datasource`
cannot test a persona. Use _Preview as User_ in Desktop, with the personas in
the playbook.
