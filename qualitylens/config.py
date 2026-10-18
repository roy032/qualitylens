"""All environment-specific values live here so tests never hard-code them."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    base_url: str = os.getenv("QL_BASE_URL", "http://localhost:3000")
    admin_user: str = os.getenv("QL_ADMIN_USER", "qa_admin")
    admin_password: str = os.getenv("QL_ADMIN_PASSWORD", "QaAdmin#2026")
    db_dsn: str = os.getenv("QL_DB_DSN", "postgresql://gitea:gitea@localhost:5432/gitea")

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/api/v1"


settings = Settings()
