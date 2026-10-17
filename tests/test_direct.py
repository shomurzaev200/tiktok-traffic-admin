"""Checks that do not need local sockets or a PostgreSQL server."""
import os
import unittest
from unittest.mock import MagicMock, patch
os.environ.update(ADMIN_USER='admin', ADMIN_PASSWORD='a'*64, DB_PASSWORD='b'*64)
from app import main
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

class DirectTests(unittest.TestCase):
    def test_auth(self):
        self.assertEqual(main.auth(HTTPBasicCredentials(username='admin',password='a'*64)), 'admin')
        with self.assertRaises(HTTPException) as error:
            main.auth(HTTPBasicCredentials(username='admin',password='wrong'))
        self.assertEqual(error.exception.status_code, 401)

    def test_url(self):
        self.assertEqual(main.validate_url('https://www.tiktok.com/@x'), 'https://www.tiktok.com/@x')
        for url in ['http://tiktok.com', 'https://tiktok.com.evil.com', 'https://x@tiktok.com', 'https://tiktok.com:444']:
            with self.assertRaises(HTTPException): main.validate_url(url)

    def test_csrf(self):
        request = MagicMock(cookies={'csrf':'token'})
        main.csrf(request,'token')
        with self.assertRaises(HTTPException): main.csrf(request,'wrong')

    def test_render(self):
        conn = MagicMock()
        conn.execute.return_value.fetchall.side_effect = [[{'id':1,'campaign':'<img>','url':'https://tiktok.com','note':'<script>','status':'pending'}], []]
        with patch.object(main,'connect') as db:
            db.return_value.__enter__.return_value = conn
            page = main.home('admin')
            self.assertIn('&lt;script&gt;',page.body.decode())
            self.assertIn('&lt;img&gt;',page.body.decode())
            self.assertIn('HttpOnly',page.headers['set-cookie'])

    def test_database_operations(self):
        conn = MagicMock()
        request = MagicMock(cookies={'csrf':'token'})
        with patch.object(main,'connect') as db:
            db.return_value.__enter__.return_value = conn
            conn.execute.return_value.fetchone.return_value = {'id':42}
            self.assertEqual(main.create(request,'https://tiktok.com/@x','campaign','note','token','admin').status_code,303)
            self.assertEqual(conn.execute.call_count,2)
            conn.reset_mock()
            conn.execute.return_value.fetchone.return_value = {'status':'pending'}
            self.assertEqual(main.update(42,request,'done','token','admin').status_code,303)
            self.assertEqual(conn.execute.call_count,3)
            self.assertEqual(main.health(),{'status':'ok'})
            conn.execute.return_value.fetchone.return_value = None
            with self.assertRaises(HTTPException) as error: main.update(404,request,'done','token','admin')
            self.assertEqual(error.exception.status_code,404)

    def test_csv(self):
        for value in ['=1',' +cmd','-1','@SUM(A1)']:
            self.assertTrue(main.safe_cell(value).startswith("'"))
        conn = MagicMock()
        conn.cursor.return_value.__enter__.return_value.__iter__.return_value = iter([dict(id=1,url='https://tiktok.com',campaign='=1',note='text',status='pending',created_at='now',updated_at='now')])
        with patch.object(main,'connect') as db:
            db.return_value.__enter__.return_value = conn
            response = main.export('admin')
            self.assertIn("'=1",response.body.decode('utf-8-sig'))

if __name__ == '__main__': unittest.main()
