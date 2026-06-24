/*
 * kipppaterson_powerschool is intentionally absent —
 * Paterson lacks the GradeBook plugin deployment required to
 * populate category grades. Paterson rows flow through the
 * gradebook audit scaffold but will have null
 * category_quarter_percent_grade until the plugin is deployed.
 * Tracked: https://github.com/TEAMSchools/teamster/issues/3908
 */
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool", "int_powerschool__category_grades"
                    ),
                    source(
                        "kippcamden_powerschool", "int_powerschool__category_grades"
                    ),
                    source(
                        "kippmiami_powerschool", "int_powerschool__category_grades"
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select
    *,

    {{ extract_code_location("union_relations") }} as _dbt_source_project,
    yearid + 1990 as academic_year,

from union_relations
