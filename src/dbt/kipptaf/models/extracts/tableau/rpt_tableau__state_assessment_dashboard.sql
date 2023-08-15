with
    promo as (
        select
            student_number,
            _dbt_source_relation,
            if(es is not null, true, false) as attended_es,
            if(ms is not null, true, false) as attended_ms,
        from
            {{ ref("base_powerschool__student_enrollments") }}
            pivot (max(grade_level) for school_level in ('ES', 'MS'))
        where rn_school = 1
    ),

    ms_enr as (
        select student_number, exitdate, school_name, _dbt_source_relation,
        from {{ ref("base_powerschool__student_enrollments") }}
        where school_level = 'MS'
    ),

    ms_grad as (
        {{
            dbt_utils.deduplicate(
                relation="ms_enr",
                partition_by="student_number",
                order_by="exitdate desc",
            )
        }}
    ),

    ps_users as (
        select
            u.lastfirst,
            u._dbt_source_relation,
            safe_cast(u.sif_stateprid as int) as sif_stateprid,
        from {{ ref("stg_powerschool__users") }} as u
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on u.homeschoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="u", right_alias="sch") }}
    ),

    njdoe_parcc as (
        select
            academic_year,
            test_code,
            valid_scores,
            proficient_count,
            coalesce(district_name, 'STATE') as district_name,
        from {{ ref("stg_njdoe__parcc") }}
        where
            subgroup = 'TOTAL'
            and school_code is null
            and (
                district_name in ('NEWARK CITY', 'CAMDEN CITY')
                or (district_name is null and dfg is null)
            )

    ),

    external_prof as (
        select
            academic_year,
            test_code,
            safe_divide(
                proficient_count_total_state, valid_scores_total_state
            ) as percent_proficient_state,
            safe_divide(
                proficient_count_total_newark, valid_scores_total_newark
            ) as percent_proficient_newark,
            safe_divide(
                proficient_count_total_camden, valid_scores_total_camden
            ) as percent_proficient_camden,
        from
            njdoe_parcc pivot (
                sum(valid_scores) as valid_scores_total,
                sum(proficient_count) as proficient_count_total
                for district_name in (
                    'STATE' as `state`,
                    'NEWARK CITY' as `newark`,
                    'CAMDEN CITY' as `camden`
                )
            )
    )

select
    co.student_number,
    co.lastfirst,
    co.academic_year,
    co.region,
    co.school_level,
    co.reporting_schoolid as schoolid,
    co.school_abbreviation,
    co.grade_level,
    co.cohort,
    co.entry_schoolid,
    co.entry_grade_level,
    co.enroll_status,
    co.lep_status,
    co.lunch_status as lunchstatus,
    co.ethnicity,
    co.gender,

    parcc.test_code,
    parcc.subject,
    parcc.test_scale_score,
    parcc.test_performance_level,
    parcc.test_reading_csem as test_standard_error,
    parcc.staff_member_identifier,
    case
        when parcc.student_with_disabilities in ('IEP', 'Y', 'B')
        then 'SPED'
        else 'No IEP'
    end as iep_status,
    case
        when parcc.subject = 'Science' and parcc.test_performance_level >= 3
        then 1.0
        when parcc.subject = 'Science' and parcc.test_performance_level < 3
        then 0.0
        when parcc.test_performance_level >= 4
        then 1.0
        when parcc.test_performance_level < 4
        then 0.0
    end as is_proficient,

    promo.attended_es,
    promo.attended_ms,

    ms.school_name as ms_attended,

    pu.lastfirst as teacher_lastfirst,

    ext.percent_proficient_state as pct_prof_nj,
    ext.percent_proficient_newark as pct_prof_nps,
    ext.percent_proficient_camden as pct_prof_cps,
    null as pct_prof_parcc,

    'PARCC' as test_type,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    {{ ref("stg_pearson__parcc") }} as parcc
    on co.student_number = parcc.local_student_identifier
    and co.academic_year = parcc.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="parcc") }}
left join
    promo
    on co.student_number = promo.student_number
    and {{ union_dataset_join_clause(left_alias="co", right_alias="promo") }}
left join
    ms_grad as ms
    on co.student_number = ms.student_number
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ms") }}
left join
    ps_users as pu
    on parcc.staff_member_identifier = pu.sif_stateprid
    and {{ union_dataset_join_clause(left_alias="parcc", right_alias="pu") }}
left join
    external_prof as ext
    on parcc.test_code = ext.test_code
    and parcc.academic_year = ext.academic_year
where co.rn_year = 1
