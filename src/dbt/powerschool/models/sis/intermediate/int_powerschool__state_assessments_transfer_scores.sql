select
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
inner join {{ ref("stg_powerschool__studenttest") }} as st on t.id = st.testid
inner join
    {{ ref("stg_powerschool__studenttestscore") }} as sts on st.id = sts.studenttestid
inner join {{ ref("stg_powerschool__testscore") }} as ts on sts.testscoreid = ts.id
where t.name = 'NJGPA'
