"""NJSLEDS Staff Course Roster validation rule catalog.

Transcribes every "An error will occur..." statement from the Staff Course
Roster Submission Handbook v1.1 (May 2026), as extracted verbatim into
`handbook-rules-staff.md`, into one `Rule` (see `rules.py`) per statement.
There are 54 handbook statements across 19 data elements; this module
constructs exactly 54 `source="handbook"` rules plus a small number of
`source="ktaf"` rules for local expectations the handbook itself does not
impose (never counted toward a state error total).

Judgment calls worth flagging for a future maintainer:

- **LastName special-character format** (`STF-LN-SPECIAL-CHARS`): the
  Validation Check text only exempts apostrophes and hyphens, but the
  Additional Notes explicitly instruct submitters to use a space to join
  multiple last names lacking a hyphen ("Davis Smyth"). The format check
  below allows a space for LastName (not FirstName) to avoid flagging the
  handbook's own recommended usage as an error.
- **Date "format" checks** (`STF-DOB-FORMAT`, `STF-SED-FORMAT`,
  `STF-SXD-FORMAT`) use `is_date8`, which validates real calendar dates, not
  just an 8-digit shape - a value like 20250230 fails both a plain digit
  regex and this check, and the handbook's "not entered in YYYYMMDD format"
  wording is read broadly enough to cover both.
- **"Value does not [meet|match] the acceptable range of values"** repeats
  across four elements. For GradeSpan and AvailableCredit, the Acceptable
  Values section gives a concrete range/shape, so the rule is checkable. For
  SectionEntryDate and SectionExitDate, no additional range is documented
  beyond the format, School-Year-window, and entry/exit-order checks already
  stated as their own separate bullets - what else "range" would test is
  genuinely ambiguous, so those two are marked `checkable=False`.
- **SectionExitDate "later than the file submission date"**
  (`STF-SXD-FUTURE`) needs the actual NJSLEDS submission timestamp. The
  wall-clock date this script runs on is not a reliable stand-in when a file
  is audited after the fact (the two sample files here are already several
  days old), so the handbook rule itself is marked uncheckable. A KTAF
  heuristic version (`KTAF-SXD-FUTURE-HEURISTIC`) is provided separately,
  clearly caveated, for same-day triage only.
"""

from __future__ import annotations

import datetime

from rules import Row, Rule, blank, in_window, is_date8, malformed, matches, present

# --------------------------------------------------------------------------- #
# KTAF-local reference data (not from the handbook - see module docstring).
# --------------------------------------------------------------------------- #

_KTAF_KNOWN_CDS_COMBOS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("80", "7325", "965"),  # Newark
        ("07", "1799", "111"),  # Camden - see notes on KTAF-CDS-COMBO below
    }
)


# --------------------------------------------------------------------------- #
# Predicates. Each returns True when the row VIOLATES the named rule.
# --------------------------------------------------------------------------- #


def _lsid_blank(row: Row) -> bool:
    return blank(row.get("LocalStaffIdentifier"))


def _smid_blank(row: Row) -> bool:
    return blank(row.get("StaffMemberIdentifier"))


def _smid_not_8_digits(row: Row) -> bool:
    return malformed(row.get("StaffMemberIdentifier"), r"\d{8}")


def _fn_blank(row: Row) -> bool:
    return blank(row.get("FirstName"))


def _fn_special_chars(row: Row) -> bool:
    return malformed(row.get("FirstName"), r"[A-Za-z'\-]+")


def _ln_blank(row: Row) -> bool:
    return blank(row.get("LastName"))


def _ln_special_chars(row: Row) -> bool:
    # Space allowed - see module docstring (Additional Notes vs Validation Check).
    return malformed(row.get("LastName"), r"[A-Za-z'\- ]+")


def _dob_blank(row: Row) -> bool:
    return blank(row.get("DateOfBirth"))


def _dob_bad_format(row: Row) -> bool:
    value = row.get("DateOfBirth")
    return present(value) and not is_date8(value)


def _cnty_blank(row: Row) -> bool:
    return blank(row.get("CountyCodeAssigned"))


def _cnty_leading_zeros(row: Row) -> bool:
    return malformed(row.get("CountyCodeAssigned"), r"\d{2}")


