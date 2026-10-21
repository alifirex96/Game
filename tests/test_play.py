import random
import unittest

from server import World, GameError
from world_data import CARS, WEAPONS


class PassengerTests(unittest.TestCase):
    def setUp(self):
        self.w = World(None, rng=random.Random(5))
        self.tokens = [self.w.join('P%d' % i) for i in range(9)]
        self.ps = [self.w.players[t] for t in self.tokens]
        self.n = 0
        driver = self.ps[0]; car = driver['car']
        for p in self.ps[1:]:
            p['x'], p['y'] = car['x'] + 20, car['y'] + 20
            p['car']['x'], p['car']['y'] = car['x'] + 3000, car['y']

    def op(self, i, **data):
        self.n += 1
        data['request_id'] = 'req%04d' % self.n
        self.w.elapsed += 1
        return self.w.command(self.tokens[i], data)

    def test_light_car_takes_three_passengers(self):
        self.ps[0]['car']['model'] = 2
        for i in (1, 2, 3):
            r = self.op(i, op='vehicle')
            self.assertIn('пассажир', r['title'].lower())
            self.assertEqual(self.ps[i]['ride'], self.ps[0]['id'])
        with self.assertRaises(GameError):
            self.op(4, op='vehicle')

    def test_bukhanka_takes_seven(self):
        self.ps[0]['car']['model'] = next(i for i, c in enumerate(CARS) if c['id'] == 'bukhanka')
        for i in range(1, 8):
            self.op(i, op='vehicle')
        with self.assertRaises(GameError):
            self.op(8, op='vehicle')

    def test_passenger_moves_with_the_car_and_steps_out(self):
        self.op(1, op='vehicle')
        self.op(0, op='vehicle')
        self.assertTrue(self.ps[0]['vehicle'])
        self.ps[0]['car']['x'] += 500
        self.w.tick(.05)
        self.assertAlmostEqual(self.ps[1]['x'], self.ps[0]['car']['x'], delta=1)
        self.op(1, op='vehicle')
        self.assertFalse(self.ps[1]['vehicle'])
        self.assertIsNone(self.ps[1]['ride'])
        self.assertLess(abs(self.ps[1]['x'] - self.ps[0]['car']['x']), 120)

    def test_wrecked_car_drops_passengers(self):
        self.op(1, op='vehicle')
        self.ps[0]['car']['wrecked_until'] = self.w.elapsed + 30
        self.w.tick(.05)
        self.assertFalse(self.ps[1]['vehicle'])


if __name__ == '__main__':
    unittest.main()


class BleedingTests(unittest.TestCase):
    def setUp(self):
        self.w = World(None, rng=random.Random(2))
        self.t = self.w.join('Раненый'); self.p = self.w.players[self.t]; self.n = 0

    def heal(self):
        self.n += 1; self.w.elapsed += 10
        return self.w.command(self.t, {'op':'heal', 'request_id':'heal%04d' % self.n})

    def test_field_dressing_stops_bleeding(self):
        self.p['items'].pop('bandage', None); self.p['items'].pop('medkit', None)
        self.p['bleeding'] = True; self.p['hp'] = 50
        self.heal()
        self.assertFalse(self.p['bleeding'])

    def test_bleeding_at_full_health_can_be_dressed(self):
        self.p['items']['bandage'] = 1; self.p['bleeding'] = True; self.p['hp'] = self.w.max_hp(self.p)
        self.heal()
        self.assertFalse(self.p['bleeding'])

    def test_cloth_when_no_supplies(self):
        self.p['items'] = {'cloth': 2}; self.p['bleeding'] = True; self.p['hp'] = 40
        self.w.stocks[self.p['faction']]['food'] = 0
        self.heal()
        self.assertFalse(self.p['bleeding'])
        self.assertEqual(self.p['items'].get('cloth'), 1)


class NewWorldTests(unittest.TestCase):
    def test_reset_starts_over_and_keeps_a_backup(self):
        import tempfile, os
        from pathlib import Path
        d = tempfile.mkdtemp(); path = Path(d) / 'world.json'
        w = World(str(path), rng=random.Random(3)); w.room_code = '654321'
        tok = w.join('Старик'); w.players[tok]['coins'] = 999; w.elapsed = 5000; w.save()
        lock = w.lock
        backup = w.reset()
        self.assertTrue(backup.exists())
        self.assertEqual(w.players, {})
        self.assertLess(w.elapsed, 1)
        self.assertIs(w.lock, lock)
        self.assertEqual(w.room_code, '654321')
        with self.assertRaises(GameError) as e:
            w.player(tok)
        self.assertIn('новую игру', str(e.exception))
        again = World(str(path), rng=random.Random(4))
        self.assertEqual(again.players, {})
        self.assertEqual(len(os.listdir(d)), 2)


