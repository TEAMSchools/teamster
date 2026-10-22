# Dashboard layout, zones and text fitting

Dashboard layout is a tree of `<zone>` elements inside `<dashboard><zones>`.
Everything here concerns that tree and how text behaves inside it. All claims
are **Verified** (observed in a render or by measurement) unless marked.

Every pixel figure in this file was measured on dashboards with
`sizing-mode='fixed'` at 1366x900, rendered through the REST image API at
`Resolution.High`, in the fonts the examples show. Outside those conditions the
numbers are hypotheses; [unverified-warnings.md](unverified-warnings.md) lists
the probes.

## The coordinate system

**Verified.** Zone `x`, `y`, `w`, `h` are in units of 1/100000 of the dashboard,
independent of pixels. Convert with the dashboard's own `<size>`:

```text
<size maxheight='900' maxwidth='1366' minheight='900' minwidth='1366' sizing-mode='fixed' />

pixels_high = h / 100000 * 900
pixels_wide = w / 100000 * 1366
```

At 900px tall, 1 pixel is about 111 units.

A recipe's pixel positions can contradict its own intent. "Directly under the
band bars" at `y=280` would have covered the bottom 52px of a card that ends at
338px. Convert every recipe coordinate to units, check it against the existing
zone map, build to the intent, and report the deviation in the hand-over.

## Containers do not sum to their children

**Verified, and it produced two arithmetic errors before it was understood.** A
flow container's children do not add up to the container. The difference is a
per-container constant (margins) with **no relation to the number of children**.
Measured on one production dashboard:

| Zone | Flow | Children | Parent minus children |
| ---- | ---- | -------- | --------------------- |
| 3    | vert | 5        | 0                     |
| 5    | horz | 4        | 0                     |
| 720  | vert | 2        | 1                     |
| 10   | horz | 5        | 586                   |
| 20   | horz | 4        | 586                   |
| 30   | horz | 3        | 587                   |
| 35   | horz | 2        | 587                   |
| 40   | vert | 4        | 888                   |
| 50   | vert | 2        | 888                   |
| 722  | horz | 3        | 2636                  |

A per-child tolerance is unsound in both directions: tight enough for zone 722
is far too loose for a container with five children. The first geometry checker
used 900 units per child, which at five children is 4,500 units of slack, and
the defect it existed to catch was a 4,445-unit shortfall. It passed.

**The correct check is differential.** Compare each zone's gap against the same
zone in a known-good baseline workbook and require an exact match. New zones,
which have no baseline counterpart, get an absolute bound (0 to 3000). That is
what `docs/tableau-xml/scripts/check_geometry.py --baseline` does. Without
`--baseline` it falls back to the absolute bound for every zone, which is far
weaker; it prints which mode it ran in.

## `fixed-size` is the size along the parent's flow axis

**Verified by measurement across 62 zones.** For a child of a `param='horz'`
container it is a width; for `param='vert'` it is a height. It coexists with
`w`/`h` and can disagree with them.

The corpus invariant: **`fixed-size` is never larger than the stored size.**
Across two production dashboards, 62 zones with `is-fixed='true'` split 21 exact
and 41 with `fixed-size` smaller. Zero larger.

Resizing a zone without updating `fixed-size` breaks that invariant and risks
Desktop re-solving the layout on open. Recompute it as
`pixels - flow-axis margin` whenever a zone's size changes.

## Text clips, it does not wrap

**Verified by render.** A header-strip caption that exceeds its width is
truncated with an ellipsis. In the observed strips, all text zones at
`fixed-size='40'` carrying an 8pt italic Arial caption, it did not wrap to a
second line; whether it wraps given more height was not probed. Calibration
points, all measured from renders:

| Zone width (units) | Characters that fit | Characters that clipped |
| ------------------ | ------------------- | ----------------------- |
| 39676              | 96, 97              | 129, 142                |
| 58565              | 108                 | not established         |

A workable rule is `97 * width / 39676`, anchored on the narrow case. It is
deliberately conservative: a caption that fails it may still fit, so the
response to a failure is to render and look, never to raise the constant.

Two related fitting failures, both render-only:

- **A big number rendered as `####`.** Tableau's "does not fit" glyph. A mark
  label with three lines (13pt caption, 10pt qualifier, 30pt number) did not fit
  a 66px zone, nor 78px, nor 88px. The fix was removing the third line, not
  growing the box.
- **A five-item color legend showed three items.** Height was the lever, not
  width. At 40px the strip fits a title plus one row of swatches; at 70px it
  fits a title plus two rows, and all five appear. The 3-then-4-then-5
  progression as height grew is what identified the cause.

## Rotated row headers clip before they wrap

