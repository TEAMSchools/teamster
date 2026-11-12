# NJ SLEDS Staff Course Roster: field and validation catalog

Extracted 2026-10-20 for dbt test design. Facts only, each with its source and
page. Where sources disagree or are silent, the item is listed in section 6, not
resolved here.

## Sources and citation keys

| Key                                | Document                                                                         | Version / date                                                                                     |
| ---------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| **SCR**                            | NJDOE Staff Course Roster Submission Handbook (27 pp)                            | Version 1.1, May 2026 (rev. May 15, 2026), cover p.1, history p.4. The cover names no school year. |
| **SM**                             | NJDOE 2026-2027 Staff Management Data Handbook (75 pp)                           | Version 1.5, August 2026 (cover p.1, history p.5)                                                  |
| **StCR**                           | NJDOE Student Course Roster Submission Handbook                                  | Version 1.4, July 28, 2026 (history p.5)                                                           |
| **FAQ-CR**                         | NJSLEDS "Staff and Student Course Roster" FAQs (web page)                        | "Last updated: July 24, 2026"; page footer 09/10/2026                                              |
| **FAQ-SM**                         | NJSLEDS Staff Management FAQs (web page)                                         | "Last updated: September 10, 2026"                                                                 |
| **FAQ-GEN**                        | NJSLEDS General Access and System Use FAQs (web page)                            | page footer 09/10/2026                                                                             |
| **RR**                             | Staff Management Reporting Responsibilities (PDF)                                | "Last Updated: July 2026"                                                                          |
| **SMID-G**                         | How to Report a Staff Member Without a State ID (SMID) (PDF)                     | undated, 2 pp                                                                                      |
| **RPT**                            | User Guide to NJSLEDS Course Roster Reports (PDF)                                | "Last Updated: May 2026" (resources page lists Jul 16, 2026)                                       |
| **SPR**                            | School Performance Reports: Course Roster Guidance (PDF)                         | "Last Updated: March 2026"                                                                         |
| **NUT**                            | NJSLEDS Orientation Guide / New User Toolkit (PDF)                               | "Last Updated: August 2026"                                                                        |
| **CAL**                            | NJSLEDS Submission Calendar (web page)                                           | page footer 10/02/2026; "Download PDF (updated 8/3/26)"                                            |
| **RES**                            | Staff and Student Course Roster User Resources (web page)                        | page footer 09/09/2026                                                                             |
| **TPL-A / TPL-B**                  | `NJSLEDS_Staff-Course-Roster_Template-A.xlsx` / `-Template-B.xlsx`               | RES lists both as updated Aug 29, 2025                                                             |
| **JC**                             | `Job Codes and Job Code Subcategories.xlsx`                                      | latest Updates row 2026-07-17                                                                      |
| **SCED**                           | `NJSLEDS_SCED-Course-Codes.xlsx`                                                 | "Updated: February 2026"                                                                           |
| **PS-SCR**                         | PowerSchool "NJ SLEDS Staff Course Roster Extract" doc (item # = output item)    | no version on page                                                                                 |
| **PS-STAFF / PS-SCHOOL / PS-DIST** | PowerSchool NJ Staff Setup / School Setup / District Setup docs                  | —                                                                                                  |
| **PS-StCR**                        | PowerSchool "NJ SLEDS Student Course Roster Extract" doc                         | —                                                                                                  |
| **PS-RN**                          | PowerSchool State Reporting release notes 26.4.1.0, 26.4.3.0, 26.5.2.0, 26.9.3.0 | —                                                                                                  |

The `NJSLEDS_Submission-Timeline_2627.pdf` text extraction came back empty (one
line), so submission dates below come from CAL.

---

## 1. Submission facts

### Window

| Event                                                                                                | Date                          | Source |
| ---------------------------------------------------------------------------------------------------- | ----------------------------- | ------ |
| SY2025-26 official period opens / closes                                                             | July 2, 2026 / August 5, 2026 | CAL    |
| Staff Management EOY submission opens (SY2026-27)                                                    | October 19, 2026              | CAL    |
| **SY2026-27 practice period opens**                                                                  | **April 1, 2027**             | CAL    |
| SY2026-27 practice period closes; Staff Management EOY submission closes; "2026-27 School Year Ends" | June 30, 2027                 | CAL    |
| **SY2026-27 official period opens**                                                                  | **July 2, 2027**              | CAL    |
| **SY2026-27 official period closes**                                                                 | **August 3, 2027**            | CAL    |

- "During the official Course Roster Submission window (July through August),
  Student Management end-of-year snapshot data is used. During the practice
  period (April through June), current Student Management records are used."
  (RPT p.3). Reports refresh nightly during both periods (RPT p.3).
- "LEAs submit course roster data once a year in NJSLEDS during the end-of-year
  submission period." Practice period starts in April (SPR p.1).
- The Course Roster submission is two submissions, Staff Course Roster and
  Student Course Roster (RPT p.1). SCR must be used "in conjunction with the
  Student Course Roster Submission Handbook for a complete Course Roster
  Submission" (SCR p.3).

### Who is in scope

| Population                                                   | What the sources say                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Rule for every row                                           | "Only the staff member responsible for 100% of the roster should be reported." Repeated in the Additional Notes of LSID, SMID, FirstName, LastName, SectionEntryDate, SectionExitDate (SCR pp.9-12, 17-18); DateOfBirth says "100% of the course roster" (p.13).                                                                                                                                                                                                                                         |
| Teachers and co-teachers                                     | "Report the teachers and co-teachers who are 100% responsible for the course section's roster and assigned to your district. A district must submit staff information for teachers that carry responsibility for 100% of the students on the district's rosters. Thus, lead teachers and co-teachers will be included in your Course Roster submission." (FAQ-CR Q1.10). Courses collected include "Standard courses taught by a single teacher or co-teachers assigned to your district" (FAQ-CR Q2.1). |
| Teacher of record                                            | The term appears only in mSGP context: entry/exit dates "determine the time in course for the teacher of record" (SCR pp.17-18); mSGP requires "The teacher of record is present for 60% of the course prior to the state assessment" (FAQ-CR Q8.2). The file has no role or teacher-of-record field.                                                                                                                                                                                                    |
| Inclusion / service teachers serving a subset                | "Districts are not required to report service rosters (commonly defined as rosters in which a subset of the section is receiving specialized services, i.e., an inclusion teacher working with small group of students)." Districts that report them create "a separate course section ... with a different local section number" holding only the served subset, assigned to the inclusion teacher; the full section is assigned "only to Teacher A" (FAQ-CR Q1.11).                                    |
| Paraprofessionals                                            | **Not addressed** by any Course Roster source. They are Staff Management reportable (FAQ-SM Q13; job codes 9100/9101/9150/9151, 4004, 0754, 0759 in JC).                                                                                                                                                                                                                                                                                                                                                 |
| Teacher on leave + permanent sub                             | "The teacher on leave and the permanent sub should both be reported to the Course Roster Submission. Include the section exit date when reporting staff members who have exited a course section on temporary leave." (FAQ-CR Q4.1)                                                                                                                                                                                                                                                                      |
| Long-term substitutes                                        | "Yes, you are required to submit long-term substitutes to Course Roster. You may identify your long-term substitutes as any substitute that holds a certificate from the state and is replacing a regularly employed teacher for a period of twenty or more consecutive days." (FAQ-CR Q4.2)                                                                                                                                                                                                             |
| Short-term / per-diem substitutes                            | Not reported to Staff Management (RR scenario 8, p.3). If a course was taught only by a series of them, "report whichever staff member is most directly tied to this course. It may be whoever oversaw the curriculum/assignments, or it may be a department head or other administrator"; that person may then be mSGP-eligible (FAQ-CR Q4.3).                                                                                                                                                          |
| Substitutes in Staff Management                              | "If a substitute is certified by the state and works in your district in the same position for more than 20 days, you must submit them" (FAQ-SM Q18; RR scenario 5, p.2).                                                                                                                                                                                                                                                                                                                                |
| Part-time staff paid by lump sum                             | Reported to Staff Management with Purchased Services job codes; "If these staff members are teaching any course for longer than 20 days in your district, at any point during the school year, they should also be submitted to the Staff Course Roster Submission." (RR scenario 6, p.2)                                                                                                                                                                                                                |
| Staff not assigned to the district (remote, college, online) | "Staff course data is required only for student courses that have a CourseType of S1 or S2. If a course section has a CourseType of R, C, or O and the course is taught by a staff member not assigned to your district, do not report a staff record." If district staff teach it (e.g., in-district college course, CourseType C), report them "with the same course identifying elements to link the student and staff member." (StCR pp.37-38)                                                       |
| Contracted preschool providers                               | Preschool students at contracted provider locations are not reported to Course Roster (FAQ-CR Q1.10 note).                                                                                                                                                                                                                                                                                                                                                                                               |
| Entity scope                                                 | SSSDs submit Course Roster; APSSDs submit Staff Management only; ESCs and DCF submit nothing to Course Roster (FAQ-CR Q1.12-Q1.13).                                                                                                                                                                                                                                                                                                                                                                      |
| Courses in scope                                             | "all courses that appear on a student's transcript should be reported", including study hall and similar (SCED 72 / 22), AvailableCredit 0.000 when no grade (FAQ-CR Q2.3). "Each term or semester of a course must be reported separately if scheduled as separate sections." (FAQ-CR Q2.2). "the Course Roster submission should cover all courses in all grades and subject areas" (RPT p.4).                                                                                                         |

### File format

- Upload as ".CSV UTF-8" formatted to the submission template (FAQ-GEN Q12; NUT
  p.6 "Submit one CSV UTF-8 file in NJSLEDS"). PowerSchool produces "the comma
  delimited file" (PS-SCR Introduction).
- Template A "Includes lookup values", for building a file from scratch;
  Template B "Header row only", for exporting from a source system (RES).
- Column order = handbook element order, 19 columns (TPL-A, TPL-B, verified).
  Exact header strings in **both** templates; four carry a trailing space:
  `LocalStaffIdentifier, StaffMemberIdentifier, FirstName, LastName, DateOfBirth, CountyCodeAssigned, DistrictCodeAssigned, SchoolCodeAssigned, SectionEntryDate, SectionExitDate, "SubjectArea ", "CourseIdentifier ", "CourseLevel ", GradeSpan, AvailableCredit, "CourseSequence ", LocalCourseTitle, LocalCourseCode, LocalSectionCode`.
- Leading zeros must be kept in CDS, SubjectArea, CourseIdentifier (SCR
  pp.14-16, 20; RPT p.5: "If leading zeroes are not included in the submission
  files, schools or courses may not be included in the reports").
- Any field whose first character is `+ - @ =` has that character removed on
  upload, in all NJSLEDS submissions (FAQ-CR Q9.1).
- Fix order: "The Staff Management file should be re-uploaded first, followed by
  the Staff Course Roster." (FAQ-CR Q1.9)

---

## 2. Element table

19 elements. 16 are unconditionally mandatory; 3 are conditional
(SectionExitDate, GradeSpan, AvailableCredit). "SM" in a cell cites the Staff
Management handbook.

| #   | Element name                 | Required? (verbatim)                                                                                                             | Type / length                              | Domain                                                                                                                                                                                                                                                | Validation rules                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | SCR page | PowerSchool source                                                                                                                                                                                                             | Notes / ambiguity                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| --- | ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | LocalStaffIdentifier (LSID)  | "Yes. This field is mandatory for all staff members."                                                                            | Alphanumeric, min 1, max 20                | District-assigned staff code                                                                                                                                                                                                                          | • Error if blank.<br>• "An error occurs if more than one staff member in the district has the same LSID."<br>• Error if it "does not exactly match the value in Staff Management."<br>• Common error "Duplicate staff record with the same information already exists in the LEA": "upload a file with each course record listed once for each staff member."                                                                                                                                                                                 | 9        | `[S_NJ_USR_X]Local_Teacher_ID`; if blank `[Users]TeacherNumber` (Alpha-numeric, 20) (PS-SCR #1)                                                                                                                                | One of the five identity fields that must match the Staff Management Snapshot (SCR p.10). SM p.16: mandatory, 1-20; SM common error "Staff member with the same LSID exists in the LEA." PS-STAFF: "Leave this field blank to cause the teacher ID to extract."                                                                                                                                                                                                                                                                                                                                                               |
| 2   | StaffMemberIdentifier (SMID) | "Yes. This field is mandatory for all staff members."                                                                            | Numeric, min 8, max 8                      | NJSLEDS-issued 8-digit ID                                                                                                                                                                                                                             | • Error "when the value submitted is not exactly 8 digits."<br>• Error if blank.<br>• Error "when the Staff Member Identifier is not a valid number issued by NJSLEDS."<br>• Error if not an exact match to Staff Management.<br>• Common error: "Combination of LSID, SMID, First Name, Last Name, and Date of Birth does not match data submitted during the Staff Management submission." All five "must match exactly to the Staff Management Snapshot page, and the record on the Snapshot must be free of Error, Sync, and Unresolved." | 10       | `[S_NJ_USR_X]StaffMemberID` (PS lists Alpha-numeric, length N/A) (PS-SCR #2)                                                                                                                                                   | PS-STAFF: fewer than 8 digits entered are "padded with preceding zeroes during data entry." SM p.17: "districts must use the SMID on all staff-level data submitted to the NJDOE." SMID-G p.1: "Preserve all 8 digits exactly."                                                                                                                                                                                                                                                                                                                                                                                               |
| 3   | FirstName                    | "Yes. This field is mandatory for all staff members."                                                                            | Alpha, min 1, max 30                       | —                                                                                                                                                                                                                                                     | • Error if blank.<br>• Error "if this field contains any special characters except for apostrophes (') and hyphens (-). Periods are not accepted."<br>• Error if not an exact match to Staff Management.                                                                                                                                                                                                                                                                                                                                      | 11       | `[S_NJ_USR_X]SMART_First_name`; if blank `[Users]First_Name` (30) (PS-SCR #3)                                                                                                                                                  | First and last names are separate fields; "No nicknames or abbreviated names should be reported." SM p.21 warning: enter "Unknown", not "FNU", for an unknown first name. PS-STAFF also has a separate `[S_NJ_USR_X]FirstName` (length 11) on the NJS SMID tab (see section 6).                                                                                                                                                                                                                                                                                                                                               |
| 4   | LastName                     | "Yes. This field is mandatory for all staff members."                                                                            | Alpha, min 1, max 50                       | —                                                                                                                                                                                                                                                     | • Error if blank.<br>• Same special-character rule as FirstName; periods not accepted.<br>• Error if not an exact match to Staff Management.                                                                                                                                                                                                                                                                                                                                                                                                  | 12       | `[S_NJ_USR_X]SMART_Last_Name`; if blank `[Users]Last_Name` (50) (PS-SCR #4)                                                                                                                                                    | Multiple last names all go in this field; hyphen only if part of the legal name ("Smith-Jones"), otherwise a space ("Davis Smyth"). SM p.23 warning: "Unknown", not "LNU". PS-RN 26.4.3.0 (PSSR-429094) extended LastName length in the extract.                                                                                                                                                                                                                                                                                                                                                                              |
| 5   | DateOfBirth                  | "Yes. This field is mandatory for all staff members."                                                                            | Date, min 8, max 8, YYYYMMDD               | Valid date                                                                                                                                                                                                                                            | • Error if blank.<br>• Error if not YYYYMMDD; "Do not include any separators such as '/' or '-'."<br>• Error if not an exact match to Staff Management.                                                                                                                                                                                                                                                                                                                                                                                       | 13       | `[UsersCoreFields]DOB` (Date, 8) (PS-SCR #5)                                                                                                                                                                                   | SM p.27 (Staff Management side): date cannot be in the future; staff "cannot be older than 105 and cannot be younger than 14 years of age." PS-STAFF lists the NJ DOB field as `[S_NJ_USR_X]DateofBirth` (see section 6).                                                                                                                                                                                                                                                                                                                                                                                                     |
| 6   | CountyCodeAssigned           | "Yes. This field is mandatory for all staff members."                                                                            | Character, min 2, max 2                    | NJSLEDS County District School (CDS) Code List                                                                                                                                                                                                        | • Error if blank.<br>• Error if "the County Code submitted does not conform to the codes listed for your district in the CDS list."<br>• Error if leading zeros are missing ("03, not 3").<br>• Error "if this field does not exactly match one of the six CountyCodeAssigned values in Staff Management."                                                                                                                                                                                                                                    | 14       | `[S_NJ_SEC_X]CountyCodeAssigned`; if blank `[Schools]CountyNbr` (2) (PS-SCR #6)                                                                                                                                                | "should reflect the accurate County Code for the specific course section." Type changed to Character (SCR p.4, Feb 12, 2025 entry). FAQ-CR Q1.8 states the match as a county+district+school set (section 3).                                                                                                                                                                                                                                                                                                                                                                                                                 |
| 7   | DistrictCodeAssigned         | "Yes. This field is mandatory for all staff members."                                                                            | Character, min 4, max 4                    | CDS list                                                                                                                                                                                                                                              | • Error if blank.<br>• Error if "the District Code submitted does not match the Submitting District."<br>• Error if leading zeros are missing ("0010, not 10").<br>• Error if not an exact match to one of the six DistrictCodeAssigned values in Staff Management.                                                                                                                                                                                                                                                                           | 15       | `[S_NJ_SEC_X]DistrictCodeAssigned`; if blank `[Gen]Cat=districts [Gen]Value` (4) (PS-SCR #7)                                                                                                                                   | "should reflect the accurate District Code for the specific course section."                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 8   | SchoolCodeAssigned           | "Yes. This field is mandatory for all staff members."                                                                            | Character, min 3, max 3                    | CDS list                                                                                                                                                                                                                                              | • Error if blank.<br>• Error if not conforming to the CDS codes for your district; "It must match a valid County + District + School Code combination in CDS."<br>• Error if leading zeros are missing ("020, not 20").<br>• Error if not an exact match to one of the six SchoolCodeAssigned values in Staff Management.                                                                                                                                                                                                                     | 16       | `[S_NJ_SEC_X]SchoolCodeAssigned`; if blank, `[Sections]SchoolID` → `[Schools]Alternate_School_Number`, if blank `[Schools]School_Number` (3) (PS-SCR #8)                                                                       | "should reflect the accurate School Code for the specific course section." SM pp.65, 68: a staff member with more than six school assignments gets one Staff Management instance with SchoolCodeAssigned = "000" "to indicate additional assignments captured through Course Roster."                                                                                                                                                                                                                                                                                                                                         |
| 9   | SectionEntryDate             | "Yes. This field is mandatory for all staff members."                                                                            | Date, min 8, max 8, YYYYMMDD               | "The most recent date the staff member was assigned to the specific section of the course."                                                                                                                                                           | • Error if blank.<br>• Error "if the value does not meet the acceptable range of values."<br>• Error if not YYYYMMDD, no separators.<br>• Error "if the staff course entry date occurs after the staff course exit date."<br>• Error "if the SectionEntryDate does not occur in the current School Year."                                                                                                                                                                                                                                     | 17       | `[Terms]FirstDay`; "If Tracking records exist, `[NJ_Section_Teacher_Tracking]Start_Date`"; all assignments extracted (PS-SCR #9)                                                                                               | "should be the date the staff member started teaching a course section and should align with the local attendance roster." Re-entry: "submit multiple records to reflect each teaching period. Do not overwrite earlier exit/entry dates with the most recent entry date." Used in mSGP time-in-course. "Acceptable range" and "current School Year" bounds are not defined in SCR (section 6).                                                                                                                                                                                                                               |
| 10  | SectionExitDate              | "This field is mandatory for all staff who are no longer active in the course. Otherwise, this field is not mandatory."          | Date, min 8, max 8, YYYYMMDD               | "The date the staff member's assignment to the specific section ended."                                                                                                                                                                               | • "An error will occur if this field is left blank."<br>• Error if outside the acceptable range.<br>• Error if not YYYYMMDD.<br>• Error "if the staff course exit date occurs before the staff course entry date."<br>• Error if not in the current School Year.<br>• Error "if the SectionExitDate is later than the file submission date (for example, a future date)."                                                                                                                                                                     | 18       | `[Terms]LastDay`; "If Tracking records exist, `[NJ_Section_Teacher_Tracking]End_Date`." PS: "reflects the teacher's last day in the section, not the first day of non-assignment." PS field type Alpha-numeric, 8 (PS-SCR #10) | "should be the date the staff member stopped teaching a course section and should align with the local attendance roster." Same re-entry and mSGP notes as #9. Required wording conflicts with the blank-is-error check (section 6). PS-RN 26.4.3.0 fixed the SectionExitDate output format.                                                                                                                                                                                                                                                                                                                                  |
| 11  | SubjectArea                  | "Yes. This field is mandatory for all courses."                                                                                  | Numeric, min 2, max 2                      | SCED subject area per the NJSLEDS SCED Course Codes document                                                                                                                                                                                          | • Error if blank.<br>• Error "if the value is not a valid SCED Subject Area code."                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 19       | `[S_NJ_SEC_X]NCES_Subject_Area`; if blank `[S_NJ_CRS_X]NCES_Subject_Area` (2) (PS-SCR #11)                                                                                                                                     | "Prior-to-secondary course codes should be used for all courses that do not have Available Credit. Secondary course codes should be used for all courses that have an Available Credit of greater than 0.000." Subject Area 51, 52, or 73 staff "will be pulled to the Teacher median SGP District Summary Report." FAQ-CR Q6.1: Secondary list if the course earns credit toward a high school diploma; a high school course may carry a Secondary code with zero credit. Q6.3: self-contained K-5 → 73. Q6.4: Prior-to-Secondary Algebra 1 = 52 052. SPR p.1: secondary codes for grades 9-12, prior-to-secondary for PK-8. |
| 12  | CourseIdentifier             | "Yes. This field is mandatory for all courses."                                                                                  | Numeric, min 3, max 3                      | SCED course identifier within the subject area                                                                                                                                                                                                        | • Error if blank.<br>• Error "if the value is not a valid SCED Course Identifier code."<br>• Error if leading zeros are missing.                                                                                                                                                                                                                                                                                                                                                                                                              | 20       | `[S_NJ_SEC_X]NCES_Course_ID`; if blank `[S_NJ_CRS_X]NCES_Course_ID` (3) (PS-SCR #12)                                                                                                                                           | SCED code = SubjectArea + CourseIdentifier (CEDS mapping, SCR pp.19-20). RPT p.1: combinations not in the NJSLEDS SCED list are left out of the Course Summary report. AP/IB have their own SCEDs (FAQ-CR Q6.2); identifiers ending 48 or 98 = Structured Learning Experience (Q6.5). SCR p.20 typo: "Available Credit or greater than 0.000".                                                                                                                                                                                                                                                                                |
| 13  | CourseLevel                  | "Yes. This field is mandatory for all courses."                                                                                  | Alpha, min 1, max 1                        | B = Basic or remedial; G = General or regular; E = Enriched or advanced (no honors designation); H = Honors; X = No specified level of rigor                                                                                                          | • Error if blank.<br>• Error "if the value is not a valid SCED Course Level code."                                                                                                                                                                                                                                                                                                                                                                                                                                                            | 21       | `[S_NJ_SEC_X]Course_Level`; if blank `[S_NJ_CRS_X]Course_Level`; "Blank is not a valid value." (PS-SCR #13)                                                                                                                    | —                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| 14  | GradeSpan                    | "This field is mandatory for all prior-to-secondary courses. This field is not required for secondary courses and can be blank." | Alphanumeric, min 4, max 4                 | "4-character alphanumeric code with no decimals. Each grade level from PK through 12 is represented by a two-digit code, ranging from PK to 12; kindergarten is represented by the letters KG, and prekindergarten by the letters PK." Example: KG01. | • Error "if the field is left blank for a course with a Prior-To-Secondary course code."<br>• Error "if the value does not match the acceptable range of values."                                                                                                                                                                                                                                                                                                                                                                             | 22       | `[S_NJ_SEC_X]Course_Span`; if blank `[S_NJ_CRS_X]Course_Span`; "extracts as blank for Secondary course codes" (PS-SCR #14)                                                                                                     | v1.1 (May 15, 2026) added "can be blank for Secondary" (SCR p.4). FAQ-CR Q7.2: the span is the grades the course is meant for, not student membership (a 7th-grade class is 0707). PS examples: PKPK, 0103 (PS-SCHOOL). Ordering (first ≤ second) is not stated. Part of the record uniqueness key (FAQ-CR Q1.6).                                                                                                                                                                                                                                                                                                             |
| 15  | AvailableCredit              | "This field is mandatory for all secondary courses. This field is not required for prior-to-secondary courses and can be blank." | Numeric with a decimal point, min 5, max 6 | 0.000-35.000                                                                                                                                                                                                                                          | • Error "if this field is left blank for a course with a Secondary course code."<br>• Error "if the value does not match the acceptable range of values."                                                                                                                                                                                                                                                                                                                                                                                     | 23       | `[Courses]Credit_Hours` (course level only, no section override); blank for Prior-to-Secondary; "format xx.xxx including decimal point" (PS-SCR #15)                                                                           | "Decimal points rounded up to the nearest thousandths are accepted"; "0.000 means the course does not carry any credits." v1.1 added "can be blank for Prior to Secondary" (SCR p.4). FAQ-CR Q7.3: use the credit value already assigned by the district; a multipart course may split credit across sequences, and "The combined credit value across all sequences must equal the total course credit."                                                                                                                                                                                                                      |
| 16  | CourseSequence               | "Yes. This field is mandatory for all courses."                                                                                  | Numeric, min 2, max 2                      | 11-99, "part n of whole m"                                                                                                                                                                                                                            | • Error if blank.<br>• Error "if the value of the first digit is greater than the value of the second digit."                                                                                                                                                                                                                                                                                                                                                                                                                                 | 24       | `[S_NJ_SEC_X]Course_Sequence_Code`; if blank `[S_NJ_CRS_X]Course_Sequence_Code`; if blank, `11` (PS-SCR #16)                                                                                                                   | Single-part course = 11. Lecture + lab: lecture 12, lab 22. PS-SCHOOL names the section field `[S_NJ_SEC_X]Course_Sequence`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| 17  | LocalCourseTitle             | "Yes. This field is mandatory for all courses."                                                                                  | Alphanumeric, min 1, max 50                | District's local title                                                                                                                                                                                                                                | • Error if blank.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | 25       | `[Courses]Course_Name` (PS lists 50) (PS-SCR #17)                                                                                                                                                                              | No statewide list; "You do not need to change your local course title." PS-DIST lists `Course_Name` length 40.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| 18  | LocalCourseCode              | "Yes. This field is mandatory for all courses."                                                                                  | Alphanumeric, min 1, max 20                | District's local course code                                                                                                                                                                                                                          | • Error if blank.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | 26       | `[Courses]Course_Number` (PS lists 15) (PS-SCR #18)                                                                                                                                                                            | One of the nine staff-student linking elements and the update key (section 3). PS-DIST lists `Course_Number` length 11.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| 19  | LocalSectionCode             | "Yes. This field is mandatory for all courses."                                                                                  | Alphanumeric, min 1, max 20                | District's local section code                                                                                                                                                                                                                         | • Error "if the field is left blank."                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | 27       | `[Sections]SectionID` (PS lists 10) (PS-SCR #19)                                                                                                                                                                               | Linking, uniqueness, and update key. Which PowerSchool column `[Sections]SectionID` means is ambiguous (section 6).                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |

Template A also enforces (TPL-A data validations, `Staff Template A` sheet):
text length 1-20 (A, LSID), 8 (B, SMID), 1-30 (C), 1-50 (D), 8 (E, I, J), 4 (N,
GradeSpan), 1-50 (Q); list `CourseLevelCodeNew` (M); decimal 0-35 (O, with error
text "between 0.000 and 20.000"); lists from `Lists!A` (F), `Lists!B` (G),
`Lists!C` (H), `SCED!A` (K), `SCED!AU` (L), `Sheet1!A` (P). Columns R and S have
no length rule on data rows.

---

## 3. Cross-record rules

### 3.1 Number and type of staff per section

Everything the sources say that constrains staff count or role on one section:

1. **Responsibility test, per row.** "Only the staff member responsible for 100%
   of the roster should be reported." (SCR pp.9-13, 17-18). Singular wording.
2. **Co-teachers are in scope.** "Report the teachers and co-teachers who are
   100% responsible for the course section's roster ... lead teachers and
   co-teachers will be included" (FAQ-CR Q1.10). "Standard courses taught by a
   single teacher or co-teachers" (FAQ-CR Q2.1).
3. **Student CourseType ties to staff count** (StCR p.37):
   - S1 = "Standard course taught by a single teacher assigned to your
     district"; S2 = "Standard course taught by co-teachers assigned to your
     district".
   - "An error will occur if a student's course type is S1 or S2 and that
     student does not have a staff member assigned to the course in the Staff
     Course Roster submission."
   - "An error will occur if a value of S2 is entered for a student course that
     does not have more than one staff member assigned to the course."
   - No stated error for S1 on a section with two or more staff.
   - "Students within the same course section should typically have the same
     CourseType", except R/C/O exception students (StCR p.38).
4. **Partial-roster staff are optional and go on their own section.** An
   inclusion teacher serving a subset is not reported on the full section; a
   district that reports service rosters creates a separate section with a
   different local section number containing only the served students (FAQ-CR
   Q1.11).
5. **Leave and substitutes on the same section.** Teacher on leave and permanent
   sub both reported; the teacher on leave carries a SectionExitDate (FAQ-CR
   Q4.1). Long-term subs (certified, replacing a regular teacher 20+ consecutive
   days) are required (Q4.2). A section taught only by short-term subs is
   assigned to the staff member "most directly tied to this course" (Q4.3).
6. **mSGP attribution** uses subject areas 51, 52, 73 (SCR p.19); the teacher of
   record must be present for 60% of the course before the state assessment,
   with SGP scores for at least 20 students enrolled for at least 70% of the
   year (FAQ-CR Q8.2). ELA grades 4-8 and Math grades 4-7 only.

**What no source says** (checked: SCR, StCR, SM, FAQ-CR, FAQ-SM, RR, RPT, SPR):

- No maximum number of co-teachers or staff rows per section. The only count
  rule is S2 needing more than one staff member.
- No minimum beyond "at least one staff row" for S1/S2 student rows.
- No lead / co-teacher / role indicator in the staff file, and no rule that
  exactly one teacher of record exists per section.
- No rule on paraprofessionals or aides.
- No rule that a roster staff member must hold a teaching job code in Staff
  Management. FAQ-CR Q4.3 explicitly allows a department head or other
  administrator.
- The only other state mentions of "co-teaching" are in the Special Education
  handbook's environment-code guidance (pp.52, 55), not roster rules.

### 3.2 Staff Course Roster ↔ Staff Management

- **SMID must exist and be valid**: "not a valid number issued by NJSLEDS" is an
  error (SCR p.10).
- **Five-field identity match**: LSID, SMID, FirstName, LastName, DateOfBirth
  must each match Staff Management exactly (SCR pp.9-13), and as a combination
  must match the Staff Management Snapshot page; the Snapshot record "must be
  free of Error, Sync, and Unresolved" (SCR p.10). SPR p.1 repeats the
  SMID/name/DOB check.
- **Assignment location match** ("Out of Sync"): SMID must match exactly and the
  roster County/District/School "must match at least one of those six sets" of
  CountyCodeAssigned1-6 / DistrictCodeAssigned1-6 / SchoolCodeAssigned1-6
  (FAQ-CR Q1.8). SCR pp.14-16 state it per field ("one of the six ... values").
  Staff Management must list every school where the person has course
  responsibilities (FAQ-CR Q1.9).
- **Active status**: "Staff member not marked active in Staff Management" is a
  listed cause of Out of Sync (FAQ-CR Q1.9). But FAQ-SM Q21: "If an inactive
  staff member is still expected to be included in a later submission (such as
  Course Roster), the record must remain in NJSLEDS through the End-of-Year
  Snapshot."
- **DistrictCodeAssigned must equal the submitting district** (SCR p.15).
- **LSID unique within the district** (SCR p.9).
- **More than six schools**: Staff Management carries SchoolCodeAssigned = "000"
  in one instance; it "must not be used as a general placeholder or blank value"
  (SM pp.65, 68).
- **Staff Management dependencies used by the roster** (SM): Status A/I, and to
  inactivate, DistrictEmploymentExitDate, DistrictEmploymentExitReason, and
  EmploymentSeparationType are required (p.39). Repeating elements 1-6:
  County/District/SchoolCodeAssigned, FullTimeEquivalency, JobCode,
  JobCodeSubcategory, AgeGroupTaught, CredentialType, one set per role or
  location (p.65). FTE 0.01-1.00 in hundredths per assignment, and the six FTEs
  must sum to less than 2.00 (p.70). JobCode 4 digits from the JC list, leading
  zeros kept; 1486 only with subcategory 2 (pp.71-72). JobCodeSubcategory must
  be one allowed for that job code (p.72). AgeGroupTaught required when
  subcategory is 3, 4, or 5 (p.73).

### 3.3 Staff Course Roster ↔ Student Course Roster

- **Nine linking elements must match exactly** between staff and student
  records: SubjectArea, CourseIdentifier, CourseLevel, CourseSequence,
  LocalCourseCode, LocalSectionCode, CountyCodeAssigned, DistrictCodeAssigned,
  SchoolCodeAssigned (FAQ-CR Q5.1). GradeSpan, AvailableCredit, and
  LocalCourseTitle are not in this list.
- **Every S1/S2 student row needs at least one staff row** on the same course
  (StCR p.37). **S2 needs more than one** (StCR p.37).
- **R/C/O rows taught by non-district staff need no staff row**; such student
  rows "will not be placed into Out-of-Sync" (StCR p.37).
- **Staff row with no student rows**: no rule found in any source.

### 3.4 Record identity, duplicates, updates

- **Uniqueness key (staff)**: LSID, SMID, FirstName, LastName, DateOfBirth,
  CountyCodeAssigned, DistrictCodeAssigned, SchoolCodeAssigned,
  SectionEntryDate, SectionExitDate, SubjectArea, CourseIdentifier, GradeSpan,
  LocalSectionCode: "one teacher assigned to one section during one timeframe"
  (FAQ-CR Q1.6).
- **Duplicates**: rows identical on all uniqueness fields in one file are
  flagged Duplicate and must be removed or consolidated (FAQ-CR Q1.7; SCR p.9
  common error).
- **Update vs new record**: an upload overwrites an existing record only if
  SMID, CountyCodeAssigned, DistrictCodeAssigned, SchoolCodeAssigned,
  SectionEntryDate, SubjectArea, CourseIdentifier, LocalCourseCode, and
  LocalSectionCode all match; a change in any of them creates a new record
  (FAQ-CR Q1.14). StCR p.17 adds, for students: do not change SectionEntryDate
  unless the original was wrong, because "changing key course roster information
  may result in an additional record being created".

### 3.5 Dates

- Entry ≤ exit (SCR pp.17-18).
- Both dates in "the current School Year" (SCR pp.17-18).
- Exit not later than the file submission date (SCR p.18).
- Re-entry to the same section within the year produces separate records; do not
  overwrite earlier periods (SCR pp.17-18). PowerSchool extracts all such
  assignments (PS-SCR #9-10; PS-RN 26.4.1.0).
- Dates "should align with the local attendance roster" (SCR pp.17-18).
- **Not stated**: whether two records for the same staff member and section may
  overlap in time, and whether co-teachers' date ranges must cover the section's
  student dates.

### 3.6 Course-attribute consistency (within a row)

- Secondary SubjectArea (01-05, 07-22, 24, 25 in the SCED list) →
  AvailableCredit required; prior-to-secondary (51-58, 60-73, 75) → GradeSpan
  required (SCR pp.22-23).
- Available Credit > 0.000 → secondary code; no Available Credit → prior-to-
  secondary code (SCR pp.19-20). A secondary course may carry 0.000 (FAQ-CR
  Q6.1).
- CourseSequence first digit ≤ second digit (SCR p.24); credits across a
  sequence sum to the course total (FAQ-CR Q7.3).
- CDS codes "for the specific course section" (SCR pp.14-16), and a valid
  County + District + School combination in CDS (SCR p.16).

---

## 4. PowerSchool-side rules

### 4.1 Purpose and setup

- Purpose: "to provide data for all educators who are 100% responsible for the
  grades given to students throughout the entire school year" (PS-SCR
  Introduction). Note the wording differs from the state's "100% of the roster".
- Prerequisites (PS-SCR Report Setup):
  1. Staff page NJ fields, including SMID and LSID.
  2. NJ fields on Courses and Sections: NCES Subject Area, Course Identifier,
     Course Level.
  3. Grade Span on the Course for prior-to-secondary subject areas; a section
     value may override. "The report will extract the first non-blank value for
     the field looking first at Sections than at Courses."
  4. Course Sequence on Course and/or Section; "If no Course Sequence is
     designated, a value of 11 will extract."
  5. "Enter teacher and staff information in the Teacher-Section Lead and
     Teachers/Staff – Additional areas of the Sections page."
- Grade Scale Mapping "is used in and must be completed prior to running Staff
  Course Roster and Student Course Roster reports" (PS-DIST).

### 4.2 Which staff are selected

- "Teachers/Staff who are 100% Allocated to a section, in a Role that is not
  excluded, will be extracted." (PS-SCR Selection Criteria)
- Sections page (PS-SCHOOL): "Teacher – Section Lead" (`[Sections]Teacher`) and
  "Teachers/Staff – Additional" (`[SectionTeacher]TeacherID`): "Population the %
  Allocation. Teachers with 100% Allocation are extracted for the Staff Course
  Roster Report unless excluded by Role." Lead and additional staff are treated
  the same; the docs do not name the allocation column.
- **Role exclusion** (PS-DIST, District Setup > Teacher Role Mapping): "Roles
  that are defined in Roles Administration > Co-Teaching are displayed",
  `[NJ_Teacher_Role_Mapping]role_def_id_01` through `role_def_id_100`; "The
  `[NJ_Teacher_Role_Mapping]role_def_id_xx` field is linked to the
  `SectionTeacher.roleid`." "Exclude from Staff Course Roster Report: Select a
  value of No or Yes. A Yes value means teachers assigned to that role will not
  be extracted" (`[NJ_Teacher_Role_Mapping]exclude_in_state_reporting_01` ...).
  No default role IDs or default exclusions are documented; the role list is
  district-defined.
- **Exclusion flags**:
  - Staff: "Exclude from Course Roster Reports",
    `[S_NJ_SSF_X]Exclude_Course_Submission_TF`, "Select Yes (1) to exclude this
    staff member" (PS-STAFF).
  - Section: `[S_NJ_SEC_X]Exclude_Course_Submission_TF`, value 1 excludes; "If
    left blank, the comparable exclusion field for the Course will be honored"
    (PS-SCHOOL).
  - Course: `[S_NJ_CRS_X]Exclude_Course_Submission_TF`, "Select Yes (1) to
    exclude this course from the Course Roster reports" (PS-DIST, PS-SCHOOL).
  - `[S_NJ_USR_X]Excl_Frm_Smart_Stf_Submissn` ("Exclude from NJ Staff
    Submissions") is listed only for the "NJ SMART SMID Submission Staff
    Extract", not the roster (PS-STAFF).
- **Report inputs** (PS-SCR Report Input): Use (district-wide / current school);
  Records to Include (all / selected teachers); Grades ("based on the grade
  level specified for the Section"); Start Date / End Date: "Teachers of a
  section are included when the section term falls within the reporting date
  range. To run report for the entire school year, enter the day following the
  last in session day of school."

### 4.3 Date derivation

- SectionEntryDate = `[Terms]FirstDay`; "If Tracking records exist,
  `[NJ_Section_Teacher_Tracking]Start_Date`." SectionExitDate =
  `[Terms]LastDay`; if tracking records exist,
  `[NJ_Section_Teacher_Tracking]End_Date`. Exit "reflects the teacher's last day
  in the section, not the first day of non-assignment." Multiple assignments
  with differing dates: "all such assignments are extracted" (PS-SCR #9-10).
- PS-RN 26.4.1.0 (PSSR-423451, Staff version 1.7): "extract all staff section
  assignments instead of only the most recent, aligning with NJDOE 2025–26
  submission requirements."
- PS-RN 26.4.3.0 (PSSR-429094, Staff version 1.8): correct SectionExitDate
  format and extended LastName length.
- The docs do not mention `SectionTeacher.Start_Date` / `End_Date`.

### 4.4 Course and location derivation

- Section field overrides course field for SubjectArea, CourseIdentifier,
  CourseLevel, GradeSpan, CourseSequence (PS-SCR #11-16). AvailableCredit,
  LocalCourseTitle, LocalCourseCode have no section override (`[Courses]`);
  LocalSectionCode is `[Sections]SectionID` (PS-SCR #15, 17-19).
- CDS: `[S_NJ_SEC_X]` overrides, then school/district defaults (PS-SCR #6-8).
  PS-SCHOOL describes the overrides as "where the student is assigned to the
  section."
- CourseType lives on `[S_NJ_SEC_X]Course_Type` / `[S_NJ_CRS_X]Course_Type` and
  is used by the Student Course Roster only (PS-SCHOOL, PS-DIST). The staff
  extract does not compute S1/S2.

### 4.5 PowerSchool vs state lengths and types

| Element          | State (SCR)                 | PowerSchool (PS-SCR, PS-DIST)                              |
| ---------------- | --------------------------- | ---------------------------------------------------------- |
| SMID             | Numeric, 8                  | Alpha-numeric, length N/A                                  |
| SectionExitDate  | Date, 8                     | Alpha-numeric, 8                                           |
| LocalCourseTitle | 1-50                        | output 50; `Courses.Course_Name` field 40                  |
| LocalCourseCode  | 1-20                        | output 15; `Courses.Course_Number` field 11                |
| LocalSectionCode | 1-20                        | output 10                                                  |
| SubjectArea      | any valid SCED subject area | "Prior-to-Secondary Codes 51-73 ... Secondary Codes 01-22" |

---

## 5. Code lists referenced

### 5.1 Template A workbook (`NJSLEDS_Staff-Course-Roster_Template-A.xlsx`)

Sheets: `Staff Template A` (visible; header only, 19 columns), `Lists` (hidden),
`SCED` (hidden), `Sheet1` (hidden). TPL-B has one sheet, `Sheet1`, with the same
19 headers and no data.

`Lists` tab (header row 1):

| Column             | Values | Content                                                                                      |
| ------------------ | ------ | -------------------------------------------------------------------------------------------- |
| A Counties         | 51     | `01`-`42` (every number, odd and even), `80`, `CT`, `DE`, `MA`, `MD`, `NC`, `NH`, `NY`, `PA` |
| B Districts        | 2,069  | 4-character codes `0001` ... `8909`                                                          |
| C Schools          | 1,413  | 3-character codes `000` ... `99F` (alphanumeric, e.g. `00A`)                                 |
| D CourseLevel      | 5      | `B`, `G`, `E`, `H`, `X`                                                                      |
| E AlphaGrade       | 18     | `A+ A A- B+ B B- C+ C C- D+ D D- F+ F F- E E+ E-` (student-side field; shared tab)           |
| F CompletionStatus | 5      | `P F I W NG` (student-side field; shared tab)                                                |

`Sheet1`: 89 CourseSequence values, `11`-`99` inclusive, including 44 values
whose first digit exceeds the second (e.g. `20`, `21`, `98`) that SCR p.24
rejects.

`SCED` tab: column A lists 44 subject areas:
`01 02 03 04 05 07 08 09 10 11 12 13 14 15 16 17 18 19 20 21 22 24 51 52 53 54 55 56 57 58 60 61 62 63 64 65 66 67 68 69 70 71 72 73`;
one column of course identifiers per subject area (named ranges `_01` ...
`_73`); column AU "all SCED" has 548 unique 3-digit identifiers (`001`-`999`).
Column `55` contains a value `1` without leading zeros. Subject areas 25 and 75
(present in the Feb 2026 SCED list) are absent.

Defined names include `Counties`, `Districts`, `Schools`, `CourseLevelCode`,
`CourseLevelCodeNew`, `AlphaGradeCode`, `CompletionStatusCode`, plus broken
names (`SubjectArea = #REF!`, `CourseIdentifier = [1]Sheet3!#REF!`, external
`[2]` references).

### 5.2 NJSLEDS SCED Course Codes (`NJSLEDS_SCED-Course-Codes.xlsx`, "Updated: February 2026")

Tabs: `Prior-to-Secondary Codes` (header row 5; 607 code rows),
`Secondary Codes` (header row 5; 1,462 code rows; adds AP/IB and SLE mapping
columns), `Updates`, `Archived`.

- Prior-to-secondary subject areas (23): 51 English Language and Literature, 52
  Mathematics, 53 Life and Physical Sciences, 54 Social Sciences and History, 55
  Visual and Performing Arts, 56 World Language and Literature, 57 Religious
  Education and Theology, 58 Physical, Health, and Safety Education, 60 Computer
  and Information Sciences, 61 Communications and Audio/Visual Technology, 62
  Business and Marketing, 63 Manufacturing, 64 Health Care Sciences, 65 Public,
  Protective, and Government Service, 66 Hospitality and Tourism, 67
  Architecture and Construction, 68 Agriculture, Food, and Natural Resources, 69
  Human Services, 70 Transportation, Distribution and Logistics, 71 Engineering
  and Technology, 72 Miscellaneous, 73 Nonsubject Specific, 75 Integrative
  Learning.
- Secondary subject areas (23): 01-05, 07-22 (same families as above plus 09
  Military Science), 24 World Language and Literature, 25 Integrative Learning.
- mSGP subject areas: 51, 52, 73 (SCR p.19).

### 5.3 Other element domains

- CourseLevel: B, G, E, H, X (SCR p.21).
- GradeSpan: two 2-character grade codes from PK, KG, 01-12 (SCR p.22).
- CourseSequence: 11-99, first digit ≤ second (SCR p.24).
- AvailableCredit: 0.000-35.000 (SCR p.23).
- CDS: NJSLEDS County District School Code List (SCR pp.14-16).
- Student-side CourseType (drives staff-count rules): S1, S2, R, C, O (StCR
  p.37).

### 5.4 Job codes (`Job Codes and Job Code Subcategories.xlsx`)

Roster rows carry no job code, but Staff Management assignment rows do (SM
pp.71-72), and the roster CDS must match one of them.

Workbook structure:

| Sheet                             | Rows                | Layout                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --------------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `All Job Codes and Subcategories` | 505 (503 non-empty) | Row 1 description; row 2 header: `Job Code`, `Purchased Services Job Code**`, `Job Code Name`, `Corresponding Job Code Subcategory`, `Column2`; group heading rows interleaved; 473 job codes, 47 with a purchased-services code (`0001`-`0047`); footnote: "Purchased Services Job Codes are to be used for staff members that are purchased services only. All other staff members must use the Job Code in Column A." |
| `Job Code Subcategory`            | 10                  | 1 GENERAL ED, 2 BILINGUAL, 3 HEARING, 4 VISUAL, 5 SPECIAL EDUCATION, 6 ADMINISTRATOR OR SUPERVISORY STAFF, 7 NON CERTIFIED STAFF                                                                                                                                                                                                                                                                                         |
| `Updates`                         | 155                 | header `Date, Action, Job Code, Purchased Services Job Code**, Job Code Name, Corresponding Job Code Subcategory`; newest 2026-07-17 "Added 2728 Hospitality and Tourism Management"; 2025-10-14 added 1192, 1193, 1487, 1898, 2722-2727, 4003, 4004                                                                                                                                                                     |

Codes per group: Administrators 8, Principals 14, Supervisor 30, Non-Supervisory
Coordinator 32, Directors 31, Private School/Only 63, Elementary 9, Middle Grade
5-8 22, Art 8, Business 14, English 12, World Language 17, Health/Physical Ed 7,
Family & Consumer Sciences 4, Industrial Arts 28, Math 4, Financial Literacy 1,
Music 3, Science 7, Social Studies 5, Supplementary Inst 2, Resource Program 2,
Teach Coach Coordinator Leader 3, Vocational Ed 100, Educational Services 34,
Non Certificated Staff 13.

Teacher- and classroom-relevant codes, complete for each group listed (bracket =
allowed subcategories as written in JC; "PS" = purchased-services code). Admin,
principal, supervisor, coordinator, and director groups (all subcategory 6) are
omitted; from "Private School/Only" only the teacher, substitute, and aide codes
are listed.

- **Private School/Only** (8): `0707` Teacher of Students with Disabilities
  (SWD) [5]; `0708` Teacher of the Blind or Visually Impaired [5]; `0709`
  Teacher of the Deaf or Hard of Hearing [5]; `0710` Teacher of the Handicapped
  (TOH) [5]; `0728` Extraordinary Services One to One Aide [7]; `0754`
  Substitute Paraprofessional Instructional [7]; `0758` Substitute Teacher [7];
  `0759` Teacher Aide/Assistant/Instructional Aide/Classroom Assistant/Bus Aide
  [7]
- **Elementary** (9): `1000` Preschool [1,2, 3,4,or 5]; `1001` Elementary
  Kindergarten-8 Grade [1,2, 3,4,or 5]; `1003` Kindergarten [1,2, 3,4,or 5];
  `1004` Elementary School Teacher K-5 [1,2, 3,4,or 5]; `1007` Elementary
  Teacher in secondary setting DLM Only Subcategory Identifier S, H, or V [1,2,
  3,4,or 5]; `1015` English/Elementary [1,2, 3,4,or 5]; `1016`
  Mathematics/Elementary [1,2, 3,4,or 5]; `1017` Science /Elementary [1,2,
  3,4,or 5]; `1018` Social Studies/Elementary [1,2, 3,4,or 5]
- **Middle Grade 5-8** (22): `1102` Mathematics Grades 5 - 8 [1,2, 3,4,or 5];
  `1103` Science Grades 5 -8 [1,2, 3,4,or 5]; `1104` Social Studies Grades 5 -8
  [1,2, 3,4,or 5]; `1105` American Sign Lang Grades 5 - 8 [1,2, 3,4,or 5];
  `1106` Lang Arts/Literacy Grades 5 - 8 [1,2, 3,4,or 5]; `1110` French Grades
  5 - 8 [1,2, 3,4,or 5]; `1125` German Grades 5 - 8 [1,2, 3,4,or 5]; `1130`
  Italian Grades 5 - 8 [1,2, 3,4,or 5]; `1145` Latin Grades 5 - 8 [1,2, 3,4,or
  5]; `1150` Spanish Grades 5 - 8 [1,2, 3,4,or 5]; `1165` Russian Grades 5 - 8
  [1,2, 3,4,or 5]; `1170` Greek Grades 5 - 8 [1,2, 3,4,or 5]; `1172` Chinese
  Grades 5 - 8 [1,2, 3,4,or 5]; `1173` Japanese Grades 5 - 8 [1,2, 3,4,or 5];
  `1174` Portuguese Grades 5 - 8 [1,2, 3,4,or 5]; `1176` Polish Grades 5 - 8
  [1,2, 3,4,or 5]; `1178` Hebrew Grades 5 - 8 [1,2, 3,4,or 5]; `1179` Korean
  Grades 5 - 8 [1,2, 3,4,or 5]; `1181` Arabic Grades 5 - 8 [1,2, 3,4,or 5];
  `1191` Other World Lang Grades 5 - 8 [1,2, 3,4,or 5]; `1192` Humanities Grades
  5-8 [1,2, 3,4,or 5]; `1193` Science, Technology, Engineering and Math (STEM)
  Grades 5-8 [1,2, 3,4,or 5]
- **Art** (8): `1200` Art [1,2, 3,4,or 5]; `1261` Dance [1,2, 3,4,or 5]; `1271`
  Theater/Stage [1,2, 3,4,or 5]; `1273` Cinema/TV Production [1,2, 3,4,or 5];
  `1283` Photography/Technical [1,2, 3,4,or 5]; `1284` Photography/Art of
  photography (HQ Only) [1,2, 3,4,or 5]; `1285` Print Making/Technical [1,2,
  3,4,or 5]; `1286` Print Making/Art of Print Making (HQ Only) [1,2, 3,4,or 5]
- **Business** (14): `1301` Business Organization [1,2, 3,4,or 5]; `1304`
  Advertising [1,2, 3,4,or 5]; `1306` Banking/Insurance Principles [1,2, 3,4,or
  5]; `1308` Economics/Economic Geography [1,2, 3,4,or 5]; `1311` Financial &
  Investment Principles [1,2, 3,4,or 5]; `1315` Business Law [1,2, 3,4,or 5];
  `1317` Marketing/Sales [1,2, 3,4,or 5]; `1331` Bookkeeping Accounting [1,2,
  3,4,or 5]; `1341` Office Organization - Practices and Procedures [1,2, 3,4,or
  5]; `1345` Clerical Office Practices [1,2, 3,4,or 5]; `1361` Shorthand [1,2,
  3,4,or 5]; `1381` Typing/Word Processing [1,2, 3,4,or 5]; `1387` Data Entry
  [1,2, 3,4,or 5]; `1388` Data Processing [1,2, 3,4,or 5]
- **English** (12): `1401` English Non-Elementary [1,2, 3,4,or 5]; `1405`
  Business English [1,2, 3,4,or 5]; `1408` Basic Skills/Remedial English [1,2,
  3,4,or 5]; `1411` Reading Development/Remedial Elementary [1,2, 3,4,or 5];
  `1412` Reading Remedial-Secondary [1,2, 3,4,or 5]; `1415` Library Skills
  Development [1,2, 3,4,or 5]; `1441` Speech Arts/Drama [1,2, 3,4,or 5]; `1442`
  Public Speaking [1,2, 3,4,or 5]; `1451` Theater [1,2, 3,4,or 5]; `1485`
  English as a 2nd Language [1,2, 3,4,or 5]; `1486` Bilingual/Bicultural [2];
  `1487` Speech Arts [1,2, 3,4,or 5]
- **World Language** (17): `1500` Language Arts/Literacy [1,2, 3,4,or 5]; `1505`
  American Sign Language [1,2, 3,4,or 5]; `1506` Chinese [1,2, 3,4,or 5]; `1510`
  French [1,2, 3,4,or 5]; `1520` German [1,2, 3,4,or 5]; `1530` Italian [1,2,
  3,4,or 5]; `1540` Latin [1,2, 3,4,or 5]; `1550` Spanish [1,2, 3,4,or 5];
  `1560` Russian [1,2, 3,4,or 5]; `1570` Greek [1,2, 3,4,or 5]; `1573` Japanese
  [1,2, 3,4,or 5]; `1574` Portuguese [1,2, 3,4,or 5]; `1576` Polish [1,2, 3,4,or
  5]; `1579` Hebrew [1,2, 3,4,or 5]; `1581` Arabic [1,2, 3,4,or 5]; `1582`
  Korean [1,2, 3,4,or 5]; `1599` Other Than Above [1,2, 3,4,or 5]
- **Health/Physical Ed** (7): `1607` Health & Physical Education [1,2, 3,4,or
  5]; `1610` Driver Education [1,2, 3,4,or 5]; `1615` Swimming/Water Safety
  [1,2, 3,4,or 5]; `1620` Health [1,2, 3,4,or 5]; `1630` Physical Education
  [1,2, 3,4,or 5]; `1644` Recreation [1,2, 3,4,or 5]; `1645` Family Life
  Education [1,2, 3,4,or 5]
- **Family & Consumer Sciences** (4): `1700` Family & Consumer Sciences -
  Comprehensive [1,2, 3,4,or 5]; `1704` Family & Consumer Sciences – Apparel,
  Textiles and Interiors [1,2, 3,4,or 5]; `1706` Family & Consumer Sciences -
  Child & Family Development [1,2, 3,4,or 5]; `1760` Family & Consumer Sciences
  – Foods/Nutrition & Food Science [1,2, 3,4,or 5]
- **Industrial Arts** (28): `1805` Career Education [1,2, 3,4,or 5]; `1812`
  General Shop [1,2, 3,4,or 5]; `1815` Plastics [1,2, 3,4,or 5]; `1818` Ceramics
  [1,2, 3,4,or 5]; `1819` Leatherworking [1,2, 3,4,or 5]; `1821` Drafting and
  Design Technology (Includes Mechanical, Architectural, Machine Drawing,
  Architecture/Home Planning, Blueprint Reading, Industrial Arts, Industrial
  Drafting) [1,2, 3,4,or 5]; `1825` Engineering Drawing [1,2, 3,4,or 5]; `1832`
  Furniture Refinish [1,2, 3,4,or 5]; `1833` General Woodwork [1,2, 3,4,or 5];
  `1842` General Metalwork [1,2, 3,4,or 5]; `1844` Machine Shop [1,2, 3,4,or 5];
  `1850` Radio and Theory [1,2, 3,4,or 5]; `1853` Basic Electricity [1,2, 3,4,or
  5]; `1854` Appliance Repair [1,2, 3,4,or 5]; `1855` Electricity/Electronics
  [1,2, 3,4,or 5]; `1856` Electronics [1,2, 3,4,or 5]; `1857` Electricity [1,2,
  3,4,or 5]; `1861` General Mechanics [1,2, 3,4,or 5]; `1862` Power Mechanics
  [1,2, 3,4,or 5]; `1864` Auto Mechanics [1,2, 3,4,or 5]; `1872` Graphic Arts
  [1,2, 3,4,or 5]; `1876` Printing [1,2, 3,4,or 5]; `1882` Home Mechanics [1,2,
  3,4,or 5]; `1893` Surveying [1,2, 3,4,or 5]; `1894` Building Trades [1,2,
  3,4,or 5]; `1896` Aeronautics [1,2, 3,4,or 5]; `1897` Technology Education
  [1,2, 3,4,or 5]; `1898` Computer Science [1,2, 3,4,or 5]
- **Math** (4): `1901` Math Non-Elementary [1,2, 3,4,or 5]; `1904` Remedial Math
  [1,2, 3,4,or 5]; `1907` Business Math [1,2, 3,4,or 5]; `1962` Computer
  Literacy/Applications/Programming [1,2, 3,4,or 5]
- **Financial Literacy** (1): `2001` Financial Literacy (Math, Social Studies,
  Business: Finance, Economics, Law, Comprehensive Business, Comprehensive
  Family and Consumer Sciences and General Business Teachers) can hold this Job
  Code [1,2, 3,4,or 5]
- **Music** (3): `2100` Music Comprehensive [1,2, 3,4,or 5]; `2110` Music
  Instrumental [1,2, 3,4,or 5]; `2130` Music Vocal [1,2, 3,4,or 5]
- **Science** (7): `2202` Science General [1,2, 3,4,or 5]; `2205` Science Earth
  [1,2, 3,4,or 5]; `2206` Science Physical [1,2, 3,4,or 5]; `2214` Science
  Military [1,2, 3,4,or 5]; `2231` Science Biological [1,2, 3,4,or 5]; `2235`
  Science Chemistry [1,2, 3,4,or 5]; `2236` Science Physics [1,2, 3,4,or 5]
- **Social Studies** (5): `2302` Social Studies Non-Elementary [1,2, 3,4,or 5];
  `2305` Social Studies Humanities [1,2, 3,4,or 5]; `2317` Social Studies
  Psychology [1,2, 3,4,or 5]; `2322` Social Studies History [1,2, 3,4,or 5];
  `2391` Social Studies Geography [1,2, 3,4,or 5]
- **Supplementary Inst** (2): `2400` Supplementary Instruction (In-Class) [1,2,
  3,4,or 5]; `2401` Supplementary Instruction (Pull-Out) [1,2, 3,4,or 5]
- **Resource Program** (2): `2405` Resource Program In-Class [1,2, 3,4,or 5];
  `2406` Resource Program Pull-Out Support [1,2, 3,4,or 5]
- **Teach Coach Coordinator Leader** (3): `2410` Teacher Coach [1,2, 3,4,or 5];
  `2411` Teacher Coordinator [1,2, 3,4,or 5]; `2412` Teacher Leader [1,2, 3,4,or
  5]
- **Vocational Ed** (100): `2501` Agricultural Occupations [1,2, 3,4,or 5];
  `2507` Agricultural Technology [1,2, 3,4,or 5]; `2508` Turf Management [1,2,
  3,4,or 5]; `2512` Marketing Education [1,2, 3,4,or 5]; `2513` Apparel and
  Accessories [1,2, 3,4,or 5]; `2514` Automotive [1,2, 3,4,or 5]; `2517` Food
  Management [1,2, 3,4,or 5]; `2518` Food Services [1,2, 3,4,or 5]; `2519` Food
  Production [1,2, 3,4,or 5]; `2520` Food Technology [1,2, 3,4,or 5]; `2522`
  Hotel and Lodging [1,2, 3,4,or 5]; `2523` Health Fitness [1,2, 3,4,or 5];
  `2525` Computer Integrated Manufacturing [1,2, 3,4,or 5]; `2526` Audio
  Technology [1,2, 3,4,or 5]; `2527` Environmental Occupations [1,2, 3,4,or 5];
  `2540` Dental Assisting [1,2, 3,4,or 5]; `2541` Legal Assisting [1,2, 3,4,or
  5]; `2551` Practical Nurse [1,2, 3,4,or 5]; `2552` Medical Assistant [1,2,
  3,4,or 5]; `2554` Health Occupation [1,2, 3,4,or 5]; `2555` Medical Dental
  Assistant [1,2, 3,4,or 5]; `2556` Nursing Assistant (Aide) [1,2, 3,4,or 5];
  `2569` Small Animal Care [1,2, 3,4,or 5]; `2571` Warehousing [1,2, 3,4,or 5];
  `2572` Automotive Technology (Includes Automobile Mechanics and Automotive
  Specialties) [1,2, 3,4,or 5]; `2573` Chemical Technology [1,2, 3,4,or 5];
  `2575` Construction Technology [1,2, 3,4,or 5]; `2576` Draft/Design Technology
  [1,2, 3,4,or 5]; `2577` Electrical Technology [1,2, 3,4,or 5]; `2579`
  Electronic Technology [1,2, 3,4,or 5]; `2580` Law Enforcement [1,2, 3,4,or 5];
  `2581` Emergency Medical Technology [1,2, 3,4,or 5]; `2593` Computer
  Technology [1,2, 3,4,or 5]; `2595` Water/ Waste Water [1,2, 3,4,or 5]; `2597`
  Power Plant Technology [1,2, 3,4,or 5]; `2600` Air Conditioning &
  Refrigeration [1,2, 3,4,or 5]; `2602` Heating/Ventilation [1,2, 3,4,or 5];
  `2603` Heating/Ventilation/Air Conditioning/Refrigeration [1,2, 3,4,or 5];
  `2612` Body/Fender Repair [1,2, 3,4,or 5]; `2613` Diesel Mechanic [1,2, 3,4,or
  5]; `2614` Heavy Equipment (Construction Mechanic) [1,2, 3,4,or 5]; `2616`
  Small Engine Repair(Internal Combustion) [1,2, 3,4,or 5]; `2617` Aircraft
  Maintenance [1,2, 3,4,or 5]; `2619` Commercial Art [1,2, 3,4,or 5]; `2620`
  Commercial Photography [1,2, 3,4,or 5]; `2621` Drafting [1,2, 3,4,or 5];
  `2622` Graphic Arts [1,2, 3,4,or 5]; `2623` Industrial Design [1,2, 3,4,or 5];
  `2624` Printing [1,2, 3,4,or 5]; `2626` Marine Trades Technology [1,2, 3,4,or
  5]; `2627` Building Trades [1,2, 3,4,or 5]; `2628` Carpentry [1,2, 3,4,or 5];
  `2630` Electricity [1,2, 3,4,or 5]; `2633` Masonry [1,2, 3,4,or 5]; `2635`
  Plumbing & Pipefitting [1,2, 3,4,or 5]; `2637` Stationary Engineering [1,2,
  3,4,or 5]; `2643` Radio Broadcasting [1,2, 3,4,or 5]; `2645` Television
  Production [1,2, 3,4,or 5]; `2646` Apparel and Textile Service [1,2, 3,4,or
  5]; `2647` Apparel and Textile Production [1,2, 3,4,or 5]; `2649`
  Tailoring/Dress Making [1,2, 3,4,or 5]; `2650` Apparel and Textile Management
  [1,2, 3,4,or 5]; `2652` Cosmetology/Hair Styling [1,2, 3,4,or 5]; `2655`
  Building Maintenance [1,2, 3,4,or 5]; `2656` Machine Shop [1,2, 3,4,or 5];
  `2659` Millwork/Cabinet Making [1,2, 3,4,or 5]; `2660` Plastics Production
  [1,2, 3,4,or 5]; `2661` Sheet Metal [1,2, 3,4,or 5]; `2663` Welding [1,2,
  3,4,or 5]; `2664` Baking [1,2, 3,4,or 5]; `2665` Commercial Food Services
  [1,2, 3,4,or 5]; `2691` Engineering Technology [1,2, 3,4,or 5]; `2692`
  Telecommunications [1,2, 3,4,or 5]; `2693` Vocational Arts/Dance [1,2, 3,4,or
  5]; `2694` Vocational Art/Theater [1,2, 3,4,or 5]; `2695` Visual Arts [1,2,
  3,4,or 5]; `2696` Vocational Art/Inst Music [1,2, 3,4,or 5]; `2697` Vocational
  Art/Vocal Music [1,2, 3,4,or 5]; `2698` Desktop Publishing [1,2, 3,4,or 5];
  `2699` Dental Office Management [1,2, 3,4,or 5]; `2700` Medical Office
  Management [1,2, 3,4,or 5]; `2701` Culinary Arts [1,2, 3,4,or 5]; `2702` Chef
  Preparation [1,2, 3,4,or 5]; `2708` Human Development & Child Care Services
  [1,2, 3,4,or 5]; `2712` Data Management [1,2, 3,4,or 5]; `2713` Computer
  Network System [1,2, 3,4,or 5]; `2714` Computer Service Technicians [1,2,
  3,4,or 5]; `2715` Computer System Engineering [1,2, 3,4,or 5]; `2716`
  Interactive Media [1,2, 3,4,or 5]; `2717` Information, Support & Services
  [1,2, 3,4,or 5]; `2718` Internet& Online Technology [1,2, 3,4,or 5]; `2720`
  Marine Sciences [1,2, 3,4,or 5]; `2721` Vocational Arts/Electronic Music [1,2,
  3,4,or 5]; `2722` General Health Science [1,2, 3,4,or 5]; `2723`
  Bioengineering [1,2, 3,4,or 5]; `2724` Merchandising and Buying [1,2, 3,4,or
  5]; `2725` Healthcare Administration Management [1,2, 3,4,or 5]; `2726` Design
  and Applied Arts [1,2, 3,4,or 5]; `2727` Fashion Design [1,2, 3,4,or 5];
  `2728` Hospitality and Tourism Management [1,2, 3,4,or 5]
- **Educational Services** (34): `3100` (PS `0001`) Director of School
  Counseling Services [1,2, 3,4,or 5]; `3101` (PS `0002`) School Counselor [1,2,
  3,4,or 5]; `3103` (PS `0036`) Teacher/Behavior Specialist (Traditional
  Students) [1,2, 3,4]; `3105` (PS `0003`) School Librarian, Media Specialist
  Assoc. [1,2, 3,4,or 5]; `3106` (PS `0044`) Associate School Library Media
  Specialist [1,2, 3,4,or 5]; `3111` (PS `0004`) Occupation Therapist [1,2,
  3,4,or 5]; `3112` (PS `0005`) Physical Therapist [1,2, 3,4,or 5]; `3113` (PS
  `0006`) Athletic Trainer [1,2, 3,4,or 5]; `3114` (PS `0007`) School Nurse
  (Must Hold A Certificate 3000 in dealing with medical needs and records is
  authorized to teach health) [1,2, 3,4,or 5]; `3115` (PS `0008`) School
  Nurse/Non Instructional (Must Hold Certificates 3010 who tend only to medical
  needs and records) [1,2, 3,4,or 5]; `3116` (PS `0009`) School Psychologist
  [1,2, 3,4,or 5]; `3117` (PS `0010`) School Social Worker [1,2, 3,4,or 5];
  `3118` (PS `0011`) Learning Disabilities Teacher Consultant [2, 3,4,or 5];
  `3119` (PS `0012`) Reading Specialist [1,2, 3,4,or 5]; `3120` (PS `0013`)
  Speech Correction/Language Specialist [1,2, 3,4,or 5]; `3121` (PS `0014`)
  Coordinator Substance Abuse [1,2, 3,4,or 5]; `3122` (PS `0015`) Educational
  Interpreter-Sign Language Interpreting [1,2, 3,4,or 5]; `3123` (PS `0016`)
  Educational Interpreter-Oral Interpreting [1,2, 3,4,or 5]; `3124` (PS `0017`)
  Educational Interpreter-Cued Speech Transliteration [1,2, 3,4,or 5]; `3125`
  (PS `0037`) Teacher/ Behavior Specialist (SE Only) [2, 3, 4,or 5]; `3126` (PS
  `0018`) Cooperative Agricultural Education [1,2, 3,4,or 5]; `3132` (PS `0019`)
  Cooperative Education Coordinator (Hazardous Occupations) [1,2, 3,4,or 5];
  `3133` (PS `0020`) Cooperative Education Coordinator (Non Hazardous
  Occupations) [1,2, 3,4,or 5]; `3134` (PS `0021`) County Apprenticeship
  Coordinator [1,2, 3,4,or 5]; `3135` (PS `0022`) Structured Learning Experience
  Coordinator [1,2, 3,4,or 5]; `3136` (PS `0038`) Transition Teacher [1,2,
  3,4,or 5]; `3137` (PS `0039`) Orientation and Mobility Specialist [4]; `3139`
  (PS `0040`) School Safety Specialist [1,2, 3,4,or 5]; `3140` (PS `0045`)
  Gifted and Talented Staff [1,2, 3,4,or 5]; `4000` (PS `0023`) Anti-Bullying
  Specialist [1,2, 3,4,or 5]; `4001` (PS `0024`) In-School Suspension [1,2,
  3,4,or 5]; `4002` (PS `0041`) Practical Nurse/Advanced Practical Nurse
  (Licensed by exam NJ) [1,2, 3,4,or 5]; `4003` (PS `0046`) Early Literacy
  Specialist [1,2, 3,4,or 5]; `4004` (PS `0047`) Bilingual Language
  Paraprofessional [1,2, 3,4,or 5]
- **Non Certificated Staff** (13): `9000` (PS `0025`) Professional Staff [7];
  `9025` (PS `0043`) BCBA Behavior Analyst [7]; `9030` (PS `0042`) Data
  Coordinator [7]; `9050` (PS `0026`) Physics (Pilot Program Only) [7]; `9100`
  (PS `0027`) Instructional Paraprofessionals (Serving Ages 3 to 5) [1,2, 3, 4,
  5, or 7]; `9101` (PS `0028`) Instructional Paraprofessionals (Serving Ages 6
  to 21) [1, 2, 3, 4, 5, or 7]; `9150` (PS `0029`) Non Instructional
  Paraprofessionals (Serving Ages 3 to 5) [1, 2, 3, 4, 5, or 7]; `9151` (PS
  `0030`) Non Instructional Paraprofessionals (Serving Ages 6 to 21) [1, 2, 3,
  4, 5, or 7]; `9200` (PS `0031`) Technicians [7]; `9300` (PS `0032`)
  Clerical/Secretarial [7]; `9400` (PS `0033`) Service Workers [7]; `9500` (PS
  `0034`) Skilled Craftsperson's [7]; `9600` (PS `0035`) Laborers Unskilled [7]

Related Staff Management rules: JobCode 1486 only with subcategory 2 (SM
pp.71-72). CredentialType required for job codes 0001-0024, 0036-0041,
0044-0047, 0100-0699, 0707-0710, 1000-4004; not for 0025-0035, 0042-0043,
0700-0706, 0711-0762 (SM p.74). EmploymentStatus `01380` = Substitute/temporary
(SM p.62). CertificationStatus Y only for certified teachers, administrators,
nurses, media specialists, counselors, child study team, psychologists;
paraprofessionals N (SM p.38; FAQ-SM Q5).

### 5.5 PowerSchool teacher roles

District-defined in Roles Administration > Co-Teaching, up to 100 role IDs
mapped in `NJ_Teacher_Role_Mapping` (PS-DIST). No role codes are published in
the PS docs.

---

## 6. Open questions and disagreements

1. **Co-teacher limits.** No source caps the number of staff on a section. SCR
   says "the staff member responsible for 100% of the roster" (singular,
   pp.9-18), while FAQ-CR Q1.10 includes "teachers and co-teachers". Whether
   three or more co-teachers, or a lead plus several co-teachers, are acceptable
   is not stated; only the S2 "more than one staff member" check exists (StCR
   p.37).
2. **SectionExitDate required or not.** "Required?" says not mandatory while the
   staff member is still active in the course, but the first validation check is
   "An error will occur if this field is left blank" (SCR p.18). FAQ-CR Q3.3
   (students) says every record will have an exit date because collection is at
   year end.
3. **"Current School Year" and "acceptable range" are undefined** for the entry
   and exit dates (SCR pp.17-18). CAL marks June 30, 2027 as the end of
   SY2026-27; the Student Management handbook uses "July 1 through June 30" for
   annual reporting periods (Student Management handbook v2.2, p.133). Not
   stated for this file.
4. **PowerSchool date source.** Dates come from `Terms.FirstDay/LastDay` unless
   `NJ_Section_Teacher_Tracking` rows exist (PS-SCR #9-10). A mid-year teacher
   change without tracking rows would give both teachers full-term dates. The
   docs do not say whether `SectionTeacher.Start_Date/End_Date` are used.
5. **Paraprofessionals, aides, inclusion staff.** No roster source addresses
   them. PowerSchool's only filters are 100% allocation and role exclusion
   (PS-SCR; PS-SCHOOL; PS-DIST), so the district's role mapping decides.
6. **Substitute threshold wording.** "twenty or more consecutive days" (FAQ-CR
   Q4.2) vs "more than 20 days" (FAQ-SM Q18; RR scenario 5) vs "longer than 20
   days ... at any point during the school year" (RR scenario 6).
7. **Identity source mismatch risk in PowerSchool.** The roster extract reads
   DOB from `[UsersCoreFields]DOB` (PS-SCR #5) while PS-STAFF lists
   `[S_NJ_USR_X]DateofBirth`; names come from `SMART_First_Name/SMART_Last_Name`
   (PS-SCR #3-4) while the NJS SMID tab has separate `[S_NJ_USR_X]FirstName` and
   `[S_NJ_USR_X]Last Name` (length 11, PS-STAFF). All five identity fields must
   match Staff Management exactly (SCR p.10). Which system and fields produce
   KTAF's Staff Management file is not in these sources.
8. **Three different keys.** Uniqueness (FAQ-CR Q1.6) includes GradeSpan and
   SectionExitDate but not LocalCourseCode; update (Q1.14) includes
   LocalCourseCode but not names, DOB, LSID, or exit date; linking (Q5.1)
   includes CourseLevel and CourseSequence but not GradeSpan or dates. Tests
   need to pick the right key per purpose.
9. **CDS match: per field or as a set?** SCR pp.14-16 say each code must match
   "one of the six" values in Staff Management; FAQ-CR Q1.8 says the
   county/district/school set must match one of the six sets.
10. **Staff with more than six schools.** Staff Management uses "000" "to
    indicate additional assignments captured through Course Roster" (SM pp.65,
    68). How Out of Sync treats roster schools not among the six listed is not
    stated.
11. **Staff Management window closes before the roster window opens.** Staff
    Management EOY closes June 30, 2027; the official roster period opens July
    2, 2027 (CAL). FAQ-CR Q1.9 says re-upload Staff Management first to clear
    Out of Sync; whether Staff Management accepts corrections in July is not
    stated.
12. **SubjectArea ranges.** PS-SCR #11 lists only 01-22 and 51-73; the Feb 2026
    SCED list adds 24 and 25 (secondary) and 75 (prior-to-secondary). TPL-A's
    SCED tab (Aug 2025) has 24 but lacks 25 and 75.
13. **SubjectArea + CourseIdentifier combination.** SCR validates each part as
    "a valid SCED ... code" (pp.19-20); whether the pair must exist in the
    NJSLEDS SCED list is not stated as an error. RPT p.1 drops invalid pairs
    from the Course Summary report.
14. **PowerSchool length truncation.** LocalCourseCode 15 and LocalSectionCode
    10 in PS vs 20 in SCR; `Courses.Course_Name` 40 vs 50 (section 4.5). Also,
    `[Sections]SectionID` is not a standard column name; it could mean
    `Sections.ID` or `Sections.Section_Number`.
15. **GradeSpan ordering and validity** (e.g. `0503` or `KGPK`) is not stated;
    TPL-A only checks length 4 (SCR p.22).
16. **Template defects.** Trailing spaces in four headers in TPL-A and TPL-B;
    AvailableCredit validation allows 0-35 but its error text says "between
    0.000 and 20.000"; the CourseSequence list includes values SCR p.24 rejects;
    Counties list includes even numbers and state abbreviations. Whether the
    upload matches headers by exact string is not stated (FAQ-SM Q23 mentions
    "template mismatch" for Staff Management).
17. **Deadline text.** RPT p.1 (May 2026) says "the August 3 deadline"; CAL
    shows the SY2025-26 official period closing August 5, 2026. CAL shows August
    3, 2027 for SY2026-27.
18. **No SY2026-27 staff roster handbook yet.** SCR v1.1 (May 2026) carries no
    school-year label; SM is already the 2026-2027 v1.5. A new SCR may arrive
    before the April 2027 practice window.
19. **PowerSchool student-side gaps that affect staff rules.** PS-StCR selects
    students who "must have completed grades in grade level 6 or higher
    courses", so K-5 sections may have staff rows and no student rows. PS-StCR's
    output table does not list CourseType, although the S1/S2 rule depends on
    it.
20. **PowerSchool `Active` flag.** PS-STAFF lists `[S_NJ_USR_X]Active` as used
    by Staff Course Roster, but PS-SCR's selection criteria do not mention it.
    The state treats staff not active in Staff Management as a cause of Out of
    Sync (FAQ-CR Q1.9) while also requiring inactive staff to stay through the
    EOY Snapshot for Course Roster (FAQ-SM Q21).
21. **AvailableCredit formatting.** SCR allows length 5-6 (p.23); PS extracts
    "xx.xxx" (PS-SCR #15). Whether values under 10 are zero-padded to 6
    characters is not stated.
22. **FirstName special characters.** SCR allows only apostrophes and hyphens
    (p.11); a space is not mentioned for FirstName, while LastName explicitly
    allows a space (p.12). TPL type is "Alpha" for both.
23. **Which KTAF LEA codes submit separately.** DistrictCodeAssigned must equal
    the submitting district (SCR p.15); confirm the LEA-to-file mapping with the
    team (not addressed by these sources).
