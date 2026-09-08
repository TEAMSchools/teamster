"""NJSLEDS Student Course Roster handbook rule catalog.

Transcribes every "An error will occur..." statement in
`handbook-rules-student.md` (Student Course Roster Submission Handbook,
Version 1.4, July 2026) into a `Rule`. There are 68 such statements, each
transcribed from an element's Validation Checks section, plus one further
handbook rule (`STU-GRADE-COMPLETION-REQUIRED`) added deliberately rather than
transcribed, for a requirement stated only under an element's "Is this Data
Element Required?" section with no matching Validation Checks bullet - see
`rules.py`'s module docstring for that methodology limit. That is 69
`source="handbook"` rules in total, plus a small set of `source="ktaf"` rules
for local expectations the handbook itself does not impose (see `rules.py`'s
module docstring for why that distinction matters).

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
    NAME_PATTERN,
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

# FirstName/LastName. Shared with the staff catalog, which words the same rule
# identically - see rules.py for the pattern and the judgement calls behind it
# (space allowed, both apostrophe forms allowed, accented letters treated as
# letters).
_NAME_PATTERN = NAME_PATTERN

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
# The CDS combinations KTAF reports under, set by the data team: Newark county
# 80 / district 7325 / school 965, and Camden county 07 / district 1799 /
# school 111.
#
# These rules are EXPECTED to fire heavily, and that is the point. The real
# files carry school code 732 on a large block of Newark rows and 179 on every
# populated-CDS Camden row. Those are not alternative valid codes - they are the
# documented CDS defect: the Alternate School Number is unset in PowerSchool
# School Setup for those schools, so the extract falls back to a prefix of the
# internal school number. As of the 2026-07-29 extract this affected 20,652 of
# 43,493 student rows, including every Camden row.
#
# An earlier draft of this catalog omitted the school-code rule entirely,
# reasoning that 965/111 "does not match real data" and would misfire. It would
# not misfire - it would correctly flag a wholly non-compliant file. Reference
# values come from the data team or the NJDOE directory, never from the file
# under test. See rules.py's module docstring.
#
# Camden's 111 is still worth confirming against the NJDOE directory before
# anyone keys it into School Setup.
# --------------------------------------------------------------------------- #

_KTAF_KNOWN_COUNTY_CODES = frozenset({"80", "07"})
_KTAF_KNOWN_DISTRICT_CODES = frozenset({"7325", "1799"})
_KTAF_KNOWN_CDS_COMBOS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("80", "7325", "965"),  # Newark
        ("07", "1799", "111"),  # Camden
    }
)


def _county_code_not_ktaf_known(row: Row) -> bool:
    """KTAF-COUNTYCODE-KNOWN: populated County Code outside KTAF's known set."""
    value = row.get("CountyCodeAssigned")
    return present(value) and str(value).strip() not in _KTAF_KNOWN_COUNTY_CODES


def _district_code_not_ktaf_known(row: Row) -> bool:
    """KTAF-DISTRICTCODE-KNOWN: populated District Code outside KTAF's known set."""
    value = row.get("DistrictCodeAssigned")
    return present(value) and str(value).strip() not in _KTAF_KNOWN_DISTRICT_CODES


def _ktaf_cds_combo_invalid(row: Row) -> bool:
    """KTAF-CDS-COMBO: the CDS triple is not one KTAF reports under.

    A blank component cannot form a valid combination, so a blank county counts
    as a violation here. That is deliberate - the state attributes the row by the
    whole triple, and an incomplete triple mis-attributes it just as a wrong one
    does.
    """
    combo = (
        str(row.get("CountyCodeAssigned", "") or "").strip(),
        str(row.get("DistrictCodeAssigned", "") or "").strip(),
        str(row.get("SchoolCodeAssigned", "") or "").strip(),
    )
    return combo not in _KTAF_KNOWN_CDS_COMBOS


# GradeSpan tokens in scope for the Prior-to-secondary "060X or higher" proxy
# below. KG and PK must be excluded by this explicit membership test rather
# than a range comparison: as strings, "KG" and "PK" both sort ABOVE "06"
# (letters sort above digits), so a naive `token >= "06"` bound - read from
# the handbook's "or higher" wording - would wrongly include them. Bounding
# above at "12" does not save a range check either, since "KG"/"PK" also sort
# above "12" and so would still need a separate exclusion; membership in the
# concrete set is the only reading that cannot mis-admit KG/PK.
_KTAF_GRADE_SPAN_SECONDARY_SCOPE = frozenset({"06", "07", "08", "09", "10", "11", "12"})


