{{- config(materialized="table") -}}

with
    subjects as (
        select
            iready_subject,

            case
                iready_subject
                when 'Reading'
                then 'Text Study'
                when 'Math'
                then 'Mathematics'
            end as illuminate_subject_area,

            case
                iready_subject when 'Reading' then 'ENG' when 'Math' then 'MATH'
            end as powerschool_credittype,

            case
                iready_subject when 'Reading' then 'ela' when 'Math' then 'math'
            end as grad_unpivot_subject,

            case
                iready_subject when 'Reading' then 'ELA' when 'Math' then 'Math'
            end as discipline,
        from unnest(['Reading', 'Math']) as iready_subject
    ),

    intervention_nj as (
        select
            _dbt_source_relation,
            studentid,
            academic_year,

            if(specprog_name = 'Bucket 2 - ELA', 'Reading', 'Math') as iready_subject,
        from {{ ref("int_powerschool__spenrollments") }}
        where specprog_name in ('Bucket 2 - ELA', 'Bucket 2 - Math')
    ),

    prev_yr_state_test as (
        select
            _dbt_source_relation,
            localstudentidentifier,

            cast(statestudentidentifier as string) as statestudentidentifier,

            academic_year + 1 as academic_year_plus,

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
            if(testperformancelevel > 3, true, false) as is_proficient,
        from {{ ref("stg_pearson__njsla") }}

        union all

        select
            _dbt_source_relation,
            null as localstudentidentifier,
            student_id as statestudentidentifier,

            academic_year + 1 as academic_year_plus,

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
            is_proficient,
        from {{ ref("int_fldoe__all_assessments") }}
        where
            scale_score is not null
            and assessment_name = 'FAST'
            and administration_window = 'PM3'
    ),

    psat_bucket1 as (
        select powerschool_student_number, discipline, max(score) as max_score,
        from {{ ref("int_collegeboard__psat_unpivot") }} as pt
        where test_subject in ('EBRW', 'Math') and test_type != 'PSAT 8/9'
        group by all
    ),

    prev_yr_iready as (
        select
            student_id,
            `subject`,

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

    cur_yr_iready as (
        select
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
    ),

    iready_exempt as (
        select
            _dbt_source_relation,
            students_student_number as student_number,
            cc_academic_year as academic_year,

            case
                sections_section_number
                when 'mgmath'
                then 'Math'
                when 'mgela'
                then 'Reading'
            end as iready_subject,
        from {{ ref("base_powerschool__course_enrollments") }}
        where
            courses_course_number = 'LOG300'
            and rn_course_number_year = 1
            and sections_section_number in ('mgmath', 'mgela')
            and not is_dropped_section
    ),

    dibels as (
        select
            mclass_student_number,
            mclass_academic_year,
            boy_composite,
            moy_composite,
            eoy_composite,

            'Reading' as iready_subject,

            row_number() over (
                partition by mclass_student_number, mclass_academic_year
                order by mclass_client_date desc
            ) as rn_year,
        from {{ ref("int_amplify__all_assessments") }}
        where mclass_measure_standard = 'Composite'
    )

-- current year and current year - 1 only to honor bucket calcs
select
    co.*,

    sj.iready_subject,
    sj.illuminate_subject_area,
    sj.powerschool_credittype,
    sj.grad_unpivot_subject,
    sj.discipline,

    a.is_iep_eligible as is_grad_iep_exempt,

    coalesce(py.njsla_proficiency, 'No Test') as state_test_proficiency,

    coalesce(pr.iready_proficiency, 'No Test') as iready_proficiency_eoy,

    coalesce(db.boy_composite, 'No Test') as dibels_boy_composite,
    coalesce(db.moy_composite, 'No Test') as dibels_moy_composite,
    coalesce(db.eoy_composite, 'No Test') as dibels_eoy_composite,
    coalesce(
        db.eoy_composite,
        db.moy_composite,
        db.boy_composite,
        'No Composite Score Available'
    ) as dibels_most_recent_composite,

    if(ie.student_number is not null, true, false) as is_exempt_iready,

    if(nj.iready_subject is not null, true, false) as bucket_two,

    if(co.grade_level < 4, pr.iready_proficiency, py.njsla_proficiency) as bucket_one,

    if(
        co.grade_level >= 9, sj.powerschool_credittype, sj.illuminate_subject_area
    ) as assessment_dashboard_join,

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
from {{ ref("int_extracts__student_enrollments") }} as co
cross join subjects as sj
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as a
    on co.students_dcid = a.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="a") }}
    and sj.discipline = a.discipline
    and a.value_type = 'Graduation Pathway'
    and a.values_column = 'M'
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as se
    on co.students_dcid = se.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="se") }}
    and sj.discipline = se.discipline
    and se.value_type = 'State Assessment Name'
