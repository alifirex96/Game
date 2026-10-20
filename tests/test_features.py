"""0.2 systems: construction, economy, AI, convoys, diplomacy, saves and LAN discovery."""
import json
import random
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from server import GameError, GameServer, World, discovery_responder
from world_data import BUILD_TIME, STORAGE_BASE, STORAGE_PER_WAREHOUSE, TOWNS, WEAPONS

def keep_alive(world):
    for p in world.players.values():
        p['last_seen'] = time.monotonic()
        p['last_input'] = time.monotonic()

def run(world, seconds, step=.1):
    for _ in range(int(seconds / step)):
        keep_alive(world)
        world.tick(step)

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.world = World(rng=random.Random(11))
        self.token = self.world.join('Тест', 'survivors')
        self.p = self.world.players[self.token]
        self.f = self.p['faction']
        self.base = self.world.towns['shabrovsky']
        self.world._set_owner(self.base, self.f)
        self.base['levels'].update(depot=1, house=1)      # what a capture leaves behind

    def act(self, op, **data):
        data.update(op=op, request_id='r' + str(random.random()))
        return self.world.command(self.token, data)

    def goto(self, obj, dy=0):
        self.p['x'] = obj['x']; self.p['y'] = obj['y'] + dy

    def test_construction_takes_time_and_allies_speed_it_up(self):
        farm = self.world.buildings['shabrovsky:farm']
        self.goto(farm, 60)
        self.act('build', id=farm['id'])
        self.assertEqual(self.base['levels']['farm'], 0)
        self.assertIn('farm', self.base['construct'])
        run(self.world, BUILD_TIME[0] / 1.5 + .5)   # one helper on site: 1.5x speed
        self.assertEqual(self.base['levels']['farm'], 1)
        self.assertNotIn('farm', self.base['construct'])

    def test_two_constructions_at_most(self):
        self.world.stocks[self.f].update(wood=999, stone=999, metal=999)
        for kind in ('farm', 'sawmill'):
            b = self.world.buildings['shabrovsky:' + kind]; self.goto(b, 60); self.act('build', id=b['id'])
        b = self.world.buildings['shabrovsky:quarry']; self.goto(b, 60)
        with self.assertRaises(GameError):
            self.act('build', id=b['id'])

    def test_storage_cap_from_warehouses(self):
        self.assertEqual(self.world.storage(self.f), STORAGE_BASE)
        self.base['levels']['warehouse'] = 2
        self.assertEqual(self.world.storage(self.f), STORAGE_BASE + 2 * STORAGE_PER_WAREHOUSE)
        self.world._reward(self.f, {'wood': 10 ** 6})
        self.assertEqual(self.world.stocks[self.f]['wood'], self.world.storage(self.f))

    def test_trade_uses_regional_prices(self):
        self.goto(self.base, 40)
        before = dict(self.world.stocks[self.f])
        self.act('trade', town=self.base['id'], give='wood', get='food', amount=10)
        self.assertEqual(self.world.stocks[self.f]['wood'], before['wood'] - 10)
        self.assertGreater(self.world.stocks[self.f]['food'], before['food'])
        with self.assertRaises(GameError):
            self.act('trade', town=self.base['id'], give='wood', get='wood', amount=10)

    def test_crafting_needs_a_workshop_level(self):
        ws = self.world.buildings['shabrovsky:workshop']; self.goto(ws, 60)
        self.world.stocks[self.f].update(metal=200, wood=200, fuel=200)
        with self.assertRaises(GameError):
            self.act('craft', item='weapon', tier=1)
        self.base['levels']['workshop'] = 1
        self.act('craft', item='weapon', tier=1)
        self.assertEqual(self.p['gear']['weapon'], 1)
        with self.assertRaises(GameError):
            self.act('craft', item='weapon', tier=2)    # needs level 2

    def test_cars_stop_at_rivers_but_cross_bridges(self):
        terrain = self.world.terrain
        bridge = None
        for ax, ay, bx, by, a, b in terrain.road_segments:
            for k in range(1, 400):
                x, y = ax + (bx - ax) * k / 400, ay + (by - ay) * k / 400
                if terrain.water(x, y):
                    bridge = (x, y, -(by - ay), bx - ax); break
            if bridge: break
        self.assertIsNotNone(bridge)
        x, y, nx, ny = bridge
        length = (nx * nx + ny * ny) ** .5
        self.p['vehicle'] = True
        self.assertFalse(self.world._blocked_for(self.p, x, y, 22))           # on the bridge
        side = (x + nx / length * 200, y + ny / length * 200)                # same river, off the road
        if terrain.water(*side):
            self.assertTrue(self.world._blocked_for(self.p, side[0], side[1], 22))
        self.p['vehicle'] = False
        self.assertFalse(self.world._blocked_for(self.p, side[0], side[1], 10))   # people wade

    def test_ai_faction_expands_without_human_players(self):
        run(self.world, 900, step=.1)
        owned = [t for t in self.world.towns.values() if t['owner'] == 'ai_scar']
        self.assertGreaterEqual(len(owned), 2)

    def test_ai_can_be_disabled(self):
        self.world.settings['ai'] = False
        run(self.world, 600, step=.25)
        owned = [t for t in self.world.towns.values() if t['owner'] == 'ai_scar']
        self.assertEqual(len(owned), 1)

    def test_convoy_carries_remote_output_home(self):
        town = self.world.towns['polevskoy']
        town['owner'] = self.f
        town['cargo'] = {'wood': 20.0, 'stone': 0.0, 'metal': 5.0, 'food': 0.0, 'fuel': 0.0}
        self.world.settings['ai'] = False
        self.world.convoy_clock = 39.95
        wood = self.world.stocks[self.f]['wood']
        run(self.world, .2)
        convoys = [n for n in self.world.npcs.values() if n['type'] == 'convoy']
        self.assertEqual(len(convoys), 1)
        run(self.world, 70, step=.1)
        self.assertEqual(self.world.fstats[self.f]['convoy'], 1)
        self.assertGreaterEqual(self.world.stocks[self.f]['wood'], wood + 19)

    def test_bandit_checkpoint_takes_a_quarter_of_cargo(self):
        convoy = self.world.spawn_npc('convoy', self.f, 7000, 5800, mode='travel', path=[[7300, 5200]],
                                      cargo={'wood': 40.0, 'stone': 0, 'metal': 0, 'food': 0, 'fuel': 0})
        self.world.posts['x'] = {'id':'x','faction':'ai_scar','x':7000,'y':5800,'hp':220,'built':0,'name':'Блокпост'}
        metal = self.world.stocks['ai_scar']['wood']
        self.world.tower_clock = 1.5
        self.world.tick_defenses(0)
        self.assertAlmostEqual(convoy['cargo']['wood'], 30.0)
        self.assertGreater(self.world.stocks['ai_scar']['wood'], metal)

    def test_truce_blocks_player_damage(self):
        other = self.world.players[self.world.join('Б')]
        other['x'], other['y'] = 3000, 3000
        self.assertTrue(self.world.hostile(self.p, other))
        self.world._start_truce(self.f, other['faction'])
        self.assertFalse(self.world.hostile(self.p, other))
        self.assertTrue(self.world.hostile(self.p, {'faction': 'ai_scar'}))

    def test_shelter_protects_from_marauders(self):
        home = self.world.home(self.f)
        self.goto(home, 40)
        m = self.world.spawn_npc('marauder', 'marauders', home['x'], home['y'] + 100)
        self.world.hurt(self.p, 30, m)
        self.assertEqual(self.p['hp'], 100)

    def test_marauder_kill_rewards_faction(self):
        m = self.world.spawn_npc('marauder', 'marauders', 3000, 3000)
        metal = self.world.stocks[self.f]['metal']
        self.world.hurt(m, 999, self.p)
        self.assertEqual(self.p['stats']['kills'], 1)
        self.assertGreater(self.world.stocks[self.f]['metal'], metal)

    def test_story_choice_sets_flag_and_advances(self):
        self.p['visited'].append('ekaterinburg')
        self.assertTrue(self.world._story_ready(self.f))
        with self.assertRaises(GameError):
            self.act('story_choice', choice=1)          # only the radio operator takes chapters
        self.goto(self.world.givers['ekaterinburg:radio'], 40)
        self.act('story_choice', choice=1)
        self.assertIn('secret_freq', self.world.story[self.f]['flags'])
        self.assertEqual(self.world.story[self.f]['index'], 1)
        with self.assertRaises(GameError):
            self.act('story_choice', choice=0)

    def test_post_must_stand_on_a_road(self):
        self.world.stocks[self.f].update(wood=200, stone=200, metal=200)
        self.p['x'], self.p['y'] = 7300, 5900
        with self.assertRaises(GameError):
            self.act('post')
        a, b = self.world.towns['ekaterinburg'], self.world.towns['tyumen']
        self.p['x'], self.p['y'] = (a['x'] + b['x']) / 2, (a['y'] + b['y']) / 2
        self.act('post')
        self.assertEqual(len(self.world.posts), 1)

    def test_fire_destroys_a_level_unless_extinguished(self):
        self.base['levels']['farm'] = 2
        self.base['fires']['farm'] = self.world.elapsed + 1
        self.base['fires']['house'] = self.world.elapsed + 1
        self.goto(self.world.buildings['shabrovsky:house'], 60)
        self.act('extinguish', id='shabrovsky:house')
        run(self.world, 1.5)
        self.assertEqual(self.base['levels']['farm'], 1)
        self.assertEqual(self.base['levels']['house'], 1)

    def test_marauders_hold_free_towns_until_killed(self):
        town = self.world.towns['revda']
        self.goto(town, 40)
        self.world.stocks[self.f].update(metal=200, food=200)
        self.world.tick_garrisons(self.world.active_players())
        guards = self.world.garrison(town)
        self.assertEqual(len(guards), 3)
        self.assertTrue(all(n['type'] == 'occupier' and n['faction'] == 'marauders' for n in guards))
        with self.assertRaises(GameError):
            self.act('capture', town='revda', method='assault')
        for n in guards:
            self.world.hurt(n, 999, self.p)
        self.world.garrison_clock = 0
        self.world.tick_garrisons(self.world.active_players())
        self.assertEqual(self.world.garrison(town), [])          # they do not come back at once
        self.world._set_owner(town, self.f)
        self.world.garrison_clock = 0
        self.world.tick_garrisons(self.world.active_players())
        defenders = self.world.garrison(town)
        self.assertGreaterEqual(len(defenders), 2)
        self.assertTrue(all(n['type'] == 'defender' and n['faction'] == self.f for n in defenders))

    def test_big_cities_have_a_stronger_garrison(self):
        town = self.world.towns['ekaterinburg']
        self.goto(town, 40)
        self.world.tick_garrisons(self.world.active_players())
        kinds = [n['type'] for n in self.world.garrison(town)]
        self.assertEqual(kinds.count('occupier'), 5)
        self.assertEqual(kinds.count('occupier_elite'), 2)

    def test_shelter_guards_warn_then_shoot(self):
        other = self.world.players[self.world.join('Сосед')]
        home = self.world.home(other['faction'])
        self.p['x'], self.p['y'] = home['x'], home['y'] + 700
        self.world.tick_garrisons(self.world.active_players())
        guards = [n for n in self.world.npcs.values() if n['type'] == 'guardian' and n['job']['shelter'] == home['id']]
        self.assertEqual(len(guards), 5)
        self.assertTrue(any(e['title'].startswith('Стой') and e['player'] == self.p['id'] for e in self.world.log))
        self.world._build_grid()
        for n in guards:
            n['cd'] = 0; self.world._think(n)
        self.assertEqual(self.p['hp'], 100)                       # outside the fence: warning only
        self.p['x'], self.p['y'] = home['x'], home['y'] + 150
        self.world._build_grid()
        for n in guards:
            n['cd'] = 0; n['target'] = None; self.world._think(n)
        self.assertLess(self.p['hp'], 100)
        own = [n for n in self.world.npcs.values() if n['type'] == 'guardian' and n['faction'] == self.f]
        self.assertTrue(all(not self.world.hostile(n, self.p) for n in own))

    def test_light_snapshot_omits_towns(self):
        state = self.world.snapshot(self.token, full=False)
        self.assertNotIn('towns', state)
        self.assertIn('npcs', state)

