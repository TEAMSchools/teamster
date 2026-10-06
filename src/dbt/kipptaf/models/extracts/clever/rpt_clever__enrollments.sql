with
    out_of_district as (
        select student_number, _dbt_source_project,
        from {{ ref("int_extracts__student_enrollments") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and is_out_of_district
    ),

    enrollments as (
        select
            cc.schoolid as school_id,

            s.student_number,
            s._dbt_source_project,

            concat(
                regexp_extract(cc._dbt_source_relation, r'(kipp\w+)_'), cc.sectionid
            ) as section_id,
        from {{ ref("stg_powerschool__cc") }} as cc
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on cc.studentid = s.id
            and cc._dbt_source_project = s._dbt_source_project
            and s.enroll_status in (0, -1)
        where cc.dateleft >= current_date('{{ var("local_timezone") }}')

        union all

        select
            schoolid as school_id,
            student_number,
            _dbt_source_project,

            concat(
                {{ var("current_academic_year") - 1990 }},
                schoolid,
                right(concat(0, grade_level), 2)
            ) as section_id,
        from {{ ref("stg_powerschool__students") }}
        where enroll_status in (0, -1)
    )

select e.school_id, e.section_id, e.student_number as student_id,
from enrollments as e
left join
    out_of_district as ood
    on e.student_number = ood.student_number
    and e._dbt_source_project = ood._dbt_source_project
where ood.student_number is null
