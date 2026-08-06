select
    t._dbt_source_relation,
    t.name as test_name,

    st.studentid,
    st.grade_level as assessment_grade_level,

    sts.numscore as testscalescore,
    sts.alphascore as testperformancelevel,

    ts.name as testcode,

    case ts.name when 'ELAGP' then 'ELA' when 'MATGP' then 'Math' end as discipline,

    case
        ts.name
        when 'ELAGP'
        then 'English Language Arts'
        when 'MATGP'
        then 'Mathematics'
    end as `subject`,
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
where t.name = 'NJGPA'
