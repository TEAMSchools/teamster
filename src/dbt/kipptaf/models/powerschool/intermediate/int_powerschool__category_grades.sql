/*
 * kipppaterson_powerschool is intentionally absent —
 * Paterson lacks the GradeBook plugin deployment required to
 * populate category grades. Paterson rows flow through the
 * gradebook audit scaffold but will have null
 * category_quarter_percent_grade until the plugin is deployed.
 * Tracked: https://github.com/TEAMSchools/teamster/issues/3908
 *
 * kippmiami_powerschool is intentionally absent from AY2026 forward —
 * Focus is Miami's gradebook, and int_students__category_grades supplies
 * Miami's category grades from int_focus__gradebook_grades. The frozen
 * PowerSchool archive is deliberately not surfaced here: restoring the
 * pre-cutover history is an Ops data-migration question. Ratified on #5010.
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
                ]
            )
        }}
    )

select
    ur.*,

    {{ extract_source_project("ur") }} as _dbt_source_project,

    ur.yearid + 1990 as academic_year,

from union_relations as ur
