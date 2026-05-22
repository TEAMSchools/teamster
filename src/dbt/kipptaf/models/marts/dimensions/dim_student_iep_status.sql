with
    -- Per-enrollment-stint PowerSchool enrollment range. Each row is one stint
    -- (entry/exit pair) for a (student, district); a student with multiple
    -- stints in the same district has multiple rows. Inner-joining the legs to
    -- this CTE per-stint clips IEP spans to the student's actual enrollment
    -- and drops phantom records. Multi-stint students get a separate dim row
    -- per stint, each clipped to its specific entry/exit window. Aggregating
    -- to min(entry)/max(exit) would wrongly span gaps between stints (e.g.,
    -- a Newark → Camden → Newark student would have a Newark range covering
    -- the Camden period).
    enrollments as (
        select
            student_number,
            _dbt_source_relation,
            _dbt_source_project,
            students_dcid,
            academic_year,
            entrydate,

            -- PowerSchool exitdate is half-open (first day AFTER stint).
            -- Subtract 1 day to get the inclusive last day so boundary-sharing
            -- stints (stint 1 exit = stint 2 entry) don't produce overlapping
            -- inclusive ends in the dim.
            coalesce(
                date_sub(exitdate, interval 1 day), cast('9999-12-31' as date)
            ) as enrollment_end,
        from {{ ref("int_powerschool__student_enrollment_union") }}
        -- graduates carry NULL entry/exit as a placeholder row; drop them
        -- (no enrollment context to clip against).
        where entrydate is not null
    ),

    nj_unioned as (
        select
            student_number,
            _dbt_source_project,
            special_education_code,
            effective_date,

            special_education as special_education_name,

            cast(nj_se_placement as string) as special_education_placement,

            -- edplan ships ~24% NULL spedlep; coalesce so NULL and 'No IEP'
            -- rows group into one island instead of splitting on the lag().
            coalesce(spedlep, 'No IEP') as iep_classification,

            -- pre-coalesce the open-ended span sentinel so nj_leg can use a
            -- plain max() without re-handling NULL.
            coalesce(
                effective_end_date, cast('9999-12-31' as date)
            ) as effective_end_date,

            -- fingerprint for island detection in nj_flagged
            format(
                '%T|%T|%T|%T',
                coalesce(spedlep, 'No IEP'),
                special_education_code,
                special_education,
                nj_se_placement
            ) as island_fingerprint,
        from {{ ref("int_edplan__njsmart_powerschool_union") }}
        -- edplan emits ~147 rows with NULL student_number that would otherwise
        -- collapse into one phantom partition (NULL=NULL in window functions)
        -- and hash to the dbt_utils null-sentinel student_key, producing
        -- spurious PK collisions across unrelated upstream rows.
        where student_number is not null
    ),

    nj_flagged as (
        select
            *,

            if(
                island_fingerprint = lag(island_fingerprint) over (
                    partition by student_number, _dbt_source_project
                    order by effective_date
                ),
                0,
                1
            ) as is_island_start,
        from nj_unioned
    ),

    nj_islanded as (
        select
            *,

            sum(is_island_start) over (
                partition by student_number, _dbt_source_project order by effective_date
            ) as island_id,
        from nj_flagged
    ),

    nj_leg_raw as (
        select
            student_number,
            _dbt_source_project,
            iep_classification,
            special_education_code,
            special_education_name,
            special_education_placement,

            min(effective_date) as effective_date_start,
            max(effective_end_date) as effective_date_end,
        from nj_islanded
        group by
            student_number,
            _dbt_source_project,
            iep_classification,
            special_education_code,
            special_education_name,
            special_education_placement,
            island_id
    ),

    nj_leg as (
        select
            l.student_number,
            l._dbt_source_project,
            l.iep_classification,
            l.special_education_code,
            l.special_education_name,
            l.special_education_placement,

            e._dbt_source_relation,
            e.academic_year,
            e.entrydate,

            greatest(l.effective_date_start, e.entrydate) as effective_date_start,
            least(l.effective_date_end, e.enrollment_end) as effective_date_end,
        from nj_leg_raw as l
        inner join
            enrollments as e
            on l.student_number = e.student_number
            and l._dbt_source_project = e._dbt_source_project
            and l.effective_date_start <= e.enrollment_end
            and l.effective_date_end >= e.entrydate
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

            coalesce(scf.spedlep, 'No IEP') as iep_classification,
        from enrollments as e
        left join
            {{ ref("stg_powerschool__studentcorefields") }} as scf
            on e.students_dcid = scf.studentsdcid
            and e._dbt_source_project = scf._dbt_source_project
        where e._dbt_source_project in ('kipppaterson', 'kippmiami')
    ),

    unioned as (
        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            academic_year,
            entrydate,
            iep_classification,
            effective_date_start,
            effective_date_end,
            special_education_code,
            special_education_name,
            special_education_placement,
        from nj_leg

        union all

        select
            student_number,
            _dbt_source_project,
            _dbt_source_relation,
            academic_year,
            entrydate,
            iep_classification,
            effective_date_start,
            effective_date_end,

            cast(null as string) as special_education_code,
            cast(null as string) as special_education_name,
            cast(null as string) as special_education_placement,
        from pm_leg
    )

select
    _dbt_source_project,
    iep_classification,
    special_education_code,
    special_education_name,
    special_education_placement,

    effective_date_start as effective_date_start_key,
    effective_date_end as effective_date_end_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_project", "effective_date_start"]
        )
    }} as student_iep_status_key,

    {{ dbt_utils.generate_surrogate_key(["student_number"]) }} as student_key,

    {{
        dbt_utils.generate_surrogate_key(
            ["student_number", "_dbt_source_relation", "academic_year", "entrydate"]
        )
    }} as student_enrollment_key,

    iep_classification != 'No IEP' as is_iep,
    effective_date_end = '9999-12-31' as is_current,
from unioned
