# Landing page render notes (Task 9)

Two kinds of check. The numeric ones were run against the data API and are
settled below. The visual ones could not be run by the agent: the output hook
redacts every PNG and JPG at any size, so no render or crop ever reaches the
model. The crops exist on disk for the user to open.

## Checked by data

Source: a throwaway probe copy of the workbook published to `GPA-monitor-temp`
with the four tiles, the four strips and the five source BAN sheets as live
views, each sheet's CSV pulled at default parameters (`p_Region` = `All`), then
the probe deleted. Full tables in `numbers.md`.

### Tile vs source BAN

| Measure                  | Tile sheet                                                    | Tile value  | Source sheet                                          | Source value | Equal |
| ------------------------ | ------------------------------------------------------------- | ----------- | ----------------------------------------------------- | ------------ | ----- |
| % Y1 GPA at or above 3.0 | `LP - Tile Y1 GPA`                                            | 69%         | `Y1 Landing - BAN Network ≥3.0`                       | 69%          | yes   |
| % Y1 Failing 2 or more   | `LP - Tile Course Failures`                                   | 8%          | `Y1 Landing - BAN Network Failing ≥2`                 | 8%           | yes   |
| % at 3.0+                | `LP - Tile Cumulative GPA`                                    | 0.484261501 | `GPA - BAN % 3.0+`                                    | 0.484261501  | yes   |
| % healthy                | `LP - Tile Gradebook Health`                                  | 15%         | `BAN Network`                                         | 15%          | yes   |
| Students still needed    | `LP - Tile Cumulative GPA` (`LP Students still needed (org)`) | 0           | `GPA - BAN Students needed` (`Students still needed`) | 0            | yes   |

All five equal as parsed numbers, not as formatted text. Two caveats worth
carrying forward:

- The shortfall pair is `0` on both sides because the org is currently above
  goal (measured 413, at 3.0+ 200 = 48.4% against a 45% goal proportion). Zero
  equals zero, so the comparison passes, but it does not exercise the arithmetic
  of `LP Students still needed (org)`. Re-check it when the org sits below goal,
  or with `p_Region` set to a region that is.
- `% at 3.0+` exports unformatted (`0.484261501`) on both the tile and the BAN,
  while the other three export percent-formatted. That is a field-format
  difference inherited from the clone source, identical on both sides, so it is
  not a defect in the tile — but it does mean the tile's on-screen text depends
  on the mark label's own format, which only the crop can confirm.

### Region strips

| Strip sheet                   | Regions                  | Values                                 |
| ----------------------------- | ------------------------ | -------------------------------------- |
| `LP - Strip Y1 GPA`           | Camden, Newark, Paterson | Camden 58%; Newark 74%; Paterson 52%   |
| `LP - Strip Course Failures`  | Camden, Newark, Paterson | Camden 16%; Newark 6%; Paterson 4%     |
| `LP - Strip Cumulative GPA`   | Camden, Newark           | Camden 0.484848485; Newark 0.484076433 |
| `LP - Strip Gradebook Health` | Camden, Newark, Paterson | Camden 3%; Newark 20%; Paterson 6%     |

The three MS/HS strips carry the same three regions; the cumulative strip is a
strict subset of them (no Paterson high school). Row alignment across the four
columns is therefore structurally sound in three of four columns and short by
one row in the fourth.

### Strip construction decision

The four-sheet construction stands. The twelve-clone fallback in the spec is not
implemented in this task. The cumulative column will show a blank Paterson row
only if Tableau pads the axis to the other columns' row count; whether it does
is a pixel question, and the user's reading of `crop-strip.png` decides it. If
that crop shows the cumulative column's rows sliding up against the other three,
the controller reopens the fallback.

## For the user's eyes

Every item below is unverified. Open the named file in
`/workspaces/teamster/.claude/scratch/tableau/lp/`.

