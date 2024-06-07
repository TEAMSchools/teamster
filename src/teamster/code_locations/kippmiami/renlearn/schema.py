import json

import py_avro_schema

from teamster.libraries.renlearn.schema import (
    AcceleratedReader,
    FastStar,
    Star,
    StarDashboardStandard,
    StarSkillArea,
)

ASSET_SCHEMA = {
    "accelerated_reader": json.loads(
        py_avro_schema.generate(py_type=AcceleratedReader)
    ),
    "fast_star": json.loads(py_avro_schema.generate(py_type=FastStar)),
    "star_dashboard_standards": json.loads(
        py_avro_schema.generate(py_type=StarDashboardStandard)
    ),
    "star": json.loads(py_avro_schema.generate(py_type=Star)),
    "star_skill_area": json.loads(py_avro_schema.generate(py_type=StarSkillArea)),
}
