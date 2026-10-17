import csv
import io
import os
import secrets
import shutil
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, Depends, HTTPException, Body, Query
from fastapi.responses import JSONResponse, RedirectResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, update, delete, func, inspect, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from .db import *
from .security import current, require, bootstrap, verify, login, digest, log, ph, ROLES
from .service import public, validate, tiktok_url, claim, transition, analytics, add_task
from .catalog import FIELDS, LABELS

@asynccontextmanager
async def lifespan(app):
    bootstrap()
    yield

app=FastAPI(title='TikTok Traffic Admin v2',version='2.0',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
attempts=defaultdict(deque)

@app.middleware('http')
async def protection(request,call_next):
    if request.headers.get('content-length','').isdigit() and int(request.headers['content-length'])>262144:
        return JSONResponse({'detail':'Слишком большой запрос'},413)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    return response

@app.exception_handler(IntegrityError)
async def conflict(request,error): return JSONResponse({'detail':'Дубликат или неверная ссылка на связанную запись'},409)

@app.exception_handler(SQLAlchemyError)
async def db_error(request,error):
    correlation=secrets.token_hex(12)
    try:
        with engine.begin() as c: c.execute(errors.insert().values(service='backend',code=type(error).__name__,message='Ошибка доступа к базе данных',correlation_id=correlation))
    except Exception: pass
    return JSONResponse({'detail':'Ошибка базы данных. Проверьте журналы контейнера и миграции.','correlation_id':correlation},503)

@app.post('/api/auth/login')
def sign_in(request:Request,data:dict=Body(...)):
    ip=request.client.host if request.client else 'unknown'
    window=attempts[ip]; tick=time.monotonic()
    while window and window[0]<tick-300: window.popleft()
    if len(window)>=10: raise HTTPException(429,'Слишком много попыток; подождите 5 минут')
    window.append(tick)
    username=str(data.get('username',''))[:80]; password=str(data.get('password',''))[:512]
    with engine.begin() as c:
        user=c.execute(select(users).where(users.c.username==username,users.c.active==True)).mappings().first()
        if not user:
            verify(password,ph.hash('invalid-account-placeholder'))
            raise HTTPException(401,'Неверный логин или пароль')
        if not verify(password,user['password_hash']): raise HTTPException(401,'Неверный логин или пароль')
        token,csrf=login(c,user); log(c,user,'login','users',user['id'])
    response=JSONResponse({'user':{k:user[k] for k in ('id','username','role')},'csrf':csrf})
    response.set_cookie('session',token,httponly=True,samesite='strict',secure=os.getenv('COOKIE_SECURE','false')=='true',max_age=43200)
    return response

@app.get('/api/auth/me')
def me(user=Depends(current)):
    return {'user':{k:user[k] for k in ('id','username','role')},'csrf':user['csrf']}

@app.post('/api/auth/logout')
def logout(request:Request,user=Depends(current)):
    with engine.begin() as c: c.execute(delete(sessions).where(sessions.c.token_hash==digest(request.cookies.get('session',''))))
    response=JSONResponse({'ok':True}); response.delete_cookie('session'); return response

@app.get('/api/openapi.json')
def openapi(user=Depends(current)): return app.openapi()

@app.get('/health/live')
def live(): return {'status':'ok'}

@app.get('/healthz')
@app.get('/health/ready')
def ready():
    try:
        with engine.connect() as c:
            c.execute(text('SELECT 1'))
            revision=c.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
        if revision!='0001_neon': raise ValueError('revision')
    except Exception: raise HTTPException(503,'БД или миграции не готовы')
    return {'status':'ok'}

@app.get('/api/catalog')
def catalog(user=Depends(current)): return {'fields':FIELDS,'labels':LABELS,'role':user['role']}

@app.get('/api/preferences')
def preferences(user=Depends(current)):
    with engine.connect() as c:
        rows={row['name']:row['value'] for row in c.execute(select(settings)).mappings()}
    return {'disable_animations':rows.get('disable_animations','false').lower()=='true','report_note':rows.get('report_note','')}

@app.post('/api/import/{resource}')
def import_records(resource:str,data:dict=Body(...),user=Depends(current)):
    require(user)
    from .reports import import_csv
    return import_csv(resource,str(data.get('csv_text','')),user)

@app.get('/api/analytics/export/{kind}')
def report(kind:str,days:int=Query(30,ge=1,le=365),user=Depends(current)):
    require(user,'ANALYST')
    from .reports import export_report
    return export_report(kind,days)

@app.get('/api/system/status')
def status(user=Depends(current)):
    ready()
    result={'backend':'OK','postgres':'OK','disk_free_gb':round(shutil.disk_usage('/').free/1024**3,2),
        'tiktok':'MANUAL_ONLY: OAuth и публикация API не настроены',
        'telegram':'CONFIGURED_NOT_VERIFIED' if os.getenv('TELEGRAM_BOT_TOKEN') else 'NOT_CONFIGURED',
        'ai':'MANUAL_ONLY'}
    try:
        from redis import Redis
        r=Redis.from_url(os.getenv('REDIS_URL','redis://redis:6379/0'),socket_connect_timeout=1,socket_timeout=1)
        result['redis']='OK' if r.ping() else 'UNAVAILABLE'
        for name in ('worker','scheduler','telegram_bot'):
            result[name]=r.get('heartbeat:'+name).decode() if r.get('heartbeat:'+name) else 'NOT_RUNNING'
    except Exception: result.update(redis='UNAVAILABLE',worker='UNKNOWN',scheduler='UNKNOWN')
    return result

@app.get('/api/dashboard/summary')
def summary(user=Depends(current)):
    with engine.connect() as c:
        counts={key:c.scalar(select(func.count()).select_from(TABLES[key])) for key in ('accounts','creators','videos','drafts','campaigns','tasks','errors')}
        counts['manual_publications']=c.scalar(select(func.count()).select_from(publications))
        counts['connected_accounts']=c.scalar(select(func.count()).where(accounts.c.token_encrypted!=None))
        counts['telegram_joins']=c.scalar(select(func.count()).where(events.c.kind=='JOIN'))
    return counts

@app.get('/api/analytics/overview')
def overview(days:int=Query(30,ge=1,le=365),user=Depends(current)):
    with engine.connect() as c: return analytics(c,days)

@app.get('/api/data/{resource}')
def listing(resource:str,q:str='',before:int|None=None,limit:int=Query(50,ge=1,le=100),user=Depends(current)):
    if resource not in TABLES: raise HTTPException(404,'Раздел не найден')
    if resource in ('users','settings','backups'): require(user,'ADMIN')
    table=TABLES[resource]; query=select(table).order_by(table.c.id.desc()).limit(limit+1)
    if before is not None: query=query.where(table.c.id<before)
    if q:
        from sqlalchemy import or_
        columns=[col for col in table.c if col.name in ('name','username','text','message','description','status','url','note')]
        if columns: query=query.where(or_(*[col.ilike('%'+q[:100].replace('%','\\%').replace('_','\\_')+'%',escape='\\') for col in columns]))
    with engine.connect() as c: rows=c.execute(query).mappings().all()
    return {'items':[public(row) for row in rows[:limit]],'next':rows[limit-1]['id'] if len(rows)>limit else None}

@app.post('/api/data/{resource}')
def create(resource:str,data:dict=Body(...),user=Depends(current)):
    require(user,'ADMIN' if resource in ('settings','schedules','channels') else 'EDITOR')
    if resource not in FIELDS: raise HTTPException(405,'Используйте действие соответствующего раздела')
    if resource=='comments' and not data.get('external_comment_id'):
        import hashlib, json
        basis={k:str(data.get(k,'' )).strip() for k in ('campaign_id','video_id','text','author')}
        if not basis['text']: raise HTTPException(422,'Без стабильного ID нужен текст комментария')
        data={**data,'external_comment_id':'manual:'+hashlib.sha256(json.dumps(basis,sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
    values=validate(resource,data); table=TABLES[resource]
    for col in table.c:
        if not col.nullable and col.default is None and not col.primary_key and col.name not in values:
            raise HTTPException(422,'Обязательное поле: '+col.name)
    with engine.begin() as c:
        row=c.execute(table.insert().values(**values).returning(table)).mappings().one()
        log(c,user,'create',resource,row['id'])
    return public(row)

@app.patch('/api/data/{resource}/{entity_id}')
def edit(resource:str,entity_id:int,data:dict=Body(...),user=Depends(current)):
    require(user,'ADMIN' if resource in ('settings','schedules','channels') else 'EDITOR')
    if resource not in FIELDS: raise HTTPException(405,'Изменение этого раздела запрещено')
    values=validate(resource,data); table=TABLES[resource]
    with engine.begin() as c:
        row=c.execute(update(table).where(table.c.id==entity_id).values(**values).returning(table)).mappings().first()
        if not row: raise HTTPException(404,'Запись не найдена')
        log(c,user,'edit',resource,entity_id)
    return public(row)

@app.delete('/api/data/{resource}/{entity_id}')
def remove(resource:str,entity_id:int,user=Depends(current)):
    require(user,'ADMIN')
    if resource not in FIELDS: raise HTTPException(405,'Удаление запрещено для истории и журналов')
    table=TABLES[resource]
    with engine.begin() as c:
        if resource=='accounts':
            row=c.execute(select(accounts).where(accounts.c.id==entity_id)).mappings().first()
            if row and row['token_encrypted']: raise HTTPException(409,'Сначала отзовите разрешения интеграции')
        if c.execute(delete(table).where(table.c.id==entity_id)).rowcount!=1: raise HTTPException(404,'Запись не найдена')
        log(c,user,'delete',resource,entity_id)
    return {'ok':True}

@app.post('/api/drafts')
def draft_create(data:dict=Body(...),user=Depends(current)):
    require(user)
    try: source_id=int(data['source_comment_id']); account_id=int(data['account_id'])
    except (KeyError,ValueError,TypeError): raise HTTPException(422,'Укажите ID исходного комментария и аккаунта')
    content=str(data.get('text','')).strip()
    if len(content)>2000: raise HTTPException(422,'Максимум 2000 символов')
    with engine.begin() as c:
        account=c.execute(select(accounts.c.status).where(accounts.c.id==account_id)).first()
        if not account: raise HTTPException(422,'Аккаунт не найден')
        if account.status=='PAUSED': raise HTTPException(409,'Аккаунт приостановлен')
        row=c.execute(drafts.insert().values(source_comment_id=source_id,account_id=account_id,text=content).returning(drafts)).mappings().one()
        log(c,user,'create','drafts',row['id'])
        c.execute(notifications.insert().values(message=f'Черновик #{row["id"]} ожидает модерации',key=f'draft:{row["id"]}'))
    return public(row)

@app.patch('/api/drafts/{draft_id}')
def draft_edit(draft_id:int,data:dict=Body(...),user=Depends(current)):
    require(user); content=str(data.get('text','')).strip()
    if not content or len(content)>2000: raise HTTPException(422,'Ответ должен содержать 1–2000 символов')
    with engine.begin() as c:
        row=c.execute(update(drafts).where(drafts.c.id==draft_id,drafts.c.claimed_by==user['id'],drafts.c.status.in_(['DRAFTED','REVIEW']))
            .values(text=content).returning(drafts)).mappings().first()
        if not row: raise HTTPException(409,'Возьмите черновик в работу; одобренный текст менять нельзя')
        log(c,user,'edit','drafts',draft_id)
    warnings=[]
    if 'http' in content.lower() or 't.me/' in content.lower(): warnings.append('Проверьте уместность ссылки и рекламы')
    with engine.connect() as c:
        if c.scalar(select(func.count()).where(drafts.c.text==content,drafts.c.id!=draft_id)): warnings.append('Такой текст уже существует')
    return {'item':public(row),'warnings':warnings}

@app.post('/api/drafts/{draft_id}/{action}')
def draft_action(draft_id:int,action:str,data:dict=Body(default={}),user=Depends(current)):
    require(user)
    if action=='generate-ai':
        from .ai import generate
        return generate(draft_id,user)
    with engine.begin() as c:
        return claim(c,draft_id,user) if action=='claim' else transition(c,draft_id,action,user,data)

@app.get('/api/drafts/{draft_id}/context')
def draft_context(draft_id:int,user=Depends(current)):
    with engine.connect() as c:
        row=c.execute(select(drafts.c.text,accounts.c.username,videos.c.url,comments.c.text.label('source_text'))
            .join(comments,drafts.c.source_comment_id==comments.c.id).join(videos,comments.c.video_id==videos.c.id)
            .join(accounts,drafts.c.account_id==accounts.c.id).where(drafts.c.id==draft_id)).mappings().first()
    if not row: raise HTTPException(404,'Не найдено')
    return dict(row)

@app.post('/api/users')
def user_create(data:dict=Body(...),user=Depends(current)):
    require(user,'SUPER_ADMIN')
    name=str(data.get('username','')).strip(); password=str(data.get('password','')); role=data.get('role')
    if not 1<=len(name)<=80 or not 12<=len(password)<=512 or role not in ROLES: raise HTTPException(422,'Неверный логин, роль или пароль (минимум 12 символов)')
    with engine.begin() as c:
        row=c.execute(users.insert().values(username=name,password_hash=ph.hash(password),role=role).returning(users)).mappings().one()
        log(c,user,'create','users',row['id'])
    return public(row)

@app.post('/api/users/{user_id}/revoke')
def revoke(user_id:int,user=Depends(current)):
    require(user,'SUPER_ADMIN')
    with engine.begin() as c:
        c.execute(delete(sessions).where(sessions.c.user_id==user_id)); log(c,user,'revoke_sessions','users',user_id)
    return {'ok':True}

@app.patch('/api/users/{user_id}')
def user_change(user_id:int,data:dict=Body(...),user=Depends(current)):
    require(user,'SUPER_ADMIN')
    if user_id==user['id']: raise HTTPException(409,'Изменение собственной роли/блокировки здесь запрещено')
    if set(data)-{'role','active','password'}: raise HTTPException(422,'Недопустимые поля')
    values={}
    if 'role' in data:
        if data['role'] not in ROLES: raise HTTPException(422,'Неизвестная роль')
        values['role']=data['role']
    if 'active' in data:
        if not isinstance(data['active'],bool): raise HTTPException(422,'Ожидается boolean')
        values['active']=data['active']
    if 'password' in data:
        if not 12<=len(str(data['password']))<=512: raise HTTPException(422,'Пароль: 12–512 символов')
        values['password_hash']=ph.hash(data['password'])
    if not values: raise HTTPException(422,'Нет изменений')
    with engine.begin() as c:
        if c.execute(update(users).where(users.c.id==user_id).values(**values)).rowcount!=1: raise HTTPException(404,'Пользователь не найден')
        c.execute(delete(sessions).where(sessions.c.user_id==user_id)); log(c,user,'update_user','users',user_id)
    return {'ok':True}

@app.post('/api/accounts/{account_id}/{action}')
def account_action(account_id:int,action:str,user=Depends(current)):
    require(user)
    if action not in ('pause','resume'): raise HTTPException(422,'Поддерживаются pause/resume')
    with engine.begin() as c:
        row=c.execute(update(accounts).where(accounts.c.id==account_id).values(status='PAUSED' if action=='pause' else 'AUTH_REQUIRED').returning(accounts.c.id)).first()
        if not row: raise HTTPException(404,'Аккаунт не найден')
        log(c,user,action,'accounts',account_id)
    return {'status':'PAUSED' if action=='pause' else 'AUTH_REQUIRED'}

@app.post('/api/tasks')
def enqueue(data:dict=Body(...),user=Depends(current)):
    require(user,'ADMIN')
    if data.get('kind')=='AI_GENERATION': raise HTTPException(409,'AI-генератор пока не подключён; создайте текст вручную')
    with engine.begin() as c:
        task_id=add_task(c,str(data.get('kind')),data.get('payload',{})); log(c,user,'enqueue','tasks',task_id)
    return {'id':task_id}

@app.post('/api/tasks/{task_id}/{action}')
def task_action(task_id:int,action:str,user=Depends(current)):
    require(user,'ADMIN')
    with engine.begin() as c:
        row=c.execute(select(tasks).where(tasks.c.id==task_id).with_for_update()).mappings().first()
        if not row: raise HTTPException(404,'Задача не найдена')
        if action=='retry' and row['status']=='FAILED' and row['attempts']<3:
            c.execute(update(tasks).where(tasks.c.id==task_id).values(status='PENDING',due_at=now()))
        elif action=='cancel' and row['status'] in ('PENDING','RETRY'):
            c.execute(update(tasks).where(tasks.c.id==task_id).values(status='CANCELLED'))
        else: raise HTTPException(409,'Действие недоступно в этом состоянии')
        log(c,user,action,'tasks',task_id)
    return {'ok':True}

@app.post('/api/{resource}/{entity_id}/resolve')
def resolve(resource:str,entity_id:int,user=Depends(current)):
    require(user,'ADMIN')
    if resource not in ('notifications','errors'): raise HTTPException(404)
    table=TABLES[resource]
    with engine.begin() as c:
        c.execute(update(table).where(table.c.id==entity_id).values(status='READ' if resource=='notifications' else 'RESOLVED'))
        log(c,user,'resolve',resource,entity_id)
    return {'ok':True}

@app.get('/api/integrations')
def integrations(user=Depends(current)):
    from .ai import configured
    provider,key,model=configured()
    return {'tiktok':{'mode':'MANUAL_ONLY','connected':False,'message':'Запись аккаунта не авторизует TikTok. Отправка комментариев и переключение аккаунтов выполняются вручную в TikTok.'},
        'ai':{'mode':provider,'model':model,'configured':bool(key and model),'message':'Генерация одного ответа по описанию через OpenAI/Gemini, только после взятия черновика в работу. Ключи в .env. Без ключа — ручной режим. Стоимость проверяйте у провайдера.'},
        'telegram':{'configured':bool(os.getenv('TELEGRAM_BOT_TOKEN')),'message':'Добавьте токен в .env и запустите профиль integrations; бот должен быть администратором канала.'}}

@app.post('/api/drafts/{draft_id}/generate-ai')
def draft_generate(draft_id:int,user=Depends(current)):
    require(user)
    from .ai import generate
    return generate(draft_id,user)

@app.get('/api/legacy')
def legacy(user=Depends(current)):
    with engine.connect() as c:
        if not inspect(c).has_table('items'): return {'items':[]}
        return {'items':[dict(x) for x in c.execute(text('SELECT * FROM items ORDER BY id DESC LIMIT 200')).mappings()]}

@app.get('/api/export/{resource}')
def export(resource:str,user=Depends(current)):
    require(user,'ANALYST')
    if resource not in TABLES or resource in ('users','settings'): raise HTTPException(404)
    table=TABLES[resource]; buf=io.StringIO(); writer=csv.writer(buf)
    names=[col.name for col in table.c if col.name not in ('token_encrypted','open_id')]; writer.writerow(names)
    with engine.connect() as c:
        for row in c.execution_options(stream_results=True).execute(select(table).order_by(table.c.id).limit(100000)).mappings():
            cells=[]
            for name in names:
                value='' if row[name] is None else str(row[name])
                cells.append("'"+value if value.lstrip().startswith(('=','+','-','@')) else value)
            writer.writerow(cells)
    return Response('\ufeff'+buf.getvalue(),media_type='text/csv',headers={'Content-Disposition':f'attachment; filename={resource}.csv'})

@app.get('/r/{slug}')
def redirect(slug:str):
    with engine.begin() as c:
        row=c.execute(select(links).where(links.c.slug==slug)).mappings().first()
        if not row: raise HTTPException(404)
        c.execute(clicks.insert().values(link_id=row['id']))
    return RedirectResponse(row['invite_url'],302)

from .telegram_service import register_routes
register_routes(app,current,require)
static=Path('/app/frontend')
if static.exists():
    app.mount('/_next',StaticFiles(directory=static/'_next'),name='next')
    @app.get('/')
    def homepage(): return FileResponse(static/'index.html')