def _dist_blank(row: Row) -> bool:
    return blank(row.get("DistrictCodeAssigned"))


def _dist_leading_zeros(row: Row) -> bool:
    return malformed(row.get("DistrictCodeAssigned"), r"\d{4}")


def _schl_blank(row: Row) -> bool:
    return blank(row.get("SchoolCodeAssigned"))


def _schl_leading_zeros(row: Row) -> bool:
    return malformed(row.get("SchoolCodeAssigned"), r"\d{3}")


def _sed_blank(row: Row) -> bool:
    return blank(row.get("SectionEntryDate"))


def _sed_bad_format(row: Row) -> bool:
    value = row.get("SectionEntryDate")
    return present(value) and not is_date8(value)


def _sed_not_in_school_year(row: Row) -> bool:
    value = row.get("SectionEntryDate")
    return is_date8(value) and not in_window(value)


def _sxd_blank(row: Row) -> bool:
    return blank(row.get("SectionExitDate"))


def _sxd_bad_format(row: Row) -> bool:
    value = row.get("SectionExitDate")
    return present(value) and not is_date8(value)


def _sxd_not_in_school_year(row: Row) -> bool:
    value = row.get("SectionExitDate")
    return is_date8(value) and not in_window(value)


def _entry_exit_out_of_order(row: Row) -> bool:
    """Shared by STF-SED-AFTER-EXIT and STF-SXD-BEFORE-ENTRY - same condition,
    two separately-worded handbook statements under two different elements.
    """
    entry = row.get("SectionEntryDate")
    exit_ = row.get("SectionExitDate")
    if not (is_date8(entry) and is_date8(exit_)):
        return False
    return str(entry).strip() > str(exit_).strip()


def _subj_blank(row: Row) -> bool:
    return blank(row.get("SubjectArea"))


def _crsid_blank(row: Row) -> bool:
    return blank(row.get("CourseIdentifier"))


def _crsid_leading_zeros(row: Row) -> bool:
    return malformed(row.get("CourseIdentifier"), r"\d{3}")


def _crslvl_blank(row: Row) -> bool:
    return blank(row.get("CourseLevel"))


def _crslvl_invalid_code(row: Row) -> bool:
    return malformed(row.get("CourseLevel"), r"[BGEHX]")


def _grdspn_bad_range(row: Row) -> bool:
    return malformed(row.get("GradeSpan"), r"(?:PK|KG|0[1-9]|1[0-2]){2}")


def _avlcr_out_of_range(row: Row) -> bool:
    value = row.get("AvailableCredit")
    if blank(value):
        return False
    if not matches(value, r"\d{1,2}\.\d{3}"):
        return True
    return not (0.0 <= float(str(value).strip()) <= 35.0)


def _crsseq_blank(row: Row) -> bool:
    return blank(row.get("CourseSequence"))


def _crsseq_digit_order(row: Row) -> bool:
    value = row.get("CourseSequence")
    if not matches(value, r"\d{2}"):
        return False
    text = str(value).strip()
    return int(text[0]) > int(text[1])


def _lct_blank(row: Row) -> bool:
    return blank(row.get("LocalCourseTitle"))


def _lcc_blank(row: Row) -> bool:
    return blank(row.get("LocalCourseCode"))


def _lsc_blank(row: Row) -> bool:
    return blank(row.get("LocalSectionCode"))


def _ktaf_cds_combo_invalid(row: Row) -> bool:
    county = str(row.get("CountyCodeAssigned") or "").strip()
    district = str(row.get("DistrictCodeAssigned") or "").strip()
    school = str(row.get("SchoolCodeAssigned") or "").strip()
    if not (county and district and school):
        return False  # already covered by the handbook blank rules
    return (county, district, school) not in _KTAF_KNOWN_CDS_COMBOS


def _ktaf_sxd_future_heuristic(row: Row) -> bool:
    value = row.get("SectionExitDate")
    if not is_date8(value):
        return False
    return str(value).strip() > datetime.date.today().strftime("%Y%m%d")


# --------------------------------------------------------------------------- #
# Rule catalog.
# --------------------------------------------------------------------------- #

