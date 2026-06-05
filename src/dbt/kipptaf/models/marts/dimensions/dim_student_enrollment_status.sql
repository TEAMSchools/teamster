with
    -- ELL: at most one span per stint; LEFT JOIN returns NULL when absent.
    ell as (
        select student_enrollment_key, is_ell, from {{ ref("dim_student_ell_status") }}
    ),

    -- IEP: latest span per stint (max effective_date_start_key).
    -- All five IEP columns come from the same row.
    iep_ranked as (
        select
            student_enrollment_key,
            is_iep,
            iep_classification,
            special_education_code,
            special_education_name,
            special_education_placement,

            row_number() over (
                partition by student_enrollment_key
                order by effective_date_start_key desc
            ) as rn,
        from {{ ref("dim_student_iep_status") }}
    ),

    iep as (
        select
            student_enrollment_key,
            is_iep,
            iep_classification,
            special_education_code,
            special_education_name,
            special_education_placement,
        from iep_ranked
        where rn = 1
    ),

    -- Meal: NJ = span covering Oct 15 of academic_year; if none, earliest span.
    -- Miami = latest span. Both fields from the same row.
    --
    -- NJ districts: kippnewark, kippcamden, kipppaterson
    -- Miami district: kippmiami
    meal_nj_oct15 as (
        select
            mel.student_enrollment_key,
            mel.is_meal_eligible,
            mel.meal_eligibility,

            row_number() over (
                partition by mel.student_enrollment_key
                order by mel.effective_date_start_key
            ) as rn,
        from {{ ref("dim_student_meal_eligibility_status") }} as mel
        inner join
            {{ ref("dim_student_enrollments") }} as enr
            on mel.student_enrollment_key = enr.student_enrollment_key
        where
            mel._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
            and date(enr.academic_year, 10, 15)
            between mel.effective_date_start_key and mel.effective_date_end_key
    ),

    -- NJ fallback: earliest span in the stint when no Oct-15 span exists.
    meal_nj_fallback as (
        select
            mel.student_enrollment_key,
            mel.is_meal_eligible,
            mel.meal_eligibility,

            row_number() over (
                partition by mel.student_enrollment_key
                order by mel.effective_date_start_key
            ) as rn,
        from {{ ref("dim_student_meal_eligibility_status") }} as mel
        where mel._dbt_source_project in ('kippnewark', 'kippcamden', 'kipppaterson')
    ),

    meal_miami as (
        select
            mel.student_enrollment_key,
            mel.is_meal_eligible,
            mel.meal_eligibility,

            row_number() over (
                partition by mel.student_enrollment_key
                order by mel.effective_date_start_key desc
            ) as rn,
        from {{ ref("dim_student_meal_eligibility_status") }} as mel
        where mel._dbt_source_project = 'kippmiami'
    ),

    meal as (
        select student_enrollment_key, is_meal_eligible, meal_eligibility,
        from meal_nj_oct15
        where rn = 1

        union all

        select fb.student_enrollment_key, fb.is_meal_eligible, fb.meal_eligibility,
        from meal_nj_fallback as fb
        where
            rn = 1
            and fb.student_enrollment_key not in (
                select meal_nj_oct15.student_enrollment_key,
                from meal_nj_oct15
                where meal_nj_oct15.rn = 1
            )

        union all

        select student_enrollment_key, is_meal_eligible, meal_eligibility,
        from meal_miami
        where rn = 1
    )

select
    enr.student_enrollment_key,
    iep.iep_classification,
    iep.special_education_code,
    iep.special_education_name,
    iep.special_education_placement,
    meal.meal_eligibility,

    coalesce(ell.is_ell, false) as is_ell,
    coalesce(iep.is_iep, false) as is_iep,
    coalesce(meal.is_meal_eligible, false) as is_meal_eligible,

from {{ ref("dim_student_enrollments") }} as enr
left join ell on enr.student_enrollment_key = ell.student_enrollment_key
left join iep on enr.student_enrollment_key = iep.student_enrollment_key
left join meal on enr.student_enrollment_key = meal.student_enrollment_key
