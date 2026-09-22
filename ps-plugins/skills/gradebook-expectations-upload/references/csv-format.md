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

```
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

Quote any `Notes` value containing a comma.

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

## Show the tables

Show each file as a table in the conversation as well. The tables are how a
person catches a wrong repeated week before it reaches PowerSchool, so do not
skip them.

## Check before anything is uploaded

Report each check and its result. If any fails, stop and say what failed.

1. **No blank cells** in any count column, in any file. Every `---` and every
   empty cell should have become a number per `week-matching.md`'s value-filling
   rules.
2. **Every quarter you were told about is present**, and every week within it —
   no gaps in `Week Number`.
3. **Week numbers start at 1** in each quarter, and every week that has a row in
   `Template QW-Date Crosswalk` for that region got the number the template
   gives it.
4. **Row counts** — for each school level, the file has **one row per
   PowerSchool week in the quarter**, which is the tab's rows _plus any weeks
   the tab omits_. So Camden's file is twice its PowerSchool week count, MS +
   HS; Newark's is its MS week count plus its HS week count; Paterson's is its
   MS week count. Do not expect the file to match the tab's row count — Camden's
   Q1 tab has 10 rows and its file has 11 per level, because PowerSchool's week
   1 is not on the tab.
5. **Sanity-check against prod.** For any week that already has a row in
   `Plugin Data Raw` for this region and level, your computed `W/H/F/S` must
   match it **exactly**. This is a stronger check than 1–4: it catches a wrong
   transformation — a bad carry-forward, a week matched to the wrong date range
   — against real, already-correct production data, not just internal
   consistency of the new file. A mismatch here means something in the
   week-matching or value-filling logic is wrong, and the same bug is silently
   wrong for every later week too. Stop and find the cause before building the
   rest of the quarter.
