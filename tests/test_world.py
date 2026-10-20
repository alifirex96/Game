"""Regression checks for the authoritative world state (stdlib only)."""
import random
import unittest
from server import GameError, World
from world_data import TOWNS, AI_SIDES, MAX_PLAYERS

class WorldTests(unittest.TestCase):
    def setUp(self):
        self.world = World(rng=random.Random(7))

    def test_map_and_resource_nodes(self):
        self.assertEqual(len(self.world.towns), len(TOWNS))
        self.assertGreaterEqual(len(self.world.towns), 15)
        self.assertGreater(len(self.world.nodes), 15)

    def test_computer_clans_hold_their_homes(self):
        for sid, name, color, home, fighter, method in AI_SIDES:
            town = self.world.towns[home]
            self.assertEqual(town['owner'], sid)
            self.assertTrue(town['base'])

    def test_every_player_is_a_side_with_a_home(self):
        a = self.world.players[self.world.join('A')]
        b = self.world.players[self.world.join('B')]
        self.assertNotEqual(a['faction'], b['faction'])
        for p in (a, b):
            home = self.world.home(p['faction'])
            self.assertEqual(home['owner'], p['faction'])
            self.assertTrue(home['base'])
            for resource in ('wood', 'stone', 'metal', 'food', 'fuel'):
                self.assertGreater(self.world.stocks[p['faction']][resource], 0)
        self.assertNotEqual(self.world.sides[a['faction']]['home'], self.world.sides[b['faction']]['home'])

    def test_player_limit(self):
        tokens = [self.world.join('P' + str(i)) for i in range(MAX_PLAYERS)]
        self.assertEqual(len(set(tokens)), MAX_PLAYERS)
        with self.assertRaises(GameError):
            self.world.join('Лишний')

    def test_reconnect_reuses_session(self):
        token = self.world.join('Player')
        self.assertEqual(self.world.join('Renamed', None, token), token)
        self.assertEqual(len(self.world.players), 1)

    def test_death_costs_coins_and_captured_towns(self):
        p = self.world.players[self.world.join('A')]
        f = p['faction']
        for tid in ('revda', 'kazan'):
            self.world.towns[tid]['owner'] = f
        p['coins'] = 500
        self.world._damage(p, 9999)
        self.assertEqual(p['coins'], 0)
        self.assertIsNone(self.world.towns['revda']['owner'])
        self.assertIsNone(self.world.towns['kazan']['owner'])
        self.assertEqual(self.world.home(f)['owner'], f)

    def test_three_active_quests(self):
        token = self.world.join('Player', 'survivors')
        self.assertEqual(len(self.world.players[token]['quests']), 3)

    def test_nonfinite_input_does_not_poison_simulation(self):
        token = self.world.join('Player', 'survivors')
        self.world.command(token, {'op':'input', 'x':float('nan'),
                                   'y':float('inf'), 'ax':float('-inf'), 'ay':0})
        self.assertEqual(self.world.players[token]['input'][:2], [0,0])
        self.world.tick(0.1)
        state = self.world.snapshot(token)
        self.assertEqual(state['me']['hp'], 100.0)

    def test_session_token_hidden_from_snapshot(self):
        token = self.world.join('Player', 'survivors')
        state = self.world.snapshot(token)
        self.assertNotIn(token, str(state))
        self.assertEqual(state['me']['faction'], self.world.players[token]['faction'])

    def test_unaffordable_action_keeps_stock(self):
        before = dict(self.world.stocks['ai_scar'])
        with self.assertRaises(GameError):
            self.world._pay('ai_scar', {'metal': 10**9})
        self.assertEqual(self.world.stocks['ai_scar'], before)

if __name__ == '__main__':
    unittest.main()
