"""Real HTTP + PostgreSQL check. Run inside the app container after compose up.
Creates one clearly marked test row and retains its audit trail.
"""
import base64
import http.cookiejar
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid

base = 'http://127.0.0.1:8000'
jar = http.cookiejar.CookieJar()
client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
credential = base64.b64encode((os.environ['ADMIN_USER'] + ':' + os.environ['ADMIN_PASSWORD']).encode()).decode()

def get(path, data=None, authenticated=True):
    request = urllib.request.Request(base + path, data=urllib.parse.urlencode(data).encode() if data is not None else None)
    if authenticated:
        request.add_header('Authorization', 'Basic ' + credential)
    return client.open(request, timeout=15)

assert get('/healthz').status == 200
try:
    get('/', authenticated=False)
    raise AssertionError('Anonymous access allowed')
except urllib.error.HTTPError as error:
    assert error.code == 401
page = get('/').read().decode()
token = re.search(r'name="csrf_token" value="([a-f0-9]+)"', page).group(1)
try:
    get('/items', {'url': 'https://www.tiktok.com/@test/video/1', 'campaign': 'test', 'csrf_token': 'wrong'})
    raise AssertionError('CSRF bypass')
except urllib.error.HTTPError as error:
    assert error.code == 403
marker = 'SMOKE-' + uuid.uuid4().hex
page = get('/items', {'url': 'https://www.tiktok.com/@test/video/1', 'campaign': marker, 'note': '<script>alert(1)</script>', 'csrf_token': token}).read().decode()
assert '&lt;script&gt;alert(1)&lt;/script&gt;' in page
item_id = re.search(r'<tr><td>(\d+)</td><td>' + marker, page).group(1)
token = re.search(r'name="csrf_token" value="([a-f0-9]+)"', page).group(1)
page = get('/items/' + item_id + '/status', {'status': 'done', 'csrf_token': token}).read().decode()
assert 'pending -&gt; done' in page
assert marker in get('/export.csv').read().decode('utf-8-sig')
print('PASS: health, auth, CSRF, create, HTML escaping, status, audit, CSV. Test row: ' + marker)
