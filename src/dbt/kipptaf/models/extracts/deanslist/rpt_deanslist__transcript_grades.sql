with
    all_grades as (
        select
            s.student_number,

            sg.schoolid,
            sg.academic_year,
            sg.course_number,
            sg.course_name,
            sg.earnedcrhrs as credit_hours,
            sg.percent as y1_grade_percent,
            sg.grade as y1_grade_letter,
            sg.storecode as term,
            if(
                sg.schoolname = 'KIPP Newark Collegiate Academy',
                'Newark Collegiate Academy',
                sg.schoolname
            ) as schoolname,

            1 as is_stored,
        from {{ ref("stg_powerschool__storedgrades") }} as sg
        inner join
            {{ ref("stg_powerschool__students") }} as s
            on sg.studentid = s.id
            and {{ union_dataset_join_clause(left_alias="sg", right_alias="s") }}
        where ifnull(sg.excludefromtranscripts, 0) = 0 and sg.storecode = 'Y1'

        union all

        select
            s.student_number,
            s.schoolid,

            fg.yearid + 1990 as academic_year,
            fg.course_number,

            c.course_name,

            fg.potential_credit_hours as credit_hours,
            fg.y1_percent_grade_adjusted as y1_grade_percent,
            fg.y1_letter_grade as y1_grade_letter,

            'Y1' as term,

            if(
                sch.name = 'KIPP Newark Collegiate Academy',
                'Newark Collegiate Academy',
                sch.name
            ) as schoolname,

            0 as is_stored,
        from {{ ref("stg_powerschool__students") }} as s
        inner join
            {{ ref("base_powerschool__final_grades") }} as fg
            on s.id = fg.studentid
            and {{ union_dataset_join_clause(left_alias="s", right_alias="fg") }}
            and fg.exclude_from_gpa = 0
            and current_date('America/New_York')
            between fg.termbin_start_date and fg.termbin_end_date
        inner join
            {{ ref("stg_powerschool__courses") }} as c
            on c.course_number = fg.course_number
            and {{ union_dataset_join_clause(left_alias="c", right_alias="fg") }}
        inner join
            {{ ref("stg_powerschool__schools") }} as sch
            on s.schoolid = sch.school_number
            and {{ union_dataset_join_clause(left_alias="s", right_alias="sch") }}
        where s.grade_level >= 5
    )

    {{
        dbt_utils.deduplicate(
            relation="all_grades",
            partition_by="student_number, academic_year, schoolname, course_number, course_name",
            order_by="is_stored desc",
        )
    }}
