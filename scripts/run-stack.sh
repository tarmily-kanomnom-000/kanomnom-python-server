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

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_dir="${repo_root}/apps/api"
dashboard_dir="${repo_root}/apps/dashboard"
fifo_path=""
dashboard_port="${DASHBOARD_PORT:-3000}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found in PATH. Install uv or load your virtual environment first." >&2
  exit 1
fi

package_runner="npm"
if command -v pnpm >/dev/null 2>&1; then
  package_runner="pnpm"
elif ! command -v npm >/dev/null 2>&1; then
  echo "Neither pnpm nor npm are available in PATH." >&2
  exit 1
fi

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
  if [[ -n "${fifo_path}" && -p "${fifo_path}" ]]; then
    rm -f "${fifo_path}"
  fi
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

fifo_path="$(mktemp -u)"
mkfifo "${fifo_path}"

forward_exit() {
  local name=$1
  local pid=$2
  if wait "${pid}"; then
    printf "%s:0\n" "${name}" >"${fifo_path}"
  else
    printf "%s:%s\n" "${name}" "$?" >"${fifo_path}"
  fi
}

forward_exit "api" "${api_pid}" &
forward_exit "dashboard" "${dashboard_pid}" &

IFS=":" read -r finished_service finished_code <"${fifo_path}"

if [[ "${finished_code}" -ne 0 ]]; then
  echo "${finished_service} exited with code ${finished_code}. Shutting down remaining services..." >&2
else
  echo "${finished_service} exited cleanly. Waiting for remaining services to finish..."
fi

wait "${api_pid}" "${dashboard_pid}" || true
