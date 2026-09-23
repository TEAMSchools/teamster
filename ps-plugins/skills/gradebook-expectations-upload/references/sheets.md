# The two sheets

Shared by every playbook. You need the **Google Drive connector** enabled —
everything here reads two spreadsheets; nothing touches a database directly.

## The source — Academics' planning sheet

**`Gradebook Expectations | SY__`**, maintained by Teaching & Learning:
<https://docs.google.com/spreadsheets/d/1yfGE6P831la2Hz0cN9echGBG2oTAgX9xzMuoR-H8Jcs/edit>

This is where the counts come from. One tab per region and school level, with
these columns:

| Column              | Use                                          |
| ------------------- | -------------------------------------------- |
| `Quarter`           | "Quarter 1" → `Q1`                           |
| `Assigned Week #`   | **Ignore it.** See the warning below.        |
| `Dates`             | How the row is matched to a PowerSchool week |
| `Grades Due on`     | Not used                                     |
| `NOTE`              | → `Notes`                                    |
| `Work Habit`        | → `W`                                        |
| `Homework`          | → `H`                                        |
| `Formative Mastery` | → `F`                                        |
| `Summative Mastery` | → `S`                                        |

A trailing `Note` column appears on some tabs. It carries reminders for humans
("First Progress Report Distributed"), not expectations — leave it out.

> ⚠️ **Two note columns, and `NOTE` is empty on most rows.** Identify every
> column by its **header**, never by counting fields across a row. `NOTE` sits
> between `Grades Due on` and `Work Habit`; the human `Note`, where it exists,
> is last. W/H/F/S are always the columns headed `Work Habit`, `Homework`,
> `Formative Mastery` and `Summative Mastery`.
>
> This matters because an empty `NOTE` can collapse when the sheet is rendered
> as text, leaving a row that looks like it has four leading fields instead of
> five. Guessing which value is which from position will silently misread a row
> where someone typed something number-like into `NOTE`. If a row's columns
> cannot be resolved against the header with confidence, **stop and say which
> row** rather than guessing.

## The reference — the data team's template sheet

**Gradebook Audit Template**:
<https://docs.google.com/spreadsheets/d/1Fx_tc1Bja2IWrIHyidTJrI4a0ZNcds07V29kjtkh3Go/edit>

**Read-only, and fed from the data warehouse.** Nobody edits it by hand and
nothing you do should try. Four tabs:

**`PS Full Calendar`** — the whole school year's week grid, not just the weeks
already loaded into `U_EXPECTATIONS`. Use it to tell a week that has no
expectations apart from a week that does not exist; the other tabs cannot
distinguish those, because they only show rows PowerSchool already has. Columns
are `academic_year`, `region`, `school_level`, `quarter`, `week_number_quarter`,
`week_start_monday`, `week_end_friday`.

> 🛑 **Before trusting this tab for a rollover, confirm the `academic_year`
> column shows the year you are loading.** This tab is filtered to whatever
> academic year the data warehouse currently considers "current" — and a
> PowerSchool instance can sit in the next school year all summer while that
> setting still points at the old one. When that happens, `PS Full Calendar`
> shows **last year's** weeks: same columns, same shape, same quarter names,
> nothing on screen saying so. A rollover run against it in that window produces
> a confident, wrong upload with no error anywhere. One glance at the
> `academic_year` column answers it — if it isn't the year you're loading, stop
> and tell the data team the year needs rolling over first.

**`Plugin Data Raw`** — what actually landed in PowerSchool's `U_EXPECTATIONS`
table, for people who cannot query the database. It shows each row, **who**
created or last changed it, and **when**. This is the pre-upload sanity check
(`csv-format.md`) and the next-day self-check (`powerschool-navigation.md`):
does my math match what's already live, and did my rows land.

Its `_dbt_source_project` column — `kippcamden`, `kippnewark`, `kipppaterson` —
is the region. **`U_EXPECTATIONS` has no `academic_year` or `region` column, on
purpose.** Academic year is controlled by backend code, not user input; region
isn't stored in the table at all — it's known only from which PowerSchool
instance the row came from. That is the same reason the upload is one file per
instance, and why a CSV header must never try to add either field back in.

**`Template QW-Date Crosswalk`** — close to the shape PowerSchool needs, but its
real job is to show **how a week number gets tagged to the week it belongs to**:
the translation between how Academics count weeks on their own sheet and how the
weeks are counted off the PowerSchool calendar. Details in `week-matching.md`.

**`PS Plugin CSV Template`** — the literal CSV header row, to copy rather than
retype:

```text
School Level,Quarter,Week Number,W,H,F,S,Notes
```

