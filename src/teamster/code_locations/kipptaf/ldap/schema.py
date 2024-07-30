import json

import py_avro_schema

from teamster.libraries.ldap.schema import Group, UserPerson

USER_PERSON_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=UserPerson,
        namespace="user_person",
        options=py_avro_schema.Option.USE_FIELD_ALIAS,
    )
)

GROUP_SCHEMA = json.loads(py_avro_schema.generate(py_type=Group, namespace="group"))
