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
    and de.de_course_name not null
where sg.course_name like '%(DE)' and sg.storecode = 'Y1'
