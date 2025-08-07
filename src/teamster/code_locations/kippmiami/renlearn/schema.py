import json

import py_avro_schema

from teamster.libraries.renlearn.schema import (
    FastStar,
    Star,
    StarDashboardStandard,
    StarSkillArea,
)

STAR_SCHEMA = json.loads(py_avro_schema.generate(py_type=Star))

FAST_STAR_SCHEMA = json.loads(py_avro_schema.generate(py_type=FastStar))

STAR_DASHBOARD_STANDARDS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StarDashboardStandard)
)

STAR_SKILL_AREA_SCHEMA = json.loads(py_avro_schema.generate(py_type=StarSkillArea))
