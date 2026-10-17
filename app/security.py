import hashlib
import os
import secrets
from datetime import timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException, Request
from sqlalchemy import select, delete
from .db import engine, users, sessions, now, audit

ph=PasswordHasher(time_cost=2,memory_cost=19456,parallelism=1)
ROLES={'SUPER_ADMIN':5,'ADMIN':4,'EDITOR':3,'ANALYST':2,'VIEWER':1}
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def aware(value): return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value

def bootstrap():
    with engine.begin() as c:
        if not c.execute(select(users.c.id).limit(1)).first():
            password=os.environ['ADMIN_PASSWORD']
            if len(password)<24: raise RuntimeError('ADMIN_PASSWORD must have at least 24 characters')
            c.execute(users.insert().values(username=os.getenv('ADMIN_USER','admin'),password_hash=ph.hash(password),role='SUPER_ADMIN'))

def current(request: Request):
    token=request.cookies.get('session','')
    with engine.connect() as c:
        row=c.execute(select(users,sessions.c.csrf,sessions.c.expires_at).join(sessions,users.c.id==sessions.c.user_id)
            .where(sessions.c.token_hash==digest(token),users.c.active==True)).mappings().first()
    if not row or aware(row['expires_at'])<now(): raise HTTPException(401,'Требуется вход')
    if request.method not in ('GET','HEAD','OPTIONS') and not secrets.compare_digest(request.headers.get('x-csrf-token',''),row['csrf']):
        raise HTTPException(403,'Обновите страницу: неверный CSRF-токен')
    return dict(row)

def require(user,role='EDITOR'):
    if ROLES.get(user['role'],0)<ROLES[role]: raise HTTPException(403,'Недостаточно прав')

def log(c,user,action,entity,entity_id=None):
    c.execute(audit.insert().values(actor_id=user['id'],action=action,entity=entity,entity_id=entity_id))

def verify(password,hashed):
    try: return ph.verify(hashed,password)
    except VerificationError: return False

def login(c,user):
    token=secrets.token_hex(32); csrf=secrets.token_hex(32)
    c.execute(sessions.insert().values(token_hash=digest(token),user_id=user['id'],csrf=csrf,expires_at=now()+timedelta(hours=12)))
    c.execute(delete(sessions).where(sessions.c.expires_at<now()))
    return token,csrf
