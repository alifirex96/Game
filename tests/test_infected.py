"""The infected: zones, senses, chasing, biting; melee and gunfire."""
import math
import unittest
from npc import NpcMixin
from world_data import FISTS, NPC_TYPES, TOWN_INFECTED
from helpers import quiet_world, act, run


class InfectedTests(unittest.TestCase):
    def setUp(self):
        self.w = quiet_world(6)
        self.token = self.w.join('Выживший'); self.p = self.w.players[self.token]
        self.w.weather = {'kind':'clear', 'until':1e9}
        self.w.elapsed = 100      # daytime

    def clear_spot(self):
        t = self.w.towns['kamenka']
        for r in range(1500, 5000, 100):
            x, y = t['x'] + r, t['y']
            if all(self.w.terrain.free_spot(x + dx, y, 20) for dx in range(-500, 501, 25)):
                return x, y
        self.fail('no clear spot')

    def test_zone_fills_and_empties(self):
        w = quiet_world(6); w.elapsed = 100
        p = w.players[w.join('Гость')]
        t = w.towns['svetlogorsk']; p['x'], p['y'] = t['x'], t['y']
        NpcMixin._tick_zones(w, 1.0, [p])
        here = [n for n in w.npcs.values() if n.get('zone') == 't:svetlogorsk']
        self.assertEqual(len(here), TOWN_INFECTED['city'])
        p['x'] = t['x'] + 20000
        for i in range(50):
            NpcMixin._tick_zones(w, 1.0, [p])
        self.assertFalse([n for n in w.npcs.values() if n.get('zone') == 't:svetlogorsk'])
        self.assertEqual(w.zones['t:svetlogorsk']['left'], TOWN_INFECTED['city'])

    def test_killed_infected_are_counted_off_the_zone(self):
        z = self.w.zones['t:kamenka']; left = z['left']
        n = self.w.spawn_npc('infected', self.p['x'] + 200, self.p['y'], zone='t:kamenka')
        self.w.hurt(n, 999, self.p)
        self.assertEqual(z['left'], left - 1); self.assertEqual(self.p['stats']['infected'], 1)

    def test_sees_a_runner_further_than_a_walker(self):
        n = self.w.spawn_npc('infected', 0, 0)
        self.p['input'] = [1, 0, True]; run_ = self.w._sight(n, self.p)
        self.p['input'] = [1, 0, False]; walk = self.w._sight(n, self.p)
        self.p['input'] = [0, 0, False]; still = self.w._sight(n, self.p)
        self.assertGreater(run_, walk); self.assertGreater(walk, still)

    def test_chases_and_bites(self):
        x, y = self.clear_spot()
        self.p['x'], self.p['y'] = x, y
        n = self.w.spawn_npc('infected', x + 180, y)
        self.p['input'] = [0, 0, False]
        run(self.w, .5, [self.p])
        self.assertEqual(n['mode'], 'chase')
        run(self.w, 4, [self.p])
        self.assertLess(self.p['hp'], 100)

    def test_hears_a_shot(self):
        x, y = self.clear_spot()
        self.p['x'], self.p['y'] = x, y
        n = self.w.spawn_npc('infected', x + 700, y)
        self.p['weapons'] = [0, FISTS]; self.p['gear']['weapon'] = 0; self.p['mags'] = {'0':8}; self.p['aim'] = [0, 1]
        run(self.w, .5, [self.p])
        self.assertEqual(n['mode'], 'idle')
        act(self.w, self.token, 'shoot')
        run(self.w, .5, [self.p])
        self.assertIn(n['mode'], ('alert', 'chase'))

    def test_axe_kills_with_two_blows(self):
        x, y = self.clear_spot(); self.p['x'], self.p['y'] = x, y
        n = self.w.spawn_npc('infected', x + 40, y)
        self.p['weapons'] = [9, FISTS]; self.p['gear']['weapon'] = 9; self.p['aim'] = [1, 0]
        act(self.w, self.token, 'shoot')
        self.assertLess(n['hp'], NPC_TYPES['infected']['hp'])
        self.w.elapsed += 2
        act(self.w, self.token, 'shoot')
        self.assertLessEqual(n['hp'], 0)

    def test_fists_miss_behind_the_back(self):
        x, y = self.clear_spot(); self.p['x'], self.p['y'] = x, y
        n = self.w.spawn_npc('infected', x - 40, y)
        self.p['aim'] = [1, 0]
        act(self.w, self.token, 'shoot')
        self.assertEqual(n['hp'], NPC_TYPES['infected']['hp'])

    def test_dead_infected_leaves_a_body(self):
        n = self.w.spawn_npc('infected', self.p['x'] + 100, self.p['y'])
        self.w.hurt(n, 999, self.p)
        run(self.w, 3, [self.p])
        self.assertIn('n' + n['id'], self.w.bodies)

    def test_animal_carcass_has_meat(self):
        n = self.w.spawn_npc('elk', self.p['x'] + 100, self.p['y'])
        self.w.hurt(n, 999, self.p)
        self.assertEqual(n['loot']['meat_raw'], NPC_TYPES['elk']['meat']); self.assertEqual(self.p['stats']['animals'], 1)

    def test_tetracycline_cures(self):
        self.p['sick'] = self.w.elapsed + 100; self.p['items'] = {'pills':1}
        act(self.w, self.token, 'use', item='pills')
        self.assertEqual(self.p['sick'], 0)


if __name__ == '__main__':
    unittest.main()
