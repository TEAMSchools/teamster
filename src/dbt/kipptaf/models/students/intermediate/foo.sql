with
    subjects as (
        select
            iready_subject,

            if(iready_subject = 'Reading', 'ELA', iready_subject) as discipline,

            case
                iready_subject
                when 'Reading'
                then 'Text Study'
                when 'Math'
                then 'Mathematics'
            end as illuminate_subject_area,
        from unnest(['Reading', 'Math']) as iready_subject
    ),

    intervention_nj as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,

            regexp_extract(specprog_name, 'Bucket 2 - (\w+)') as discipline,
        from {{ ref("int_powerschool__spenrollments") }}
        where
            rn_student_program_year_desc = 1
            and specprog_name in ('Bucket 2 - ELA', 'Bucket 2 - Math')
    ),

    prev_yr_state_test as (
        select
            _dbt_source_relation,
            localstudentidentifier,
            academic_year,
            is_proficient,

            cast(statestudentidentifier as string) as statestudentidentifier,

            case
                when `subject` like 'English Language Arts%'
                then 'Text Study'
                when `subject` in ('Algebra I', 'Algebra II', 'Geometry')
                then 'Mathematics'
                else `subject`
            end as `subject`,

            case
                when testperformancelevel < 3
                then 'Below/Far Below'
                when testperformancelevel = 3
                then 'Approaching'
                when testperformancelevel > 3
                then 'At/Above'
            end as njsla_proficiency,
        from {{ ref("int_pearson__all_assessments") }}

        union all

        select
            _dbt_source_relation,

            null as localstudentidentifier,

            academic_year,
            is_proficient,
            student_id as statestudentidentifier,

            case
                when assessment_subject like 'English Language Arts%'
                then 'Text Study'
                when assessment_subject in ('Algebra I', 'Algebra II', 'Geometry')
                then 'Mathematics'
                else assessment_subject
            end as `subject`,

            case
                when achievement_level_int = 1
                then 'Below/Far Below'
                when achievement_level_int = 2
                then 'Approaching'
                when achievement_level_int >= 3
                then 'At/Above'
            end as proficiency,
        from {{ ref("int_fldoe__all_assessments") }}
        where
            scale_score is not null
            and assessment_name = 'FAST'
            and administration_window = 'PM3'
    ),

    psat_bucket1 as (
        select powerschool_student_number, discipline, max(score) as max_score,
        from {{ ref("int_collegeboard__psat_unpivot") }}
        where test_subject in ('EBRW', 'Math') and test_type != 'PSAT 8/9'
        group by powerschool_student_number, discipline
    ),

    prev_yr_iready as (
        select
            _dbt_source_relation,
            student_id,
            `subject`,
            academic_year_int as academic_year,

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

    cur_yr_iready as (
        select
            _dbt_source_relation,
            student_id as student_number,
            academic_year_int as academic_year,
            `subject`,
            projected_is_proficient_typical as is_proficient,
        from {{ ref("base_iready__diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and projected_sublevel_number_typical is not null
            and student_grade_int between 3 and 8

        union all

        select
            _dbt_source_relation,
            student_id as student_number,
            academic_year_int as academic_year,
            `subject`,

            if(level_number_with_typical >= 4, true, false) as is_proficient,
        from {{ ref("base_iready__diagnostic_results") }}
        where
            test_round = 'BOY'
            and rn_subj_round = 1
            and sublevel_number_with_typical is not null
            and student_grade_int between 0 and 2
    )

select
    co._dbt_source_relation,
    co.student_number,
    co.academic_year,

    sj.iready_subject,
    sj.discipline,
    sj.illuminate_subject_area,

    a.values_column as ps_grad_path_code,

    coalesce(a.is_iep_eligible, false) as is_grad_iep_exempt,

    coalesce(py.njsla_proficiency, 'No Test') as state_test_proficiency,

    coalesce(pr.iready_proficiency, 'No Test') as iready_proficiency_eoy,

    if(nj.iready_subject is not null, true, false) as bucket_two,

    if(co.grade_level < 4, pr.iready_proficiency, py.njsla_proficiency) as bucket_one,

    /* years are hardcoded here because of changes on how buckets are calculated from
    one sy to the next */
    case
        when
            co.academic_year = 2023
            and co.grade_level < 4
            and pr.iready_proficiency = 'At/Above'
        then 'Bucket 1'
        when
            co.academic_year = 2023
            and co.grade_level >= 4
            and py.njsla_proficiency = 'At/Above'
        then 'Bucket 1'
        when
            co.academic_year >= 2024
            and co.grade_level between 0 and 8
            and coalesce(py.is_proficient, ci.is_proficient)
        then 'Bucket 1'
        when co.academic_year >= 2024 and co.grade_level = 11 and ps.max_score >= 420
        then 'Bucket 1'
        when nj.iready_subject is not null
        then 'Bucket 2'
        else 'Unbucketed'
    end as nj_student_tier,

    case
        when
            co.grade_level < 3
            and co.is_self_contained
            and co.special_education_code in ('CMI', 'CMO', 'CSE')
        then true
        when sj.discipline = 'ELA' and se.values_column in ('2', '3', '4')
        then true
        when sj.discipline = 'Math' and se.values_column = '3'
        then true
        else false
    end as is_exempt_state_testing,

from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as sj
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as a
    on co.students_dcid = a.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="a") }}
    and sj.discipline = a.discipline
    and a.value_type = 'Graduation Pathway'
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as se
    on co.students_dcid = se.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="se") }}
    and sj.discipline = se.discipline
    and se.value_type = 'State Assessment Name'
left join
    prev_yr_state_test as py
    /* TODO: find records that only match on SID */
    on co.state_studentnumber = py.statestudentidentifier
    and co.academic_year = (py.academic_year + 1)
    and {{ union_dataset_join_clause(left_alias="co", right_alias="py") }}
    and sj.illuminate_subject_area = py.subject
left join
    prev_yr_iready as pr
    on co.student_number = pr.student_id
    and co.academic_year = (pr.academic_year + 1)
    and {{ union_dataset_join_clause(left_alias="co", right_alias="pr") }}
    and sj.iready_subject = pr.subject
left join
    cur_yr_iready as ci
    on co.student_number = ci.student_number
    and co.academic_year = ci.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ci") }}
    and sj.iready_subject = ci.subject
left join
    intervention_nj as nj
    on co.studentid = nj.studentid
    and co.academic_year = nj.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
    and sj.discipline = nj.discipline
left join
    psat_bucket1 as ps
    on co.student_number = ps.powerschool_student_number
    and sj.discipline = ps.discipline
where co.rn_year = 1
