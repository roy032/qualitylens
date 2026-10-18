#!/usr/bin/env bash
# Start the target app and create the admin account the tests log in with.
# Safe to run more than once.
set -euo pipefail
cd "$(dirname "$0")/.."

ADMIN_USER="${QL_ADMIN_USER:-qa_admin}"
ADMIN_PASSWORD="${QL_ADMIN_PASSWORD:-QaAdmin#2026}"

docker compose up -d --wait

if docker compose exec -T -u git gitea gitea admin user list | awk '{print $2}' | grep -qx "$ADMIN_USER"; then
  echo "Admin user '$ADMIN_USER' already exists"
else
  docker compose exec -T -u git gitea gitea admin user create --admin \
    --username "$ADMIN_USER" --password "$ADMIN_PASSWORD" \
    --email "$ADMIN_USER@example.com" --must-change-password=false
fi

curl -fsS http://localhost:3000/api/v1/version && echo " <- Gitea is up"
