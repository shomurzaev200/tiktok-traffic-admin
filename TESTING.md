# Проверка и приёмка

Полная автоматическая проверка выполняется GitHub Actions на Ubuntu 24.04 с настоящим PostgreSQL и Docker. Не запускайте тесты интеграции на рабочей базе: они создают и изменяют записи.

```bash
python -m pip install -r requirements.txt pytest==8.3.5
# DATABASE_URL должен указывать на отдельную тестовую БД
alembic upgrade head
alembic upgrade head
python -m pytest -q tests/test_v2.py
python -m unittest discover -s tests -p test_direct.py -v
```

Frontend:

```bash
cd frontend
npm install --no-audit --no-fund
npm run typecheck
npm run lint
npm run build
```

Стек на staging:

```bash
sudo docker compose config --quiet
sudo docker compose up -d --build --wait --wait-timeout 300
sudo docker compose exec -T app python < scripts/smoke_v2.py
sudo docker compose --profile jobs up -d
sudo docker compose exec -T app python < scripts/smoke_jobs.py
bash scripts/backup.sh
# Укажите реальное имя копии из backups; подтвердите RESTORE_TEST
bash scripts/restore.sh traffic-YYYYMMDDTHHMMSSZ-PID.dump
```

Браузерный тест из frontend, при работающем staging на 127.0.0.1:8000 и корректных ADMIN_USER/ADMIN_PASSWORD в окружении:

```bash
npx playwright install --with-deps chromium
npx playwright test
```

Он входит, добавляет аккаунт, открывает разделы меню, выходит и сохраняет screenshots в test-results. Проверка screenshot человеком отдельно отмечается в CHECKS.

Live AI/Telegram тесты не выполняются автоматически и не расходуют чужие ключи. AI unit-тест подменяет HTTP-ответ явным mock; это не подтверждение работоспособности ключа/модели. Telegram attribution тест использует отдельно созданное тестовое событие и проверяет дедупликацию. Он не заменяет проверку live polling с правами бота.