| Check                                                                                             | Open                                  |
| ------------------------------------------------------------------------------------------------- | ------------------------------------- |
| `####` in any of the four network tiles                                                           | `crop-tiles.png`                      |
| Clipped or ellipsised text in any nav card                                                        | `crop-cards.png`                      |
| A blank line where a title or caption belongs (a zone missing `show-title='true'`)                | every crop                            |
| A literal `[federated` or `[Parameters]` token anywhere on the page                               | every crop                            |
| Two zones overlapping                                                                             | `render-landing-page.png` (full page) |
| Strip rows aligned across the four columns, and what the cumulative column does opposite Paterson | `crop-strip.png`                      |
| The Q1 render's two Y1 tile titles reading `Q1`                                                   | `render-landing-q1.png`               |
| Courier grid alignment in the definitions block                                                   | `crop-definitions.png`                |
| The 130 px year control rendering at its intended width                                           | `crop-header.png`                     |
| The 120 px button captions fitting their buttons                                                  | `crop-links.png`                      |
| Coverage-line text and its wrap                                                                   | `crop-coverage.png`                   |

Two behaviours no still image can answer; they need the live review copy
(`review_luid` in `review-meta.txt`, opened in a browser):

- Hovering a guide slot shows no tooltip.
- The `tabdoc:goto-sheet` buttons and the `nav-action` clicks land on the right
  tabs.

## Crop sizes

Source render `render-landing-page.png` is 2732 x 3000, i.e. exactly 2x the 1366
x 1500 design grid `crop_lp.py` assumes, so each box scales cleanly.

| File                   | Size (px)  | Bytes  |
| ---------------------- | ---------- | ------ |
| `crop-header.png`      | 2732 x 192 | 57939  |
| `crop-tiles.png`       | 2732 x 456 | 85641  |
| `crop-strip.png`       | 2732 x 356 | 88538  |
| `crop-cards.png`       | 2732 x 476 | 176788 |
| `crop-definitions.png` | 2732 x 816 | 249039 |
| `crop-coverage.png`    | 2732 x 456 | 54834  |
| `crop-links.png`       | 2732 x 344 | 13064  |

## Render path restored (2026-09-10, after commit 574ee50d2)

The output scanner now skips the base64 carrier of image blocks. Both paths
verified: `Read` on a stored PNG and `mcp__tableau__get-view-image` on the
review copy return pixels. A fresh 1366x1500 render of the review copy's Landing
Page is identical to the 17:56 stored render, so everything below is current,
and none of it was visible to the CSV checks in `numbers.md`.

What the render shows that the XML and CSV checks did not:

- All four tile numbers render as `####` overflow. Three of the four region
  strips (Y1 GPA, failures, healthy gradebooks) also overflow; the cumulative
  strip renders `48.5%` / `48.4%` correctly. The value is right in the CSV, so
  this is a label width or number-format problem in the text marks, not data.
- The healthy-gradebooks tile and strip carry a navy fill inherited from the
  Rollup sheets they were cloned from; region labels there are navy on navy.
- The cumulative tile and strip titles read `Grade Grade 11`: the title text
  already says `Grade` and the parameter value carries it too.
- The header title truncates to `Academic & Gradebook Health | Landi..` at the
  configured font size and width.
- The coverage grid renders in a serif monospace fallback (Courier-like); the
  font asked for is not on the server.

Lesson for the skill: a CSV-equals-source check proves the number, not the
pixel. Run a server render on every review-copy publish and read it.

## 2026-09-10 render-fix round: all four defects closed

Base is production **revision 26** (2026-09-10 20:02:27 UTC), which already
contained the landing page — the owner published the review copy to production
before the defects were fixed. `fix_lp.py` patches that base; `build_lp.py` is
historical from here, because it adds a page to a workbook that has none.

Two publish-and-render rounds. Review copy
`55cac48f-15d0-4048-b219-bb8dfbf39700` in GPA-monitor-temp, rendered through
`get-view-image` and read as cropped JPEGs.

| #   | Defect                                  | Fix                                                                                                                                                                                         | Confirmed on render |
| --- | --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------- |
| 1   | `####` on 4 tiles and 3 strips          | shorter label stacks: two trend lines dropped from the Y1 and failures tiles, 30 pt -> 22 pt and 42 pt -> 24 pt values, headings 13 pt -> 11 pt, strips reduced to a single 12 pt value run | round 1             |
| 1b  | tiles read `of students`, count missing | the denominator instance was on Tooltip only; added a `<text>` encoding                                                                                                                     | round 2             |
| 2   | navy healthy-gradebooks tile and strip  | dropped the inherited `element='table'` navy background and ruling 12's white `element='header'` rule; recoloured every `#ffffff` run to the navy-on-white palette                          | round 1             |
| 3   | `Grade Grade 11`                        | dropped the literal `Grade ` before `[Parameters].[Parameter 10]`, whose aliases already read `Grade 11`                                                                                    | round 1             |
| 4   | header clipped to `Landi..`             | title runs 16 pt -> 12 pt (14 pt still clipped to `Landing P..` in round 1)                                                                                                                 | round 2             |

