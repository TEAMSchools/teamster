with
    students as (
        select
            e._dbt_source_relation,
            e.students_dcid,
            e.studentid,
            e.student_number,
            e.state_studentnumber,
            e.contact_id as kippadb_contact_id,
            e.grade_level,
            e.cohort,

            discipline,

        from {{ ref("int_tableau__student_enrollments") }} as e
        cross join unnest(['Math', 'ELA']) as discipline
        where e.grade_level between 8 and 12
    ),

    transfer_scores as (
        select
            b._dbt_source_relation,
            b.name as test_name,

            s.studentid,
            s.grade_level as assessment_grade_level,

            t.numscore as testscalescore,
            t.alphascore as testperformancelevel,

            r.name as testcode,
            case
                r.name when 'ELAGP' then 'ELA' when 'MATGP' then 'Math'
            end as discipline,
            case
                r.name
                when 'ELAGP'
                then 'English Language Arts'
                when 'MATGP'
                then 'Mathematics'
            end as `subject`,
        from {{ ref("stg_powerschool__test") }} as b
        inner join
            {{ ref("stg_powerschool__studenttest") }} as s
            on b.id = s.testid
            and {{ union_dataset_join_clause(left_alias="b", right_alias="s") }}
        inner join
            {{ ref("stg_powerschool__studenttestscore") }} as t
            on s.studentid = t.studentid
            and s.id = t.studenttestid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="t") }}
        inner join
            {{ ref("stg_powerschool__testscore") }} as r
            on s.testid = r.testid
            and t.testscoreid = r.id
            and {{ union_dataset_join_clause(left_alias="s", right_alias="r") }}
        where b.name = 'NJGPA'
    ),

    njgpa as (
        select
            s._dbt_source_relation,
            s.state_studentnumber,

            x.testscalescore,
            x.discipline,
        from students as s
        left join
            transfer_scores as x
            on s.studentid = x.studentid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="x") }}
        where x.studentid is not null

        union all

        select
            _dbt_source_relation,

            safe_cast(statestudentidentifier as string) as state_studentnumber,

            testscalescore,

            case
                testcode when 'ELAGP' then 'ELA' when 'MATGP' then 'Math'
            end as discipline,
        from {{ ref("stg_pearson__njgpa") }}
        where testscorecomplete = 1 and testcode in ('ELAGP', 'MATGP')
    ),

    njgpa_rollup as (
        select
            _dbt_source_relation,
            state_studentnumber,
            discipline,

            max(testscalescore) as testscalescore,
        from njgpa
        group by _dbt_source_relation, state_studentnumber, discipline
    ),

    college_assessment_scores as (
        select
            e.student_number,
            e.cohort,
            e.discipline,

            s.test_type,
            s.scope,
            s.score_type,
            s.subject_area,
            s.scale_score,

            c.cutoff,
        from students as e
        inner join
            {{ ref("int_assessments__college_assessments_official") }} as s
            on e.discipline = s.discipline
            and e.student_number = s.student_number
        inner join
            {{ ref("int_reporting__promotional_status") }} as c
            on e.cohort = c.cohort
            and e.discipline = c.discipline
            and s.score_type = c.subject
        where s.rn_highest = 1 and s.subject_area != 'Composite'
    )

select *
from
    college_assessment_scores

    /*,

    test_scores as (
        select
            r._dbt_source_relation,
            r.student_number,
            r.students_dcid,
            r.grade_level,
            r.discipline,

            coalesce(o1.act, false) as act,
            coalesce(o1.sat, false) as sat,

            coalesce(o2.psat10, false) as psat10,

            if(n.testscalescore is null, false, true) as njgpa_attempt,
            if(n.testscalescore >= 725, true, false) as njgpa_pass,
        from students as r
        left join
            njgpa_rollup as n
            on r.state_studentnumber = n.state_studentnumber
            and r.discipline = n.discipline
            and {{ union_dataset_join_clause(left_alias="r", right_alias="n") }}
        left join
            act_sat_pivot as o1
            on r.kippadb_contact_id = o1.contact
            and r.discipline = o1.discipline
        left join
            psat10_rollup as o2
            on r.student_number = o2.local_student_id
            and r.discipline = o2.discipline
    )

select
    r._dbt_source_relation,
    r.student_number,
    r.discipline,
    r.act,
    r.sat,
    r.psat10,
    r.njgpa_attempt,
    r.njgpa_pass,

    u.values_column as code,

    case
        when r.grade_level != 12
        then u.values_column
        when u.values_column in ('M', 'N', 'O', 'P')
        then u.values_column
        when r.njgpa_pass
        then 'S'
        when r.njgpa_attempt and not r.njgpa_pass and r.act
        then 'E'
        when r.njgpa_attempt and not r.njgpa_pass and not r.act and r.sat
        then 'D'
        when
            r.njgpa_attempt
            and not r.njgpa_pass
            and not r.act
            and not r.sat
            and r.psat10
        then 'J'
        else 'R'
    end as final_grad_path,
from test_scores as r
left join
    {{ ref("int_powerschool__s_nj_stu_x_unpivot") }} as u
    on r.students_dcid = u.studentsdcid
    and r.discipline = u.discipline
    and {{ union_dataset_join_clause(left_alias="r", right_alias="u") }}
    and u.value_type = 'Graduation Pathway'
*/
    
