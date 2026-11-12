# NJ SLEDS Student Course Roster: field and rule catalog

Facts only, no test design. Every rule is quoted or closely paraphrased from a
source below, with its citation. Where sources disagree, the disagreement is
recorded in section 6 rather than resolved. Compiled 2026-10-20.

## Sources and citation keys

| Key                       | Source                                                                                                                                                             | Version / date                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| HB p.N                    | NJDOE _Student Course Roster Submission Handbook_ (`pdf_txt/NJSLEDS_Student-Course-Roster_Handbook.txt`)                                                           | Version 1.4, cover "July 2026", revision history "July 28, 2026" (HB p.1, p.5) |
| UG p.N                    | _User Guide to NJSLEDS Course Roster Reports_                                                                                                                      | "Last Updated: May 2026" (UG p.1)                                              |
| SPR p.N                   | _School Performance Reports: Course Roster Guidance_                                                                                                               | "Last Updated: March 2026" (SPR p.1)                                           |
| FAQ Qn                    | NJSLEDS Course Roster FAQ page (`pages/faq_roster.html`)                                                                                                           | FAQ "Last updated: July 24, 2026"; page last updated 09/10/2026                |
| CAL                       | NJSLEDS Submission Calendar page (`pages/calendar_.html`)                                                                                                          | "2026-2027 SCHOOL YEAR v1.0", built 7/6/2026, page last updated 10/02/2026     |
| SYS                       | NJSLEDS system updates page (`sys_updates.txt`), Course Roster section                                                                                             | Last updated October 8, 2026                                                   |
| RES                       | NJSLEDS Course Roster User Resources page (`pages/resources_roster.html`)                                                                                          | Page last updated 09/09/2026                                                   |
| PS-X item N               | PowerSchool _NJ SLEDS Student Course Roster Extract_ spec (`ps_txt/nj-sleds-student-course-roster-extract.md`); item = row in its Report Output table              | undated web page                                                               |
| PS-SCH / PS-DIST / PS-SID | PowerSchool NJ _School Setup_, _District Setup_, _NJSLEDS Student Management Information_ pages                                                                    | undated web pages                                                              |
| TPL-A / TPL-B             | `NJSLEDS_Student-Course-Roster_Template-A.xlsx` / `-B.xlsx`                                                                                                        | both "Aug 29, 2025" per RES                                                    |
| SCED                      | `NJSLEDS_SCED-Course-Codes.xlsx`                                                                                                                                   | sheets say "Updated: February 2026"; RES says Feb 27, 2026                     |
| OPE                       | `NJSLEDS_OPE-ID-List.xlsx`                                                                                                                                         | undated                                                                        |
| SPEC                      | `docs/superpowers/specs/2026-07-30-nj-sleds-grade-credit-backfill-design.md` (in-house)                                                                            | 2026-07-30                                                                     |
| SUB                       | `docs/superpowers/nj-sleds-roster/submission/README.md` (in-house)                                                                                                 | —                                                                              |
| RB                        | `docs/superpowers/nj-sleds-roster/runbook.md` on unmerged branch `anthonygwalters/docs/claude-nj-sleds-course-roster-runbook` (in-house; not in the main checkout) | —                                                                              |

Not usable: `NJSLEDS_Submission-Timeline_2627.pdf` has no extractable text, so
CAL is the only date source for SY2026-27.

## 1. Submission facts

### Window (SY2026-27)

| Event                                            | Date                                                                                            | Source |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ------ |
| Student Course Roster practice period opens      | April 1, 2027                                                                                   | CAL    |
| Student Course Roster practice period closes     | June 30, 2027 (same day the 2026-27 school year ends and Student Management End-of-Year closes) | CAL    |
| Student Course Roster official submission opens  | July 2, 2027                                                                                    | CAL    |
| Student Course Roster official submission closes | August 3, 2027                                                                                  | CAL    |
| Staff Course Roster                              | same four dates as Student                                                                      | CAL    |

Context:

- UG p.3: practice period is "April through June", official window "July through
  August". During the official window the Course Roster Reports use "Student
  Management end-of-year snapshot data"; during practice they use "current
  Student Management records."
- SPR p.1: "LEAs submit course roster data once a year in NJSLEDS during the
  end-of-year submission period." Uploading during practice lets the Office of
  Performance Management review the data (SPR p.1).
- The prior cycle (SY2025-26) ran July 2, 2026 to a close that CAL displays as
  "August 5, 2026" but tags `datetime="2026-08-03"`; UG p.1 says "before the
  August 3 deadline." See section 6.

### What is in scope

- All courses in all grades and subject areas: "the Course Roster submission
  should cover all courses in all grades and subject areas" (UG p.4).
- "all courses that appear on a student's transcript should be reported",
  including Study Hall, Community Service, Workplace Experience; unclassified
  courses use the miscellaneous SCED subject areas (Prior to Secondary 72,
  Secondary 22); "The available credit value should be 0.000 if students do not
  receive a grade. If a course appears on the transcript (even with zero
  credit), it should be reported." (FAQ Q2.3)
- Students: "Report students enrolled and attending courses in your district.
  This includes students attending your district, that are not your Student
  Management reporting responsibility; these students will appear in your Out of
  District Records page in Student Management." (FAQ Q1.10)
- Excluded populations: "Preschool students placed at contracted preschool
  provider locations are not reported" (FAQ Q1.10); "Course Roster data will not
  be collected from private placements or non-publics" (FAQ Q1.12).
- Service rosters (a subset of a section receiving specialized services) are not
  required; districts that report them create a separate section for the service
  roster (FAQ Q1.11).
- Course types collected: standard (single teacher or co-teachers assigned to
  the district), remote, online, and college-level dual enrollment/dual credit
  taught by staff assigned or not assigned to the district (FAQ Q2.1, Q2.2).
  "Course Type codes for these scenarios should only be used if the district/
  entity where the student attends the course is NOT required to report these
  students. Each term or semester of a course must be reported separately if
  scheduled as separate sections." (FAQ Q2.2)
- Dual enrollment: CourseType `C` "should only be used if there is an existing
  articulation agreement between the high school and a college or university"
  (HB p.37, p.39); "It should not be used for AP/IB courses when there is just
  the possibility of earning college credit." (SPR p.2)
- Departed students: "If no Student Course Roster Record is submitted for a
  student, then that student's SGP will not be counted in the Median SGP
  calculation" (FAQ Q3.1, Q8.3). Whether to store a final grade for a student
  who left (which is what makes the SIS emit a record) "is a district decision"
  (FAQ Q3.2).
- Grade levels: the handbook places no grade-level restriction on rows;
  GradeSpan runs PK through 12 (HB p.26). The student's grade level is not a
  file element; reports take it from Student Management by SID (UG p.2).

### Date range

- SectionEntryDate and SectionExitDate must each "occur in the current School
  Year" (HB p.20, p.22); SectionExitDate may not be "later than the file
  submission date" (HB p.22).
- "Since the course submission is being collected at the end of the year, will
  all students have a course exit date?" "Yes." (FAQ Q3.3)
