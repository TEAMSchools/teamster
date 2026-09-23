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

- **All four quarters** (`rollover.md`) → skip to step 3. **Replace** mode does
  the delete and the load in one action, and deleting everything is what you
  want.
- **Some quarters** (`refresh.md`) → delete them by hand first, one quarter at a
  time:

  1. Set the **Quarter** filter to the quarter being replaced. Leave the
     **School Level** filter on All.
  2. Click the checkbox in the table header (select/deselect all visible). It
     checks only the rows the filter is currently showing.
  3. Read the **N rows selected** count beside **Delete Selected**. It must
     match the number of rows that quarter should have. If it does not, stop —
     there is something in that quarter you did not expect.
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
  - **No row may be flagged Duplicate**, assuming you did step 2. Add mode
    inserts a duplicate as a genuine second record; it does not overwrite. A
    duplicate flag here means the delete did not cover what you are loading.
- Choose the mode: **Add** after a manual per-quarter delete (`refresh.md`);
  **Replace** only when loading all four quarters (`rollover.md`). Replace's
  prompt counts every existing row on the instance, not just the ones in your
  file — read that number and make sure it is the whole table you meant to
  clear.
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

> **If you are reading this and the steps above are missing or still say
> PLACEHOLDER, stop.** Do not guess your way through a delete in PowerSchool.
> Contact the data team — this skill shipped incomplete.

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
3. **Delete four columns:** `academic_year`, `region`, `week_start_monday` and
   `week_end_friday` (columns F and G).
4. **Retype the header row** to exactly:
   ```
   School Level,Quarter,Week Number,W,H,F,S,Notes
   ```
   The tab's own headers are the database names. Left as they are, the file is
   rejected outright and nothing imports.
5. **Save as `.csv`**, then load it per the steps above.
