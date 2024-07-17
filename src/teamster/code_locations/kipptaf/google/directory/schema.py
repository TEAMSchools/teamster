import json

import py_avro_schema

from teamster.libraries.google.directory.schema import (
    Group,
    Member,
    OrgUnits,
    Role,
    RoleAssignment,
    User,
)

GROUPS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Group, namespace="group"))

MEMBERS_SCHEMA = json.loads(py_avro_schema.generate(py_type=Member, namespace="member"))

ORGUNITS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=OrgUnits, namespace="orgunits")
)

ROLE_ASSIGNMENTS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=RoleAssignment, namespace="role_assignment")
)

ROLES_SCHEMA = json.loads(py_avro_schema.generate(py_type=Role, namespace="role"))

USERS_SCHEMA = json.loads(py_avro_schema.generate(py_type=User, namespace="user"))