- Each continuous enrollment period in a section is a separate record (HB p.20,
  p.22).

### File format

- 25 columns, in the order of the element table below (HB pp.11-39; TPL-A and
  TPL-B header rows match this order exactly).
- TPL-A and TPL-B header cells for four columns carry a trailing space:
  `SubjectArea `, `CourseIdentifier `, `CourseLevel `, `CourseSequence `.
- PowerSchool produces "the comma delimited file to submit to NJ SLEDS" (PS-X
  Introduction). The handbook does not state delimiter, header-row requirement,
  quoting, encoding, or line endings.
- RES: "Use Template A if you don't have a source system and are building your
  file from scratch (includes lookup values)"; "Use Template B if you are
  exporting from a source system (header row only)".
- Dates are `YYYYMMDD` with no separators (HB p.15, p.20, p.22).
- Leading zeros must be kept on LID (HB p.11), CDS codes (HB pp.16-18),
  CourseIdentifier (HB p.24); UG p.5: "make sure that all CDS codes, subject
  area codes, and course identifier codes include leading zeroes (e.g., "01" or
  "010")" or records may drop out of reports.
- Any field whose first character is `+`, `-`, `@`, or `=` has that character
  removed on upload; "This new rule will apply to all NJSLEDS fields in all
  submissions." (FAQ Q9.1)
- Certification: submitting is "a formal certification that the information is
  accurate" (HB p.9).

### Handbook version notes (HB p.5-6)

- 1.4 (July 28, 2026): CDS validation wording: shared-time "should refer to
  Attending, not Receiving".
- 1.3 (July 2026): CourseType for exception students (R, C, O) may differ from
  others in the same section.
- 1.2 (May 2026): GradeSpan may be blank for Secondary courses; AvailableCredit
  may be blank for Prior to Secondary courses. SYS confirms both took effect in
  the validator May 15, 2026.
- 1.1 (March 2026): LID and SID definitions aligned to NJSLEDS.
- 1.0 (February 11, 2026): NJ SMART renamed to NJSLEDS.
- NJ SMART 2.4 (December 17, 2020): DualInstitution added; grade validation
  restored for credit-bearing Secondary courses and Prior to Secondary 060X+.

## 2. Element table

Required counts: 17 Mandatory, 8 Conditional, 0 Optional (25 elements). The
three grade elements are a one-of group (HB p.33).

