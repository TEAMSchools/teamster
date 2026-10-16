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

**Follows the switch, wholly.** `GPA - Dist by grade` — bars, mark labels and
the `GPA band` colour encoding all resolve through
`Calculation_0141679102236570168` (`Cum GPA (unweighted)`), which branches on
`[Parameters].[Parameter 11]`. `GPA - BAN % 3.5+` and `GPA - BAN % 3.0+` do the
same.

**Follows the switch in part.** `GPA - Goal by grade` and `GPA - Goal by school`
each encode three things — bar length, mark label, colour — and not every
encoding is parameter-aware. On `GPA - Goal by grade`, bar length and the mark
label both resolve through `Calculation_0141679102236570168`; only the colour,
`Calculation_7236501339153214575` (`Goal status`), is built on
`Calculation_9485136151529756033` / `Calculation_4693780698737655073`, a
projected-only pair. On `GPA - Goal by school`, only the bar length,
`Calculation_9335003396903351453` (`% at 3.0+`), is parameter-aware. Both the
mark label, `Calculation_3466859908724272046` (`Gap to goal (pts)`), and the
colour — the same `Goal status` calc — are built on that same projected-only
pair. Setting the basis to `On the books today` therefore moves the bars on both
panels while their gap labels and colours stay projected, which is what produces
a near-zero-length bar carrying a label like `+11.4pp` in green.

**Ignores the switch, always projected.** `GPA - BAN Below 3.0`,
`GPA - BAN Can reach`, `GPA - BAN Gap to goal` and `GPA - BAN Students needed`.
The first two read `cumulative_y1_gpa_unweighted` directly. The last two also
compare against `gpa_goal_proportion_org`, or `gpa_goal_proportion_region` when
`[Parameter 3]` is not `"All"`.

**Ignores the switch, shows both.** `GPA - Dist on the books` and
`GPA - Dist projected` render on-the-books and projected figures as two rows of
one panel, whatever the switch is set to.

A reader who sets the basis to `On the books today` therefore sees four numbers
and one panel that do not change, two panels whose bars move while their labels
and colour stay projected, and the dashboard says nothing about any of it.

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

**Live.** The plan was for `GPA - BAN % 3.5+` and `GPA - BAN % 3.0+` to gain the
placeholder as their middle line, in the slot the other two BANs already use, so
all four would share one structure: label, basis, number. That failed twice. A
`<[Parameters].…>` token renders blank inside a mark label. Routing the
parameter through a calculation on the Text shelf was worse — it blanked the
whole label, title and number included, not just the basis line. The
worksheet-title route is the only one that resolves a parameter in this
workbook. `GPA - BAN % 3.5+` and `GPA - BAN % 3.0+` ship with static text,
`Follows the GPA basis`, in the same run style and position instead.
`GPA - Dist by grade`, `GPA - Goal by grade` and `GPA - Goal by school` carry
the live placeholder as a worksheet title, top left, under the header strip —
that route works, which is why those three keep it.

**Fixed.** `GPA - BAN Gap to goal` and `GPA - BAN Students needed` already say
`— always projected`, inline in the 13 point label where it runs long. The plan
called for splitting it onto its own line in the standard grey; that rendered
the number as `####` in both BANs — three lines do not fit the box at this size
— so the build reverted to production's inline form, which is what ships. Card
3's first header strip states in its caption that the panel shows both bases.

**Left alone.** The row labels ship as `Actual` / `Projected`, a different
vocabulary from the parameter's own `On the books today` / `Projected EOY` —
three names for two states. That inconsistency stands on purpose: lengthening
either row label to match the parameter's wording caused a mid-word wrap defect
that cost two fix rounds, and the card caption directly above already explains
what the rows are.

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
| Card 4, first  | % at 3.0+ by grade           | Share at a 3.0 cumulative or better. Tick is the grade's network goal. Colour always projected.              |
| Card 4, second | Gap to goal, school by grade | Bar is % at 3.0+, follows the basis. Label and colour always projected. Tick is the school goal.             |

Header strips clip their caption with an ellipsis rather than wrapping it, so
caption length is a hard constraint and not a matter of taste. The budget scales
with the strip's width. Measured from renders: at 39676 units, captions of 97
and 96 characters render in full while 129 and 142 clip; at 58565 units, 108
characters render in full. `assert_cum_cards.py` enforces `97 * width / 39676`,
which is deliberately conservative — a caption that fails it may still fit, so
the response to a failure is to render and look, never to raise the constant.

No structural check can see this. It cost a round: the first attempt at the two
`Card 4` captions above stated the always-projected caveat correctly and at 129
and 142 characters, and both truncated mid-sentence on screen.

`GPA - Title`'s caption hedged with "Projected end-of-year unless the basis
switch is set to on the books today". Every panel now states its own basis, so
that sentence was removed.

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

- The band legend zone folds into strip 810, which needs 70 pixels to render all
  five legend entries — not the 40 pixels a plain header strip costs.
- The two single-row bars go from 86 to 74 pixels each, not the planned 62.
- Goal strip goes from 78 to 80 pixels — it grew, not the planned shrink to 66.
- `GPA - Goal by school` goes from 399 to 360 pixels. Twelve rows at 30 pixels
  each; the Academic Health equivalent runs nine rows at 20 and reads fine.
- `GPA - Goal by grade` goes from 141 to 120 pixels.
- `GPA - Dist by grade` loses height, 330 to 302 pixels, rather than the planned
  gain to 356.
- The headline card also shrank, 138 to 116 pixels, a change nothing in this
  design called for.

The planned savings did not hold. The legend's own strip costs as much as a
plain strip plus what the legend itself needs, and the goal strip grew instead
of shrinking. What actually freed the room for the body to grow from 556 to 576
pixels was the headline card's unplanned 22 pixel loss, offset by 2 pixels back
into the goal strip — not the legend fold. `GPA - Dist by grade` ends up
smaller, not larger, because strip 810 and the two single-row bars above it in
body left consumed more of the column's share than planned. The build's check —
that each flow container's children sum to the parent and the whole dashboard
sums to 100000 units — held throughout; it confirms internal consistency, not
that the plan's pixel predictions did.

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
