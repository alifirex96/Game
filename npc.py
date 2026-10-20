"""Computer-controlled characters: marauders, militia, AI faction squads and convoys.

Mixed into server.World. Everything here runs on the host, inside the world lock.
"""
import math
import secrets
import time
from world_data import (FACTIONS, BASES, BUILDINGS, NPC_TYPES, POI_KINDS, ARMOR, WEAPONS, NPC_FACTION, WILDLIFE, REGIONS,
                        RESOURCES, WORLD_SIZE)

AI_PRIORITY = ['farm', 'house', 'sawmill', 'depot', 'quarry', 'workshop', 'warehouse',
               'garage', 'guard', 'radio']
MAX_MARAUDERS = 36
MAX_CREATURES = 40
MONSTERS = ('marauders', 'wild', 'mutants')
SQUAD_COSTS = {'talk':{'food':12,'wood':8},'bribe':{'food':18,'fuel':8},'assault':{'metal':12,'food':6}}


def other_faction(f):
    return 'bandits' if f == 'survivors' else 'survivors'


class NpcMixin:
    # ---- shared helpers -------------------------------------------------
    def truce_active(self):
        return self.truce.get('until', 0) > self.elapsed

    @staticmethod
    def side(entity):
        return entity['faction']

    def hostile(self, a, b):
        fa = a['faction']; fb = b['faction']
        if fa == fb or 'game' in (fa, fb):
            return False
        if fa in MONSTERS or fb in MONSTERS:
            return True
        if fa in FACTIONS and fb in FACTIONS:
            return not self.truce_active()
        neutral, other = (a, b) if fa == 'neutral' else (b, a)
        return neutral.get('enemy') == other['faction']

    def active_players(self):
        now = time.monotonic()
        return [p for p in self.players.values() if now - p['last_seen'] < 8]

    def human_faction(self, f):
        """A faction is human-led while one of its players was seen in the last minute."""
        now = time.monotonic()
        return any(p['faction'] == f and now - p['last_seen'] < 60 for p in self.players.values())

    def ai_faction(self, f):
        return self.settings.get('ai', True) and not self.human_faction(f)

    def flag(self, f, name):
        return name in self.story.get(f, {}).get('flags', [])

    def spawn_npc(self, kind, faction, x, y, **extra):
        spec = NPC_TYPES[kind]
        hp = spec['hp'] * (1.5 if kind == 'convoy' and self.flag(faction, 'armed_convoys') else 1)
        npc = {'id':secrets.token_hex(5),'type':kind,'faction':faction,'x':float(x),'y':float(y),
               'angle':0.0,'hp':float(hp),'max':float(hp),'mode':'wander','home':[float(x),float(y)],
               'goal':None,'path':[],'cd':0.0,'think':self.rng.random()*.2,'target':None,
               'shot':-10.0,'far':0.0,'job':None}
        npc.update(extra)
        self.npcs[npc['id']] = npc
        return npc

    def _path_points(self, route):
        return [[x + self.rng.uniform(-14, 14), y + self.rng.uniform(-14, 14)] for x, y in self.terrain.route_points(route)]

    def _target_alive(self, ref):
        if not ref:
            return None
        kind, ident = ref
        if kind == 'p':
            p = next((o for o in self.players.values() if o['id'] == ident), None)
            if p and p['hp'] > 0 and time.monotonic() - p['last_seen'] < 8:
                return p
            return None
        n = self.npcs.get(ident)
        return n if n and n['hp'] > 0 else None

    def _entities(self):
        out = [p for p in self.active_players() if p['hp'] > 0]
        out.extend(n for n in self.npcs.values() if n['hp'] > 0)
        return out

    def _ref(self, entity):
        return ('p', entity['id']) if 'stats' in entity else ('n', entity['id'])

    # ---- damage ---------------------------------------------------------
    def hurt(self, target, amount, attacker=None):
        """Apply damage to a player, an NPC or a road post. Returns True on a kill."""
        if 'stats' in target:
            if target['hp'] <= 0:
                return False
            if attacker is not None and attacker.get('faction') != target['faction'] \
                    and self._dist(target, self.towns[BASES[target['faction']]]) < 240:
                return False   # home shelters stay safe
            amount *= 1 - ARMOR[target['gear']['armor']]['reduce'] - (.1 if target['level'] >= 20 else 0)
            if target['vehicle']:
                car = target['car']
                car['hp'] = max(0, car.get('hp', 100) - amount)
                amount *= .3
                if car['hp'] <= 0:
                    self._wreck_car(target)
                    amount += 15
            self._damage(target, amount)
            # Gunshots open wounds; armor makes it less likely.
            if target['hp'] > 0 and amount >= 6 and not target['bleeding'] and \
                    self.rng.random() < .3 - ARMOR[target['gear']['armor']]['reduce'] * .5:
                target['bleeding'] = True
                self._notice('Кровотечение', 'Перевяжись: H (бинт или аптечка).', player=target['id'], tone='error')
            if target['hp'] <= 0 and attacker is not None:
                self._credit_kill(attacker, target)
                return True
            return False
        if 'built' in target:   # road post
            target['hp'] -= amount
            if target['hp'] <= 0 and target['id'] in self.posts:
                del self.posts[target['id']]
                self.effects.append({'id':secrets.token_hex(4),'kind':'boom','x':target['x'],'y':target['y'],
                                     'ex':target['x'],'ey':target['y'],'until':self.elapsed+1.2,'faction':None})
                self._notice('Пост разрушен', target['name'], faction=target['faction'], tone='error')
                if attacker is not None and attacker.get('faction') in FACTIONS:
                    self._notice('Вражеский пост уничтожен', '+12 металла', faction=attacker['faction'])
                    self._reward(attacker['faction'], {'metal':12})
                return True
            return False
        if target['hp'] <= 0:
            return False
        target['hp'] -= amount
        if target['faction'] == 'neutral' and attacker is not None and attacker.get('faction') in FACTIONS:
            target['enemy'] = attacker['faction']
        if target['hp'] <= 0:
            self._npc_killed(target, attacker)
            return True
        if attacker is not None and target['type'] != 'convoy' and target['mode'] != 'fight':
            target['target'] = self._ref(attacker); target['mode'] = 'fight'
        return False

    def _credit_kill(self, attacker, victim):
        f = attacker.get('faction')
        if f not in FACTIONS:
            return
        self.fstats[f]['kills'] += 1
        if 'stats' in attacker:
            attacker['stats']['kills'] += 1
            kind = victim.get('faction')
            self.gain_xp(attacker, 'kill_player' if 'stats' in victim else
                         'kill_marauder' if victim.get('type') == 'marauder' else
                         'kill_animal' if kind in ('wild', 'game') else 'kill_mutant' if kind == 'mutants' else 'kill_fighter')
            if kind in ('wild', 'game'):
                attacker['stats']['hunt'] += 1
            elif kind == 'mutants':
                attacker['stats']['mutants'] += 1
        if 'stats' in victim:
            self._notice(victim['name'] + ' ранен', 'Победа: ' + FACTIONS[f], faction=f)

    def _npc_killed(self, npc, attacker):
        npc['hp'] = 0
        self.effects.append({'id':secrets.token_hex(4),'kind':'boom' if npc['type'] == 'convoy' else 'fall',
                             'x':npc['x'],'y':npc['y'],'ex':npc['x'],'ey':npc['y'],'until':self.elapsed+1.2,'faction':None})
        f = attacker.get('faction') if attacker else None
        if npc['type'] == 'convoy':
            cargo = npc.get('cargo', {})
            self._notice('Колонна уничтожена', 'Груз потерян у дороги.', faction=npc['faction'], tone='error')
            if f in FACTIONS and f != npc['faction']:
                share = .72 if self.flag(f, 'cargo_cut') else .6
                loot = {k: round(v * share, 1) for k, v in cargo.items() if v > 0}
                self._reward(f, loot)
                self.fstats[f]['kills'] += 1
                if f == 'bandits':
                    self.fstats[f]['tribute'] += 1
                if 'stats' in attacker:
                    attacker['stats']['kills'] += 1
                    self.gain_xp(attacker, 'kill_convoy')
                self._notice('Груз перехвачен', self.resource_text({k:int(v) for k, v in loot.items()}) or 'Пустой кузов', faction=f)
            return
        if f in FACTIONS:
            spec = NPC_TYPES[npc['type']]
            self._reward(f, spec['loot'])
            if attacker is not None and 'stats' in attacker:
                if spec.get('meat'):
                    got = self.give_item(attacker, 'meat_raw', spec['meat'])
                    self._notice('Добыча: ' + spec['name'], ('Сырое мясо ×' + str(got)) if got else 'Рюкзак полон — мясо осталось.', player=attacker['id'])
                elif self.rng.random() < (.4 if npc['faction'] == 'mutants' else .25):
                    self._loot_items(attacker, 1)
            self._credit_kill(attacker, npc)

    def _wreck_car(self, p):
        car = p['car']
        car['hp'] = 0
        car['wrecked_until'] = self.elapsed + 25
        self.effects.append({'id':secrets.token_hex(4),'kind':'boom','x':p['x'],'y':p['y'],'ex':p['x'],'ey':p['y'],
                             'until':self.elapsed+1.4,'faction':None})
        p['vehicle'] = False
        self._notice('Машина подбита', 'Её отбуксируют в убежище через 25 секунд.', player=p['id'], tone='error')

    def shoot_line(self, shooter, ax, ay, rng_, dmg, width=20):
        """Hitscan from shooter along (ax, ay). Returns the end point."""
        best = rng_; hit = None
        for o in self._entities():
            if o is shooter or not self.hostile_shot(shooter, o):
                continue
            dx = o['x'] - shooter['x']; dy = o['y'] - shooter['y']
            along = dx * ax + dy * ay; side = abs(dx * ay - dy * ax)
            size = 30 if (o.get('vehicle') or o.get('type') == 'convoy') else width
            if 0 < along < best and side < size and not self._covered(shooter, o):
                hit = o; best = along
        for post in list(self.posts.values()):
            if post['faction'] == shooter['faction'] or (self.truce_active() and shooter['faction'] in FACTIONS):
                continue
            dx = post['x'] - shooter['x']; dy = post['y'] - shooter['y']
            along = dx * ax + dy * ay; side = abs(dx * ay - dy * ax)
            if 0 < along < best and side < 34:
                hit = post; best = along
        end = {'x':shooter['x'] + ax * min(best, rng_), 'y':shooter['y'] + ay * min(best, rng_)}
        if hit is not None:
            self.hurt(hit, dmg, shooter)
        return end

    def hostile_shot(self, shooter, other):
        """Who a deliberate player shot may hit: never allies, neutral militia always."""
        if shooter['faction'] == other['faction']:
            return False
        if other.get('faction') in ('neutral', 'game'):
            return True
        return self.hostile(shooter, other)

    # ---- per-tick systems ----------------------------------------------
    def tick_npcs(self, dt, active):
        self.npc_clock += dt
        self._spawn_marauders(active)
        self._spawn_creatures(active)
        for npc in list(self.npcs.values()):
            if npc['hp'] <= 0:
                npc['dead'] = npc.get('dead', 0) + dt
                if npc['dead'] > 2.5:
                    del self.npcs[npc['id']]
                continue
            if npc['type'] == 'marauder' or npc['faction'] in ('wild', 'game', 'mutants'):
                near = min((self._dist(npc, p) for p in active), default=1e9)
                npc['far'] = npc['far'] + dt if near > 3400 else 0
                if npc['far'] > 20:
                    del self.npcs[npc['id']]
                    continue
            npc['cd'] = max(0, npc['cd'] - dt)
            npc['think'] -= dt
            if npc['think'] <= 0:
                npc['think'] = .2
                self._think(npc)
            self._move_npc(npc, dt)

    def _spawn_marauders(self, active):
        if self.npc_clock < 6:
            return
        self.npc_clock = 0
        count = sum(1 for n in self.npcs.values() if n['type'] == 'marauder')
        for p in active:
            if p['hp'] <= 0 or count >= MAX_MARAUDERS:
                continue
            # Ruins attract guards when somebody approaches.
            for poi in self.terrain.pois.values():
                if self._dist(p, poi) < 1100:
                    st = self.poi_state.setdefault(poi['id'], {})
                    if st.get('guards_until', 0) <= self.elapsed:
                        st['guards_until'] = self.elapsed + 300
                        for i in range(POI_KINDS[poi['kind']]['guards']):
                            spot = self._free_near(poi['x'], poi['y'], 160, 300)
                            if spot:
                                self.spawn_npc('marauder', 'marauders', spot[0], spot[1]); count += 1
            if any(self._dist(p, t) < 1000 for t in self.towns.values()):
                continue
            nearby = sum(1 for n in self.npcs.values() if n['type'] == 'marauder' and self._dist(n, p) < 2400)
            cap = 3 - (1 if p['faction'] == 'survivors' and self.flag('survivors', 'marauder_pact') else 0)
            if nearby < cap and self.rng.random() < .45:
                angle = self.rng.uniform(0, math.pi * 2)
                spot = self._free_near(p['x'] + math.cos(angle) * 1150, p['y'] + math.sin(angle) * 1150, 0, 250)
                if spot and not self.terrain.in_town(spot[0], spot[1], 300):
                    for i in range(1 + (self.rng.random() < .4)):
                        self.spawn_npc('marauder', 'marauders', spot[0] + i * 30, spot[1]); count += 1

    def is_night(self):
        hour = (8 + self.elapsed * 1.4 / 60) % 24
        return hour >= 21 or hour < 6

    def _spawn_creatures(self, active):
        """Wildlife by region around travellers; mutants near ruins and in the North, more at night."""
        if self.creature_clock > self.elapsed:
            return
        self.creature_clock = self.elapsed + 7
        count = sum(1 for n in self.npcs.values() if n['faction'] in ('wild', 'game', 'mutants'))
        night = self.is_night()
        for p in active:
            if p['hp'] <= 0 or count >= MAX_CREATURES or any(self._dist(p, t) < 1100 for t in self.towns.values()):
                continue
            town = min(self.towns.values(), key=lambda t: self._dist(t, p))
            biome = REGIONS[town['region']]['biome']
            near = [n for n in self.npcs.values() if self._dist(n, p) < 2600]
            if sum(1 for n in near if n['faction'] in ('wild', 'game')) < 3 and self.rng.random() < .4:
                kind = self.rng.choice(WILDLIFE[biome])
                size = self.rng.randint(2, 4) if kind == 'wolf' else self.rng.randint(1, 2) if kind in ('elk', 'boar') else 1
                count += self._spawn_group(p, kind, size)
            ruins = any(self._dist(o, p) < 1600 and o['kind'] in ('factory', 'military', 'mine', 'oil') for o in self.terrain.pois.values())
            north = REGIONS[town['region']]['cold'] >= 3
            cap = (3 if night else 1) + (1 if ruins or north else 0)
            chance = (.55 if night else .15) + (.2 if ruins or north else 0)
            if sum(1 for n in near if n['faction'] == 'mutants') < cap and self.rng.random() < chance:
                roll = self.rng.random()
                kind = 'brute' if roll < .1 else 'spitter' if roll < .3 else 'mutant'
                count += self._spawn_group(p, kind, 1 if kind != 'mutant' else self.rng.randint(1, 3))

    def _spawn_group(self, p, kind, size):
        angle = self.rng.uniform(0, math.pi * 2)
        spot = self._free_near(p['x'] + math.cos(angle) * 1200, p['y'] + math.sin(angle) * 1200, 0, 250)
        if not spot or self.terrain.in_town(spot[0], spot[1], 300):
            return 0
        for i in range(size):
            self.spawn_npc(kind, NPC_FACTION[kind], spot[0] + i * 26, spot[1] + (i % 2) * 22)
        return size

    def _free_near(self, x, y, rmin, rmax):
        for attempt in range(14):
            a = self.rng.uniform(0, math.pi * 2); r = self.rng.uniform(rmin, rmax)
            nx = x + math.cos(a) * r; ny = y + math.sin(a) * r
            if self.terrain.free_spot(nx, ny, 16):
                return nx, ny
        return None

    def _think(self, npc):
        spec = NPC_TYPES[npc['type']]
        if npc['type'] == 'convoy':
            return
        if spec.get('passive'):
            threat = min((o for o in self._entities() if o is not npc and o['faction'] not in ('game', 'wild')),
                         key=lambda o: self._dist(o, npc), default=None)
            if threat is not None and self._dist(threat, npc) < spec['flee']:
                a = math.atan2(npc['y'] - threat['y'], npc['x'] - threat['x']) + self.rng.uniform(-.5, .5)
                npc['goal'] = [npc['x'] + math.cos(a) * 500, npc['y'] + math.sin(a) * 500]; npc['mode'] = 'wander'
                npc['fleeing'] = self.elapsed
            elif not npc['goal'] or self.rng.random() < .03:
                hx, hy = npc['home']; spot = self._free_near(hx, hy, 0, 420)
                if spot: npc['goal'] = list(spot)
            return
        target = self._target_alive(npc['target'])
        if target is not None and not self.hostile(npc, target) and target.get('faction') != 'neutral':
            target = None
        aggro = spec.get('aggro', 470 if npc['type'] != 'militia' else 520) * (1.3 if npc['faction'] == 'mutants' and self.is_night() else 1)
        if target is None or self._dist(npc, target) > aggro * 1.6:
            target = None
            best = aggro
            for o in self._entities():
                if o is npc or not self.hostile(npc, o):
                    continue
                d = self._dist(npc, o)
                if d < best and not self._covered(npc, o):
                    best = d; target = o
        npc['target'] = self._ref(target) if target is not None else None
        if target is not None:
            npc['mode_before'] = npc.get('mode_before') or npc['mode']
            npc['mode'] = 'fight'
            d = self._dist(npc, target)
            if spec.get('melee'):
                if d < spec['range'] + (12 if target.get('vehicle') else 0) and npc['cd'] <= 0:
                    npc['cd'] = spec['cd'] * self.rng.uniform(.85, 1.2); npc['shot'] = self.elapsed
                    self.effects.append({'id':secrets.token_hex(4),'kind':'bite','x':npc['x'],'y':npc['y'],'ex':target['x'],'ey':target['y'],
                                         'until':self.elapsed+.3,'faction':npc['faction']})
                    if self.rng.random() < .8:
                        self.hurt(target, spec['dmg'], npc)
                return
            if d < spec['range'] and npc['cd'] <= 0 and not self._covered(npc, target):
                npc['cd'] = spec['cd'] * self.rng.uniform(.85, 1.25)
                npc['shot'] = self.elapsed
                chance = max(.28, min(.85, .9 - d / spec['range'] * .5))
                ex = target['x'] + self.rng.uniform(-14, 14); ey = target['y'] + self.rng.uniform(-14, 14)
                self.effects.append({'id':secrets.token_hex(4),'kind':'acid' if spec.get('acid') else 'shot','x':npc['x'],'y':npc['y'],'ex':ex,'ey':ey,
                                     'until':self.elapsed+.2,'faction':npc['faction']})
                if self.rng.random() < chance:
                    self.hurt(target, spec['dmg'], npc)
            return
        if npc['mode'] == 'fight':
            npc['mode'] = npc.pop('mode_before', None) or 'wander'
        if npc['mode'] == 'wander' and (not npc['goal'] or self.rng.random() < .04):
            hx, hy = npc['home']
            spot = self._free_near(hx, hy, 0, 380)
            if spot:
                npc['goal'] = list(spot)
        if npc['mode'] == 'guard' and self.rng.random() < .05:
            hx, hy = npc['home']
            npc['goal'] = [hx + self.rng.uniform(-90, 90), hy + self.rng.uniform(-90, 90)]
        if npc['mode'] == 'hold':
            t = self.towns.get(npc.get('job', {}).get('town')) if npc.get('job') else None
            if t and (self._dist(npc, t) > 120 or self.rng.random() < .05):
                a = self.rng.uniform(0, math.pi * 2)
                npc['goal'] = [t['x'] + math.cos(a) * 70, t['y'] + math.sin(a) * 70]

    def _move_npc(self, npc, dt):
        spec = NPC_TYPES[npc['type']]
        speed = spec['speed']
        goal = None
        if npc['mode'] == 'fight':
            target = self._target_alive(npc['target'])
            if target is not None:
                d = self._dist(npc, target)
                npc['angle'] = math.atan2(target['y'] - npc['y'], target['x'] - npc['x'])
                if d > spec['range'] * .7:
                    goal = [target['x'], target['y']]
                leash = npc['home']
                if npc['type'] not in ('raider', 'ranger') and math.hypot(npc['x'] - leash[0], npc['y'] - leash[1]) > 1100:
                    npc['target'] = None; npc['mode'] = npc.pop('mode_before', None) or 'wander'
                    goal = leash
        elif npc['mode'] == 'travel':
            if npc['path']:
                goal = npc['path'][0]
                if math.hypot(goal[0] - npc['x'], goal[1] - npc['y']) < 40:
                    npc['path'].pop(0)
                    goal = npc['path'][0] if npc['path'] else None
                if not npc['path']:
                    self._arrived(npc)
                    return
        else:
            goal = npc['goal']
        if not goal:
            return
        dx = goal[0] - npc['x']; dy = goal[1] - npc['y']; d = math.hypot(dx, dy)
        if d < 8:
            npc['goal'] = None
            return
        if self.weather['kind'] in ('storm', 'snow'):
            speed *= .88
        step = min(d, speed * dt)
        nx = npc['x'] + dx / d * step; ny = npc['y'] + dy / d * step
        if npc['mode'] != 'travel':
            if self.terrain.water(nx, ny):
                step *= .45; nx = npc['x'] + dx / d * step; ny = npc['y'] + dy / d * step
            if self.terrain.solid(nx, npc['y'], 10):
                nx = npc['x']
            if self.terrain.solid(nx, ny, 10):
                ny = npc['y']
            if nx == npc['x'] and ny == npc['y']:
                npc['goal'] = None
        npc['x'] = max(20, min(WORLD_SIZE[0] - 20, nx)); npc['y'] = max(20, min(WORLD_SIZE[1] - 20, ny))
        if npc['mode'] != 'fight':
            npc['angle'] = math.atan2(dy, dx)

    def _arrived(self, npc):
        job = npc.get('job') or {}
        if npc['type'] == 'convoy':
            f = npc['faction']
            if self.towns[BASES[f]]['owner'] == f:
                self._reward(f, npc.get('cargo', {}))
                self.fstats[f]['convoy'] += 1
                self._notice('Колонна прибыла', self.resource_text({k:int(v) for k, v in npc.get('cargo', {}).items() if v >= 1}), faction=f)
            del self.npcs[npc['id']]
            return
        if job.get('kind') == 'home':
            del self.npcs[npc['id']]
            return
        npc['mode'] = 'hold'
        npc['since'] = self.elapsed

    # ---- towers, posts and convoys --------------------------------------
    def tick_defenses(self, dt):
        self.tower_clock += dt
        if self.tower_clock < 1.5:
            return
        self.tower_clock = 0
        entities = self._entities()
        for t in self.towns.values():
            level = t['levels']['guard']
            if not level:
                continue
            tower = self.buildings[t['id'] + ':guard']
            owner = t['owner'] or 'neutral'
            cap = t['capture']
            me = {'faction':owner,'enemy':cap['faction'] if cap and cap['method'] == 'assault' else None}
            best = 380 + 40 * level; target = None
            for o in entities:
                if o.get('type') == 'convoy':
                    continue
                if not self.hostile(me, o) and not (cap and o['faction'] == cap['faction'] and cap['method'] == 'assault'):
                    continue
                d = self._dist(tower, o)
                if d < best:
                    best = d; target = o
            if target is not None:
                self.effects.append({'id':secrets.token_hex(4),'kind':'tower','x':tower['x'],'y':tower['y']-30,
                                     'ex':target['x'],'ey':target['y'],'until':self.elapsed+.2,'faction':t['owner']})
                self.hurt(target, 5 + 3 * level, {'faction':owner,'id':'tower'})
        for post in list(self.posts.values()):
            f = post['faction']
            me = {'faction':f}
            dmg = 9 if self.flag(f, 'iron_road') else 6
            best = 380; target = None
            for o in entities:
                if o.get('type') == 'convoy' or not self.hostile(me, o):
                    continue
                d = self._dist(post, o)
                if d < best:
                    best = d; target = o
            if target is not None:
                self.effects.append({'id':secrets.token_hex(4),'kind':'tower','x':post['x'],'y':post['y'],
                                     'ex':target['x'],'ey':target['y'],'until':self.elapsed+.2,'faction':f})
                self.hurt(target, dmg, {'faction':f,'id':'post'})
            if f == 'survivors':
                for p in entities:
                    if 'stats' in p and p['faction'] == f and self._dist(p, post) < 260:
                        p['hp'] = min(self.max_hp(p), p['hp'] + 4.5)
            # Bandit checkpoints take a quarter of passing enemy cargo once.
            if f == 'bandits' and not self.truce_active():
                for n in self.npcs.values():
                    if n['type'] == 'convoy' and n['faction'] != f and n['hp'] > 0 and \
                            post['id'] not in n.setdefault('taxed', []) and self._dist(n, post) < 230:
                        n['taxed'].append(post['id'])
                        toll = {k: round(v * .25, 1) for k, v in n['cargo'].items()}
                        for k, v in toll.items():
                            n['cargo'][k] -= v
                        self._reward(f, toll)
                        self.fstats[f]['tribute'] += 1
                        self._notice('Пошлина с колонны', self.resource_text({k:int(v) for k, v in toll.items() if v >= 1}), faction=f)
                        self._notice('Колонну обобрали на блокпосту', 'Четверть груза потеряна.', faction=n['faction'], tone='error')
        self.post_clock += 1.5
        if self.post_clock >= 30:
            self.post_clock = 0
            for post in self.posts.values():
                if post['faction'] == 'bandits':
                    extra = 1 if self.flag('bandits', 'iron_road') else 0
                    self._reward('bandits', {'fuel':2 + extra,'metal':2 + extra})
                else:
                    self.reputation['survivors'] = min(100, self.reputation['survivors'] + .5)

    def tick_convoys(self, dt):
        self.convoy_clock += dt
        if self.convoy_clock < 40:
            return
        self.convoy_clock = 0
        for f in FACTIONS:
            if sum(1 for n in self.npcs.values() if n['type'] == 'convoy' and n['faction'] == f) >= 3:
                continue
            towns = [t for t in self.towns.values() if t['owner'] == f and not t['base'] and sum(t['cargo'].values()) >= 10]
            if not towns:
                continue
            t = max(towns, key=lambda t: sum(t['cargo'].values()))
            route = self.terrain.route(t['id'], BASES[f])
            cargo = {k: v for k, v in t['cargo'].items() if v > 0}
            t['cargo'] = {k: 0.0 for k in RESOURCES}
            if len(route) < 2:
                self._reward(f, cargo)
                continue
            self.spawn_npc('convoy', f, t['x'], t['y'] + 40, mode='travel', path=self._path_points(route),
                           cargo=cargo, job={'kind':'convoy','from':t['id']})
            self._notice('Колонна вышла', t['name'] + ' → ' + self.towns[BASES[f]]['name'] + '. Груз можно сопроводить.', faction=f)

    # ---- AI commander for a faction without human players ---------------
    def tick_ai(self, dt):
        self.ai_clock += dt
        if self.ai_clock < 5:
            return
        self.ai_clock = 0
        for f in FACTIONS:
            if not self.ai_faction(f):
                continue
            st = self.ai_state.setdefault(f, {'build':0,'expand':240,'raid':600,'tax':0,'defend':0})
            if self.elapsed >= st['build']:
                st['build'] = self.elapsed + 22
                self._ai_build(f)
            if self.elapsed >= st['defend']:
                st['defend'] = self.elapsed + 10
                self._ai_defend(f)
            if self.elapsed >= st['expand']:
                st['expand'] = self.elapsed + self.rng.uniform(150, 240)
                self._ai_expand(f)
            if f == 'bandits' and self.elapsed >= st['tax']:
                st['tax'] = self.elapsed + 90
                for t in self.towns.values():
                    if t['owner'] == f and not t['base'] and t['loyalty'] > 62 and not t['capture']:
                        t['loyalty'] -= 12; self._reward(f, {'metal':8,'food':8}); self.fstats[f]['tribute'] += 1
                        break
            if f == 'bandits' and self.elapsed >= st['raid'] and not self.truce_active():
                st['raid'] = self.elapsed + self.rng.uniform(200, 300)
                self._ai_raid(f)
            for t in self.towns.values():
                if t['owner'] == f and t['loyalty'] < 40 and self.stocks[f]['food'] > 30 and \
                        self.elapsed >= t['cooldowns'].get('aid:' + f, 0):
                    self.stocks[f]['food'] -= 8; t['loyalty'] = min(100, t['loyalty'] + 14)
                    t['cooldowns']['aid:' + f] = self.elapsed + 40

    def _ai_build(self, f):
        options = []
        for t in self.towns.values():
            if t['owner'] != f or t['capture'] or len(t['construct']) >= 1:
                continue
            for rank, k in enumerate(AI_PRIORITY):
                level = t['levels'][k]
                if level >= 3 or (k != 'depot' and level >= t['levels']['depot']):
                    continue
                if k == 'radio' and not t['base']:
                    continue
                cost = self.build_cost(t, k)
                if self._can_pay(f, {r: v * 1.15 for r, v in cost.items()}):
                    options.append((level * 4 + rank + (0 if t['base'] else 2), t, k, cost))
        if options:
            options.sort(key=lambda o: o[0])
            _, t, k, cost = options[0]
            self._pay(f, cost)
            self.start_construction(t, k, None)

    def _ai_targets(self, f, enemy_ok):
        mine = [t['id'] for t in self.towns.values() if t['owner'] == f]
        out = []
        for t in self.towns.values():
            if t['owner'] == f or t['base'] or t['capture'] or t['shield'] > self.elapsed:
                continue
            if t['owner'] and (not enemy_ok or self.truce_active()):
                continue
            d = min(self.terrain.road_distance(m, t['id']) for m in mine) if mine else 1e9
            out.append((d + (2500 if t['owner'] else 0), t))
        out.sort(key=lambda o: o[0])
        return [t for d, t in out]

    def _squad(self, f, kind):
        return [n for n in self.npcs.values() if n['faction'] == f and n.get('job') and n['job'].get('kind') == kind and n['hp'] > 0]

    def _ai_expand(self, f):
        if self._squad(f, 'capture'):
            return
        owned = sum(1 for t in self.towns.values() if t['owner'] == f)
        rival = sum(1 for t in self.towns.values() if t['owner'] == other_faction(f))
        # The computer side keeps pace with the players instead of running away with the map.
        if owned > rival + 2:
            return
        targets = self._ai_targets(f, enemy_ok=owned >= 3 and self.elapsed > 900)
        if not targets:
            return
        target = targets[0]
        method = 'talk' if f == 'survivors' and not target['owner'] else 'assault'
        if not self._can_pay(f, SQUAD_COSTS[method]):
            method = 'bribe' if self._can_pay(f, SQUAD_COSTS['bribe']) else None
        if method is None:
            return
        homes = [t for t in self.towns.values() if t['owner'] == f]
        home = min(homes, key=lambda t: self.terrain.road_distance(t['id'], target['id']))
        route = self.terrain.route(home['id'], target['id'])
        if len(route) < 2:
            return
        kind = 'ranger' if f == 'survivors' else 'raider'
        size = 2 + (owned >= 4) + (method == 'assault')
        for i in range(size):
            self.spawn_npc(kind, f, home['x'] + i * 24, home['y'] + 60, mode='travel',
                           path=self._path_points(route),
                           job={'kind':'capture','town':target['id'],'method':method,'tries':0})
        self._notice('Отряд вышел в путь', FACTIONS[f] + ' направляются к поселению ' + target['name'] + '.',
                     faction=other_faction(f))

    def _ai_raid(self, f):
        if self._squad(f, 'raid'):
            return
        victims = [t for t in self.towns.values() if t['owner'] == other_faction(f) and not t['base']]
        if not victims:
            return
        mine = [t for t in self.towns.values() if t['owner'] == f]
        target = min(victims, key=lambda t: min(self.terrain.road_distance(m['id'], t['id']) for m in mine))
        home = min(mine, key=lambda t: self.terrain.road_distance(t['id'], target['id']))
        route = self.terrain.route(home['id'], target['id'])
        if len(route) < 2:
            return
        for i in range(3):
            self.spawn_npc('raider', f, home['x'] + i * 24, home['y'] + 60, mode='travel',
                           path=self._path_points(route), job={'kind':'raid','town':target['id']})
        self._notice('Разведка заметила налётчиков', 'Бандиты идут к поселению ' + target['name'] + '. Защитите площадь.',
                     faction=other_faction(f), tone='error')

    def _ai_defend(self, f):
        for t in self.towns.values():
            c = t['capture']
            if t['owner'] != f or not c or c['faction'] == f or self._squad(f, 'defend'):
                continue
            kind = 'ranger' if f == 'survivors' else 'raider'
            for i in range(2):
                spot = self._free_near(t['x'], t['y'], 120, 260)
                if spot:
                    self.spawn_npc(kind, f, spot[0], spot[1], mode='hold', job={'kind':'defend','town':t['id']})

    def tick_squads(self):
        """Squads that reached their town try to take it, hold the square or raid it."""
        for npc in list(self.npcs.values()):
            job = npc.get('job') or {}
            if npc['hp'] <= 0 or npc['mode'] not in ('hold', 'fight') or 'town' not in job:
                continue
            t = self.towns[job['town']]
            f = npc['faction']
            if job['kind'] == 'defend':
                if not t['capture'] or t['owner'] != f:
                    self._send_home(npc)
                continue
            if job['kind'] == 'raid':
                if self.elapsed - npc.get('since', self.elapsed) > 15 and npc['mode'] == 'hold':
                    squad = [n for n in self._squad(f, 'raid') if n['job']['town'] == t['id']]
                    victim = t['owner']
                    if victim in FACTIONS and victim != f and not self.truce_active():
                        loot = {k: min(20, round(self.stocks[victim][k] * .15, 1)) for k in ('food', 'metal', 'fuel')}
                        for k, v in loot.items():
                            self.stocks[victim][k] -= v
                        self._reward(f, loot); self.fstats[f]['tribute'] += 1
                        t['loyalty'] = max(0, t['loyalty'] - 10)
                        self._notice('Набег на ' + t['name'], 'Унесено: ' + self.resource_text({k:int(v) for k, v in loot.items()}),
                                     faction=victim, tone='error')
                    for n in squad:
                        self._send_home(n)
                continue
            if job['kind'] != 'capture':
                continue
            if t['owner'] == f:
                if not t['capture']:
                    self._send_home(npc)
                continue
            if t['capture'] and t['capture']['faction'] == f:
                continue
            if t['capture'] or t['shield'] > self.elapsed or t['base']:
                if self.elapsed - npc.get('since', self.elapsed) > 60:
                    self._send_home(npc)
                continue
            key = 'attempt:' + f
            if t['cooldowns'].get(key, 0) > self.elapsed or npc['mode'] != 'hold':
                continue
            squad = [n for n in self._squad(f, 'capture') if n['job']['town'] == t['id'] and self._dist(n, t) < 300]
            method = job['method']
            if job['tries'] >= 3 or not self._can_pay(f, SQUAD_COSTS[method]):
                for n in squad:
                    self._send_home(n)
                continue
            for n in squad:
                n['job']['tries'] += 1
            self._pay(f, SQUAD_COSTS[method])
            chance = self.chance_for(f, t, method, len(squad), 0)
            roll = self.rng.randint(1, 100)
            t['cooldowns'][key] = self.elapsed + 35
            if roll <= chance:
                self.begin_capture(t, f, method)

    def _send_home(self, npc):
        f = npc['faction']
        homes = [t for t in self.towns.values() if t['owner'] == f]
        if not homes:
            npc['hp'] = 0
            return
        home = min(homes, key=lambda t: self._dist(t, npc))
        npc['mode'] = 'travel'; npc['path'] = [[home['x'], home['y']]]; npc['job'] = {'kind':'home'}
        npc['target'] = None

    def spawn_militia(self, t, attacker):
        owner = t['owner'] or 'neutral'
        count = 1 + t['levels']['guard'] + (1 if t['owner'] and self.flag(t['owner'], 'militia') else 0)
        for i in range(count):
            spot = self._free_near(t['x'], t['y'], 90, 240)
            if spot:
                self.spawn_npc('militia', owner, spot[0], spot[1], mode='guard', home=[spot[0], spot[1]],
                               enemy=attacker, job={'kind':'militia','town':t['id']})

    def clear_militia(self, t):
        for n in list(self.npcs.values()):
            if n['type'] == 'militia' and (n.get('job') or {}).get('town') == t['id']:
                del self.npcs[n['id']]

    def npc_view(self, n):
        out = {k: n[k] for k in ('id', 'type', 'faction', 'hp', 'max', 'mode', 'shot')}
        out['x'] = round(n['x'], 1); out['y'] = round(n['y'], 1); out['angle'] = round(n['angle'], 2)
        if n['type'] == 'convoy':
            out['cargo'] = int(sum(n.get('cargo', {}).values()))
        return out