Values read off the round-2 render, all matching the regenerated `numbers.md`:

- Tiles: 69%, 8%, 48.4%, 14%; `of 5,275 students`, `of 5,322 students`,
  `0 students still needed (projected)`, `52 of 363 teachers`.
- Strips: Y1 GPA Camden 58% / Newark 74% / Paterson 52%; failures 16% / 6% / 4%;
  cumulative Camden 48.5% / Newark 48.4%; healthy gradebooks 3% / 19% / 6%.

`numbers.md` was regenerated against revision 26 on a fresh PROBE copy (deleted
afterwards): all five tile-vs-source pairs equal. Two values moved from the
2026-09-10 18:19 table because the extract refreshed with the owner's publish —
`% healthy` 15% -> 14%, gradebook strip Newark 20% -> 19% — on both sides, so
the equalities hold.

### Still not verified by this round

- **Desktop opens the package.** Only the owner opening `final.twbx` proves it;
  Server accepted the publish, which proves nothing about Desktop.
- **Hover and click.** Tooltips on the guide slots, the `tabdoc:goto-sheet`
  buttons and the nav actions still need a human in the live review copy.
- **The coverage grid's serif fallback.** Unchanged and still cosmetic: the
  requested monospace font is not installed on the server.
- **The shortfall calc's nonzero branch.** Still 0 == 0 (org above goal), so
  still unexercised; parked in #5247 per ruling 16.

## 2026-09-10 layout round: header, roster links, reference blocks

Three changes requested after reviewing the fixed render, all confirmed on a
server render of the review copy.

| Change                 | Was                                                               | Now                                                                              |
| ---------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| header nav buttons     | five `tabdoc:goto-sheet` buttons, duplicating the tab cards below | removed; the cards are the only navigation                                       |
| GPA Roster links       | a `Links` row at the foot of the page                             | a `Roster links` container in the header, the same idiom as the other four views |
| definitions + coverage | two full-width blocks stacked, 27200 + 15200 units                | one `Reference` horizontal container, two columns                                |

The freed header width also retired the round-2 font fix for defect 4. The title
was cut to 12 pt only because 29059 units (~397 px) could not hold it at 16 pt;
with the buttons gone the zone is 60980 units (~832 px) and the title is back at
its design size of 16 pt, untruncated.

Zone tree after the change, all flow containers closing exactly:

```text
46 vert                                   h=98934
  9  [Header] horz          fixed=80      h=5333
     1  bitmap logo         fixed=167     w=12811
     2  LP - Title                        w=60980
     3  paramctrl P2        fixed=130     w=10103
     50 [Roster links] vert fixed=204     w=14934
        51 text label       fixed=22      h=2000
        52 horz                           h=3333
           53/54/55  Links - GPA Roster - Newark / Camden / Paterson
  14 [Tiles] horz           fixed=220     h=14667
  19 [Regions] horz         fixed=150     h=10000
  20 Miami footnote         fixed=20      h=1866
  36 [Directory] horz       fixed=220     h=14667
  60 [Reference] horz       fixed=696     h=46400
     61 vert                fixed=780     w=57721
        37 definitions      fixed=380     h=25867
        62 empty                          h=20533
     63 vert                              w=41107
        38 coverage grid    fixed=199     h=13800
        64 empty                          h=32600
  45 empty                                h=6001
```

The two-pass part was the reference container: see the lessons entry on text
zones centring their content vertically. The first attempt put both text zones
straight into the horizontal container and they rendered floating in the middle
of it, out of line with each other.

### Left over

About 290 px of blank sits below the reference blocks now that the Links row is
gone and the two text blocks share a row. The page is a fixed 1366x1500 canvas,
so shortening it means recomputing every vertical unit against a new canvas
height — not done, and not necessary for correctness. Two ways to spend that
space instead if wanted: raise the dashboard's fixed height down to about 1210
px, or give the region strips their second line back (the weekly delta and the
teacher denominator, dropped in the `####` fix because a 3-row band at 150 px
could not hold two lines).

## 2026-09-10 shrink round: 60 px header, inline deltas, 1130 px canvas

