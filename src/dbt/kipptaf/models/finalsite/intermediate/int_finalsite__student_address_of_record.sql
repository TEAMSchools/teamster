-- is_picked_address added upstream in #4680; this comment forces state:modified
-- so CI rebuilds the union and picks up the new column.
-- All four regions are unioned here, including Miami — following
-- int_finalsite__contact_id_attributes rather than
-- int_finalsite__student_contacts. The latter excludes Miami to avoid
-- double-counting contacts against the PowerSchool branch of
-- int_students__contacts; no equivalent risk exists for an address model, and
-- Focus is the Miami consumer.
with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "kippcamden_finalsite",
                        "int_finalsite__student_address_of_record",
                    ),
                    source(
                        "kippmiami_finalsite",
                        "int_finalsite__student_address_of_record",
                    ),
                    source(
                        "kippnewark_finalsite",
                        "int_finalsite__student_address_of_record",
                    ),
                    source(
                        "kipppaterson_finalsite",
                        "int_finalsite__student_address_of_record",
                    ),
                ]
            )
        }}
    )

select *, {{ extract_source_project("union_relations") }} as _dbt_source_project,
from union_relations
