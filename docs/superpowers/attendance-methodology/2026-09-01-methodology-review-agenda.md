# Attendance methodology — agenda for Walters

**PR:** [#5057](https://github.com/TEAMSchools/teamster/pull/5057) · branch
`cristinabaldor/refactor/claude-cube-tesseract-multi-stage` · open,
`mergeable_state: blocked` (awaiting CODEOWNERS approval)

**Figures as of:** the dbt Cloud CI build of commit `4d0dc38e4`, 2026-09-01
21:09 — `fct_student_days` 29,590,677 rows, `fct_student_periods` 4,374,240
rows. Topline figures come from production.

**Read first:** nothing on a production dashboard moves when this merges.
Tableau and Topline both read `int_students__attendance_daily` directly. Neither
reads `fct_student_days` or `fct_student_periods` — verified by grep across
`src/`; the only consumers are `src/cube/` and the facts' own YAML. Every
discrepancy below is Cube-vs-production, not a number that changes under
someone's feet.

---

## 1. What this ships (10 min)

Chronic absence, the ADA tier and truancy are now computed once, in dbt, on
`fct_student_days` — a materialized daily fact where every row carries the
student's cumulative position at that school. `fct_student_periods` reads that
fact at period end and derives nothing. Cube computes nothing at query time.

What that buys, in the order it matters to the dashboard:

- **Chronic absence and truancy cut by subgroup at period grain** — race,
  gender, grade level, ELL, IEP, special education, meal eligibility, homeroom
  teacher, term, campus, city. That is the equity analysis the dashboard exists
  for, and it did not work at period grain before.
- **A population count beside every rate, from the same query.** Enrollment and
  attendance sit on one cube now, so `count_students` and
  `count_students_min_10_days` come back alongside the rate they scope.
  Eligibility accumulates through the year, so a rate without its denominator is
  unreadable in September.
- **Any pinned date resolves.** Break days carry a row, so a weekend or holiday
  answers the same as a school day. Chronic absence and truancy are available
  for one specific date, not only at period end.
- **Speed.** Cube queries went 10.1s to 2–4s. The old path measured 38.4s at
  year grain and 51.6s at week grain against a 55-second poll deadline.

---

## 2. Where we differ from production today (25 min — the main event)

Ranked by how much the number moves.

### Must decide

#### 2.1 · Chronic absence — the 10-day eligibility floor

Read off the built branch facts. AY2025 excludes Miami on both sides, so the
comparison is the three regions production will actually serve.

| AY2025, complete year                                    | Population | Chronically absent |       Rate |
| -------------------------------------------------------- | ---------: | -----------------: | ---------: |
| Topline as published — each student's latest scored week |      9,724 |              2,669 |     27.45% |
| Topline's rule at student x school x year                |      9,761 |              2,677 |     27.43% |
| Built fact, floor removed                                |      9,740 |              2,676 |     27.47% |
| **Built fact as shipped, 10-day floor**                  |  **9,672** |          **2,632** | **27.21%** |

**At full year the two rules agree to one student.** 2,677 against 2,676 on the
numerator, at the same grain. Every other difference — rounding, partial days,
comparing day counts instead of a decimal — moves nothing. The entire gap is the
floor: 0.26 points, and 68 students out of the denominator.

The floor is not a full-year story, though. It is an opening-weeks story:

| AY2026, cumulative to 2026-09-01        | Population | Chronically absent |       Rate |
| --------------------------------------- | ---------: | -----------------: | ---------: |
| Topline as published                    |     11,339 |              3,317 |     29.25% |
| Built fact, floor removed               |     11,241 |              3,427 |     30.49% |
| **Built fact as shipped, 10-day floor** |  **5,062** |          **1,556** | **30.74%** |

Three weeks in, the floor **halves the population** — 11,241 down to 5,062 —
while moving the rate by a quarter of a point. It is a statement about who you
are willing to judge, not about where the rate lands.

That population gap is closing by the day. The most membership days any student
has reached is 15. New Jersey's first student day was 2026-08-19, which puts NJ
students at exactly 10 days on 2026-09-01 — they crossed the floor that morning.
Miami, which opened 2026-08-12, crossed a week earlier.

**Decision:** floor or no floor. If floor, the first three weeks of a year have
no chronic-absence rate for most of the network, and
`count_students_min_10_days` has to be on screen next to the rate.

#### 2.2 · Truancy — any day in the period, or the period's last day

| AY2025, week grain, three regions                             | Student-weeks | Truant |       Rate |
| ------------------------------------------------------------- | ------------: | -----: | ---------: |
| Topline — truant on **any** day of the week                   |       370,863 | 11,848 |     3.195% |
| **Built fact** — status on the week's **last membership day** |       370,159 |  9,392 | **2.537%** |

A fifth lower. The flag turns on _and_ off — Miami counts absences in a rolling
90-day window, NJ projects the year's absences from the running rate — so a
student can be truant on Monday and not by Friday. Topline counts them; the
built fact does not.

No eligibility floor applies to truancy on either side. Neither the Miami nor
the NJ rule requires one.

**Decision:** which is the reportable status. Independent of 2.1.

#### 2.3 · Total Enrollment — the anchor day

Measured against the built branch facts, network, `student_number`-deduped on
all three sides.

| Week of        | Topline (Monday) | Daily view, pinned Monday | Period view, served in week |
| -------------- | ---------------: | ------------------------: | --------------------------: |
| 2025-10-06     |           10,640 |                    10,636 |                      10,638 |
| 2026-05-04     |           10,401 |                    10,399 |                      10,393 |
| **2026-08-10** |            **0** |                         0 |                   **1,514** |
| **2026-08-17** |       **11,269** |                 **1,512** |                   **6,391** |
| 2026-08-24     |           11,114 |                    11,114 |                      11,060 |
| 2026-08-31     |           11,044 |                    11,042 |                      10,964 |

**Settled weeks: pinning the Monday on the daily view reproduces Topline.** The
two disagree on 0 to 4 students out of ~10,500 — under 0.04%, and never by more
than 4 in one direction and 1 in the other. If we want Topline's Total
Enrollment on this layer, that is the measure, and it needs no decision.

**"Served in the period" is a genuinely different question** and should not be
substituted for it. It runs 2 to 80 students below Topline in settled weeks and
disagrees in both directions, because it requires a membership day in the week.

**The per-school double count is small.** An in-district mid-week transfer
counts once per school: 0 to 5 students a week (2026-08-24: 11,065 rows against
11,060 students). Real, but not the thing to spend the meeting on.

**The whole gap is the first two weeks of an academic year, and it is a Topline
defect rather than a methodology choice.** Topline's Monday anchor fails twice,
in opposite directions:

- **Week of 2026-08-10: Topline reports 0.** Miami was in session 12–14 August —
  1,514 students. Topline's `is_enrolled_week` tests the _Monday_, and Miami
  entry dates fall after Monday the 10th. Its own `is_enrolled_week_end` column,
  which tests the Sunday, returns 1,511 for that week and is not the one the
  metric uses.
- **Week of 2026-08-17: Topline reports 11,269.** NJ's first student day is
  **Wednesday 2026-08-19**. Topline counts 9,757 NJ students as enrolled two
  days before their school year begins, because entry dates roll over to 1 July
  while the school calendar week starting the 17th already exists.

**Decision:** none needed for the measure — pinning the Monday matches. The
question for the room is whether Topline's Monday anchor should keep reporting
zero for a week Miami was in school, and a full roster for a week New Jersey was
not.

### Shared problems — not a methodology choice, but they will get asked about

#### 2.4 · Truancy reads about 50% right now, on both methods

| AY2026 week    | Topline student-weeks | Topline truant | Topline rate | Built fact student-weeks | Built fact truant | Built fact rate |
| -------------- | --------------------: | -------------: | -----------: | -----------------------: | ----------------: | --------------: |
| 2026-08-10     |                 1,606 |              0 |        0.00% |                    1,514 |                 0 |           0.00% |
| 2026-08-17     |                11,327 |          6,530 |       57.65% |                    6,393 |             1,566 |          24.50% |
| 2026-08-24     |                11,169 |          5,953 |       53.30% |                   11,065 |             5,482 |          49.54% |
| **2026-08-31** |                11,066 |          5,592 |   **50.53%** |                   10,965 |             5,544 |      **50.56%** |

The NJ rule projects a student's absences to a full-year total, so two absences
in seven days projects past the 50-absence threshold. Half the network trips it,
and the rate falls week by week as the projection settles.

**By the third week the two methods agree to three hundredths of a point.**
Nothing in this PR hides the problem and nothing in it causes the problem. It is
the same flag on both sides, and **it needs its own fix, which is not in this
PR.**

The week of 2026-08-17 differs only because Topline counts students whose
schools were not yet in session — see 2.3.

**2.5 · Miami AY2020–AY2025 attendance is excluded.** Decided, not open — `main`
commit 2ed91424a, closing #4803, after Focus re-dated 959 enrollment stints so
the fact rows pointed at enrollment records `dim_student_enrollments` no longer
holds. Every attendance surface reads that model, so the gap is network-wide,
not a Cube artifact. AY2026 forward includes Miami through Focus.

**Consequence for labelling:** for AY2025 and earlier, a rate is a three-region
figure and a headcount is a four-region figure. Same year, different footprint.
Including Miami gives 26.04% AY2025 chronic absence against 27.22% excluding it
— Miami sits below the network at 17.99%, so its absence _raises_ the network
rate.

**2.6 · Paterson #4193, open and unquantified.** PowerSchool
attendance-conversion items are incomplete, which touches `attendance_value` and
therefore ADA, tier, chronic absence and truancy. `membership_value` is clean,
so enrollment is unaffected. I could not reproduce the claimed suppression: only
275 of 92,809 AY2025 membership days carry a null attendance value (0.3%), and
Paterson reads 92.68% / 93.37% ADA against Newark's 92.52%. **Someone on the
PowerSchool side can settle this faster than I can from aggregates.**

### Agrees with production — say it, then move on

- **ADA matches.** AY2025 network ADA is 0.920679 here against 0.920678 from
  `int_students__attendance_daily`, the model every Tableau attendance surface
  and both Topline attendance models read. The whole delta is 13 membership days
  — one student, 13 dates in November 2025, attendance rows on days the
  enrollment spine says the student was not enrolled. Sixth decimal. Worth
  knowing before someone finds it.
- **The 90.0% boundary agrees with Topline.** Topline uses
  `ada_running <= 0.90`; this PR uses `<= 90.0%` on accumulated day counts.
  Production Cube uses `< 0.90` and is the odd one out — moving it aligns Cube
  with Topline and shifts 198 AY2025 enrollments. **Caveat:** KIPP Foundation
  criteria contradict themselves — item 1 calls 90% and above on track, item 8
  defines chronic absence as at or below 90.0%. We follow item 8 and both state
  criteria. **Confirm with KIPP Foundation before the figure goes to them.** If
  they want item 1, it is one operator and a rebuild.
- **Rounding, partial days, decimal-vs-day-counts move nothing.** Applied one at
  a time to the same AY2025 population: 0 students each.
- **Mid-year leavers are included, same as Topline.** Topline's spine keys on
  entry and exit dates rather than status. Production Cube excludes students
  marked "Transferred Out" in the current academic year; this PR does not, which
  closes that gap. The predicate never fired for AY2025 but will fire in AY2026,
  so an AY2026 comparison against a production Cube figure will differ by an
  amount nobody has measured.

### New capability — nobody has agreed to it yet

- **Cumulative truancy at month and year grain.** Topline aggregates every
  indicator by week and never across weeks, so no month or year truancy figure
  exists today. This produces both. Nothing to reconcile, but also nothing
  anyone has signed off.
- **Truancy grain bug, #5103.** The `is_truant` carry-forward runs per school
  while the flag it carries is computed per student per year, so an in-district
  transfer can read false at the new school. 19 to 62 student-years a year,
  0.16% to 0.58%, and only within the truant subset.
- **186 Miami AY2026 enrollment stints produce no rows, #5024.** Their
  `exitdate` is on or before their `entrydate`, so the spine's clamp yields no
  day. Upstream, not introduced here. A Miami AY2026 headcount from these facts
  runs short by up to that many stints until #5024 is fixed.

---

## 3. Chase-down list (10 min)

| #   | Item                                                                                                                                      | Owner            | Blocks                                                          |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | --------------------------------------------------------------- |
| 1   | Confirm KIPP Foundation reads chronic absence as item 8 (at or below 90.0%), not item 1                                                   | ?                | Any figure going to KIPP                                        |
| 2   | Status check on #4193 — is Paterson attendance still distorted?                                                                           | PowerSchool side | Whether the caveat comes off both the fact and the view         |
| 3   | Decide whether Topline's Monday anchor gets fixed — it reports 0 for the week Miami opened and a full NJ roster two days before NJ opened | ?                | Topline's own opening-week figures, independent of this PR      |
| 4   | Decide whether the NJ truancy projection gets its own fix, and where                                                                      | ?                | 2.4 — it will be asked about either way                         |
| 5   | Flag the stale PR-schema attendance view so the next person validating does not read a four-region AY2025                                 | me               | Any validation run against `dbt_cloud_pr_70403104388001_5057_*` |

**One thing to know if you validate any of this yourself.** The PR-schema copy
of `int_students__attendance_daily` was created 2026-08-28 and predates `main`'s
removal of the frozen Miami PowerSchool archive, so it still returns 229,463
Miami AY2025 rows that production does not have. Anything read off
`dbt_cloud_pr_70403104388001_5057_marts` for AY2025 is therefore a
**four-region** figure unless Miami is filtered out — network chronic absence
reads 26.03% there against the 27.21% production will serve. AY2026 is
unaffected: the PR-schema and prod views return the identical 2,042,693 rows.
Every AY2025 figure in this document has Miami excluded on both sides.

---

## 4. Merge mechanics — 3 minutes, but it bites if skipped

Cube Cloud redeploys the moment this lands on `main`. The Dagster deploy plus
the sensor tick that builds the new facts takes minutes to tens of minutes. Cube
wins that race, so for that window the old measures are gone and the new views
point at tables that do not exist — every query fails at BigQuery, one at a
time, nothing failing loudly.

Ordering, from the PR:

1. Switch Cube Cloud to CLI deploy mode (stops the automatic production build)
1. Merge
1. Wait for the Dagster deploy across all five code locations
1. Run one ordered build: `int_students__enrollment_days` → `fct_student_days` →
   `fct_student_periods`
1. Confirm both marts hold rows
1. Deploy Cube deliberately, then switch back to Git deploy mode

Then @cbini drops five orphaned prod relations. The old
`fct_student_attendance_daily` marts **view** is the one that matters: it is a
view, so it keeps resolving live and keeps publishing the pre-2026
chronic-absence definition to anyone querying the warehouse directly. Ninety
days of `JOBS_BY_PROJECT` show no consumer, so this is cleanup rather than a
live wrong number.

---

## Appendix — where each figure comes from

- Topline rules read from `int_topline__ada_running_weekly`
  (`round(safe_divide(...), 3)`, partitioned per school),
  `int_topline__truancy_weekly` (`max(if(is_truant, 1, 0))` per
  student-school-week), and `int_topline__student_metrics`
  (`if(ada_running <= 0.90, 1, 0)`; `Total Enrollment` = `is_enrolled_week` from
  `int_extracts__student_enrollments_weeks`, i.e. Monday between entry and
  exit).
- New rules read from `fct_student_days.sql` (tier ladder, `is_ca_eligible`,
  `is_truant` carry-forward) and `fct_student_periods.sql`
  (`period_end_date_key` = the student's own last membership day in the bucket).
- Chronic-absence and truancy figures are read off the built branch
  `fct_student_periods`; the Topline side comes from prod
  `int_topline__ada_running_weekly` and `int_topline__truancy_weekly`, plus one
  reconstruction of Topline's rule at student x school x year from prod
  `int_students__attendance_daily` so the grains line up.
- `int_topline__truancy_weekly` carries rows for weeks that have not happened
  yet, because `int_students__attendance_daily` holds the full scheduled
  calendar. `int_topline__dashboard_aggregations` filters them with
  `term <= current_date`, so the dashboard is fine — but do not read that
  intermediate model directly.
- Total Enrollment figures in 2.3 are read off the built branch facts in
  `dbt_cloud_pr_70403104388001_5057_marts` (`fct_student_days` 29,590,829 rows,
  `fct_student_periods` 4,374,313 rows, both built 2026-09-01 20:23) against
  prod `int_extracts__student_enrollments_weeks`. First in-session dates come
  from `int_students__calendar_day`; first student _membership_ day is
  2026-08-12 for Miami and 2026-08-19 for all three NJ regions.
