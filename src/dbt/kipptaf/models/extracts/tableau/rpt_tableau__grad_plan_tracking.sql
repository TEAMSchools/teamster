with
    students as (
        select
            _dbt_source_relation,
            academic_year,
            academic_year_display,
            district,
            schoolid,
            region,
            school,
            studentid,
            students_dcid,
            student_number,
            state_studentnumber,
            salesforce_id,
            student_name,
            student_first_name,
            student_last_name,
            grade_level,
            enroll_status,
            student_email,
            cohort,
            ktc_cohort,
            gender,
            ethnicity,
            lep_status,
            iep_status,
            gifted_and_talented,
            is_504,
            is_out_of_district,
            is_self_contained,
            is_counseling_services,
            is_student_athlete,
            advisory,
            college_match_gpa,
            college_match_gpa_bands,

        from {{ ref("int_extracts__student_enrollments") }}
        where
            grade_level >= 9
            and academic_year = {{ var("current_academic_year") }}
            and student_number = 203535
    ),

    waivers as (
        select
            p.studentsdcid,
            p.subject_id,
            p.subject_name,
            p.waivedcredits,

            stuw.authorizedby,
            stuw.waiveddate,

        from {{ ref("int_powerschool__grad_plans_progress_students") }} as p
        left join
            students as s
            on p.studentsdcid = s.students_dcid
            and {{ union_dataset_join_clause(left_alias="p", right_alias="s") }}
        left join
            {{ ref("stg_powerschool__gpstudentwaiver") }} as stuw
            on s.studentid = stuw.studentid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="stuw") }}
            and stuw.gpnodeidforwaived = p.subject_id
        where p.waivedcredits > 0
    )

select
    e.*,

    -- from stored grades
    sub.earnedcredits as total_earnedcredits,
    -- from cc table
    sub.enrolledcredits as total_enrolledcredits,
    -- from schedule requests table 
    sub.requestedcredits as total_requestedcredits,
    sub.requiredcredits as total_requiredcredits,
    sub.waivedcredits as total_waivedcredits,

    gpn.id as gpnode_id,
    gpn.name as gpnode_name,
    gpn.creditcapacity as total_creditcapacity,

    gp.name as gradplan_name,

from students as e
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

    -- select
    -- e._dbt_source_relation,
    -- e.academic_year,
    -- e.students_dcid,
    -- e.studentid,
    -- e.student_number,
    -- e.grade_level,
    -- sub.earnedcredits,  -- from stored grades
    -- sub.enrolledcredits,  -- from cc table
    -- sub.requestedcredits,  -- from schedule requests table
    -- sub.requiredcredits,
    -- sub.waivedcredits,
    -- sub.isadvancedplan,
    -- gpn.id as gpnode_id,
    -- gpn.name as gpnode_name,
    -- gpn.allowanyof,
    -- gpn.allowwaiver,
    -- gpn.altcompletioncount,
    -- gpn.completioncount,
    -- gpn.creditcapacity,
    -- gpn.sortorder,
    -- gpver.startyear,
    -- gpver.endyear,
    -- gpver.minimumgrade,
    -- gpver.minimumgradepercentage,
    -- gp.name as gradplan_name,
    -- waiv.authorizedby,
    -- waiv.waiveddate,
    -- tc.total_earnedcredits,
    -- tc.total_enrolledcredits,
    -- tc.total_requestedcredits,
    -- tc.total_waivedcredits,
    -- tc.total_requiredcredits,
    -- tc.total_creditcapacity,
    -- coalesce(
    -- gpver.minimumgpa.int_value,
    -- gpver.minimumgpa.double_value,
    -- gpver.minimumgpa.bytes_decimal_value
    -- ) as minimumgpa,
    -- from {{ ref("int_extracts__student_enrollments") }} as e
    -- left join
    -- {{ ref("stg_powerschool__gpprogresssubject") }} as sub
    -- on e.students_dcid = sub.studentsdcid
    -- and {{ union_dataset_join_clause(left_alias="e", right_alias="sub") }}
    -- inner join
    -- {{ ref("stg_powerschool__gpnode") }} as gpn
    -- on sub.gpnodeid = gpn.id
    -- and sub.nodetype = gpn.nodetype
    -- and {{ union_dataset_join_clause(left_alias="sub", right_alias="gpn") }}
    -- and gpn.name not in ('Total Credits', 'Overall Credits')
    -- inner join
    -- {{ ref("stg_powerschool__gpversion") }} as gpver
    -- on gpn.gpversionid = gpver.id
    -- and {{ union_dataset_join_clause(left_alias="gpn", right_alias="gpver") }}
    -- inner join
    -- {{ ref("stg_powerschool__gradplan") }} as gp
    -- on gpver.gradplanid = gp.id
    -- and gp.name in ('HS Distinction Diploma', 'NJ State Diploma')
    -- and {{ union_dataset_join_clause(left_alias="gpver", right_alias="gp") }}
    -- left join waivers as waiv on e.student_number = waiv.student_number
    -- left join
    -- total_credits as tc
    -- on e.student_number = tc.student_number
    -- and gp.name = tc.gradplan_name
    -- where
    -- e.academic_year = {{ var("current_academic_year") }}
    -- and e.school_level = 'HS'
    -- and gpn.name != gp.name
    -- and e.student_number = 203535
    
