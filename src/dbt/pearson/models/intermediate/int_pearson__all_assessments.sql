{#- ref() inside the loop is captured at parse time, so only the relations a
    district names in the var enter its graph. -#}
{% set relations = [] %}
{% for m in var("pearson_state_assessment_relations") %}
    {% do relations.append(ref(m)) %}
{% endfor %}

with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=relations,
                include=[
                    "academic_year",
                    "administration_period",
                    "americanindianoralaskanative",
                    "asian",
                    "assessment_name",
                    "assessment_version",
                    "assessmentgrade",
                    "assessmentyear",
                    "blackorafricanamerican",
                    "discipline",
                    "englishlearnerel",
                    "firstname",
                    "hispanicorlatinoethnicity",
                    "is_bl_fb",
                    "is_proficient",
                    "lastorsurname",
                    "localstudentidentifier",
                    "module_code",
                    "nativehawaiianorotherpacificislander",
                    "period",
                    "statestudentidentifier",
                    "studenttestuuid",
                    "studentwithdisabilities",
                    "subject",
                    "subject_area",
                    "test_date",
                    "test_grade",
                    "testcode",
                    "testperformancelevel",
                    "testperformancelevel_text",
                    "testscalescore",
                    "testscorecomplete",
                    "twoormoreraces",
                    "white",
                ],
            )
        }}
    ),

    aligned as (
        -- trunk-ignore(sqlfluff/AM04): union_relations resolves columns at run time
        select
            *,

            'Actual' as results_type,
            'KTAF NJ' as district_state,

            module_code as aligned_test_code,
            subject_area as aligned_subject,
            administration_period as `admin`,

            coalesce(studentwithdisabilities in ('504', 'B'), false) as is_504,

            if(englishlearnerel = 'Y', true, false) as lep_status,

            if(
                studentwithdisabilities in ('IEP', 'B'), 'Has IEP', 'No IEP'
            ) as iep_status,

            if(is_proficient, 1, 0) as is_proficient_int,

            case
                when twoormoreraces = 'Y'
                then 'T'
                when hispanicorlatinoethnicity = 'Y'
                then 'H'
                when americanindianoralaskanative = 'Y'
                then 'I'
                when asian = 'Y'
                then 'A'
                when blackorafricanamerican = 'Y'
                then 'B'
                when nativehawaiianorotherpacificislander = 'Y'
                then 'P'
                when white = 'Y'
                then 'W'
            end as race_ethnicity,

            case
                when `subject` like 'English Language Arts%'
                then 'Text Study'
                when `subject` in ('Algebra I', 'Algebra II', 'Geometry')
                then 'Mathematics'
                else `subject`
            end as illuminate_subject,

            case
                when assessment_name = 'NJSLA' and testperformancelevel <= 2
                then 'Below/Far Below'
                when assessment_name = 'NJSLA' and testperformancelevel = 3
                then 'Approaching'
                when assessment_name = 'NJSLA' and testperformancelevel >= 4
                then 'At/Above'
            end as njsla_aggregated_proficiency,

            case
                when assessment_name = 'NJSLA' and testperformancelevel <= 2
                then 'Not Proficient (1-2)'
                when assessment_name = 'NJSLA' and testperformancelevel = 3
                then 'Bubble (3)'
                when assessment_name = 'NJSLA' and testperformancelevel >= 4
                then 'Proficient (4-5)'
            end as njsla_performance_band_group_label,

            case
                when testperformancelevel_text = 'Did Not Yet Meet Expectations'
                then 'Lvl 1'
                when testperformancelevel_text = 'Partially Met Expectations'
                then 'Lvl 2'
                when
                    testperformancelevel_text
                    in ('Approached Expectations', 'Not Yet Graduation Ready')
                then 'Lvl 3'
                when
                    testperformancelevel_text
                    in ('Met Expectations', 'Graduation Ready')
                then 'Lvl 4'
                when testperformancelevel_text = 'Exceeded Expectations'
                then 'Lvl 5'
            end as aligned_performance_band_group,

            case
                when assessment_name = 'NJGPA'
                then 0
                when assessment_name = 'NJSLA Science' and testperformancelevel = 2
                then 1
                when discipline in ('ELA', 'Math') and testperformancelevel = 3
                then 1
                else 0
            end as is_approaching_int,

            case
                when assessment_name = 'NJGPA' and testperformancelevel = 1
                then 1
                when assessment_name = 'NJSLA Science' and testperformancelevel < 2
                then 1
                when discipline in ('ELA', 'Math') and testperformancelevel < 3
                then 1
                else 0
            end as is_below_int,

            case
                assessment_name
                when 'PARCC'
                then 'state_nj_parcc'
                when 'NJSLA'
                then 'state_nj_njsla'
                when 'NJSLA Science'
                then 'state_nj_njsla_science'
                when 'NJGPA'
                then 'state_nj_njgpa'
                else 'state_nj_unknown'
            end as assessment_type,

        from union_relations
    )

select
    *,

    case
        race_ethnicity
        when 'B'
        then 'African American'
        when 'A'
        then 'Asian'
        when 'I'
        then 'American Indian'
        when 'H'
        then 'Hispanic'
        when 'P'
        then 'Native Hawaiian'
        when 'T'
        then 'Other'
        when 'W'
        then 'White'
        else 'Blank'
    end as aligned_aggregate_ethnicity,

    if(lep_status, 'ML', 'Not ML') as aligned_ml_status,

    if(
        iep_status = 'Has IEP',
        'Students With Disabilities',
        'Students Without Disabilities'
    ) as aligned_iep_status,

from aligned
