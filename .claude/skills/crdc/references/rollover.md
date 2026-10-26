# Rollover for the next cycle

Run this once per cycle, before the kickoff doc goes out. It takes in OCR's
changes, maps each one to the model and the collection sheet, updates the code,
and confirms the fall snapshot date.

## 1. Take in OCR's changes

Ask the user for OCR's changes document for the cycle ("<year> CRDC General
Overview, Changes, and List of Data Elements") and the form PDFs. If they do not
have them, look them up on crdc.communities.ed.gov with WebFetch. Save the PDFs
in the session scratchpad and extract the text:

```bash
uv run --no-project --with pypdf python -c "import pypdf, sys; print('\n'.join(p.extract_text() for p in pypdf.PdfReader(sys.argv[1]).pages))" <pdf> > <scratchpad>/ocr-changes.txt
```

Read three parts: what is new, what is removed, and whether any disaggregation
changed. The appendix marks new items as underlined and removed ones as struck
through; plain text extraction loses both, so read the changes section at the
front, not only the appendix.

## 2. Map each change

Build a table in the session scratchpad, one row per changed element:

| Column         | What goes in it                                                                  |
| -------------- | -------------------------------------------------------------------------------- |
| Element        | OCR's wording                                                                    |
| Change         | New optional, new required, removed, or disaggregation changed                   |
| Form           | LEA or school                                                                    |
| Collection tab | The `DF - ` or `SF - ` tab it belongs on, or "new tab"                           |
| Model section  | The `crdc_question_section` it touches, or "none" when an owner supplies it      |
| Action         | Code change, sheet row added or removed, owner to ask, or "KTAF will not answer" |

Every element whose model section is not "none" needs a code change. Hand the
table to the user; the decision to answer an optional element is theirs.

### SY2025-26, already mapped

| Change                                                       | Model                                                    | Collection sheet                    |
| ------------------------------------------------------------ | -------------------------------------------------------- | ----------------------------------- |
| Nonbinary removed from enrollment, IDEA, 504, EL, discipline | `crdc_gender` still maps `X` to Nonbinary; open decision | Remove NBIN tab and nonbinary cells |
| Gender identity harassment items removed                     | None                                                     | Remove those rows on HIBD and HIBS  |
| COVID remote instruction items removed                       | None                                                     | Remove the COVID rows (likely DIND) |
| New optional: instruction type, remote setting, % remote     | None                                                     | Add rows if KTAF answers            |
| New optional: non-LEA facility students and their restraint  | None                                                     | Add rows on RSTR if KTAF answers    |
| New optional: threat assessment team and referrals           | None                                                     | New tab if KTAF answers             |
| New optional: FTE teachers certified in bilingual ed         | None                                                     | Add row on STAF if KTAF answers     |

The nonbinary change waits on the data team lead and compliance. Do not change
`crdc_gender` until they decide how these students are counted.

## 3. Fall snapshot

The top of `rpt_tableau__crdc_roster.sql` sets the date: 1 October of the
submission year, or the next Monday when it falls on a weekend.

1. Find OCR's definition of the fall snapshot for the cycle in the form
   instructions or FAQ.
2. Compute the date the model will use and confirm it matches OCR's definition.
   Quote OCR's wording to the user; do not paraphrase it from memory. For
   SY2025-26 the model uses 1 October 2025, a Wednesday.
3. If OCR changed the definition, change the three `set` lines at the top of the
   SQL to match.
4. Check the student side. `is_enrolled_oct01` comes from the enrollment model
   and is always the literal 1 October, so in a weekend year `ENRL` and the
   course sections count different days (reference doc → Known issues, "Two fall
   snapshot dates"). If the cycle's snapshot is not 1 October, raise it with the
   user before the counts are used.
5. Write the date into the kickoff doc's reference periods.

## 4. Update the code

- Work on a feature branch, per the repo's branch rules. Read
  `rpt_tableau__crdc_roster.sql` in full first.
- A new model-fed element becomes a new branch in the final union: its own
  `crdc_question_section` and `crdc_question_description`, the same column list
  in the same order as every other branch. A new hand-tagged element needs only
  its section code added to the `in (...)` list on the tagged branch and to the
  `case` that describes it.
- A removed element: remove its branch, or its code from the tagged list.
- Update the model's YAML (`crdc_question_section` description) and the
  reference doc's "What each branch computes" table in the same PR.
- Verify with
  `uv run dbt build --select rpt_tableau__crdc_roster --project-dir <worktree>/src/dbt/kipptaf`
  against the user's dev target (invoke `dbt-local-dev` first), then the counts
  in [model-and-workbook.md](model-and-workbook.md) → A count looks wrong.

## 5. Roll the files

- New cycle subfolder in the CRDC folder; copy the kickoff doc
  ([kickoff.md](kickoff.md)) and collection sheet
  ([collection-sheet.md](collection-sheet.md)) into it.
- Rebuild the student-numbers tab and check the SCED crosswalk
  ([model-and-workbook.md](model-and-workbook.md) → Before the workbook).
- Update the reference doc's "The 2025-26 changes" section for the new cycle and
  its "Good to implement next cycle" list against the new elements.
