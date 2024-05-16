import json

import py_avro_schema

from teamster.ldap.schema import Group, UserPerson

ASSET_SCHEMA = {
    "user_person": json.loads(
        py_avro_schema.generate(
            py_type=UserPerson,
            namespace="user_person",
            options=py_avro_schema.Option.USE_FIELD_ALIAS,
        )
    ),
    "group": json.loads(py_avro_schema.generate(py_type=Group, namespace="group")),
}
