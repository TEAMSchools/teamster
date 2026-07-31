"""NJSLEDS Student Course Roster handbook rule catalog.

Transcribes every "An error will occur..." statement in
`handbook-rules-student.md` (Student Course Roster Submission Handbook,
Version 1.4, July 2026) into a `Rule`. There are 68 handbook statements; this
module exports exactly one `Rule` per statement, plus a small set of
`source="ktaf"` rules for local expectations the handbook itself does not
impose (see `rules.py`'s module docstring for why that distinction matters).

Several handbook elements require the SCED (School Courses for the Exchange of
Data) Subject Area / Course Identifier code to know whether a course is
"Secondary" or "Prior-to-Secondary" before a conditional requirement even
applies (e.g. GradeSpan is mandatory only for Prior-to-Secondary courses;
AvailableCredit and CreditsEarned only for Secondary courses). This file does
not have the SCED code list, so those conditional rules are marked
`checkable=False` rather than approximated - see each rule's
`uncheckable_reason`.
"""

from __future__ import annotations

from collections.abc import Callable

from rules import (
    Row,
    Rule,
    as_float,
    blank,
    in_window,
    is_date8,
    malformed,
    matches,
    present,
)

# --------------------------------------------------------------------------- #
# Shared format patterns.
# --------------------------------------------------------------------------- #

# FirstName/LastName: "any special characters except for apostrophes (') and
# hyphens (-)". Space is included for both fields, not just LastName: the
# LastName Additional Notes give a compound-name example with a plain space
# ("Davis Smyth"), and the real Newark/Camden files carry legitimately
# space-containing FirstName values too (78 rows across both files) - treating
# space as a disallowed "special character" for FirstName produced false
# positives against real data during validation, so it is allowed here for
# both name fields.
_NAME_PATTERN = r"[A-Za-z‘’' \-]+"

# GradeSpan: "each grade level from PK through 12... two-digit code... KG for
# kindergarten... PK for prekindergarten". A GradeSpan is two such codes
# concatenated (e.g. "KG01", "0810"); the handbook's own example does not
# require the two halves to be ordered low-to-high, so ordering is not
# enforced here.
_GRADE_SPAN_CODE = r"(?:PK|KG|0[1-9]|1[0-2])"
_GRADE_SPAN_PATTERN = _GRADE_SPAN_CODE + "{2}"

# CourseLevel: the valid set (B, G, E, H, X) is enumerated directly in the
# handbook's Acceptable Values, unlike SubjectArea/CourseIdentifier which defer
# to an external SCED document - so this one is checkable without that list.
_COURSE_LEVEL_PATTERN = r"[BGEHX]"

# AlphaGradeEarned: A/B/C/D/E/F, each optionally with + or -.
_ALPHA_GRADE_PATTERN = r"[A-F][+\-]?"

# CompletionStatus: P, F, W, I, NG.
_COMPLETION_STATUS_PATTERN = r"P|F|W|I|NG"


# --------------------------------------------------------------------------- #
# Predicate factories, for the repeated shapes (blank / format / date format /
# school-year window / numeric range).
# --------------------------------------------------------------------------- #


def _blank_check(column: str) -> Callable[[Row], bool]:
    """Factory: True when `column` is blank."""

    def check(row: Row) -> bool:
        return blank(row.get(column))

    return check


def _format_check(column: str, pattern: str) -> Callable[[Row], bool]:
    """Factory: True when a populated `column` fails to fullmatch `pattern`.

    Uses `malformed()`, not `not matches(...)`, so a blank `column` is silent
    here - blankness is its own rule where the handbook states one.
    """

    def check(row: Row) -> bool:
        return malformed(row.get(column), pattern)

    return check


def _date_format_check(column: str) -> Callable[[Row], bool]:
    """Factory: True when a populated `column` is not a real YYYYMMDD date."""

    def check(row: Row) -> bool:
        value = row.get(column)
        return present(value) and not is_date8(value)

    return check


def _school_year_check(column: str) -> Callable[[Row], bool]:
    """Factory: True when a validly-formatted `column` date is outside SY.

    Guarded on `is_date8` so a malformed date is attributed only to the
    element's own format rule, not double-counted here as a school-year miss
    too.
    """

    def check(row: Row) -> bool:
        value = row.get(column)
        return is_date8(value) and not in_window(value)

    return check


def _out_of_range(value: str | None, low: float, high: float) -> bool:
    """True when a populated value fails to parse as a number in [low, high].

    None of AvailableCredit/CreditsEarned/NumericGradeEarned has a separate
    format-only bullet, so a non-numeric populated value is treated as out of
    range too - the range bullet is the only Validation Check that would
    catch it.
    """
    if blank(value):
        return False
    parsed = as_float(value)
    return parsed is None or not (low <= parsed <= high)


