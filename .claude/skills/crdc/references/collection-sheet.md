# The collection sheet

The internal Google Sheet where every answer is gathered before entry, one per
cycle (`SY23-24 CRDC Data Submission` is the last one). It is laid out like the
OCR form so values can be typed straight across.

## Set it up

1. Copy the last cycle's sheet into the new cycle subfolder and rename it.
2. Add a value column for every district that files. SY2023-24 had `CAM` and
   `NEW`; add `PAT` from SY2025-26.
3. Clear every value column, the SME column, and the progress tracker. Keep the
   audit reason and correction reason columns empty but in place; the entry step
   fills them.
4. Apply the element changes from [rollover.md](rollover.md): add rows for new
   elements KTAF will answer, delete rows OCR removed. For SY2025-26 that
   removes the NBIN tab (nonbinary indicator) and the gender identity rows on
   the harassment tabs, once the form confirms it.
5. Clear the `ARRS - Raw Data` tab. It lists incidents at student level (names,
   student numbers, incident links): keep the sheet shared only with people
   working the collection.

## Layout

- `Home`: instructions, and percent complete per region per tab.
- `DF - <code>` tabs: the district (LEA) form. `SF - <code>` tabs: the school
  form.
- Each item tab has the columns Section, Subsection, Description, Details (OCR's
  wording), Timeframe (the reference period), one value column per region, and
  SME. Tabs that drew OCR quality flags also have Audit Reason and Correction
  Reason Details.
- A value like `708,2,2,0,1245,4,271` is one number per breakdown in the OCR
  form's order (for enrollment, the seven race and ethnicity categories). Keep
  that order; entry types it straight across.

## Who fills what

SY2023-24 SMEs, by role. "Blank" means the SME cell was empty last cycle, and
"role unconfirmed" means a name was recorded without a role. Use the kickoff
doc's owner table for the current cycle.

| Tab                                | What it asks                                                                | Filled by                                    |
| ---------------------------------- | --------------------------------------------------------------------------- | -------------------------------------------- |
| DF - SSPR                          | LEA enrollment count on the snapshot date                                   | Data team (model)                            |
| DF - CRCO                          | Civil rights coordinators                                                   | Compliance contact (role unconfirmed)        |
| DF - HIBD                          | Written harassment or bullying policy                                       | Compliance contact (role unconfirmed)        |
| DF - NBIN                          | Any students recorded as nonbinary (removed for 2025-26)                    | Blank                                        |
| DF - DSED                          | Distance education enrollment                                               | Teaching and Learning                        |
| DF - HSEE                          | High school equivalency prep program                                        | Blank (answered No)                          |
| SF - SCHR, SF - DIND               | School characteristics, instruction type                                    | Blank                                        |
| SF - ENRL, SF - PENR               | Enrollment by demographics; gifted, dual enrollment, credit recovery        | Data team (model)                            |
| SF - COUR, SF - APIB, SF - SAT/ACT | Algebra I, math, science, computer and data science; AP and IB; SAT and ACT | Data team (model)                            |
| SF - RETN                          | Retention by grade                                                          | Data team (model)                            |
| SF - ATHL                          | Interscholastic athletics                                                   | Teaching and Learning, data team tags        |
| SF - STAF, SF - SECR               | Teacher FTE and certification; security staff                               | Talent                                       |
| SF - DISC                          | Discipline counts and indicators                                            | Discipline owner (data team last cycle)      |
| SF - ARRS, SF - OFFN, SF - HIBS    | Referrals and arrests; offenses; harassment or bullying                     | Two school-level contacts (role unconfirmed) |
| SF - RSTR                          | Restraint and seclusion                                                     | Blank; ask the special education owner       |
| SF - INET                          | Internet access and devices                                                 | Technology                                   |

"Data team (model)" tabs come from the workbook
([model-and-workbook.md](model-and-workbook.md)). Every other tab is typed in by
its owner; the warehouse has no source for it.

## Chasing gaps

- Read the Home tab's progress per region before each milestone. An empty value
  column for a region is the gap to chase, not the whole tab.
- An owner who cannot answer by the gap deadline names why (no source, no owner,
  unclear question). Record the reason in the kickoff doc's open questions.
- Discipline and arrest counts from department sheets are checked against the
  ARRS raw-data tab before entry: the incident list and the count must agree.
