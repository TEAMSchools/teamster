with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source("kippnewark_powerschool", model.name),
                    source("kippcamden_powerschool", model.name),
                    source("kippmiami_powerschool", model.name),
                ]
            )
        }}
    )

select
    ur.*,

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

    row_number() over (
        partition by
            ur._dbt_source_relation, ur.cc_studyear, csc.illuminate_subject_area
        order by ur.cc_termid desc, ur.cc_dateenrolled desc, ur.cc_dateleft desc
    ) as rn_student_year_illuminate_subject_desc,
from union_relations as ur
left join
    {{ ref("stg_powerschool__s_nj_crs_x") }} as cx
    on ur.courses_dcid = cx.coursesdcid
    and {{ union_dataset_join_clause(left_alias="ur", right_alias="cx") }}
left join
    {{ ref("stg_assessments__course_subject_crosswalk") }} as csc
    on ur.cc_course_number = csc.powerschool_course_number
