with
    union_relations as (
        {{
            dbt_utils.union_relations(
                relations=[
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_assignmentpresets",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_courses",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_grades",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_observationtypes",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_tags",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_eventtag1",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_goaltypes",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_measurementgroups",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_meetingtypes",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_rubrictag1",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_schooltag1",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_usertag1",
                    ),
                    source(
                        "schoolmint_grow",
                        "src_schoolmint_grow__generic_tags_usertypes",
                    ),
                ],
                exclude=["additionalFields"],
            )
        }}
    )

select
    _id as tag_id,
    __v,
    abbreviation,
    archivedat as archived_at,
    color,
    created,
    creator,
    district,
    lastmodified as last_modified,
    `name`,
    `order`,
    parent,
    parents,
    `rows`,
    showondash as show_on_dash,
    tags,
    `type`,
    `url`,
    regexp_extract(
        _dbt_source_relation, r'src_schoolmint_grow__generic_tags_(\w+)'
    ) as tag_type,
from union_relations
where _dagster_partition_key = 'f'