class CorpseTests(unittest.TestCase):
    def setUp(self):
        self.w = World(None, rng=random.Random(11))
        self.t = self.w.join('Охотник'); self.p = self.w.players[self.t]

    def kill(self, kind, faction):
        npc = self.w.spawn_npc(kind, faction, self.p['x'] + 40, self.p['y'])
        npc['angle'] = 1.2
        self.w.hurt(npc, 999, self.p)
        for _ in range(40):
            self.w.tick(.1)
        return npc

    def test_dead_people_and_animals_stay_on_the_ground(self):
        for kind, faction in (('marauder', 'marauders'), ('wolf', 'wild')):
            npc = self.kill(kind, faction)
            self.assertNotIn(npc['id'], self.w.npcs)
            body = self.w.bodies.get('n' + npc['id'])
            self.assertIsNotNone(body, kind)
            self.assertEqual(body['npc']['type'], kind)
            self.assertEqual(body['npc']['angle'], 1.2)

    def test_what_the_dead_carried_is_on_the_body(self):
        self.w.rng = random.Random(0)
        npc = self.w.spawn_npc('marauder', 'marauders', self.p['x'] + 40, self.p['y'])
        self.w.hurt(npc, 999, self.p)
        npc['loot'] = {'ammo9': 4}
        before = self.p['items'].get('ammo9', 0)
        for _ in range(30):
            self.w.tick(.1)
        bid = 'n' + npc['id']
        self.assertEqual(self.w.bodies[bid]['items'], {'ammo9': 4})
        self.w.loot_body(self.p, bid)
        self.assertEqual(self.p['items'].get('ammo9', 0), before + 4)
        self.assertIn(bid, self.w.bodies)                    # the body stays, just empty

    def test_corpses_go_after_five_minutes(self):
        npc = self.kill('marauder', 'marauders')
        self.w.elapsed += 301
        self.w.tick(.1)
        self.assertNotIn('n' + npc['id'], self.w.bodies)


class RespawnAmmoTests(unittest.TestCase):
    def test_coming_back_with_a_full_magazine_and_spare_rounds(self):
        w = World(None, rng=random.Random(12))
        t = w.join('Невезучий'); p = w.players[t]
        p['mags'] = {'0': 0}; p['items'] = {}
        w._damage(p, 999)
        self.assertEqual(p['items'], {})                   # everything stayed on the body
        for _ in range(80):
            w.tick(.1)
        self.assertGreater(p['hp'], 0)
        self.assertEqual(w._mag(p), 8)
        self.assertEqual(p['items'].get('ammo9'), 16)

    def test_every_owned_gun_comes_back_loaded(self):
        w = World(None, rng=random.Random(14))
        t = w.join('Стрелок'); p = w.players[t]
        p['weapons'] = [0, 1, 2, 3, 5]; p['gear']['weapon'] = 0; p['mags'] = {}; p['items'] = {}
        w._damage(p, 999)
        for _ in range(80):
            w.tick(.1)
        self.assertEqual(p['weapons'], [0, 1, 2, 3, 5])                # nothing is lost
        for i in p['weapons']:
            p['gear']['weapon'] = i
            self.assertEqual(w._mag(p), WEAPONS[i]['mag'])
        self.assertEqual(p['items'].get('ammo9'), 16)
        self.assertEqual(p['items'].get('ammo762'), 30)
        self.assertGreaterEqual(p['items'].get('shells', 0), 6)          # the shotgun and the sawn-off share one stack
        self.assertGreaterEqual(p['items'].get('ammo54', 0), 6)


class RoadWreckTests(unittest.TestCase):
    def test_wrecks_are_rare_and_solid(self):
        import math
        w = World(None, rng=random.Random(13))
        road = sum(math.hypot(s[2] - s[0], s[3] - s[1]) for s in w.terrain.road_segments)
        self.assertGreater(len(w.terrain.wrecks), 20)
        self.assertGreater(road / len(w.terrain.wrecks), 5000)          # about one per 7 km of highway
        wr = w.terrain.wrecks[0]
        self.assertTrue(w.blocked(wr['x'], wr['y'], 10))                  # a person cannot walk through
        t = w.join('Водитель'); p = w.players[t]
        spec = w.car_spec(p)
        self.assertTrue(w._car_blocked(spec, wr['x'], wr['y'], 0.0))       # nor drive through
        self.assertFalse(w.blocked(wr['x'] + 400, wr['y'] + 400, 10) and w.terrain.wreck_hit(wr['x'] + 400, wr['y'] + 400, 10))
