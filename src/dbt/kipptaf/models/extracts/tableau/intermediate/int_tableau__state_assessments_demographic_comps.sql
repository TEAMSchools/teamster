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
    test_code_metadata as (
        select
            aligned_level_test_code,
            any_value(school_level) as school_level,
            any_value(grade_range_band) as grade_range_band,
            any_value(discipline) as discipline,
        from {{ ref("stg_google_sheets__state_test_comparison_demographics") }}
        group by aligned_level_test_code
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
            and a.academic_year >= 2018
            and a.season = 'Spring'
            and a.testscalescore is not null
        where
            e.rn_year = 1
            and e.academic_year >= {{ var("current_academic_year") - 7 }}
            and e.grade_level > 2
            and e.school_level != 'OD'

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
            and a.academic_year >= 2018
            and a.administration = 'Spring'
            and a.scale_score is not null
        where
            e.rn_year = 1
            and e.academic_year >= {{ var("current_academic_year") - 7 }}
            and e.grade_level > 2
            and e.school_level != 'OD'

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
            and e.academic_year >= {{ var("current_academic_year") - 7 }}
            and e.grade_level > 2
    )

select
    academic_year,
    district_state,
    region,
    assessment_name,
    test_code,

    round(
        avg(is_proficient_int) * count(student_number), 0
    ) as total_proficient_students,
    count(student_number) as total_students,
    avg(is_proficient_int) as percent_proficient,

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
            grouping(ml_status) = 0
            or grouping(iep_status) = 0
            or grouping(lunch_status) = 0
        then 'Subgroup'
        when grouping(gender) = 0
        then 'Gender'
        when grouping(aggregate_ethnicity) = 0
        then 'Aggregate Ethnicity'
    end as comparison_demographic_group,

    case
        when
            {% for dim in focus_dims %}
                grouping({{ dim }}) = 1{% if not loop.last %} and {% endif %}
            {% endfor %}
        then 'All Students'
        else coalesce(gender, aggregate_ethnicity, lunch_status, ml_status, iep_status)
    end as comparison_demographic_subgroup,

    /* (b) comparison_entity from region null-ness */
    if(grouping(region) = 1, district_state, 'Region') as comparison_entity,

    /* (c) test_code-derived columns via sheet lookup */
    any_value(m.school_level) as school_level,
    any_value(m.grade_range_band) as grade_range_band,
    any_value(m.discipline) as discipline,

from scores
left join test_code_metadata as m on scores.test_code = m.aligned_level_test_code
group by
    grouping sets (
        {# Total (all focus dims rolled up) — with and without region #}
        ({{ base_dims | join(", ") }}, region),
        ({{ base_dims | join(", ") }}),

        {# One focus dim active at a time — with and without region #}
        {% for dim in focus_dims %}
            ({{ base_dims | join(", ") }}, region, {{ dim }}),
            ({{ base_dims | join(", ") }}, {{ dim }})
            {% if not loop.last %},{% endif %}
        {% endfor %}
    )
