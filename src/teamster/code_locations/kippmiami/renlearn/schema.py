import json

import py_avro_schema

from teamster.libraries.renlearn.schema import Star, StarDashboardStandard

STAR_SCHEMA = json.loads(py_avro_schema.generate(py_type=Star))

STAR_DASHBOARD_STANDARDS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StarDashboardStandard)
)

# FAST_STAR_SCHEMA = json.loads(py_avro_schema.generate(py_type=FastStar))
# STAR_SKILL_AREA_SCHEMA = json.loads(py_avro_schema.generate(py_type=StarSkillArea))
