# Landing page hand-off: Academic & Gradebook Health Suite

## What was built

A new `Landing Page` dashboard was added to the Academic & Gradebook Health
Suite workbook, built by editing the workbook's `.twb` XML rather than in
Desktop. It carries a header with the academic-year control and five navigation
buttons, four network tiles, a four-column region strip with a Miami footnote,
five tab cards with help-guide slots, a definitions block, a coverage grid, and
the three GPA roster links.

## The review copy

A review copy is published for you to click through. Nothing was published to
Production.

| Item         | Value                                                   |
| ------------ | ------------------------------------------------------- |
| Name         | `ZZ-REVIEW 2026-09-10 AGHS landing page`                |
| Workbook id  | `55cac48f-15d0-4048-b219-bb8dfbf39700`                  |
| URL          | `https://tableau.kipp.org/#/site/KIPPNJ/workbooks/9587` |
| Project      | `GPA-monitor-temp`                                      |
| Default view | `Landing Page` (verified after publish)                 |

It opens on `Landing Page`: the server reported that view as the workbook's
default after the publish, so this is verified rather than assumed. Six views
are live on the review copy:

- `Academic Health Home`
- `Academic Health Schools`
- `Cumulative GPA Monitor`
- `Gradebook School Rollup`
- `Gradebook Teacher View`
- `Landing Page`

Ten further sheets are published hidden, the same set the production workbook
hides.

## The package to publish

The file to open in Desktop and publish is:

```text
/workspaces/teamster/.claude/scratch/tableau/lp/final.twbx
```

It is 28,390,025 bytes. Two things were checked on it. The packaged `.twb`
equals the edited `out.twb` byte for byte, so nothing was translated on the way
into the zip and no bare LF line endings survive. And every other entry in the
package — the extract and the images — matches the production donor `.twbx` by
CRC, one for one. Only the `.twb` entry differs.

## Production

The production workbook was at revision 25 before any of this work, and it is
still at revision 25. Nothing in this build touched it.

Publishing to Production is your action, not the agent's. So is any rollback: a
rollback is itself a production publish, and it stays with you.

## The numbers

Every tile was read against the BAN it clones, on a throwaway probe copy, with
every parameter left at its default: `p_Region` = `All`, `Grade view` = `11`,
`GPA basis` = `Projected EOY`, `Health basis` = `Excluding comments`,
`p_Marking_Period` = `Y1`. The values are network aggregates; no student-level
data appears here or on the page.

| Measure                  | Tile sheet                   | Tile value                | Source sheet                          | Source value              | Equal |
| ------------------------ | ---------------------------- | ------------------------- | ------------------------------------- | ------------------------- | ----- |
| % Y1 GPA at or above 3.0 | `LP - Tile Y1 GPA`           | 69% (0.69)                | `Y1 Landing - BAN Network ≥3.0`       | 69% (0.69)                | yes   |
| % Y1 Failing 2 or more   | `LP - Tile Course Failures`  | 8% (0.08)                 | `Y1 Landing - BAN Network Failing ≥2` | 8% (0.08)                 | yes   |
| % at 3.0+                | `LP - Tile Cumulative GPA`   | 0.484261501 (0.484261501) | `GPA - BAN % 3.0+`                    | 0.484261501 (0.484261501) | yes   |
| % healthy                | `LP - Tile Gradebook Health` | 15% (0.15)                | `BAN Network`                         | 15% (0.15)                | yes   |
| Students still needed    | `LP - Tile Cumulative GPA`   | 0 (0.0)                   | `GPA - BAN Students needed`           | 0 (0.0)                   | yes   |

Region strips:

| Strip sheet                   | Regions                  | Values                                 |
| ----------------------------- | ------------------------ | -------------------------------------- |
| `LP - Strip Y1 GPA`           | Camden, Newark, Paterson | Camden=58%; Newark=74%; Paterson=52%   |
| `LP - Strip Course Failures`  | Camden, Newark, Paterson | Camden=16%; Newark=6%; Paterson=4%     |
| `LP - Strip Cumulative GPA`   | Camden, Newark           | Camden=0.484848485; Newark=0.484076433 |
| `LP - Strip Gradebook Health` | Camden, Newark, Paterson | Camden=3%; Newark=20%; Paterson=6%     |

The three MS/HS strips carry the same three regions. The cumulative strip
carries Camden and Newark only, a strict subset of the other three, because
Paterson has no high school.

The strip shipped as four worksheets side by side, one per source, each with
region on rows. The spec allowed a fallback — twelve small sheets, one per
region row per source, laid out as a grid — and it was not built. The cumulative
sheet has no Paterson row because Paterson has no high school, so if
`crop-strip.png` shows that column's rows sitting out of line with the other
three, that is the signal to rebuild the strip as the fallback grid.

## What is verified, and how

### Verified by data

All five tile-to-source comparisons above, read as parsed numbers rather than as
formatted text, and the region set behind each of the four strip columns.

### Verified by checkers

- `check_twb.py` — the edited `.twb` reports CLEAN against the content models
  the skill has attested.
- `check_geometry.py` — the new `Landing Page` zone tree checked on absolute
  bounds, and each of the five existing dashboards checked against the base as
  baseline. All six pass. All eleven flow containers sum exactly, with a gap of
  zero, verified by walking the parsed tree rather than by the checker's
  tolerance.
- `check_additive.py` — strips every addition the edit was allowed to make and
  requires the remainder to be byte-identical to the base. The final run
  stripped
  `{'worksheets': 19, 'dashboard': 1, 'dashboard-window': 1, 'sheet-windows': 19, 'nav-actions': 9, 'url-actions': 3, 'calcs': 3}`
  and the remainder matched. That is the proof that no existing dashboard,
  worksheet or action was altered.
