# NJSLEDS Staff Course Roster — extracted validation rules

Source: Staff Course Roster Submission Handbook, **Version 1.1**, May 2026.

Mechanically extracted from the handbook PDF so the rule catalog is built from
verbatim text rather than transcription. Do not hand-edit — regenerate if the
handbook is revised.

Data elements found: **19**.

---

## LocalStaffIdentifier (LSID)

_Handbook page 9._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Alphanumeric Minimum Length: 1 Maximum Length: 20

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if this field does not exactly match the value in Staff
  Management.

### Additional Notes

• Only the staff member responsible for 100% of the roster should be reported.

### Common Errors

Error Message: Duplicate staff record with the same information already exists
in the LEA. Resolution: Review the staff member’s course records to identify
which courses are duplicated. To resolve, upload a file with each course record
listed once for each staff member.

---

## StaffMemberIdentifier (SMID)

_Handbook page 10._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Numeric Minimum Length: 8 Maximum Length: 8

### Validation Checks

- • An error will occur when the value submitted is not exactly 8 digits.
- • An error will occur if this field is left blank.
- • An error will occur when the Staff Member Identifier is not a valid number
  issued by NJSLEDS.
- • An error will occur if this field does not exactly match the value in Staff
  Management.

### Additional Notes

• Only the staff member responsible for 100% of the roster should be reported.

### Common Errors

Error Message: Combination of LSID, SMID, First Name, Last Name, and Date of
Birth does not match data submitted during the Staff Management submission.
Resolution: To resolve this error, click on the Snapshot page in Staff
Management. Compare the values of all five fields (LSID, SMID, First Name, Last
Name, and Date of Birth) in the record against the fields in the Staff Course
Roster submission. All five fields in the Staff Course Roster submission must
match exactly to the Staff Management Snapshot page, and the record on the
Snapshot must be free of Error, Sync, and Unresolved. Make the necessary changes
within your local data system and then re-upload to the Staff Course Roster
submission to resolve the combination error.

---

## FirstName

_Handbook page 11._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Alpha Minimum Length: 1 Maximum Length: 30

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if this field contains any special characters except for
  apostrophes (‘) and hyphens (-).
- • An error will occur if this field does not exactly match the value in Staff
  Management.

### Additional Notes

• First names and last names must be reported as separate fields. • No nicknames
or abbreviated names should be reported. • Only the staff member responsible for
100% of the roster should be reported.

### Common Errors

N/A

---

## LastName

_Handbook page 12._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Alpha Minimum Length: 1 Maximum Length: 50

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if this field contains any special characters except for
  apostrophes (‘) and hyphens (-).
- • An error will occur if this field does not exactly match the value in Staff
  Management.

### Additional Notes

• First name and last name must be reported as separate fields. • Staff members
with more than one last name should include all last names in this field.
Hyphens may be used if they are part of the legal name (e.g., Smith-Jones).
Names without hyphens should be entered with a space (e.g., Davis Smyth). • Only
the staff member responsible for 100% of the roster should be reported.

### Common Errors

N/A

---

## DateOfBirth

_Handbook page 13._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Date Minimum Length: 8 Maximum Length: 8 Format: YYYYMMDD

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the date is not entered in YYYYMMDD format (for
  example, 20150128).
- • An error will occur if this field does not exactly match the value in Staff
  Management.

### Additional Notes

• Only the staff member responsible for 100% of the course roster should be
reported.

### Common Errors

N/A

---

## CountyCodeAssigned

_Handbook page 14._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Character Minimum Length: 2 Maximum Length: 2 For County Codes, please
refer to the NJSLEDS County District School Code List.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the County Code submitted does not conform to the
  codes listed for your district in the CDS list.
- • An error will occur if required leading zeros are missing, resulting in an
  incorrect value format.
- • An error will occur if this field does not exactly match one of the six
  CountyCodeAssigned values in Staff Management.

### Additional Notes

• The CountyCodeAssigned should reflect the accurate County Code for the
specific course section.

### Common Errors

N/A

---

## DistrictCodeAssigned

_Handbook page 15._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Character Minimum Length: 4 Maximum Length: 4 For District Codes, please
refer to the NJSLEDS County District School Code List.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the District Code submitted does not match the
  Submitting District.
