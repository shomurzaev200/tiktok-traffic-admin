# EC2 / обновление v1 → neon-v2

Не заменяйте работающий сервер до успешного CI. Ветка neon-v2 отдельная; main содержит прежнюю версию. Нужны минимум 2 ГБ RAM и 5 ГБ свободного диска, рекомендуется 4 ГБ RAM и EBS 30 ГБ.

Для новой установки см. README. Для прямого доступа: .env APP_HOST=0.0.0.0, APP_PORT=8000, COOKIE_SECURE=false; Security Group TCP8000/My IP. Пароль вводится в форме, HTTP Basic заменён на сессию. HTTPS отдельно.

Для существующего проекта сначала сохраните БД и конфигурацию **до смены ветки**:

```bash
cd /home/ubuntu/tiktok-traffic-admin
umask 077
mkdir -p backups
sudo docker compose exec -T db pg_dump -U traffic -d traffic -Fc > backups/pre-neon.dump
sudo docker compose exec -T db pg_restore --list < backups/pre-neon.dump
cp .env backups/pre-neon.env
cp compose.yaml backups/pre-neon-compose.yaml
git rev-parse HEAD > backups/pre-neon-commit.txt
```

Если использовали ровно изменение привязки 127.0.0.1 на 0.0.0.0 из чата, перенесите его в .env:

```bash
grep -q '^APP_HOST=' .env || echo 'APP_HOST=0.0.0.0' >> .env
git diff -- compose.yaml
```

Убедитесь, что diff содержит **только эту строку порта**, тогда восстановите исходный Compose (копия уже сохранена):

```bash
git restore -- compose.yaml
git fetch origin
git switch --track origin/neon-v2
bash scripts/start.sh
bash scripts/healthcheck.sh
sudo docker compose exec -T app python < scripts/smoke_v2.py
```

Если есть другие локальные изменения, остановитесь и сохраните/перенесите их вручную; не используйте reset --hard. Команда git restore здесь относится только к проверенному изменению порта и уже сделанной копии.

Следующие обновления neon-v2: `bash scripts/update.sh`. Скрипт делает backup до pull, не перезаписывает .env, не удаляет volumes. Для профиля jobs добавьте COMPOSE_PROFILES=jobs в .env; для Telegram после задания токена COMPOSE_PROFILES=jobs,integrations.

Существующие items/audit сохраняются; в новых таблицах нет выдуманных аккаунтов/кампаний. Вход первоначально по прежним ADMIN_USER/ADMIN_PASSWORD. Добавление реестра аккаунта не выполняет TikTok OAuth.

Откат: остановите app/worker/scheduler/telegram-bot и восстановите из pre-neon dump в отдельную БД на staging; используйте сохранённую версию кода/Compose и только затем переключайте production. Старая версия и старые таблицы не удаляются миграцией.
