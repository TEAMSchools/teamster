# Failure catalog

Every failure observed in the source project, as symptom to cause to fix.
Ordered by where you notice it. All entries are **Verified** unless marked.

## Desktop refuses to open the workbook

Server accepted and rendered every one of these first.

| Symptom (Desktop error)                                                      | Cause                                                     | Fix                                                                   |
| ---------------------------------------------------------------------------- | --------------------------------------------------------- | --------------------------------------------------------------------- |
| `no declaration found for element 'button'`                                  | Feature not declared in the workbook's manifest           | Add `BasicButtonObject` + `BasicButtonObjectTextSupport`              |
| `no declaration found for element 'toggle-action'`                           | Same                                                      | Add `CollapsiblePane`                                                 |
| `attribute 'user-specific' is not declared for element 'extract'`            | A regex manifest rebuild dropped a dotted entry           | Insert into the manifest, never regenerate it                         |
| `missing elements in content model '(((layout-options?)…),table,simple-id)'` | Hand-built worksheet has no `<simple-id>`                 | Clone the skeleton from a working worksheet                           |
| `missing elements in content model '(datasources?,…,slices?,aggregation)'`   | `<view>` has no `<aggregation>`                           | Same                                                                  |
| `element 'reference-line' is not allowed…` (`D2E8DA72`)                      | `<customized-tooltip>` inserted before `<reference-line>` | Insert after the last of label-data/dropline/trendline/reference-line |

All six are covered by `docs/tableau-xml/scripts/check_twb.py`. Run it before
handing anything over; the whole point is to catch these without a Desktop round
trip. Models and manifest table: [content-models.md](content-models.md).

## Something renders blank or literal

| Symptom                                                   | Cause                                                                 | Fix                                                             |
| --------------------------------------------------------- | --------------------------------------------------------------------- | --------------------------------------------------------------- |
| Worksheet title shows nothing at all                      | The dashboard zone carries `show-title='false'`                       | Flip to `'true'` in `<zones>`, not `<devicelayouts>`            |
| A line in a mark label is blank, space still reserved     | Parameter token in `<customized-label>`; it does not resolve          | Use static text, or move the value to a worksheet title         |
| An entire mark label vanishes: caption, value, everything | A calculated field was added to the Text shelf                        | Revert; Text displaces `customized-label`                       |
| Tooltip prints raw `[federated…].[usr:Calculation_…:qk]`  | Encoding form: **unresolved**, see [dynamic-text.md](dynamic-text.md) | Copy a working tooltip's runs verbatim, swap only the instances |
| A field name prints literally in a label template         | Missing `<` `>` placeholder delimiters around the token               | Add them, entity-encoded                                        |

## Layout is wrong

| Symptom                                 | Cause                                                  | Fix                                                     |
| --------------------------------------- | ------------------------------------------------------ | ------------------------------------------------------- |
| A number renders as `####`              | Text does not fit its box                              | Remove a line; growing the box 66→78→88px did not help  |
| A caption truncates with an ellipsis    | Over roughly `97 * width / 39676` characters           | Shorten it; strips clip, they do not wrap               |
| A legend shows some of its entries      | Strip too short for the swatch rows                    | Height, not width: 40px fits one row, 70px fits two     |
| Row labels clip, then wrap mid-word     | Row-header width, not zone height                      | Shorten the label text                                  |
| Two zones overlap on screen             | A zone at the wrong nesting depth; valid XML, no error | `docs/tableau-xml/scripts/check_geometry.py --baseline` |
| A percent-of-total axis doubles to 200% | A `<lod>` on the Detail shelf changed the mark grain   | Put the field on Tooltip instead                        |
| A dual axis renders side by side        | Fold flag missing from the **table-level** `<style>`   | See below                                               |

The dual-axis fold flag is not on the shelf:

```xml
<style-rule element='axis'>
  <encoding attr='space' class='0' field='[ds].[measure]' field-type='quantitative'
            fold='true' scope='cols' synchronized='true' type='space' />
  <format attr='display' class='0' field='[ds].[measure]' scope='cols' value='false' />
</style-rule>
```

