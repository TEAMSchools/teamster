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

    stored_raw as (
        select
            _dbt_source_project,
            `grade`,
            earnedcrhrs,

            cast(studentid as string) as studentid_str,
            cast(sectionid as string) as sectionid_str,
        from `teamster-332318.kipptaf_powerschool.stg_powerschool__storedgrades`
        where
            academic_year = 2025
            and storecode = 'Y1'
            and _dbt_source_project in ('kippnewark', 'kippcamden')
    ),

    stored as (
        select
            _dbt_source_project,
            studentid_str,
            sectionid_str,

            max(`grade`) as stored_letter,
            max(earnedcrhrs) as stored_earned_credit,
            count(distinct `grade`) as n_stored_letters,
            count(distinct earnedcrhrs) as n_stored_credits,
        from stored_raw
        group by _dbt_source_project, studentid_str, sectionid_str
    ),

    students as (
        select
            _dbt_source_project,

            cast(student_number as string) as student_number_str,
            cast(id as string) as studentid_str,
        from `teamster-332318.kipptaf_powerschool.stg_powerschool__students`
        where _dbt_source_project in ('kippnewark', 'kippcamden')
    ),

    newark_joined as (
        select
            e.*,

            sc.sced_level,
            sg.stored_letter,
            sg.stored_earned_credit,
            sg.n_stored_letters,
            sg.n_stored_credits,

            'newark' as region,
        from `teamster-332318.cokafor.stg_student_extract_newark` as e
        left join sced as sc
            on e.SubjectArea = sc.subject_area
            and e.CourseIdentifier = sc.course_identifier
        left join students as st
            on e.LocalIdentificationNumber = st.student_number_str
            and st._dbt_source_project = 'kippnewark'
        left join stored as sg
            on st.studentid_str = sg.studentid_str
            and e.LocalSectionCode = sg.sectionid_str
            and sg._dbt_source_project = 'kippnewark'
    ),

    camden_joined as (
        select
            e.*,

            sc.sced_level,
            sg.stored_letter,
            sg.stored_earned_credit,
            sg.n_stored_letters,
            sg.n_stored_credits,

            'camden' as region,
        from `teamster-332318.cokafor.stg_student_extract_camden` as e
        left join sced as sc
            on e.SubjectArea = sc.subject_area
            and e.CourseIdentifier = sc.course_identifier
        left join students as st
            on e.LocalIdentificationNumber = st.student_number_str
            and st._dbt_source_project = 'kippcamden'
        left join stored as sg
            on st.studentid_str = sg.studentid_str
            and e.LocalSectionCode = sg.sectionid_str
            and sg._dbt_source_project = 'kippcamden'
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
    stored_letter,
    stored_earned_credit,
    n_stored_letters,
    n_stored_credits,
from scoped
"""