class SaveTests(unittest.TestCase):
    def test_round_trip_keeps_new_systems(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'world.json'
            w = World(path, rng=random.Random(2))
            token = w.join('А')
            side = w.players[token]['faction']
            w.players[token]['gear']['armor'] = 2
            w.posts['p1'] = {'id':'p1','faction':side,'x':1,'y':2,'hp':100,'built':0,'name':'Пост'}
            w.story[side]['flags'].append('iron_road')
            w.room_code = '654321'
            w.save()
            loaded = World(path)
            self.assertEqual(loaded.players[token]['gear']['armor'], 2)
            self.assertIn('p1', loaded.posts)
            self.assertIn('iron_road', loaded.story[side]['flags'])
            self.assertEqual(loaded.sides[side]['shelter'], w.sides[side]['shelter'])
            self.assertEqual(loaded.room_code, '654321')

    def test_version_one_save_is_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'world.json'
            old_towns = {}
            for tid, name, x, y, region in TOWNS[:15]:
                owner = 'survivors' if tid == 'shabrovsky' else 'bandits' if tid == 'pervouralsk' else None
                levels = {k: 0 for k in ('depot','house','sawmill','quarry','workshop','farm','garage','radio','guard')}
                levels['depot'] = 2 if owner else 0
                old_towns[tid] = {'owner': owner, 'levels': levels, 'loyalty': 60, 'shield': 0, 'cooldowns': {}, 'intel': {}}
            player = {'id':'abc','name':'Старый','faction':'survivors','x':7300,'y':5270,'angle':0,'hp':80,'stamina':100,
                      'vehicle':False,'car':{'x':7390,'y':5225,'angle':0},'dead_until':0,'aim':[0,1],'last_action':{},
                      'stats':{'harvest':2,'build':0,'event':0,'explore':0,'deliver':0,'capture':0,'aid':0},
                      'visited':['shabrovsky'],'quests':[],'quest_serial':0,'completed':0,'pending':None}
            raw = {'schema':1,'time':500,'production_clock':3,'towns':old_towns,
                   'stocks':{f:{r:50 for r in ('wood','stone','metal','food','fuel')} for f in ('survivors','bandits')},
                   'reputation':{'survivors':5,'bandits':-3},'players':{'tok':player},'harvested':{},'events_done':{},'winner':None}
            path.write_text(json.dumps(raw), encoding='utf-8')
            w = World(path)
            self.assertIsNone(w.load_warning)
            self.assertEqual(w.elapsed, 500)
            self.assertEqual((w.players['tok']['x'], w.players['tok']['y']), (7300 * 3, 5270 * 3))
            self.assertEqual(w.towns['shabrovsky']['levels']['depot'], 2)
            self.assertEqual(w.towns['shabrovsky']['levels']['warehouse'], 0)
            self.assertIn('magadan', w.towns)
            p = w.players['tok']
            self.assertEqual(p['gear'], {'weapon':0,'armor':0,'clothes':0,'backpack':0})
            self.assertEqual(p['stats']['kills'], 0)
            self.assertEqual(p['car']['hp'], 100.0)

class DiscoveryTests(unittest.TestCase):
    def test_reply_never_contains_the_room_code(self):
        server = GameServer(('127.0.0.1', 0), World(), '123456', 'Тестовая')
        port = 38000 + random.randint(0, 900)
        thread = threading.Thread(target=discovery_responder, args=(server, port), daemon=True)
        thread.start(); time.sleep(.3)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2)
        try:
            sock.sendto(b'AFTERSILENCE?', ('127.0.0.1', port))
            data, _ = sock.recvfrom(1024)
        finally:
            sock.close(); server.stop_event.set(); server.server_close(); thread.join(2)
        info = json.loads(data.decode('utf-8'))
        self.assertEqual(info['game'], 'after-silence')
        self.assertEqual(info['port'], server.server_port)
        self.assertNotIn('123456', data.decode('utf-8'))

