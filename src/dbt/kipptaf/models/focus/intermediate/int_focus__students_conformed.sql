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

            cast(
                regexp_replace(cast(student_number as string), r'^8400', '') as int64
            ) as student_number,
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
    -- Strip a leading 8400 (Miami-Dade's FLDOE district number) where present;
    -- pass any other value through unchanged rather than guessing at a different
    -- prefix, so the one known anomalous id stays visible instead of being
    -- silently mangled.
    identified as (
        select
            _dbt_source_relation,
            _dbt_source_project,
            first_name,
            middle_name,
            last_name,
            powerschool_id,
            florida_student_number,
            florida_education_identifier,
            race_white_label,
            race_asian_label,
            race_black_or_african_american_label,
            race_american_indian_or_alaska_native_label,
            race_native_hawaiian_or_other_pacific_islander_label,

            cast(
                regexp_replace(cast(student_id as string), r'^8400', '') as int64
            ) as student_number,

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

    -- lunchstatus has no usable Focus source: free_reduced_meals_program is a
    -- single school-wide Community Eligibility Provision constant, so it carries
    -- no per-student signal. Carry the archive value forward for returning
    -- students; new students get null, because a fabricated FRL value feeds an
    -- economic-disadvantage proxy. spedlep and lep_status get the same treatment
    -- in int_focus__student_core_fields_conformed, which is where the archive
    -- keeps them.
    --
    -- ethnicity carries forward too, for a different reason: the archive is
    -- internally inconsistent (Hispanic with no race flag maps to 'T' for 36
    -- students and 'H' for 8), so no derivation can reproduce it. Carrying it
    -- forward keeps dim_students.race byte-identical for returning students.
    archive as (
        select student_number, lunchstatus, ethnicity,
        from {{ ref("stg_powerschool__students") }}
        where _dbt_source_project = 'kippmiami'
    )

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

    -- dob and gender take Focus, not the archive: Focus is the live system and
    -- the two agree on all but 13 and 5 of 3,453 returning students, which are
    -- post-freeze corrections that should win.
    r.dob,
    r.gender,

    a.lunchstatus,

    e.enroll_status,

    coalesce(
        a.ethnicity,
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
        end
    ) as ethnicity,

from raced as r
left join archive as a on r.student_number = a.student_number
left join current_stint as e on r.student_number = e.student_number
