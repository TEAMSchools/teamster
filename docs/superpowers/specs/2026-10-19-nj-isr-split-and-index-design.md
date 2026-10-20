# NJ ISR split and regional index — design

Issue: #6026

## Why

Each fall the state releases New Jersey Individual Student Reports (ISRs) as a
few large PDFs per region. Schools need each student's report to send home and
to hand to a new school when a family transfers out.

Two kinds of ticket come in every year, and both are urgent and avoidable:

- A school says an ISR is missing from its file when the ISR is there.
- A school cannot find the ISR for a student who left, because it does not know
  the region's transfer-out folder exists, even though we announce it every
  year.

The old split also made files that are hard to use. Last year's KIPP TEAM
Academy file was 474 MB, too large for Drive to preview, so staff had to
download it to find one student. The same school, cut straight from this year's
state file, is 8.6 MB.

This project makes the split a repeatable yearly command and gives schools a
lookup they can use without filing a ticket.

## Goals

1. Split each region's ISR PDFs into one PDF per school per report type. A
   student's report goes to their current school for the new school year, in
   alphabetical order by last name.
2. Put every report for a student who left KTAF, or who matches no student, in
   one `Transfer Out & Unmatched` folder per region.
3. Build one index Google Sheet per region per administration. Each row names a
   student, a subject, the file that holds the report, a link to that file, and
   the page where the report starts.
4. Make the index easy enough that a school operations person finds any report
   on the first try with no training. "A small child could figure it out" is the
   bar the user set.
5. Run once a year by the data team, with no engineer involvement after the
   first code review and the one-time sign-in setup.

## Non-goals

- Homeroom packets, chase sheets, distribution tracking, and reconciliation
  dashboards. An earlier exploration on branch
  `anthonygwalters/feat/claude-nj-isr-distribution` designed those. This design
  supersedes it and reuses only its format findings.
- dbt models, a Dagster asset, or any warehouse table for the ISR pages. The
  index Sheet is written directly.
- The Labels PDF. It holds Science score stickers only, several per page, so it
  cannot be split by student without redrawing it.
- Rows for enrolled students who have no report. A possible follow-up; see
  _Later_.
- A typed search box in the Sheet. Staff have view-only access, and a viewer
  cannot type in a cell.
- Changing anyone's Drive sharing. The command never adds or removes access.
- Moving the Drive folders to a shared drive. That is #6027.

## Anti-goals

These would make the project a failure even if the command runs:

- A student's report lands in a school folder that is not the student's current
  school. A wrong-school file shows another family's scores and portal access
  code to the wrong staff. Uncertain matches go to `Transfer Out & Unmatched`,
  never to a guessed school.
- The index shows a portal access code, date of birth, state ID, or score.
- The command guesses at a record boundary and continues. It stops with a clear
  message instead.
- A rerun breaks links that schools already saved or bookmarked.
- Staff need instructions longer than the 3 steps on the Sheet to use it.
- A Drive folder ID or link key lands in this public repo.

## What the Spring 2026 files look like

Verified on the real files on 2026-10-19 (Newark `7325`, Camden `1799`, Paterson
`7899`):

| File kind                         | Pages per student | Grades          | Records |
| --------------------------------- | ----------------- | --------------- | ------- |
| `..._ISR_SLA_Combined.pdf`        | 4                 | 3 to 9          | 5,357   |
| `..._ISR_SLA_Single.pdf`          | 2                 | mostly 11 (Sci) | 424     |
| `..._ISR_SLA_Combined_100226.pdf` | 4                 | 1 student each  | 2       |
| `..._Labels_SLA.pdf` (skipped)    | several per page  | Science only    | n/a     |

- The input holds 5,783 records. The 2 corrected records replace 2 originals, so
  the output holds 5,781 records.
- Filenames follow
  `{year}_{season}_{district}-{school}_{ISR|Labels}_{SLA|GPA}[_{Combined|Single}][_{MMDDYY}].pdf`.
  Paterson has no `Single` file this year.
- The state uses 1 school code per district (`7325_965`, `1799_111`,
  `7899_925`). The PDFs carry no campus, so campus assignment comes entirely
  from PowerSchool.
- Record boundary: the footer token `{district}.{district}_{school}.{seq}`
  prints on the first and last page of each record. On page 1 it is glued to the
  end of the 6-character Family Portal access code, so the pattern must not
  start with a word boundary: `(\d{4})\.(\1_\d{3})\.(\d+)`. Pages between 2
  tokens with the same `seq` belong to that record. In every file, `seq` runs
  from 1 with no gaps and every page lands in exactly 1 record.