if __name__ == '__main__':
    unittest.main()

class SpawnAndLevelTests(unittest.TestCase):
    def setUp(self):
        self.world = World(rng=random.Random(5))

    def test_each_player_spawns_at_a_random_free_spot(self):
        spots = []
        for i in range(4):
            p = self.world.players[self.world.join('P' + str(i))]
            self.assertFalse(self.world.terrain.water(p['x'], p['y']))
            self.assertFalse(self.world.terrain.solid(p['x'], p['y'], 10))
            self.assertLess(((p['car']['x'] - p['x']) ** 2 + (p['car']['y'] - p['y']) ** 2) ** .5, 100)
            spots.append((p['x'], p['y']))
        for a in range(4):
            for b in range(a + 1, 4):
                self.assertGreater(((spots[a][0] - spots[b][0]) ** 2 + (spots[a][1] - spots[b][1]) ** 2) ** .5, 1400)

    def test_respawn_moves_to_a_new_random_spot(self):
        token = self.world.join('A', 'survivors'); p = self.world.players[token]
        before = (p['x'], p['y'])
        self.world._damage(p, 999)
        self.world.elapsed = p['dead_until']
        run(self.world, .2)
        self.assertEqual(p['hp'], self.world.max_hp(p))
        self.assertNotEqual((p['x'], p['y']), before)

    def test_experience_raises_level_health_and_perks(self):
        token = self.world.join('A', 'survivors'); p = self.world.players[token]
        self.assertEqual((p['level'], p['xp']), (1, 0))
        for _ in range(20):
            self.world.gain_xp(p, 'harvest')     # 80 xp
        self.assertEqual(p['level'], 2)
        self.assertEqual(self.world.max_hp(p), 105)
        self.assertEqual(p['hp'], 105)
        p['level'] = 10; p['hp'] = 50
        self.world.stocks[p['faction']]['food'] = 50
        self.world.command(token, {'op':'heal','request_id':'heal-1'})
        self.assertEqual(p['hp'], 95)
        self.assertEqual(self.world.stocks[p['faction']]['food'], 47)

    def test_level_survives_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'w.json'
            w = World(path, rng=random.Random(1))
            token = w.join('A'); w.players[token].update(level=7, xp=33); w.save()
            loaded = World(path)
            self.assertEqual((loaded.players[token]['level'], loaded.players[token]['xp']), (7, 33))

