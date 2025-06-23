select
    gp._dbt_source_relation,
    gp.plan_id,
    gp.plan_name,
    gp.discipline_id,
    gp.discipline_name,
    gp.subject_id,
    gp.subject_name,
    gp.plan_credit_capacity,
    gp.discipline_credit_capacity,
    gp.subject_credit_capacity,
    gp.studentsdcid,

    sg.academic_year,
    sg.schoolname,
    sg.studentid,
    sg.teacher_name,
    sg.course_number,
    sg.course_name,
    sg.sectionid,
    sg.credit_type,
    sg.grade as letter_grade,
    sg.potentialcrhrs as official_potential_credits,
    sg.potentialcrhrs as potential_credits,
    sg.earnedcrhrs as earned_credits,
    sg.is_transfer_grade,

    'Earned' as credit_status,
from {{ ref("int_powerschool__gpnode") }} as gp
inner join
    {{ ref("stg_powerschool__storedgrades") }} as sg
    on gp.storedgradesdcid = sg.dcid
    and {{ union_dataset_join_clause(left_alias="gp", right_alias="sg") }}
    and sg.storecode = 'Y1'

union all

select
    gp._dbt_source_relation,
    gp.plan_id,
    gp.plan_name,
    gp.discipline_id,
    gp.discipline_name,
    gp.subject_id,
    gp.subject_name,
    gp.plan_credit_capacity,
    gp.discipline_credit_capacity,
    gp.subject_credit_capacity,
    gp.studentsdcid,

    fg.academic_year,
    fg.school_name as schoolname,
    fg.studentid,
    fg.teacher_lastfirst as teacher_name,
    fg.course_number,
    fg.course_name,
    fg.sectionid,
    fg.credittype as credit_type,
    fg.y1_letter_grade_adjusted as letter_grade,
    fg.courses_credit_hours as official_potential_credits,

    gpnu.enrolledcredits as potential_credits,

    if(fg.y1_letter_grade not like 'F%', gpnu.enrolledcredits, 0.0) as earned_credits,

    false as is_transfer_grade,
    'Enrolled' as credit_status,
from {{ ref("int_powerschool__gpnode") }} as gp
inner join
    {{ ref("int_powerschool__gpnode_unpivot") }} as gpnu
    on gp.subject_id = gpnu.id
    and gp.studentsdcid = gpnu.studentsdcid
    and {{ union_dataset_join_clause(left_alias="gp", right_alias="gpnu") }}
inner join
    {{ ref("base_powerschool__final_grades") }} as fg
    on gp.ccdcid = fg.cc_dcid
    and {{ union_dataset_join_clause(left_alias="gp", right_alias="fg") }}
    and fg.termbin_is_current