| #   | Element name              | Required?                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Type/length                       | Domain                                                                                                                                                                | Validation rules (each is a stated error)                                                                                                                                                                                                                                                                                                                                                        | Handbook page | PowerSchool source                                                                                                                                                                                                                                                     | Notes/ambiguity                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| --- | ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | LocalIdentificationNumber | Mandatory: "This field is mandatory for all students."                                                                                                                                                                                                                                                                                                                                                                                                                | Alphanumeric, 1-20                | District-assigned                                                                                                                                                     | (1) Blank.                                                                                                                                                                                                                                                                                                                                                                                       | p.11          | `[Students]Student_Number` (PS-X item 1, len 20)                                                                                                                                                                                                                       | Must be unique for the student throughout enrollment; keep leading zeros; no embedded meaning (p.11). Common error "Duplicate student record with the same information exists in the LEA"; fix by listing each course record once per student (p.11).                                                                                                                                                                                                                                                                      |
| 2   | StateIdentificationNumber | Mandatory: "This field is mandatory for students."                                                                                                                                                                                                                                                                                                                                                                                                                    | Numeric, exactly 10               | NJSLEDS-issued SID                                                                                                                                                    | (1) Not exactly 10 digits. (2) Blank. (3) "not a valid number issued by NJSLEDS". (4) Does not exactly match Student Management.                                                                                                                                                                                                                                                                 | p.12          | `[Students]State_StudentNumber` (PS-X item 2)                                                                                                                                                                                                                          | Common error: SID + FirstName + LastName + DateOfBirth must match the Student Management Snapshot exactly, and the Snapshot record must be "free of Error, Sync, Transfer Requests, and Unresolved" (p.12).                                                                                                                                                                                                                                                                                                                |
| 3   | FirstName                 | Mandatory: "mandatory for all students."                                                                                                                                                                                                                                                                                                                                                                                                                              | Alpha, 1-30                       | —                                                                                                                                                                     | (1) Blank. (2) Special characters other than apostrophe and hyphen; "Periods are not accepted". (3) Does not exactly match Student Management.                                                                                                                                                                                                                                                   | p.13          | `[Students]First_Name`; `[StudentCoreFields]PSCore_Legal_First_Name` if populated (PS-X item 3); report input "Student Name to Print" = Preferred or Legal (PS-X item 26)                                                                                              | No nicknames or abbreviations (p.13). Unknown name: report "Unknown" (FAQ Q3.4).                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| 4   | LastName                  | Mandatory: "mandatory for all students."                                                                                                                                                                                                                                                                                                                                                                                                                              | Alpha, 1-50                       | —                                                                                                                                                                     | (1) Blank. (2) Special characters other than apostrophe and hyphen; periods not accepted. (3) Does not exactly match Student Management.                                                                                                                                                                                                                                                         | p.14          | `[Students]Last_Name`; `[StudentCoreFields]PSCore_Legal_Last_Name` if populated (PS-X item 4)                                                                                                                                                                          | Include all last names; hyphen only if part of the legal name, otherwise a space (p.14).                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| 5   | DateOfBirth               | Mandatory: "mandatory for all students."                                                                                                                                                                                                                                                                                                                                                                                                                              | Date, 8, `YYYYMMDD`               | —                                                                                                                                                                     | (1) Blank. (2) Not `YYYYMMDD`, or contains separators. (3) "outside of reasonable parameters (i.e. date occurs in the future, date ages student outside legal limits of education system)". (4) Does not exactly match Student Management.                                                                                                                                                       | p.15          | `[Students]DOB`, extracted as `YYYYMMDD` (PS-X item 5)                                                                                                                                                                                                                 | "Reasonable parameters" not quantified.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 6   | CountyCodeAssigned        | Mandatory (required text is garbled: "Yes. This field is The New Jersey County in which the student is currently assigned to the course. for all students.")                                                                                                                                                                                                                                                                                                          | Character, exactly 2              | NJSLEDS County District School Code List                                                                                                                              | (1) Blank. (2) Does not conform to the codes listed for your district in the CDS list. (3) Missing leading zeros ("03, not 3"). (4) CDS does not align with the student's Student Management record for the same SID: non-shared-time to Attending CDS; shared-time vocational (Enrollment Type = S and Reported Shared Vocational = Y) to Attending CDS; all other shared-time to Resident CDS. | p.16          | `[S_NJ_SEC_X]CountyCodeAssigned`; if blank `[Schools]CountyNumber` (PS-X item 6)                                                                                                                                                                                       | Should reflect the county "for the specific course section" (p.16). PS-SCH names the school field `[Schools]CountyNbr`.                                                                                                                                                                                                                                                                                                                                                                                                    |
| 7   | DistrictCodeAssigned      | Mandatory: "mandatory for all students."                                                                                                                                                                                                                                                                                                                                                                                                                              | Character, exactly 4              | CDS list                                                                                                                                                              | (1) Blank. (2) "does not match the Submitting District". (3) Missing leading zeros ("0010, not 10"). (4) Same Student Management CDS alignment rule as #6.                                                                                                                                                                                                                                       | p.17          | `[S_NJ_SEC_X]DistrictCodeAssigned`; if blank `[Gen]Cat=districts [Gen]Value` (PS-X item 7)                                                                                                                                                                             | PS-SCH says a blank section override extracts "the District Code found on the District Info page" instead. See section 6.                                                                                                                                                                                                                                                                                                                                                                                                  |
| 8   | SchoolCodeAssigned        | Mandatory: "mandatory for all students."                                                                                                                                                                                                                                                                                                                                                                                                                              | Character, exactly 3              | CDS list                                                                                                                                                              | (1) Blank. (2) Does not conform to the codes for your district in the CDS list. (3) Missing leading zeros ("020, not 20"). (4) "School Code designated for a non-operational school is used". (5) Same Student Management CDS alignment rule as #6.                                                                                                                                              | p.18          | `[S_NJ_SEC_X]SchoolCodeAssigned`; if blank, the section's school (`[Sections]SchoolID`): `[Schools]Alternate_School_Number`, else `[Schools]School_Number` (PS-X item 8)                                                                                               | PS-X labels this item "School Code Attending". PS-DIST: for a charter with multiple buildings, store the state school number in Alternate School Number.                                                                                                                                                                                                                                                                                                                                                                   |
| 9   | SectionEntryDate          | Mandatory: "mandatory for all students."                                                                                                                                                                                                                                                                                                                                                                                                                              | Date, 8, `YYYYMMDD`               | Current school year                                                                                                                                                   | (1) Blank. (2) "does not meet the acceptable range of values". (3) Not `YYYYMMDD`. (4) Entry date after exit date. (5) Not in the current School Year.                                                                                                                                                                                                                                           | p.20-21       | `[S_NJ_SGR_X]Section_Start_Date`; if no stored grade `[CC]DateEnrolled`. "only the most recent assignment extracts" (PS-X item 9)                                                                                                                                      | Date the student started attending; align with local attendance roster. One record per continuous enrollment period; erroneous records need a delete request. Do not change a submitted entry date unless it was wrong, because a changed key creates a new record (p.20-21). Used in mSGP. "Acceptable range" undefined.                                                                                                                                                                                                  |
| 10  | SectionExitDate           | Conditional: "Sometimes. This field is mandatory for all students who are no longer active in the course. Otherwise, this field is not mandatory and should be left blank."                                                                                                                                                                                                                                                                                           | Date, 8, `YYYYMMDD`               | Current school year, not after submission date                                                                                                                        | (1) "An error will occur if this field is left blank." (2) Outside acceptable range. (3) Not `YYYYMMDD`. (4) Exit date before entry date. (5) Not in the current School Year. (6) Later than the file submission date.                                                                                                                                                                           | p.22          | `[S_NJ_SGR_X]Section_End_Date`; if no stored grades `[CC]DateLeft`; most recent assignment only (PS-X item 10, typed Alpha-numeric 8)                                                                                                                                  | Rule (1) contradicts the conditional requirement (section 6). FAQ Q3.3: at year end every student has an exit date. "Do not overwrite earlier exit/entry dates with the most recent entry date." (p.22) Entry date equal to exit date is not stated as an error.                                                                                                                                                                                                                                                           |
| 11  | SubjectArea               | Mandatory: "mandatory for all courses."                                                                                                                                                                                                                                                                                                                                                                                                                               | Numeric, exactly 2                | NJSLEDS SCED Course Codes document                                                                                                                                    | (1) Blank. (2) Not a valid SCED Subject Area code.                                                                                                                                                                                                                                                                                                                                               | p.23          | `[S_NJ_SEC_X]NCES_Subject_Area`; if blank `[S_NJ_CRS_X]NCES_Subject_Area` (PS-X item 11)                                                                                                                                                                               | Prior to Secondary codes for courses without Available Credit; Secondary codes for Available Credit greater than 0.000 (p.23). Subject areas 51, 52, 73 may affect mSGP (p.23). No explicit leading-zero error for this element, but UG p.5 warns about it.                                                                                                                                                                                                                                                                |
| 12  | CourseIdentifier          | Mandatory: "mandatory for all courses."                                                                                                                                                                                                                                                                                                                                                                                                                               | Numeric, exactly 3                | SCED document                                                                                                                                                         | (1) Blank. (2) Not a valid SCED Course Identifier code. (3) Missing leading zeros.                                                                                                                                                                                                                                                                                                               | p.24          | `[S_NJ_SEC_X]NCES_Course_ID`; if blank `[S_NJ_CRS_X]NCES_Course_ID` (PS-X item 12)                                                                                                                                                                                     | Same prior/secondary credit note as #11 (p.24). The handbook does not say the identifier is validated as a pair with SubjectArea (section 6).                                                                                                                                                                                                                                                                                                                                                                              |
| 13  | CourseLevel               | Mandatory: "mandatory for all courses."                                                                                                                                                                                                                                                                                                                                                                                                                               | Alpha, 1                          | `B` Basic/remedial, `G` General/regular, `E` Enriched/advanced, `H` Honors, `X` No specified level                                                                    | (1) Blank. (2) Not a valid SCED Course Level code.                                                                                                                                                                                                                                                                                                                                               | p.25          | `[S_NJ_SEC_X]Course_Level`; if blank `[S_NJ_CRS_X]Course_Level`; "Blank is not a valid value" (PS-X item 13)                                                                                                                                                           | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 14  | GradeSpan                 | Conditional: "This field is mandatory for all prior-to-secondary courses. This field is not mandatory for secondary courses and can be blank."                                                                                                                                                                                                                                                                                                                        | Alphanumeric, exactly 4           | Two 2-character grade codes, PK through 12, kindergarten `KG`, prekindergarten `PK` (e.g. `KG01`)                                                                     | (1) Blank for a course with a Prior-To-Secondary course code. (2) Does not match the acceptable range of values.                                                                                                                                                                                                                                                                                 | p.26          | `[S_NJ_SEC_X]Course_Span`; if blank `[S_NJ_CRS_X]Course_Span`; "extracts as blank for Secondary course codes" (PS-X item 14)                                                                                                                                           | Start-before-end ordering is not stated. Span is the grades the course is meant to teach, not the members' grades (FAQ Q7.2). SYS (May 15, 2026): may be populated or blank on Secondary courses without error.                                                                                                                                                                                                                                                                                                            |
| 15  | AvailableCredit           | Conditional: "This field is mandatory for all secondary courses. This field is not mandatory for prior-to-secondary courses and can be blank."                                                                                                                                                                                                                                                                                                                        | Numeric with a decimal point, 5-6 | `0.000`-`35.000`                                                                                                                                                      | (1) Blank for a course with a Secondary course code. (2) Outside the acceptable range.                                                                                                                                                                                                                                                                                                           | p.27          | `[Courses]Credit_Hours`; extracts blank for Prior-To-Secondary codes; format `xx.xxx` (PS-X item 15)                                                                                                                                                                   | "Decimal points rounded up to the nearest thousandths are accepted"; "0.000 means the course does not carry any credits" (p.27). Common-error fix: value "includes three decimal places" (p.27). Multi-part courses may split credit across sequences, and the parts "must equal the total course credit" (FAQ Q7.3). Do not alter established credit values for the submission (FAQ Q7.3). PS has no section-level override.                                                                                              |
| 16  | CourseSequence            | Mandatory: "mandatory for all courses."                                                                                                                                                                                                                                                                                                                                                                                                                               | Numeric, exactly 2                | `11`-`99`; first digit = part n, second = total m                                                                                                                     | (1) Blank. (2) First digit greater than second digit.                                                                                                                                                                                                                                                                                                                                            | p.28          | `[S_NJ_SEC_X]Course_Sequence_Code`; if blank `[S_NJ_CRS_X]Course_Sequence_Code`; if blank `11` (PS-X item 16)                                                                                                                                                          | `11` = 1 of 1; lecture `12` and lab `22` example (p.28). Whether a `0` digit is valid is not stated. PS-SCH names the section field `[S_NJ_SEC_X]Course_Sequence`.                                                                                                                                                                                                                                                                                                                                                         |
| 17  | LocalCourseTitle          | Mandatory: "mandatory for all courses."                                                                                                                                                                                                                                                                                                                                                                                                                               | Alphanumeric, 1-50                | Local, no statewide list                                                                                                                                              | (1) Blank.                                                                                                                                                                                                                                                                                                                                                                                       | p.29          | `[Courses]Course_Name` (PS-X item 19, len 50)                                                                                                                                                                                                                          | Leading `+ - @ =` stripped on upload (FAQ Q9.1). PS-DIST lists `Course_Name` length 40.                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| 18  | LocalCourseCode           | Mandatory: "mandatory for all courses."                                                                                                                                                                                                                                                                                                                                                                                                                               | Alphanumeric, 1-20                | Local                                                                                                                                                                 | (1) Blank.                                                                                                                                                                                                                                                                                                                                                                                       | p.30          | `[Courses]Course_Number` (PS-X item 20, len 15)                                                                                                                                                                                                                        | Part of the update key (FAQ Q1.14) and the staff-link key (FAQ Q5.1). PS-DIST lists `Course_Number` length 11.                                                                                                                                                                                                                                                                                                                                                                                                             |
| 19  | LocalSectionCode          | Mandatory: "mandatory for all courses."                                                                                                                                                                                                                                                                                                                                                                                                                               | Alphanumeric, 1-20                | Local                                                                                                                                                                 | (1) Blank.                                                                                                                                                                                                                                                                                                                                                                                       | p.31          | `[Sections]SectionID` (PS-X item 21, len 10)                                                                                                                                                                                                                           | In-house: confirmed equal to PowerSchool `sections.id`; zero matches on `section_number` or `dcid` (SPEC). Part of the uniqueness, update, and staff-link keys (FAQ Q1.2, Q1.14, Q5.1).                                                                                                                                                                                                                                                                                                                                    |
| 20  | CreditsEarned             | Conditional: "This field is mandatory for all students in courses with Secondary course codes who are no longer active in the course and have been assigned a SectionExitDate. Otherwise, this field is not mandatory."                                                                                                                                                                                                                                               | Numeric with decimal point, 5-6   | `0.000`-`35.000`                                                                                                                                                      | (1) "An error will occur if the field is left blank." (2) Outside the acceptable range. (3) Not entered for students who have a SectionExitDate and a Secondary course code. (4) CreditsEarned greater than AvailableCredit.                                                                                                                                                                     | p.32          | `[StoredGrades]EarnedCrHrs`, format `xx.xxx`; with "Include Dropped Enrollments", dropped prior-to-secondary courses report blank (PS-X item 22)                                                                                                                       | Rule (1) contradicts the conditional requirement (section 6). Common-error fix: "includes three decimal places" (p.32). Rule (4) is undefined where AvailableCredit is blank (Prior to Secondary).                                                                                                                                                                                                                                                                                                                         |
| 21  | NumericGradeEarned        | Conditional (one of 21-23): "All students with a SectionExitDate entered for Secondary course codes with an available credit of greater than 0.000 must have either the NumericGradeEarned, AlphaGradeEarned, or CompletionStatus field filled in." Same for "Prior-to-secondary course codes with an grade span of 060X or higher". "NumericGradeEarned field is mandatory for the aforementioned students if AlphaGradeEarned and CompletionStatus are left blank." | Numeric, 1-3                      | `0`-`100`, whole number                                                                                                                                               | (1) Outside the acceptable range. (2) Not a whole number ("Round all decimals to the nearest whole number").                                                                                                                                                                                                                                                                                     | p.33-34       | `[StoredGrades]Grade` mapped through `[NJ_Grade_Scale_Mapping-Numeric]code000`-`code100` (PS-X item 23)                                                                                                                                                                | Not weighted; convert scales above 100 to a percentage (p.34). Value ranges "will not be expanded for the current collection" (p.34). No state grade scale (FAQ Q7.4).                                                                                                                                                                                                                                                                                                                                                     |
| 22  | AlphaGradeEarned          | Conditional (one of 21-23); same wording, "mandatory ... if NumericGradeEarned and CompletionStatus are left blank."                                                                                                                                                                                                                                                                                                                                                  | Character, 1-2                    | `A A+ A- B B+ B- C C+ C- D D+ D- E E+ E- F F+ F-` (18)                                                                                                                | (1) Not in the acceptable values.                                                                                                                                                                                                                                                                                                                                                                | p.35          | `[StoredGrades]Grade` mapped through `[NJ_Grade_Scale_Mapping-Alpha]code_a+`-`code_f-` (PS-X item 24)                                                                                                                                                                  | "E, E+ and E- refer to a grade and not 'Exempt'." (p.35) `P` is not in this domain.                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| 23  | CompletionStatus          | Conditional (one of 21-23); same wording, "mandatory ... if NumericGradeEarned and AlphaGradeEarned are left blank."                                                                                                                                                                                                                                                                                                                                                  | Alpha, 1-2                        | `P` Pass, `F` Fail, `W` Withdrawal, `I` Incomplete, `NG` No grade earned                                                                                              | (1) Not in the acceptable values.                                                                                                                                                                                                                                                                                                                                                                | p.36          | `[StoredGrades]Grade` mapped through `[NJ_Grade_Scale_Mapping-Comp]` `code_pass`, `code_fail`, `code_withdrawal`, `code_incomplete`, `code_ng` (PS-X item 25); dropped enrollments get the "Completion Status for Non-Graded Courses" report input (PS-X Report Input) | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          |
| 24  | CourseType                | Mandatory: "This field is mandatory for all students."                                                                                                                                                                                                                                                                                                                                                                                                                | Alphanumeric, 1-2                 | `S1` standard, single in-district teacher; `S2` standard, in-district co-teachers; `R` remote, attended off-site; `C` college dual enrollment/dual credit; `O` online | (1) `S1` or `S2` and the student has no staff member assigned to the course in the Staff Course Roster. (2) `S2` and the course does not have more than one staff member assigned.                                                                                                                                                                                                               | p.37-38       | Not in the PS-X output table. Setup pages list `[S_NJ_SEC_X]Course_Type` (section, "Used in: Student Course Roster", PS-SCH) and `[S_NJ_CRS_X]Course_Type` (course, PS-DIST)                                                                                           | Staff data required only for S1/S2. R/C/O taught by out-of-district staff: no staff record, and the student record "will not be placed into Out-of-Sync". If in-district staff teach an R/C/O section, report them with "the same course identifying elements". Same section "should typically have the same CourseType", except R/C/O students (p.37-38). SYS: an S1 rule was removed April 10, 2026 and "may be reintroduced in a revised form". No explicit blank or invalid-value error is listed despite "mandatory". |
| 25  | DualInstitution           | Conditional: "mandatory for student course records with a CourseType = C ... Otherwise, this field is not mandatory."                                                                                                                                                                                                                                                                                                                                                 | Numeric, exactly 8                | NJSLEDS OPE ID List                                                                                                                                                   | (1) CourseType = `C` and blank. (2) CourseType not `C` and populated. (3) OPE ID does not match a valid code on the OPE ID List.                                                                                                                                                                                                                                                                 | p.39          | `[S_NJ_CRS_X]Dual_Institution` (course level, PS-X item 17)                                                                                                                                                                                                            | Use only with an existing articulation agreement (p.39). OPE IDs carry leading zeros (e.g. `00100200`), so "Numeric" must still preserve them.                                                                                                                                                                                                                                                                                                                                                                             |