class TownLayoutTests(unittest.TestCase):
    def test_highways_meet_town_streets_and_streets_are_clear(self):
        w = World()
        from world_data import TOWN_GATE, LANDMARKS
        for ax, ay, bx, by, a, b in w.terrain.road_segments:
            for (x, y), tid in (((ax, ay), a), ((bx, by), b)):
                t = w.towns[tid]
                on_x = abs(abs(x - t['x']) - TOWN_GATE[0]) < 1 and abs(y - t['y']) < 1
                on_y = abs(abs(y - t['y']) - TOWN_GATE[1]) < 1 and abs(x - t['x']) < 1
                self.assertTrue(on_x or on_y, tid)
        for t in w.towns.values():
            for k in range(-460, 461, 20):
                self.assertFalse(w.terrain.solid(t['x'] + k, t['y'], 12), t['id'])
                self.assertFalse(w.terrain.solid(t['x'], t['y'] + k * 400 / 460, 12), t['id'])
        self.assertEqual(set(LANDMARKS), set(w.towns))

    def test_npc_routes_follow_gates(self):
        w = World()
        pts = w.terrain.route_points(['shabrovsky', 'revda'])
        self.assertEqual(pts[0], list(w.terrain.gate('shabrovsky', 'revda')))
        self.assertEqual(pts[-1], [w.towns['revda']['x'], w.towns['revda']['y']])

