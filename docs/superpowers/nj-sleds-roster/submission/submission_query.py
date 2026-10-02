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

# The passing subset of ALPHA_GRADE_DOMAIN ("D-" or better, per the design
# spec). Named explicitly rather than derived by excluding the failing
# grades, so both lists stay independently reviewable. Must remain a subset
# of ALPHA_GRADE_DOMAIN.
PASSING_ALPHA_GRADES = frozenset(
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
    }
)

# Sorted, comma-joined SQL literal lists built from the constants above, so
# the Python domain and the SQL `in (...)` domain can never drift apart.
# sorted() on these codes happens to match the conventional A, A+, A- order,
# since '+' sorts before '-' and a bare letter is a prefix of both.
_ALPHA_GRADE_DOMAIN_SQL = ", ".join(f"'{g}'" for g in sorted(ALPHA_GRADE_DOMAIN))
_PASSING_ALPHA_GRADES_SQL = ", ".join(f"'{g}'" for g in sorted(PASSING_ALPHA_GRADES))

# Regions this tool still submits for. Camden's 2026-07-31 submission was
# accepted, error-free, and certified, so its extract is final - reprocessing
# it can only introduce a difference from what the state already holds. Newark
# remains open, and from the 2026-08-02 extract onward its files arrive alone.
#
# This is the single source of truth: the gate's base-table iteration, the
# submission export, and the ungraded worklist all derive their region set
# from here. Restoring a region means adding it back to this tuple and
# re-measuring the baselines in validate_submission.py - nothing else.
#
# SUBMISSION_SQL still builds both regions' branches below, each pinned to its
# own source project, and filters at the end. Keeping the branch and filtering
# it out means a certified region can be brought back by editing one tuple
# rather than reconstructing SQL that has been deleted.
REGIONS_IN_SCOPE = ("newark",)

_REGIONS_IN_SCOPE_SQL = ", ".join(f"'{r}'" for r in sorted(REGIONS_IN_SCOPE))

# trunk-ignore(bandit/B608): grade domain values are module constants, not user input
SUBMISSION_SQL = f"""
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

    live_raw as (
        select
            _dbt_source_project,
            `grade`,
            enddate,

            cast(studentid as string) as studentid_str,
            cast(sectionid as string) as sectionid_str,
            max(enddate) over (
                partition by _dbt_source_project, studentid, sectionid
            ) as max_enddate,
        from `teamster-332318.kipptaf_powerschool.stg_powerschool__pgfinalgrades`
        where
            enddate between date '2025-07-01' and date '2026-06-30'
            and `grade` is not null
            and _dbt_source_project in ('kippnewark', 'kippcamden')
    ),

    live as (
        select
            _dbt_source_project,
            studentid_str,
            sectionid_str,

            max(`grade`) as live_letter,
            count(distinct `grade`) as n_live_letters,
        from live_raw
        where enddate = max_enddate
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
            lg.live_letter,
            lg.n_live_letters,

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
        left join live as lg
            on st.studentid_str = lg.studentid_str
            and e.LocalSectionCode = lg.sectionid_str
            and lg._dbt_source_project = 'kippnewark'
    ),

    camden_joined as (
        select
            e.*,

            sc.sced_level,
            sg.stored_letter,
            sg.stored_earned_credit,
            sg.n_stored_letters,
            sg.n_stored_credits,
            lg.live_letter,
            lg.n_live_letters,

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
        left join live as lg
            on st.studentid_str = lg.studentid_str
            and e.LocalSectionCode = lg.sectionid_str
            and lg._dbt_source_project = 'kippcamden'
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

            substr(grade_span_padded, 1, 2) as grade_span_start,
        from typed
    ),

    scoped as (
        select
            *,

            case
                when sced_level = 'secondary' and available_credit_num > 0
                then 'HS'
                when
                    grade_span_start
                    in ('06', '07', '08', '09', '10', '11', '12')
                then 'MS'
                else 'OUT'
            end as grade_band,
        from banded
    ),

    conflict_guarded as (
        select
            *,

            if(n_stored_letters > 1, null, stored_letter) as safe_stored,
            if(n_live_letters > 1, null, live_letter) as safe_live,
            if(
                n_stored_letters > 1 or n_stored_credits > 1,
                null,
                stored_earned_credit
            ) as safe_stored_credit,
        from scoped
    ),

    sourced as (
        select
            *,

            coalesce(safe_stored, safe_live) as candidate_letter,
            case
                when safe_stored is not null then 'stored'
                when safe_live is not null then 'live'
                else 'none'
            end as grade_source,
        from conflict_guarded
    ),

    emitted_grade as (
        select
            *,

            if(
                grade_band in ('HS', 'MS')
                and candidate_letter in ({_ALPHA_GRADE_DOMAIN_SQL}),
                candidate_letter,
                cast(null as string)
            ) as emitted_alpha_grade,
        from sourced
    ),

    emitted_credit as (
        select
            *,

            case
                when grade_band != 'HS'
                then cast(null as string)
                when safe_stored_credit is not null
                then format('%.3f', safe_stored_credit)
                when emitted_alpha_grade is null
                then cast(null as string)
                when emitted_alpha_grade in ({_PASSING_ALPHA_GRADES_SQL})
                then format('%.3f', available_credit_num)
                else '0.000'
            end as emitted_credits_earned,
        from emitted_grade
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
    emitted_credits_earned as CreditsEarned,
    NumericGradeEarned,
    emitted_alpha_grade as AlphaGradeEarned,
    CompletionStatus,
    CourseType,
    DualInstitution,
    region,
    grade_band,
    stored_letter,
    stored_earned_credit,
    n_stored_letters,
    n_stored_credits,
    live_letter,
    n_live_letters,
    candidate_letter,
    grade_source,
from emitted_credit
where region in ({_REGIONS_IN_SCOPE_SQL})
"""

