"""Create secrets once; never overwrite an existing configuration."""
import os
from pathlib import Path
import secrets

target = Path(__file__).resolve().parents[1] / '.env'
with target.open('x', encoding='utf-8', newline='\n') as f:
    f.write(f'POSTGRES_PASSWORD={secrets.token_hex(32)}\nADMIN_USER=admin\n'
            f'ADMIN_PASSWORD={secrets.token_hex(32)}\nAPP_PORT=8000\n')
os.chmod(target, 0o600)
print('Created .env. Read ADMIN_PASSWORD locally; do not share this file.')
