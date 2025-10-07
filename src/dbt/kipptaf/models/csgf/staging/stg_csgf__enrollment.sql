with
    calendar_days as (
        select yearid, schoolid, avg(days_total) as total_instructional_days,
        from {{ ref("int_powerschool__calendar_rollup") }}
        where yearid = {{ var("current_academic_year") - 1990 }}
        group by yearid, schoolid
    )

select
    c.total_instructional_days,

    et.budget_target as total_budgeted_enrollment,

    coalesce(
        case
            r.race_ethnicity_reporting
            when 'Black/African American'
            then 'Black or African American'
            else r.race_ethnicity_reporting
        end,
        'Decline to State'
    ) as race_ethnicity_of_primary_leader,

    coalesce(
        case
            r.gender_identity
            when 'Cis Woman'
            then 'Woman'
            when 'Cis Man'
            then 'Male'
            else r.gender_identity
        end,
        'Not Listed'
    ) as gender_of_primary_leader,

    case
        s.`name`
        when 'Paterson Prep Middle School'
        then 'KIPP Paterson MS'
        when 'Paterson Prep Elementary School'
        then 'KIPP Paterson ES'
        else s.`name`
    end as school,

from {{ ref("stg_powerschool__schools") }} as s
inner join calendar_days as c on s.school_number = c.schoolid
left join
    `kipptaf_google_sheets.stg_google_sheets__topline_enrollment_targets` as et
    on s.school_number = et.schoolid
    and et.academic_year = {{ var("current_academic_year") }}
left join {{ ref("int_people__staff_roster") }} as r on s.principalemail = r.work_email
