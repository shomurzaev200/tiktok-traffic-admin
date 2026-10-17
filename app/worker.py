import os
import secrets
import shutil
from datetime import timedelta
from celery import Celery
from redis import Redis
from sqlalchemy import select, update
from .db import engine, tasks, schedules, errors, channels, notifications, now
from .service import add_task
from .telegram_service import sync_channel

redis_url=os.getenv('REDIS_URL','redis://redis:6379/0')
celery=Celery('traffic',broker=redis_url,backend=redis_url)
celery.conf.update(task_serializer='json',accept_content=['json'],result_serializer='json',task_track_started=True,
    task_acks_late=True,worker_prefetch_multiplier=1,broker_transport_options={'visibility_timeout':300},
    task_time_limit=120,task_soft_time_limit=100,beat_schedule={'dispatch':{'task':'traffic.dispatch','schedule':15.0}})

@celery.task(name='traffic.dispatch')
def dispatch():
    r=Redis.from_url(redis_url); r.set('heartbeat:scheduler','ACTIVE',ex=60); r.set('heartbeat:worker','ACTIVE',ex=60)
    claimed=[]
    with engine.begin() as c:
        # Lease recovery is safe: these jobs never publish comments or send messages.
        c.execute(update(tasks).where(tasks.c.status=='RUNNING',tasks.c.lease_until<now()).values(status='RETRY',due_at=now()))
        due=c.execute(select(schedules).where(schedules.c.enabled==True,schedules.c.next_run<=now()).with_for_update(skip_locked=True)).mappings().all()
        for schedule in due:
            add_task(c,schedule['kind'],key=f'schedule:{schedule["id"]}:{int(schedule["next_run"].timestamp())}')
            c.execute(update(schedules).where(schedules.c.id==schedule['id']).values(next_run=now()+timedelta(minutes=schedule['interval_minutes'])))
        rows=c.execute(select(tasks).where(tasks.c.status.in_(['PENDING','RETRY']),tasks.c.due_at<=now(),tasks.c.attempts<3)
            .order_by(tasks.c.id).limit(10).with_for_update(skip_locked=True)).mappings().all()
        for row in rows:
            c.execute(update(tasks).where(tasks.c.id==row['id']).values(status='RUNNING',attempts=row['attempts']+1,lease_until=now()+timedelta(minutes=3)))
            claimed.append(row['id'])
    for task_id in claimed: execute.delay(task_id)

@celery.task(name='traffic.execute')
def execute(task_id):
    with engine.connect() as c: row=c.execute(select(tasks).where(tasks.c.id==task_id)).mappings().first()
    if not row or row['status']!='RUNNING': return
    try:
        if row['kind']=='SYSTEM_CHECK':
            free=round(shutil.disk_usage('/').free/1024**3,2); result={'disk_free_gb':free}
            if free<5:
                with engine.begin() as c:
                    key='disk:'+now().strftime('%Y-%m-%d')
                    if not c.scalar(select(notifications.c.id).where(notifications.c.key==key)):
                        c.execute(notifications.insert().values(key=key,message='На диске менее 5 ГБ свободного места'))
        elif row['kind']=='TELEGRAM_SYNC':
            with engine.connect() as c: ids=c.execute(select(channels.c.id)).scalars().all()
            result={'channels':[sync_channel(i) for i in ids]}
        else: raise ValueError('UNSUPPORTED_TASK')
        with engine.begin() as c: c.execute(update(tasks).where(tasks.c.id==task_id,tasks.c.status=='RUNNING').values(status='SUCCESS',result=result))
    except Exception as error:
        # Never persist raw network exceptions: URLs may contain API secrets.
        transient=isinstance(error,(TimeoutError,ConnectionError))
        retry=transient and row['attempts']<3
        with engine.begin() as c:
            c.execute(update(tasks).where(tasks.c.id==task_id).values(status='RETRY' if retry else 'FAILED',last_error=type(error).__name__,due_at=now()+timedelta(seconds=30*2**row['attempts'])))
            c.execute(errors.insert().values(service='worker',code=type(error).__name__,message=f'Задача #{task_id} не выполнена; проверьте настройки интеграции',correlation_id=secrets.token_hex(12)))
