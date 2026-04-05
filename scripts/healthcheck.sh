#!/bin/bash
# Post-startup health validation for DR.CODE-v2

echo "Running DR.CODE-v2 health checks..."

BACKEND_OK=$(curl -sf --max-time 10 http://localhost:8002/api/health && echo "OK" || echo "FAIL")
FRONTEND_OK=$(curl -sf --max-time 10 http://localhost:3001 && echo "OK" || echo "FAIL")

echo "Backend (8002): $BACKEND_OK"
echo "Frontend (3001): $FRONTEND_OK"

[ "$BACKEND_OK" = "OK" ] && [ "$FRONTEND_OK" = "OK" ] && exit 0 || exit 1
