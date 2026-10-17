"""Restore only the known legacy binding edit, after saving APP_HOST in .env."""
from pathlib import Path
import subprocess
path=Path('compose.yaml')
head=subprocess.check_output(['git','show','HEAD:compose.yaml'],text=True)
local=path.read_text()
known=head.replace('127.0.0.1:${APP_PORT:-8000}:8000','0.0.0.0:${APP_PORT:-8000}:8000')
if local==known and local!=head:
    path.write_text(head,encoding='utf-8',newline='\n')
