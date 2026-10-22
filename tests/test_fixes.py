"""Regressions found in the full play-through before 0.7."""
import random
import unittest
from server import GameError, World
from world_data import CARS
from test_features import open_ground


class FixTests(unittest.TestCase):
    def setUp(self):
        self.w = World(rng=random.Random(5))
        self.w.settings['ai'] = False
        for name in ('_spawn_marauders', '_spawn_creatures', 'tick_garrisons'):
            setattr(self.w, name, lambda active: None)
        self.ta = self.w.join('Водитель'); self.a = self.w.players[self.ta]
        self.tb = self.w.join('Попутчик'); self.b = self.w.players[self.tb]

    def act(self, token, op, **data):
        data.update(op=op, request_id='f' + str(random.random()))
        return self.w.command(token, data)

    def test_free_goods_are_not_sold(self):
        town = next(iter(self.w.towns.values()))
        self.a['x'], self.a['y'] = town['x'], town['y']
        with self.assertRaises(GameError):
            self.act(self.ta, 'buy', town=town['id'], kind='meat', count=50)
        self.assertNotIn('meat', self.a['items'])

    def test_bad_op_is_a_game_error(self):
        for op in (None, ['a'], 5):
            with self.assertRaises(GameError):
                self.w.command(self.ta, {'op':op, 'request_id':'xxxx1'})

    def test_dead_driver_lets_passengers_out(self):
        car = self.a['car']; self.a['vehicle'] = True
        self.a['x'], self.a['y'] = car['x'], car['y']
        self.b['x'], self.b['y'] = car['x'] + 10, car['y']
        self.assertIs(self.w.board(self.b), self.a)
        car['vx'] = 300.0
        self.w._damage(self.a, 999)
        self.assertEqual(car['vx'], 0.0)
        self.assertFalse(self.b['vehicle']); self.assertIsNone(self.b.get('ride'))

    def test_wedged_car_eases_out(self):
        x, y = open_ground(self.w)
        car = self.a['car']; car.update(x=x, y=y, angle=0.0, vx=0.0, vy=0.0)
        wall = {'x':x, 'y':y, 'w':30, 'h':30}
        self.w.terrain.add_rect(wall)
        spec = CARS[car['model']]
        self.assertTrue(self.w._car_blocked(spec, x, y, 0.0))
        self.a['vehicle'] = True
        self.w.drive(self.a, .05, 0, 1, False, 0)
        self.assertFalse(self.w._car_blocked(spec, car['x'], car['y'], car['angle']))
        self.w.terrain.remove_rect(wall)

    def test_quest_rests_after_hand_in(self):
        g = next(g for g in self.w.givers.values() if g['type'] == 'trader')
        self.a['x'], self.a['y'] = g['x'], g['y'] + 30
        self.act(self.ta, 'quest_accept', giver=g['id'], kind='explore')
        q = self.a['quests'][0]; self.a['stats']['explore'] = q['start'] + q['target']
        self.act(self.ta, 'quest_turnin', giver=g['id'], id=q['id'])
        offers = [o['kind'] for o in self.w.dialog(self.a, g)['offers']]
        self.assertNotIn('explore', offers)
        with self.assertRaises(GameError):
            self.act(self.ta, 'quest_accept', giver=g['id'], kind='explore')
        self.w.elapsed += 601
        self.act(self.ta, 'quest_accept', giver=g['id'], kind='explore')

    def test_house_wall_can_be_patched(self):
        house = next(h for h in self.w.terrain.houses.values() if h['walls'])
        self.a['x'], self.a['y'] = house['x'], house['y']
        camp = self.w.found_camp(self.a)
        slot = next(k for k in camp['fence'] if k.startswith('w'))
        self.w.damage_camp_piece(camp, slot, 99999)
        self.assertTrue(self.w.camp_breached(camp))
        self.a['items'] = {'planks':10, 'nails':20}
        self.w.build_part(self.a, camp, 'wall')
        self.assertGreater(camp['fence'][slot]['hp'], 0)

    def test_crate_must_be_built_before_use(self):
        self.a['x'], self.a['y'] = open_ground(self.w)
        camp = self.w.found_camp(self.a)
        self.a['items'] = {'scrap':5}
        with self.assertRaises(GameError):
            self.w.stash_move(self.a, camp, 'scrap', 5, True)

    def test_newcomers_wake_up_in_warm_regions(self):
        from world_data import REGIONS
        for _ in range(10):
            self.w._place_randomly(self.a)
            town = min(self.w.towns.values(), key=lambda t: (t['x'] - self.a['x']) ** 2 + (t['y'] - self.a['y']) ** 2)
            self.assertLessEqual(REGIONS[town['region']]['cold'], 2)


if __name__ == '__main__':
    unittest.main()