## 3. Cross-record rules

### Uniqueness and duplicates

- A Student Course Roster record is unique on: LocalIdentificationNumber,
  StateIdentificationNumber, FirstName, LastName, DateOfBirth,
  CountyCodeAssigned, DistrictCodeAssigned, SchoolCodeAssigned,
  SectionEntryDate, SectionExitDate, SubjectArea, CourseIdentifier, GradeSpan,
  LocalSectionCode. "These fields collectively define one student in one section
  during one time period." (FAQ Q1.2)
- Two or more rows in the same file, same district, identical on all of those
  fields are flagged Duplicate. "The system does not merge or choose between
  records. The district must remove or correct the duplicate row before
  processing can continue." (FAQ Q1.3)
- Handbook common error under LID: "Duplicate student record with the same
  information exists in the LEA"; resolution "upload a new file with each course
  record listed once for each student." (HB p.11)
- The grain is one row per student per section per continuous enrollment period,
  not one per student-section: "If a student enters a course sections, exits,
  and later re-enters the same course section within the School Year, submit
  multiple records to reflect each enrollment period." (HB p.20, p.22)

### Update (overwrite) key across uploads

- A re-upload overwrites an existing record only if all of these match:
  StateIdentificationNumber, CountyCodeAssigned, DistrictCodeAssigned,
  SchoolCodeAssigned, SectionEntryDate, SubjectArea, CourseIdentifier,
  LocalCourseCode, LocalSectionCode. Any change "will create a new Course Roster
  record". (FAQ Q1.14)
