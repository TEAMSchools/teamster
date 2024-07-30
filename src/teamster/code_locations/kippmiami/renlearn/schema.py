import json

import py_avro_schema

from teamster.libraries.renlearn.schema import (
    AcceleratedReader,
    FastStar,
    Star,
    StarDashboardStandard,
    StarSkillArea,
)

ACCELERATED_READER_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=AcceleratedReader)
)

STAR_SCHEMA = json.loads(py_avro_schema.generate(py_type=Star))

FAST_STAR_SCHEMA = json.loads(py_avro_schema.generate(py_type=FastStar))

STAR_DASHBOARD_STANDARDS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=StarDashboardStandard)
)

STAR_SKILL_AREA_SCHEMA = json.loads(py_avro_schema.generate(py_type=StarSkillArea))
