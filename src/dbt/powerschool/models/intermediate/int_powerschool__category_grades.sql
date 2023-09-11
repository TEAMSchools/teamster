with
    enr_gr as (
        select
            enr.cc_abs_sectionid as sectionid,
            enr.cc_studentid as studentid,
            enr.cc_schoolid as schoolid,
            enr.cc_course_number as course_number,
            enr.courses_credittype as credittype,
            enr.is_dropped_section,

            tb.yearid,
            tb.storecode,
            tb.date1 as termbin_start_date,
            tb.date2 as termbin_end_date,
            left(tb.storecode, 1) as storecode_type,
            'RT' || right(tb.storecode, 1) as reporting_term,
            if(
                current_date('{{ var("local_timezone") }}')
                between tb.date1 and tb.date2,
                true,
                false
            ) as is_current,

            if(pgf.grade = '--', null, pgf.percent) as percent_grade,
            nullif(pgf.citizenship, '') as citizenship_grade,
        from {{ ref("base_powerschool__course_enrollments") }} as enr
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on enr.cc_schoolid = tb.schoolid
            and enr.cc_abs_termid = tb.termid
        left join
            {{ ref("stg_powerschool__pgfinalgrades") }} as pgf
            on enr.cc_studentid = pgf.studentid
            and enr.cc_sectionid = pgf.sectionid
            and tb.storecode = pgf.finalgradename
        where not enr.is_dropped_course
    ),

    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="enr_gr",
                partition_by="studentid, yearid, course_number, storecode",
                order_by="is_dropped_section desc, percent_grade desc",
            )
        }}
    )

select
    *,

    round(
        avg(percent_grade) over (
            partition by studentid, yearid, course_number, storecode_type
            order by termbin_start_date asc
        ),
        0
    ) as percent_grade_y1_running,
from deduplicate
