#!/usr/bin/env bash
set -euo pipefail
project_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
[[ "$project_dir" =~ ^/[a-zA-Z0-9_./-]+$ ]] || { echo 'Путь проекта должен быть без пробелов и специальных символов'; exit 1; }
sudo tee /etc/systemd/system/tiktok-traffic-backup.service >/dev/null <<EOF
[Unit]
Description=TikTok Traffic Admin database backup
After=docker.service
Requires=docker.service
[Service]
Type=oneshot
WorkingDirectory=$project_dir
ExecStart=/usr/bin/bash $project_dir/scripts/backup.sh
UMask=0077
EOF
sudo tee /etc/systemd/system/tiktok-traffic-backup.timer >/dev/null <<'EOF'
[Unit]
Description=Daily TikTok Traffic Admin backup
[Timer]
OnCalendar=*-*-* 03:00:00 UTC
Persistent=true
RandomizedDelaySec=300
[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now tiktok-traffic-backup.timer
sudo systemctl list-timers tiktok-traffic-backup.timer --no-pager
echo 'Ежедневное копирование включено. Копии не удаляются автоматически; следите за свободным местом и переносите их вне EC2.'
