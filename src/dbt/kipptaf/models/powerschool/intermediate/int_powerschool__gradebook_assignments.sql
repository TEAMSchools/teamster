/*
 * kipppaterson_powerschool is intentionally absent —
 * Paterson lacks the GradeBook plugin deployment required to
 * populate assignment data. Paterson teacher rows flow through
 * the gradebook audit scaffold but will have zero assignment
 * counts and null max score flags until the plugin is deployed.
 * Tracked: https://github.com/TEAMSchools/teamster/issues/3908
 */
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippnewark_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                    source(
                        "kippcamden_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                    source(
                        "kippmiami_powerschool",
                        "int_powerschool__gradebook_assignments",
                    ),
                ]
            )
        }}
    )

-- trunk-ignore(sqlfluff/AM04)
select *, {{ extract_code_location("union_relations") }} as _dbt_source_project,

from union_relations
