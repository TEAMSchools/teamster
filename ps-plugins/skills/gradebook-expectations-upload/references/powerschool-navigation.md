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

## 2. Delete the rows being replaced

**There is no control that deletes "just Q2".** The upload modal's Replace mode
deletes _every_ row on the instance — all quarters, all school levels — not just
the ones in your file. So which path you take depends on what is being loaded:

> 🛑 **The Quarter filter scopes Delete Selected. It does nothing to Replace.**
>
> Filtering to a quarter and then choosing Replace does **not** replace that
> quarter. The page loads every row on the instance when it opens, and Replace
> deletes that whole list; the filter only hides rows on screen. Someone who
> filters to Q2, uploads a Q2 file and picks Replace loses Q1, Q3 and Q4.
>
> Nothing on screen warns them. The only tell is the confirmation dialog's count
> — "permanently delete ALL _n_ existing records" — where _n_ is the whole
> table, not the filtered view. **Never describe filtering as a way to narrow
> what an upload touches.** It narrows what Delete Selected touches, and that is
> all.

- **All four quarters** (`rollover.md`) → skip to step 3. **Replace** mode does
  the delete and the load in one action, and deleting everything is what you
  want.
- **A quarter that has no rows yet** → there is nothing to delete. Skip to step
  3 and use **Add**. This is the normal case for a quarter going in for the
  first time, and you already know which quarters those are: `Plugin Data Raw`
  showed you what is live when you ran the sanity-check. **Do not walk someone
  through deleting rows you have already established do not exist** — they will
  read a count of 0 against an expected count, follow the instruction to stop,
  and report a problem that is not there.

- **A quarter that already has rows** (`refresh.md`) → delete them by hand
  first, one quarter at a time:

  1. Set the **Quarter** filter to the quarter being replaced. Leave the
     **School Level** filter on All. This is the one place the filter does real
     work — it is what makes the next two steps act on that quarter alone.
  2. Click the checkbox in the table header (select/deselect all visible). It
     checks only the rows the filter is currently showing, and changing the
     filter unchecks anything it hides, so the selection cannot outlive the view
     that made it.
  3. Read the **N rows selected** count beside **Delete Selected**. It must
     match **what `Plugin Data Raw` showed for that quarter and instance** — the
     rows already in there, not the number of rows you are about to load. The
     two differ whenever a quarter's week count has changed, and quoting the
     file's row count sends people looking for a discrepancy that is just the
     old quarter being a different length. If the screen and `Plugin Data Raw`
     disagree, trust the screen — it is live — and say so before deleting
     anything.
  4. Click **Delete Selected**. The confirmation lists every row as School Level
     / Quarter / Week. Confirm only if every line is the intended quarter.
  5. Deletion runs at roughly one row per second and the page reloads when it
     finishes. Do not navigate away.
  6. Repeat for each quarter being replaced.

## 3. Load the file

Click **Upload CSV**.

- If there is any doubt about the header, download the template from the modal
  and build from it. The header is validated positionally, and a mismatch is
  rejected outright — nothing imports.
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

- **Change a row** — click **Edit** on it, fix the counts, **Save Changes**.
  Nothing is deleted first, so that week is never briefly empty on the
  dashboard.
- **Add a missing row** — **+ New Expectation** in the toolbar, fill it in,
  **Save New Expectation**. It warns if School Level + Quarter + Week Number
  already exists but **does not stop you**, so check the list first or you will
  create a duplicate.
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
   hold your note text — not a number. PowerSchool matches columns by position
   and never by name, so if `notes` is still sitting where `W` belongs, the
   header is accepted and then **every row** is rejected with "W must be a
   number".
7. **Save as `.csv`**, then load it per the steps above.
