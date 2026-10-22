# Dashboard layout, zones and text fitting

Dashboard layout is a tree of `<zone>` elements inside `<dashboard><zones>`.
Everything here concerns that tree, how text fits inside it, and how a table
worksheet fills its cells and headers. All claims are **Verified** (observed in
a render or by measurement) unless marked.

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

## Pop-outs are hidden, and the geometry check skips hidden zones

**Verified.** A show/hide button opens a container whose zones all carry
`hidden-by-user='true'`: Tableau marks every zone in the subtree, not only the
container. `check_geometry.py` skips hidden zones, so a plain pass says nothing
about a pop-out. An overlap planted inside one passed the plain run and failed
with `--show`.

Every pop-out in the source workbook, 8 across 3 dashboards, is a floating zone
at the top level of `<zones>`, beside the full-canvas tiled root. A floating
zone overlaps the root by design, and so does any visible floating object: the
untouched base fails `Academic Health Schools` with
`overlap at top-level: zone 4 and zone 812` when run without a baseline. With
`--baseline`, an overlap the baseline also has prints as `also in baseline` and
does not count.

For each pop-out that contains an edited zone, run the checker again with
`--show` naming the pop-out's top-level container, the id in the button's
`<toggle-action>` (`zone-ids=[220]`):

```bash
uv run python docs/tableau-xml/scripts/check_geometry.py out.twb "Dashboard" --baseline base.twb --show 220
```

`--show` un-hides that zone and its subtree in both files. A pop-out the
baseline lacks has no baseline overlap to match, so its one overlap with the
root fails; confirm that is the only failure line.

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

## Table headers truncate with `..`

**Verified by render.** In a table with every field on Rows, the field labels
across the top rendered `Cumulative ..`, `Projected cu..` and `Student Sli..`.
None wrapped at `height-header` 34, and the workbook has no wrap format to copy.
Budget about 6.7 px per character at 1x for the default header font, then set
each field's `<format attr='width' field='…' value='…' />` to fit the label, or
shorten the label.

With `fit-width` zoom (`<viewpoint name='<sheet>'><zoom type='fit-width' />`
under the dashboard's `<window>`), keep the sum of the header widths within the
zone's width in pixels. When the sum exceeds it, every column narrows and more
labels truncate.

## Filling a table cell with colour

**Verified by render.** In a table with discrete rows and discrete columns,
`Square` marks stay square. At the default size, `size` 2 and `size` 5 they drew
smaller than the cell; with `marks-scaling-off`, `size` 60 and 300 overlapped
the rows above and below.

What fills a cell is a `Bar` on a fixed, hidden axis, the idiom in
`Your sections grid`:

- Columns: a constant header calc times a calc returning `0.5`, as
  `([ds].[none:<header calc>:nk] * [ds].[min:<half calc>:qk])`.
- `<mark class='Bar' />` with
  `<mark-sizing mark-sizing-setting='marks-scaling-off' />`.
- The axis fixed and hidden:

  ```xml
  <style-rule element='axis'>
    <encoding attr='space' class='0' field='[ds].[min:<half calc>:qk]' field-type='quantitative' max='0.55' min='-0.05' range-type='fixed' scope='cols' type='space' />
    <format attr='display' class='0' field='[ds].[min:<half calc>:qk]' scope='cols' value='false' />
  </style-rule>
  ```

- Zeroline, column gridlines and column `table-div` off (`stroke-size` 0,
  `line-visibility` off).
- `<format attr='display-field-labels' scope='cols' value='false' />` under
  `<style-rule element='worksheet'>`, which hides the header calc's field label.

The Bar's `size` sets its thickness against the row. `1.6` drew a pill about 70%
of the row height and shipped; `2.5` and `4` filled the whole cell, and 3 of the
4 label text colours disappeared.

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

## Editing the right copy of the tree

**Verified.** A dashboard has a `<zones>` block and may have a `<devicelayouts>`
block containing its own copy of the same zone ids. Edit `<zones>`. A change
applied only to `<devicelayouts>` has no effect on the default layout, which is
what the render API shows. What phone or tablet viewers see was not probed; say
in the hand-over whether a `<devicelayouts>` block exists and that it was
untouched ([unverified-warnings.md](unverified-warnings.md)).
