# trunk-ignore-all(pyright/reportIncompatibleVariableOverride)
import json

import py_avro_schema

from teamster.libraries.zendesk.schema import Minutes, TicketMetric


class agent_wait_time_in_minutes_record(Minutes):
    """helper class for backwards compatibility"""


class first_resolution_time_in_minutes_record(Minutes):
    """helper class for backwards compatibility"""


class full_resolution_time_in_minutes_record(Minutes):
    """helper class for backwards compatibility"""


class on_hold_time_in_minutes_record(Minutes):
    """helper class for backwards compatibility"""


class reply_time_in_minutes_record(Minutes):
    """helper class for backwards compatibility"""


class requester_wait_time_in_minutes_record(Minutes):
    """helper class for backwards compatibility"""


class ticket_metrics_record(TicketMetric):
    """helper class for backwards compatibility"""

    agent_wait_time_in_minutes: agent_wait_time_in_minutes_record | None = None
    first_resolution_time_in_minutes: first_resolution_time_in_minutes_record | None = (
        None
    )
    full_resolution_time_in_minutes: full_resolution_time_in_minutes_record | None = (
        None
    )
    on_hold_time_in_minutes: on_hold_time_in_minutes_record | None = None
    reply_time_in_minutes: reply_time_in_minutes_record | None = None
    requester_wait_time_in_minutes: requester_wait_time_in_minutes_record | None = None


TICKET_METRIC_SCHEMA = json.loads(
    py_avro_schema.generate(
        py_type=ticket_metrics_record,
        options=py_avro_schema.Option.NO_DOC | py_avro_schema.Option.NO_AUTO_NAMESPACE,
    )
)