# The worklist identifies rows by local IDs only (LocalIdentificationNumber,
# LocalSectionCode) - never FirstName, LastName, DateOfBirth, or
# StateIdentificationNumber, per the project's worklist PII convention.
# LocalIdentificationNumber is enough to find the student in PowerSchool.
UNGRADED_WORKLIST_COLUMNS = [
    "region",
    "grade_band",
    "LocalIdentificationNumber",
    "LocalSectionCode",
    "LocalCourseCode",
    "LocalCourseTitle",
    "SubjectArea",
    "CourseIdentifier",
    "CourseLevel",
    "GradeSpan",
    "AvailableCredit",
    "SectionEntryDate",
    "SectionExitDate",
    "CourseType",
    "ungraded_rows",
    "section_rows",
    "reason",
    "section_shape",
]

# trunk-ignore(bandit/B608): SUBMISSION_SQL is a module constant, not user input
UNGRADED_WORKLIST_SQL = f"""
with
    v as ({SUBMISSION_SQL}),

    in_scope as (
        select * from v where grade_band in ('HS', 'MS')
    ),

    section_totals as (
        select
            region,
            LocalSectionCode,

            count(*) as section_rows,
        from in_scope
        group by region, LocalSectionCode
    ),

    ungraded as (
        select * from in_scope where AlphaGradeEarned is null
    ),

    ungraded_by_section as (
        select
            region,
            LocalSectionCode,

            count(*) as ungraded_rows,
        from ungraded
        group by region, LocalSectionCode
    )

select
    u.region,
    u.grade_band,
    u.LocalIdentificationNumber,
    u.LocalSectionCode,
    u.LocalCourseCode,
    u.LocalCourseTitle,
    u.SubjectArea,
    u.CourseIdentifier,
    u.CourseLevel,
    u.GradeSpan,
    u.AvailableCredit,
    u.SectionEntryDate,
    u.SectionExitDate,
    u.CourseType,

    ubs.ungraded_rows,

    st.section_rows,

    case
        when u.candidate_letter is not null
        then 'grade exists but outside the handbook domain'
        when u.n_stored_letters > 1 or u.n_live_letters > 1
        then 'conflicting grades across sources or terms'
        else 'no grade in either source'
    end as reason,
    case
        when ubs.ungraded_rows = st.section_rows
        then 'whole section ungraded'
        else 'partial - classmates were graded'
    end as section_shape,
from ungraded as u
inner join ungraded_by_section as ubs
    on u.region = ubs.region
    and u.LocalSectionCode = ubs.LocalSectionCode
inner join section_totals as st
    on u.region = st.region
    and u.LocalSectionCode = st.LocalSectionCode
"""
