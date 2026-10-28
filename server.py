#!/usr/bin/env python3
"""After Silence: authoritative LAN simulation. No third-party dependencies.

Since 0.8 the rules follow DayZ: a compact coastal region, infected in every settlement, loot lying in
buildings, cars that belong to nobody, and a fresh start on the shore after every death.
"""
import argparse
import copy
import json
import math
import os
import random
import secrets
import signal
import socket
import threading
import time
import traceback
import webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from world_data import (ROAD_HALF, VERSION, WORLD_SIZE, TOWNS, REGIONS, MAX_PLAYERS, SIDE_COLORS, NPC_TYPES, BODY_TIME,
                        CAMP_PARTS, WEAPONS, ARMOR, ITEMS, CLOTHES, BACKPACKS, CARS, WEATHER, SWAP_TIME, FISTS, START_ITEMS,
                        RESPAWN_TIME, WEAPON_ITEM, GEAR_ITEM, config)
from terrain import Terrain, resource_nodes, RECT_CELL, FLAT
from npc import NpcMixin
from vehicles import VehicleMixin
from camps import CampMixin
from loot import LootMixin
from admin import AdminMixin

ROOT = Path(__file__).resolve().parent
SAVE_VERSION = 3
DISCOVERY_PORT = 8766
STAT_KEYS = ('infected','animals','players','loot','harvest')
CLAN_SIZE = 6
TRADE_RANGE = 260
MAX_HP = 100.0
NODE_RESPAWN = 600

def clamp(v, low, high):
    return max(low, min(high, v))

def dist(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])

def finite(v, default=0):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default

class GameError(Exception):
    pass

