with
    subjects as (
        select
            `subject` as iready_subject,

            case
                `subject`
                when 'Reading'
                then 'Text Study'
                when 'Math'
                then 'Mathematics'
            end as illuminate_subject_area,

            case
                `subject` when 'Reading' then 'ENG' when 'Math' then 'MATH'
            end as powerschool_credittype,

            case
                `subject` when 'Reading' then 'ela' when 'Math' then 'math'
            end as grad_unpivot_subject,

            case
                `subject` when 'Reading' then 'ELA' when 'Math' then 'Math'
            end as discipline,
        from unnest(['Reading', 'Math']) as `subject`
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
    ),

    psat_bucket1 as (
        select
            safe_cast(pt.local_student_id as int) as local_student_id,

            if(
                pt.score_type = 'sat10_eb_read_write_section_score', 'ELA', 'Math'
            ) as discipline,

            max(pt.score) as score,

            if(max(pt.score) >= 420, 'Bucket 1', null) as bucket_1,
        from {{ ref("int_illuminate__psat_unpivot") }} as pt
        inner join
            {{ ref("base_powerschool__student_enrollments") }} as co
            on safe_cast(pt.local_student_id as int) = co.student_number
            and pt.academic_year = co.academic_year
            and co.rn_year = 1
            and co.grade_level = 10
        where
            pt.score_type
            in ('psat10_math_section_score', 'psat10_eb_read_write_section_score')
        group by all
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
            _dbt_source_relation,
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
    ),

    iready_exempt as (
        select
            _dbt_source_relation,
            students_student_number as student_number,
            cc_academic_year as academic_year,

            true as `value`,

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
            and not is_dropped_section
            and sections_section_number in ('mgmath', 'mgela')
    ),

    mia_territory as (
        select
            r._dbt_source_relation,
            r.roster_name as territory,

            a.student_school_id as student_number,

            row_number() over (
                partition by a.student_school_id order by r.roster_id asc
            ) as rn_territory,
        from {{ ref("stg_deanslist__rosters") }} as r
        left join
            {{ ref("stg_deanslist__roster_assignments") }} as a
            on r.roster_id = a.dl_roster_id
        where r.school_id = 472 and r.roster_type = 'House' and r.active = 'Y'
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

select
    co._dbt_source_relation,
    co.student_number,
    co.studentid,
    co.academic_year,
    co.gifted_and_talented,

    sj.iready_subject,
    sj.illuminate_subject_area,
    sj.powerschool_credittype,
    sj.grad_unpivot_subject,
    sj.discipline,

    a.is_iep_eligible as is_grad_iep_exempt,

    mt.territory,

    coalesce(py.njsla_proficiency, 'No Test') as state_test_proficiency,

    coalesce(pr.iready_proficiency, 'No Test') as iready_proficiency_eoy,

    coalesce(ie.value, false) as is_exempt_iready,

    coalesce(db.boy_composite, 'No Test') as dibels_boy_composite,
    coalesce(db.moy_composite, 'No Test') as dibels_moy_composite,
    coalesce(db.eoy_composite, 'No Test') as dibels_eoy_composite,
    coalesce(
        db.eoy_composite,
        db.moy_composite,
        db.boy_composite,
        'No Composite Score Available'
    ) as dibels_most_recent_composite,

    if(nj.iready_subject is not null, true, false) as bucket_two,

    if(t.iready_subject is not null, true, false) as tutoring_nj,

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
            co.academic_year > 2023
            and co.grade_level between 0 and 8
            and coalesce(py.is_proficient, ci.is_proficient)
        then 'Bucket 1'
        when co.academic_year > 2023 and co.grade_level = 11 and ps.bucket_1 is not null
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
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as sj
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as se
    on co.students_dcid = se.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="se") }}
    and sj.discipline = se.discipline
    and se.value_type = 'State Assessment Name'
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as a
    on co.students_dcid = a.studentsdcid
    and {{ union_dataset_join_clause(left_alias="co", right_alias="a") }}
    and sj.discipline = a.discipline
    and a.value_type = 'Graduation Pathway'
    and a.values_column = 'M'
left join
    intervention_nj as nj
    on co.studentid = nj.studentid
    and co.academic_year = nj.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="nj") }}
    and sj.iready_subject = nj.iready_subject
left join
    tutoring_nj as t
    on co.studentid = t.studentid
    and co.academic_year = t.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="t") }}
    and sj.iready_subject = t.iready_subject
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
    and {{ union_dataset_join_clause(left_alias="co", right_alias="pr") }}
    and sj.iready_subject = pr.subject
left join
    cur_yr_iready as ci
    on co.student_number = ci.student_number
    and co.academic_year = ci.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ci") }}
    and sj.iready_subject = ci.subject
left join
    iready_exempt as ie
    on co.student_number = ie.student_number
    and co.academic_year = ie.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="ie") }}
    and sj.iready_subject = ie.iready_subject
left join
    mia_territory as mt
    on co.student_number = mt.student_number
    and {{ union_dataset_join_clause(left_alias="co", right_alias="mt") }}
    and mt.rn_territory = 1
left join
    dibels as db
    on co.student_number = db.mclass_student_number
    and co.academic_year = db.mclass_academic_year
    and sj.iready_subject = db.iready_subject
    and db.rn_year = 1
left join
    psat_bucket1 as ps
    on co.student_number = ps.local_student_id
    and sj.discipline = ps.discipline
where co.rn_year = 1 and co.academic_year >= {{ var("current_academic_year") - 1 }}
