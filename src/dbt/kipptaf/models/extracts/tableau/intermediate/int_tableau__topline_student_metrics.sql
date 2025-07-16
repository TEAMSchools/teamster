with
    student_id_union as (
        select
            studentid,

            'Attendance' as metric_category,
            '' as metric_subcategory,
            '' as metric_subject,
            'Y1' as metric_period,
            'ADA' as metric_name,
            '' as metric_value_string,

            yearid + 1990 as academic_year,

            round(avg(attendancevalue), 2) as metric_value_float,

        from {{ ref("int_powerschool__ps_adaadm_daily_ctod") }}
        where
            membershipvalue = 1
            and calendardate <= current_date('{{ var("local_timezone") }}')
        group by yearid, studentid, _dbt_source_relation
    ),

    student_number_union as (
        select
            student_id as student_number,

            'Assessment' as metric_category,
            'i-Ready Diagnostic' as metric_subcategory,
            subject as metric_subject,
            test_round as metric_period,
            'Is Proficient (ORP 4+)' as metric_name,
            '' as metric_value_string,

            academic_year_int as academic_year,

            if(overall_relative_placement_int >= 4, 1, 0) as metric_value_float,

        from {{ ref("base_iready__diagnostic_results") }}
        where rn_subj_round = 1 and test_round != 'Outside Round'
    )

select
    co.schoolid,
    co.school_abbreviation,
    co.school_name,
    co.student_number,
    co.grade_level,
    co.gender,
    co.spedlep,
    co.academic_year,

    sn.metric_category,
    sn.metric_subcategory,
    sn.metric_subject,
    sn.metric_period,
    sn.metric_name,
    sn.metric_value_float,
    sn.metric_value_string,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    student_number_union as sn
    on co.student_number = sn.student_number
    and co.academic_year = sn.academic_year
where co.rn_year = 1 and co.grade_level != 99

union all

select
    co.schoolid,
    co.school_abbreviation,
    co.school_name,
    co.student_number,
    co.grade_level,
    co.gender,
    co.spedlep,
    co.academic_year,

    si.metric_category,
    si.metric_subcategory,
    si.metric_subject,
    si.metric_period,
    si.metric_name,
    si.metric_value_float,
    si.metric_value_string,
from {{ ref("base_powerschool__student_enrollments") }} as co
inner join
    student_id_union as si
    on co.studentid = si.studentid
    and co.academic_year = si.academic_year
    and {{ union_dataset_join_clause(left_alias="co", right_alias="si") }}
where co.rn_year = 1 and co.grade_level != 99
