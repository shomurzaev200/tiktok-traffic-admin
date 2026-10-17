#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
umask 077
mkdir -p backups
name="traffic-$(date -u +%Y%m%dT%H%M%SZ)-$$.dump"
tmp="backups/$name.partial"
trap 'echo "Резервная копия не завершена: проверьте файл .partial" >&2' ERR
sudo docker compose exec -T db pg_dump -U traffic -d traffic -Fc > "$tmp"
sudo docker compose exec -T db pg_restore --list < "$tmp" >/dev/null
mv -- "$tmp" "backups/$name"
(cd backups && sha256sum "$name" > "$name.sha256")
size=$(stat -c%s "backups/$name")
checksum=$(sha256sum "backups/$name" | awk '{print $1}')
if ! sudo docker compose exec -T app python -m app.backup_registry "$name" "$size" "$checksum"; then
  echo 'Копия проверена, но метаданные в админке не зарегистрированы (приложение может быть недоступно).'
fi
echo "Копия: backups/$name. Сохраните её и .env отдельно от EC2. Автоматического удаления копий нет."
