with
    -- Per-enrollment-stint PowerSchool enrollment range. One row per stint;
    -- multi-stint students get multiple dim rows per LEP record, each clipped
    -- to its specific entry/exit window. Aggregating to min/max would span
    -- gaps between stints.
    enrollments as (
        select
            students_dcid,
            student_number,
            _dbt_source_relation,
            _dbt_source_project,
            academic_year,
            entrydate,

            -- PowerSchool exitdate is half-open (first day AFTER stint).
            -- Subtract 1 day to get the inclusive last day so boundary-sharing
            -- stints don't produce overlapping inclusive ends in the dim.
            coalesce(
                date_sub(exitdate, interval 1 day), cast('9999-12-31' as date)
            ) as enrollment_end,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        -- graduates carry NULL entry/exit as a placeholder row; drop them
        -- (no enrollment context to clip against).
        where entrydate is not null
    ),

    nj_primary as (
        select
            e.student_number,
            njs._dbt_source_project,
            e._dbt_source_relation,
            e.academic_year,
            e.entrydate,

            greatest(njs.lepbegindate, e.entrydate) as effective_date_start,

            least(
                coalesce(njs.lependdate, cast('9999-12-31' as date)), e.enrollment_end
            ) as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
        inner join
            enrollments as e
            on njs.studentsdcid = e.students_dcid
            and njs._dbt_source_project = e._dbt_source_project
            and njs.lepbegindate <= e.enrollment_end
            and coalesce(njs.lependdate, cast('9999-12-31' as date)) >= e.entrydate
        where njs.lepbegindate is not null
    ),

    nj_secondary as (
        select
            e.student_number,
            njs._dbt_source_project,
            e._dbt_source_relation,
            e.academic_year,
            e.entrydate,

            greatest(njs.lepbegindate2, e.entrydate) as effective_date_start,

            least(
                coalesce(njs.liependdate2, cast('9999-12-31' as date)), e.enrollment_end
            ) as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
        inner join
            enrollments as e
            on njs.studentsdcid = e.students_dcid
            and njs._dbt_source_project = e._dbt_source_project
            and njs.lepbegindate2 <= e.enrollment_end
            and coalesce(njs.liependdate2, cast('9999-12-31' as date)) >= e.entrydate
        where njs.lepbegindate2 is not null
    ),

    nj_leg as (
        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            academic_year,
            entrydate,
            effective_date_start,
            effective_date_end,
        from nj_primary
        union all
        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            academic_year,
            entrydate,
            effective_date_start,
            effective_date_end,
        from nj_secondary
    ),

    pm_leg as (
        select
            e.student_number,
            e._dbt_source_project,
            e._dbt_source_relation,
            e.academic_year,
            e.entrydate,

            e.entrydate as effective_date_start,
            e.enrollment_end as effective_date_end,
        from enrollments as e
        inner join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on e.students_dcid = scf.studentsdcid
            and e._dbt_source_project = scf._dbt_source_project
        -- Miami only: Paterson is already covered by stg_powerschool__s_nj_stu_x
        -- (NJ leg). Including Paterson here double-counts ELL spans.
        where e._dbt_source_project = 'kippmiami' and scf.lep_status is true
    ),

    unioned as (
        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            academic_year,
            entrydate,
            effective_date_start,
            effective_date_end,
        from nj_leg
        union all
        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            academic_year,
            entrydate,
            effective_date_start,
            effective_date_end,
        from pm_leg
    )

select
    _dbt_source_project,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as student_ell_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "academic_year", "entrydate"]
        )
    }} as student_enrollment_key,

    true as is_ell,
    effective_date_end = '9999-12-31' as is_current,
from unioned
