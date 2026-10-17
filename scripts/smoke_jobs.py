"""Run inside app with jobs profile active. No external messages are sent."""
import os
import time
import uuid
from sqlalchemy import select, func
from redis import Redis
from app.db import engine, tasks
from app.service import add_task

redis=Redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=2)
assert redis.ping()
with engine.begin() as c:
    task_id=add_task(c,'SYSTEM_CHECK',key='smoke-jobs-'+uuid.uuid4().hex)
deadline=time.monotonic()+75
while time.monotonic()<deadline:
    with engine.connect() as c: row=c.execute(select(tasks).where(tasks.c.id==task_id)).mappings().one()
    if row['status']=='SUCCESS':
        assert 'disk_free_gb' in row['result']
        print('PASS: Redis, Celery worker, scheduler dispatch, database-backed task execution')
        break
    if row['status']=='FAILED': raise AssertionError(row['last_error'])
    time.sleep(2)
else: raise AssertionError('Worker did not process the task within 75 seconds')