- "Because NJSLEDS is a target system, changing key course roster information
  may result in an additional record being created rather than updating the
  existing record." Records submitted in error need a delete request (HB
  p.20-21). Delete requests go through the in-system Help Desk (FAQ contact
  section).
- SYS (May 15, 2026) removed GradeSpan and AvailableCredit from the Staff Course
  Roster overwrite key only; FAQ Q1.14's student key never included them.

### Linkage to Student Management (Out of Sync)

- SID, FirstName, LastName, DateOfBirth must exactly match Student Management
  (HB pp.12-15); the combination must match the Snapshot, and the Snapshot
  record must be free of Error, Sync, Transfer Requests, and Unresolved (HB
  p.12).
- CDS must match Student Management by enrollment type (HB pp.16-18): Attending
  CDS for non-shared-time and for shared-time vocational (Enrollment Type = S
  and Reported Shared Vocational = Y); Resident CDS for all other shared-time.
  FAQ Q1.4 states the same in terms of ReportedSharedVoc = Y (attending) or N
  (resident).
- Also check "that the student is active (DistrictStatus = A and SchoolStatus =
  A)" (FAQ Q1.5).
- "Out of Sync" also covers "a required student is missing from your course
  roster file" (FAQ Q1.4); "Student missing from the Student Course Roster file"
  is a listed cause (FAQ Q1.5).
- SYS (April 13, 2026): Out of Sync previously "only checked current
  enrollment"; logic now "account[s] for mid-year student movement."

### Linkage to the Staff Course Roster

- "The Course Identifier elements are nine data elements combined to form your
  unique course identification. All nine of these elements must match exactly
  between the staff record and student record to successfully link a staff
  member and student to one course. The nine elements are Subject Area, Course
  Identifier, Course Level, Course Sequence, Local Course Code, Local Section
  Code, County Code Assigned, District Code Assigned, and School Code Assigned."
  (FAQ Q5.1)
- The student file carries no teacher identifier. The SMID lives only on the
  staff file and is checked against Staff Management (FAQ Q1.8); the student to
  teacher link is the nine elements above.
- CourseType `S1`/`S2` requires a linked staff record; `S2` requires more than
  one (HB p.37). `R`/`C`/`O` with out-of-district staff need none (HB p.37).
  In-district staff teaching a `C` section are reported "with the same course
  identifying elements to link the student and staff member" (HB p.38).
- Staff side, for context: report teachers and co-teachers "100% responsible"
  for the section roster (FAQ Q1.10); teacher on leave and permanent sub are
  both reported (FAQ Q4.1); long-term subs (20+ consecutive days) are reported
  (FAQ Q4.2).

### Section-level consistency

- "Students within the same course section should typically have the same
  CourseType. Please note that some students may have exceptions (R, C, O) which
  would be reported differently than other students in the same course section."
  (HB p.38)
- CDS "should reflect the accurate ... Code for the specific course section" (HB
  pp.16-18).
