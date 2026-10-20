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
from world_data import BASES, BUILD_TIME, STORAGE_BASE, STORAGE_PER_WAREHOUSE, TOWNS

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
        self.base = self.world.towns[BASES['survivors']]

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
        self.world.stocks['survivors'].update(wood=999, stone=999, metal=999)
        for kind in ('farm', 'sawmill'):
            b = self.world.buildings['shabrovsky:' + kind]; self.goto(b, 60); self.act('build', id=b['id'])
        b = self.world.buildings['shabrovsky:quarry']; self.goto(b, 60)
        with self.assertRaises(GameError):
            self.act('build', id=b['id'])

    def test_storage_cap_from_warehouses(self):
        self.assertEqual(self.world.storage('survivors'), STORAGE_BASE)
        self.base['levels']['warehouse'] = 2
        self.assertEqual(self.world.storage('survivors'), STORAGE_BASE + 2 * STORAGE_PER_WAREHOUSE)
        self.world._reward('survivors', {'wood': 10 ** 6})
        self.assertEqual(self.world.stocks['survivors']['wood'], self.world.storage('survivors'))

    def test_trade_uses_regional_prices(self):
        self.goto(self.base, 40)
        before = dict(self.world.stocks['survivors'])
        self.act('trade', town=self.base['id'], give='wood', get='food', amount=10)
        self.assertEqual(self.world.stocks['survivors']['wood'], before['wood'] - 10)
        self.assertGreater(self.world.stocks['survivors']['food'], before['food'])
        with self.assertRaises(GameError):
            self.act('trade', town=self.base['id'], give='wood', get='wood', amount=10)

    def test_crafting_needs_a_workshop_level(self):
        ws = self.world.buildings['shabrovsky:workshop']; self.goto(ws, 60)
        self.world.stocks['survivors'].update(metal=200, wood=200, fuel=200)
        with self.assertRaises(GameError):
            self.act('craft', item='weapon', tier=1)
        self.base['levels']['workshop'] = 1
        self.act('craft', item='weapon', tier=1)
        self.assertEqual(self.p['gear']['weapon'], 1)
        with self.assertRaises(GameError):
            self.act('craft', item='weapon', tier=2)    # needs level 2

    def test_cars_stop_at_rivers_but_cross_bridges(self):
        # Volga crossing on the Nizhny Novgorod - Kazan road.
        self.p['vehicle'] = True
        self.p['x'], self.p['y'] = 4070.0, 4500.0       # off the road, west bank of the river
        self.assertTrue(self.world.terrain.water(4070, 4500) or self.world.terrain.water(4060, 4500))
        self.p['input'] = [1, 0, False]
        run(self.world, 1)
        self.assertTrue(self.world._blocked_for(self.p, 4060, 4500, 22) or self.world.terrain.on_road(4060, 4500, 70))
        self.assertFalse(self.world._blocked_for(self.p, 4070, 4183, 22))   # the bridge

    def test_ai_faction_expands_without_human_players(self):
        run(self.world, 900, step=.25)
        owned = [t for t in self.world.towns.values() if t['owner'] == 'bandits']
        self.assertGreaterEqual(len(owned), 2)

    def test_ai_can_be_disabled(self):
        self.world.settings['ai'] = False
        run(self.world, 600, step=.25)
        owned = [t for t in self.world.towns.values() if t['owner'] == 'bandits']
        self.assertEqual(len(owned), 1)

    def test_convoy_carries_remote_output_home(self):
        town = self.world.towns['polevskoy']
        town['owner'] = 'survivors'
        town['cargo'] = {'wood': 20.0, 'stone': 0.0, 'metal': 5.0, 'food': 0.0, 'fuel': 0.0}
        self.world.settings['ai'] = False
        self.world.convoy_clock = 39.95
        wood = self.world.stocks['survivors']['wood']
        run(self.world, .2)
        convoys = [n for n in self.world.npcs.values() if n['type'] == 'convoy']
        self.assertEqual(len(convoys), 1)
        run(self.world, 25, step=.1)
        self.assertEqual(self.world.fstats['survivors']['convoy'], 1)
        self.assertGreaterEqual(self.world.stocks['survivors']['wood'], wood + 19)

    def test_bandit_checkpoint_takes_a_quarter_of_cargo(self):
        convoy = self.world.spawn_npc('convoy', 'survivors', 7000, 5800, mode='travel', path=[[7300, 5200]],
                                      cargo={'wood': 40.0, 'stone': 0, 'metal': 0, 'food': 0, 'fuel': 0})
        self.world.posts['x'] = {'id':'x','faction':'bandits','x':7000,'y':5800,'hp':220,'built':0,'name':'Блокпост'}
        metal = self.world.stocks['bandits']['wood']
        self.world.tower_clock = 1.5
        self.world.tick_defenses(0)
        self.assertAlmostEqual(convoy['cargo']['wood'], 30.0)
        self.assertGreater(self.world.stocks['bandits']['wood'], metal)

    def test_truce_blocks_player_damage(self):
        bandit = self.world.players[self.world.join('Б', 'bandits')]
        bandit['x'], bandit['y'] = 3000, 3000
        self.world.truce['until'] = self.world.elapsed + 100
        self.assertFalse(self.world.hostile(self.p, bandit))
        self.world.truce['until'] = 0
        self.assertTrue(self.world.hostile(self.p, bandit))

    def test_shelter_protects_from_marauders(self):
        self.goto(self.base, 40)
        m = self.world.spawn_npc('marauder', 'marauders', self.base['x'], self.base['y'] + 100)
        self.world.hurt(self.p, 30, m)
        self.assertEqual(self.p['hp'], 100)

    def test_marauder_kill_rewards_faction(self):
        m = self.world.spawn_npc('marauder', 'marauders', 3000, 3000)
        metal = self.world.stocks['survivors']['metal']
        self.world.hurt(m, 999, self.p)
        self.assertEqual(self.p['stats']['kills'], 1)
        self.assertGreater(self.world.stocks['survivors']['metal'], metal)

    def test_story_choice_sets_flag_and_advances(self):
        self.p['visited'].append('ekaterinburg')
        self.assertTrue(self.world._story_ready('survivors'))
        self.act('story_choice', choice=1)
        self.assertIn('secret_freq', self.world.story['survivors']['flags'])
        self.assertEqual(self.world.story['survivors']['index'], 1)
        with self.assertRaises(GameError):
            self.act('story_choice', choice=0)

    def test_post_must_stand_on_a_road(self):
        self.world.stocks['survivors'].update(wood=200, stone=200, metal=200)
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

    def test_assault_raises_militia(self):
        town = self.world.towns['revda']
        self.world.begin_capture(town, 'survivors', 'assault')
        militia = [n for n in self.world.npcs.values() if n['type'] == 'militia']
        self.assertGreaterEqual(len(militia), 1)
        self.assertTrue(all(n['enemy'] == 'survivors' for n in militia))

    def test_light_snapshot_omits_towns(self):
        state = self.world.snapshot(self.token, full=False)
        self.assertNotIn('towns', state)
        self.assertIn('npcs', state)

