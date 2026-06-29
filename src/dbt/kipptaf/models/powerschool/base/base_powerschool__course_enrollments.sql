with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                    source(
                        "kipppaterson_powerschool",
                        "base_powerschool__course_enrollments",
                    ),
                ]
            )
        }}
    ),

    add_dbt_field as (
        select ur.*, {{ extract_code_location("ur") }} as _dbt_source_project,
        from union_relations as ur
    )

select
    a.* except (courses_credittype),

    cx.ap_course_subject,
    cx.block_schedule_session,
    cx.county_code_override,
    cx.course_level,
    cx.course_sequence_code,
    cx.course_span,
    cx.course_type,
    cx.cte_test_name_code,
    cx.ctecollegecredits as cte_college_credits,
    cx.ctetestdevelopercode as cte_test_developer_code,
    cx.ctetestname as cte_test_name,
    cx.district_code_override,
    cx.dual_institution,
    cx.exclude_course_submission_tf,
    cx.nces_course_id,
    cx.nces_subject_area,
    cx.school_code_override,
    cx.sla_include_tf,

    csc.illuminate_subject_area,
    csc.is_foundations,
    csc.is_advanced_math,
    csc.discipline,

    {{ extract_region("a") }} as region,

    case
        when a.courses_credittype in ('ENG', 'ELA')
        then 'ENG'
        when a.courses_credittype in ('MATH', 'Math')
        then 'MATH'
        when a.courses_credittype in ('SCI', 'Science')
        then 'SCI'
        when a.courses_credittype in ('HR', 'Homeroom')
        then 'HR'
        else a.courses_credittype
    end as courses_credittype,

    if(cx.ap_course_subject is not null, true, false) as is_ap_course,

    if(csc.discipline = 'SOC', 'Civics', csc.discipline) as standardized_discipline,

    row_number() over (
        partition by a._dbt_source_relation, a.cc_studyear, csc.illuminate_subject_area
        order by a.cc_termid desc, a.cc_dateenrolled desc, a.cc_dateleft desc
    ) as rn_student_year_illuminate_subject_desc,

from add_dbt_field as a
left join
    {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
    on a.courses_dcid = cx.coursesdcid
    and a._dbt_source_project = cx._dbt_source_project
left join
    {{ ref("stg_google_sheets__assessments__course_subject_crosswalk") }} as csc
    on a.cc_course_number = csc.powerschool_course_number
