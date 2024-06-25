import json

import py_avro_schema

from teamster.libraries.adp.payroll.schema import GeneralLedger


class general_ledger_file_record(GeneralLedger):
    """helper classes for backwards compatibility"""


GENERAL_LEDGER_FILE_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=general_ledger_file_record,
        options=py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE,
    )
)
