"""Gitea REST API (/api/v1) on top of the engine's ApiClient: one method per endpoint the suite uses."""
from __future__ import annotations

from qualitylens.http import ApiClient
from suite.config import settings


class GiteaApi(ApiClient):
    def __init__(self, auth: tuple[str, str] | None = None, token: str | None = None,
                 base_url: str = settings.api_url, timeout: float = 15):
        super().__init__(base_url, auth=auth, token=token, token_scheme="token", timeout=timeout)

    _ok = staticmethod(ApiClient.ok)  # the name the suite's fixtures use

    # --- users -------------------------------------------------------------
    def me(self):
        return self.get("/user")

    def create_user(self, payload: dict):
        return self.post("/admin/users", json=payload)

    def delete_user(self, username: str):
        return self.delete(f"/admin/users/{username}", params={"purge": "true"})

    def create_token(self, username: str, name: str, scopes: list[str]):
        return self.post(f"/users/{username}/tokens", json={"name": name, "scopes": scopes})

    # --- repositories ----------------------------------------------------
    def create_repo(self, name: str, **fields):
        return self.post("/user/repos", json={"name": name, **fields})

    def get_repo(self, owner: str, repo: str):
        return self.get(f"/repos/{owner}/{repo}")

    def delete_repo(self, owner: str, repo: str):
        return self.delete(f"/repos/{owner}/{repo}")

    # --- issues ------------------------------------------------------------
    def create_issue(self, owner: str, repo: str, title: str, **fields):
        return self.post(f"/repos/{owner}/{repo}/issues", json={"title": title, **fields})

    def get_issue(self, owner: str, repo: str, number: int | str):
        return self.get(f"/repos/{owner}/{repo}/issues/{number}")

    def list_issues(self, owner: str, repo: str, **params):
        return self.get(f"/repos/{owner}/{repo}/issues", params=params)

    def edit_issue(self, owner: str, repo: str, number: int, **fields):
        return self.patch(f"/repos/{owner}/{repo}/issues/{number}", json=fields)

    def add_comment(self, owner: str, repo: str, number: int, body: str):
        return self.post(f"/repos/{owner}/{repo}/issues/{number}/comments", json={"body": body})

    def list_comments(self, owner: str, repo: str, number: int):
        return self.get(f"/repos/{owner}/{repo}/issues/{number}/comments")

    def edit_comment(self, owner: str, repo: str, comment_id: int, body: str):
        return self.patch(f"/repos/{owner}/{repo}/issues/comments/{comment_id}", json={"body": body})

    def delete_comment(self, owner: str, repo: str, comment_id: int):
        return self.delete(f"/repos/{owner}/{repo}/issues/comments/{comment_id}")

    # --- milestones --------------------------------------------------------
    def create_milestone(self, owner: str, repo: str, title: str, **fields):
        return self.post(f"/repos/{owner}/{repo}/milestones", json={"title": title, **fields})

    def get_milestone(self, owner: str, repo: str, milestone_id: int):
        return self.get(f"/repos/{owner}/{repo}/milestones/{milestone_id}")

    # --- labels ------------------------------------------------------------
    def create_label(self, owner: str, repo: str, name: str, color: str = "#ee0701", **fields):
        return self.post(f"/repos/{owner}/{repo}/labels", json={"name": name, "color": color, **fields})

    def list_labels(self, owner: str, repo: str):
        return self.get(f"/repos/{owner}/{repo}/labels")

    # --- misc --------------------------------------------------------------
    def render_markdown(self, text: str):
        """Server-side Markdown rendering, the same sanitiser the web UI uses for issue and comment bodies."""
        return self.post("/markdown", json={"text": text, "mode": "gfm"})
