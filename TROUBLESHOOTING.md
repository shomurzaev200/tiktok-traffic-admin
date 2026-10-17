# Диагностика

```bash
bash scripts/diagnostics.sh
```

- No space left: `df -h /`, `df -i /`, `lsblk`; увеличьте EBS и ext4 по инструкции AWS, затем восстановите dpkg. Автоматической очистки пользовательских данных нет.
- docker.service отсутствует: установлен только клиент; `bash scripts/install-docker.sh` устанавливает и движок. Запуск проверяется `sudo docker info`.
- app restarting: `sudo docker compose logs --tail=120 app`. Сначала исправьте исключение; изменения AWS-порта не исправляют падение приложения.
- Ошибка миграции: сохраните backup и полный traceback без .env. Миграция повторно запускается через Alembic; при успехе повтор безопасен.
- Connection refused: `sudo docker compose ps -a`, `sudo docker compose port app 8000`, проверка `/health/ready` на сервере. Для прямого порта APP_HOST=0.0.0.0 и Security Group TCP8000/My IP.
- Тайм-аут снаружи при работающем локальном health: проверьте текущий public IP EC2, Security Group, IP клиента и firewall. Не открывайте 5432/6379.
- Ошибка входа: первоначальные ADMIN_USER/ADMIN_PASSWORD из .env. Смена .env не меняет пароль уже созданного пользователя. При HTTPS COOKIE_SECURE=true, при прямом HTTP false.
- CSRF 403: обновите страницу и войдите заново. VIEWER/ANALYST не могут менять данные.
- 409 при создании: уникальный username/URL/comment ID или неверный FK. Нельзя удалить запись, на которую ссылается история.
- Чужой оператор занял черновик: он должен освободить REVIEW через release. Обход резерва через UI не разрешён.
- Telegram: токен, числовой chat_id, права администратора/can_invite_users; один polling на токен, отсутствие другого webhook. Неверные секреты автоматически бесконечно не повторяются.
- AI: provider, model, API key, доступ модели и квота провайдера; лимит за скользящие 24 часа. Без ключа редактируйте вручную.
- Задачи PENDING: нужен COMPOSE_PROFILES=jobs и рабочие Redis/worker/scheduler. Время dispatch до 15 секунд.
- Ошибка сборки Next.js с exit 137: недостаточно памяти; рекомендуется 4 ГБ для сборки. Не объявляйте сборку успешной до получения exit 0.

Никогда не публикуйте `cat .env`, полный `docker compose config` или приватный ключ. Команда `docker compose config --quiet` проверяет конфигурацию без вывода секретов.
