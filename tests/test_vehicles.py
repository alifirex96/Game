"""Car physics on the host."""
import math
import random
import time
import unittest
from server import GameError, World
from world_data import CARS


class VehicleTests(unittest.TestCase):
    def setUp(self):
        self.w = World(rng=random.Random(5))
        self.w.settings['ai'] = False
        for name in ('_spawn_marauders', '_spawn_creatures', 'tick_garrisons'):
            setattr(self.w, name, lambda active: None)
        self.token = self.w.join('Водитель'); self.p = self.w.players[self.token]
        # The longest straight stretch of highway outside settlements.
        ax, ay, bx, by, a, b = max(self.w.terrain.road_segments, key=lambda s: math.hypot(s[2] - s[0], s[3] - s[1]))
        self.dir = math.atan2(by - ay, bx - ax)
        u = .2; self.start = (ax + (bx - ax) * u, ay + (by - ay) * u)
        self.p['car'] = self.w.new_car(self.start[0], self.start[1], self.dir, 40.0, 2)
        self.p['x'], self.p['y'] = self.start
        self.p['vehicle'] = True

    def run_input(self, steer, throttle, seconds, handbrake=False):
        for i in range(int(seconds / .05)):
            self.p['input'] = [steer, -throttle, handbrake]
            self.p['last_input'] = self.p['last_seen'] = time.monotonic()
            self.w.tick(.05)

    def speed(self):
        return math.hypot(self.p['car']['vx'], self.p['car']['vy'])

    def test_accelerates_brakes_and_reverses(self):
        self.run_input(0, 1, 1.0)
        early = self.speed()
        self.run_input(0, 1, 3.0)
        self.assertGreater(self.speed(), early)
        self.assertLessEqual(self.speed(), CARS[2]['max'] * 1.01)
        top = self.speed()
        self.run_input(0, -1, .4)                  # brakes first...
        self.assertLess(self.speed(), top - 150)
        self.run_input(0, -1, 2.0)                 # ...then backs up slowly
        car = self.p['car']; fwd = car['vx'] * math.cos(car['angle']) + car['vy'] * math.sin(car['angle'])
        self.assertLess(fwd, 0)
        self.assertGreaterEqual(fwd, -CARS[2]['max'] * .36)

    def test_steering_needs_speed(self):
        a0 = self.p['car']['angle']
        self.run_input(1, 0, 1.0)
        self.assertAlmostEqual(self.p['car']['angle'], a0, places=3)      # a standing car does not spin
        self.run_input(1, 1, 1.0)
        self.assertNotAlmostEqual(self.p['car']['angle'], a0, places=2)

    def test_exit_only_when_stopped_and_on_the_drivers_side(self):
        self.run_input(0, 1, 2.0)
        with self.assertRaises(GameError):
            self.w.command(self.token, {'op':'vehicle', 'request_id':'exit-1'})
        self.run_input(0, 0, 2.0, handbrake=True)
        car = self.p['car']
        self.w.command(self.token, {'op':'vehicle', 'request_id':'exit-2'})
        self.assertFalse(self.p['vehicle'])
        # Left of the heading (y grows downwards): the driver's door.
        side = (self.p['x'] - car['x']) * math.sin(car['angle']) - (self.p['y'] - car['y']) * math.cos(car['angle'])
        self.assertGreater(side, 0)

    def test_hard_crash_damages_the_car(self):
        car = self.p['car']; spec = CARS[car['model']]
        car['vx'], car['vy'] = math.cos(car['angle']) * 400, math.sin(car['angle']) * 400
        self.w.blocked = lambda x, y, r: True        # a wall everywhere
        self.w.drive(self.p, .05, 0, 1, False, 0)
        self.assertLess(car['hp'], 100)
        self.assertLess(math.hypot(car['vx'], car['vy']), 150)

    def test_running_over_a_marauder_hurts_him(self):
        car = self.p['car']
        m = self.w.spawn_npc('marauder', 'marauders', car['x'] + math.cos(car['angle']) * 30, car['y'] + math.sin(car['angle']) * 30)
        car['vx'], car['vy'] = math.cos(car['angle']) * 300, math.sin(car['angle']) * 300
        self.w._build_grid()
        self.w.drive(self.p, .02, 0, 1, False, 0)
        self.assertLess(m['hp'], m['max'])

    def test_buying_a_car_replaces_the_old_one(self):
        self.p['vehicle'] = False
        t = self.w.towns['revda']; self.p['x'], self.p['y'] = t['x'], t['y'] + 40
        self.p['coins'] = 1000; self.p['level'] = 6
        self.w.command(self.token, {'op':'buy', 'town':'revda', 'kind':'car', 'index':5, 'request_id':'buy-niva'})
        self.assertEqual(self.p['car']['model'], 5)
        self.assertEqual(self.p['coins'], 1000 - CARS[5]['price'])
        self.assertLessEqual(self.p['car']['fuel'], CARS[5]['tank'])
