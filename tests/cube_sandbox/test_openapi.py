"""The published OpenAPI spec against the published catalog.

A hand-written spec beside a generated catalog is a drift pair: the catalog
moves when the model is bumped and nothing makes the spec follow. These tests
are what make the spec a checked artifact rather than a snapshot of one
afternoon.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

_ROOT = Path(__file__).resolve().parents[2]
_SPEC = _ROOT / "docs" / "reference" / "cube-sandbox-openapi.yml"
_CATALOG = _ROOT / "docs" / "reference" / "cube-catalog-meta.json"


def _spec() -> dict:
    return yaml.safe_load(_SPEC.read_text(encoding="utf-8"))


def _catalog_views() -> set[str]:
    catalog = json.loads(_CATALOG.read_text(encoding="utf-8"))
    return {c["name"] for c in catalog["cubes"] if c.get("type") == "view"}


def test_the_spec_lists_exactly_the_catalog_s_views() -> None:
    declared = set(_spec()["components"]["schemas"]["ViewName"]["enum"])

    assert declared == _catalog_views()


def test_the_view_enum_is_not_silently_empty() -> None:
    # Both sides reading empty would satisfy the comparison above.
    assert len(_catalog_views()) == 6


def test_authorization_is_an_api_key_not_a_bearer_scheme() -> None:
    # The whole reason this file exists. Cube's own spec declares
    # `type: http, scheme: bearer`, from which every generator emits
    # `Authorization: Bearer <token>` — and KTAF's checkAuth reads the RAW
    # token, so the prefix fails every call with a 403 that never mentions it.
    scheme = _spec()["components"]["securitySchemes"]["rawJwt"]

    assert scheme["type"] == "apiKey"
    assert scheme["in"] == "header"
    assert scheme["name"] == "Authorization"
    # Assert on the FIELDS, not the prose: `scheme` and `bearerFormat` are
    # what an http/bearer declaration carries and what a generator reads. The
    # description deliberately says the word "Bearer" to explain its absence.
    assert "scheme" not in scheme
    assert "bearerFormat" not in scheme


def test_load_documents_the_long_poll_as_a_200() -> None:
    # Cube answers a query it is still computing with {"error": "Continue
    # wait"} at HTTP 200. A client that treats 200 as success hands that
    # object to its caller as data.
    ok = _spec()["paths"]["/v1/load"]["post"]["responses"]["200"]
    refs = json.dumps(ok["content"]["application/json"]["schema"])

    assert "ContinueWait" in refs
    assert "LoadResult" in refs


def test_sql_takes_a_query_parameter_rather_than_a_body() -> None:
    # Our own client calls GET /v1/sql with a JSON-encoded `query` param.
    # Documenting it as a POST body would generate a client that 404s.
    operation = _spec()["paths"]["/v1/sql"]
    assert set(operation) == {"get"}

    names = [p["name"] for p in operation["get"]["parameters"]]
    assert names == ["query"]


def test_the_server_is_the_sandbox_and_says_so() -> None:
    # A spec that defaulted to production would point a partner's generated
    # client at real student data.
    servers = _spec()["servers"]

    assert len(servers) == 1
    assert "petite-dorton" in servers[0]["url"]
    assert "fabricated" in servers[0]["description"].lower()


def test_the_spec_parses_as_openapi() -> None:
    # Beyond valid YAML: the structural contract a generator relies on.
    spec = _spec()

    assert spec["openapi"].startswith("3.")
    assert spec["info"]["title"] and spec["info"]["version"]
    assert set(spec["paths"]) == {"/v1/meta", "/v1/load", "/v1/sql"}
    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            assert operation.get("operationId"), f"{method} {path} has no operationId"
            assert "403" in operation["responses"], f"{method} {path} omits 403"


def test_every_schema_reference_resolves() -> None:
    # A typo in a $ref makes a generator emit a client missing that type,
    # which compiles and then fails at the call site.
    spec = _spec()
    schemas = set(spec["components"]["schemas"])
    responses = set(spec["components"]["responses"])

    unresolved = []
    for ref in _refs(spec):
        kind, _, name = ref.removeprefix("#/components/").partition("/")
        pool = (
            schemas if kind == "schemas" else responses if kind == "responses" else None
        )
        if pool is None or name not in pool:
            unresolved.append(ref)

    assert not unresolved, f"unresolved $ref: {unresolved}"


def _refs(node: object) -> list[str]:
    if isinstance(node, dict):
        found = [node["$ref"]] if isinstance(node.get("$ref"), str) else []
        for key, value in node.items():
            if key != "$ref":
                found += _refs(value)
        return found
    if isinstance(node, list):
        return [ref for item in node for ref in _refs(item)]
    return []
