"""The generic API client: URL joining, auth, timeouts and set-up failures that explain themselves."""
import pytest
import requests

from qualitylens.http import ApiClient

pytestmark = pytest.mark.unit


def response(status, body=b"", method="GET", url="http://app/api/x"):
    r = requests.Response()
    r.status_code = status
    r._content = body
    r.url = url
    r.request = requests.Request(method, url).prepare()
    return r


@pytest.fixture
def sent(monkeypatch):
    calls = []

    def fake(self, method, url, **kwargs):
        calls.append((method, url, kwargs))
        return response(200, b"{}", method, url)

    monkeypatch.setattr(requests.Session, "request", fake)
    return calls


def test_verbs_join_base_url_and_default_timeout(sent):
    client = ApiClient("http://app/api/", timeout=7)
    for verb in ("get", "post", "put", "patch", "delete"):
        getattr(client, verb)("/x", json={"a": 1})
    assert sent == [(m, "http://app/api/x", {"json": {"a": 1}, "timeout": 7})
                    for m in ("GET", "POST", "PUT", "PATCH", "DELETE")]
    client.get("/y", timeout=1)
    assert sent[-1] == ("GET", "http://app/api/y", {"timeout": 1})


def test_defaults():
    client = ApiClient("http://a//")
    assert client.base_url == "http://a" and client.timeout == 15


def test_auth_and_token():
    assert ApiClient("http://a", auth=("u", "p")).session.auth == ("u", "p")
    assert ApiClient("http://a", token="t").session.headers["Authorization"] == "Bearer t"
    assert ApiClient("http://a", token="t", token_scheme="token").session.headers["Authorization"] == "token t"
    assert "Authorization" not in ApiClient("http://a").session.headers


def test_ok_returns_json():
    assert ApiClient.ok(response(201, b'{"id": 1}')) == {"id": 1}
    assert ApiClient.ok(response(200, b"[1, 2]")) == [1, 2]
    assert ApiClient.ok(response(204), 204) == {}


def test_ok_fails_with_the_request_and_body():
    with pytest.raises(AssertionError, match=r"Setup call POST http://app/api/x returned 500: boom"):
        ApiClient.ok(response(500, b"boom", "POST"))
    with pytest.raises(AssertionError, match="returned 200"):
        ApiClient.ok(response(200, b"{}"), 201)
