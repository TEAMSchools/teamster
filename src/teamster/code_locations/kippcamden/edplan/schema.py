import json

import py_avro_schema

from teamster.libraries.edplan.schema import NJSmartPowerschool


class njsmart_powerschool_record(NJSmartPowerschool):
    """helper classes for backwards compatibility"""


pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

NJSMART_POWERSCHOOL = json.loads(
    py_avro_schema.generate(py_type=njsmart_powerschool_record, options=pas_options)
)
