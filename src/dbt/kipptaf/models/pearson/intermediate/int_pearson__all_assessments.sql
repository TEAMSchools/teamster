with
    union_relations as (
        {{
            dbt_utils.union_relations(
                source_column_name="_dbt_source_relation_2",
                relations=[
                    ref("stg_pearson__parcc"),
                    ref("stg_pearson__njsla"),
                    ref("stg_pearson__njsla_science"),
                    ref("stg_pearson__njgpa"),
                    ref("stg_cambium__njgpa"),
                ],
                include=[
                    "_dbt_source_relation",
                    "_dbt_source_project",
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
    )

/* Every per-row derivation lives upstream: pearson_aligned_columns() in the
   pearson package for the Pearson relations, and stg_cambium__njgpa for the
   adaptive NJGPA rows. Only the two cross-source repairs remain here. */
select
    u.* except (_dbt_source_relation_2) replace (
        cast(u.statestudentidentifier as string) as statestudentidentifier,
        coalesce(x.student_number, u.localstudentidentifier) as localstudentidentifier
    ),
from union_relations as u
left join
    {{ ref("stg_google_sheets__pearson__student_crosswalk") }} as x
    on u.studenttestuuid = x.student_test_uuid
