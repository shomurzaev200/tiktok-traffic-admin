#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
name="${1:-}"
[[ "$name" =~ ^traffic-[0-9TZ]+-[0-9]+\.dump$ ]] || { echo 'Укажите имя файла из backups, без пути'; exit 1; }
[[ -f "backups/$name" && -f "backups/$name.sha256" ]] || { echo 'Нет копии или контрольной суммы'; exit 1; }
(cd backups && sha256sum --check "$name.sha256")
echo 'Будет создана новая БД traffic_restore для проверки. Рабочая БД traffic не меняется.'
read -r -p 'Введите RESTORE_TEST: ' answer
[[ "$answer" == RESTORE_TEST ]] || exit 1
# createdb fails rather than overwriting an existing restore database.
sudo docker compose exec -T db createdb -U traffic traffic_restore
sudo docker compose exec -T db pg_restore --exit-on-error -U traffic -d traffic_restore < "backups/$name"
sudo docker compose exec -T db psql -U traffic -d traffic_restore -c '\dt'
echo 'Проверочная БД traffic_restore сохранена. Переключение production выполняется отдельно после проверки.'
