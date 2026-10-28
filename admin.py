"""The host's admin panel: spawning anything, teleporting, healing, weather and time.

Mixed into server.World. The HTTP handler accepts /api/admin only from the host computer itself (127.0.0.1),
so players on other computers can never reach these commands.
"""
import math
from world_data import ITEMS, NPC_TYPES, CARS, WEATHER, WEAPONS, WORLD_SIZE, FISTS

ADMIN_NPCS = ('infected', 'infected_soldier', 'wolf', 'bear', 'boar', 'elk')


class AdminMixin:
    def _admin_target(self, me, pid):
        if not pid or pid == me['id']:
            return me
        p = next((q for q in self.players.values() if q['id'] == pid), None)
        if not p:
            raise self.GameError('Игрок не найден.')
        return p

    def _place(self, p, x, y):
        """Move a player, out of any car, to the nearest free spot around (x, y)."""
        if p['vehicle']:
            self.leave_car(p, force=True)
        x = min(max(x, 40), WORLD_SIZE[0] - 40); y = min(max(y, 40), WORLD_SIZE[1] - 40)
        spot = (x, y) if self.terrain.free_spot(x, y, 14) else self._free_near(x, y, 20, 200) or (x, y)
        p['x'], p['y'] = spot

    def admin(self, token, data):
        me = self.player(token)
        op = data.get('op')
        n = int(min(max(self.finite_num(data.get('n', 1)), 1), 50))
        if op == 'teleport':
            p = self._admin_target(me, data.get('target'))
            self._place(p, self.finite_num(data.get('x')), self.finite_num(data.get('y')))
            return {'title':'Телепорт', 'text':p['name'] + ' перенесён.'}
        if op == 'goto':
            p = self._admin_target(me, data.get('target'))
            self._place(me, p['x'] + 40, p['y'])
            return {'title':'Телепорт', 'text':'Ты рядом с ' + p['name'] + '.'}
        if op == 'bring':
            p = self._admin_target(me, data.get('target'))
            self._place(p, me['x'] + 40, me['y'])
            return {'title':'Телепорт', 'text':p['name'] + ' рядом с тобой.'}
        if op == 'give':
            item = data.get('item')
            if item not in ITEMS:
                raise self.GameError('Такой вещи нет.')
            p = self._admin_target(me, data.get('target'))
            weapon = ITEMS[item].get('weapon')
            # A gun from the admin comes loaded.
            mag = WEAPONS[weapon]['mag'] if weapon is not None and not WEAPONS[weapon].get('melee') else 0
            try:
                got, off = self.receive(p, item, n, mag)
            except self.GameError:
                got, off = 0, None
            if off:
                self._loot_add(off, 1, p['x'], p['y'] + 16)
            if got < n:
                # What does not fit lies at the feet.
                self._loot_add(item, n - got if 'weapon' not in ITEMS[item] and 'gear' not in ITEMS[item] else 1, p['x'] + 20, p['y'] + 10)
            return {'title':'Выдано: ' + ITEMS[item]['name'] + (' ×' + str(n) if n > 1 else ''), 'text':p['name'] + ('' if got >= n else ' · не влезло — на земле')}
        if op == 'spawn_loot':
            item = data.get('item')
            if item not in ITEMS:
                raise self.GameError('Такой вещи нет.')
            self._loot_add(item, n, me['x'] + self.rng.uniform(-30, 30), me['y'] + 40)
            return {'title':'На земле: ' + ITEMS[item]['name'] + (' ×' + str(n) if n > 1 else '')}
        if op == 'spawn_npc':
            kind = data.get('kind')
            if kind not in ADMIN_NPCS:
                raise self.GameError('Такого существа нет.')
            a0 = math.atan2(me['aim'][1], me['aim'][0])
            for i in range(n):
                a = a0 + (i - n / 2) * .25
                spot = self._free_near(me['x'] + math.cos(a) * 300, me['y'] + math.sin(a) * 300, 0, 80)
                if spot:
                    self.spawn_npc(kind, spot[0], spot[1], mode='wander' if kind not in ('infected', 'infected_soldier') else 'idle')
            return {'title':'Появились: ' + NPC_TYPES[kind]['name'] + (' ×' + str(n) if n > 1 else '')}
        if op == 'spawn_car':
            model = int(self.finite_num(data.get('model')))
            if not 0 <= model < len(CARS):
                raise self.GameError('Такой машины нет.')
            car = self.new_car(me['x'] + 120, me['y'], 0.0, model)
            car.update(fuel=float(CARS[model]['tank']), hp=100.0)
            spot = self._car_spot(CARS[model], car, 0, 400)
            if not spot:
                del self.cars[car['id']]
                raise self.GameError('Рядом нет места для машины.')
            car['x'], car['y'] = spot
            return {'title':'Машина: ' + CARS[model]['name'], 'text':'Полный бак.'}
        if op == 'heal':
            p = self._admin_target(me, data.get('target'))
            if p['hp'] <= 0:
                raise self.GameError(p['name'] + ' мёртв.')
            p.update(hp=100.0, food=100.0, water=100.0, warmth=100.0, stamina=100.0, bleeding=False, sick=0.0)
            return {'title':'Вылечен', 'text':p['name']}
        if op == 'kill':
            p = self._admin_target(me, data.get('target'))
            if p is me:
                p['god'] = False
            if p['hp'] > 0:
                p['hit_by'] = {'name':'ведущий', 'kind':'admin', 'at':self.elapsed}
                self._damage(p, 1e6)
            return {'title':'Убит', 'text':p['name']}
        if op == 'god':
            me['god'] = not me.get('god')
            return {'title':'Бессмертие ' + ('включено' if me['god'] else 'выключено')}
        if op == 'clear':
            r = 2000
            count = 0
            for npc in list(self.npcs.values()):
                if npc['hp'] > 0 and abs(npc['x'] - me['x']) < r and abs(npc['y'] - me['y']) < r:
                    self.hurt(npc, 1e6, None); count += 1
            return {'title':'Убрано существ: ' + str(count)}
        if op == 'restock':
            r = 1800
            for bid, x, y in [s for cell in self.spot_grid.values() for s in cell]:
                if abs(x - me['x']) < r and abs(y - me['y']) < r:
                    self.loot_restock.pop(bid, None)
            for lid in [l['id'] for l in self.loot_near(me['x'], me['y'], r) if l['spot']]:
                self._loot_remove(lid)
            self.loot_clock = 99
            return {'title':'Лут обновится', 'text':'Дома вокруг наполнятся заново.'}
        if op == 'weather':
            kind = data.get('kind')
            if kind not in WEATHER:
                raise self.GameError('Такой погоды нет.')
            self.weather = {'kind':kind, 'until':self.elapsed + 600}
            return {'title':'Погода: ' + WEATHER[kind]}
        if op == 'time':
            hour = self.finite_num(data.get('hour')) % 24
            now = (8 + self.elapsed * 1.4 / 60) % 24
            # Time only goes forward: the clock is wound to the next such hour.
            self.elapsed += ((hour - now) % 24) * 60 / 1.4
            return {'title':'Время: ' + '%02d:00' % int(hour)}
        raise self.GameError('Неизвестная команда.')

    @staticmethod
    def finite_num(v, default=0.0):
        try:
            f = float(v)
            return f if math.isfinite(f) else default
        except (TypeError, ValueError):
            return default

    def admin_info(self):
        return {'npcs':list(ADMIN_NPCS), 'fists':FISTS}
