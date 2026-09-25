# Building and checking the CSV

Shared by `rollover.md` and `refresh.md`. Read `sheets.md` and
`week-matching.md` first — this assumes every row already has a week number and
a value.

## One CSV per PowerSchool instance

`U_EXPECTATIONS` has no region column, which is the only reason the split
exists. Each region is a separate PowerSchool instance and takes its own file.

- **Camden** — MS and HS rows, both from the Camden tab
- **Newark** — MS and HS rows in the **same** file, from two different tabs
- **Paterson** — MS rows, from the Newark/Paterson MS tab

## The file must be a CSV

Not `.xlsx`, not a Google Sheet. The plugin parses CSV and nothing else, so a
spreadsheet file cannot be imported at all. Do not use a spreadsheet-building
tool for this — write a plain `.csv`.

## The header row must be exactly this

```text
School Level,Quarter,Week Number,W,H,F,S,Notes
```

> 🛑 **These are display names, not the database column names, and there is no
> `Academic Year` or `Region` column** — the plugin doesn't take either as
> input; see `sheets.md` for why. A file headed
> `school_level,quarter,week_number,cnt_w,cnt_h,cnt_f,cnt_s,notes` is **rejected
> outright** — "Header row does not match template" — and nothing imports. This
> is a mistake that has already been made once. Matching is case-insensitive and
> trims whitespace; the _order_ is what cannot vary.

| CSV column     | From                                             |
| -------------- | ------------------------------------------------ |
| `School Level` | `MS` or `HS`, from the tab                       |
| `Quarter`      | `Quarter` — "Quarter 1" → `Q1`                   |
| `Week Number`  | The week number worked out in `week-matching.md` |
| `W`            | `Work Habit`                                     |
| `H`            | `Homework`                                       |
| `F`            | `Formative Mastery`                              |
| `S`            | `Summative Mastery`                              |
| `Notes`        | `NOTE`                                           |

**Quote any `Notes` value containing a comma, a double quote or a line break,
and double any quote inside it** — `He said "go"` is written `"He said ""go"""`.
An unquoted comma shifts every later column on that row, and a raw line break
splits the row in two. Both then fail as invalid rows, which the import skips
while still reporting success, so the week simply never arrives.

Simpler still: strip line breaks out of a note rather than quoting them. A note
is one line of text.

Order the rows **all MS first, then all HS, each ascending by week number.**
PowerSchool does not care, but a person scanning the table in the conversation
does — that is how a wrong repeated week gets spotted.

## How to hand it over

Produce each region's CSV as a **downloadable file in the conversation.** Do not
save it to Google Drive — the person doing the upload needs a real `.csv` on
their own machine to pick in the PowerSchool file dialog, and a round trip
through Drive risks it being converted to a Google Sheet.

Name files so the region and period are obvious, e.g.
`gradebook_expectations_newark_SY2026-27_Q2.csv`.

### When the quarter already has rows, the file is the whole instance

A quarter with no rows live goes in with **Add**, and the per-quarter file above
is the file. A quarter that **already has rows** is replaced instead, and
Replace makes the file the entire table — so the file has to hold every row the
instance should end up with, not just the quarter you changed.

Build it as one file per instance:

1. The new quarter's rows, as built above.
2. Plus every row `Plugin Data Raw` shows for that instance in the quarters you
   are **not** changing, copied across unchanged — same school levels, same week
   numbers, same counts, same notes.

Name it for what it is, so nobody confuses it with the per-quarter file:
`gradebook_expectations_newark_SY2026-27_FULL.csv`.

**Two checks on this file specifically**, both before it is handed over:

- **Its row count equals the instance's current total, plus or minus the change
  in that one quarter's week count.** Get the current total from
  `Plugin Data Raw` for that instance and say both numbers out loud. A combined
  file that is merely the size of one quarter is the per-quarter file wearing
  the wrong name, and uploading it in Replace mode deletes the other quarters.
- **Every quarter that should survive is present**, with the week count it had.
  List the quarters and their row counts in the conversation.

Say which file is which when you hand them over, and say plainly that the
per-quarter file must never be uploaded in Replace mode.

## Show the tables

Show each file as a table in the conversation as well. The tables are how a
person catches a wrong repeated week before it reaches PowerSchool, so do not
skip them.

