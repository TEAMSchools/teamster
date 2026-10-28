with
    finalsite_students as (
        select
            cast(ida.focus_student_id_prefixed as int64) as student_number,

            string_agg(distinct c.status, ', ' order by c.status) as finalsite_statuses,

            logical_or(c.status = 'enrolled') as is_enrolled_in_finalsite,
        from {{ ref("int_finalsite__contact_id_attributes") }} as ida
        inner join
            {{ ref("stg_finalsite__contacts") }} as c
            on ida.finalsite_enrollment_id = c.finalsite_enrollment_id
        where ida.focus_student_id_prefixed is not null
        group by ida.focus_student_id_prefixed
    ),

    active_stints as (
        select student_number, academic_year, schoolid, startdate, exitdate,
        from {{ ref("int_focus__student_enrollment_roster") }}
        where
            academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and not is_pre_year_withdrawal
            -- no-shows share start and exit date
            and startdate < exitdate
            and exitdate >= current_date('{{ var("local_timezone") }}')
    )

select
    e.student_number,
    e.academic_year,
    e.schoolid,
    e.startdate,
    e.exitdate,

    f.finalsite_statuses,
from active_stints as e
left join finalsite_students as f on e.student_number = f.student_number
where f.is_enrolled_in_finalsite is not true
