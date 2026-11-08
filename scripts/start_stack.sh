#!/usr/bin/env bash
# Start Agent API, Web development server, and the local Phase 2 CV node.
#
# Values in the project .env are loaded for local development. All runtime
# endpoints and local-node details are explicit environment configuration.

set -euo pipefail

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
log_dir="$project_root/runs/logs"

mkdir -p "$log_dir"

agent_pid=""
web_pid=""
cv_pid=""
frpc_pid=""

cleanup() {
    trap - EXIT INT TERM
    for pid in "$frpc_pid" "$cv_pid" "$web_pid" "$agent_pid"; do
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

# Prevent dead local proxy variables (e.g., 127.0.0.1:7890 when Clash is off)
# from breaking frpc tunnel or outbound LLM/Embedding requests.
if [[ "${http_proxy:-}${HTTP_PROXY:-}${https_proxy:-}${HTTPS_PROXY:-}" == *"127.0.0.1:7890"* ]]; then
    if ! (echo >/dev/tcp/127.0.0.1/7890) >/dev/null 2>&1; then
        unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
    fi
fi

: "${CV_NODE_TOKEN:?CV_NODE_TOKEN must be configured in .env}"
: "${AGENT_BIND_HOST:?AGENT_BIND_HOST must be configured in .env}"
: "${AGENT_PORT:?AGENT_PORT must be configured in .env}"
: "${AGENT_URL:?AGENT_URL must be configured in .env}"
: "${WEB_BIND_HOST:?WEB_BIND_HOST must be configured in .env}"
: "${WEB_PORT:?WEB_PORT must be configured in .env}"
: "${CV_NODE_ID:?CV_NODE_ID must be configured in .env}"
: "${CV_NODE_DISPLAY_NAME:?CV_NODE_DISPLAY_NAME must be configured in .env}"
: "${CV_CONTROL_PORT:?CV_CONTROL_PORT must be configured in .env}"
: "${CV_BIND_HOST:?CV_BIND_HOST must be configured in .env}"
: "${CV_NODE_CONTROL_URL:?CV_NODE_CONTROL_URL must be configured in .env}"
: "${CV_NODE_CAPACITY:?CV_NODE_CAPACITY must be configured in .env}"
: "${LOCAL_CAMERA_ID:?LOCAL_CAMERA_ID must be configured in .env}"
: "${LOCAL_CAMERA_DISPLAY_NAME:?LOCAL_CAMERA_DISPLAY_NAME must be configured in .env}"
: "${LOCAL_CAMERA_SOURCE:?LOCAL_CAMERA_SOURCE must be configured in .env}"
: "${LOCAL_CAMERA_SOURCE_TYPE:?LOCAL_CAMERA_SOURCE_TYPE must be configured in .env}"
cv_node_id=$CV_NODE_ID
cv_control_port=$CV_CONTROL_PORT
cv_capacity=$CV_NODE_CAPACITY
camera_id=$LOCAL_CAMERA_ID
cv_source=$LOCAL_CAMERA_SOURCE
export CV_NODE_ID="$cv_node_id"
export CV_CONTROL_PORT="$cv_control_port"
export CV_NODE_CAPACITY="$cv_capacity"
export CV_NODE_TOKEN
export AGENT_URL
: "${CV_ALLOWED_MEDIA_ROOTS:?CV_ALLOWED_MEDIA_ROOTS must be configured in .env}"
# Agent mounts this directory at /media; CV archives evidence beneath its
# snapshots child so snapshot_uri=snapshots/YYYYMMDD/*.jpg resolves directly.
: "${AGENT_MEDIA_ROOT:?AGENT_MEDIA_ROOT must be configured in .env}"
: "${CV_SNAPSHOT_DIR:?CV_SNAPSHOT_DIR must be configured in .env}"
mkdir -p "$CV_SNAPSHOT_DIR"

if curl --noproxy '*' --silent --fail "$AGENT_URL/docs" >/dev/null 2>&1; then
    echo "Agent URL is already serving a process; stop it before running start_stack.sh." >&2
    echo "Refusing to reuse an existing Agent because it may not contain the current code." >&2
    exit 1
fi

echo "Applying database migrations"
alembic upgrade head >"$log_dir/alembic.log" 2>&1

redis_url="${AGENT_REDIS_URL:-}"
if [[ -n "$redis_url" ]]; then
    if [[ "$redis_url" == *"127.0.0.1"* || "$redis_url" == *"localhost"* ]]; then
        if command -v redis-cli >/dev/null 2>&1; then
            if ! redis-cli ping >/dev/null 2>&1; then
                echo "Starting local redis-server..."
                service redis-server start >/dev/null 2>&1 || redis-server --daemonize yes >/dev/null 2>&1 || true
            fi
            if redis-cli ping >/dev/null 2>&1; then
                echo "Redis is online ($redis_url)"
            else
                echo "Warning: Redis is configured at $redis_url but unreachable; Agent will run in in-memory fallback mode." >&2
            fi
        fi
    else
        echo "Using remote Redis at $redis_url"
    fi
else
    echo "AGENT_REDIS_URL is not set; Agent will run in in-memory fallback mode."
fi

echo "Starting Agent API on $AGENT_URL"
python3 -m uvicorn agent.main:create_app --factory --host "$AGENT_BIND_HOST" --port "$AGENT_PORT" \
    >"$log_dir/agent.log" 2>&1 &
agent_pid=$!

node_online=false
for _ in {1..20}; do
    if ! kill -0 "$agent_pid" 2>/dev/null; then
        echo "Agent failed to start; see $log_dir/agent.log" >&2
        exit 1
    fi
    if curl --noproxy '*' --silent --fail "$AGENT_URL/docs" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl --noproxy '*' --silent --fail "$AGENT_URL/docs" >/dev/null 2>&1; then
    echo "Agent did not become ready; see $log_dir/agent.log" >&2
    exit 1
fi

echo "Starting Web development server on $WEB_BIND_HOST:$WEB_PORT"
(
    cd "$project_root/web"
    VITE_DEV_API_TARGET="$AGENT_URL" npm run dev -- --host "$WEB_BIND_HOST" --port "$WEB_PORT"
) >"$log_dir/web.log" 2>&1 &
web_pid=$!

echo "Registering local CV node: $cv_node_id"
node_payload=$(python3 -c 'import json, os; print(json.dumps({"node_id": os.environ["CV_NODE_ID"], "display_name": os.environ["CV_NODE_DISPLAY_NAME"], "control_url": os.environ["CV_NODE_CONTROL_URL"], "capacity": int(os.environ["CV_NODE_CAPACITY"]), "control_token": os.environ["CV_NODE_TOKEN"]}))')
node_status=$(curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}' \
    -X POST "$AGENT_URL/api/v1/cv-nodes" \
    -H 'Content-Type: application/json' -d "$node_payload")
if [[ "$node_status" != "201" && "$node_status" != "409" ]]; then
    echo "Failed to register local CV node (HTTP $node_status)" >&2
    exit 1
fi

echo "Starting CV Control node on $CV_NODE_CONTROL_URL"
CV_CONTROL_PORT="$cv_control_port" python3 -m uvicorn perception.control_api:create_control_app --factory --host "$CV_BIND_HOST" --port "$cv_control_port" \
    >"$log_dir/cv-control.log" 2>&1 &
cv_pid=$!

control_ready=false
for _ in {1..30}; do
    if ! kill -0 "$cv_pid" 2>/dev/null; then
        echo "CV Control failed to start; see $log_dir/cv-control.log" >&2
        exit 1
    fi
    if curl --noproxy '*' --silent --fail "$CV_NODE_CONTROL_URL/control/v1/health" \
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
    if curl --noproxy '*' --silent "$AGENT_URL/api/v1/cv-nodes" | grep -q '"node_id":"'"$cv_node_id"'".*"is_online":true'; then
        node_online=true
        break
    fi
    sleep 1
done

if [[ "$node_online" != true ]]; then
    echo "CV node did not report online within 20 seconds; see $log_dir/cv-control.log" >&2
    exit 1
fi

camera_payload=$(CAMERA_ID="$camera_id" CAMERA_SOURCE="$cv_source" python3 -c 'import json, os; print(json.dumps({"camera_id": os.environ["CAMERA_ID"], "display_name": os.environ["LOCAL_CAMERA_DISPLAY_NAME"], "node_id": os.environ["CV_NODE_ID"], "source_type": os.environ["LOCAL_CAMERA_SOURCE_TYPE"], "source_uri": os.environ["CAMERA_SOURCE"]}))')
camera_status=$(curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}' \
    -X POST "$AGENT_URL/api/v1/managed-cameras" \
    -H 'Content-Type: application/json' -d "$camera_payload")
if [[ "$camera_status" != "201" && "$camera_status" != "409" ]]; then
    echo "Failed to register local camera (HTTP $camera_status)" >&2
    exit 1
fi

start_status=$(curl --noproxy '*' --silent --output /dev/null --write-out '%{http_code}' \
    -X POST "$AGENT_URL/api/v1/cameras/$camera_id/monitoring:start")
if [[ "$start_status" != "202" ]]; then
    echo "Failed to start local camera session (HTTP $start_status)" >&2
    exit 1
fi

frpc_config_raw="${FRPC_CONFIG:-deploy/frp/frpc.toml}"
if [[ "$frpc_config_raw" = /* ]]; then
    frpc_config="$frpc_config_raw"
else
    frpc_config="$project_root/$frpc_config_raw"
fi
frp_enabled="${FRP_ENABLED:-}"
if [[ -z "$frp_enabled" ]]; then
    if [[ -f "$frpc_config" ]]; then
        frp_enabled="true"
    else
        frp_enabled="false"
    fi
fi

if [[ "$frp_enabled" == "true" ]]; then
    frpc_bin="${FRPC_BIN:-$(command -v frpc 2>/dev/null || echo "$HOME/.local/bin/frpc")}"
    if [[ ! -x "$frpc_bin" ]]; then
        echo "frpc binary not found or not executable at $frpc_bin; set FRPC_BIN or FRP_ENABLED=false in .env" >&2
        exit 1
    fi
    if [[ ! -f "$frpc_config" ]]; then
        echo "frpc config not found at $frpc_config; set FRPC_CONFIG or FRP_ENABLED=false in .env" >&2
        exit 1
    fi
    echo "Starting frpc tunnel with $frpc_config"
    "$frpc_bin" -c "$frpc_config" >"$log_dir/frpc.log" 2>&1 &
    frpc_pid=$!

    frpc_ready=false
    for _ in {1..15}; do
        if ! kill -0 "$frpc_pid" 2>/dev/null; then
            echo "frpc failed to start; see $log_dir/frpc.log" >&2
            exit 1
        fi
        if grep -q "start proxy success" "$log_dir/frpc.log" 2>/dev/null; then
            frpc_ready=true
            break
        fi
        sleep 1
    done

    if [[ "$frpc_ready" != true ]]; then
        echo "frpc did not establish tunnel within 15 seconds; see $log_dir/frpc.log" >&2
        exit 1
    fi
fi

echo "Stack started. Web: $WEB_BIND_HOST:$WEB_PORT; CV node: $cv_node_id${frpc_pid:+; frpc: active}"
echo "Logs: $log_dir"
echo "Press Ctrl+C to stop Agent, Web, CV Control${frpc_pid:+, and frpc}."

wait -n "$agent_pid" "$web_pid" "$cv_pid" ${frpc_pid:+"$frpc_pid"}