- No handbook sentence requires every row of a section to carry the same course
  code or credit. That consistency follows only from FAQ Q5.1 (the nine link
  elements must match the section's staff record); AvailableCredit, GradeSpan,
  and LocalCourseTitle are not among the nine. This is an inference, flagged as
  such.

### Within-row cross-field rules (collected from section 2)

- SCED level drives credit: Prior to Secondary codes for courses without
  Available Credit; Secondary codes for Available Credit greater than 0.000 (HB
  p.23-24). FAQ Q6.1: "If the student is earning credit applicable to a high
  school diploma through the course, a code from the Secondary list must be
  selected. Courses designated with a Prior to Secondary Grade Span should not
  be reported using Secondary course codes." A Secondary course may carry zero
  credit (FAQ Q6.1 note).
- GradeSpan required when the SCED code is Prior to Secondary (HB p.26).
- AvailableCredit required when the SCED code is Secondary (HB p.27).
- CreditsEarned required when the code is Secondary and SectionExitDate is
  present; CreditsEarned ≤ AvailableCredit (HB p.32).
- At least one of NumericGradeEarned, AlphaGradeEarned, CompletionStatus when
  SectionExitDate is present and either (a) Secondary code with AvailableCredit
  > 0.000 or (b) Prior to Secondary code with GradeSpan "060X or higher" (HB
  > p.33-36).
- SectionEntryDate ≤ SectionExitDate; both in the current school year;
  SectionExitDate ≤ file submission date (HB p.20, p.22).
- CourseType `C` if and only if DualInstitution is populated (HB p.39).
- Guidance, not validation: Secondary SCED codes for grades 9-12, Prior to
  Secondary for PK-8 (SPR p.1); structured learning experiences use Workplace
  Experience codes ending in 48 or 98 (SPR p.1-2, FAQ Q6.5); AP/IB courses use
  their own SCED codes (FAQ Q6.2, SPR p.2); self-contained K-5 uses subject area
  73 (FAQ Q6.3); Prior to Secondary Algebra 1 is `52`/`052` (FAQ Q6.4).
- mSGP inclusion (FAQ Q8.2): subject area 51, 52, or 73; LA grades 4-8 and Math
  grades 4-7; teacher of record present 60% of the course before the state
  assessment; at least 20 students with SGPs enrolled 70% of the year.

## 4. PowerSchool-side rules

### Record selection (PS-X "Student Selection")

All must hold for a row to extract:

1. "The school must not be excluded from state reporting." (field
   `[Schools]State_ExcludeFromReporting`, PS-DIST)
2. "The student must not be excluded from state reporting."
3. "The student must be included in NJ SLEDS Student Course Report." (PS-SID
   shows an "Include in NJSLEDS Extracts" Yes/No with no table.field given)
4. "The student was enrolled at any time between the report start and end
   dates."
5. "The course must not be excluded from state reporting."
6. "The section must not be excluded from state reporting."
7. "The grade must not be excluded from state reporting."
8. "There should be a stored grade with a Store Code that is mapped using the NJ
   Final Grade Mapping."
9. "Dropped courses will be excluded for a student (based on CC table with
   negative TermID) unless a grade was issued and stored for that dropped
   course."
10. "The student must not be flagged as Non Public ([S_NJ_STU_X]NonPublic)."
11. "The student must have completed grades in grade level 6 or higher courses."

### Exclusion flags

- Course: "Exclude from Course Submission",
  `[S_NJ_CRS_X]Exclude_Course_Submission_TF`: "Select Yes (1) to exclude this
  course from the Course Roster reports." (PS-SCH, PS-DIST)
- Section: "Exclude from Course Roster Reports",
  `[S_NJ_SEC_X]Exclude_Course_Submission_TF`: "A value of 1 in this field
  indicates this Section is to be excluded. If left blank, the comparable
  exclusion field for the Course will be honored." (PS-SCH)
- PS-X item 18 "Exclude Course Roster": "The report excludes the Course
  enrollments if ExcludeCourseRoster_YN is set 'Yes'." (field name differs from
  the setup pages; see section 6)

### Report inputs (PS-X "Report Input")

- Start Date and End Date for the reporting period.
- Grades filter (blank = all).
- Student Name to Print: Preferred Name or Legal Name (PS-X item 26).
- Include Dropped Enrollments (optional). When on, "Completion Status for
  Non-Graded Courses" (P, F, I, W, NG) is applied to dropped section
  enrollments; dropped records display "only if no grades were assigned for the
  courses taught in those sections." If the current and a prior dropped
  enrollment share a section ID, the current row carries all elements except
  Completion Status, and the dropped rows carry their own entry/exit dates and
  the selected Completion Status.

### How SectionEntryDate and SectionExitDate are derived

- Entry: `[S_NJ_SGR_X]Section_Start_Date`; if no stored grade,
  `[CC]DateEnrolled`. Exit: `[S_NJ_SGR_X]Section_End_Date`; if no stored grade,
  `[CC]DateLeft`. (PS-X items 9-10)
- "If the student was assigned to the section on multiple occasions with
  differing dates, only the most recent assignment extracts." (PS-X items 9, 10)
- Term first and last day (`[Terms]FirstDay`, `[Terms]LastDay`) are listed as
  used by the Student Course Roster (PS-SCH); the spec does not say how.

### Grades and credits

- NJ Final Grade Mapping (PS-DIST): per school and term, the Store Code
  extracted as the final grade, plus a Completion Date ("the last in-session day
  of the term"). Stored in `[S_NJ_Final_Grade_Mapping_S]` (`schoolID`, `termID`,
  `storeCode` length 2, `completionDate`). Copied at EOY when a matching term
  exists; otherwise mapped by hand.
- Grade Scale Mapping (PS-DIST): "This mapping is used in and must be completed
  prior to running Staff Course Roster and Student Course Roster reports." One
  mapping per Grade Scale Type per Grade Scale; exact matches to state values
  need no mapping; a mark with two meanings (F as pass/fail fail vs letter F)
  "cannot be mapped to two different values."
- Grades extract for Prior to Secondary codes only when the span is "060x and
  higher" (PS-X items 23-25), so PowerSchool leaves grade fields blank on Prior
  to Secondary rows below that span.
- PS-X items 23 and 25 describe Numeric and Completion Status as "mandatory for
  secondary course codes" without the handbook's AvailableCredit > 0.000
  condition.

### Section and course NJ fields that feed the file

| Field                  | Course table (`S_NJ_CRS_X`)                                                                             | Section override (`S_NJ_SEC_X`)                                    | Source          |
| ---------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------ | --------------- |
| SubjectArea            | `NCES_Subject_Area`                                                                                     | `NCES_Subject_Area`                                                | PS-SCH, PS-DIST |
| CourseIdentifier       | `NCES_Course_ID`                                                                                        | `NCES_Course_ID`                                                   | PS-SCH, PS-DIST |
| CourseLevel            | `Course_Level`                                                                                          | `Course_Level`                                                     | PS-SCH, PS-DIST |
| GradeSpan              | `Course_Span`                                                                                           | `Course_Span`                                                      | PS-SCH, PS-DIST |
| CourseSequence         | `Course_Sequence_Code`                                                                                  | `Course_Sequence` (PS-SCH) / `Course_Sequence_Code` (PS-X)         | PS-SCH, PS-X    |
| CourseType             | `Course_Type`                                                                                           | `Course_Type`                                                      | PS-SCH, PS-DIST |
| DualInstitution        | `Dual_Institution`                                                                                      | none                                                               | PS-DIST         |
| AvailableCredit        | `[Courses]Credit_Hours`                                                                                 | none                                                               | PS-X item 15    |
| County/District/School | none for this report (course-level `County/District/School_Code_Override` are for the CTE extract only) | `CountyCodeAssigned`, `DistrictCodeAssigned`, `SchoolCodeAssigned` | PS-SCH, PS-DIST |
| Exclude                | `Exclude_Course_Submission_TF`                                                                          | `Exclude_Course_Submission_TF`                                     | PS-SCH, PS-DIST |
| Block schedule         | `Block_Schedule_Session`                                                                                | `Block_Schedule_Session`                                           | PS-SCH, PS-DIST |

