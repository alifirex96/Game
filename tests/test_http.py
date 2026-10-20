"""Basic LAN HTTP behavior and session validation."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from server import GameServer, World

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.game = GameServer(('127.0.0.1', 0), World(), '123456')
        cls.base = 'http://127.0.0.1:' + str(cls.game.server_port)
        cls.thread = threading.Thread(target=cls.game.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.game.shutdown()
        cls.game.server_close()
        cls.thread.join(timeout=3)

    def request(self, path, payload=None, token=None):
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        headers = {'Content-Type':'application/json'} if data is not None else {}
        if token:
            headers['X-Session'] = token
        req = Request(self.base + path, data=data, headers=headers)
        with urlopen(req, timeout=3) as response:
            return response.status, json.loads(response.read().decode('utf-8'))

    def test_config_exposes_version(self):
        status, result = self.request('/api/config')
        self.assertEqual(status, 200)
        self.assertIn('version', result)

    def test_anonymous_state_is_denied(self):
        with self.assertRaises(HTTPError) as ctx:
            self.request('/api/state')
        self.assertEqual(ctx.exception.code, 401)

    def test_join_and_state(self):
        _, data = self.request('/api/join', {'name':'Test', 'faction':'survivors','code':'123456'})
        token = data['token']
        status, state = self.request('/api/state', token=token)
        self.assertEqual(status, 200)
        self.assertEqual(state['me']['name'], 'Test')

    def test_bad_session_action_denied(self):
        with self.assertRaises(HTTPError) as ctx:
            self.request('/api/action', {'op':'input','x':1,'y':0}, 'bad-session')
        self.assertEqual(ctx.exception.code, 401)

if __name__ == '__main__':
    unittest.main()
