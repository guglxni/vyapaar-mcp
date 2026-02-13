#!/bin/bash
# Start ngrok tunnel for local Razorpay webhook development
# Uses environment variable from .env for secure token handling

set -e

echo "🔐 Vyapaar MCP — Secure Tunnel Startup"
echo "========================================"

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found"
    echo "   Please copy .env.example to .env and fill in your credentials"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | grep -v '^$' | xargs)

# Check if NGROK_AUTHTOKEN is set
if [ -z "$NGROK_AUTHTOKEN" ] || [ "$NGROK_AUTHTOKEN" = "your_ngrok_authtoken_here" ]; then
    echo "❌ Error: NGROK_AUTHTOKEN not configured"
    echo "   Please add your ngrok authtoken to .env:"
    echo "   1. Get token from: https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "   2. Add to .env: NGROK_AUTHTOKEN=your_actual_token"
    exit 1
fi

# Check if ngrok.yml exists
if [ ! -f ngrok.yml ]; then
    echo "❌ Error: ngrok.yml not found"
    echo "   The tunnel configuration file is missing"
    exit 1
fi

echo "✅ Configuration loaded"
echo "✅ Starting ngrok tunnel on port 8000 (HTTPS only)..."
echo ""
echo "📋 Next steps after tunnel starts:"
echo "   1. Copy the HTTPS forwarding URL (https://xxxxx.ngrok-free.app)"
echo "   2. Configure Razorpay webhook: Settings > Webhooks"
echo "   3. Set webhook URL to: https://xxxxx.ngrok-free.app/webhook/razorpay"
echo "   4. Generate and save a secure webhook secret:"
echo "      openssl rand -hex 32"
echo "   5. Update .env with VYAPAAR_RAZORPAY_WEBHOOK_SECRET"
echo ""
echo "Press Ctrl+C to stop the tunnel"
echo "========================================"
echo ""

# Start ngrok using config file
ngrok start --config ngrok.yml vyapaar-mcp
