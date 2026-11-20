"""Fabricated-data sandbox for KTAF's Cube semantic layer.

This package builds synthetic BigQuery tables shaped like the Cube model's
real inputs, so the model, its access policies, and its identity resolution
can be exercised without ever reading production data. `model.py` is the
introspection module every later task imports to learn which tables and
columns the Cube model touches; nothing else in this package parses
`src/cube/` directly.
"""

from __future__ import annotations
