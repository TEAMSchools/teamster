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

    for s in schools:
        context.log.info(f"UPDATING\t{s['name']}")

        role_change = False
        schools_payload = {
            "district": schoolmint_grow.district_id,
            "observationGroups": [],
        }

        school_users = [
            u
            for u in users
            if u["school_id"] == s["_id"]
            and u["user_id"] is not None
            and u["inactive"] == 0
        ]

        # observation groups
        for grp in s["observationGroups"]:
            grp_users = [su for su in school_users if su["group_name"] == grp["name"]]
            grp_roles = {k: grp[k] for k in grp if k in ["observees", "observers"]}
            grp_update = {"_id": grp["_id"], "name": grp["name"]}

            for role, membership in grp_roles.items():
                mem_ids = [m["_id"] for m in membership]
                role_users = [gu for gu in grp_users if role in gu["group_type"]]

                for ru in role_users:
                    if ru["user_id"] not in mem_ids:
                        context.log.info(
                            f"Adding {ru['user_email']} to {grp['name']}/{role}"
                        )

                        mem_ids.append(ru["user_id"])
                        role_change = True

                grp_update[role] = mem_ids

            schools_payload["observationGroups"].append(grp_update)

        # school admins
        admin_roles = {
            "admins": "School Admin",
            "assistantAdmins": "School Assistant Admin",
        }

        for key, role_name in admin_roles.items():
            existing = s[key]
            new = [
                {"_id": su["user_id"], "name": su["user_name"]}
                for su in school_users
                if role_name in su.get("role_names", [])
            ]

            for n in new:
                match = [sa for sa in existing if sa["_id"] == n["_id"]]

                if not match:
                    context.log.info(f"Adding {n['user_email']} to {role_name}")

                    existing.append(n)
                    role_change = True

            schools_payload[key] = existing

        if role_change:
            schoolmint_grow.put("schools", s["_id"], json=schools_payload)
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
