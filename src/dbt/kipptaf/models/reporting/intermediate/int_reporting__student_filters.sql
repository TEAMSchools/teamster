with
    subjects as (
        select
            subject as iready_subject,
            (
                case
                    when subject = 'Reading'
                    then 'Text Study'
                    when subject = 'Math'
                    then 'Mathematics'
                end
            ) as illuminate_subject_area,
            (
                case
                    when subject = 'Reading'
                    then 'ENG'
                    when subject = 'Math'
                    then 'MATH'
                end
            ) as powerschool_credittype,
        from unnest(['Reading', 'Math']) as subject
    ),
    intervention_nj as (
        select
            st.local_student_id as student_number,
            right(
                left(g.group_name, length(g.group_name) - 8), length(g.group_name) - 19
            ) as subject
        from {{ source("illuminate", "group_student_aff") }} as s
        inner join
            {{ source("illuminate", "groups") }} as g
            on s.group_id = g.group_id
            and g.group_name like 'Bucket 2%'
        left join
            {{ ref("stg_illuminate__students") }} as st on s.student_id = st.student_id
        where s.end_date is null or s.end_date < current_date('America/New_York')
    ),
    prev_yr_state_test as (
        select
            localstudentidentifier,
            statestudentidentifier,
            academic_year + 1 as academic_year_plus,
            (
                case
                    when subject like 'English Language Arts%'
                    then 'Text Study'
                    when subject in ('Algebra I', 'Algebra II', 'Geometry')
                    then 'Mathematics'
                    else subject
                end
            ) as subject,
            (
                case
                    when testperformancelevel < 3
                    then 'Below/Far Below'
                    when testperformancelevel = 3
                    then 'Approaching'
                    when testperformancelevel > 3
                    then 'At/Above'
                end
            ) as njsla_proficiency
        from {{ ref("stg_pearson__njsla") }}
    ),
    tutoring_nj as (
        select _dbt_source_relation, studentid, academic_year, 'Math' as iready_subject
        from {{ ref("int_powerschool__spenrollments") }}
        where
            (current_date('America/New_York') between enter_date and exit_date)
            and specprog_name = 'Tutoring'
    )
select
    co._dbt_source_relation,
    co.student_number,
    co.studentid,
    sj.iready_subject,
    sj.illuminate_subject_area,
    sj.powerschool_credittype,
    coalesce(nj.subject, 'Not Bucket 2') as bucket_two,
    coalesce(py.njsla_proficiency, 'No Test') as state_test_proficiency,
    case
        when t.iready_subject is not null then 'Tutored' else 'Not Tutored'
    end as tutoring_nj
from {{ ref("base_powerschool__student_enrollments") }} as co
cross join subjects as sj
left join
    intervention_nj as nj
    on co.student_number = nj.student_number
    and sj.iready_subject = nj.subject
left join
    prev_yr_state_test as py
    on (
        co.student_number = py.localstudentidentifier
        or cast(co.state_studentnumber as int64) = py.statestudentidentifier
    )
    and co.academic_year = py.academic_year_plus
    and sj.illuminate_subject_area = py.subject
left join
    tutoring_nj as t
    on co.studentid = t.studentid
    and co.academic_year = t.academic_year
    and sj.iready_subject = t.iready_subject
    and {{ union_dataset_join_clause(left_alias="co", right_alias="t") }}
where co.rn_year = 1 and co.academic_year >= {{ var("current_academic_year") }} - 1