School setup that feeds CDS fallbacks (PS-DIST): `[Schools]School_Number`
("state assigned. Format ####"), `[Schools]Alternate_School_Number` ("3 (Numeric
only)"; for a charter with multiple buildings, "use this field to store the
State Assigned school number to be reported"), `[Schools]CountyNbr` ("state
assigned. Format ##").

### Defects already observed in KTAF's native extract (in-house, SY2025-26)

Aggregates only, from SPEC, SUB, and RB:

- Grades: NumericGradeEarned, AlphaGradeEarned, and CompletionStatus empty on
  every row of the 2026-07-29 extract (43,493 rows: Newark 33,150, Camden
  10,343). (SPEC)
- CreditsEarned: populated on all 14,343 Secondary-code rows with one distinct
  value, `0.000`. (SPEC)
- Every row carried a SectionExitDate. (SPEC)
- Causes named: "customizations in the KTAF grading model, and mapping gaps in
  PowerSchool's NJ state-reporting configuration." (SPEC)
- After the in-house backfill from `storedgrades` `Y1`, 108 in-scope rows still
  had no grade and 50 Secondary rows had no CreditsEarned (SUB). Stored `Y1`
  letter grades were all within the 18-value domain; `earnedcrhrs` never
  exceeded AvailableCredit (SPEC). The live-grades fallback carried `F*`, `P`,
  and `I` values that are not legal AlphaGradeEarned (SPEC).
- CDS: 20,652 of 43,493 rows carried a bad County or School code, including
  every Camden row. Observed combos: Newark `80/7325/965` correct; Newark blank
  county with school `732`; Newark `80/7325/732`; Camden blank county with
  `1799/179`; Camden `07/1799/179`. Root cause given: unset Alternate School
  Number (3 Newark, 5 Camden schools), falling back to the internal school
  number. (SPEC, RB "Setup-level fixes")
- GradeSpan: staff extract carried 3-character spans `202`, `303`, `404`
  (leading zero lost). (RB check 10)
- Span coverage observed: `0606`, `0707`, `0808`, `0508`, `KG08`, `0505`,
  `0404`, `0303`, `0202`, `0101`, `KGKG` (SPEC). So the extract did emit rows
  for spans below grade 6, despite selection rule 11 above.
- Identity: 12 Newark-sample students mismatched the state record (fewer than 10
  last name, fewer than 10 DOB, fewer than 10 first name); fewer than 10
  students lacked a valid SID (RB checks 11-12, "State-ID population").
- Sections: 13 staff-only orphan sections in the Newark sample; 0 student-only
  (RB checks 14-16).
- Dual enrollment: CourseType was always `S1` or `C`; every `C` row had an
  8-digit DualInstitution (RB "Dual-enrollment").
- The extract was one row per (LocalIdentificationNumber, LocalSectionCode) with
  no duplicates (SPEC), consistent with PS-X emitting only the most recent
  assignment.
- 33 student local IDs are shared across Newark and Camden (SPEC), so LID is
  unique only within a district.

## 5. Code lists referenced

| List                                      | Where it comes from                                                                                                                          | Contents (as of the files on disk)                                                                                                                                                                                                                                                                                                                                                                    |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| County District School codes              | NJSLEDS County District School Code List, Key Documents page (HB pp.16-18). Copy in `code-lookups/NJSLEDS_County-District-School-Codes.xlsx` | TPL-A Lists tab: County 51 values (`01`-`42`, `80`, `CT DE MA MD NC NH NY PA`); District 2,069 four-character codes; School 1,413 three-character codes (some alphanumeric, e.g. `99A`). Validation is "codes listed for your district" (HB p.16, p.18), not the full list. KTAF values per RB: Newark `80`/`7325`/`965`, Camden `07`/`1799`/`111` (Camden school code flagged "to confirm" in SPEC). |
| SCED subject areas and course identifiers | NJSLEDS SCED Course Codes document, Key Documents page (HB p.23-24)                                                                          | SCED (Feb 2026): 607 Prior to Secondary pairs in subject areas 51-58, 60-73, 75; 1,462 Secondary pairs in 01-05, 07-22, 24, 25. Columns include AP or IB Course, Corresponding AP/IB Exam, SPR Course Participation table and subject, SLE flag, NJDOE Guidance. An Updates tab and an Archived tab exist. TPL-A SCED tab: 44 subject areas (01-05, 07-22, 24, 51-58, 60-73), 2,170 pairs.            |
| SCED level split                          | HB p.23; PS-X item 11; PS-DIST                                                                                                               | PS-X: Secondary 01-22, Prior to Secondary 51-73. PS-DIST: Secondary 01-24. SCED file: Secondary also has 25, Prior also has 75.                                                                                                                                                                                                                                                                       |
| CourseLevel                               | HB p.25                                                                                                                                      | `B G E H X` (TPL-A matches)                                                                                                                                                                                                                                                                                                                                                                           |
| GradeSpan tokens                          | HB p.26                                                                                                                                      | `PK`, `KG`, `01`-`12`, two per value; PS-SCH examples `PKPK`, `0103`                                                                                                                                                                                                                                                                                                                                  |
| CourseSequence                            | HB p.28                                                                                                                                      | `11`-`99`, first digit ≤ second. TPL-A dropdown is every integer 11-99 (89 values)                                                                                                                                                                                                                                                                                                                    |
| AlphaGradeEarned                          | HB p.35                                                                                                                                      | 18 values; TPL-A matches (`AlphaGradeNew`, Lists E2:E19)                                                                                                                                                                                                                                                                                                                                              |
| CompletionStatus                          | HB p.36                                                                                                                                      | `P F W I NG`; TPL-A matches                                                                                                                                                                                                                                                                                                                                                                           |
| CourseType                                | HB p.37                                                                                                                                      | `S1 S2 R C O`; TPL-A matches                                                                                                                                                                                                                                                                                                                                                                          |
| OPE ID                                    | NJSLEDS OPE ID List, Key Documents page (HB p.39)                                                                                            | OPE: New Jersey tab 176 eight-character IDs; Out of State tab 6,950. TPL-A Lists H: 7,207 entries, 7,160 distinct, one 6-character entry (`666800`).                                                                                                                                                                                                                                                  |
| Local course codes, titles, section codes | none                                                                                                                                         | "There is no state-wide standardized list" (HB pp.29-31)                                                                                                                                                                                                                                                                                                                                              |
| Credit type                               | none                                                                                                                                         | The Student Course Roster has no credit-type element. Credit appears only as AvailableCredit and CreditsEarned (`0.000`-`35.000`).                                                                                                                                                                                                                                                                    |
| Student grade level                       | none in this file                                                                                                                            | Taken from Student Management by SID for reports (UG p.2). Adult `A1`/`A2` excluded from the Course Summary report (UG p.2).                                                                                                                                                                                                                                                                          |

