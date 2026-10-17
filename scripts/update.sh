#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
bash scripts/preflight.sh
sudo docker compose config --quiet
sudo docker compose exec -T db pg_isready -U traffic -d traffic
bash scripts/backup.sh
umask 077
cp -- .env "backups/env-$(date -u +%Y%m%dT%H%M%SZ)-$$"
git rev-parse HEAD > backups/previous-commit.txt
# Record the port chosen in v1 before switching to variable binding.
if ! grep -q '^APP_HOST=' .env; then
  if grep -q '0\.0\.0\.0:' compose.yaml; then echo 'APP_HOST=0.0.0.0' >> .env; else echo 'APP_HOST=127.0.0.1' >> .env; fi
fi
git fetch origin
# The only legacy local edit handled automatically is the known port binding.
python3 scripts/preserve_port.py
git diff --quiet || { echo 'Есть локальные изменения; остановка без перезаписи. Сохраните их отдельно.'; exit 1; }
git pull --ff-only
bash scripts/start.sh
bash scripts/healthcheck.sh
