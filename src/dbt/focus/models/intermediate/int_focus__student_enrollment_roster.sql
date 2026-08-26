with
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollment as (
        select
            s.first_name as student_first_name,
            s.last_name as student_last_name,
            s.florida_education_identifier as fteid,
            s.student_e_mail_address as student_email,
            s.student_id as student_number,
            s.dob,

            -- int_focus__students already strips the 8400 Miami-Dade district
            -- prefix and casts birthdate to a date, so both are read from there
            -- rather than re-derived here.
            s.student_number as network_student_number,

            e.id as student_enrollment_id,
            e.created_at as enrollment_created_at,
            e.syear as academic_year,
            e.school_id as schoolid,
            e.start_date as startdate,
            e.prior_district_label,
            e.prior_state_label,
            e.prior_country_label,
            e.educational_choice_label,
            e.student_offender_transfer_label,

            sch.title as school_title,
            sch.state_school_id as school_state_school_id,
            sch.school_number,
            sch.state,
            sch.school_level,

            g.short_name as grade_level_short_name,

            ec.short_name as entrycode,

            dc.short_name as exitcode,

            fd.first_day_of_school,

            concat(s.last_name, ', ', s.first_name) as student_name,

            cast(e.syear as string)
            || '-'
            || right(cast(e.syear + 1 as string), 2) as academic_year_display,

            coalesce(e.end_date, date(e.syear + 1, 6, 30)) as exitdate,

            case
                g.short_name
                when 'PK'
                then -1
                when 'KG'
                then 0
                else cast(regexp_extract(g.short_name, r'\d+') as int)
            end as grade_level,

            case
                when dc.grad_type = 'graduated'
                then 3
                when e.drop_code is not null
                then 2
                else 0
            end as enroll_status,

        from {{ ref("int_focus__students") }} as s
        inner join
            {{ ref("int_focus__student_enrollment") }} as e
            on s.student_id = e.student_id
        left join {{ ref("int_focus__schools") }} as sch on e.school_id = sch.id
        left join
            {{ ref("stg_focus__school_gradelevels") }} as g
            on e.grade_id = g.id
            and e.school_id = g.school_id
            and g.short_name != '30'
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as ec
            on e.enrollment_code = ec.id
        left join
            {{ ref("stg_focus__student_enrollment_codes") }} as dc
            on e.drop_code = dc.id
        -- TODO: first day is network-wide per syear; if per-school calendar
        -- variance matters (or a second Focus region onboards), key this by
        -- school as well.
        left join
            {{ ref("int_focus__school_year_first_day") }} as fd on e.syear = fd.syear
    ),

    -- Focus permits two open stints for the same student, year, and start
    -- date; SY26 is the first year of Focus data where it has happened. The
    -- incomplete record is demoted, then the most recently created one wins.
    -- Recency reads enrollment_created_at, not the id: Focus assigns ids in
    -- batches, and 20% of SY26 id pairs order differently than creation time,
    -- so the id alone is not a recency proxy. The id breaks exact ties.
    -- Deduping here, ahead of with_flags, keeps rn_year contiguous --
    -- consumers filter on rn_year = 1 and would lose a student left holding
    -- only rn_year = 2.
    -- TODO: drop once Focus stops accepting duplicate open stints (#4905).
    deduplicate as (
        {{
            dbt_utils.deduplicate(
                relation="enrollment",
                partition_by="student_number, academic_year, startdate",
                order_by="""
                    (schoolid is null) asc,
                    enrollment_created_at desc,
                    student_enrollment_id desc
                """,
            )
        }}
    ),

    with_flags as (
        -- trunk-ignore(sqlfluff/AM04): deduplicate resolves columns at run time
        select
            *,

            if(startdate <= first_day_of_school, true, false) as is_enrolled_fdos,

            if(
                date(academic_year, 10, 1) between startdate and exitdate, true, false
            ) as is_enrolled_oct01,

            if(
                date(academic_year, 10, 15) between startdate and exitdate, true, false
            ) as is_enrolled_oct15,

            if(
                date(academic_year + 1, 3, 15) between startdate and exitdate,
                true,
                false
            ) as is_enrolled_mar15,

            if(exitdate < first_day_of_school, true, false) as is_pre_year_withdrawal,

            row_number() over (
                partition by student_number, academic_year
                order by academic_year desc, exitdate desc
            ) as rn_year,

            row_number() over (
                partition by student_number
                order by academic_year desc, exitdate desc, startdate desc
            ) as rn_all,
        from deduplicate
    ),

    with_year_counts as (
        select
            *,

            row_number() over (
                partition by student_number, schoolid, rn_year
                order by academic_year asc, exitdate asc
            ) as year_in_school,

            row_number() over (
                partition by student_number, rn_year
                order by academic_year asc, exitdate asc
            ) as year_in_network,
        from with_flags
    )

select
    * except (year_in_school, year_in_network),

    if(rn_year = 1, year_in_school, null) as year_in_school,

    if(rn_year = 1, year_in_network, null) as year_in_network,

from with_year_counts