- • An error will occur if required leading zeros are missing, resulting in an
  incorrect value format.
- • An error will occur if this field does not exactly match one of the six
  DistrictCodeAssigned values in Staff Management.

### Additional Notes

• The DistrictCodeAssigned should reflect the accurate District Code for the
specific course section.

### Common Errors

N/A

---

## SchoolCodeAssigned

_Handbook page 16._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Character Minimum Length: 3 Maximum Length: 3 For School Codes, please
refer to the NJSLEDS County District School Code List.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the School Code submitted does not conform to the
  codes listed for your district in the CDS list.
- • An error will occur if required leading zeros are missing, resulting in an
  incorrect value format.
- • An error will occur if this field does not exactly match one of the six
  SchoolCodeAssigned values in Staff Management.

### Additional Notes

• The SchoolCodeAssigned should reflect the accurate School Code for the
specific course section.

### Common Errors

N/A

---

## SectionEntryDate

_Handbook page 17._

### Is this Data Element Required?

Yes. This field is mandatory for all staff members.

### Acceptable Values

Type: Date Minimum Length: 8 Maximum Length: 8 Format: YYYYMMDD

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value does not meet the acceptable range of
  values.
- • An error will occur if the date is not entered in YYYYMMDD format (for
  example, 20250128).
- • An error will occur if the staff course entry date occurs after the staff
  course exit date.
- • An error will occur if the SectionEntryDate does not occur in the current
  School Year.

### Additional Notes

• Only the staff member responsible for 100% of the roster should be reported. •
If a staff member enters, exits, and later re-enters the same course section
within the School Year, submit multiple records to reflect each teaching period.
Do not overwrite earlier exit/entry dates with the most recent entry date. •
Section Entry and Section Exit Dates are used in the mSGP calculation to
determine the time in course for the teacher of record. For more information on
how an mSGP is calculated, please review the Median Student Growth Percentiles
page.

### Common Errors

N/A

---

## SectionExitDate

_Handbook page 18._

### Is this Data Element Required?

This field is mandatory for all staff who are no longer active in the course.
Otherwise, this field is not mandatory.

### Acceptable Values

Type: Date Minimum Length: 8 Maximum Length: 8 Format: YYYYMMDD

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value does not meet the acceptable range of
  values.
- • An error will occur if the date is not entered in YYYYMMDD format (for
  example, 20250128).
- • An error will occur if the staff course exit date occurs before the staff
  course entry date.
- • An error will occur if the SectionExitDate does not occur in the current
  School Year.
- • An error will occur if the SectionExitDate is later than the file submission
  date (for example, a future date).

### Additional Notes

• Only the staff member responsible for 100% of the roster should be reported. •
If a staff member enters, exits, and later re-enters the same course section
within the School Year, submit multiple records to reflect each teaching period.
Do not overwrite earlier exit/entry dates with the most recent entry date. •
Section Entry and Section Exit Dates are used in the mSGP calculation to
determine the time in course for the teacher of record. For more information on
how an mSGP is calculated, please review the Median Student Growth Percentiles
page.

### Common Errors

N/A

---

## SubjectArea

_Handbook page 19._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Numeric Minimum Length: 2 Maximum Length: 2 For Subject Area Codes, please
refer to the NJSLEDS SCED Course Codes document.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value is not a valid SCED Subject Area code.

### Additional Notes

• You will need to work cooperatively with your curriculum coordinator to assign
the appropriate subject area code. Some courses will require your professional
judgement. • Prior-to-secondary course codes should be used for all courses that
do not have Available Credit. Secondary course codes should be used for all
courses that have an Available Credit of greater than 0.000. • Staff members
reported with a Subject Area of 51, 52, or 73 will be pulled to the Teacher
median SGP District Summary Report. For more information on how an mSGP is
calculated, please review the Median Student Growth Percentiles page.

### Common Errors

N/A

---

## CourseIdentifier

_Handbook page 20._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Numeric Minimum Length: 3 Maximum Length: 3 For Course Identifier Codes,
please refer to the NJSLEDS SCED Course Codes document.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value is not a valid SCED Course Identifier code.
- • An error will occur if required leading zeros are missing, resulting in an
  incorrect value format.

### Additional Notes