With it the axes fold correctly. **Unresolved:** even folded, the second axis
drew no marks, including as a plain `Bar`. The approach was abandoned. If you
need dual axis, budget a real investigation.

## Reference lines

**Verified.** A per-cell reference line does not resolve on a percent-of-total
axis. It renders at a constant `2.0` whatever field it is given, and stretches
the axis to 200% doing it. Five variations were tried. It works normally on a
plain `usr:` axis:

```xml
<reference-line axis-column='[ds].[usr:Calculation_…:qk]'
                value-column='[ds].[avg:goal_field:qk]'
                formula='average' scope='per-cell' />
```

The value field must be in the view, and on Tooltip rather than Detail.

## Data reads wrong

| Symptom                                                      | Cause                                                                 |
| ------------------------------------------------------------ | --------------------------------------------------------------------- |
| A parameter action fires and nothing changes                 | A blanket replace rewrote the parameter's `<member>` domain           |
| A pop-out never opens; clicks corrupt an unrelated parameter | A merge deleted the boolean parameter and left every reference behind |
| Viz-in-tooltip stops working                                 | A merge deleted the tooltip worksheet and kept both references        |
| Bars move with a control but labels and colours do not       | Encodings on one sheet resolve through different calcs; see below     |

That last one is a reasoning failure, not a mechanical one. On one panel the bar
length resolved through a parameter-aware calculation while the mark label and
the colour resolved through projected-only calculations. Setting the control to
the other basis moved the bars and left the labels, producing a near-zero bar
labelled `+11.4pp` in green. The analysis that missed it traced only the bar.
**Trace every encoding on a sheet (rows, columns, text, colour, size, tooltip),
not just the one that looks like the measure.**

## Tooling and process

| Symptom                                          | Cause                                                                   |
| ------------------------------------------------ | ----------------------------------------------------------------------- |
| Workbook truncated to a fraction of its size     | Loop variable shadowed an outer regex match object                      |
| Whole file shows as changed in a diff            | `read_text(encoding="utf-8")` flattened CRLF to LF                      |
| Published workbook is a few hundred kilobytes    | `include_extract=False` on download                                     |
| Download lands at `name.twbx.twbx`               | `tableauserverclient` appends the extension to `filepath`               |
| An exit code is reported as `0` or `120` wrongly | Read through a pipeline; `$?` was `tail`'s status or a SIGPIPE artifact |
| A commit lands on the wrong branch               | A failed command short-circuited a chained `cd`; use `git -C` always    |

## The tests themselves

The most expensive category, because everything reports success.

| Symptom                                                  | Cause                                                                       |
| -------------------------------------------------------- | --------------------------------------------------------------------------- |
| Geometry checker passes the exact bug it was written for | Per-child tolerance; 900 units × 5 children exceeded the 4,445-unit defect  |
| Geometry checker false-positives on production           | An absolute tolerance tight enough for one container is wrong for another   |
| Structure assertion passes a duplicated zone             | A parent map overwritten in document order hid the stale entry              |
| Structure assertion passes a re-parented zone            | It checked existence and type, never parentage                              |
| Structure assertion passes a reordered zone              | No sibling-order check                                                      |
| Structure assertion passes a card nested inside a card   | Only leaf zones were pinned; the containers never were                      |
| Assertion checks presence, not position                  | Searching a whole block for a token, rather than asserting the run sequence |

Every one of those was found by building a mutant and running the assertion
against it. `docs/tableau-xml/scripts/mutate.py` does the surgery.

## The two reasoning failures worth naming

**Evidence does not transfer across surfaces.** A parameter placeholder was
proved in a worksheet title, then applied to mark labels on the reasoning that
mark labels already carry placeholders. They carry _field_ placeholders. It
rendered blank.

**Presence in a file is not evidence of rendering.** A tooltip form was copied
from the workbook on the assumption that anything present must work. The copy
rendered literally. Whether the original works is still unconfirmed.

Both have the same shape: structural similarity treated as behavioral proof.
When you catch yourself reasoning that way, probe instead
([dynamic-text.md](dynamic-text.md), "How to probe a new surface").