class SaveTests(unittest.TestCase):
    def test_round_trip_keeps_new_systems(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'world.json'
            w = World(path, rng=random.Random(2))
            token = w.join('А', 'bandits')
            w.players[token]['gear']['armor'] = 2
            w.posts['p1'] = {'id':'p1','faction':'bandits','x':1,'y':2,'hp':100,'built':0,'name':'Блокпост'}
            w.story['bandits']['flags'].append('iron_road')
            w.room_code = '654321'
            w.save()
            loaded = World(path)
            self.assertEqual(loaded.players[token]['gear']['armor'], 2)
            self.assertIn('p1', loaded.posts)
            self.assertIn('iron_road', loaded.story['bandits']['flags'])
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
            self.assertEqual(w.towns['shabrovsky']['levels']['depot'], 2)
            self.assertEqual(w.towns['shabrovsky']['levels']['warehouse'], 0)
            self.assertIn('magadan', w.towns)
            p = w.players['tok']
            self.assertEqual(p['gear'], {'weapon':0,'armor':0})
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
        for i, faction in enumerate(('survivors', 'survivors', 'bandits', 'bandits')):
            p = self.world.players[self.world.join('P' + str(i), faction)]
            self.assertFalse(self.world.terrain.water(p['x'], p['y']))
            self.assertFalse(self.world.terrain.solid(p['x'], p['y'], 10))
            self.assertLess(((p['car']['x'] - p['x']) ** 2 + (p['car']['y'] - p['y']) ** 2) ** .5, 100)
            spots.append((round(p['x']), round(p['y'])))
        self.assertEqual(len(set(spots)), 4)
        survivors = [p for p in self.world.players.values() if p['faction'] == 'survivors']
        bandits = [p for p in self.world.players.values() if p['faction'] == 'bandits']
        for s in survivors:
            for b in bandits:
                self.assertGreater(((s['x'] - b['x']) ** 2 + (s['y'] - b['y']) ** 2) ** .5, 1400)

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
        self.world.stocks['survivors']['food'] = 50
        self.world.command(token, {'op':'heal','request_id':'heal-1'})
        self.assertEqual(p['hp'], 95)
        self.assertEqual(self.world.stocks['survivors']['food'], 47)

    def test_level_survives_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'w.json'
            w = World(path, rng=random.Random(1))
            token = w.join('A', 'bandits'); w.players[token].update(level=7, xp=33); w.save()
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
