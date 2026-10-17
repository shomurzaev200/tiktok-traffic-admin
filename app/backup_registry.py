"""Best-effort metadata only; dump correctness never depends on web runtime."""
import re
import sys
from .db import engine, backups
name,size,checksum=sys.argv[1:]
if not re.fullmatch(r'traffic-[0-9TZ]+-[0-9]+\.dump',name) or not re.fullmatch(r'[a-f0-9]{64}',checksum):
    raise ValueError('Invalid backup metadata')
with engine.begin() as c:
    c.execute(backups.insert().values(filename=name,sha256=checksum,bytes=int(size),status='VERIFIED'))
