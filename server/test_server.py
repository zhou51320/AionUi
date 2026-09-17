import io
import os
import unittest
import zipfile
from app import create_app, init_database
from models import db, User, UserConfig, MarketFile, ClientLog
from crypto_utils import encrypt_api_key, decrypt_api_key

class TestConfig:
    TESTING = True
    SECRET_KEY = 'test-secret-key-12345'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'test_uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    JWT_EXPIRATION_DAYS = 1

class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        os.makedirs(TestConfig.UPLOAD_FOLDER, exist_ok=True)
        with self.app.app_context():
            init_database(self.app)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        # Clean up test uploads
        if os.path.exists(TestConfig.UPLOAD_FOLDER):
            for f in os.listdir(TestConfig.UPLOAD_FOLDER):
                os.remove(os.path.join(TestConfig.UPLOAD_FOLDER, f))
            os.rmdir(TestConfig.UPLOAD_FOLDER)

    def login(self, username, password):
        resp = self.client.post('/api/auth/login', json={'username': username, 'password': password})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['code'], 0)
        return data['data']['token']

    def test_crypto_utils(self):
        plain = "sk-test-key-abc123xyz"
        cipher = encrypt_api_key(plain)
        self.assertNotEqual(plain, cipher)
        decrypted = decrypt_api_key(cipher)
        self.assertEqual(plain, decrypted)

    def test_auth_flow(self):
        # Normal user login
        token = self.login('user', 'user123')
        self.assertTrue(bool(token))

        # Check me
        resp = self.client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data['data']['username'], 'user')
        self.assertEqual(data['data']['role'], 'user')

        # Logout
        resp = self.client.post('/api/auth/logout')
        self.assertEqual(resp.status_code, 200)

    def test_config_sync(self):
        token = self.login('user', 'user123')
        headers = {'Authorization': f'Bearer {token}'}

        # Update config
        put_resp = self.client.put('/api/config', headers=headers, json={
            'api_key': 'sk-my-custom-key',
            'base_url': 'https://my-proxy.com/v1',
            'model_name': 'claude-3-5-sonnet',
            'extra_config': {'temperature': 0.7}
        })
        self.assertEqual(put_resp.status_code, 200)
        put_data = put_resp.get_json()
        self.assertEqual(put_data['data']['api_key'], 'sk-my-custom-key')
        self.assertEqual(put_data['data']['base_url'], 'https://my-proxy.com/v1')

        # Get config
        get_resp = self.client.get('/api/config', headers=headers)
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.get_json()
        self.assertEqual(get_data['data']['api_key'], 'sk-my-custom-key')
        self.assertEqual(get_data['data']['base_url'], 'https://my-proxy.com/v1')
        self.assertEqual(get_data['data']['model_name'], 'claude-3-5-sonnet')
        self.assertEqual(get_data['data']['extra_config']['temperature'], 0.7)

    def test_market_flow(self):
        admin_token = self.login('admin', 'admin123')
        user_token = self.login('user', 'user123')

        # Create mock zip file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('plugin.json', '{"name": "test-plugin"}')
        zip_buffer.seek(0)

        # Admin uploads market package
        upload_resp = self.client.post(
            '/api/market/upload',
            headers={'Authorization': f'Bearer {admin_token}'},
            data={
                'file': (zip_buffer, 'test-plugin.zip'),
                'category': 'plugin',
                'description': 'A test plugin package'
            },
            content_type='multipart/form-data'
        )
        self.assertEqual(upload_resp.status_code, 201)
        upload_data = upload_resp.get_json()
        file_id = upload_data['data']['id']
        self.assertTrue(file_id > 0)

        # Regular user cannot upload
        zip_buffer.seek(0)
        user_upload_resp = self.client.post(
            '/api/market/upload',
            headers={'Authorization': f'Bearer {user_token}'},
            data={'file': (zip_buffer, 'test2.zip'), 'category': 'plugin'},
            content_type='multipart/form-data'
        )
        self.assertEqual(user_upload_resp.status_code, 403)

        # User lists market packages
        list_resp = self.client.get('/api/market/files?category=plugin', headers={'Authorization': f'Bearer {user_token}'})
        self.assertEqual(list_resp.status_code, 200)
        files = list_resp.get_json()['data']
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['filename'], 'test-plugin.zip')

        # User downloads package
        down_resp = self.client.get(f'/api/market/download/{file_id}', headers={'Authorization': f'Bearer {user_token}'})
        self.assertEqual(down_resp.status_code, 200)
        self.assertEqual(down_resp.mimetype, 'application/zip')

        # Admin deletes file
        del_resp = self.client.delete(f'/api/market/files/{file_id}', headers={'Authorization': f'Bearer {admin_token}'})
        self.assertEqual(del_resp.status_code, 200)

    def test_log_reporting(self):
        user_token = self.login('user', 'user123')
        admin_token = self.login('admin', 'admin123')

        # Post log from user client
        post_resp = self.client.post('/api/logs', headers={'Authorization': f'Bearer {user_token}'}, json={
            'level': 'ERROR',
            'message': 'Model connection timed out',
            'client_info': 'AionUi Desktop Win7 x64'
        })
        self.assertEqual(post_resp.status_code, 201)

        # Regular user cannot view all logs
        user_get_resp = self.client.get('/api/logs', headers={'Authorization': f'Bearer {user_token}'})
        self.assertEqual(user_get_resp.status_code, 403)

        # Admin can view logs
        admin_get_resp = self.client.get('/api/logs?level=ERROR', headers={'Authorization': f'Bearer {admin_token}'})
        self.assertEqual(admin_get_resp.status_code, 200)
        logs = admin_get_resp.get_json()['data']
        self.assertEqual(logs['total'], 1)
        self.assertEqual(logs['items'][0]['message'], 'Model connection timed out')
        self.assertEqual(logs['items'][0]['username'], 'user')

if __name__ == '__main__':
    unittest.main()
