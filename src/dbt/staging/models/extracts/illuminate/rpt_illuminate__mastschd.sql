select  -- noqa: disable=ST06
    -- noqa: disable=RF05
    concat(
        regexp_extract(sec._dbt_source_relation, r'(kipp\w+)_'), sec.id
    ) as `01 Section ID`,

    tr.schoolid as `02 Site ID`,
    tr.name as `03 Term Name`,

    sec.course_number as `04 Course ID`,

    t.teachernumber as `05 User ID`,

    case
        when tr.schoolid = 73253 then sec.expression else sec.section_number
    end as `06 Period`,

    concat((tr.yearid + 1990), '-', (tr.yearid + 1991)) as `07 Academic Year`,

    null as `08 Room Number`,
    null as `09 Session Type ID`,
    null as `10 Local Term ID`,
    null as `11 Quarter Num`,

    tr.firstday as `12 User Start Date`,
    tr.lastday as `13 User End Date`,

    1 as `14 Primary Teacher`,
    null as `15 Teacher Competency Level`,
    null as `16 Is Attendance Enabled`,
from {{ ref("stg_powerschool__terms") }} as tr
inner join
    {{ ref("stg_powerschool__sections") }} as sec
    on tr.id = sec.termid
    and tr.schoolid = sec.schoolid
    and {{ union_dataset_join_clause(left_alias="tr", right_alias="sec") }}
inner join
    {{ ref("int_powerschool__teachers") }} as t
    on sec.teacher = t.id
    and {{ union_dataset_join_clause(left_alias="sec", right_alias="t") }}
where tr.yearid = ({{ var("current_academic_year") }} - 1990)