def _range_check(column: str, low: float, high: float) -> Callable[[Row], bool]:
    """Factory: True when a populated `column` is outside [low, high]."""

    def check(row: Row) -> bool:
        return _out_of_range(row.get(column), low, high)

    return check


# --------------------------------------------------------------------------- #
# One-off cross-field predicates.
# --------------------------------------------------------------------------- #


def _entry_date_after_exit_date(row: Row) -> bool:
    """STU-SECTIONENTRYDATE-AFTER-EXIT: entry date later than exit date.

    Only evaluated when both dates are validly formatted, so a malformed date
    is attributed to its own format rule instead of this ordering rule too.
    """
    entry = row.get("SectionEntryDate")
    exit_date = row.get("SectionExitDate")
    if not (is_date8(entry) and is_date8(exit_date)):
        return False
    return str(entry).strip() > str(exit_date).strip()


def _exit_date_before_entry_date(row: Row) -> bool:
    """STU-SECTIONEXITDATE-BEFORE-ENTRY: exit date earlier than entry date.

    Same underlying comparison as `_entry_date_after_exit_date`, kept as a
    separate, separately-named function because it is a distinct handbook
    statement scoped to SectionExitDate rather than SectionEntryDate.
    """
    entry = row.get("SectionEntryDate")
    exit_date = row.get("SectionExitDate")
    if not (is_date8(entry) and is_date8(exit_date)):
        return False
    return str(exit_date).strip() < str(entry).strip()


def _course_sequence_first_digit_exceeds_second(row: Row) -> bool:
    """STU-COURSESEQUENCE-FIRSTDIGIT-GT-SECOND: first digit exceeds the second.

    Only evaluated when the value is a well-formed 2-digit sequence - there is
    no separate format bullet for CourseSequence, and the handbook's wording
    ("the value of the first digit... the second digit") presumes exactly two
    digits to compare.
    """
    value = row.get("CourseSequence")
    if not matches(value, r"\d{2}"):
        return False
    text = str(value).strip()
    return int(text[0]) > int(text[1])


def _credits_earned_exceeds_available(row: Row) -> bool:
    """STU-CREDITSEARNED-EXCEEDS-AVAILABLE: CreditsEarned > AvailableCredit."""
    earned = as_float(row.get("CreditsEarned"))
    available = as_float(row.get("AvailableCredit"))
    if earned is None or available is None:
        return False
    return earned > available


def _numeric_grade_not_whole(row: Row) -> bool:
    """STU-NUMERICGRADEEARNED-NOTWHOLE: a parseable value that is not whole."""
    parsed = as_float(row.get("NumericGradeEarned"))
    if parsed is None:
        return False
    return parsed != int(parsed)


def _dual_institution_blank_for_coursetype_c(row: Row) -> bool:
    """STU-DUALINSTITUTION-BLANK-COURSETYPE-C: CourseType C, DualInstitution blank."""
    course_type = str(row.get("CourseType") or "").strip()
    return course_type == "C" and blank(row.get("DualInstitution"))


def _dual_institution_populated_for_non_c(row: Row) -> bool:
    """STU-DUALINSTITUTION-POPULATED-NOT-C: DualInstitution set without CourseType C."""
    course_type = str(row.get("CourseType") or "").strip()
    return course_type != "C" and present(row.get("DualInstitution"))


# --------------------------------------------------------------------------- #
# KTAF-local rules (source="ktaf"). Never counted toward a state error total -
# see rules.py's module docstring and HANDOFF.md.
#
# The org-provided expectation was Newark county 80 / district 7325 / school
# 965, and Camden county 07 / district 1799 / school 111 (school unconfirmed).
# Profiling the real Newark and Camden student files against that expectation
# found:
#   - County and District match the given values exactly wherever populated
#     (Newark: county always "80" or blank, district always "7325"; Camden:
#     county always "07" or blank, district always "1799"). Both are encoded
#     below.
#   - School does NOT match: Newark legitimately uses two School Codes ("965"
#     and "732"), not only "965", and Camden's only School Code in the file is
#     "179", not "111". Encoding either single value as a KTAF check would
#     misfire on real rows, so no KTAF school-code rule is included. This
#     confirms the Camden "111" guess was wrong and that the org's
#     Newark-school assumption was incomplete; flagged in the report for the
#     org to confirm the intended KTAF CDS combinations before anyone builds
#     on "965"/"111" elsewhere.
# --------------------------------------------------------------------------- #

_KTAF_KNOWN_COUNTY_CODES = frozenset({"80", "07"})
_KTAF_KNOWN_DISTRICT_CODES = frozenset({"7325", "1799"})


