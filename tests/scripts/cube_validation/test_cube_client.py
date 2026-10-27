import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request

import pytest

# trunk-ignore(pyright/reportMissingImports): conftest.py registers cube_validation
from cube_validation.cube_client import (
    Compiled,
    Cube,
    CubeError,
    CubeRefusal,
    bind,
    drop_limit,
    mint_token,
    network_schools,
    refuse_unless_safe,
    sort_school_filters,
    urlopen_json,
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
        {"query": {"measures": ["m"], "timezone": "UTC"}},
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


def test_queries_default_to_utc_and_keep_an_explicit_zone():
    seen = []

    def fetch(method, url, headers, body=None):
        if method == "GET":
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["query"][0]
            seen.append(json.loads(q))
            return {"sql": {"sql": ["SELECT 1", []]}}
        assert body is not None
        seen.append(body["query"])
        return {"data": []}

    cube = Cube("https://c/api", "s", "x@y", fetch=fetch)
    cube.compiled({"dimensions": ["v.d"]})
    cube.load({"measures": ["v.m"], "timezone": "America/New_York"})

    assert seen[0]["timezone"] == "UTC"
    assert seen[1]["timezone"] == "America/New_York"


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


VF = f"kipptaf_marts.{FACT}"
BASE = f"SELECT 1 FROM `kipptaf_marts`.`{FACT}` WHERE "


def _refuse(sql, params, match):
    with pytest.raises(CubeRefusal, match=match):
        refuse_unless_safe(Compiled(sql, params, []), view_fact=VF, network_schools=ALL)


def test_single_school_equals_is_refused():
    _refuse(BASE + "abbreviation = ?", ["A"], "1 of 3")


def test_unnest_short_list_is_refused():
    _refuse(BASE + "abbreviation IN UNNEST(?)", [["A", "B"]], "2 of 3")


def test_unnest_full_list_passes():
    refuse_unless_safe(
        Compiled(BASE + "abbreviation IN UNNEST(?)", [["A", "B", "C"]], []),
        view_fact=VF,
        network_schools=ALL,
    )


def test_no_school_filter_is_refused():
    _refuse(BASE + "grade_level = ?", [5], "No school filter")


def test_default_deny_is_refused():
    _refuse(
        BASE + "(1 = 0) AND abbreviation IN (?, ?, ?)", ["A", "B", "C"], "default-deny"
    )


def test_extra_school_is_refused():
    _refuse(BASE + "abbreviation IN (?, ?, ?, ?)", ["A", "B", "C", "D"], "4 of 3")


def test_fewer_params_is_an_error():
    with pytest.raises(CubeError, match="2 placeholders but 1"):
        bind(Compiled("a = ? AND b = ?", [1], []))


def test_extra_params_is_an_error():
    with pytest.raises(CubeError, match="1 placeholders but 2"):
        bind(Compiled("a = ?", [1, 2], []))


def test_question_mark_in_string_literal_is_text():
    assert bind(Compiled("a = 'why?' AND b = ?", [7], [])) == "a = 'why?' AND b = 7"


def test_list_param_is_array_literal():
    assert (
        bind(Compiled("x IN UNNEST(?)", [["A", "O'B"]], []))
        == "x IN UNNEST(['A', 'O\\'B'])"
    )


def test_newline_is_escaped():
    assert bind(Compiled("x = ?", ["a\nb\tc\r"], [])) == "x = 'a\\nb\\tc\\r'"


def test_none_and_bool():
    assert bind(Compiled("? ? ?", [None, True, False], [])) == "NULL TRUE FALSE"


def test_unsupported_type_is_an_error():
    import datetime

    with pytest.raises(CubeError, match="date"):
        bind(Compiled("x = ?", [datetime.date(2026, 1, 1)], []))


@pytest.mark.parametrize("col", ["school_abbreviation", "region_abbreviation"])
def test_prefixed_abbreviation_column_is_not_the_school_filter(col):
    _refuse(BASE + f"{col} IN (?, ?, ?)", ["A", "B", "C"], "No school filter")


@pytest.mark.parametrize(
    "col", ["t.abbreviation", "`t`.`abbreviation`", "`abbreviation`"]
)
def test_qualified_and_quoted_school_filter_counts(col):
    refuse_unless_safe(
        Compiled(BASE + f"{col} IN (?, ?, ?)", ["A", "B", "C"], []),
        view_fact=VF,
        network_schools=ALL,
    )


def test_two_filters_that_only_union_to_network_are_refused():
    _refuse(
        BASE + "abbreviation IN (?, ?) AND abbreviation = ?",
        ["A", "B", "C"],
        "2 of 3",
    )


def test_sort_school_filters_orders_every_form():
    sql = (
        "WHERE `l`.abbreviation IN ('C', 'A', 'B') "
        "AND abbreviation IN UNNEST(['B', 'A']) AND abbreviation = 'Z' "
        "AND name IN ('Y', 'X')"
    )
    assert sort_school_filters(sql) == (
        "WHERE `l`.abbreviation IN ('A', 'B', 'C') "
        "AND abbreviation IN UNNEST(['A', 'B']) AND abbreviation = 'Z' "
        "AND name IN ('Y', 'X')"
    )


@pytest.mark.parametrize("url", ["http://c/api", "file:///etc/passwd", "ftp://c/api"])
def test_base_url_that_is_not_https_is_refused(url):
    with pytest.raises(CubeError, match="https"):
        Cube(url, "s", "x@y")


def test_request_to_a_non_https_url_is_refused_before_it_is_sent():
    with pytest.raises(CubeError, match="https"):
        urlopen_json("GET", "file:///etc/passwd", {})


@pytest.mark.parametrize(
    "error", [urllib.error.URLError("no route"), TimeoutError("timed out")]
)
def test_network_failure_is_a_cube_error(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(urllib.request, "urlopen", fail)
    with pytest.raises(CubeError, match="did not answer"):
        urlopen_json("GET", "https://cube.example/x", {})
