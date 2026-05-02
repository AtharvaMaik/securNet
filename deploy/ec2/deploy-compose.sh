#!/usr/bin/env bash
set -euo pipefail

APP_DIR=${APP_DIR:-/opt/security-observability-platform}
ENV_FILE=${ENV_FILE:-$APP_DIR/.env}

cd "$APP_DIR"
mkdir -p infra/runtime-logs

docker compose --env-file "$ENV_FILE" -f infra/docker-compose.yml pull || true
docker compose --env-file "$ENV_FILE" -f infra/docker-compose.yml up --build -d