class World(NpcMixin, VehicleMixin, CampMixin, LootMixin, AdminMixin):
    def __init__(self, save_path=None, rng=None):
        self.lock = threading.RLock()
        self.rng = rng or random.SystemRandom()
        self.save_path = Path(save_path) if save_path else None
        self.players = {}
        self.elapsed = 0.0
        self.save_clock = 0.0
        self.creature_clock = 0.0
        self.harvested = {}
        self.log = []
        self.seq = 0
        self.effects = []
        self.noises = []
        # A side is one player; clans group sides. Players live in camps they build themselves.
        self.sides = {}
        self.npcs = {}
        self.weather = {'kind':'clear','until':300.0}
        self.clans = {}
        self.offers = {}
        self.camps = {}
        self.bodies = {}
        self.settings = {}
        self.room_code = None
        self.dirty = False
        self.load_warning = None
        self.terrain = Terrain()
        self.towns = {t[0]: {'id':t[0],'name':t[1],'x':t[2],'y':t[3],'region':t[4],'kind':t[5],
                             'r':self.terrain.towns[t[0]]['r'],'h':self.terrain.towns[t[0]]['h']} for t in TOWNS}
        for poi in self.terrain.pois.values():
            for part in poi['parts']:
                if part['sprite'] not in FLAT:self.terrain.add_rect(part)
        self.nodes = resource_nodes(self.terrain)
        self.init_loot()
        self.init_infected()
        self.cars = {}
        if self.save_path and self.save_path.exists():
            self.load()
        self.fill_cars()

    # ---- sides ----------------------------------------------------------
    def add_side(self, sid, name, color):
        self.sides[sid] = {'id':sid,'name':name,'color':color,'camp':None,'clan':None}

    def release_side(self, sid):
        """A player who left for good: the camp falls apart, the clan forgets them."""
        camp = self.camp_of(sid)
        if camp:
            self.abandon_camp(camp)
        for c in self.clans.values():
            if sid in c['members']: c['members'].remove(sid)
            if sid in c['invites']: c['invites'].remove(sid)
        for cid, c in list(self.clans.items()):
            if not c['members']:
                del self.clans[cid]
            elif c['leader'] == sid:
                c['leader'] = c['members'][0]
        self.offers = {k: o for k, o in self.offers.items() if sid not in (o['from_side'], o['to_side'])}
        self.sides.pop(sid, None)

    def side_name(self, sid):
        return self.sides[sid]['name'] if sid in self.sides else 'Незнакомец'

    GameError = None   # set below, used by the mixins

    def allied(self, a, b):
        ca = self.sides.get(a, {}).get('clan'); cb = self.sides.get(b, {}).get('clan')
        return a == b or (ca is not None and ca == cb)

    def truce_between(self, a, b):
        """Clan mates do not hurt each other; everybody else is fair game."""
        return a != b and self.allied(a, b)

    _dist = staticmethod(dist)

    def _notice(self, title, text='', faction=None, player=None, tone='info', skip=None):
        self.seq += 1
        self.log.append({'id':self.seq,'title':title,'text':text,'faction':faction,'player':player,'tone':tone,'skip':skip})
        self.log=self.log[-60:]

    def _public_player(self, p):
        out={k:p[k] for k in ('id','name','faction','x','y','angle','hp','stamina','vehicle','dead_until','gear')}
        # What the character is doing, for animation on every client.
        out['act']=p.get('act');out['reload']=p.get('reload_until',0);out['mag']=self._mag(p)
        clan=self.clans.get(self.sides.get(p['faction'],{}).get('clan'))
        out['tag']=clan['tag'] if clan else ''
        out['car']=p.get('car');out['seat']=p.get('seat');out['max_hp']=MAX_HP
        out['shot']=p.get('shot',-10);out['busy']=p.get('busy',-10);out['moving']=bool(p['input'][0] or p['input'][1])
        out['sprint']=bool(p['input'][2])
        return out

    def _free_color(self,color,sid=None):
        used={s['color'] for k,s in self.sides.items() if k!=sid}
        if color in SIDE_COLORS and color not in used:return color
        return next((c for c in SIDE_COLORS if c not in used),SIDE_COLORS[len(self.sides)%len(SIDE_COLORS)])

    def join(self, name, faction=None, token=None, color=None):
        """Every player is a side of their own. The faction argument is ignored (kept for old clients)."""
        if token in self.players:
            p=self.players[token]
            p['last_seen']=time.monotonic()
            p['name']=str(name).strip()[:20] or p['name']
            side=self.sides[p['faction']];side['name']=p['name']
            if color in SIDE_COLORS:side['color']=self._free_color(color,p['faction'])
            return token
        name=str(name).strip()[:20] or 'Путник'
        now=time.monotonic()
        if len(self.players)>=MAX_PLAYERS:
            stale=[(t,p) for t,p in self.players.items() if now-p['last_seen']>60]
            if not stale:
                raise GameError('В комнате уже '+str(MAX_PLAYERS)+' игроков. Дождись свободного места.')
            self._leave(stale[0][0])
        color=self._free_color(color)
        token=secrets.token_urlsafe(32);pid=secrets.token_hex(6);sid='p_'+pid
        self.add_side(sid,name,color)
        p={'id':pid,'name':name,'faction':sid,'x':0.0,'y':0.0,'angle':-math.pi/2,'vehicle':False,'car':None,'seat':None,
           'last_seen':now,'last_input':now,'input':[0,0,False],'aim':[0,-1],'paused':False,'last_action':{},'receipts':OrderedDict(),
           'dead_until':0.0}
        self._fresh_character(p)
        self.players[token]=p
        self._notice(name+' присоединился','')
        self.dirty=True
        return token

    def _leave(self,token):
        p=self.players.pop(token)
        if p['vehicle']:self.leave_car(p,force=True)
        self.release_side(p['faction'])

    def _fresh_character(self,p):
        """A new life: rags, an apple and a bandage on a random stretch of the shore."""
        p.update(hp=MAX_HP,stamina=100.0,food=60.0,water=60.0,warmth=80.0,bleeding=False,sick=0.0,warned=[],
                 gear={'weapon':FISTS,'armor':0,'clothes':0,'backpack':0},weapons=[FISTS],mags={},items=dict(START_ITEMS),
                 stats={k:0 for k in STAT_KEYS},born=self.elapsed,reload_until=0.0,vehicle=False,car=None,seat=None,dead_until=0.0)
        p.pop('act',None)
        x,y=self._spawn_point(p)
        p['x'],p['y']=x,y;p['angle']=-math.pi/2
        near=min(self.towns.values(),key=lambda t:dist(t,p))
        self._notice('Ты очнулся на берегу','Рядом '+near['name']+'. Ищи еду, воду и оружие в домах. Заражённые слышат шум и видят тех, кто бежит.',player=p['id'])

    def _spawn_point(self,p):
        """A random spot on the shore, away from other players and the infected."""
        others=[o for o in self.players.values() if o is not p and o['hp']>0]
        coast=self.terrain.coast
        for attempt in range(60):
            x,y=self.rng.choice(coast)
            x+=self.rng.uniform(-200,200);y+=self.rng.uniform(-120,120)
            if not self.terrain.free_spot(x,y,24):continue
            pos={'x':x,'y':y}
            if any(dist(o,pos)<1500 for o in others):continue
            if any(n['hp']>0 and dist(n,pos)<500 for n in self.npcs.values()):continue
            return x,y
        return coast[0]

    def max_hp(self,p):
        return MAX_HP

    def reset(self):
        """A new game from scratch. The old save stays next to the new one as a dated backup."""
        lock,rng,path,code,settings=self.lock,self.rng,self.save_path,self.room_code,dict(self.settings)
        backup=None
        if path:
            self.save()
        if path and path.exists():
            stamp=time.strftime('%Y%m%d-%H%M%S');n=1
            backup=path.with_name(path.stem+'-'+stamp+'.bak'+path.suffix)
            while backup.exists():
                n+=1;backup=path.with_name(path.stem+'-'+stamp+'-'+str(n)+'.bak'+path.suffix)
            path.replace(backup)
        self.__init__(path,rng)
        self.lock=lock;self.room_code=code;self.settings.update(settings);self.reset_at=time.monotonic()
        if path:self.save()
        return backup

    def player(self,token):
        p=self.players.get(token)
        if not p:
            if time.monotonic()-getattr(self,'reset_at',-1e9)<600:
                raise GameError('Ведущий начал новую игру. Войди снова.')
            raise GameError('Сессия завершилась. Войди в игру снова.')
        p['last_seen']=time.monotonic()
        return p

    def _near(self,p,obj,r=180):
        if dist(p,obj)>r:
            raise GameError('Подойди ближе.')

    def _cooldown(self,p,key,seconds):
        if self.elapsed-p['last_action'].get(key,-10000)<seconds:
            raise GameError('Подожди перед следующей попыткой.')
        p['last_action'][key]=self.elapsed

    def snapshot(self,token,full=True):
        p=self.player(token); f=p['faction']; now=time.monotonic()
        me=self._public_player(p)
        me['god']=bool(p.get('god'))
        for k in ('stats','weapons','items','food','water','warmth','bleeding','sick','mags','born'):
            me[k]=copy.deepcopy(p[k])
        near=lambda o,r:abs(o['x']-p['x'])<r and abs(o['y']-p['y'])<r
        out={'version':VERSION,'stamp':time.monotonic(),'time':round(self.elapsed,2),'me':me,
             'players':[self._public_player(o) for o in self.players.values() if now-o['last_seen']<12 or o is p],
             'npcs':[self.npc_view(n) for n in self.npcs.values() if near(n,2600)],
             'cars':[self.car_view(c) for c in self.cars.values()],
             'loot':[self.loot_view(l) for l in self.loot_near(p['x'],p['y'],1300)],
             'weather':self.weather,
             'camps':[self.camp_view(c,p) for c in self.camps.values()],
             'bodies':[b for b in self.bodies.values() if near(b,5000)],
             'sides':{sid:{'name':s['name'],'color':s['color'],'camp':s.get('camp'),'clan':s.get('clan')} for sid,s in self.sides.items()},
             'clans':{cid:{k:c[k] for k in ('id','name','tag','leader','members','color')} for cid,c in self.clans.items()},
             'invites':[cid for cid,c in self.clans.items() if f in c['invites']],
             'offers':[self.offer_view(o) for o in self.offers.values() if o['until']>self.elapsed and p['id'] in (o['from'],o['to'])],
             'messages':[e for e in self.log if (e['faction'] in (None,f)) and (e['player'] in (None,p['id'])) and p['id'] not in (e.get('skip') or ())],
             'effects':[e for e in self.effects if abs(e['x']-p['x'])<2600 and abs(e['y']-p['y'])<2000][-40:],
             'load_warning':self.load_warning,'full':full}
        if full:
            out['harvested']={k:v for k,v in self.harvested.items() if v>self.elapsed}
        return out

    # ---- commands -------------------------------------------------------
    def command(self,token,data):
        p=self.player(token)
        op=data.get('op')
        if not isinstance(op,str): raise GameError('Неизвестное действие.')
        if op=='input':
            p['input']=[clamp(finite(data.get('x')), -1,1),clamp(finite(data.get('y')),-1,1),bool(data.get('sprint'))]
            p['aim']=[clamp(finite(data.get('ax')), -1,1),clamp(finite(data.get('ay'),1),-1,1)]
            p['last_input']=time.monotonic(); p['paused']=bool(data.get('paused'))
            return {}
        request_id=data.get('request_id')
        if not isinstance(request_id,str) or not 4<=len(request_id)<=80:
            raise GameError('Некорректный номер действия.')
        if request_id in p['receipts']:
            return p['receipts'][request_id]
        if p['hp']<=0:
            raise GameError('Ты погиб. Новая жизнь начнётся через несколько секунд.')
        # Per-action results are recorded before replying. A network retry cannot spend twice.
        result=self._act(p,op,data)
        p['receipts'][request_id]=result
        while len(p['receipts'])>80: p['receipts'].popitem(last=False)
        self.dirty=True
        kind=self._act_kind(p,op,data,result)
        if kind:p['act']={'kind':kind,'at':round(self.elapsed,2)}
        if op not in ('shoot','vehicle','heal','reload','equip'):
            p['busy']=self.elapsed
            # With 25 players a disk write per action is too much: the world is written within two seconds.
            self.save_clock=max(self.save_clock,8)
        return result

    def _act_kind(self,p,op,data,result):
        """Which animation an action plays: tools for work, hands for eating and dressing wounds."""
        if isinstance(result,dict) and result.get('quiet') and op!='shoot':return None
        if op=='harvest':
            n=self.nodes.get(str(data.get('id')))
            return {'wood':'chop','metal':'mine'}.get(n['kind'],'gather') if n else None
        if op in ('repair','craft_item'):return 'hammer'
        if op in ('pickup','loot_body','stash_put','stash_take'):return 'search'
        if op=='drink':return 'drink'
        if op=='heal':return 'bandage'
        if op=='use':
            item=data.get('item')
            return 'drink' if item in ('water','tea','soda') else 'bandage' if item in ('bandage','medkit','pills') else 'eat'
        return None

    # ---- weapons --------------------------------------------------------
    def _reload(self,p):
        """Fill the magazine from the backpack; returns how many rounds went in."""
        w=p['gear']['weapon'];weapon=WEAPONS[w]
        if weapon.get('melee'):return 0
        ammo=weapon['ammo_item']
        need=weapon['mag']-self._mag(p);n=min(need,p['items'].get(ammo,0))
        if n<=0:return 0
        self.take_items(p,{ammo:n});p['mags'][str(w)]=self._mag(p)+n
        p['reload_until']=self.elapsed+weapon['reload'];p['act']={'kind':'reload','at':round(self.elapsed,2)}
        return n

    def _mag(self,p):
        w=p['gear']['weapon']
        if WEAPONS[w].get('melee'):return 0
        return p.setdefault('mags',{}).get(str(w),0)

    def _shoot(self,p):
        weapon=WEAPONS[p['gear']['weapon']]
        ax,ay=p['aim'];length=math.hypot(ax,ay) or 1;ax/=length;ay/=length
        if weapon.get('melee'):
            self._cooldown(p,'shoot',weapon['cd']*.92)
            p['shot']=self.elapsed;p['act']={'kind':'strike','at':round(self.elapsed,2)}
            self.melee_hit(p,ax,ay,weapon)
            return {'quiet':True}
        if p.get('reload_until',0)>self.elapsed: raise GameError('Перезарядка.')
        if self._mag(p)<=0:
            if not self._reload(p):raise GameError('Нет патронов: '+ITEMS[weapon['ammo_item']]['name']+'.')
            raise GameError('Перезарядка.')
        self._cooldown(p,'shoot',weapon['cd']*.92)
        left=self._mag(p)-1;p['mags'][str(p['gear']['weapon'])]=left
        # The last round in the magazine starts an automatic reload if there is ammo in the backpack.
        if left<=0:self._reload(p)
        if weapon.get('spread'):
            spread=self.rng.uniform(-weapon['spread'],weapon['spread']);ax,ay=ax*math.cos(spread)-ay*math.sin(spread),ax*math.sin(spread)+ay*math.cos(spread)
        end=self.shoot_line(p,ax,ay,weapon['range'],weapon['dmg'],weapon.get('width',20))
        p['shot']=self.elapsed
        # Every shot is heard: the infected come running.
        self.make_noise(p['x'],p['y'],weapon['noise'],p)
        self.effects.append({'id':secrets.token_hex(4),'kind':'shot','x':p['x'],'y':p['y'],'ex':end['x'],'ey':end['y'],'until':self.elapsed+.22,'faction':p['faction'],'weapon':p['gear']['weapon']})
        return {'quiet':True}

    def _act(self,p,op,data):
        f=p['faction']
        if op=='shoot':
            if p['vehicle']: raise GameError('Из машины не стрелять.')
            return self._shoot(p)
        if op=='reload':
            weapon=WEAPONS[p['gear']['weapon']]
            if weapon.get('melee'): raise GameError('Это оружие не заряжают.')
            if p.get('reload_until',0)<=self.elapsed and self._mag(p)<weapon['mag'] and not self._reload(p):
                raise GameError('Нет патронов: '+ITEMS[weapon['ammo_item']]['name']+'.')
            return {'quiet':True}
        if op=='equip':
            idx=data.get('weapon')
            if not isinstance(idx,int) or idx not in p['weapons']: raise GameError('Этого оружия у тебя нет.')
            if idx!=p['gear']['weapon']:
                p['gear']['weapon']=idx;p['reload_until']=max(p.get('reload_until',0),self.elapsed+SWAP_TIME)
                p['act']={'kind':'swap','at':round(self.elapsed,2)}
            return {'quiet':True}
        if op=='harvest':
            n=self.nodes.get(str(data.get('id')))
            if not n: raise GameError('Здесь нечего собрать.')
            self._near(p,n,70)
            if p['vehicle']: raise GameError('Выйди из машины.')
            if self.harvested.get(n['id'],0)>self.elapsed: raise GameError('Здесь уже пусто. Загляни позже.')
            if n['kind']=='wood' and 9 not in p['weapons']: raise GameError('Чтобы рубить дерево на доски, нужен топор.')
            self._cooldown(p,'harvest',.8)
            item,count={'wood':('planks',self.rng.randint(1,2)),'metal':('scrap',self.rng.randint(1,2)),
                        'food':(self.rng.choice(('apple','apple','herbs')),self.rng.randint(1,3))}[n['kind']]
            got=self.give_item(p,item,count)
            if not got: raise GameError('Рюкзак полон.')
            self.harvested[n['id']]=self.elapsed+NODE_RESPAWN;p['stats']['harvest']+=1
            if n['kind']=='wood':self.make_noise(n['x'],n['y'],320,p)
            return {'title':ITEMS[item]['name']+' ×'+str(got),'success':True}
        if op=='vehicle':
            self._cooldown(p,'vehicle',.4)
            if p['vehicle']:
                self.leave_car(p)
                return {'title':'Ты вышел из машины','quiet':True}
            car,seat=self.enter_car(p)
            spec=self.car_spec(car)
            if seat=='driver':
                return {'title':spec['name'],'text':'W — газ, S — тормоз и задний ход, A/D — руль, Shift — ручник, F — выйти. Бак: '+str(int(car['fuel']))+' / '+str(spec['tank'])+'.','quiet':True}
            driver=self.car_driver(car)
            return {'title':'Ты пассажир · '+spec['name'],'text':('Ведёт '+driver['name']+'. ' if driver else '')+'F — выйти, когда машина остановится.','quiet':True}
        if op=='repair':
            if p['items'].get('repairkit',0)<1: raise GameError('Нет ремкомплекта. Его находят на заводах и заправках или делают на верстаке.')
            car=self.car_near(p,110)
            if not car or p['vehicle']: raise GameError('Подойди к машине пешком.')
            if car['hp']<=0: raise GameError('Эту машину уже не починить.')
            if car['hp']>=100: raise GameError('Машина исправна.')
            self.take_items(p,{'repairkit':1});car['hp']=100.0
            return {'title':'Машина отремонтирована','text':self.car_spec(car)['name'],'success':True}
        if op=='refuel':
            car=self.car_near(p,140) if not p['vehicle'] else self.cars.get(p['car'])
            if not car: raise GameError('Рядом нет машины.')
            if car['hp']<=0: raise GameError('Машина сгорела.')
            tank=self.car_spec(car)['tank']
            if car['fuel']>=tank-.5: raise GameError('Бак полон.')
            pump=self.pump_near(car,220)
            if pump and not data.get('canister'):
                car['fuel']=float(tank)
                return {'title':'Заправка','text':'Колонка ещё качает. Бак полон: '+str(tank)+'.','success':True}
            if p['items'].get('canister',0)<1: raise GameError('Нет канистры. Заправиться можно у колонки на заправке или из канистры.')
            self.take_items(p,{'canister':1});car['fuel']=min(tank,car['fuel']+20)
            return {'title':'Канистра залита','text':'Бак: '+str(int(car['fuel']))+' / '+str(tank)+'.','success':True}
        if op=='heal':
            if p['hp']>=MAX_HP and not p['bleeding']: raise GameError('Ты не ранен.')
            for item in (('bandage','medkit') if p['bleeding'] else ('medkit','bandage')):
                if p['items'].get(item,0)>0:
                    self._cooldown(p,'heal',3);return self._use(p,item)
            # No bandage: tear up a piece of cloth. It still stops the bleeding.
            if p['bleeding'] and p['items'].get('cloth',0)>0:
                self._cooldown(p,'heal',3);self.take_items(p,{'cloth':1});p['bleeding']=False
                return {'title':'Перевязка тряпкой','text':'Кровь остановлена, −1 ткань.','success':True}
            raise GameError('Нечем перевязаться: нужен бинт, аптечка или ткань.')
        if op=='use':
            item=data.get('item')
            if item not in ITEMS or p['items'].get(item,0)<1: raise GameError('Этого нет в рюкзаке.')
            spec=ITEMS[item]
            if not any(k in spec for k in ('food','water','hp','stop_bleed','cure','warmth')): raise GameError(spec['name']+' — это не едят и не пьют.')
            self._cooldown(p,'use',.6)
            return self._use(p,item)
        if op=='drink':
            if p['vehicle']: raise GameError('Выйди из машины.')
            around=[(p['x']+dx,p['y']+dy) for dx in (-70,0,70) for dy in (-70,0,70)]
            wet=[q for q in around if self.terrain.water(q[0],q[1])]
            if not wet: raise GameError('Рядом нет воды.')
            if all(self.terrain.sea(*q) for q in wet):
                raise GameError('Морская вода солёная — её не пьют. Ищи реку, озеро или бутылку.')
            self._cooldown(p,'drink',2);p['water']=min(100,p['water']+35)
            # Raw river water is a gamble without tetracycline.
            if self.rng.random()<.2:
                p['sick']=self.elapsed+120
                return {'title':'Вода из реки','text':'Жажда утолена, но вода была грязной: отравление. Поможет тетрациклин.','success':False}
            return {'title':'Вода из реки','text':'Жажда +35. Сырая вода может вызвать отравление.','success':True}
        if op=='pickup':
            if p['vehicle']: raise GameError('Выйди из машины.')
            return self.pickup(p,str(data.get('id')))
        if op=='drop':
            if p['vehicle']: raise GameError('Выйди из машины.')
            return self.drop_thing(p,data.get('item'),data.get('count',1))
        if op=='loot_body':
            if p['vehicle']: raise GameError('Выйди из машины.')
            item=data.get('item')
            return self.loot_body(p,data.get('id'),item if isinstance(item,str) and item in ITEMS else None)
        if op=='craft_item':
            self._cooldown(p,'craft',.4)
            return self.craft(p,str(data.get('id')))
        if op=='camp_found':
            camp=self.found_camp(p)
            where='в доме' if camp.get('house') else 'здесь'
            self._notice('Лагерь основан '+where,'Строй в нём: L. Костёр, ящик, верстак, ограда.',player=p['id'])
            return {'title':'Лагерь основан','text':'Теперь построй костёр и ящик: L рядом с лагерем.','success':True}
        if op in ('camp_build','camp_abandon','stash_put','stash_take','camp_break'):
            camp=self.camps.get(str(data.get('camp'))) or self.camp_of(f)
            if not camp: raise GameError('Лагеря нет. Основай его: L.')
            if op=='camp_break':
                if p['vehicle']: raise GameError('Выйди из машины.')
                slot=str(data.get('slot'))
                piece=camp['fence'].get(slot) or camp['parts'].get(slot)
                if not piece or piece['hp']<=0: raise GameError('Ломать нечего.')
                at=piece.get('rect',piece)
                if dist(p,at)>70: raise GameError('Подойди вплотную.')
                if self.camp_allowed(camp,f): raise GameError('Это твой лагерь. Разобрать — в меню лагеря.')
                self._cooldown(p,'break',1.0);p['act']={'kind':'hammer','at':round(self.elapsed,2)}
                weapon=WEAPONS[p['gear']['weapon']]
                broke=self.damage_camp_piece(camp,slot,45 if weapon.get('melee') and p['gear']['weapon']!=FISTS else 15,p)
                self.make_noise(at['x'],at['y'],420,p)
                self._notice('Кто-то ломает лагерь',p['name'],faction=camp['owner'],tone='error')
                return {'title':'Разрушено' if broke else 'Удар','text':'Осталось '+str(int(piece['hp']))+' прочности.' if not broke else '','success':True,'quiet':not broke}
            # Abandoning works from anywhere: the camp may be a long walk away.
            if op=='camp_abandon':
                if camp['owner']!=f: raise GameError('Бросить лагерь может только хозяин.')
                left=bool(camp['stash']['items'])
                self.abandon_camp(camp)
                return {'title':'Лагерь брошен','text':('Вещи из ящика остались лежать на месте лагеря. ' if left else '')+'Новый лагерь можно заложить там, где стоишь: L.','success':False}
            if dist(p,camp)>(max(self.terrain.houses[camp['house']]['w'],self.terrain.houses[camp['house']]['h'])/2+60 if camp.get('house') else 220): raise GameError('Подойди к лагерю.')
            if op=='camp_build':
                if not self.camp_allowed(camp,f): raise GameError('Это чужой лагерь.')
                name=self.build_part(p,camp,str(data.get('kind')),data.get('slot'));p['act']={'kind':'hammer','at':round(self.elapsed,2)}
                self.make_noise(camp['x'],camp['y'],300,p)
                return {'title':'Построено: '+name,'success':True}
            n=self.stash_move(p,camp,str(data.get('item')),finite(data.get('count',1),1),op=='stash_put')
            if not n: raise GameError('Не поместилось.' if op=='stash_take' else 'Нечего положить.')
            return {'title':('Положено' if op=='stash_put' else 'Взято')+': '+ITEMS[data.get('item')]['name']+' ×'+str(n),'success':True,'quiet':True}
        if op.startswith('offer_'):
            return self._offer(p,op,data)
        if op.startswith('clan_'):
            return self._clan(p,op,data)
        raise GameError('Неизвестное действие.')

    # ---- trade between players: items only -----------------------------------
    def _bundle(self,raw):
        """A clean {'items':{}} from client data."""
        raw=raw if isinstance(raw,dict) else {}
        out={'items':{}}
        items=raw.get('items')
        for k,v in (items if isinstance(items,dict) else {}).items():
            n=int(clamp(finite(v),0,99))
            if k in ITEMS and n and 'weapon' not in ITEMS[k] and 'gear' not in ITEMS[k]:out['items'][k]=n
        return out

    def _has_bundle(self,p,b):
        return all(p['items'].get(k,0)>=v for k,v in b['items'].items())

    def _move_bundle(self,a,b,bundle):
        for k,v in bundle['items'].items():
            a['items'][k]-=v
            if not a['items'][k]:del a['items'][k]
            b['items'][k]=b['items'].get(k,0)+v

    def bundle_text(self,b):
        return ', '.join(ITEMS[k]['name']+' ×'+str(v) for k,v in b['items'].items()) or 'ничего'

    def offer_view(self,o):
        names={q['id']:q['name'] for q in self.players.values()}
        return dict(o,from_name=names.get(o['from'],'?'),to_name=names.get(o['to'],'?'),give_text=self.bundle_text(o['give']),want_text=self.bundle_text(o['want']))

    def _offer(self,p,op,data):
        if op=='offer_make':
            other=next((o for o in self.players.values() if o['id']==data.get('to')),None)
            if not other or other is p or other['hp']<=0: raise GameError('Игрок не найден.')
            if dist(p,other)>TRADE_RANGE: raise GameError('Для обмена нужно стоять рядом.')
            give=self._bundle(data.get('give'));want=self._bundle(data.get('want'))
            if not give['items'] and not want['items']: raise GameError('Предложение пустое.')
            if not self._has_bundle(p,give): raise GameError('У тебя нет того, что ты предлагаешь.')
            if sum(1 for o in self.offers.values() if o['from']==p['id'] and o['until']>self.elapsed)>=3: raise GameError('У тебя уже три предложения. Дождись ответа.')
            oid=secrets.token_hex(5)
            self.offers[oid]={'id':oid,'from':p['id'],'to':other['id'],'from_side':p['faction'],'to_side':other['faction'],'give':give,'want':want,'until':self.elapsed+90}
            self._notice('Предложение обмена',p['name']+' отдаёт: '+self.bundle_text(give)+'; просит: '+self.bundle_text(want)+'. Ответ — O.',player=other['id'])
            return {'title':'Предложение отправлено','text':other['name']+' может ответить 90 секунд.','success':True}
        o=self.offers.get(str(data.get('id')))
        if not o or o['until']<=self.elapsed or p['id'] not in (o['from'],o['to']): raise GameError('Предложение уже не действует.')
        if op=='offer_cancel':
            del self.offers[o['id']]
            other=o['to'] if o['from']==p['id'] else o['from']
            self._notice('Обмен отклонён',p['name']+' отказался.',player=other)
            return {'title':'Обмен отменён','success':False}
        if op!='offer_accept' or o['to']!=p['id']: raise GameError('Принять может только тот, кому предложили.')
        giver=next((q for q in self.players.values() if q['id']==o['from']),None)
        if not giver or dist(giver,p)>TRADE_RANGE: raise GameError('Для обмена нужно стоять рядом.')
        if not self._has_bundle(giver,o['give']): raise GameError('У '+giver['name']+' уже нет обещанного.')
        if not self._has_bundle(p,o['want']): raise GameError('У тебя нет того, что просят.')
        def after(q,minus,plus):
            out=dict(q['items'])
            for k,v in minus.items():out[k]=out.get(k,0)-v
            for k,v in plus.items():out[k]=out.get(k,0)+v
            return self.slots_used({k:v for k,v in out.items() if v>0})
        if after(p,o['want']['items'],o['give']['items'])>self.slots(p): raise GameError('Не хватит места в рюкзаке.')
        if after(giver,o['give']['items'],o['want']['items'])>self.slots(giver): raise GameError('У '+giver['name']+' не хватит места в рюкзаке.')
        del self.offers[o['id']]
        self._move_bundle(giver,p,o['give']);self._move_bundle(p,giver,o['want'])
        self._notice('Обмен состоялся',p['name']+' принял предложение.',player=giver['id'])
        return {'title':'Обмен состоялся','text':'Получено: '+self.bundle_text(o['give'])+'.','success':True}

    # ---- clans -------------------------------------------------------------
    def _clan(self,p,op,data):
        f=p['faction'];mine=self.sides[f].get('clan');clan=self.clans.get(mine)
        if op=='clan_create':
            if clan: raise GameError('Ты уже в группе.')
            name=' '.join(str(data.get('name','')).split())[:24]
            if len(name)<3: raise GameError('Название группы — от трёх букв.')
            if any(c['name'].lower()==name.lower() for c in self.clans.values()): raise GameError('Такая группа уже есть.')
            cid='c_'+secrets.token_hex(4)
            tag=''.join(w[0] for w in name.split())[:4].upper() if len(name.split())>1 else name[:4].upper()
            self.clans[cid]={'id':cid,'name':name,'tag':tag,'leader':f,'members':[f],'invites':[],'color':self.sides[f]['color']}
            self.sides[f]['clan']=cid
            self._notice('Собрана группа «'+name+'»',p['name']+' зовёт людей.')
            return {'title':'Группа «'+name+'»','text':'Приглашай игроков рядом. В группе не стреляют друг в друга и делят лагерь.','success':True}
        if op=='clan_join':
            c=self.clans.get(str(data.get('id')))
            if clan: raise GameError('Сначала выйди из своей группы.')
            if not c or f not in c['invites']: raise GameError('Приглашения нет.')
            if len(c['members'])>=CLAN_SIZE: raise GameError('В группе уже '+str(CLAN_SIZE)+' человек.')
            c['invites'].remove(f);c['members'].append(f);self.sides[f]['clan']=c['id']
            self._notice(p['name']+' вступил в группу','«'+c['name']+'»')
            return {'title':'Ты в группе «'+c['name']+'»','success':True}
        if op=='clan_decline':
            c=self.clans.get(str(data.get('id')))
            if c and f in c['invites']:c['invites'].remove(f)
            return {'title':'Приглашение отклонено','success':False}
        if not clan: raise GameError('Ты не состоишь в группе.')
        if op=='clan_leave':
            clan['members'].remove(f);self.sides[f]['clan']=None
            if not clan['members']:del self.clans[clan['id']]
            elif clan['leader']==f:clan['leader']=clan['members'][0]
            self._notice(p['name']+' покинул группу','«'+clan['name']+'»')
            return {'title':'Ты вышел из группы','success':False}
        g=str(data.get('side'))
        if clan['leader']!=f: raise GameError('Это решает глава группы.')
        if op=='clan_invite':
            target=next((o for o in self.players.values() if o['faction']==g),None)
            if not target or g==f: raise GameError('Игрок не найден.')
            if self.sides[g].get('clan'): raise GameError(target['name']+' уже в группе.')
            if len(clan['members'])+len(clan['invites'])>=CLAN_SIZE+2: raise GameError('Слишком много приглашений.')
            if g not in clan['invites']:clan['invites'].append(g)
            self._notice('Приглашение в группу','«'+clan['name']+'» зовёт тебя. Ответ — O → Группа.',player=target['id'])
            return {'title':'Приглашение отправлено','text':target['name'],'success':True}
        if op=='clan_kick':
            if g not in clan['members'] or g==f: raise GameError('Такого человека в группе нет.')
            clan['members'].remove(g);self.sides[g]['clan']=None
            self._notice('Исключён из группы',self.side_name(g)+' · «'+clan['name']+'»')
            return {'title':'Исключён','text':self.side_name(g),'success':True}
        raise GameError('Неизвестное действие.')

    def slots(self,p):
        return BACKPACKS[p['gear']['backpack']]['slots']

    def _use(self,p,item):
        spec=ITEMS[item];self.take_items(p,{item:1})
        p['food']=clamp(p['food']+spec.get('food',0),0,100);p['water']=clamp(p['water']+spec.get('water',0),0,100)
        p['warmth']=clamp(p['warmth']+spec.get('warmth',0),0,100);p['hp']=min(MAX_HP,p['hp']+spec.get('hp',0))
        if spec.get('stop_bleed'):p['bleeding']=False
        if spec.get('cure'):p['sick']=0
        if spec.get('risk') and self.rng.random()<spec['risk']:
            p['sick']=self.elapsed+120
            return {'title':spec['name'],'text':'Сытость +'+str(spec.get('food',0))+', но живот скрутило: отравление.','success':False}
        return {'title':spec['name'],'text':spec['desc'],'success':True}

    # ---- death ---------------------------------------------------------------
    def _damage(self,p,amount):
        if p.get('god'):return
        p['hp']=max(0,p['hp']-amount)
        if p['hp']==0 and not p['dead_until']:
            if p['vehicle']:self.leave_car(p,force=True)
            p['dead_until']=self.elapsed+RESPAWN_TIME;p['vehicle']=False;p['input']=[0,0,False]
            self._death(p)

    def _death(self,p):
        """Everything the dead carried stays on the body: backpack, guns, clothes. The next life starts with nothing."""
        items=dict(p['items'])
        for w in p['weapons']:
            if w!=FISTS:
                key=WEAPON_ITEM[w];items[key]=items.get(key,0)+1
        for kind in ('clothes','backpack','armor'):
            tier=p['gear'][kind]
            if tier:items[GEAR_ITEM[(kind,tier)]]=items.get(GEAR_ITEM[(kind,tier)],0)+1
        mags={str(w):n for w,n in p['mags'].items() if n}
        p['items']={};p['weapons']=[FISTS];p['mags']={};p['gear']={'weapon':FISTS,'armor':0,'clothes':0,'backpack':0}
        bid=self.drop_pile(p['x'],p['y'],items,'Тело: '+p['name'])
        if bid:self.bodies[bid]['mags']=mags;self.bodies[bid]['player']=p['id']
        lived=int((self.elapsed-p.get('born',self.elapsed))//60)
        st=p['stats']
        self._notice('Ты погиб','Прожито '+str(lived)+' мин. Заражённых: '+str(st['infected'])+', игроков: '+str(st['players'])+'. Всё осталось на теле.',player=p['id'],tone='error')
        # Everybody else hears about it: who died, from what and where.
        near=min(self.towns.values(),key=lambda t:dist(t,p))
        hit=p.get('hit_by') or {}
        killer=hit.get('id') if hit.get('kind')=='player' and self.elapsed-hit.get('at',-99)<20 else None
        self._notice(p['name']+' погиб',self._death_cause(p)+' · рядом '+near['name']+'.',tone='death',skip=[p['id'],killer])
        p.pop('hit_by',None)
        self.dirty=True

    def _death_cause(self,p):
        """A short line for the others: the last blow if it was recent, otherwise what drained the life."""
        hit=p.get('hit_by')
        if hit and self.elapsed-hit['at']<20:
            if hit['kind']=='player':return 'Убит игроком '+hit['name']
            if hit['kind']=='infected':return 'Растерзан заражёнными'
            if hit['kind']=='animal':return 'Погиб от зверя: '+hit['name'].lower()
            if hit['kind']=='crash':return 'Разбился на машине'
            if hit['kind']=='admin':return 'Убит ведущим'
        return {'bleeding':'Истёк кровью','water':'Умер от жажды','food':'Умер от голода','cold':'Замёрз насмерть',
                'sick':'Умер от болезни'}.get(p.get('drain'),'Погиб')

    def _covered(self,a,b):
        length=dist(a,b)
        for step in range(1,int(length/25)):
            mix=step*25/max(length,1)
            if self.terrain.solid(a['x']+(b['x']-a['x'])*mix,a['y']+(b['y']-a['y'])*mix,0): return True
        return False

    def blocked(self,x,y,r,faction=None):
        if not r<=x<=WORLD_SIZE[0]-r or not r<=y<=WORLD_SIZE[1]-r: return True
        return self.solid_for(x,y,r,faction)

    def solid_for(self,x,y,r,faction=None):
        """Walls, buildings and camp fences; a camp's gate lets its owner and clan through."""
        for b in self.terrain.grid.get((int(x//RECT_CELL),int(y//RECT_CELL)),()):
            if abs(x-b['x'])<b['w']/2+r and abs(y-b['y'])<b['h']/2+r:
                if b.get('gate') and self.gate_open_for(b,faction):continue
                return True
        return self.terrain.wreck_hit(x,y,r)

    def make_noise(self,x,y,radius,who=None):
        if radius>0:self.noises.append({'x':x,'y':y,'r':radius,'until':self.elapsed+.6,'who':who['id'] if who else None})

    # ---- simulation ---------------------------------------------------------
    def tick(self,dt):
        now=time.monotonic()
        active=[p for p in self.players.values() if now-p['last_seen']<8]
        if not active or all(p['paused'] for p in active): return
        dt=clamp(dt,0,.1);self.elapsed+=dt;self.save_clock+=dt
        self.effects=[e for e in self.effects if e['until']>self.elapsed]
        self.noises=[n for n in self.noises if n['until']>self.elapsed]
        for p in active:
            if p['hp']<=0:
                if self.elapsed>=p['dead_until']:self._fresh_character(p)
                continue
            x,y,sprint=p['input'] if now-p['last_input']<.65 and not p['paused'] else (0,0,False)
            length=math.hypot(x,y)
            if length>1: x/=length;y/=length
            moving=bool(x or y)
            speed=140
            if p['vehicle']:
                car=self.cars.get(p['car'])
                if not car:self.leave_car(p,force=True)
                elif p['seat']=='passenger':self.ride(p,car)
                else:
                    # W/S are throttle and brake, A/D steer, Shift is the handbrake.
                    live=now-p['last_input']<.65 and not p['paused']
                    self.drive(p,car,dt,clamp(p['input'][0] if live else 0,-1,1),clamp(-(p['input'][1] if live else 0),-1,1),bool(sprint))
            elif sprint and p['stamina']>1 and moving:
                speed=220;p['stamina']=max(0,p['stamina']-dt*16)
            else: p['stamina']=min(100,p['stamina']+dt*12*(.4 if min(p['food'],p['water'])<20 or p['warmth']<25 else 1))
            self._survive(p,dt,sprint and moving and not p['vehicle'])
            if not p['vehicle']:
                if self.terrain.water(p['x'],p['y']):speed*=.45
                nx=p['x']+x*speed*dt;ny=p['y']+y*speed*dt
                if not self.blocked(nx,p['y'],10,p['faction']):p['x']=nx
                if not self.blocked(p['x'],ny,10,p['faction']):p['y']=ny
                if moving:p['angle']=math.atan2(y,x)
                if p.get('act') and moving and p['act']['kind'] in ('search','eat','drink','bandage','gather','chop','mine','hammer'):p.pop('act',None)
            if self.near_camp_part(p,'fire',130):p['hp']=min(MAX_HP,p['hp']+dt*1.5)
        self.tick_npcs(dt,active)
        self.tick_cars(dt)
        self.tick_loot(dt,active)
        self.tick_camps(dt);self.tick_bodies()
        self._tick_world(dt)
        if self.save_clock>=10:
            self.save_clock=0;self.save()

    def _survive(self,p,dt,sprinting):
        """Hunger, thirst, cold, bleeding and sickness, simulated on the host."""
        sick=p['sick']>self.elapsed
        k=(2 if sprinting else .6 if p['vehicle'] else 1)*(1.8 if sick else 1)
        p['food']=max(0,p['food']-.05*k*dt);p['water']=max(0,p['water']-.065*k*dt)
        town=min(self.towns.values(),key=lambda t:dist(t,p))
        hour=(8+self.elapsed*1.4/60)%24;night=hour>=21 or hour<6
        wading=not p['vehicle'] and self.terrain.water(p['x'],p['y'])
        exposure=REGIONS[town['region']]['cold']*10+(12 if night else 0)
        exposure+={'rain':10,'storm':18,'snow':16,'fog':4}.get(self.weather['kind'],0)+(18 if wading else 0)
        exposure-=CLOTHES[p['gear']['clothes']]['warm']+(25 if p['vehicle'] else 0)
        fire=bool(self.near_camp_part(p,'fire',170))
        target=100 if fire else clamp(100-max(0,exposure)*1.6,0,100)
        rate=2.5 if fire else .6
        p['warmth']+=clamp(target-p['warmth'],-rate*dt,rate*dt)
        parts={'food':.3 if p['food']<=0 else 0,'water':.5 if p['water']<=0 else 0,'cold':.35 if p['warmth']<20 else 0,
               'bleeding':.5 if p['bleeding'] else 0,'sick':.08 if sick else 0}
        drain=sum(parts.values())
        if drain:p['drain']=max(parts,key=parts.get);self._damage(p,drain*dt)
        elif p['food']>70 and p['water']>70 and p['warmth']>50:p['hp']=min(MAX_HP,p['hp']+.2*dt)
        for key,value,low,text in (('food',p['food'],25,'Ты голоден. Поешь из рюкзака: G.'),
                                   ('water',p['water'],25,'Хочется пить. V — вода из рюкзака, из реки или озера.'),
                                   ('warmth',p['warmth'],30,'Ты замерзаешь. Тёплая одежда, машина или костёр.')):
            if value<low and key not in p['warned']:
                p['warned'].append(key);self._notice({'food':'Голод','water':'Жажда','warmth':'Холод'}[key],text,player=p['id'],tone='error')
            elif value>low+15 and key in p['warned']:p['warned'].remove(key)

    def _tick_world(self,dt):
        if self.weather['until']<=self.elapsed:
            kinds=['clear']*9+['rain']*4+['fog']*3+['storm']*2+['snow']
            self.weather={'kind':self.rng.choice(kinds),'until':self.elapsed+self.rng.uniform(200,420)}
        for k in [k for k,o in self.offers.items() if o['until']<=self.elapsed]:del self.offers[k]

    # ---- persistence ----------------------------------------------------
    def save(self):
        if not self.save_path:return
        players={}
        for token,p in self.players.items():
            players[token]={k:v for k,v in p.items() if k not in ('last_seen','last_input','input','receipts','paused')}
        payload={'schema':SAVE_VERSION,'version':VERSION,'time':self.elapsed,'players':players,'sides':self.sides,
                 'harvested':self.harvested,'weather':self.weather,'settings':self.settings,'room_code':self.room_code,
                 'clans':self.clans,'camps':self.camps,'bodies':self.bodies,'cars':self.cars,'loot':self.loot,
                 'loot_restock':self.loot_restock,'zones':self.zone_save()}
        try:
            self.save_path.parent.mkdir(parents=True,exist_ok=True)
            tmp=self.save_path.with_suffix('.tmp')
            with tmp.open('w',encoding='utf-8') as h:
                json.dump(payload,h,ensure_ascii=False);h.flush();os.fsync(h.fileno())
            try:os.chmod(tmp,0o600)
            except OSError:pass
            os.replace(str(tmp),str(self.save_path));self.dirty=False
        except OSError as exc:
            self.load_warning='Не удалось сохранить мир. Проверь свободное место и доступ к своей папке.'
            print('Save error:',exc,flush=True)

    def _set_aside(self,reason):
        """Keep an old or damaged save next to the new world instead of overwriting it."""
        backup=self.save_path.with_name(self.save_path.stem+'.'+reason+'-'+str(int(time.time()))+'.json')
        try:os.replace(str(self.save_path),str(backup))
        except OSError:pass
        return backup

    def load(self):
        try:
            raw=json.loads(self.save_path.read_text(encoding='utf-8'))
        except (OSError,ValueError):
            self._set_aside('unreadable')
            self.load_warning='Сохранение не удалось прочитать. Его копия сохранена рядом; начат новый мир.'
            return
        if raw.get('schema')!=SAVE_VERSION:
            # Worlds from before 0.8 had another map and other rules: they are kept aside, untouched.
            backup=self._set_aside('before-0.8')
            self.room_code=raw.get('room_code') if isinstance(raw.get('room_code'),str) and len(raw['room_code'])==6 and raw['room_code'].isdigit() else None
            self.load_warning='Мир из прошлой версии игры сохранён рядом ('+backup.name+'). Начат новый мир по правилам DayZ.'
            return
        try:
            players={}
            for token,p in list(raw.get('players',{}).items())[:MAX_PLAYERS]:
                if not isinstance(p.get('faction'),str):raise ValueError('Faction')
                p['x']=clamp(finite(p['x']),25,WORLD_SIZE[0]-25);p['y']=clamp(finite(p['y']),25,WORLD_SIZE[1]-25)
                p.update(last_seen=-1000,last_input=-1000,input=[0,0,False],receipts=OrderedDict(),paused=False,vehicle=False,car=None,seat=None)
                gear=p.get('gear') or {}
                p['gear']={'weapon':int(clamp(finite(gear.get('weapon',FISTS)),0,len(WEAPONS)-1)),'armor':int(clamp(finite(gear.get('armor',0)),0,len(ARMOR)-1)),
                           'clothes':int(clamp(finite(gear.get('clothes',0)),0,len(CLOTHES)-1)),'backpack':int(clamp(finite(gear.get('backpack',0)),0,len(BACKPACKS)-1))}
                p['weapons']=sorted({int(clamp(finite(i),0,len(WEAPONS)-1)) for i in p.get('weapons',[])}|{FISTS,p['gear']['weapon']})
                items=p.get('items') or {};p['items']={k:max(0,int(finite(v))) for k,v in items.items() if k in ITEMS and finite(v)>0 and 'weapon' not in ITEMS[k] and 'gear' not in ITEMS[k]}
                for key,default in (('food',70.0),('water',70.0),('warmth',90.0),('hp',MAX_HP),('stamina',100.0)):p[key]=clamp(finite(p.get(key,default),default),0,100)
                p['mags']={str(k):int(clamp(finite(v),0,999)) for k,v in (p.get('mags') or {}).items()} if isinstance(p.get('mags'),dict) else {}
                st=p.get('stats') or {};p['stats']={k:int(finite(st.get(k,0))) for k in STAT_KEYS}
                p['reload_until']=0.0;p.pop('act',None);p['born']=finite(p.get('born',0))
                p['bleeding']=bool(p.get('bleeding'));p['sick']=finite(p.get('sick',0));p['warned']=[]
                p['dead_until']=finite(p.get('dead_until',0));p['last_action']={}
                players[token]=p
            sides={}
            for sid,info in (raw.get('sides') or {}).items():
                if isinstance(info,dict):
                    sides[sid]={'id':sid,'name':str(info.get('name',''))[:30],'color':str(info.get('color','#cccccc'))[:9],
                                'camp':info.get('camp') if isinstance(info.get('camp'),str) else None,'clan':None}
            clans={}
            for cid,c in (raw.get('clans') or {}).items():
                members=[m for m in c.get('members',[]) if m in sides and not sides[m]['clan']][:CLAN_SIZE]
                if not members:continue
                clans[cid]={'id':cid,'name':str(c.get('name','Группа'))[:24],'tag':str(c.get('tag',''))[:4],'members':members,
                            'leader':c.get('leader') if c.get('leader') in members else members[0],
                            'invites':[m for m in c.get('invites',[]) if m in sides],'color':str(c.get('color','#cccccc'))[:9]}
                for m in members:sides[m]['clan']=cid
            for p in players.values():
                if p['faction'] not in sides:raise ValueError('Player side')
            self.elapsed=max(0,finite(raw.get('time')))
            self.players=players;self.sides=sides;self.clans=clans
            self._load_camps(raw,sides)
            self.harvested={k:finite(v) for k,v in (raw.get('harvested') or {}).items()}
            if isinstance(raw.get('weather'),dict) and raw['weather'].get('kind') in WEATHER:self.weather=raw['weather']
            self.settings.update(raw.get('settings') or {})
            self.load_cars(raw.get('cars') or {})
            self.load_loot(raw)
            self.zone_load(raw.get('zones') or {})
            code=raw.get('room_code')
            self.room_code=code if isinstance(code,str) and len(code)==6 and code.isdigit() else None
        except (ValueError,KeyError,TypeError,AttributeError,StopIteration):
            # Preserve the original damaged file for recovery before autosave writes a new world.
            self._set_aside('unreadable')
            self.__init__(None,self.rng)
            self.load_warning='Сохранение не удалось прочитать. Его копия сохранена рядом; начат новый мир.'

    def camp_view(self,c,p):
        out={'id':c['id'],'owner':c['owner'],'x':c['x'],'y':c['y'],'house':c.get('house'),
             'parts':{k:{'hp':round(v['hp']),'max':v['max'],'x':v['x'],'y':v['y']} for k,v in c['parts'].items()},
             'fence':{k:{'hp':round(v['hp']),'max':v['max'],'kind':v.get('kind','wall'),'house':bool(v.get('house')),
                         'x':v['rect']['x'],'y':v['rect']['y'],'w':v['rect']['w'],'h':v['rect']['h']} for k,v in c['fence'].items()},
             'breached':self.camp_breached(c)}
        # What lies in the crate is seen by its people, and by anyone once the fence is breached.
        if (self.camp_allowed(c,p['faction']) or out['breached']) and dist(c,p)<400:
            out['stash']=c['stash']
        return out

    def _load_camps(self,raw,sides):
        """Camps keep their fences as solid rectangles; house camps reuse the house's own walls."""
        self.camps={};self.bodies={}
        for cid,c in (raw.get('camps') or {}).items():
            if not isinstance(c,dict) or c.get('owner') not in sides:continue
            house=self.terrain.houses.get(c.get('house')) if c.get('house') else None
            if c.get('house') and not house:continue
            camp={'id':cid,'owner':c['owner'],'x':finite(c.get('x')),'y':finite(c.get('y')),'house':house['id'] if house else None,
                  'parts':{},'fence':{},'stash':{'items':{}},'water_at':finite(c.get('water_at',0))}
            for k,v in ((c.get('stash') or {}).get('items') or {}).items():
                if k in ITEMS and finite(v)>0:camp['stash']['items'][k]=int(finite(v))
            for k,v in (c.get('parts') or {}).items():
                if k in CAMP_PARTS and isinstance(v,dict):camp['parts'][k]={'kind':k,'hp':finite(v.get('hp')),'max':finite(v.get('max',1),1),'x':finite(v.get('x')),'y':finite(v.get('y'))}
            for slot,v in (c.get('fence') or {}).items():
                if not isinstance(v,dict) or not isinstance(v.get('rect'),dict):continue
                if v.get('house') and house and slot.startswith('w') and slot[1:].isdigit() and int(slot[1:])<len(house['walls']):
                    rect=house['walls'][int(slot[1:])]
                else:
                    r=v['rect'];rect={'x':finite(r.get('x')),'y':finite(r.get('y')),'w':finite(r.get('w'),10),'h':finite(r.get('h'),10),'camp':cid}
                    if slot=='gate':rect['gate']=True
                    if finite(v.get('hp'))>0:self.terrain.add_rect(rect)
                piece={'kind':v.get('kind','wall'),'hp':finite(v.get('hp')),'max':finite(v.get('max',1),1),'rect':rect}
                if v.get('house'):piece['house']=True
                if piece['hp']<=0 and v.get('house'):self.terrain.remove_rect(rect)
                camp['fence'][slot]=piece
            self.camps[cid]=camp;sides[c['owner']]['camp']=cid
        for s in sides.values():
            if s.get('camp') not in self.camps:s['camp']=None
        for bid,b in (raw.get('bodies') or {}).items():
            if not isinstance(b,dict):continue
            self.bodies[bid]={'id':bid,'x':finite(b.get('x')),'y':finite(b.get('y')),'name':str(b.get('name',''))[:40],'until':finite(b.get('until')),
                              'items':{k:int(finite(v)) for k,v in (b.get('items') or {}).items() if k in ITEMS and finite(v)>0},
                              'mags':{str(k):int(finite(v)) for k,v in (b.get('mags') or {}).items()}}
            if isinstance(b.get('npc'),dict) and b['npc'].get('type') in NPC_TYPES:
                n=b['npc'];self.bodies[bid]['npc']={'type':n['type'],'look':n.get('look'),'angle':finite(n.get('angle')),'faction':str(n.get('faction',''))}


World.GameError = GameError

class GameServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    request_queue_size=32

    def __init__(self,address,world,join_code,title='Комната'):
        self.world=world;self.join_code=join_code;self.join_attempts={};self.stop_event=threading.Event()
        self.title=title
        super().__init__(address,Handler)

STATIC={'/':'index.html','/index.html':'index.html','/style.css':'style.css','/game.js':'game.js',
        '/sprites.js':'sprites.js','/render.js':'render.js','/audio.js':'audio.js','/icon.svg':'icon.svg',
        '/assets/characters.png':'assets/characters.png','/assets/cars.png':'assets/cars.png','/assets/hero.png':'assets/hero.png',
        '/assets/infected.png':'assets/infected.png','/assets/infected.json':'assets/infected.json','/assets/loot.png':'assets/loot.png',
        '/assets/loot.json':'assets/loot.json','/assets/trees.png':'assets/trees.png','/assets/trees.json':'assets/trees.json'}
TYPES={'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'application/javascript; charset=utf-8','svg':'image/svg+xml','png':'image/png','jpg':'image/jpeg','json':'application/json; charset=utf-8'}

class Handler(BaseHTTPRequestHandler):
    server_version='AfterSilence/'+VERSION
    timeout=15          # idle connections do not hold a thread forever

    def log_message(self,fmt,*args):
        if len(args)>1 and str(args[1]) not in ('200','304'):print(fmt%args,flush=True)

    def _local(self):
        return self.client_address[0] in ('127.0.0.1','::1')

    def _json(self,status,value):
        data=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)

    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/api/config':
            w=self.server.world
            cfg=config();cfg['nodes']=list(w.nodes.values())
            cfg['pois']=list(w.terrain.pois.values())
            cfg['towns']=[dict(t,r=w.terrain.towns[t['id']]['r'],h=w.terrain.towns[t['id']]['h']) for t in cfg['towns']]
            cfg['streets']=[[round(v) for v in s] for s in w.terrain.streets]
            cfg['houses']=[{k:h[k] for k in ('id','town','kind','x','y','w','h','door','use')} for h in w.terrain.houses.values()]
            cfg['wrecks']=[[k['x'],k['y'],k['a'],k['m'],int(k['bus']),int(k['burnt'])] for k in w.terrain.wrecks]
            cfg['road_lines']=[{'ax':s[0],'ay':s[1],'bx':s[2],'by':s[3],'a':s[4],'b':s[5]} for s in w.terrain.road_segments]
            cfg['pumps']=w.pumps()
            cfg['join_code']=self.server.join_code if self._local() else None
            cfg['lan_addresses']=lan_addresses(self.server.server_port) if cfg['join_code'] else []
            cfg['host']=self._local()
            with w.lock:cfg['settings']=dict(w.settings)
            cfg['admin']=self.server.world.admin_info() if self._local() else None
            self._json(200,cfg);return
        if path=='/api/state':
            with self.server.world.lock:
                try:self._json(200,self.server.world.snapshot(self.headers.get('X-Session','')))
                except GameError as e:self._json(401,{'error':str(e)})
                except Exception:
                    traceback.print_exc();self._json(500,{'error':'Ошибка на сервере.'})
            return
        if path not in STATIC:self._json(404,{'error':'Файл не найден'});return
        p=ROOT/'web'/STATIC[path]
        try:blob=p.read_bytes()
        except OSError:self._json(404,{'error':'Файл не найден'});return
        self.send_response(200)
        self.send_header('Content-Type',TYPES[p.suffix[1:]])
        self.send_header('Content-Length',str(len(blob)));self.send_header('Cache-Control','no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(blob)

    def do_POST(self):
        # Same-origin JSON only. No CORS and no ambient cookies/session credentials.
        origin=self.headers.get('Origin')
        if origin and urlsplit(origin).netloc!=self.headers.get('Host'):
            self._json(403,{'error':'Другой источник запроса.'});return
        if not self.headers.get('Content-Type','').startswith('application/json'):
            self._json(415,{'error':'Ожидался JSON.'});return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:raise ValueError()
            data=json.loads(self.rfile.read(length).decode('utf-8'))
            if not isinstance(data,dict):raise ValueError()
        except (ValueError,UnicodeDecodeError):self._json(400,{'error':'Некорректный запрос.'});return
        with self.server.world.lock:
            try:
                path=urlsplit(self.path).path
                if path=='/api/join':
                    ip=self.client_address[0];now=time.monotonic()
                    attempts=self.server.join_attempts.setdefault(ip,[])
                    attempts[:]=[n for n in attempts if now-n<60]
                    if len(attempts)>=12:self._json(429,{'error':'Слишком много попыток. Подожди минуту.'});return
                    if not self._local() and not secrets.compare_digest(str(data.get('code','')).encode('utf-8'),self.server.join_code.encode('utf-8')):
                        attempts.append(now);self._json(403,{'error':'Неверный код комнаты.'});return
                    token=self.server.world.join(data.get('name',''),None,data.get('token'),data.get('color'))
                    self._json(200,{'token':token,'state':self.server.world.snapshot(token)});return
                if path=='/api/host':
                    # Room settings are changed only on the host computer itself.
                    if not self._local():self._json(403,{'error':'Настройки меняет только ведущий.'});return
                    if data.get('new_world'):
                        backup=self.server.world.reset()
                        self._json(200,{'settings':self.server.world.settings,'reset':True,'backup':backup.name if backup else None});return
                    self.server.world.save()
                    if data.get('shutdown'):
                        self._json(200,{'settings':self.server.world.settings,'stopping':True})
                        self.server.stop_event.set()
                        threading.Thread(target=self.server.shutdown,daemon=True).start();return
                    self._json(200,{'settings':self.server.world.settings});return
                if path=='/api/admin':
                    # The admin panel works only on the host computer itself.
                    if not self._local():self._json(403,{'error':'Админ-панель доступна только на компьютере ведущего.'});return
                    result=self.server.world.admin(self.headers.get('X-Session',''),data)
                    self.server.world.dirty=True
                    self._json(200,{'result':result,'state':self.server.world.snapshot(self.headers.get('X-Session',''))});return
                if path!='/api/action':self._json(404,{'error':'Команда не найдена.'});return
                token=self.headers.get('X-Session','')
                if token not in self.server.world.players:self._json(401,{'error':'Ведущий начал новую игру. Войди снова.' if time.monotonic()-getattr(self.server.world,'reset_at',-1e9)<600 else 'Нужно войти в комнату.'});return
                result=self.server.world.command(token,data)
                full=data.get('op')!='input' or bool(data.get('full'))
                self._json(200,{'result':result,'state':self.server.world.snapshot(token,full)})
            except GameError as e:self._json(400,{'error':str(e)})
            except (TypeError,ValueError,KeyError):self._json(400,{'error':'Некорректные данные действия.'})
            except Exception:
                # A bug in one action must not drop the connection or the room.
                traceback.print_exc();self._json(500,{'error':'Ошибка на сервере: действие не выполнено.'})

def simulate(world,stop):
    """Advance the world 20 times a second. A faulty tick is logged and skipped: the room keeps running."""
    before=time.monotonic();errors=0
    while not stop.wait(.05):
        now=time.monotonic()
        try:
            with world.lock:world.tick(now-before)
        except Exception:
            errors+=1
            if errors<=20 or errors%1000==0:traceback.print_exc()
        before=now

def lan_addresses(port):
    addresses=set()
    try:
        for item in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET):
            ip=item[4][0]
            if not ip.startswith('127.'):addresses.add('http://'+ip+':'+str(port))
    except OSError:pass
    # Route selection is local; no datagram is sent by UDP connect.
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.connect(('192.0.2.1',9))
        ip=s.getsockname()[0];s.close()
        if not ip.startswith('127.'):addresses.add('http://'+ip+':'+str(port))
    except OSError:pass
    return sorted(addresses)

def discovery_responder(server,port=DISCOVERY_PORT):
    """Answer LAN room searches from the launcher. The reply never contains the room code."""
    try:
        sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        sock.bind(('',port));sock.settimeout(.5)
    except OSError as exc:
        print('Поиск комнат в сети недоступен: '+str(exc),flush=True);return
    while not server.stop_event.is_set():
        try:data,addr=sock.recvfrom(256)
        except socket.timeout:continue
        except OSError:break
        if data!=b'AFTERSILENCE?':continue
        with server.world.lock:
            now=time.monotonic()
            players=sum(1 for p in server.world.players.values() if now-p['last_seen']<12)
        reply={'game':'after-silence','version':VERSION,'port':server.server_port,'name':server.title,'players':players}
        try:sock.sendto(json.dumps(reply,ensure_ascii=False).encode('utf-8'),addr)
        except OSError:pass
    sock.close()

def run():
    parser=argparse.ArgumentParser(description='После тишины — автономная игра и LAN-сервер')
    parser.add_argument('--host',default='0.0.0.0');parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--save',default=str(Path.home()/'.local/share/after-silence/world.json'))
    parser.add_argument('--new-code',action='store_true',help='выдать новый код комнаты')
    parser.add_argument('--no-ai',action='store_true',help='оставлено для старых ярлыков; ничего не делает')
    parser.add_argument('--open',action='store_true');args=parser.parse_args()
    world=World(args.save)
    # A room keeps its code across restarts so friends can rejoin with the same code.
    if args.new_code or not world.room_code:world.room_code=str(secrets.randbelow(900000)+100000)
    world.save()
    code=world.room_code
    lan=args.host not in ('127.0.0.1','localhost')
    try:server=GameServer((args.host,args.port),world,code,socket.gethostname()[:30] or 'Комната')
    except OSError as exc:
        print('Не удалось открыть порт '+str(args.port)+': '+str(exc),flush=True)
        print('Возможно, игра уже запущена: http://127.0.0.1:'+str(args.port),flush=True)
        return 1
    print('\nПОСЛЕ ТИШИНЫ '+VERSION+'\nНа этом ПК: http://127.0.0.1:'+str(args.port),flush=True)
    if lan:print('Для друзей: '+', '.join(lan_addresses(args.port))+'\nКод комнаты: '+code+'\nЗакрытие этого окна завершит игру для всех.\n',flush=True)
    else:print('Одиночная игра: сеть не используется.\n',flush=True)
    threading.Thread(target=simulate,args=(world,server.stop_event),daemon=True).start()
    if lan:threading.Thread(target=discovery_responder,args=(server,),daemon=True).start()
    def terminate(*_):
        server.stop_event.set()
        threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
    if hasattr(signal,'SIGHUP'):signal.signal(signal.SIGHUP,terminate)
    if args.open:threading.Timer(.5,lambda:webbrowser.open('http://127.0.0.1:'+str(args.port))).start()
    try:server.serve_forever(poll_interval=.2)
    finally:
        server.stop_event.set()
        with world.lock:world.save()
        server.server_close()
    return 0

if __name__=='__main__':
    raise SystemExit(run())
