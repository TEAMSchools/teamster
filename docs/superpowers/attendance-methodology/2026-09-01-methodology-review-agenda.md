# Attendance methodology — agenda for Walters

**PR:** [#5057](https://github.com/TEAMSchools/teamster/pull/5057) · branch
`cristinabaldor/refactor/claude-cube-tesseract-multi-stage` · open,
`mergeable_state: blocked` (awaiting CODEOWNERS approval)

**Figures as of:** a full local build of both facts, 2026-09-02 — 29.6M and 4.4M
rows, with attendance through 2026-09-02. Topline figures come from production.
Every figure below was re-measured after the review; none is carried over from
the pre-review draft.

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
  attendance sit on one cube now, so `count_students` comes back alongside the
  rate it scopes. Early in a year the rate is volatile, so a figure without its
  denominator is unreadable — see 2.1.
- **Any pinned date resolves.** Break days carry a row, so a weekend or holiday
  answers the same as a school day. Chronic absence and truancy are available
  for one specific date, not only at period end.
- **Speed.** Cube queries went 10.1s to 2–4s. The old path measured 38.4s at
  year grain and 51.6s at week grain against a 55-second poll deadline.

---

## 2. What the review decided, and what it costs (25 min — the main event)

Three of the four decisions are shipped. What is left is the cost of each,
measured, plus the one question still open.

### The three big decisions

#### 2.1 · Chronic absence — the floor is gone

Walters' call. No minimum-membership-day floor anywhere, so every student with a
resolvable ADA counts. The 1–9 day band the floor used to discard is 15,609
students carrying 4,544 chronic-absence cases at AY2026 month grain, all now on
both sides of the rate.

**At year end this now agrees with Topline.**

| AY2025, complete year, three regions | Denominator | Chronically absent |       Rate |
| ------------------------------------ | ----------: | -----------------: | ---------: |
| Topline as published                 |       9,724 |              2,669 |     27.45% |
| **Built fact**                       |       9,740 |              2,678 | **27.49%** |

0.04 points apart. The floored version read 27.21%; removing the floor closed
the gap rather than opening one, which is worth saying out loud because it was
not the expected direction.

**The cost is volatility, and it is large right now.** AY2026 chronic absence,
by the date it is read:

| As of          | Avg membership days |  Rated | Chronically absent |       Rate |
| -------------- | ------------------: | -----: | -----------------: | ---------: |
| 2026-08-24     |                 3.3 | 10,935 |              2,187 |     20.00% |
| 2026-08-28     |                 7.2 | 10,896 |              2,634 |     24.17% |
| 2026-08-31     |                 8.1 | 10,919 |              2,916 |     26.71% |
| 2026-09-01     |                 9.1 | 10,934 |              3,098 |     28.33% |
| **2026-09-02** |                10.1 | 10,937 |              2,657 | **24.29%** |

**The rate moved 4.0 points in one day**, 28.33% to 24.29%. At ten membership
days a single present-or-absent day pushes a student across the 90% line, so
this is arithmetic, not a data problem. It settles as the denominator grows — by
AY2025 year end the same rule agrees with Topline to 0.04 points.

**What that means for a dashboard.** A chronic-absence figure published in the
first three weeks of a year will be revised by several points, day to day, and
nothing in the data model can prevent that. `count_students` is on both views so
the population is always visible beside the rate. If a stakeholder needs a
stable number in September, the honest answer is a stated start date, not a
floor.

**One caveat that outlives this meeting.** Every rate divides by
`count_students`, so a pre-AY2026 figure reads low — a student the enrollment
spine holds with no recorded attendance sits in the denominator and can never
reach the numerator. At year grain that is 3.7 points for AY2025, 5.4 for
AY2024, 6.3 for AY2023, essentially all of it Miami. #5114 closes it. AY2026
forward is already unaffected, so this only bites on historical figures.

#### 2.2 · Truancy — any day in the week, or the week's last day

Truancy is a **status**, not an event: both regional rules test a running
absence figure, so it turns on and off within a week. Topline keeps the max
across the week; this fact reads the last membership day. Walters asked for the
magnitude.

**The disagreement is strictly one-directional.** Period-end can only ever be a
subset of any-day, so the whole question is whether we keep a student who was
truant on Monday and recovered by Friday. Measured off the same rows, so this
isolates the reading and nothing else:

| Academic year  | Student-weeks | Any-day | Period-end | Dropped | Share of any-day |
| -------------- | ------------: | ------: | ---------: | ------: | ---------------: |
| AY2024         |       350,367 |  14,381 |     11,796 |   2,585 |        **18.0%** |
| AY2025         |       369,984 |  11,448 |      9,391 |   2,057 |        **18.0%** |
| AY2026 to date |        29,893 |  13,145 |      9,324 |   3,821 |            29.1% |

Zero student-weeks go the other way in any year. Over a settled year period-end
drops **18% of the any-day count**, and it landed on 18.0% twice running — as
stable a figure as anything in this document.

**But almost all of it is the start of the year.** AY2025, share of the any-day
count that period-end drops, by month:

| Month        | Any-day | Period-end | Share dropped |
| ------------ | ------: | ---------: | ------------: |
| Aug 2025     |   1,360 |        879 |     **35.4%** |
| Sep 2025     |   2,729 |      1,866 |         31.6% |
| Oct 2025     |   1,086 |        853 |         21.5% |
| Nov 2025     |     880 |        755 |         14.2% |
| Dec 2025     |     810 |        731 |          9.8% |
| Jan 2026     |     891 |        789 |         11.4% |
| Feb 2026     |     631 |        575 |          8.9% |
| Mar 2026     |   1,010 |        955 |          5.4% |
| Apr 2026     |     608 |        584 |          3.9% |
| May 2026     |     806 |        773 |          4.1% |
| **Jun 2026** |     637 |        631 |      **0.9%** |

Monotonic decay, 35.4% to 0.9%. **After October the two readings are the same
measure.** The NJ figure is a running rate times the year's membership days, so
early on the rate swings week to week on a handful of days and a student flips
in and out; by spring the rate barely moves and there is nothing to flip.

**The human magnitude, AY2025.** Of 9,724 students:

- 1,938 were truant at some point under any-day, 1,429 under period-end.
- **509 students would carry a truancy flag at some point under Topline's
  reading and never under ours** — 5.2% of all students, and 26% of the any-day
  truant population.
- 1,570 students had at least one week where the status flipped mid-week.

**Recommendation: period-end, and it costs less than it looks.** Any-day asks
"was this student ever truant this week", which for a running-rate status means
"did the noisiest day of the week cross the line". Period-end asks "is this
student truant now", which is what a status is for and what an intervention list
needs. The reading only diverges materially in August and September, and that is
exactly where the underlying projection is least trustworthy — see 2.4.

If Walters prefers any-day for continuity with Topline, the cost is a September
truancy count roughly a third higher than the settled status, and 509 students a
year appearing on a list they are off by Friday.

#### 2.3 · Total Enrollment — anchored on the first membership day

Walters' call, shipped. `fct_student_periods` carries
`period_start_membership_date_key`, the student's own earliest membership day in
the period, exposed on the view as `period_start_membership_date`.

| Week of        | Topline (Monday) |  Anchored | First membership days |
| -------------- | ---------------: | --------: | --------------------- |
| **2026-08-10** |            **0** | **1,514** | 08-12 to 08-14        |
| **2026-08-17** |       **11,256** | **6,359** | 08-17 to 08-21        |
| 2026-08-24     |           11,099 |    11,037 | 08-24 to 08-28        |
| 2026-08-31     |           11,020 |    10,977 | 08-31 to 09-02        |

Topline's Monday anchor fails in both directions at the start of a year. It
reports **0** for the week Miami opened — 1,514 students were in school
Wednesday to Friday — and **11,256** for the week of 17 August, counting the
whole New Jersey roster two days before New Jersey's first student day of
Wednesday 19 August. Settled weeks converge to within 0.4%.

**Open on the Topline side:** whether Topline's own Total Enrollment gets the
same anchor. That is Topline's number, not this layer's, and it is wrong today
independently of this PR.

### Shared problems — not a methodology choice, but they will get asked about

#### 2.4 · Truancy reads about 50% on Topline right now

| AY2026 week    | Topline student-weeks | Topline rate | Built fact student-weeks | Built fact rate |
| -------------- | --------------------: | -----------: | -----------------------: | --------------: |
| 2026-08-10     |                 1,606 |        0.00% |                    1,514 |           0.00% |
| 2026-08-17     |                11,312 |       57.69% |                    6,361 |          24.19% |
| 2026-08-24     |                11,152 |       53.36% |                   11,040 |          49.39% |
| **2026-08-31** |                11,061 |   **50.85%** |                   10,978 |      **21.24%** |

The NJ rule projects a student's absences to a full-year total, so two absences
in seven days projects past the 50-absence threshold. Half the network trips it
on Topline, and it falls week by week as the projection settles.

**The two methods do not agree, and the gap is widest in the current week** —
50.85% against 21.24%. Period-end reads the settled projection; any-day reads
the worst day of the week. That is the same choice as 2.2, which is why 2.2
matters more than the AY2025 figure alone suggests.

**Neither method causes the projection problem and neither fixes it.** It is one
upstream flag. Whichever reading we pick, a 50% truancy headline is available to
anyone querying Topline today, and that needs its own fix.

**2.5 · Miami AY2020–AY2025 attendance is excluded, and being restored.** `main`
commit 2ed91424a dropped the frozen archive (closing #4803) after Focus re-dated
959 enrollment stints so the fact rows pointed at enrollment records
`dim_student_enrollments` no longer holds. Every attendance surface reads that
model, so the gap is network-wide rather than a Cube artifact.

**#5114 is now open to restore it** — the archive still serves two sibling
facts. Treat this as temporary: pre-AY2026 rates gain a fourth region when it
lands, so every pre-AY2026 figure in this document is a three-region rate that
will move.

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
Paterson reads 92.68% / 93.37% ADA against Newark's 92.52%.

**Walters' read is that this is a permanent exclusion for pre-AY2026** — the
conversion items were never captured at the time, so unlike Miami's there is
nothing to restore from. That is now recorded in the fact and view descriptions.
It means Paterson's pre-AY2026 presence-derived values carry an uncertainty that
will not be resolved, rather than one pending a backfill.

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
- **Chronic absence and truancy no longer reset when a student changes
  schools.** Cristina's call. They accumulate per student per year while the
  rates still aggregate by school, so a transferring student carries their
  position into the new school's rows for the periods they are there. Affects 11
  to 46 student-years a year, 0.1% to 0.4%, and closes #5103 rather than
  documenting it.
- **A day we could not measure supports neither verdict.** `is_truant` used to
  survive a null attendance value, a break day and a pre-AY2021
  `membership_value = 0` row, so 246,583 daily rows published a truancy verdict
  with no ADA tier beside them. Both flags are now gated on the cumulative
  count, so they resolve over identical rows and one denominator serves every
  rate. Cost: 105,679 daily rows and 4,367 period rows stop reading truant,
  1.72% of the period numerator.

### New capability — nobody has agreed to it yet

- **Cumulative truancy at month and year grain.** Topline aggregates every
  indicator by week and never across weeks, so no month or year truancy figure
  exists today. This produces both. Nothing to reconcile, but also nothing
  anyone has signed off.
- **186 Miami AY2026 enrollment stints produce no rows, #5024.** Their
  `exitdate` is on or before their `entrydate`, so the spine's clamp yields no
  day. Upstream, not introduced here. A Miami AY2026 headcount from these facts
  runs short by up to that many stints until #5024 is fixed.

---

## 3. Chase-down list (10 min)

| #   | Item                                                                                                                                                                       | Owner            | Blocks                                            |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------- | ------------------------------------------------- |
| 1   | Compare truancy any-day vs period-end against how other networks and the states report it — the one decision still open, and the current-week gap is 50.85% against 21.24% | me               | Deciding 2.2                                      |
| 2   | Confirm KIPP Foundation reads chronic absence as item 8 (at or below 90.0%), not item 1                                                                                    | ?                | Any figure going to KIPP                          |
| 3   | Confirm #4193 is permanent for pre-AY2026, as Walters reads it                                                                                                             | PowerSchool side | Whether the caveat is final or pending a backfill |
| 4   | Decide whether Topline's Monday anchor gets the same first-membership-day fix                                                                                              | ?                | Topline's own opening-week figures                |
| 5   | Decide whether the NJ truancy projection gets its own fix, and where                                                                                                       | ?                | 2.4 — asked about either way                      |
| 6   | Decide what a dashboard publishes in the first three weeks of a year, given the rate moves ~4 points a day                                                                 | ?                | Any September figure                              |

Closed since the review: the Total Enrollment gap is measured and anchored
(2.3), every chronic-absence and truancy figure is re-measured off built facts,
the Miami rundown is tracked at #5114, and #5103 is closed by the per-student
accumulation.

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
- New rules read from `fct_student_days.sql` (tier ladder, and both `ada_tier`
  and `is_truant` gated on `n_membership_days_ytd > 0`) and
  `fct_student_periods.sql` (`period_start_membership_date_key` and
  `period_end_date_key` = the student's own first and last membership day in the
  bucket).
- Every figure in section 2 is read off a local build of both facts on
  2026-09-02 — `fct_student_days` 29.6M rows, `fct_student_periods` 4.4M rows,
  attendance through 2026-09-02. The Topline side comes from prod
  `int_topline__ada_running_weekly`, `int_topline__truancy_weekly` and
  `int_extracts__student_enrollments_weeks`.
- AY2025 figures exclude Miami on both sides, so they compare the three regions
  production serves today. #5114 will change that.
- Rates divide by `count_students`, every student in the slice. A second
  flag-scoped denominator was built and then dropped as confusing; the cost is
  that pre-AY2026 rates read 3.7 to 6.3 points low until #5114 lands, which the
  cube and view descriptions now state.
- `int_topline__truancy_weekly` carries rows for weeks that have not happened
  yet, because `int_students__attendance_daily` holds the full scheduled
  calendar. `int_topline__dashboard_aggregations` filters them with
  `term <= current_date`, so the dashboard is fine — but do not read that
  intermediate model directly.
- First in-session dates come from `int_students__calendar_day`; the first
  student _membership_ day is 2026-08-12 for Miami and 2026-08-19 for all three
  NJ regions.
