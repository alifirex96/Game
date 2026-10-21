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

    def test_computer_clans_start_with_a_town_and_a_shelter(self):
        for sid, name, color, home, fighter, method in AI_SIDES:
            self.assertEqual(self.world.towns[home]['owner'], sid)
            self.assertIn(self.world.sides[sid]['shelter'], self.world.shelters)
        self.assertFalse(any(t['base'] for t in self.world.towns.values()))

    def test_every_player_is_a_side_with_a_home(self):
        a = self.world.players[self.world.join('A')]
        b = self.world.players[self.world.join('B')]
        self.assertNotEqual(a['faction'], b['faction'])
        for p in (a, b):
            self.assertIn(self.world.sides[p['faction']]['shelter'], self.world.shelters)
            self.assertFalse(any(t['owner'] == p['faction'] for t in self.world.towns.values()))
            for resource in ('wood', 'stone', 'metal', 'food', 'fuel'):
                self.assertGreater(self.world.stocks[p['faction']][resource], 0)
        self.assertNotEqual(self.world.sides[a['faction']]['shelter'], self.world.sides[b['faction']]['shelter'])

    def test_player_limit(self):
        self.assertEqual(MAX_PLAYERS, 25)
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
        self.assertEqual(self.world.sides[f]['shelter'], self.world.home(f)['id'])

    def test_quests_come_only_from_people(self):
        token = self.world.join('Player', 'survivors')
        self.assertEqual(self.world.players[token]['quests'], [])

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


class TradeAndClanTests(unittest.TestCase):
    def setUp(self):
        self.world = World(rng=random.Random(3))
        self.ta = self.world.join('Аня'); self.tb = self.world.join('Боря')
        self.a = self.world.players[self.ta]; self.b = self.world.players[self.tb]
        self.b['x'], self.b['y'] = self.a['x'] + 60, self.a['y']

    def act(self, token, op, **data):
        data.update(op=op, request_id='t' + str(random.random()))
        return self.world.command(token, data)

    def test_players_swap_coins_items_and_resources(self):
        self.a['coins'] = 50; self.b['items']['medkit'] = 1
        wood = self.world.stocks[self.a['faction']]['wood']
        self.act(self.ta, 'offer_make', to=self.b['id'], give={'coins':30, 'res':{'wood':5}}, want={'items':{'medkit':1}})
        offer = self.world.snapshot(self.tb)['offers'][0]
        with self.assertRaises(GameError):
            self.act(self.ta, 'offer_accept', id=offer['id'])        # only the other side accepts
        self.act(self.tb, 'offer_accept', id=offer['id'])
        self.assertEqual((self.a['coins'], self.b['coins']), (20, 30))
        self.assertEqual(self.a['items'].get('medkit'), 1)
        self.assertNotIn('medkit', self.b['items'])
        self.assertEqual(self.world.stocks[self.a['faction']]['wood'], wood - 5)
        self.assertEqual(self.world.offers, {})

    def test_trade_needs_to_stand_close(self):
        self.a['coins'] = 10
        self.b['x'] += 2000
        with self.assertRaises(GameError):
            self.act(self.ta, 'offer_make', to=self.b['id'], give={'coins':10}, want={})

    def test_clan_members_do_not_fight(self):
        fa, fb = self.a['faction'], self.b['faction']
        self.assertTrue(self.world.hostile(self.a, self.b))
        self.a['coins'] = 30
        self.act(self.ta, 'clan_create', name='Северный ветер')
        cid = self.world.sides[fa]['clan']
        self.act(self.ta, 'clan_invite', side=fb)
        self.assertIn(cid, self.world.snapshot(self.tb)['invites'])
        self.act(self.tb, 'clan_join', id=cid)
        self.assertFalse(self.world.hostile(self.a, self.b))
        self.assertEqual(self.world.snapshot(self.ta)['players'][0]['tag'], 'СВ')
        self.act(self.tb, 'clan_leave')
        self.assertTrue(self.world.hostile(self.a, self.b))


class HeroLookTests(unittest.TestCase):
    def test_look_follows_level_and_colour_tells_players_apart(self):
        from world_data import hero_look, SIDE_COLORS, MAX_LEVEL
        self.assertEqual(hero_look(1), 0)
        self.assertEqual(hero_look(MAX_LEVEL), 19)
        self.assertTrue(all(hero_look(n) <= hero_look(n + 1) for n in range(1, MAX_LEVEL)))
        w = World(rng=random.Random(1))
        a = w.players[w.join('А', None, None, SIDE_COLORS[5])]
        b = w.players[w.join('Б', None, None, SIDE_COLORS[5])]
        self.assertEqual(w.sides[a['faction']]['color'], SIDE_COLORS[5])
        self.assertNotEqual(w.sides[b['faction']]['color'], SIDE_COLORS[5])
        a['level'] = 16
        self.assertEqual(w._public_player(a)['look'], hero_look(16))


class WeaponHandlingTests(unittest.TestCase):
    def test_magazine_runs_out_and_reloads(self):
        from world_data import WEAPONS
        w = World(rng=random.Random(2))
        token = w.join('Стрелок'); p = w.players[token]
        w.stocks[p['faction']]['metal'] = 999
        results = []
        for i in range(WEAPONS[0]['mag'] + 3):          # one attempt every half second
            w.elapsed += .5
            try:
                w.command(token, {'op':'shoot', 'request_id':'shot-%d' % i}); results.append(True)
            except GameError:
                results.append(False)
        mag = WEAPONS[0]['mag']
        self.assertEqual(results, [True] * mag + [False, False, True])    # 1.4 s reload after the last round
        w.command(token, {'op':'equip', 'weapon':0, 'request_id':'eq-1'})
        p['weapons'].append(1)
        w.command(token, {'op':'equip', 'weapon':1, 'request_id':'eq-2'})
        self.assertEqual(p['act']['kind'], 'swap')
        with self.assertRaises(GameError):
            w.command(token, {'op':'shoot', 'request_id':'shot-x'})   # still drawing the new weapon

    def test_actions_report_their_animation(self):
        w = World(rng=random.Random(2))
        token = w.join('Работник'); p = w.players[token]
        n = next(n for n in w.nodes.values() if n['kind'] == 'wood')
        p['x'], p['y'] = n['x'], n['y'] + 20
        w.command(token, {'op':'harvest', 'id':n['id'], 'request_id':'harvest-1'})
        self.assertEqual(p['act']['kind'], 'chop')
        self.assertEqual(w._public_player(p)['act']['kind'], 'chop')
