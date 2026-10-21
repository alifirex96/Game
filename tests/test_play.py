import random
import unittest

from server import World, GameError
from world_data import CARS


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
