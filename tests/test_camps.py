"""Camps, crafting, ammunition and searching abandoned houses."""
import random
import time
import unittest
from server import GameError, World
from world_data import WEAPONS
from test_features import open_ground


class CampTests(unittest.TestCase):
    def setUp(self):
        self.w = World(rng=random.Random(8))
        self.w.settings['ai'] = False
        for name in ('_spawn_marauders', '_spawn_creatures', 'tick_garrisons'):
            setattr(self.w, name, lambda active: None)
        self.ta = self.w.join('Хозяин'); self.a = self.w.players[self.ta]
        self.tb = self.w.join('Гость'); self.b = self.w.players[self.tb]
        self.spot = open_ground(self.w)
        self.a['x'], self.a['y'] = self.spot
        self.a['items'] = {'planks':60, 'nails':120, 'scrap':10, 'cloth':10}
        self.a['gear']['backpack'] = 3

    def act(self, token, op, **data):
        data.update(op=op, request_id='c' + str(random.random()))
        return self.w.command(token, data)

    def fence(self, camp):
        for i in range(8):
            self.w.build_part(self.a, camp, 'wall')
        self.w.build_part(self.a, camp, 'gate')

    def test_fence_keeps_strangers_out_and_lets_the_clan_in(self):
        self.act(self.ta, 'camp_found')
        camp = self.w.camp_of(self.a['faction'])
        self.a['x'] -= 40; self.a['y'] -= 40           # stand clear of the gate's place
        self.fence(camp)
        self.assertFalse(self.w.camp_breached(camp))
        gate = camp['fence']['gate']['rect']
        self.assertFalse(self.w.blocked(gate['x'], gate['y'], 6, self.a['faction']))
        self.assertTrue(self.w.blocked(gate['x'], gate['y'], 6, self.b['faction']))
        self.w.sides[self.a['faction']]['clan'] = self.w.sides[self.b['faction']]['clan'] = 'c1'
        self.w.clans['c1'] = {'id':'c1', 'name':'К', 'tag':'К', 'leader':self.a['faction'], 'members':[self.a['faction'], self.b['faction']], 'invites':[], 'color':'#fff'}
        self.assertFalse(self.w.blocked(gate['x'], gate['y'], 6, self.b['faction']))

    def test_a_breached_fence_opens_the_stash(self):
        self.act(self.ta, 'camp_found')
        camp = self.w.camp_of(self.a['faction'])
        self.a['x'] -= 40; self.a['y'] -= 40
        self.fence(camp); self.w.build_part(self.a, camp, 'stash')
        self.w.stash_move(self.a, camp, 'scrap', 5, True)
        self.b['x'], self.b['y'] = camp['x'], camp['y'] + 130          # outside the gate
        with self.assertRaises(GameError):
            self.act(self.tb, 'stash_take', camp=camp['id'], item='scrap', count=5)
        # Shots break a section of the fence; then the crate is open to anyone.
        wall = camp['fence']['n1']['rect']
        self.b['x'], self.b['y'] = wall['x'], wall['y'] - 200; self.b['aim'] = [0, 1]
        self.w.stocks[self.b['faction']]['metal'] = 99
        for i in range(40):
            self.w.elapsed += 1; self.b['mags']['0'] = 8
            try:
                self.act(self.tb, 'shoot')
            except GameError:
                pass
        self.assertLessEqual(camp['fence']['n1']['hp'], 0)
        self.assertFalse(self.w.terrain.solid(wall['x'], wall['y'], 1))
        self.assertTrue(self.w.camp_breached(camp))
        self.b['x'], self.b['y'] = camp['x'], camp['y']
        self.act(self.tb, 'stash_take', camp=camp['id'], item='scrap', count=5)
        self.assertEqual(self.b['items'].get('scrap'), 5)

    def test_camp_in_an_abandoned_house_uses_its_walls(self):
        house = next(h for h in self.w.terrain.houses.values() if h['kind'] == 'panel')
        self.a['x'], self.a['y'] = house['x'], house['y']
        camp = self.w.found_camp(self.a)
        self.assertEqual(camp['house'], house['id'])
        self.assertTrue(self.w.camp_breached(camp))                 # the doorway is open
        self.a['x'], self.a['y'] = house['x'] + 20, house['y']
        self.w.build_part(self.a, camp, 'gate')                     # a door
        self.assertFalse(self.w.camp_breached(camp))
        with self.assertRaises(GameError):
            self.w.build_part(self.a, camp, 'wall')
        self.b['x'], self.b['y'] = house['x'], house['y']
        with self.assertRaises(GameError):
            self.w.found_camp(self.b)                               # someone lives here already

    def test_bed_brings_you_back_to_camp(self):
        camp = self.w.found_camp(self.a)
        self.w.build_part(self.a, camp, 'bed')
        self.w._damage(self.a, 9999)
        self.w.elapsed = self.a['dead_until'] + .1
        self.a['last_seen'] = time.monotonic(); self.w.tick(.05)
        bed = camp['parts']['bed']
        self.assertLess(abs(self.a['x'] - bed['x']) + abs(self.a['y'] - bed['y']), 30)
        self.assertEqual(len(self.w.bodies), 1)

    def test_bench_makes_ammo_and_reload_uses_it(self):
        camp = self.w.found_camp(self.a)
        self.w.build_part(self.a, camp, 'bench')
        bench = camp['parts']['bench']; self.a['x'], self.a['y'] = bench['x'] + 20, bench['y']
        self.a['items'].update(gunpowder=1); self.a['items'].pop('ammo9', None)
        self.act(self.ta, 'craft_item', id='ammo9')
        self.assertEqual(self.a['items']['ammo9'], 10)
        self.a['mags']['0'] = 0
        self.act(self.ta, 'reload')
        self.assertEqual(self.a['mags']['0'], WEAPONS[0]['mag'])
        self.assertEqual(self.a['items']['ammo9'], 10 - WEAPONS[0]['mag'])
        self.a['items'].pop('ammo9'); self.a['mags']['0'] = 0; self.w.elapsed += 5
        with self.assertRaises(GameError):
            self.act(self.ta, 'reload')
        with self.assertRaises(GameError):
            self.act(self.ta, 'craft_item', id='ammo9')             # no gunpowder left
        self.a['x'] += 600
        with self.assertRaises(GameError):
            self.act(self.ta, 'craft_item', id='nails')             # far from the bench

    def test_hand_crafting_and_house_search(self):
        self.act(self.ta, 'craft_item', id='bandage')
        self.assertEqual(self.a['items']['bandage'], 1)
        house = next(iter(self.w.terrain.houses.values()))
        self.b['items'] = {}; self.b['x'], self.b['y'] = house['x'], house['y']
        r = self.act(self.tb, 'search_house', id=house['id'])
        self.assertTrue(self.b['items'] or 'Пусто' in r['text'])
        with self.assertRaises(GameError):
            self.act(self.tb, 'search_house', id=house['id'])       # searched already


if __name__ == '__main__':
    unittest.main()
