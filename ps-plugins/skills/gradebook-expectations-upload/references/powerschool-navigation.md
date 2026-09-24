# Uploading to PowerSchool

Do this **only after every check in `csv-format.md`'s "Check before anything is
uploaded" has passed.**

Work **one region at a time, start to finish.** A region's delete and load
happen in one sitting: in between, that region's dashboard has no expectations
for those weeks, for every school in the region.

## 1. Reach the page

Log in to that region's PowerSchool as an admin with the school selector set to
**District**. The **Gradebook Expectations** link is in the left navigation bar
under Applications. Newark, Camden and Paterson are separate instances with
separate logins:

| Region   | PowerSchool instance  |
| -------- | --------------------- |
| Newark   | `psteam.kippnj.org`   |
| Camden   | `camden.kippnj.org`   |
| Paterson | `ps.kipppaterson.org` |

If the link is missing, or the page bounces you back to the admin home, the
account is not in the `Gradebook Group` security group. Stop and ask the data
team. Do not work around it.

## 2. Decide the path before you describe it

**Work this out before you say a word to the person.** `Plugin Data Raw` shows
you what is live on this instance right now, per quarter and school level. Read
it first, then walk them down one path only. Never present the branches and ask
them which applies — they cannot see the table, and you can.

Filter `Plugin Data Raw` to this instance and the quarter you are loading:

- **No rows for that quarter** → nothing to delete. Go to step 3 and use
  **Add**. Do not mention deleting, and do not mention filters. This is the
  normal case for a quarter going in for the first time. Walking someone through
  deleting rows you already know are absent makes them read a count of 0 against
  an expected number, stop, and report a problem that does not exist.
- **Loading all four quarters** (`rollover.md`) → go to step 3 and use
  **Replace**. It clears the instance and loads in one action, and clearing
  everything is what you want.
- **The quarter already has rows** and you are not loading all four → see
  _Replacing one quarter that already has rows_ below.

### Replacing one quarter that already has rows

Do **not** do this by filtering the table and deleting the selection. Build a
file holding the whole instance and use **Replace**:

1. Take the new quarter's rows you just built.
2. Add every row `Plugin Data Raw` shows for the quarters you are **not**
   changing, copied across unchanged.
3. That combined file is the instance's intended contents, so **Replace** is
   correct and does the clearing for you.

This avoids the filter entirely, and the filter is where the sharp edge is:

> 🛑 **The Quarter filter scopes Delete Selected. It does nothing to Replace,
> and it silently stops applying after any delete or import.**
>
> The page loads every row on the instance when it opens, and Replace deletes
> that whole list — the filter only hides rows on screen. Worse, the table is
> re-rendered after every delete and every import **without** re-applying the
> filter, so every row becomes visible again while the dropdown still shows the
> quarter. Re-picking the quarter it already displays fires no change event, so
> the filter never re-applies, and the header checkbox then selects the entire
> instance.
>
> Nothing on screen warns about either. **Never describe filtering as a way to
> narrow what an upload touches**, and never build a bulk delete on it.

**One question you must ask before using Replace this way**, because only the
person can answer it:

> `Plugin Data Raw` refreshes overnight, so it shows the instance as of about 3
> AM today. Has anyone loaded or hand-edited expectations on this instance since
> then?

If yes, or they are unsure, stop. Replace would revert whatever they did, and
the mirror cannot show you what it was. Tell the data team instead.

## 3. Load the file

Click **Upload CSV**.

- If there is any doubt about the header, download the template from the modal
  and build from it. Each header cell is matched by name, case-insensitively and
  trimmed, in a fixed order — so the names must be right and so must the order.
  A mismatch is rejected outright — nothing imports.
- Download this region's CSV from the conversation, choose it here, then read
  the preview before going further:
  - **The valid row count must equal the number of rows in your file.** Invalid
    rows are skipped silently and the import still reports success.
  - **No row may be flagged Duplicate.** Add mode inserts a duplicate as a
    genuine second record; it does not overwrite. A duplicate flag means that
    quarter already had rows after all — either the step 2 delete missed some,
    or the quarter was not as empty as `Plugin Data Raw` suggested. Stop and go
    back to step 2 rather than importing on top.
- Choose the mode. The question is not how many quarters you are loading — it is
  **whether your file is the whole intended contents of this instance.**

  - **Replace** makes the file the entire table. Everything currently on the
    instance is deleted first, across every quarter and school level, and only
    what is in the file survives. Correct for a full-year rollover, and equally
    correct for a deliberate mass correction — if you have built a file holding
    every row you want the instance to end up with, Replace is the right tool
    and the cleanest one.
  - **Add** inserts the file's rows alongside what is already there. Correct for
    a per-quarter load, where the other quarters must survive untouched.

  The failure to avoid is **Replace with a partial file** — loading one quarter
  in Replace mode silently deletes the other three. That is not a reason to
  avoid Replace; it is a reason to check the file first. Replace's prompt counts
  every existing row on the instance, not just the ones in your file: read that
  number and confirm it is the whole table you meant to clear.

- Click **Import** and leave the window alone until it says Done. The modal
  locks itself during the upload on purpose.

