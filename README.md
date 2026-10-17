# TikTok Traffic Admin — Ubuntu 24.04 / AWS EC2

Самостоятельно собранный проект: исходный `tiktok-traffic-admin.zip` из старого чата недоступен. Это рабочая минимальная админка ручной модерации: реестр ссылок TikTok, название кампании/Telegram-канала, заметки, четыре статуса, журнал действий и CSV. FastAPI обслуживает интерфейс и формы; PostgreSQL хранит данные в постоянном Docker volume.

Проект не получает комментарии из TikTok, не отправляет комментарии, не публикует видео, не собирает статистику подписчиков Telegram. Решение approved — локальная отметка модератора. API TikTok и OAuth пока не подключены; никаких ключей TikTok для запуска не требуется. Разрешённые интеграции можно добавить отдельно после получения необходимых разрешений приложения и пользователей.

## 1. Подготовка EC2

Ubuntu Server 24.04, архитектура amd64 или arm64. Практический ориентир: 2 ГБ RAM, 20 ГБ EBS; меньшие ресурсы могут ограничить сборку. Проблема прежнего диска считается решённой, никаких команд удаления данных здесь нет.

В AWS Security Group разрешите входящий TCP 22 только с вашего IP. Порты 8000 и 5432 открывать не нужно: приложение слушает только loopback сервера, база не публикует порт. Для установки нужны исходящие HTTPS/DNS. SSH-ключ храните на своём компьютере.

## 2. Загрузка с Windows (PowerShell)

### Вариант без ZIP: скачать прямо на сервер с GitHub

Репозиторий: https://github.com/shomurzaev200/tiktok-traffic-admin

После входа по SSH на Ubuntu 24.04 выполните для первого развёртывания:

```bash
set -e
sudo apt-get update
sudo apt-get install -y git python3
cd /home/ubuntu
test ! -e tiktok-traffic-admin
git clone https://github.com/shomurzaev200/tiktok-traffic-admin.git
cd tiktok-traffic-admin
bash scripts/install-docker.sh
bash scripts/start.sh
sudo docker compose exec -T app python < scripts/smoke.py
cat .env
```

`test ! -e` останавливает этот блок, если папка уже существует: не перезаписывайте существующее развёртывание. Для повторного запуска уже установленного проекта достаточно `cd /home/ubuntu/tiktok-traffic-admin && bash scripts/start.sh`. Скрипт сохраняет существующий .env и базу.

Далее откройте туннель по разделу 4. Вместо клонирования можно использовать ZIP по инструкции ниже.

Скачайте ZIP из ответа и замените три значения ниже на свои. `EC2_PUBLIC_IP` — публичный IPv4/DNS из AWS, а не адрес вида 172.31.x.x.

```powershell
$Key = 'C:\Users\YOUR_NAME\Downloads\your-key.pem'
$Server = 'EC2_PUBLIC_IP'
$Archive = 'C:\Users\YOUR_NAME\Downloads\tiktok-traffic-admin.zip'
scp -i "$Key" "$Archive" "ubuntu@${Server}:/home/ubuntu/tiktok-traffic-admin.zip"
ssh -i "$Key" "ubuntu@$Server"
```

Дальнейшие команды выполняйте в SSH на Ubuntu:

```bash
sudo apt-get update
sudo apt-get install -y unzip python3
cd /home/ubuntu
# Для первого запуска; если папка уже существует, сначала сохраните её и .env.
test ! -e tiktok-traffic-admin && unzip tiktok-traffic-admin.zip
cd /home/ubuntu/tiktok-traffic-admin
bash scripts/install-docker.sh
sudo docker --version
sudo docker compose version
```

Установщик рассчитан на чистую Ubuntu 24.04 и официальный репозиторий Docker. Если Docker уже установлен, он ничего не меняет. Если `docker compose version` не работает, проверьте происхождение установленного Docker, прежде чем заменять пакеты.

## 3. Конфигурация и запуск

```bash
cd /home/ubuntu/tiktok-traffic-admin
python3 scripts/init_env.py
chmod 600 .env
# Посмотрите пароль на своём терминале; не отправляйте .env в чат.
cat .env
sudo docker compose config --quiet
sudo docker compose up -d --build --wait --wait-timeout 180
sudo docker compose ps
curl --fail http://127.0.0.1:8000/healthz
```

Ожидается `{"status":"ok"}`, оба контейнера healthy. Повторный запуск генератора .env намеренно завершится ошибкой FileExistsError: существующие пароли не перезаписываются. Не запускайте `cp .env.example .env` после генератора.

Поля `.env`: POSTGRES_PASSWORD — пароль БД, ADMIN_USER — логин админки (по умолчанию admin), ADMIN_PASSWORD — пароль админки, APP_PORT — локальный порт сервера (8000). Генератор создаёт разные случайные пароли по 64 hex-символа. Не меняйте POSTGRES_PASSWORD после инициализации volume без согласованной смены пароля роли PostgreSQL: переменная не меняет пароль существующей БД.

## 4. SSH-туннель и вход

На Windows откройте **второе** окно PowerShell:

