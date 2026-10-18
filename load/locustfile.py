"""Load test for the key Gitea endpoints.

Simulated user mix (weights): mostly reads, some writes, like a real issue tracker.
Pass/fail thresholds are enforced at the end of the run so CI fails on a
performance regression, not just on errors.

Run headless (what CI does):
    locust -f load/locustfile.py --headless -u 20 -r 5 -t 60s --host http://localhost:3000 \
           --csv load/results/run --html load/results/report.html
"""
import os
import uuid

from locust import HttpUser, between, events, task

ADMIN = (os.getenv("QL_ADMIN_USER", "qa_admin"), os.getenv("QL_ADMIN_PASSWORD", "QaAdmin#2026"))
REPO = "load-target"

# Service-level objectives. Tune to your hardware, then keep them stable so trends mean something.
MAX_FAILURE_RATIO = float(os.getenv("QL_MAX_FAILURE_RATIO", "0.01"))   # 1 %
MAX_P95_MS = float(os.getenv("QL_MAX_P95_MS", "800"))


@events.test_start.add_listener
def create_target_repo(environment, **_):
    """One shared repository with some issues, so read endpoints return real data."""
    import requests
    api = f"{environment.host}/api/v1"
    requests.delete(f"{api}/repos/{ADMIN[0]}/{REPO}", auth=ADMIN, timeout=10)
    requests.post(f"{api}/user/repos", json={"name": REPO, "auto_init": True}, auth=ADMIN, timeout=10)
    for i in range(10):
        requests.post(f"{api}/repos/{ADMIN[0]}/{REPO}/issues", json={"title": f"seed {i}"}, auth=ADMIN, timeout=10)


class GiteaUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.client.auth = ADMIN

    @task(5)
    def list_issues(self):
        self.client.get(f"/api/v1/repos/{ADMIN[0]}/{REPO}/issues?limit=20", name="GET /issues")

    @task(3)
    def view_repo(self):
        self.client.get(f"/api/v1/repos/{ADMIN[0]}/{REPO}", name="GET /repo")

    @task(2)
    def search_repos(self):
        self.client.get("/api/v1/repos/search?q=load&limit=10", name="GET /repos/search")

    @task(1)
    def issue_page_html(self):
        self.client.get(f"/{ADMIN[0]}/{REPO}/issues", name="GET issues page (HTML)")

    @task(1)
    def create_issue(self):
        with self.client.post(f"/api/v1/repos/{ADMIN[0]}/{REPO}/issues",
                              json={"title": f"load {uuid.uuid4().hex[:8]}"},
                              name="POST /issues", catch_response=True) as resp:
            if resp.status_code != 201:
                resp.failure(f"expected 201, got {resp.status_code}")


@events.quitting.add_listener
def enforce_slos(environment, **_):
    stats = environment.stats.total
    p95 = stats.get_response_time_percentile(0.95)
    problems = []
    if stats.fail_ratio > MAX_FAILURE_RATIO:
        problems.append(f"failure ratio {stats.fail_ratio:.2%} > {MAX_FAILURE_RATIO:.0%}")
    if p95 > MAX_P95_MS:
        problems.append(f"p95 {p95:.0f} ms > {MAX_P95_MS:.0f} ms")
    if problems:
        print("LOAD TEST FAILED: " + "; ".join(problems))
        environment.process_exit_code = 1
    else:
        print(f"LOAD TEST PASSED: {stats.num_requests} requests, "
              f"failures {stats.fail_ratio:.2%}, p95 {p95:.0f} ms")
