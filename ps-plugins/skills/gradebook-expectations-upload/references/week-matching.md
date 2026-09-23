# How the audit reads this, and how to match weeks

Shared by every playbook that touches counts (rollover, refresh) or diagnoses
them (troubleshoot).

## How the audit reads this

**Per quarter, exactly one row is operative on the dashboard — the most recent
week.**

- **A quarter that has closed** uses that quarter's last week, forever. It stays
  on file and keeps showing on the dashboard even after later quarters start — a
  closed quarter's row is frozen at its final week, not blank.
- **A quarter that is running** uses **the week before the current week**, so
  teachers are not penalised for a week still in progress. This row moves
  forward as each week completes.

So at any point in the middle of the year, the dashboard can be showing three
different things at once for three different quarters: Q1 frozen at its last
week, Q2 frozen at its last week, and Q3 sitting on whichever week most recently
finished — each perfectly correct, and each a different kind of "current." If
something looks wrong, check which of these you are actually looking at before
assuming the data is bad — see `troubleshoot.md`.

**Gaps are filled, not flagged.** The query fills zeros at the start of the
year, and carries the previous week forward for a missing later week. Both exist
so that **expected assignments are never null**.

**So a missing or short week never surfaces as an error.** The query carries
forward from whatever week _is_ present and serves a number that looks exactly
like a real one — just lower. This is the same silence the skill warns about for
an unreplaced quarter, reached a different way.

Counts are **cumulative within a quarter** — Camden Q1 runs `0,0,0,0` at week 1
up to `15,9,9,2` at week 11 — which is why an earlier week reads as a smaller
expectation rather than as missing data.

Because the active-quarter read is the _previous_ week, intermediate weeks are
not just an audit trail behind the final one. Each becomes the operative row in
its turn.

## Give every row a week number and a value

This is the whole transformation. Do it per tab, per quarter, in date order.

### Week numbers come from `PS Full Calendar`, never from the sheet

1. Take the row's `Dates` from the Academics tab.
2. Find the row in `PS Full Calendar` (`sheets.md`) for that **region and school
   level** whose `week_start_monday` and `week_end_friday` bracket those dates.
   Its `week_number_quarter` is the week number. The calendar has an MS row and
   an HS row per week, and the two can diverge, so matching on region alone
   picks one of them arbitrarily.

`PS Full Calendar` carries the whole school year, not just weeks that have
already loaded into PowerSchool, so this works the same way for a week that
happened last month or one that hasn't happened yet — including a genuine
rollover, before a single row exists anywhere else. There is no "last week you
matched" to run out of and continue numbering from; every row gets matched
against the calendar the same way.

> Confirm `PS Full Calendar`'s `academic_year` column shows the year you're
> loading before matching against it — see `sheets.md`. The tab can silently
> show last year's weeks all summer if the warehouse hasn't rolled the year over
> yet.

> 🛑 **Never use `Assigned Week #`, and never use row order.** It is a human's
> numbering, not PowerSchool's.
>
> **It will often look perfectly reasonable, and that is the trap.** On the
> Camden Q1 tab it reads 1–10, tidy and plausible — and wrong, because
> PowerSchool's Q1 has eleven weeks and starts a week earlier. Taking it at face
> value there costs you a week and shifts every count in the region. On other
> tabs it is visibly broken (Newark HS and Camden both restart Q2 at 10 after Q1
> ended at 10), but do not wait for it to look broken before distrusting it.
> Match on dates every time.

**PowerSchool's calendar can have weeks the Academics tab never lists.**
Camden's Q1 week 1 is 8/17–8/21; Academics' Camden tab starts at 8/24. That week
still needs a row, and Academics' first row is week **2**, not week 1. If you
number by row order you shift every Camden week by one and every count with it.

### Filling values

Per category column, within one quarter, in week order:

1. Use the sheet's value if there is one.
2. **No value, and it is the first week of the quarter → `0`.**
3. **No value, and it is not the first week → carry the previous row's value
   forward**, within the same quarter.

`---` (or `--`) is not a count. It means no expectation — a revisions week, a
break — and takes **rule 2 or rule 3, whichever applies**: `0` if it is the
quarter's first week, the previous row's value otherwise. It usually appears on
a quarter's last row, but not always: Newark HS Q1 week 1 and Camden Q1 week 2
both carry `--` in `Summative Mastery`, and the first of those is a rule 2 case.
Carry-forward never crosses a quarter boundary; each quarter starts fresh at
rule 2.

This is the same rule the audit query applies when it meets a gap, so the file
and the query agree rather than each patching holes their own way. It is also
why a revisions week repeats the prior week's counts, which is correct: a week
with no new expectations still expects everything assigned so far to be graded.
