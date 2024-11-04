with
    -- note for charlie: id like for the CTE below to be considered a permanent
    -- fixture of the data model. not all tables on the data model that need to be
    -- connected have the same student identifier and dont always need all of the
    -- extra information from student_enrollments (base or int_tableau). i just need a
    -- way to connect two tables with different student identifiers. i dont need all
    -- the fields below for THIS particular view, but i left them there for you to
    -- review the possibilty of making this CTE, as is, as a its own view/table
    student_id_crosswalk as (
        select distinct
            e._dbt_source_relation,
            e.studentid,
            e.students_dcid,
            e.student_number,
            e.state_studentnumber,
            e.fleid,
            e.infosnap_id,

            a.contact_id as contact_id,

            i.student_id as illuminate_id,
        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("int_kippadb__roster") }} as a on e.student_number = a.student_number
        left join
            {{ ref("stg_illuminate__students") }} as i
            on e.student_number = i.local_student_id
    ),

    waivers as (
        select
            sub.waivedcredits,

            c.student_number,

            gpn.id as gpnode_id,
            gpn.name as gpnode_name,

            gp.name as gradplan_name,

            stuw.authorizedby,
            stuw.waiveddate,

        from {{ ref("stg_powerschool__gpprogresssubject") }} as sub
        left join
            student_id_crosswalk as c
            on sub.studentsdcid = c.students_dcid
            and {{ union_dataset_join_clause(left_alias="sub", right_alias="c") }}
        inner join
            {{ ref("stg_powerschool__gpnode") }} as gpn
            on sub.gpnodeid = gpn.id
            and sub.nodetype = gpn.nodetype
            and {{ union_dataset_join_clause(left_alias="sub", right_alias="gpn") }}
            and gpn.name not in ('Total Credits', 'Overall Credits')
        inner join
            {{ ref("stg_powerschool__gpversion") }} as gpver
            on gpn.gpversionid = gpver.id
            and {{ union_dataset_join_clause(left_alias="gpn", right_alias="gpver") }}
        inner join
            {{ ref("stg_powerschool__gradplan") }} as gp
            on gpver.gradplanid = gp.id
            and gp.name = 'HS Distinction Diploma'
            and {{ union_dataset_join_clause(left_alias="gpver", right_alias="gp") }}
        left join
            {{ ref("stg_powerschool__gpstudentwaiver") }} as stuw
            on c.studentid = stuw.studentid
            and {{ union_dataset_join_clause(left_alias="c", right_alias="stuw") }}
            and stuw.gpnodeidforwaived = gpn.id
        where gpn.name != gp.name and sub.waivedcredits > 0
    )

select *
from waivers
