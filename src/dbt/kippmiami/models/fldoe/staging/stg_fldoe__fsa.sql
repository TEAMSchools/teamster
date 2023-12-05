with
    fsa as (
        select
            dis as district_id,
            sch as school_id,
            tgrade as test_grade,
            schoolyear as school_year,
            scoreflag as score_flag,
            nullif(trim(fleid), '') as fleid,
            nullif(trim(testname), '') as test_name,
            nullif(trim(pass), '') as pass,
            nullif(trim(disname), '') as district_name,
            nullif(trim(schname), '') as school_name,
            nullif(trim(firstname), '') as first_name,
            nullif(trim(mi), '') as mi,
            nullif(trim(lastname), '') as last_name,
            nullif(trim(rptstatus), '') as report_status,
            nullif(trim(conditioncode), '') as condition_code,
            nullif(trim(earn1_ptpos1), '') as earn1_ptpos1,
            nullif(trim(earn2_ptpos2), '') as earn2_ptpos2,
            nullif(trim(earn3_ptpos3), '') as earn3_ptpos3,
            nullif(trim(earn4_ptpos4), '') as earn4_ptpos4,
            nullif(trim(earn5_ptpos5), '') as earn5_ptpos5,
            nullif(trim(earn_wd1_ptpos_wd1), '') as earn_wd1_ptpos_wd1,
            nullif(trim(earn_wd2_ptpos_wd2), '') as earn_wd2_ptpos_wd2,
            nullif(trim(earn_wd3_ptpos_wd3), '') as earn_wd3_ptpos_wd3,
            nullif(trim(scoreflag_w), '') as score_flag_w,
            coalesce(
                safe_cast(trim(scoreflag_r.string_value) as int), scoreflag_r.long_value
            ) as score_flag_r,
            coalesce(
                safe_cast(trim(scalescore.string_value) as int), scalescore.long_value
            ) as scale_score,
            coalesce(
                safe_cast(trim(performancelevel.string_value) as int),
                performancelevel.long_value
            ) as performance_level,
            safe_cast(left(safe_cast(schoolyear as string), 2) as int)
            + 2000 as academic_year,
        from {{ source("fldoe", "src_fldoe__fsa") }}
    )

select
    fleid,
    test_name,
    test_grade,
    scale_score,
    performance_level,
    pass,
    district_id,
    district_name,
    school_id,
    school_name,
    school_year,
    first_name,
    mi,
    last_name,
    condition_code,
    report_status,
    score_flag,
    score_flag_r,
    score_flag_w,
    regexp_extract(test_name, r'^(\w+)\s') as administration_round,
    regexp_extract(test_name, r'^\w+\s\d+\s(\w+)\s\d+$') as test_subject,
    safe_cast(regexp_extract(test_name, r'^\w+\s(\d+)') as int) - 1 as academic_year,
    safe_cast(split(earn1_ptpos1, '/')[0] as int) as earn1,
    safe_cast(split(earn1_ptpos1, '/')[1] as int) as ptpos1,
    safe_cast(split(earn2_ptpos2, '/')[0] as int) as earn2,
    safe_cast(split(earn2_ptpos2, '/')[1] as int) as ptpos2,
    safe_cast(split(earn3_ptpos3, '/')[0] as int) as earn3,
    safe_cast(split(earn3_ptpos3, '/')[1] as int) as ptpos3,
    safe_cast(split(earn4_ptpos4, '/')[0] as int) as earn4,
    safe_cast(split(earn4_ptpos4, '/')[1] as int) as ptpos4,
    safe_cast(split(earn5_ptpos5, '/')[0] as int) as earn5,
    safe_cast(split(earn5_ptpos5, '/')[1] as int) as ptpos5,
    safe_cast(split(earn_wd1_ptpos_wd1, '/')[0] as int) as earn_wd1,
    safe_cast(split(earn_wd1_ptpos_wd1, '/')[1] as int) as ptpos_wd1,
    safe_cast(split(earn_wd2_ptpos_wd2, '/')[0] as int) as earn_wd2,
    safe_cast(split(earn_wd2_ptpos_wd2, '/')[1] as int) as ptpos_wd2,
    safe_cast(split(earn_wd3_ptpos_wd3, '/')[0] as int) as earn_wd3,
    safe_cast(split(earn_wd3_ptpos_wd3, '/')[1] as int) as ptpos_wd3,
    case
        performance_level
        when 1
        then 'Inadequate'
        when 2
        then 'Below Satisfactory'
        when 3
        then 'Satisfactory'
        when 4
        then 'Proficient'
        when 5
        then 'Mastery'
    end as achievement_level,
    if(performance_level >= 3, 'true', 'false') as is_proficient,
from fsa
