"""The infected and wild animals: spawning, senses, chasing, biting, and damage for everybody.

Mixed into server.World. Everything here runs on the host, inside the world lock.

Every settlement and every place outside the towns is a zone with its own number of infected. They appear
when a player comes near and vanish when nobody has been around for a while; the ones killed come back
slowly. An infected stands or shuffles about until it sees a player (running players and players in cars
are seen from further away, night and fog hide them) or hears a noise: a shot, an engine, an axe. Then it
runs at the source. Animals live outside the towns: wolves, bears and boars attack, elk flee.
"""
import math
import secrets
import time
from world_data import (NPC_TYPES, POI_KINDS, ARMOR, NPC_FACTION, WILDLIFE, REGIONS, WORLD_SIZE, TOWN_INFECTED,
                        INFECTED_LOOKS, MAX_INFECTED, ITEMS, FISTS)

CELL = 600                 # spatial grid for target searches
WAKE = 3000                # characters further than this from every player sleep
ZONE_NEAR = 1000           # a zone fills when a player is this far outside its edge
ZONE_FORGET = 2200         # and empties when everybody stays further than this for ZONE_IDLE seconds
ZONE_IDLE = 40
ZONE_REGEN = 120           # one killed infected returns this often
MAX_CREATURES = 30
LOSE_SIGHT = 10            # seconds an infected keeps chasing someone it no longer sees


def ray_rect(sx, sy, ax, ay, r):
    """Distance along a unit ray to an axis-aligned rectangle, or None."""
    lo, hi = 0.0, 1e9
    for s, a, c, half in ((sx, ax, r['x'], r['w'] / 2), (sy, ay, r['y'], r['h'] / 2)):
        if abs(a) < 1e-9:
            if abs(s - c) > half:
                return None
            continue
        t1 = (c - half - s) / a; t2 = (c + half - s) / a
        lo = max(lo, min(t1, t2)); hi = min(hi, max(t1, t2))
        if lo > hi:
            return None
    return lo


