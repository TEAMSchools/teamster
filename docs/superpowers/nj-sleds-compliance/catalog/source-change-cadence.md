# Source change cadence: PowerSchool NJ state reporting and NJDOE SLEDS

Facts only. Source paths are relative to
`/tmp/claude-1000/-workspaces-teamster/a2d984af-2c1c-4829-afff-45ec620ac2cf/scratchpad/njdoe_dl/`
(called `$DL` below). PowerSchool page text lives in `$DL/ps_txt/`, raw HTML in
`$DL/ps/`, NJDOE HTML in `$DL/pages/`. Today is 2026-10-20.

Coverage gap to read first: only the **2026** per-release pages were fetched as
text (19 files `$DL/ps_txt/state-reporting-26-*-release-notes.md`). The 2025
per-release pages were **not** downloaded (`$DL/ps/` has only
`2025-release-notes.html`, the year index). Section 1 therefore lists 2025
versions from the page tree only, with no change descriptions, and section 2
covers 2026 entries only. No release page states a calendar date.

## 1. PowerSchool NJ state reporting releases

### Numbering pattern

- Page title and URL: `State Reporting YY.M.N.P Release Notes`, path
  `/pssis-nj/latest/state-reporting-YY-M-N-P-release-notes`
  (`$DL/ps_pages.tsv`).
- `YY` = two-digit year, `M` = month number 1-12. Every year 2020-2025 has at
  least one release in each of the 12 months; 2026 has releases in months 1-10
  (computed from `$DL/ps_pages.tsv`).
- `N` (third number) takes only the values 1, 2, 3 in every year; `P` (fourth
  number) is `0` for 145 of the 164 releases and `1` (17) or `2` (2) for the
  rest (re-release of the same month/N, for example 25.10.1.1 and 25.12.1.1;
  21.x has two `.2`). No fetched page defines what `N` means, so it is not
  interpreted here.
- Each 2026 page says: "A release announcement will be posted on PowerSchool
  Community when the installer is available for download. Refer to 2026 State
  Reporting Releases
  (ps-compliance.powerschool-docs.com/pssis-all-states/latest/2026-release-notes)
  for release dates." (every `$DL/ps_txt/state-reporting-26-*` file, intro
  line). That All States page was not fetched, so no release dates are known.
- `$DL/ps_txt/release-notes.md`: tells readers to also check the All States
  release notes at docs.powerschool.com/ALLSTATES.

### Cadence, releases per year (count of `state-reporting-YY-*-release-notes`

rows in `$DL/ps_pages.tsv`, 372 rows total)

| Year | Releases | Notes                                |
| ---- | -------- | ------------------------------------ |
| 2020 | 20       |                                      |
| 2021 | 22       |                                      |
| 2022 | 25       |                                      |
| 2023 | 22       |                                      |
| 2024 | 29       |                                      |
| 2025 | 27       |                                      |
| 2026 | 19       | through 26.10.1.0 (months 1-10 only) |

Total 164 release pages, about 1.7 to 2.4 per month depending on the year. The
full page tree (`/pssis-nj/latest/__pagetree.json`) parses to 372 nodes in 13
top-level branches (see section 6).

### 2025 releases (27 versions; contents not retrieved)

25.1.1.0, 25.1.2.0, 25.2.1.0, 25.2.2.0, 25.3.1.0, 25.3.2.0, 25.4.1.0, 25.4.2.0,
25.4.3.0, 25.5.1.0, 25.5.2.0, 25.6.1.0, 25.6.2.0, 25.7.3.0, 25.8.1.0, 25.8.2.0,
25.9.1.0, 25.9.2.0, 25.9.3.0, 25.10.1.0, 25.10.1.1, 25.10.2.0, 25.11.1.0,
25.11.2.0, 25.12.1.0, 25.12.1.1, 25.12.2.0 (source: `$DL/ps_pages.tsv`). Dates:
not stated. Change text: not fetched.

### 2026 releases (19)

Source for every row:
`$DL/ps_txt/state-reporting-26-<M>-<N>-<P>-release-notes.md`. Dates: not stated
on any page. Release order is the version order.

