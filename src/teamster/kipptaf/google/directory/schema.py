import json

import py_avro_schema

from teamster.google.directory.schema import (
    Group,
    Member,
    OrgUnits,
    Role,
    RoleAssignment,
    User,
)

ASSET_SCHEMA = {
    "groups": json.loads(py_avro_schema.generate(py_type=Group, namespace="group")),
    "members": json.loads(py_avro_schema.generate(py_type=Member, namespace="member")),
    "orgunits": json.loads(
        py_avro_schema.generate(py_type=OrgUnits, namespace="orgunits")
    ),
    "role_assignments": json.loads(
        py_avro_schema.generate(py_type=RoleAssignment, namespace="role_assignment")
    ),
    "roles": json.loads(py_avro_schema.generate(py_type=Role, namespace="role")),
    "users": json.loads(py_avro_schema.generate(py_type=User, namespace="user")),
}