class ShopTests(unittest.TestCase):
    def setUp(self):
        self.world = World(rng=random.Random(9))
        self.token = self.world.join('Покупатель', 'survivors')
        self.p = self.world.players[self.token]
        self.f = self.p['faction']
        t = self.world.towns['revda']
        self.p['x'], self.p['y'] = t['x'], t['y'] + 40

    def act(self, op, **data):
        data.update(op=op, request_id='s' + str(random.random()))
        return self.world.command(self.token, data)

    def test_coins_come_from_quests(self):
        self.assertEqual(self.p['coins'], 0)
        g = next(g for g in self.world.givers.values() if g['town'] == 'revda' and g['type'] != 'radio')
        self.p['x'] += 800
        with self.assertRaises(GameError):
            self.act('talk', giver=g['id'])                          # too far away
        self.p['x'], self.p['y'] = g['x'], g['y'] + 30
        dialog = self.act('talk', giver=g['id'])['dialog']
        self.assertTrue(dialog['greet'])
        offer = dialog['offers'][0]
        self.act('quest_accept', giver=g['id'], kind=offer['kind'])
        q = self.p['quests'][0]
        with self.assertRaises(GameError):
            self.act('quest_turnin', giver=g['id'], id=q['id'])     # not done yet
        self.p['stats'][q['kind']] += q['target']
        self.act('quest_turnin', giver=g['id'], id=q['id'])
        self.assertEqual(self.p['coins'], q['coins'])
        self.assertEqual(self.p['quests'], [])

    def test_buying_weapons_needs_coins_and_level(self):
        with self.assertRaises(GameError):
            self.act('buy', town='revda', kind='weapon', index=3)       # no coins
        self.p['coins'] = 2000
        with self.assertRaises(GameError):
            self.act('buy', town='revda', kind='weapon', index=3)       # level 2 needed
        self.p['level'] = 2
        self.act('buy', town='revda', kind='weapon', index=3)
        self.assertIn(3, self.p['weapons'])
        self.assertEqual(self.p['gear']['weapon'], 3)
        self.assertEqual(self.p['coins'], 2000 - WEAPONS[3]['price'])
        with self.assertRaises(GameError):
            self.act('buy', town='revda', kind='weapon', index=5)       # level 12 needed
        with self.assertRaises(GameError):
            self.act('buy', town='revda', kind='weapon', index=3)       # already owned
        self.act('equip', weapon=0)
        self.assertEqual(self.p['gear']['weapon'], 0)
        with self.assertRaises(GameError):
            self.act('equip', weapon=6)

    def test_enemy_traders_refuse(self):
        self.world.towns['revda']['owner'] = 'ai_scar'
        self.p['coins'] = 500
        with self.assertRaises(GameError):
            self.act('buy', town='revda', kind='medkit')

    def test_medkit_heals_before_food_and_repairkit_fixes_car(self):
        self.p['coins'] = 500
        self.act('buy', town='revda', kind='medkit')
        self.act('buy', town='revda', kind='repairkit')
        self.p['hp'] = 20; food = self.world.stocks[self.f]['food']
        self.act('heal')
        self.assertEqual(self.p['hp'], 80)
        self.assertEqual(self.world.stocks[self.f]['food'], food)
        self.p['car'].update(x=self.p['x'] + 50, y=self.p['y'], hp=30.0)
        self.act('repair', kit=True)
        self.assertEqual(self.p['car']['hp'], 100.0)
        self.assertNotIn('medkit', self.p['items'])
        self.assertNotIn('repairkit', self.p['items'])

    def test_supplies_go_to_faction_stock(self):
        self.p['coins'] = 100
        fuel = self.world.stocks[self.f]['fuel']
        self.act('buy', town='revda', kind='supplies')
        self.assertEqual(self.world.stocks[self.f]['fuel'], fuel + 15)


