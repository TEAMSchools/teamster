with
    scores as (
        select
            t._dbt_source_relation,
            t._dbt_source_project,
            t.name as test_name,

            st.id as studenttestid,
            st.studentid,
            st.grade_level as assessment_grade_level,

            sts.numscore as testscalescore,
            sts.alphascore as testperformancelevel,

            ts.name as score_name,

            'NJGPA' as assessment_name,

            regexp_replace(ts.name, r'-A$', '') as testcode,

            if(
                regexp_contains(ts.name, r'-A$'), 'NJGPA-A', 'NJGPA'
            ) as assessment_version,

        from {{ ref("stg_powerschool__test") }} as t
        inner join
            {{ ref("stg_powerschool__studenttest") }} as st
            on t.id = st.testid
            and t._dbt_source_project = st._dbt_source_project
        inner join
            {{ ref("stg_powerschool__studenttestscore") }} as sts
            on st.id = sts.studenttestid
            and st._dbt_source_project = sts._dbt_source_project
        inner join
            {{ ref("stg_powerschool__testscore") }} as ts
            on sts.testscoreid = ts.id
            and sts._dbt_source_project = ts._dbt_source_project
        /* The holder was renamed from 'NJGPA' when the adaptive score fields were
           added, and the two PowerSchool instances are renamed independently, so
           both names stay matchable. */
        where t.name in ('NJGPA', 'NJGPA/NJGPA-A')
    )

select
    _dbt_source_relation,
    _dbt_source_project,
    test_name,
    studentid,
    assessment_grade_level,
    testscalescore,
    testperformancelevel,
    score_name,
    assessment_name,
    testcode,
    assessment_version,

    case testcode when 'ELAGP' then 'ELA' when 'MATGP' then 'Math' end as discipline,

    case
        testcode
        when 'ELAGP'
        then 'English Language Arts'
        when 'MATGP'
        then 'Mathematics'
    end as `subject`,

from scores