def _grade_completion_missing_heuristic(row: Row) -> bool:
    """KTAF-GRADE-COMPLETION-MISSING-HEURISTIC: proxy for
    STU-GRADE-COMPLETION-REQUIRED (checkable=False - see that rule).

    Fires when SectionExitDate is populated, NumericGradeEarned,
    AlphaGradeEarned, and CompletionStatus are all blank, and the row is in
    scope by proxy for one of the handbook's two triggering conditions:

    - AvailableCredit parses as a number greater than 0 (proxy for a
      Secondary course code with available credit), or
    - GradeSpan is populated and its first two characters are a grade token
      06-12 (proxy for a Prior-to-secondary course code with a grade span of
      060X or higher).

    Both proxies substitute for the real test, which needs the NCES SCED
    code list this tool does not have - see STU-GRADE-COMPLETION-REQUIRED's
    `uncheckable_reason`.
    """
    if blank(row.get("SectionExitDate")):
        return False
    if not (
        blank(row.get("NumericGradeEarned"))
        and blank(row.get("AlphaGradeEarned"))
        and blank(row.get("CompletionStatus"))
    ):
        return False
    available_credit = as_float(row.get("AvailableCredit"))
    if available_credit is not None and available_credit > 0:
        return True
    grade_span = row.get("GradeSpan")
    if present(grade_span):
        token = str(grade_span).strip()[:2]
        if token in _KTAF_GRADE_SPAN_SECONDARY_SCOPE:
            return True
    return False


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
            "Acceptable Values gives Min/Max Length 2. The handbook's own "
            "'leading zeros' bullet only makes sense if the field's content "
            "is numeric digit positions - a true alphabetic value has no "
            "notion of a missing leading zero. That implication, not what "
            "any particular file contains, is what justifies reading this "
            "as a fixed-width 2-digit numeric check."
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
            "Acceptable Values gives Min/Max Length 4; the same reasoning "
            "as STU-COUNTYCODE-LEADINGZEROS applies at this width - the "
            "handbook's own 'leading zeros' bullet only makes sense for "
            "numeric digit content, which is what justifies a fixed-width "
            "4-digit numeric check here, independent of what any file "
            "contains."
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
            "A KTAF school-code expectation IS encoded below, as part of "
            "KTAF-CDS-COMBO (County+District+School together: Newark "
            "80/7325/965, Camden 07/1799/111). An earlier version of this "
            "note argued the opposite - that expecting 965/111 'does not "
            "hold against real data' because the file then in hand showed "
            "732 and 179 - and left the rule out entirely. That reasoning "
            "was wrong: 732 and 179 were the PowerSchool School Setup "
            "defect (Alternate School Number unset, so the extract fell "
            "back to a prefix of the internal school number), not valid "
            "alternative codes. The 2026-07-31 extract carries the correct "
            "965/111 codes on every row, confirming the original "
            "expectation rather than the substitution. See KTAF-CDS-COMBO's "
            "own notes, and rules.py's module docstring, for the fuller "
            "account."
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
            "Acceptable Values gives Min/Max Length 3; the same reasoning "
            "applies at this width. The check rests on the handbook's own "
            "'leading zeros' bullet implying numeric digit content, not on "
            "what any file contains - in particular, not on 732 or 179, "
            "which KTAF-CDS-COMBO's notes document as the PowerSchool "
            "School Setup defect rather than valid codes."
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
    # --- Grade-or-completion mandate, handbook pp34-36 (Is this Data Element
    # Required?, not Validation Checks - see rules.py's module docstring for
    # why this rule has no Validation-Checks-transcribed counterpart) -------
    Rule(
        id="STU-GRADE-COMPLETION-REQUIRED",
        element="NumericGradeEarned+AlphaGradeEarned+CompletionStatus",
        page=34,
        error_text=(
            "All students with a SectionExitDate entered for Secondary "
            "course codes with an available credit of greater than 0.000 "
            "must have either the NumericGradeEarned, AlphaGradeEarned, or "
            "CompletionStatus field filled in. All students with a "
            "SectionExitDate entered for Prior-to-secondary course codes "
            "with an grade span of 060X or higher (where X is replaced with "
            "a full GradeSpan such as 0606, 0607, 0608, and so on) must "
            "have either the NumericGradeEarned, AlphaGradeEarned, or "
            "CompletionStatus field filled in."
        ),
        checkable=False,
        uncheckable_reason=(
            "Deciding whether a course is Secondary or Prior-to-secondary "
            "requires the NCES SCED (School Courses for the Exchange of "
            "Data) code list to classify the course's SubjectArea/"
            "CourseIdentifier combination; the upload file does not contain "
            "that list."
        ),
        notes=(
            "This is stated identically under 'Is this Data Element "
            "Required?' on pages 34 (NumericGradeEarned), 35 "
            "(AlphaGradeEarned), and 36 (CompletionStatus) - error_text is "
            "quoted from the NumericGradeEarned section verbatim, including "
            "its 'an grade span' wording. None of the three elements' "
            "Validation Checks sections has a matching blank-check bullet, "
            "which is why the original transcription pass never produced a "
            "rule for this requirement; see rules.py's module docstring. A "
            "checkable proxy is provided separately as "
            "KTAF-GRADE-COMPLETION-MISSING-HEURISTIC, below, using "
            "AvailableCredit and GradeSpan in place of the SCED list - it is "
            "a KTAF rule, not this handbook rule, and is never counted "
            "toward a state error total."
        ),
        tags=("sced",),
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
    Rule(
        id="KTAF-CDS-COMBO",
        element="CountyCodeAssigned+DistrictCodeAssigned+SchoolCodeAssigned",
        page=0,
        error_text=(
            "KTAF expectation, not a handbook rule: County, District, and "
            "School Code together must match one of the CDS combinations KTAF "
            "reports under - Newark (80, 7325, 965) or Camden (07, 1799, 111)."
        ),
        checkable=True,
        source="ktaf",
        predicate=_ktaf_cds_combo_invalid,
        notes=(
            "Passes clean as of the 2026-07-31 extract: both student files "
            "carry the correct triple on every row. It did not before. The "
            "2026-07-29 extract carried 732 on a large block of Newark rows "
            "and 179 on every populated-CDS Camden row - 20,652 of 43,493 "
            "rows - because the Alternate School Number was unset in "
            "PowerSchool School Setup, so the extract fell back to a prefix "
            "of the internal school number. The School Setup fix landed "
            "between those two extracts, which also confirms 111 as Camden's "
            "real code.\n\n"
            "Do not retune the expected codes to match what a file "
            "contains - see rules.py's module docstring for why an earlier "
            "draft dropped this rule entirely and what that would have cost."
        ),
        tags=("cds_list",),
    ),
    Rule(
        id="KTAF-GRADE-COMPLETION-MISSING-HEURISTIC",
        element="NumericGradeEarned+AlphaGradeEarned+CompletionStatus",
        page=0,
        error_text=(
            "KTAF heuristic, not a handbook rule: SectionExitDate is "
            "populated, NumericGradeEarned/AlphaGradeEarned/CompletionStatus "
            "are all blank, and the row proxies into scope for the "
            "handbook's grade-or-completion mandate (STU-GRADE-COMPLETION-"
            "REQUIRED, checkable=False) via AvailableCredit > 0 or a "
            "GradeSpan of 06-12."
        ),
        checkable=True,
        source="ktaf",
        predicate=_grade_completion_missing_heuristic,
        notes=(
            "This is a proxy for STU-GRADE-COMPLETION-REQUIRED, not the "
            "handbook rule itself - it substitutes AvailableCredit and "
            "GradeSpan for the NCES SCED code list that rule actually needs "
            "to decide Secondary vs. Prior-to-secondary, so it can both "
            "over- and under-fire relative to what the state actually "
            "checks. As a KTAF rule it is never counted toward a state "
            "error total; it exists to give an analyst a number to act on "
            "the same day, not a verified violation count.\n\n"
            "On the 2026-07-31 extract this is expected to fire on roughly "
            "28,727 rows across the two student files, because the "
            "submitted file is the raw PowerSchool extract without the "
            "grade backfill applied - most rows with a SectionExitDate "
            "genuinely have no grade or completion status recorded yet."
        ),
        tags=("sced", "ambiguous"),
    ),
    Rule(
        id="KTAF-COURSETYPE-BLANK",
        element="CourseType",
        page=37,
        error_text=(
            "KTAF expectation, not a handbook rule: CourseType, when "
            "blank, is flagged directly. The handbook states under 'Is "
            "this Data Element Required?' that CourseType is mandatory for "
            "all students, but its Validation Checks section has no "
            "matching blank-check bullet to transcribe (only the S1/S2 "
            "staff-assignment checks), so no handbook rule encodes this."
        ),
        checkable=True,
        source="ktaf",
        predicate=_blank_check("CourseType"),
        notes=(
            "Substitutes for the missing Validation Check, not a state "
            "rule - the state may or may not actually reject a blank "
            "CourseType, and this cannot be counted toward its error total. "
            "Reports 0 on the 2026-07-31 files: CourseType is populated on "
            "every row in both student files."
        ),
        tags=("ambiguous",),
    ),
]