Unlike the other tabs, nothing feeds this one automatically and it has no
counterpart on the other sheet — it exists only so nobody types the header by
hand. A retyped header that doesn't match this exactly is rejected outright by
the PowerSchool import page.

> **Everything comes from the PowerSchool calendar.** Academics' own week
> numbering is theirs; PowerSchool's is the one that decides where a row goes.

**The three warehouse-fed tabs are as of the previous week, and refresh nightly
between 2 and 3 AM.** Nothing you upload today appears here until 3 AM tomorrow
at the earliest, and none of them ever show the week currently in progress. That
is by design, not a fault — see `week-matching.md`, _How the audit reads this_.

## How to read these sheets

Both sheets are multi-tab Google Sheets. Neither Drive operation gives you
everything, so use both, for different things:

| Call                                                                                          | Use it for                                                                           | Do **not** use it for                                             |
| --------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ | ----------------------------------------------------------------- |
| **Content read** (`read_file_content`)                                                        | **All values.** Returns every tab's rows in order.                                   | Tab names — it returns unlabelled tables with no headings at all. |
| **Metadata read** at maximum verbosity (`get_file_metadata`, `snippetVerbosity: MAX_ALLOWED`) | **Tab names only.** Returns each tab as a `# <tab name>` heading, in the same order. | Values — see below.                                               |

**Why the split, and why you cannot skip either half:**

- The content read has **no tab names**, and every tab-selection rule in this
  skill is name-based. Without names you cannot tell the three Camden/Newark-HS
  variants apart.
- The metadata read renders rows as CSV and **silently drops an empty `NOTE`
  column**, so `Quarter 1,1,8/24-8/28,8/31,1,1,1,0` has four leading fields
  where the real row has five. Take counts from it and `Work Habit` gets read
  out of the `NOTE` slot on every row with an empty note. The content read keeps
  the column aligned.

Match names to tables by order — both calls return the tabs in the same
sequence.

> 🛑 **Never identify a tab by its values.** Several tabs open with identical or
> near-identical counts — the drafts especially — so a tab that "looks like
> Camden" may be a Newark HS draft. Guessing wrong puts one region's rows into
> another region's file, silently. Names, always.

**The first tab is a hidden `(Q2-4 under construction)` draft.** That is normal
and does not mean the read failed. There are **ten tabs**: three usable, three
drafts, three Miami, and a dates reference.

> 🛑 **Stop and say so if you cannot see every tab's rows _and_ every tab's
> name.** A truncated content read, or names you could not retrieve, both mean
> stop. Do not proceed on a partial read, do not guess a tab's identity, and
> never fall back to answering from what you already know. A half-read sheet
> produces a wrong upload exactly as silently as a stale one — that is the
> failure this whole skill exists to prevent.

## Rules for both sheets

1. **Read them live through the Drive connector, every run.** Say which files
   you opened and check `academic_year` matches the year being loaded. A sheet
   from last year looks completely normal and produces a completely wrong
   upload.
2. 🛑 **Never read a local or attached copy.** Not an `.xlsx` sitting in the
   project, not a file pasted into the chat, not a download from an earlier run.
   A copy goes stale the moment T&L edits the sheet and nothing on screen tells
   you it has. If you find such a file, say so and use the Drive link instead.
3. 🛑 **Never save either sheet anywhere.** Do not download them, do not add
   them to a project, and never commit them to a repository.

## Which tabs feed which instance

One tab can feed two instances, and two tabs are not for PowerSchool at all.

| Academics tab          | Produces                          |
| ---------------------- | --------------------------------- |
| `Newark/Paterson - MS` | Newark **MS** and Paterson **MS** |
| `NJ - Newark HS`       | Newark **HS**                     |
| `NJ - Camden MS/HS`    | Camden **MS** and Camden **HS**   |
| Any **Miami** tab      | **Nothing.** Skip them.           |

- **Newark and Paterson MS share a tab** and get identical counts, but land in
  two different PowerSchool instances, so they go in two different files.
- **Camden's single tab produces both MS and HS rows**, identical to each other.
- **Miami is on Focus, not PowerSchool.** It has no PS instance and no
  `U_EXPECTATIONS` table. Never build a Miami file.

> 🛑 **Use the visible per-quarter tabs, not the hidden "(Q2-4 under
> construction)" ones.** The hidden tabs disagree with the visible ones on dates
> — one gives Q1 week 2 as 9/2–9/5 where the visible tab says 8/31–9/4, and the
> visible tab is the one matching PowerSchool. They are drafts. If the only tab
> for a quarter is an "under construction" one, that quarter is not ready to
> load; say so rather than using it.
