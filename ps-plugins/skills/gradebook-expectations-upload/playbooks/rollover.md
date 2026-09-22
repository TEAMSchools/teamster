# Playbook A — Start-of-year rollover

**When this is the right playbook:** a new school year is starting and the full
year's expectations calendar needs to go into all three PowerSchool instances
for the first time. This is the normal case — Academics typically finalizes the
whole year before school starts, and it all loads at once, then gets edited
incrementally as the year goes (that's `refresh.md`).

_A quarter-at-a-time start of year (only Q1 decided when school starts) is
atypical — treat it as `refresh.md` instead, and use its messaging about what's
still outstanding._

## Steps

1. **Read `../references/sheets.md`** if you have not already — the two
   spreadsheets, their columns, and which tab feeds which instance.
2. **Confirm the rollover can actually run.** Two things have to both be true:

   1. The new school year's calendar is already loaded in PowerSchool.
   2. **The data warehouse's current academic year has been rolled over.**

   Check the second one by opening `PS Full Calendar` (`sheets.md`) and reading
   its `academic_year` column.

   🛑 **If it does not show the year you are loading, stop here and tell the
   data team the academic year needs rolling over in the warehouse first.**
   `PS Full Calendar` is filtered to whatever year the warehouse currently calls
   "current," and a PowerSchool instance can sit in the next school year all
   summer while that setting still points at the old one. When that happens the
   tab shows **last year's** weeks — same columns, same shape, same quarter
   names, nothing on screen telling you. Building a rollover file against it in
   that window produces a confident, wrong upload with no error anywhere.

3. **Check what's actually decided.** Open every Academics tab. Don't ask which
   quarters are being loaded — determine it from which tabs are real (non-draft)
   versus "under construction." Report what you found: "All four quarters are
   decided for all three regions" is the expected finding here. If it isn't — if
   some quarters are still drafts — say so and switch to `refresh.md`'s framing
   for what's missing; don't silently load a partial year under this playbook.
4. **Read `../references/week-matching.md`** and give every row in every tab a
   PowerSchool week number and a filled value, per quarter, per region.
   `PS Full Calendar` carries the whole year, including weeks that have not
   happened yet, so this works the same way whether the year is brand new or
   partway through.
5. **Read `../references/csv-format.md`** and build one CSV per instance
   (Camden, Newark, Paterson), covering all four quarters. Run every check in
   it, including the prod sanity-check.
6. **Read `../references/powerschool-navigation.md`** and upload. For a full
   four-quarter load, this is the **Replace** path (step 2's first bullet) — one
   action does the delete and the load together for that instance.
7. **Verify the next day** as that same reference describes, and tell the data
   team what you loaded.

## Stop and escalate if

- `PS Full Calendar`'s `academic_year` column doesn't show the year you're
  loading (step 2).
- Any of `csv-format.md`'s checks fail and you can't see why.
- A region's tabs disagree about which quarters are actually ready.
- The numbers look implausible (see `../SKILL.md`'s escalation list).
