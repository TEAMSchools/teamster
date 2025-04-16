from dagster import AssetCheckResult, OpExecutionContext, op

from teamster.libraries.schoolmint.grow.resources import SchoolMintGrowResource


@op
def schoolmint_grow_user_update_op(
    context: OpExecutionContext, schoolmint_grow: SchoolMintGrowResource, users
):
    exceptions = []

    for u in users:
        if u["surrogate_key_source"] == u["surrogate_key_destination"]:
            continue

        method = None
        request_args = ["users"]

        user_id = u["user_id"]
        inactive = u["inactive"]
        user_email = u["user_email"]

        # restore
        if inactive == 0 and u["archived_at"] is not None:
            try:
                context.log.info(f"RESTORING\t{user_email}")
                method = "PUT"
                request_args.extend([user_id, "restore"])

                schoolmint_grow.put(
                    *request_args, params={"district": schoolmint_grow.district_id}
                )

                # reset vars for update
                request_args = ["users"]
            except Exception as e:
                exception_details = {
                    "user_email": user_email,
                    "request_args": request_args,
                    "method": method,
                    "exception": e,
                }

                context.log.error(exception_details)
                exceptions.append(exception_details)

                continue

        # build user payload
        payload = {
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
            "roles": [u["role_id"]],
        }

        try:
            # create
            if inactive == 0 and user_id is None:
                context.log.info(f"CREATING\t{user_email}")
                method = "POST"

                create_response = schoolmint_grow.post(*request_args, json=payload)

                u["user_id"] = create_response["_id"]
            # update
            elif inactive == 0 and user_id is not None:
                context.log.info(f"UPDATING\t{user_email}")
                method = "PUT"
                request_args.append(user_id)

                schoolmint_grow.put(*request_args, json=payload)
            # archive
            elif inactive == 1 and user_id is not None and u["archived_at"] is None:
                context.log.info(f"ARCHIVING\t{user_email}")
                method = "DELETE"
                request_args.append(user_id)

                schoolmint_grow.delete(*request_args)
        except Exception as e:
            exception_details = {
                "user_email": user_email,
                "request_args": request_args,
                "method": method,
                "payload": payload,
                "exception": e,
            }

            context.log.error(exception_details)
            exceptions.append(exception_details)

            continue

    if exceptions:
        yield AssetCheckResult(passed=False)
        # raise Failure(metadata={"exceptions": exceptions}, allow_retries=False)

    return users


@op
def schoolmint_grow_school_update_op(
    context: OpExecutionContext, schoolmint_grow: SchoolMintGrowResource, users
):
    schools = schoolmint_grow.get("schools")["data"]

    for school in schools:
        school_id = school["_id"]

        context.log.info(f"UPDATING\t{school['name']}")

        payload: dict = {"district": schoolmint_grow.district_id}

        school_users = [
            u
            for u in users
            if u["school_id"] == school_id
            and u["user_id"] is not None
            and u["inactive"] == 0
        ]

        # observation groups
        teachers_observation_group = [
            g for g in school["observationGroups"] if g["name"] == "Teachers"
        ][0]

        observees = [
            u["user_id"] for u in school_users if "observees" in u["group_type"]
        ]
        observers = set(
            [u["user_id"] for u in school_users if "observers" in u["group_type"]]
        )
        coaches = set(
            [u["coach_id"] for u in school_users if u["coach_id"] is not None]
        )

        payload["observationGroups"] = [
            {
                "_id": teachers_observation_group["_id"],
                "name": "Teachers",
                "observees": observees,
                "observers": list(observers | coaches),
            }
        ]

        # school admins
        admin_roles = {
            "admins": "School Admin",
            "assistantAdmins": "School Assistant Admin",
        }

        for key, role_name in admin_roles.items():
            payload[key] = [
                {"_id": u["user_id"], "name": u["user_name"]}
                for u in school_users
                if role_name == u["role_name"]
            ]

        schoolmint_grow.put("schools", school_id, json=payload)
