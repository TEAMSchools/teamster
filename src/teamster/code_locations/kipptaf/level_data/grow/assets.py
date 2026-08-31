import pathlib
from collections.abc import Iterator
from typing import Any

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetCheckSpec,
    AssetExecutionContext,
    AssetKey,
    DailyPartitionsDefinition,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
    config_from_files,
)
from dagster_gcp import BigQueryResource

from teamster.code_locations.kipptaf import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kipptaf.level_data.grow.schema import (
    ASSET_SCHEMA,
    ASSIGNMENT_SCHEMA,
    OBSERVATION_SCHEMA,
)
from teamster.libraries.level_data.grow.assets import build_grow_asset
from teamster.libraries.level_data.grow.resources import (
    GrowAPIError,
    GrowIncompleteResponseError,
    GrowResource,
)

STATIC_PARTITONS_DEF = StaticPartitionsDefinition(["t", "f"])
MULTI_PARTITIONS_DEF = MultiPartitionsDefinition(
    {
        "archived": STATIC_PARTITONS_DEF,
        "last_modified": DailyPartitionsDefinition(
            start_date="2023-07-31", timezone=str(LOCAL_TIMEZONE), end_offset=1
        ),
    }
)

key_prefix = [CODE_LOCATION, "schoolmint", "grow"]
config_dir = pathlib.Path(__file__).parent / "config"

grow_static_partition_assets = [
    build_grow_asset(
        asset_key=[*key_prefix, e["asset_name"].replace("-", "_").replace("/", "_")],
        endpoint=e["asset_name"],
        partitions_def=STATIC_PARTITONS_DEF,
        schema=ASSET_SCHEMA[e["asset_name"]],
        op_tags=e.get("op_tags"),
    )
    for e in config_from_files([f"{config_dir}/static-partition-assets.yaml"])[
        "endpoints"
    ]
]

assignments = build_grow_asset(
    asset_key=[*key_prefix, "assignments"],
    endpoint="assignments",
    partitions_def=MULTI_PARTITIONS_DEF,
    schema=ASSIGNMENT_SCHEMA,
)

observations = build_grow_asset(
    asset_key=[*key_prefix, "observations"],
    endpoint="observations",
    partitions_def=MULTI_PARTITIONS_DEF,
    schema=OBSERVATION_SCHEMA,
)


