import hashlib
import re
import secrets
from datetime import timedelta
from urllib.parse import urlsplit
from fastapi import HTTPException
from sqlalchemy import select, update, func
from .db import *
from .catalog import FIELDS, INTS, HIDDEN
from .security import log

def public(row): return {k:v for k,v in dict(row).items() if k not in HIDDEN}
def tiktok_url(value):
    try:
        p=urlsplit(value); h=(p.hostname or '').lower()
        valid=p.scheme=='https' and not p.username and not p.password and p.port in (None,443) and (h=='tiktok.com' or h.endswith('.tiktok.com'))
    except ValueError: valid=False
    if not valid: raise HTTPException(422,'Нужна HTTPS-ссылка на tiktok.com')
    return value

def validate(resource,data):
    allowed=FIELDS.get(resource,{})
    if not data or set(data)-set(allowed): raise HTTPException(422,'Недопустимые поля')
    result={}
    for key,value in data.items():
        if value is None or value=='':
            if key.endswith('_id'): result[key]=None
            elif key in INTS or key in ('budget','spend'): continue
            elif key in ('username','profile_url','url','name','chat_id','kind'): raise HTTPException(422,'Поле не может быть пустым: '+key)
            elif value=='': result[key]=''
            continue
        if isinstance(allowed[key],list) and value not in allowed[key]: raise HTTPException(422,'Недопустимое значение '+key)
        if key in INTS:
            try: value=int(value)
            except (TypeError,ValueError): raise HTTPException(422,'Ожидается целое число: '+key)
            if value<0 or (key=='interval_minutes' and value<5): raise HTTPException(422,'Недопустимое число: '+key)
        elif key in ('spend','budget'):
            try: value=float(value)
            except (TypeError,ValueError): raise HTTPException(422,'Ожидается число')
            import math
            if not math.isfinite(value) or value<0: raise HTTPException(422,'Расходы должны быть неотрицательными')
        elif key=='enabled':
            if not isinstance(value,bool): raise HTTPException(422,'Ожидается boolean')
        else:
            value=str(value).strip()
            if len(value)>4000: raise HTTPException(422,'Текст длиннее 4000 символов')
        if key in ('url','profile_url'): value=tiktok_url(value)
        if key=='username':
            value=value.lstrip('@')
            if not re.fullmatch(r'[\w.]{1,80}',value,re.ASCII): raise HTTPException(422,'Неверный username')
        if key=='chat_id' and not re.fullmatch(r'-100\d{5,20}',value): raise HTTPException(422,'Нужен числовой ID канала вида -100…')
        result[key]=value
    return result

def add_task(c,kind,payload=None,key=None):
    if kind not in ('SYSTEM_CHECK','TELEGRAM_SYNC','AI_GENERATION'): raise HTTPException(422,'Тип задачи не поддерживается')
    return c.execute(tasks.insert().values(kind=kind,payload=payload or {},idempotency_key=key or secrets.token_hex(24)).returning(tasks.c.id)).scalar_one()

def claim(c,draft_id,user):
    row=c.execute(update(drafts).where(drafts.c.id==draft_id,drafts.c.status.in_(['DRAFTED','REVIEW']),
        (drafts.c.claimed_by==None)|(drafts.c.claimed_by==user['id'])).values(claimed_by=user['id'],status='REVIEW').returning(drafts)).mappings().first()
    if not row: raise HTTPException(409,'Задача занята другим оператором или уже обработана')
    log(c,user,'claim','drafts',draft_id)
    return public(row)

def transition(c,draft_id,action,user,payload):
    row=c.execute(select(drafts).where(drafts.c.id==draft_id).with_for_update()).mappings().first()
    if not row: raise HTTPException(404,'Черновик не найден')
    if row['claimed_by']!=user['id']: raise HTTPException(409,'Сначала возьмите задачу в работу')
    allowed={'approve':('REVIEW','APPROVED'),'reject':('REVIEW','SKIPPED'),'release':('REVIEW','DRAFTED'),'publish-manual':('APPROVED','PUBLISHED')}
    if action not in allowed: raise HTTPException(422,'Неизвестное действие')
    before,after=allowed[action]
    if row['status']!=before: raise HTTPException(409,'Неверный текущий статус')
    values={'status':after}
    if action=='approve' and not row['text'].strip(): raise HTTPException(422,'Пустой ответ нельзя одобрить')
    if action=='release': values['claimed_by']=None
    if action=='publish-manual':
        result_url=tiktok_url(str(payload.get('result_url','')))
        if payload.get('confirmed') is not True: raise HTTPException(422,'Подтвердите, что опубликовали ответ вручную')
        values.update(result_url=result_url,published_at=now())
        c.execute(publications.insert().values(draft_id=draft_id,idempotency_key=hashlib.sha256(f'manual:{draft_id}'.encode()).hexdigest(),
            operator_id=user['id'],result_url=result_url))
    c.execute(update(drafts).where(drafts.c.id==draft_id).values(**values))
    log(c,user,action,'drafts',draft_id)
    return {'status':after,'verification':'operator_reported' if action=='publish-manual' else None}

def analytics(c,days=30):
    since=now()-timedelta(days=days)
    rows=[]
    for campaign in c.execute(select(campaigns).order_by(campaigns.c.id).limit(500)).mappings():
        tracked=c.scalar(select(func.count()).select_from(clicks.join(links,links.c.id==clicks.c.link_id)).where(links.c.campaign_id==campaign['id'],clicks.c.created_at>=since))
        joins=c.scalar(select(func.count(func.distinct(events.c.user_hash))).where(events.c.campaign_id==campaign['id'],events.c.kind=='JOIN',events.c.created_at>=since))
        leaves=c.scalar(select(func.count()).where(events.c.campaign_id==campaign['id'],events.c.kind=='LEAVE',events.c.created_at>=since))
        rows.append({'id':campaign['id'],'name':campaign['name'],'clicks':tracked,'joins':joins,'leaves':leaves,
            'conversion':round(100*joins/tracked,2) if tracked else None,'spend':campaign['spend'],
            'cost_per_subscriber':round(campaign['spend']/joins,2) if joins else None})
    daily=c.execute(select(func.date(events.c.created_at).label('day'),events.c.kind,func.count().label('count'))
        .where(events.c.created_at>=since).group_by(func.date(events.c.created_at),events.c.kind).order_by(func.date(events.c.created_at))).mappings().all()
    return {'campaigns':rows,'daily':[dict(x) for x in daily],'days':days,'attribution':'Only received Telegram events. Manual publications are operator reports; clicks are requests, not unique people.',
        'retention':None,'subscriber_history':None}
