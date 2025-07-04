with
    enr_termbins as (
        select
            enr.cc_dcid,
            enr.cc_studentid,
            enr.cc_sectionid,
            enr.cc_yearid,
            enr.cc_abs_termid,
            enr.cc_academic_year,
            enr.cc_dateenrolled,
            enr.cc_dateleft,
            enr.cc_schoolid,
            enr.cc_course_number,
            enr.courses_excludefromgpa,
            enr.courses_course_name,
            enr.courses_credittype,
            enr.courses_credit_hours,
            enr.courses_gradescaleid,
            enr.courses_gradescaleid_unweighted,
            enr.teacher_lastfirst,
            enr.school_name,
            enr.is_dropped_section,

            tb.storecode,
            tb.date1 as termbin_start_date,
            tb.date2 as termbin_end_date,

            if(
                current_date('{{ var("local_timezone") }}')
                between tb.date1 and tb.date2,
                true,
                false
            ) as termbin_is_current,

            if(
                min(tb.storecode) over (partition by enr.cc_sectionid) like 'Q%',
                25.000,
                case
                    when tb.storecode like 'Q%'
                    then 22.000
                    when tb.storecode like 'E%'
                    then 5.000
                end
            ) as term_weighted_points_possible,
        from {{ ref("base_powerschool__course_enrollments") }} as enr
        inner join
            {{ ref("stg_powerschool__termbins") }} as tb
            on enr.cc_schoolid = tb.schoolid
            and enr.cc_abs_termid = tb.termid
            and tb.storecode_type in ('Q', 'E')
        where
            enr.cc_academic_year = {{ var("current_academic_year") }}
            and not enr.is_dropped_section
    ),

    enr_grades as (
        select
            et.*,

            sg.grade as sg_letter_grade,
            sg.percent_decimal as sg_percent,
            sg.excludefromgpa as sg_exclude_from_gpa,
            sg.excludefromgraduation as sg_exclude_from_graduation,

            sgs.grade_points as sg_grade_points,

            pgf.lastgradeupdate,
            pgf.citizenship,
            pgf.comment_value,

            u.teachernumber as whomodified_teachernumber,

            if(
                sg.potentialcrhrs != 0.0, sg.potentialcrhrs, null
            ) as sg_potential_credit_hours,

            if(
                et.is_dropped_section and sg.percent is null, null, pgf.grade
            ) as fg_letter_grade,
            if(
                et.is_dropped_section and sg.percent is null, null, pgf.grade_adjusted
            ) as fg_letter_grade_adjusted,
            if(
                et.is_dropped_section and sg.percent is null, null, pgf.percent_decimal
            ) as fg_percent,
            if(
                et.is_dropped_section and sg.percent is null,
                null,
                pgf.percent_decimal_adjusted
            ) as fg_percent_adjusted,

            case
                when et.is_dropped_section and sg.percent is null
                then null
                when pgf.grade is null
                then null
                else pgfs.grade_points
            end as fg_grade_points,

            row_number() over (
                partition by
                    et.cc_studentid, et.cc_course_number, et.cc_yearid, et.storecode
                order by
                    sg.percent desc,
                    et.is_dropped_section asc,
                    et.cc_dateleft desc,
                    et.cc_sectionid desc
            ) as rn_enr_fg,
        from enr_termbins as et
        left join
            {{ ref("stg_powerschool__storedgrades") }} as sg
            on et.cc_studentid = sg.studentid
            and et.cc_course_number = sg.course_number
            and et.cc_abs_termid = sg.termid
            and et.storecode = sg.storecode
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as sgs
            on et.courses_gradescaleid = sgs.gradescaleid
            and sg.percent between sgs.min_cutoffpercentage and sgs.max_cutoffpercentage
        left join
            {{ ref("stg_powerschool__pgfinalgrades") }} as pgf
            on et.cc_studentid = pgf.studentid
            and et.cc_sectionid = pgf.sectionid
            and et.storecode = pgf.finalgradename
        left join
            {{ ref("int_powerschool__gradescaleitem_lookup") }} as pgfs
            on et.courses_gradescaleid = pgfs.gradescaleid
            and pgf.percent
            between pgfs.min_cutoffpercentage and pgfs.max_cutoffpercentage
        left join {{ ref("stg_powerschool__users") }} as u on pgf.whomodifiedid = u.dcid
    ),

    final_grades as (
        select
            *,

            coalesce(
                sg_potential_credit_hours, courses_credit_hours
            ) as potential_credit_hours,
            coalesce(sg_exclude_from_gpa, courses_excludefromgpa) as exclude_from_gpa,
            coalesce(sg_exclude_from_graduation, 0) as exclude_from_graduation,
            coalesce(sg_letter_grade, fg_letter_grade) as term_letter_grade,
            coalesce(
                sg_letter_grade, fg_letter_grade_adjusted
            ) as term_letter_grade_adjusted,
            coalesce(sg_percent, fg_percent) as term_percent_grade,
            coalesce(sg_percent, fg_percent_adjusted) as term_percent_grade_adjusted,
            coalesce(sg_grade_points, fg_grade_points) as term_grade_points,

            sum(term_weighted_points_possible) over (
                partition by cc_course_number, cc_studentid, cc_yearid
            ) as y1_weighted_points_possible,
            sum(term_weighted_points_possible) over (
                partition by cc_course_number, cc_studentid, cc_yearid
                order by termbin_end_date asc
            ) as y1_weighted_points_possible_running,
        from enr_grades
        where rn_enr_fg = 1
    ),

    fg_running as (
        select
            *,

            term_percent_grade
            * term_weighted_points_possible as term_weighted_points_earned,
            term_percent_grade_adjusted
            * term_weighted_points_possible as term_weighted_points_earned_adjusted,

            sum(term_percent_grade_adjusted * term_weighted_points_possible) over (
                partition by cc_course_number, cc_studentid, cc_yearid
                order by termbin_end_date asc
            ) as term_weighted_points_earned_adjusted_running,

            sum(term_percent_grade * term_weighted_points_possible) over (
                partition by cc_studentid, cc_course_number, cc_yearid
                order by termbin_end_date asc
            ) as y1_weighted_points_earned_running,
            sum(term_percent_grade_adjusted * term_weighted_points_possible) over (
                partition by cc_studentid, cc_course_number, cc_yearid
                order by termbin_end_date asc
            ) as y1_weighted_points_earned_adjusted_running,

            sum(
                if(term_percent_grade is not null, term_weighted_points_possible, null)
            ) over (
                partition by cc_course_number, cc_studentid, cc_yearid
                order by termbin_end_date asc
            ) as y1_weighted_points_valid_running,
        from final_grades
    ),

    y1 as (
        select
            * except (
                fg_percent,
                fg_percent_adjusted,
                sg_percent,
                term_percent_grade,
                term_percent_grade_adjusted
            ),

            round(fg_percent * 100.000, 0) as fg_percent,
            round(fg_percent_adjusted * 100.000, 0) as fg_percent_adjusted,
            round(sg_percent * 100.000, 0) as sg_percent,
            round(term_percent_grade * 100.000, 0) as term_percent_grade,
            round(
                term_percent_grade_adjusted * 100.000, 0
            ) as term_percent_grade_adjusted,

            round(
                (y1_weighted_points_earned_running / y1_weighted_points_valid_running)
                * 100.000,
                0
            ) as y1_percent_grade,
            round(
                (
                    y1_weighted_points_earned_adjusted_running
                    / y1_weighted_points_valid_running
                )
                * 100.000,
                0
            ) as y1_percent_grade_adjusted,

            sum(
                if(
                    term_weighted_points_earned_adjusted_running is not null,
                    term_weighted_points_possible,
                    null
                )
            ) over (
                partition by cc_course_number, cc_studentid, cc_yearid
                order by termbin_end_date asc
            ) as y1_weighted_points_need_to_get_running,

            lag(term_weighted_points_earned_adjusted_running, 1, 0.000) over (
                partition by cc_studentid, cc_yearid, cc_course_number
                order by termbin_end_date asc
            ) as term_weighted_points_earned_adjusted_running_lag,
        from fg_running
    )