| Version   | PSSR refs                                                      | What changed (one line)                                                                                                                                                                                                |
| --------- | -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 26.1.1.0  | 409744, 415347                                                 | Add to Favorites restored on NJSLEDS report pages; ASSA Student Data Validation headers say LIEP, not LEP                                                                                                              |
| 26.1.2.0  | 418538, 381664                                                 | All-states: SRP parameter pages scale when minimized; Student Incident Profile v1.12 reports up to three behavior-code levels                                                                                          |
| 26.2.1.0  | 411094                                                         | NJSLEDS Student Management v6.5: special ed classification logic tied to reevaluation date                                                                                                                             |
| 26.2.2.0  | 418244, 419895, 417911, 417869, 421942                         | All-states: discipline letter hyphen fix; Hearing Screening date filters; Student Incident Profile page-break options (v1.11); RepoSchema scripts run once                                                             |
| 26.3.1.0  | 415767, 411104, 419075, 419733                                 | Accessibility on Incident Management mapping; new Alternate State School Number field; Student Management v6.6 attendance defaults for non-public students; special ed classification dropdown update                  |
| 26.3.2.0  | 422511, 421726, 422733, 419980, 426313                         | Student Incident Profile v1.15; Attendance Profile v1.13 honors tracks; Learning Preferences page; new Incidents and Details enterprise report; NJSLA/NJGPA Adaptive Student File v1.1 excludes DLM students           |
| 26.4.1.0  | 423451                                                         | Staff Course Roster v1.7 extracts all staff section assignments                                                                                                                                                        |
| 26.4.2.0  | 425665, 406148, 425036                                         | Student Incident Profile v1.16; Varicella immunization rule fix; NJSMART references replaced with NJSLEDS in NJ SPED labels                                                                                            |
| 26.4.3.0  | 427581, 429094, 350043, 428676                                 | Attendance reports (v9.2, v6.8) omit excluded enrollments; Course Roster Staff v1.8 and Student v2.9 (SectionExitDate format, longer LastName); A45 vision screening fields                                            |
| 26.5.2.0  | 429831, 410230, 431608, 431341                                 | Discipline letter v2.1; test results change history; Student Course Roster v3.0 parameter for dropped sections; NCES course identifier list                                                                            |
| 26.6.2.0  | 378727, 427504, 433366, 433240                                 | CRDC 2023-24 report fix; General State Information include fields default blank; NJSLA/NJSLA-S accommodation labels; NJSLA/NJGPA-Adaptive Student Attributes v1.2                                                      |
| 26.7.1.0  | 381128, 437955, 411226, 436597                                 | Change history for Student Programs; NCEA 2026-27 fields; Dual Institution Smart Search; NCES course identifier and AP options                                                                                         |
| 26.7.2.0  | 303008, 438990, 439185, 418466                                 | CRDC reports older than 23-24 deprecated; Student Course Roster v3.1; Student Management v6.7 same-school/year enrollments; subdistrict logic for CDS Codes Extract v1.2 and Transfer Card (A41) v2.0                  |
| 26.8.1.0  | 432286, 442681                                                 | Student Management v6.8: subdistrict numbers; School Entry Date fallback                                                                                                                                               |
| 26.8.2.0  | 439554, 433790, 377493, 370717, 366694, 366830, 445234, 445229 | Minimum PowerSchool SIS 26.3.0.1; Office Visit Details order; CRDC fixes; NJ context-sensitive help; 2026-27 SPED and Student Management data-entry changes (class 19, NJGPA, world language, LEIP home language note) |
| 26.9.1.0  | 445230, 445011 (two entries share this ID)                     | NJSLEDS Special Education Data v1.4 (two fields removed, two added); DOE-approved SCED codes selectable; Student Management shared-time State Excused Absences divided by 2 at 0.5 membership                          |
| 26.9.2.0  | 445283, 445295, 446452, 438696                                 | CRDC 25-26 LEA, School, Student UI updates; sub-district read-only security fix                                                                                                                                        |
| 26.9.3.0  | 451186, 452391, 452084, 450022                                 | Student Programs change-history link fix; CRDC 25-26 sub-district UI; discipline letter action-code filter; Staff Management 26-27 code updates (DistrictEntryCode, DistrictEmploymentExitReason)                      |
| 26.10.1.0 | 453099, 454535, 453540                                         | Performance Report 26-27 district and school survey entry pages; NJ TIDE Student File template updated for 2026-27 registration                                                                                        |