- `repack.py` — zero bare LF, and the packaged `.twb` byte-identical to the
  source.
- Mutation proofs — each checker was run against a deliberately broken copy
  before it was trusted. `check_additive` was proved on a fixture that mutates
  an existing zone, and `check_geometry` on a mutant that opens a 24,707-unit
  gap in zone 14. Both fail on the mutant and pass on the control.

### Inferred, not verified

These are judgment calls the corpus does not settle. Each is a place to look
first if Desktop or the server objects.

- The navigation-button form. A button zone whose `<button>` carries
  `action='tabdoc:goto-sheet window-id="..."'` is present elsewhere in the
  suite, but no publish-and-click test in this project has confirmed it lands.
- The `nav-action` clicks on the tiles and cards, for the same reason. A render
  cannot click.
- `<repository-location>` is omitted from the new dashboard. Every existing
  dashboard has one, recording where Server last published it, but the new page
  has never been published, so there is no URL to write. If Desktop refuses the
  file with a dashboard content-model error, this element is the first thing to
  add back.
- The grouping of children inside `<actions>`. The base's grouping is consistent
  and the new actions follow it, but no recorded refusal message covers that
  element, so the evidence is a pattern rather than a rule.
- The flow-container `zone-style` with no background is written with the three
  border formats and no `margin` entry, matching the base's own containers. No
  content-model rule requires it.
- Wrapping in a tall text zone is unprobed, so every line break in the
  definitions block and the coverage grid is explicit and each rendered line is
  asserted to be at most 110 characters. Whether Tableau would have wrapped them
  acceptably is unknown.
- The strip values themselves. Only the region row set behind each of the four
  strip columns was checked. No strip value was compared against Home with
  `p_Region` set to each region in turn, nor against the Monitor at Camden and
  Newark, which is what the spec's verification list asks for.
- The shortfall calculation's nonzero branch. `LP Students still needed (org)`
  read 0 against a source that also read 0, because the org currently sits above
  goal, so the equality passed without exercising the arithmetic. To exercise
  it, in this order:
  1. Copy
     `docs/tableau-xml/lessons/2026-09-10-landing-page/scripts/test_zz_lp_numbers.py`
     back into `tests/`.
  2. Run `repack_probe.py` first. It builds the probe `.twbx` with the thirteen
     sheets unhidden, which is the only way a worksheet is queryable.
  3. Run the test once with `opts.parameter("Grade view", "9")` added to the CSV
     options, a grade that may sit below goal, and confirm the probe is deleted
     afterwards.

  This is an optional check, not a known defect.

- The region variant of the same calculation.
  `LP Students still needed (region)` read 0 for both Camden and Newark, so its
  arithmetic is exactly as unexercised as the org variant's, and the same re-run
  covers it.

## What only you can check

The visual checks below could not be run by the agent: the output hook redacts
every image, so no render or crop ever reached it. The crops are on disk in
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

And these, which no still image can answer.

### On the review copy in the browser

- Every button and every card click lands on the right tab.
- The three GPA roster links resolve.
- `p_Academic_Year` set on `Landing Page` carries to Home, Schools and the
  Monitor.
- Hovering a help-guide slot shows no tooltip.

### In Tableau Desktop with the `.twbx`

- Desktop opens `final.twbx` without a content-model refusal.

## Device layouts

Four of the existing dashboards carry a `<devicelayouts>` block. None was
touched, and none was added to `Landing Page`. Tablet and phone viewers
therefore see whatever Tableau derives for the new page on its own. If a device
layout is wanted, it is a Desktop change on top of this one.

## Connection credentials

A REST publish does not carry embedded connection credentials, and none were
re-embedded on the review copy. A scheduled extract refresh of the review copy
would prompt for credentials. This affects only the review copy — publishing
from Desktop carries embedded credentials the way it always has.

## Deliberate follow-ups

Five things were left out on purpose.

1. **Launch page entry, at production publish time.** The staff launch page
   still points at `Academic Health Home`, and it should keep doing so until the
   landing page is live in Production. On the day you publish, make two edits to
   the `academic_gradebook_health_suite` entry in `docs/launch/links.yml`. Set
   the URL to
   `https://tableau.kipp.org/t/KIPPNJ/views/AcademicGradebookHealthSuite/LandingPage?:embed=y`,
   and add one clause to the description naming the landing page — for example
   "…and student course grades, opening on a landing page that routes to every
   tab." `status` stays `verified`, because the URL is live at that moment and
   `needs-review` would take the whole entry off the page. Then run
   `uv run --group docs pytest tests/launch -q` and expect all tests to pass.
2. **Help-guide URLs.** Five `LP - Guide *` sheets ship reading
   `Help guide: coming soon`, with no action behind them. Going live is a label
   change on each sheet plus one URL action per sheet.
3. **The grading policy and expectations links.** Omitted, because no URLs were
   supplied for them. The spec's rule was that a link with no URL at build time
   does not ship.
4. **The Miami footnote.** The strip carries a footnote saying Miami is not yet
   in any measure on the page. When Miami rows arrive in the sources the strip
   picks them up on its own, and the footnote is removed by hand. Its second
   sentence in the shipped workbook reads "Paterson has no high school, so its
   cumulative GPA cell is blank"; if the render shows no blank cell, reword it
   in Desktop at publish time to say the cumulative column has no Paterson row.
5. **`LP Gap to goal (region)`.** Ruling 18: the calculation
   (`Calculation_7700000000000000002`) is defined at datasource level but
   referenced by no sheet. Removing it, or wiring it onto the strip, is a
   follow-up. It stays for now because removing it would mean rebuilding and
   republishing the review copy.
