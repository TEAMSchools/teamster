-- note for charlie and charlie only. if you are not charlie, look away: the intent of
-- this new int table is to replace several duplicated ctes that are used on the
-- int_students__graduation_path_codes view (which then feeds students autocomm), and
-- on the
-- rpt_tableau__graduation_requirements view. i anticipate this new int view below
-- also becoming a source for future graduation eligibility projects as we add to the
-- mix with credit tracking efforts for HS students. i would have also made this new
-- source a table, but i still dont understand how to do that, no matter how many
-- examples i see online. if you could turn it into a table (if it makes sesnse), it
-- would be much appreciated. thanks!
with
    students as (
        select
            e._dbt_source_relation,
            e.students_dcid,
            e.studentid,
            e.student_number,
            e.state_studentnumber,
            e.contact_id as kippadb_contact_id,
            e.cohort,
            e.enroll_status,

            discipline,

            max(e.grade_level) as most_recent_grade_level,
            max(e.academic_year) max_academic_year,

            case
                max(e.grade_level)
                when 9
                then max(e.academic_year) + 4
                when 10
                then max(e.academic_year) + 3
                when 11
                then max(e.academic_year) + 2
                when 12
                then max(e.academic_year) + 1
            end as expected_grad_year,

        from {{ ref("int_tableau__student_enrollments") }} as e
        cross join unnest(['Math', 'ELA']) as discipline
        where e.grade_level between 9 and 12
        group by all
    ),

    transfer_scores as (
        select
            b._dbt_source_relation,

            s.studentid,

            t.numscore as testscalescore,

            r.name as testcode,

            case
                r.name when 'ELAGP' then 'ELA' when 'MATGP' then 'Math'
            end as discipline,

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

            x.testcode,
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
            testcode,
            testscalescore,

            case
                testcode when 'ELAGP' then 'ELA' when 'MATGP' then 'Math'
            end as discipline,
        from {{ ref("stg_pearson__njgpa") }}
        where testscorecomplete = 1 and testcode in ('ELAGP', 'MATGP')
    ),

    njgpa_rollup as (
        select
            e._dbt_source_relation,
            e.students_dcid,
            e.studentid,
            e.student_number,
            e.state_studentnumber,
            e.kippadb_contact_id,
            e.cohort,
            e.expected_grad_year,
            e.enroll_status,
            e.most_recent_grade_level,
            e.discipline,

            s.testcode,
            s.testscalescore,

            'Official' as test_type,
            'NJGPA' as scope,

            case
                s.testcode
                when 'ELAGP'
                then 'English Language Arts'
                when 'MATGP'
                then 'Mathematics'
            end as subject_area,

            row_number() over (
                partition by e.student_number, s.testcode order by s.testscalescore desc
            ) as rn_highest,

        from students as e
        inner join
            njgpa as s
            on e.discipline = s.discipline
            and e.state_studentnumber = s.state_studentnumber
    )

select
    e._dbt_source_relation,
    e.students_dcid,
    e.studentid,
    e.student_number,
    e.state_studentnumber,
    e.kippadb_contact_id,
    e.cohort,
    e.expected_grad_year,
    e.enroll_status,
    e.most_recent_grade_level,
    e.discipline,

    e.test_type,
    e.scope,
    e.testcode as score_type,
    e.subject_area,
    e.testscalescore as scale_score,
    e.rn_highest,

    c.`domain`,
    c.sf_standardized_test,
    c.cutoff,

    if(e.testscalescore >= c.cutoff, true, false) as met_pathway_requirement,

from njgpa_rollup as e
inner join
    {{ ref("stg_reporting__promo_status_cutoffs") }} as c
    on e.expected_grad_year = c.cohort
    and e.discipline = c.discipline
    and c.code = 'NJGPA'

union all

select
    e._dbt_source_relation,
    e.students_dcid,
    e.studentid,
    e.student_number,
    e.state_studentnumber,
    e.kippadb_contact_id,
    e.cohort,
    e.expected_grad_year,
    e.enroll_status,
    e.most_recent_grade_level,
    e.discipline,

    s.test_type,
    s.scope,
    s.score_type,
    s.subject_area,
    s.scale_score,
    s.rn_highest,

    c.`domain`,
    c.sf_standardized_test,
    c.cutoff,

    if(s.scale_score >= c.cutoff, true, false) as met_pathway_requirement,

from students as e
inner join
    {{ ref("int_assessments__college_assessments_official") }} as s
    on e.discipline = s.discipline
    and e.student_number = s.student_number
    and s.subject_area != 'Composite'
inner join
    {{ ref("stg_reporting__promo_status_cutoffs") }} as c
    on e.expected_grad_year = c.cohort
    and e.discipline = c.discipline
    and s.score_type = c.subject
