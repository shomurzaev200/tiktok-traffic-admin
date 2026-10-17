#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
bash scripts/preflight.sh
sudo -v
bash scripts/install-docker.sh
bash scripts/start.sh
echo 'Откройте админку на выбранном адресе и порту. Логин ADMIN_USER и первоначальный пароль ADMIN_PASSWORD находятся в .env.'
