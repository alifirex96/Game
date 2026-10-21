#!/usr/bin/env python3
"""After Silence: authoritative LAN simulation. No third-party dependencies."""
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
import webbrowser
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from world_data import (ROAD_HALF, VERSION, WORLD_SIZE, RESOURCES, TOWNS, REGIONS, MAX_PLAYERS,
                        SIDE_COLORS, AI_SIDES, STORY_LINE, POST, BODY_TIME, CAMP_PARTS,
                        BIG_TOWNS, START_STOCK, NODE_RESPAWN, LOOKS, GIVERS, GIVER_PLAN, MAX_ACTIVE_QUESTS, BUILDINGS, EVENTS, QUESTS, WEAPONS, ARMOR, POI_KINDS,
                        POST_COST, PRICES, BUILD_TIME, STORAGE_BASE, STORAGE_PER_WAREHOUSE,
                        WEATHER, WORLD_SCALE, MAX_LEVEL, XP, PERKS, SHOP_ITEMS, STORY_COINS, ITEMS, LOOT_ITEMS, CLOTHES, BACKPACKS, CAR_TANK, CARS, xp_to_next, max_hp, hero_look, SWAP_TIME, config)
from terrain import Terrain, town_buildings, resource_nodes, landmark_rect, RECT_CELL
from npc import NpcMixin
from vehicles import VehicleMixin
from camps import CampMixin

ROOT = Path(__file__).resolve().parent
SAVE_VERSION = 2
DISCOVERY_PORT = 8766
STAT_KEYS = ('harvest','build','event','explore','deliver','capture','aid','kills','loot','trade','hunt','mutants')
FSTAT_KEYS = ('kills','convoy','tribute','post','trade','capture')
CLAN_SIZE = 6
TRADE_RANGE = 260

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

