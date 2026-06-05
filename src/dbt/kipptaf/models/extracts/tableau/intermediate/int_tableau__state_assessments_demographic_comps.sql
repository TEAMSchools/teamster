{#
    Student-level assessment scores joined to enrollment demographics,
    then aggregated via GROUPING SETS into demographic comparison rows.

    Each grouping set produces one demographic focus at a time (or a total),
    crossed with region present-or-rolled-up — 12 sets total.
#}
{% set base_dims = [
    "academic_year",
    "district_state",
    "assessment_name",
    "test_code",
] %}

{% set focus_dims = [
    "gender",
    "aggregate_ethnicity",
    "lunch_status",
    "ml_status",
    "iep_status",
] %}

with
    /*
        Prelim score gating: automatically includes preliminary NJ scores only
        when official scores for that assessment/year have not yet landed in
        int_pearson__all_assessments. This eliminates the need to manually
        comment/uncomment the prelim branch each time a new student list file
        is loaded — the branch self-deactivates once official scores arrive.
    */
    prelim_assessments as (
        select academic_year, test_type, count(*) as record_count,

        from {{ ref("int_pearson__student_list_report") }}
        where
            -- 2024: first year we track preliminary scores for comparison
            academic_year >= 2024
            and administration = 'Spring'
            and scale_score is not null
        group by academic_year, test_type
    ),

    valid_prelim_assessments as (
        select pa.academic_year, pa.test_type,

        from prelim_assessments as pa
        left join
            {{ ref("int_pearson__all_assessments") }} as p
            on pa.academic_year = p.academic_year
            -- test_type in prelim data matches assessment_name in official records
            and pa.test_type = p.assessment_name
            and p.`admin` = 'Spring'
        group by pa.academic_year, pa.test_type
        having count(p.assessment_name) = 0
    ),

    test_code_metadata as (
        select
            aligned_test_code,
            school_level,
            any_value(grade_range_band) as grade_range_band,
            any_value(discipline) as discipline,

        from {{ ref("stg_google_sheets__state_test_comparison_demographics") }}
        group by aligned_test_code, school_level
    ),

    scores as (
        -- NJ's official scores
        select
            e.academic_year,
            e.region,
            e.student_number,

            a.district_state,
            a.assessment_name,
            a.is_proficient_int,
            a.aligned_test_code as test_code,
            a.aligned_ml_status as ml_status,

            e.aligned_gender as gender,

            a.aligned_aggregate_ethnicity as aggregate_ethnicity,
            a.aligned_iep_status as iep_status,

            /*
                Use school_level_alt (not school_level) — carries PS-classification
                overrides for schools whose high_grade maps to the wrong band (e.g.
                Sumner reclassified to ES in 2025 but its Grade 5 remains MS band).

                Hatch 2021-2023 Gr3/4: students were enrolled at an MS-classified
                school due to historical PS data issues; Grade 3/4 assessment band
                is ES and the Google Sheet only carries ES entries for ELA03/MAT03/
                ELA04/MAT04.

                PPES 2023 Gr5: Paterson Prep Elementary was growing grade-by-grade
                (school_level = ES, high_grade = 5); Grade 5 assessment band is MS
                and the Google Sheet only carries MS entries for ELA05/MAT05/SCI05.
            */
            case
                when
                    e.academic_year in (2021, 2022, 2023)
                    and e.school = 'Hatch'
                    and e.grade_level in (3, 4)
                then 'ES'
                when e.academic_year = 2023 and e.school = 'PPES' and e.grade_level = 5
                then 'MS'
                else e.school_level_alt
            end as school_level,

            if(
                e.lunch_status in ('F', 'R'),
                'Economically Disadvantaged',
                'Non Economically Disadvantaged'
            ) as lunch_status,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("int_pearson__all_assessments") }} as a
            on e.academic_year = a.academic_year
            and e.pearson_local_student_identifier = a.localstudentidentifier
            and {{ union_dataset_join_clause(left_alias="e", right_alias="a") }}
            and a.`admin` = 'Spring'
            and a.testscalescore is not null
        where
            e.rn_year = 1
            -- 2018: earliest year with available comps data
            and e.academic_year >= 2018
            and e.grade_level > 2
            and e.school_level != 'OD'
            -- ELA11 was not a valid NJSLA test for Spring 2018-2019
            and a.aligned_test_code != 'ELA11'

        union all

        -- NJ's prelim scores
        select
            e.academic_year,
            e.region,
            e.student_number,

            a.district_state,
            a.test_type as assessment_name,
            a.is_proficient_int,
            a.aligned_test_code as test_code,

            e.ml_status,
            e.aligned_gender as gender,

            case
                when e.race_ethnicity = 'B'
                then 'African American'
                when e.race_ethnicity = 'A'
                then 'Asian'
                when e.race_ethnicity = 'I'
                then 'American Indian'
                when e.race_ethnicity = 'H'
                then 'Hispanic'
                when e.race_ethnicity = 'P'
                then 'Native Hawaiian'
                when e.race_ethnicity = 'T'
                then 'Other'
                when e.race_ethnicity = 'W'
                then 'White'
                when e.race_ethnicity is null
                then 'Blank'
            end as aggregate_ethnicity,

            if(
                e.iep_status = 'Has IEP',
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as iep_status,

            /*
                Use school_level_alt (not school_level) — carries PS-classification
                overrides for schools whose high_grade maps to the wrong band (e.g.
                Sumner reclassified to ES in 2025 but its Grade 5 remains MS band).

                Hatch 2021-2023 Gr3/4: students were enrolled at an MS-classified
                school due to historical PS data issues; Grade 3/4 assessment band
                is ES and the Google Sheet only carries ES entries for ELA03/MAT03/
                ELA04/MAT04.

                PPES 2023 Gr5: Paterson Prep Elementary was growing grade-by-grade
                (school_level = ES, high_grade = 5); Grade 5 assessment band is MS
                and the Google Sheet only carries MS entries for ELA05/MAT05/SCI05.
            */
            case
                when
                    e.academic_year in (2021, 2022, 2023)
                    and e.school = 'Hatch'
                    and e.grade_level in (3, 4)
                then 'ES'
                when e.academic_year = 2023 and e.school = 'PPES' and e.grade_level = 5
                then 'MS'
                else e.school_level_alt
            end as school_level,

            if(
                e.lunch_status in ('F', 'R'),
                'Economically Disadvantaged',
                'Non Economically Disadvantaged'
            ) as lunch_status,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("int_pearson__student_list_report") }} as a
            on e.academic_year = a.academic_year
            and e.pearson_local_student_identifier = a.local_student_identifier
            and {{ union_dataset_join_clause(left_alias="e", right_alias="a") }}
            -- see prelim_assessments CTE
            and a.academic_year >= 2024
            and a.administration = 'Spring'
            and a.scale_score is not null
        inner join
            valid_prelim_assessments as vpa
            on a.academic_year = vpa.academic_year
            and a.test_type = vpa.test_type
        where
            e.rn_year = 1
            -- 2018: earliest year with available comps data
            and e.academic_year >= 2018
            and e.grade_level > 2
            and e.school_level != 'OD'
            -- ELA11 was not a valid NJSLA test for Spring 2018-2019
            and a.aligned_test_code != 'ELA11'

        union all

        -- FL's official scores
        select
            e.academic_year,
            e.region,
            e.student_number,

            a.district_state,
            a.assessment_name,
            a.is_proficient_int,
            a.test_code,

            e.ml_status,
            e.aligned_gender as gender,

            case
                when e.race_ethnicity = 'B'
                then 'African American'
                when e.race_ethnicity = 'A'
                then 'Asian'
                when e.race_ethnicity = 'I'
                then 'American Indian'
                when e.race_ethnicity = 'H'
                then 'Hispanic'
                when e.race_ethnicity = 'P'
                then 'Native Hawaiian'
                when e.race_ethnicity = 'T'
                then 'Other'
                when e.race_ethnicity = 'W'
                then 'White'
                when e.race_ethnicity is null
                then 'Blank'
            end as aggregate_ethnicity,

            if(
                e.iep_status = 'Has IEP',
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as iep_status,

            e.school_level,

            if(
                e.lunch_status in ('F', 'R'),
                'Economically Disadvantaged',
                'Non Economically Disadvantaged'
            ) as lunch_status,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            {{ ref("int_fldoe__all_assessments") }} as a
            on e.academic_year = a.academic_year
            and e.state_studentnumber = a.student_id
            and {{ union_dataset_join_clause(left_alias="e", right_alias="a") }}
            and a.results_type = 'Actual'
            and a.scale_score is not null
            and a.season = 'Spring'
        where
            e.region = 'Miami'
            and e.rn_year = 1
            -- 2018: earliest year with available comps data
            and e.academic_year >= 2018
            and e.grade_level > 2
    )

