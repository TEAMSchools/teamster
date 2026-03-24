select
    s.student_number,
    s.lastfirst,

    sg.studentid,
    sg.schoolname,
    sg.academic_year,
    sg.course_name,
    sg.course_number,
    sg.teacher_name,
    sg.dcid as storedgrades_dcid,

    de.de_course_name,
    de.de_pass_yn,
    de.de_score,
    de.de_semester,
    de.de_institution,

    s.student_number || '_' || sg.course_number as unique_identifier,

from {{ ref("stg_powerschool__storedgrades") }} as sg
left join
    {{ ref("stg_powerschool__students") }} as s
    on sg.studentid = s.id
    and {{ union_dataset_join_clause(left_alias="sg", right_alias="s") }}
left join
    {{ ref("stg_powerschool__u_storedgrades_de") }} as de
    on sg.dcid = de.storedgradesdcid
    and {{ union_dataset_join_clause(left_alias="sg", right_alias="de") }}
    and de.de_course_name is not null
-- TODO: establish storecode policy for DE grades as institutions now submit
-- twice yearly (fall → Q2, spring → ?). If spring grades land on Y1 in the
-- same academic year, a student will have both Q2 and Y1 rows for the same
-- course, causing duplicates. Consider a priority/fallback CTE at that point.
where sg.course_name like '%(DE)' and sg.storecode in ('Y1', 'Q2')
