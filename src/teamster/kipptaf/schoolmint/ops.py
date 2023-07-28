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
    context.log.info("Processing user creation/updates...")
    for u in users:
        user_id = u["user_id"]

        # restore
        if u["inactive"] == 0 and u["inactive_ws"] == 1:
            try:
                schoolmint_grow.put("users", user_id, "restore")

                context.log.info(
                    f"{u['user_name']} ({u['user_internal_id']}) - RESTORED"
                )
            except Exception:
                continue

        # build user payload
        user_payload = {
            "district": schoolmint_grow.district_id,
            "name": u["user_name"],
            "email": u["user_email"],
            "internalId": u["user_internal_id"],
            "inactive": u["inactive"],
            "defaultInformation": {
                "school": u["school_id"],
                "gradeLevel": u["grade_id"],
                "course": u["course_id"],
            },
            "coach": u["coach_id"],
            "roles": json.loads(u["role_id"]),
        }

        # create or update
        if user_id is None:
            try:
                create_resp = schoolmint_grow.post("users", json=user_payload)

                user_id = create_resp["_id"]

                u["user_id"] = user_id

                context.log.info(
                    f"{u['user_name']} ({u['user_internal_id']}) - CREATED"
                )
            except Exception:
                continue
        else:
            try:
                schoolmint_grow.put("users", user_id, json=user_payload)

                context.log.info(
                    f"{u['user_name']} ({u['user_internal_id']}) - UPDATED"
                )
            except Exception:
                continue

        # archive
        if u["inactive"] == 1 and u["archived_at"] is None:
            try:
                schoolmint_grow.delete("users", user_id)

                context.log.info(
                    f"{u['user_name']} ({u['user_internal_id']}) - ARCHIVED"
                )
            finally:
                continue

    context.log.info("Processing school role changes...")
    schools = schoolmint_grow.get("schools")["data"]
    for s in schools:
        context.log.info(f"{s['name']}")

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
                            f"Adding {ru['user_name']} to {grp['name']}/{role}"
                        )
                        mem_ids.append(ru["user_id"])
                        role_change = True

                grp_update[role] = mem_ids

            schools_payload["observationGroups"].append(grp_update)

        # school admins
        school_admins = s["admins"]
        new_school_admins = [
            {"_id": su["user_id"], "name": su["user_name"]}
            for su in school_users
            if "School Admin" in su.get("role_names", [])
        ]

        for nsa in new_school_admins:
            sa_match = [sa for sa in school_admins if sa["_id"] == nsa["_id"]]
            if not sa_match:
                context.log.info(f"Adding {nsa['name']} to School Admins")
                school_admins.append(nsa)
                role_change = True

        schools_payload["admins"] = school_admins

        # school assistant admins
        asst_admins = s["assistantAdmins"]
        new_asst_admins = [
            {"_id": su["user_id"], "name": su["user_name"]}
            for su in school_users
            if "School Assistant Admin" in su.get("role_names", [])
        ]
        for naa in new_asst_admins:
            aa_match = [aa for aa in asst_admins if aa["_id"] == naa["_id"]]
            if not aa_match:
                context.log.info(f"Adding {naa['name']} to School Assistant Admins")
                asst_admins.append(naa)
                role_change = True

        schools_payload["assistantAdmins"] = asst_admins

        if role_change:
            schoolmint_grow.put("schools", s["_id"], json=schools_payload)
        else:
            context.log.info("No school role changes")
