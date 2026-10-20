---
name: nj-isr-reports
description: >-
  Use when the state releases NJSLA or NJGPA Individual Student Reports (ISRs)
  and they need splitting by school with a regional index, when a school cannot
  find a student's ISR, when someone asks to rerun or fix the ISR split or index
  (state corrections, enrollment changes), or when working on the investigation
  CSV or teamster.libraries.nj_isr. Triggers: "NJSLA ISR", "NJGPA ISR",
  "Transfer Out & Unmatched", "Find a student's NJSLA report", issues #6026 and
  #6027.
---

# NJ ISR split and index

`uv run python -m teamster.libraries.nj_isr` splits the state's regional ISR
PDFs into one PDF per school per report type, files each student under their
current school, and writes one index Sheet per region. The design, with its
dated revisions, is
[the spec](../../../docs/superpowers/specs/2026-10-19-nj-isr-split-and-index-design.md).
Flags: `uv run python -m teamster.libraries.nj_isr --help`.

## Rules for every run

- The ISR PDFs, the output PDFs, and the investigation CSV hold student names,
  birth dates, and state IDs. They stay in git-ignored `.claude/scratch/` or the
  session scratchpad, never a commit, issue, PR, or Slack message.
- The repo is public. Pass the `Report Cards and Transcripts` link with
  `--root-folder` at run time; never write a Drive folder ID or link into a
  file.
- Drive and Sheets calls run as the Codespace service account
  `codespaces@teamster-332318.iam.gserviceaccount.com`. Nobody signs in. It must
  be a Content manager of the Data Team shared drive that holds
  `Report Cards and Transcripts`; a permission error means it lost that role.
- One program per run: NJSLA files and NJGPA (`_GPA`) files go in separate input
  folders and separate runs.

## Steps

Each step is done when its check passes.

1. **Download the PDFs.** Get the ISR PDFs from the Cambium portal into
   `.claude/scratch/njsla-njgpa-isr/{season} {year} ISRs/`. The folder must live
   there: the investigation CSV lands inside it by default. Done when every
   district the program tests has at least 1 original ISR file: Newark, Camden,
   and Paterson for NJSLA; Newark and Camden for NJGPA. Once Paterson has a
   grade 11, add `7899` to `PROGRAM_DISTRICTS["NJGPA"]` in `destinations.py`.
2. **Update the school list.** In
   `src/teamster/libraries/nj_isr/destinations.py`, edit `SCHOOL_FOLDERS` for
   each new, renamed, or closed school (key: region and PowerSchool `schoolid`;
   value: the school's Drive folder name). Create a new school's
   `{abbreviation} Report Cards` folder in Drive first, with school-level
   sharing. Done when every school with enrolled tested students has a row whose
   folder name matches exactly 1 Drive folder.
3. **Dry run.** Run with
   `--input <folder> --dry-run --local-out <scratchpad dir>`. Read the summary,
   checking that each `School folders` line pairs a school with its own Drive
   folder, then the investigation CSV. The CSV lists every partial match (last
   name or birth date differs from PowerSchool), unmatched report, source
   disagreement the command resolved, and state ID repeated within a file. Hand
   it to the Data team to check and fix in PowerSchool. Done when the run
   finishes without a conservation error and, before the real run, the Data team
   has checked every `birth date differs` row whose `filed_in` is a school,
   because a same-surname sibling is the likely wrong match. Rerun the dry run
   after their fixes land if they change enrollment.
4. **Test run.** Create an empty test folder in the Data Team shared drive, add
   the service account, and run with `--root-folder <test folder link>`,
   `--create-missing-folders`, and `--page-anchor`. Done when all 3 checks pass:
   the largest school file previews in Drive (if it does not, stop, do not run
   against the real root, and tell the code owner, because per-grade output is a
   code change); 3 index rows open the right file and page; and a second
   identical run keeps every file link and lists no file under
   `Files no longer produced`. After the checks, delete the test folder: it
   holds a full copy of every report.
5. **Real run.** Same command, with `--root-folder` set to the link of the
   `Report Cards and Transcripts` folder and without `--create-missing-folders`.
   On the real root a missing or misnamed school folder must stop the run; with
   the flag, that school's reports would go into a new folder its staff do not
   know about. Add `--page-anchor` only if the test run's links landed on the
   right page. Done when the summary's `Root folder` line names
   `Report Cards and Transcripts` and each region's readers are the staff who
   should see that region. Share each region's yearly folder
   (`{season} {year} NJSLA ISRs`) with that region's school staff if they cannot
   open it.
6. **Tell schools where the index is.** The
   `00 - Find a student's NJSLA report - {season} {year}` shortcut in each
   school's yearly folder opens the region's index. Transfer-out students'
   reports are in the region's `Transfer Out & Unmatched` folder.

## Reruns

Rerun when the state sends corrections or enrollment changes.

- Use the complete input folder. The command refuses to publish unless every
  district the program tests (Step 1) has an original ISR file, because a
  partial input would overwrite other schools' files.
- File links survive. The command tags every file it creates in Drive
  `properties` and replaces content in place by tag and name. Tags work under
  any identity; a rerun must use the same scheme or it duplicates files.
- Page numbers can shift. The same run rewrites the index, so it always matches
  the files.
- A tagged file the run no longer produces stays in Drive and is listed under
  `Files no longer produced`. A first run has nothing to list. On a rerun, read
  the list and add `--allow-trash` only when every listed file should go.
