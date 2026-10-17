import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.update(ADMIN_USER='admin', ADMIN_PASSWORD='a'*64, DB_PASSWORD='b'*64)
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app import main

class AppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.client.auth = ('admin', 'a'*64)

    def test_auth(self):
        self.assertEqual(TestClient(main.app).get('/').status_code, 401)
        self.assertEqual(self.client.get('/', auth=('admin','wrong')).status_code, 401)

    def test_url_validation(self):
        self.assertEqual(main.validate_url('https://www.tiktok.com/@x/video/1'), 'https://www.tiktok.com/@x/video/1')
        for url in ['http://tiktok.com', 'https://tiktok.com.evil.com', 'https://evil.com', 'https://user@tiktok.com', 'https://tiktok.com:444']:
            with self.assertRaises(HTTPException):
                main.validate_url(url)

    def test_csrf_and_status(self):
        self.assertEqual(self.client.post('/items', data={'url':'https://tiktok.com','campaign':'x','csrf_token':'bad'}).status_code, 403)
        self.client.cookies.set('csrf','token')
        self.assertEqual(self.client.post('/items/1/status', data={'status':'spam','csrf_token':'token'}).status_code, 422)

    def test_render_escape_and_health(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.side_effect = [[{'id':1,'campaign':'<img>','url':'https://tiktok.com','note':'<script>','status':'pending'}], []]
        with patch.object(main, 'connect') as db:
            db.return_value.__enter__.return_value = conn
            page = self.client.get('/')
            self.assertEqual(page.status_code, 200)
            self.assertIn('&lt;script&gt;', page.text)
            self.assertIn('&lt;img&gt;', page.text)
            self.assertIn('httponly', page.headers['set-cookie'].lower())
            self.assertEqual(self.client.get('/healthz').json(), {'status':'ok'})

    def test_csv_injection(self):
        for text in ['=1+1',' +cmd','-1','@SUM(A1)']:
            self.assertTrue(main.safe_cell(text).startswith("'"))
        self.assertEqual(main.safe_cell('hello'), 'hello')

if __name__ == '__main__':
    unittest.main()
