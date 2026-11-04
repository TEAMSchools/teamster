# Portfolio appeals from NJDOE

A portfolio appeal is pathway code `N`. NJDOE grants them and sends one decision
PDF per region. The C3 team (Ashley Leonardi) forwards them, usually over Slack,
near the end of the school year. The data team turns them into PowerSchool Quick
Import files. There is no pipeline: the model only ever reads the resulting
`ps_grad_path_code`, and never overrides an `N`.

Only Newark and Camden have high schools today, so the script accepts only those
two regions. When Paterson's first class reaches grade 12, add `Paterson` to
`REGIONS` in the script and a third `--pdf` here.

The Portfolio Data folder on the data team's shared drive holds one
`SY<yy>-<yy> Portfolio` subfolder per year with that year's PDFs. Ask the data
team for the link. The folder also holds the Portfolio Converter Excel workbook
and the NJ Portfolio Appeal Upload Template sheet: the old PowerQuery route. The
script below replaces both; do not use them.

## Steps

1. If the PDFs arrived over Slack, ask the user to save them into that year's
   Drive subfolder first; there is no Slack download step. Then download both
   PDFs into the session scratchpad, never into the repo. They carry student
   names and state IDs. With the Google Drive MCP, `download_file_content`
   spills the base64 to a tool-results file; decode it with Python into the
   scratchpad.
2. Run the converter from the repo root:

   ```bash
   uv run --with pdfplumber python \
       .claude/skills/graduation-pathways/scripts/portfolio_appeals_to_tsv.py \
       --pdf Newark=<scratchpad>/newark.pdf --pdf Camden=<scratchpad>/camden.pdf \
       --out <scratchpad>/portfolio_tsv
   ```

   It keeps each student whose ELA or Mathematics outcome is `Approved`, maps
   the 10-digit State Student Identifier to the PowerSchool `student_number`
   through `kipptaf_extracts.int_extracts__student_enrollments`, and writes
   `<Region> - ELA.tsv` and `<Region> - Math.tsv`. It prints counts only.

3. Read its output. It writes no files when anything is wrong, and deletes any
   earlier output in `--out`. A non-zero exit means stop: a PDF whose table
   header is not name, state ID, ELA, Mathematics (NJDOE changed the layout), an
   outcome other than `Approved`/`NA` (NJDOE changed the wording), a state ID
   with no PowerSchool student, or a student who resolves to the other region.
   Settle each with the C3 team before importing; never hand-edit the TSVs to
   make it pass.
4. Put the four TSVs in that year's Drive subfolder, so the user can reach them
   from the PowerSchool browser session. Delete them from the scratchpad once
   imported.
5. The user imports each file in its region's PowerSchool: Data and Reporting,
   Imports, Quick Import. Choose the **Students** table, **LF** as the
   end-of-line marker, and the TSV. Confirm the column names, tick to exclude
   the first row, and choose the update-the-student's-record option. PowerSchool
   lists the students it changed; anything in red is an error, and Walters
   resolves those.

**Switch PowerSchool instances between the Newark and Camden files.** Importing
a region's file into the other instance is the failure this procedure is most
prone to. The script's region check catches a student in the wrong PDF, not a
file imported into the wrong instance.

## After the import

Check the import landed, the day after (PowerSchool reaches the warehouse
overnight). For each region and subject, every approved student should read `N`
in `stg_powerschool__s_nj_stu_x` (`graduation_pathway_ela`,
`graduation_pathway_math`), joined to `stg_powerschool__students` on
`dcid = studentsdcid` in the region's `kipp<region>_powerschool` dataset. Report
counts per region and subject, never student numbers.

On SY25-26 (checked 2026-09-30) the script's output matched PowerSchool for
every approval in both regions. The TSVs that the old route left in the
Portfolio Data folder are not a record of what was imported: the Camden pair
there does not match PowerSchool. Trust PowerSchool, not a leftover file.