@asset(
    key=[*key_prefix, "user_sync"],
    deps=[AssetKey(["kipptaf", "extracts", "rpt_schoolmint_grow__users"])],
    check_specs=[
        AssetCheckSpec(name="zero_api_errors", asset=[*key_prefix, "user_sync"])
    ],
    group_name="grow",
    kinds={"python", "task"},
)
def grow_user_sync(
    context: AssetExecutionContext, db_bigquery: BigQueryResource, grow: GrowResource
) -> Iterator[Output | AssetCheckResult]:
    # query data
    query = "select * from kipptaf_extracts.rpt_schoolmint_grow__users"
    errors: list[dict[str, Any]] = []

    context.log.info(query)
    with db_bigquery.get_client() as bq:
        query_job = bq.query(query=query, project=db_bigquery.project)

    arrow = query_job.to_arrow()

    context.log.info(f"Retrieved {arrow.num_rows} rows")
    users = arrow.to_pylist()

    # create/update users
    for u in users:
        if u["surrogate_key_source"] == u["surrogate_key_destination"]:
            continue

        method = None

        user_id = u["user_id"]
        inactive = u["inactive"]
        user_email = u["user_email"]

        # restore
        if inactive == 0 and u["archived_at"] is not None:
            request_args = ["users", user_id, "restore"]

            try:
                context.log.info(f"RESTORING\t{user_email}")
                grow.put(*request_args, params={"district": grow.district_id})
            except (GrowAPIError, GrowIncompleteResponseError) as e:
                errors.append(
                    {
                        "method": "PUT",
                        "request_args": request_args,
                        "exception": e.args[0],
                    }
                )

                continue

        # build user payload
        payload: dict[str, Any] = {
            "district": grow.district_id,
            "name": u["user_name"],
            "email": user_email,
            "internalId": u["user_internal_id"],
            "inactive": inactive,
            "defaultInformation": {
                "school": u["school_id"],
                "gradeLevel": u["grade_id"],
                "course": u["course_id"],
            },
            "coach": u["coach_id"],
            "roles": list(u["role_ids"]),
            "regionalAdminSchools": list(u["regional_admin_school_ids"]),
            "readonly": bool(u["readonly"]),
        }

        # reset request_args after the restore branch may have mutated it
        request_args = ["users"]

        try:
            # create
            if inactive == 0 and user_id is None:
                context.log.info(f"CREATING\t{user_email}")
                method = "POST"

                create_response = grow.post(*request_args, json=payload)

                u["user_id"] = create_response["_id"]
            # update
            elif inactive == 0 and user_id is not None:
                context.log.info(f"UPDATING\t{user_email}")
                method = "PUT"
                request_args.append(user_id)

                grow.put(*request_args, json=payload)
            # archive
            elif inactive == 1 and user_id is not None and u["archived_at"] is None:
                context.log.info(f"ARCHIVING\t{user_email}")
                method = "DELETE"
                request_args.append(user_id)

                grow.delete(*request_args)
        except (GrowAPIError, GrowIncompleteResponseError) as e:
            errors.append(
                {
                    "method": method,
                    "request_args": request_args,
                    "payload": payload,
                    "exception": e.args[0],
                }
            )

            continue

    # update school observation groups
    admin_roles = {
        "admins": "School Admin",
        "assistantAdmins": "School Assistant Admin",
    }

    schools = grow.get("schools")["data"]

    # A coach's home school often differs from their reports', so resolve
    # coaches from the full user set rather than from school_users.
    users_by_grow_id = {u["user_id"]: u for u in users if u["user_id"] is not None}

    for school in schools:
        school_id = school["_id"]

        context.log.info(f"UPDATING\t{school['name']}")

        payload: dict[str, Any] = {"district": grow.district_id}

        school_users = [
            u
            for u in users
            if u["school_id"] == school_id
            and u["user_id"] is not None
            and u["inactive"] == 0
        ]

        # observation groups: one per coach, so a coach who is also a teacher
        # sees only their own reports rather than every teacher at the school.
        # Keyed by _id: two groups can share a name, and losing one here would
        # drop it from the payload, which deletes it.
        existing_by_id: dict[str, str] = {
            g["_id"]: g["name"] for g in school["observationGroups"]
        }

        school_observers = sorted(
            {u["user_id"] for u in school_users if "observers" in u["group_type"]}
        )

        # Route every observee to their coach's group, or to the fallback.
        by_coach: dict[str, list[str]] = {}
        uncoached: list[str] = []

        for u in school_users:
            if "observees" not in u["group_type"]:
                continue

            coach_id = u["coach_id"]

            # A coach absent from the extract cannot own a group, so their
            # reports fall back rather than disappearing.
            if coach_id is None or coach_id not in users_by_grow_id:
                uncoached.append(u["user_id"])
            else:
                by_coach.setdefault(coach_id, []).append(u["user_id"])

        def coach_group_name(coach: dict[str, Any]) -> str:
            # The employee-number prefix is the match key, so a display-name
            # change relabels the group without breaking its identity.
            return f"Coach {coach['user_internal_id']} - {coach['user_name']}"

        wanted: dict[str, dict[str, Any]] = {
            # Teachers survives as the fallback for observees with no coach.
            "Teachers": {"observees": uncoached, "observers": school_observers}
        }

        for coach_id, observee_ids in by_coach.items():
            coach = users_by_grow_id[coach_id]

            wanted[coach_group_name(coach)] = {
                "observees": observee_ids,
                "observers": [coach_id],
            }

        observation_groups = []
        claimed: set[str] = set()

        # Match by the "Coach <employee_number>" prefix so a renamed coach
        # keeps their group's _id. Skips already-claimed ids so two wanted
        # groups can never resolve to the same existing group.
        def match_existing(name: str) -> str | None:
            for group_id, group_name in existing_by_id.items():
                if group_id in claimed:
                    continue

                if group_name == name:
                    return group_id

            prefix = name.split(" - ")[0] + " - "

            return next(
                (
                    group_id
                    for group_id, group_name in existing_by_id.items()
                    if group_id not in claimed and group_name.startswith(prefix)
                ),
                None,
            )

        for name, members in wanted.items():
            group: dict[str, Any] = {"name": name, **members}
            group_id = match_existing(name)

            if group_id is not None:
                group["_id"] = group_id
                claimed.add(group_id)

            observation_groups.append(group)

        # The school PUT REPLACES this array, so a group left out is deleted.
        # Emit every surviving group emptied rather than dropping it, so no
        # observation history is ever orphaned by a coach moving on.
        for group_id, group_name in existing_by_id.items():
            if group_id in claimed:
                continue

            observation_groups.append(
                {
                    "_id": group_id,
                    "name": group_name,
                    "observees": [],
                    "observers": [],
                }
            )

        payload["observationGroups"] = observation_groups

        for key, role_name in admin_roles.items():
            payload[key] = [
                {"_id": u["user_id"], "name": u["user_name"]}
                for u in school_users
                if role_name in u["role_names"]
            ]

        try:
            grow.put("schools", school_id, json=payload)
        except (GrowAPIError, GrowIncompleteResponseError) as e:
            errors.append(
                {
                    "method": "PUT",
                    "request_args": ["schools", school_id],
                    "payload": payload,
                    "exception": e.args[0],
                }
            )

            continue

    yield Output(value=None)
    yield AssetCheckResult(
        passed=(len(errors) == 0),
        asset_key=context.asset_key,
        check_name="zero_api_errors",
        metadata={"errors": errors},
        severity=AssetCheckSeverity.WARN,
    )


grow_multi_partitions_assets = [
    assignments,
    observations,
]

assets = [
    *grow_multi_partitions_assets,
    *grow_static_partition_assets,
    grow_user_sync,
]
