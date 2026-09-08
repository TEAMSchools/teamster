with
    grades as (
        select
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
            sg.dcid as grade_dcid,
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

            sch.name is null as is_transfer_grade,

            'Earned' as credit_status,

            coalesce(sg.earnedcrhrs, 0.0) as earned_credits,

        from {{ ref("int_powerschool__gpnode") }} as gpn
        inner join
            {{ ref("stg_powerschool__gpprogresssubject") }} as sub
            on gpn.subject_id = sub.gpnodeid
            and gpn.nodetype = sub.nodetype
        inner join
            {{ ref("stg_powerschool__gpprogresssubjectearned") }} as se
            on sub.id = se.gpprogresssubjectid
        inner join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on se.storedgradesdcid = sg.dcid
            and sg.storecode = 'Y1'
        left join
            {{ ref("stg_powerschool__schools") }} as sch on sg.schoolname = sch.name

        union all

        select
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
            fg.cc_dcid as grade_dcid,
            fg.school_name as schoolname,
            fg.studentid,
            fg.teacher_lastfirst as teacher_name,
            fg.course_number,
            fg.course_name,
            fg.sectionid,
            fg.credittype as credit_type,
            fg.y1_letter_grade_adjusted as letter_grade,
            fg.courses_credit_hours as official_potential_credits,
            sub.enrolledcredits as potential_credits,

            false as is_transfer_grade,

            'Enrolled' as credit_status,

            if(
                fg.y1_letter_grade not like 'F%', sub.enrolledcredits, 0.0
            ) as earned_credits,

        from {{ ref("int_powerschool__gpnode") }} as gpn
        inner join
            {{ ref("stg_powerschool__gpprogresssubject") }} as sub
            on gpn.subject_id = sub.gpnodeid
            and gpn.nodetype = sub.nodetype
        inner join
            {{ ref("stg_powerschool__gpprogresssubjectenrolled") }} as se
            on sub.id = se.gpprogresssubjectid
        inner join
            {{ ref("base_powerschool__final_grades") }} as fg
            on se.ccdcid = fg.cc_dcid
            and fg.academic_year = {{ var("current_academic_year") }}
            and fg.termbin_is_current
    )

select
    g.plan_id,
    g.plan_name,
    g.discipline_id,
    g.discipline_name,
    g.subject_id,
    g.subject_name,
    g.plan_credit_capacity,
    g.discipline_credit_capacity,
    g.subject_credit_capacity,
    g.studentsdcid,
    g.academic_year,
    g.grade_dcid,
    g.schoolname,
    g.studentid,
    g.teacher_name,
    g.course_number,
    g.course_name,
    g.sectionid,
    g.credit_type,
    g.letter_grade,
    g.official_potential_credits,
    g.potential_credits,
    g.is_transfer_grade,
    g.credit_status,
    g.earned_credits,

    sp.enrolledcredits as plan_enrolled_credits,
    sp.requestedcredits as plan_requested_credits,
    sp.earnedcredits as plan_earned_credits,
    sp.waivedcredits as plan_waived_credits,

    sd.enrolledcredits as discipline_enrolled_credits,
    sd.requestedcredits as discipline_requested_credits,
    sd.earnedcredits as discipline_earned_credits,
    sd.waivedcredits as discipline_waived_credits,

    ss.enrolledcredits as subject_enrolled_credits,
    ss.requestedcredits as subject_requested_credits,
    ss.earnedcredits as subject_earned_credits,
    ss.waivedcredits as subject_waived_credits,

    coalesce(sp.requiredcredits, g.plan_credit_capacity) as plan_required_credits,
    coalesce(
        sd.requiredcredits, g.discipline_credit_capacity
    ) as discipline_required_credits,
    coalesce(ss.requiredcredits, g.subject_credit_capacity) as subject_required_credits,

from grades as g
left join
    {{ ref("stg_powerschool__gpprogresssubject") }} as sp
    on g.plan_id = sp.gpnodeid
    and g.studentsdcid = sp.studentsdcid
left join
    {{ ref("stg_powerschool__gpprogresssubject") }} as sd
    on g.discipline_id = sd.gpnodeid
    and g.studentsdcid = sd.studentsdcid
left join
    {{ ref("stg_powerschool__gpprogresssubject") }} as ss
    on g.subject_id = ss.gpnodeid
    and g.studentsdcid = ss.studentsdcid
