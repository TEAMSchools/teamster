# Playbook B — Mid-year refresh

**When this is the right playbook:** some quarters' counts are newly decided,
changed, or need reloading — but not a full first-time rollover. This is also
the playbook for an atypical start of year where only part of the calendar is
ready (this year's Q1-only situation is an example, not the norm — see
`rollover.md`).

## Steps

1. **Read `../references/sheets.md`** if you have not already.
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

   Take the date from the first row of that quarter in the Academics tab. If the
   tab has no rows for that quarter, or only an "under construction" draft, say
   the deadline cannot be determined and that T&L need to fill it in.

   **Why this matters more than it looks:** an unreplaced future quarter does
   not break anything visibly. It serves last year's counts, which look like
   real numbers, so the dashboard reports confidently wrong results for the
   whole quarter. Nobody gets an error. A blank dashboard gets reported the same
   day; a wrong expectation can run for months.

6. **Read `../references/powerschool-navigation.md`** and walk the person
   through it. Your file holds one quarter and the others must survive, so the
   mode is **Add**. Replace would make the file the entire table and delete the
   quarters you are not loading.

   Say that as the reason, not as a rule. Replace is the right tool when the
   file _is_ the whole intended contents of the instance — a rollover, or a
   deliberate mass correction built to cover every row that should remain. If
   the person asks for Replace, find out which they have before talking them out
   of it.

   **Whether a delete comes first depends on what is already there, and step 4
   told you.** A quarter with no rows in `Plugin Data Raw` goes straight to Add.
   Only a quarter that already has rows needs the hand-delete, and then the
   count to expect is the one `Plugin Data Raw` showed — not your file's row
   count. Walking someone through deleting rows you have already reported do not
   exist wastes their time and makes them stop on a false alarm.

7. **Verify the next day**, and tell the data team.

## Stop and escalate if

- Any of `csv-format.md`'s checks fail and you can't see why.
- A quarter's only tab is an "under construction" draft.
- An Academics row's dates match no PowerSchool week, or match more than one.
- The numbers look implausible — counts falling as the quarter progresses, or a
  week far out of line with its neighbours.
- A quarter has two blocks and **both** match the calendar, or **neither** does.
  One matching and one not is decidable without asking.
