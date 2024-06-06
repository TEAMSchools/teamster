# trunk-ignore-all(pyright/reportIncompatibleVariableOverride)
import json

import py_avro_schema

from teamster.libraries.tableau.schema import View, Workbook


class view_record(View):
    """helper class for backwards compatibility"""


class workbook_record(Workbook):
    """helper class for backwards compatibility"""

    views: list[view_record | None] | None = None


WORKBOOK_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=workbook_record,
        namespace="workbook",
        options=py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE,
    )
)

# remove top-level namespace for backwards compatibility
del WORKBOOK_SCHEMA["namespace"]
