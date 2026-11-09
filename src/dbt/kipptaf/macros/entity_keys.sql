{#-
    One macro per entity whose surrogate key is hashed in 2+ marts (rule A7).
    Arguments are column expressions as strings, in the order shown.
    nullable: true wraps the hash as null when the first argument is null;
    a column expression wraps it as null when that expression is null.
-#}
{% macro _entity_key(columns, nullable) %}
    {%- set hash = dbt_utils.generate_surrogate_key(columns) -%}
    {%- if nullable is sameas true -%} {%- set nullable = columns[0] -%} {%- endif -%}
    {%- if nullable -%}
        {%- set wrapped = "if(" ~ nullable ~ " is not null, " ~ hash -%}
        {{ return(wrapped ~ ", cast(null as string))") }}
    {%- endif -%}
    {{ return(hash) }}
{% endmacro %}

{% macro student_key(student_number, nullable=false) %}
    {{ return(_entity_key([student_number], nullable)) }}
{% endmacro %}

{% macro staff_key(employee_number, nullable=false) %}
    {{ return(_entity_key([employee_number], nullable)) }}
{% endmacro %}

{% macro work_assignment_key(item_id, nullable=false) %}
    {{ return(_entity_key([item_id], nullable)) }}
{% endmacro %}

{% macro region_key(business_unit_code, nullable=false) %}
    {{ return(_entity_key([business_unit_code], nullable)) }}
{% endmacro %}

{% macro survey_key(survey_id, nullable=false) %}
    {{ return(_entity_key([survey_id], nullable)) }}
{% endmacro %}

{% macro survey_question_key(question_shortname, nullable=false) %}
    {{ return(_entity_key([question_shortname], nullable)) }}
{% endmacro %}

{% macro college_key(college_code_branch, nullable=false) %}
    {{ return(_entity_key([college_code_branch], nullable)) }}
{% endmacro %}

{% macro job_candidate_key(candidate_id, nullable=false) %}
    {{ return(_entity_key([candidate_id], nullable)) }}
{% endmacro %}

{% macro staff_observation_key(observation_id, nullable=false) %}
    {{ return(_entity_key([observation_id], nullable)) }}
{% endmacro %}

{% macro staff_observation_rubric_key(rubric_id, nullable=false) %}
    {{ return(_entity_key([rubric_id], nullable)) }}
{% endmacro %}

{% macro staff_observation_goal_type_key(tag_id, nullable=false) %}
    {{ return(_entity_key([tag_id], nullable)) }}
{% endmacro %}

{% macro course_section_key(sections_dcid, source_project, nullable=false) %}
    {{ return(_entity_key([sections_dcid, source_project], nullable)) }}
{% endmacro %}

{% macro course_key(course_number, source_project, nullable=false) %}
    {{ return(_entity_key([course_number, source_project], nullable)) }}
{% endmacro %}

{% macro student_section_enrollment_key(cc_dcid, source_project, nullable=false) %}
    {{ return(_entity_key([cc_dcid, source_project], nullable)) }}
{% endmacro %}

{% macro intervention_type_key(source_project, reason, nullable=false) %}
    {{ return(_entity_key([source_project, reason], nullable)) }}
{% endmacro %}

{% macro behavioral_incident_key(incident_id, source_project, nullable=false) %}
    {{ return(_entity_key([incident_id, source_project], nullable)) }}
{% endmacro %}

{% macro family_communication_key(record_id, source_project, nullable=false) %}
    {{ return(_entity_key([record_id, source_project], nullable)) }}
{% endmacro %}

{% macro staff_observation_rubric_measurement_key(
    rubric_id, measurement_id, nullable=false
) %}
    {{ return(_entity_key([rubric_id, measurement_id], nullable)) }}
{% endmacro %}

{% macro job_posting_key(job_title, department, job_city, nullable=false) %}
    {{ return(_entity_key([job_title, department, job_city], nullable)) }}
{% endmacro %}

{% macro student_day_key(
    student_number, source_project, calendar_date, nullable=false
) %}
    {{
        return(
            _entity_key([student_number, source_project, calendar_date], nullable)
        )
    }}
{% endmacro %}

{% macro student_enrollment_key(
    student_number,
    source_project,
    academic_year,
    entry_date,
    nullable=false
) %}
    {{
        return(
            _entity_key(
                [student_number, source_project, academic_year, entry_date],
                nullable,
            )
        )
    }}
{% endmacro %}

{% macro assessment_key(
    assessment_type, module_code, assessment_id, test_type, nullable=false
) %}
    {{
        return(
            _entity_key(
                [assessment_type, module_code, assessment_id, test_type], nullable
            )
        )
    }}
{% endmacro %}

{% macro term_key(
    term_type,
    term_code,
    term_name,
    start_date,
    region,
    school_id,
    grade_band,
    nullable=false
) %}
    {{
        return(
            _entity_key(
                [
                    term_type,
                    term_code,
                    term_name,
                    start_date,
                    region,
                    school_id,
                    grade_band,
                ],
                nullable,
            )
        )
    }}
{% endmacro %}

{% macro survey_administration_key(
    survey_id,
    term_type,
    term_code,
    term_name,
    start_date,
    region,
    school_id,
    grade_band,
    nullable=false
) %}
    {{
        return(
            _entity_key(
                [
                    survey_id,
                    term_type,
                    term_code,
                    term_name,
                    start_date,
                    region,
                    school_id,
                    grade_band,
                ],
                nullable,
            )
        )
    }}
{% endmacro %}

{% macro assessment_administration_key(
    assessment_type,
    module_code,
    administered_date,
    academic_year,
    source_project,
    administration_period,
    assessment_id,
    test_type,
    nullable=false
) %}
    {{
        return(
            _entity_key(
                [
                    assessment_type,
                    module_code,
                    administered_date,
                    academic_year,
                    source_project,
                    administration_period,
                    assessment_id,
                    test_type,
                ],
                nullable,
            )
        )
    }}
{% endmacro %}
