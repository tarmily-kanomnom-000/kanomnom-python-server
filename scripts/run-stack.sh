#!/usr/bin/env bash
set -euo pipefail

mode="${1:-}"
if [[ -z "${mode}" ]]; then
  echo "Usage: $(basename "$0") <dev|prod>" >&2
  exit 64
fi

if [[ "${mode}" != "dev" && "${mode}" != "prod" ]]; then
  echo "Unknown mode: ${mode}. Expected dev or prod." >&2
  exit 64
fi

if [[ "${mode}" == "dev" ]]; then
  export FASTAPI_ENV="${FASTAPI_ENV:-development}"
  export TELEGRAM_BOT_ENABLED="${TELEGRAM_BOT_ENABLED:-0}"
else
  export FASTAPI_ENV="${FASTAPI_ENV:-production}"
  export TELEGRAM_BOT_ENABLED="${TELEGRAM_BOT_ENABLED:-1}"
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_dir="${repo_root}/apps/api"
dashboard_dir="${repo_root}/apps/dashboard"
dashboard_port="${DASHBOARD_PORT:-3000}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found in PATH. Install uv or load your virtual environment first." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is not available in PATH." >&2
  exit 1
fi
package_runner="npm"

api_pid=""
dashboard_pid=""

cleanup() {
  local exit_code=$1
  trap - EXIT INT TERM
  if [[ -n "${api_pid}" ]] && kill -0 "${api_pid}" >/dev/null 2>&1; then
    echo "Stopping FastAPI service (pid ${api_pid})"
    kill "${api_pid}" >/dev/null 2>&1 || true
  fi
  if [[ -n "${dashboard_pid}" ]] && kill -0 "${dashboard_pid}" >/dev/null 2>&1; then
    echo "Stopping dashboard (pid ${dashboard_pid})"
    kill "${dashboard_pid}" >/dev/null 2>&1 || true
  fi
  wait >/dev/null 2>&1 || true
  exit "${exit_code}"
}

trap 'cleanup "$?"' EXIT
trap 'cleanup 130' INT TERM

(
  cd "${api_dir}"
  if [[ "${mode}" == "dev" ]]; then
    echo "Starting FastAPI service in dev mode from ${api_dir}"
    uv run fastapi dev src/app.py --host 0.0.0.0 --port 6969
  else
    echo "Starting FastAPI service in prod mode from ${api_dir}"
    uv run fastapi run src/app.py --host 0.0.0.0 --port 6969
  fi
) &
api_pid=$!

(
  cd "${dashboard_dir}"
  if [[ "${mode}" == "dev" ]]; then
    echo "Starting dashboard dev server using ${package_runner} from ${dashboard_dir}"
    PORT="${dashboard_port}" ${package_runner} run dev -- --port "${dashboard_port}"
  else
    echo "Building dashboard for production using ${package_runner}"
    ${package_runner} run build
    echo "Starting dashboard production server using ${package_runner}"
    PORT="${dashboard_port}" ${package_runner} run start -- -p "${dashboard_port}"
  fi
) &
dashboard_pid=$!

finished_service=""
finished_code=0
remaining_pid=""

if wait -n "${api_pid}" "${dashboard_pid}"; then
  finished_code=0
else
  finished_code=$?
fi

if ! kill -0 "${api_pid}" >/dev/null 2>&1; then
  finished_service="api"
  remaining_pid="${dashboard_pid}"
elif ! kill -0 "${dashboard_pid}" >/dev/null 2>&1; then
  finished_service="dashboard"
  remaining_pid="${api_pid}"
fi

if [[ -z "${finished_service}" ]]; then
  finished_service="unknown"
fi

if [[ "${finished_code}" -ne 0 ]]; then
  echo "${finished_service} exited with code ${finished_code}. Shutting down remaining services..." >&2
  if [[ -n "${remaining_pid}" ]] && kill -0 "${remaining_pid}" >/dev/null 2>&1; then
    kill "${remaining_pid}" >/dev/null 2>&1 || true
  fi
else
  echo "${finished_service} exited cleanly. Waiting for remaining services to finish..."
fi

if [[ -n "${remaining_pid}" ]] && kill -0 "${remaining_pid}" >/dev/null 2>&1; then
  wait "${remaining_pid}" || true
fi

exit "${finished_code}"
