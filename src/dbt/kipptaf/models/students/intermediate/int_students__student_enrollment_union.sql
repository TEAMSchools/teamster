with
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            region,
            academic_year,
            exitdate,
            enroll_status,
            entrycode,
            exitcode,
            grade_level,
            rn_year,
            year_in_school,
            year_in_network,
            is_enrolled_oct01,
            is_enrolled_oct15,
            is_enrolled_mar15,
            dob,
            state,

            ps_schoolid as schoolid,
            startdate as entrydate,
            student_first_name as first_name,
            student_last_name as last_name,

            network_student_number as student_number,
        from {{ ref("int_focus__student_enrollment_roster") }}
    ),

    powerschool_conformed as (
        select *,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        where _dbt_source_project != 'kippmiami'
    ),

    unioned as (
        select *,
        from powerschool_conformed

        full union all corresponding

        select *,
        from focus_conformed
    )

    -- TODO(#5045): remove once Ops corrects the backdated PowerSchool re-entry
    -- dates that put two stints on one entrydate.
    {{
        dbt_utils.deduplicate(
            relation="unioned",
            partition_by="student_number, _dbt_source_project, academic_year, entrydate",
            order_by="rn_year asc",
        )
    }}
