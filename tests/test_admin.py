"""The host's admin panel and the death notices everybody gets."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from server import GameError, GameServer, Handler
from helpers import quiet_world, run


class AdminTests(unittest.TestCase):
    def setUp(self):
        self.w = quiet_world(3)
        self.token = self.w.join('Ведущий'); self.me = self.w.players[self.token]
        self.other_token = self.w.join('Гость'); self.other = self.w.players[self.other_token]

    def cmd(self, op, **data):
        data['op'] = op
        return self.w.admin(self.token, data)

    def test_teleport_bring_and_goto(self):
        t = self.w.towns['svetlogorsk']
        self.cmd('teleport', x=t['x'], y=t['y'])
        self.assertLess(abs(self.me['x'] - t['x']) + abs(self.me['y'] - t['y']), 500)
        self.cmd('bring', target=self.other['id'])
        self.assertLess(abs(self.other['x'] - self.me['x']), 300)
        self.other['x'] += 20000
        self.cmd('goto', target=self.other['id'])
        self.assertLess(abs(self.other['x'] - self.me['x']), 300)

    def test_give_loaded_gun_and_spawn_things(self):
        self.cmd('give', item='w_ak')
        self.assertIn(2, self.me['weapons']); self.assertEqual(self.me['mags']['2'], 30)
        self.cmd('give', item='canned', n=3, target=self.other['id'])
        self.assertEqual(self.other['items']['canned'], 3)
        self.cmd('spawn_loot', item='medkit', n=2)
        self.assertTrue(any(l['item'] == 'medkit' and l['n'] == 2 for l in self.w.loot.values()))
        npcs = len(self.w.npcs)
        self.cmd('spawn_npc', kind='bear', n=2)
        self.assertGreater(len(self.w.npcs), npcs)
        cars = len(self.w.cars)
        self.cmd('spawn_car', model=1)
        self.assertEqual(len(self.w.cars), cars + 1)
        with self.assertRaises(GameError):
            self.cmd('spawn_npc', kind='dragon')

    def test_god_heal_weather_time(self):
        self.cmd('god')
        self.w._damage(self.me, 500)
        self.assertEqual(self.me['hp'], 100)
        self.me['bleeding'] = True; self.me['food'] = 5
        self.cmd('heal')
        self.assertFalse(self.me['bleeding']); self.assertEqual(self.me['food'], 100)
        self.cmd('weather', kind='fog'); self.assertEqual(self.w.weather['kind'], 'fog')
        before = self.w.elapsed
        self.cmd('time', hour=22)
        self.assertGreater(self.w.elapsed, before); self.assertTrue(self.w.is_night())

    def test_others_hear_about_a_death_and_its_cause(self):
        killer = self.w.players[self.w.join('Стрелок')]
        self.other['hit_by'] = {'kind':'player', 'id':killer['id'], 'name':killer['name'], 'at':self.w.elapsed}
        self.w._damage(self.other, 999)
        mine = [m for m in self.w.snapshot(self.token)['messages'] if m['tone'] == 'death']
        self.assertEqual(len(mine), 1)
        self.assertIn('Гость погиб', mine[0]['title']); self.assertIn('Стрелок', mine[0]['text'])
        theirs = [m for m in self.w.snapshot(self.other_token)['messages'] if m['tone'] == 'death']
        self.assertEqual(theirs, [])
        killer_token = next(t for t, p in self.w.players.items() if p is killer)
        self.assertEqual([m for m in self.w.snapshot(killer_token)['messages'] if m['tone'] == 'death'], [])

    def test_death_from_bleeding_is_named(self):
        self.other['bleeding'] = True; self.other['hp'] = .5
        run(self.w, 2, [self.me, self.other])
        text = [m['text'] for m in self.w.log if m['tone'] == 'death']
        self.assertTrue(text and text[-1].startswith('Истёк кровью'))


class AdminHttpTests(unittest.TestCase):
    def test_admin_is_refused_from_another_computer(self):
        w = quiet_world(2); token = w.join('Ведущий')
        game = GameServer(('127.0.0.1', 0), w, '123456')
        threading.Thread(target=game.serve_forever, daemon=True).start()
        try:
            def post(local):
                original = Handler._local
                Handler._local = lambda self: local
                try:
                    req = Request('http://127.0.0.1:%d/api/admin' % game.server_port, data=json.dumps({'op':'god'}).encode(),
                                  headers={'Content-Type':'application/json', 'X-Session':token})
                    with urlopen(req, timeout=3) as r:
                        return r.status
                finally:
                    Handler._local = original
            with self.assertRaises(HTTPError) as ctx:
                post(False)
            self.assertEqual(ctx.exception.code, 403)
            self.assertEqual(post(True), 200)
        finally:
            game.shutdown(); game.server_close()


if __name__ == '__main__':
    unittest.main()
