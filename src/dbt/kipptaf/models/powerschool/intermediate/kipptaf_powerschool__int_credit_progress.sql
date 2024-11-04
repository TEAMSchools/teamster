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

    -- note for charlie: open to finding a better way to do this, but this CTE is here
    -- cuz: 1) the majority of students have two grad plans set on PS - the basic one,
    -- which is called NJ State Diploma; and the advanced one: HS Distinction Diploma.
    -- all students are expected to finish the advanced one, but if they don't, they
    -- get defaulted to the basic one. however, PS allows credit waivers to be entered
    -- only on non-basic grad plans and the unique id used to track the waivers match
    -- only the advanced degree rows (i.e. i cannot bring waiver data for the basic
    -- plan, and there is no way to tag which plan a student will end up completing,so
    -- i need to bring both)
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
    ),

    -- note for charlie: this CTE saves me the time and error-possibilities when
    -- calculating total credits completed, waived and the goal.
    total_credits as (
        select
            e._dbt_source_relation,
            e.academic_year,
            e.students_dcid,
            e.studentid,
            e.student_number,

            sub.earnedcredits as total_earnedcredits,  -- from stored grades
            sub.enrolledcredits as total_enrolledcredits,  -- from cc table
            sub.requestedcredits as total_requestedcredits,  -- from schedule requests table
            sub.requiredcredits as total_requiredcredits,
            sub.waivedcredits as total_waivedcredits,

            gpn.id as gpnode_id,
            gpn.name as gpnode_name,
            gpn.creditcapacity as total_creditcapacity,

            gp.name as gradplan_name,

        from {{ ref("base_powerschool__student_enrollments") }} as e
        left join
            {{ ref("stg_powerschool__gpprogresssubject") }} as sub
            on e.students_dcid = sub.studentsdcid
            and {{ union_dataset_join_clause(left_alias="e", right_alias="sub") }}
        inner join
            {{ ref("stg_powerschool__gpnode") }} as gpn
            on sub.gpnodeid = gpn.id
            and sub.nodetype = gpn.nodetype
            and {{ union_dataset_join_clause(left_alias="sub", right_alias="gpn") }}
            and gpn.name in ('Total Credits', 'Overall Credits')
        inner join
            {{ ref("stg_powerschool__gpversion") }} as gpver
            on gpn.gpversionid = gpver.id
            and {{ union_dataset_join_clause(left_alias="gpn", right_alias="gpver") }}
        inner join
            {{ ref("stg_powerschool__gradplan") }} as gp
            on gpver.gradplanid = gp.id
            and gp.name in ('HS Distinction Diploma', 'NJ State Diploma')
            and {{ union_dataset_join_clause(left_alias="gpver", right_alias="gp") }}
        where
            e.academic_year = {{ var("current_academic_year") }}
            and e.school_level = 'HS'
            and e.rn_year = 1
    )

select
    e._dbt_source_relation,
    e.academic_year,
    e.students_dcid,
    e.studentid,
    e.student_number,
    e.grade_level,

    sub.earnedcredits,  -- from stored grades
    sub.enrolledcredits,  -- from cc table
    sub.requestedcredits,  -- from schedule requests table
    sub.requiredcredits,
    sub.waivedcredits,
    sub.isadvancedplan,

    gpn.id as gpnode_id,
    gpn.name as gpnode_name,
    gpn.allowanyof,
    gpn.allowwaiver,
    gpn.altcompletioncount,
    gpn.completioncount,
    gpn.creditcapacity,
    gpn.sortorder,

    gpver.startyear,
    gpver.endyear,
    gpver.minimumgrade,
    gpver.minimumgradepercentage,
    coalesce(
        gpver.minimumgpa.int_value,
        gpver.minimumgpa.double_value,
        gpver.minimumgpa.bytes_decimal_value
    ) as minimumgpa,

    gp.name as gradplan_name,

    waiv.authorizedby,
    waiv.waiveddate,

    tc.total_earnedcredits,
    tc.total_enrolledcredits,
    tc.total_requestedcredits,
    tc.total_waivedcredits,
    tc.total_requiredcredits,
    tc.total_creditcapacity,

from {{ ref("base_powerschool__student_enrollments") }} as e
left join
    {{ ref("stg_powerschool__gpprogresssubject") }} as sub
    on e.students_dcid = sub.studentsdcid
    and {{ union_dataset_join_clause(left_alias="e", right_alias="sub") }}
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
    and gp.name in ('HS Distinction Diploma', 'NJ State Diploma')
    and {{ union_dataset_join_clause(left_alias="gpver", right_alias="gp") }}
left join waivers as waiv on e.student_number = waiv.student_number
left join
    total_credits as tc
    on e.student_number = tc.student_number
    and gp.name = tc.gradplan_name
where
    e.academic_year = {{ var("current_academic_year") }}
    and e.school_level = 'HS'
    and e.rn_year = 1
    and gpn.name != gp.name
