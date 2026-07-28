{% set scaffold_source_mode = var("finalsite_scaffold_source", "blend") %}
{% if scaffold_source_mode not in ("powerschool", "blend") %}
    {{
        exceptions.raise_compiler_error(
            "finalsite_scaffold_source must be 'powerschool' or 'blend' -- got"
            ~ " '"
            ~ scaffold_source_mode
            ~ "'"
        )
    }}
{% endif %}

with
    powerschool as (
        select
            school_level,
            school_number,
            abbreviation,
            _dbt_source_project,

            {{ extract_region("stg_powerschool__schools") }} as region,

        from {{ ref("stg_powerschool__schools") }}
        where state_excludefromreporting = 0 and _dbt_source_project != 'kippmiami'
    ),

    /* Grade membership is derived from current enrollment, not
       low_grade/high_grade -- see fresh-dashboard-data-model.md. */
    current_grade_levels as (
        select distinct
            schoolid,
            grade_level,
            _dbt_source_project,

            case
                when grade_level >= 9
                then 'HS'
                when grade_level >= 5
                then 'MS'
                else 'ES'
            end as school_level_alt,

        from {{ ref("stg_powerschool__students") }}
        where enroll_status = 0
    ),

    powerschool_scaffold as (
        select
            ps.school_level,
            ps.region,
            ps.school_number as schoolid,
            ps.abbreviation as school,

            cgl.grade_level,
            cgl.school_level_alt,

            'KTAF' as org,
            'powerschool' as scaffold_source,

            {{ var("finalsite_recruitment_year") }} as enrollment_academic_year,

        from powerschool as ps
        inner join
            current_grade_levels as cgl
            on ps.school_number = cgl.schoolid
            and ps._dbt_source_project = cgl._dbt_source_project
    ),

    focus as (
        select
            school_level,
            school_number,
            abbreviation,
            _dbt_source_project,

            {{ extract_region("stg_powerschool__schools") }} as region,

        from {{ ref("stg_powerschool__schools") }}
        where state_excludefromreporting = 0 and _dbt_source_project != 'kippmiami'
    ),

    /* Focus mirror of powerschool_scaffold above -- see
       fresh-dashboard-data-model.md. */
    focus_levels as (
        select distinct
            ps_schoolid as schoolid,
            school_abbreviation as school,
            region,
            grade_level,

            case
                when grade_level >= 9
                then 'HS'
                when grade_level >= 5
                then 'MS'
                else 'ES'
            end as school_level,

        from {{ ref("int_focus__student_enrollments") }}
        where
            enroll_status = 0
            and academic_year = {{ var("current_academic_year") }}
            and rn_year = 1
            and ps_schoolid is not null
    ),

    focus_scaffold as (
        select
            schoolid,
            school,
            region,
            grade_level,

            {{ var("finalsite_recruitment_year") }} as enrollment_academic_year,

            'KTAF' as org,
            'focus' as scaffold_source,

            school_level,

            if(
                schoolid = 179905 and grade_level >= 5, 'MS', school_level
            ) as school_level_alt,

        from focus_levels
    )

    {% if scaffold_source_mode == "blend" and var(
        "finalsite_recruitment_year"
    ) != var("current_academic_year") %}
        ,

        existing_keys as (
            select schoolid, grade_level,
            from powerschool_scaffold

            union all

            select schoolid, grade_level,
            from focus_scaffold
        ),

        /* Schools/grades Finalsite is recruiting for that don't exist in
           PowerSchool/Focus yet -- see fresh-dashboard-data-model.md and the
           fresh-dashboard skill's rollover procedure. */
        finalsite_new as (
            select distinct
                u.schoolid,
                u.school,
                u.region,
                u.grade_level,

                case
                    when u.grade_level >= 9
                    then 'HS'
                    when u.grade_level >= 5
                    then 'MS'
                    else 'ES'
                end as school_level,

            from {{ ref("int_finalsite__status_report_unpivot") }} as u
            left join
                existing_keys as k
                on u.schoolid = k.schoolid
                and u.grade_level = k.grade_level
            where
                u.enrollment_academic_year = {{ var("finalsite_recruitment_year") }}
                and u.schoolid != 0
                and k.schoolid is null
        ),

        finalsite_new_scaffold as (
            select
                schoolid,
                school,
                region,
                grade_level,

                {{ var("finalsite_recruitment_year") }} as enrollment_academic_year,

                'KTAF' as org,
                'finalsite' as scaffold_source,

                school_level,

                if(
                    schoolid = 179905 and grade_level >= 5, 'MS', school_level
                ) as school_level_alt,

            from finalsite_new
        )
    {% endif %}

    {% if scaffold_source_mode == "blend" %}
        ,

        selected_scaffold as (
            select
                schoolid,
                school,
                region,
                grade_level,
                enrollment_academic_year,
                org,
                scaffold_source,
                school_level,
                school_level_alt,
            from powerschool_scaffold

            union all

            select
                schoolid,
                school,
                region,
                grade_level,
                enrollment_academic_year,
                org,
                scaffold_source,
                school_level,
                school_level_alt,
            from focus_scaffold

            {% if var("finalsite_recruitment_year") != var(
                    "current_academic_year"
                ) %}
                union all

                select
                    schoolid,
                    school,
                    region,
                    grade_level,
                    enrollment_academic_year,
                    org,
                    scaffold_source,
                    school_level,
                    school_level_alt,
                from finalsite_new_scaffold
            {% endif %}
        ),

        school_priority as (
            select
                schoolid,
                school,
                region,
                enrollment_academic_year,
                org,

                min(
                    case
                        scaffold_source
                        when 'powerschool'
                        then 1
                        when 'focus'
                        then 2
                        else 3
                    end
                ) as source_priority,

            from selected_scaffold
            group by schoolid, school, region, enrollment_academic_year, org
        )
    {% endif %}

{% if scaffold_source_mode == "powerschool" %}

    select
        schoolid,
        school,
        region,
        grade_level,
        enrollment_academic_year,
        org,
        scaffold_source,
        school_level,
        school_level_alt,
    from powerschool_scaffold

{% else %}

    select
        schoolid,
        school,
        region,
        grade_level,
        enrollment_academic_year,
        org,
        scaffold_source,
        school_level,
        school_level_alt,
    from selected_scaffold

    union all

    select
        schoolid,
        school,
        region,

        -9 as grade_level,

        enrollment_academic_year,
        org,

        case
            source_priority
            when 1
            then 'powerschool'
            when 2
            then 'focus'
            else 'finalsite'
        end as scaffold_source,

        cast(null as string) as school_level,
        cast(null as string) as school_level_alt,

    from school_priority

    union all

    /* grain projection: school_level is functionally determined by
       grade_level alone (same CASE everywhere), so distinct on the region
       grain is safe, not a dup mask. */
    select distinct
        0 as schoolid,

        region as school,
        region,
        grade_level,
        enrollment_academic_year,
        org,

        cast(null as string) as scaffold_source,

        school_level,
        school_level as school_level_alt,

    from selected_scaffold

{% endif %}
