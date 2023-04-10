from alchemer import AlchemerSession
from dagster import OpExecutionContext, Output, Resource, asset


@asset()
def survey(context: OpExecutionContext, alchemer: Resource[AlchemerSession]):
    survey = alchemer.survey.get(context.partition_key.keys_by_dimension["survey_id"])

    record_count = (
        sum([int(v) for v in survey.statistic.values()])
        if survey.statistic is not None
        else 0
    )

    disqualified_count = (
        survey.statistic.get("Disqualified", 0) if survey.statistic is not None else 0
    )

    yield Output(
        value=survey.data,
        metadata={
            "record_count": record_count,
            "disqualified_count": disqualified_count,
        },
    )