- Each record carries exactly 1 state ID (`Student ID:` then 10 digits), a date
  of birth (`Date of Birth:` then `MM/DD/YY`), and `ENROLLED GRADE:` on its
  inner pages.
- The cover page lists the subjects the report covers: English Language Arts,
  Mathematics, and Science where tested.
- A file with a date suffix (`_100226`) is a corrected report from the state.
  Each corrected student also appears in the original file. The corrected pages
  replace the original pages.
- A repeated state ID can appear within a file. Both records stay; the run
  summary names the duplicate.
- The NJGPA files from the earlier exploration use the same footer token on
  every page, 2 pages per student. The same segmentation rule covers them, so
  `_GPA` files work when they are in the input folder.

## How a report reaches a school

### Match

Find a candidate PowerSchool `student_number` for each record in this order:

1. The state's own crosswalk: `kipptaf_cambium.int_cambium__all_assessments`,
   `state_student_id` to `student_number`, for the Spring administration
   (`academic_year` = administration year - 1, `period = 'Spring'`).
2. `kipptaf_powerschool.base_powerschool__student_enrollments.state_studentnumber`,
   any year.

Then confirm the candidate: the last name and date of birth printed on the
report must match PowerSchool. Compare last names after removing case, accents,
spaces, hyphens, and apostrophes, and accept a match on any one part of a
multi-part last name. Never compare first names, because nicknames differ. A
record that fails confirmation, or has no candidate, is unmatched. An unmatched
record goes to `Transfer Out & Unmatched` and never stops the run.

When steps 1 and 2 point to different students (4 records in 2026), confirm each
candidate. The one that passes wins. If neither passes, or both do, the record
is unmatched.

### Route

- Current school: the student's row in `base_powerschool__student_enrollments`
  with `academic_year` = the new school year, `rn_year = 1`, and
  `enroll_status = 0`. The report goes to that school's folder, in whatever
  region the school is in. A few students moved between regions this year; their
  reports follow them.
- Everything else goes to the testing region's `Transfer Out & Unmatched`
  folder: students not enrolled in the new year, students who left during it,
  and unmatched records.

On 2026-10-19, before the name and birth date check, routing gave 4,753 records
to 19 schools, 1,025 to transfer-out folders, and 3 unmatched. These counts move
as enrollment changes, so they are a guide, not a test.

### Write the PDFs

- One PDF per destination folder per report type. A high school gets 2 files
  (grade 9 ELA and grade 11 Science). An elementary or middle school gets 1.
- Inside each file, students sort by PowerSchool `last_name`, then `first_name`,
  then `student_number`. Unmatched records use the name printed on the report
  and sort after matched ones.
- Each student's pages stay together and in their original order.
- Cut pages straight from the state's file into each output, and let the writer
  share fonts and images across pages. Do not build one PDF per student and
  merge them; that copies every font and image once per student. The largest
  2026 school file is 1,808 pages, about 9 MB.
- File names use plain words a school leader understands, with no vendor terms
  like "Combined" or "Single". For example,
  `KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf` and
  `KIPP Newark Collegiate Academy - NJSLA Science Reports (Grade 11) - Spring 2026.pdf`.

### Drive layout

The command follows the layout schools already use:

```text
Report Cards and Transcripts/
  Newark Report Cards and Transcripts/              (1 per region)
    Spring 2026 NJSLA ISRs/                         (new each year)
      Newark NJSLA Reports Index - Spring 2026      (the index Sheet)
      Transfer Out & Unmatched/
    TEAM Report Cards/                              (1 per school, exists)
      Spring 2026 NJSLA ISRs/                       (new each year)
        KIPP TEAM Academy - NJSLA Reports - Spring 2026.pdf
        00 - Find a state test report - Spring 2026 (shortcut to the index)
```

- The user passes the link to `Report Cards and Transcripts` when running the
  command. The repo never stores a folder ID or link key, because the repo is
  public.
- A committed config maps each region to its region folder name, and each
  PowerSchool `schoolid` to its school folder name, for example
  `TEAM Report Cards`. The command finds folders by name and stops if a name
  matches 0 folders or more than 1.
- The command creates the yearly folders, `Transfer Out & Unmatched`, the index
  Sheet, and the shortcuts when they do not exist.

### Reruns

A rerun happens when the state sends corrections or when enrollment changes.

- Every run routes from current enrollment, so a student who changed schools
  moves to the new school's file.
- The command tags every file it creates with the administration in Drive's file
  properties (`appProperties`).