select
    s.academic_year,
    s.district_state,
    s.region,
    s.assessment_name,
    s.test_code,

    round(
        avg(s.is_proficient_int) * count(s.student_number), 0
    ) as total_proficient_students,

    count(s.student_number) as total_students,

    avg(s.is_proficient_int) as percent_proficient,

    /* (a) focus_level + demographic labels */
    case
        {% for dim in focus_dims %}
            when grouping({{ dim }}) = 0 then '{{ dim }}'
        {% endfor %}
        else 'all_null'
    end as focus_level,

    case
        when
            {% for dim in focus_dims %}
                grouping({{ dim }}) = 1{% if not loop.last %} and {% endif %}
            {% endfor %}
        then 'Total'
        when
            grouping(s.ml_status) = 0
            or grouping(s.iep_status) = 0
            or grouping(s.lunch_status) = 0
        then 'Subgroup'
        when grouping(s.gender) = 0
        then 'Gender'
        when grouping(s.aggregate_ethnicity) = 0
        then 'Aggregate Ethnicity'
    end as comparison_demographic_group,

    case
        when
            {% for dim in focus_dims %}
                grouping({{ dim }}) = 1{% if not loop.last %} and {% endif %}
            {% endfor %}
        then 'All Students'
        else
            coalesce(
                s.gender,
                s.aggregate_ethnicity,
                s.lunch_status,
                s.ml_status,
                s.iep_status
            )
    end as comparison_demographic_subgroup,

    /* (b) comparison_entity from region null-ness */
    if(grouping(s.region) = 1, s.district_state, 'Region') as comparison_entity,

    /* (c) test_code-derived columns via sheet lookup */
    any_value(m.school_level) as school_level,
    any_value(m.grade_range_band) as grade_range_band,
    any_value(m.discipline) as discipline,

from scores as s
left join
    test_code_metadata as m
    on s.test_code = m.aligned_test_code
    and s.school_level = m.school_level
group by
    grouping sets (
        {# Total (all focus dims rolled up) — with and without region #}
        ({{ base_dims | join(", ") }}, s.region),
        ({{ base_dims | join(", ") }}),

        {# One focus dim active at a time — with and without region #}
        {% for dim in focus_dims %}
            ({{ base_dims | join(", ") }}, s.region, {{ dim }}),
            ({{ base_dims | join(", ") }}, {{ dim }})
            {% if not loop.last %},{% endif %}
        {% endfor %}
    )
