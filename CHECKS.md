# Фактические проверки — 18 октября 2026

Проверенный код: `b0dfd5d13b3eda5ad43adb918c62d965a75c411e`, ветка neon-v2. Последующие изменения относятся только к документации.

**GitHub Actions: SUCCESS** — [полный прогон](https://github.com/shomurzaev200/tiktok-traffic-admin/actions/runs/39080240769).

Среда: GitHub-hosted Ubuntu 24.04, Python 3.12, Node 22, настоящий PostgreSQL 16 и Docker. Рабочий EC2 пользователя в этих тестах не использовался.

| Проверка | Результат |
|---|---|
| Установка Python-зависимостей | PASS |
| bash -n всех shell-скриптов | PASS |
| compileall app/migrations/scripts | PASS |
| Alembic upgrade head на пустой тестовой БД | PASS |
| Повторный Alembic upgrade head | PASS |
| pytest tests/test_v2.py | **8 passed** |
| Регрессионные прямые тесты первой версии | **6 passed** |
| TypeScript tsc --noEmit | PASS |
| ESLint | PASS, без warnings/errors |
| Next.js production static build | PASS |
| Docker Compose config с профилем jobs | PASS |
| Сборка Linux Docker image | PASS |
| PostgreSQL и app health checks | PASS |
| HTTP smoke: вход, сессия, CRUD, дубли, резерв, одобрение, отчёт ручной публикации | PASS |
| Сохранение количества аккаунтов после restart app | PASS |
| Повторный HTTP smoke после restart | PASS |
| Redis + Celery + scheduler: выполнение SYSTEM_CHECK | PASS |
| pg_dump custom backup + pg_restore --list + SHA256 | PASS |
| Восстановление в отдельную traffic_restore | PASS |
| Playwright Chromium: вход, добавление аккаунта, переход по всем разделам, выход | **1 passed**, 3.2 s |
| Снимки интерфейса из E2E | Сохранены в [neon-evidence](https://github.com/shomurzaev200/tiktok-traffic-admin/actions/runs/39080240769/artifacts/12118184564) |
| Локальная структура ZIP, CRC, отсутствие .env, генерация секретов без перезаписи | PASS |

Интеграционные тесты проверяют SQLAlchemy foreign keys против реальной схемы PostgreSQL, запрет удаления связанного аккаунта, две конкурентные попытки claim с результатом 200/409, RBAC, CSRF, уникальный ключ комментария, единственную запись ручной публикации, Telegram update deduplication, расчёт аналитики, импорт CSV и отчёты. Для AI явно используется mock HTTP; это не реальный вызов модели.

## NOT TESTED / ограничения

- Реальные Telegram Bot API/polling с токеном и администраторскими правами.
- Реальные OpenAI/Gemini ключи, модели, квоты, стоимость и региональная доступность.
- TikTok OAuth и API-публикация: не реализованы; аккаунты только в ручном реестре.
- Установка на текущий EC2, существующие локальные изменения Compose и фактическая причина прежнего app Restarting: серверные логи не предоставлены.
- Совместимость с копией реальной production-БД пользователя: старые таблицы не удаляются кодом миграции, но конкретный дамп не получен.
- Live HTTPS, внешний firewall/Security Group, публичный порт пользователя.
- Systemd backup timer на реальном сервере: проверен синтаксис скрипта, таймер на EC2 не устанавливался.
- Нагрузочный тест 100 тыс. видео/1 млн событий; отзывчивость на 2 ГБ RAM и сборка на малом EC2.
- Визуальный просмотр screenshot человеком: NOT TESTED. Снимки созданы CI, но локальная загрузка для просмотра была отклонена политикой разрешений; автоматический браузерный тест прошёл.
- Полный независимый security audit и полное соответствие всему MASTER PROMPT V2 не заявляются. Подробности — COVERAGE.md.

Все тестовые аккаунты/события/ключи относятся только к изолированной CI-среде. Ничего не отправлялось в TikTok и реальные Telegram-чаты; production-секреты не использовались.
