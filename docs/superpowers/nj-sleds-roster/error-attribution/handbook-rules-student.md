# NJSLEDS Student Course Roster — extracted validation rules

Source: Student Course Roster Submission Handbook, **Version 1.4**, July 2026.

Mechanically extracted from the handbook PDF so the rule catalog is built from
verbatim text rather than transcription. Do not hand-edit — regenerate if the
handbook is revised.

Data elements found: **25**.

---

## LocalIdentificationNumber (LID)

_Handbook page 11._

### Is this Data Element Required?

Yes. This field is mandatory for all students.

### Acceptable Values

Type: Alphanumeric Minimum Length: 1 Maximum Length: 20

### Validation Checks

- • An error will occur if this field is left blank.

### Additional Notes

• Type and length can vary based on a series of numbers and letters used by a
school district. A student’s LID must be unique throughout the student’s
enrollment in the district. For districts without LIDs, an LID scheme must be
created and assigned for all students so that the NJDOE can uniquely identify
all students in a particular district. • For LIDs that contain leading zeros, be
sure when extracting and storing the data for transmission that the zeros are
maintained. • It is important for confidentiality purposes that LIDs do not
contain any embedded meaning linked to student- specific information.

### Common Errors

Error Message: Duplicate student record with the same information exists in the
LEA. Resolution: Review the student’s course records to identify which courses
are duplicated. To resolve, upload a new file with each course record listed
once for each student.

---

## StateIdentificationNumber (SID)

_Handbook page 12._

### Is this Data Element Required?

Yes. This field is mandatory for students.

### Acceptable Values

Type: Numeric Minimum Length: 10 Maximum Length: 10

### Validation Checks

- • An error will occur when the value submitted is not exactly 10 digits.
- • An error will occur if this field is left blank.
- • An error will occur when the State Identification Number is not a valid
  number issued by NJSLEDS.
- • An error will occur if this field does not exactly match the value in
  Student Management.

### Additional Notes

• All submission files must include SIDs for students who have had SIDs issued.

### Common Errors

Error Message: Combination of State ID, First Name, Last Name, and Date of Birth
does not match data submitted during Student Management. Resolution: To resolve
this error, click on the Snapshot page in Student Management. Compare the values
of all four fields (SID, First Name, Last Name, and Date of Birth) in the record
against the fields in the Student Course Roster submission. All four fields in
the Student Course Roster submission must match exactly to the Student Snapshot
page, and the record on the Snapshot must be free of Error, Sync, Transfer
Requests, and Unresolved. Make the necessary changes within your Student
Information System (SIS) and then re-export and re-upload to the Student Course
Roster submission to resolve the combination error.

---

## FirstName

_Handbook page 13._

### Is this Data Element Required?

Yes. This field is mandatory for all students.

### Acceptable Values

Type: Alpha Minimum Length: 1 Maximum Length: 30

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if this data element contains any special characters
  except for apostrophes (‘) and hyphens (-).
- • An error will occur if this field does not exactly match the value in
  Student Management.

### Additional Notes

• First names and last names must be reported as separate fields. • No nicknames
or abbreviated names should be reported.

### Common Errors

N/A

---

## LastName

_Handbook page 14._

### Is this Data Element Required?

Yes. This field is mandatory for all students.

### Acceptable Values

Type: Alpha Minimum Length: 1 Maximum Length: 50

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if this data element contains any special characters
  except for apostrophes (‘) and hyphens (-).
- • An error will occur if this field does not exactly match the value in
  Student Management.

### Additional Notes

• First name and last name must be reported as separate fields. • Students with
more than one last name should include all last names in this field. Hyphens may
be used if they are part of the legal name (e.g., Smith-Jones). Names without
hyphens should be entered with a space (e.g., Davis Smyth).

### Common Errors

N/A

---

## DateOfBirth

_Handbook page 15._

### Is this Data Element Required?

Yes. This field is mandatory for all students.

### Acceptable Values

Type: Date Minimum Length: 8 Maximum Length: 8 Format: YYYYMMDD

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the date is not entered in YYYYMMDD format (for
  example, 20150128).
