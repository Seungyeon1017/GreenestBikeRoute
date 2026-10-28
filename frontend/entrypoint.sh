#!/bin/sh

# Replace the build-time placeholder with the backend URL for this container.
API_URL="${NEXT_PUBLIC_GREENEST_API_URL:-http://127.0.0.1:8001}"
find /app/.next -type f -print0 | xargs -0 sed -i "s#NEXT_PUBLIC_GREENEST_API_URL#$API_URL#g"

echo "Starting App (backend: $API_URL)"
exec "$@"
