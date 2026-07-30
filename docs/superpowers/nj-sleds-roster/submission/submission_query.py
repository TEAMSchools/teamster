"""SQL and constants for the NJ SLEDS student course submission view.

SUBMISSION_SQL is a bare SELECT with no trailing semicolon so it can be used
as a subquery by the validator or wrapped in CREATE OR REPLACE VIEW by the
builder.
"""

SUBMISSION_COLUMNS = [
    "LocalIdentificationNumber",
    "StateIdentificationNumber",
    "FirstName",
    "LastName",
    "DateOfBirth",
    "CountyCodeAssigned",
    "DistrictCodeAssigned",
    "SchoolCodeAssigned",
    "SectionEntryDate",
    "SectionExitDate",
    "SubjectArea",
    "CourseIdentifier",
    "CourseLevel",
    "GradeSpan",
    "AvailableCredit",
    "CourseSequence",
    "LocalCourseTitle",
    "LocalCourseCode",
    "LocalSectionCode",
    "CreditsEarned",
    "NumericGradeEarned",
    "AlphaGradeEarned",
    "CompletionStatus",
    "CourseType",
    "DualInstitution",
]

ALPHA_GRADE_DOMAIN = frozenset(
    {
        "A",
        "A+",
        "A-",
        "B",
        "B+",
        "B-",
        "C",
        "C+",
        "C-",
        "D",
        "D+",
        "D-",
        "E",
        "E+",
        "E-",
        "F",
        "F+",
        "F-",
    }
)

SUBMISSION_SQL = """
with
    sced as (
        select
            subject_area,
            course_identifier,
            sced_level,
        from `teamster-332318.cokafor.ref_sced_codes`
    ),

    newark_joined as (
        select
            e.*,

            sc.sced_level,

            'newark' as region,
        from `teamster-332318.cokafor.stg_student_extract_newark` as e
        left join sced as sc
            on e.SubjectArea = sc.subject_area
            and e.CourseIdentifier = sc.course_identifier
    ),

    camden_joined as (
        select
            e.*,

            sc.sced_level,

            'camden' as region,
        from `teamster-332318.cokafor.stg_student_extract_camden` as e
        left join sced as sc
            on e.SubjectArea = sc.subject_area
            and e.CourseIdentifier = sc.course_identifier
    ),

    joined as (
        select * from newark_joined
        union all
        select * from camden_joined
    ),

    normalized as (
        select
            *,

            nullif(GradeSpan, '') as grade_span_raw,
            nullif(AvailableCredit, '') as available_credit_raw,
        from joined
    ),

    typed as (
        select
            *,

            lpad(grade_span_raw, 4, '0') as grade_span_padded,
            safe_cast(available_credit_raw as float64) as available_credit_num,
        from normalized
    ),

    banded as (
        select
            *,

            substr(grade_span_padded, 3, 2) as grade_span_upper,
        from typed
    ),

    scoped as (
        select
            *,

            case
                when sced_level = 'secondary' and available_credit_num > 0
                then 'HS'
                when
                    grade_span_upper
                    in ('06', '07', '08', '09', '10', '11', '12')
                then 'MS'
                else 'OUT'
            end as grade_band,
        from banded
    )

select
    LocalIdentificationNumber,
    StateIdentificationNumber,
    FirstName,
    LastName,
    DateOfBirth,
    CountyCodeAssigned,
    DistrictCodeAssigned,
    SchoolCodeAssigned,
    SectionEntryDate,
    SectionExitDate,
    SubjectArea,
    CourseIdentifier,
    CourseLevel,
    GradeSpan,
    AvailableCredit,
    CourseSequence,
    LocalCourseTitle,
    LocalCourseCode,
    LocalSectionCode,
    CreditsEarned,
    NumericGradeEarned,
    AlphaGradeEarned,
    CompletionStatus,
    CourseType,
    DualInstitution,
    region,
    grade_band,
from scoped
"""
