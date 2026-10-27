"""Web-layer security: XSS, CSRF, cookies, headers, injection. Manual cases: TC-SEC-WEB-*.

These are regression checks for protections Gitea already has, so a configuration change or an
upgrade that weakens one of them fails the build. They are not a penetration test.
"""
from html.parser import HTMLParser

import allure
import pytest
import requests
from playwright.sync_api import expect

from pages.issue_pages import IssuePage
from suite.config import settings
from suite.data import unique

pytestmark = [pytest.mark.security, allure.feature("Security: Web")]
OWNER = settings.admin_user

XSS_PAYLOADS = {
    "script-tag": "<script>alert('xss')</script>",
    "img-onerror": "<img src=x onerror=alert('xss')>",
    "svg-onload": "<svg onload=alert('xss')>",
    "js-link": "[click me](javascript:alert('xss'))",
    "event-attr": '<a href="#" onclick="alert(\'xss\')">click</a>',
    "iframe": '<iframe src="https://example.com"></iframe>',
}


class ActiveContentFinder(HTMLParser):
    """Collects every element or attribute in rendered HTML that a browser would execute.

    Parsing (rather than searching the text) matters: `&lt;img onerror=...&gt;` is harmless
    escaped text, while `<img onerror=...>` is an attack.
    """
    def __init__(self):
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "iframe", "object", "embed"):
            self.found.append(f"<{tag}>")
        for name, value in attrs:
            if name.startswith("on"):
                self.found.append(f"{tag}[{name}]")
            if name in ("href", "src", "action") and (value or "").strip().lower().startswith("javascript:"):
                self.found.append(f"{tag}[{name}={value}]")


@pytest.mark.api
@pytest.mark.parametrize("payload", XSS_PAYLOADS.values(), ids=XSS_PAYLOADS.keys())
def test_markdown_renderer_strips_active_content(api, payload):
    """Issue and comment bodies go through this renderer; nothing executable may survive it."""
    resp = api.render_markdown(payload)
    assert resp.status_code == 200
    finder = ActiveContentFinder()
    finder.feed(resp.text)
    assert finder.found == [], f"active content survived sanitising: {resp.text}"


@pytest.mark.ui
@pytest.mark.smoke
@allure.title("Stored XSS: script payloads in an issue title and body never execute")
def test_stored_xss_does_not_execute(admin_page, api, repo):
    payload = "\n\n".join(XSS_PAYLOADS.values())
    created = api._ok(api.create_issue(OWNER, repo["name"], XSS_PAYLOADS["img-onerror"], body=payload))
    dialogs = []
    admin_page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))

    issue = IssuePage(admin_page, OWNER, repo["name"], created["number"]).open()
    expect(issue.heading).to_contain_text("<img src=x onerror=")  # shown as text, not turned into an element
    admin_page.goto(f"{settings.base_url}/{OWNER}/{repo['name']}/issues")
    admin_page.wait_for_load_state("load")
    assert dialogs == []


@pytest.mark.api
def test_state_change_without_csrf_token_rejected(temp_user):
    """A signed-in browser session cannot be used to create data without the per-session CSRF token."""
    web = requests.Session()
    login_form = web.get(f"{settings.base_url}/user/login", timeout=15).text
    token = login_form.split('name="_csrf" value="', 1)[1].split('"', 1)[0]
    web.post(f"{settings.base_url}/user/login", timeout=15, data={
        "_csrf": token, "user_name": temp_user["username"], "password": temp_user["password"]})
    assert web.get(f"{settings.base_url}/user/settings", timeout=15, allow_redirects=False).status_code == 200

    name = unique("csrf")
    forged = web.post(f"{settings.base_url}/repo/create", timeout=15, data={
        "uid": "0", "repo_name": name, "default_branch": "main", "object_format_name": "sha1"})
    assert forged.status_code == 400
    assert "Invalid CSRF token" in forged.text
    assert requests.get(f"{settings.api_url}/repos/{temp_user['username']}/{name}", timeout=15).status_code == 404


@pytest.mark.api
def test_session_cookies_are_httponly_and_samesite():
    resp = requests.get(f"{settings.base_url}/user/login", timeout=15)
    cookies = {c.split("=", 1)[0]: c for c in resp.raw.headers.get_all("Set-Cookie")}
    for name in ("i_like_gitea", "_csrf"):
        assert name in cookies, f"{name} cookie not set"
        assert "HttpOnly" in cookies[name], f"{name} readable from JavaScript"
        assert "SameSite=Lax" in cookies[name], f"{name} sent on cross-site requests"


@pytest.mark.api
@pytest.mark.parametrize("path", ["/user/login", "/explore/repos"])
def test_pages_cannot_be_framed(path):
    """Clickjacking: other sites must not be able to embed Gitea pages."""
    resp = requests.get(f"{settings.base_url}{path}", timeout=15)
    assert resp.headers.get("X-Frame-Options") == "SAMEORIGIN"


@pytest.mark.api
@pytest.mark.parametrize("query", ["' OR 1=1--", "\" OR \"\"=\"", "\\", "' UNION SELECT passwd FROM \"user\"--"],
                         ids=["or-1-1", "double-quote", "backslash", "union"])
def test_search_handles_sql_metacharacters(api, repo, query):
    """Injection probes are treated as literal text: no server error and no rows leak."""
    resp = api.get("/repos/search", params={"q": query})
    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.api
@pytest.mark.parametrize("path", ["/../../etc/passwd", "/qa_admin/%2e%2e/%2e%2e/etc/passwd",
                                  "/api/v1/repos/qa_admin/x/raw/..%2f..%2f..%2fetc%2fpasswd"],
                         ids=["dotdot", "encoded", "raw-endpoint"])
def test_path_traversal_blocked(path):
    resp = requests.get(settings.base_url + path, timeout=15)
    assert resp.status_code in (400, 404)
    assert "root:x:0:0" not in resp.text


@pytest.mark.api
def test_login_error_does_not_reveal_accounts():
    """Wrong password for a real account and any password for a missing one must look identical."""
    def attempt(user):
        web = requests.Session()
        form = web.get(f"{settings.base_url}/user/login", timeout=15).text
        token = form.split('name="_csrf" value="', 1)[1].split('"', 1)[0]
        resp = web.post(f"{settings.base_url}/user/login", timeout=15,
                        data={"_csrf": token, "user_name": user, "password": "Wrong-Passw0rd"})
        return resp.status_code, "Username or password is incorrect." in resp.text

    assert attempt(settings.admin_user) == attempt("nobody_" + unique("x").replace("-", "_")) == (200, True)
