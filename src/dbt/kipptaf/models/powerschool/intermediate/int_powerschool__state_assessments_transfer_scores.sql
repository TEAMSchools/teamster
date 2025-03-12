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
    and {{ union_dataset_join_clause(left_alias="t", right_alias="st") }}
inner join
    {{ ref("stg_powerschool__studenttestscore") }} as sts
    on st.id = sts.studenttestid
    and {{ union_dataset_join_clause(left_alias="st", right_alias="sts") }}
inner join
    {{ ref("stg_powerschool__testscore") }} as ts
    on sts.testscoreid = ts.id
    and {{ union_dataset_join_clause(left_alias="sts", right_alias="ts") }}
where t.name = 'NJGPA'
