"""Cars standing in the world: seats, driving, fuel, repairs and wrecks."""
import math
import unittest
from server import GameError
from world_data import CARS, WORLD_CARS
from helpers import quiet_world, act, run


class VehicleTests(unittest.TestCase):
    def setUp(self):
        self.w = quiet_world(5)
        self.token = self.w.join('Водитель'); self.p = self.w.players[self.token]
        ax, ay, bx, by, a, b = max(self.w.terrain.road_segments, key=lambda s: math.hypot(s[2] - s[0], s[3] - s[1]))
        self.dir = math.atan2(by - ay, bx - ax)
        self.start = (ax + (bx - ax) * .2, ay + (by - ay) * .2)
        self.w.cars.clear()
        self.car = self.w.new_car(self.start[0], self.start[1], self.dir, 2)
        self.car.update(fuel=30.0, hp=100.0)
        self.p['x'], self.p['y'] = self.start[0] + 10, self.start[1]

    def drive(self, steer, throttle, seconds, handbrake=False):
        for i in range(int(seconds / .05)):
            self.p['input'] = [steer, -throttle, handbrake]
            run(self.w, .05, [self.p])

    def test_world_is_stocked_with_cars(self):
        w = quiet_world(2)
        self.assertEqual(len(w.cars), WORLD_CARS)
        for c in w.cars.values():
            self.assertLessEqual(c['fuel'], CARS[c['model']]['tank'])
            self.assertFalse(w.terrain.water(c['x'], c['y']))

    def test_anyone_can_drive_and_fuel_burns(self):
        act(self.w, self.token, 'vehicle')
        self.assertEqual(self.p['seat'], 'driver')
        self.drive(0, 1, 3)
        moved = math.hypot(self.car['x'] - self.start[0], self.car['y'] - self.start[1])
        self.assertGreater(moved, 200); self.assertLess(self.car['fuel'], 30)

    def test_empty_tank_does_not_go(self):
        self.car['fuel'] = 0
        act(self.w, self.token, 'vehicle')
        self.drive(0, 1, 2)
        self.assertLess(math.hypot(self.car['x'] - self.start[0], self.car['y'] - self.start[1]), 5)

    def test_passengers_ride_and_seats_run_out(self):
        act(self.w, self.token, 'vehicle')
        riders = []
        for i in range(CARS[2]['seats'] - 1):
            t = self.w.join('Пассажир %d' % i); q = self.w.players[t]
            q['x'], q['y'] = self.car['x'], self.car['y'] + 30
            act(self.w, t, 'vehicle'); riders.append(q)
            self.assertEqual(q['seat'], 'passenger')
        t = self.w.join('Лишний'); q = self.w.players[t]; q['x'], q['y'] = self.car['x'], self.car['y'] + 30
        with self.assertRaisesRegex(GameError, 'Мест нет'):
            act(self.w, t, 'vehicle')
        self.drive(0, 1, 2)
        self.assertEqual((riders[0]['x'], riders[0]['y']), (self.car['x'], self.car['y']))
        self.drive(0, 0, 3, True)
        act(self.w, self.token, 'vehicle')
        self.assertFalse(self.p['vehicle']); self.assertIsNone(self.w.car_driver(self.car))

    def test_refuel_from_canister_and_repair(self):
        self.car['fuel'] = 0; self.car['hp'] = 40
        self.p['items'] = {'canister':1, 'repairkit':1}
        act(self.w, self.token, 'refuel'); self.assertEqual(self.car['fuel'], 20)
        act(self.w, self.token, 'repair'); self.assertEqual(self.car['hp'], 100)
        with self.assertRaises(GameError):
            act(self.w, self.token, 'refuel')

    def test_wreck_throws_everybody_out_and_is_replaced_later(self):
        act(self.w, self.token, 'vehicle')
        self.w.wreck_car(self.car)
        self.assertFalse(self.p['vehicle'])
        with self.assertRaises(GameError):
            act(self.w, self.token, 'vehicle')
        self.w.elapsed += 5000
        self.w.fill_cars()
        self.assertNotIn(self.car['id'], self.w.cars)
        self.assertEqual(len(self.w.cars), WORLD_CARS)


if __name__ == '__main__':
    unittest.main()
