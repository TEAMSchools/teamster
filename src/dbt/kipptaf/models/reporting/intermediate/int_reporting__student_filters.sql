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
            st.local_student_id as student_number,
            g.nj_intervention_subject,
            row_number() over (
                partition by st.local_student_id, g.nj_intervention_subject
                order by s.gsa_id desc
            ) as rn_bucket,
        from {{ ref("stg_illuminate__group_student_aff") }} as s
        inner join
            {{ ref("stg_illuminate__groups") }} as g
            on s.group_id = g.group_id
            and g.nj_intervention_tier = 2
            and g.group_name in (
                'Bucket 2 - Math - HS',
                'Bucket 2 - Reading - HS',
                'Bucket 2 - Reading - Gr5-8',
                'Bucket 2 - Math - Gr5-8',
                'Bucket 2 - Reading - GrK-4',
                'Bucket 2 - Math - GrK-4'
            )
        inner join
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
    ),

    dibels as (
        select
            mclass_student_number,
            mclass_academic_year,
            db.boy_composite,
            db.moy_composite,
            db.eoy_composite,
            'Reading' as iready_subject,
            row_number() over (
                partition by mclass_student_number, mclass_academic_year
                order by mclass_client_date desc
            ) as rn_year,
        from {{ ref("int_amplify__all_assessments") }} as db
        where mclass_measure = 'Composite'
    )

select
    co.academic_year,
    co._dbt_source_relation,
    co.student_number,
    co.studentid,
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

    if(nj.nj_intervention_subject is not null, true, false) as bucket_two,

    if(t.iready_subject is not null, true, false) as tutoring_nj,

    if(co.grade_level < 4, pr.iready_proficiency, py.njsla_proficiency) as bucket_one,

    if(
        co.grade_level >= 9, sj.powerschool_credittype, sj.illuminate_subject_area
    ) as assessment_dashboard_join,

    case
        when co.grade_level < 4 and pr.iready_proficiency = 'At/Above'
        then 'Bucket 1'
        when co.grade_level >= 4 and py.njsla_proficiency = 'At/Above'
        then 'Bucket 1'
        when nj.nj_intervention_subject is not null
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
    intervention_nj as nj
    on co.student_number = nj.student_number
    and sj.iready_subject = nj.nj_intervention_subject
    and nj.rn_bucket = 1
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
    iready_exempt as ie
    on co.academic_year = ie.academic_year
    and co.student_number = ie.student_number
    and sj.iready_subject = ie.iready_subject
left join
    mia_territory as mt on co.student_number = mt.student_number and mt.rn_territory = 1
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as se
    on co.students_dcid = se.studentsdcid
    and sj.discipline = se.discipline
    and {{ union_dataset_join_clause(left_alias="co", right_alias="se") }}
    and se.value_type = 'State Assessment Name'
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as a
    on co.students_dcid = a.studentsdcid
    and sj.discipline = a.discipline
    and {{ union_dataset_join_clause(left_alias="co", right_alias="a") }}
    and a.value_type = 'Graduation Pathway'
    and a.values_column = 'M'
left join
    dibels as db
    on co.academic_year = db.mclass_academic_year
    and co.student_number = db.mclass_student_number
    and sj.iready_subject = db.iready_subject
    and db.rn_year = 1
where co.rn_year = 1 and co.academic_year >= {{ var("current_academic_year") - 1 }}
