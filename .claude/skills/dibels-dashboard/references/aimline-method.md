# The aimline method

What the aimline verdict means, the two targets it involves, the grains it is
reported at, and where our wording departs from T&L's.

## The aimline sibling, and the three traps in it

`int_amplify__pm_met_criteria_aimline` mirrors the internal model stage for
stage. Only the first stage differs: `met_measure_standard_goal` translates
Amplify's `aimline_status` instead of comparing a score to a cohort target.
Inputs are `int_amplify__all_assessments` (`model_type = 'Aimline'`, which
carries `aimline_status`, `aimline_season_student_goal` and
`met_measure_standard_goal` -- the translation lives there so every consumer
reads one flag, under the SAME name the internal method uses), the by-levels
gate for `pm_goal_criteria`, `benchmark_goal` and the previous EXPECTED round,
and the roster's Aimline rows for completion. It is wired into
`rpt_tableau__dibels_dashboard` as a third UNION branch, told apart by
`model_type`.

**Trap 1 -- the by-levels gate needs the cohort level.** It is split by
`measure_standard_level`, and on an Aimline row `overall_probe_eligible` carries
that level (Below Benchmark / Well Below Benchmark), not the `'Yes'` an Internal
row carries. Join without it and every row doubles. The gate is unique on (year,
region, grade, admin_season, round_number, expected_measure_standard,
measure_standard_level) -- 2,108 of 2,108 -- so with it there is no fan-out.