Most recent release in the fetched set: **26.10.1.0** (date not stated; the tree
lists it first under 2026). 26.10.1.0 is also the last row in
`$DL/ps_pages.tsv`'s 2026 group.

## 2. Release-note entries touching our four reports (2026 only; 2025 not fetched)

"Mentions" means the entry names the report or its template by name. Closely
paraphrased unless in quotes. Adjacent entries that do not name the report are
listed separately and not counted.

### NJ SLEDS Student Management Report (6 entries name it)

Report page: `$DL/ps_txt/nj-smart-sid-management-report.md`.

1. 26.2.1.0, PSSR-411094: "NJSLEDS Student Management Version: 6.5. Special
   Education Classification is reported in the output when the reevaluation date
   precedes the report submission date, unless the student is ineligible or
   declassified before the report date and is now resolved."
2. 26.3.1.0, PSSR-419075: "NJSLEDS Student Management Version: 6.6. Attendance
   fields for non-public, out-of-district students are now reported with
   consistent default values (all blank or all zero) to prevent NJSLEDS
   validation errors."
3. 26.7.2.0, PSSR-439185: "NJSLEDS Student Management report version: 6.7. All
   enrollments for a student within the same school and school year are included
   in reports using established logic for data representation."
4. 26.8.1.0, PSSR-432286: "NJSLEDS Student Management Version: 6.8. Reports use
   subdistrict numbers for specified fields when subdistricts are enabled and
   default to district numbers when subdistricts are not enabled."
5. 26.8.1.0, PSSR-442681: "NJSLEDS Student Management Version: 6.8. The School
   Entry Date logic ... uses the entry date from the corresponding student or
   reenrollment record when the field is blank, while maintaining all existing
   report functionality and format."
6. 26.9.1.0, PSSR-445011 (second of two entries with this ID): "The Student
   Management template is updated to calculate State Excused Absences for
   Shared-Time students by considering their membership value. Students with a
   0.5 membership value will now have the total calculated value for State
   Excused absences divided by 2 to align with NJSLEDS requirements."

