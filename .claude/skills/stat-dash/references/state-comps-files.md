# State comps files: the yearly load

How the official State, City and Neighborhood Schools figures get from the state
websites into the comps sheet each year. For interim figures from a screenshot
or a press deck, and for the full-swap rules when a year is already in the
sheet, see [comps-sheet.md](comps-sheet.md).

The sheet: spreadsheet `1yS6xU7ygiOrrtc29pUc3jr590qk7ttag3RuzVHaPOv8`, tab
`State Assesssment Comps Demographics` (the typo is the real tab name).

## Where the files live

Google Drive, `Workspace/STAT Dashboard/Comps Processing/`:

| Folder                                                  | What goes in it                             | Who puts it there                           |
| ------------------------------------------------------- | ------------------------------------------- | ------------------------------------------- |
| `State Assessment Results from NJ Website/<YYYY-YYYY>/` | the NJDOE `.xlsx` files, as downloaded      | the NJ script downloads; Claude places them |
| `State Assessment Results from FL Website/<YYYY-YYYY>/` | the 18 FLDOE crosstabs                      | a person downloads; Claude renames          |
| `State Results from Other Sources/`                     | screenshots for interim or unofficial comps | a person; Claude reads it (see below)       |

- Screenshots are processed per [comps-sheet.md](comps-sheet.md).
- Only official source files go in Drive. Never write script output there.
- The Codespace's ADC can read these folders but its token is read-only. Renames
  and uploads go through the Google Drive MCP, which runs as the user.
- Paste-ready output goes to the gitignored `.claude/scratch/`. Delete it once
  the paste is verified.

## Florida (Miami)

### Download: 18 crosstabs in 3 batches

1. edudata.fldoe.org, Advanced Reports, PK-12 Assessments, acknowledge the
   notice, then the Build A Table tab.
2. Set Year, and Assessment = Individual Assessments.
3. Download 6 files per level, one per Indicator 1: (None), Race, Economic
   Status, Sex, Current ELL Status, Disability Status. Use Current ELL Status,
   not English Language Learner Code.

   | Batch   | District       | School | Drilldown                                     |
   | ------- | -------------- | ------ | --------------------------------------------- |
   | Schools | 13-Miami-Dade  | All    | expanded, so District and School columns show |
   | City    | 13-Miami-Dade  |        | collapsed                                     |
   | State   | District (All) |        | collapsed                                     |

4. After changing level, check that the filter summary above the table names the
   right District.
5. Download, then Crosstab. CSV is fine. Suppressed cells export as `*`.
6. The person drops each batch in the year folder. Claude checks it and renames
   it `<YYYY-MM-DD> <state|city|schools> <all|race|ecodis|sex|ml|swd>.csv`
   before the next batch. A crosstab does not record its filters: the file name
   is the only record of what it is.

### Build

```bash
uv run python .claude/skills/stat-dash/scripts/build_fl_comps.py \
  <folder with the 18 files> --academic-year 2025 --school-year 2025-26 \
  --output .claude/scratch/fl_comps_2025.tsv
```

`--academic-year` is the starting year; `--school-year` is FLDOE's label. The
summary prints row counts by entity, neighborhood schools with no rows, files
ignored for their name, and any `PROBLEM` line. The script exits non-zero on a
problem. A `level check failed` line means a state file is really Miami-Dade or
a city file is really statewide: re-download that pair.

### Neighborhood schools

Miami-Dade school numbers, kept as a constant in the script:

| Number | School                       |
| ------ | ---------------------------- |
| 0101   | Arcola Lake Elementary       |
| 0521   | Broadmoor Elementary         |
| 6031   | Brownsville Middle           |
| 4491   | Henry E.S. Reeves K-8 Center |
| 2981   | Liberty City Elementary      |
| 6391   | Madison Middle               |
| 4501   | Poinciana Park Elementary    |

4501 has no 2025-26 data, so 2025-26 used the other six. Ask Walters whether
that list still stands. A new KTAF Florida school outside Miami needs its own
neighborhood schools and its own City (county): ask Walters before the next run.

### Method notes