- If a file with the same tag and name exists, the command replaces its content
  and keeps its file ID. Saved links and bookmarks keep working.
- A tagged file that the new run no longer produces (a school with 0 reports of
  that type) goes to the Drive trash. The index is rewritten in the same run, so
  no index row points at it.
- Page numbers can shift on a rerun. The index always matches the files because
  the same run writes both.

### Index Sheet

1 Sheet per region per administration, in that region's yearly folder. The
Spring 2027 run makes a new Sheet, so the 2026 rows stay for transfer requests.
A rerun rewrites the Sheet's values and keeps its ID.

Staff open the Sheet as viewers. The first tab, `All reports`, opens with a
frozen banner of 3 steps in large text:

1. Press Ctrl+F (Cmd+F on a Mac) and type the student's last name.
2. Click the blue link in that student's row.
3. Go to the page number in the `Page` column.

Below the banner sits the full list, sorted by student name. A second tab,
`About`, says what the Sheet is, when the command last ran, and where to send a
question (the Data ticket queue, never a person's contact details).

Columns, in plain words:

| Column             | Example                                      |
| ------------------ | -------------------------------------------- |
| Student            | `Last, First`                                |
| Student number     | PowerSchool `student_number`                 |
| Grade when tested  | `5`                                          |
| Subject            | `Math`                                       |
| Where to find it   | school name, or `Transfer Out & Unmatched`   |
| School last spring | the 2025-26 school, to help the old school   |
| Open the report    | link to the PDF                              |
| Page               | the page where this student's report starts  |
| Note               | for example `Corrected by the state on 10/2` |

- 1 row per student per subject listed on the report's cover.
- A student who moved between regions appears in the index for the region that
  holds the file.
- The index never shows an access code, date of birth, state ID, or score.

### Access

A shortcut does not grant access. School staff can open a file only if the file
or its folder is shared with them. The user sets sharing once per region, by
hand:

- Every school's staff in a region can view that region's yearly folder, which
  holds the index Sheet and `Transfer Out & Unmatched`.
- School folders keep the school-level sharing they already have.

The run summary prints who can currently open each region's Sheet, so the user
can confirm the sharing after the first run.

## How it runs

- A command in the teamster repo, run from a Codespace with `uv run`, about once
  a year after the state releases ISRs. It takes the folder of ISR PDFs, the new
  school year, and the link to `Report Cards and Transcripts`.
- The folders live in My Drive space, where a service account cannot create
  files. So Drive and Sheets calls run as the person who runs the command,
  through their own Google sign-in. BigQuery reads keep using the Codespace's
  default credentials.
- The sign-in token stays outside the repo and never prints.
- `--dry-run` scans, matches, and prints the summary with no Drive writes.
  `--local-out {dir}` also writes the PDFs to a local folder for inspection.
- The run summary prints counts by region and destination, the unmatched
  records, the source disagreements, the failed confirmations, and the
  corrections applied. Names stay in the terminal and local scratch, never in
  git or GitHub.
- After #6027 moves the folders to the Data Team shared drive, the command can
  switch to the service account and drop the personal sign-in.

## Checks the command enforces

The command stops with a message, and writes nothing, when any of these fail:

- A file's footer district does not match its filename district.
- A file's `seq` values do not run from 1 with no gaps.
- A page belongs to no record, or a record's pages are not contiguous.
- A record has 0 or more than 1 state ID.
- A current school has reports but no folder name in the config, or its folder
  name matches 0 or more than 1 folder.
- Record conservation: every output record appears in exactly 1 output file, and
  the output count equals the input count minus the replaced originals.

## Decided by the user

- Split by the student's current school for the new school year.
- Students in alphabetical order within each school file.
- One file per school per report type. The first real run confirms that a school
  file previews in Drive; if it does not, switch to one file per grade before
  any links go to schools.
- One `Transfer Out & Unmatched` folder per region.
- One index Sheet per region at the region folder level, with a shortcut in each
  school folder. Not published to the web.
- Zero friction for school staff is the main design goal.
- Drive and Sheets writes run as the user's own Google account until #6027
  lands.
- A GitHub issue (#6026) and a new worktree branch.

## Calls made in this design (the user can overrule)

- A command run from a Codespace rather than a Dagster asset. It can become a
  Dagster asset after #6027 if someone outside the data team needs to run it.
- `pypdfium2` reads page text. On these files `pypdf` reads about 2 pages per
  second and would take about 2 hours on Newark's file; `pypdfium2` reads about
  100 pages per second. `pypdfium2` is Apache or BSD licensed. Avoid PyMuPDF,
  which is AGPL. `pypdf`, already a dependency, writes the output PDFs.
- Last name and birth date confirm every match; first names are never compared.
- No search box; a sorted list with Ctrl+F steps instead, because staff are
  viewers.
- Reruns route from current enrollment and update files in place.
- One index Sheet per administration, with the year in its name and in the
  shortcut name.
- A report follows the student across regions, and so does the index row.
- Corrected reports replace originals; duplicates within a file both stay.
- The `School last spring` column, to help the old school answer a transfer
  request.
- A yearly folder at the region level holds the index and
  `Transfer Out & Unmatched`, mirroring the yearly folders inside schools.

## Left to the builder

- How the personal Google sign-in works. Prove it first: create, update, and
  trash a test file in a folder the user owns. Try a `gcloud` sign-in that
  writes to its own config folder, so it does not replace the Codespace's
  default credentials. If Google blocks that sign-in from asking for Drive
  access, fall back to a desktop sign-in client in the `teamster-332318`
  project, which may need the data engineer to create.
- Module layout. Pure helpers that unit tests import belong in
  `src/teamster/libraries/`, per `src/teamster/CLAUDE.md`. Keep segmentation,
  confirmation, and routing as pure functions over page text and rows, so tests
  need no PDFs.
- Whether Drive's PDF viewer honors a `#page=N` link. If it does, the
  `Open the report` link jumps straight to the student's first page.
- How to find per-subject "not tested" status on the cover page for the `Note`
  column, if the text supports it.
- Exact file and folder names, within the plain-words rule.

## Testing

- Unit tests on segmentation, name confirmation, and routing use synthetic page
  text and rows. No real student data enters the repo.
- A dry run with `--local-out` on the 2026 files must output 5,781 records and
  pass record conservation.
- A first real run writes into a test folder the user owns. The user confirms
  that the largest school file previews in Drive and that the index links open
  the right file. Only then does a run write into school folders.
- A second real run with no input change leaves every file ID unchanged.

## Before the first real run

The user provides or confirms:

1. The link to `Report Cards and Transcripts`, and the folder name for each
   school that has reports.
2. Edit access to every school folder for the account that runs the command.
3. Sharing of each region's yearly folder with every school's staff in that
   region.

## Later

- Rows for currently enrolled students in tested grades who have no report, so a
  search for a new student returns "no 2026 NJ report on file" instead of
  nothing.
- NJGPA files when the user adds them to the input folder.
- A Dagster asset, if the run moves outside the data team.

## Revision 2026-10-19: service account after the shared-drive move

Google blocks the `gcloud` sign-in client from asking for Drive access in KTAF's
Workspace, so the personal sign-in in _How it runs_ cannot work as designed. The
user chose to move `Report Cards and Transcripts` into the Data Team shared
drive first (#6027). This revision replaces every statement above about running
as the user:

- Drive and Sheets calls run as the Codespace service account,
  `codespaces@teamster-332318.iam.gserviceaccount.com`, which is a Content
  manager of the Data Team shared drive. Nobody signs in.
- The test-folder run needs only a test folder in the Data Team shared drive
  with the service account added, so it can happen before #6027 finishes.
- The real run into school folders waits on #6027.
- _Before the first real run_ item 2 becomes: the service account is a Content
  manager of the shared drive that holds the folders.
- The Drive tag lives in `properties`, not `appProperties`. `appProperties` are
  private to the app that wrote them, so a rerun under another identity would
  miss every tag and duplicate the files.
- A rerun publishes only with the complete input: at least 1 original ISR file
  for every district. A partial input would overwrite other schools' files with
  a subset of students.

## Revision 2026-10-20: relaxed confirmation with an investigation list

The 2026 dry run left 60 records unmatched. 54 of them had a single state-ID
candidate that agreed with PowerSchool on the last name or the birth date, but
not both. The user approved relaxing _Match_:

- A candidate confirms when its last name or its birth date matches the report.
  A candidate that matches both is a full match; one that matches only 1 is a
  partial match. Both kinds route to the student's current school.
- When the 2 sources point to different students, a single full match wins;
  otherwise a single partial match wins; otherwise the record is a
  `source_conflict`.
- Every partial match and every unmatched record goes on an investigation list.
  The command writes it as a CSV on every run, dry runs included, in the
  git-ignored scratch area, and the summary prints its path. It holds the
  printed and PowerSchool names and birth dates, so it never goes to a Drive
  folder that school staff can open, and the index shows no note for a partial
  match.
