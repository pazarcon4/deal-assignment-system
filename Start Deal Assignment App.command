#!/bin/bash
cd "$(dirname "$0")"

if [ -f .env ]; then
    set -a
    source .env
    set +a
else
    echo "No .env file found. Create one with DATABASE_URL=<your Supabase connection string> first."
    exit 1
fi

LAN_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)

echo "Starting Deal Assignment System..."
echo "(Leave this window open while you use the app. Close it to stop the app.)"
echo
if [ -n "$LAN_IP" ]; then
    echo "Share this link with your team (same network/VPN required): http://$LAN_IP:5050/"
else
    echo "Could not detect a LAN IP -- only this Mac will be able to reach the app."
fi
echo

# Open the browser after a short delay so the server has time to start
( sleep 2 && open "http://127.0.0.1:5050/" ) &

python3 app.py