- • An error will occur if the date falls outside of reasonable parameters (i.
- • An error will occur if this field does not exactly match the value in
  Student Management.

### Additional Notes

N/A

### Common Errors

N/A

---

## CountyCodeAssigned

_Handbook page 16._

### Is this Data Element Required?

Yes. This field is The New Jersey County in which the student is currently
assigned to the course. for all students.

### Acceptable Values

Type: Character Minimum Length: 2 Maximum Length: 2 For County Codes, please
refer to the NJSLEDS County District School Code List, found on the Key
Documents page on the NJSLEDS User Resources website.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the County Code submitted does not conform to the
  codes listed for your district in the CDS list.
- • An error will occur if required leading zeros are missing, resulting in an
  incorrect value format.
- • An error will occur if the County Code, District Code, and School Code
  reported in Student Course Roster do not align with the corresponding Student
  Management record for the same student (SID).

### Additional Notes

• The CountyCodeAssigned should reflect the accurate County Code for the
specific course section.

### Common Errors

N/A

---

## DistrictCodeAssigned

_Handbook page 17._

### Is this Data Element Required?

Yes. This field is mandatory for all students.

### Acceptable Values

Type: Character Minimum Length: 4 Maximum Length: 4 For District Codes, please
refer to the NJSLEDS County District School Code List, found on the Key
Documents page on the NJSLEDS User Resources website.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the District Code submitted does not match the
  Submitting District.
- • An error will occur if required leading zeros are missing, resulting in an
  incorrect value format.
- • An error will occur if the County Code, District Code, and School Code
  reported in Student Course Roster do not align with the corresponding Student
  Management record for the same student (SID).

### Additional Notes

• The DistrictCodeAssigned should reflect the accurate District Code for the
specific course section.

### Common Errors

N/A

---

## SchoolCodeAssigned

_Handbook page 18._

### Is this Data Element Required?

Yes. This field is mandatory for all students.

### Acceptable Values

Type: Character Minimum Length: 3 Maximum Length: 3 For School Codes, please
refer to the NJSLEDS County District School Code List, found on the Key
Documents page on the NJSLEDS User Resources website.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the School Code submitted does not conform to the
  codes listed for your district in the CDS list.
- • An error will occur if required leading zeros are missing, resulting in an
  incorrect value format.
- • An error will occur if a School Code designated for a non-operational school
  is used.
- • An error will occur if the County Code, District Code, and School Code
  reported in Student Course Roster do not align with the corresponding Student
  Management record for the same student (SID).

### Additional Notes

• The SchoolCodeAssigned should reflect the accurate School Code for the
specific course section.

### Common Errors

N/A

---

## SectionEntryDate

_Handbook page 20._

### Is this Data Element Required?

Yes. This field is mandatory for all students.

### Acceptable Values

Type: Date Minimum Length: 8 Maximum Length: 8 Format: YYYYMMDD

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value does not meet the acceptable range of
  values.
- • An error will occur if the date is not entered in YYYYMMDD format (for
  example, 20250128).
- • An error will occur if the student course entry date occurs after the
  student course exit date.
- • An error will occur if the SectionEntryDate does not occur in the current
  School Year.

### Additional Notes

• Report each continuous period of enrollment in a section as a separate record.
If a student enters a course sections, exits, and later re-enters the same
course section within the School Year, submit multiple records to reflect each
enrollment period. If records were submitted in error, please submit a delete
request. Section Entry and Section Exit dates are used in the mSGP calculation
to determine the time in course for the student. For more information on how an
mSGP is calculated, please review the Median Student Growth Percentiles page.

### Common Errors

Error Message: Date must be in the current school year. Resolution: Review the
SectionEntryDate reported for the student’s course section and confirm that it
reflects the date the student began attending that specific course section
during the current school year. If the date is outside the current school year,
correct the value in the Student Information System, re-export, and re-upload
the file. If the student’s course section record already exists in NJSLEDS, do
not change the SectionEntryDate unless the original date was incorrect. Because
NJSLEDS is a target system, changing key course roster information may result in
an additional record being created rather than updating the existing record. If
the student exited and later

---

## SectionExitDate

_Handbook page 22._

### Is this Data Element Required?

Sometimes. This field is mandatory for all students who are no longer active in
the course. Otherwise, this field is not mandatory and should be left blank.

### Acceptable Values

Type: Date Minimum Length: 8 Maximum Length: 8 Format: YYYYMMDD

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value does not meet the acceptable range of
  values.
- • An error will occur if the date is not entered in YYYYMMDD format (for
  example, 20250128).
- • An error will occur if the student course exit date occurs before the
  student course entry date.
- • An error will occur if the SectionExitDate does not occur in the current
  School Year.
- • An error will occur if the SectionExitDate is later than the file submission
  date (for example, a future date).

### Additional Notes

• Report each continuous period of enrollment in a section as a separate record.
If a student enters a course sections, exits, and later re-enters the same
course section within the School Year, submit multiple records to reflect each
enrollment period. Do not overwrite earlier exit/entry dates with the most
recent entry date. • Section Entry and Section Exit dates are used in the mSGP
calculation to determine the time in course for the student. For more
information on how an mSGP is calculated, please review the Median Student
Growth Percentiles page.

### Common Errors

N/A

---

## SubjectArea

_Handbook page 23._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Numeric Minimum Length: 2 Maximum Length: 2 For Subject Area Codes, please
refer to the NJSLEDS SCED Course Codes document, found on the Key Documents page
of the NJSLEDS User Resources website.

### Validation Checks

- • An error will occur if this field is left blank.
- • An error will occur if the value is not a valid SCED Subject Area code.

### Additional Notes

• You will need to work cooperatively with your curriculum coordinator to assign
the appropriate subject area code. Some courses will require your professional
judgement. • Prior-to-secondary course codes should be used for all courses that
do not have Available Credit. Secondary course codes should be used for all
courses that have an Available Credit of greater than 0.000. • Students reported
with a Subject Area of 51, 52, or 73 may affect a staff member’s mSGP . For more
information on how an mSGP is calculated, please review the Median Student
Growth Percentiles page.

### Common Errors

N/A

---

## CourseIdentifier

_Handbook page 24._

### Is this Data Element Required?

Yes. This field is mandatory for all courses.

### Acceptable Values

Type: Numeric Minimum Length: 3 Maximum Length: 3 For Course Identifier Codes,
please refer to the NJSLEDS SCED Course Codes document, found on the Key
Documents page of the NJSLEDS User Resources website.

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

_Handbook page 25._

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

_Handbook page 26._

### Is this Data Element Required?

This field is mandatory for all prior-to-secondary courses. This field is not
mandatory for secondary courses and can be blank.

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

_Handbook page 27._

### Is this Data Element Required?

This field is mandatory for all secondary courses. This field is not mandatory
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

Error Message: Field must be a value in the range 0.000 to 35.000. Resolution:
Verify that the value reported to this field falls in the appropriate range and
includes three decimal places in your source system. Re-export and re-upload the
file to NJSLEDS to the Student Course Roster Submission to resolve the error.

---

## CourseSequence

_Handbook page 28._

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

_Handbook page 29._

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

_Handbook page 30._

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

_Handbook page 31._

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

## CreditsEarned

_Handbook page 32._

### Is this Data Element Required?

This field is mandatory for all students in courses with Secondary course codes
who are no longer active in the course and have been assigned a SectionExitDate.
Otherwise, this field is not mandatory.

### Acceptable Values

Type: Numeric with decimal point Minimum Length: 5 Maximum Length: 6 Values:
0.000-35.000

### Validation Checks

- • An error will occur if the field is left blank.
- • An error will occur if the value does not match the acceptable range of
  values.
- • An error will occur if the value is not entered for students who have a
  SectionExitDate and a Secondary course code.
- • An error will occur if CreditsEarned is greater than AvailableCredit.

### Additional Notes

• Decimal points are accepted in this field.

### Common Errors

Error Message: Field must be a value in the range 0.000 to 35.000. Resolution:
Verify that the value reported to this data element falls in the appropriate
range and includes three decimal places in your source system. Re-export and
re-upload the file to the Student Course Roster submission to resolve the error.

---

## NumericGradeEarned

_Handbook page 34._

### Is this Data Element Required?

• All students with a SectionExitDate entered for Secondary course codes with an
available credit of greater than 0.000 must have either the NumericGradeEarned,
AlphaGradeEarned, or CompletionStatus field filled in. • All students with a
SectionExitDate entered for Prior-to-secondary course codes with an grade span
of 060X or higher (where X is replaced with a full GradeSpan such as 0606, 0607,
0608, and so on) must have either the NumericGradeEarned, AlphaGradeEarned, or
CompletionStatus field filled in. • NumericGradeEarned field is mandatory for
the aforementioned students if AlphaGradeEarned and CompletionStatus are left
blank.

### Acceptable Values

Type: Numeric Minimum Length: 1 Maximum Length: 3 Values: 0-100

### Validation Checks

- • An error will occur if the value does not match the acceptable range of
  values.
- • An error will occur if NumericGradeEarned is not entered as a whole number.

### Additional Notes

• NumericGradeEarned is not a weighted value. If the highest allowed numeric
grade is greater than 100, convert it to a percentage grade that falls within
the acceptable values. • Range of Values provided for CompletionStatus,
NumericGradeEarned, and AlphaGradeEarned will not be expanded for the current
collection. Continue to maintain your local records to account for any necessary
data that is not collected in the Course Roster submission.

### Common Errors

N/A

---

## AlphaGradeEarned

_Handbook page 35._

### Is this Data Element Required?

• All students with a SectionExitDate entered for Secondary course codes with an
available credit of greater than 0.000 must have either the NumericGradeEarned,
AlphaGradeEarned, or CompletionStatus field filled in. • All students with a
SectionExitDate entered for Prior-to-secondary course codes with an grade span
of 060X or higher (where X is replaced with a full GradeSpan such as 0606, 0607,
0608, and so on) must have either the NumericGradeEarned, AlphaGradeEarned, or
CompletionStatus field filled in. • AlphaGradeEarned field is mandatory for the
aforementioned students if NumericGradeEarned and CompletionStatus are left
blank.

### Acceptable Values

Type: Character Minimum Length: 1 Maximum Length: 2 Values: A, A+, A-, B, B+,
B-, C, C+, C-, D, D+, D-, E, E+, E-, F , F+, F-

### Validation Checks

- • An error will occur if the value does not match the acceptable range of
  values.

### Additional Notes

• E, E+ and E- refer to a grade and not “Exempt”. • Range of Values provided for
CompletionStatus, NumericGradeEarned, and AlphaGradeEarned will not be expanded
for the current collection. Continue to maintain your local records to account
for any necessary data that is not collected in the Course Roster submission.

### Common Errors

N/A

---

## CompletionStatus

_Handbook page 36._

### Is this Data Element Required?

• All students with a SectionExitDate entered for Secondary course codes with an
available credit of greater than 0.000 must have either the NumericGradeEarned,
AlphaGradeEarned, or CompletionStatus field filled in. • All students with a
SectionExitDate entered for Prior-to-secondary course codes with an grade span
of 060X or higher (where X is replaced with a full GradeSpan such as 0606, 0607,
0608, and so on) must have either the NumericGradeEarned, AlphaGradeEarned, or
CompletionStatus field filled in. • CompletionStatus field is mandatory for the
aforementioned students if NumericGradeEarned and AlphaGradeEarned are left
blank.

### Acceptable Values

Type: Alpha Minimum Length: 1 Maximum Length: 2 Values: • P = Pass • F = Fail •
W = Withdrawal • I = Incomplete • NG = No grade earned

### Validation Checks

- • An error will occur if the value does not match the acceptable range of
  values.

### Additional Notes

• Range of Values provided for CompletionStatus, NumericGradeEarned, and
AlphaGradeEarned will not be expanded for the current collection. Continue to
maintain your local records to account for any necessary data that is not
collected in the Course Roster submission.

### Common Errors

N/A

---

## CourseType

_Handbook page 37._

### Is this Data Element Required?

Yes. This field is mandatory for all students.

### Acceptable Values

Type: Alphanumeric Minimum Length: 1 Maximum Length: 2 Values: • S1 = Standard
course taught by a single teacher assigned to your district • S2 = Standard
course taught by co-teachers assigned to your district • R = Remote course
physically attended by the student off-site and taught by staff assigned or not
assigned to your district • C = College level dual enrollment/dual credit course
taught by staff assigned or not assigned to your district • O = Online course
taught by staff assigned or not assigned to your district

### Validation Checks

- • An error will occur if a student’s course type is S1 or S2 and that student
  does not have a staff member assigned to the course in the Staff Course Roster
  submission.
- • An error will occur if a value of S2 is entered for a student course that
  does not have more than one staff member assigned to the course.

### Additional Notes

• The majority of the course sections reported will be reported with a
CourseType of S1 or S2. • Course Type C should only be used if there is an
existing articulation agreement between the high school and a college or
university. • Staff course data is required only for student courses that have a
CourseType of S1 or S2. If a course section has a CourseType of R, C, or O and
the course is taught by a staff member not assigned to your district, do not
report a staff record to the Staff Course Roster submission. This student record
will not be placed into Out-of- Sync when uploaded. • Course Types R, C, and O
are exceptions to the Course Roster Submission reporting responsibilities. In
most cases, these courses are taught by staff not assigned to your district.
These CourseType values have been developed to allow an opportunity to report
these courses regardless of the lack of staff data. If the staff member taught
the course and is assigned to your district, you should report the staff member
to the Staff

---

## DualInstitution

_Handbook page 39._

### Is this Data Element Required?

This field is mandatory for student course records with a CourseType = C
(College level dual enrollment/dual credit course taught by staff assigned or
not assigned to your district). Otherwise, this field is not mandatory.

### Acceptable Values

Type: Numeric Minimum Length: 8 Maximum Length: 8 For OPE ID Codes, please refer
to the NJSLEDS OPE ID List, found on the Key Documents page of the NJSLEDS User
Resources website.

### Validation Checks

- • An error will occur if a student’s CourseType = C and DualInstitution is
  left blank.
- • An error will occur if a student’s CourseType ≠ C and DualInstitution is
  populated.
- • An error will occur if the OPE ID Code does not match a valid code on the
  OPE ID List.

### Additional Notes

• The DualInstitution field (and CourseType of C) should only be used if there
is an existing articulation agreement between the high school and a college or
university.

### Common Errors

N/A

---

Total error conditions extracted: **68**.