| Change                       | Was                       | Now                                                          |
| ---------------------------- | ------------------------- | ------------------------------------------------------------ |
| header height                | 80 px                     | 60 px                                                        |
| strip detail (delta / count) | dropped in the `####` fix | inline at 8 pt to the right of the value, on all four strips |
| canvas height                | 1500 px                   | **1130 px**                                                  |

The strip detail came back because the `####` constraint was only ever vertical.
A 12 pt value over an 8 pt line does not fit a ~43 px row band; the same pair
side by side occupies about 130 px of a 337 px column. All four strips now read
like `58%  (-9.4pp vs. 1 wk)`, `3%  3 of 95 teachers`,
`48.5%  0 still needed (region goal)`.

One wording bug surfaced by making that text visible again: the gradebook strip
said `of <field> teachers` while the field already returns `52 of 363`, so it
rendered `3% of 3 of 95 teachers`. Corrected to match the tile.

### Canvas arithmetic

Zone units are 1/100000 of the canvas, so shortening it rewrites nothing by
itself and silently invalidates every `fixed-size`. `relayout_vertical` declares
the layout in pixels and regenerates every vertical `y`/`h`:

| Row             | px  | units (1130 canvas) |
| --------------- | --- | ------------------- |
| outer margin    | 8   | 708                 |
| Header          | 60  | 5310                |
| Tiles           | 220 | 19469               |
| Regions         | 150 | 13274               |
| Miami footnote  | 28  | 2478                |
| Directory       | 220 | 19469               |
| Reference       | 420 | 37168               |
| trailing spacer | 16  | 1416                |

Two passes on the Reference height. At 372 px the definitions block clipped — 21
lines of mixed 9 pt and 11 pt text, which measures about 347 px but does not fit
a 364 px content box. Tableau marked the cut with a trailing ellipsis after
`school in the GPA goals source…` and still left visible space below it, because
it drops whole lines. 420 px fits, with the closing `Can still reach 3.0` line
present and no ellipsis.

### Values on the render, unchanged

Tiles 69%, 8%, 48.4%, 14%; strips 58/74/52, 16/6/4, 48.5/48.4, 3/19/6 — the same
values `numbers.md` records against production revision 26. No calculation,
field or filter changed this round, only label composition and geometry.

## 2026-09-10 guide links

The Gradebook School Rollup and Gradebook Teacher View cards now link to the
published help article. Both point at the same guide, which covers the two tabs
together:
`https://teamschools.zendesk.com/hc/en-us/articles/43377104764567-Gradebook-Health-Dashboard-Guide`

Each slot reads `Help guide: Gradebook Health Dashboard Guide`, with the article
name underlined in the workbook's link blue (`#57c0e9`, the same treatment as
the GPA Roster links). Confirmed on a render. The other three cards still read
`Help guide: coming soon`.

**Not verified:** that the links open. A URL action fires on click and no render
can show a click, so this needs a human on the live review copy.

## 2026-09-11 Desktop refusal, fixed

The owner's Desktop open of `final.twbx` failed with D2E8DA72 on two sheets:
`element 'panes' is not allowed for content model '(view,style,panes,...)'`. The
D2 fix had deleted the whole `<style>` element from `LP - Tile Gradebook Health`
and `LP - Strip Gradebook Health` rather than just the navy rule inside it, and
`style` is mandatory in that model. Both sheets now keep an empty `<style />`,
the form five other worksheets in this workbook already use.

Nothing visible changed: an absent `<style>` and an empty one render
identically, which is why Server published it and three review renders looked
correct. `check_twb.py` gained `check_table_model` so this class is caught by a
checker from now on; it is mutation-tested and the untouched base still passes
it.

**The review copy moved.** The publish script named copies with `date.today()`,
so the post-midnight rerun created a second workbook instead of overwriting. The
name is now pinned.

|                                |                                                                                                 |
| ------------------------------ | ----------------------------------------------------------------------------------------------- |
| Current review copy            | `ZZ-REVIEW 2026-09-11 AGHS landing page`                                                        |
| luid                           | `57eefdb3-df9d-495a-b784-abea68d27b72`                                                          |
| URL                            | `https://tableau.kipp.org/#/site/KIPPNJ/workbooks/9593`                                         |
| Stale copy to ignore or delete | `ZZ-REVIEW 2026-09-10 AGHS landing page`, workbook 9587 — still holds the file Desktop rejected |
