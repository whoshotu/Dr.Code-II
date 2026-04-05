#!/bin/bash
# Sends a realistic mock GitHub PR webhook to local backend
# Usage: ./scripts/test_webhook.sh [port]

set -e

PORT=${1:-8002}
PAYLOAD='{
  "action": "opened",
  "pull_request": {
    "number": 42,
    "title": "feat: add antigravity module",
    "head": {"sha": "abc123def456", "ref": "feature/antigravity"},
    "base": {"ref": "main"},
    "user": {"login": "dr-code-bot"},
    "body": "This PR adds the antigravity module with full test coverage."
  },
  "repository": {
    "full_name": "test-org/dr-code-v2",
    "name": "dr-code-v2",
    "private": false
  },
  "sender": {"login": "dr-code-bot"}
}'

echo "Sending mock PR webhook to http://localhost:$PORT/api/integrations/git/webhook"
echo "---"

RESPONSE=$(curl -s --max-time 10 -o /tmp/webhook_response_body.json -w "%{http_code}" \
  -X POST "http://localhost:$PORT/api/integrations/git/webhook" \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: pull_request" \
  -H "X-Hub-Signature-256: sha256=test_bypass" \
  -d "$PAYLOAD" || echo "000")

if [ "$RESPONSE" = "000" ]; then
  echo "ERROR: Cannot connect to backend at http://localhost:$PORT"
  echo "Is the backend running? Start with: cd backend && uvicorn server:app --port $PORT"
  exit 1
fi

echo "HTTP Status: $RESPONSE"
echo "---"

if [ -s /tmp/webhook_response_body.json ]; then
  python3 -m json.tool /tmp/webhook_response_body.json 2>/dev/null || cat /tmp/webhook_response_body.json
else
  echo "(empty response body)"
fi

echo "---"

if [ "$RESPONSE" = "200" ]; then
  echo "Webhook accepted successfully"
else
  echo "Webhook returned unexpected status: $RESPONSE"
  exit 1
fi
