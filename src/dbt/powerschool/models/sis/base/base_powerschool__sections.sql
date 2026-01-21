select
    {{
        dbt_utils.star(
            from=ref("stg_powerschool__sections"),
            relation_alias="sec",
            prefix="sections_",
        )
    }},

    {{
        dbt_utils.star(
            from=ref("stg_powerschool__courses"),
            relation_alias="cou",
            prefix="courses_",
        )
    }},

    {{
        dbt_utils.star(
            from=ref("stg_powerschool__terms"),
            relation_alias="term",
            prefix="terms_",
        )
    }},

    sch.name as school_name,

    t.teachernumber,
    t.lastfirst as teacher_lastfirst,

    {# TODO: refactor to gsheet #}
    case
        cou.gradescaleid
        /* unweighted 2019+ */
        when 991
        then 976
        /* unweighted 2016-2018 */
        when 712
        then 874
        /* MISSING GRADESCALE - default 2016+ */
        when null
        then 874
        else cou.gradescaleid
    end as courses_gradescaleid_unweighted,
from {{ ref("stg_powerschool__sections") }} as sec
inner join
    {{ ref("stg_powerschool__courses") }} as cou
    on sec.course_number = cou.course_number
inner join
    {{ ref("stg_powerschool__terms") }} as term
    on sec.termid = term.id
    and sec.schoolid = term.schoolid
inner join
    {{ ref("stg_powerschool__schools") }} as sch on sec.schoolid = sch.school_number
left join
    {{ ref("int_powerschool__teachers") }} as t
    on sec.teacher = t.id
    and sec.schoolid = t.schoolid
