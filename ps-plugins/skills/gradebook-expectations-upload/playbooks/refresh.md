# Playbook B — Mid-year refresh

**When this is the right playbook:** some quarters' counts are newly decided,
changed, or need reloading — but not a full first-time rollover. This is also
the playbook for an atypical start of year where only part of the calendar is
ready (this year's Q1-only situation is an example, not the norm — see
`rollover.md`).

## Steps

1. **Read `../references/sheets.md`** if you have not already, then open
   `PS Full Calendar` and **check its `academic_year` column shows the year you
   are loading.** If it does not, stop here and tell the data team the year
   needs rolling over in the warehouse first.

   This is not a rollover-only check. Mid-year is where it is hardest to notice:
   the tab still shows a full set of weeks with ordinary dates, every check
   below still passes, and every week number is shifted. Nothing downstream
   catches it.

2. **Check what's actually decided.** Open every Academics tab you were asked
   about (or, if unspecified, every tab). Don't ask which quarters are being
   loaded — the sheet already answers it: a real, non-draft tab means it's
   decided. Report what you found ("Only Q1 is decided for all three regions;
   Q2-4 are still drafts") and proceed with what's decided. Only ask a question
   here if the sheet is genuinely ambiguous or contradicts what the person asked
   for — e.g. they said "load Q2" but only Q1 is decided.

   A tab holding **two blocks for the same quarter** is not ambiguity. Resolve
   it against the calendar per `../references/week-matching.md` and say which
   block you used.

3. **Read `../references/week-matching.md`** and give every row in every decided
   quarter a PowerSchool week number and a filled value.
4. **Read `../references/csv-format.md`** and build one CSV per instance,
   covering only the decided quarter(s). Run every check, including the prod
   sanity-check — for a refresh there will usually be existing `Plugin Data Raw`
   rows to check against; use them.
5. **Say clearly, for every quarter NOT being loaded:**

   > Q_n_ still has last year's expectations. It opens Monday _date_, and from
   > that Monday the audit will be wrong for Q_n_ until it is replaced.

   **Take the date from `PS Full Calendar`** — the `week_start_monday` of that
   quarter's week 1, for that region and school level. The calendar holds the
   whole year, so this works for a quarter whose Academics tab is still an
   "under construction" draft or has no rows at all. That is exactly when the
   deadline matters most, and it is always determinable.

   Never say the deadline cannot be worked out, and never ask T&L to supply it.
   They are the person you are talking to, and the date is the one thing here
   they need from you.

   **Why this matters more than it looks:** an unreplaced future quarter does
   not break anything visibly. It serves last year's counts, which look like
   real numbers, so the dashboard reports confidently wrong results for the
   whole quarter. Nobody gets an error. A blank dashboard gets reported the same
   day; a wrong expectation can run for months.

6. **Read `../references/powerschool-navigation.md`** and walk the person
   through it. Which mode depends on what your file holds, not on how many
   quarters you were asked about: **Add** when the file is one quarter and the
   others must survive untouched, **Replace** when the file _is_ the whole
   intended contents of the instance.

   Say that as the reason, not as a rule. Replace is not something to talk
   people out of — it is correct for a rollover, for a deliberate mass
   correction, and for the whole-instance file that replaces one quarter's rows.
   What is wrong is Replace with a partial file. If the person asks for Replace,
   find out which they have before answering.

   **Work out which path applies before you describe any of it**, from what
   `Plugin Data Raw` showed you in step 4. A quarter with no rows there goes
   straight to Add, and you should not mention deleting or filtering at all. A
   quarter that already has rows takes the whole-instance Replace described in
   `powerschool-navigation.md` step 2, which needs one question answered first.
   Walk the person down one path. Do not lay out the branches and ask which they
   are in — they cannot see the table and you can.

7. **Verify the next day**, and tell the data team.

## Stop and escalate if

- Any of `csv-format.md`'s checks fail and you can't see why.
- A quarter you were asked to load has only an "under construction" draft tab.
  (A quarter you are _not_ loading being a draft is normal — report its deadline
  per step 5 and carry on.)
- An Academics row's dates overlap no PowerSchool week, and the row is not a
  break or revisions row carrying `---`. A row that overlaps two weeks is
  decidable — see `../references/week-matching.md` — and does not belong here.
- A week is far out of line with its neighbours in a way a typo does not
  explain. A **falling** count is check 5's job, and goes to the person, not the
  data team — they can fix their own sheet.
- A quarter has two blocks and **both** match the calendar, or **neither** does.
  One matching and one not is decidable without asking.

Escalating stops the file it affects, not the run. Hand over the regions that
passed and name the one you are holding back.
