#!/usr/bin/env bash

tms-api() {
  cat > "$HOME/code/flow-ops-tms/api/.env" << ENV
DATABASE_URL=postgresql+asyncpg://oms_user:oms_dev_password@localhost:5433/flow_ops_tms
OMS_DATABASE_URL=postgresql+asyncpg://oms_user:oms_dev_password@localhost:5433/flow_ops_oms
OMS_API_URL=http://localhost:8000/api/v1
SECRET_KEY=tms-dev-secret-key-change-in-prod
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ENV
  cd "$HOME/code/flow-ops-tms/api"
  uv run uvicorn app.main:app --reload --port 8001 --host 0.0.0.0
}

tms-web() {
  cat > "$HOME/code/flow-ops-tms/web/.env.local" << ENV
NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1
ENV
  cd "$HOME/code/flow-ops-tms/web"
  npm run dev -- --hostname 0.0.0.0
}

export -f tms-api
export -f tms-web
