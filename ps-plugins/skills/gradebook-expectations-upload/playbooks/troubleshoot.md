# Playbook C — Troubleshooting

**When this is the right playbook:** the person is asking "why does this look
wrong" — the gradebook audit dashboard is showing an unexpected number, a
missing week, or counts that don't match what Academics decided. This is a
**diagnostic** flow. It does not build or upload a file by default; most of the
time the right ending is a single-row fix (`powerschool-navigation.md`, step 5)
or an explanation that nothing is actually wrong.

## 1. Find out what's being reported

Ask which region, quarter, and (if known) week looks wrong, and what the person
expected instead. If they don't know — "the numbers just look off" — start
broad: pull `Plugin Data Raw` for every region and eyeball it for the patterns
below before narrowing in.

## 2. Rule out the two most common non-bugs

**a. It's reading the wrong week.** Read `../references/week-matching.md`'s "How
the audit reads this" first. The dashboard shows exactly one row per quarter — a
closed quarter frozen at its last week, the running quarter sitting on the
_previous_ completed week, never the current in-progress one. A huge share of
"this looks wrong" reports are actually this: someone looking at Q1's frozen
final-week number in November and expecting it to have moved, or expecting this
week's count to already be reflected today. If that's what's happening, there is
nothing to fix — explain what they're looking at instead.

**b. The quarter being asked about isn't decided yet.** Before treating a
missing or stale quarter as a bug, check the Academics tab for it
(`../references/sheets.md`). If the only tab for that quarter is still "under
construction," this isn't a mystery to solve — it's the exact situation
`refresh.md` already describes: the quarter serves last year's counts until
someone loads it, and that's expected right up until it opens. Give the same
"Q_n_ opens Monday _date_" framing `refresh.md` uses, and stop there — this
isn't a diagnostic case, it's a not-ready-yet case.

Take that date from `PS Full Calendar` — the `week_start_monday` of that
quarter's week 1 for the region and school level. It holds the whole year, so
the date is there even when the Academics tab for that quarter is an empty
draft. Never tell the person the date can't be worked out; it always can.

## 3. Re-derive what _should_ be there, and diff it against prod

1. Read `../references/sheets.md` and open the Academics tab(s) for the affected
   region/quarter.
2. Run the same translation `week-matching.md` describes — date to PowerSchool
   week number, value-filling rules — to work out what each week's `W/H/F/S`
   _should_ be. This is the same computation `csv-format.md` does when building
   a file; here you're using it to check, not to build.
3. Pull `Plugin Data Raw` for that region and level and compare, week by week.

## 4. Common causes, in rough likelihood order

- **A decided quarter was never loaded, or only partly loaded** (this is
  different from 2b's not-yet-decided case — this is a quarter Academics _has_
  finalized that never made it into PowerSchool). It's silently serving last
  year's (or no) counts — see `week-matching.md`'s "gaps are filled, not
  flagged." This looks like real data, not an error. If this is the cause, route
  to `refresh.md` to actually load it — troubleshooting ends here, it doesn't
  fix it itself.
- **A delete didn't fully cover what was replaced**, leaving a duplicate or a
  stale row behind. Check `whocreated`/`whencreated` in `Plugin Data Raw` — a
  row from someone else, or an older timestamp than the rest of that quarter's
  rows, means an earlier delete missed it.
- **A row's date matched the wrong PowerSchool week**, or matched none.
  Recompute per `week-matching.md`'s date-matching rules, and check for the
  Camden-style "PowerSchool has a week the Academics tab doesn't list" case.
- **The two-note-column trap** (`sheets.md`) — a value got misread from the
  wrong column when a row was originally built.
- **A typo'd count** — one week far out of line with its neighbours, or counts
  falling instead of holding/rising within a quarter (they're cumulative; see
  `week-matching.md`).

## 5. Fix it

- **One wrong week, in an otherwise-correct quarter** →
  `powerschool-navigation.md` step 5, edit that single row. Do not
  delete-and-reload the whole quarter for one bad row.
- **A quarter that was never loaded, or needs a real reload** → hand off to
  `refresh.md`, don't build the fix inside this playbook.
- **Nothing is actually wrong** (step 2's cases — wrong week, or not decided
  yet) → explain what the dashboard is showing and why, and stop there.

## Stop and escalate if

- The mismatch doesn't fit any of the causes above.
- Multiple regions or quarters show the same kind of mismatch — that suggests
  something systemic (a template sheet issue, a warehouse model change), not a
  one-off data entry error, and is a data-team problem, not a single-row fix.
- You're not confident the fix is a single row — see
  `powerschool-navigation.md`'s warning against using Replace to patch anything
  less than a genuine full reload.
