"""Regression checks for the authoritative world state (stdlib only)."""
import random
import unittest
from server import GameError, World
from world_data import FACTIONS, TOWNS, BASES

class WorldTests(unittest.TestCase):
    def setUp(self):
        self.world = World(rng=random.Random(7))

    def test_map_and_resource_nodes(self):
        self.assertEqual(len(self.world.towns), len(TOWNS))
        self.assertEqual(len(self.world.towns), 15)
        self.assertGreater(len(self.world.nodes), 15)

    def test_initial_faction_bases(self):
        for faction, town_id in BASES.items():
            town = self.world.towns[town_id]
            self.assertEqual(town['owner'], faction)
            self.assertTrue(town['base'])

    def test_each_faction_starts_with_resources(self):
        for faction in FACTIONS:
            for resource in ('wood', 'stone', 'metal', 'food', 'fuel'):
                self.assertGreater(self.world.stocks[faction][resource], 0)

    def test_four_player_limit(self):
        tokens = [self.world.join('P'+str(i), faction)
                  for faction in FACTIONS for i in range(2)]
        self.assertEqual(len(set(tokens)), 4)
        with self.assertRaises(GameError):
            self.world.join('Fifth', next(iter(FACTIONS)))

    def test_reconnect_reuses_session(self):
        token = self.world.join('Player', 'survivors')
        self.assertEqual(self.world.join('Renamed', 'survivors', token), token)
        self.assertEqual(len(self.world.players), 1)

    def test_invalid_faction(self):
        with self.assertRaises(GameError):
            self.world.join('Unknown', 'aliens')

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
        self.assertEqual(state['me']['faction'], 'survivors')

    def test_unaffordable_action_keeps_stock(self):
        before = dict(self.world.stocks['survivors'])
        with self.assertRaises(GameError):
            self.world._pay('survivors', {'metal': 10**9})
        self.assertEqual(self.world.stocks['survivors'], before)

if __name__ == '__main__':
    unittest.main()