## Check before anything is uploaded

Run every check and report each result. **A failed check stops the file it
failed on, not the whole run** — if Camden fails and Newark and Paterson pass,
hand over Newark and Paterson and say which one is held back and why.

First, one check that is not about your file at all:

> 🛑 **`PS Full Calendar`'s `academic_year` must be the year you are loading.**
> Check this on every run, not just a rollover. The tab is filtered to whatever
> year the warehouse currently calls current, and mid-year is where a stale year
> is hardest to notice: the weeks look ordinary, the counts look ordinary, and
> every week number is shifted. If it shows the wrong year, stop and tell the
> data team — nothing below can catch this.

Then, on the file:

1. **No blank cells** in any count column, in any file. Every `---` and every
   empty cell should have become a number per `week-matching.md`'s value-filling
   rules.
2. **Every quarter you were told about is present**, and every week within it —
   no gaps in `Week Number`.
3. **Week numbers start at 1** in each quarter and run without gaps to that
   quarter's week count.

   Where `Template QW-Date Crosswalk` has a row for a week, its number must
   match yours. **Expect it to be empty for the weeks you are loading** — it
   only carries weeks that have already completed, so on a rollover it covers
   nothing in the file and on a mid-year load it covers only the past. That is
   normal and is not a failure. It confirms nothing about the weeks ahead, so do
   not report this check as evidence the new numbers are right;
   `PS Full Calendar` is what they were matched against.

4. **Row counts** — for each school level, the file has **one row per
   PowerSchool week in the quarter**, which is the tab's rows _plus any weeks
   the tab omits_. So Camden's file is twice its PowerSchool week count, MS +
   HS; Newark's is its MS week count plus its HS week count; Paterson's is its
   MS week count. Do not expect the file to match the tab's row count — Camden's
   Q1 tab has 10 rows and its file has 11 per level, because PowerSchool's week
   1 is not on the tab.
5. **No count falls** as a quarter progresses. Run this after value-filling, per
   category column, per school level, within each quarter. Counts are
   cumulative, so a column that goes 4, 5, 3, 6 is wrong — usually a typo in the
   planning sheet, occasionally a carry-forward that ran backwards.

   Say which quarter, week and column, and what the neighbours are. If it looks
   like a typo in Academics' own sheet, **tell the person** — they are Teaching
   & Learning and can fix it at source. Do not route it to the data team, who
   cannot know the intended number.

   **No count exceeds 20 either.** These are cumulative totals for a whole
   quarter, and 20 is above anything Teaching & Learning have set: the highest
   value live in `U_EXPECTATIONS` is 15 work habits, with homework and formative
   at 9 and summative at 2. A 50 where 5 was meant passes every other check here
   — it rises, it fills, the row count is right — and then reports every teacher
   in that region as far behind. Treat a value over 20 the same way as a falling
   count: name it and ask, rather than loading it.

   **If the person confirms the number is intended, load it.** The ceiling is a
   tripwire, not a rule about what Teaching & Learning may decide — say you are
   proceeding on their confirmation, and tell the data team afterwards so the
   ceiling in this file can move. Never hold a file back over a number its owner
   has just confirmed.

   The maxima above are what is live today, which is a single quarter's worth. A
   quarter with more weeks reaches higher totals honestly, so expect the
   headroom to shrink as the year fills in.

6. **Sanity-check against prod — only where the number should not have
   changed.** For a week that already has a row in `Plugin Data Raw` for this
   region and level **and that you are not deliberately changing**, your
   computed `W/H/F/S` must match it exactly. A mismatch there means a wrong
   transformation — a bad carry-forward, a week matched to the wrong dates — and
   the same bug is silently wrong for every later week.

   **Skip this check for any week whose number is meant to change, and skip it
   entirely on a rollover.** A refresh exists because T&L changed the counts, so
   a mismatch on a changed week is the point, not a defect. And `U_EXPECTATIONS`
   has no `academic_year` column, so last year's rows sit at the same school
   level, quarter and week as this year's — on a rollover every row would "fail"
   against numbers for a year you are replacing.

   Say which weeks you compared and which you skipped. A check reported as
   passing when it compared nothing is worse than one reported as skipped.
