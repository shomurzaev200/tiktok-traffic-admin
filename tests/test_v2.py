"""Integration tests against a dedicated PostgreSQL test database, never production."""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import select, func

os.environ.setdefault('ADMIN_USER','admin')
os.environ.setdefault('ADMIN_PASSWORD','a'*64)
from app.api import app
from app import db
from app.security import bootstrap
from app.service import claim, tiktok_url, validate
from app.telegram_service import ingest

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c:
        result=c.post('/api/auth/login',json={'username':os.environ['ADMIN_USER'],'password':os.environ['ADMIN_PASSWORD']})
        assert result.status_code==200,result.text
        c.headers['X-CSRF-Token']=result.json()['csrf']
        yield c

def post(c,path,data):
    result=c.post(path,json=data)
    assert result.status_code==200,result.text
    return result.json()

def create(c,resource,data): return post(c,'/api/data/'+resource,data)

def test_auth_csrf_and_rbac(client):
    anonymous=TestClient(app)
    assert anonymous.get('/api/data/accounts').status_code==401
    assert anonymous.post('/api/auth/login',json={'username':'admin','password':'wrong'}).status_code==401
    viewer=post(client,'/api/users',{'username':'viewer_'+uuid.uuid4().hex,'password':'safe-test-password-123','role':'VIEWER'})
    result=anonymous.post('/api/auth/login',json={'username':viewer['username'],'password':'safe-test-password-123'})
    anonymous.headers['X-CSRF-Token']=result.json()['csrf']
    assert anonymous.post('/api/data/accounts',json={'username':'nope','profile_url':'https://tiktok.com/@nope'}).status_code==403
    assert anonymous.get('/api/data/accounts').status_code==200
    old=client.headers.pop('X-CSRF-Token')
    assert client.post('/api/data/campaigns',json={'name':'blocked'}).status_code==403
    client.headers['X-CSRF-Token']=old
    data=client.get('/api/data/users').json()
    assert all('password_hash' not in row for row in data['items'])

def test_manual_workflow_and_deduplication(client):
    suffix=uuid.uuid4().hex
    campaign=create(client,'campaigns',{'name':'Test '+suffix})
    account=create(client,'accounts',{'username':'a'+suffix,'profile_url':'https://www.tiktok.com/@a'+suffix})
    assert account['status']=='AUTH_REQUIRED' and 'token_encrypted' not in account
    creator=create(client,'creators',{'username':'c'+suffix,'profile_url':'https://www.tiktok.com/@c'+suffix})
    video=create(client,'videos',{'url':'https://www.tiktok.com/@a/video/'+suffix,'creator_id':creator['id'],'campaign_id':campaign['id']})
    source={'external_comment_id':suffix,'video_id':video['id'],'campaign_id':campaign['id'],'text':'Какой контекст?'}
    comment=create(client,'comments',source)
    assert client.post('/api/data/comments',json=source).status_code==409
    draft=post(client,'/api/drafts',{'source_comment_id':comment['id'],'account_id':account['id'],'text':'<script>text</script>'})
    assert client.post('/api/drafts',json={'source_comment_id':comment['id'],'account_id':account['id']}).status_code==409
    assert client.post(f'/api/drafts/{draft["id"]}/approve',json={}).status_code==409
    post(client,f'/api/drafts/{draft["id"]}/claim',{})
    result=client.patch(f'/api/drafts/{draft["id"]}',json={'text':'Ответ проверен оператором'})
    assert result.status_code==200
    post(client,f'/api/drafts/{draft["id"]}/approve',{})
    assert client.patch(f'/api/drafts/{draft["id"]}',json={'text':'new'}).status_code==409
    post(client,f'/api/drafts/{draft["id"]}/publish-manual',{'confirmed':True,'result_url':video['url']})
    assert client.post(f'/api/drafts/{draft["id"]}/publish-manual',json={'confirmed':True,'result_url':video['url']}).status_code==409
    assert client.get(f'/api/drafts/{draft["id"]}/context').json()['text']=='Ответ проверен оператором'
    assert client.get('/api/export/drafts').status_code==200
    assert client.delete(f'/api/data/accounts/{account["id"]}').status_code==409

def test_atomic_claim_two_operators(client):
    suffix=uuid.uuid4().hex
    campaign=create(client,'campaigns',{'name':'Race'})
    account=create(client,'accounts',{'username':'r'+suffix,'profile_url':'https://www.tiktok.com/@r'+suffix})
    video=create(client,'videos',{'url':'https://www.tiktok.com/@x/video/'+suffix})
    comment=create(client,'comments',{'campaign_id':campaign['id'],'video_id':video['id'],'text':'race'})
    draft=post(client,'/api/drafts',{'source_comment_id':comment['id'],'account_id':account['id'],'text':'reply'})
    users=[post(client,'/api/users',{'username':f'op{i}_{suffix}','password':'safe-test-password','role':'EDITOR'}) for i in range(2)]
    def attempt(user):
        try:
            with db.engine.begin() as c: claim(c,draft['id'],user)
            return 200
        except HTTPException as error: return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool: statuses=list(pool.map(attempt,users))
    assert sorted(statuses)==[200,409]

def test_telegram_dedup_and_analytics(client):
    suffix=uuid.uuid4().hex
    channel=create(client,'channels',{'name':'Test','chat_id':'-100'+str(uuid.uuid4().int)[:12]})
    campaign=create(client,'campaigns',{'name':'Telegram '+suffix,'channel_id':channel['id']})
    with db.engine.begin() as c:
        c.execute(db.links.insert().values(campaign_id=campaign['id'],channel_id=channel['id'],invite_url='https://t.me/+'+suffix,slug=suffix))
    event={'update_id':int(uuid.uuid4().int%10**15),'chat_member':{'chat':{'id':int(channel['chat_id'])},'old_chat_member':{'status':'left'},
        'new_chat_member':{'status':'member','user':{'id':12345}},'invite_link':{'invite_link':'https://t.me/+'+suffix}}}
    assert ingest(event) is True
    assert ingest(event) is False
    assert client.get('/r/'+suffix,follow_redirects=False).status_code==302
    overview=client.get('/api/analytics/overview').json()
    row=next(x for x in overview['campaigns'] if x['id']==campaign['id'])
    assert row['joins']==1 and row['clicks']==1 and row['conversion']==100

def test_ai_missing_key_and_mock_response(client):
    from app.ai import request_text
    with patch('app.ai.httpx.post') as call:
        call.return_value.json.return_value={'output':[{'content':[{'type':'output_text','text':'Контекстный ответ'}]}],'usage':{'input_tokens':10,'output_tokens':3}}
        assert request_text('openai','fake-key','test-model','text')==('Контекстный ответ',10,3)
        assert call.call_args.kwargs['json']['store'] is False
    assert client.get('/api/integrations').json()['ai']['mode']=='manual'

def test_validation_and_health(client):
    for url in ['http://tiktok.com','https://tiktok.com.evil.com','https://127.0.0.1','https://user@tiktok.com','https://tiktok.com:9']:
        with pytest.raises(HTTPException): tiktok_url(url)
    assert client.get('/health/ready').json()=={'status':'ok'}
    assert client.get('/api/openapi.json').status_code==200
    assert client.get('/api/data/accounts?limit=101').status_code==422
    assert client.post('/api/data/accounts',json={'username':'x','profile_url':'https://tiktok.com','token_encrypted':'fake'}).status_code==422
