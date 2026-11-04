# Content models and the feature manifest

Tableau Desktop validates a workbook against a content model on open. Tableau
Server does not. Every rule here came from a Desktop refusal on a file Server
had already accepted and rendered. Desktop's error text quotes the model
verbatim: when you hit one, copy the model out of the error rather than guessing
at it.

Marks: **Verified** = observed in a render or a Desktop error. **Inferred** =
consistent with observation, not directly tested.

## The feature manifest decides which elements are legal

**Verified.** `<document-format-change-manifest>` is a per-workbook declaration
of the features that workbook uses. An element whose feature is not declared is
rejected with `no declaration found for element 'x'`, even though the file
declares the same `version` and build as a workbook where that element is fine.
This is why moving a working element between two workbooks fails. Two workbooks
in the same suite had complementary gaps:

| Element                                        | Required feature                                                                                                  |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `<button>`                                     | `BasicButtonObject` and `BasicButtonObjectTextSupport`                                                            |
| `<toggle-action>`, `active-visual-state-index` | `CollapsiblePane`                                                                                                 |
| Dynamic zone visibility                        | `DatagraphCoreV1`, `DatagraphNodeDashboardZoneVisibilityV1`, `DatagraphNodeSingleValueFieldV1`, `ParameterAction` |
| `<extract>` with `user-specific`               | `_.fcp.VConnDownstreamExtractsWithWarnings...`                                                                    |

Adding an element means adding its manifest entry.

The manifest is per workbook, so a refusal is too. "Desktop refuses dynamic zone
visibility" was true of one lineage whose manifest lacked `DatagraphCoreV1`; the
merged successor declared all four features and carried a Tableau-authored
datagraph (observed in the file). Before ruling a feature out, grep the target's
manifest for it, and grep again whenever the base lineage changes: a merge or a
promoted review copy is a lineage change.

### Insert into the manifest. Never regenerate it

**Verified.** A regex that rebuilt the manifest silently dropped
`<_.fcp.VConnDownstreamExtractsWithWarnings.../>` because the pattern matched
`[A-Za-z0-9_]+` and the entry name contains dots. That un-declared the feature
that makes the extract's `user-specific` attribute legal, and Desktop refused
the file with `attribute 'user-specific' is not declared for element 'extract'`.
`check_manifest_drop` in `docs/tableau-xml/scripts/check_twb.py` diffs manifest
entries against a reference workbook, dotted names included, for exactly this
reason.

## The content models

Copy these into any script that inserts elements. Order is strict; optionality
is as Desktop reports it.

### Pane

```text
(view, mark, mark-sizing?, encodings?, label-data*, dropline?, trendline?,
 reference-line, customized-tooltip, customized-label, style)
```

**Verified**, error `D2E8DA72`. Inserting `<customized-tooltip>` straight after
`</encodings>` puts it ahead of a sheet's `<reference-line>` and Desktop refuses
to open the workbook with
`element 'reference-line' is not allowed for content model '(view,mark,mark-sizing?,encodings?,label-data*,dropline?,trendline?,reference-line,customized-tooltip,customized-label,style)'`.
The element Desktop names is the one that could not follow what you inserted,
not the one you touched. On sheets with a reference line (a goal tick, a target
marker) the tooltip must come after it. The trap: most sheets have no reference
line, so an insert anchored on `</encodings>` works everywhere until it does
not.

The indicators are as Desktop printed them. Read literally, `reference-line`,
`customized-tooltip` and `customized-label` are each required exactly once, yet
this corpus has panes without a reference line that Desktop opens, so the
cardinality is not established (see
[unverified-warnings.md](unverified-warnings.md)). `check_pane_order` in
`check_twb.py` verifies order only: a second `<customized-tooltip>` in one pane
passes it. Check for an existing one before inserting.

### Encodings

Observed in the file: `<encodings>` children have no fixed order. One untouched
base holds 31 distinct child sequences, among them
`color, lod, tooltip ×7, text`, `text, color`, and
`color, text, tooltip, tooltip, tooltip, lod, tooltip`; `text` alone is the
commonest. An assertion that required sorted children failed the unedited file.
Insert a new `<lod>` after the last existing `<lod>`, else after `<color>`, else
as the first child, and assert that position rather than any global order. The
parameter-action constant that goes on Detail this way is in
[layout-and-zones.md](layout-and-zones.md).

### Worksheet

```text
((layout-options? | repository-location?), table, simple-id)
```

**Verified.** Two consequences:

- `<layout-options>`, which holds `<title>` and `<caption>`, must precede
  `<table>`. A worksheet with no `layout-options` needs the whole block inserted
  at the very start of the element, not next to the table.
- Every worksheet needs `<simple-id>`. Hand-built worksheets omit it easily and
  Desktop reports
  `missing elements in content model '(((layout-options?)|(repository-location?)),table,simple-id)'`.

### View

```text
(datasources?, mapsources?, datasource-dependencies*, filter, sort, perspectives,
 shelf-sorts, slices?, aggregation)
```

**Verified.** Every `<view>` needs `<aggregation>`. A hand-built worksheet that
omits it is rejected with
`missing elements in content model '(datasources?,...,slices?,aggregation)'`.
The cheapest fix is to clone the filter/slices/aggregation skeleton from a
working sheet rather than compose one.

Read literally the model requires `filter`, `sort`, `perspectives` and
`shelf-sorts`, yet a Tableau-authored title sheet in this corpus carries only
`datasources`, `datasource-dependencies` and `aggregation`, and Desktop saved
that file. A hand-built close-button sheet copied that minimal `<view>`; Server
rendered it (Verified), and a Desktop open is pending (Inferred).

Inside a `<view>`, `<filter>` elements and `<column-instance>` dependencies are
sorted by column string in every sheet of this corpus (uppercase `Calculation_`
before lowercase field names); `<slices>` columns are not. Insert before the
neighbour that will follow, and assert that position.

### Zone (dashboard layout)

```text
(formatted-text, layout-cache?, zone, flipboard, zone-style?)
```

**Verified.** Child zones come _before_ the container's own `<zone-style>`.
Getting this backwards is rejected. In the files observed, a container's own
style is indented 14 spaces and its children's 16, though indentation is
cosmetic.

## What no schema check catches

**Verified.** A zone nested at the wrong depth is valid XML and satisfies the
content model. It renders as an overlap or a gap. Nothing in Desktop or Server
complains. This is the single most dangerous class of edit, because the whole
toolchain reports success. `docs/tableau-xml/scripts/check_geometry.py` exists
to cover it: it compares each container's parent-minus-children gap against the
same container in a known-good baseline and requires an exact match.

## Practical rule for insertion

Write the model into the inserting script as an ordered list, find the position
by scanning for the last element that must precede your new one, and assert the
result is still in model order before writing. `check_pane_order` in
`check_twb.py` does this as a post-hoc check; doing it at insert time as well is
cheap.
