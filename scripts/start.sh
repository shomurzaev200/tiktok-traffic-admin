#!/usr/bin/env bash
# First launch and subsequent starts; existing .env and database are preserved.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ ! -f .env ]]; then
  python3 scripts/init_env.py
fi
chmod 600 .env
sudo docker compose config --quiet
sudo docker compose up -d --build --wait --wait-timeout 180
sudo docker compose ps
sudo docker compose exec -T app python -c 'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8000/healthz").read().decode())'
echo 'Started. Admin credentials are in .env. Access through your SSH tunnel.'
