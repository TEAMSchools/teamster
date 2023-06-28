from teamster.core.ldap.sensors import build_ldap_asset_sensor

from .. import CODE_LOCATION
from . import assets

ldap_asset_sensor = build_ldap_asset_sensor(
    code_location=CODE_LOCATION, asset_defs=assets, minimum_interval_seconds=600
)

__all__ = [
    ldap_asset_sensor,
]
