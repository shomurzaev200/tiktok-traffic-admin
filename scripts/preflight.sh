#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
. /etc/os-release
[[ "$ID" == ubuntu && "$VERSION_ID" == 24.04 ]] || { echo 'Нужна Ubuntu 24.04'; exit 1; }
case "$(uname -m)" in x86_64|aarch64) ;; *) echo 'Поддерживаются amd64 и arm64'; exit 1;; esac
available=$(df -PB1 . | awk 'NR==2 {print $4}')
[[ "$available" -ge 5368709120 ]] || { echo 'Нужно минимум 5 ГБ свободного места. Увеличьте EBS до сборки.'; exit 1; }
inode_free=$(df -Pi . | awk 'NR==2 {print $4}')
[[ "$inode_free" -ge 50000 ]] || { echo 'Недостаточно свободных inode'; exit 1; }
memory=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
[[ "$memory" -ge 1800000 ]] || { echo 'Нужно минимум 2 ГБ RAM; рекомендуется 4 ГБ для сборки Next.js'; exit 1; }
command -v python3 >/dev/null
echo 'Ресурсы проверены. Существующие данные не изменялись.'