• You will need to work cooperatively with your curriculum coordinator to assign
the appropriate Course Identifier code. Some courses will require your
professional judgement. • Prior-to-secondary course codes should be used for all
courses that do not have Available Credit. Secondary course codes should be used
for all courses that have an Available Credit or greater than 0.000.

### Common Errors

N/A

---

## CourseLevel

_Handbook page 21._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Alpha Minimum Length: 1 Maximum Length: 1 • B = Basic or remedial. A
course focusing primarily on skills development, including literacy in language,
mathematics, and the physical and social sciences. These courses are typically
less rigorous than standard courses and may be intended to prepare a student for
a general course. • G = General or regular. A course providing instruction in a
given subject area that focuses primarily on general concepts appropriate for
the grade level. General courses typically meet the state’s or district’s
expectations of scope and difficulty for mastery of the content. • E = Enriched
or advanced. A course that augments the content and/or rigor of a general
course, but does not carry an honors designation. • H = Honors. An advanced
level course designed for students who have earned honors status according to
educational requirements. • X = No specified level of rigor.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value is not a valid SCED Course Level code.

### Additional Notes

• You will need to work cooperatively with your curriculum coordinator to assign
the appropriate Course Level. Some courses will require your professional
judgment.

### Common Errors

N/A

---

## GradeSpan

_Handbook page 22._

### Is this Data Element Required?

This field is mandatory for all prior-to-secondary courses. This field is not
required for secondary courses and can be blank.

### Acceptable Values

Type: Alphanumeric Minimum Length: 4 Maximum Length: 4 • 4-character
alphanumeric code with no decimals. • Each grade level from PK through 12 is
represented by a two-digit code, ranging from PK to 12; kindergarten is
represented by the letters KG, and prekindergarten by the letters PK.

### Validation Checks

- • An error will occur if the field is left blank for a course with a
  Prior-To-Secondary course code.
- • An error will occur if the value does not match the acceptable range of
  values.

### Additional Notes

• For example, a course appropriate for kindergarten and first grade would be
assigned a Grade Span of KG01.

### Common Errors

N/A

---

## AvailableCredit

_Handbook page 23._

### Is this Data Element Required?

This field is mandatory for all secondary courses. This field is not required
for prior-to-secondary courses and can be blank.

### Acceptable Values

Type: Numeric with a decimal point Minimum Length: 5 Maximum Length: 6 Values:
0.000-35.000

### Validation Checks

- • An error will occur if this field is left blank for a course with a
  Secondary course code.
- • An error will occur if the value does not match the acceptable range of
  values.

### Additional Notes

• Decimal points rounded up to the nearest thousandths are accepted in this
field. • 0.000 means the course does not carry any credits.

### Common Errors

N/A

---

## CourseSequence

_Handbook page 24._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Numeric Minimum Length: 2 Maximum Length: 2 Values: 11-99

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value of the first digit is greater than the
  value of the second digit.

### Additional Notes

• For single section courses, Course Sequence will equal 11 which means 1 of 1
in a course sequence. Example of a Course with multiple sections: a science
course that includes a lecture and lab section. Lecture would be coded with a
Course Sequence of 12 (1 of 2), the lab would be coded with a Course Sequence of
22 (2 of 2).

### Common Errors

N/A

---

## LocalCourseTitle

_Handbook page 25._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Alphanumeric Minimum Length: 1 Maximum Length: 50

### Validation Checks

- • An error will occur if this field is left blank.

### Additional Notes

• There is no state-wide standardized list of local course titles. Enter the
local course title currently used in your district. You do not need to change
your local course title.

### Common Errors

N/A

---

## LocalCourseCode

_Handbook page 26._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Alphanumeric Minimum Length: 1 Maximum Length: 20

### Validation Checks

- • An error will occur if this field is left blank.

### Additional Notes

• There is no state-wide standardized list of local course codes. Enter the
local course code currently used in your district. You do not need to change
your local course codes.

### Common Errors

N/A

---

## LocalSectionCode

_Handbook page 27._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Alphanumeric Minimum Length: 1 Maximum Length: 20

### Validation Checks

- • An error will occur if the field is left blank.

### Additional Notes

• There is no state-wide standardized list of local section codes. Enter the
local section code currently used in your district. You do not need to change
your local section codes.

### Common Errors

N/A

---

Total error conditions extracted: **54**.
