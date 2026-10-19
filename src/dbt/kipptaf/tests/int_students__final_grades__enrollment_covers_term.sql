with
    graded as (
        select cc_dcid, _dbt_source_project, termbin_start_date, termbin_end_date,
        from {{ ref("int_students__final_grades") }}
        where term_letter_grade is not null or term_percent_grade is not null
    )

select
    g.cc_dcid,
    g._dbt_source_project,
    g.termbin_start_date,
    g.termbin_end_date,

    ce.cc_dateenrolled,
    ce.exit_date,
from graded as g
inner join
    {{ ref("int_students__course_enrollments") }} as ce
    on g.cc_dcid = ce.cc_dcid
    and g._dbt_source_project = ce._dbt_source_project
where ce.cc_dateenrolled > g.termbin_end_date or ce.exit_date <= g.termbin_start_date
