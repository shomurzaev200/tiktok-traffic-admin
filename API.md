# API

OpenAPI: GET `/api/openapi.json` после входа. Все `/api/*` кроме login требуют действующей сессии; изменяющие запросы требуют `X-CSRF-Token`, полученный из login/me. Политика ролей проверяется backend независимо от видимости кнопок.

- POST `/api/auth/login` — JSON username/password; возвращает cookie, csrf и пользователя.
- GET `/api/auth/me`; POST `/api/auth/logout`.
- GET `/api/catalog` — разрешённые поля и русские заголовки форм.
- GET `/api/data/{resource}?q=…&before=ID&limit=50` — keyset pagination, максимум 100, сортировка ID DESC.
- POST `/api/data/{resource}`; PATCH/DELETE `/api/data/{resource}/{id}` — CRUD только разрешённых справочников. Секретные поля не принимаются.
- POST `/api/drafts` — source_comment_id/account_id/text.
- PATCH `/api/drafts/{id}` — текст, только оператором, взявшим задачу.
- POST `/api/drafts/{id}/claim|approve|reject|release`.
- POST `/api/drafts/{id}/publish-manual` — JSON confirmed=true/result_url; сохраняет отчёт оператора.
- POST `/api/drafts/{id}/generate-ai` — один запрос к настроенному AI.
- GET `/api/drafts/{id}/context` — текст, аккаунт, видео для ручной публикации.
- POST `/api/users`; PATCH `/api/users/{id}`; POST `/api/users/{id}/revoke` — SUPER_ADMIN.
- POST `/api/accounts/{id}/pause|resume` — локальная пауза реестра.
- POST `/api/tasks` — kind SYSTEM_CHECK/TELEGRAM_SYNC; POST `/api/tasks/{id}/retry|cancel`.
- POST `/api/telegram/channels/{id}/sync`; POST `/api/telegram/invite-links` с campaign_id.
- GET `/api/dashboard/summary`, `/api/analytics/overview?days=30`, `/api/system/status`, `/api/integrations`, `/api/legacy`.
- POST `/api/notifications/{id}/resolve`, `/api/errors/{id}/resolve`.
- GET `/api/export/{resource}` — до 100 тыс. записей CSV с защитой от formula injection; требуется ANALYST или выше.
- GET `/r/{slug}` — публичный отслеживаемый редирект, без произвольной целевой ссылки из запроса.
- GET `/health/live`, `/health/ready`, `/healthz` — без авторизации, минимум сведений.

Роли: VIEWER — чтение; ANALYST — чтение/CSV; EDITOR — подготовка и модерация; ADMIN — настройки, каналы, расписания, удаление, задачи; SUPER_ADMIN — управление пользователями. Удаление связанных записей запрещается внешними ключами; история не удаляется generic CRUD.

Ошибки: `detail` в JSON; 401 вход, 403 роль/CSRF, 409 дубль/конфликт, 422 валидация, 429 лимит, 502 внешняя интеграция, 503 БД. Сырой SQL и токены не выдаются пользователю.
