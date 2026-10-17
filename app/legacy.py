import csv
import io
import os
import secrets
from contextlib import asynccontextmanager
from html import escape
from urllib.parse import urlparse

import psycopg
from psycopg.rows import dict_row
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials

USER = os.environ['ADMIN_USER']
PASSWORD = os.environ['ADMIN_PASSWORD']
if len(PASSWORD) < 24 or len(os.environ['DB_PASSWORD']) < 24:
    raise RuntimeError('Generate strong secrets using scripts/init_env.py')

def connect():
    return psycopg.connect(host=os.environ.get('DB_HOST', 'db'),
        dbname=os.environ.get('DB_NAME', 'traffic'), user=os.environ.get('DB_USER', 'traffic'),
        password=os.environ['DB_PASSWORD'], connect_timeout=5, row_factory=dict_row)

@asynccontextmanager
async def lifespan(app):
    with connect() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS items (
          id BIGSERIAL PRIMARY KEY, url TEXT NOT NULL, campaign TEXT NOT NULL,
          note TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
          CHECK (status IN ('pending','approved','rejected','done')),
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
        conn.execute('''CREATE TABLE IF NOT EXISTS audit (
          id BIGSERIAL PRIMARY KEY, item_id BIGINT NOT NULL REFERENCES items(id),
          actor TEXT NOT NULL, action TEXT NOT NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now())''')
    yield

app = FastAPI(title='TikTok Traffic Admin', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
basic = HTTPBasic()

def auth(credentials: HTTPBasicCredentials = Depends(basic)):
    good_user = secrets.compare_digest(credentials.username.encode(), USER.encode())
    good_password = secrets.compare_digest(credentials.password.encode(), PASSWORD.encode())
    if not (good_user and good_password):
        raise HTTPException(401, 'Invalid credentials', headers={'WWW-Authenticate': 'Basic'})
    return credentials.username

def csrf(request: Request, token: str):
    saved = request.cookies.get('csrf', '')
    if not saved or not secrets.compare_digest(saved, token):
        raise HTTPException(403, 'Invalid CSRF token; reload the page')

def validate_url(url: str):
    parsed = urlparse(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443) or not (host == 'tiktok.com' or host.endswith('.tiktok.com')):
        raise HTTPException(422, 'Use an HTTPS TikTok URL')
    return url

@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'"
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.get('/healthz')
def health():
    try:
        with connect() as conn:
            conn.execute('SELECT 1')
    except psycopg.Error:
        raise HTTPException(503, 'Database unavailable')
    return {'status': 'ok'}

@app.get('/', response_class=HTMLResponse)
def home(actor=Depends(auth)):
    token = secrets.token_hex(32)
    with connect() as conn:
        items = conn.execute('SELECT * FROM items ORDER BY id DESC LIMIT 200').fetchall()
        events = conn.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 30').fetchall()
    rows = ''
    for item in items:
        options = ''.join(f'<option {"selected" if s == item["status"] else ""}>{s}</option>' for s in ('pending','approved','rejected','done'))
        rows += f'''<tr><td>{item['id']}</td><td>{escape(item['campaign'])}</td>
        <td><a href="{escape(item['url'], quote=True)}" target="_blank" rel="noopener noreferrer">Открыть TikTok</a></td>
        <td class="note">{escape(item['note'])}</td><td><form method="post" action="/items/{item['id']}/status">
        <input type="hidden" name="csrf_token" value="{token}"><select name="status">{options}</select><button>Сохранить</button></form></td></tr>'''
    history = ''.join(f"<li>#{e['item_id']} — {escape(e['action'])}, {escape(e['actor'])}, {e['created_at']}</li>" for e in events)
    response = HTMLResponse(f'''<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
    <title>TikTok Traffic Admin</title><style>body{{font:16px system-ui;max-width:1200px;margin:32px auto;padding:16px;background:#f6f7fb;color:#192335}}input,textarea,select,button{{padding:10px;margin:5px}}table{{width:100%;background:white;border-collapse:collapse}}td,th{{padding:12px;border-bottom:1px solid #ddd;text-align:left}}.note{{white-space:pre-wrap;overflow-wrap:anywhere;max-width:350px}}button{{cursor:pointer}}</style>
    <h1>TikTok Traffic Admin</h1><p>Ручной реестр видео и кампаний для Telegram. Решения сохраняются только здесь. Публикаций и отправки комментариев нет.</p>
    <form method="post" action="/items"><input type="hidden" name="csrf_token" value="{token}">
    <input name="url" type="url" placeholder="https://www.tiktok.com/..." maxlength="2048" required>
    <input name="campaign" placeholder="Кампания / Telegram-канал" maxlength="120" required>
    <textarea name="note" placeholder="Заметка модератора" maxlength="4000"></textarea><button>Добавить</button></form>
    <p>pending — ожидает; approved — одобрено локально; rejected — отклонено; done — обработано вручную.</p>
    <p><a href="/export.csv">Экспорт CSV</a> · Показаны последние 200 записей; экспорт содержит все записи.</p>
    <table><tr><th>ID</th><th>Кампания</th><th>Видео</th><th>Заметка</th><th>Статус</th></tr>{rows}</table>
    <h2>Последние 30 действий</h2><ul>{history}</ul></html>''')
    response.set_cookie('csrf', token, httponly=True, samesite='strict', max_age=3600)
    return response

@app.post('/items')
def create(request: Request, url: str = Form(..., max_length=2048), campaign: str = Form(..., min_length=1, max_length=120), note: str = Form('', max_length=4000), csrf_token: str = Form(...), actor=Depends(auth)):
    csrf(request, csrf_token)
    try:
        url = validate_url(url.strip())
    except ValueError:
        raise HTTPException(422, 'Invalid URL')
    if not campaign.strip():
        raise HTTPException(422, 'Campaign is required')
    with connect() as conn:
        item = conn.execute('INSERT INTO items(url,campaign,note) VALUES (%s,%s,%s) RETURNING id', (url, campaign.strip(), note)).fetchone()
        conn.execute('INSERT INTO audit(item_id,actor,action) VALUES (%s,%s,%s)', (item['id'], actor, 'created'))
    return RedirectResponse('/', status_code=303)

@app.post('/items/{item_id}/status')
def update(item_id: int, request: Request, status: str = Form(...), csrf_token: str = Form(...), actor=Depends(auth)):
    csrf(request, csrf_token)
    if status not in ('pending','approved','rejected','done'):
        raise HTTPException(422, 'Invalid status')
    with connect() as conn:
        item = conn.execute('SELECT status FROM items WHERE id=%s FOR UPDATE', (item_id,)).fetchone()
        if not item:
            raise HTTPException(404, 'Item not found')
        conn.execute('UPDATE items SET status=%s, updated_at=now() WHERE id=%s', (status, item_id))
        conn.execute('INSERT INTO audit(item_id,actor,action) VALUES (%s,%s,%s)', (item_id, actor, item['status'] + ' -> ' + status))
    return RedirectResponse('/', status_code=303)

def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(('=', '+', '-', '@')) else text

@app.get('/export.csv')
def export(actor=Depends(auth)):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(['id','url','campaign','note','status','created_at','updated_at'])
    with connect() as conn:
        with conn.cursor(name='export') as cursor:
            cursor.execute('SELECT * FROM items ORDER BY id')
            for row in cursor:
                writer.writerow([safe_cell(row[k]) for k in ('id','url','campaign','note','status','created_at','updated_at')])
    return Response('\ufeff' + buffer.getvalue(), media_type='text/csv; charset=utf-8', headers={'Content-Disposition': 'attachment; filename=traffic.csv'})