**Trap 2 -- `met_measure_standard_goal` is nullable on the Aimline branch on
purpose.** Amplify publishes no status on a share of probes even where a goal is
present, so the rollups treat null as unknown, not as a miss. Do not "fix" it
to 0. (On the Internal branch the same column is never null on a sat row, which
is why the two branches' status twins have different value counts.)
`avg(...) = 1` would silently credit a code with an unpublished standard, which
is why the code and round rollups use countif-plus-min/max instead of the
internal model's avg.

**Trap 3 -- the streak runs over EXPECTED rounds, not sat ones.** T&L define
two-in-a-row as "two consecutive rounds that they were supposed to test on", so
`previous_expected_round` is a `lag()` over the gate, and the model self-joins
the student's row for that round. A measure the schedule tests in rounds 1 and 3
only streaks across round 2 correctly; where the student was expected and
absent, it falls back to their last recorded verdict. A plain `lag()` over
scored rows gets both cases wrong in opposite directions. T&L dropped the
three-in-a-row variant.

**Decisions that are T&L's, not ours** -- do not "correct" them:

- `benchmark_goal` is UNPADDED here, and padded on the internal method.
  Academics keep the 3-word buffer for the internal trajectory and not for
  aimline, so the two methods' `met_admin_benchmark_goal` are three words apart
  by design -- 9,117 aimline rows meet the unpadded standard against 5,758 that
  would meet the padded one. Never union or compare the two columns.
  **Re-reviewed 2026-09-19 and KEPT.** The case for aligning them is good --
  at-grade-level is the one question that does not depend on method -- but
  changing either side moves a number T&L already read, so the split stands and
  the name stays. Measured at the extract: of 35,496 rows scored on both
  methods, 3,162 read met on Aimline and not on Internal, and ZERO the reverse.
  One-directional is the signature of a uniformly higher bar; a non-zero reverse
  count means something other than the pad has changed. Confirmed independently
  -- `met_admin_benchmark_goal_unpadded` on Internal reproduces the Aimline
  column cell for cell, 8,731 met and 26,751 not on each.
- `met_admin_benchmark_goal_unpadded` exists on the INTERNAL branch and is
  deliberately unused. It is the same comparison without the buffer, parked so a
  future consumer wanting a cross-method at-grade-level figure needs no model
  change. Null on Benchmark and Aimline rows, because aimline's is already
  unpadded and a copy would be redundant. Binding it to a view raises Internal
  attainment from 5,569 to 8,731 on AY2025 -- a T&L decision, not an engineering
  one. Do not wire it up on your own initiative.
- `Not Tested` overrides every other category, because they define it at the
  round: not tested on one or more of the round's expected measures means Not
  Tested for the whole round, including the measures they did sit.
- `Meeting Aimline, On-Track` fires on the benchmark alone, per their rule that
  a student meeting benchmark but not aimline still belongs there. The label
  overstates what it checks; that is their wording.
- `No Aimline Data, On-Track` and `No Aimline Data, Off-Track` are the fifth and
  sixth categories their four omit. Academics chose to show the score and flag
  the missing target rather than hide the row or call it Not Tested. The same
  words, `No Aimline Data`, name the same condition on every other aimline
  status column -- one spelling network-wide since 2026-09-19.
- `aimline_status` is the source the verdict is translated FROM, and stops at
  this model -- the extract does not publish it, because
  `measure_standard_goal_status` already carries the same verdict in academics'
  wording. Read it here when you need Amplify's literal At or Above / Below.
- `aimline_value_by_date` IS the target `aimline_status` was computed against,
  and publishes as the extract's `goal` on Aimline rows. Do not derive the
  verdict from `aimline_season_student_goal` instead: that is the season-end
  target and reproduces `aimline_status` on only five rows in six, where the
  moving value reproduces it exactly. What the column measurably does, and the
  one question still open about it, is under "The two aimline targets" below.

Validated on AY2025 against PROD: 36,502 rows, exact grain, six tests pass, 5
rows lost to the roster join (3 Newark students, in the yml). Measure documented
counts against prod, never a dev build -- `--favor-state` does NOT defer a model
that already exists in your dev schema, so a stale `zz_<user>_*` copy silently
wins and the build looks authoritative. That is how nine figures in these docs
were wrong for four days.

## "% meeting aimline, overall and by measure" is three grains, and all three already exist

Academics' phrasing hides three questions. Asked on 2026-09-15 what they meant,
the answer was: did the student meet the aimline on this measure standard this
round, on every expected standard under one measure name code, and on every
expected standard in the round. Same AND-gate shape as the testing states.

**Do not build anything for this.** All three are already columns:
`met_measure_standard_goal`, `met_measure_name_code_goal`, and
`met_pm_round_criteria` / `met_pm_round_overall_criteria` (the second variant
also requires full participation). "% not meeting" is the inverse of the same
flags -- it needs no new field either.

Three things to say when this comes up:

- **Take it from the verdict, not from `aimline_category`.** The category
  applies T&L's benchmark-wins rule, so 696 AY2025 rows read
  `Meeting Aimline, On-Track` while below the aimline. For an
  intervention-targeting metric the label undercounts the problem set.
- **Name the grain on every view.** AY2025 "% not meeting" runs 56.8% at measure
  standard, 65.1% at name code, 72.9% at round, and 77.6% at round with the
  participation gate -- all four defensible, so an unlabelled 57% and an
  unlabelled 78% will both get quoted as the same metric.
- **The gate is over EXPECTED standards, never all possible ones.** Reading
  Accuracy has zero expected rows in rounds 5 to 8, so ORF from round 5 needs
  Reading Fluency alone. Requiring both would fail every grade 3-8 student for
  the back half of the year by definition.

Two decisions belong to academics: whether grain 3 uses the participation gate
(their wording says yes), and whether the no-verdict rows count as not met
(12,695 of 44,865 at measure grain, so the choice moves each rate by 10 to 20
points).

## The met/not-met flags have labelled twins, and the workbook needs a change

`int_amplify__pm_met_criteria` emits three `*_status` strings beside its flags:
`pm_round_status` (`Met` / `Not Met` / `Round Incomplete`),
`measure_standard_goal_status` (`Met` / `Not Met`) and
`admin_benchmark_goal_status` (`Met Benchmark` / `Did Not Meet Benchmark`).
`rpt_tableau__dibels_dashboard` passes all three through and coalesces the
untested gap to `Not Tested`, so on a PM row they are never null and null now
means one thing only -- a Benchmark row.

**Bind views to the status strings, not to the numeric flags**, because the
flags' null contract differs by method and the strings' does not.
`met_measure_standard_goal` on the Internal branch is a plain `if`, so it is
never null on a sat row; on the Aimline branch it is a `case` over
`aimline_status` with no `else`, so 3,312 of 35,482 sat rows (9.3%) are null on
AY2025. An `AVG()` of the flag therefore answers a different question per
method. `measure_standard_goal_status` names every one of those states -- so
count `COUNTD([Student Number])` over an explicit value instead.

**Its vocabulary differs by method on purpose**, so do not write a calc that
expects one value set across both:

| Internal     |   Rows | Aimline           |   Rows |
| ------------ | -----: | ----------------- | -----: |
| `Met`        | 11,096 | `Meeting Aimline` | 13,886 |
| `Not Met`    | 24,386 | `Below Aimline`   | 18,284 |
| `Not Tested` |  9,383 | `Not Tested`      |  9,383 |
| --           |     -- | `No Aimline Data` |  3,312 |

The full vocabulary, settled 2026-09-19. Every column also carries `Not Tested`
from the extract's coalesce.

| Grain             | Internal                               | Aimline                                                              |
| ----------------- | -------------------------------------- | -------------------------------------------------------------------- |
| Measure standard  | Met / Not Met                          | Meeting Aimline / Below Aimline / No Aimline Data                    |
| Measure name code | Met / Not Met                          | Meeting Aimline / Below Aimline / No Aimline Data                    |
| Round             | Met / Not Met / Round Incomplete       | Meeting Aimline / Below Aimline / No Aimline Data / Round Incomplete |
| Admin benchmark   | Met Benchmark / Did Not Meet Benchmark | identical to Internal                                                |

Three rules behind it: aimline columns name what the verdict is measured
against; the benchmark grain reads the same on both because the standard does
not depend on method; and `No Aimline Data` is the one spelling for that
condition at every grain (the round column said `No Aimline Status` until
2026-09-19).

So a view can switch between the three aimline grains with one colour legend. A
view mixing an aimline grain with an internal one cannot -- only `Not Tested` is
shared.

Only `Not Tested` is shared, so a combined view needs its own colour legend.
`admin_benchmark_goal_status` reads `Met Benchmark` / `Did Not Meet Benchmark`
on both, because the benchmark standard is the one grain that does not depend on
method. It is the only status column whose values match across the two.

They exist because `met_pm_round_overall_criteria = 0` means both "did not meet"
and "could not be evaluated". `Round Incomplete` keys on
`met_pm_round_criteria`, NOT on the overall flag -- under `AND` a measure the
student sat and failed settles the round however much is missing, so keying on
the overall flag overstates it about fourfold. 375 rows of 35,524 on AY2025.

**The workbook is the other half of this and is not done.** The Literacy
Dashboard's `PM - Met Goal Selector` is a CASE returning one of the three
numeric flags, coloured null / 0 / 1 as No Data / Not Met / Met. To surface the
new state, point each branch at the matching `*_status` column so the calc
returns strings and carries no logic:

```text
CASE [PM - Met Goal Parameter]
WHEN 'Met Overall Goal'   THEN [PM Round Status]
WHEN 'Met Standard Goal'  THEN [Measure Standard Goal Status]
WHEN 'Met Benchmark Goal' THEN [Admin Benchmark Goal Status]
END
```

**Also outstanding, and more urgent: every PM view must now filter
`model_type`.** The dashboard has a third branch for the aimline method, so both
methods emit rows for the same student and any unfiltered PM view double-counts.
Nothing in the workbook filters it yet.

Two things to watch on the selector itself. The existing No Data alias is on the
NULL member, and PM rows are no longer null -- repoint it to `Not Tested`. And
check whether any sheet aggregates the selector as a measure (an `AVG()`
met-rate); converting it to a string breaks that sheet, so if one exists, add
the string version as a second calc for Colour and leave the numeric one for
measures. The workbook's datasource is embedded, and Tableau's VizQL Data
Service returns 500 on embedded sources, so the MCP cannot read the calculated
fields -- this has to be checked in Desktop.

## Measure grain and measure-standard grain differ by 15 points on ORF

Measured 2026-09-19 on AY2025. `NWF` and `ORF` each carry two measure standards;
`PSF`, `WRF` and `Comprehension` carry one. So for those two codes "met the
measure" and "met a standard of the measure" are different questions, and the
answers are far apart.

The two ORF standards -- Reading Fluency (words per minute) and Reading Accuracy
(percent correct) -- disagree on **41% of Internal student-rounds** where both
were scored (34% on Aimline). NWF's pair come off one probe and disagree on 8.7%
/ 16.7%.

Reported meeting rate, standard grain against code grain:

| Method   | Code | At standard |   At code |
| -------- | ---- | ----------: | --------: |
| Internal | ORF  |       35.3% | **20.5%** |
| Internal | NWF  |       28.4% |     24.1% |
| Aimline  | ORF  |       43.0% |     28.8% |
| Aimline  | NWF  |       43.3% |     34.9% |

**The trap is labelling, not arithmetic.** The Region Overview - PM tab's column
selector reads "Measure" but is bound to `expected_measure_standard`, so a
reader picking ORF gets the standard-grain figure under a measure-grain label.
Both numbers are correct answers to different questions; only one matches the
question the label asks.

A measure-labelled view binds `expected_measure_name_code` with
`met_measure_name_code_goal` / `measure_name_code_goal_status`. A
standard-labelled view keeps the `_standard_` pair. Do not mix a dimension from
one grain with a flag from the other.

## Where the model's wording departs from T&L's doc, on purpose

T&L's canonical definitions live in the "Definitions Needed" table of "SY26 -
KIPP NJ - DIBELS PM Rounds + Goals" (owner mtambawala). The model matches it
everywhere except two places, both settled by the dashboard owner on 2026-09-19
after reading the doc against the model. **Do not "correct" either one back to
the doc.**

- **`Meeting Aimline, On-Track`** -- the doc says "On Track and Meeting
  Aimline". Kept as is so it reads as a pair with `Meeting Aimline, Off-Track`.
  Same concept, better-matched siblings.
- **`Not Tested` vs `Round Incomplete`** -- the doc defines Not Tested as "not
  PM tested on ONE OR MORE measures", i.e. our Round Incomplete. Split
  deliberately, for two reasons worth repeating to whoever asks: cohort-level
  testing already makes "why is this student untested" hard to read, since BB
  and WBB students sit different rounds; and Alisha Fairfax asked for
  percent-tested-over-time, which needs fully tested / not started / incomplete
  as separate states so schools can target the incomplete ones.

The doc also records where `aimline_value_by_date` started: T&L's own words, "I
don't know what this is. Decision: wait until we get definitions from KIPP
Foundation before we do anything with this." That hold is DISCHARGED --
Amplify's own report documentation defines the column, so it now publishes. Cite
the definition, not the old decision, if someone reopens it.

`On Track to Benchmark`, which appears in some of their screenshots but in no
definitions table, comes from a separate wishlist line -- "Meeting Aimline,
Below Benchmark Trajectory, could be a swap view". That is the origin of
`aimline_trajectory_category`. It is a different ask, not drift, so do not
retire that column as a duplicate without checking whether the swap view is
still wanted.

**Three pads exist, and the doc's "PADDING UPDATE (K-8)" block governs two of
them -- not the PM one.** Read against the PM chain the block looks like a
contradiction. It is not; it is about the benchmark-goal chain.

| Pad    | Where                                       | Applies to                                  |
| ------ | ------------------------------------------- | ------------------------------------------- |
| `+3`   | `stg_google_sheets__dibels_pm_goals`        | `benchmark_goal_padded`, the PM bar         |
| `+5`   | `rpt_gsheets__dibels_bm_goals_calculations` | expected at/above count, BOY ONLY           |
| `x1.5` | `rpt_gsheets__dibels_bm_goals_calculations` | the expected-minus-actual gap, every season |

That resolves the wording exactly. "Double padded" is the `+5` AND the `x1.5`
together, which is BOY. "Single padding, keep the 1.5 pad" is dropping the `+5`
and keeping the multiplier -- which is what `if(period = 'BOY', 5, 0)` already
does. Implemented, seasonal, and matching the note.

So the PM `+3` is correct as shipped and that block never referred to it.
Confirmed by the owner 2026-09-19. Do not re-open it from the doc text, and do
not read "double padded" as a PM instruction.

## Regions are not on the same round, and round numbers are not unique

AY2025 Miami sits a week to a month behind the NJ regions on every round, and
runs THREE rounds per season where NJ runs four. So Miami's round 4 is in
MOY->EOY while every NJ round 4 is in BOY->MOY. Simulated against the AY2025
gate:

| As of      | Camden | Newark | Paterson | Miami        |
| ---------- | ------ | ------ | -------- | ------------ |
| 2025-12-01 | R3     | R3     | R3       | R2           |
| 2026-02-05 | R4     | R4     | R4       | R4, MOY->EOY |

Two consequences. `expected_round_selection` exists so a view can say "wherever
each cohort actually is" instead of hard-coding a number -- it reads `Current`
on the latest round whose window has OPENED, partitioned by year, region and
grade, and carries that round's label on every other row. A string, not a
boolean, so one filter selection follows each region; the cost is that a round
that is current somewhere is no longer selectable by number on this field, so
"everyone's round 3" comes from `expected_round_number` or
`expected_round_label`. And `expected_round_label` is load-bearing, NOT
cosmetic: a filter on the bare round number silently mixes NJ students
mid-first-half with Miami students in their second half.

Latent today only because Miami produces no rows in the extract at all. Do not
"simplify" the label away on the grounds that round numbers look unique -- they
look unique because Miami is missing.

## The switcher grid, and why its names are inconsistent

Added 2026-09-19. One Tableau selector pair drives every distribution view --
granularity picks the row, comparison item the column:

| Grain             | Own goal                        | Benchmark                            | Aimline + benchmark                          | Trajectory                            |
| ----------------- | ------------------------------- | ------------------------------------ | -------------------------------------------- | ------------------------------------- |
| Measure standard  | `measure_standard_goal_status`  | `admin_benchmark_goal_status`        | `aimline_category`                           | `aimline_trajectory_category`         |
| Measure name code | `measure_name_code_goal_status` | `measure_name_code_benchmark_status` | `measure_name_code_aimline_benchmark_status` | `measure_name_code_trajectory_status` |
| Round             | `pm_round_status`               | `round_benchmark_status`             | `aimline_round_category`                     | `round_trajectory_status`             |

"Own goal" is the method's own target -- cumulative growth on Internal, the
aimline on Aimline. The right two lenses are Aimline-only.

**Do not file the naming inconsistency as a bug.** The five new columns use
`<grain>_<lens>_status`; the four older ones do not. Aligning all nine was
considered and DEFERRED on the day, because three of the older names are shared
with Internal and renaming them forces a rebind of the internal Tableau tabs
too. It is recorded in the reference document as a follow-up. Additive was the
owner's explicit choice for timing.

**Coarser grains are strictly stricter.** AY2025 Aimline benchmark: 8,731 met at
measure standard, 5,197 at name code, 3,004 at round, zero rows where a coarser
grain reads met while a finer one does not. If that ever inverts, something is
wrong with a rollup window.

**Grain and dimension must move together.** A coarse-grain value repeats across
the round's measure rows, so a view showing round-grain status broken out by
measure standard asserts a difference that does not exist, and student counts
stop summing to the population -- 404 slice-counts against 327 students at
measure-standard grain in one measured school. Drive the Columns dimension from
the same parameter as the status column.

## The four goal grains each have a flag and a labelled twin

| Grain             | Flag                            | Labelled twin                   |
| ----------------- | ------------------------------- | ------------------------------- |
| Measure standard  | `met_measure_standard_goal`     | `measure_standard_goal_status`  |
| Measure name code | `met_measure_name_code_goal`    | `measure_name_code_goal_status` |
| Round             | `met_pm_round_overall_criteria` | `pm_round_status`               |
| Admin benchmark   | `met_admin_benchmark_goal`      | `admin_benchmark_goal_status`   |

All four flags are 1/0/null on both methods, so a numeric selector works across
them; all four twins are non-null on PM rows. The name-code twin was added
2026-09-19 -- before that the selector returned a number on that one option and
strings on the rest.

**Each grain needs its own dimension on the view.** Measured on the 14,924
multi-standard code groups: the standard and benchmark flags VARY within a name
code (2,948 and 1,746 groups on Internal), while the code and round flags are
constant across it (0 of 14,924). Display a code-grain or round-grain value
broken out by measure standard and it repeats identically across the
sub-standards -- the average stays right, but the view asserts a difference that
does not exist.

## The two aimline targets, and three ways to get them wrong

Measured 2026-09-19 on AY2025. Full tables in the reference doc under
[Both methods have a moving target](../../../docs/models/dibels-dashboard-data-model.md);
what a session needs before opening a file is here.

**Aimline has TWO targets and they go in different extract columns. Keep them
apart.**

| Extract column                    | Internal rows             | Aimline rows                    |
| --------------------------------- | ------------------------- | ------------------------------- |
| `goal`                            | `cumulative_growth_words` | `aimline_value_by_date`         |
| `aimline_season_student_goal`     | null                      | Amplify's season endpoint       |
| `aimline_season_student_goal_gap` | null                      | score minus the season endpoint |

`goal` is the MOVING target -- what the verdict was computed against, climbing
across the season -- and it is the one column both methods share, because both
halves answer the same question. The season endpoint is a different quantity,
per student rather than per cohort, and stays in its own column. Do not merge
them, and do not compare a score to the season endpoint to get the verdict.

AY2025 populations: `goal` on all 44,865 Internal rows and 32,170 of 44,865
Aimline rows; `aimline_season_student_goal` on 33,873 Aimline rows with the gap
on the same 33,873. The two counts differ by ~1,700 rows where Amplify published
a season endpoint but no aimline value for that probe -- those carry a gap while
`measure_standard_goal_status` reads `No Aimline Data`, so a roster can show a
gap on a row that has no verdict.

**`measure_standard_round_verdicts` puts the whole season on one row.** One
hyphen-separated character per round in round order, e.g. `B-B-A`. `A` is at or
above (meeting aimline, or met on internal), `B` is below (below aimline, or not
met), `?` is No Aimline Data, `.` is a round not tested. A/B is Amplify's own
pair, which is why it was chosen over Met/Not Met wording -- leaders already
read it that way. One alphabet for both methods on purpose. No token is the
hyphen, so `B-B-.` reads unambiguously as three rounds.

It is scoped to the administration season (never runs BOY->MOY into MOY->EOY,
which carry different goals) and built over the expectation spine, so a skipped
round is a `.` rather than a shortened string. It repeats across its partition
-- season-level value on a round-level row -- so counting students on it without
a round filter multiplies by the round count. Null on Benchmark rows.

Verified AY2025: on all 89,730 PM rows the character at the row's own round
position equals that row's own `measure_standard_goal_status`, zero mismatches
either method. Known wrinkle: 3 partitions per method (14 rows) repeat a
character, from the course-enrollment fan-out that predates the column.

**Never verify a derived column by re-applying its own derivation.** The verdict
string shipped broken and a check reported zero mismatches, because the check
re-used the same CASE the column was built from -- it compared the expression to
itself. The Aimline half matched on `like 'Met%'`, which `Meeting Aimline` does
not satisfy (`Mee`, not `Met`), so all 13,886 met-aimline rows rendered `?`
instead of `A` and nothing caught it. Derive the expected value from a DIFFERENT
column -- here the underlying `met_measure_standard_goal` flag -- or the check
is theatre. `rpt_tableau__dibels_dashboard__round_verdict_token_reconciles` now
does that and reproduces the failure at 13,886 rows.

A related habit: the token is driven off the `1`/`0`/`null` flag rather than off
the human-readable `*_status` string, so a future wording change on either
method's vocabulary cannot silently re-break it. Prefer flags over string
prefixes anywhere the two methods' vocabularies diverge.

WATCH OUT when verifying anything partitioned on this extract: leave
`model_type` out of the partition and you merge Internal with Aimline, which
silently doubles every partition. That is the same double-count trap the
row-level rules warn about, and it burned a verification pass in this session
before the column itself turned out to be correct.

**The one open decision: Below Aimline outranks No Aimline Data.** When a
round's measures disagree, the round rollup takes the worst state, and every
rung of that order is forced by the row-level cascade EXCEPT this one. A student
below the aimline on one measure and carrying no published aimline on another
reads `Below Aimline`, on the reading that a real negative verdict beats a
missing one. Academics have NOT confirmed it. If they reverse it, 694 of 10,046
AY2025 `Below Aimline` round groups (6.9%) become `No Aimline Data` — a one-line
change to the cascade that moves published numbers. Do not present round-level
aimline figures as settled without saying this is open.

**Reading a roster row.** Grain is student x measure standard x season x round,
one row per round -- "every score so far at round 3" is three stacked rows, not
one wide row. The season endpoint is the END OF THAT SEASON, not the year: a
BOY->MOY row's goal is the MOY target, and MOY->EOY carries a different one.
Round numbers run 1-8 across the year without restarting, so round 3 is
unambiguously BOY->MOY, but Camden's MOY->EOY is rounds 6-8 where Newark and
Paterson run 5-8 -- which is why `expected_round_label` stays load-bearing. A
row's gap is THAT round's score minus the season endpoint, so it can read
negative while the status reads `Meeting Aimline`: on pace, not yet arrived.
Never filter a roster on `period` -- it is null on the 9,383 untested rows, the
exact rows a participation view needs; use `expected_round_label`.

**`aimline_value_by_date` reproduces the aimline verdict exactly.** On the
extract, `measure_standard_score >= goal` matches `measure_standard_goal_status`
on 32,170 of 32,170 scored Aimline rows with a target (13,886 Meeting Aimline,
18,284 Below Aimline, zero disagreements either way). The season endpoint agrees
on only 7,850 of those 13,886. Zero rows carry a verdict without a target or a
target without a verdict. If a view's aimline numbers disagree with the status
column, the view is wrong, not the data.

**The hold on it is discharged.** Amplify's report documentation defines it as
the "score that is on the aimline on the day that the PM test is administered",
ranged 0-999 whole for most measures, 0-100 for ORF Accuracy, 0-999 with `.5`
for Maze -- and our data conforms exactly (3,134 Maze decimals, all `.5`, no
range violations). That definition was the blocker; it is answered.

Measured behaviour, AY2025: a straight line in calendar days (mean absolute
residual 0.126 words against the line through each partition's first and last
probe, max 1.0), monotonic non-decreasing on 29,051 of 29,051 consecutive pairs,
never above the season endpoint, equal to it on 1,819 extract rows and on 10.9%
of final probes. It moves in 14,732 of 19,467 multi-probe partitions (76%) where
the season endpoint moves in 32 (0.2%).

How Amplify anchors the line is NOT an open question for this repo. Amplify
publishes the equation behind the starting point; it is too complex to be worth
reimplementing and there is no reason to, since school leaders already treat the
per-student goal as Amplify's output and trust it. Route any "how is this drawn"
question to Amplify. Do NOT spend a session fitting it from the published
columns -- that work is done and at its limit. (For the record: the endpoint is
not a shared season-end date; extrapolating each line to its season endpoint
spreads Newark BOY->MOY over 52 dates. Property of the method, affects no column
we publish.)

**Amplify's `goal` is a per-student growth target, not the grade's bar.** It is
written from the individual student's point of view -- where this student should
reasonably reach by the end of the period, given where they started -- so two
students in the same class on the same measure can correctly hold different
goals. `benchmark_goal` is the opposite kind of thing: one published grade-level
standard everyone is held to. A per-student endpoint is what the per-student
aimline trajectory has to run to.

It is therefore not `benchmark_goal` unpadded, which is the tempting guess and
wrong for two rows in three: 36.6% of probe rows match our standard exactly,
39.8% sit below it, 23.6% above. Grade 3 Reading Fluency BOY->MOY -- our
standard 105, Amplify's goals 33 to 189. The rows that do match are students
whose individual target coincides with the standard, not evidence the column is
the standard. Never substitute either column for the other, and never label
`goal` as a grade-level goal in a view.

## A missing aimline `goal` is a school-grade condition, not thin data

Grades 5 and 7 carry `goal` null rates of 15.9% and 14.6% against 1.7-3.4%
elsewhere, which invites "those grades cancelled PM testing, so Amplify had too
little data." Tested 2026-09-19 and rejected -- do not re-run this.

- The students sat the probes: Newark Purpose grade 7 is 335 probe rows, 335
  scored, 335 with no goal.
- They have the BOY benchmark the goal derives from -- 99.6% of goal-null
  students against 99.9% of goal-present ones. Prior-year PM is not an input to
  the current year's goal at all.
- It is binary per student: 1 of 759 grade-5 students had a mix of goal-present
  and goal-null rows.
- It concentrates in two cells -- Purpose grade 7 at 100% and Rise grade 5 at
  88% are 72% of the whole problem, while TEAM grade 7 and PPMS grade 5 are at
  zero.

Reads as an mClass setup or rostering condition at those cells. **Nobody has
asked Amplify what suppresses a `goal`** -- that is the open action, and until
it is answered the above is inference from the pattern. The `aimline_status`
gaps in the same grades (30.5% and 35.5%) are a superset and may have a separate
cause; not investigated.

## What the aimline verdict is judged against, and why it is not ours to change

Measured 2026-09-23. This is the single most misread thing in the whole domain,
so lead with it when anyone asks what "Meeting Aimline" means.

**We do not compute the verdict.** `met_measure_standard_goal` on the Aimline
branch is Amplify's own `aimline_status` translated at
`int_amplify__all_assessments.sql` -- `'At or Above'` to 1, `'Below'` to 0, and
null for anything else. `aimline_status` and `aimline_value_by_date` are both
raw columns in Amplify's PM SFTP file; the staging model only casts the type.
There is no comparison in our code to change.

**Amplify judges against the by-date value, not the season goal.** On AY2025
scored rows carrying both targets:

| Comparator                                               | Agrees with Amplify's verdict |
| -------------------------------------------------------- | ----------------------------- |
| `measure_standard_score >= goal` (aimline value by date) | 32,170 of 32,170              |
| `measure_standard_score >= aimline_season_student_goal`  | 26,134 of 32,170              |

The two comparators disagree on 6,036 rows. On every one of those 6,036 the
student is at or above the by-date value and below their season goal, and
Amplify says met. Zero exceptions in either direction.

**So a student can read "At or Above" every round and still finish below their
own season goal.** That is not a defect and it is not new; it is what the vendor
field means. It is also what people assume it does not mean, which is the whole
problem. The gap is large enough to matter: AY2025 BOY->MOY R3, grades 3-8,
scored students only --

| Measure                      | Reads Meeting Aimline | At or above season goal |
| ---------------------------- | --------------------- | ----------------------- |
| Reading Fluency (ORF)        | 37.3%                 | 24.1%                   |
| Reading Accuracy (ORF-Accu)  | 44.8%                 | 50.2%                   |
| Reading Comprehension (Maze) | 37.1%                 | 27.4%                   |
| Decoding (NWF-WRC)           | 32.5%                 | 18.2%                   |
| Letter Sounds (NWF-CLS)      | 30.6%                 | 13.4%                   |

ORF-Accu runs the other way because accuracy aimlines are nearly flat, so being
on the line at R3 is harder than clearing the season number. Do not assume the
error has one sign.

**How to say it to a non-technical audience**, which took three hours to arrive
at and should not be re-derived: _Meeting Aimline means Amplify says the student
is at or above their aimline as of this round -- on pace -- not that they have
reached their end-of-season goal. Those are different students, and on ORF it is
37% versus 24%._

**The traps, in the order sessions have fallen into them:**

1. Do not "fix" the comparator to use the season goal. That overrides the
   vendor's published verdict on 6,036 rows and puts the dashboard at odds with
   every aimline report Amplify has ever sent. If academics wants the
   season-goal reading, it is a second measure alongside the existing one, not a
   correction.
2. Do not put the season goal next to the verdict on a roster without the
   by-date target beside it. A student reading "Season Gap 0" next to "Meeting
   Aimline, Off-Track" looks like a contradiction until you can see that the
   round target was 8, the score was 13, and the grade-level benchmark was 30.
3. The evidence above is observational, not vendor-documented. Confirming it
   with Amplify is still open. Say so rather than citing it as their spec.

The existing note on `aimline_season_student_goal` in
`int_amplify__pm_met_criteria_aimline.yml` already says not to derive the
verdict from that column, and it is right. Read it before proposing otherwise.
