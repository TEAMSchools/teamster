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
grain change is the intent. That Tooltip leaves the partition alone is
**Inferred**; the probe is in [unverified-warnings.md](unverified-warnings.md).

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

## Floating containers

**Verified** by a depth trace and by render. A floating zone is a top-level
child of `<zones>`, a sibling of the `layout-basic` root that follows it, not a
descendant. An assertion that expected the Tableau-authored floating container
under the root failed a correct file. A new floating panel goes after the last
top-level zone, before `</zones>`.

A container shown and hidden by dynamic zone visibility carries
`hidden-by-user='true'` on the zone **and on every descendant** in the saved
file. Copied that way, the panel rendered hidden at the parameter's `false` and
shown at `true`. The binding is a node pair in the existing `<datagraph>`: its
`dashboard-zone-visibility-node` names the zone id and a `dashboard-identifier`
that is the `<dashboard>` element's `<simple-id>`, not the `<window>`'s. The two
differ, and the render toggled only with the dashboard's.

`check_geometry.py --baseline` passed a dashboard carrying two floating
containers (one Tableau-authored, one added) and failed a one-zone mutant of the
same file, so floating siblings did not false-positive it in this corpus.

## Removing a sibling from a flow

**Verified.** Deleting a fixed-width child from a horizontal flow is a cascade,
not a one-zone edit. Removing a 659-unit sliver from the right of one row meant
widening 15 zones down the surviving column: 4 vertical containers, 5 rows and 3
flexible leaves each `w +659`, and 3 fixed right-hand leaves `x +659`, so that
every container's parent-minus-children gap kept its baseline value. Write the
cascade as a table of `(zone id, attribute, old, new)`, apply each row as an
exactly-once substitution, and assert each once. `check_geometry.py --baseline`
reports a missed row as a gap pair (`zone 37 gap 659, zone 36 gap -659`).

## Adding a filter card

**Verified by render**: the card appeared in the strip with the strip's gap
unchanged, and every differing pixel between the two publishes lay inside the
strip. That picking a value filters the sheets is **Inferred**; a render cannot
click.

A dashboard filter card is three elements per filtered sheet plus one zone:

- In each sheet's `<view>`: a
  `<filter class='categorical' column='…' filter-group='N'>` holding a
  `level-members` groupfilter, a `<column-instance>` in that sheet's
  `<datasource-dependencies>`, and a `<column>` in `<slices>`. Filters and
  column-instances are sorted, slices are not
  ([content-models.md](content-models.md)); anchor each insert on the neighbour
  that will follow it rather than computing a sort.
- `filter-group` is a workbook-wide integer: the fresh base's max plus one.
- One `type-v2='filter'` zone whose `name` is any one of the filtered sheets.
- Guard "instance not yet referenced" per sheet, not per workbook: another sheet
  may already use the same instance legitimately.

A `distribute-evenly` strip does not re-solve its stored geometry on Server.
Adding a ninth child means re-tiling every child's `w` and `x` by hand
(`8 × 10981 + 10980 = 98828` across the strip) or the geometry check fails.

## Editing the right copy of the tree

**Verified.** A dashboard has a `<zones>` block and may have a `<devicelayouts>`
block containing its own copy of the same zone ids. Edit `<zones>`. A change
applied only to `<devicelayouts>` has no effect on the default layout, which is
what the render API shows. What phone or tablet viewers see was not probed; say
in the hand-over whether a `<devicelayouts>` block exists and that it was
untouched ([unverified-warnings.md](unverified-warnings.md)).
