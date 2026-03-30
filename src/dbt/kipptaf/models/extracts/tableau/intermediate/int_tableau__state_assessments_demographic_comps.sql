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
    assessment_scores as (
        select
            _dbt_source_relation,
            academic_year,
            localstudentidentifier,
            statestudentidentifier as state_id,
            assessment_name,
            is_proficient,
            is_proficient_int,

            results_type,
            district_state,
            aligned_test_code as test_code,

            case
                when race_ethnicity = 'B'
                then 'African American'
                when race_ethnicity = 'A'
                then 'Asian'
                when race_ethnicity = 'I'
                then 'American Indian'
                when race_ethnicity = 'H'
                then 'Hispanic'
                when race_ethnicity = 'P'
                then 'Native Hawaiian'
                when race_ethnicity = 'T'
                then 'Other'
                when race_ethnicity = 'W'
                then 'White'
                when race_ethnicity is null
                then 'Blank'
            end as aggregate_ethnicity,

            if(lep_status, 'ML', 'Not ML') as ml_status,

            if(
                iep_status = 'Has IEP',
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as iep_status,

        from {{ ref("int_pearson__all_assessments") }}
        where
            testscalescore is not null and `period` = 'Spring' and academic_year >= 2018

        union all

        select
            _dbt_source_relation,
            academic_year,

            null as localstudentidentifier,

            student_id as state_id,
            assessment_name,
            is_proficient,
            if(is_proficient, 1, 0) as is_proficient_int,

            'Actual' as results_type,
            'KTAF FL' as district_state,

            test_code,

            null as aggregate_ethnicity,
            null as ml_status,
            null as iep_status,

        from {{ ref("int_fldoe__all_assessments") }}
        where scale_score is not null and season = 'Spring'

        union all

        select
            _dbt_source_relation,
            academic_year,

            local_student_identifier as localstudentidentifier,

            cast(state_student_identifier as string) as state_id,

            test_type as assessment_name,
            is_proficient,
            if(is_proficient, 1, 0) as is_proficient_int,
            results_type,
            district_state,
            aligned_test_code as test_code,

            null as aggregate_ethnicity,
            null as ml_status,
            null as iep_status,

        from {{ ref("int_pearson__student_list_report") }}
        where
            state_student_identifier is not null
            and administration = 'Spring'
            and test_type = 'NJSLA'
            and academic_year = {{ var("current_academic_year") }}
    ),

    /* NJ scores */
    nj_scores as (
        select
            e.academic_year,
            e.region,
            e.student_number,

            a.district_state,
            a.assessment_name,
            a.aggregate_ethnicity,
            a.ml_status,
            a.iep_status,
            a.is_proficient_int,

            if(
                e.lunch_status in ('F', 'R'),
                'Economically Disadvantaged',
                'Non Economically Disadvantaged'
            ) as lunch_status,

            case
                when a.test_code = 'ALG01'
                then concat(a.test_code, '_', e.school_level)
                else a.test_code
            end as test_code,

            case
                e.gender
                when 'F'
                then 'Female'
                when 'M'
                then 'Male'
                when 'X'
                then 'Non-Binary'
            end as gender,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            assessment_scores as a
            on e.academic_year = a.academic_year
            and e.pearson_local_student_identifier = a.localstudentidentifier
            and {{ union_dataset_join_clause(left_alias="e", right_alias="a") }}
            and a.results_type = 'Actual'
        where
            e.rn_year = 1
            and e.academic_year >= {{ var("current_academic_year") - 7 }}
            and e.grade_level > 2
            and e.school_level != 'OD'
    ),

    /* FL scores */
    fl_scores as (
        select
            e.academic_year,
            e.region,
            e.student_number,

            a.district_state,
            a.assessment_name,

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

            e.ml_status,

            if(
                e.iep_status = 'Has IEP',
                'Students With Disabilities',
                'Students Without Disabilities'
            ) as iep_status,

            a.is_proficient_int,

            if(
                e.lunch_status in ('F', 'R'),
                'Economically Disadvantaged',
                'Non Economically Disadvantaged'
            ) as lunch_status,

            case
                when a.test_code = 'ALG01'
                then concat(a.test_code, '_', e.school_level)
                else a.test_code
            end as test_code,

            case
                e.gender
                when 'F'
                then 'Female'
                when 'M'
                then 'Male'
                when 'X'
                then 'Non-Binary'
            end as gender,

        from {{ ref("int_extracts__student_enrollments") }} as e
        inner join
            assessment_scores as a
            on e.academic_year = a.academic_year
            and e.state_studentnumber = a.state_id
            and {{ union_dataset_join_clause(left_alias="e", right_alias="a") }}
            and a.results_type = 'Actual'
        where
            e.region = 'Miami'
            and e.rn_year = 1
            and e.academic_year >= {{ var("current_academic_year") - 7 }}
            and e.grade_level > 2
    ),

    demographic_comps as (
        select *
        from nj_scores
        union all
        select *
        from fl_scores
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

    /* (c) test_code-derived columns */
    case
        when
            test_code in (
                'ELA09',
                'ELA10',
                'ELA11',
                'ELAGP',
                'ALG01_HS',
                'GEO01',
                'ALG02',
                'MATGP',
                'SCI11'
            )
        then 'HS'
        when test_code = 'ALG01_MS'
        then 'MS'
        when safe_cast(right(test_code, 2) as numeric) between 5 and 8
        then 'MS'
        else 'ES'
    end as school_level,

    case
        when
            test_code in (
                'ELA09',
                'ELA10',
                'ELA11',
                'ELAGP',
                'ALG01_HS',
                'GEO01',
                'ALG02',
                'MATGP',
                'SCI11'
            )
        then 'HS'
        else '3-8'
    end as grade_range_band,

    case
        when left(test_code, 3) in ('MAT', 'ALG', 'GEO')
        then 'Math'
        when left(test_code, 3) = 'ELA'
        then 'ELA'
        when left(test_code, 3) = 'SCI'
        then 'Science'
        when left(test_code, 3) = 'SOC'
        then 'Social Studies'
    end as discipline,

from demographic_comps

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
