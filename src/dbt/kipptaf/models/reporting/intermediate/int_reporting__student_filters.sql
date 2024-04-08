with
    subjects as (
        select
            subject as iready_subject,
            case
                subject when 'Reading' then 'Text Study' when 'Math' then 'Mathematics'
            end as illuminate_subject_area,
            case
                subject when 'Reading' then 'ENG' when 'Math' then 'MATH'
            end as powerschool_credittype,
            case
                subject when 'Reading' then 'ela' when 'Math' then 'math'
            end as grad_unpivot_subject,
        from unnest(['Reading', 'Math']) as subject
    ),

    intervention_nj as (
        select
            st.local_student_id as student_number,

            regexp_extract(g.group_name, r'Bucket 2 - (Math|Reading) -') as subject,
        from {{ source("illuminate", "group_student_aff") }} as s
        inner join
            {{ source("illuminate", "groups") }} as g
            on s.group_id = g.group_id
            and g.group_name like 'Bucket 2%'
        left join
            {{ ref("stg_illuminate__students") }} as st on s.student_id = st.student_id
        where
            s.end_date is null
            or s.end_date > current_date('{{ var("local_timezone") }}')
    ),

    prev_yr_state_test as (
        select
            localstudentidentifier,
            safe_cast(statestudentidentifier as string) as statestudentidentifier,
            academic_year + 1 as academic_year_plus,
            case
                when subject like 'English Language Arts%'
                then 'Text Study'
                when subject in ('Algebra I', 'Algebra II', 'Geometry')
                then 'Mathematics'
                else subject
            end as subject,
            case
                when testperformancelevel < 3
                then 'Below/Far Below'
                when testperformancelevel = 3
                then 'Approaching'
                when testperformancelevel > 3
                then 'At/Above'
            end as njsla_proficiency,
        from {{ ref("stg_pearson__njsla") }}
    ),

    tutoring_nj as (
        select _dbt_source_relation, studentid, academic_year, 'Math' as iready_subject,
        from {{ ref("int_powerschool__spenrollments") }}
        where
            specprog_name = 'Tutoring'
            and current_date('{{ var("local_timezone") }}')
            between enter_date and exit_date
    ),

    prev_yr_iready as (
        select
            student_id,
            subject,
            academic_year_int + 1 as academic_year_plus,
            case
                when overall_relative_placement_int < 3
                then 'Below/Far Below'
                when overall_relative_placement_int = 3
                then 'Approaching'
                when overall_relative_placement_int > 3
                then 'At/Above'
            end as iready_proficiency,
        from {{ ref("base_iready__diagnostic_results") }}
        where rn_subj_round = 1 and test_round = 'EOY'
    ),

    composite_only as (
        select
            bss.academic_year,
            bss.student_primary_id as student_number,
            bss.benchmark_period as mclass_period,
            u.level as mclass_measure_level,
        from {{ ref("stg_amplify__benchmark_student_summary") }} as bss
        inner join
            {{ ref("int_amplify__benchmark_student_summary_unpivot") }} as u
            on bss.surrogate_key = u.surrogate_key
        where
            bss.academic_year = {{ var("current_academic_year") }}
            and u.measure = 'Composite'
    ),

    dibels_overall_composite_by_window as (
        select distinct academic_year, student_number, p.boy, p.moy, p.eoy,
        from
            composite_only pivot (
                max(mclass_measure_level) for mclass_period in ('BOY', 'MOY', 'EOY')
            ) as p
    ),

    iready_exempt as (
        select
            students_student_number as student_number,
            cc_academic_year as academic_year,
            true as `value`,
            case
                when sections_section_number = 'mgmath'
                then 'Math'
                when sections_section_number = 'mgela'
                then 'Reading'
            end as iready_subject,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            courses_course_number = 'LOG300'
            and sections_section_number in ('mgmath', 'mgela')
            and not is_dropped_section
            and rn_course_number_year = 1
    ),

    mia_territory as (
        select
            a.student_school_id as student_number,
            r.roster_name as territory,
            row_number() over (
                partition by a.student_school_id order by r.roster_id asc
            ) as rn_territory,
        from {{ ref("stg_deanslist__rosters") }} as r
        left join
            {{ ref("stg_deanslist__roster_assignments") }} as a
            on r.roster_id = a.dl_roster_id
        where r.school_id = 472 and r.roster_type = 'House' and r.active = 'Y'
    )

select
    co.academic_year,
    co._dbt_source_relation,
    co.student_number,
    co.studentid,

    sj.iready_subject,
    sj.illuminate_subject_area,
    sj.powerschool_credittype,
    sj.grad_unpivot_subject,

    a.is_iep_eligible as is_grad_iep_exempt,

    mt.territory,

    coalesce(db.boy, 'No Test') as dibels_boy_composite,
    coalesce(db.moy, 'No Test') as dibels_moy_composite,
    coalesce(db.eoy, 'No Test') as dibels_eoy_composite,

    if(nj.subject is not null, true, false) as bucket_two,

    coalesce(py.njsla_proficiency, 'No Test') as state_test_proficiency,

    if(t.iready_subject is not null, true, false) as tutoring_nj,

    coalesce(pr.iready_proficiency, 'No Test') as iready_proficiency_eoy,

    if(co.grade_level < 4, pr.iready_proficiency, py.njsla_proficiency) as bucket_one,

    case
        when co.grade_level < 4 and pr.iready_proficiency = 'At/Above'
        then 'Bucket 1'
        when co.grade_level >= 4 and py.njsla_proficiency = 'At/Above'
        then 'Bucket 1'
        when nj.subject is not null
        then 'Bucket 2'
    end as nj_student_tier,

    coalesce(ie.value, false) as is_exempt_iready,

    if(
        co.grade_level >= 9, sj.powerschool_credittype, sj.illuminate_subject_area
    ) as assessment_dashboard_join,
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as sj
left join
    intervention_nj as nj
    on co.student_number = nj.student_number
    and sj.iready_subject = nj.subject
left join
    prev_yr_state_test as py
    {# TODO: find records that only match on SID #}
    on co.student_number = py.localstudentidentifier
    and co.academic_year = py.academic_year_plus
    and sj.illuminate_subject_area = py.subject
left join
    tutoring_nj as t
    on co.studentid = t.studentid
    and co.academic_year = t.academic_year
    and sj.iready_subject = t.iready_subject
    and {{ union_dataset_join_clause(left_alias="co", right_alias="t") }}
left join
    prev_yr_iready as pr
    on co.student_number = pr.student_id
    and co.academic_year = pr.academic_year_plus
    and sj.iready_subject = pr.subject
left join
    dibels_overall_composite_by_window as db
    on co.academic_year = db.academic_year
    and co.student_number = db.student_number
    and sj.iready_subject = 'Reading'
left join
    iready_exempt as ie
    on co.academic_year = ie.academic_year
    and co.student_number = ie.student_number
    and sj.iready_subject = ie.iready_subject
left join
    {{ ref("int_powerschool__nj_graduation_pathway_unpivot") }} as a
    on co.students_dcid = a.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="a") }}
    and sj.grad_unpivot_subject = a.subject
    and a.values_column = 'M'
left join
    mia_territory as mt on co.student_number = mt.student_number and mt.rn_territory = 1
where co.rn_year = 1 and co.academic_year >= {{ var("current_academic_year") }} - 1
