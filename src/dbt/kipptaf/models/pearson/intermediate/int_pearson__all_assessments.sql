with
    union_relations as (
        {{
            dbt_utils.union_relations(
                source_column_name="_dbt_source_relation_2",
                relations=[
                    source("kippnewark_pearson", "int_pearson__all_assessments"),
                    source("kippcamden_pearson", "int_pearson__all_assessments"),
                    source("kipppaterson_pearson", "int_pearson__all_assessments"),
                    source("kippnewark_cambium", "stg_cambium__njgpa"),
                    source("kippcamden_cambium", "stg_cambium__njgpa"),
                ],
                include=[
                    "_dbt_source_relation",
                    "academic_year",
                    "admin",
                    "administration_period",
                    "aligned_aggregate_ethnicity",
                    "aligned_iep_status",
                    "aligned_ml_status",
                    "aligned_performance_band_group",
                    "aligned_subject",
                    "aligned_test_code",
                    "americanindianoralaskanative",
                    "asian",
                    "assessment_name",
                    "assessment_type",
                    "assessment_version",
                    "assessmentgrade",
                    "assessmentyear",
                    "blackorafricanamerican",
                    "discipline",
                    "district_state",
                    "englishlearnerel",
                    "firstname",
                    "hispanicorlatinoethnicity",
                    "iep_status",
                    "illuminate_subject",
                    "is_504",
                    "is_approaching_int",
                    "is_below_int",
                    "is_bl_fb",
                    "is_proficient",
                    "is_proficient_int",
                    "lastorsurname",
                    "lep_status",
                    "localstudentidentifier",
                    "module_code",
                    "nativehawaiianorotherpacificislander",
                    "njsla_aggregated_proficiency",
                    "njsla_performance_band_group_label",
                    "period",
                    "race_ethnicity",
                    "results_type",
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

    sourced as (
        select
            * except (_dbt_source_relation, _dbt_source_relation_2),

            /* The Pearson relations arrive with the staging relation they came
               from; the Cambium relations have no inner union, so fall back to
               this union's own source column. Either way the value names the
               district dataset. */
            coalesce(
                _dbt_source_relation, _dbt_source_relation_2
            ) as _dbt_source_relation,
        from union_relations
    )

/* Every per-row derivation lives upstream: int_pearson__all_assessments in the
   pearson package and stg_cambium__njgpa in the cambium package. Only the two
   cross-source repairs remain here. */
select
    s.* replace (
        cast(s.statestudentidentifier as string) as statestudentidentifier,
        coalesce(x.student_number, s.localstudentidentifier) as localstudentidentifier
    ),

    {{ extract_source_project("s") }} as _dbt_source_project,
from sourced as s
left join
    {{ ref("stg_google_sheets__pearson__student_crosswalk") }} as x
    on s.studenttestuuid = x.student_test_uuid
