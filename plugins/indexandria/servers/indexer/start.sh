#!/usr/bin/env bash
# Start the Indexandria MCP server (HTTP mode on port 21517)
#
# Usage:
#   ./start.sh           Start on default port 21517
#   ./start.sh 9000      Start on custom port
#   ./start.sh stop      Stop the running server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-21517}"
PID_FILE="${HOME}/.indexandria/server.pid"

mkdir -p "${HOME}/.indexandria"

start_server() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Indexandria is already running (PID $(cat "$PID_FILE"))"
        echo "URL: http://localhost:${PORT}/mcp"
        return 0
    fi

    echo "Starting Indexandria on http://localhost:${PORT}/mcp ..."

    cd "$SCRIPT_DIR"
    UV_CACHE_DIR="${HOME}/.indexandria/uv-cache" \
    INDEXER_DB_PATH="${HOME}/.indexandria/index.db" \
    INDEXANDRIA_PORT="$PORT" \
        nohup uv run server.py --port "$PORT" \
        > "${HOME}/.indexandria/server.log" 2>&1 &

    echo $! > "$PID_FILE"
    sleep 2

    if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "Indexandria started (PID $(cat "$PID_FILE"))"
        echo "URL: http://localhost:${PORT}/mcp"
        echo "Logs: ~/.indexandria/server.log"
    else
        echo "ERROR: Server failed to start. Check ~/.indexandria/server.log"
        rm -f "$PID_FILE"
        exit 1
    fi
}

stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID="$(cat "$PID_FILE")"
        if kill -0 "$PID" 2>/dev/null; then
            kill "$PID"
            echo "Indexandria stopped (PID $PID)"
        else
            echo "Indexandria is not running (stale PID file)"
        fi
        rm -f "$PID_FILE"
    else
        echo "Indexandria is not running"
    fi
}

case "${1:-}" in
    stop)
        stop_server
        ;;
    *)
        start_server
        ;;
esac
