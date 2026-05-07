# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml>=6.0", "ruamel.yaml>=0.18"]
# ///

"""Sync dbt mart YAML descriptions into Cube cube YAML files.

Reads each cube file under ``src/cube/model/cubes/``, locates the matching
dbt mart YAML via ``sql_table:``, and inserts dbt column descriptions onto
cube dimensions that lack them. Patches dimensions only — measures are
calculations and require hand-authored descriptions. Existing Cube
descriptions are preserved.

Usage:
    uv run scripts/sync_cube_descriptions.py [--check]
"""

from __future__ import annotations
