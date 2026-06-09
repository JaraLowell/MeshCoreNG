#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVER_SCRIPT="${SCRIPT_DIR}/tcp_bridge_server.py"
PID_FILE="${TCP_BRIDGE_PID_FILE:-${REPO_DIR}/.tcp_bridge_server.pid}"
LOG_DIR="${TCP_BRIDGE_LOG_DIR:-${REPO_DIR}/logs}"
LOG_FILE="${TCP_BRIDGE_LOG_FILE:-${LOG_DIR}/tcp_bridge_server.log}"

HOST="${TCP_BRIDGE_HOST:-0.0.0.0}"
PORT="${TCP_BRIDGE_PORT:-4200}"
STATUS_HOST="${TCP_BRIDGE_STATUS_HOST:-0.0.0.0}"
STATUS_PORT="${TCP_BRIDGE_STATUS_PORT:-8080}"
CLIENT_TIMEOUT="${TCP_BRIDGE_CLIENT_TIMEOUT:-180}"
STATUS_INTERVAL="${TCP_BRIDGE_STATUS_INTERVAL:-60}"
PASSWORD="${TCP_BRIDGE_PASSWORD:-}"
EXTRA_ARGS="${TCP_BRIDGE_EXTRA_ARGS:-}"

is_running() {
  [[ -f "${PID_FILE}" ]] || return 1
  local pid
  pid="$(cat "${PID_FILE}")"
  [[ -n "${pid}" ]] || return 1
  kill -0 "${pid}" 2>/dev/null
}

start_server() {
  if is_running; then
    echo "TCP bridge server is already running, pid $(cat "${PID_FILE}")"
    return 0
  fi

  mkdir -p "${LOG_DIR}"

  local args=(
    "${SERVER_SCRIPT}"
    --host "${HOST}"
    --port "${PORT}"
    --status-host "${STATUS_HOST}"
    --status-port "${STATUS_PORT}"
    --client-timeout "${CLIENT_TIMEOUT}"
    --status-interval "${STATUS_INTERVAL}"
  )

  if [[ -n "${PASSWORD}" ]]; then
    args+=(--password "${PASSWORD}")
  fi

  # shellcheck disable=SC2086
  nohup python3 "${args[@]}" ${EXTRA_ARGS} >>"${LOG_FILE}" 2>&1 &
  echo "$!" >"${PID_FILE}"
  echo "TCP bridge server started, pid $(cat "${PID_FILE}")"
  echo "Log: ${LOG_FILE}"
}

stop_server() {
  if ! is_running; then
    echo "TCP bridge server is not running"
    rm -f "${PID_FILE}"
    return 0
  fi

  local pid
  pid="$(cat "${PID_FILE}")"
  kill "${pid}"

  for _ in {1..20}; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      rm -f "${PID_FILE}"
      echo "TCP bridge server stopped"
      return 0
    fi
    sleep 0.25
  done

  echo "TCP bridge server did not stop after 5s, sending SIGKILL"
  kill -9 "${pid}" 2>/dev/null || true
  rm -f "${PID_FILE}"
}

status_server() {
  if is_running; then
    echo "TCP bridge server is running, pid $(cat "${PID_FILE}")"
    echo "Status page: http://${STATUS_HOST}:${STATUS_PORT}/"
    echo "Log: ${LOG_FILE}"
  else
    echo "TCP bridge server is not running"
  fi
}

case "${1:-}" in
  start)
    start_server
    ;;
  stop)
    stop_server
    ;;
  restart)
    stop_server
    start_server
    ;;
  status)
    status_server
    ;;
  logs)
    mkdir -p "${LOG_DIR}"
    touch "${LOG_FILE}"
    tail -f "${LOG_FILE}"
    ;;
  *)
    cat <<EOF
Usage: $(basename "$0") {start|stop|restart|status|logs}

Environment variables:
  TCP_BRIDGE_HOST             default: 0.0.0.0
  TCP_BRIDGE_PORT             default: 4200
  TCP_BRIDGE_STATUS_HOST      default: 0.0.0.0
  TCP_BRIDGE_STATUS_PORT      default: 8080
  TCP_BRIDGE_PASSWORD         optional
  TCP_BRIDGE_CLIENT_TIMEOUT   default: 180
  TCP_BRIDGE_STATUS_INTERVAL  default: 60
  TCP_BRIDGE_LOG_FILE         default: ./logs/tcp_bridge_server.log
  TCP_BRIDGE_EXTRA_ARGS       optional extra tcp_bridge_server.py args

Examples:
  tools/tcp_bridge_server_ctl.sh start
  TCP_BRIDGE_PASSWORD=secret tools/tcp_bridge_server_ctl.sh start
  tools/tcp_bridge_server_ctl.sh logs
EOF
    exit 2
    ;;
esac