def _county_code_not_ktaf_known(row: Row) -> bool:
    """KTAF-COUNTYCODE-KNOWN: populated County Code outside KTAF's known set."""
    value = row.get("CountyCodeAssigned")
    return present(value) and str(value).strip() not in _KTAF_KNOWN_COUNTY_CODES


def _district_code_not_ktaf_known(row: Row) -> bool:
    """KTAF-DISTRICTCODE-KNOWN: populated District Code outside KTAF's known set."""
    value = row.get("DistrictCodeAssigned")
    return present(value) and str(value).strip() not in _KTAF_KNOWN_DISTRICT_CODES


# --------------------------------------------------------------------------- #
# The catalog.
# --------------------------------------------------------------------------- #

RULES: list[Rule] = [
    # --- LocalIdentificationNumber (LID), handbook p11 ---------------------
    Rule(
        id="STU-LID-BLANK",
        element="LocalIdentificationNumber",
        page=11,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("LocalIdentificationNumber"),
    ),
    # --- StateIdentificationNumber (SID), handbook p12 ----------------------
    Rule(
        id="STU-SID-NOT10DIGITS",
        element="StateIdentificationNumber",
        page=12,
        error_text=(
            "An error will occur when the value submitted is not exactly 10 digits."
        ),
        checkable=True,
        predicate=_format_check("StateIdentificationNumber", r"\d{10}"),
    ),
    Rule(
        id="STU-SID-BLANK",
        element="StateIdentificationNumber",
        page=12,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("StateIdentificationNumber"),
    ),
    Rule(
        id="STU-SID-INVALID-ISSUED",
        element="StateIdentificationNumber",
        page=12,
        error_text=(
            "An error will occur when the State Identification Number is not "
            "a valid number issued by NJSLEDS."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs NJSLEDS's own record of SIDs it has issued; not derivable "
            "from the upload file alone."
        ),
        tags=("student-management",),
    ),
    Rule(
        id="STU-SID-MISMATCH-STUDENT-MGMT",
        element="StateIdentificationNumber",
        page=12,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Student Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the student's Student Management (state SIS) record to "
            "compare against; the Course Roster file has no such reference "
            "value."
        ),
        tags=("student-management",),
    ),
    # --- FirstName, handbook p13 ---------------------------------------------
    Rule(
        id="STU-FIRSTNAME-BLANK",
        element="FirstName",
        page=13,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("FirstName"),
    ),
    Rule(
        id="STU-FIRSTNAME-SPECIALCHARS",
        element="FirstName",
        page=13,
        error_text=(
            "An error will occur if this data element contains any special "
            "characters except for apostrophes (‘) and hyphens (-)."
        ),
        checkable=True,
        predicate=_format_check("FirstName", _NAME_PATTERN),
        notes=(
            "Allowed pattern also permits a space, matching the "
            "compound-name convention the handbook documents for LastName "
            "('Davis Smyth'); real Newark/Camden data has legitimate "
            "space-containing FirstName values, and disallowing space "
            "produced false positives during validation."
        ),
    ),
    Rule(
        id="STU-FIRSTNAME-MISMATCH-STUDENT-MGMT",
        element="FirstName",
        page=13,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Student Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the student's Student Management (state SIS) record to "
            "compare against; not present in the Course Roster file."
        ),
        tags=("student-management",),
    ),
    # --- LastName, handbook p14 -----------------------------------------------
    Rule(
        id="STU-LASTNAME-BLANK",
        element="LastName",
        page=14,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("LastName"),
    ),
    Rule(
        id="STU-LASTNAME-SPECIALCHARS",
        element="LastName",
        page=14,
        error_text=(
            "An error will occur if this data element contains any special "
            "characters except for apostrophes (‘) and hyphens (-)."
        ),
        checkable=True,
        predicate=_format_check("LastName", _NAME_PATTERN),
        notes=(
            "Allowed pattern includes a space per the handbook's own "
            "compound-surname example ('Davis Smyth')."
        ),
    ),
    Rule(
        id="STU-LASTNAME-MISMATCH-STUDENT-MGMT",
        element="LastName",
        page=14,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Student Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the student's Student Management (state SIS) record to "
            "compare against; not present in the Course Roster file."
        ),
        tags=("student-management",),
    ),
    # --- DateOfBirth, handbook p15 --------------------------------------------
    Rule(
        id="STU-DOB-BLANK",
        element="DateOfBirth",
        page=15,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("DateOfBirth"),
    ),
    Rule(
        id="STU-DOB-FORMAT",
        element="DateOfBirth",
        page=15,
        error_text=(
            "An error will occur if the date is not entered in YYYYMMDD "
            "format (for example, 20150128)."
        ),
        checkable=True,
        predicate=_date_format_check("DateOfBirth"),
    ),
    Rule(
        id="STU-DOB-REASONABLE-RANGE",
        element="DateOfBirth",
        page=15,
        error_text=(
            "An error will occur if the date falls outside of reasonable parameters (i."
        ),
        checkable=False,
        uncheckable_reason=(
            "The extracted handbook text is truncated mid-sentence before "
            "stating the actual bound ('reasonable parameters (i.' cuts "
            "off) - no threshold is given anywhere else in the element to "
            "encode without guessing."
        ),
        tags=("ambiguous",),
    ),
    Rule(
        id="STU-DOB-MISMATCH-STUDENT-MGMT",
        element="DateOfBirth",
        page=15,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Student Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the student's Student Management (state SIS) record to "
            "compare against; not present in the Course Roster file."
        ),
        tags=("student-management",),
    ),
    # --- CountyCodeAssigned, handbook p16 -------------------------------------
    Rule(
        id="STU-COUNTYCODE-BLANK",
        element="CountyCodeAssigned",
        page=16,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("CountyCodeAssigned"),
    ),
    Rule(
        id="STU-COUNTYCODE-NOT-IN-CDS",
        element="CountyCodeAssigned",
        page=16,
        error_text=(
            "An error will occur if the County Code submitted does not "
            "conform to the codes listed for your district in the CDS list."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the NJSLEDS County-District-School (CDS) code list for "
            "the submitting LEA; not present in the upload file. See "
            "KTAF-COUNTYCODE-KNOWN for a narrower local proxy."
        ),
        tags=("cds-list",),
    ),
    Rule(
        id="STU-COUNTYCODE-LEADINGZEROS",
        element="CountyCodeAssigned",
        page=16,
        error_text=(
            "An error will occur if required leading zeros are missing, "
            "resulting in an incorrect value format."
        ),
        checkable=True,
        predicate=_format_check("CountyCodeAssigned", r"\d{2}"),
        notes=(
            "Acceptable Values gives Min/Max Length 2; read here as a "
            "fixed-width 2-digit numeric check, which is exactly what a "
            "missing leading zero would violate. Populated values in the "
            "real Newark/Camden files are exclusively 2-digit numeric "
            "('80'/'07'), consistent with this reading."
        ),
    ),
    Rule(
        id="STU-COUNTYCODE-MISALIGN-STUDENT-MGMT",
        element="CountyCodeAssigned",
        page=16,
        error_text=(
            "An error will occur if the County Code, District Code, and "
            "School Code reported in Student Course Roster do not align "
            "with the corresponding Student Management record for the same "
            "student (SID)."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the student's Student Management (state SIS) record to "
            "compare the CDS triple against; not present in the Course "
            "Roster file."
        ),
        tags=("student-management",),
    ),
    # --- DistrictCodeAssigned, handbook p17 -----------------------------------
    Rule(
        id="STU-DISTRICTCODE-BLANK",
        element="DistrictCodeAssigned",
        page=17,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("DistrictCodeAssigned"),
    ),
    Rule(
        id="STU-DISTRICTCODE-MISMATCH-SUBMITTING",
        element="DistrictCodeAssigned",
        page=17,
        error_text=(
            "An error will occur if the District Code submitted does not "
            "match the Submitting District."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the identity of the LEA/account that submitted the file, "
            "which is not a column in the roster; see KTAF-DISTRICTCODE-"
            "KNOWN for a local proxy scoped to KTAF's known Newark/Camden "
            "district codes."
        ),
        tags=("submission-metadata",),
    ),
    Rule(
        id="STU-DISTRICTCODE-LEADINGZEROS",
        element="DistrictCodeAssigned",
        page=17,
        error_text=(
            "An error will occur if required leading zeros are missing, "
            "resulting in an incorrect value format."
        ),
        checkable=True,
        predicate=_format_check("DistrictCodeAssigned", r"\d{4}"),
        notes=(
            "Acceptable Values gives Min/Max Length 4; the real Newark/"
            "Camden files are exclusively 4-digit numeric ('7325'/'1799')."
        ),
    ),
    Rule(
        id="STU-DISTRICTCODE-MISALIGN-STUDENT-MGMT",
        element="DistrictCodeAssigned",
        page=17,
        error_text=(
            "An error will occur if the County Code, District Code, and "
            "School Code reported in Student Course Roster do not align "
            "with the corresponding Student Management record for the same "
            "student (SID)."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the student's Student Management (state SIS) record to "
            "compare the CDS triple against; not present in the Course "
            "Roster file."
        ),
        tags=("student-management",),
    ),
    # --- SchoolCodeAssigned, handbook p18 -------------------------------------
    Rule(
        id="STU-SCHOOLCODE-BLANK",
        element="SchoolCodeAssigned",
        page=18,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("SchoolCodeAssigned"),
    ),
    Rule(
        id="STU-SCHOOLCODE-NOT-IN-CDS",
        element="SchoolCodeAssigned",
        page=18,
        error_text=(
            "An error will occur if the School Code submitted does not "
            "conform to the codes listed for your district in the CDS list."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the NJSLEDS County-District-School (CDS) code list for "
            "the submitting LEA; not present in the upload file."
        ),
        notes=(
            "No KTAF-known-school-code rule is included below. The "
            "org-provided expectation (Newark school 965, Camden school "
            "111) does not hold against the real data used to build this "
            "catalog: the Newark file legitimately uses two School Codes "
            "(965 and 732), and the Camden file's only School Code is 179, "
            "not 111. Encoding either single value would misfire on real "
            "rows, so it was left out rather than approximated - flagged in "
            "the report for the org to confirm the correct KTAF CDS school "
            "combinations."
        ),
        tags=("cds-list",),
    ),
    Rule(
        id="STU-SCHOOLCODE-LEADINGZEROS",
        element="SchoolCodeAssigned",
        page=18,
        error_text=(
            "An error will occur if required leading zeros are missing, "
            "resulting in an incorrect value format."
        ),
        checkable=True,
        predicate=_format_check("SchoolCodeAssigned", r"\d{3}"),
        notes=(
            "Acceptable Values gives Min/Max Length 3; the real Newark/"
            "Camden files are exclusively 3-digit numeric ('965'/'732'/"
            "'179')."
        ),
    ),
    Rule(
        id="STU-SCHOOLCODE-NONOPERATIONAL",
        element="SchoolCodeAssigned",
        page=18,
        error_text=(
            "An error will occur if a School Code designated for a "
            "non-operational school is used."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the NJDOE list of school codes marked non-operational; "
            "not present in the upload file."
        ),
        tags=("cds-list",),
    ),
    Rule(
        id="STU-SCHOOLCODE-MISALIGN-STUDENT-MGMT",
        element="SchoolCodeAssigned",
        page=18,
        error_text=(
            "An error will occur if the County Code, District Code, and "
            "School Code reported in Student Course Roster do not align "
            "with the corresponding Student Management record for the same "
            "student (SID)."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the student's Student Management (state SIS) record to "
            "compare the CDS triple against; not present in the Course "
            "Roster file."
        ),
        tags=("student-management",),
    ),
    # --- SectionEntryDate, handbook p20 ---------------------------------------
    Rule(
        id="STU-SECTIONENTRYDATE-BLANK",
        element="SectionEntryDate",
        page=20,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("SectionEntryDate"),
    ),
    Rule(
        id="STU-SECTIONENTRYDATE-RANGE",
        element="SectionEntryDate",
        page=20,
        error_text=(
            "An error will occur if the value does not meet the acceptable "
            "range of values."
        ),
        checkable=False,
        uncheckable_reason=(
            "No date range or bound is stated in Acceptable Values beyond "
            "format and the separately-listed current-School-Year bullet; "
            "what distinct condition this bullet tests is not specified in "
            "the extracted text."
        ),
        tags=("ambiguous",),
    ),
    Rule(
        id="STU-SECTIONENTRYDATE-FORMAT",
        element="SectionEntryDate",
        page=20,
        error_text=(
            "An error will occur if the date is not entered in YYYYMMDD "
            "format (for example, 20250128)."
        ),
        checkable=True,
        predicate=_date_format_check("SectionEntryDate"),
    ),
    Rule(
        id="STU-SECTIONENTRYDATE-AFTER-EXIT",
        element="SectionEntryDate",
        page=20,
        error_text=(
            "An error will occur if the student course entry date occurs "
            "after the student course exit date."
        ),
        checkable=True,
        predicate=_entry_date_after_exit_date,
    ),
    Rule(
        id="STU-SECTIONENTRYDATE-NOT-IN-SY",
        element="SectionEntryDate",
        page=20,
        error_text=(
            "An error will occur if the SectionEntryDate does not occur in "
            "the current School Year."
        ),
        checkable=True,
        predicate=_school_year_check("SectionEntryDate"),
    ),
    # --- SectionExitDate, handbook p22 -----------------------------------------
    Rule(
        id="STU-SECTIONEXITDATE-BLANK",
        element="SectionExitDate",
        page=22,
        error_text="An error will occur if this field is left blank.",
        checkable=False,
        uncheckable_reason=(
            "SectionExitDate is mandatory only when the student is no "
            "longer active in the course (per the element's Required-ness "
            "note); whether blank is an error for a given row depends on "
            "the student's true enrollment status in that section, which "
            "the roster file exposes only via this same field - there is no "
            "independent active/inactive flag to check against without "
            "circularity."
        ),
        tags=("ambiguous",),
    ),
    Rule(
        id="STU-SECTIONEXITDATE-RANGE",
        element="SectionExitDate",
        page=22,
        error_text=(
            "An error will occur if the value does not meet the acceptable "
            "range of values."
        ),
        checkable=False,
        uncheckable_reason=(
            "No date range or bound is stated in Acceptable Values beyond "
            "format and the separately-listed current-School-Year bullet; "
            "what distinct condition this bullet tests is not specified in "
            "the extracted text."
        ),
        tags=("ambiguous",),
    ),
    Rule(
        id="STU-SECTIONEXITDATE-FORMAT",
        element="SectionExitDate",
        page=22,
        error_text=(
            "An error will occur if the date is not entered in YYYYMMDD "
            "format (for example, 20250128)."
        ),
        checkable=True,
        predicate=_date_format_check("SectionExitDate"),
    ),
    Rule(
        id="STU-SECTIONEXITDATE-BEFORE-ENTRY",
        element="SectionExitDate",
        page=22,
        error_text=(
            "An error will occur if the student course exit date occurs "
            "before the student course entry date."
        ),
        checkable=True,
        predicate=_exit_date_before_entry_date,
    ),
    Rule(
        id="STU-SECTIONEXITDATE-NOT-IN-SY",
        element="SectionExitDate",
        page=22,
        error_text=(
            "An error will occur if the SectionExitDate does not occur in "
            "the current School Year."
        ),
        checkable=True,
        predicate=_school_year_check("SectionExitDate"),
    ),
    Rule(
        id="STU-SECTIONEXITDATE-FUTURE",
        element="SectionExitDate",
        page=22,
        error_text=(
            "An error will occur if the SectionExitDate is later than the "
            "file submission date (for example, a future date)."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the actual NJSLEDS file-submission/upload date, which is "
            "not a column in the roster file. The wall-clock date this tool "
            "happens to run on is not a reliable stand-in for when the file "
            "was actually submitted, so it is not used as an approximation."
        ),
        tags=("submission-metadata",),
    ),
    # --- SubjectArea, handbook p23 ---------------------------------------------
    Rule(
        id="STU-SUBJECTAREA-BLANK",
        element="SubjectArea",
        page=23,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("SubjectArea"),
    ),
    Rule(
        id="STU-SUBJECTAREA-INVALID-SCED",
        element="SubjectArea",
        page=23,
        error_text=(
            "An error will occur if the value is not a valid SCED Subject Area code."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the NJSLEDS/NCES SCED Course Codes document listing "
            "valid Subject Area codes; not present in the upload file."
        ),
        tags=("sced",),
    ),
    # --- CourseIdentifier, handbook p24 -----------------------------------------
    Rule(
        id="STU-COURSEIDENTIFIER-BLANK",
        element="CourseIdentifier",
        page=24,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("CourseIdentifier"),
    ),
    Rule(
        id="STU-COURSEIDENTIFIER-INVALID-SCED",
        element="CourseIdentifier",
        page=24,
        error_text=(
            "An error will occur if the value is not a valid SCED Course "
            "Identifier code."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the NJSLEDS/NCES SCED Course Codes document listing "
            "valid Course Identifier codes; not present in the upload file."
        ),
        tags=("sced",),
    ),
    Rule(
        id="STU-COURSEIDENTIFIER-LEADINGZEROS",
        element="CourseIdentifier",
        page=24,
        error_text=(
            "An error will occur if required leading zeros are missing, "
            "resulting in an incorrect value format."
        ),
        checkable=True,
        predicate=_format_check("CourseIdentifier", r"\d{3}"),
    ),
    # --- CourseLevel, handbook p25 -----------------------------------------------
    Rule(
        id="STU-COURSELEVEL-BLANK",
        element="CourseLevel",
        page=25,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("CourseLevel"),
    ),
    Rule(
        id="STU-COURSELEVEL-INVALID",
        element="CourseLevel",
        page=25,
        error_text=(
            "An error will occur if the value is not a valid SCED Course Level code."
        ),
        checkable=True,
        predicate=_format_check("CourseLevel", _COURSE_LEVEL_PATTERN),
        notes=(
            "Unlike SubjectArea/CourseIdentifier, CourseLevel's valid set "
            "(B, G, E, H, X) is enumerated directly in the handbook's "
            "Acceptable Values rather than deferred to an external SCED "
            "document, so this is checkable without that list."
        ),
    ),
    # --- GradeSpan, handbook p26 --------------------------------------------------
    Rule(
        id="STU-GRADESPAN-BLANK-PRIORSECONDARY",
        element="GradeSpan",
        page=26,
        error_text=(
            "An error will occur if the field is left blank for a course "
            "with a Prior-To-Secondary course code."
        ),
        checkable=False,
        uncheckable_reason=(
            "Whether a course is Prior-to-Secondary is a property of its "
            "SubjectArea/CourseIdentifier combination on the SCED code "
            "list; needs that list to evaluate."
        ),
        tags=("sced",),
    ),
    Rule(
        id="STU-GRADESPAN-RANGE",
        element="GradeSpan",
        page=26,
        error_text=(
            "An error will occur if the value does not match the "
            "acceptable range of values."
        ),
        checkable=True,
        predicate=_format_check("GradeSpan", _GRADE_SPAN_PATTERN),
    ),
    # --- AvailableCredit, handbook p27 --------------------------------------------
    Rule(
        id="STU-AVAILABLECREDIT-BLANK-SECONDARY",
        element="AvailableCredit",
        page=27,
        error_text=(
            "An error will occur if this field is left blank for a course "
            "with a Secondary course code."
        ),
        checkable=False,
        uncheckable_reason=(
            "Whether a course is Secondary is a property of its "
            "SubjectArea/CourseIdentifier combination on the SCED code "
            "list; needs that list to evaluate."
        ),
        tags=("sced",),
    ),
    Rule(
        id="STU-AVAILABLECREDIT-RANGE",
        element="AvailableCredit",
        page=27,
        error_text=(
            "An error will occur if the value does not match the "
            "acceptable range of values."
        ),
        checkable=True,
        predicate=_range_check("AvailableCredit", 0.0, 35.0),
    ),
    # --- CourseSequence, handbook p28 ----------------------------------------------
    Rule(
        id="STU-COURSESEQUENCE-BLANK",
        element="CourseSequence",
        page=28,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("CourseSequence"),
    ),
    Rule(
        id="STU-COURSESEQUENCE-FIRSTDIGIT-GT-SECOND",
        element="CourseSequence",
        page=28,
        error_text=(
            "An error will occur if the value of the first digit is "
            "greater than the value of the second digit."
        ),
        checkable=True,
        predicate=_course_sequence_first_digit_exceeds_second,
    ),
    # --- LocalCourseTitle, handbook p29 ---------------------------------------------
    Rule(
        id="STU-LOCALCOURSETITLE-BLANK",
        element="LocalCourseTitle",
        page=29,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("LocalCourseTitle"),
    ),
    # --- LocalCourseCode, handbook p30 ----------------------------------------------
    Rule(
        id="STU-LOCALCOURSECODE-BLANK",
        element="LocalCourseCode",
        page=30,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_blank_check("LocalCourseCode"),
    ),
    # --- LocalSectionCode, handbook p31 ----------------------------------------------
    Rule(
        id="STU-LOCALSECTIONCODE-BLANK",
        element="LocalSectionCode",
        page=31,
        error_text="An error will occur if the field is left blank.",
        checkable=True,
        predicate=_blank_check("LocalSectionCode"),
    ),
    # --- CreditsEarned, handbook p32 -------------------------------------------------
    Rule(
        id="STU-CREDITSEARNED-BLANK",
        element="CreditsEarned",
        page=32,
        error_text="An error will occur if the field is left blank.",
        checkable=False,
        uncheckable_reason=(
            "Whether blank is actually an error depends on whether the "
            "course carries a Secondary code and the student has a "
            "SectionExitDate (per the element's Required-ness note); the "
            "Secondary/Prior-to-Secondary determination needs the SCED code "
            "list."
        ),
        tags=("sced",),
    ),
    Rule(
        id="STU-CREDITSEARNED-RANGE",
        element="CreditsEarned",
        page=32,
        error_text=(
            "An error will occur if the value does not match the "
            "acceptable range of values."
        ),
        checkable=True,
        predicate=_range_check("CreditsEarned", 0.0, 35.0),
    ),
    Rule(
        id="STU-CREDITSEARNED-REQUIRED-SECONDARY-EXITED",
        element="CreditsEarned",
        page=32,
        error_text=(
            "An error will occur if the value is not entered for students "
            "who have a SectionExitDate and a Secondary course code."
        ),
        checkable=False,
        uncheckable_reason=(
            "Whether a course is Secondary is a property of its "
            "SubjectArea/CourseIdentifier combination on the SCED code "
            "list; needs that list to evaluate."
        ),
        tags=("sced",),
    ),
    Rule(
        id="STU-CREDITSEARNED-EXCEEDS-AVAILABLE",
        element="CreditsEarned",
        page=32,
        error_text=(
            "An error will occur if CreditsEarned is greater than AvailableCredit."
        ),
        checkable=True,
        predicate=_credits_earned_exceeds_available,
    ),
    # --- NumericGradeEarned, handbook p34 --------------------------------------------
    Rule(
        id="STU-NUMERICGRADEEARNED-RANGE",
        element="NumericGradeEarned",
        page=34,
        error_text=(
            "An error will occur if the value does not match the "
            "acceptable range of values."
        ),
        checkable=True,
        predicate=_range_check("NumericGradeEarned", 0.0, 100.0),
    ),
    Rule(
        id="STU-NUMERICGRADEEARNED-NOTWHOLE",
        element="NumericGradeEarned",
        page=34,
        error_text=(
            "An error will occur if NumericGradeEarned is not entered as a "
            "whole number."
        ),
        checkable=True,
        predicate=_numeric_grade_not_whole,
    ),
    # --- AlphaGradeEarned, handbook p35 -----------------------------------------------
    Rule(
        id="STU-ALPHAGRADEEARNED-RANGE",
        element="AlphaGradeEarned",
        page=35,
        error_text=(
            "An error will occur if the value does not match the "
            "acceptable range of values."
        ),
        checkable=True,
        predicate=_format_check("AlphaGradeEarned", _ALPHA_GRADE_PATTERN),
    ),
    # --- CompletionStatus, handbook p36 -----------------------------------------------
    Rule(
        id="STU-COMPLETIONSTATUS-RANGE",
        element="CompletionStatus",
        page=36,
        error_text=(
            "An error will occur if the value does not match the "
            "acceptable range of values."
        ),
        checkable=True,
        predicate=_format_check("CompletionStatus", _COMPLETION_STATUS_PATTERN),
    ),
    # --- CourseType, handbook p37 --------------------------------------------------------
    Rule(
        id="STU-COURSETYPE-S1S2-NO-STAFF",
        element="CourseType",
        page=37,
        error_text=(
            "An error will occur if a student’s course type is S1 or "
            "S2 and that student does not have a staff member assigned to "
            "the course in the Staff Course Roster submission."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the Staff Course Roster submission to know which staff "
            "are assigned to the course section; not present in the "
            "Student Course Roster file."
        ),
        tags=("staff-roster",),
    ),
    Rule(
        id="STU-COURSETYPE-S2-SINGLESTAFF",
        element="CourseType",
        page=37,
        error_text=(
            "An error will occur if a value of S2 is entered for a student "
            "course that does not have more than one staff member assigned "
            "to the course."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the Staff Course Roster submission to know how many "
            "staff are assigned to the course section; not present in the "
            "Student Course Roster file."
        ),
        tags=("staff-roster",),
    ),
    # --- DualInstitution, handbook p39 --------------------------------------------------
    Rule(
        id="STU-DUALINSTITUTION-BLANK-COURSETYPE-C",
        element="DualInstitution",
        page=39,
        error_text=(
            "An error will occur if a student’s CourseType = C and "
            "DualInstitution is left blank."
        ),
        checkable=True,
        predicate=_dual_institution_blank_for_coursetype_c,
    ),
    Rule(
        id="STU-DUALINSTITUTION-POPULATED-NOT-C",
        element="DualInstitution",
        page=39,
        error_text=(
            "An error will occur if a student’s CourseType ≠ C "
            "and DualInstitution is populated."
        ),
        checkable=True,
        predicate=_dual_institution_populated_for_non_c,
    ),
    Rule(
        id="STU-DUALINSTITUTION-INVALID-OPEID",
        element="DualInstitution",
        page=39,
        error_text=(
            "An error will occur if the OPE ID Code does not match a valid "
            "code on the OPE ID List."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the NJSLEDS OPE ID List to validate against; not "
            "present in the upload file."
        ),
        tags=("ope-id",),
    ),
    # --- KTAF-local rules, source="ktaf" -------------------------------------------------
    Rule(
        id="KTAF-COUNTYCODE-KNOWN",
        element="CountyCodeAssigned",
        page=16,
        error_text=(
            "KTAF expectation, not a handbook rule: County Code, when "
            "populated, should be one of KTAF's known operating counties "
            "(Newark 80, Camden 07)."
        ),
        checkable=True,
        source="ktaf",
        predicate=_county_code_not_ktaf_known,
        notes=(
            "Corroborated against real data: every populated "
            "CountyCodeAssigned value in the Newark and Camden student "
            "files used to validate this catalog is exactly '80' or '07'. "
            "Blank rows are not flagged here - see STU-COUNTYCODE-BLANK, a "
            "handbook rule."
        ),
    ),
    Rule(
        id="KTAF-DISTRICTCODE-KNOWN",
        element="DistrictCodeAssigned",
        page=17,
        error_text=(
            "KTAF expectation, not a handbook rule: District Code should be "
            "one of KTAF's known districts (Newark 7325, Camden 1799)."
        ),
        checkable=True,
        source="ktaf",
        predicate=_district_code_not_ktaf_known,
        notes=(
            "Corroborated against real data: every DistrictCodeAssigned "
            "value in both the Newark and Camden student files used to "
            "validate this catalog is exactly '7325' or '1799' "
            "respectively, with no blanks."
        ),
    ),
]
