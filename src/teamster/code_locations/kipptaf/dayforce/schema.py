import json

import py_avro_schema

from teamster.libraries.dayforce.schema import (
    Employee,
    EmployeeManager,
    EmployeeStatus,
    EmployeeWorkAssignment,
)

ASSET_SCHEMA = {
    "employees": json.loads(
        py_avro_schema.generate(py_type=Employee, namespace="employee")
    ),
    "employee_manager": json.loads(
        py_avro_schema.generate(py_type=EmployeeManager, namespace="employee_manager")
    ),
    "employee_status": json.loads(
        py_avro_schema.generate(py_type=EmployeeStatus, namespace="employee_status")
    ),
    "employee_work_assignment": json.loads(
        py_avro_schema.generate(
            py_type=EmployeeWorkAssignment, namespace="employee_work_assignment"
        )
    ),
}
