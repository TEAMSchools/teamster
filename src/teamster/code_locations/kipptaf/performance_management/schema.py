import json

import py_avro_schema

from teamster.libraries.performance_management.schema import (
    ObservationDetail,
    OutlierDetection,
)

OUTLIER_DETECTION_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=OutlierDetection, namespace="outlier_detection")
)

OBSERVATION_DETAILS_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=ObservationDetail)
)
