import json

from dagster import OpExecutionContext, op
from dagster_gcp import BigQueryResource
from google.cloud import bigquery
from pandas import DataFrame

from teamster.core.schoolmint.grow.resources import SchoolMintGrowResource

from .. import CODE_LOCATION


@op
def schoolmint_grow_get_user_update_data_op(
    context: OpExecutionContext, db_bigquery: BigQueryResource
):
    # query extract view
    dataset_ref = bigquery.DatasetReference(
        project=db_bigquery.project, dataset_id=f"{CODE_LOCATION}_extracts"
    )

    with db_bigquery.get_client() as bq:
        table = bq.get_table(dataset_ref.table(table_id="rpt_schoolmint_grow__users"))

        rows = bq.list_rows(table=table)

    df: DataFrame = rows.to_dataframe()

    return df.to_dict(orient="records")


@op
def schoolmint_grow_user_update_op(
    context: OpExecutionContext, schoolmint_grow: SchoolMintGrowResource, users
):
    for u in users:
        user_id = u["user_id"]
        inactive = u["inactive"]
        user_email = u["user_email"]

        try:
            # restore
            if inactive == 0 and u["inactive_ws"] == 1:
                context.log.info(f"RESTORING\t{user_email}")
                schoolmint_grow.put("users", user_id, "restore")
        except Exception:
            continue

        # build user payload
        user_payload = {
            "district": schoolmint_grow.district_id,
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
            "roles": json.loads(u["role_id"]),
        }

        try:
            # create
            if inactive == 0 and user_id is None:
                context.log.info(f"CREATING\t{user_email}")
                create_resp = schoolmint_grow.post("users", json=user_payload)
                user_id = create_resp["_id"]
                u["user_id"] = user_id
            # update
            elif inactive == 0:
                context.log.info(f"UPDATING\t{user_email}")
                schoolmint_grow.put("users", user_id, json=user_payload)
        except Exception:
            continue

        try:
            # archive
            if inactive == 1 and u["archived_at"] is None:
                context.log.info(f"ARCHIVING\t{user_email}")
                schoolmint_grow.delete("users", user_id)
        except Exception:
            continue

    return users


@op
def schoolmint_grow_school_update_op(
    context: OpExecutionContext, schoolmint_grow: SchoolMintGrowResource, users
):
    schools = schoolmint_grow.get("schools")["data"]

    for school in schools:
        school_id = school["_id"]

        context.log.info(f"UPDATING\t{school['name']}")

        role_change = False
        payload = {"district": schoolmint_grow.district_id, "observationGroups": []}

        school_users = [
            u
            for u in users
            if u["school_id"] == school_id
            and u["user_id"] is not None
            and u["inactive"] == 0
        ]

        # observation groups
        for group in school["observationGroups"]:
            group_name = group["name"]

            group_update = {"_id": group["_id"], "name": group_name}

            group_users = [u for u in school_users if u["group_name"] == group_name]
            group_roles = {
                k: group[k] for k in group if k in ["observees", "observers"]
            }

            for role, membership in group_roles.items():
                mem_ids = [m["_id"] for m in membership]
                role_users = [u for u in group_users if role in u["group_type"]]

                for user in role_users:
                    user_id = user["user_id"]

                    if user_id not in mem_ids:
                        context.log.info(
                            f"Adding {user['user_email']} to {group_name}/{role}"
                        )

                        mem_ids.append(user_id)
                        role_change = True

                group_update[role] = mem_ids

            payload["observationGroups"].append(group_update)

        # school admins
        admin_roles = {
            "admins": "School Admin",
            "assistantAdmins": "School Assistant Admin",
        }

        for key, role_name in admin_roles.items():
            existing_users = school[key]
            new_users = [
                u for u in school_users if role_name in u.get("role_names", [])
            ]

            for user in new_users:
                match = [u for u in existing_users if u["_id"] == user["_id"]]

                if not match:
                    context.log.info(f"Adding {user['user_email']} to {role_name}")

                    role_change = True
                    existing_users.append(
                        {"_id": user["user_id"], "name": user["user_name"]}
                    )

            payload[key] = existing_users

        if role_change:
            schoolmint_grow.put("schools", school_id, json=payload)
        else:
            context.log.info("No school role changes")


@op
def schoolmint_grow_user_delete_op(
    context: OpExecutionContext, schoolmint_grow: SchoolMintGrowResource, users
):
    for u in users:
        user_id = u["user_id"]

        try:
            context.log.info(f"ARCHIVING\t{user_id}")
            schoolmint_grow.delete("users", user_id)
        except Exception:
            continue