select
    y1.cc_dcid,
    y1.cc_studentid as studentid,
    y1.cc_sectionid as sectionid,
    y1.cc_course_number as course_number,
    y1.cc_yearid as yearid,
    y1.cc_academic_year as academic_year,
    y1.cc_abs_termid as termid,
    y1.cc_dateenrolled as dateenrolled,
    y1.cc_dateleft as dateleft,
    y1.cc_schoolid as schoolid,
    y1.courses_course_name as course_name,
    y1.courses_credittype as credittype,
    y1.teacher_lastfirst,
    y1.school_name,
    y1.is_dropped_section,
    y1.storecode,
    y1.term_percent_grade,
    y1.sg_percent,
    y1.fg_percent,
    y1.term_letter_grade,
    y1.sg_letter_grade,
    y1.fg_letter_grade,
    y1.term_percent_grade_adjusted,
    y1.fg_percent_adjusted,
    y1.term_letter_grade_adjusted,
    y1.fg_letter_grade_adjusted,
    y1.y1_percent_grade,
    y1.y1_percent_grade_adjusted,
    y1.term_grade_points,
    y1.sg_grade_points,
    y1.fg_grade_points,
    y1.courses_gradescaleid,
    y1.courses_gradescaleid_unweighted,
    y1.termbin_start_date,
    y1.termbin_end_date,
    y1.termbin_is_current,
    y1.exclude_from_gpa,
    y1.sg_exclude_from_gpa,
    y1.courses_excludefromgpa,
    y1.exclude_from_graduation,
    y1.sg_exclude_from_graduation,
    y1.potential_credit_hours,
    y1.sg_potential_credit_hours,
    y1.courses_credit_hours,
    y1.term_weighted_points_possible,
    y1.term_weighted_points_earned,
    y1.term_weighted_points_earned_adjusted,
    y1.term_weighted_points_earned_adjusted_running,
    y1.y1_weighted_points_possible,
    y1.y1_weighted_points_possible_running,
    y1.y1_weighted_points_earned_running,
    y1.y1_weighted_points_earned_adjusted_running,
    y1.y1_weighted_points_valid_running,
    y1.lastgradeupdate,
    y1.whomodified_teachernumber,
    y1.citizenship,
    y1.comment_value,

    y1gs.grade_points as y1_grade_points,
    y1gs.letter_grade as y1_letter_grade,

    y1gsu.grade_points as y1_grade_points_unweighted,

    if(
        y1.y1_percent_grade < 0.500, 'F*', y1gs.letter_grade
    ) as y1_letter_grade_adjusted,
    if(
        y1gs.letter_grade like 'F%', 0.0, y1.potential_credit_hours
    ) as projected_earned_credit_hours,

    /*
        need-to-get calc:
        - target % x y1 points possible as of next term
        - minus current term points
        - divided by current term weight
    */
    (
        (y1.y1_weighted_points_need_to_get_running * 0.900)
        - y1.term_weighted_points_earned_adjusted_running_lag
    )
    / (y1.term_weighted_points_possible / 100.000) as need_90,
    (
        (y1.y1_weighted_points_need_to_get_running * 0.800)
        - y1.term_weighted_points_earned_adjusted_running_lag
    )
    / (y1.term_weighted_points_possible / 100.000) as need_80,
    (
        (y1.y1_weighted_points_need_to_get_running * 0.700)
        - y1.term_weighted_points_earned_adjusted_running_lag
    )
    / (y1.term_weighted_points_possible / 100.000) as need_70,
    (
        (y1.y1_weighted_points_need_to_get_running * 0.600)
        - y1.term_weighted_points_earned_adjusted_running_lag
    )
    / (y1.term_weighted_points_possible / 100.000) as need_60,
from y1
left join
    {{ ref("int_powerschool__gradescaleitem_lookup") }} as y1gs
    on y1.courses_gradescaleid = y1gs.gradescaleid
    and y1.y1_percent_grade_adjusted
    between y1gs.min_cutoffpercentage and y1gs.max_cutoffpercentage
left join
    {{ ref("int_powerschool__gradescaleitem_lookup") }} as y1gsu
    on y1.courses_gradescaleid_unweighted = y1gsu.gradescaleid
    and y1.y1_percent_grade_adjusted
    between y1gsu.min_cutoffpercentage and y1gsu.max_cutoffpercentage
