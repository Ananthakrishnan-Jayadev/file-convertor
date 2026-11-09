#!/usr/bin/env bash
# Update File Converter on the server to the latest code on GitHub.
#   On the server:     ~/file-convertor/deploy/deploy.sh
#   From the laptop:   ssh ananthu@192.168.1.113 '~/file-convertor/deploy/deploy.sh'
# Files being converted at that moment are marked as failed after the restart; nothing else is lost.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT=$(grep -E '^FC_PORT=' .env 2>/dev/null | cut -d= -f2 || true)
PORT=${PORT:-8010}

# The container runs as your user and writes here, so it has to exist and be yours.
mkdir -p data

echo "Fetching the latest code..."
git pull --ff-only

echo "Building and restarting (the first build takes several minutes)..."
docker compose up -d --build

# Old images from earlier builds take space; drop the dangling ones.
docker image prune -f >/dev/null

echo -n "Waiting for File Converter to answer"
for _ in $(seq 1 45); do
  if curl -fs -o /dev/null "http://127.0.0.1:${PORT}/api/formats" 2>/dev/null; then
    echo " - up at http://$(hostname -I | awk '{print $1}'):${PORT}"
    exit 0
  fi
  echo -n "."; sleep 2
done
echo
echo "File Converter didn't answer within 90 seconds. Its log:" >&2
docker compose logs --tail 40 fileconvert >&2
exit 1
