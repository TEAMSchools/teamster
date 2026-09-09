# Scripts

Five files. Two are checkers you run on every edit, one builds mutants to test
your assertions, one repacks the archive, one is the credentialed template.

All were used against a real 1.9 MB production workbook. `check_twb.py` and
`check_geometry.py` carry no workbook-specific values and should work anywhere.
`mutate.py` and `repack.py` are generic. `tsc_session.py` has placeholders.

## `check_twb.py`

Everything Tableau Desktop rejects that Tableau Server does not. Each check
corresponds to a real refusal on a file Server had already accepted.

```bash
uv run python check_twb.py <workbook.twb> [--ref <known-good.twb>]
```

| Check                 | Catches                                                                |
| --------------------- | ---------------------------------------------------------------------- |
| `check_worksheets`    | Worksheet missing `<simple-id>`                                        |
| `check_features`      | An element whose feature is not in `<document-format-change-manifest>` |
| `check_views`         | A `<view>` with no `<aggregation>`                                     |
| `check_pane_order`    | Pane children out of content-model order                               |
| `check_manifest_drop` | Manifest entries present in `--ref` and lost, dotted names included    |
| `check_unknown`       | Elements absent from the reference workbook                            |

`--ref` should be the untouched base you pulled. Without it the last two checks
are skipped.

## `check_geometry.py`

Dashboard zone geometry. Nothing else in the toolchain catches a zone at the
wrong nesting depth — it is valid XML, and Server renders it as an overlap.

```bash
uv run python check_geometry.py <workbook.twb> "<dashboard>" [--baseline <base.twb>]
```

Three invariants: visible siblings do not overlap, including at top level; a
flow container's parent-minus-children gap matches the same container in the
baseline exactly; the top-level `layout-basic` zone spans the full canvas.

**Always pass `--baseline`.** Without it the gap check falls back to an absolute
0–3000 bound, which is far weaker. The script prints which mode it ran in so a
weak pass cannot be mistaken for a strong one.

Why differential rather than a tolerance: container gaps are per-container
constants (0, 1, 586, 587, 888, 2636 in one dashboard) with no relation to child
count. A per-child tolerance generous enough for the widest container silently
passed a 4,445-unit defect.

## `mutate.py`

Builds a deliberately-broken copy so you can prove an assertion has teeth.

```bash
uv run python mutate.py <src.twb> <out.twb> "<dashboard>" <op> [args...]
```

| Operation                        | Simulates                                      |
| -------------------------------- | ---------------------------------------------- |
| `control`                        | nothing; must be byte-identical to the source  |
| `duplicate <zone> <before>`      | a stale copy left behind by a move             |
| `reparent <zone> <new-parent>`   | a zone attached to the wrong container         |
| `move-after <zone> <sibling>`    | children in the wrong order                    |
| `swap <zone-a> <zone-b>`         | two zones exchanged                            |
| `set-attr <zone> <attr> <val>`   | a wrong attribute on the zone tag              |
| `set-format <zone> <attr> <val>` | a wrong value in the zone's own `<zone-style>` |
| `delete <zone>`                  | a zone dropped entirely                        |

Run `control` first every time. If it is not byte-identical, the surgery is
lossy and every mutant result is void — this is exactly why the script does text
surgery rather than using ElementTree, whose round trip fails a regex assertion
on an unmutated file.

`set-attr` edits the `<zone>` tag; `set-format` edits a `<format>` inside the
zone's own `<zone-style>`. Border colours, backgrounds and margins live in the
latter.

The script refuses to write a mutant identical to its input, so an op that
matched nothing fails loudly instead of producing a passing no-op test.

## `repack.py`

```bash
uv run python repack.py <edited.twb> <donor.twbx> <out.twbx>
```

Copies every entry from the donor archive and swaps only the `.twb`, then
asserts the packaged bytes are identical to the source and that no bare LF was
introduced. An earlier version flattened 27,000 CRLF endings on every repack and
nobody noticed, because the file on disk stayed correct.

## `tsc_session.py`

Template for download, publish and render. Copy it to `tests/test_zz_*.py`, fill
the three `REPLACE-ME` values, run under pytest, delete it.

The publish gate is the important line:

```python
assert item.project_id == TEMP_PROJECT, f"published to {item.project_name}!"
```

Put it immediately after the publish call, before any render or populate. It is
the only thing standing between a scripted mistake and a corrupted production
workbook.

## Reading exit codes

Never through a pipeline. `cmd | tail` reports `tail`'s status, and two exit
codes were misreported that way in this project.

```bash
uv run python check_twb.py out.twb >/tmp/o.out 2>&1; rc=$?
echo "[$rc] $(tail -1 /tmp/o.out)"
```
