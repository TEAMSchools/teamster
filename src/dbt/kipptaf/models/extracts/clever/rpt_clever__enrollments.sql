select
    cc.schoolid as school_id,
    concat(
        regexp_extract(cc._dbt_source_relation, r'(kipp\w+)_'), cc.sectionid
    ) as section_id,

    s.student_number as student_id,
from {{ ref("stg_powerschool__cc") }} as cc
inner join
    {{ ref("stg_powerschool__students") }} as s
    on cc.studentid = s.id
    and {{ union_dataset_join_clause(left_alias="cc", right_alias="s") }}
where cc.dateleft >= current_date('{{ var("local_timezone") }}')

union all

/* ENR sections */
select
    schoolid as school_id,
    concat(
        {{ var("current_academic_year") }} - 1990,
        schoolid,
        right(concat(0, grade_level), 2)
    ) as section_id,
    student_number as student_id,
from {{ ref("stg_powerschool__students") }}
where enroll_status in (0, -1)
