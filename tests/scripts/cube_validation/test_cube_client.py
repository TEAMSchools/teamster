import base64
import hashlib
import hmac
import json

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.cube_client import (
    Compiled,
    Cube,
    CubeRefusal,
    bind,
    drop_limit,
    mint_token,
    network_schools,
    refuse_unless_safe,
)

FACT = "fct_student_attendance_enrollment_daily"
ALL = {"A", "B", "C"}


def _dec(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def test_token_payload_and_signature():
    tok = mint_token("s3cret", "x@example.org", 1000)
    h, p, s = tok.split(".")

    assert "=" not in tok
    assert json.loads(_dec(p)) == {"email": "x@example.org", "iat": 1000, "exp": 1300}
    want = hmac.new(b"s3cret", f"{h}.{p}".encode(), hashlib.sha256).digest()
    assert _dec(s) == want
    assert json.loads(_dec(h)) == {"alg": "HS256", "typ": "JWT"}


def test_header_has_no_bearer_and_load_posts_query():
    calls = []

    def fetch(method, url, headers, body=None):
        calls.append((method, url, headers, body))

        return {"data": [{"a": 1}]}

    rows = Cube("https://c/api", "s", "x@y", fetch=fetch).load({"measures": ["m"]})

    assert rows == [{"a": 1}]
    method, url, headers, body = calls[0]
    assert (method, url, body) == (
        "POST",
        "https://c/api/load",
        {"query": {"measures": ["m"]}},
    )
    assert not headers["Authorization"].lower().startswith("bearer")
    assert headers["Authorization"].count(".") == 2


def test_compiled_maps_sql_shape_and_polls():
    answers = iter(
        [
            {"error": "Continue wait"},
            {
                "sql": {
                    "sql": ["SELECT ? FROM t", ["a"]],
                    "preAggregations": [{"x": 1}],
                }
            },
        ]
    )
    urls = []

    def fetch(method, url, headers, body=None):
        urls.append((method, url))

        return next(answers)

    c = Cube("https://c/api", "s", "x@y", fetch=fetch, sleep=lambda _: None).compiled(
        {"measures": ["m"]}
    )

    assert c == Compiled("SELECT ? FROM t", ["a"], [{"x": 1}])
    assert urls[0][0] == "GET" and urls[0][1].startswith("https://c/api/sql?query=")
    assert len(urls) == 2


def test_bind_escapes_quotes():
    assert bind(Compiled("x = ?", ["O'Neil"], [])) == "x = 'O\\'Neil'"


def test_bind_numbers_bare_and_backslash():
    assert (
        bind(Compiled("a = ? AND b = ?", [5, "a\\b"], [])) == "a = 5 AND b = 'a\\\\b'"
    )


def test_drop_limit():
    assert drop_limit("SELECT 1 LIMIT 10000") == "SELECT 1"
    assert drop_limit("SELECT 1") == "SELECT 1"


def _sql(fact=FACT, n=3):
    return f"SELECT 1 FROM `kipptaf_marts`.`{fact}` WHERE abbreviation IN ({', '.join('?' * n)})"


def test_safe_query_passes():
    refuse_unless_safe(
        Compiled(_sql(), ["A", "B", "C"], []),
        view_fact=f"kipptaf_marts.{FACT}",
        network_schools=ALL,
    )


def test_preaggregation_is_refused():
    with pytest.raises(CubeRefusal, match="pre-aggregation"):
        refuse_unless_safe(
            Compiled(_sql(), ["A", "B", "C"], [{"n": 1}]),
            view_fact=f"kipptaf_marts.{FACT}",
            network_schools=ALL,
        )


def test_second_fact_is_refused():
    sql = _sql() + " JOIN kipptaf_marts.fct_other o ON 1=1"

    with pytest.raises(CubeRefusal, match="fct_other"):
        refuse_unless_safe(
            Compiled(sql, ["A", "B", "C"], []),
            view_fact=f"kipptaf_marts.{FACT}",
            network_schools=ALL,
        )


def test_short_school_list_is_refused():
    with pytest.raises(CubeRefusal, match="2 of 3"):
        refuse_unless_safe(
            Compiled(_sql(n=2), ["A", "B"], []),
            view_fact=f"kipptaf_marts.{FACT}",
            network_schools=ALL,
        )


def test_network_schools_reads_abbreviations():
    class Wh:
        def rows(self, sql):
            assert "dim_locations" in sql

            return [
                {"abbreviation": "A"},
                {"abbreviation": "B"},
                {"abbreviation": None},
            ]

    assert network_schools(Wh()) == {"A", "B"}
