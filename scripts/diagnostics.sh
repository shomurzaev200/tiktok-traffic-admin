#!/usr/bin/env bash
set -u
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
df -h /
df -i /
free -h
sudo docker compose version
sudo docker compose ps -a
sudo docker compose logs --tail=80 app db