left join
    prev_yr_state_test as py
    {# TODO: find records that only match on SID #}
    on co.student_number = py.localstudentidentifier
    and co.academic_year = py.academic_year_plus
    and {{ union_dataset_join_clause(left_alias="co", right_alias="py") }}
    and sj.illuminate_subject_area = py.subject
left join
    prev_yr_iready as pr
    on co.student_number = pr.student_id
    and co.academic_year = pr.academic_year_plus
    and sj.iready_subject = pr.subject
left join
    dibels as db
    on co.student_number = db.mclass_student_number
    and co.academic_year = db.mclass_academic_year
    and sj.iready_subject = db.iready_subject
    and db.rn_year = 1
left join
    iready_exempt as ie
    on co.student_number = ie.student_number
    and co.academic_year = ie.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ie") }}
    and sj.iready_subject = ie.iready_subject
left join
    intervention_nj as nj
    on co.studentid = nj.studentid
    and co.academic_year = nj.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
    and sj.iready_subject = nj.iready_subject
left join
    cur_yr_iready as ci
    on co.student_number = ci.student_number
    and co.academic_year = ci.academic_year
    and sj.iready_subject = ci.subject
left join
    psat_bucket1 as ps
    on co.student_number = ps.powerschool_student_number
    and sj.discipline = ps.discipline
where co.academic_year >= {{ var("current_academic_year") - 1 }}

union all

/* academic year < current year - 1 */
select
    co.*,

    sj.iready_subject,
    sj.illuminate_subject_area,
    sj.powerschool_credittype,
    sj.grad_unpivot_subject,
    sj.discipline,

    a.is_iep_eligible as is_grad_iep_exempt,

    coalesce(py.njsla_proficiency, 'No Test') as state_test_proficiency,

    coalesce(pr.iready_proficiency, 'No Test') as iready_proficiency_eoy,

    coalesce(db.boy_composite, 'No Test') as dibels_boy_composite,
    coalesce(db.moy_composite, 'No Test') as dibels_moy_composite,
    coalesce(db.eoy_composite, 'No Test') as dibels_eoy_composite,
    coalesce(
        db.eoy_composite,
        db.moy_composite,
        db.boy_composite,
        'No Composite Score Available'
    ) as dibels_most_recent_composite,

    if(ie.student_number is not null, true, false) as is_exempt_iready,

    if(nj.iready_subject is not null, true, false) as bucket_two,

    if(co.grade_level < 4, pr.iready_proficiency, py.njsla_proficiency) as bucket_one,

    if(
        co.grade_level >= 9, sj.powerschool_credittype, sj.illuminate_subject_area
    ) as assessment_dashboard_join,

    null as nj_student_tier,

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
from {{ ref("int_extracts__student_enrollments") }} as co
cross join subjects as sj
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as a
    on co.students_dcid = a.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="a") }}
    and sj.discipline = a.discipline
    and a.value_type = 'Graduation Pathway'
    and a.values_column = 'M'
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as se
    on co.students_dcid = se.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="se") }}
    and sj.discipline = se.discipline
    and se.value_type = 'State Assessment Name'
left join
    prev_yr_state_test as py
    {# TODO: find records that only match on SID #}
    on co.student_number = py.localstudentidentifier
    and co.academic_year = py.academic_year_plus
    and {{ union_dataset_join_clause(left_alias="co", right_alias="py") }}
    and sj.illuminate_subject_area = py.subject
left join
    prev_yr_iready as pr
    on co.student_number = pr.student_id
    and co.academic_year = pr.academic_year_plus
    and sj.iready_subject = pr.subject
left join
    dibels as db
    on co.student_number = db.mclass_student_number
    and co.academic_year = db.mclass_academic_year
    and sj.iready_subject = db.iready_subject
    and db.rn_year = 1
left join
    iready_exempt as ie
    on co.student_number = ie.student_number
    and co.academic_year = ie.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ie") }}
    and sj.iready_subject = ie.iready_subject
left join
    intervention_nj as nj
    on co.studentid = nj.studentid
    and co.academic_year = nj.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
    and sj.iready_subject = nj.iready_subject
left join
    cur_yr_iready as ci
    on co.student_number = ci.student_number
    and co.academic_year = ci.academic_year
    and sj.iready_subject = ci.subject
where co.academic_year < {{ var("current_academic_year") - 1 }}