class SurvivalTests(unittest.TestCase):
    def setUp(self):
        self.world = World(rng=random.Random(4))
        self.world.settings['ai'] = False
        self.token = self.world.join('Выживший', 'survivors')
        self.p = self.world.players[self.token]
        self.f = self.p['faction']
        self.p['x'], self.p['y'] = 8000.0 * 3, 6200.0 * 3          # open country in the Urals

    def act(self, op, **data):
        data.update(op=op, request_id='v' + str(random.random()))
        return self.world.command(self.token, data)

    def test_hunger_and_thirst_drop_and_hurt_at_zero(self):
        food, water = self.p['food'], self.p['water']
        run(self.world, 60, step=.1)
        self.assertLess(self.p['food'], food)
        self.assertLess(self.p['water'], water - 4)
        self.p.update(food=0.0, water=0.0, hp=50.0)
        run(self.world, 10, step=.1)
        self.assertLess(self.p['hp'], 45)

    def test_items_feed_and_bandage_stops_bleeding(self):
        self.p.update(food=10.0, bleeding=True)
        self.p['items'] = {'canned': 1, 'bandage': 1}
        self.act('use', item='canned')
        self.assertGreaterEqual(self.p['food'], 49)
        self.p['hp'] = 50
        self.act('heal')
        self.assertFalse(self.p['bleeding'])
        self.assertEqual(self.p['items'], {})

    def test_backpack_limits_items(self):
        self.p['items'] = {'water': 6}
        self.assertEqual(self.world.give_item(self.p, 'canned'), 0)
        self.p['gear']['backpack'] = 1
        self.assertEqual(self.world.give_item(self.p, 'canned', 10), 6)

    def test_cold_north_needs_warm_clothes(self):
        north = self.world.towns['vorkuta']
        self.p['x'], self.p['y'] = north['x'] + 1500, north['y'] + 900
        self.world.weather = {'kind': 'snow', 'until': 1e9}
        self.world.elapsed = 700               # night
        run(self.world, 120, step=.1)
        cold = self.p['warmth']
        self.assertLess(cold, 30)
        self.p['gear']['clothes'] = 3
        run(self.world, 200, step=.1)
        self.assertGreater(self.p['warmth'], cold + 20)

    def test_river_water_and_town_canteen(self):
        terrain = self.world.terrain
        spot = next((x, y) for ax, ay, bx, by, h in terrain.water_segments
                    for x, y in [((ax + bx) / 2, (ay + by) / 2)] if terrain.water(x, y) and not terrain.in_town(x, y, 100))
        self.p['x'], self.p['y'] = spot
        self.p['water'] = 10.0
        self.act('drink')
        self.assertGreaterEqual(self.p['water'], 44)
        base = self.world.home(self.f)
        self.p['x'], self.p['y'] = base['x'], base['y'] + 40
        self.p.update(food=5.0, water=5.0)
        with self.assertRaises(GameError):
            self.act('canteen', town='revda')                    # not ours
        self.act('canteen', town='shelter')
        self.assertGreater(self.p['food'], 50)
        with self.assertRaises(GameError):
            self.act('canteen', town='shelter')

    def test_shop_sells_clothes_backpacks_and_food(self):
        t = self.world.towns['revda']
        self.p['x'], self.p['y'] = t['x'], t['y'] + 40
        self.p['coins'] = 1000; self.p['level'] = 5
        self.act('buy', town='revda', kind='clothes', index=2)
        self.act('buy', town='revda', kind='backpack', index=2)
        self.act('buy', town='revda', kind='canned')
        self.assertEqual((self.p['gear']['clothes'], self.p['gear']['backpack']), (2, 2))
        self.assertEqual(self.p['items'].get('canned'), 1)

