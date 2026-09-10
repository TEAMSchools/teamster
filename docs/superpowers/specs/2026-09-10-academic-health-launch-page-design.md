# Academic & Gradebook Health Suite launch page

Refs [#5235](https://github.com/TEAMSchools/teamster/issues/5235). Brainstormed
2026-09-10 against the production workbook as downloaded that day.

## Decision

Add one new dashboard, `Landing Page`, to the Academic & Gradebook Health Suite
workbook (`b3c14d67-3130-46ac-82a0-0637a5cc2da5`). It becomes the first tab and
the workbook's default view. The five existing dashboards, their worksheets,
parameters and actions do not change. The new dashboard is additive: new
worksheets, one new dashboard, new actions, and nothing else.

The page shows two things: the headline number from each of the four datasets
the suite reads, at network and region grain, and a directory of what each tab
answers. Below the fold it carries the definitions the suite never states in one
place, a coverage grid, and a link strip.

The page is built as `.twb` XML through the `tableau-workbook-xml` skill,
published to a temp project as a review copy, and handed over as a `.twbx` for
the user to publish to Production.

## Why

Today the workbook opens on `Gradebook Teacher View`, its default view. The
suite has five tabs across three GPA concepts and two gradebook health bases,
and nothing tells a first-time user which tab answers their question or what
"healthy" or "cumulative" means on each one.

The OKRTS, DDI and CARAT landing pages share one skeleton: a welcome header, a
"How can this dashboard help me?" tab directory, one question-titled data block,
and a status vocabulary with a legend. They also share one failure mode. Each
accreted hidden show/hide panels and filters until it stopped orienting anyone:
OKRTS has seven collapsed analysis containers and a student roster behind
buttons, CARAT's landing block has ten filters and colliding labels, DDI's
renders with clipped headers and an empty main panel. This page keeps the
skeleton and refuses the accretion. One control, no analysis, no hidden panels.

## Scope

In scope:

- One new dashboard, `Landing Page`, fixed 1366 by 1500.
- New worksheets for the header title, four network tiles, the region strip,
  five directory cards, five help-guide link sheets, and the Miami footnote.
- Go to Sheet actions from the header buttons, the tiles and the cards to the
  existing dashboards.
- The workbook's default view set to `Landing Page` at publish.
- The `academic_gradebook_health_suite` entry in `docs/launch/links.yml` pointed
  at the new view.
- The `academic_gradebook_health_suite` exposure in
  `src/dbt/kipptaf/models/exposures/tableau.yml` gains the two refs it is
  missing: `rpt_tableau__gpa_goal_progress` and `rpt_tableau__gradebook_audit`.
  The workbook embeds five sources and the exposure lists three.

Out of scope:

- Any change to `Academic Health Home`, `Academic Health Schools`,
  `Cumulative GPA Monitor`, `Gradebook School Rollup` or
  `Gradebook Teacher View`. Home keeps its BAN grid, its three analytical panels
  and its parameters exactly as they are.
- Any change to a dbt model. Every number on the page comes from a calculation
  the workbook already has.
- Miami rows. Miami is filtered out of every source the suite reads until Focus
  gradebook data is onboarded. The page plans for Miami with a footnote, not a
  hardcoded row.
- Row-level security. None applies to aggregate data here; everyone sees every
  region.

## Page structure

Fixed size 1366 wide by 1500 tall. Zones from top to bottom, with a pixel budget
that keeps the first four above a 900-pixel fold:

| Zone          | Height | Content                                                        |
| ------------- | ------ | -------------------------------------------------------------- |
| Header        | 80     | Logo, title sheet, caption, Academic Year control, tab buttons |
| Network tiles | 220    | Four tiles, equal width                                        |
| Region strip  | 170    | One row per region, four measures, plus the Miami footnote     |
| Tab directory | 220    | Five cards, equal width                                        |
| Definitions   | 400    | Two-column static table                                        |
| Coverage grid | 220    | Static table, region and school level by tab                   |
| Links         | 60     | One strip                                                      |

Padding follows the existing dashboards' tiled containers. No floating zones.

The dashboard is tiled throughout, one vertical flow container holding one
horizontal flow container per zone. The other three landing pages use
`layout-basic` outer zones with floating children; this page does not, because
every overlap bug found in them was a zone at the wrong nesting depth.

### Header

Left to right: the `CMO_logo_whiteOrange.png` bitmap already in the workbook, a
title worksheet cloned from `Y1 Landing - Title` reading
`Academic & Gradebook Health | Landing Page`, with a caption reading:

> Middle and high schools in Camden, Newark and Paterson. One place to see the
> headline numbers and find the right tab.

The right end holds the existing `p_Academic_Year` parameter control and a
navigation button row with one button per existing tab, in tab order. No other
control appears anywhere on the page.

Freshness is not in the header. Each tile carries its own data update time,
because the tile is the thing whose age matters and the sources refresh on
separate schedules.

### Network tiles

Four worksheets, each cloned from an existing BAN sheet with its region
restriction removed. Each tile reads the same calculation as its source sheet,
by name, and adds nothing. Tile anatomy, top to bottom: measure name, value
large, denominator line, the comparison line the source sheet already has, a
basis line in small text, and the source's data update time.

| Tile             | Cloned from                           | Value calc                 | Denominator and comparison                                                                                          | Basis line                                                          | Navigates to              |
| ---------------- | ------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- | ------------------------- |
| Y1 GPA           | `Y1 Landing - BAN Network ≥3.0`       | `% Y1 GPA at or above 3.0` | Students with a Y1 GPA. `Y1 GPA 1 Week Change ≥3.0` and the 2-week and prior-quarter deltas the sheet already shows | Weighted Y1 GPA, middle and high schools; marking period in title   | `Academic Health Home`    |
| Course failures  | `Y1 Landing - BAN Network Failing ≥2` | `% Y1 Failing 2 or more`   | Students with a Y1 failing count. Same three deltas                                                                 | Y1 grades, middle and high schools                                  | `Academic Health Schools` |
| Cumulative GPA   | `GPA - BAN % 3.0+`                    | `% at 3.0+`                | `Measured` students. `Students still needed` to reach the network goal, and `Gap to goal (pts)`                     | Unweighted cumulative GPA, projected to year end, high schools only | `Cumulative GPA Monitor`  |
| Gradebook health | `BAN Network`                         | `% healthy`                | `Healthy text` (healthy of total teachers). Current quarter                                                         | Current quarter, middle and high schools; health basis in title     | `Gradebook School Rollup` |

Filters kept on each clone: the `Year Filter` calculation, so the tile follows
`p_Academic_Year`; the `MP Filter` calculation on the two Y1 tiles; and the
`Health basis` parameter read on the gradebook tile. Parameters are
workbook-global, so the two Y1 tiles follow `p_Marking_Period` and the gradebook
tile follows `Health basis` wherever the user last set them, exactly as Home's
and the Rollup's BANs do. Their defaults are `Y1` and `Excluding comments`.
Because of that, the marking period and the health basis are shown in each
tile's worksheet title, where a parameter token resolves, not in the mark label,
where it renders blank. Filters removed: the `Region Filter` calculation, `hos`
and `school_level`, so each tile is network-wide regardless of what the user
last set on Home.

The two Y1 tiles show a live number from day one, the same way Home's BANs do.
There is no empty-state rule. The gradebook tile's prior-quarter comparison has
nothing to compare against during Q1 and stays blank until Q2, the same way a
prior-week delta is blank in week one.

The cumulative tile is high schools only by construction:
`rpt_tableau__gpa_goal_progress` carries HS rows only. The basis line says so.

### Region strip

One worksheet with `region` on rows and the four measures on columns, values
with their comparison deltas beside them. Region rows come from the data. Today
that is Camden, Newark and Paterson. Paterson shows a dash on the cumulative GPA
column because it has no high school, with a footnote mark.

The strip uses the same four value calculations as the tiles. Three of them are
plain `COUNTD` ratios and split by region on rows without change. The fourth,
the cumulative goal pair (`Students still needed` and `Gap to goal (pts)`),
reads the org goal or the region goal based on `p_Region`. The strip needs a
two-line variant of each that reads `gpa_goal_proportion_region` directly, so a
region row compares against its own goal whatever `p_Region` is set to. These
are the only new calculations on the page. They are copies of the existing pair
with the parameter branch removed, and they live on the
`rpt_tableau__gpa_goal_progress` source alongside the originals.

Because the strip reads four sources, it is four worksheets side by side in one
horizontal container, each with `region` on rows in the same sort order, with
the region header shown once on the leftmost. Row alignment across the four
depends on every source carrying the same region set. Today all four carry
Camden, Newark and Paterson, and `rpt_tableau__gpa_goal_progress` carries Camden
and Newark only. The cumulative strip sheet therefore pads Paterson with a blank
row by including `region` from the `rpt_tableau__student_course_grades` source
on rows through a blend, or, if the blend misaligns in render, the strip falls
back to one sheet per region row per source, twelve small sheets in a grid. The
build plan picks between the two after the first render; the spec requires only
that every region row aligns across all four columns.

No school-level split appears in this zone. Home already splits Network, MS and
HS, and the two pages should complement rather than repeat each other.

Beneath the strip, one static text line:

> Miami is not yet in any measure on this page. It joins when Focus gradebook
> data is onboarded.

When Miami rows arrive in the sources, the strip picks them up on its own and
the footnote is removed by hand.

### Tab directory

Five cards in one row, equal width, about 260 wide by 200 tall. Each card is a
vertical container holding two worksheets. The upper worksheet is the card body,
one text mark cloned from `Sheet Card - expectations`, about 176 tall, so the
whole body is one click target for a Go to Sheet action. The lower worksheet is
the help-guide link, one text mark cloned from `Links - GPA Roster - Newark`,
about 24 tall. The mark labels are static strings; nothing in them resolves a
field or parameter, because a parameter token in a mark label renders blank.

Card body anatomy, top to bottom: tab name styled as a link, the question the
tab answers, `Grain:`, `Scope:`, `Built for:`, and on the two tabs that show
student names a badge reading `Shows student names` in a warm color. "Built for"
rather than "Visible to" because nothing on the suite is access-gated; the line
says who the tab is designed around.

The help-guide link is the last line of every card and points at that tab's
Zendesk Help Center guide. The guides do not exist yet, so the sheet ships in
placeholder form: label `Help guide: coming soon`, muted text, and no URL
action. When a guide is published, the switch to live is two edits on that one
sheet and nothing else on the page: the label becomes `Help guide` styled as a
link, and a URL action is added with the sheet as its source, cloned from the
`GPA Roster Newark` actions. The slot is reserved now so the card layout does
not shift when the links arrive. This is the one place the page carries a
placeholder, and it is labelled as one rather than shipped as a dead link.

No "You are here" card for the launch page itself. All three reference pages
carry one and it spends a card describing the page the reader is already on.

Card copy:

| Tab                     | Question                                                                                                   | Grain                    | Scope                                  | Built for                             | Student names |
| ----------------------- | ---------------------------------------------------------------------------------------------------------- | ------------------------ | -------------------------------------- | ------------------------------------- | ------------- |
| Academic Health Home    | How is this year's weighted GPA and course-failure picture moving, by school, school level and subject?    | School                   | MS and HS. Camden, Newark, Paterson    | Regional and school leaders           | No            |
| Academic Health Schools | Where is failure concentrated by teacher, and which students near the 2.0 and 3.0 cusps need office hours? | School, teacher, student | MS and HS                              | School leaders, APs, counselors       | Yes           |
| Cumulative GPA Monitor  | Are HS cohorts on track for the unweighted cumulative GPA goal by year end, and who sits just below 3.0?   | Grade, school, student   | HS only. Camden and Newark             | KIPP Forward, HS leaders              | Yes           |
| Gradebook School Rollup | What share of teachers have healthy gradebooks, by school and manager?                                     | School, manager, teacher | MS and HS. Camden, Newark, Paterson MS | School leaders, instructional coaches | No            |
| Gradebook Teacher View  | What does my own gradebook need before the quarter closes?                                                 | Teacher, section         | Your own sections                      | Teachers                              | No            |

### Definitions

One static text object laid out as a two-column table, term on the left, one
plain sentence on the right. Each entry quotes the threshold its calculation
uses. Order:

| Term                          | Definition                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Y1 GPA                        | Weighted, current year only, quarter to date. The GPA on Home, School View and the two Y1 tiles.                                                                                                                                                                                                                                                                                                                                  |
| Cumulative GPA                | Unweighted, every high school year on record. The GPA on the Monitor and the cumulative tile. The two GPAs are never interchangeable.                                                                                                                                                                                                                                                                                             |
| Weighted versus unweighted    | An unweighted GPA scores every course on the same scale, topping out at 4.33 for an A+. An A in AP Biology counts the same as an A in regular Biology. A weighted GPA gives honors and AP courses a bump above that for the same letter grade. Y1 GPA on this suite is weighted. Cumulative GPA is unweighted, so a student's cumulative number will usually read lower than their Y1 number, and that is expected, not an error. |
| Projected versus on the books | The Monitor's basis switch. On the books is the cumulative GPA from posted grades today. Projected carries this year's in-progress grades to year end. The tile uses projected.                                                                                                                                                                                                                                                   |
| Marking period                | Q1 through Q4 are quarter grades. Y1 is the running year grade. Home's default is Y1.                                                                                                                                                                                                                                                                                                                                             |
| Failing                       | A course whose Y1 letter grade is an F. The failures tile counts students with 2 or more.                                                                                                                                                                                                                                                                                                                                         |
| Healthy gradebook             | A teacher with no flag on any of their sections this quarter. The two bases differ by one flag: excluding comments ignores the below-70-without-comment flag until quarter close. The tile uses excluding comments.                                                                                                                                                                                                               |
| The three gradebook flags     | Not enough assignments entered against the expectation for the category. A grade above 100. A grade below 70 with no comment.                                                                                                                                                                                                                                                                                                     |
| Goal                          | The share of students expected at or above 3.0 cumulative, set per network, region and school in the GPA goals source.                                                                                                                                                                                                                                                                                                            |
| Can still reach 3.0           | A student below 3.0 whose GPA needed to get there is within the grade scale.                                                                                                                                                                                                                                                                                                                                                      |

Source of each threshold: `% Y1 GPA at or above 3.0` and `% Y1 GPA below 2.0`
compare `gpa_y1` to 3.00 and 2.00; `% Y1 Failing 2 or more` compares
`gpa_n_failing_y1` to 2, and `n_failing_y1` in `int_powerschool__gpa_term`
counts `y1_letter_grade like 'F%'`; the gradebook flags are
`not_enough_assignments`, `has_grade_above_100` and
`has_grade_below_70_no_comment` in `rpt_tableau__gradebook_audit`; the two
health bases are `is_healthy_gradebook_all_flags` and
`is_healthy_gradebook_excl_comments`; the cusp rule is
`is_cumulative_3_0_attainable` in `rpt_tableau__gpa_goal_progress`.

### Coverage grid

A static table. Rows: Camden MS, Camden HS, Newark MS, Newark HS, Paterson MS,
Paterson HS, Miami. Columns: the five tabs. A filled mark where the tab has data
for that row. Paterson HS reads as an empty row with the note "No high school".
Miami reads as an empty row with the note "Not in the suite until Focus
gradebook data is onboarded". This is the one place on the suite that says why a
Miami user sees nothing on the Rollup.

Coverage as of 2026-09-10:

| Row         | Home | Schools | Monitor | Rollup | Teacher View |
| ----------- | ---- | ------- | ------- | ------ | ------------ |
| Camden MS   | yes  | yes     |         | yes    | yes          |
| Camden HS   | yes  | yes     | yes     | yes    | yes          |
| Newark MS   | yes  | yes     |         | yes    | yes          |
| Newark HS   | yes  | yes     | yes     | yes    | yes          |
| Paterson MS | yes  | yes     |         | yes    | yes          |
| Paterson HS |      |         |         |        |              |
| Miami       |      |         |         |        |              |

### Links

One strip at the bottom. The three existing `Links - GPA Roster - <Region>`
worksheets are placed on the new dashboard as they are, and the three existing
URL actions each gain the new dashboard as a source, the same way each of them
already lists Home, Schools and the Monitor. Two further links, the grading
policy and the assignment expectations sheet, are included only if the user
supplies a shareable URL for each before the build starts. A link with no URL at
build time is left out. No dead links ship, and no "request access" link,
because there is no access gate. The per-tab Zendesk help guides are not in this
strip; each lives on its own tab card, described above.

## Navigation and actions

Two paths reach every tab: the button row in the header and the card in the
directory. Both are Go to Sheet actions targeting the existing dashboards by
name. The four tiles also navigate, each to the tab in its table above. No
filter actions, no highlight actions, no parameter actions. Nothing on the
launch page changes the state of any other tab.

`p_Academic_Year` is the existing parameter, so setting it here carries to Home,
Schools and the Monitor the way it already does between those tabs. The Rollup
and Teacher View read the current quarter and do not listen to it. That is the
existing behavior and stays.

## Build approach

XML edit through the `tableau-workbook-xml` skill, with these rules on top of
the skill's own:

- Every new worksheet is cloned from a named working sheet in the same workbook
  so it inherits a valid skeleton: `simple-id`, `view` with `aggregation`, pane
  child order. The clone source for each is named in this spec.
- The new dashboard's `<zones>` block is tiled flow containers only. A
  `<devicelayouts>` block is not added.
- New worksheet names carry a `LP - ` prefix so the new sheet set can be listed
  by prefix and the byte-identity check below can exclude it.
- The three new dashboard-to-dashboard action sources and the two new goal
  calculations are the only additions outside the new dashboard and its
  worksheets.
- Publish target is a temp project the user names, `GPA-monitor-temp`
  (`c74d8e08-b856-4430-a759-ebacb061e376`) if they name none, under a
  `ZZ-REVIEW <date>` workbook name, with `hidden_views` set to every
  pre-existing publishable sheet that is not one of the five live dashboards.
- Nothing publishes to Production from this work. The user publishes the
  handed-over `.twbx`.

## Verification

Build:

- Both skill checkers pass against the untouched base first, then against every
  edit with the base as reference.
- Byte identity of the five existing dashboards: the edited `.twb` with the
  `Landing Page` dashboard, every `LP - ` worksheet, the two new calculations
  and the new actions removed diffs empty against the base. One attribute is
  exempt: the default view is the dashboard window that carries
  `maximized='true'`, so that marker moves from the `Gradebook Teacher View`
  window to the new one. The checker normalizes that attribute out on both sides
  and separately requires exactly one maximized window, `Landing Page`. A
  mutation that touches one existing dashboard zone must make this check fail
  before it counts.
- `repack.py` reports zero bare LF and packaged bytes equal to the source.

Render, on the review copy:

- Each network tile rendered and read against the matching BAN on its source tab
  at the same parameter settings: the Y1 tiles against Home with `p_Region` set
  to `All`, the cumulative tile against the Monitor, the gradebook tile against
  the Rollup. A tile that disagrees with its source by any amount is a defect,
  because both read the same calculation.
- The region strip checked the same way with Home's `p_Region` set to each
  region in turn, and the Monitor's set to Camden and Newark.
- Every region row aligned across all four strip columns.
- Definitions, coverage grid, links and cards read in crops for `####`, clipped
  or ellipsised text, a literal `[federated…]` or parameter token, and
  overlapping zones. Crops rather than a full frame because the output hook
  redacts a full render.

Only the user can check:

- Desktop opens the `.twbx` without a content-model refusal.
- Every Go to Sheet action lands on the right tab. A render cannot click.
- The two external links resolve, and each help-guide slot reads
  `Help guide: coming soon` with no action behind it.
- `p_Academic_Year` set on `Landing Page` carries to Home, Schools and the
  Monitor.

Hand-off is the `.twbx`, the review copy's URL, Production's revision number
before any of this, and a list of what was rendered, what was inferred, and what
needs the user's click.

## Risks

- A hand-built worksheet passes Server and refuses in Desktop. Mitigation is
  cloning from working sheets and the checkers; the Desktop open is the only
  real check and it is the user's.
- The region strip misaligns across four sources with different region sets.
  Mitigation is the fallback grid layout named above; the spec requires
  alignment, not a particular construction.
- The two new goal calculations drift from the originals if the originals are
  edited later. Mitigation is naming them after the originals with a `(region)`
  suffix and a comment in the calculation pointing at the source.
- Home's BAN grid and the launch tiles show the same numbers by design, and both
  follow `p_Marking_Period`. A user who sets Q1 on Home and returns to
  `Landing Page` sees Q1 tiles. The tile title names the marking period so the
  number is never read against the wrong period.
