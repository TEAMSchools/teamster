from teamster.code_locations.kippmiami import CODE_LOCATION, LOCAL_TIMEZONE
from teamster.code_locations.kippmiami.finalsite.assets import status_report
from teamster.code_locations.kippmiami.fldoe.assets import eoc, fast, fte, science
from teamster.libraries.couchdrop.sensors import build_couchdrop_sftp_sensor

couchdrop_sftp_sensor = build_couchdrop_sftp_sensor(
    code_location=CODE_LOCATION,
    local_timezone=LOCAL_TIMEZONE,
    asset_selection=[eoc, fast, fte, science, status_report],
    # 5 min, not the 10 min the other locations use: this sensor is what notices
    # the manual midday Finalsite SFTP push, and its poll interval is the dominant
    # term in the push-to-usable chain (poll + 2m13s ingest + 3m34s dbt = ~11 min
    # worst case at 5 min, ~16 min at 10). The 12:30 freshness check on #4736 has
    # to be able to fire on a genuinely-stalled chain rather than one still in
    # flight, and a push at the 12:15 late bound has to be rebuilt well before the
    # 12:45 delivery -- 10 min breaks both. Raising this back silently erodes the
    # push window the 2pm commitment depends on. See #4736.
    minimum_interval_seconds=(60 * 5),
    folder_id="1BLu_qlbcw_jcRZ8m9KIib0UbkPgK4uiM",
    exclude_dirs=[f"/data-team/{CODE_LOCATION}/fldoe/fsa"],
)

sensors = [
    couchdrop_sftp_sensor,
]
