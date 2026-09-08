# Cumulative GPA Monitor cards, captions and basis reminder

Refs [#5190](https://github.com/TEAMSchools/teamster/issues/5190).

## Problem

The Cumulative GPA Monitor is the only tab in the
`Academic & Gradebook Health Suite` with no titles and no captions. Every body
zone sets `show-title='false'`. A reader gets two rotated row labels, the words
`Grade Level`, and nothing else.

`GPA - Goal by school` is the worst case. It encodes four things and explains
none of them: bar length is the share of students at a 3.0 cumulative GPA or
above, the mark label is the gap to goal in percentage points, colour is at or
below goal, and the grey tick is that school's own goal.

The dashboard also hides which GPA basis a reader is looking at, and that is the
more dangerous gap. The `GPA basis` control switches between `Projected EOY` and
`On the books today`. Some panels follow it and some ignore it, with nothing on
screen marking the difference.

## The three-way split

Tracing `[Parameter 11]` through the calculations gives three groups, not two.
The reminder design follows from this split, so it is recorded here in full.

**Follows the switch.** `GPA - Dist by grade`, `GPA - Goal by grade`,
`GPA - Goal by school`, `GPA - BAN % 3.5+` and `GPA - BAN % 3.0+`. Each resolves
through `Calculation_0141679102236570168` (`Cum GPA (unweighted)`), which
branches on `[Parameters].[Parameter 11]`.

**Ignores the switch, always projected.** `GPA - BAN Below 3.0`,
`GPA - BAN Can reach`, `GPA - BAN Gap to goal` and `GPA - BAN Students needed`.
The first two read `cumulative_y1_gpa_unweighted` directly. The last two also
compare against `gpa_goal_proportion_org`, or `gpa_goal_proportion_region` when
`[Parameter 3]` is not `"All"`.

**Ignores the switch, shows both.** `GPA - Dist on the books` and
`GPA - Dist projected` render on-the-books and projected figures as two rows of
one panel, whatever the switch is set to.

A reader who sets the basis to `On the books today` therefore sees four numbers
and one panel that did not change, and the dashboard says nothing about it.

## The pattern being copied

Academic Health Home and Academic Health Schools already solve the titling
problem, and they solve it the same way. Three reusable pieces:

- **Card.** A container with `border-style` `solid`, `border-color` `#001e62`,
  `border-width` 1 and `margin` 5.
- **Header strip.** The card's first child: a horizontal `layout-flow` with
  `background-color` `#e6e6e6`, holding a text zone plus whichever legend or
  parameter control belongs to that chart.
- **Section label.** Bare text in `Tableau Semibold` `#001e62`, sitting above a
  card rather than inside it.

The text zone pairs a bold title with an 8 point italic caption:

```xml
<run bold='true' fontcolor='#000000' fontname='Arial'>Y1 Weighted GPA by School</run>
<run>Æ&#10;</run>
<run fontcolor='#000000' fontname='Arial' fontsize='8' italic='true'>What % of students have a GPA of ≥ 3.0?</run>
```

One card can hold several header-and-chart pairs. Academic Health Home zone 63
holds two. Copying that nesting, rather than giving every chart its own border,
is what makes the pixel budget work.

## Design

### Structure

Four cards:

1. **Headline.** The four big numbers, in one bordered card.
2. **Goal strip.** The `Progress against the goal` label and its two numbers.
3. **Body left.** Header strip, then `GPA - Dist on the books` and
   `GPA - Dist projected`; header strip carrying the GPA band legend, then
   `GPA - Dist by grade`.
4. **Body right.** Header strip, then `GPA - Goal by grade`; header strip, then
   `GPA - Goal by school`.

The standalone GPA band legend zone is absorbed into card 3's second header
strip, where Academic Health docks its own legends. That removes a floating
element and frees 38 pixels.

Two fixes ride along. The dashboard's outer `layout-basic` zone has no margin,
unlike Academic Health Home's `margin` of 8, which is why the title clips
against the top edge. The controls strip gets `background-color` `#f5f5f5` to
match Academic Health Home.

### The basis reminder

A dashboard text zone is dead text and cannot resolve a parameter. Live basis
text has to come from a parameter control, a worksheet title or caption, or a
mark label. This design uses the last two.

The six big-number sheets already build their text in `<customized-label>` with
a CDATA-wrapped placeholder, so the mechanism is proven live in this workbook:

```xml
<run fontcolor='#001e62' fontname='Tableau Semibold' fontsize='30'><![CDATA[<[federated.0n798br073i5kb170j6l90uiv50a].[usr:Calculation_4645249709926099321:qk]>]]></run>
```

Two of them already carry a fixed basis line between the label and the number:

```xml
<run fontcolor='#8c8c8c' fontname='Tableau Light' fontsize='10'>Always projected</run>
```

Every basis line in this design reuses that exact formatting, so `Tableau Light`
10 in `#8c8c8c` means "which basis you are looking at" everywhere on the
dashboard, whether a mark label or a sheet title renders it.

**Live.** `GPA - BAN % 3.5+` and `GPA - BAN % 3.0+` gain the placeholder as
their middle line, in the slot the other two BANs already use. All four then
share one structure: label, basis, number. `GPA - Dist by grade`,
`GPA - Goal by grade` and `GPA - Goal by school` carry the same line as a
worksheet title, top left, under the header strip.

**Fixed.** `GPA - BAN Gap to goal` and `GPA - BAN Students needed` already say
`— always projected`, but inline in the 13 point label where it runs long. Split
it onto its own line in the standard grey. Card 3's first header strip states in
its caption that the panel shows both bases.

`GPA - Dist by grade` cannot use a native axis title, because its value axis
sets `display='false'`. The other two charts do render a default `% at 3.0+`
axis title, but one runs up the left edge and the other along the bottom.
Worksheet titles put the reminder in the same place on all three, which is what
makes it read as a convention rather than three separate notes.

### Caption copy

Each row below is one header strip, named by its card and its position in that
card.

| Header strip   | Title                        | Caption                                                                                                      |
| -------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Card 2 label   | Progress against the goal    | Always projected, against the network goal — or the selected region's goal.                                  |
| Card 3, first  | Band mix, network            | On the books today above, projected to year end below. This panel shows both, whatever the switch is set to. |
| Card 3, second | Band mix by grade            | The same bands, split by grade.                                                                              |
| Card 4, first  | % at 3.0+ by grade           | Share of students at a 3.0 cumulative or better. The grey tick is the network goal for that grade.           |
| Card 4, second | Gap to goal, school by grade | Bar length is % at 3.0+; the label is the gap in points; the grey tick is that school's own goal.            |

`GPA - Title`'s caption currently hedges with "Projected end-of-year unless the
basis switch is set to on the books today". Once every panel states its own
basis, that sentence can go.

### Colour

A reviewer asked for the met and not-met colours to match the Gradebook Fidelity
dashboard. Doing that also fixes a collision. The goal bars currently use
`#2f5fc4` and `#d8342f`, which are also the `3.0-3.49` and `below 2.0` band
colours in the stacked charts directly above them, so blue and red each carry
two meanings on one screen.

Edit the map on `Calculation_7236501339153214575` only:

| Member           | Now       | New       |
| ---------------- | --------- | --------- |
| At or above goal | `#2f5fc4` | `#12a47c` |
| Below goal       | `#d8342f` | `#b3161c` |
| Not yet measured | `#b6c0cf` | unchanged |
| null             | `#edc948` | unchanged |

The new pair matches `Calculation_1052997927364395018` (`Cell state`) on the
fidelity dashboard. `#b6c0cf` stays even though it is also the `2.5-2.99` band
grey, because a neutral meaning "no data" reads the same in both places.

That encoding colours three sheets, not two: `GPA - Goal by grade`,
`GPA - Goal by school` and `GPA - BAN Gap to goal`. The goal strip's headline
number therefore turns green at goal and red when short, which was not part of
the original request but keeps the strip consistent with the panels below it.

Academic Health Home's twin calculation, `Calculation_4005670422418128910`,
stays on blue and red. The two tabs will show the same concept in different
colours until someone decides otherwise.

Green and red separate mainly by hue, so they are the harder pair for red-green
colour blindness, where the current blue and red are safer. `#12a47c` leans teal
enough to survive most simulations, and the bars carry signed point labels
either way. The owner chose this pair knowing that.

## Pixel budget

The canvas is 1366 by 900 with `sizing-mode="fixed"`, and it is allocated to the
last pixel today: title 60, controls 68, headline 138, goal strip 78, body 556.
Body left holds 86, 86, 38 and 330. Body right holds 141 and 399.

Four header strips and three worksheet titles have to come from somewhere:

- The band legend zone folds into a header strip: 38 pixels.
- The two single-row bars go from 86 to 62 pixels each. They are single bars.
- Goal strip goes from 78 to 66 pixels.
- `GPA - Goal by school` goes from 399 to 360 pixels. Twelve rows at 30 pixels
  each; the Academic Health equivalent runs nine rows at 20 and reads fine.
- `GPA - Goal by grade` goes from 141 to 120 pixels.
- `GPA - Dist by grade` gains, 330 to 356 pixels.

The visible cost concentrates in the school panel, and it is smaller than it
first looked. Reconciling each flow container's children against its parent
during planning showed that folding the standalone legend into a header strip
frees more than the four strips cost, so the by-grade chart grows rather than
shrinking. The build's check is that each flow container's children sum to the
parent and the whole dashboard sums to 100000 units.

## Build order

The order is deliberate: the unproven thing first, then content, then geometry.

**Step 0. Re-pull production.** Not the copy on disk. The owner published
revision 3.0 at 14:39 on 2026-09-08, adding a cross-datasource School filter
(`filter-group='17'`) to 17 sheets. Building on an older base destroys it.
Record the revision and diff the worksheet and parameter lists against the base.

**Step 1. Probe the placeholder.** The parameter token
`<![CDATA[<[Parameters].[Parameter 11]>]]>` is inferred from the field and
built-in placeholder syntax already in the file. No parameter placeholder exists
in this workbook yet. Change one title, publish to `GPA-monitor-temp`, render at
both parameter values through the render API, and read the text back. If it does
not resolve, stop and report. Fallbacks, in order: the caption-style syntax,
then native axis titles for the two goal panels with a badge worksheet for the
third, then fixed text.

**Step 2. Colour.** Four values in one encoding map.

**Step 3. Reminders.** Six `<customized-label>` edits and three worksheet
titles. No zone moves yet, so the whole content layer is renderable and readable
before any geometry changes.

**Step 4. Structure.** The re-parenting, last, so a layout break bisects cleanly
instead of hiding behind a text bug.

## Verification

- `check_twb.py` and an XML parse after every script. It covers worksheet
  `simple-id`, `<view>` and `<aggregation>`, element-versus-manifest feature
  declarations, and manifest entries dropped against `--ref`.
- Colour: sample pixels from the render and assert `#12a47c` and `#b3161c` are
  present and `#2f5fc4` and `#d8342f` are absent from that panel. Not by eye.
- Reminders: render at both parameter values, assert both strings appear and
  that they differ.
- Structure: assert geometry programmatically. No sibling overlap, every flow
  container's children summing to the parent, total 100000. No existing checker
  does this, and it is what would have caught the rollup overlay on 2026-09-08.
- Merge check: worksheet list and parameter list diffed against the step 0 pull,
  and the School filter confirmed on all 17 sheets.

## Constraints

Never publish to the `Production` project. The deliverable is a `.twbx` plus a
review copy in `GPA-monitor-temp` (`c74d8e08-b856-4430-a759-ebacb061e376`) for
the owner to publish. Publish with the extract included and tabs visible.

Insert into `<document-format-change-manifest>`, never rebuild it. A regex
rebuild on 2026-09-08 silently dropped a dotted entry and broke the extract.

The paragraph break inside `<formatted-text>` is the literal run
`<run>Æ&#10;</run>`, 235 of them in the file, and it must be byte-exact. The
file uses CRLF line endings.

A zone at the wrong nesting level is valid XML that renders overlapping, and no
schema check catches it.

## Out of scope

Academic Health Home's goal colours. The dashed cumulative reference line, which
the owner is doing by hand. Any change to the underlying dbt models.
