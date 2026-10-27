"""Camps, crafting and bodies of the fallen.

Mixed into server.World. Everything here runs on the host, inside the world lock.

A camp belongs to one side (clan mates share it). It is founded on open ground, where a square fence
can be built around it, or inside an abandoned house, whose walls become the fence. Parts are built
from materials in the backpack; walls and the gate can be shot or broken, and once the fence is breached
an outsider may empty the stash.
"""
import math
import secrets
from world_data import (ROAD_HALF, ITEMS, RECIPES, CAMP_PARTS, CAMP_HALF, CAMP_STASH_SLOTS, HOUSE_WALL_HP, BODY_TIME,
                        NPC_TYPES, WEAPONS, GEAR_ITEM)


class CampError(Exception):
    pass


# Dead people and animals lie where they fell for five minutes; the oldest go first past the cap.
CORPSE_TIME = 300
MAX_CORPSES = 90


class CampMixin:
    # ---- backpack accounting: materials stack, food and medicine take a slot each ----
    @staticmethod
    def slots_used(items):
        return sum(-(-n // ITEMS[k].get('stack', 1)) for k, n in items.items() if n > 0 and k in ITEMS)

    def room_for(self, p, item, count):
        """How many of `item` still fit into the backpack."""
        stack = ITEMS[item].get('stack', 1); have = p['items'].get(item, 0)
        free_slots = self.slots(p) - self.slots_used(p['items'])
        spare = (-have) % stack if have else 0
        return max(0, min(count, spare + max(0, free_slots) * stack))

    def give_item(self, p, item, count=1):
        n = self.room_for(p, item, count)
        if n:
            p['items'][item] = p['items'].get(item, 0) + n
        return n

    def take_items(self, p, needs):
        if any(p['items'].get(k, 0) < v for k, v in needs.items()):
            missing = [ITEMS[k]['name'].lower() + ' ' + str(v - p['items'].get(k, 0)) for k, v in needs.items() if p['items'].get(k, 0) < v]
            raise self.GameError('Не хватает: ' + ', '.join(missing) + '.')
        for k, v in needs.items():
            p['items'][k] -= v
            if not p['items'][k]:
                del p['items'][k]

    def items_text(self, items):
        return ', '.join(ITEMS[k]['name'] + ' ×' + str(v) for k, v in items.items() if v) or 'ничего'

    # ---- camps ----
    def camp_of(self, sid):
        cid = self.sides.get(sid, {}).get('camp')
        return self.camps.get(cid) if cid else None

    def camp_allowed(self, camp, f):
        return camp['owner'] == f or self.allied(camp['owner'], f)

    def _part_spots(self, camp):
        """Where the furniture stands: a ring inside the fence, or the corners of a house."""
        if camp.get('house'):
            h = self.terrain.houses[camp['house']]; ax, ay = h['w'] / 2 - 13, h['h'] / 2 - 13
            spots = [(.55, -.55), (-.55, .55), (.55, .55), (0, 0)]
            return {k: (camp['x'] + sx * ax, camp['y'] + sy * ay) for k, (sx, sy) in zip(('stash', 'bench', 'collector', 'fire'), spots)}
        r = CAMP_HALF * .5
        return {'fire': (camp['x'], camp['y']), 'stash': (camp['x'] + r, camp['y'] - r),
                'bench': (camp['x'] - r, camp['y'] + r * .9), 'collector': (camp['x'] + r, camp['y'] + r * .9)}

    @staticmethod
    def fence_slots(x, y):
        """Eight fence sections and a gate in the middle of the south side."""
        a = CAMP_HALF; t = 10; out = []
        out.append(('n1', x - a / 2, y - a, a, t)); out.append(('n2', x + a / 2, y - a, a, t))
        out.append(('w1', x - a, y - a / 2, t, a)); out.append(('w2', x - a, y + a / 2, t, a))
        out.append(('e1', x + a, y - a / 2, t, a)); out.append(('e2', x + a, y + a / 2, t, a))
        out.append(('s1', x - a * .6, y + a, a * .8, t)); out.append(('s2', x + a * .6, y + a, a * .8, t))
        out.append(('gate', x, y + a, a * .4, t))
        return [{'slot':s, 'x':cx, 'y':cy, 'w':w, 'h':h} for s, cx, cy, w, h in out]

    def found_camp(self, p):
        f = p['faction']
        if self.camp_of(f):
            raise self.GameError('У тебя уже есть лагерь. Брось его, чтобы основать новый.')
        if p['vehicle']:
            raise self.GameError('Выйди из машины.')
        x, y = p['x'], p['y']
        house = self.terrain.house_at(x, y, -6)
        if house:
            if any(c.get('house') == house['id'] for c in self.camps.values()):
                raise self.GameError('Этот дом уже занят.')
            cx, cy = house['x'], house['y']
        else:
            if self.terrain.in_town(x, y, 60) and not self.terrain.house_at(x, y, 40) and self.terrain.in_core(x, y):
                raise self.GameError('На площади лагерь не поставить. Займи пустой дом или отойди.')
            for fx, fy in [(x + dx, y + dy) for dx in (-CAMP_HALF, 0, CAMP_HALF) for dy in (-CAMP_HALF, 0, CAMP_HALF)]:
                if self.terrain.solid(fx, fy, 8) or self.terrain.water(fx, fy, 6) or self.terrain.on_road(fx, fy, ROAD_HALF + 10) or self.terrain.on_street(fx, fy, 6):
                    raise self.GameError('Здесь тесно для лагеря: нужна ровная площадка 200 × 200 без дорог и воды. Или зайди в пустой дом.')
            cx, cy = x, y
        if any(math.hypot(c['x'] - cx, c['y'] - cy) < 450 for c in self.camps.values()):
            raise self.GameError('Рядом чужой лагерь.')
        cid = 'c' + secrets.token_hex(4)
        camp = {'id':cid, 'owner':f, 'x':round(cx, 1), 'y':round(cy, 1), 'house':house['id'] if house else None,
                'parts':{}, 'fence':{}, 'stash':{'items':{}}, 'water_at':self.elapsed}
        if house:
            # The house's own walls are the fence: sturdy, already standing. The doorway needs a door.
            for i, rect in enumerate(house['walls']):
                camp['fence']['w%d' % i] = {'hp':HOUSE_WALL_HP, 'max':HOUSE_WALL_HP, 'rect':rect, 'house':True}
        self.camps[cid] = camp; self.sides[f]['camp'] = cid
        self.dirty = True
        return camp

    def abandon_camp(self, camp, silent=False):
        for part in camp['fence'].values():
            if not part.get('house') and part.get('rect') and part['hp'] > 0:
                self.terrain.remove_rect(part['rect'])
            elif part.get('house') and part['hp'] <= 0:
                # The house stands again for the next settler.
                self.terrain.add_rect(part['rect'])
        if camp.get('gate_rect'):
            camp['gate_rect'] = None
        if camp['stash']['items']:
            self.drop_pile(camp['x'], camp['y'], dict(camp['stash']['items']), 'Брошенный ящик')
        side = self.sides.get(camp['owner'])
        if side and side.get('camp') == camp['id']:
            side['camp'] = None
        self.camps.pop(camp['id'], None)

    def camp_breached(self, camp):
        """Outsiders get in when the fence is unfinished or broken somewhere."""
        if camp.get('house'):
            gate = camp['fence'].get('gate')
            return not gate or gate['hp'] <= 0 or any(w['hp'] <= 0 for w in camp['fence'].values())
        slots = [s['slot'] for s in self.fence_slots(camp['x'], camp['y'])]
        return any(s not in camp['fence'] or camp['fence'][s]['hp'] <= 0 for s in slots)

    def build_part(self, p, camp, kind, slot=None):
        if kind not in CAMP_PARTS:
            raise self.GameError('Такой постройки нет.')
        spec = CAMP_PARTS[kind]
        if kind in ('wall', 'gate'):
            if camp.get('house'):
                if kind == 'wall':
                    # A breached house wall is patched up with planks and nails.
                    broken = [s for s, v in camp['fence'].items() if v.get('house') and v['hp'] <= 0]
                    if not broken:
                        raise self.GameError('Стены дома целы.')
                    piece = camp['fence'][broken[0]]
                    self.take_items(p, spec['needs'])
                    piece['hp'] = piece['max']
                    self.terrain.add_rect(piece['rect'])
                    return 'Стена дома'
                slot = 'gate'
                h = self.terrain.houses[camp['house']]; d = h['door']
                gx, gy = {'n':(h['x'], h['y'] - h['h'] / 2 + 4), 's':(h['x'], h['y'] + h['h'] / 2 - 4),
                          'w':(h['x'] - h['w'] / 2 + 4, h['y']), 'e':(h['x'] + h['w'] / 2 - 4, h['y'])}[d]
                rect = {'x':gx, 'y':gy, 'w':30 if d in 'ns' else 8, 'h':8 if d in 'ns' else 30}
            else:
                slots = {s['slot']: s for s in self.fence_slots(camp['x'], camp['y'])}
                if kind == 'gate':
                    slot = 'gate'
                elif slot not in slots or slot == 'gate':
                    free = [s for s in slots if s != 'gate' and (s not in camp['fence'] or camp['fence'][s]['hp'] <= 0)]
                    if not free:
                        raise self.GameError('Ограда уже закрыта.')
                    slot = free[0]
                rect = dict((k, slots[slot][k]) for k in ('x', 'y', 'w', 'h'))
            old = camp['fence'].get(slot)
            if old and old['hp'] > 0:
                raise self.GameError('Здесь уже стоит ' + spec['name'].lower() + '.')
            if any(abs(o['x'] - rect['x']) < rect['w'] / 2 + 12 and abs(o['y'] - rect['y']) < rect['h'] / 2 + 12
                   for o in self.active_players() if o['hp'] > 0 and not o['vehicle']):
                raise self.GameError('Отойди с места, где ставишь ' + spec['name'].lower() + '.')
            self.take_items(p, spec['needs'])
            rect['camp'] = camp['id']
            if kind == 'gate':
                rect['gate'] = True
            part = {'kind':kind, 'hp':spec['hp'], 'max':spec['hp'], 'rect':rect}
            if old and old.get('house'):
                part.update(hp=HOUSE_WALL_HP, max=HOUSE_WALL_HP, house=True)
            camp['fence'][slot] = part
            if kind == 'wall' or not rect.get('gate'):
                self.terrain.add_rect(rect)
            else:
                self.terrain.add_rect(rect)          # gates are solid in the grid; allies pass them in blocked_for
            return spec.get('house_name', spec['name']) if camp.get('house') else spec['name']
        if kind in camp['parts'] and camp['parts'][kind]['hp'] > 0:
            raise self.GameError(spec['name'] + ' уже есть.')
        self.take_items(p, spec['needs'])
        x, y = self._part_spots(camp)[kind]
        camp['parts'][kind] = {'kind':kind, 'hp':spec['hp'], 'max':spec['hp'], 'x':round(x, 1), 'y':round(y, 1)}
        return spec.get('house_name', spec['name']) if camp.get('house') else spec['name']

    def gate_open_for(self, rect, faction):
        camp = self.camps.get(rect.get('camp'))
        return bool(rect.get('gate') and camp and faction and self.camp_allowed(camp, faction))

    def damage_camp_piece(self, camp, slot, amount, attacker=None):
        piece = camp['fence'].get(slot) if slot in camp['fence'] else camp['parts'].get(slot)
        if not piece or piece['hp'] <= 0:
            return False
        piece['hp'] = max(0.0, piece['hp'] - amount)
        if piece['hp'] > 0:
            return False
        if piece.get('rect'):
            self.terrain.remove_rect(piece['rect'])
        name = CAMP_PARTS.get(piece.get('kind'), {}).get('name', 'Стена')
        self.effects.append({'id':secrets.token_hex(4), 'kind':'boom', 'x':piece.get('x', piece.get('rect', {}).get('x', camp['x'])),
                             'y':piece.get('y', piece.get('rect', {}).get('y', camp['y'])), 'ex':camp['x'], 'ey':camp['y'],
                             'until':self.elapsed + 1.0, 'faction':None})
        self._notice('Лагерь атакуют', name + ' разрушен' + ('а' if name.endswith('а') else '') + '.', faction=camp['owner'], tone='error')
        if slot == 'stash':
            # A smashed crate spills its contents on the ground.
            self.drop_pile(camp['x'], camp['y'], dict(camp['stash']['items']), 'Разбитый ящик')
            camp['stash'] = {'items':{}}
        return True

    def camp_targets(self):
        """Shootable pieces: fence sections, gates and furniture."""
        for camp in self.camps.values():
            for slot, piece in camp['fence'].items():
                if piece['hp'] > 0:
                    yield camp, slot, piece['rect']
            for slot, piece in camp['parts'].items():
                if piece['hp'] > 0:
                    yield camp, slot, {'x':piece['x'], 'y':piece['y'], 'w':22, 'h':22}

    def tick_camps(self, dt):
        for camp in self.camps.values():
            col = camp['parts'].get('collector'); crate = camp['parts'].get('stash')
            if col and col['hp'] > 0 and crate and crate['hp'] > 0 and self.elapsed - camp.get('water_at', 0) >= 120:
                camp['water_at'] = self.elapsed
                stash = camp['stash']['items']
                if stash.get('water', 0) < 3 and self.slots_used(stash) < CAMP_STASH_SLOTS:
                    stash['water'] = stash.get('water', 0) + 1

    def near_camp_part(self, p, kind, r=90):
        """An allowed camp part within reach (own or clan), or None."""
        for camp in self.camps.values():
            part = camp['parts'].get(kind)
            if part and part['hp'] > 0 and math.hypot(part['x'] - p['x'], part['y'] - p['y']) < r and self.camp_allowed(camp, p['faction']):
                return camp
        return None

    # ---- crafting ----
    def craft(self, p, rid):
        rec = next((r for r in RECIPES if r['id'] == rid), None)
        if not rec:
            raise self.GameError('Такого рецепта нет.')
        at = rec['at']
        if at == 'fire' and not self.near_camp_part(p, 'fire', 110):
            raise self.GameError('Нужен огонь: костёр или печка в лагере.')
        if at == 'bench' and not self.near_camp_part(p, 'bench', 90):
            raise self.GameError('Это делают на верстаке в лагере.')
        if 'weapon_from' in rec:
            src, dst = rec['weapon_from']
            if src not in p['weapons']:
                raise self.GameError('Нужно ' + WEAPONS[src]['name'].lower() + '.')
            if dst in p['weapons']:
                raise self.GameError('У тебя уже есть ' + WEAPONS[dst]['name'].lower() + '.')
            self.take_items(p, rec.get('needs', {}))
            p['weapons'].remove(src); p['weapons'].append(dst); p['weapons'].sort()
            # The rounds left in the long gun go back into the backpack.
            left = p['mags'].pop(str(src), 0)
            if left:
                self.give_item(p, WEAPONS[src]['ammo_item'], left)
            if p['gear']['weapon'] == src:
                p['gear']['weapon'] = dst
            return {'title':rec['name'], 'text':'Ствол короче, дробь шире: в упор страшнее.', 'success':True}
        if 'gear' in rec:
            kind, tier = rec['gear']
            if p['gear'][kind] >= tier:
                raise self.GameError('У тебя уже есть это или лучше.')
        if 'makes' in rec:
            after = dict(p['items'])
            for k, v in rec.get('needs', {}).items():
                after[k] = after.get(k, 0) - v
            for k, v in rec['makes'].items():
                after[k] = after.get(k, 0) + v
            used = self.slots_used({k: v for k, v in after.items() if v > 0})
            if used > self.slots(p) and used > self.slots_used(p['items']):
                raise self.GameError('В рюкзаке не хватит места.')
        self.take_items(p, rec.get('needs', {}))
        if 'gear' in rec:
            kind, tier = rec['gear']
            old = p['gear'][kind]
            p['gear'][kind] = tier
            if old:
                self._loot_add(GEAR_ITEM[(kind, old)], 1, p['x'], p['y'] + 16)
            return {'title':rec['name'], 'text':'Готово и надето.', 'success':True}
        for k, v in rec['makes'].items():
            p['items'][k] = p['items'].get(k, 0) + v
        return {'title':'Сделано: ' + rec['name'], 'text':self.items_text(rec['makes']), 'success':True}

    # ---- bodies and dropped piles ----
    def drop_pile(self, x, y, items, name):
        if not items:
            return None
        bid = 'b' + secrets.token_hex(4)
        self.bodies[bid] = {'id':bid, 'x':round(x, 1), 'y':round(y, 1), 'items':items, 'name':name, 'until':self.elapsed + BODY_TIME}
        return bid

    def drop_corpse(self, npc):
        """A dead infected or animal stays where it fell; what it carried can be taken (E)."""
        bid = 'n' + npc['id']
        self.bodies[bid] = {'id':bid, 'x':round(npc['x'], 1), 'y':round(npc['y'], 1), 'items':dict(npc.get('loot') or {}),
                            'name':NPC_TYPES[npc['type']]['name'], 'until':self.elapsed + CORPSE_TIME,
                            'npc':{'type':npc['type'], 'look':npc.get('look'), 'angle':round(npc.get('angle', 0.0), 2), 'faction':npc['faction']}}
        corpses = sorted((b for b in self.bodies.values() if b.get('npc')), key=lambda b: b['until'])
        for b in corpses[:max(0, len(corpses) - MAX_CORPSES)]:
            del self.bodies[b['id']]
        return bid

    def tick_bodies(self):
        for bid in [k for k, b in self.bodies.items() if b['until'] <= self.elapsed]:
            del self.bodies[bid]

    # ---- stash ----
    def stash_move(self, p, camp, item, count, put):
        crate = camp['parts'].get('stash')
        if not crate or crate['hp'] <= 0:
            raise self.GameError('Ящика нет: построй его (L).')
        if not self.camp_allowed(camp, p['faction']) and not self.camp_breached(camp):
            raise self.GameError('Ящик за оградой. Чтобы добраться, пробей стену или ворота.')
        stash = camp['stash']['items']
        if item not in ITEMS or 'weapon' in ITEMS[item] or 'gear' in ITEMS[item]:
            raise self.GameError('Такой вещи нет.')
        if put:
            n = min(int(count), p['items'].get(item, 0))
            room = ITEMS[item].get('stack', 1) * (CAMP_STASH_SLOTS - self.slots_used(stash)) + ((-stash.get(item, 0)) % ITEMS[item].get('stack', 1) if stash.get(item) else 0)
            n = max(0, min(n, room))
            if n:
                self.take_items(p, {item:n}); stash[item] = stash.get(item, 0) + n
        else:
            n = self.give_item(p, item, min(int(count), stash.get(item, 0)))
            if n:
                stash[item] -= n
                if not stash[item]:
                    del stash[item]
        return n
