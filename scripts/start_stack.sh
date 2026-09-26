#!/usr/bin/env bash
# Start Agent API, Web development server, and the local Phase 2 CV node.
#
# Usage:
#   ./scripts/start_stack.sh [camera_id] [video_or_rtsp_source]
#
# Values in the project .env are loaded for local development.  The CV node
# values below are deliberately local-only defaults; remote nodes are registered
# through the Web management page instead.

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
camera_id=${1:-cam_field_01}
cv_source=${2:-tests/fixtures/sample_walk.mp4}
log_dir="$project_root/runs/logs"

mkdir -p "$log_dir"

agent_pid=""
web_pid=""
cv_pid=""

cleanup() {
    trap - EXIT INT TERM
    for pid in "$cv_pid" "$web_pid" "$agent_pid"; do
        if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done
}

trap cleanup EXIT INT TERM

cd "$project_root"

if [[ -f "$project_root/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$project_root/.env"
    set +a
fi

: "${AGENT_ADMIN_TOKEN:?AGENT_ADMIN_TOKEN must be configured in .env}"
: "${CV_NODE_TOKEN:?CV_NODE_TOKEN must be configured in .env}"
cv_node_id=${CV_NODE_ID:-cv-local-01}
cv_control_port=${CV_CONTROL_PORT:-8100}
cv_capacity=${CV_NODE_CAPACITY:-1}
export CV_NODE_ID="$cv_node_id"
export CV_CONTROL_PORT="$cv_control_port"
export CV_NODE_CAPACITY="$cv_capacity"
export CV_NODE_TOKEN
export AGENT_URL="${AGENT_URL:-http://127.0.0.1:8000}"
export CV_ALLOWED_MEDIA_ROOTS="${CV_ALLOWED_MEDIA_ROOTS:-$project_root}"
# Agent mounts this directory at /media; CV archives evidence beneath its
# snapshots child so snapshot_uri=snapshots/YYYYMMDD/*.jpg resolves directly.
export AGENT_MEDIA_ROOT="${AGENT_MEDIA_ROOT:-$project_root/runs/media}"
export CV_SNAPSHOT_DIR="${CV_SNAPSHOT_DIR:-$AGENT_MEDIA_ROOT/snapshots}"
mkdir -p "$CV_SNAPSHOT_DIR"

if curl --noproxy '*' --silent --fail http://127.0.0.1:8000/docs >/dev/null 2>&1; then
    echo "Agent port 8000 is already serving a process; stop it before running start_stack.sh." >&2
    echo "Refusing to reuse an existing Agent because it may not contain the current code." >&2
    exit 1
fi

echo "Starting Agent API on http://127.0.0.1:8000"
python3 -m uvicorn agent.main:create_app --factory --host 0.0.0.0 --port 8000 \
    >"$log_dir/agent.log" 2>&1 &
agent_pid=$!

node_online=false
for _ in {1..20}; do
    if ! kill -0 "$agent_pid" 2>/dev/null; then
        echo "Agent failed to start; see $log_dir/agent.log" >&2
        exit 1
    fi
    if curl --noproxy '*' --silent --fail http://127.0.0.1:8000/docs >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl --noproxy '*' --silent --fail http://127.0.0.1:8000/docs >/dev/null 2>&1; then
    echo "Agent did not become ready; see $log_dir/agent.log" >&2
    exit 1
fi

echo "Starting Web development server on http://127.0.0.1:5173"
(
    cd "$project_root/web"
    npm run dev
) >"$log_dir/web.log" 2>&1 &
web_pid=$!

echo "Registering local CV node: $cv_node_id"
node_payload=$(python3 -c 'import json, os; print(json.dumps({"node_id": os.environ["CV_NODE_ID"], "display_name": "本机 CV 节点", "control_url": "http://127.0.0.1:" + os.environ["CV_CONTROL_PORT"], "capacity": int(os.environ["CV_NODE_CAPACITY"]), "control_token": os.environ["CV_NODE_TOKEN"]}))')
node_status=$(curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}' \
    -X POST http://127.0.0.1:8000/api/v1/cv-nodes \
    -H "Authorization: Bearer $AGENT_ADMIN_TOKEN" -H 'Content-Type: application/json' -d "$node_payload")
if [[ "$node_status" != "201" && "$node_status" != "409" ]]; then
    echo "Failed to register local CV node (HTTP $node_status)" >&2
    exit 1
fi

echo "Starting CV Control node on http://127.0.0.1:$cv_control_port"
CV_CONTROL_PORT="$cv_control_port" python3 -m uvicorn perception.control_api:create_control_app --factory --host 0.0.0.0 --port "$cv_control_port" \
    >"$log_dir/cv-control.log" 2>&1 &
cv_pid=$!

control_ready=false
for _ in {1..30}; do
    if ! kill -0 "$cv_pid" 2>/dev/null; then
        echo "CV Control failed to start; see $log_dir/cv-control.log" >&2
        exit 1
    fi
    if curl --noproxy '*' --silent --fail "http://127.0.0.1:$cv_control_port/control/v1/health" \
        -H "Authorization: Bearer $CV_NODE_TOKEN" >/dev/null 2>&1; then
        control_ready=true
        break
    fi
    sleep 1
done

if [[ "$control_ready" != true ]]; then
    echo "CV Control did not become ready within 30 seconds; see $log_dir/cv-control.log" >&2
    exit 1
fi

node_online=false
for _ in {1..20}; do
    if ! kill -0 "$cv_pid" 2>/dev/null; then
        echo "CV Control failed to start; see $log_dir/cv-control.log" >&2
        exit 1
    fi
    if curl --noproxy '*' --silent http://127.0.0.1:8000/api/v1/cv-nodes -H "Authorization: Bearer $AGENT_ADMIN_TOKEN" | grep -q '"node_id":"'"$cv_node_id"'".*"is_online":true'; then
        node_online=true
        break
    fi
    sleep 1
done

if [[ "$node_online" != true ]]; then
    echo "CV node did not report online within 20 seconds; see $log_dir/cv-control.log" >&2
    exit 1
fi

camera_payload=$(CAMERA_ID="$camera_id" CAMERA_SOURCE="$cv_source" python3 -c 'import json, os; print(json.dumps({"camera_id": os.environ["CAMERA_ID"], "display_name": "本地样例摄像头", "node_id": os.environ["CV_NODE_ID"], "source_type": "file", "source_uri": os.environ["CAMERA_SOURCE"]}))')
camera_status=$(curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}' \
    -X POST http://127.0.0.1:8000/api/v1/managed-cameras \
    -H "Authorization: Bearer $AGENT_ADMIN_TOKEN" -H 'Content-Type: application/json' -d "$camera_payload")
if [[ "$camera_status" != "201" && "$camera_status" != "409" ]]; then
    echo "Failed to register local camera (HTTP $camera_status)" >&2
    exit 1
fi

start_status=$(curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}' \
    -X POST "http://127.0.0.1:8000/api/v1/cameras/$camera_id/monitoring:start" \
    -H "Authorization: Bearer $AGENT_ADMIN_TOKEN")
if [[ "$start_status" != "202" ]]; then
    echo "Failed to start local camera session (HTTP $start_status)" >&2
    exit 1
fi

echo "Stack started. Web: http://127.0.0.1:5173; CV node: $cv_node_id"
echo "Logs: $log_dir"
echo "Press Ctrl+C to stop Agent, Web, and CV Control."

wait "$cv_pid"
