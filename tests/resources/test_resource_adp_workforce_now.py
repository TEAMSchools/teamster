import json
import logging
import pathlib
import types

import pytest
from dagster import build_resources
from requests.exceptions import HTTPError, JSONDecodeError
from tenacity import RetryError, wait_none

from teamster.libraries.adp.workforce_now.api.resources import (
    AdpWorkforceNowError,
    AdpWorkforceNowResource,
)


def get_adp_wfn_resource() -> AdpWorkforceNowResource:
    from teamster.code_locations.kipptaf.resources import ADP_WORKFORCE_NOW_RESOURCE

    with build_resources(
        resources={"adp_wfn": ADP_WORKFORCE_NOW_RESOURCE}
    ) as resources:
        return resources.adp_wfn


def test_event_notification():
    adp_wfn = get_adp_wfn_resource()

    r = adp_wfn._request(
        method="GET", url=f"{adp_wfn._service_root}/core/v1/event-notification-messages"
    )

    print(r.json())


def _test_get_worker(aoid: str | None = None, as_of_date: str | None = None):
    adp_wfn = get_adp_wfn_resource()

    params = {
        "asOfDate": as_of_date,
        "$select": ",".join(
            [
                "workers/associateOID",
                "workers/businessCommunication",
                "workers/customFieldGroup",
                "workers/languageCode",
                "workers/person/birthDate",
                "workers/person/communication",
                "workers/person/customFieldGroup",
                "workers/person/disabledIndicator",
                "workers/person/ethnicityCode",
                "workers/person/genderCode",
                "workers/person/genderSelfIdentityCode",
                "workers/person/highestEducationLevelCode",
                "workers/person/legalAddress",
                "workers/person/legalName",
                "workers/person/militaryClassificationCodes",
                "workers/person/militaryStatusCode",
                "workers/person/preferredName",
                "workers/person/raceCode",
                "workers/workAssignments",
                "workers/workerDates",
                "workers/workerID",
                "workers/workerStatus",
            ]
        ),
    }

    if aoid is not None:
        data = adp_wfn.get(endpoint=f"hr/v2/workers/{aoid}", params=params).json()
        filepath = pathlib.Path(f"env/test/adp/workers/{aoid}.json")
    else:
        data = adp_wfn.get_records(endpoint="hr/v2/workers", params=params)
        filepath = pathlib.Path("env/test/adp/workers/workers.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=data, fp=filepath.open(mode="w"))


def test_get_worker():
    _test_get_worker(aoid="G3J18W59P8K8W9R9", as_of_date="07/02/2025")


def test_get_worker_list():
    test_cases = [
        {"aoid": "G3ASWDTVJ0WV2TAE", "as_of_date": "07/25/2024"},
        {"aoid": "G3ASWDTVJ0WV1BGB", "as_of_date": "08/14/2024"},
        {"aoid": "G3Z22CB7N12F1ZT0", "as_of_date": "08/13/2024"},
        {"aoid": "G3R8E9HV8QXW9AWE", "as_of_date": "01/29/2024"},
    ]

    for kwargs in test_cases:
        print(kwargs)
        _test_get_worker(**kwargs)


def test_get_workers_meta():
    adp_wfn = get_adp_wfn_resource()

    data = adp_wfn.get(endpoint="hr/v2/workers/meta").json()
    filepath = pathlib.Path("env/test/adp/workers/meta.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=data, fp=filepath.open(mode="w"))


def test_get_valiation_tables():
    adp_wfn = get_adp_wfn_resource()

    data = adp_wfn.get(endpoint="hcm/v1/validation-tables/jobs").json()
    filepath = pathlib.Path("env/test/adp/hcm/v1/validation-tables/jobs.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=data, fp=filepath.open(mode="w"))


def test_get_talent_associate_memberships():
    aoid = "G550F72Q44ZGT3QT"

    adp_wfn = get_adp_wfn_resource()

    data = adp_wfn.get(
        endpoint=f"/talent/v2/associates/{aoid}/associate-memberships"
    ).json()
    filepath = pathlib.Path("env/test/adp/talent/associate-memberships.json")

    filepath.parent.mkdir(parents=True, exist_ok=True)

    json.dump(obj=data, fp=filepath.open(mode="w"))


class _FakeResponse:
    def __init__(
        self,
        status_code: int,
        json_body: dict,
        *,
        text: str = "",
        json_raises: bool = False,
    ) -> None:
        self.status_code = status_code
        self._json_body = json_body
        self.text = text
        self._json_raises = json_raises

    def json(self) -> dict:
        if self._json_raises:
            raise JSONDecodeError("Expecting value", "", 0)

        return self._json_body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"{self.status_code} Server Error", response=self)  # pyright: ignore[reportArgumentType]


def _build_offline_resource(request_fn) -> AdpWorkforceNowResource:
    """Instantiate the resource without the network setup_for_execution path."""
    adp_wfn = AdpWorkforceNowResource(
        client_id="x", client_secret="x", cert_filepath="x", key_filepath="x"
    )

    object.__setattr__(adp_wfn, "_session", types.SimpleNamespace(request=request_fn))
    object.__setattr__(adp_wfn, "_log", logging.getLogger("test_adp_wfn"))

    return adp_wfn


def test_request_retries_on_server_error(monkeypatch: pytest.MonkeyPatch):
    """A 5xx response is transient and must be retried.

    Regression: non-429 errors were re-raised as a bare ``Exception``, which the
    tenacity ``retry_if_exception_type`` predicate did not match, so 500s failed
    on the first attempt instead of being retried.
    """
    # make tenacity backoff instant for the test
    monkeypatch.setattr(AdpWorkforceNowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(500, {"status": 500, "error": "Internal Server Error"})
        return _FakeResponse(200, {"ok": True})

    adp_wfn = _build_offline_resource(request_fn)

    response = adp_wfn._request(method="GET", url="https://api.adp.com/hr/v2/workers")

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_does_not_retry_on_client_error(monkeypatch: pytest.MonkeyPatch):
    """A non-429 4xx is deterministic: raise a specific error without retrying."""
    monkeypatch.setattr(AdpWorkforceNowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(400, {"status": 400, "error": "Bad Request"})

    adp_wfn = _build_offline_resource(request_fn)

    with pytest.raises(AdpWorkforceNowError):
        adp_wfn._request(method="GET", url="https://api.adp.com/hr/v2/workers")

    assert calls["n"] == 1


def test_request_retries_server_error_with_non_json_body(
    monkeypatch: pytest.MonkeyPatch,
):
    """A 5xx whose body is not JSON (a gateway 504 HTML page) must still retry.

    Regression: the handler called ``response.json()`` before checking the
    status code. A gateway 504 returns a non-JSON body, so ``.json()`` raised
    ``JSONDecodeError`` — which the tenacity predicate does not match — and the
    request failed on the first attempt instead of being retried as a 5xx.
    """
    monkeypatch.setattr(AdpWorkforceNowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(504, {}, json_raises=True, text="504 Gateway Time-out")
        return _FakeResponse(200, {"ok": True})

    adp_wfn = _build_offline_resource(request_fn)

    response = adp_wfn._request(method="GET", url="https://api.adp.com/hr/v2/workers")

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_non_json_server_error_retries_as_httperror(
    monkeypatch: pytest.MonkeyPatch,
):
    """A persistent non-JSON 5xx is retried, then exhausts as a wrapped HTTPError.

    The underlying cause across all attempts must be the retryable ``HTTPError``,
    never the ``JSONDecodeError`` produced by parsing a non-JSON gateway body. On
    exhaustion tenacity wraps the last failure in ``RetryError``.
    """
    monkeypatch.setattr(AdpWorkforceNowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(504, {}, json_raises=True, text="504 Gateway Time-out")

    adp_wfn = _build_offline_resource(request_fn)

    with pytest.raises(RetryError) as exc_info:
        adp_wfn._request(method="GET", url="https://api.adp.com/hr/v2/workers")

    assert calls["n"] == 5
    assert isinstance(exc_info.value.last_attempt.exception(), HTTPError)


def test_request_non_json_client_error_raises_adp_error(
    monkeypatch: pytest.MonkeyPatch,
):
    """A non-JSON 4xx surfaces ``AdpWorkforceNowError`` without retrying.

    The deterministic-4xx branch must tolerate a non-JSON body instead of
    crashing on ``response.json()``.
    """
    monkeypatch.setattr(AdpWorkforceNowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(404, {}, json_raises=True, text="404 Not Found")

    adp_wfn = _build_offline_resource(request_fn)

    with pytest.raises(AdpWorkforceNowError):
        adp_wfn._request(method="GET", url="https://api.adp.com/hr/v2/workers")

    assert calls["n"] == 1


def test_request_retries_on_transient_gateway_404(monkeypatch: pytest.MonkeyPatch):
    """ADP's gateway returns a transient ``default backend - 404`` mid-pagination.

    Regression: this load-balancer 404 was classified as a deterministic 4xx and
    raised ``AdpWorkforceNowError`` without retrying. It must be re-raised as the
    retryable ``HTTPError`` so tenacity retries with backoff (the genuine-404
    case above must still fail fast).
    """
    monkeypatch.setattr(AdpWorkforceNowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        if calls["n"] < 3:
            return _FakeResponse(404, {}, text="default backend - 404")
        return _FakeResponse(200, {"ok": True})

    adp_wfn = _build_offline_resource(request_fn)

    response = adp_wfn._request(method="GET", url="https://api.adp.com/hr/v2/workers")

    assert response.status_code == 200
    assert calls["n"] == 3


def test_request_persistent_gateway_404_retries_as_httperror(
    monkeypatch: pytest.MonkeyPatch,
):
    """A persistent gateway 404 is retried, then exhausts as a wrapped HTTPError.

    Confirms the transient-gateway-404 branch routes through the retryable
    ``HTTPError`` path end-to-end rather than the non-retryable
    ``AdpWorkforceNowError`` path.
    """
    monkeypatch.setattr(AdpWorkforceNowResource._request.retry, "wait", wait_none())  # pyright: ignore[reportFunctionMemberAccess]

    calls = {"n": 0}

    def request_fn(method: str, url: str, **kwargs) -> _FakeResponse:
        calls["n"] += 1
        return _FakeResponse(404, {}, text="default backend - 404")

    adp_wfn = _build_offline_resource(request_fn)

    with pytest.raises(RetryError) as exc_info:
        adp_wfn._request(method="GET", url="https://api.adp.com/hr/v2/workers")

    assert calls["n"] == 5
    assert isinstance(exc_info.value.last_attempt.exception(), HTTPError)
