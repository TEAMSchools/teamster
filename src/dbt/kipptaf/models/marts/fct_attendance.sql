with
    daily_attendance as (
        select *, from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
    ),

    final as (
        select
            student_number,
            schoolid as school_id,
            calendardate as date_day,
            membershipvalue as membership_value,
            is_absent,
            is_present_weighted,
            is_tardy,
            is_ontime,
            is_suspended,
            semester,
            term,
        from daily_attendance

    )
select *
from final
