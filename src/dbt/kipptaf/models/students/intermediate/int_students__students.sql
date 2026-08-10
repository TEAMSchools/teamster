with
    -- int_focus__student_enrollments.student_number holds the PREFIXED Focus id,
    -- not the network student number, so it is unprefixed here before joining.
    -- Focus also records enroll_status per stint (1,090 students carry more than
    -- one value), while the network treats it as the student's current standing
    -- copied onto every row, so the most recent stint wins.
    -- trunk-ignore(sqlfluff/ST03): referenced via dbt_utils.deduplicate below
    enrollment_stints as (
        select
            academic_year,
            startdate,
            enroll_status,

            {{ unprefix_focus_student_id("student_number") }} as student_number,
        from {{ ref("int_focus__student_enrollments") }}
    ),

    current_stint as (
        {{
            dbt_utils.deduplicate(
                relation="enrollment_stints",
                partition_by="student_number",
                order_by="academic_year desc, startdate desc",
            )
        }}
    ),

    -- The unprefixed Focus student id is the canonical network student number.
    identified as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            first_name,
            middle_name,
            last_name,
            powerschool_id,
            disis_id,
            florida_student_number,
            florida_education_identifier,
            race_white_label,
            race_asian_label,
            race_black_or_african_american_label,
            race_american_indian_or_alaska_native_label,
            race_native_hawaiian_or_other_pacific_islander_label,

            {{ unprefix_focus_student_id("student_id") }} as student_number,

            date(birthdate) as dob,

            regexp_extract(sex_label, r'\[(\w+)\]') as gender,
        from {{ ref("int_focus__students") }}
    ),

    -- Focus race flags decode to Yes/No labels. The archive's ethnicity column
    -- is a race code that ignores Hispanic ethnicity entirely: 322 students
    -- flagged Hispanic and White carry 'W', and 239 flagged Hispanic and Black
    -- carry 'B'. Reproduce that convention rather than the federal one.
    raced as (
        select
            *,

            (
                if(race_black_or_african_american_label = 'Yes', 1, 0)
                + if(race_white_label = 'Yes', 1, 0)
                + if(race_asian_label = 'Yes', 1, 0)
                + if(race_american_indian_or_alaska_native_label = 'Yes', 1, 0)
                + if(race_native_hawaiian_or_other_pacific_islander_label = 'Yes', 1, 0)
            ) as race_count,
        from identified
    ),

    -- Miami student identity from Focus, conformed to the PowerSchool column
    -- names and value domains so it merges into the network student spine below
    -- by column name (full union all corresponding).
    focus_conformed as (
        select
            r._dbt_source_relation,
            r._dbt_source_project,
            r.student_number,
            r.first_name,
            r.middle_name,
            r.last_name,
            r.powerschool_id,
            r.florida_student_number,
            r.florida_education_identifier,

            -- dob and gender take Focus, not the archive: Focus is the live
            -- system and the two agree on all but 13 and 5 of 3,453 returning
            -- students, which are post-freeze corrections that should win.
            r.dob,
            r.gender,

            e.enroll_status,

            -- Focus's free_reduced_meals_program is a CEP direct-certification
            -- flag, not an eligibility status -- every Miami student carries
            -- the same "CEP NOT Direct Cert" value, and Focus stores nothing
            -- resembling the archive's F/R/P domain. Null until Ops surfaces a
            -- real per-student eligibility field; a school-wide constant would
            -- feed an economic-disadvantage proxy with no signal in it.
            cast(null as string) as lunchstatus,

            -- dim_students publishes this as district_student_identifier for
            -- Miami. disis_id is the MDCPS id, stored as NUMERIC, which drops
            -- the leading zero most of them carry -- pad back to the 7 digits
            -- MDCPS issues. Populated only for students the PowerSchool
            -- migration brought over, so it is null for anyone enrolled since,
            -- until Ops fills it.
            lpad(cast(r.disis_id as string), 7, '0') as state_studentnumber,

            case
                when r.race_count > 1
                then 'T'
                when r.race_black_or_african_american_label = 'Yes'
                then 'B'
                when r.race_white_label = 'Yes'
                then 'W'
                when r.race_asian_label = 'Yes'
                then 'A'
                when r.race_american_indian_or_alaska_native_label = 'Yes'
                then 'I'
                when r.race_native_hawaiian_or_other_pacific_islander_label = 'Yes'
                then 'P'
            end as ethnicity,
        from raced as r
        left join current_stint as e on r.student_number = e.student_number
    ),

    -- Focus is Miami's system of record for student identity, so the frozen
    -- archive contributes no rows -- only the carry-forward values above, for
    -- the fields Focus has no source for. The 493 departed students the Focus
    -- seed never received are dropped with it.
    powerschool_filtered as (
        select p.*,
        from {{ ref("stg_powerschool__students") }} as p
        where p._dbt_source_project != 'kippmiami'
    )

select *,
from powerschool_filtered

full union all corresponding

select *,
from focus_conformed