class NpcMixin:
    # ---- zones of the infected ------------------------------------------
    def init_infected(self):
        self.zones = {}
        for t in self.towns.values():
            self.zones['t:' + t['id']] = {'id':'t:' + t['id'], 'x':t['x'], 'y':t['y'], 'rx':t['r'], 'ry':t['h'],
                                          'max':TOWN_INFECTED[t['kind']], 'left':TOWN_INFECTED[t['kind']], 'up':False,
                                          'idle':0.0, 'regen':0.0, 'soldiers':False}
        for poi in self.terrain.pois.values():
            n = POI_KINDS[poi['kind']]['infected']
            self.zones['p:' + poi['id']] = {'id':'p:' + poi['id'], 'x':poi['x'], 'y':poi['y'], 'rx':260, 'ry':220, 'max':n, 'left':n,
                                            'up':False, 'idle':0.0, 'regen':0.0,
                                            'soldiers':POI_KINDS[poi['kind']]['loot'] == 'military'}
        self.npc_clock = 0.0

    def zone_save(self):
        return {k: {'left':z['left'], 'regen':z['regen']} for k, z in self.zones.items()}

    def zone_load(self, raw):
        for k, v in raw.items():
            z = self.zones.get(k)
            if z and isinstance(v, dict):
                try:
                    z['left'] = max(0, min(z['max'], int(v.get('left', z['max']))))
                    z['regen'] = float(v.get('regen', 0))
                except (TypeError, ValueError):
                    pass

    def _zone_gap(self, z, o):
        """How far a point is outside the zone's rectangle (0 inside)."""
        dx = max(0.0, abs(o['x'] - z['x']) - z['rx']); dy = max(0.0, abs(o['y'] - z['y']) - z['ry'])
        return math.hypot(dx, dy)

    def _tick_zones(self, dt, people):
        count = sum(1 for n in self.npcs.values() if n.get('zone'))
        for z in self.zones.values():
            if z['left'] < z['max']:
                z['regen'] += dt
                if z['regen'] >= ZONE_REGEN:
                    z['regen'] = 0.0; z['left'] += 1
            gap = min((self._zone_gap(z, p) for p in people), default=1e9)
            if not z['up']:
                if gap < ZONE_NEAR and z['left'] > 0 and count < MAX_INFECTED:
                    z['up'] = True; z['idle'] = 0.0
                    count += self._fill_zone(z, min(z['left'], MAX_INFECTED - count))
                continue
            if gap > ZONE_FORGET:
                z['idle'] += dt
                if z['idle'] > ZONE_IDLE:
                    # Nobody around: the zone's infected go back into the count and leave the simulation.
                    for n in [n for n in self.npcs.values() if n.get('zone') == z['id']]:
                        if n['hp'] > 0:
                            del self.npcs[n['id']]
                    z['up'] = False
            else:
                z['idle'] = 0.0

    def _fill_zone(self, z, n):
        made = 0
        for i in range(n):
            spot = self._free_near(z['x'], z['y'], 0, max(120, min(z['rx'], z['ry']) * .9))
            if not spot:
                continue
            kind = 'infected_soldier' if z['soldiers'] and self.rng.random() < .6 else 'infected'
            self.spawn_npc(kind, spot[0], spot[1], zone=z['id'])
            made += 1
        return made

    # ---- shared helpers -------------------------------------------------
    def hostile(self, a, b):
        """Infected and predators attack people; people may hurt anybody but their clan."""
        fa = a['faction']; fb = b['faction']
        if 'stats' in a and 'stats' in b:
            return fa != fb and not self.truce_between(fa, fb)
        if 'stats' in b:
            return fa in ('infected', 'wild')
        if 'stats' in a:
            return True
        return False

    def active_players(self):
        now = time.monotonic()
        return [p for p in self.players.values() if now - p['last_seen'] < 8]

    def spawn_npc(self, kind, x, y, **extra):
        spec = NPC_TYPES[kind]
        npc = {'id':secrets.token_hex(5), 'type':kind, 'faction':NPC_FACTION[kind], 'x':float(x), 'y':float(y),
               'angle':self.rng.uniform(-math.pi, math.pi), 'hp':float(spec['hp']), 'max':float(spec['hp']), 'mode':'idle',
               'home':[float(x), float(y)], 'goal':None, 'cd':0.0, 'think':self.rng.random() * .25, 'target':None,
               'shot':-10.0, 'far':0.0, 'near':0.0, 'seen':-100.0}
        if kind in INFECTED_LOOKS:
            npc['look'] = self.rng.choice(INFECTED_LOOKS[kind])
        npc.update(extra)
        self.npcs[npc['id']] = npc
        return npc

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

    def _build_grid(self):
        grid = {}
        for o in self._entities():
            grid.setdefault((int(o['x'] // CELL), int(o['y'] // CELL)), []).append(o)
        self._grid = grid

    def _nearby(self, x, y, r):
        """Living players and creatures within roughly r of a point (grid cells)."""
        grid = getattr(self, '_grid', None)
        if grid is None:
            return [o for o in self._entities() if abs(o['x'] - x) <= r and abs(o['y'] - y) <= r]
        out = []
        for cx in range(int((x - r) // CELL), int((x + r) // CELL) + 1):
            for cy in range(int((y - r) // CELL), int((y + r) // CELL) + 1):
                for o in grid.get((cx, cy), ()):
                    if o['hp'] > 0:
                        out.append(o)
        return out

    def _ref(self, entity):
        return ('p', entity['id']) if 'stats' in entity else ('n', entity['id'])

    def is_night(self):
        hour = (8 + self.elapsed * 1.4 / 60) % 24
        return hour >= 21 or hour < 6

    def _free_near(self, x, y, rmin, rmax):
        for attempt in range(14):
            a = self.rng.uniform(0, math.pi * 2); r = self.rng.uniform(rmin, rmax)
            nx = x + math.cos(a) * r; ny = y + math.sin(a) * r
            if self.terrain.free_spot(nx, ny, 16):
                return nx, ny
        return None

    # ---- damage ---------------------------------------------------------
    def hurt(self, target, amount, attacker=None, bleed=.3):
        """Apply damage to a player or a creature. Returns True on a kill."""
        if 'stats' in target:
            if target['hp'] <= 0:
                return False
            amount *= 1 - ARMOR[target['gear']['armor']]['reduce']
            if attacker is not None:
                kind = 'player' if 'stats' in attacker else 'infected' if attacker['faction'] == 'infected' else 'animal'
                target['hit_by'] = {'kind':kind, 'id':attacker['id'], 'name':attacker['name'] if kind == 'player' else NPC_TYPES[attacker['type']]['name'], 'at':self.elapsed}
            if target['vehicle']:
                car = self.cars.get(target.get('car'))
                if car:
                    car['hp'] = max(0.0, car['hp'] - amount / self.car_spec(car)['armor'])
                    amount *= .3
                    if car['hp'] <= 0:
                        self.wreck_car(car)
                        amount += 15
            self._damage(target, amount)
            # Wounds bleed; armor makes it less likely.
            if target['hp'] > 0 and amount >= 5 and not target['bleeding'] and \
                    self.rng.random() < bleed - ARMOR[target['gear']['armor']]['reduce'] * .5:
                target['bleeding'] = True
                self._notice('Кровотечение', 'Перевяжись: H (бинт, аптечка или ткань).', player=target['id'], tone='error')
            if target['hp'] <= 0 and attacker is not None:
                self._credit_kill(attacker, target)
                return True
            return False
        if target['hp'] <= 0:
            return False
        target['hp'] -= amount
        if target['hp'] <= 0:
            self._npc_killed(target, attacker)
            return True
        if attacker is not None and 'stats' in attacker and not NPC_TYPES[target['type']].get('passive'):
            target['target'] = self._ref(attacker); target['mode'] = 'chase'; target['seen'] = self.elapsed
        return False

    def _credit_kill(self, attacker, victim):
        if 'stats' not in attacker:
            return
        if 'stats' in victim:
            attacker['stats']['players'] += 1
            self._notice('Ты убил ' + victim['name'], 'Всё, что было при нём, осталось на теле.', player=attacker['id'], tone='error')
            self._notice('Тебя убил ' + attacker['name'], '', player=victim['id'], tone='error')
        elif victim['faction'] == 'infected':
            attacker['stats']['infected'] += 1
        else:
            attacker['stats']['animals'] += 1

    def _npc_killed(self, npc, attacker):
        npc['hp'] = 0
        self.effects.append({'id':secrets.token_hex(4), 'kind':'fall', 'x':npc['x'], 'y':npc['y'], 'ex':npc['x'], 'ey':npc['y'],
                             'until':self.elapsed + 1.2, 'faction':None})
        if attacker is not None:
            self._credit_kill(attacker, npc)
        z = self.zones.get(npc.get('zone'))
        if z:
            z['left'] = max(0, z['left'] - 1)
        spec = NPC_TYPES[npc['type']]
        loot = {}
        if spec.get('meat'):
            # A carcass gives meat and a hide; take them from the body (E).
            loot['meat_raw'] = spec['meat']
            if npc['type'] != 'boar':
                loot['hide'] = 2 if npc['type'] == 'bear' else 1
        elif self.rng.random() < (.35 if npc['type'] == 'infected_soldier' else .2):
            table = 'military' if npc['type'] == 'infected_soldier' else 'residential'
            item, n = self._roll(table)
            if 'weapon' not in ITEMS[item] and 'gear' not in ITEMS[item]:
                loot[item] = n
        npc['loot'] = loot

    def shoot_line(self, shooter, ax, ay, rng_, dmg, width=20):
        """Hitscan from shooter along (ax, ay). Returns the end point."""
        best = rng_; hit = None
        for o in self._nearby(shooter['x'], shooter['y'], rng_):
            if o is shooter or not self.hostile_shot(shooter, o):
                continue
            dx = o['x'] - shooter['x']; dy = o['y'] - shooter['y']
            along = dx * ax + dy * ay; side = abs(dx * ay - dy * ax)
            size = 30 if o.get('vehicle') else width
            if 0 < along < best and side < size and not self._covered(shooter, o):
                hit = o; best = along
        # Camp fences, gates and furniture of other people stop bullets and take the damage.
        piece = None
        for camp, slot, rect in self.camp_targets():
            if abs(rect['x'] - shooter['x']) > best + 60 or abs(rect['y'] - shooter['y']) > best + 60:
                continue
            if self.camp_allowed(camp, shooter.get('faction')):
                continue
            d = ray_rect(shooter['x'], shooter['y'], ax, ay, rect)
            if d is not None and d < best:
                best = d; hit = None; piece = (camp, slot)
        # Cars standing in the way catch bullets too.
        car_hit = None
        for car in self.cars.values():
            if car['wrecked_at'] is not None or car.get('id') == shooter.get('car'):
                continue
            dx = car['x'] - shooter['x']; dy = car['y'] - shooter['y']
            along = dx * ax + dy * ay; side = abs(dx * ay - dy * ax)
            if 0 < along < best and side < self.car_spec(car)['wid'] * .45 and not self.car_driver(car) and not self.car_riders(car):
                best = along; hit = None; piece = None; car_hit = car
        end = {'x':shooter['x'] + ax * min(best, rng_), 'y':shooter['y'] + ay * min(best, rng_)}
        if piece:
            self.damage_camp_piece(piece[0], piece[1], dmg, shooter)
        elif car_hit:
            car_hit['hp'] = max(0.0, car_hit['hp'] - dmg * .3 / self.car_spec(car_hit)['armor'])
            if car_hit['hp'] <= 0:
                self.wreck_car(car_hit)
        elif hit is not None:
            self.hurt(hit, dmg, shooter)
        return end

    def melee_hit(self, p, ax, ay, weapon):
        """A swing in front of the player: the nearest enemy within reach takes the blow."""
        best = None
        for o in self._nearby(p['x'], p['y'], weapon['range'] + 30):
            if o is p or o.get('vehicle') or not self.hostile_shot(p, o):
                continue
            dx = o['x'] - p['x']; dy = o['y'] - p['y']; d = math.hypot(dx, dy)
            if d > weapon['range'] + 14 or (d > 1 and (dx * ax + dy * ay) / d < .45):
                continue
            if best is None or d < best[0]:
                best = (d, o)
        self.effects.append({'id':secrets.token_hex(4), 'kind':'swing', 'x':p['x'], 'y':p['y'], 'ex':p['x'] + ax * weapon['range'],
                             'ey':p['y'] + ay * weapon['range'], 'until':self.elapsed + .25, 'faction':p['faction'], 'weapon':p['gear']['weapon']})
        if best:
            o = best[1]
            self.hurt(o, weapon['dmg'] * self.rng.uniform(.85, 1.15), p, bleed=.15 if p['gear']['weapon'] == FISTS else .35)
            # A hit staggers: the infected loses a moment.
            if 'stats' not in o:
                o['cd'] = max(o['cd'], .5)
            self.make_noise(p['x'], p['y'], 160, p)
        return best[1] if best else None

    def hostile_shot(self, shooter, other):
        """Who a player's shot or blow may hit: anybody but themselves and their clan."""
        if shooter is other:
            return False
        if 'stats' in other:
            return not self.truce_between(shooter['faction'], other['faction']) and shooter['faction'] != other['faction']
        return True

    # ---- per-tick systems ----------------------------------------------
    def tick_npcs(self, dt, active):
        people = [p for p in active if p['hp'] > 0]
        self.npc_clock += dt
        if self.npc_clock >= 1.0:
            self._tick_zones(self.npc_clock, people)
            self._spawn_creatures(people)
            self.npc_clock = 0.0
        self._build_grid()
        self.wake_clock = getattr(self, 'wake_clock', 0.0) - dt
        recount = self.wake_clock <= 0
        if recount:
            self.wake_clock = 1.0
        for npc in list(self.npcs.values()):
            if npc['hp'] <= 0:
                npc['dead'] = npc.get('dead', 0) + dt
                if npc['dead'] > 2.5:
                    # The fall is over: the body stays on the ground for a while.
                    self.drop_corpse(npc)
                    del self.npcs[npc['id']]
                continue
            if recount:
                npc['near'] = min((self._dist(npc, p) for p in people), default=1e9)
                if not npc.get('zone'):
                    npc['far'] = npc['far'] + 1 if npc['near'] > 3400 else 0
                    if npc['far'] > 20:
                        del self.npcs[npc['id']]
                        continue
            if npc['near'] > WAKE:
                continue
            npc['cd'] = max(0, npc['cd'] - dt)
            npc['think'] -= dt
            if npc['think'] <= 0:
                npc['think'] = .25
                self._think(npc)
            self._move_npc(npc, dt)

    def _spawn_creatures(self, people):
        """Wildlife by region around travellers outside the towns."""
        if self.creature_clock > self.elapsed:
            return
        self.creature_clock = self.elapsed + 8
        count = sum(1 for n in self.npcs.values() if not n.get('zone'))
        for p in people:
            if count >= MAX_CREATURES or self.terrain.in_town(p['x'], p['y'], 600):
                continue
            near = [n for n in self.npcs.values() if not n.get('zone') and self._dist(n, p) < 2600]
            if len(near) >= 3 or self.rng.random() > .35:
                continue
            town = min(self.towns.values(), key=lambda t: self._dist(t, p))
            kind = self.rng.choice(WILDLIFE[REGIONS[town['region']]['biome']])
            size = self.rng.randint(2, 3) if kind == 'wolf' else self.rng.randint(1, 2) if kind in ('elk', 'boar') else 1
            a = self.rng.uniform(0, math.pi * 2)
            spot = self._free_near(p['x'] + math.cos(a) * 1300, p['y'] + math.sin(a) * 1300, 0, 250)
            if not spot or self.terrain.in_town(spot[0], spot[1], 300):
                continue
            for i in range(size):
                self.spawn_npc(kind, spot[0] + i * 26, spot[1] + (i % 2) * 22, mode='wander')
            count += size

    # ---- senses ----------------------------------------------------------------
    def _sight(self, npc, o):
        """How far this creature notices this player right now."""
        spec = NPC_TYPES[npc['type']]
        base = spec.get('sight', spec.get('aggro', 400))
        if o.get('vehicle'):
            return base * 1.6
        moving = o['input'][0] or o['input'][1]
        k = 1.0 if (moving and o['input'][2]) else .7 if moving else .45
        if self.is_night():
            k *= .6
        if self.weather['kind'] in ('fog', 'snow'):
            k *= .65
        elif self.weather['kind'] in ('rain', 'storm'):
            k *= .85
        return base * k

    def _think(self, npc):
        spec = NPC_TYPES[npc['type']]
        if spec.get('passive'):
            threat = min((o for o in self._nearby(npc['x'], npc['y'], spec['flee']) if 'stats' in o),
                         key=lambda o: self._dist(o, npc), default=None)
            if threat is not None and self._dist(threat, npc) < spec['flee']:
                a = math.atan2(npc['y'] - threat['y'], npc['x'] - threat['x']) + self.rng.uniform(-.5, .5)
                npc['goal'] = [npc['x'] + math.cos(a) * 500, npc['y'] + math.sin(a) * 500]; npc['mode'] = 'flee'
            elif not npc['goal'] or self.rng.random() < .03:
                npc['mode'] = 'wander'
                spot = self._free_near(npc['home'][0], npc['home'][1], 0, 420)
                if spot:
                    npc['goal'] = list(spot)
            return
        target = self._target_alive(npc['target'])
        if target is not None and not self.hostile(npc, target):
            target = None
        # Who can it see right now?
        seen = None; best = 1e9
        for o in self._nearby(npc['x'], npc['y'], 800):
            if 'stats' not in o or not self.hostile(npc, o):
                continue
            d = self._dist(npc, o)
            if d < self._sight(npc, o) and d < best and not self._covered(npc, o):
                best = d; seen = o
        if seen is not None:
            if target is None or self._dist(npc, seen) < self._dist(npc, target) * .7:
                target = seen
            if target is seen:
                npc['seen'] = self.elapsed
        if target is not None and (self.elapsed - npc['seen'] > LOSE_SIGHT or self._dist(npc, target) > 1600):
            # Lost: walk to the last place it was seen, then calm down.
            npc['goal'] = [target['x'], target['y']]; target = None; npc['mode'] = 'alert'
        if target is None and npc['faction'] == 'infected':
            noise = None
            for n in self.noises:
                d = math.hypot(n['x'] - npc['x'], n['y'] - npc['y'])
                if d < n['r'] and (noise is None or d < noise[0]):
                    noise = (d, n)
            if noise:
                n = noise[1]
                npc['goal'] = [n['x'] + self.rng.uniform(-60, 60), n['y'] + self.rng.uniform(-60, 60)]; npc['mode'] = 'alert'
                npc['alert_until'] = self.elapsed + 20
        npc['target'] = self._ref(target) if target is not None else None
        if target is not None:
            npc['mode'] = 'chase'
            d = self._dist(npc, target)
            reach = spec['range'] + (16 if target.get('vehicle') else 0)
            if d < reach and npc['cd'] <= 0:
                npc['cd'] = spec['cd'] * self.rng.uniform(.85, 1.2); npc['shot'] = self.elapsed
                self.effects.append({'id':secrets.token_hex(4), 'kind':'bite', 'x':npc['x'], 'y':npc['y'], 'ex':target['x'], 'ey':target['y'],
                                     'until':self.elapsed + .3, 'faction':npc['faction']})
                if self.rng.random() < .8:
                    self.hurt(target, spec['dmg'], npc, bleed=spec.get('bleed', .3))
                    # An infected bite can carry an infection; tetracycline cures it.
                    if npc['faction'] == 'infected' and 'stats' in target and target['hp'] > 0 and self.rng.random() < .06 \
                            and target['sick'] <= self.elapsed:
                        target['sick'] = self.elapsed + 180
                        self._notice('Заражение', 'Рана воспалилась: лихорадка. Поможет тетрациклин.', player=target['id'], tone='error')
            return
        if npc['mode'] == 'chase':
            npc['mode'] = 'idle'
        if npc['mode'] == 'alert':
            if npc.get('alert_until', 0) < self.elapsed or not npc['goal']:
                npc['mode'] = 'idle'
            return
        # Idle: the infected shuffle about where they stand; animals wander their range.
        if not npc['goal'] and self.rng.random() < (.02 if npc['faction'] == 'infected' else .05):
            spot = self._free_near(npc['home'][0], npc['home'][1], 0, 180 if npc['faction'] == 'infected' else 420)
            if spot:
                npc['goal'] = list(spot)

    def _move_npc(self, npc, dt):
        spec = NPC_TYPES[npc['type']]
        goal = None
        speed = spec['speed']
        if npc['mode'] == 'chase':
            target = self._target_alive(npc['target'])
            if target is not None:
                d = self._dist(npc, target)
                npc['angle'] = math.atan2(target['y'] - npc['y'], target['x'] - npc['x'])
                if d > spec['range'] * .7:
                    goal = [target['x'], target['y']]
                speed = spec.get('run', spec['speed'])
        else:
            goal = npc['goal']
            if npc['mode'] in ('alert', 'flee'):
                speed = spec.get('run', spec['speed']) * (.7 if npc['mode'] == 'alert' else 1)
            elif npc['faction'] == 'infected':
                speed *= .6
        npc['running'] = speed > spec['speed'] * 1.2
        if not goal:
            return
        dx = goal[0] - npc['x']; dy = goal[1] - npc['y']; d = math.hypot(dx, dy)
        if d < 8:
            npc['goal'] = None
            return
        if self.weather['kind'] in ('storm', 'snow'):
            speed *= .9
        if npc['cd'] > spec.get('cd', 1) * .9:
            speed *= .3      # just struck or was struck
        step = min(d, speed * dt)
        nx = npc['x'] + dx / d * step; ny = npc['y'] + dy / d * step
        if self.terrain.water(nx, ny):
            step *= .45; nx = npc['x'] + dx / d * step; ny = npc['y'] + dy / d * step
        moved = False
        if not self.solid_for(nx, npc['y'], 10, npc['faction']):
            npc['x'] = nx; moved = True
        if not self.solid_for(npc['x'], ny, 10, npc['faction']):
            npc['y'] = ny; moved = True
        if not moved:
            # Stuck on a wall: sidestep around it.
            a = math.atan2(dy, dx) + (math.pi / 2 if self.rng.random() < .5 else -math.pi / 2)
            sx, sy = npc['x'] + math.cos(a) * step, npc['y'] + math.sin(a) * step
            if not self.solid_for(sx, sy, 10, npc['faction']):
                npc['x'], npc['y'] = sx, sy
            elif npc['mode'] != 'chase':
                npc['goal'] = None
        npc['x'] = max(20, min(WORLD_SIZE[0] - 20, npc['x'])); npc['y'] = max(20, min(WORLD_SIZE[1] - 20, npc['y']))
        if npc['mode'] != 'chase':
            npc['angle'] = math.atan2(dy, dx)

    def npc_view(self, n):
        out = {k: n[k] for k in ('id', 'type', 'faction', 'hp', 'max', 'mode', 'shot')}
        if 'look' in n:
            out['look'] = n['look']
        out['x'] = round(n['x'], 1); out['y'] = round(n['y'], 1); out['angle'] = round(n['angle'], 2)
        out['run'] = bool(n.get('running'))
        return out
