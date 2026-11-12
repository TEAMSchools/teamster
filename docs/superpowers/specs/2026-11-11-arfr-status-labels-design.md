# ARFR status labels on DeansList report cards and letters

Refs #6336. Closes #5677 through the same pull request.

## Intent

The DeansList report card and the Promotional Status dashboard read the same
retention data but label students who are off track in only one area ("gray")
differently. The report card prints "Off-Track: 2+ Grade Levels Below" or
"Off-Track: Excessive Absences"; the dashboard prints "On-Track (Academic
Warning)" or "On-Track (Attendance Warning)". Families and school leaders see
two answers, and K-2 students, whose academics are measured with DIBELS, get a
"grade levels" label that does not apply to them.

Teaching & Learning approved Option C: the report card uses the dashboard's
wording. They also supplied the 2026-27 promotion-in-doubt letter draft (Google
Doc "NJ (ARFR) K-8 Retention System 2026-2027 (FINAL)", tabs "ES Letter",
"Newark/Pat MS Letter", "Camden MS Letter"). Q1 report cards and letters print
**Friday 11/13/2026 in every region**. Everything below must be live for that
print; there is no fallback date.

## Decisions

| Decision                                                                                                                                                                        | Source                                                         |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Overall row for gray K-8 students reads "On-Track (Academic Warning)" or "On-Track (Attendance Warning)"                                                                        | Option C, approved 11/11                                       |
| Orange students keep "At-Risk for Retention"                                                                                                                                    | Unchanged                                                      |
| Academics row drops "- 2+ grade levels below" and reads "Off-Track" for every grade                                                                                             | Approved earlier in #6336                                      |
| The 18 exempt students keep their true status, "At-Risk for Retention", through Q3                                                                                              | Same rule as 2025-26                                           |
| Camden letters follow the Camden criteria: attendance "Not Met" below 88% (85% kindergarten); core classes "Not Met" at 2 failing; add the 3-class automatic-retention sentence | Decided 11/11; posted as a comment on the Camden MS Letter tab |
| Letters print for orange students only, from a DeansList roster                                                                                                                 | 2026-27 policy                                                 |

## Goals

- The report card Overall row says the same thing as the dashboard for every K-8
  student.
- No K-2 report card or letter describes DIBELS results in grade levels.
- Promotion-in-doubt letters match the 2026-27 draft, with Camden using its own
  thresholds.
- All of it is live and render-tested before Friday's print.

## Non-goals

- Progress reports. They print only the attendance status, which does not
  change.
- Defining the label once for both the dashboard and DeansList. The dashboard
  keeps its own calculated field until a follow-up after Q1.
- The dashboard's `school_level = 'OD'` gap and its stale "Is On-Track Int"
  field.
- Miami, which `rpt_deanslist__promo_status` already excludes.
- Q4 report cards, which print promoted/retained from other data.

## Anti-goals

- A blank or broken report card or letter on print day.
- A letter whose attendance or status line contradicts the dashboard for the
  same student.
- DeansList template source or any student data in this repo, which is public.

## Approaches

### Report card labels

- A (chosen). Rewrite the label ladder in `rpt_deanslist__promo_status` only.
  One extract model, a small CI rebuild, and the user can merge extract changes
  the same day.
- B. Compute one label column in `int_students__promotional_status` for both
  DeansList and the Tableau dashboard. It removes the duplicate definition, but
  it touches a hub model and needs a workbook republish. Deferred to after Q1.

### Letter attendance status

- A (chosen). Derive it from `promo_status_attendance`, which already applies
  each region's and grade's threshold from the policy sheet. The letter only
  branches on region for the printed "88%" or "90%" in the requirement text.
- B. Hard-code 85/88/90 by region and grade in the letter. Rejected: a second
  copy of the policy is how today's 90%-for-everyone bug happened.
- C. Add threshold fields to the DeansList extract. Rejected for now: whether
  DeansList accepts new custom-data fields is untested, and Friday leaves no
  room to find out.

## Design

### 1. Data: `rpt_deanslist__promo_status` (this repo)

For NJ regions (`Newark`, `Camden`, `Paterson`):

