"""Camps, crafting and ammunition."""
import random
import time
import unittest
from server import GameError, World
from world_data import WEAPONS, FISTS
from helpers import quiet_world, open_ground


class CampTests(unittest.TestCase):
    def setUp(self):
        self.w = quiet_world(8)
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
        self.b['weapons'] = [0, FISTS]; self.b['gear']['weapon'] = 0
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

    def test_bench_makes_a_sawnoff_and_reload_uses_ammo(self):
        camp = self.w.found_camp(self.a)
        self.w.build_part(self.a, camp, 'bench')
        bench = camp['parts']['bench']; self.a['x'], self.a['y'] = bench['x'] + 20, bench['y']
        self.a['weapons'] = [1, FISTS]; self.a['gear']['weapon'] = 1; self.a['mags'] = {'1':3}
        self.a['items'].update(tape=1, shells=1)
        self.act(self.ta, 'craft_item', id='sawnoff')
        self.assertEqual(self.a['weapons'], [3, FISTS]); self.assertEqual(self.a['gear']['weapon'], 3)
        self.assertEqual(self.a['items']['shells'], 4)              # the rounds from the long gun
        self.w.elapsed += 5
        self.act(self.ta, 'reload')
        self.assertEqual(self.a['mags']['3'], 2)
        self.assertEqual(self.a['items']['shells'], 2)
        self.a['x'] += 600
        with self.assertRaises(GameError):
            self.act(self.ta, 'craft_item', id='nails')             # far from the bench

    def test_hand_crafting(self):
        self.act(self.ta, 'craft_item', id='bandage')
        self.assertEqual(self.a['items']['bandage'], 1)
        with self.assertRaises(GameError):
            self.act(self.ta, 'craft_item', id='meat')              # needs a fire

    def test_owner_abandons_from_far_away(self):
        camp = self.w.found_camp(self.a)
        self.a['x'] += 40000                                        # a long drive away
        self.w.elapsed += 5
        self.act(self.ta, 'camp_abandon', camp=camp['id'])
        self.assertNotIn(camp['id'], self.w.camps)
        self.assertIsNone(self.w.sides[self.a['faction']]['camp'])


if __name__ == '__main__':
    unittest.main()
