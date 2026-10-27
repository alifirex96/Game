"""Loot on the ground: what lies in buildings, what players drop, and taking things from bodies.

Mixed into server.World. Runs on the host inside the world lock.

Every house and every building of a place outside the towns has a few spots where things can lie. When a
player comes within LOOT_RANGE, empty buildings whose restock time has passed get new things from the table
of their kind (rural, residential, medical, industrial, farm, gas, military). Untouched things vanish after
LOOT_LIFETIME, so the region slowly refills on its own.
"""
import math
import secrets
from world_data import (ITEMS, WEAPONS, LOOT_TABLES, LOOT_RESTOCK, LOOT_LIFETIME, LOOT_RANGE, LOOT_PER_HOUSE,
                        LOOT_PER_POI_PART, MAX_GUNS, FISTS, BACKPACKS, GEAR_ITEM, WEAPON_ITEM, CLOTHES, ARMOR)

LOOT_CELL = 500
MAX_LOOT = 3000
PICK_RANGE = 70
GEAR_KINDS = {'clothes':CLOTHES, 'backpack':BACKPACKS, 'armor':ARMOR}


class LootMixin:
    def init_loot(self):
        self.loot = {}
        self.loot_grid = {}
        self.loot_restock = {}
        self.loot_clock = 0.0
        self.loot_spots = {}
        self.spot_grid = {}
        for bid, table, kind, pts in self.terrain.loot_spots():
            self.loot_spots[bid] = (table, kind, pts)
            x = sum(q[0] for q in pts) / len(pts); y = sum(q[1] for q in pts) / len(pts)
            self.spot_grid.setdefault((int(x // LOOT_CELL), int(y // LOOT_CELL)), []).append((bid, x, y))

    # ---- grid of things on the ground ---------------------------------------
    def _loot_cell(self, l):
        return (int(l['x'] // LOOT_CELL), int(l['y'] // LOOT_CELL))

    def _loot_add(self, item, n, x, y, spot=None, mag=0):
        lid = 'l' + secrets.token_hex(5)
        l = {'id':lid, 'item':item, 'n':int(n), 'x':round(x, 1), 'y':round(y, 1), 'spot':spot,
             'until':self.elapsed + LOOT_LIFETIME}
        if mag:
            l['mag'] = int(mag)
        self.loot[lid] = l
        self.loot_grid.setdefault(self._loot_cell(l), set()).add(lid)
        return l

    def _loot_remove(self, lid):
        l = self.loot.pop(lid, None)
        if l:
            cell = self.loot_grid.get(self._loot_cell(l))
            if cell:
                cell.discard(lid)
        return l

    def loot_near(self, x, y, r):
        out = []
        for cx in range(int((x - r) // LOOT_CELL), int((x + r) // LOOT_CELL) + 1):
            for cy in range(int((y - r) // LOOT_CELL), int((y + r) // LOOT_CELL) + 1):
                for lid in self.loot_grid.get((cx, cy), ()):
                    l = self.loot[lid]
                    if abs(l['x'] - x) < r and abs(l['y'] - y) < r:
                        out.append(l)
        return out

    @staticmethod
    def loot_view(l):
        out = {k: l[k] for k in ('id', 'item', 'n', 'x', 'y')}
        if l.get('mag'):
            out['mag'] = l['mag']
        return out

    def load_loot(self, raw):
        for lid, l in (raw.get('loot') or {}).items():
            try:
                if l['item'] in ITEMS and int(l['n']) > 0:
                    new = self._loot_add(l['item'], int(l['n']), float(l['x']), float(l['y']), l.get('spot'), int(l.get('mag', 0)))
                    new['until'] = float(l.get('until', self.elapsed + LOOT_LIFETIME))
            except (TypeError, ValueError, KeyError):
                continue
        for k, v in (raw.get('loot_restock') or {}).items():
            if k in self.loot_spots:
                try:
                    self.loot_restock[k] = float(v)
                except (TypeError, ValueError):
                    pass

    # ---- spawning ----------------------------------------------------------------
    def _roll(self, table):
        rows = LOOT_TABLES[table]
        total = sum(r[1] for r in rows); pick = self.rng.uniform(0, total)
        for item, weight, low, high in rows:
            pick -= weight
            if pick <= 0:
                return item, self.rng.randint(low, high)
        item, weight, low, high = rows[-1]
        return item, low

    def _stock_spot(self, bid):
        table, kind, pts = self.loot_spots[bid]
        self.loot_restock[bid] = self.elapsed + LOOT_RESTOCK * self.rng.uniform(.8, 1.2)
        # Many buildings stand empty: somebody has been here before you.
        if self.rng.random() < .3:
            return
        top = LOOT_PER_HOUSE.get(kind, LOOT_PER_POI_PART)
        for i in range(self.rng.randint(1, top)):
            item, n = self._roll(table)
            x, y = pts[i % len(pts)]
            mag = 0
            w = ITEMS[item].get('weapon')
            if w is not None and not WEAPONS[w].get('melee') and self.rng.random() < .35:
                mag = self.rng.randint(1, max(1, WEAPONS[w]['mag'] // 3))
            self._loot_add(item, n, x + self.rng.uniform(-8, 8), y + self.rng.uniform(-8, 8), bid, mag)

    def tick_loot(self, dt, active):
        self.loot_clock += dt
        if self.loot_clock < 2:
            return
        self.loot_clock = 0.0
        people = [p for p in active if p['hp'] > 0]
        # Things nobody touched for a long time vanish, unless somebody stands right next to them.
        for lid in [k for k, l in self.loot.items() if l['until'] <= self.elapsed]:
            l = self.loot[lid]
            if not any(abs(p['x'] - l['x']) < 400 and abs(p['y'] - l['y']) < 400 for p in people):
                self._loot_remove(lid)
        if len(self.loot) >= MAX_LOOT:
            return
        busy = {l['spot'] for l in self.loot.values() if l['spot']}
        for p in people:
            r = LOOT_RANGE
            for cx in range(int((p['x'] - r) // LOOT_CELL), int((p['x'] + r) // LOOT_CELL) + 1):
                for cy in range(int((p['y'] - r) // LOOT_CELL), int((p['y'] + r) // LOOT_CELL) + 1):
                    for bid, x, y in self.spot_grid.get((cx, cy), ()):
                        if bid in busy or self.loot_restock.get(bid, 0) > self.elapsed:
                            continue
                        # Nothing appears right under somebody's nose.
                        if any(abs(o['x'] - x) < 260 and abs(o['y'] - y) < 260 for o in people):
                            continue
                        if any(c.get('house') == bid for c in self.camps.values()):
                            continue
                        self._stock_spot(bid); busy.add(bid)

    # ---- taking things ---------------------------------------------------------------
    def guns(self, p):
        return [w for w in p['weapons'] if not WEAPONS[w].get('melee')]

    def receive(self, p, item, n, mag=0):
        """Put a found thing on the player: weapons in hand, gear on the body, the rest into the backpack.

        Returns (taken, dropped): how many were taken, and the gear item taken off in exchange (or None)."""
        spec = ITEMS[item]
        if 'weapon' in spec:
            w = spec['weapon']
            if w in p['weapons']:
                # A second copy of a gun is worth its rounds; a second knife is not worth carrying.
                if mag and not WEAPONS[w].get('melee'):
                    got = self.give_item(p, WEAPONS[w]['ammo_item'], mag)
                    return (1 if got else 0), None
                raise self.GameError('Такое оружие у тебя уже есть.')
            if not WEAPONS[w].get('melee') and len(self.guns(p)) >= MAX_GUNS:
                raise self.GameError('Больше трёх стволов не унести. Выброси лишний: инвентарь (I).')
            p['weapons'].append(w); p['weapons'].sort()
            if mag:
                p['mags'][str(w)] = p['mags'].get(str(w), 0) + mag
            if p['gear']['weapon'] == FISTS:
                p['gear']['weapon'] = w
            return 1, None
        if 'gear' in spec:
            kind, tier = spec['gear']
            old = p['gear'][kind]
            if old == tier:
                raise self.GameError('На тебе уже ' + GEAR_KINDS[kind][tier]['name'].lower() + '.')
            if kind == 'backpack' and self.slots_used(p['items']) > BACKPACKS[tier]['slots']:
                raise self.GameError('В ' + BACKPACKS[tier]['name'].lower() + ' не поместятся твои вещи.')
            p['gear'][kind] = tier
            return 1, (GEAR_ITEM[(kind, old)] if old else None)
        return self.give_item(p, item, n), None

    def pickup(self, p, lid):
        l = self.loot.get(lid)
        if not l:
            raise self.GameError('Здесь уже ничего нет.')
        if math.hypot(l['x'] - p['x'], l['y'] - p['y']) > PICK_RANGE:
            raise self.GameError('Подойди ближе.')
        got, off = self.receive(p, l['item'], l['n'], l.get('mag', 0))
        if not got:
            raise self.GameError('Рюкзак полон.')
        name = ITEMS[l['item']]['name']
        l['n'] -= got
        if l['n'] <= 0 or 'weapon' in ITEMS[l['item']] or 'gear' in ITEMS[l['item']]:
            self._loot_remove(lid)
        if off:
            self._loot_add(off, 1, p['x'] + self.rng.uniform(-14, 14), p['y'] + self.rng.uniform(6, 18))
        text = ITEMS[l['item']].get('desc', '')
        if 'gear' in ITEMS[l['item']]:
            text = 'Надето.' + (' Старое — на земле.' if off else '')
        elif 'weapon' in ITEMS[l['item']]:
            text = 'В руках: 1–' + str(len(p['weapons'])) + ' переключают оружие.' if p['gear']['weapon'] == ITEMS[l['item']]['weapon'] else 'За спиной.'
        return {'title':name + (' ×' + str(got) if got > 1 else ''), 'text':text, 'success':True, 'quiet':'weapon' not in ITEMS[l['item']] and 'gear' not in ITEMS[l['item']]}

    def drop_thing(self, p, item, count=1):
        """Put something on the ground: 'w:<index>' for a weapon, 'gear:<kind>' for worn gear, else an item."""
        x, y = p['x'] + self.rng.uniform(-16, 16), p['y'] + self.rng.uniform(8, 22)
        if isinstance(item, str) and item.startswith('w:'):
            try:
                w = int(item[2:])
            except ValueError:
                raise self.GameError('Такого оружия нет.')
            if w == FISTS or w not in p['weapons']:
                raise self.GameError('Такого оружия у тебя нет.')
            p['weapons'].remove(w)
            mag = p['mags'].pop(str(w), 0)
            if p['gear']['weapon'] == w:
                p['gear']['weapon'] = FISTS
            self._loot_add(WEAPON_ITEM[w], 1, x, y, None, mag)
            return {'title':'Выброшено: ' + WEAPONS[w]['name'], 'success':False, 'quiet':True}
        if isinstance(item, str) and item.startswith('gear:'):
            kind = item[5:]
            if kind not in GEAR_KINDS or not p['gear'][kind]:
                raise self.GameError('Снимать нечего.')
            if kind == 'backpack' and self.slots_used(p['items']) > BACKPACKS[0]['slots']:
                raise self.GameError('Сначала выложи вещи: в карманы столько не влезет.')
            self._loot_add(GEAR_ITEM[(kind, p['gear'][kind])], 1, x, y)
            p['gear'][kind] = 0
            return {'title':'Снято', 'success':False, 'quiet':True}
        if item not in ITEMS or p['items'].get(item, 0) < 1:
            raise self.GameError('Этого нет в рюкзаке.')
        try:
            n = max(1, min(int(count), p['items'][item]))
        except (TypeError, ValueError):
            n = 1
        self.take_items(p, {item:n})
        # Same things dropped on one spot lie in one heap.
        heap = next((l for l in self.loot_near(p['x'], p['y'], 40) if l['item'] == item and not l['spot']), None)
        if heap:
            heap['n'] += n; heap['until'] = self.elapsed + LOOT_LIFETIME
        else:
            self._loot_add(item, n, x, y)
        return {'title':'Выброшено: ' + ITEMS[item]['name'] + ' ×' + str(n), 'success':False, 'quiet':True}

    def loot_body(self, p, bid, item=None):
        """Take one thing from a body, or everything that fits when no item is named."""
        b = self.bodies.get(str(bid))
        if not b:
            raise self.GameError('Здесь уже ничего нет.')
        if math.hypot(b['x'] - p['x'], b['y'] - p['y']) > 90:
            raise self.GameError('Подойди ближе.')
        keys = [item] if item else list(b['items'])
        if item and b['items'].get(item, 0) < 1:
            raise self.GameError('Этого уже нет.')
        taken = {}; skipped = False
        for k in keys:
            n = b['items'].get(k, 0)
            if n <= 0:
                continue
            spec = ITEMS[k]
            mag = 0
            if 'weapon' in spec:
                mag = b.get('mags', {}).pop(str(spec['weapon']), 0)
            try:
                got, off = self.receive(p, k, n, mag)
            except self.GameError:
                if item:
                    raise
                if mag:
                    b.setdefault('mags', {})[str(spec['weapon'])] = mag
                skipped = True
                continue
            if off:
                b['items'][off] = b['items'].get(off, 0) + 1
            if got:
                taken[k] = taken.get(k, 0) + got
                b['items'][k] -= got
                if b['items'][k] <= 0:
                    del b['items'][k]
            if got < n:
                skipped = True
        if not b['items'] and not b.get('npc'):
            del self.bodies[b['id']]
        if not taken:
            raise self.GameError('Ничего не взято: нет места.' if skipped else 'Пусто.')
        return {'title':'Забрано: ' + b['name'], 'text':self.items_text(taken) + ('. Остальное не влезло.' if skipped else '.'), 'success':True}
