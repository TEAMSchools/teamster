select
    gpn._dbt_source_relation,
    gpn.plan_id,
    gpn.plan_name,
    gpn.discipline_id,
    gpn.discipline_name,
    gpn.subject_id,
    gpn.subject_name,
    gpn.plan_credit_capacity,
    gpn.discipline_credit_capacity,
    gpn.subject_credit_capacity,

    sub.studentsdcid,

    sg.academic_year,
    sg.dcid as cc_dcid,
    sg.schoolname,
    sg.studentid,
    sg.teacher_name,
    sg.course_number,
    sg.course_name,
    sg.sectionid,
    sg.credit_type,
    sg.grade as letter_grade,
    sg.is_transfer_grade,

    'Earned' as credit_status,

    sg.potentialcrhrs as official_potential_credits,
    sg.potentialcrhrs as potential_credits,
    sg.earnedcrhrs as earned_credits,

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
    and {{ union_dataset_join_clause(left_alias="se", right_alias="sg") }}
    and sg.storecode = 'Y1'

union all

select
    gpn._dbt_source_relation,
    gpn.plan_id,
    gpn.plan_name,
    gpn.discipline_id,
    gpn.discipline_name,
    gpn.subject_id,
    gpn.subject_name,
    gpn.plan_credit_capacity,
    gpn.discipline_credit_capacity,
    gpn.subject_credit_capacity,

    sub.studentsdcid,

    fg.academic_year,
    fg.cc_dcid,
    fg.school_name as schoolname,
    fg.studentid,
    fg.teacher_lastfirst as teacher_name,
    fg.course_number,
    fg.course_name,
    fg.sectionid,
    fg.credittype as credit_type,
    fg.y1_letter_grade_adjusted as letter_grade,

    false as is_transfer_grade,

    'Enrolled' as credit_status,

    fg.courses_credit_hours as official_potential_credits,

    gps.enrolledcredits as potential_credits,

    if(fg.y1_letter_grade not like 'F%', gps.enrolledcredits, 0.0) as earned_credits,

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
    and fg.academic_year = {{ var("current_academic_year") }}
    and fg.termbin_is_current
inner join
    {{ ref("int_powerschool__gpprogresssubject") }} as gps
    on sub.gpnodeid = gps.id
    and sub.studentsdcid = gps.studentsdcid
    and gps.degree_plan_section = 'Subject'
    and {{ union_dataset_join_clause(left_alias="sub", right_alias="gps") }}
