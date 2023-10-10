with
    studentrace_agg as (
        select studentid, _dbt_source_relation, string_agg(racecd) as racecd,
        from {{ ref("stg_powerschool__studentrace") }}
        group by studentid, _dbt_source_relation
    ),

    course_enrollment_count as (
        select
            _dbt_source_relation,
            students_student_number,
            cc_academic_year,
            count(cc_sectionid) as sectionid_count,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            cc_academic_year = {{ var("current_academic_year") }}
            and not is_dropped_section
        group by _dbt_source_relation, students_student_number, cc_academic_year
    ),

    student_enrollments as (
        select
            se._dbt_source_relation,
            se.student_number,
            se.state_studentnumber,
            se.lastfirst,
            se.enroll_status,
            se.gender,
            se.ethnicity,
            se.fedethnicity,
            se.academic_year,
            se.region,
            se.schoolid,
            se.school_name,
            se.school_abbreviation,
            se.grade_level,
            se.advisory_name,
            se.fteid,
            safe_cast(se.dob as string) as dob,
            if(
                regexp_contains(se.lastfirst, r"\s{2,}|[^\w\s',-]"), 1, 0
            ) as name_spelling_flag,
            if(se.ethnicity is null, 1, 0) as missing_ethnicity_flag,
            if(se.gender is null, 1, 0) as missing_gender_flag,
            if(se.state_studentnumber is null, 1, 0) as missing_sid_flag,
            if(se.dob is null, 1, 0) as missing_dob_flag,

            r.racecd,

            cast(cec.sectionid_count as string) as sectionid_count,
            if(cec.sectionid_count <= 3, true, false) as underenrollment_flag,

            case
                when se.fteid != fte.id
                then concat(se.fteid, ' != ', fte.id)
                when se.fteid is null
                then 'MISSING'
                when se.fteid = 0
                then 'FTE == 0'
                else safe_cast(se.fteid as string)
            end as fteid_detail,
            case
                when se.fteid is null
                then 1
                when se.fteid = 0
                then 1
                when se.fteid != fte.id
                then 1
                else 0
            end as missing_fte_flag,

            if(se.region = 'KMS', se.ethnicity, r.racecd) as race_eth_detail,
            case
                when se.region = 'Miami' and se.ethnicity is null
                then 1
                when se.region = 'Miami' and se.ethnicity = ''
                then 1
                when
                    se.region != 'Miami'
                    and se.fedethnicity is null
                    and r.racecd is null
                then 1
                else 0
            end as race_eth_flag,
        from {{ ref("base_powerschool__student_enrollments") }} as se
        left join
            {{ ref("stg_powerschool__fte") }} as fte
            on se.schoolid = fte.schoolid
            and se.yearid = fte.yearid
            and {{ union_dataset_join_clause(left_alias="se", right_alias="fte") }}
            and fte.name like 'Full Time Student%'
        left join
            studentrace_agg as r
            on se.studentid = r.studentid
            and {{ union_dataset_join_clause(left_alias="se", right_alias="r") }}
        left join
            course_enrollment_count as cec
            on se.student_number = cec.students_student_number
            and se.academic_year = cec.cc_academic_year
            and {{ union_dataset_join_clause(left_alias="se", right_alias="cec") }}
        where
            se.academic_year = {{ var("current_academic_year") }}
            and se.schoolid != 999999
            and se.rn_year = 1
    )

select
    _dbt_source_relation as `db_name`,
    schoolid,
    school_name,
    school_abbreviation,
    student_number,
    region,
    lastfirst,
    grade_level,
    advisory_name as team,

    'Name Spelling' as element,

    lastfirst as detail,
    name_spelling_flag as flag,
from student_enrollments

union all

select
    _dbt_source_relation as `db_name`,
    schoolid,
    school_name,
    school_abbreviation,
    student_number,
    region,
    lastfirst,
    grade_level,
    advisory_name as team,

    'Missing Ethnicity' as element,

    ethnicity as detail,
    missing_ethnicity_flag as flag,
from student_enrollments

union all

select
    _dbt_source_relation as `db_name`,
    schoolid,
    school_name,
    school_abbreviation,
    student_number,
    region,
    lastfirst,
    grade_level,
    advisory_name as team,

    'Missing Gender' as element,

    gender as detail,
    missing_gender_flag as flag,
from student_enrollments

union all

select
    _dbt_source_relation as `db_name`,
    schoolid,
    school_name,
    school_abbreviation,
    student_number,
    region,
    lastfirst,
    grade_level,
    advisory_name as team,

    'Missing SID' as element,

    state_studentnumber as detail,
    missing_sid_flag as flag,
from student_enrollments

union all

select
    _dbt_source_relation as `db_name`,
    schoolid,
    school_name,
    school_abbreviation,
    student_number,
    region,
    lastfirst,
    grade_level,
    advisory_name as team,

    'Missing DOB' as element,

    dob as detail,
    missing_dob_flag as flag,
from student_enrollments

union all

select
    _dbt_source_relation as `db_name`,
    schoolid,
    school_name,
    school_abbreviation,
    student_number,
    region,
    lastfirst,
    grade_level,
    advisory_name as team,

    'Missing or Incorrect FTEID' as element,

    fteid_detail as detail,
    missing_fte_flag as flag,
from student_enrollments

union all

select
    _dbt_source_relation as `db_name`,
    schoolid,
    school_name,
    school_abbreviation,
    student_number,
    region,
    lastfirst,
    grade_level,
    advisory_name as team,

    'Missing Race/Ethnicity' as element,

    race_eth_detail as detail,
    race_eth_flag as flag,
from student_enrollments

union all

select
    _dbt_source_relation as `db_name`,
    schoolid,
    school_name,
    school_abbreviation,
    student_number,
    region,
    lastfirst,
    grade_level,
    advisory_name as team,

    'Under Enrolled' as element,

    sectionid_count as detail,
    1 as flag,
from student_enrollments
where underenrollment_flag

union all

select
    se._dbt_source_relation as `db_name`,
    se.schoolid,
    se.school_name,
    se.school_abbreviation,
    se.student_number,
    se.region,
    se.lastfirst,
    se.grade_level,
    se.advisory_name as team,

    'Enrollment Dupes' as element,

    concat(
        ceo.cc_course_number,
        ' - ',
        ceo.sections_section_number,
        ' - ',
        ceo.cc_dateenrolled,
        '-',
        ceo.cc_dateleft
    ) as detail,
    1 as flag,
from student_enrollments as se
inner join
    {{ ref("qa_powerschool__course_enrollment_overlap") }} as ceo
    on se.student_number = ceo.students_student_number
    and se.academic_year = ceo.cc_academic_year
    and {{ union_dataset_join_clause(left_alias="se", right_alias="ceo") }}
