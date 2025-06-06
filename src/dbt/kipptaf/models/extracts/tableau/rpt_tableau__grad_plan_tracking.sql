select
    gpn._dbt_source_relation,
    gpn.plan_name,
    gpn.discipline_name,
    gpn.subject_id,
    gpn.subject_name,
    gpn.plan_credit_capacity,
    gpn.discipline_credit_capacity,
    gpn.subject_credit_capacity,

    sub.studentsdcid,

    sg.academic_year,
    sg.schoolname,
    sg.studentid,
    sg.teacher_name,
    sg.course_number,
    sg.course_name,
    sg.sectionid,
    sg.credit_type,
    sg.grade as letter_grade,
    sg.earnedcrhrs as credits,
    sg.is_transfer_grade,

    'Earned' as credit_status,
from {{ ref("int_powerschool__gpnode") }} as gpn
inner join
    {{ ref("stg_powerschool__gpprogresssubject") }} as sub
    on gpn.subject_id = sub.gpnodeid
    and gpn.nodetype = sub.nodetype
    and {{ union_dataset_join_clause(left_alias="gpn", right_alias="sub") }}
inner join
    {{ ref("stg_powerschool__gpprogresssubjectearned") }} as se
    on sub.id = se.gpprogresssubjectid
    and {{ union_dataset_join_clause(left_alias="sub", right_alias="se") }}
inner join
    {{ ref("stg_powerschool__storedgrades") }} as sg
    on se.storedgradesdcid = sg.dcid
    and sg.storecode = 'Y1'
    and {{ union_dataset_join_clause(left_alias="se", right_alias="sg") }}

union all

select
    gpn._dbt_source_relation,
    gpn.plan_name,
    gpn.discipline_name,
    gpn.subject_id,
    gpn.subject_name,
    gpn.plan_credit_capacity,
    gpn.discipline_credit_capacity,
    gpn.subject_credit_capacity,

    sub.studentsdcid,

    fg.academic_year,
    fg.school_name as schoolname,
    fg.studentid,
    fg.teacher_lastfirst as teacher_name,
    fg.course_name,
    fg.course_number,
    fg.sectionid,
    fg.credittype as credit_type,
    fg.y1_letter_grade_adjusted as letter_grade,
    fg.potential_credit_hours as credits,

    false as is_transfer_grade,

    'Enrolled' as credit_status,
from {{ ref("int_powerschool__gpnode") }} as gpn
inner join
    {{ ref("stg_powerschool__gpprogresssubject") }} as sub
    on gpn.subject_id = sub.gpnodeid
    and gpn.nodetype = sub.nodetype
    and {{ union_dataset_join_clause(left_alias="gpn", right_alias="sub") }}
inner join
    {{ ref("stg_powerschool__gpprogresssubjectenrolled") }} as se
    on sub.id = se.gpprogresssubjectid
    and {{ union_dataset_join_clause(left_alias="sub", right_alias="se") }}
inner join
    {{ ref("base_powerschool__final_grades") }} as fg
    on se.ccdcid = fg.cc_dcid
    and {{ union_dataset_join_clause(left_alias="se", right_alias="fg") }}
    and fg.storecode = 'Y1'