Related, counted separately (data-entry screens, not the report): 26.8.2.0,
PSSR-445229 "NJSLEDS: Student Management Data Entry 26-27": graduation pathway
indicators for ELA and Math gain value NJGPA (stored as 'S'); Special Education
Classification gains 19 ("Undergoing Initial Evaluation to Determine Eligibility
for Special Education Services", no federal code); World Language Assessment
gains ASLT and NEWL; Home Language fields get a note that "A value of English is
not valid for submission for students in an LEIP". Also 26.3.1.0 PSSR-411104
(Alternate State School Number field) and PSSR-419733 (special ed classification
dropdown) change inputs but do not name the report.

Version progression visible in the notes: v6.5 (26.2.1.0), v6.6 (26.3.1.0), v6.7
(26.7.2.0), v6.8 (26.8.1.0).

### Student Course Roster Extract (3 entries)

Report page: `$DL/ps_txt/nj-sleds-student-course-roster-extract.md`.

1. 26.4.3.0, PSSR-429094: "NJSLEDS Course Roster Submission - Student Version:
   2.9 ... updated to output correct SectionExitDate format and support extended
   LastName length, to ensure that the reports comply with state requirements."
   (shared entry with Staff, v1.8)
2. 26.5.2.0, PSSR-431608: "NJSELDS [sic] Course Roster Submission - Student
   Version: 3.0. The report includes a parameter to include all sections and
   specify completion status for non-graded courses, ensuring dropped section
   enrollments are recorded with entry and exit dates and the selected
   completion status."
3. 26.7.2.0, PSSR-438990: "Student Course Roster Report version: 3.1. The
   CreditsEarned field ... outputs a blank value for dropped prior-to-secondary
   courses when the include dropped classes parameter is enabled."

Adjacent (course data the extract reads, report not named): 26.5.2.0 PSSR-431341
and 26.7.1.0 PSSR-436597 (NCES Course Identifier lists, AP options add
Cybersecurity and Networking); 26.9.1.0 PSSR-445011 first entry (DOE-approved
SCED codes selectable, discontinued codes no longer selectable).

### Staff Course Roster Extract (2 entries)

Report page: `$DL/ps_txt/nj-smart-staff-course-roster-extract.md`.

1. 26.4.1.0, PSSR-423451: "NJSLEDS Course Roster Submission - Staff version:
   1.7. Updated the Staff Course Roster report to extract all staff section
   assignments instead of only the most recent, aligning with NJDOE 2025-26
   submission requirements."
2. 26.4.3.0, PSSR-429094: "NJSLEDS Course Roster Submission - Staff Version: 1.8
   ... output correct SectionExitDate format and support extended LastName
   length." (same entry as Student v2.9 above)

Same adjacent NCES/SCED entries as the Student Course Roster apply.

### State Assessment Registration Report (0 entries name it)

Report page: `$DL/ps_txt/nj-state-assessment-registration-report.md` (intro:
"used to generate the New Jersey State Assessment Registration file"). No 2026
release note uses that report name. Adjacent assessment-file and setup entries
(not counted):

- 26.3.2.0, PSSR-426313: NJSLA/NJGPA-Adaptive Student File Template v1.1 no
  longer includes students assigned to DLM for Math and ELA.
- 26.5.2.0, PSSR-410230: Change History can be enabled on Student Test Results.
- 26.6.2.0, PSSR-433366: NJSLA and NJSLA-S accommodation page labels and options
  updated.
- 26.6.2.0, PSSR-433240: NJSLA/NJGPA-Adaptive Student Attributes report v1.2
  accommodation export logic.
- 26.10.1.0, PSSR-453540: "NJSLEDS TIDE Student File template is updated to meet
  the format requirements for student registration in the 2026-27 assessment
  year"; obsolete filler columns removed, new optional columns added and
  extracted blank, mandatory items extracted.

Whether the Assessment Registration Report is the same file as the TIDE/Adaptive
templates is not stated on the pages fetched.

## 3. Known issues listed for the four reports

PowerSchool side: none listed.
`$DL/ps_txt/state-reporting-submission-related-known-issues.md` is a stub: "This
page contains the known issues for each report/functionality as of the specified
date. Updated: January 22, 2020", with no issue entries. It says
submission-related known issues are sent through PowerSchool Community (SIS
State Specific Emerging Issues space, filter label "New Jersey"). That space was
not fetched. The four report pages have no known-issue section (`grep` of
`$DL/ps_txt/nj-*report*.md` and the course roster pages found no "known issue"
heading; the only hits were unrelated words).

Individual 2026 release notes carry one "Known Issue" note, on a different
report: 26.1.2.0 PSSR-381664, Student Incident Profile (4th and 5th level
behavior codes do not associate in the database).

NJDOE side (`$DL/pages/sledsnews_system-updates.shtml.html`, "Last updated:
October 8, 2026"):

- Student Management, current known issue, posted Sept. 10, 2026: "Transfer
  Request Record Remains After a Completed Transfer". After a completed transfer
  and re-upload, an older Transfer Request record can show beside a newer Valid
  record. Guidance: rely on the newer Valid record while a fix is in progress.
- Course Roster (covers Student and Staff Course Roster): "No current known
  issues in Course Roster."
- Staff Management: "No current known issues." (Staff Course Roster out-of-sync
  fix is under Staff Management; see section 5.)
- Assessment registration: the page has no section for it (sections are ID
  Management, Student Management, Staff Management, Special Education, Course
  Roster, Staff Vacancy).
- Not one of our four reports: Special Education known issue posted Oct. 2, 2026
  (Initial Process Delay Reason validation on historical records).

## 4. PowerSchool New Jersey Start of Year Checklist

Source: `$DL/ps_txt/new-jersey-start-of-year-checklist.md`. The page lists tasks
under five headings; numbering below is continuous across them. It also links
the PowerSchool Start of Year Guide for additional updates.

District Setup

1. Review entry, exit, and ethnicity codes
2. Review and update school information
3. Update the default term level
4. Update course information
5. Update Period Mapping
6. Review and update Grade Setup
7. Update Industry Valued Credentials

School Setup 8. Review Years & Terms 9. Review Periods and Cycle Days 10. Review
Sections 11. Review Bell Schedule 12. Complete Calendar Setup 13. Review
Attendance Codes, Categories, and Conversions 14. Review Full-time Equivalencies

Staff Setup 15. Review staff member demographic information

Student Setup 16. Review student demographic information 17. Review school
enrollment 18. Pre-Register students 19. Apply credit for advanced courses 20.
Review Inclusion/Exclusion from State Reporting 21. State Reporting Specific
Fields, with these field sets: - NJS SID: SSID, Immigrant Status, Race,
Enrollment Information, Program Information (LEP Information, ELA Graduation
Pathway Indicator, Math Graduation Pathway Indicator), Attendance Information -
NJS Student: Student Information, Program Information, Health Information,
Homeless Status, Alternative Education Information, Title I Information,
Cumulative Days in Membership, Cumulative Days Present, Cumulative Days Towards
Truancy - NJS SpEd: IEP Dates, Program Codes, Placement Information, Services
Information - NJS CTE: CIP Code, Program Status, Course Override Fields,
Attendance Information for Shared Time Students - Industry Credentials:
Enrollment History - PreID ASK/ACCESS: Program Information (Section 504), State
Assessment Information (District, County and School Codes), Examiner
Information - ESSA - Title I Status - ASSA - Special Status Information -
Register Reports - Charter School Information - PreID NJBCT - Special Services
Information (Title I, LEP), Accommodations, Modifications, Exemptions and CDS -
PreID HSPA - Special Services Information (Title I, LEP), Accommodations,
Modifications, Exemptions and CDS - PreID Alg - PARCC - PARCC Retest, Codes,
Location Information, Examiner Information, Test Overrides, Accommodations

Incident Management Setup (prose, not a checklist) 22. Set up incident types,
codes, and subcodes at the district level, either by loading the one-time New
Jersey configuration file (Start Page > District Setup > District Information)
or manually (Start Page > District Setup > Incident Management).

Observation: the field-set list still names PARCC, NJBCT, HSPA and Alg, and uses
"NJ SID" naming, none of which match the 2026 release notes (NJSLA, NJGPA,
NJSLEDS). The checklist has no step naming the Student Management, Course
Roster, or Assessment Registration reports.

## 5. NJDOE side

### SLEDS system-updates page, what changed recently

Source: `$DL/pages/sledsnews_system-updates.shtml.html` (title "NJSLEDS Known
System Issues and Status Updates"). "Last updated: October 8, 2026"; footer
"Page Last Updated: 10/08/2026". Entries with dates, newest first (our four
reports in bold):

| Date                                                   | Area                                | Change                                                                                                                                                                                                                               |
| ------------------------------------------------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Oct. 8, 2026                                           | **Student Management**              | Fixed: incorrect missing-field errors for preschool referral records (classification 19 with grade 3H/3F/4H/4F/5H/5F); re-upload needed. Grade level must be populated for the exemption                                             |
| Oct. 8, 2026                                           | **Student Management**              | Updated: FAFSA and graduation pathway cross-field rules simplified; grade 9-11 no longer get FAFSA-driven pathway errors; denial pathway (O/P) applies only to grade 12                                                              |
| Oct. 8, 2026                                           | **Student Management**              | Fixed: IEP graduation fields and FAFSA may be blank before April 1 for applicable grade 12 records unless exit code L                                                                                                                |
| Oct. 2, 2026                                           | Special Education                   | Known issue posted: Initial Process Delay Reason validation on historical records                                                                                                                                                    |
| Oct. 1, 2026                                           | **Student Management**              | Fixed: incorrect SchoolExitDate warning for 2026-27                                                                                                                                                                                  |
| Sept. 23, 2026                                         | Staff Vacancy                       | Fixed: hire-count validation for open positions                                                                                                                                                                                      |
| Sept. 11, 2026                                         | Special Education                   | Fix confirmed (posted Sept. 2): fields wrongly required when ParentalConsentObtained is N or R                                                                                                                                       |
| Sept. 10, 2026                                         | **Student Management**              | Known issue posted: Transfer Request record remains after completed transfer                                                                                                                                                         |
| Aug. 21, 2026                                          | **Student Management**              | Fixed: SchoolEntryDate and DistrictEntryDate validation no longer compares to current date. Fall Official Submission accepts historical dates and future dates through Oct. 15, 2026; after the Fall Snapshot, through June 30, 2027 |
| June 26, 2026                                          | **Student Management**              | Fixed: last name "Null" accepted                                                                                                                                                                                                     |
| May 29, 2026                                           | **Staff Course Roster**             | Fixed: Out of Sync for staff assigned to more than six schools; enter 000 in School Code Assigned for one of six slots as overflow                                                                                                   |
| May 15, 2026                                           | **Student and Staff Course Roster** | GradeSpan may be blank for Secondary SCED courses (still required for Prior-to-Secondary)                                                                                                                                            |
| May 15, 2026                                           | **Student and Staff Course Roster** | AvailableCredit may be blank for Prior-to-Secondary SCED courses (still required for Secondary)                                                                                                                                      |
| May 15, 2026                                           | **Staff Course Roster**             | GradeSpan and AvailableCredit removed from the overwrite key; earlier edits may have created duplicates, contact Help Desk                                                                                                           |
| Apr. 13, 2026                                          | **Student and Staff Course Roster** | Fixed: Out of Sync logic now accounts for mid-year student movement                                                                                                                                                                  |
| Apr. 10, 2026                                          | **Student Course Roster**           | Course Type S1 validation rule removed; may return in revised form                                                                                                                                                                   |
| Mar. 13, 2026 (data cleared Mar. 19, reopened Mar. 23) | Staff Vacancy                       | New RecordID field; all existing vacancy data cleared                                                                                                                                                                                |

Undated "Fixed" Student Management items (page lists 17 resolved in total):
grade level for state-responsible students (Resident CDS 21-8909-100 and
21-8501), adult-student DateOfBirth age check removed, Days Open for adult high
schools, Biliterate and World Language rules, grade level for receiving
districts, Tuition Code 3, decimal attendance values (shared-time only),
voluntary FAFSA, LIEPLanguageofInstruction, special ed classification for
preschool-age students, and holding code 19.

Pages for Staff Management, Special Education, and Staff Vacancy have separate
fixed lists (6, 5, and 3 resolved). Course Roster lists 5 resolved (the five
dated Course Roster rows above, S1 included).

### SY2026-27 submission calendar

Source: `$DL/pages/calendar_.html`. "Page Last Updated: 10/02/2026". The page is
a flat list of dated events grouped by quarter and month, not a table. It shows
opens, closes, and "important dates" only; **no certification dates appear
anywhere on the page** (`grep -ic certif` returns 0). Links on the page:
"Download Excel (updated 7/6/26)"
(`/education/sleds/calendar/docs/NJSLEDS_Submission-Timeline-2627.xlsx`) and
"Download PDF (updated 8/3/26)"
(`/education/sleds/calendar/docs/NJSLEDS_Submission-Timeline_2627.pdf`), both
older than the page's 10/02/2026 update stamp.

| Submission                                                | Opens             | Closes            |
| --------------------------------------------------------- | ----------------- | ----------------- |
| Student Management, Official Fall (2026-27)               | July 6, 2026      | October 15, 2026  |
| Student Management, End-of-Year (2026-27)                 | October 19, 2026  | June 30, 2027     |
| Student Management, Graduation Snapshot (2025-26)         | July 6, 2026      | August 31, 2026   |
| Student Management, Seal of Biliteracy                    | not listed        | March 10, 2027    |
| Staff Management, Official Fall (2026-27)                 | July 6, 2026      | October 15, 2026  |
| Staff Management, End-of-Year (2026-27)                   | October 19, 2026  | June 30, 2027     |
| Staff Vacancy, Official Fall (2026-27)                    | August 6, 2026    | October 15, 2026  |
| Staff Vacancy, End-of-Year (2026-27)                      | October 19, 2026  | June 30, 2027     |
| Special Education, Practice Period (2026-27)              | August 20, 2026   | October 15, 2026  |
| Special Education, Official Submission                    | October 19, 2026  | November 16, 2026 |
| Special Education, Practice Period 2                      | November 18, 2026 | June 30, 2027     |
| Performance Report, Official Submission                   | October 16, 2026  | November 20, 2026 |
| CTE, Official (2025-26)                                   | July 2, 2026      | August 5, 2026    |
| Staff Course Roster, Official (2025-26)                   | July 2, 2026      | August 5, 2026    |
| Student Course Roster, Official (2025-26)                 | July 2, 2026      | August 5, 2026    |
| CTE, Practice                                             | April 1, 2027     | June 30, 2027     |
| Staff Course Roster, Practice                             | April 1, 2027     | June 30, 2027     |
| Student Course Roster, Practice                           | April 1, 2027     | June 30, 2027     |
| CTE, Official (school year not labeled)                   | July 2, 2027      | August 3, 2027    |
| Staff Course Roster, Official (school year not labeled)   | July 2, 2027      | August 3, 2027    |
| Student Course Roster, Official (school year not labeled) | July 2, 2027      | August 3, 2027    |

Other dated items: July 6, 2026 "NJSLEDS Officially Opens for 2026-27 School
Year"; 2025-26 High School Graduation Appeals window Sept. 14 to Oct. 2, 2026;
June 30, 2027 "2026-27 School Year Ends". December 2026, January 2027, February
2027, May 2027, and September 2027 each read "No scheduled submissions".

Not on the calendar: Assessment Registration (no submission row). The page does
not label the course roster rows by school year after June 2026; the 2027 course
roster rows sit under 2027 months only.

## 6. Fetch mechanics

- Per the requester, both sites were fetched with plain `curl -A 'Mozilla/5.0'`,
  no authentication, no cookies. The files on disk contain full page content
  with no login wall text (no "sign in" or "enable JavaScript" placeholders
  found with `grep -il` over `$DL/ps/*.html`). The curl invocations themselves
  are not in the files read; this is stated on the requester's word.
- PowerSchool site (`ps-compliance.powerschool-docs.com/pssis-nj/latest/...`):
  `/pssis-nj/latest/__pagetree.json` returns a JSON array of nested
  `{id, title, path, children}` nodes covering every page. Saved as
  `$DL/ps/__pagetree.json.html`; it parses as JSON (13 top-level nodes, 372
  nodes total, matching the 372 rows of `$DL/ps_pages.tsv`). Page links are
  root-relative (`/pssis-nj/latest/<slug>`). Release-note tables are present in
  the static HTML.
- NJDOE pages (`www.nj.gov/education/sleds/...`): static HTML. Links are
  root-relative (`/education/sleds/calendar/docs/...xlsx|pdf`), so a base URL is
  needed to download them. The "Fixed Items" accordions on the system-updates
  page and the quarter accordions on the calendar are present in the HTML (not
  loaded by script). The system-updates page ends in the standard footer, so it
  is not truncated.
- Pages that look JS-rendered or incomplete:
  - `$DL/ps_txt/2025-release-notes.md` and `2026-release-notes.md`: body is only
    the heading; the list of child releases appears only in the sidebar
    navigation of the raw HTML (`$DL/ps/2026-release-notes.html`), not in the
    page body.
  - `$DL/ps_txt/reports-and-extracts.md`: body is one sentence ("Generate these
    reports to collect information ...") with no child list; the report names
    are known only from the page tree.
  - `$DL/ps_txt/state-reporting-submission-related-known-issues.md`: body has a
    header and a Community link with no issue content; the page is stale
    (Updated January 22, 2020), not a rendering failure.
  - `$DL/ps_txt/release-notes.md`: only a pointer to the All States notes.
  - `$DL/ps_txt/state-reporting-26-2-2-0-release-notes.md`: the table header row
    ("Reference / Summary / Release Note") is missing from the extracted text;
    entries are present.
- Not fetched: 2025 per-release pages; All States release notes (where release
  dates live); PowerSchool Community known-issues space.
