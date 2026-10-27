"""Joining, survival, death on the DayZ rules, saving and old saves."""
import json
import math
import tempfile
import time
import unittest
from pathlib import Path
from server import GameError, World, SAVE_VERSION
from world_data import FISTS, START_ITEMS, RESPAWN_TIME, WORLD_SIZE, MAX_PLAYERS
from helpers import quiet_world, act, run


class WorldTests(unittest.TestCase):
    def setUp(self):
        self.w = quiet_world()
        self.token = self.w.join('Игрок'); self.p = self.w.players[self.token]

    def test_fresh_character_wakes_on_the_shore_with_almost_nothing(self):
        p = self.p
        self.assertEqual(p['weapons'], [FISTS])
        self.assertEqual(p['items'], START_ITEMS)
        self.assertEqual(p['gear'], {'weapon':FISTS, 'armor':0, 'clothes':0, 'backpack':0})
        self.assertFalse(self.w.terrain.water(p['x'], p['y']))
        near_sea = any(self.w.terrain.sea(p['x'] + math.cos(a) * 1200, p['y'] + math.sin(a) * 1200) for a in [k * math.pi / 8 for k in range(16)])
        self.assertTrue(near_sea)
        self.assertNotIn('level', p); self.assertNotIn('coins', p)

    def test_players_spawn_apart(self):
        q = self.w.players[self.w.join('Второй')]
        self.assertGreater(math.hypot(q['x'] - self.p['x'], q['y'] - self.p['y']), 1400)

    def test_room_is_capped(self):
        for i in range(MAX_PLAYERS - 1):
            self.w.join('Игрок ' + str(i))
        with self.assertRaises(GameError):
            self.w.join('Лишний')

    def test_death_leaves_everything_on_the_body_and_respawns_fresh(self):
        p = self.p
        p['weapons'] = [2, 8, FISTS]; p['gear'].update(weapon=2, clothes=1, backpack=2, armor=1); p['mags'] = {'2':17}
        p['items'] = {'canned':2, 'ammo762':40}
        x, y = p['x'], p['y']
        self.w._damage(p, 1000)
        body = next(b for b in self.w.bodies.values() if b.get('player') == p['id'])
        self.assertEqual((body['x'], body['y']), (round(x, 1), round(y, 1)))
        for item in ('w_ak', 'w_knife', 'vatnik', 'pack', 'vest', 'canned', 'ammo762'):
            self.assertIn(item, body['items'])
        self.assertEqual(body['mags'], {'2':17})
        with self.assertRaises(GameError):
            act(self.w, self.token, 'heal')
        run(self.w, RESPAWN_TIME + .5, [p])
        self.assertGreater(p['hp'], 0)
        self.assertEqual(p['weapons'], [FISTS]); self.assertEqual(p['items'], START_ITEMS)
        self.assertEqual(p['stats']['infected'], 0)

    def test_hunger_and_thirst_run_down(self):
        p = self.p; food, water = p['food'], p['water']
        run(self.w, 10, [p])
        self.assertLess(p['food'], food); self.assertLess(p['water'], water)

    def test_bleeding_hurts_until_bandaged(self):
        p = self.p; p['bleeding'] = True
        run(self.w, 4, [p]); hp = p['hp']
        self.assertLess(hp, 100)
        act(self.w, self.token, 'heal')
        self.assertFalse(p['bleeding'])
        self.assertNotIn('bandage', p['items'])

    def test_cloth_stops_bleeding_without_a_bandage(self):
        p = self.p; p['bleeding'] = True; p['items'] = {'cloth':1}
        act(self.w, self.token, 'heal')
        self.assertFalse(p['bleeding']); self.assertNotIn('cloth', p['items'])

    def test_sea_water_is_not_drinkable(self):
        p = self.p
        for r in range(0, 3000, 20):
            for a in range(16):
                x = p['x'] + math.cos(a * math.pi / 8) * r; y = p['y'] + math.sin(a * math.pi / 8) * r
                if self.w.terrain.sea(x, y + 40) and not self.w.terrain.water(x, y):
                    p['x'], p['y'] = x, y
                    with self.assertRaisesRegex(GameError, 'солён'):
                        act(self.w, self.token, 'drink')
                    return
        self.fail('no shore')

    def test_eating_from_the_backpack(self):
        p = self.p; p['food'] = 30
        act(self.w, self.token, 'use', item='apple')
        self.assertEqual(p['food'], 42); self.assertNotIn('apple', p['items'])

    def test_receipts_make_actions_idempotent(self):
        p = self.p; p['items'] = {'apple':3}
        data = {'op':'use', 'item':'apple', 'request_id':'same-id'}
        self.w.command(self.token, dict(data)); self.w.command(self.token, dict(data))
        self.assertEqual(p['items']['apple'], 2)

    def test_snapshot_has_no_economy(self):
        s = self.w.snapshot(self.token)
        for key in ('towns', 'quests', 'stocks', 'posts', 'coins'):
            self.assertNotIn(key, s); self.assertNotIn(key, s['me'])
        self.assertIn('loot', s); self.assertIn('cars', s)

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'world.json'
            w = World(path); t = w.join('Сохранённый'); p = w.players[t]
            p['items'] = {'canned':2}; p['weapons'] = [0, FISTS]; p['mags'] = {'0':5}
            camp_count = len(w.cars)
            w.save()
            w2 = World(path); q = w2.players[t]
            self.assertEqual(q['items'], {'canned':2}); self.assertEqual(q['weapons'], [0, FISTS]); self.assertEqual(q['mags'], {'0':5})
            self.assertEqual(len(w2.cars), camp_count)
            self.assertIsNone(w2.load_warning)

    def test_old_world_is_set_aside(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'world.json'
            path.write_text(json.dumps({'schema':2, 'room_code':'654321', 'players':{}}), encoding='utf-8')
            w = World(path)
            self.assertIn('прошлой версии', w.load_warning)
            self.assertEqual(w.room_code, '654321')
            self.assertTrue(any('before-0.8' in f.name for f in Path(d).iterdir()))

    def test_damaged_save_is_kept(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'world.json'
            path.write_text('{broken', encoding='utf-8')
            w = World(path)
            self.assertTrue(w.load_warning)
            self.assertTrue(any('unreadable' in f.name for f in Path(d).iterdir()))

    def test_new_world_keeps_a_backup(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'world.json'
            w = World(path); w.room_code = '111222'; w.join('Старый'); w.save()
            backup = w.reset()
            self.assertTrue(backup.exists()); self.assertEqual(w.players, {}); self.assertEqual(w.room_code, '111222')

    def test_clan_mates_do_not_hurt_each_other(self):
        q_token = self.w.join('Друг'); q = self.w.players[q_token]
        act(self.w, self.token, 'clan_create', name='Север')
        act(self.w, self.token, 'clan_invite', side=q['faction'])
        act(self.w, q_token, 'clan_join', id=self.w.sides[self.p['faction']]['clan'])
        self.assertFalse(self.w.hostile_shot(self.p, q))
        stranger = self.w.players[self.w.join('Чужой')]
        self.assertTrue(self.w.hostile_shot(self.p, stranger))

    def test_trade_moves_items(self):
        q_token = self.w.join('Торговец'); q = self.w.players[q_token]
        q['x'], q['y'] = self.p['x'] + 50, self.p['y']
        self.p['items'] = {'canned':2}; q['items'] = {'ammo9':10}
        r = act(self.w, self.token, 'offer_make', to=q['id'], give={'items':{'canned':1}}, want={'items':{'ammo9':10}})
        oid = next(iter(self.w.offers))
        act(self.w, q_token, 'offer_accept', id=oid)
        self.assertEqual(self.p['items'], {'canned':1, 'ammo9':10}); self.assertEqual(q['items'], {'canned':1})


if __name__ == '__main__':
    unittest.main()
