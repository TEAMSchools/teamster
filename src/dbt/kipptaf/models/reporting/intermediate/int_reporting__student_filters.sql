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
        from unnest(['Reading', 'Math']) as subject
    ),

    intervention_nj as (
        select
            st.local_student_id as student_number,

            regexp_extract(g.group_name, r'Bucket 2 - (\w+) - Gr\w-\w') as subject,
        from {{ source("illuminate", "group_student_aff") }} as s
        inner join
            {{ source("illuminate", "groups") }} as g
            on s.group_id = g.group_id
            and g.group_name like 'Bucket 2%'
        left join
            {{ ref("stg_illuminate__students") }} as st on s.student_id = st.student_id
        where
            s.end_date is null
            or s.end_date < current_date('{{ var("local_timezone") }}')
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
    )

select
    co.academic_year,
    co._dbt_source_relation,
    co.student_number,
    co.studentid,

    sj.iready_subject,
    sj.illuminate_subject_area,
    sj.powerschool_credittype,

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
where co.rn_year = 1 and co.academic_year >= {{ var("current_academic_year") }} - 1
