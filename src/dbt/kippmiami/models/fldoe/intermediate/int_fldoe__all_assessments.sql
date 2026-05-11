with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    ref("stg_fldoe__eoc"),
                    ref("stg_fldoe__fast"),
                    ref("stg_fldoe__science"),
                    source("fldoe", "stg_fldoe__fsa"),
                ]
            )
        }}
    ),

    transformed as (
        select
            test_code,
            academic_year,
            administration_window,
            season,
            discipline,
            assessment_subject,
            scale_score,
            achievement_level,
            is_proficient,

            cast(
                coalesce(assessment_grade, test_grade, enrolled_grade) as string
            ) as assessment_grade,

            coalesce(performance_level, achievement_level_int) as performance_level,
            coalesce(student_id, fleid) as student_id,

            regexp_extract(
                _dbt_source_relation, r'stg_fldoe__(\w+)'
            ) as assessment_name,
        from union_relations
    ),

    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    fleid_lookup_raw as (
        select s.student_number, s.dcid, suf.fleid,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("stg_powerschool__u_studentsuserfields") }} as suf
            on s.dcid = suf.studentsdcid
        where s.dcid >= 1 and suf.fleid is not null
    ),

    fleid_lookup as (
        {{
            dbt_utils.deduplicate(
                relation="fleid_lookup_raw",
                partition_by="fleid",
                order_by="dcid desc",
            )
        }}
    )

select
    t.* except (assessment_name),

    if(
        t.assessment_name = 'science', 'Science', upper(t.assessment_name)
    ) as assessment_name,

    fl.student_number,
from transformed as t
left join fleid_lookup as fl on t.student_id = fl.fleid
