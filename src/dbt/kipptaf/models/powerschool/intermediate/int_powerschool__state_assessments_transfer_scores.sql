-- purpose of this view: this CTE is used, as is, in 2 views -
-- int_students__graduation_path_codes and rpt_tableau__graduation_requirements. this
-- chunk brings over NJGPA scores of students who enrolled with us AFTER they
-- attempted the test. we dont get score files for them because they didnt test with
-- us, but we still need to know: 1) their attempt and, 2) their scores, so that we
-- can calculate graduation eligibility for the grad requirements dash, AND for
-- writing the correct grad path code into PS via autocomm_students. i wasnt sure
-- where this would go, but i figured since all the tables are from PS, it would go
-- here.
select
    b._dbt_source_relation,
    b.name as test_name,

    s.studentid,
    s.grade_level as assessment_grade_level,

    t.numscore as testscalescore,
    t.alphascore as testperformancelevel,

    r.name as testcode,
    case r.name when 'ELAGP' then 'ELA' when 'MATGP' then 'Math' end as discipline,
    case
        r.name when 'ELAGP' then 'English Language Arts' when 'MATGP' then 'Mathematics'
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