RULES: list[Rule] = [
    # --- LocalStaffIdentifier (LSID) -- handbook page 9 ------------------- #
    Rule(
        id="STF-LSID-BLANK",
        element="LocalStaffIdentifier",
        page=9,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_lsid_blank,
    ),
    Rule(
        id="STF-LSID-STAFFMGMT-MISMATCH",
        element="LocalStaffIdentifier",
        page=9,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Staff Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the Staff Management snapshot for this staff member "
            "(LSID/SMID/First Name/Last Name/Date of Birth combination) - "
            "not derivable from the Course Roster file alone."
        ),
        tags=("staff_management",),
    ),
    # --- StaffMemberIdentifier (SMID) -- handbook page 10 ------------------ #
    Rule(
        id="STF-SMID-LENGTH",
        element="StaffMemberIdentifier",
        page=10,
        error_text="An error will occur when the value submitted is not exactly 8 digits.",
        checkable=True,
        predicate=_smid_not_8_digits,
    ),
    Rule(
        id="STF-SMID-BLANK",
        element="StaffMemberIdentifier",
        page=10,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_smid_blank,
    ),
    Rule(
        id="STF-SMID-INVALID-NJSLEDS-ID",
        element="StaffMemberIdentifier",
        page=10,
        error_text=(
            "An error will occur when the Staff Member Identifier is not a "
            "valid number issued by NJSLEDS."
        ),
        checkable=False,
        uncheckable_reason="Needs the NJSLEDS-issued Staff Member Identifier registry.",
    ),
    Rule(
        id="STF-SMID-STAFFMGMT-MISMATCH",
        element="StaffMemberIdentifier",
        page=10,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Staff Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the Staff Management snapshot for this staff member "
            "(LSID/SMID/First Name/Last Name/Date of Birth combination) - "
            "not derivable from the Course Roster file alone."
        ),
        tags=("staff_management",),
    ),
    # --- FirstName -- handbook page 11 ------------------------------------ #
    Rule(
        id="STF-FN-BLANK",
        element="FirstName",
        page=11,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_fn_blank,
    ),
    Rule(
        id="STF-FN-SPECIAL-CHARS",
        element="FirstName",
        page=11,
        error_text=(
            "An error will occur if this field contains any special characters "
            "except for apostrophes (‘) and hyphens (-)."
        ),
        checkable=True,
        predicate=_fn_special_chars,
    ),
    Rule(
        id="STF-FN-STAFFMGMT-MISMATCH",
        element="FirstName",
        page=11,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Staff Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the Staff Management snapshot for this staff member "
            "(LSID/SMID/First Name/Last Name/Date of Birth combination) - "
            "not derivable from the Course Roster file alone."
        ),
        tags=("staff_management",),
    ),
    # --- LastName -- handbook page 12 ------------------------------------- #
    Rule(
        id="STF-LN-BLANK",
        element="LastName",
        page=12,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_ln_blank,
    ),
    Rule(
        id="STF-LN-SPECIAL-CHARS",
        element="LastName",
        page=12,
        error_text=(
            "An error will occur if this field contains any special characters "
            "except for apostrophes (‘) and hyphens (-)."
        ),
        checkable=True,
        predicate=_ln_special_chars,
        notes=(
            "Allows a literal space in addition to letters/apostrophe/hyphen: "
            "Additional Notes for this element instruct submitters to join "
            "multiple last names with a space when no hyphen is used "
            "('Davis Smyth'), which the bare Validation Check text does not "
            "itself exempt."
        ),
    ),
    Rule(
        id="STF-LN-STAFFMGMT-MISMATCH",
        element="LastName",
        page=12,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Staff Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the Staff Management snapshot for this staff member "
            "(LSID/SMID/First Name/Last Name/Date of Birth combination) - "
            "not derivable from the Course Roster file alone."
        ),
        tags=("staff_management",),
    ),
    # --- DateOfBirth -- handbook page 13 ----------------------------------- #
    Rule(
        id="STF-DOB-BLANK",
        element="DateOfBirth",
        page=13,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_dob_blank,
    ),
    Rule(
        id="STF-DOB-FORMAT",
        element="DateOfBirth",
        page=13,
        error_text=(
            "An error will occur if the date is not entered in YYYYMMDD "
            "format (for example, 20150128)."
        ),
        checkable=True,
        predicate=_dob_bad_format,
        notes="Uses is_date8, which also rejects a syntactically 8-digit but calendar-invalid date.",
    ),
    Rule(
        id="STF-DOB-STAFFMGMT-MISMATCH",
        element="DateOfBirth",
        page=13,
        error_text=(
            "An error will occur if this field does not exactly match the "
            "value in Staff Management."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the Staff Management snapshot for this staff member "
            "(LSID/SMID/First Name/Last Name/Date of Birth combination) - "
            "not derivable from the Course Roster file alone."
        ),
        tags=("staff_management",),
    ),
    # --- CountyCodeAssigned -- handbook page 14 ---------------------------- #
    Rule(
        id="STF-CNTY-BLANK",
        element="CountyCodeAssigned",
        page=14,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_cnty_blank,
    ),
    Rule(
        id="STF-CNTY-CDS-LIST",
        element="CountyCodeAssigned",
        page=14,
        error_text=(
            "An error will occur if the County Code submitted does not "
            "conform to the codes listed for your district in the CDS list."
        ),
        checkable=False,
        uncheckable_reason="Needs the NJSLEDS County District School (CDS) code list for the LEA.",
        tags=("cds_list",),
    ),
    Rule(
        id="STF-CNTY-LEADING-ZEROS",
        element="CountyCodeAssigned",
        page=14,
        error_text=(
            "An error will occur if required leading zeros are missing, "
            "resulting in an incorrect value format."
        ),
        checkable=True,
        predicate=_cnty_leading_zeros,
    ),
    Rule(
        id="STF-CNTY-STAFFMGMT-MISMATCH",
        element="CountyCodeAssigned",
        page=14,
        error_text=(
            "An error will occur if this field does not exactly match one of "
            "the six CountyCodeAssigned values in Staff Management."
        ),
        checkable=False,
        uncheckable_reason="Needs the Staff Management snapshot's six CountyCodeAssigned values.",
        tags=("staff_management",),
    ),
    # --- DistrictCodeAssigned -- handbook page 15 -------------------------- #
    Rule(
        id="STF-DIST-BLANK",
        element="DistrictCodeAssigned",
        page=15,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_dist_blank,
    ),
    Rule(
        id="STF-DIST-SUBMITTING-MISMATCH",
        element="DistrictCodeAssigned",
        page=15,
        error_text=(
            "An error will occur if the District Code submitted does not "
            "match the Submitting District."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the identity of the actual submitting LEA for this upload, "
            "which is not a column in the Course Roster file."
        ),
        tags=("cds_list",),
    ),
    Rule(
        id="STF-DIST-LEADING-ZEROS",
        element="DistrictCodeAssigned",
        page=15,
        error_text=(
            "An error will occur if required leading zeros are missing, "
            "resulting in an incorrect value format."
        ),
        checkable=True,
        predicate=_dist_leading_zeros,
    ),
    Rule(
        id="STF-DIST-STAFFMGMT-MISMATCH",
        element="DistrictCodeAssigned",
        page=15,
        error_text=(
            "An error will occur if this field does not exactly match one of "
            "the six DistrictCodeAssigned values in Staff Management."
        ),
        checkable=False,
        uncheckable_reason="Needs the Staff Management snapshot's six DistrictCodeAssigned values.",
        tags=("staff_management",),
    ),
    # --- SchoolCodeAssigned -- handbook page 16 ---------------------------- #
    Rule(
        id="STF-SCHL-BLANK",
        element="SchoolCodeAssigned",
        page=16,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_schl_blank,
    ),
    Rule(
        id="STF-SCHL-CDS-LIST",
        element="SchoolCodeAssigned",
        page=16,
        error_text=(
            "An error will occur if the School Code submitted does not "
            "conform to the codes listed for your district in the CDS list."
        ),
        checkable=False,
        uncheckable_reason="Needs the NJSLEDS County District School (CDS) code list for the LEA.",
        tags=("cds_list",),
    ),
    Rule(
        id="STF-SCHL-LEADING-ZEROS",
        element="SchoolCodeAssigned",
        page=16,
        error_text=(
            "An error will occur if required leading zeros are missing, "
            "resulting in an incorrect value format."
        ),
        checkable=True,
        predicate=_schl_leading_zeros,
    ),
    Rule(
        id="STF-SCHL-STAFFMGMT-MISMATCH",
        element="SchoolCodeAssigned",
        page=16,
        error_text=(
            "An error will occur if this field does not exactly match one of "
            "the six SchoolCodeAssigned values in Staff Management."
        ),
        checkable=False,
        uncheckable_reason="Needs the Staff Management snapshot's six SchoolCodeAssigned values.",
        tags=("staff_management",),
    ),
    # --- SectionEntryDate -- handbook page 17 ------------------------------ #
    Rule(
        id="STF-SED-BLANK",
        element="SectionEntryDate",
        page=17,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_sed_blank,
    ),
    Rule(
        id="STF-SED-RANGE",
        element="SectionEntryDate",
        page=17,
        error_text="An error will occur if the value does not meet the acceptable range of values.",
        checkable=False,
        uncheckable_reason=(
            "Ambiguous for a date field: no range beyond the format, "
            "School-Year-window, and entry/exit-order checks is documented "
            "elsewhere on this page, and those are already their own bullets."
        ),
        tags=("ambiguous",),
    ),
    Rule(
        id="STF-SED-FORMAT",
        element="SectionEntryDate",
        page=17,
        error_text=(
            "An error will occur if the date is not entered in YYYYMMDD "
            "format (for example, 20250128)."
        ),
        checkable=True,
        predicate=_sed_bad_format,
        notes="Uses is_date8, which also rejects a syntactically 8-digit but calendar-invalid date.",
    ),
    Rule(
        id="STF-SED-AFTER-EXIT",
        element="SectionEntryDate",
        page=17,
        error_text=(
            "An error will occur if the staff course entry date occurs after "
            "the staff course exit date."
        ),
        checkable=True,
        predicate=_entry_exit_out_of_order,
    ),
    Rule(
        id="STF-SED-NOT-IN-SY",
        element="SectionEntryDate",
        page=17,
        error_text=(
            "An error will occur if the SectionEntryDate does not occur in "
            "the current School Year."
        ),
        checkable=True,
        predicate=_sed_not_in_school_year,
    ),
    # --- SectionExitDate -- handbook page 18 ------------------------------- #
    Rule(
        id="STF-SXD-BLANK",
        element="SectionExitDate",
        page=18,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_sxd_blank,
    ),
    Rule(
        id="STF-SXD-RANGE",
        element="SectionExitDate",
        page=18,
        error_text="An error will occur if the value does not meet the acceptable range of values.",
        checkable=False,
        uncheckable_reason=(
            "Ambiguous for a date field: no range beyond the format, "
            "School-Year-window, and entry/exit-order checks is documented "
            "elsewhere on this page, and those are already their own bullets."
        ),
        tags=("ambiguous",),
    ),
    Rule(
        id="STF-SXD-FORMAT",
        element="SectionExitDate",
        page=18,
        error_text=(
            "An error will occur if the date is not entered in YYYYMMDD "
            "format (for example, 20250128)."
        ),
        checkable=True,
        predicate=_sxd_bad_format,
        notes="Uses is_date8, which also rejects a syntactically 8-digit but calendar-invalid date.",
    ),
    Rule(
        id="STF-SXD-BEFORE-ENTRY",
        element="SectionExitDate",
        page=18,
        error_text=(
            "An error will occur if the staff course exit date occurs before "
            "the staff course entry date."
        ),
        checkable=True,
        predicate=_entry_exit_out_of_order,
    ),
    Rule(
        id="STF-SXD-NOT-IN-SY",
        element="SectionExitDate",
        page=18,
        error_text=(
            "An error will occur if the SectionExitDate does not occur in "
            "the current School Year."
        ),
        checkable=True,
        predicate=_sxd_not_in_school_year,
    ),
    Rule(
        id="STF-SXD-FUTURE",
        element="SectionExitDate",
        page=18,
        error_text=(
            "An error will occur if the SectionExitDate is later than the "
            "file submission date (for example, a future date)."
        ),
        checkable=False,
        uncheckable_reason=(
            "Needs the actual NJSLEDS file submission date/timestamp, which "
            "is not a column in the upload. The wall-clock date this script "
            "runs on is not a reliable stand-in for a file audited after the "
            "fact (see KTAF-SXD-FUTURE-HEURISTIC for a caveated same-day proxy)."
        ),
        tags=("ambiguous",),
    ),
    # --- SubjectArea -- handbook page 19 ----------------------------------- #
    Rule(
        id="STF-SUBJ-BLANK",
        element="SubjectArea",
        page=19,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_subj_blank,
    ),
    Rule(
        id="STF-SUBJ-INVALID-SCED",
        element="SubjectArea",
        page=19,
        error_text="An error will occur if the value is not a valid SCED Subject Area code.",
        checkable=False,
        uncheckable_reason="Needs the NJSLEDS/NCES SCED Course Codes document's Subject Area list.",
        tags=("sced",),
    ),
    # --- CourseIdentifier -- handbook page 20 ------------------------------ #
    Rule(
        id="STF-CRSID-BLANK",
        element="CourseIdentifier",
        page=20,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_crsid_blank,
    ),
    Rule(
        id="STF-CRSID-INVALID-SCED",
        element="CourseIdentifier",
        page=20,
        error_text="An error will occur if the value is not a valid SCED Course Identifier code.",
        checkable=False,
        uncheckable_reason="Needs the NJSLEDS/NCES SCED Course Codes document's Course Identifier list.",
        tags=("sced",),
    ),
    Rule(
        id="STF-CRSID-LEADING-ZEROS",
        element="CourseIdentifier",
        page=20,
        error_text=(
            "An error will occur if required leading zeros are missing, "
            "resulting in an incorrect value format."
        ),
        checkable=True,
        predicate=_crsid_leading_zeros,
    ),
    # --- CourseLevel -- handbook page 21 ----------------------------------- #
    Rule(
        id="STF-CRSLVL-BLANK",
        element="CourseLevel",
        page=21,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_crslvl_blank,
    ),
    Rule(
        id="STF-CRSLVL-INVALID-CODE",
        element="CourseLevel",
        page=21,
        error_text="An error will occur if the value is not a valid SCED Course Level code.",
        checkable=True,
        predicate=_crslvl_invalid_code,
        notes=(
            "Unlike SubjectArea/CourseIdentifier, the valid Course Level "
            "codes (B, G, E, H, X) are enumerated directly in the handbook's "
            "Acceptable Values text rather than deferred to an external SCED "
            "document, so this is checkable without outside data."
        ),
    ),
    # --- GradeSpan -- handbook page 22 ------------------------------------- #
    Rule(
        id="STF-GRDSPN-BLANK-PRIOR-TO-SECONDARY",
        element="GradeSpan",
        page=22,
        error_text=(
            "An error will occur if the field is left blank for a course "
            "with a Prior-To-Secondary course code."
        ),
        checkable=False,
        uncheckable_reason=(
            "Whether a course is Prior-To-Secondary is a property of its "
            "SubjectArea/CourseIdentifier SCED classification, which needs "
            "the NJSLEDS/NCES SCED Course Codes document - not derivable "
            "from whether other fields happen to be populated."
        ),
        tags=("sced",),
    ),
    Rule(
        id="STF-GRDSPN-RANGE",
        element="GradeSpan",
        page=22,
        error_text="An error will occur if the value does not match the acceptable range of values.",
        checkable=True,
        predicate=_grdspn_bad_range,
    ),
    # --- AvailableCredit -- handbook page 23 ------------------------------- #
    Rule(
        id="STF-AVLCR-BLANK-SECONDARY",
        element="AvailableCredit",
        page=23,
        error_text=(
            "An error will occur if this field is left blank for a course "
            "with a Secondary course code."
        ),
        checkable=False,
        uncheckable_reason=(
            "Whether a course is Secondary is a property of its "
            "SubjectArea/CourseIdentifier SCED classification, which needs "
            "the NJSLEDS/NCES SCED Course Codes document - not derivable "
            "from whether other fields happen to be populated."
        ),
        tags=("sced",),
    ),
    Rule(
        id="STF-AVLCR-RANGE",
        element="AvailableCredit",
        page=23,
        error_text="An error will occur if the value does not match the acceptable range of values.",
        checkable=True,
        predicate=_avlcr_out_of_range,
    ),
    # --- CourseSequence -- handbook page 24 -------------------------------- #
    Rule(
        id="STF-CRSSEQ-BLANK",
        element="CourseSequence",
        page=24,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_crsseq_blank,
    ),
    Rule(
        id="STF-CRSSEQ-DIGIT-ORDER",
        element="CourseSequence",
        page=24,
        error_text=(
            "An error will occur if the value of the first digit is greater "
            "than the value of the second digit."
        ),
        checkable=True,
        predicate=_crsseq_digit_order,
    ),
    # --- LocalCourseTitle -- handbook page 25 ------------------------------ #
    Rule(
        id="STF-LCT-BLANK",
        element="LocalCourseTitle",
        page=25,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_lct_blank,
    ),
    # --- LocalCourseCode -- handbook page 26 ------------------------------- #
    Rule(
        id="STF-LCC-BLANK",
        element="LocalCourseCode",
        page=26,
        error_text="An error will occur if this field is left blank.",
        checkable=True,
        predicate=_lcc_blank,
    ),
    # --- LocalSectionCode -- handbook page 27 ------------------------------ #
    Rule(
        id="STF-LSC-BLANK",
        element="LocalSectionCode",
        page=27,
        error_text="An error will occur if the field is left blank.",
        checkable=True,
        predicate=_lsc_blank,
    ),
    # --- KTAF local expectations (not counted toward a state error total) - #
    Rule(
        id="KTAF-CDS-COMBO",
        element="CountyCodeAssigned+DistrictCodeAssigned+SchoolCodeAssigned",
        page=0,
        error_text=(
            "Local KTAF expectation: CountyCodeAssigned, DistrictCodeAssigned, "
            "and SchoolCodeAssigned must together match one of KTAF's known "
            "CDS combinations for the submitting region."
        ),
        checkable=True,
        source="ktaf",
        predicate=_ktaf_cds_combo_invalid,
        notes=(
            "Known combinations: Newark (80, 7325, 965) and Camden "
            "(07, 1799, 111), set by the data team.\n\n"
            "This rule is EXPECTED to fire heavily, and that is the point. "
            "Camden's uploads carry school code 179 on every populated-CDS "
            "row, and Newark's carry 732 on a large block of rows. Those are "
            "not alternative valid codes - they are the documented CDS "
            "defect: the Alternate School Number is unset in PowerSchool "
            "School Setup for those schools, so the extract falls back to a "
            "prefix of the internal school number. As of the 2026-07-29 "
            "extract this affected 20,652 of 43,493 student rows, including "
            "every Camden row.\n\n"
            "Do not 'fix' this rule by changing the expected codes to match "
            "what the file contains. An earlier draft of this catalog did "
            "exactly that - it substituted 179 for 111 on the reasoning that "
            "a rule firing on 100% of rows must have a bad reference value. "
            "Here, 100% is the correct answer, and the substitution would "
            "have reported a wholly non-compliant file as clean. Reference "
            "values come from the data team or the NJDOE directory, never "
            "from the file under test.\n\n"
            "Camden's 111 is still worth confirming against the NJDOE "
            "directory before anyone keys it into School Setup."
        ),
        tags=("cds_list",),
    ),
    Rule(
        id="KTAF-SXD-FUTURE-HEURISTIC",
        element="SectionExitDate",
        page=0,
        error_text=(
            "Local heuristic: SectionExitDate is later than the date this "
            "script was run, as a same-day proxy for the handbook's "
            "file-submission-date check (STF-SXD-FUTURE, marked uncheckable)."
        ),
        checkable=True,
        source="ktaf",
        predicate=_ktaf_sxd_future_heuristic,
        notes=(
            "Only a reliable proxy when run the same day the file is "
            "actually submitted to NJSLEDS. Do not treat a hit as a "
            "confirmed state error for a file audited after the fact."
        ),
        tags=("ambiguous",),
    ),
]
