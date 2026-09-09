import pathlib
from collections.abc import Callable, Iterator
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

# Grow school payload key -> role name. Also the roles that observe a school's
# Teachers fallback group: a coach reaches their own reports through their own
# group, so listing them on the fallback too duplicates it in their picker.
ADMIN_ROLES = {"admins": "School Admin", "assistantAdmins": "School Assistant Admin"}


def _match_observation_group(
    name: str,
    match_key: str | None,
    existing_by_id: dict[str, str],
    claimed: set[str],
) -> str | None:
    """Unclaimed existing group id for this wanted group, or None.

    Exact name first, then a suffix match on ``match_key`` (the parenthesised
    employee number, which survives a coach rename). None means no fallback.
    """
    unclaimed = [(i, n) for i, n in existing_by_id.items() if i not in claimed]

    return next((i for i, n in unclaimed if n == name), None) or (
        next((i for i, n in unclaimed if n.endswith(match_key)), None)
        if match_key is not None
        else None
    )


def _can_anchor_group(user: dict[str, Any]) -> bool:
    """Active, writable, and observer-capable: can be a group's sole observer."""
    return (
        user["inactive"] == 0
        and not user["readonly"]
        and "observers" in user["group_type"]
    )


def _observes_fallback(user: dict[str, Any]) -> bool:
    """A school admin or assistant admin who can anchor a group."""
    return _can_anchor_group(user) and not set(ADMIN_ROLES.values()).isdisjoint(
        user["role_names"]
    )


def _at_school(
    school_users: list[dict[str, Any]],
    users_by_grow_id: dict[str, dict[str, Any]],
    pred: Callable[[dict[str, Any]], bool],
) -> list[str]:
    """Home-school users matching pred, plus managers of reports here who match.

    A leader covering a satellite campus reaches its users through their
    reports, not their own school_id.
    """
    managers = (users_by_grow_id.get(u["coach_id"]) for u in school_users)

    return sorted(
        {u["user_id"] for u in school_users if pred(u)}
        | {m["user_id"] for m in managers if m is not None and pred(m)}
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

    users = query_job.to_arrow().to_pylist()
    context.log.info(f"Retrieved {len(users)} rows")

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

        school_observers = _at_school(
            school_users, users_by_grow_id, _observes_fallback
        )

        # Route every observee to their coach's group, or to the fallback.
        by_coach: dict[str, list[str]] = {}
        uncoached: list[str] = []

        for u in school_users:
            if "observees" not in u["group_type"]:
                continue

            coach_id = u["coach_id"]
            coach = users_by_grow_id.get(coach_id) if coach_id is not None else None

            # A coach absent from the extract, or present but unable to
            # actually observe (revoked, inactive, or readonly), cannot own a
            # group, so their reports fall back rather than landing in a
            # group nobody can act in.
            if coach_id is None or coach is None or not _can_anchor_group(coach):
                uncoached.append(u["user_id"])
            else:
                by_coach.setdefault(coach_id, []).append(u["user_id"])

        wanted: dict[str, dict[str, Any]] = {
            # Teachers survives as the fallback for observees with no coach. An
            # empty fallback drops its observers too, or it still shows up in
            # each of their pickers holding nobody.
            "Teachers": {
                "observees": uncoached,
                "observers": school_observers if uncoached else [],
            }
        }
        # Parenthesised employee number, so a display-name change relabels
        # the group without breaking its identity. None (e.g. Teachers) gets
        # no fallback match. Kept separate from `wanted` so it never leaks
        # into the payload sent to the Grow API.
        match_keys: dict[str, str | None] = {"Teachers": None}

        for coach_id, observee_ids in by_coach.items():
            coach = users_by_grow_id[coach_id]
            name = f"{coach['user_name']} ({coach['user_internal_id']})"

            wanted[name] = {
                "observees": observee_ids,
                "observers": [coach_id],
            }
            match_keys[name] = f"({coach['user_internal_id']})"

        observation_groups = []
        claimed: set[str] = set()

        # Match on the explicit match key so a renamed coach keeps their
        # group's _id. Skips already-claimed ids so two wanted groups can
        # never resolve to the same existing group.
        for name, members in wanted.items():
            group: dict[str, Any] = {"name": name, **members}
            group_id = _match_observation_group(
                name, match_keys[name], existing_by_id, claimed
            )

            if group_id is not None:
                group["_id"] = group_id
                claimed.add(group_id)

            observation_groups.append(group)

        # The school PUT REPLACES this array, so a group left out is deleted.
        # Emit every surviving group emptied rather than dropping it, so no
        # observation history is ever orphaned by a coach moving on.
        observation_groups += [
            {"_id": i, "name": n, "observees": [], "observers": []}
            for i, n in existing_by_id.items()
            if i not in claimed
        ]

        payload["observationGroups"] = observation_groups

        for key, role_name in ADMIN_ROLES.items():
            payload[key] = [
                {"_id": i, "name": users_by_grow_id[i]["user_name"]}
                for i in _at_school(
                    school_users,
                    users_by_grow_id,
                    lambda u, r=role_name: u["inactive"] == 0 and r in u["role_names"],
                )
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


grow_multi_partitions_assets = [assignments, observations]

assets = [
    *grow_multi_partitions_assets,
    *grow_static_partition_assets,
    grow_user_sync,
]