**Verified.** Two single-row bars labelled `Actual Unweighted` and
`Projected Unweighted` clipped to `al Un / ghted` when their zones shrank from
86px to 62px, then wrapped mid-word at 74px. Row-header width, not zone height,
is the constraint. Shortening the label text was cheaper than fighting the
header sizing; the labels are constant-string calculated fields, so it is a
one-string edit.

## A `<lod>` on Detail changes the mark grain

**Verified.** Adding a field to the Detail shelf of a percent-of-total sheet
doubled the axis to 200%. Percent-of-total is a table calculation over the mark
partition, and Detail changes that partition. The source project put tooltip
fields on the **Tooltip** shelf instead and reserved Detail for cases where the
grain change is the intent. Tooltip-shelf fields (an `attr:` dimension and a
plain count, on a percent-of-total sheet) left the render byte-identical
(Verified), and a one-value constant on Detail also left the axis alone. The
probe in [unverified-warnings.md](unverified-warnings.md) stays open for a
many-valued dimension on Tooltip.

## Copying a card pattern

The layout idiom used across the source suite:

```xml
<!-- card: navy hairline, 5-unit inset -->
<zone-style>
  <format attr='border-color' value='#001e62' />
  <format attr='border-style' value='solid' />
  <format attr='border-width' value='1' />
  <format attr='margin' value='5' />
</zone-style>
```

```xml
<!-- header strip: horizontal flow, grey, holding a text zone plus a legend or control -->
<zone fixed-size='40' h='4444' id='800' is-fixed='true' param='horz'
      type-v2='layout-flow' w='58565' x='586' y='39111'>
  <zone fixed-size='40' forceUpdate='true' h='4444' id='801' is-fixed='true'
        type-v2='text' w='58565' x='586' y='39111'>
    <formatted-text>
      <run bold='true' fontcolor='#000000' fontname='Arial'>Band mix, network</run>
      <run>Æ&#10;</run>
      <run fontcolor='#000000' fontname='Arial' fontsize='8' italic='true'>Caption text.</run>
    </formatted-text>
    <zone-style>
      <format attr='border-color' value='#000000' />
      <format attr='border-style' value='none' />
      <format attr='border-width' value='0' />
      <format attr='margin' value='4' />
    </zone-style>
  </zone>
  <zone-style>
    <format attr='border-color' value='#000000' />
    <format attr='border-style' value='none' />
    <format attr='border-width' value='0' />
    <format attr='background-color' value='#e6e6e6' />
  </zone-style>
</zone>
```

Two structural points:

- One card can hold several header-and-chart pairs. Giving every chart its own
  border costs two margins per card and is usually what breaks a pixel budget.
- A flow container should have at least one child **without** `is-fixed='true'`
  so something can absorb slack. In the corpus, every working strip pairs a
  fixed text zone with a flexible sibling. A strip where every child is fixed
  was unprecedented and is worth avoiding.

## A floating panel driven by a parameter action

