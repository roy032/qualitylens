"""Reproduce every confirmed bug from a clean state and save the evidence.

    python scripts/capture_evidence.py

For each bug this writes bug-reports/evidence/BUG-00N.txt (the exact HTTP requests
and responses) and, where the bug is visible in the UI, BUG-00N.png. Re-run it
against a newer Gitea version to check whether a bug has been fixed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from qualitylens.api_client import GiteaApi  # noqa: E402
from qualitylens.config import settings  # noqa: E402
from qualitylens.data import new_user_payload, unique  # noqa: E402

OUT = ROOT / "bug-reports" / "evidence"
OWNER = settings.admin_user
api = GiteaApi(auth=(settings.admin_user, settings.admin_password))


class Log:
    def __init__(self, bug: str):
        self.path = OUT / f"{bug}.txt"
        self.lines = [f"{bug} evidence. Gitea {api.get('/version').json()['version']}, {settings.base_url}", ""]

    def call(self, resp, note: str = "", keep: tuple[str, ...] = ()):
        """Log one request/response. `keep` limits a JSON response to the fields that matter."""
        req = resp.request
        body = req.body.decode() if isinstance(req.body, bytes) else (req.body or "")
        if len(body) > 300:
            body = body[:300] + f"... ({len(body)} chars)"
        text = resp.text
        try:
            data = resp.json()
            if keep and isinstance(data, dict):
                data = {k: data.get(k) for k in keep}
            elif keep and isinstance(data, list):
                data = [{k: item.get(k) for k in keep} for item in data]
            text = json.dumps(data, ensure_ascii=False)
        except ValueError:
            pass
        if len(text) > 600:
            text = text[:600] + " ..."
        self.lines += [f"# {note}" if note else "", f"> {req.method} {req.url}", f"> {body}" if body else "",
                       f"< {resp.status_code}", f"< {text}", ""]
        return resp

    def note(self, text: str):
        self.lines += [text, ""]

    def save(self):
        self.path.write_text("\n".join(line for line in self.lines if line is not None))
        print("wrote", self.path.relative_to(ROOT))


def screenshot(url: str, path: Path, clip_selector: str | None = None):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(f"{settings.base_url}/user/login")
        page.fill("#user_name", settings.admin_user)
        page.fill("#password", settings.admin_password)
        page.get_by_role("button", name="Sign In").click()
        page.goto(url)
        target = page.locator(clip_selector).first if clip_selector else page
        target.screenshot(path=str(path))
        browser.close()
    print("wrote", path.relative_to(ROOT))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    repo = unique("evidence")
    api._ok(api.create_repo(repo, auto_init=True))
    base = f"/repos/{OWNER}/{repo}"

    # BUG-001 whitespace-only issue title
    log = Log("BUG-001")
    r = log.call(api.create_issue(OWNER, repo, "   "), "Create issue with title of three spaces", keep=("number", "title", "state"))
    n = r.json()["number"]
    log.call(api.get_issue(OWNER, repo, n), "Read it back: title is now an empty string", keep=("number", "title", "state"))
    log.call(api.create_issue(OWNER, repo, ""), "For comparison: an empty title is rejected")
    log.save()
    screenshot(f"{settings.base_url}/{OWNER}/{repo}/issues", OUT / "BUG-001.png", "#issue-list")

    # BUG-002 silent truncation over 255 characters
    log = Log("BUG-002")
    r = log.call(api.create_issue(OWNER, repo, "x" * 256), "Create issue with a 256-character title", ("number", "state"))
    stored = api.get_issue(OWNER, repo, r.json()["number"]).json()["title"]
    log.note(f"Stored title length: {len(stored)} characters, ends with {stored[-3:]!r} (input was 256 'x').")
    log.save()

    # BUG-003 duplicate label names
    log = Log("BUG-003")
    log.call(api.create_label(OWNER, repo, "bug", "#ff0000"), "Create label 'bug'", ("id", "name", "color"))
    log.call(api.create_label(OWNER, repo, "bug", "#00ff00"), "Create label 'bug' again", ("id", "name", "color"))
    log.call(api.list_labels(OWNER, repo), "List labels: two labels named 'bug'", ("id", "name"))
    log.save()
    screenshot(f"{settings.base_url}/{OWNER}/{repo}/labels", OUT / "BUG-003.png", ".issue-label-list")

    # BUG-004 misleading password error
    log = Log("BUG-004")
    user = new_user_payload(password="Ab1!")
    log.call(api.create_user(user), "Create user with a 4-character password")
    user = new_user_payload(password="")
    log.call(api.create_user(user), "For comparison: no password at all")
    log.save()

    # BUG-005 unknown state filter ignored
    log = Log("BUG-005")
    log.call(api.list_issues(OWNER, repo, state="bogus", limit=1), "List issues with state=bogus", ("number", "title", "state"))
    log.call(api.edit_issue(OWNER, repo, 1, state="bogus"), "For comparison: the same value on edit is rejected")
    log.save()

    # BUG-006 malformed JSON
    log = Log("BUG-006")
    log.call(api.post(f"{base}/issues", data='{"title":', headers={"Content-Type": "application/json"}),
             "POST a truncated JSON body")
    log.save()

    # BUG-007 whitespace-only comment
    log = Log("BUG-007")
    n = api._ok(api.create_issue(OWNER, repo, "Comment target", body="Original issue description"))["number"]
    log.call(api.add_comment(OWNER, repo, n, "   "), "Comment consisting of three spaces", ("id", "body"))
    log.call(api.add_comment(OWNER, repo, n, ""), "For comparison: an empty comment is rejected")
    log.save()
    screenshot(f"{settings.base_url}/{OWNER}/{repo}/issues/{n}", OUT / "BUG-007.png", ".issue-content-left")

    print(f"Evidence repository left in place for inspection: {settings.base_url}/{OWNER}/{repo}")


if __name__ == "__main__":
    main()