- 2025-26 is the first year State and City use FLDOE's official totals. Earlier
  years summed school rows, which drops every suppressed cell, so subgroups were
  undercounted. Neighborhood Schools still sums school rows, the only option.
- Mapping: Black is `African American`; Two or More Races is `Other`; Pacific
  Islander and Not Reported are dropped; Current ELL is `ML`; SWD is
  `Students With Disabilities`; Eco. / Non-Eco. Disadvantaged map to the two
  `Economically Disadvantaged` subgroups; Civics is `SOC08`.
- Grade 9+ and the high school EOCs are left out. They start with 2026-27
  results, pulled with FLDOE's Grade Enrolled filter so middle schoolers compare
  to middle schoolers and high schoolers to high schoolers (#5636).
- Known suspicious 2024-25 rows, left for Walters: Miami City SOC08 All Students
  (302 students), Miami State SOC08 (42,703), Neighborhood Schools race rows
  that add up to more than the Neighborhood Schools total, and Miami State MAT08
  (272,013).

## New Jersey (Newark, Camden, Paterson)

Run the script once NJDOE posts the year (roughly November; before that the URLs
return 404 and the script says so).

```bash
uv run python .claude/skills/stat-dash/scripts/build_nj_comps.py \
  --academic-year 2024 --download-dir .claude/scratch/nj_2425 \
  --output .claude/scratch/nj_comps_2024.tsv
```

Then place the downloaded files in the NJ Drive folder for that year.

What the script does:

- City is the host district's `District Total` row: Newark Public School
  District `3570`, Camden City School District `0680`, Paterson Public School
  District `4010`. State rows repeat once per region.
- Percent proficient is Level 4 + Level 5 for ELA and Math, Level 3 + Level 4
  for Science, and Level 2 for NJGPA.
- A cell NJDOE suppresses (`*`) is skipped. When only the count is suppressed
  (State Female, to protect a small Non-Binary cell), the percentage goes in
  with `total_students` blank.
- ALG01 follows the sheet's existing layout. Grade - 08 is the middle school row
  (`MS`, `3-8`, group `Grade`), which staging relabels `Total` / `All Students`.
  Grade - 09 and - 10 go in as `HS_09` / `HS_10` with `remove_row = TRUE`, which
  staging rolls up into one weighted HS row. The all-grades rows go in as
  `MS_HS` with `remove_row = TRUE`. Grades 06 and 07 are left out, as the sheet
  always has.

Checked against the sheet's 2024 NJ rows using the 2024-25 files: all 1,375 rows
reproduced; 1,369 identical in every column. The 6 that differ are Paterson
State Female rows the sheet left blank. The script also writes 279 rows the old
manual load skipped: ALG02, American Indian and Native Hawaiian, State subgroups
whose City cell is suppressed, and rows with a suppressed count. Keep them: a
comp KTAF has no students for shows as an empty cell, not a wrong number.

## Loading into the sheet

1. Check whether the year is already in the sheet (the query in
   [comps-sheet.md](comps-sheet.md), _Replace interim comps_). Empty means
   append; otherwise do the full swap described there.
2. For an append, paste the TSV at the first empty row of the tab.
3. Verify by reading the tab back through ADC. The row count for the year and
   region must equal the TSV's line count:

   ```python
   # uv run --with google-api-python-client python <script.py>
   import google.auth
   from googleapiclient.discovery import build

   creds, _ = google.auth.default(
       scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
   )
   values = (
       build("sheets", "v4", credentials=creds)
       .spreadsheets()
       .values()
       .get(
           spreadsheetId="1yS6xU7ygiOrrtc29pUc3jr590qk7ttag3RuzVHaPOv8",
           range="'State Assesssment Comps Demographics'!A:N",
       )
       .execute()["values"]
   )
   header, rows = values[0], values[1:]
   pasted = [r for r in rows if r[0] == "2025" and r[7] == "Miami"]
   print(len(pasted))
   ```

   Then run the Step 6 audit in [comps-sheet.md](comps-sheet.md).

4. dbt picks up the sheet on its own. The STAT dashboard does not: it is a
   manual Tableau refresh, and its owner (Walters) has to run it.