**Verified** by render (hidden at the parameter's `false`, shown at `true`) and
by the owner's click (a band opened the panel, the × closed it), which together
verify the zone, the datagraph binding and the two actions. Every fragment below
is from the built file; the ids and GUIDs are the parts to swap.

A floating zone is a top-level child of `<zones>`, a sibling of the
`layout-basic` root that follows it, never a descendant. Nothing on the tag says
"floating"; the position in the tree does. A new panel goes after the last
top-level zone, before `</zones>`. A container shown and hidden by dynamic zone
visibility carries `hidden-by-user='true'` on itself **and on every descendant**
in the saved file:

```xml
<zone friendly-name='Band Roster' h='61555' hidden-by-user='true' id='800' param='vert' type-v2='layout-flow' w='98828' x='586' y='37556'>
  <zone fixed-size='30' h='3333' hidden-by-user='true' id='801' is-fixed='true' param='horz' type-v2='layout-flow' w='98828' x='586' y='37556'>
    <zone forceUpdate='true' h='3333' hidden-by-user='true' id='802' type-v2='text' w='94436' x='586' y='37556'>…</zone>
    <zone fixed-size='60' h='3333' hidden-by-user='true' id='803' is-fixed='true' name='Y1 Schools - Roster Close' show-title='false' w='4392' x='95022' y='37556'>…</zone>
  </zone>
  <zone h='58222' hidden-by-user='true' id='804' name='Y1 Schools - Grades Roster' show-title='false' w='98828' x='586' y='40889'>…</zone>
</zone>
```

The binding is a node pair added to the workbook's existing `<datagraph>`, plus
one `<edge>` and two `<pair>` entries under `<node-execution-subgraphs>`, all
with fresh GUIDs. `dashboard-identifier` is the `<dashboard>` element's
`<simple-id>`, not the `<window>`'s; the two differ, and the build used the
dashboard's:

```xml
<single-value-field-node fieldname='[Parameters].[Parameter 15]' fieldname-input-guid='…' node-guid='…' value-output-guid='OUT' />
<dashboard-zone-visibility-node dashboard-identifier='{1FABAC57-…}' node-guid='…' visibility-input-guid='IN' zone-id='800' />
<!-- under <edges> -->
<edge from='OUT' to='IN' />
```

The open and close actions are `<edit-parameter-action>` elements, not
`<action>`. The source value is a constant calculated field (`TRUE` to open,
`FALSE` to close) on the source sheet's Detail shelf, declared in that sheet's
`<datasource-dependencies>` as `<column>` and `<column-instance>`:

```xml
<edit-parameter-action caption='Open roster from band' name='[Action_Panel01]'>
  <activation type='on-select' />
  <source dashboard='Academic Health Schools' type='sheet' worksheet='Y1 Schools - GPA Distribution' />
  <agg-type type='attr' />
  <clear-option type='do-nothing' value='b:false' />
  <params>
    <param name='source-field' value='[federated.…].[none:Calculation_7600000000000000101:nk]' />
    <param name='target-parameter' value='[Parameters].[Parameter 15]' />
  </params>
</edit-parameter-action>
```

Two consequences of that constant on Detail. It has one value, so it does not
split the mark partition: the percent-of-total source sheet kept its axis and
bars in the closed render, re-laid only by a 9px widening (Verified). It does
show in the sheet's automatic tooltip as `Panel open: True` unless the sheet
carries a `<customized-tooltip>` (Inferred; the hover is pending).

The close button is a one-mark sheet: `<mark class='Shape' />`, a single `<lod>`
of the `FALSE` constant, `<format attr='shape' value=':filled/times' />`, and a
`<view>` of only `datasources`, `datasource-dependencies` and `aggregation`
([content-models.md](content-models.md)).

`check_geometry.py` skips every `hidden-by-user` zone, so nothing above is
geometry-checked. The panel's rectangle against the zone map is your own
assertion; the open-state render is the check.

## Removing a sibling from a flow

**Verified.** Deleting a fixed-width child from a flow is a cascade, not a
one-zone edit. Every container and flexible leaf in the surviving column grows
by the removed width; every fixed leaf to its right shifts by it; every
container's parent-minus-children gap stays at its baseline value. Removing a
659-unit sliver meant 15 zones: 12 `w +659` and 3 `x +659`. Write the cascade as
a table of `(zone id, attribute, old, new)`, apply each row as an exactly-once
substitution, and assert each once. A missed row shows in
`check_geometry.py --baseline` as a gap pair
(`zone 37 gap 659, zone 36 gap -659`).

## Adding a filter card

**Verified by render**: the card appeared in the strip with the strip's gap
unchanged, and every differing pixel between the two publishes lay inside the
strip. That picking a value filters the sheets is **Inferred**; a render cannot
click. Fragments are from the built file.

Three elements in each filtered sheet's `<view>`, each inserted before the
neighbour that will follow it (filters and column-instances are sorted by column
string, slices are not; [content-models.md](content-models.md)):

```xml
<filter class='categorical' column='[federated.…].[none:credit_type:nk]' filter-group='18'>
  <groupfilter function='level-members' level='[none:credit_type:nk]' user:ui-enumeration='all' user:ui-marker='enumerate' />
</filter>
<!-- under <datasource-dependencies> -->
<column-instance column='[credit_type]' derivation='None' name='[none:credit_type:nk]' pivot='key' type='nominal' />
<!-- under <slices> -->
<column>[federated.…].[none:credit_type:nk]</column>
```

`filter-group` is a workbook-wide integer: the fresh base's max plus one. Guard
"instance not yet referenced" per sheet, not per workbook; another sheet may
already use the same instance.

One zone in the strip; `param` carries the column instance and `name` any one of
the filtered sheets:

```xml
<zone h='6666' id='712' mode='checkdropdown' name='Y1 Schools - School Grade Distro' param='[federated.…].[none:credit_type:nk]' type-v2='filter' values='database' w='10980' x='88434' y='7556'>…</zone>
```

A strip with `layout-strategy-id='distribute-evenly'` does not re-solve its
stored geometry on Server. Re-tile every child by hand: each `w` is
`floor(inner / n)`, with one extra unit on `inner mod n` of the children, where
`inner` is the strip's `w` minus its baseline gap; each `x` is cumulative from
the strip's `x`. Nine children in a 98828-unit strip with gap 0 are eight at
10981 and one at 10980. Anything else fails the geometry check.

## Editing the right copy of the tree

**Verified.** A dashboard has a `<zones>` block and may have a `<devicelayouts>`
block containing its own copy of the same zone ids. Edit `<zones>`. A change
applied only to `<devicelayouts>` has no effect on the default layout, which is
what the render API shows. What phone or tablet viewers see was not probed; say
in the hand-over whether a `<devicelayouts>` block exists and that it was
untouched ([unverified-warnings.md](unverified-warnings.md)).
