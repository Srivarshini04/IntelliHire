#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "Starting infrastructure..."
docker compose -f "$ROOT/docker-compose.yml" up -d postgres redis qdrant

echo "Waiting for Postgres..."
until docker compose -f "$ROOT/docker-compose.yml" exec -T postgres pg_isready -U delulu > /dev/null 2>&1; do
  sleep 1
done

echo "Infrastructure ready."
echo ""
echo "Backend:  cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app --reload"
echo "Frontend: cd frontend && npm install && npm run dev"