## 6. Open questions and disagreements

1. **Re-enrollment collapse.** HB p.20 and p.22 require one record per
   continuous enrollment period; PS-X items 9-10 say "only the most recent
   assignment extracts." A student who exits and re-enters a section loses the
   earlier period(s) in the native extract.
2. **CourseType has no documented extract source.** It is element 24 and
   mandatory (HB p.37), but PS-X's output table (items 1-26) omits it. PS-SCH
   and PS-DIST list section and course `Course_Type` fields; precedence is not
   stated. Separately, SYS says an S1 validation rule was removed April 10, 2026
   and "may be reintroduced", while HB v1.4 (July 2026) still lists the S1/S2
   staff-assignment error. Which S1 rule was removed is not stated.
3. **Conditional fields with unconditional blank errors.** SectionExitDate (HB
   p.22) and CreditsEarned (HB p.32) are described as conditionally required,
   yet each lists "An error will occur if this field is left blank." For
   CreditsEarned this matters on Prior to Secondary rows (blank allowed by the
   required text, an error by the validation text).
4. **"060X and higher" and below-grade-6 rows.** HB p.33-36 does not say which
   end of the span is tested (SPEC chose the start; 219 rows differ). PS-X
   selection rule 11 ("must have completed grades in grade level 6 or higher
   courses") reads as excluding lower-grade rows, but the in-house extract
   contained 14,766 rows with spans starting below `06`, and UG p.4 says the
   submission covers all grades. Also unstated: whether grades are permitted,
   expected, or must be blank outside the required populations (SPEC
   "Contingencies").
5. **SCED validation basis.** TPL-A's SCED tab (Aug 29, 2025) disagrees with the
   SCED file (Feb 2026): 150 template pairs are not on the SCED list, 49
   SCED-list pairs are missing from the template (13 of them subject area 25, 1
   subject area 75), and the template's SubjectArea dropdown lacks 25 and 75. HB
   p.24 says only "not a valid SCED Course Identifier code" and does not say
   whether the subject and identifier are validated as a pair; UG p.1 says
   unlisted combinations are left out of the Course Summary report, which
   implies they can load. PS-X and PS-DIST disagree on the Secondary range
   (01-22 vs 01-24).
6. **Runbook check 9 is stricter than the handbook.** RB check 9 flags Secondary
   rows with AvailableCredit 0 and Secondary rows with GradeSpan populated. HB
   p.27 allows `0.000` ("does not carry any credits"), FAQ Q6.1 allows
   zero-credit Secondary courses, and SYS (May 15, 2026) allows GradeSpan either
   way on Secondary codes.
7. **DistrictCodeAssigned fallback.** PS-X item 7 falls back to
   `[Gen]Cat=districts [Gen]Value`, which PS-DIST describes as the Districts of
   Residence table; PS-SCH says a blank override extracts the District Info page
   value (`[Prefs]districtnumber`). In-house data showed the district code
   correct, so the effective source is unconfirmed.
8. **Exclusion flag name.** Setup pages use `Exclude_Course_Submission_TF`
   (course and section); PS-X item 18 names `ExcludeCourseRoster_YN`.
9. **SY2025-26 close date.** CAL displays "August 5, 2026" with
   `datetime="2026-08-03"`; UG p.1 says "August 3 deadline." The SY2026-27 close
   (August 3, 2027) is consistent in text and markup.
10. **Template quirks (not rules).** TPL-A data-validation error text for
    AvailableCredit and CreditsEarned says "between 0.000 and 20.000" while the
    bounds are 0-35 and the prompt says 35.000. Four header names carry a
    trailing space. The CourseIdentifier dropdown is the union of all 548
    identifiers, though its prompt says it is filtered by subject area. Several
    defined names (Counties, Districts, Schools, AlphaGradeCode) point at
    truncated ranges; the active validations use the full ranges. The
    DualInstitution list has one 6-character entry, and 46 of its values appear
    more than once (7,207 entries, 7,160 distinct).
11. **Required text garbled.** HB p.16 CountyCodeAssigned "Is this Data Element
    Required?" pastes the definition into the sentence; treated as Mandatory. HB
    p.12 SID says "mandatory for students" (drops "all").
12. **Grade one-of not listed as a validation check.** The "at least one of the
    three grade fields" rule appears only under "Is this Data Element Required?"
    (HB p.34-36), not in any Validation Checks list. Whether the validator
    enforces it as an error is not stated.
13. **Ordering and digit rules not stated.** GradeSpan start ≤ end, and whether
    CourseSequence may contain a `0` digit, are not stated (HB p.26, p.28).
14. **Name type vs content.** FirstName and LastName are typed "Alpha" (HB
    p.13-14), yet LastName notes allow spaces and hyphens and FirstName allows
    apostrophes. PS-X can emit the preferred name ("Student Name to Print"),
    which would fail the exact-match rule against Student Management.
15. **Length mismatches in PowerSchool.** LocalCourseCode: handbook 1-20, PS-X
    15, PS-DIST 11. LocalCourseTitle: handbook 1-50, PS-X 50, PS-DIST 40.
    LocalSectionCode: handbook 1-20, PS-X 10 (internal `sections.id`). None
    exceed the handbook maximum; PowerSchool's truncation behavior, if any, is
    not documented.
16. **CDS per section vs per student.** CDS "should reflect the accurate ...
    Code for the specific course section" (HB pp.16-18), but must also match the
    student's Student Management Attending (or Resident) CDS. A student whose
    section sits at a school other than their Student Management school can
    satisfy only one. SYS (April 13, 2026) changed Out of Sync to account for
    mid-year movement but gives no rule.
17. **Out-of-district students.** FAQ Q1.10 says to report students attending
    the district who are not its Student Management responsibility; how Out of
    Sync treats them is not stated beyond their appearing on the Out of District
    Records page.
18. **AvailableCredit is course-level only in PowerSchool.** FAQ Q7.3 allows
    splitting credit across sequence parts (`12`/`22`), but PS-X sources
    AvailableCredit from `[Courses]Credit_Hours` with no section override, so a
    split needs separate courses.
19. **File encoding, quoting, line endings.** Not specified by NJDOE or PS-X.
    SUB notes the native extract appears to carry a UTF-8 BOM and the in-house
    export does not; unverified against the upload portal.
20. **"Include in NJ SLEDS Student Course Report".** PS-X selection rule 3 names
    this flag; PS-SID shows "Include in NJSLEDS Extracts" (Yes/No) with no
    table.field, so the controlling field is unconfirmed.
