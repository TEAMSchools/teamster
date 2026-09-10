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