class WildlifeAndFuelTests(unittest.TestCase):
    def setUp(self):
        self.world = World(rng=random.Random(21))
        self.world.settings['ai'] = False
        self.token = self.world.join('Охотник', 'survivors')
        self.p = self.world.players[self.token]
        self.f = self.p['faction']
        self.p['x'], self.p['y'] = 8000.0 * 3, 6200.0 * 3

    def quiet(self):
        self.world._spawn_marauders = lambda active: None
        self.world._spawn_creatures = lambda active: None
        self.world.tick_garrisons = lambda active: None

    def act(self, op, **data):
        data.update(op=op, request_id='w' + str(random.random()))
        return self.world.command(self.token, data)

    def test_creatures_appear_in_the_wild(self):
        self.world.elapsed = 700        # night brings mutants out
        run(self.world, 120, step=.1)
        factions = {n['faction'] for n in self.world.npcs.values()}
        self.assertTrue({'wild', 'game'} & factions)
        self.assertIn('mutants', factions)

    def test_hunting_gives_meat_to_cook_at_home(self):
        elk = self.world.spawn_npc('elk', 'game', self.p['x'] + 200, self.p['y'])
        self.assertTrue(self.world.hostile_shot(self.p, elk))
        self.world.hurt(elk, 999, self.p)
        self.assertEqual(self.p['items'].get('meat_raw'), 3)
        self.assertEqual(self.p['stats']['hunt'], 1)
        base = self.world.home(self.f)
        self.p['x'], self.p['y'] = base['x'], base['y'] + 40
        self.act('cook', town='shelter')
        self.assertEqual(self.p['items'].get('meat'), 3)
        self.assertNotIn('meat_raw', self.p['items'])

    def test_elk_runs_and_wolves_bite(self):
        elk = self.world.spawn_npc('elk', 'game', self.p['x'] + 150, self.p['y'])
        wolf = self.world.spawn_npc('wolf', 'wild', self.p['x'] + 20, self.p['y'] + 10)
        self.world._think(elk)
        self.assertGreater(elk['goal'][0], elk['x'])               # away from the player
        hp = self.p['hp']
        for _ in range(12):
            wolf['cd'] = 0; self.world._think(wolf)
        self.assertLess(self.p['hp'], hp)
        self.assertFalse(self.world.hostile(wolf, elk))

    def test_each_car_has_its_own_tank(self):
        self.quiet()
        stock = self.world.stocks[self.f]['fuel']
        car = self.p['car']; car['fuel'] = 5.0
        self.p['vehicle'] = True; self.p['x'], self.p['y'] = car['x'], car['y']
        self.p['input'] = [1, 0, False]
        run(self.world, 40, step=.1)
        self.assertEqual(self.p['car']['fuel'], 0)
        self.assertEqual(self.world.stocks[self.f]['fuel'], stock)
        with self.assertRaises(GameError):
            self.act('refuel', canister=True)
        self.p['items']['canister'] = 1
        self.act('refuel', canister=True)
        self.assertEqual(self.p['car']['fuel'], 20)

    def test_refuel_only_in_own_settlement(self):
        self.p['vehicle'] = False
        revda = self.world.towns['revda']
        self.p['x'], self.p['y'] = revda['x'], revda['y'] + 40
        self.p['car'].update(x=revda['x'] + 100, y=revda['y'] + 60, fuel=2.0)
        with self.assertRaises(GameError):
            self.act('refuel', town='revda')
        revda['owner'] = self.f
        stock = self.world.stocks[self.f]['fuel']
        self.act('refuel', town='revda')
        self.assertEqual(self.p['car']['fuel'], min(45, 2 + stock))
        self.assertLess(self.world.stocks[self.f]['fuel'], stock)