class World(NpcMixin, VehicleMixin, CampMixin):
    def __init__(self, save_path=None, rng=None):
        self.lock = threading.RLock()
        self.rng = rng or random.SystemRandom()
        self.save_path = Path(save_path) if save_path else None
        self.players = {}
        self.elapsed = 0.0
        self.production_clock = 0.0
        self.save_clock = 0.0
        self.npc_clock = self.tower_clock = self.post_clock = self.convoy_clock = self.ai_clock = 0.0
        self.creature_clock = 0.0
        self.event_clock = 0.0
        self.towns = {}
        self.harvested = {}
        self.events_done = {}
        self.log = []
        self.seq = 0
        self.effects = []
        self.winner = None
        # A side is one player or one computer clan. Players live in camps they build themselves.
        self.sides = {}
        self.stocks = {}
        self.reputation = {}
        self.buildings = {}
        self.npcs = {}
        self.posts = {}
        self.airdrops = {}
        self.poi_state = {}
        self.weather = {'kind':'clear','until':300.0}
        self.truce = {'pairs':{},'proposals':[],'cooldown':{}}
        self.clans = {}
        self.offers = {}
        self.garrison_state = {}
        self.camps = {}
        self.bodies = {}
        self.story = {}
        self.fstats = {}
        self.ai_state = {}
        self.settings = {'ai':True}
        self.room_code = None
        self.dirty = False
        self.load_warning = None
        self.terrain = Terrain()
        self._make_world()
        if self.save_path and self.save_path.exists():
            self.load()
        for sid, name, color, town, fighter, method in AI_SIDES:
            if sid not in self.sides and self.towns[town]['owner'] is None:
                self.add_side(sid, name, color, ai={'fighter':fighter,'method':method}, town=town)
        for f in self.sides:
            if not self.story[f]['start']:
                self._story_start(f)

    # ---- sides ----------------------------------------------------------
    def add_side(self, sid, name, color, ai=None, town=None):
        """A side holds the towns it took and, for players, one camp it builds itself."""
        self.sides[sid] = {'id':sid,'name':name,'color':color,'camp':None,'ai':bool(ai),'clan':None,
                           'fighter':(ai or {}).get('fighter','raider'),'method':(ai or {}).get('method','assault')}
        # Computer clans do not gather by hand, so they start richer and scavenge in tick_ai.
        self.stocks[sid] = {k: v * (4 if ai else 1) for k, v in START_STOCK.items()}
        self.reputation[sid] = 0
        self.story[sid] = {'index':0,'flags':[],'start':{}}
        self.fstats[sid] = {k:0 for k in FSTAT_KEYS}
        if town:
            t = self.towns[town]
            t.update(owner=sid, loyalty=60, capture=None, shield=0.0, construct={}, fires={})
            for k in ('depot','house'):
                t['levels'][k] = max(1, t['levels'][k])
        self._story_start(sid)

    def release_side(self, sid):
        """A side that left for good gives its settlements back to their people."""
        for t in self.towns.values():
            if t['owner'] == sid:
                self._set_owner(t, None); t['loyalty'] = 45
        camp = self.camp_of(sid)
        if camp:
            self.abandon_camp(camp)
        for pid in [k for k, v in self.posts.items() if v['faction'] == sid]:
            del self.posts[pid]
        for nid in [k for k, n in self.npcs.items() if n['faction'] == sid]:
            del self.npcs[nid]
        for c in self.clans.values():
            if sid in c['members']: c['members'].remove(sid)
            if sid in c['invites']: c['invites'].remove(sid)
        for cid, c in list(self.clans.items()):
            if not c['members']:
                del self.clans[cid]
            elif c['leader'] == sid:
                c['leader'] = c['members'][0]
        self.offers = {k: o for k, o in self.offers.items() if sid not in (o['from_side'], o['to_side'])}
        for store in (self.sides, self.stocks, self.reputation, self.story, self.fstats, self.ai_state):
            store.pop(sid, None)

    def side_name(self, sid):
        return self.sides[sid]['name'] if sid in self.sides else 'Независимые'

    def capital(self, sid):
        """The side's most developed settlement: convoys bring cargo there."""
        owned = [t for t in self.towns.values() if t['owner'] == sid]
        return max(owned, key=lambda t: (sum(t['levels'].values()), t['id'])) if owned else None

    GameError = None   # set below, used by the mixins

    def best_level(self, sid, kind):
        return max([t['levels'][kind] for t in self.towns.values() if t['owner'] == sid] or [0])

    def allied(self, a, b):
        ca = self.sides.get(a, {}).get('clan'); cb = self.sides.get(b, {}).get('clan')
        return a == b or (ca is not None and ca == cb)

    def truce_between(self, a, b):
        """Clan mates and sides with a running truce do not fight each other."""
        if a != b and self.allied(a, b):
            return True
        return a != b and self.truce['pairs'].get('|'.join(sorted((a, b))), 0) > self.elapsed

    _dist = staticmethod(dist)

    def _make_world(self):
        for t in TOWNS:
            tid,name,x,y,region = t
            self.towns[tid] = {'id':tid,'name':name,'x':x,'y':y,'region':region,'r':self.terrain.towns[tid]['r'],'h':self.terrain.towns[tid]['h'],
                'owner':None,'base':False,'loyalty':45,
                'levels':{k:0 for k in BUILDINGS},
                'capture':None,'shield':0.0,'cooldowns':{},'intel':{},
                'construct':{},'cargo':{k:0.0 for k in RESOURCES},'fires':{}}
            for b in town_buildings(tid,x,y):
                self.buildings[b['id']]=b
                self.terrain.add_rect(b)
            lm=landmark_rect(tid,x,y)
            if lm:self.terrain.add_rect(lm)
        for poi in self.terrain.pois.values():
            for part in poi['parts']:
                if part['sprite']!='pump':self.terrain.add_rect(part)
        self.nodes = resource_nodes(self.terrain)
        # Two people with work on every square, three in big cities.
        self.givers = {}
        for i, tid in enumerate(self.towns):
            t = self.towns[tid]
            kinds = [GIVER_PLAN[i % len(GIVER_PLAN)], GIVER_PLAN[(i + 3) % len(GIVER_PLAN)]]
            if tid in BIG_TOWNS:
                kinds.append('radio')
            for k, kind in enumerate(kinds):
                a = .6 + k * 2.1
                gid = tid + ':' + kind
                spec = GIVERS[kind]
                self.givers[gid] = {'id':gid,'town':tid,'type':kind,'role':spec['role'],'look':spec['look'],'art':spec['art'],
                                    'name':spec['names'][(i + k) % len(spec['names'])],
                                    'x':round(t['x'] + math.cos(a) * 168),'y':round(t['y'] + math.sin(a) * 140)}

    def _notice(self, title, text='', faction=None, player=None, tone='info', skip=None):
        self.seq += 1
        self.log.append({'id':self.seq,'title':title,'text':text,'faction':faction,'player':player,'tone':tone,'skip':skip})
        self.log=self.log[-60:]

    def _public_player(self, p):
        out={k:p[k] for k in ('id','name','faction','x','y','angle','hp','stamina','vehicle','dead_until','gear','level','xp')}
        out['look']=hero_look(p['level'])
        # What the character is doing, for animation on every client.
        out['act']=p.get('act');out['reload']=p.get('reload_until',0);out['mag']=self._mag(p)
        clan=self.clans.get(self.sides.get(p['faction'],{}).get('clan'))
        out['tag']=clan['tag'] if clan else ''
        out['ride']=p.get('ride')
        out['max_hp']=max_hp(p['level'])
        car=p['car']
        out['car']={k:car.get(k,0) for k in ('x','y','angle','hp','wrecked_until','fuel')}
        out['car'].update(model=car.get('model',2),vx=round(car.get('vx',0),1),vy=round(car.get('vy',0),1),steer=round(car.get('steer',0),3),
                          brake=bool(car.get('brake')),slip=bool(car.get('slip')))
        out['shot']=p.get('shot',-10);out['busy']=p.get('busy',-10);out['moving']=bool(p['input'][0] or p['input'][1])
        out['sprint']=bool(p['input'][2])
        return out

    def _free_color(self,color,sid=None):
        used={s['color'] for k,s in self.sides.items() if k!=sid}
        if color in SIDE_COLORS and color not in used:return color
        return next((c for c in SIDE_COLORS if c not in used),SIDE_COLORS[len(self.sides)%len(SIDE_COLORS)])

    def join(self, name, faction=None, token=None, color=None):
        """Every player is a side of their own. The faction argument is ignored (kept for old clients).
        Everyone plays the same hero, whose look follows the level; the chosen colour tells players apart."""
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
            self.release_side(stale[0][1]['faction']);del self.players[stale[0][0]]
        color=self._free_color(color)
        token=secrets.token_urlsafe(32);pid=secrets.token_hex(6);sid='p_'+pid
        self.add_side(sid,name,color)
        p={'id':pid,'name':name,'faction':sid,
           'x':0.0,'y':0.0,'angle':0.0,
           'hp':100.0,'stamina':100.0,'vehicle':False,
           'car':self.new_car(0.0,0.0,0.0,20.0),
           'dead_until':0.0,'last_seen':now,'last_input':now,'input':[0,0,False],
           'aim':[0,1],'paused':False,'last_action':{},'receipts':OrderedDict(),
           'stats':{k:0 for k in STAT_KEYS},'gear':{'weapon':0,'armor':0,'clothes':0,'backpack':0},'level':1,'xp':0,
           'coins':0,'weapons':[0],'items':{'water':1,'crackers':1,'ammo9':16,'cloth':2,'planks':2},'mags':{'0':WEAPONS[0]['mag']},
           'food':70.0,'water':70.0,'warmth':90.0,'bleeding':False,'sick':0.0,'warned':[],
           'visited':[],'quests':[],'quest_serial':0,'completed':0,'pending':None}
        self._place_randomly(p)
        self.players[token]=p
        self._notice(name+' присоединился','')
        self.dirty=True
        return token

    def _spawn_point(self,p):
        """A random roadside spot away from enemies; every player starts somewhere different."""
        f=p['faction']
        enemies=[o for o in self.players.values() if o is not p and o['faction']!=f]
        for attempt in range(80):
            ax,ay,bx,by,a,b=self.rng.choice(self.terrain.road_segments)
            u=self.rng.uniform(.12,.88);length=math.hypot(bx-ax,by-ay) or 1
            nx,ny=-(by-ay)/length,(bx-ax)/length;side=self.rng.choice((-1,1))*self.rng.uniform(ROAD_HALF+30,ROAD_HALF+110)
            x=ax+(bx-ax)*u+nx*side;y=ay+(by-ay)*u+ny*side
            if not self.terrain.free_spot(x,y,30) or self.terrain.water(x,y,40):continue
            pos={'x':x,'y':y}
            if any(dist(o,pos)<1500 for o in enemies):continue
            if any(t['owner'] not in (None,f) and dist(t,pos)<1000 for t in self.towns.values()):continue
            if any(n['hp']>0 and n['type']!='convoy' and self.hostile(n,p) and dist(n,pos)<700 for n in self.npcs.values()):continue
            # Leave room for the car beside the player.
            for k in range(8):
                ang=k*math.pi/4;cx=x+math.cos(ang)*70;cy=y+math.sin(ang)*70
                if self.terrain.free_spot(cx,cy,24) and not self.terrain.water(cx,cy,30):
                    return x,y,cx,cy
        t=self.rng.choice(list(self.towns.values()))
        return t['x']+t['r']+120,t['y']+80,t['x']+t['r']+120,t['y']+160

    def _place_randomly(self,p):
        x,y,cx,cy=self._spawn_point(p)
        p['x']=x;p['y']=y;p['vehicle']=False
        # The tank is the player's own: it is not refilled for free, only kept from running completely dry.
        fuel=max(10.0,p['car'].get('fuel',30.0)) if isinstance(p.get('car'),dict) else 30.0
        model=p['car'].get('model') if isinstance(p.get('car'),dict) else None
        p['car']=self.new_car(cx,cy,self.rng.uniform(-math.pi,math.pi),fuel,model)
        near=min(self.towns.values(),key=lambda t:dist(t,p))
        self._notice('Ты очнулся у дороги','Рядом: '+near['name']+'. Лагеря у тебя нет: построй его (L) или займи пустой дом.',player=p['id'])

    def max_hp(self,p):
        return max_hp(p['level'])

    def has_perk(self,p,level):
        return p['level']>=level

    def gain_xp(self,p,reason):
        """Award experience on the host; levels raise health and damage and unlock perks."""
        if 'stats' not in p or p['level']>=MAX_LEVEL:return
        p['xp']+=XP.get(reason,0)
        while p['level']<MAX_LEVEL and p['xp']>=xp_to_next(p['level']):
            p['xp']-=xp_to_next(p['level']);p['level']+=1
            p['hp']=self.max_hp(p)
            perk=next((k for k in PERKS if k['level']==p['level']),None)
            self.effects.append({'id':secrets.token_hex(4),'kind':'levelup','x':p['x'],'y':p['y'],'ex':p['x'],'ey':p['y'],'until':self.elapsed+1.5,'faction':p['faction'],'player':p['id']})
            self._notice('Новый уровень: '+str(p['level']),'Здоровье '+str(int(self.max_hp(p)))+', урон +'+str(3*(p['level']-1))+'%.'+(' Навык: '+perk['name']+' — '+perk['desc'] if perk else ''),player=p['id'])
            self._notice(p['name']+' достиг уровня '+str(p['level']),'',faction=p['faction'],skip=p['id'])
        if p['level']>=MAX_LEVEL:p['xp']=0

    def _quest(self,p,tpl,giver):
        q=copy.deepcopy(tpl)
        p['quest_serial']+=1
        q['id']=p['id']+'-q'+str(p['quest_serial'])
        q['start']=p['stats'][q['kind']]
        q['from']=giver['name']+', '+self.towns[giver['town']]['name']
        if q['kind']=='deliver':
            others=sorted((t for t in self.towns.values() if t['id']!=giver['town']),key=lambda t:dist(t,self.towns[giver['town']]))
            target=self.rng.choice(others[:4])
            q['town']=target['id']; q['text']+=' Место: '+target['name']+'.'
        return q

    def _giver_near(self,p,gid):
        g=self.givers.get(str(gid))
        if not g: raise GameError('Здесь никого нет.')
        if p['vehicle']: raise GameError('Выйди из машины, чтобы поговорить.')
        self._near(p,g,150)
        return g

    def dialog(self,p,g):
        """What a person on the square says and offers this player."""
        spec=GIVERS[g['type']];t=self.towns[g['town']]
        fill=lambda line:line.format(town=t['name'],region=t['region'],name=p['name'])
        pick=lambda lines:fill(lines[int(self.elapsed//30+len(g['id']))%len(lines)])
        mine=[q for q in p['quests'] if q['giver']==g['type']]
        done=[q for q in mine if p['stats'][q['kind']]-q['start']>=q['target']]
        active={q['kind'] for q in p['quests']}
        offers=[] if len(p['quests'])>=MAX_ACTIVE_QUESTS else \
            [{k:tpl[k] for k in ('kind','name','text','intro','coins','reward','target')} for tpl in QUESTS if tpl['giver']==g['type'] and tpl['kind'] not in active]
        out={'giver':{k:g[k] for k in ('id','name','role','type','look','art','town')},'greet':pick(spec['greet']),'lore':pick(spec['lore']),
             'offers':offers,'full':len(p['quests'])>=MAX_ACTIVE_QUESTS,
             'turnins':[{'id':q['id'],'name':q['name'],'coins':q.get('coins',0),'reward':q['reward'],'done':q.get('done','')} for q in done],
             'progress':[{'id':q['id'],'name':q['name'],'n':max(0,p['stats'][q['kind']]-q['start']),'target':q['target']} for q in mine if q not in done]}
        if g['type']=='radio':
            f=p['faction'];c=self._chapter(f)
            out['story']={'chapter':c,'ready':self._story_ready(f),'progress':self._story_progress(f)}
        return out

    def reset(self):
        """A new game from scratch. The old save stays next to the new one as a dated backup."""
        lock,rng,path,code,settings=self.lock,self.rng,self.save_path,self.room_code,dict(self.settings)
        backup=None
        if path and path.exists():
            backup=path.with_name(path.stem+'-'+time.strftime('%Y%m%d-%H%M%S')+'.bak'+path.suffix)
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

    def storage(self,f):
        return STORAGE_BASE+STORAGE_PER_WAREHOUSE*sum(t['levels']['warehouse'] for t in self.towns.values() if t['owner']==f)

    def _can_pay(self,f,cost):
        return all(self.stocks[f].get(k,0)+1e-6>=v for k,v in cost.items())

    def _pay(self,f,cost):
        if not self._can_pay(f,cost):
            raise GameError('Не хватает ресурсов фракции.')
        for k,v in cost.items():
            self.stocks[f][k]-=v

    def _reward(self,f,reward):
        cap=self.storage(f)
        for k,v in reward.items():
            old=self.stocks[f].get(k,0)
            # Stock above the cap (old saves, refunds) is kept but never grows further.
            self.stocks[f][k]=clamp(old+v,0,max(cap,old) if v>0 else 99999)

    def _near(self,p,obj,r=180):
        if dist(p,obj)>r:
            raise GameError('Подойди ближе к цели.')

    def _cooldown(self,p,key,seconds):
        if self.elapsed-p['last_action'].get(key,-10000)<seconds:
            raise GameError('Подожди перед следующей попыткой.')
        p['last_action'][key]=self.elapsed

    def _town_action(self,p,tid):
        if tid not in self.towns:
            raise GameError('Поселение не найдено.')
        t=self.towns[tid]
        self._near(p,t,170)
        if p['vehicle']:
            raise GameError('Сначала выйди из машины: F.')
        return t

    def build_cost(self,t,kind):
        level=t['levels'][kind]
        factor=[1,1.8,2.8][min(level,2)]
        return {k:math.ceil(v*factor) for k,v in BUILDINGS[kind]['cost'].items()}

    def economy(self,t):
        population=(4 if t['levels']['depot'] else 0)+8*t['levels']['house']
        free=population; active={}
        for k in ('farm','sawmill','quarry','workshop','garage','warehouse'):
            req=BUILDINGS[k]['workers']*t['levels'][k]
            active[k]=bool(req and req<=free)
            if active[k]: free-=req
        return population,population-free,active

    def chance_for(self,f,t,method,allies,weapon):
        levels=t['levels']
        intel=t['intel'].get(f,{})
        bonus=intel.get('bonus',0) if intel.get('until',0)>self.elapsed else 0
        defense=levels['guard']*12+levels['depot']*3+(t['loyalty']*.15 if t['owner'] else 0)
        radio=self.best_level(f,'radio')*5 if f in self.sides else 0
        if method=='scout': return 85
        if method in ('intimidate','gift'): return 80 if method=='intimidate' else 90
        if method=='talk': value=66+self.reputation[f]*.15+radio+bonus-defense+(5 if self.flag(f,'secret_freq') else 0)
        elif method=='bribe': value=72+bonus+radio-defense*.8
        elif method=='raid': value=58+max(0,allies-1)*10+weapon*5-levels['guard']*10-levels['depot']*3
        else: value=65+max(0,allies-1)*12+weapon*5+bonus-defense+(8 if self.flag(f,'iron_hand') else 0)
        return int(clamp(value,10,95))

    def chance(self,p,t,method):
        f=p['faction']
        allies=sum(1 for o in self.players.values() if o['faction']==f and o['hp']>0 and dist(o,t)<240 and time.monotonic()-o['last_seen']<8)
        allies+=sum(1 for n in self.npcs.values() if n['faction']==f and n['hp']>0 and n['type'] in ('ranger','raider') and dist(n,t)<240)
        value=self.chance_for(f,t,method,allies,p['gear']['weapon'])
        if self.has_perk(p,25) and method in ('talk','bribe','assault'):value=min(95,value+5)
        return value

    def town_view(self,p,t,guards=None):
        population,workers,active=self.economy(t)
        result=copy.deepcopy(t)
        result.pop('intel',None)
        result.update(population=population,workers=workers,active=active)
        result['intel']=t['intel'].get(p['faction'],{}).get('bonus',0) if t['intel'].get(p['faction'],{}).get('until',0)>self.elapsed else 0
        # Chances are worked out only for settlements close by: with 25 players this is the costly part.
        result['chances']={m:self.chance(p,t,m) for m in ('talk','bribe','assault','scout','raid')} if dist(p,t)<1400 else {}
        result['guards']=guards.get(t['id'],0) if guards is not None else self.garrison_count(t)
        result['event_ready']=self.elapsed>=self.events_done.get(t['id']+':'+p['faction'],0)
        return result

    def snapshot(self,token,full=True):
        p=self.player(token); f=p['faction']; now=time.monotonic()
        me=self._public_player(p)
        for k in ('stats','quests','completed','visited','pending','coins','weapons','items','food','water','warmth','bleeding','sick'):
            me[k]=copy.deepcopy(p[k])
        story=self.story[f]; chapter=self._chapter(f)
        out={'version':VERSION,'stamp':time.monotonic(),'time':round(self.elapsed,2),'me':me,
                'players':[self._public_player(o) for o in self.players.values() if now-o['last_seen']<12 or o is p],
                'stock':{k:round(v,2) for k,v in self.stocks[f].items()},'reputation':round(self.reputation[f],1),
                'storage':self.storage(f),

                'npcs':[self.npc_view(n) for n in self.npcs.values() if dist(n,p)<2600 or (n['type']=='convoy' and n['faction']==f)],
                'posts':[{k:o[k] for k in ('id','faction','x','y','hp','name')} for o in self.posts.values()],
                'airdrops':list(self.airdrops.values()),
                'loot':{pid:st.get(f,0) for pid,st in self.poi_state.items() if st.get(f,0)>self.elapsed},
                'weather':self.weather,
                'camps':[self.camp_view(c,p) for c in self.camps.values()],
                'bodies':[b for b in self.bodies.values() if abs(b['x']-p['x'])<5000 and abs(b['y']-p['y'])<5000],
                'sides':{sid:{'name':s['name'],'color':s['color'],'camp':s.get('camp'),'ai':s['ai'],'clan':s.get('clan'),
                              'towns':sum(1 for t in self.towns.values() if t['owner']==sid)} for sid,s in self.sides.items()},
                'clans':{cid:{k:c[k] for k in ('id','name','tag','leader','members','color')} for cid,c in self.clans.items()},
                'invites':[cid for cid,c in self.clans.items() if f in c['invites']],
                'offers':[self.offer_view(o) for o in self.offers.values() if o['until']>self.elapsed and p['id'] in (o['from'],o['to'])],
                'truce':{'pairs':{g:self.truce['pairs'].get('|'.join(sorted((f,g))),0) for g in self.sides if g!=f},
                         'proposals':[x for x in self.truce['proposals'] if x['until']>self.elapsed and f in (x['from'],x['to'])]},
                'story':{'index':story['index'],'flags':story['flags'],'chapter':chapter,'ready':self._story_ready(f),
                         'progress':self._story_progress(f)},
                'fstats':self.fstats[f],'ai':{g:self.ai_faction(g) for g in self.sides},
                'messages':[e for e in self.log if (e['faction'] in (None,f)) and (e['player'] in (None,p['id'])) and e.get('skip')!=p['id']],
                'effects':[e for e in self.effects if abs(e['x']-p['x'])<2600 and abs(e['y']-p['y'])<2000][-40:],'winner':self.winner,'load_warning':self.load_warning,'full':full}
        if full:
            # Light snapshots skip settlements: they change slowly, characters move fast.
            guards={}
            for n in self.npcs.values():
                job=n.get('job') or {}
                if n['hp']>0 and job.get('kind')=='garrison':guards[job['town']]=guards.get(job['town'],0)+1
            out['towns']={k:self.town_view(p,t,guards) for k,t in self.towns.items()}
            out['harvested']={k:v for k,v in self.harvested.items() if v>self.elapsed}
        return out

    # ---- story ----------------------------------------------------------
    def _chapter(self,f):
        chapters=STORY_LINE;i=self.story[f]['index']
        return chapters[i] if i<len(chapters) else None

    def _story_start(self,f):
        self.story[f]['start']=dict(self.fstats[f])

    def _story_progress(self,f):
        c=self._chapter(f)
        if not c:return [1,1]
        g=c['goal'];kind=g['kind']
        if kind=='visit':
            done=any(g['town'] in p['visited'] for p in self.players.values() if p['faction']==f)
            return [int(done),1]
        if kind=='building':return [min(g['level'],self.best_level(f,g['building'])),g['level']]
        if kind=='towns':return [min(g['target'],sum(1 for t in self.towns.values() if t['owner']==f)),g['target']]
        if kind=='victory':return [int(self.winner==f),1]
        key={'convoy':'convoy','tribute':'tribute','post':'post','kills':'kills'}[kind]
        return [min(g['target'],self.fstats[f][key]-self.story[f]['start'].get(key,0)),g['target']]

    def _story_ready(self,f):
        c=self._chapter(f)
        if not c or not c['choices']:return False
        n,target=self._story_progress(f)
        return n>=target

    # ---- commands -------------------------------------------------------
    def command(self,token,data):
        p=self.player(token)
        op=data.get('op')
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
            raise GameError('Ты приходишь в себя. Подожди несколько секунд.')
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
        if isinstance(result,dict) and (result.get('quiet') or result.get('event') or result.get('dialog')) and op!='shoot':return None
        if op=='harvest':
            n=self.nodes.get(str(data.get('id')))
            return {'wood':'chop','stone':'mine','metal':'mine'}.get(n['kind'],'gather') if n else None
        if op in ('build','extinguish','repair','craft'):return 'hammer'
        if op in ('loot','airdrop','post','cook','search_house','loot_body','stash_put','stash_take'):return 'search'
        if op in ('drink','canteen'):return 'drink' if op=='drink' else 'eat'
        if op=='heal':return 'bandage'
        if op=='use':
            item=data.get('item')
            return 'drink' if item in ('water','tea') else 'bandage' if item in ('bandage','medkit','antibiotics') else 'eat'
        return None

    def _reload(self,p):
        """Fill the magazine from the backpack; returns how many rounds went in."""
        w=p['gear']['weapon'];weapon=WEAPONS[w];ammo=weapon['ammo_item']
        need=weapon['mag']-self._mag(p);n=min(need,p['items'].get(ammo,0))
        if n<=0:return 0
        self.take_items(p,{ammo:n});p['mags'][str(w)]=self._mag(p)+n
        p['reload_until']=self.elapsed+weapon['reload'];p['act']={'kind':'reload','at':round(self.elapsed,2)}
        return n

    def _respawn_ammo(self,p):
        """Coming back after a death: a full magazine and a couple more in the backpack for the gun in hand."""
        w=p['gear']['weapon'];weapon=WEAPONS[w]
        p.setdefault('mags',{})[str(w)]=weapon['mag'];p['reload_until']=0
        spare=self.give_item(p,weapon['ammo_item'],int(clamp(weapon['mag']*2,6,30)))
        self._notice('Патроны с собой',weapon['name']+': полный магазин'+(' и '+str(spare)+' в рюкзаке' if spare else '')+'.',player=p['id'])

    def _mag(self,p):
        w=p['gear']['weapon'];mags=p.setdefault('mags',{})
        return mags.get(str(w),WEAPONS[w]['mag'])

    def _act(self,p,op,data):
        f=p['faction']
        if op=='harvest':
            n=self.nodes.get(str(data.get('id')))
            if not n: raise GameError('Ресурс не найден.')
            self._near(p,n,70)
            if p['vehicle']: raise GameError('Выйди из машины, чтобы собрать ресурсы.')
            if self.harvested.get(n['id'],0)>self.elapsed: raise GameError('Здесь пока нечего собирать. Запасы восстановятся позже.')
            self._cooldown(p,'harvest',.7)
            amount=n['amount']+(2 if self.has_perk(p,5) else 0)
            self._reward(f,{n['kind']:amount}); self.harvested[n['id']]=self.elapsed+NODE_RESPAWN
            p['stats']['harvest']+=1;self.gain_xp(p,'harvest')
            extra=''
            mat={'wood':'planks','metal':'scrap','food':'herbs'}.get(n['kind'])
            if mat and self.rng.random()<.6 and self.give_item(p,mat,self.rng.randint(1,2)):extra=' · '+ITEMS[mat]['name'].lower()+' в рюкзак'
            if n['kind']=='food' and self.rng.random()<.25 and self.give_item(p,self.rng.choice(('canned','crackers','water'))):extra+=' · еда в рюкзак'
            if n['kind']=='fuel' and self.rng.random()<.35 and self.give_item(p,'canister'):extra=' · канистра в рюкзак'
            return {'title':'+'+str(amount)+' · '+RESOURCES[n['kind']]+extra,'success':True}
        if op=='build':
            b=self.buildings.get(str(data.get('id')))
            if not b: raise GameError('Здание не найдено.')
            self._near(p,b,155)
            if p['vehicle']: raise GameError('Выйди из машины, чтобы восстановить здание.')
            t=self.towns[b['town']]; k=b['kind']; level=t['levels'][k]
            if t['owner']!=f: raise GameError('Сначала установи контроль над поселением на его площади.')
            if t['capture']: raise GameError('Строительство приостановлено: идёт захват.')
            if k in t['construct']: raise GameError('Здесь уже идут работы. Стой рядом, чтобы ускорить их.')
            if level>=3: raise GameError('Достигнут максимальный уровень.')
            if k!='depot' and level>=t['levels']['depot']: raise GameError('Сначала улучши опорный пункт.')
            if len(t['construct'])>=2: raise GameError('В поселении уже две стройки. Дождись окончания одной из них.')
            population,workers,active=self.economy(t)
            if level>=1 and population-workers<1: raise GameError('Нет свободных рабочих для стройки. Восстанови жилой дом.')
            self._pay(f,self.build_cost(t,k));self.start_construction(t,k,p)
            p['stats']['build']+=1;self.gain_xp(p,'build')
            return {'title':BUILDINGS[k]['name']+': работы начаты','text':'Уровень '+str(level+1)+' через '+str(BUILD_TIME[level])+' сек. Союзники рядом ускоряют стройку.','success':True}
        if op=='vehicle':
            self._cooldown(p,'vehicle',.4)
            car=p['car']
            if p.get('ride'):
                self.unboard(p)
                return {'title':'Ты вышел из машины','quiet':True}
            if p['vehicle']:
                if math.hypot(car.get('vx',0),car.get('vy',0))>80: raise GameError('Сначала останови машину: S — тормоз, Shift — ручник.')
                spot=self.car_exit_spot(p)
                if not spot: raise GameError('Двери не открыть: рядом стена. Отъедь немного.')
                p['x'],p['y']=spot;p['vehicle']=False;car.update(vx=0.0,vy=0.0,steer=0.0,brake=False,slip=False)
                return {'title':'Ты вышел из машины','quiet':True}
            if dist(p,car)>self.car_spec(p)['len']*.6+30:
                q=self.board(p)
                if q: return {'title':'Ты пассажир · '+self.car_spec(q)['name'],'text':'Ведёт '+q['name']+'. F — выйти, когда машина остановится.','quiet':True}
            if car.get('wrecked_until',0)>self.elapsed: raise GameError('Машина разбита. Её скоро отбуксируют к лагерю.')
            self._near(p,car,self.car_spec(p)['len']*.6+30)
            p['vehicle']=True;p['x']=car['x'];p['y']=car['y'];p['angle']=car['angle']
            return {'title':self.car_spec(p)['name'],'text':'W — газ, S — тормоз и задний ход, A/D — руль, Shift — ручник, F — выйти.','quiet':True}
        if op=='repair' and data.get('kit'):
            if p['items'].get('repairkit',0)<1: raise GameError('Нет ремкомплекта. Его продают в магазине на площади.')
            if p['vehicle'] or dist(p['car'],p)>110: raise GameError('Подойди к своей машине пешком.')
            if p['car'].get('wrecked_until',0)>self.elapsed: raise GameError('Машина разбита, её отбуксируют к лагерю.')
            if p['car'].get('hp',100)>=100: raise GameError('Машина исправна.')
            p['items']['repairkit']-=1;p['car']['hp']=100.0;left=p['items']['repairkit']
            if not left:del p['items']['repairkit']
            return {'title':'Машина отремонтирована','text':'Ремкомплектов осталось: '+str(left),'success':True}
        if op=='repair':
            g=[b for b in self.buildings.values() if b['kind']=='garage' and self.towns[b['town']]['owner']==f and self.towns[b['town']]['levels']['garage']>0 and dist(b,p)<200]
            if not g: raise GameError('Ремонт возможен у своего восстановленного гаража.')
            if dist(p['car'],p)>220: raise GameError('Подгони машину к гаражу.')
            if p['car'].get('hp',100)>=100: raise GameError('Машина исправна.')
            self._pay(f,{'metal':4});p['car']['hp']=100.0
            return {'title':'Машина отремонтирована','text':'−4 металла','success':True}
        if op=='heal':
            if p['hp']>=self.max_hp(p) and not p['bleeding']: raise GameError('Ты не ранен.')
            for item in (('bandage','medkit') if p['bleeding'] else ('medkit',)):
                if p['items'].get(item,0)>0:
                    self._cooldown(p,'heal',3);return self._use(p,item)
            # No bandage: tear up whatever is at hand. It still stops the bleeding.
            medic=self.has_perk(p,10);cost=3 if medic else 5;amount=45 if medic else 35
            if p['bleeding'] and not self._can_pay(f,{'food':cost}) and p['items'].get('cloth',0)>0:
                self._cooldown(p,'heal',3);self.take_items(p,{'cloth':1});p['bleeding']=False
                return {'title':'Перевязка тряпкой','text':'Кровь остановлена, −1 ткань.','success':True}
            self._cooldown(p,'heal',6);self._pay(f,{'food':cost});p['hp']=min(self.max_hp(p),p['hp']+amount)
            stopped=p['bleeding'];p['bleeding']=False
            return {'title':'Перевязка','text':'Здоровье +'+str(amount)+', −'+str(cost)+' припасов'+(' · кровь остановлена' if stopped else ''),'success':True}
        if op=='craft':
            item=data.get('item');tier=data.get('tier')
            table={'weapon':WEAPONS,'armor':ARMOR}.get(item)
            if table is None or not isinstance(tier,int) or not 1<=tier<len(table) or 'workshop' not in table[tier]: raise GameError('Этот предмет не делают в мастерской.')
            ws=[b for b in self.buildings.values() if b['kind']=='workshop' and self.towns[b['town']]['owner']==f and dist(b,p)<170]
            if not ws: raise GameError('Изготовление возможно у мастерской своего поселения.')
            level=max(self.towns[b['town']]['levels']['workshop'] for b in ws)
            if level<table[tier]['workshop']: raise GameError('Нужна мастерская уровня '+str(table[tier]['workshop'])+'.')
            if (tier in p['weapons']) if item=='weapon' else p['gear'][item]>=tier: raise GameError('У тебя уже есть это или лучше.')
            self._pay(f,table[tier]['cost']);p['gear'][item]=tier;self.gain_xp(p,'craft')
            if item=='weapon':p['weapons'].append(tier)
            return {'title':table[tier]['name'],'text':'Снаряжение готово.','success':True}
        if op=='event_open':
            t=self._town_action(p,str(data.get('town')))
            key=t['id']+':'+f
            if self.events_done.get(key,0)>self.elapsed: raise GameError('Здесь пока тихо. Следующее событие появится через несколько минут.')
            if p['pending'] and p['pending']['town']==t['id']: return {'event':p['pending']}
            idx=(list(self.towns).index(t['id'])+int(self.elapsed//240))%len(EVENTS)
            event=copy.deepcopy(EVENTS[idx]); event.update(id=secrets.token_hex(6),town=t['id'])
            for option in event['options']:
                option['chance']=int(clamp(option['chance'],10,95))
            p['pending']=event
            return {'event':event}
        if op=='event_choice':
            ev=p['pending']
            if not ev or ev['id']!=data.get('id'): raise GameError('Событие уже завершено.')
            t=self._town_action(p,ev['town']); key=t['id']+':'+f
            if self.events_done.get(key,0)>self.elapsed: raise GameError('Союзник уже завершил это событие.')
            choice=data.get('choice')
            if not isinstance(choice,int) or not 0<=choice<len(ev['options']): raise GameError('Выбери решение.')
            option=ev['options'][choice]
            self._pay(f,option['cost'])
            roll=self.rng.randint(1,100); ok=roll<=option['chance']
            self.events_done[key]=self.elapsed+180; p['pending']=None
            if ok:
                self._reward(f,option['reward']); p['stats']['event']+=1;self.gain_xp(p,'event')
                self.reputation[f]=clamp(self.reputation[f]+option.get('rep',0),-100,100)
                if t['owner']==f: t['loyalty']=clamp(t['loyalty']+option.get('rep',0)+option.get('loyalty',0),0,100)
                elif option.get('loyalty'): t['loyalty']=clamp(t['loyalty']+option['loyalty'],0,100)
                p['hp']=min(self.max_hp(p),p['hp']+option.get('heal',0))
                if option.get('intel'): t['intel'][f]={'bonus':option['intel'],'until':self.elapsed+240}
            else:
                self._damage(p,option['risk']); self.reputation[f]=max(-100,self.reputation[f]-2);self.gain_xp(p,'event_fail')
            return {'title':'Решение сработало' if ok else 'Неудача','success':ok,'roll':roll,'chance':option['chance'],
                    'text':('Получено: '+self.resource_text(option['reward']) if ok else 'Затраченные ресурсы потеряны. Здоровье −'+str(option['risk']))+' · Бросок '+str(roll)+' из 100.'}
        if op in ('capture','scout','aid','deliver','tax','trade','raid'):
            t=self._town_action(p,str(data.get('town')))
            if op=='deliver':
                q=next((q for q in p['quests'] if q['kind']=='deliver' and q.get('town')==t['id'] and p['stats']['deliver']-q['start']<q['target']),None)
                if not q: raise GameError('Для этого поселения нет активного задания на доставку.')
                self._pay(f,{'food':6}); p['stats']['deliver']+=1;self.gain_xp(p,'deliver')
                self.reputation[f]=min(100,self.reputation[f]+4)
                return {'title':'Припасы доставлены','text':'Вернись к торговцу за оплатой.','success':True}
            if op=='trade':
                return self._trade(p,t,data)
            if op=='aid':
                if t['owner']!=f: raise GameError('Поддерживать можно своё поселение.')
                key='aid:'+f
                if self.elapsed<t['cooldowns'].get(key,0): raise GameError('Жители ещё распределяют предыдущую помощь.')
                self._pay(f,{'food':8});t['loyalty']=min(100,t['loyalty']+14)
                p['stats']['aid']+=1;self.reputation[f]=min(100,self.reputation[f]+3);self.gain_xp(p,'aid')
                t['cooldowns'][key]=self.elapsed+40
                return {'title':'Жители получили помощь','text':'Лояльность +14.','success':True}
            if op=='tax':
                if t['owner']!=f: raise GameError('Дань собирают только в своих поселениях.')
                if self.elapsed<t['cooldowns'].get('tax',0): raise GameError('Дань уже собрана. Подожди минуту.')
                penalty=12 if self.flag(f,'fair_share') else 18
                bonus=4 if self.flag(f,'iron_hand') else 0
                t['cooldowns']['tax']=self.elapsed+60;t['loyalty']-=penalty
                self._reward(f,{'metal':12+bonus,'food':12});self.fstats[f]['tribute']+=1;self.gain_xp(p,'tax')
                if t['loyalty']<20:
                    self._set_owner(t,None);t['loyalty']=45
                    self._notice('Бунт в поселении',t['name']+' снова независимо.')
                return {'title':'Дань собрана','text':'+'+str(12+bonus)+' металла и +12 припасов; лояльность −'+str(penalty)+'. При лояльности ниже 20 поселение восстаёт.'}
            if op=='raid':
                return self._raid(p,t)
            if t['owner']==f: raise GameError('Поселение уже принадлежит твоей стороне.')
            if t['owner'] and self.truce_between(f,t['owner']): raise GameError('С хозяином поселения действует перемирие или вы в одном клане.')
            if self.garrison_alive(t,f): raise GameError('Площадь держат '+('мародёры' if not t['owner'] else 'охранники '+self.side_name(t['owner']))+'. Сначала перебей их.')
            if t['capture']: raise GameError('Уже идёт захват. Помоги удержать площадь.')
            if t['shield']>self.elapsed: raise GameError('После смены владельца поселение защищено две минуты.')
            cooldown_key='attempt:'+f
            if t['cooldowns'].get(cooldown_key,0)>self.elapsed: raise GameError('Подготовка новой попытки ещё не завершена.')
            method=str(data.get('method')) if op=='capture' else str(data.get('method') or 'scout')
            costs={'scout':{'food':3},'intimidate':{'metal':6},'gift':{'food':10},'talk':{'food':12,'wood':8},'bribe':{'food':18,'fuel':8},'assault':{'metal':12,'food':6}}
            prep=method in ('scout','intimidate','gift')
            if method not in costs or (op=='scout')!=prep: raise GameError('Неизвестный способ захвата.')
            chance=self.chance(p,t,method);self._pay(f,costs[method])
            roll=self.rng.randint(1,100);ok=roll<=chance
            t['cooldowns'][cooldown_key]=self.elapsed+(12 if prep else 35)
            if ok and prep:
                t['intel'][f]={'bonus':20 if method=='scout' else 15,'until':self.elapsed+240}
                if method=='intimidate':t['loyalty']=max(0,t['loyalty']-10)
                if method=='gift':self.reputation[f]=min(100,self.reputation[f]+2);t['loyalty']=min(100,t['loyalty']+5)
                text={'scout':'+20% к шансу захвата на 4 минуты.','intimidate':'+15% к шансу на 4 минуты, лояльность жителей −10.','gift':'+15% к шансу на 4 минуты, репутация +2.'}[method]
                return {'title':{'scout':'Разведданные получены','intimidate':'Жители напуганы','gift':'Гуманитарная помощь принята'}[method],'text':text,'success':True,'chance':chance,'roll':roll}
            if ok:
                self.begin_capture(t,f,method)
            elif method=='assault': self._damage(p,25)
            return {'title':('Удерживай площадь 30 секунд' if not prep else 'Подготовка не удалась') if ok else 'Попытка не удалась',
                    'text':('Нужен хотя бы один союзник пешком в круге. Враги рядом останавливают захват.' if ok else 'Ресурсы потрачены; повторная попытка станет доступна позже.'),
                    'success':ok,'chance':chance,'roll':roll}
        if op=='talk':
            g=self._giver_near(p,data.get('giver'))
            return {'dialog':self.dialog(p,g),'quiet':True}
        if op=='quest_accept':
            g=self._giver_near(p,data.get('giver'))
            tpl=next((q for q in QUESTS if q['giver']==g['type'] and q['kind']==data.get('kind')),None)
            if not tpl: raise GameError('Такой работы здесь нет.')
            if len(p['quests'])>=MAX_ACTIVE_QUESTS: raise GameError('У тебя уже '+str(MAX_ACTIVE_QUESTS)+' задания. Сначала закончи что-нибудь.')
            if any(q['kind']==tpl['kind'] for q in p['quests']): raise GameError('Похожее дело у тебя уже есть.')
            q=self._quest(p,tpl,g);p['quests'].append(q)
            return {'title':'Задание: '+q['name'],'text':q['text']+' Сдать — '+GIVERS[g['type']]['role'].lower()+' в любом поселении.','success':True,'dialog':self.dialog(p,g)}
        if op=='quest_turnin':
            g=self._giver_near(p,data.get('giver'))
            q=next((q for q in p['quests'] if q['id']==data.get('id')),None)
            if not q or q['giver']!=g['type']: raise GameError('Это задание сдают другому человеку.')
            if p['stats'][q['kind']]-q['start']<q['target']: raise GameError('Задание ещё не выполнено.')
            self._reward(f,q['reward']);self.reputation[f]=min(100,self.reputation[f]+2)
            coins=q.get('coins',20);p['coins']+=coins;p['completed']+=1
            p['quests'].remove(q);self.gain_xp(p,'quest')
            return {'title':'Задание сдано','text':g['name']+': «'+q.get('done','Спасибо.')+'» +'+str(coins)+' монет · '+self.resource_text(q['reward']),'success':True,'dialog':self.dialog(p,g)}
        if op=='quest_drop':
            q=next((q for q in p['quests'] if q['id']==data.get('id')),None)
            if not q: raise GameError('Задание не найдено.')
            p['quests'].remove(q)
            return {'title':'Задание брошено','text':q['name'],'success':False}
        if op=='story_choice':
            if not any(g['type']=='radio' and dist(g,p)<160 for g in self.givers.values()): raise GameError('Главу сдают радисту в крупном городе.')
            if not self._story_ready(f): raise GameError('Глава ещё не завершена.')
            c=self._chapter(f);choice=data.get('choice')
            if not isinstance(choice,int) or not 0<=choice<len(c['choices']): raise GameError('Выбери решение.')
            opt=c['choices'][choice]
            if opt.get('cost'):self._pay(f,opt['cost'])
            self._reward(f,opt.get('reward',{}));self.reputation[f]=clamp(self.reputation[f]+opt.get('rep',0),-100,100)
            if opt.get('flag'):self.story[f]['flags'].append(opt['flag'])
            if opt.get('loyalty'):
                for t in self.towns.values():
                    if t['owner']==f:t['loyalty']=clamp(t['loyalty']+opt['loyalty'],0,100)
            self.story[f]['index']+=1;self._story_start(f);self.gain_xp(p,'story')
            p['coins']+=STORY_COINS
            self._notice('Глава завершена: '+c['title'],p['name']+' выбрал: '+opt['name'],faction=f)
            return {'title':opt['name'],'text':opt['text']+' +'+str(STORY_COINS)+' монет.','success':True}
        if op=='shoot':
            if p['vehicle']: raise GameError('Стрелять можно только пешком.')
            weapon=WEAPONS[p['gear']['weapon']]
            if p.get('reload_until',0)>self.elapsed: raise GameError('Перезарядка.')
            if self._mag(p)<=0:
                self._reload(p)
                raise GameError('Магазин пуст.')
            self._cooldown(p,'shoot',weapon['cd']*.92)
            left=self._mag(p)-1;p['mags'][str(p['gear']['weapon'])]=left
            # The last round in the magazine starts an automatic reload if there is ammo in the backpack.
            if left<=0:self._reload(p)
            ax,ay=p['aim'];length=math.hypot(ax,ay) or 1;ax/=length;ay/=length
            if weapon.get('spread'):
                spread=self.rng.uniform(-weapon['spread'],weapon['spread']);ax,ay=ax*math.cos(spread)-ay*math.sin(spread),ax*math.sin(spread)+ay*math.cos(spread)
            end=self.shoot_line(p,ax,ay,weapon['range'],weapon['dmg']*(1+.03*(p['level']-1)),weapon.get('width',20))
            p['shot']=self.elapsed
            self.effects.append({'id':secrets.token_hex(4),'kind':'shot','x':p['x'],'y':p['y'],'ex':end['x'],'ey':end['y'],'until':self.elapsed+.22,'faction':f,'weapon':p['gear']['weapon']})
            return {'quiet':True}
        if op=='reload':
            if p.get('reload_until',0)<=self.elapsed and self._mag(p)<WEAPONS[p['gear']['weapon']]['mag'] and not self._reload(p):
                raise GameError('Нет патронов: '+ITEMS[WEAPONS[p['gear']['weapon']]['ammo_item']]['name']+'.')
            return {'quiet':True}
        if op=='use':
            item=data.get('item')
            if item not in ITEMS or item in ('repairkit','canister') or p['items'].get(item,0)<1: raise GameError('Этого предмета нет в рюкзаке.')
            if ITEMS[item].get('mat') or ITEMS[item].get('ammo'): raise GameError(ITEMS[item]['name']+' — материал для крафта (C).')
            self._cooldown(p,'use',.6)
            return self._use(p,item)
        if op=='drink':
            if p['vehicle']: raise GameError('Выйди из машины.')
            if not self.terrain.water(p['x'],p['y'],70): raise GameError('Рядом нет воды.')
            self._cooldown(p,'drink',2);p['water']=min(100,p['water']+35)
            # Raw river water is a gamble without antibiotics.
            if self.rng.random()<.25:
                p['sick']=self.elapsed+120
                return {'title':'Вода из реки','text':'Жажда утолена, но вода была грязной: отравление. Помогут антибиотики.','success':False}
            return {'title':'Вода из реки','text':'Жажда +35. Сырая вода может вызвать отравление.','success':True}
        if op=='canteen':
            t=self._service(p,data)
            if p['last_action'].get('canteen',-1000)+90>self.elapsed: raise GameError('Повара ещё не приготовили следующую порцию.')
            self._pay(f,{'food':3});p['last_action']['canteen']=self.elapsed
            p['food']=min(100,p['food']+50);p['water']=min(100,p['water']+70);p['warmth']=min(100,p['warmth']+20)
            return {'title':'Столовая и колодец','text':'Сытость +50, жажда +70. −3 припаса фракции.','success':True}
        if op=='refuel':
            car=p['car'];tank=self.car_tank(p)
            if car.get('wrecked_until',0)>self.elapsed: raise GameError('Машина разбита.')
            if car.get('fuel',0)>=tank-.5: raise GameError('Бак полон.')
            if data.get('canister'):
                if p['items'].get('canister',0)<1: raise GameError('Нет канистры. Её продают в магазине и находят в тайниках.')
                if not p['vehicle'] and dist(car,p)>110: raise GameError('Подойди к своей машине.')
                p['items']['canister']-=1
                if not p['items']['canister']:del p['items']['canister']
                car['fuel']=min(tank,car.get('fuel',0)+20)
                return {'title':'Канистра залита','text':'Бак: '+str(int(car['fuel']))+' / '+str(tank)+'.','success':True}
            # Filling up from the faction stock is possible only in a settlement your side holds.
            t=self.towns.get(str(data.get('town')))
            if not t or t['owner']!=f: raise GameError('Заправиться можно только в поселении своей стороны или из канистры.')
            if dist(car,t)>650 or (not p['vehicle'] and dist(p,t)>650): raise GameError('Подгони машину ближе.')
            need=tank-car.get('fuel',0);take=min(need,self.stocks[f]['fuel'])
            if take<1: raise GameError('В запасе фракции нет топлива. Его дают гаражи, канистры у дорог и торговля.')
            self.stocks[f]['fuel']-=take;car['fuel']=car.get('fuel',0)+take
            return {'title':'Заправка в '+t['name'],'text':'+'+str(int(take))+' топлива из запаса фракции. Бак: '+str(int(car['fuel']))+' / '+str(tank)+'.','success':True}
        if op=='cook':
            t=self._service(p,data)
            raw=p['items'].get('meat_raw',0)
            if not raw: raise GameError('Нет сырого мяса. Добудь зверя на охоте.')
            del p['items']['meat_raw'];p['items']['meat']=p['items'].get('meat',0)+raw
            return {'title':'Мясо пожарено','text':'Жареное мясо ×'+str(raw)+'.','success':True}
        if op=='equip':
            idx=data.get('weapon')
            if not isinstance(idx,int) or idx not in p['weapons']: raise GameError('Этого оружия у тебя нет.')
            if idx!=p['gear']['weapon']:
                p['gear']['weapon']=idx;p['reload_until']=max(p.get('reload_until',0),self.elapsed+SWAP_TIME)
                p['act']={'kind':'swap','at':round(self.elapsed,2)}
            return {'quiet':True}
        if op=='buy':
            return self._buy(p,data)
        if op=='loot':
            poi=self.terrain.pois.get(str(data.get('id')))
            if not poi: raise GameError('Место не найдено.')
            self._near(p,poi,170)
            if p['vehicle']: raise GameError('Выйди из машины.')
            st=self.poi_state.setdefault(poi['id'],{})
            if st.get(f,0)>self.elapsed: raise GameError('Тайник уже обыскан. Запасы появятся через '+str(int(st[f]-self.elapsed))+' сек.')
            if any(n['type'] in ('marauder','bandit') and n['hp']>0 and dist(n,poi)<330 for n in self.npcs.values()): raise GameError('Сначала разберись с мародёрами у тайника.')
            loot=POI_KINDS[poi['kind']]['loot'];st[f]=self.elapsed+300
            self._reward(f,loot);p['stats']['loot']+=1;self.gain_xp(p,'loot')
            got=self._loot_items(p,1)+[ITEMS[k]['name']+' ×'+str(v) for k,v in self.poi_materials(p,poi).items()]
            return {'title':'Тайник: '+poi['name'],'text':self.resource_text(loot)+('. В рюкзак: '+', '.join(got) if got else '. Рюкзак полон.'),'success':True}
        if op=='airdrop':
            drop=self.airdrops.get(str(data.get('id')))
            if not drop: raise GameError('Груз уже забрали.')
            self._near(p,drop,80)
            del self.airdrops[drop['id']];self._reward(f,drop['loot']);p['stats']['loot']+=1;self.gain_xp(p,'airdrop')
            self._notice('Груз найден',p['name'])
            got=[ITEMS[k]['name'] for k in ('medkit','water','canned') if self.give_item(p,k)]
            return {'title':'Сброшенный груз','text':self.resource_text(drop['loot'])+('. В рюкзак: '+', '.join(got) if got else ''),'success':True}
        if op=='extinguish':
            b=self.buildings.get(str(data.get('id')))
            if not b: raise GameError('Здание не найдено.')
            self._near(p,b,160);t=self.towns[b['town']]
            if b['kind'] not in t['fires']: raise GameError('Здесь не горит.')
            del t['fires'][b['kind']];self.reputation[f]=min(100,self.reputation[f]+2);self.gain_xp(p,'extinguish')
            if t['owner']==f:t['loyalty']=min(100,t['loyalty']+5)
            return {'title':'Пожар потушен','text':'Жители благодарны: репутация +2.','success':True}
        if op=='post':
            if p['vehicle']: raise GameError('Выйди из машины.')
            if not self.terrain.on_road(p['x'],p['y'],ROAD_HALF+30): raise GameError('Пост ставится прямо на трассе между поселениями.')
            if self.terrain.in_town(p['x'],p['y'],250): raise GameError('Слишком близко к поселению.')
            if any(dist(o,p)<700 for o in self.posts.values()): raise GameError('Рядом уже стоит пост.')
            if sum(1 for o in self.posts.values() if o['faction']==f)>=3: raise GameError('У фракции уже три поста.')
            self._pay(f,POST_COST)
            post={'id':secrets.token_hex(5),'faction':f,'x':round(p['x'],1),'y':round(p['y'],1),'hp':220,'built':self.elapsed,'name':POST['name']+' · '+p['name']}
            self.posts[post['id']]=post;self.fstats[f]['post']+=1;self.gain_xp(p,'post')
            return {'title':POST['name'],'text':POST['desc'],'success':True}
        if op in ('truce_propose','truce_accept','truce_break'):
            g=str(data.get('side'))
            if g not in self.sides or g==f: raise GameError('Выбери, с кем договариваться.')
            key='|'.join(sorted((f,g)))
            if op=='truce_propose':
                if self.truce_between(f,g): raise GameError('Перемирие уже действует.')
                if self.truce['cooldown'].get(key,0)>self.elapsed: raise GameError('Новое предложение можно отправить чуть позже.')
                self.truce['cooldown'][key]=self.elapsed+120
                if self.ai_faction(g):
                    mine=sum(1 for t in self.towns.values() if t['owner']==f);theirs=sum(1 for t in self.towns.values() if t['owner']==g)
                    accept=.3+self.reputation[f]/250+(.2 if self.flag(f,'open_signal') else 0)+(.1 if mine>theirs else 0)
                    if self.rng.random()<accept:
                        self._start_truce(f,g)
                        return {'title':'Перемирие заключено','text':'10 минут без стрельбы и захватов с '+self.side_name(g)+'.','success':True}
                    return {'title':'Предложение отвергнуто','text':self.side_name(g)+' тебе не доверяют. Повысь репутацию.','success':False}
                self.truce['proposals']=[x for x in self.truce['proposals'] if x['until']>self.elapsed and not (x['from']==f and x['to']==g)]
                self.truce['proposals'].append({'from':f,'to':g,'until':self.elapsed+90})
                self._notice('Предложение перемирия',self.side_name(f)+' предлагает 10 минут мира. Ответ — Esc → Дипломатия.',faction=g)
                return {'title':'Предложение отправлено','text':'У '+self.side_name(g)+' 90 секунд на ответ.','success':True}
            if op=='truce_accept':
                pr=next((x for x in self.truce['proposals'] if x['from']==g and x['to']==f and x['until']>self.elapsed),None)
                if not pr: raise GameError('Нет действующего предложения.')
                self.truce['proposals'].remove(pr);self._start_truce(f,g)
                return {'title':'Перемирие заключено','text':'10 минут без стрельбы и захватов.','success':True}
            if not self.truce_between(f,g): raise GameError('Перемирия нет.')
            self.truce['pairs'][key]=0;self.reputation[f]=clamp(self.reputation[f]-15,-100,100)
            self._notice('Перемирие нарушено',self.side_name(f)+' разорвал договор с '+self.side_name(g)+'.',tone='error')
            return {'title':'Перемирие разорвано','text':'Репутация −15.','success':False}
        if op.startswith('offer_'):
            return self._offer(p,op,data)
        if op=='craft_item':
            self._cooldown(p,'craft',.4)
            return self.craft(p,str(data.get('id')))
        if op=='search_house':
            if p['vehicle']: raise GameError('Выйди из машины.')
            self._cooldown(p,'search',.6)
            return self.search_house(p,data.get('id'))
        if op=='loot_body':
            if p['vehicle']: raise GameError('Выйди из машины.')
            return self.loot_body(p,data.get('id'))
        if op=='camp_found':
            camp=self.found_camp(p)
            where='в доме' if camp.get('house') else 'здесь'
            self._notice('Лагерь основан '+where,'Строй в нём: L. Костёр, спальник, ящик, верстак, ограда.',player=p['id'])
            return {'title':'Лагерь основан','text':'Теперь построй костёр и спальник: L рядом с лагерем.','success':True}
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
                broke=self.damage_camp_piece(camp,slot,45,p)
                self._notice('Кто-то ломает лагерь',p['name'],faction=camp['owner'],tone='error')
                return {'title':'Разрушено' if broke else 'Удар','text':'Осталось '+str(int(piece['hp']))+' прочности.' if not broke else '','success':True,'quiet':not broke}
            # Abandoning works from anywhere: the camp may be a long drive away.
            if op=='camp_abandon':
                if camp['owner']!=f: raise GameError('Бросить лагерь может только хозяин.')
                left=bool(camp['stash']['items'] or camp['stash']['coins'])
                self.abandon_camp(camp)
                return {'title':'Лагерь брошен','text':('Вещи из ящика остались лежать на месте лагеря. ' if left else '')+'Новый лагерь можно заложить там, где стоишь: L.','success':False}
            if dist(p,camp)>(max(self.terrain.houses[camp['house']]['w'],self.terrain.houses[camp['house']]['h'])/2+60 if camp.get('house') else 220): raise GameError('Подойди к лагерю.')
            if op=='camp_build':
                if not self.camp_allowed(camp,f): raise GameError('Это чужой лагерь.')
                name=self.build_part(p,camp,str(data.get('kind')),data.get('slot'));p['act']={'kind':'hammer','at':round(self.elapsed,2)}
                self.gain_xp(p,'build')
                return {'title':'Построено: '+name,'success':True}
            n=self.stash_move(p,camp,str(data.get('item')),finite(data.get('count',1),1),op=='stash_put')
            if not n: raise GameError('Не поместилось.' if op=='stash_take' else 'Нечего положить.')
            return {'title':('Положено' if op=='stash_put' else 'Взято')+': '+(str(n)+' монет' if data.get('item')=='coins' else ITEMS[data.get('item')]['name']+' ×'+str(n)),'success':True,'quiet':True}
        if op.startswith('clan_'):
            return self._clan(p,op,data)
        raise GameError('Неизвестное действие.')

    def _service(self,p,data):
        """Canteen and fire on the square of a settlement your side holds."""
        f=p['faction']
        t=self._town_action(p,str(data.get('town')))
        if t['owner']!=f: raise GameError('Это есть только в поселениях твоей стороны.')
        return t

    # ---- trade between players -------------------------------------------
    def _bundle(self,raw):
        """A clean {'coins':n,'items':{},'res':{}} from client data."""
        raw=raw if isinstance(raw,dict) else {}
        out={'coins':int(clamp(finite(raw.get('coins',0)),0,99999)),'items':{},'res':{}}
        for k,v in (raw.get('items') or {}).items():
            n=int(clamp(finite(v),0,99))
            if k in ITEMS and n:out['items'][k]=n
        for k,v in (raw.get('res') or {}).items():
            n=int(clamp(finite(v),0,9999))
            if k in RESOURCES and n:out['res'][k]=n
        return out

    def _has_bundle(self,p,b):
        return p['coins']>=b['coins'] and all(p['items'].get(k,0)>=v for k,v in b['items'].items()) and self._can_pay(p['faction'],b['res'])

    def _move_bundle(self,a,b,bundle):
        a['coins']-=bundle['coins'];b['coins']+=bundle['coins']
        for k,v in bundle['items'].items():
            a['items'][k]-=v
            if not a['items'][k]:del a['items'][k]
            b['items'][k]=b['items'].get(k,0)+v
        if a['faction']!=b['faction']:
            self._pay(a['faction'],bundle['res']);self._reward(b['faction'],bundle['res'])

    def bundle_text(self,b):
        parts=([str(b['coins'])+' монет'] if b['coins'] else [])+[ITEMS[k]['name']+' ×'+str(v) for k,v in b['items'].items()]+ \
              [str(v)+' '+RESOURCES[k].lower() for k,v in b['res'].items()]
        return ', '.join(parts) or 'ничего'

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

    def _load_camps(self,raw,sides,stretch):
        """Camps keep their fences as solid rectangles; house camps reuse the house's own walls."""
        self.camps={};self.bodies={}
        for cid,c in (raw.get('camps') or {}).items():
            if not isinstance(c,dict) or c.get('owner') not in sides or stretch!=1:continue
            house=self.terrain.houses.get(c.get('house')) if c.get('house') else None
            if c.get('house') and not house:continue
            camp={'id':cid,'owner':c['owner'],'x':finite(c.get('x')),'y':finite(c.get('y')),'house':house['id'] if house else None,
                  'parts':{},'fence':{},'stash':{'items':{},'coins':max(0,int(finite((c.get('stash') or {}).get('coins',0))))},'water_at':finite(c.get('water_at',0))}
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
            if isinstance(b,dict) and stretch==1:
                self.bodies[bid]={'id':bid,'x':finite(b.get('x')),'y':finite(b.get('y')),'name':str(b.get('name',''))[:40],'until':finite(b.get('until')),
                                  'coins':max(0,int(finite(b.get('coins',0)))),'items':{k:int(finite(v)) for k,v in (b.get('items') or {}).items() if k in ITEMS and finite(v)>0}}

    def offer_view(self,o):
        names={q['id']:q['name'] for q in self.players.values()}
        return dict(o,from_name=names.get(o['from'],'?'),to_name=names.get(o['to'],'?'),give_text=self.bundle_text(o['give']),want_text=self.bundle_text(o['want']))

    def _offer(self,p,op,data):
        if op=='offer_make':
            other=next((o for o in self.players.values() if o['id']==data.get('to')),None)
            if not other or other is p or other['hp']<=0: raise GameError('Игрок не найден.')
            if dist(p,other)>TRADE_RANGE: raise GameError('Для обмена нужно стоять рядом.')
            give=self._bundle(data.get('give'));want=self._bundle(data.get('want'))
            if give==self._bundle({}) and want==self._bundle({}): raise GameError('Предложение пустое.')
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
        for q in (p,giver):q['stats']['trade']+=1;self.gain_xp(q,'trade')
        self._notice('Обмен состоялся',p['name']+' принял предложение.',player=giver['id'])
        return {'title':'Обмен состоялся','text':'Получено: '+self.bundle_text(o['give'])+'.','success':True}

    # ---- clans -------------------------------------------------------------
    def _clan(self,p,op,data):
        f=p['faction'];mine=self.sides[f].get('clan');clan=self.clans.get(mine)
        if op=='clan_create':
            if clan: raise GameError('Ты уже в клане.')
            name=' '.join(str(data.get('name','')).split())[:24]
            if len(name)<3: raise GameError('Название клана — от трёх букв.')
            if any(c['name'].lower()==name.lower() for c in self.clans.values()): raise GameError('Такой клан уже есть.')
            if p['coins']<30: raise GameError('Создание клана стоит 30 монет.')
            p['coins']-=30;cid='c_'+secrets.token_hex(4)
            tag=''.join(w[0] for w in name.split())[:4].upper() if len(name.split())>1 else name[:4].upper()
            self.clans[cid]={'id':cid,'name':name,'tag':tag,'leader':f,'members':[f],'invites':[],'color':self.sides[f]['color']}
            self.sides[f]['clan']=cid
            self._notice('Основан клан «'+name+'»',p['name']+' собирает людей.')
            return {'title':'Клан «'+name+'»','text':'Приглашай игроков рядом через меню клана. В клане не стреляют друг в друга.','success':True}
        if op=='clan_join':
            c=self.clans.get(str(data.get('id')))
            if clan: raise GameError('Сначала выйди из своего клана.')
            if not c or f not in c['invites']: raise GameError('Приглашения нет.')
            if len(c['members'])>=CLAN_SIZE: raise GameError('В клане уже '+str(CLAN_SIZE)+' человек.')
            c['invites'].remove(f);c['members'].append(f);self.sides[f]['clan']=c['id']
            for g in c['members']:self.truce['pairs'].pop('|'.join(sorted((f,g))),None)
            self._notice(p['name']+' вступил в клан','«'+c['name']+'»')
            return {'title':'Ты в клане «'+c['name']+'»','success':True}
        if op=='clan_decline':
            c=self.clans.get(str(data.get('id')))
            if c and f in c['invites']:c['invites'].remove(f)
            return {'title':'Приглашение отклонено','success':False}
        if not clan: raise GameError('Ты не состоишь в клане.')
        if op=='clan_leave':
            clan['members'].remove(f);self.sides[f]['clan']=None
            if not clan['members']:del self.clans[clan['id']]
            elif clan['leader']==f:clan['leader']=clan['members'][0]
            self._notice(p['name']+' покинул клан','«'+clan['name']+'»')
            return {'title':'Ты вышел из клана','success':False}
        g=str(data.get('side'))
        if clan['leader']!=f: raise GameError('Это решает глава клана.')
        if op=='clan_invite':
            target=next((o for o in self.players.values() if o['faction']==g),None)
            if not target or g==f: raise GameError('Игрок не найден.')
            if self.sides[g].get('clan'): raise GameError(target['name']+' уже в клане.')
            if len(clan['members'])+len(clan['invites'])>=CLAN_SIZE+2: raise GameError('Слишком много приглашений.')
            if g not in clan['invites']:clan['invites'].append(g)
            self._notice('Приглашение в клан','«'+clan['name']+'» зовёт тебя. Ответ — O → Клан.',player=target['id'])
            return {'title':'Приглашение отправлено','text':target['name'],'success':True}
        if op=='clan_kick':
            if g not in clan['members'] or g==f: raise GameError('Такого человека в клане нет.')
            clan['members'].remove(g);self.sides[g]['clan']=None
            self._notice('Исключён из клана',self.side_name(g)+' · «'+clan['name']+'»')
            return {'title':'Исключён','text':self.side_name(g),'success':True}
        raise GameError('Неизвестное действие.')

    def slots(self,p):
        return BACKPACKS[p['gear']['backpack']]['slots']

    def _use(self,p,item):
        spec=ITEMS[item];p['items'][item]-=1
        if not p['items'][item]:del p['items'][item]
        p['food']=clamp(p['food']+spec.get('food',0),0,100);p['water']=clamp(p['water']+spec.get('water',0),0,100)
        p['warmth']=clamp(p['warmth']+spec.get('warmth',0),0,100);p['hp']=min(self.max_hp(p),p['hp']+spec.get('hp',0))
        if spec.get('stop_bleed'):p['bleeding']=False
        if spec.get('cure'):p['sick']=0
        if spec.get('risk') and self.rng.random()<spec['risk']:
            p['sick']=self.elapsed+120
            return {'title':spec['name'],'text':'Сытость +'+str(spec.get('food',0))+', но живот скрутило: отравление.','success':False}
        return {'title':spec['name'],'text':spec['desc'],'success':True}

    def _loot_items(self,p,count):
        got=[]
        for i in range(count):
            item=self.rng.choice(LOOT_ITEMS)
            if self.give_item(p,item):got.append(ITEMS[item]['name'])
        return got

    def _buy(self,p,data):
        """Shop on the square of an own or neutral settlement; prices are in personal coins."""
        f=p['faction'];t=self._town_action(p,str(data.get('town')))
        if t['owner'] not in (None,f) and not self.truce_between(f,t['owner']): raise GameError('Торговцы чужого поселения тебе не продают.')
        kind=data.get('kind');idx=data.get('index')
        if kind=='car':
            if not isinstance(idx,int) or not 0<=idx<len(CARS) or not CARS[idx]['price']: raise GameError('Такой машины нет.')
            spec=CARS[idx]
            if p['level']<spec['level']: raise GameError('Нужен уровень '+str(spec['level'])+'.')
            if p['car'].get('model')==idx: raise GameError('Это и есть твоя машина.')
            if p['vehicle']: raise GameError('Выйди из машины.')
            if p['coins']<spec['price']: raise GameError('Не хватает монет: нужно '+str(spec['price'])+'.')
            spot=next(((t['x']+dx,t['y']+dy) for dx,dy in ((0,90),(90,0),(-90,0),(0,-90),(140,140)) if not self._car_blocked(spec,t['x']+dx,t['y']+dy,0)),None)
            if not spot: raise GameError('На площади негде поставить машину.')
            p['coins']-=spec['price']
            fuel=min(spec['tank'],p['car'].get('fuel',0)) if not p['car'].get('wrecked_until') else 10.0
            p['car']=self.new_car(spot[0],spot[1],0.0,fuel,idx)
            return {'title':'Твоя машина: '+spec['name'],'text':'Старую забрали в счёт оплаты; бензин перелит. Машина стоит на площади.','success':True}
        if kind in ('weapon','armor','clothes','backpack'):
            table={'weapon':WEAPONS,'armor':ARMOR,'clothes':CLOTHES,'backpack':BACKPACKS}[kind]
            if not isinstance(idx,int) or not 1<=idx<len(table): raise GameError('Такого товара нет.')
            item=table[idx]
            if p['level']<item['level']: raise GameError('Нужен уровень '+str(item['level'])+'.')
            if kind=='weapon' and idx in p['weapons']: raise GameError('Это оружие уже у тебя.')
            if kind!='weapon' and p['gear'][kind]>=idx: raise GameError('У тебя уже есть не хуже.')
            price=item['price'];name=item['name']
        elif kind in SHOP_ITEMS or kind in ITEMS:
            item=SHOP_ITEMS.get(kind) or ITEMS[kind];price=item['price'];name=item['name']
            count=int(clamp(finite(data.get('count',1),1),1,50)) if kind in ITEMS else 1
            if kind in ITEMS and self.room_for(p,kind,count)<count: raise GameError('Рюкзак полон. Купи рюкзак побольше или используй вещи.')
            price*=count;name+=(' ×'+str(count) if count>1 else '')
        else: raise GameError('Такого товара нет.')
        if p['coins']<price: raise GameError('Не хватает монет: нужно '+str(price)+'. Монеты дают за поручения и главы сюжета.')
        p['coins']-=price
        if kind=='weapon':p['weapons'].append(idx);p['gear']['weapon']=idx
        elif kind in ('armor','clothes','backpack'):p['gear'][kind]=idx
        elif kind=='supplies':self._reward(f,{'food':20,'fuel':15})
        elif kind=='materials':self._reward(f,{'wood':30,'stone':25,'metal':15})
        else:p['items'][kind]=p['items'].get(kind,0)+count
        return {'title':'Куплено: '+name,'text':'−'+str(price)+' монет. Осталось '+str(p['coins'])+'.','success':True}

    def _start_truce(self,a,b):
        self.truce['pairs']['|'.join(sorted((a,b)))]=self.elapsed+600
        for f in (a,b):self.reputation[f]=clamp(self.reputation[f]+3,-100,100)
        self._notice('Перемирие',self.side_name(a)+' и '+self.side_name(b)+' не стреляют друг в друга 10 минут.')

    def _trade(self,p,t,data):
        f=p['faction']
        if t['owner'] not in (None,f) and not self.truce_between(f,t['owner']): raise GameError('Торговцы чужого поселения не станут с тобой меняться.')
        give=data.get('give');get=data.get('get');amount=data.get('amount')
        if give not in RESOURCES or get not in RESOURCES or give==get or amount not in (10,25,50): raise GameError('Выбери, что отдать и что получить.')
        self._cooldown(p,'trade',.8)
        prices=PRICES.get(t['region'],PRICES['default'])
        mod=.78 if t['owner']!=f else .86+t['loyalty']*.001
        receive=int(amount*prices[give]/prices[get]*mod)
        if receive<1: raise GameError('Слишком невыгодный обмен.')
        self._pay(f,{give:amount});self._reward(f,{get:receive})
        p['stats']['trade']+=1;self.fstats[f]['trade']+=1;self.gain_xp(p,'trade')
        return {'title':'Обмен совершён','text':'−'+str(amount)+' '+RESOURCES[give].lower()+' → +'+str(receive)+' '+RESOURCES[get].lower(),'success':True}

    def _raid(self,p,t):
        f=p['faction']
        victim=t['owner']
        if victim not in self.sides or victim==f: raise GameError('Набег возможен только на чужое поселение.')
        if self.truce_between(f,victim): raise GameError('Действует перемирие.')
        if t['cooldowns'].get('raid',0)>self.elapsed: raise GameError('Жители ещё начеку. Подожди.')
        chance=self.chance(p,t,'raid');self._pay(f,{'metal':8,'food':4})
        roll=self.rng.randint(1,100);ok=roll<=chance;t['cooldowns']['raid']=self.elapsed+90
        if not ok:
            self._damage(p,20)
            return {'title':'Набег отбит','text':'Здоровье −20.','success':False,'chance':chance,'roll':roll}
        loot={k:min(20,round(self.stocks[victim][k]*.15,1)) for k in ('food','metal','fuel')}
        for k,v in loot.items():self.stocks[victim][k]-=v
        self._reward(f,loot);t['loyalty']=max(0,t['loyalty']-12);self.fstats[f]['tribute']+=1;self.gain_xp(p,'raid')
        self._notice('Набег на '+t['name'],'Бандиты унесли: '+self.resource_text({k:int(v) for k,v in loot.items()}),faction=victim,tone='error')
        return {'title':'Набег удался','text':self.resource_text({k:int(v) for k,v in loot.items()}),'success':True,'chance':chance,'roll':roll}

    def start_construction(self,t,kind,p):
        level=t['levels'][kind]
        t['construct'][kind]={'progress':0.0,'total':float(BUILD_TIME[min(level,2)]),'level':level+1,
                              'by':p['id'] if p else None}

    def begin_capture(self,t,f,method):
        t['capture']={'faction':f,'progress':0.0,'duration':30.0,'method':method,'contested':False,'active':True}
        self._notice('Начался захват',t['name']+' · площадь удерживает '+self.side_name(f)+'.')

    def _set_owner(self,t,f):
        t['owner']=f;t['construct']={};t['fires']={}
        self.clear_garrison(t)

    @staticmethod
    def resource_text(resources):
        return ', '.join(str(v)+' '+RESOURCES[k].lower() for k,v in resources.items() if v) or 'помощь и опыт'

    def _damage(self,p,amount):
        p['hp']=max(0,p['hp']-amount)
        if p['hp']==0 and not p['dead_until']:
            p['dead_until']=self.elapsed+7;p['vehicle']=False;p['input']=[0,0,False]
            self._death_penalty(p)
            self._notice('Ты ранен','Через 7 секунд очнёшься в новом месте у дороги.',player=p['id'],tone='error')

    def _death_penalty(self,p):
        """Death costs every captured settlement; the backpack and coins stay on the body."""
        f=p['faction'];lost=[]
        for t in self.towns.values():
            if t['owner']==f:
                self._set_owner(t,None);t['loyalty']=45;t['capture']=None;t['shield']=0.0;lost.append(t['name'])
            elif t['capture'] and t['capture']['faction']==f:
                t['capture']=None
        coins=p['coins'];p['coins']=0
        items=p['items'];p['items']={}
        self.drop_pile(p['x'],p['y'],items,coins,'Тело: '+p['name'])
        self._notice('Всё осталось на теле','Рюкзак и монеты лежат там, где ты погиб, '+str(BODY_TIME//60)+' минут — их может забрать кто угодно.'+(' Поселения снова независимы: '+', '.join(lost)+'.' if lost else ''),player=p['id'],tone='error')
        if lost:self._notice(p['name']+' погиб',', '.join(lost)+' — снова независимые поселения.',skip=p['id'])
        self.dirty=True

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
        return False

    def tick(self,dt):
        now=time.monotonic()
        active=[p for p in self.players.values() if now-p['last_seen']<8]
        if not active or all(p['paused'] for p in active): return
        dt=clamp(dt,0,.1);self.elapsed+=dt;self.production_clock+=dt;self.save_clock+=dt
        self.effects=[e for e in self.effects if e['until']>self.elapsed]
        garage={f:self.best_level(f,'garage') for f in self.sides}
        for p in active:
            car=p['car']
            if car.get('wrecked_until',0) and self.elapsed>=car['wrecked_until']:
                camp=self.camp_of(p['faction']);t=camp if camp else p
                spot=self._free_near(t['x'],t['y'],160,320) or (t['x']+150,t['y'])
                p['car']=self.new_car(spot[0],spot[1],0.0,max(10.0,car.get('fuel',0)),car.get('model'))
            if p['hp']<=0:
                if self.elapsed>=p['dead_until']:
                    # Each respawn is a new random roadside spot; the car comes along so nobody is stranded.
                    p['hp']=self.max_hp(p);p['dead_until']=0
                    p.update(food=max(p['food'],60.0),water=max(p['water'],60.0),warmth=80.0,bleeding=False,sick=0.0)
                    camp=self.camp_of(p['faction']);bed=camp and camp['parts'].get('bed')
                    if bed and bed['hp']>0:
                        p['x'],p['y']=bed['x'],bed['y']+14;p['vehicle']=False
                        self._notice('Ты очнулся в лагере','Спальник спас. Вещи остались на теле — сходи за ними.',player=p['id'])
                    else:self._place_randomly(p)
                    self._respawn_ammo(p)
                continue
            x,y,sprint=p['input'] if now-p['last_input']<.65 and not p['paused'] else (0,0,False)
            length=math.hypot(x,y)
            if length>1: x/=length;y/=length
            moving=bool(x or y)
            speed=140
            if p.get('ride') and not p['vehicle']:p['ride']=None
            if p.get('ride'):
                self.tick_ride(p)
            elif p['vehicle']:
                # W/S are throttle and brake, A/D steer, Shift is the handbrake.
                self.drive(p,dt,clamp(p['input'][0] if now-p['last_input']<.65 and not p['paused'] else 0,-1,1),
                           clamp(-(p['input'][1] if now-p['last_input']<.65 and not p['paused'] else 0),-1,1),bool(sprint),garage[p['faction']])
            elif sprint and p['stamina']>1 and moving:
                speed=220;p['stamina']=max(0,p['stamina']-dt*22)
            else: p['stamina']=min(100,p['stamina']+dt*14*(.4 if min(p['food'],p['water'])<20 or p['warmth']<25 else 1))
            self._survive(p,dt,sprint and moving and not p['vehicle'])
            if not p['vehicle']:
                if self.terrain.water(p['x'],p['y']):speed*=.45
                nx=p['x']+x*speed*dt;ny=p['y']+y*speed*dt
                if not self._blocked_for(p,nx,p['y'],10):p['x']=nx
                if not self._blocked_for(p,p['x'],ny,10):p['y']=ny
                if moving:p['angle']=math.atan2(y,x)
            for t in self.towns.values():
                if abs(p['x']-t['x'])<t['r']+150 and abs(p['y']-t['y'])<t['h']+150 and t['id'] not in p['visited']:
                    p['visited'].append(t['id']);p['stats']['explore']+=1;self.gain_xp(p,'explore')
                    self._notice('Новое место',t['name'],player=p['id'])
            if self.near_camp_part(p,'fire',130):p['hp']=min(self.max_hp(p),p['hp']+dt*1.5)
        self.tick_npcs(dt,active)
        self.tick_squads()
        self.tick_defenses(dt)
        self.tick_convoys(dt)
        self.tick_ai(dt)
        self._tick_construction(dt,active)
        self._tick_captures(dt,active)
        self._tick_world_events(dt)
        self.tick_camps(dt);self.tick_bodies()
        if self.production_clock>=12:
            self.production_clock-=12
            self._produce()
        if not self.winner:
            for f in self.sides:
                count=sum(1 for t in self.towns.values() if t['owner']==f)
                if count>=5 and self.best_level(f,'radio')>=2:
                    self.winner=f;self._notice('Связь восстановлена',self.side_name(f)+' связал пять поселений. Мир остаётся доступен для игры.');self.save()
        if self.save_clock>=10:
            self.save_clock=0;self.save()

    def _survive(self,p,dt,sprinting):
        """Hunger, thirst, cold, bleeding and sickness, simulated on the host."""
        sick=p['sick']>self.elapsed
        k=(2 if sprinting else .6 if p['vehicle'] else 1)*(1.8 if sick else 1)
        p['food']=max(0,p['food']-.065*k*dt);p['water']=max(0,p['water']-.1*k*dt)
        town=min(self.towns.values(),key=lambda t:dist(t,p))
        hour=(8+self.elapsed*1.4/60)%24;night=hour>=21 or hour<6
        wading=not p['vehicle'] and self.terrain.water(p['x'],p['y'])
        exposure=REGIONS[town['region']]['cold']*10+(10 if p['y']<1300*WORLD_SCALE else 0)+(12 if night else 0)
        exposure+={'rain':10,'storm':18,'snow':16,'fog':4}.get(self.weather['kind'],0)+(15 if wading else 0)
        exposure-=CLOTHES[p['gear']['clothes']]['warm']+(25 if p['vehicle'] else 0)
        fire=(town['owner']==p['faction'] and dist(town,p)<300) or bool(self.near_camp_part(p,'fire',170)) or any(o['faction']==p['faction'] and dist(o,p)<220 for o in self.posts.values())
        target=100 if fire else clamp(100-max(0,exposure)*1.6,0,100)
        rate=2.5 if fire else .6
        p['warmth']+=clamp(target-p['warmth'],-rate*dt,rate*dt)
        drain=(.3 if p['food']<=0 else 0)+(.5 if p['water']<=0 else 0)+(.35 if p['warmth']<20 else 0)+(.5 if p['bleeding'] else 0)+(.08 if sick else 0)
        if drain:self._damage(p,drain*dt)
        elif p['food']>70 and p['water']>70 and p['warmth']>50:p['hp']=min(self.max_hp(p),p['hp']+.2*dt)
        for key,value,low,text in (('food',p['food'],25,'Ты голоден. Поешь: G или столовая своего поселения.'),
                                   ('water',p['water'],25,'Хочется пить. V — вода из рюкзака или из реки.'),
                                   ('warmth',p['warmth'],30,'Ты замерзаешь. Тёплая одежда, машина, костёр в своём поселении.')):
            if value<low and key not in p['warned']:
                p['warned'].append(key);self._notice({'food':'Голод','water':'Жажда','warmth':'Холод'}[key],text,player=p['id'],tone='error')
            elif value>low+15 and key in p['warned']:p['warned'].remove(key)

    def _blocked_for(self,p,x,y,r):
        if self.blocked(x,y,r,p['faction']):return True
        # Cars cannot drive into rivers and lakes; bridges are the roads.
        return p['vehicle'] and self.terrain.water(x,y,8) and not self.terrain.on_road(x,y,ROAD_HALF+10) and not self.terrain.on_street(x,y,10)

    def _tick_construction(self,dt,active):
        for t in self.towns.values():
            if not t['construct'] or t['capture']:continue
            for kind,c in list(t['construct'].items()):
                b=self.buildings[t['id']+':'+kind]
                helpers=sum(1 for p in active if p['faction']==t['owner'] and p['hp']>0 and not p['vehicle'] and dist(p,b)<230)
                c['progress']+=dt*(1+.5*helpers)
                if c['progress']>=c['total']:
                    del t['construct'][kind]
                    builder=next((p for p in self.players.values() if p['id']==c.get('by')),None)
                    if builder:self.gain_xp(builder,'built')
                    t['levels'][kind]=min(3,c['level']);t['loyalty']=min(100,t['loyalty']+4)
                    self._notice(BUILDINGS[kind]['name']+': уровень '+str(t['levels'][kind]),'Поселение: '+t['name'],faction=t['owner'])
                    self.dirty=True

    def _tick_captures(self,dt,active):
        for t in self.towns.values():
            c=t['capture']
            if not c:continue
            f=c['faction']
            attackers=[p for p in active if p['faction']==f and p['hp']>0 and not p['vehicle'] and dist(p,t)<160 and not p['paused']]
            attackers+=[n for n in self.npcs.values() if n['faction']==f and n['hp']>0 and n['type'] in ('ranger','raider') and dist(n,t)<160]
            enemies=[p for p in active if p['faction']!=f and p['hp']>0 and dist(p,t)<185 and not self.truce_between(p['faction'],f)]
            enemies+=[n for n in self.npcs.values() if n['hp']>0 and n['type']!='convoy' and dist(n,t)<185 and self.hostile(n,{'faction':f})]
            c['contested']=bool(enemies);c['active']=bool(attackers)
            if attackers and not enemies:c['progress']+=dt
            elif not attackers:c['progress']-=dt*1.2
            if c['progress']< -4:
                t['capture']=None;self._notice('Захват сорван',t['name']+' · атакующие покинули площадь.')
            elif c['progress']>=c['duration']:
                self._set_owner(t,f);t['shield']=self.elapsed+120
                t['loyalty']=38 if c['method']=='assault' else 72
                if c['method']=='assault':
                    candidates=[k for k in ('house','sawmill','quarry','workshop','farm') if t['levels'][k]>0]
                    if candidates:t['levels'][self.rng.choice(candidates)]-=1
                t['levels']['depot']=max(1,t['levels']['depot']);t['capture']=None
                for p in active:
                    if p['faction']==f:p['stats']['capture']+=1;self.gain_xp(p,'capture')
                self.fstats[f]['capture']+=1
                self._notice('Поселение под контролем',t['name']+' · '+self.side_name(f));self.dirty=True;self.save()

    def _produce(self):
        for t in self.towns.values():
            f=t['owner']
            if not f or t['capture']:continue
            pop,workers,enabled=self.economy(t)
            enough=self.stocks[f]['food']>=pop*.035
            self.stocks[f]['food']=max(0,self.stocks[f]['food']-pop*.035)
            modifier=(.65+t['loyalty']*.005)*(1 if enough else .5)
            for k,on in enabled.items():
                if on and 'output' in BUILDINGS[k]:
                    resource,amount=BUILDINGS[k]['output']
                    value=amount*t['levels'][k]*modifier*(1.15 if k=='farm' and self.flag(f,'open_doors') else 1)
                    if t['base']:self._reward(f,{resource:value})
                    else:
                        # Remote towns ship part of their output by truck; trucks can be robbed.
                        self._reward(f,{resource:value*.7});t['cargo'][resource]=t['cargo'].get(resource,0)+value*.3
        self.dirty=True

    def _tick_world_events(self,dt):
        if self.weather['until']<=self.elapsed:
            kinds=['clear']*9+['rain']*4+['fog']*3+['storm']*2+['snow']*2
            self.weather={'kind':self.rng.choice(kinds),'until':self.elapsed+self.rng.uniform(200,420)}
        for k,d in list(self.airdrops.items()):
            if d['until']<self.elapsed:del self.airdrops[k]
        for t in self.towns.values():
            for kind,until in list(t['fires'].items()):
                if until<=self.elapsed:
                    del t['fires'][kind]
                    floor=1 if kind=='depot' and t['owner'] else 0
                    if t['levels'][kind]>floor:
                        t['levels'][kind]-=1
                        self._notice('Пожар уничтожил здание',BUILDINGS[kind]['name']+' · '+t['name']+' · уровень −1',faction=t['owner'],tone='error')
        self.event_clock+=dt
        if self.event_clock<170:return
        self.event_clock=self.rng.uniform(-60,0)
        kind=self.rng.choice(['refugees','fire','marauders','airdrop','airdrop','weather'])
        owned=[t for t in self.towns.values() if t['owner']]
        if kind=='refugees' and owned:
            t=self.rng.choice(owned);t['loyalty']=min(100,t['loyalty']+10)
            self._notice('Пришли беженцы',t['name']+': новые руки и надежда. Лояльность +10.',faction=t['owner'])
        elif kind=='fire' and owned:
            t=self.rng.choice(owned)
            options=[k for k in BUILDINGS if t['levels'][k]>0 and k not in t['fires']]
            if options:
                k=self.rng.choice(options);t['fires'][k]=self.elapsed+90
                self._notice('Пожар в поселении '+t['name'],BUILDINGS[k]['name']+' горит! Подойди и нажми E за 90 секунд.',faction=t['owner'],tone='error')
        elif kind=='marauders' and owned:
            t=self.rng.choice(owned)
            for i in range(4):
                spot=self._free_near(t['x'],t['y'],650,900)
                if spot:
                    n=self.spawn_npc('marauder','marauders',spot[0],spot[1])
                    n['goal']=[t['x'],t['y']];n['home']=[t['x'],t['y']]
            self._notice('Мародёры у поселения '+t['name'],'Банда идёт к площади.',faction=t['owner'],tone='error')
        elif kind=='airdrop':
            seg=self.rng.choice(self.terrain.road_segments);u=self.rng.uniform(.3,.7)
            x=seg[0]+(seg[2]-seg[0])*u+self.rng.uniform(-120,120);y=seg[1]+(seg[3]-seg[1])*u+self.rng.uniform(-120,120)
            if self.terrain.free_spot(x,y,30):
                near=min(self.towns.values(),key=lambda t:math.hypot(t['x']-x,t['y']-y))
                did=secrets.token_hex(4)
                self.airdrops[did]={'id':did,'x':round(x),'y':round(y),'until':self.elapsed+360,
                                    'loot':{'metal':18,'fuel':14,'food':14},'near':near['name']}
                self._notice('Сброшен груз','Парашют замечен у трассы возле '+near['name']+'. Метка на карте.')
        else:
            self.weather={'kind':self.rng.choice(['storm','fog','snow']),'until':self.elapsed+self.rng.uniform(150,260)}
            self._notice('Погода портится',WEATHER[self.weather['kind']]+': машины едут медленнее.')

    # ---- persistence ----------------------------------------------------
    def save(self):
        if not self.save_path:return
        players={}
        for token,p in self.players.items():
            players[token]={k:v for k,v in p.items() if k not in ('last_seen','last_input','input','receipts','paused')}
        convoys=[n for n in self.npcs.values() if n['type']=='convoy' and n['hp']>0]
        payload={'schema':SAVE_VERSION,'version':VERSION,'time':self.elapsed,'production_clock':self.production_clock,
                 'towns':self.towns,'sides':self.sides,'stocks':self.stocks,'reputation':self.reputation,
                 'players':players,'harvested':self.harvested,'events_done':self.events_done,'winner':self.winner,
                 'posts':self.posts,'convoys':convoys,'weather':self.weather,'truce':self.truce,'story':self.story,
                 'fstats':self.fstats,'ai_state':self.ai_state,'poi_state':self.poi_state,'settings':self.settings,
                 'airdrops':self.airdrops,'room_code':self.room_code,'scale':WORLD_SCALE,'clans':self.clans,
                 'camps':self.camps,'bodies':self.bodies}
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

    def load(self):
        try:
            raw=json.loads(self.save_path.read_text(encoding='utf-8'))
            if raw.get('schema') not in (1,SAVE_VERSION):raise ValueError('Save version')
            # Saves made before the map was stretched keep their places relative to the towns.
            stretch=WORLD_SCALE/max(1,finite(raw.get('scale',1),1))
            players={}
            for token,p in list(raw.get('players',{}).items())[:MAX_PLAYERS]:
                if not isinstance(p.get('faction'),str):raise ValueError('Faction')
                p['x']=clamp(finite(p['x'])*stretch,25,WORLD_SIZE[0]-25);p['y']=clamp(finite(p['y'])*stretch,25,WORLD_SIZE[1]-25)
                if isinstance(p.get('car'),dict):p['car']['x']=finite(p['car'].get('x'))*stretch;p['car']['y']=finite(p['car'].get('y'))*stretch
                p.update(last_seen=-1000,last_input=-1000,input=[0,0,False],receipts=OrderedDict(),paused=False)
                gear=p.get('gear') or {}
                p['gear']={'weapon':int(clamp(finite(gear.get('weapon',0)),0,len(WEAPONS)-1)),'armor':int(clamp(finite(gear.get('armor',0)),0,len(ARMOR)-1)),
                           'clothes':int(clamp(finite(gear.get('clothes',0)),0,len(CLOTHES)-1)),'backpack':int(clamp(finite(gear.get('backpack',0)),0,len(BACKPACKS)-1))}
                p['car'].setdefault('hp',100.0);p['car'].setdefault('wrecked_until',0.0);p['car'].setdefault('model',2)
                if not isinstance(p['car']['model'],int) or not 0<=p['car']['model']<len(CARS):p['car']['model']=2
                p['car']['fuel']=clamp(finite(p['car'].get('fuel',30.0),30.0),0,CARS[p['car']['model']]['tank'])
                for k in ('vx','vy','steer'):p['car'][k]=0.0
                for k in STAT_KEYS:p['stats'].setdefault(k,0)
                p['level']=int(clamp(finite(p.get('level',1),1),1,MAX_LEVEL));p['xp']=max(0,int(finite(p.get('xp',0))))
                p['coins']=max(0,int(finite(p.get('coins',0))))
                p['weapons']=sorted({int(clamp(finite(i),0,len(WEAPONS)-1)) for i in p.get('weapons',[])}|{0,p['gear']['weapon']})
                items=p.get('items') or {};p['items']={k:max(0,int(finite(v))) for k,v in items.items() if k in ITEMS and finite(v)>0}
                for key,default in (('food',80.0),('water',80.0),('warmth',90.0)):p[key]=clamp(finite(p.get(key,default),default),0,100)
                p['mags']={str(k):int(clamp(finite(v),0,999)) for k,v in (p.get('mags') or {}).items()} if isinstance(p.get('mags'),dict) else {}
                p['reload_until']=finite(p.get('reload_until',0));p.pop('act',None)
                p['bleeding']=bool(p.get('bleeding'));p['sick']=finite(p.get('sick',0));p['warned']=[]
                players[token]=p
            towns=copy.deepcopy(self.towns)
            for tid,t in towns.items():
                v=raw['towns'].get(tid)
                if v is None:continue        # a settlement added after this save was made
                t['owner']=v['owner'];t['levels']={k:int(clamp(finite(v['levels'].get(k,0)),0,3)) for k in BUILDINGS}
                t['loyalty']=clamp(finite(v['loyalty']),0,100)
                for key in ('shield','cooldowns','intel'):t[key]=v.get(key,t[key])
                t['construct']={k:c for k,c in v.get('construct',{}).items() if k in BUILDINGS and isinstance(c,dict)}
                t['cargo']={k:clamp(finite(v.get('cargo',{}).get(k,0)),0,9999) for k in RESOURCES}
                t['fires']={k:finite(u) for k,u in v.get('fires',{}).items() if k in BUILDINGS}
                t['capture']=None;t['base']=False
            def side_data(key,f,default):
                return (raw.get(key) or {}).get(f,default)
            sides={};stocks={};reputation={};story={};fstats={}
            def adopt(sid,info,old):
                sides[sid]=info
                st=side_data('stocks',old,{})
                stocks[sid]={r:clamp(finite(st.get(r,40)),0,99999) for r in RESOURCES}
                reputation[sid]=clamp(finite(side_data('reputation',old,0)),-100,100)
                sv=side_data('story',old,{}) or {}
                story[sid]={'index':int(clamp(finite(sv.get('index',0)),0,len(STORY_LINE))),'flags':[str(x) for x in sv.get('flags',[])],'start':sv.get('start') or {}}
                fs=side_data('fstats',old,{}) or {}
                fstats[sid]={k:int(finite(fs.get(k,0))) for k in FSTAT_KEYS}
            if isinstance(raw.get('sides'),dict):
                for sid,info in raw['sides'].items():
                    if not isinstance(info,dict):raise ValueError('Side')
                    # 0.4 sides had a home settlement: it stays theirs. Shelters of 0.5 are gone; camps come back below.
                    adopt(sid,{'id':sid,'name':str(info.get('name',''))[:30],'color':str(info.get('color','#cccccc'))[:9],
                               'camp':info.get('camp') if isinstance(info.get('camp'),str) else None,'clan':None,
                               'ai':bool(info.get('ai')),'fighter':info.get('fighter','raider'),'method':info.get('method','assault')},sid)
                    if info.get('home') in towns and 'shelter' not in info and 'camp' not in info:towns[info['home']]['owner']=sid
            else:
                # Saves from the survivors-and-bandits era: every player becomes a side of their own.
                heirs={}
                for token,p in players.items():
                    old=p['faction'];sid='p_'+p['id']
                    adopt(sid,{'id':sid,'name':p['name'],'color':SIDE_COLORS[len(sides)%len(SIDE_COLORS)],'camp':None,
                               'clan':None,'ai':False,'fighter':'raider','method':'assault'},old if old not in heirs else None)
                    heirs.setdefault(old,sid);p['faction']=sid
                for t in towns.values():
                    t['owner']=heirs.get(t['owner'])
            clans={}
            for cid,c in (raw.get('clans') or {}).items():
                members=[m for m in c.get('members',[]) if m in sides and not sides[m]['clan']][:CLAN_SIZE]
                if not members:continue
                clans[cid]={'id':cid,'name':str(c.get('name','Клан'))[:24],'tag':str(c.get('tag',''))[:4],'members':members,
                            'leader':c.get('leader') if c.get('leader') in members else members[0],
                            'invites':[m for m in c.get('invites',[]) if m in sides],'color':str(c.get('color','#cccccc'))[:9]}
                for m in members:sides[m]['clan']=cid
            for p in players.values():
                if p['faction'] not in sides:raise ValueError('Player side')
                p.pop('look',None)
            for t in towns.values():
                if t['owner'] not in sides:t['owner']=None
            self.elapsed=max(0,finite(raw['time']));self.production_clock=finite(raw.get('production_clock',0))%12
            self.towns=towns;self.players=players;self.sides=sides;self.stocks=stocks;self.reputation=reputation
            self.story=story;self.fstats=fstats;self.clans=clans
            self._load_camps(raw,sides,stretch)
            self.harvested=raw.get('harvested',{});self.events_done=raw.get('events_done',{})
            self.winner=raw.get('winner') if raw.get('winner') in sides else None
            self.posts={pid:dict(v,x=finite(v.get('x'))*stretch,y=finite(v.get('y'))*stretch) for pid,v in raw.get('posts',{}).items() if v.get('faction') in sides}
            if stretch==1:
                for n in raw.get('convoys',[]):
                    if n.get('faction') in sides and n.get('type')=='convoy':self.npcs[n['id']]=n
            if isinstance(raw.get('weather'),dict) and raw['weather'].get('kind') in WEATHER:self.weather=raw['weather']
            truce=raw.get('truce')
            if isinstance(truce,dict) and isinstance(truce.get('pairs'),dict):
                self.truce['pairs']={k:finite(v) for k,v in truce['pairs'].items()}
            self.ai_state={k:v for k,v in (raw.get('ai_state') or {}).items() if k in sides};self.poi_state=raw.get('poi_state') or {}
            self.settings.update(raw.get('settings') or {});self.airdrops=(raw.get('airdrops') or {}) if stretch==1 else {}
            code=raw.get('room_code')
            self.room_code=code if isinstance(code,str) and len(code)==6 and code.isdigit() else None
        except (OSError,ValueError,KeyError,TypeError,AttributeError,StopIteration):
            # Preserve the original damaged file for recovery before autosave writes a new world.
            backup=self.save_path.with_name(self.save_path.stem+'.unreadable-'+str(int(time.time()))+'.json')
            try:os.replace(str(self.save_path),str(backup))
            except OSError:pass
            self.load_warning='Сохранение не удалось прочитать. Его копия сохранена рядом; начат новый мир.'


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
        '/assets/characters.png':'assets/characters.png','/assets/givers.png':'assets/givers.png',
        '/assets/portraits.jpg':'assets/portraits.jpg','/assets/cars.png':'assets/cars.png','/assets/hero.png':'assets/hero.png'}
TYPES={'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'application/javascript; charset=utf-8','svg':'image/svg+xml','png':'image/png','jpg':'image/jpeg'}

class Handler(BaseHTTPRequestHandler):
    server_version='AfterSilence/'+VERSION

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
            cfg=config();cfg['buildings_world']=list(w.buildings.values());cfg['nodes']=list(w.nodes.values())
            cfg['pois']=list(w.terrain.pois.values())
            cfg['givers']=list(w.givers.values())
            cfg['towns']=[dict(t,r=w.terrain.towns[t['id']]['r'],h=w.terrain.towns[t['id']]['h']) for t in cfg['towns']]
            cfg['streets']=[[round(v) for v in s] for s in w.terrain.streets]
            cfg['houses']=[{k:h[k] for k in ('id','town','kind','x','y','w','h','door')} for h in w.terrain.houses.values()]
            cfg['road_lines']=[{'ax':s[0],'ay':s[1],'bx':s[2],'by':s[3],'a':s[4],'b':s[5]} for s in w.terrain.road_segments]
            cfg['join_code']=self.server.join_code if self._local() else None
            cfg['lan_addresses']=lan_addresses(self.server.server_port) if cfg['join_code'] else []
            cfg['host']=self._local()
            with w.lock:cfg['settings']=dict(w.settings)
            self._json(200,cfg);return
        if path=='/api/state':
            with self.server.world.lock:
                try:self._json(200,self.server.world.snapshot(self.headers.get('X-Session','')))
                except GameError as e:self._json(401,{'error':str(e)})
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
                    if not self._local() and not secrets.compare_digest(str(data.get('code','')),self.server.join_code):
                        attempts.append(now);self._json(403,{'error':'Неверный код комнаты.'});return
                    token=self.server.world.join(data.get('name',''),None,data.get('token'),data.get('color'))
                    self._json(200,{'token':token,'state':self.server.world.snapshot(token)});return
                if path=='/api/host':
                    # Room settings are changed only on the host computer itself.
                    if not self._local():self._json(403,{'error':'Настройки меняет только ведущий.'});return
                    if 'ai' in data:self.server.world.settings['ai']=bool(data['ai'])
                    if data.get('new_world'):
                        backup=self.server.world.reset()
                        self._json(200,{'settings':self.server.world.settings,'reset':True,'backup':backup.name if backup else None});return
                    self.server.world.save()
                    if data.get('shutdown'):
                        self._json(200,{'settings':self.server.world.settings,'stopping':True})
                        self.server.stop_event.set()
                        threading.Thread(target=self.server.shutdown,daemon=True).start();return
                    self._json(200,{'settings':self.server.world.settings});return
                if path!='/api/action':self._json(404,{'error':'Команда не найдена.'});return
                token=self.headers.get('X-Session','')
                if token not in self.server.world.players:self._json(401,{'error':'Ведущий начал новую игру. Войди снова.' if time.monotonic()-getattr(self.server.world,'reset_at',-1e9)<600 else 'Нужно войти в комнату.'});return
                result=self.server.world.command(token,data)
                full=data.get('op')!='input' or bool(data.get('full'))
                self._json(200,{'result':result,'state':self.server.world.snapshot(token,full)})
            except GameError as e:self._json(400,{'error':str(e)})
            except (TypeError,ValueError,KeyError):self._json(400,{'error':'Некорректные данные действия.'})

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
    parser.add_argument('--no-ai',action='store_true',help='без компьютерного противника')
    parser.add_argument('--open',action='store_true');args=parser.parse_args()
    world=World(args.save)
    # A room keeps its code across restarts so friends can rejoin with the same code.
    if args.new_code or not world.room_code:world.room_code=str(secrets.randbelow(900000)+100000)
    if args.no_ai:world.settings['ai']=False
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
    def simulation():
        before=time.monotonic()
        while not server.stop_event.wait(.05):
            now=time.monotonic()
            with world.lock:world.tick(now-before)
            before=now
    threading.Thread(target=simulation,daemon=True).start()
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