```powershell
$Key = 'C:\Users\YOUR_NAME\Downloads\your-key.pem'
$Server = 'EC2_PUBLIC_IP'
ssh -i "$Key" -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:8000:127.0.0.1:8000 "ubuntu@$Server"
```

Оставьте окно открытым. В браузере откройте http://127.0.0.1:8000, логин admin и ADMIN_PASSWORD из .env. HTTP Basic защищён SSH-туннелем; приложение предназначено для одного доверенного администратора. Для выхода закройте приватное окно браузера: Basic Auth может кэшироваться браузером. Для публичного доступа необходимы отдельная HTTPS-конфигурация и усиление авторизации; текущую привязку loopback менять не нужно.

Если локальный порт занят, используйте `-L 127.0.0.1:8001:127.0.0.1:8000` и откройте http://127.0.0.1:8001. Если изменили APP_PORT на сервере, замените последнее 8000 в туннеле.

## 5. Проверка реального стека на сервере

```bash
sudo docker compose exec -T app python < scripts/smoke.py
```

Ожидается PASS: проверяются БД через HTTP, защита входа, CSRF, добавление, экранирование HTML, смена статуса, аудит и CSV. Тест оставляет одну запись SMOKE со статусом done для проверки сохранения. Затем:

```bash
sudo docker compose restart app
sudo docker compose ps
```

Запись должна остаться в админке. После перезагрузки EC2 Docker и контейнеры запускаются автоматически. IP EC2 может измениться при остановке/старте, если не используется Elastic IP.

## 6. Диагностика

```bash
cd /home/ubuntu/tiktok-traffic-admin
sudo docker compose ps -a
sudo docker compose logs --tail=100 app db
sudo docker compose config --quiet
curl -i http://127.0.0.1:8000/healthz
sudo docker compose exec -T db pg_isready -U traffic -d traffic
df -h
df -i
free -h
sudo docker system df
sudo systemctl status docker --no-pager
```

- `401` на `/` без пароля — ожидаемое поведение; `/healthz` доступен без пароля.
- `403` при сохранении — обновите страницу и повторите; другая вкладка могла обновить CSRF cookie.
- `password authentication failed` — проверьте соответствие .env существующей БД. Не удаляйте volume.
- `port already allocated` — проверьте `sudo ss -ltnp` или смените APP_PORT, затем повторите `sudo docker compose up -d`.
- `permission denied` для Docker — используйте sudo, как в инструкции.
- Сборка не скачивает пакеты — проверьте интернет, DNS, исходящие правила EC2.
- Завершение с кодом 137 — проверьте RAM и `sudo journalctl -k --no-pager -n 100`.
- Браузер не открывается — сначала добейтесь успешного curl на сервере, затем проверьте SSH-туннель, IP и TCP 22.

Не публикуйте вывод полного `docker compose config`: он может содержать секреты. Логи не содержат паролей приложения, но могут включать введённые вами данные и адреса.

## 7. Остановка, резервная копия, восстановление

```bash
# Остановка с сохранением БД
sudo docker compose down
# Повторный запуск
sudo docker compose up -d --wait
# Резервная копия (содержит пользовательские данные)
umask 077
mkdir -p backups
sudo docker compose exec -T db pg_dump -U traffic -d traffic > "backups/traffic-$(date +%F-%H%M%S).sql"
```

Сохраните резервную копию и .env вне EC2 в защищённом месте. Не используйте `docker compose down -v`: это удаляет БД. Восстановление предназначено для **пустой** БД нового развёртывания. До первого запуска app поднимите только db и выполните:

```bash
sudo docker compose up -d db --wait
# Замените имя файла на существующую резервную копию
sudo docker compose exec -T db psql -v ON_ERROR_STOP=1 -U traffic -d traffic < backups/traffic-YYYY-MM-DD-HHMMSS.sql
sudo docker compose up -d --build --wait
```

Схема создаётся при старте транзакционно через CREATE TABLE IF NOT EXISTS; для этой первой версии отдельный сервис миграций не нужен. При будущих изменениях схемы потребуются версионные миграции.

## 8. Структура и проверки

`compose.yaml`, `Dockerfile`, `.env.example`, `requirements.txt`, `app/main.py`, `scripts/init_env.py`, `scripts/install-docker.sh`, `scripts/smoke.py`, `tests/test_app.py`, `CHECKS.md`.

Для локальных тестов с Python 3.12:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt httpx==0.28.1
python -m unittest discover -s tests -v
```

Фактически выполненные проверки и ограничения — в CHECKS.md. Локальные тесты подменяют БД; реальный интеграционный тест выполняется командой из раздела 5. Верхнеуровневые зависимости зафиксированы, транзитивные зависимости и теги базовых образов могут обновляться; это не побитово воспроизводимая сборка.

## Официальные источники

- Установка Docker на Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Compose plugin: https://docs.docker.com/compose/install/linux/
- TikTok Content Posting API: https://developers.tiktok.com/doc/content-posting-api-get-started/

Для будущей публикации через TikTok необходимы зарегистрированное приложение, соответствующий продукт/разрешения и требования TikTok к согласию и проверке приложения. В текущем проекте интеграция намеренно отсутствует: ручная работа доступна сразу, без неофициальных API, прокси и обхода ограничений.
