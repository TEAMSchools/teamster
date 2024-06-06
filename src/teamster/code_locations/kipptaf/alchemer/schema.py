import json

import py_avro_schema

from teamster.libraries.alchemer.schema import (
    Survey,
    SurveyCampaign,
    SurveyQuestion,
    SurveyResponse,
)

pas_options = py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE

SURVEY_SCHEMA = json.loads(py_avro_schema.generate(py_type=Survey, options=pas_options))

SURVEY_CAMPAIGN_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SurveyCampaign, options=pas_options)
)

SURVEY_QUESTION_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SurveyQuestion, options=pas_options)
)

SURVEY_RESPONSE_SCHEMA = json.loads(
    py_avro_schema.generate(py_type=SurveyResponse, options=pas_options)
)