| Column                    | New value                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `promo_status_overall`    | `At-Risk for Retention` when the policy overall status is `Off-Track`; for grades below 9, `On-Track (Academic Warning)` when academics are off track and attendance is on track, `On-Track (Attendance Warning)` when attendance is off track and academics are on track; otherwise the policy overall status. This mirrors the dashboard's "Promo Status Detail" field for K-8. |
| `promo_status_grades`     | The policy academic status as is (`On-Track` / `Off-Track`) for every grade.                                                                                                                                                                                                                                                                                                      |
| `promo_status_attendance` | Unchanged.                                                                                                                                                                                                                                                                                                                                                                        |

Grades 9-12 keep their current values. The ladder keys on `grade_level`, not
`school_level`, so the 'OD' students fall where their grade puts them.

Required with the change: a dbt unit test covering each branch of the ladder,
and `description:` on the model and every column in its properties file.

### 2. DeansList: promotion-in-doubt letter

Source owned by KIPP BOLD Academy, installed at the NJ K-8 schools. Edits:

- **Attendance status**: "Met" when `promo_status_attendance` is `On-Track`,
  "Not Met" when it is off track, "-" when blank. Replaces the hard-coded 90%
  comparison.
- **Attendance requirement text**: 88% for Camden grades 5-8, 90% elsewhere. The
  elementary wording stays generic, as in the draft.
- **Reading row, K-2**: the Data column shows the DIBELS composite
  (`dibels_composite_recent`, already in the extract). The requirement text adds
  the draft's note that K-2 data reflects DIBELS and 3-4 data reflects i-Ready.
- **Math and Reading status**: print "Met" / "Not Met", as the draft shows,
  mapped from `promo_status_math` and `promo_status_lit`.
- **Core classes, Camden**: keep "Not Met" at 2 or more failing classes and add
  the sentence on 3 failing classes meaning automatic retention with no summer
  school eligibility.
- **Status box and opening sentence**: no code change. For orange students they
  print "At-Risk for Retention".

### 3. DeansList: elementary report card

Source owned by KIPP Lanning Square Primary. Edits:

- 2nd grade joins K and 1st on the "Academics (DIBELS)" row, which shows the
  DIBELS composite in the Detail column.
- Grades 5-6 (Sumner) get the "(i-Ready reading & math)" label and the Math
  line, like grades 3-4.

### 4. DeansList: middle/high school report card

Source owned by KIPP Cooper Norcross High School. No template change; it prints
the new values as they arrive. Render-check that the Spanish labels fit the
Status column.

### 5. DeansList: Spanish translations

Add to the translations grid before printing: the 2 warning labels, the K-2
DIBELS note, and the Camden automatic-retention sentence. A missing entry prints
the English text, not a blank (verified in DeansList's report helper code), so a
late translation degrades instead of breaking.

## How the DeansList work is done

Template edits follow the workflow in `.claude/scratch/deanslist/` (gitignored):
pull the live four files, save a baseline, apply scripted edits, run the gates
(JS syntax, GraphQL validation against the introspected schema, cross-file
partial consistency), then hand the user a paste list. The baseline is the
rollback: pasting it back restores the live report.

## Verification

- dbt: unit test passes; CI build passes; after merge, label counts in prod
  match the pre-merge projection from current data.
- After the DeansList upload, the user renders and checks: a K-2 letter, a
  Camden grade 5-8 letter, a Newark grade 5-8 letter, one Spanish letter, a 2nd
  grade and a Sumner 6th grade report card, and a middle school report card with
  each warning label in English and Spanish.

## Timeline

| When                | What                                                                    |
| ------------------- | ----------------------------------------------------------------------- |
| Wed 11/11           | This doc; data pull request opened; live templates pulled and baselined |
| Thu 11/12 morning   | Template edits built and gated; translations requested                  |
| Thu 11/12 midday    | User pastes templates; render tests against current data                |
| Thu 11/12 afternoon | User merges the data pull request; prod view confirmed rebuilt          |
| Thu 11/12 evening   | DeansList upload run once, with the user's OK; report cards re-checked  |
| Fri 11/13           | Print. The 1:25 am nightly upload is the backstop                       |

## Left to the builder

- How the letter detects Camden (a `city` field on the schools query, or a
  school-id list), provided the GraphQL gate passes.
- Exact placement of the new letter text within the existing partials.
- Whether manual retentions (0 today) should also print "At-Risk for Retention";
  the dashboard treats them as off track. Not in scope unless a value appears
  before Friday.

## Open items

- Whether the letter and report cards are installed at the Paterson schools.
  Checking needs a school switch in DeansList, which the user approves first.
- Spanish wording for the new strings, from Teaching & Learning.
