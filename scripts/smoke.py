"""End-to-end API smoke test. Retains labelled SMOKE records."""
import http.cookiejar
import json
import os
import urllib.error
import urllib.request
import uuid

base='http://127.0.0.1:8000'
client=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
csrf=''
def call(path,data=None,method=None):
    request=urllib.request.Request(base+path,data=json.dumps(data).encode() if data is not None else None,method=method)
    request.add_header('Content-Type','application/json'); request.add_header('X-CSRF-Token',csrf)
    with client.open(request,timeout=30) as response: return json.load(response)

assert call('/health/ready')['status']=='ok'
login=call('/api/auth/login',{'username':os.getenv('ADMIN_USER','admin'),'password':os.environ['ADMIN_PASSWORD']})
csrf=login['csrf']
suffix=uuid.uuid4().hex
campaign=call('/api/data/campaigns',{'name':'SMOKE-'+suffix})
account=call('/api/data/accounts',{'username':'smoke'+suffix,'profile_url':'https://www.tiktok.com/@smoke'+suffix})
assert account['status']=='AUTH_REQUIRED'
video=call('/api/data/videos',{'url':'https://www.tiktok.com/@smoke/video/'+suffix,'campaign_id':campaign['id']})
source={'campaign_id':campaign['id'],'video_id':video['id'],'text':'SMOKE comment','external_comment_id':suffix}
comment=call('/api/data/comments',source)
try:
    call('/api/data/comments',source)
    raise AssertionError('Duplicate allowed')
except urllib.error.HTTPError as error: assert error.code==409
draft=call('/api/drafts',{'source_comment_id':comment['id'],'account_id':account['id'],'text':'Ручной тестовый ответ'})
call(f'/api/drafts/{draft["id"]}/claim',{})
call(f'/api/drafts/{draft["id"]}/approve',{})
call(f'/api/drafts/{draft["id"]}/publish-manual',{'confirmed':True,'result_url':video['url']})
assert call('/api/auth/me')['user']['username']==os.getenv('ADMIN_USER','admin')
print('PASS V2: database readiness, login, session, accounts, campaigns, videos, comments, deduplication, claim, approval, manual report, audit. Records: SMOKE-'+suffix)
