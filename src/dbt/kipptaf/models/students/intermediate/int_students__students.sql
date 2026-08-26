with
    current_stint as (
        select student_number, enroll_status,
        from {{ ref("int_focus__student_enrollment_roster") }}
        where rn_all = 1
    ),

    focus_conformed as (
        select
            s._dbt_source_relation,
            s._dbt_source_project,
            s.student_number,
            s.first_name,
            s.middle_name,
            s.last_name,
            s.powerschool_id,
            s.florida_student_number,
            s.florida_education_identifier,
            s.dob,
            s.gender,
            s.ethnicity,
            s.state_studentnumber,

            s.lunchstatus,

            e.enroll_status,
        from {{ ref("int_focus__students") }} as s
        -- Joined on Focus's own prefixed id. Both sides are Focus-native, so
        -- stripping the 8400 prefix on each just to match them back up is a
        -- round trip -- and it made the join depend on the unprefix rule
        -- holding, which is not a property this join needs.
        left join current_stint as e on s.student_id = e.student_number
    ),

    powerschool_filtered as (
        select p.*,
        from {{ ref("stg_powerschool__students") }} as p
        where p._dbt_source_project != 'kippmiami'
    )

select *,
from powerschool_filtered

full union all corresponding

select *,
from focus_conformed