## 4. Confirm what landed

The page has no total-row counter, so check each quarter you loaded: set the
**Quarter** filter to it, click the header select-all checkbox, and read the **N
rows selected** count. It must equal that quarter's row count in the file you
built. Click the header checkbox again to clear the selection, then **Clear
Filters**. Spot-check one week's W/H/F/S against the file.

Write down the row count per region and quarter — the next-day check below
reports it.

> The data team maintains an authoritative internal reference for these screens.
> If what you see on screen does not match what is written here, that reference
> wins — tell the data team the mismatch so they can fix whichever one has
> drifted.

## 5. Fixing one row

The list page also edits rows one at a time. For a single wrong week this is the
right tool, and after a failed bulk run it is the **only** safe one. This is
also the tool for `troubleshoot.md`'s fixes — a troubleshooting session should
essentially never end in a Replace.

**Use it when** one week's counts are wrong, a note has a typo, or a
delete-and-load died partway and left a quarter half-built.

**Do not use it** for a whole quarter or a new quarter. That is steps 2 and 3.

**This is the only place to use the Quarter filter.** Narrowing the table to
find one or two rows is what it is for. It is safe here because you are clicking
a specific row, not selecting in bulk — and because you do it on a freshly
loaded page, before any delete or import has re-rendered the table out from
under it.

- **Change a row** — click **Edit** on it, fix the counts, **Save Changes**.
  Nothing is deleted first, so that week is never briefly empty on the
  dashboard.

  > ⚠️ **Check every field shows its current value before you save.** The Edit
  > form fills the School Level, Quarter and Notes fields, but Week Number and
  > the four counts are written with an empty value and may come up blank. If
  > any of the five is empty, type it back in from the row you just clicked.
  > Saving with them blank writes the blanks.

- **Add a missing row** — **+ New Expectation** in the toolbar, fill it in,
  **Save New Expectation**. If School Level + Quarter + Week Number already
  exists it **refuses to save** and tells you. It also refuses on a blank School
  Level, Quarter or Week Number. So a duplicate cannot be created this way — but
  a refusal mid-repair looks like a broken form, so expect it.
- **Remove a row** — **Edit** it, then **Delete This Record** at the bottom. It
  asks for confirmation.

> 🛑 **If a delete or import died partway, rebuild the missing rows here. Do not
> re-run Replace.** Replace deletes every row on the instance — all quarters,
> both school levels — so using it to repair a half-finished Q2 destroys Q1, Q3
> and Q4 as well. A dozen rows by hand is tedious; Replace is a region-wide
> outage.

## Verify the next day, and tell the data team

**The upload is not finished on the day you do it.**

The template sheet refreshes nightly between 2 and 3 AM. **Come back the next
morning, after 3 AM**, open `Plugin Data Raw`, and check:

1. **Every week you loaded is there**, for every region you loaded, at the week
   numbers you assigned.
2. **No counts came through empty.**
3. **The counts match the file you uploaded.** Spot-check the first and last
   week of each quarter.
4. **`whocreated` and `whencreated` are yours, and from this upload.** If a row
   shows someone else, or an older timestamp, it was not replaced — the delete
   in step 2 missed it.

Then message the data team with which regions and quarters you loaded, when, and
what the next-day check showed. They run verification you cannot — that week
counts match the school calendar, and that the dashboard's category rows are
intact.

## If the skill cannot run — emergency fallback

Only when this skill is unavailable and the data team cannot help, and only to
**restore weeks that were already loaded**. It cannot produce a file for a
quarter that has not been loaded yet, because `Template QW-Date Crosswalk` stops
at the last completed week.

1. **Download** the `Template QW-Date Crosswalk` tab. Do the edits on the
   download, never in the sheet — the sheet is read-only and warehouse-fed.
2. **Split the rows by `region`** into one file per PowerSchool instance. Do
   this first, while you still have the column.
3. **Delete four columns**, picking them out **by the header you see on screen**
   — not by column letter, because the letters shift the moment you delete the
   first one. Delete `region`, `week_start_monday`, `week_end_friday` and
   `academic_year`.
4. **Move `notes` so it is the last column**, to the right of `S`. On the tab it
   sits to the left of `W`, and PowerSchool reads the columns by position, so it
   has to be moved. After steps 3 and 4 you should have eight columns, left to
   right, in exactly this order:

   ```text
   school_level  quarter  week_number_quarter  W  H  F  S  notes
   ```

5. **Retype the header row** to exactly:

   ```text
   School Level,Quarter,Week Number,W,H,F,S,Notes
   ```

   The tab's own headers are the database names. Left as they are, the file is
   rejected outright and nothing imports.

6. **Check the two end columns before you save.** Read the file left to right:
   the first column should hold `ES`, `MS` or `HS`, and the last column should
   hold your note text — not a number. The header is checked by name, but the
   **data rows are read purely by position**, so a header you retyped correctly
   over columns you left in the wrong order passes the header check and then
   fails every row. If `notes` is sitting where `W` belongs, you get "W must be
   a number" on **every row**.
7. **Save as `.csv`**, then load it per the steps above.
