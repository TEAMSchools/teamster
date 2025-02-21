with
    students as (
        select
            e._dbt_source_relation,
            e.dcid as students_dcid,
            e.id as studentid,
            e.student_number,
            e.state_studentnumber,
            e.grade_level,

            discipline,

            adb.contact_id as kippadb_contact_id,
        from {{ ref("stg_powerschool__students") }} as e
        cross join unnest(['Math', 'ELA']) as discipline
        left join
            {{ ref("int_kippadb__roster") }} as adb
            on e.student_number = adb.student_number
        where e.grade_level between 9 and 12
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

    act_sat_official as (
        select
            salesforce_id,
            scope,

            case
                course_discipline when 'ENG' then 'ELA' when 'MATH' then 'Math'
            end as course_discipline,

            case
                when score_type in ('act_reading', 'act_math') and scale_score >= 17
                then true
                when score_type = 'sat_reading_test_score' and scale_score >= 23
                then true
                when score_type = 'sat_math_test_score' and scale_score >= 22
                then true
                when score_type = 'sat_math' and scale_score >= 440
                then true
                when score_type = 'sat_ebrw' and scale_score >= 450
                then true
                else false
            end as met_pathway_requirement,

        from {{ ref("int_assessments__college_assessment") }}
        where
            rn_highest = 1
            and score_type in (
                'act_reading',
                'act_math',
                'sat_math_test_score',
                'sat_math',
                'sat_reading_test_score',
                'sat_ebrw'
            )
    ),

    act_sat_pivot as (
        select salesforce_id, course_discipline, act, sat,
        from
            act_sat_official
            pivot (max(met_pathway_requirement) for scope in ('ACT', 'SAT'))
    ),

    psat_official as (
        select
            'PSAT' as scope,

            case
                course_discipline when 'ENG' then 'ELA' when 'MATH' then 'Math'
            end as course_discipline,

            safe_cast(student_number as int) as local_student_id,

            if(scale_score >= 420, true, false) as met_pathway_requirement,

        from {{ ref("int_assessments__college_assessment") }}
        where
            rn_highest = 1
            and score_type in (
                'psat10_psat_math_section',
                'psatnmsqt_psat_math_section',
                'psat10_psat_ebrw',
                'psatnmsqt_psat_ebrw'
            )
    ),

    psat_rollup as (
        select
            local_student_id,
            scope,
            course_discipline,
            max(met_pathway_requirement) as psat,
        from psat_official
        group by local_student_id, course_discipline, scope
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

    test_scores as (
        select
            r._dbt_source_relation,
            r.student_number,
            r.students_dcid,
            r.grade_level,
            r.discipline,

            coalesce(o1.act, false) as act,
            coalesce(o1.sat, false) as sat,

            coalesce(o2.psat, false) as psat,

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
            on r.kippadb_contact_id = o1.salesforce_id
            and r.discipline = o1.course_discipline
        left join
            psat_rollup as o2
            on r.student_number = o2.local_student_id
            and r.discipline = o2.course_discipline
    )

select
    r._dbt_source_relation,
    r.student_number,
    r.discipline,
    r.act,
    r.sat,
    r.psat,
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
        when r.njgpa_attempt and not r.njgpa_pass and not r.act and not r.sat and r.psat
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
