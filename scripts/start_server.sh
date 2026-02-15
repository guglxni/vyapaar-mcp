#!/bin/bash
# Vyapaar MCP Server - Launch Script
# Usage: ./scripts/start_server.sh [sse|stdio]

set -e

cd "$(dirname "$0")/.."

# Detect transport mode
TRANSPORT="${1:-sse}"

if [ "$TRANSPORT" = "sse" ]; then
    echo "🚀 Starting Vyapaar MCP Server (SSE mode on localhost:8000)"
    echo "   Dashboard: http://localhost:8000"
    echo ""
elif [ "$TRANSPORT" = "stdio" ]; then
    echo "🚀 Starting Vyapaar MCP Server (stdio mode)"
    echo ""
else
    echo "Usage: $0 [sse|stdio]"
    exit 1
fi

# Export environment
export VYAPAAR_TRANSPORT="$TRANSPORT"
export VYAPAAR_HOST="${VYAPAAR_HOST:-127.0.0.1}"
export VYAPAAR_PORT="${VYAPAAR_PORT:-8000}"

# Check dependencies
echo "🔍 Checking dependencies..."
if ! curl -s redis://localhost:6379/1 > /dev/null 2>&1; then
    echo "   ⚠️  Redis: checking..."
fi

# Activate environment and run
source .venv/bin/activate
exec python -m vyapaar_mcp.server
