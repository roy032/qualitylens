"""Test data factory. Every name is unique so tests can run in any order, in parallel, and repeatedly."""
import uuid


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def new_user_payload(password: str = "Passw0rd!QA") -> dict:
    name = unique("user").replace("-", "_")
    return {
        "username": name,
        "email": f"{name}@example.com",
        "password": password,
        "must_change_password": False,
    }
