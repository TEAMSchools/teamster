with
    -- Per-(student, district) PowerSchool enrollment range. Inner-joining the
    -- legs to this CTE clips LEP spans to the student's actual enrollment in
    -- the district and drops phantom NJSmart records for districts where the
    -- student was never enrolled.
    enrollments as (
        select
            students_dcid,
            student_number,
            _dbt_source_project,

            min(entrydate) as enrollment_start,
            max(coalesce(exitdate, cast('9999-12-31' as date))) as enrollment_end,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        group by students_dcid, student_number, _dbt_source_project
    ),

    nj_primary as (
        select
            e.student_number,
            njs._dbt_source_project,

            greatest(njs.lepbegindate, e.enrollment_start) as effective_date_start,

            least(
                coalesce(njs.lependdate, cast('9999-12-31' as date)), e.enrollment_end
            ) as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
        inner join
            enrollments as e
            on njs.studentsdcid = e.students_dcid
            and njs._dbt_source_project = e._dbt_source_project
        where
            njs.lepbegindate is not null
            and njs.lepbegindate <= e.enrollment_end
            and coalesce(njs.lependdate, cast('9999-12-31' as date))
            >= e.enrollment_start
    ),

    nj_secondary as (
        select
            e.student_number,
            njs._dbt_source_project,

            greatest(njs.lepbegindate2, e.enrollment_start) as effective_date_start,

            least(
                coalesce(njs.liependdate2, cast('9999-12-31' as date)), e.enrollment_end
            ) as effective_date_end,
        from {{ ref("stg_powerschool__s_nj_stu_x") }} as njs
        inner join
            enrollments as e
            on njs.studentsdcid = e.students_dcid
            and njs._dbt_source_project = e._dbt_source_project
        where
            njs.lepbegindate2 is not null
            and njs.lepbegindate2 <= e.enrollment_end
            and coalesce(njs.liependdate2, cast('9999-12-31' as date))
            >= e.enrollment_start
    ),

    nj_leg as (
        select
            student_number,
            _dbt_source_project,
            effective_date_start,
            effective_date_end,
        from nj_primary
        union all
        select
            student_number,
            _dbt_source_project,
            effective_date_start,
            effective_date_end,
        from nj_secondary
    ),

    pm_leg as (
        select distinct
            e.student_number,
            e._dbt_source_project,

            e.enrollment_start as effective_date_start,
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
            effective_date_start,
            effective_date_end,
        from nj_leg
        union all
        select
            student_number,
            _dbt_source_project,
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

    true as is_ell,
    effective_date_end = '9999-12-31' as is_current,
from unioned
