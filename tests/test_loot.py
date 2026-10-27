"""Loot in buildings, picking up, dropping and taking things from bodies."""
import math
import unittest
from server import GameError
from world_data import FISTS, LOOT_TABLES, ITEMS, MAX_GUNS
from helpers import quiet_world, act, run


class LootTests(unittest.TestCase):
    def setUp(self):
        self.w = quiet_world(4)
        self.token = self.w.join('Мародёр'); self.p = self.w.players[self.token]

    def put(self, item, n=1, mag=0):
        return self.w._loot_add(item, n, self.p['x'] + 20, self.p['y'], None, mag)

    def test_every_table_item_exists(self):
        for table in LOOT_TABLES.values():
            for item, weight, low, high in table:
                self.assertIn(item, ITEMS); self.assertLessEqual(low, high)

    def test_buildings_fill_when_someone_comes_near(self):
        t = self.w.towns['svetlogorsk']; self.p['x'], self.p['y'] = t['x'], t['y']
        self.assertEqual(self.w.loot, {})
        run(self.w, 2.1, [self.p])
        near = self.w.loot_near(self.p['x'], self.p['y'], 1700)
        self.assertGreater(len(near), 20)
        # Nothing appears right next to the player.
        self.assertFalse(any(abs(l['x'] - self.p['x']) < 200 and abs(l['y'] - self.p['y']) < 200 and l['spot'] for l in near))
        count = len(self.w.loot)
        run(self.w, 2.1, [self.p])
        self.assertEqual(len(self.w.loot), count)     # no restock until the timer runs out

    def test_food_goes_into_the_backpack(self):
        l = self.put('canned', 1)
        act(self.w, self.token, 'pickup', id=l['id'])
        self.assertEqual(self.p['items']['canned'], 1); self.assertNotIn(l['id'], self.w.loot)

    def test_pickup_needs_to_be_close(self):
        l = self.w._loot_add('canned', 1, self.p['x'] + 300, self.p['y'])
        with self.assertRaises(GameError):
            act(self.w, self.token, 'pickup', id=l['id'])

    def test_weapon_goes_to_hand_with_its_rounds(self):
        l = self.put('w_ak', 1, mag=7)
        act(self.w, self.token, 'pickup', id=l['id'])
        self.assertIn(2, self.p['weapons']); self.assertEqual(self.p['gear']['weapon'], 2); self.assertEqual(self.p['mags']['2'], 7)

    def test_only_three_guns(self):
        self.p['weapons'] = [0, 1, 2, FISTS]
        l = self.put('w_sks')
        with self.assertRaisesRegex(GameError, 'трёх'):
            act(self.w, self.token, 'pickup', id=l['id'])
        knife = self.put('w_knife')
        act(self.w, self.token, 'pickup', id=knife['id'])
        self.assertIn(8, self.p['weapons'])
        self.assertEqual(MAX_GUNS, 3)

    def test_gear_is_worn_and_the_old_one_dropped(self):
        self.p['gear']['clothes'] = 1
        l = self.put('peacoat')
        act(self.w, self.token, 'pickup', id=l['id'])
        self.assertEqual(self.p['gear']['clothes'], 3)
        self.assertTrue(any(o['item'] == 'vatnik' for o in self.w.loot.values()))

    def test_smaller_backpack_must_fit_the_things(self):
        self.p['gear']['backpack'] = 3; self.p['items'] = {k:1 for k in ('canned', 'water', 'tea', 'medkit', 'repairkit', 'canister', 'soda', 'apple', 'beans', 'pills', 'crackers', 'bandage', 'meat', 'herbs')}
        l = self.put('bag')
        with self.assertRaises(GameError):
            act(self.w, self.token, 'pickup', id=l['id'])

    def test_drop_and_pick_back(self):
        self.p['items'] = {'ammo9':20}
        act(self.w, self.token, 'drop', item='ammo9', count=20)
        self.assertNotIn('ammo9', self.p['items'])
        l = next(o for o in self.w.loot.values() if o['item'] == 'ammo9')
        act(self.w, self.token, 'pickup', id=l['id'])
        self.assertEqual(self.p['items']['ammo9'], 20)

    def test_drop_weapon_keeps_magazine(self):
        self.p['weapons'] = [0, FISTS]; self.p['gear']['weapon'] = 0; self.p['mags'] = {'0':6}
        act(self.w, self.token, 'drop', item='w:0')
        self.assertEqual(self.p['weapons'], [FISTS]); self.assertEqual(self.p['gear']['weapon'], FISTS)
        l = next(o for o in self.w.loot.values() if o['item'] == 'w_pm')
        self.assertEqual(l['mag'], 6)
        with self.assertRaises(GameError):
            act(self.w, self.token, 'drop', item='w:%d' % FISTS)

    def test_body_gives_back_guns_and_clothes(self):
        q_token = self.w.join('Жертва'); q = self.w.players[q_token]
        q['weapons'] = [2, FISTS]; q['gear'].update(weapon=2, clothes=2); q['mags'] = {'2':12}; q['items'] = {'canned':1}
        q['x'], q['y'] = self.p['x'] + 30, self.p['y']
        self.w._damage(q, 999)
        body = next(b for b in self.w.bodies.values() if b.get('player') == q['id'])
        act(self.w, self.token, 'loot_body', id=body['id'])
        self.assertIn(2, self.p['weapons']); self.assertEqual(self.p['mags']['2'], 12)
        self.assertEqual(self.p['gear']['clothes'], 2); self.assertEqual(self.p['items'].get('canned'), 1)

    def test_old_loot_vanishes(self):
        l = self.w._loot_add('apple', 1, self.p['x'] + 3000, self.p['y'])
        l['until'] = self.w.elapsed
        run(self.w, 2.1, [self.p])
        self.assertNotIn(l['id'], self.w.loot)


if __name__ == '__main__':
    unittest.main()
