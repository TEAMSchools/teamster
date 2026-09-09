with
    focus_conformed as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            region,
            academic_year,
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

            -- The roster's exitdate is the stint's inclusive last day and
            -- PowerSchool's is the day after it. Conform to PowerSchool here so
            -- every consumer's half-open date-range join holds network-wide.
            date_add(exitdate, interval 1 day) as exitdate,
        from {{ ref("int_focus__student_enrollment_roster") }}
    ),

    unioned as (
        select *,
        from {{ ref("int_powerschool__student_enrollment_union") }}

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
