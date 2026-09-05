# Cumulative GPA Monitor — Tableau build generators

Generators for the Cumulative GPA Monitor dashboard in
`Academic & Gradebook Health Suite`, built by editing `.twb` XML directly.

The Tableau MCP server is read-only — it has no publish, no workbook edit, and
no tool that returns a calculated-field formula. So the dashboard was built by
unpacking the `.twbx`, editing the XML, and repackaging. These files are that
work, persisted.

## Why this exists

The dashboard has 31 calculated fields, 3 parameters, 19 worksheets and a
1366x900 dashboard. Rebuilding any of it by hand is hours. `specs.py` captures
all of it as data, so it can be re-applied to a fresh server baseline.

## Files

| File               | Purpose                                                                                                          |
| ------------------ | ---------------------------------------------------------------------------------------------------------------- |
| `specs.py`         | The build, as data. 32 calculated fields, 12 parameters, 20 worksheets, the dashboard zone tree, 4 colour rules. |
| `twb.py`           | Primitives for editing a `.twb` inside a `.twbx`, plus the audits.                                               |
| `apply.py`         | Applies the styling layer from `specs.py` to a workbook that already has the sheets.                             |
| `verify.py`        | Diffs a regenerated workbook against a reference on every styling dimension.                                     |
| `extract_specs.py` | Regenerates `specs.py` from a finished `.twbx`. Run this after hand edits in Desktop to recapture them.          |

## Every reference is a caption, never an internal id

`[Calculation_4693780698737655073]` differs on every baseline. `specs.py` stores
`[Measured (projected)]` instead, and `twb.to_internal()` resolves captions
against whatever workbook it is given — raising on anything it cannot resolve
rather than emitting a dangling reference. That is what makes the specs
portable.

## Usage

```bash
# apply the styling layer to a downloaded workbook
uv run python scripts/tableau_gpa_monitor/apply.py in.twbx out.twbx

# check a regenerated workbook against a known-good one
uv run python scripts/tableau_gpa_monitor/verify.py out.twbx reference.twbx

# recapture specs after editing the workbook in Desktop
uv run python scripts/tableau_gpa_monitor/extract_specs.py
```

Credentialed work (download, publish, render) must run under pytest — the
autouse fixture in `tests/conftest.py` loads 1Password secrets. A plain
`uv run python` gets none. Write a throwaway `tests/**/test_zz_*.py`, run it,
delete it. See `tests/CLAUDE.md`.

## Verified

`apply.py` was run against a server baseline carrying no styling, and the result
diffed against the hand-built reference:

```text
colours + default-formats:  14 match, 0 differ
per-sheet styling:          80 match, 0 differ
```

## What this does NOT do

`apply.py` covers the styling layer only — colours, number formats, captions,
strokes, alignment. It does **not** construct the 19 worksheets or the dashboard
from nothing. Those specs are captured in `specs.py`, but the builder that
consumes them is not written. Today this regenerates styling onto a workbook
that already has the sheets.

## Traps these files encode

Each of these produced a workbook that passed every structural assertion and was
still wrong. They are enforced in code rather than left to the caller.

- **CRLF is load-bearing.** A regex ending `\n` matches nothing.
- **XML normalises literal newlines in attributes to spaces**, so a multi-line
  formula must use `&#10;`.
- **`zipfile.writestr(zinfo, ...)` mutates the ZipInfo it is handed**, and those
  objects back the source archive's central directory. Read every payload before
  opening the output, or later reads fail with `BadZipFile: Bad magic number`.
- **A colour rule keys on a column-INSTANCE, and the derivation must match what
  the worksheets use** — a row-level dimension is `none:`, an aggregate calc is
  `usr:`. A rule with the wrong derivation stays in the file, resolves to a real
  instance, passes every assertion, and silently does nothing.
  `Workbook.audit_colour_rules()` is the check that catches it.
- **A datasource-level colour rule also needs a datasource-level
  `<column-instance>`**, or Desktop strips the entire `<style>` block on the
  next save.
- **A custom number format needs a leading `*`** — `*0.0%`, `*0.00`,
  `*+0.0"PP";-0.0"PP";0.0"PP"`. Without it Tableau discards the format and
  renders full precision. `#,##0` is accepted either way. `p1%` is not a real
  code; `p0.0%` is.
- **`hidden='true'` on a `<window>` makes a worksheet unreachable** unless it is
  already on a dashboard.
- **An empty pane `<style />` means mark labels never draw**, even with the pill
  on the card. A Bar mark needs `mark-labels-show=true`; a Text mark draws
  regardless.
- **`Workbook.audit_geometry()` is valid only on freshly generated layout.**
  Tableau's own dashboards do not tile exactly, and Desktop rewrites the numbers
  on every round-trip. Scope it with `only=<dashboard name>`.
