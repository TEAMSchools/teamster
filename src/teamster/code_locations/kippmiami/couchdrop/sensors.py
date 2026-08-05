from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.finalsite.assets import status_report
from teamster.code_locations.kippmiami.fldoe.assets import eoc, fast, fte, science
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[eoc, fast, fte, science, status_report],
    # 2 min, not the 10 min the other locations use: this sensor is what notices
    # the manual midday Finalsite SFTP push, and its poll interval is the dominant
    # term in the push-to-usable chain. At 10 min the worst case is ~16 min (poll +
    # 2m13s ingest + 3m34s dbt), which overruns the 12:30 Focus delivery for a push
    # at the 12:15 late bound; at 2 min it is ~8 min, leaving real margin. Raising
    # this back to 10 min silently breaks the 12:00-12:15 push window that the 2pm
    # commitment to stakeholders depends on. See #4736.
    minimum_interval_seconds=(60 * 2),
    folder_id="1BLu_qlbcw_jcRZ8m9KIib0UbkPgK4uiM",
    exclude_dirs=[f"/data-team/{CODE_LOCATION}/fldoe/fsa"],
)

sensors = [
    couchdrop_sftp_sensor,
]
