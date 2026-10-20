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
from world_data import (VERSION, WORLD_SIZE, FACTIONS, RESOURCES, TOWNS, REGIONS,
                        BASES, BUILDINGS, EVENTS, QUESTS, STORY, WEAPONS, ARMOR, POI_KINDS,
                        POSTS, POST_COST, PRICES, BUILD_TIME, STORAGE_BASE, STORAGE_PER_WAREHOUSE,
                        WEATHER, MAX_LEVEL, XP, PERKS, xp_to_next, max_hp, config)
from terrain import Terrain, town_buildings, resource_nodes, landmark_rect
from npc import NpcMixin, other_faction

ROOT = Path(__file__).resolve().parent
SAVE_VERSION = 2
DISCOVERY_PORT = 8766
STAT_KEYS = ('harvest','build','event','explore','deliver','capture','aid','kills','loot','trade')
FSTAT_KEYS = ('kills','convoy','tribute','post','trade','capture')

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

class World(NpcMixin):
    def __init__(self, save_path=None, rng=None):
        self.lock = threading.RLock()
        self.rng = rng or random.SystemRandom()
        self.save_path = Path(save_path) if save_path else None
        self.players = {}
        self.elapsed = 0.0
        self.production_clock = 0.0
        self.save_clock = 0.0
        self.npc_clock = self.tower_clock = self.post_clock = self.convoy_clock = self.ai_clock = 0.0
        self.event_clock = 0.0
        self.towns = {}
        self.harvested = {}
        self.events_done = {}
        self.log = []
        self.seq = 0
        self.effects = []
        self.winner = None
        self.stocks = {f:dict(wood=44.0,stone=32.0,metal=26.0,food=48.0,fuel=35.0) for f in FACTIONS}
        self.reputation = {f:0 for f in FACTIONS}
        self.buildings = {}
        self.npcs = {}
        self.posts = {}
        self.airdrops = {}
        self.poi_state = {}
        self.weather = {'kind':'clear','until':300.0}
        self.truce = {'until':0.0,'proposal':None,'cooldown':{}}
        self.story = {f:{'index':0,'flags':[],'start':{}} for f in FACTIONS}
        self.fstats = {f:{k:0 for k in FSTAT_KEYS} for f in FACTIONS}
        self.ai_state = {}
        self.settings = {'ai':True}
        self.room_code = None
        self.dirty = False
        self.load_warning = None
        self.terrain = Terrain()
        self._make_world()
        if self.save_path and self.save_path.exists():
            self.load()
        for f in FACTIONS:
            if not self.story[f]['start']:
                self._story_start(f)

    _dist = staticmethod(dist)

    def _make_world(self):
        for t in TOWNS:
            tid,name,x,y,region = t
            owner = next((f for f,b in BASES.items() if b == tid), None)
            self.towns[tid] = {'id':tid,'name':name,'x':x,'y':y,'region':region,
                'owner':owner,'base':bool(owner),'loyalty':70 if owner else 45,
                'levels':{k:(1 if owner and k in ('depot','house') else 0) for k in BUILDINGS},
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

    def _notice(self, title, text='', faction=None, player=None, tone='info', skip=None):
        self.seq += 1
        self.log.append({'id':self.seq,'title':title,'text':text,'faction':faction,'player':player,'tone':tone,'skip':skip})
        self.log=self.log[-60:]

    def _public_player(self, p):
        out={k:p[k] for k in ('id','name','faction','x','y','angle','hp','stamina','vehicle','dead_until','gear','level','xp')}
        out['max_hp']=max_hp(p['level'])
        out['car']={k:p['car'].get(k,0) for k in ('x','y','angle','hp','wrecked_until')}
        out['shot']=p.get('shot',-10);out['busy']=p.get('busy',-10);out['moving']=bool(p['input'][0] or p['input'][1])
        out['sprint']=bool(p['input'][2])
        return out

    def join(self, name, faction, token=None):
        if token in self.players:
            p=self.players[token]
            p['last_seen']=time.monotonic()
            p['name']=str(name).strip()[:20] or p['name']
            return token
        if faction not in FACTIONS:
            raise GameError('Выбери сторону.')
        name=str(name).strip()[:20] or 'Путник'
        now=time.monotonic()
        members=[(t,p) for t,p in self.players.items() if p['faction']==faction]
        if len(members)>=2:
            stale=[(t,p) for t,p in members if now-p['last_seen']>60]
            if not stale:
                raise GameError('На этой стороне уже два игрока. Выбери другую сторону или дождись свободного места.')
            del self.players[stale[0][0]]
        token=secrets.token_urlsafe(32)
        tid=BASES[faction]; town=self.towns[tid]
        slot=len([p for p in self.players.values() if p['faction']==faction])
        p={'id':secrets.token_hex(6),'name':name,'faction':faction,
           'x':town['x']+slot*40,'y':town['y']+70,'angle':0.0,
           'hp':100.0,'stamina':100.0,'vehicle':False,
           'car':{'x':town['x']+90+slot*65,'y':town['y']+25,'angle':0.0,'hp':100.0,'wrecked_until':0.0},
           'dead_until':0.0,'last_seen':now,'last_input':now,'input':[0,0,False],
           'aim':[0,1],'paused':False,'last_action':{},'receipts':OrderedDict(),
           'stats':{k:0 for k in STAT_KEYS},'gear':{'weapon':0,'armor':0},'level':1,'xp':0,
           'visited':[tid],'quests':[],'quest_serial':0,'completed':0,'pending':None}
        self._place_randomly(p)
        for q in range(3):
            p['quests'].append(self._quest(p,q))
        self.players[token]=p
        self._notice(name+' присоединился',FACTIONS[faction])
        self.dirty=True
        return token

    def _spawn_point(self,p):
        """A random roadside spot away from enemies; every player starts somewhere different."""
        f=p['faction']
        enemies=[o for o in self.players.values() if o is not p and o['faction']!=f]
        for attempt in range(80):
            ax,ay,bx,by,a,b=self.rng.choice(self.terrain.road_segments)
            u=self.rng.uniform(.12,.88);length=math.hypot(bx-ax,by-ay) or 1
            nx,ny=-(by-ay)/length,(bx-ax)/length;side=self.rng.choice((-1,1))*self.rng.uniform(70,150)
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
        t=self.towns[BASES[f]]
        return t['x'],t['y']+70,t['x']+90,t['y']+25

    def _place_randomly(self,p):
        x,y,cx,cy=self._spawn_point(p)
        p['x']=x;p['y']=y;p['vehicle']=False
        p['car']={'x':cx,'y':cy,'angle':self.rng.uniform(-math.pi,math.pi),'hp':100.0,'wrecked_until':0.0}
        near=min(self.towns.values(),key=lambda t:dist(t,p))
        self._notice('Ты очнулся у дороги','Рядом: '+near['name']+'. Убежище: '+self.towns[BASES[p['faction']]]['name']+' — метка на карте M.',player=p['id'])

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

    def _quest(self,p,index):
        q=copy.deepcopy(QUESTS[index%len(QUESTS)])
        p['quest_serial']+=1
        q['id']=p['id']+'-q'+str(p['quest_serial'])
        q['start']=p['stats'][q['kind']]
        if q['kind']=='deliver':
            choices=[t for t in self.towns.values() if not t['base']]
            target=min(choices,key=lambda t:dist(p,t))
            q['town']=target['id']; q['text']+=' Место: '+target['name']+'.'
        return q

    def player(self,token):
        p=self.players.get(token)
        if not p:
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
        radio=self.towns[BASES[f]]['levels']['radio']*5
        if method=='scout': return 85
        if method in ('intimidate','gift'): return 80 if method=='intimidate' else 90
        if method=='talk': value=63+(10 if f=='survivors' else -5)+self.reputation[f]*.15+radio+bonus-defense+(5 if self.flag(f,'secret_freq') else 0)
        elif method=='bribe': value=72+bonus+radio-defense*.8
        elif method=='raid': value=58+max(0,allies-1)*10+weapon*5-levels['guard']*10-levels['depot']*3
        else: value=60+(10 if f=='bandits' else 0)+max(0,allies-1)*12+weapon*5+bonus-defense+(8 if self.flag(f,'iron_hand') else 0)
        return int(clamp(value,10,95))

    def chance(self,p,t,method):
        f=p['faction']
        allies=sum(1 for o in self.players.values() if o['faction']==f and o['hp']>0 and dist(o,t)<240 and time.monotonic()-o['last_seen']<8)
        allies+=sum(1 for n in self.npcs.values() if n['faction']==f and n['hp']>0 and n['type'] in ('ranger','raider') and dist(n,t)<240)
        value=self.chance_for(f,t,method,allies,p['gear']['weapon'])
        if self.has_perk(p,25) and method in ('talk','bribe','assault'):value=min(95,value+5)
        return value

    def town_view(self,p,t):
        population,workers,active=self.economy(t)
        result=copy.deepcopy(t)
        result.pop('intel',None)
        result.update(population=population,workers=workers,active=active)
        result['intel']=t['intel'].get(p['faction'],{}).get('bonus',0) if t['intel'].get(p['faction'],{}).get('until',0)>self.elapsed else 0
        result['chances']={m:self.chance(p,t,m) for m in ('talk','bribe','assault','scout','raid')}
        result['event_ready']=self.elapsed>=self.events_done.get(t['id']+':'+p['faction'],0)
        return result

    def snapshot(self,token,full=True):
        p=self.player(token); f=p['faction']; now=time.monotonic()
        me=self._public_player(p)
        for k in ('stats','quests','completed','visited','pending'):
            me[k]=copy.deepcopy(p[k])
        story=self.story[f]; chapter=self._chapter(f)
        out={'version':VERSION,'stamp':time.monotonic(),'time':round(self.elapsed,2),'me':me,
                'players':[self._public_player(o) for o in self.players.values() if now-o['last_seen']<12 or o is p],
                'stock':{k:round(v,2) for k,v in self.stocks[f].items()},'reputation':round(self.reputation[f],1),
                'storage':self.storage(f),
                'towns':{k:self.town_view(p,t) for k,t in self.towns.items()},
                'harvested':{k:v for k,v in self.harvested.items() if v>self.elapsed},
                'npcs':[self.npc_view(n) for n in self.npcs.values() if dist(n,p)<2600 or (n['type']=='convoy' and n['faction']==f)],
                'posts':[{k:o[k] for k in ('id','faction','x','y','hp','name')} for o in self.posts.values()],
                'airdrops':list(self.airdrops.values()),
                'loot':{pid:st.get(f,0) for pid,st in self.poi_state.items() if st.get(f,0)>self.elapsed},
                'weather':self.weather,'truce':{'until':self.truce['until'],'proposal':self.truce['proposal'],
                    'ai':self.ai_faction(other_faction(f))},
                'story':{'index':story['index'],'flags':story['flags'],'chapter':chapter,'ready':self._story_ready(f),
                         'progress':self._story_progress(f)},
                'fstats':self.fstats[f],'ai':{g:self.ai_faction(g) for g in FACTIONS},
                'messages':[e for e in self.log if (e['faction'] in (None,f)) and (e['player'] in (None,p['id'])) and e.get('skip')!=p['id']],
                'effects':self.effects[-40:],'winner':self.winner,'load_warning':self.load_warning,'full':full}
        if not full:
            # Light snapshots between full ones: settlements change slowly, characters move fast.
            del out['towns'],out['harvested']
        return out

    # ---- story ----------------------------------------------------------
    def _chapter(self,f):
        chapters=STORY[f];i=self.story[f]['index']
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
        if kind=='building':return [min(g['level'],self.towns[BASES[f]]['levels'][g['building']]),g['level']]
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
            raise GameError('Ты возвращаешься в убежище. Подожди несколько секунд.')
        # Per-action results are recorded before replying. A network retry cannot spend twice.
        result=self._act(p,op,data)
        p['receipts'][request_id]=result
        while len(p['receipts'])>80: p['receipts'].popitem(last=False)
        self.dirty=True
        if op not in ('shoot','vehicle','heal'):
            p['busy']=self.elapsed
            self.save()
        return result

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
            self._reward(f,{n['kind']:amount}); self.harvested[n['id']]=self.elapsed+100
            p['stats']['harvest']+=1;self.gain_xp(p,'harvest')
            return {'title':'+'+str(amount)+' · '+RESOURCES[n['kind']],'success':True}
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
            if p['vehicle']:
                for angle in (0,math.pi/2,math.pi,3*math.pi/2):
                    x=p['x']+math.cos(angle)*44; y=p['y']+math.sin(angle)*44
                    if not self.blocked(x,y,11):
                        p['x']=x;p['y']=y;p['vehicle']=False
                        return {'title':'Ты вышел из машины'}
                raise GameError('Рядом нет места для выхода. Отъедь немного.')
            if p['car'].get('wrecked_until',0)>self.elapsed: raise GameError('Машина разбита. Её скоро отбуксируют в убежище.')
            self._near(p,p['car'],85)
            p['vehicle']=True;p['x']=p['car']['x'];p['y']=p['car']['y']
            return {'title':'За рулём','text':'WASD — ехать, F — выйти. Топливо общее для фракции.'}
        if op=='repair':
            g=[b for b in self.buildings.values() if b['kind']=='garage' and self.towns[b['town']]['owner']==f and self.towns[b['town']]['levels']['garage']>0 and dist(b,p)<200]
            if not g: raise GameError('Ремонт возможен у своего восстановленного гаража.')
            if dist(p['car'],p)>220: raise GameError('Подгони машину к гаражу.')
            if p['car'].get('hp',100)>=100: raise GameError('Машина исправна.')
            self._pay(f,{'metal':4});p['car']['hp']=100.0
            return {'title':'Машина отремонтирована','text':'−4 металла','success':True}
        if op=='heal':
            if p['hp']>=self.max_hp(p): raise GameError('Ты не ранен.')
            medic=self.has_perk(p,10);cost=3 if medic else 5;amount=45 if medic else 35
            self._cooldown(p,'heal',6);self._pay(f,{'food':cost});p['hp']=min(self.max_hp(p),p['hp']+amount)
            return {'title':'Перевязка','text':'Здоровье +'+str(amount)+', −'+str(cost)+' припасов','success':True}
        if op=='craft':
            item=data.get('item');tier=data.get('tier')
            table={'weapon':WEAPONS,'armor':ARMOR}.get(item)
            if table is None or not isinstance(tier,int) or not 1<=tier<len(table): raise GameError('Неизвестный предмет.')
            ws=[b for b in self.buildings.values() if b['kind']=='workshop' and self.towns[b['town']]['owner']==f and dist(b,p)<170]
            if not ws: raise GameError('Изготовление возможно у мастерской своего поселения.')
            level=max(self.towns[b['town']]['levels']['workshop'] for b in ws)
            if level<table[tier]['workshop']: raise GameError('Нужна мастерская уровня '+str(table[tier]['workshop'])+'.')
            if p['gear'][item]>=tier: raise GameError('У тебя уже есть это или лучше.')
            self._pay(f,table[tier]['cost']);p['gear'][item]=tier;self.gain_xp(p,'craft')
            return {'title':table[tier]['name'],'text':'Снаряжение готово.','success':True}
        if op=='event_open':
            t=self._town_action(p,str(data.get('town')))
            key=t['id']+':'+f
            if self.events_done.get(key,0)>self.elapsed: raise GameError('Здесь пока тихо. Следующее событие появится через несколько минут.')
            if p['pending'] and p['pending']['town']==t['id']: return {'event':p['pending']}
            idx=(list(self.towns).index(t['id'])+int(self.elapsed//240))%len(EVENTS)
            event=copy.deepcopy(EVENTS[idx]); event.update(id=secrets.token_hex(6),town=t['id'])
            for option in event['options']:
                option['chance']=int(clamp(option['chance']+(8 if f=='bandits' and option.get('violent') else 0),10,95))
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
                self._pay(f,{'food':12}); p['stats']['deliver']+=1;self.gain_xp(p,'deliver')
                self.reputation[f]=min(100,self.reputation[f]+4)
                return {'title':'Припасы доставлены','text':'Забери награду в журнале J.','success':True}
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
                if f!='bandits' or t['owner']!=f or t['base']: raise GameError('Дань доступна бандитам в захваченных поселениях.')
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
            if t['base']: raise GameError('Стартовые убежища защищены от захвата.')
            if t['owner'] and self.truce_active(): raise GameError('Действует перемирие: чужие поселения захватывать нельзя.')
            if t['capture']: raise GameError('Уже идёт захват. Помоги удержать площадь.')
            if t['shield']>self.elapsed: raise GameError('После смены владельца поселение защищено две минуты.')
            cooldown_key='attempt:'+f
            if t['cooldowns'].get(cooldown_key,0)>self.elapsed: raise GameError('Подготовка новой попытки ещё не завершена.')
            method=str(data.get('method')) if op=='capture' else str(data.get('method') or 'scout')
            costs={'scout':{'food':3},'intimidate':{'metal':6},'gift':{'food':10},'talk':{'food':12,'wood':8},'bribe':{'food':18,'fuel':8},'assault':{'metal':12,'food':6}}
            prep=method in ('scout','intimidate','gift')
            if method not in costs or (op=='scout')!=prep: raise GameError('Неизвестный способ захвата.')
            if method=='intimidate' and f!='bandits' or method=='gift' and f!='survivors': raise GameError('Этот способ недоступен твоей стороне.')
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
                    'text':('Нужен хотя бы один союзник пешком в круге. Защитники останавливают захват.'+(' Ополчение поднялось на защиту!' if method=='assault' else '') if ok else 'Ресурсы потрачены; повторная попытка станет доступна позже.'),
                    'success':ok,'chance':chance,'roll':roll}
        if op=='claim':
            q=next((q for q in p['quests'] if q['id']==data.get('id')),None)
            if not q or p['stats'][q['kind']]-q['start']<q['target']: raise GameError('Задание ещё не выполнено.')
            self._reward(f,q['reward']);self.reputation[f]=min(100,self.reputation[f]+3)
            p['completed']+=1; idx=p['quests'].index(q)
            # Cycle through varied objectives; only one delivery can be active at once.
            next_index=(p['completed']+2)%len(QUESTS)
            active_kinds={item['kind'] for item in p['quests'] if item is not q}
            while QUESTS[next_index]['kind'] in active_kinds: next_index=(next_index+1)%len(QUESTS)
            p['quests'][idx]=self._quest(p,next_index);self.gain_xp(p,'quest')
            return {'title':'Задание выполнено','text':self.resource_text(q['reward']),'success':True}
        if op=='story_choice':
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
            self._notice('Глава завершена: '+c['title'],p['name']+' выбрал: '+opt['name'],faction=f)
            return {'title':opt['name'],'text':opt['text'],'success':True}
        if op=='shoot':
            if p['vehicle']: raise GameError('Стрелять можно только пешком.')
            weapon=WEAPONS[p['gear']['weapon']]
            self._cooldown(p,'shoot',weapon['cd']*.92)
            self._pay(f,{'metal':weapon['ammo']*(.6 if self.has_perk(p,15) else 1)})
            ax,ay=p['aim'];length=math.hypot(ax,ay) or 1;ax/=length;ay/=length
            if p['gear']['weapon']==2:
                spread=self.rng.uniform(-.05,.05);ax,ay=ax*math.cos(spread)-ay*math.sin(spread),ax*math.sin(spread)+ay*math.cos(spread)
            end=self.shoot_line(p,ax,ay,weapon['range'],weapon['dmg']*(1+.03*(p['level']-1)),28 if p['gear']['weapon']==1 else 20)
            p['shot']=self.elapsed
            self.effects.append({'id':secrets.token_hex(4),'kind':'shot','x':p['x'],'y':p['y'],'ex':end['x'],'ey':end['y'],'until':self.elapsed+.22,'faction':f,'weapon':p['gear']['weapon']})
            return {'quiet':True}
        if op=='loot':
            poi=self.terrain.pois.get(str(data.get('id')))
            if not poi: raise GameError('Место не найдено.')
            self._near(p,poi,170)
            if p['vehicle']: raise GameError('Выйди из машины.')
            st=self.poi_state.setdefault(poi['id'],{})
            if st.get(f,0)>self.elapsed: raise GameError('Тайник уже обыскан. Запасы появятся через '+str(int(st[f]-self.elapsed))+' сек.')
            if any(n['type']=='marauder' and n['hp']>0 and dist(n,poi)<330 for n in self.npcs.values()): raise GameError('Сначала разберись с мародёрами у тайника.')
            loot=POI_KINDS[poi['kind']]['loot'];st[f]=self.elapsed+300
            self._reward(f,loot);p['stats']['loot']+=1;self.gain_xp(p,'loot')
            return {'title':'Тайник: '+poi['name'],'text':self.resource_text(loot),'success':True}
        if op=='airdrop':
            drop=self.airdrops.get(str(data.get('id')))
            if not drop: raise GameError('Груз уже забрали.')
            self._near(p,drop,80)
            del self.airdrops[drop['id']];self._reward(f,drop['loot']);p['stats']['loot']+=1;self.gain_xp(p,'airdrop')
            self._notice('Груз найден',p['name']+' · '+FACTIONS[f])
            return {'title':'Сброшенный груз','text':self.resource_text(drop['loot']),'success':True}
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
            if not self.terrain.on_road(p['x'],p['y'],90): raise GameError('Пост ставится прямо на трассе между поселениями.')
            if self.terrain.in_town(p['x'],p['y'],250): raise GameError('Слишком близко к поселению.')
            if any(dist(o,p)<700 for o in self.posts.values()): raise GameError('Рядом уже стоит пост.')
            if sum(1 for o in self.posts.values() if o['faction']==f)>=3: raise GameError('У фракции уже три поста.')
            self._pay(f,POST_COST)
            post={'id':secrets.token_hex(5),'faction':f,'x':round(p['x'],1),'y':round(p['y'],1),'hp':220,'built':self.elapsed,'name':POSTS[f]['name']}
            self.posts[post['id']]=post;self.fstats[f]['post']+=1;self.gain_xp(p,'post')
            self._notice(POSTS[f]['name']+' поставлен',p['name']+' контролирует трассу.',faction=f)
            return {'title':POSTS[f]['name'],'text':POSTS[f]['desc'],'success':True}
        if op=='truce_propose':
            if self.truce_active(): raise GameError('Перемирие уже действует.')
            if self.truce['cooldown'].get(f,0)>self.elapsed: raise GameError('Новое предложение можно отправить чуть позже.')
            self.truce['cooldown'][f]=self.elapsed+120
            g=other_faction(f)
            if self.ai_faction(g):
                accept=.3+self.reputation[f]/250+(.2 if self.flag(f,'open_signal') else 0)+(.1 if sum(1 for t in self.towns.values() if t['owner']==f)>sum(1 for t in self.towns.values() if t['owner']==g) else 0)
                if self.rng.random()<accept:
                    self._start_truce(f)
                    return {'title':'Перемирие заключено','text':'10 минут без стрельбы и захватов между сторонами.','success':True}
                return {'title':'Предложение отвергнуто','text':FACTIONS[g]+' не доверяют вам. Повысь репутацию.','success':False}
            self.truce['proposal']={'from':f,'until':self.elapsed+90}
            self._notice('Предложение перемирия',FACTIONS[f]+' предлагают 10 минут мира. Ответ — в меню Esc → Дипломатия.',faction=g)
            return {'title':'Предложение отправлено','text':'У другой стороны 90 секунд на ответ.','success':True}
        if op=='truce_accept':
            pr=self.truce['proposal']
            if not pr or pr['from']==f or pr['until']<self.elapsed: raise GameError('Нет действующего предложения.')
            self._start_truce(pr['from'])
            return {'title':'Перемирие заключено','text':'10 минут без стрельбы и захватов.','success':True}
        if op=='truce_break':
            if not self.truce_active(): raise GameError('Перемирия нет.')
            self.truce['until']=0;self.reputation[f]=clamp(self.reputation[f]-15,-100,100)
            self._notice('Перемирие нарушено',FACTIONS[f]+' разорвали договор.',tone='error')
            return {'title':'Перемирие разорвано','text':'Репутация −15.','success':False}
        raise GameError('Неизвестное действие.')

    def _start_truce(self,initiator):
        self.truce['until']=self.elapsed+600;self.truce['proposal']=None
        for f in FACTIONS:self.reputation[f]=clamp(self.reputation[f]+3,-100,100)
        self._notice('Перемирие','Выжившие и бандиты не стреляют друг в друга 10 минут.')

    def _trade(self,p,t,data):
        f=p['faction']
        if t['owner'] not in (None,f) and not self.truce_active(): raise GameError('Торговцы чужой стороны не станут с тобой меняться.')
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
        if f!='bandits': raise GameError('Набеги устраивают бандиты.')
        victim=t['owner']
        if victim not in FACTIONS or victim==f or t['base']: raise GameError('Набег возможен на чужое поселение, кроме убежища.')
        if self.truce_active(): raise GameError('Действует перемирие.')
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
        self._notice('Начался захват',t['name']+' · '+FACTIONS[f]+' удерживают площадь.')
        if method=='assault':
            self.spawn_militia(t,f)

    def _set_owner(self,t,f):
        t['owner']=f;t['construct']={};t['fires']={}
        self.clear_militia(t)

    @staticmethod
    def resource_text(resources):
        return ', '.join(str(v)+' '+RESOURCES[k].lower() for k,v in resources.items() if v) or 'помощь и опыт'

    def _damage(self,p,amount):
        p['hp']=max(0,p['hp']-amount)
        if p['hp']==0 and not p['dead_until']:
            p['dead_until']=self.elapsed+7;p['vehicle']=False;p['input']=[0,0,False]
            self._notice('Ты ранен','Возвращение в убежище через 7 секунд.',player=p['id'],tone='error')

    def _covered(self,a,b):
        length=dist(a,b)
        for step in range(1,int(length/25)):
            mix=step*25/max(length,1)
            if self.terrain.solid(a['x']+(b['x']-a['x'])*mix,a['y']+(b['y']-a['y'])*mix,0): return True
        return False

    def blocked(self,x,y,r):
        if not r<=x<=WORLD_SIZE[0]-r or not r<=y<=WORLD_SIZE[1]-r: return True
        return self.terrain.solid(x,y,r)

    def tick(self,dt):
        now=time.monotonic()
        active=[p for p in self.players.values() if now-p['last_seen']<8]
        if not active or all(p['paused'] for p in active): return
        dt=clamp(dt,0,.1);self.elapsed+=dt;self.production_clock+=dt;self.save_clock+=dt
        self.effects=[e for e in self.effects if e['until']>self.elapsed]
        garage={f:self.towns[BASES[f]]['levels']['garage'] for f in FACTIONS}
        for p in active:
            car=p['car']
            if car.get('wrecked_until',0) and self.elapsed>=car['wrecked_until']:
                t=self.towns[BASES[p['faction']]]
                p['car']={'x':t['x']+90,'y':t['y']+25,'angle':0.0,'hp':100.0,'wrecked_until':0.0}
            if p['hp']<=0:
                if self.elapsed>=p['dead_until']:
                    # Each respawn is a new random roadside spot; the car comes along so nobody is stranded.
                    p['hp']=self.max_hp(p);p['dead_until']=0
                    self._place_randomly(p)
                continue
            x,y,sprint=p['input'] if now-p['last_input']<.65 and not p['paused'] else (0,0,False)
            length=math.hypot(x,y)
            if length>1: x/=length;y/=length
            moving=bool(x or y)
            speed=140
            if p['vehicle']:
                level=garage[p['faction']]
                speed=390*(1+.08*level) if self.stocks[p['faction']]['fuel']>.01 else 0
                if self.weather['kind'] in ('storm','snow'):speed*=.85
                if moving and speed: self.stocks[p['faction']]['fuel']=max(0,self.stocks[p['faction']]['fuel']-dt*.18*(1-.1*level))
            elif sprint and p['stamina']>1 and moving:
                speed=220;p['stamina']=max(0,p['stamina']-dt*22)
            else: p['stamina']=min(100,p['stamina']+dt*14)
            r=22 if p['vehicle'] else 10
            if not p['vehicle'] and self.terrain.water(p['x'],p['y']):speed*=.45
            nx=p['x']+x*speed*dt;ny=p['y']+y*speed*dt
            if not self._blocked_for(p,nx,p['y'],r):p['x']=nx
            if not self._blocked_for(p,p['x'],ny,r):p['y']=ny
            if moving:p['angle']=math.atan2(y,x)
            if p['vehicle']:p['car'].update(x=p['x'],y=p['y'],angle=p['angle'])
            for t in self.towns.values():
                if dist(p,t)<650 and t['id'] not in p['visited']:
                    p['visited'].append(t['id']);p['stats']['explore']+=1;self.gain_xp(p,'explore')
                    self._notice('Новое место',t['name'],player=p['id'])
            home=self.towns[BASES[p['faction']]]
            if dist(p,home)<220:p['hp']=min(self.max_hp(p),p['hp']+dt*4)
        self.tick_npcs(dt,active)
        self.tick_squads()
        self.tick_defenses(dt)
        self.tick_convoys(dt)
        self.tick_ai(dt)
        self._tick_construction(dt,active)
        self._tick_captures(dt,active)
        self._tick_world_events(dt)
        if self.production_clock>=12:
            self.production_clock-=12
            self._produce()
        if not self.winner:
            for f in FACTIONS:
                count=sum(1 for t in self.towns.values() if t['owner']==f)
                if count>=5 and self.towns[BASES[f]]['levels']['radio']>=2:
                    self.winner=f;self._notice('Связь восстановлена',FACTIONS[f]+' связали пять поселений. Мир остаётся доступен для игры.');self.save()
        if self.save_clock>=10:
            self.save_clock=0;self.save()

    def _blocked_for(self,p,x,y,r):
        if self.blocked(x,y,r):return True
        # Cars cannot drive into rivers and lakes; bridges are the roads.
        return p['vehicle'] and self.terrain.water(x,y,8) and not self.terrain.on_road(x,y,70)

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
            enemies=[p for p in active if p['faction']!=f and p['hp']>0 and dist(p,t)<185 and not (self.truce_active() and t['owner'] is None)]
            enemies+=[n for n in self.npcs.values() if n['hp']>0 and n['type']!='convoy' and dist(n,t)<185 and self.hostile(n,{'faction':f})]
            c['contested']=bool(enemies);c['active']=bool(attackers)
            if attackers and not enemies:c['progress']+=dt
            elif not attackers:c['progress']-=dt*1.2
            if c['progress']< -4:
                t['capture']=None;self.clear_militia(t);self._notice('Захват сорван',t['name']+' · атакующие покинули площадь.')
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
                self._notice('Поселение под контролем',t['name']+' · '+FACTIONS[f]);self.dirty=True;self.save()

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
                 'towns':self.towns,'stocks':self.stocks,'reputation':self.reputation,
                 'players':players,'harvested':self.harvested,'events_done':self.events_done,'winner':self.winner,
                 'posts':self.posts,'convoys':convoys,'weather':self.weather,'truce':self.truce,'story':self.story,
                 'fstats':self.fstats,'ai_state':self.ai_state,'poi_state':self.poi_state,'settings':self.settings,
                 'airdrops':self.airdrops,'room_code':self.room_code}
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
            # Validate into temporary structures: a partial read must never replace the live world.
            towns=copy.deepcopy(self.towns)
            for tid,t in towns.items():
                v=raw['towns'].get(tid)
                if v is None:continue        # a settlement added after this save was made
                if v['owner'] not in (None,'survivors','bandits'):raise ValueError('Owner')
                t['owner']=v['owner'];t['levels']={k:int(clamp(finite(v['levels'].get(k,0)),0,3)) for k in BUILDINGS}
                t['loyalty']=clamp(finite(v['loyalty']),0,100)
                for key in ('shield','cooldowns','intel'):t[key]=v.get(key,t[key])
                t['construct']={k:c for k,c in v.get('construct',{}).items() if k in BUILDINGS and isinstance(c,dict)}
                t['cargo']={k:clamp(finite(v.get('cargo',{}).get(k,0)),0,9999) for k in RESOURCES}
                t['fires']={k:finite(u) for k,u in v.get('fires',{}).items() if k in BUILDINGS}
                t['capture']=None
            stocks={f:{r:clamp(finite(raw['stocks'][f][r]),0,99999) for r in RESOURCES} for f in FACTIONS}
            players={}
            for token,p in list(raw.get('players',{}).items())[:4]:
                if p['faction'] not in FACTIONS:raise ValueError('Faction')
                p['x']=clamp(finite(p['x']),25,WORLD_SIZE[0]-25);p['y']=clamp(finite(p['y']),25,WORLD_SIZE[1]-25)
                p.update(last_seen=-1000,last_input=-1000,input=[0,0,False],receipts=OrderedDict(),paused=False)
                gear=p.get('gear') or {}
                p['gear']={'weapon':int(clamp(finite(gear.get('weapon',0)),0,len(WEAPONS)-1)),'armor':int(clamp(finite(gear.get('armor',0)),0,len(ARMOR)-1))}
                p['car'].setdefault('hp',100.0);p['car'].setdefault('wrecked_until',0.0)
                for k in STAT_KEYS:p['stats'].setdefault(k,0)
                p['level']=int(clamp(finite(p.get('level',1),1),1,MAX_LEVEL));p['xp']=max(0,int(finite(p.get('xp',0))))
                players[token]=p
            self.elapsed=max(0,finite(raw['time']));self.production_clock=finite(raw.get('production_clock',0))%12
            self.towns=towns;self.stocks=stocks;self.players=players
            self.reputation={f:clamp(finite(raw['reputation'][f]),-100,100) for f in FACTIONS}
            self.harvested=raw.get('harvested',{});self.events_done=raw.get('events_done',{});self.winner=raw.get('winner')
            self.posts={k:v for k,v in raw.get('posts',{}).items() if v.get('faction') in FACTIONS}
            for n in raw.get('convoys',[]):
                if n.get('faction') in FACTIONS and n.get('type')=='convoy':self.npcs[n['id']]=n
            if isinstance(raw.get('weather'),dict) and raw['weather'].get('kind') in WEATHER:self.weather=raw['weather']
            truce=raw.get('truce')
            if isinstance(truce,dict):self.truce.update(until=finite(truce.get('until')),proposal=None,cooldown={})
            for f in FACTIONS:
                st=(raw.get('story') or {}).get(f)
                if isinstance(st,dict):
                    self.story[f]={'index':int(clamp(finite(st.get('index')),0,len(STORY[f]))),'flags':[str(x) for x in st.get('flags',[])],'start':st.get('start') or {}}
                fs=(raw.get('fstats') or {}).get(f) or {}
                self.fstats[f]={k:int(finite(fs.get(k,0))) for k in FSTAT_KEYS}
            self.ai_state=raw.get('ai_state') or {};self.poi_state=raw.get('poi_state') or {}
            self.settings.update(raw.get('settings') or {});self.airdrops=raw.get('airdrops') or {}
            code=raw.get('room_code')
            self.room_code=code if isinstance(code,str) and len(code)==6 and code.isdigit() else None
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            # Preserve the original damaged file for recovery before autosave writes a new world.
            backup=self.save_path.with_name(self.save_path.stem+'.unreadable-'+str(int(time.time()))+'.json')
            try:os.replace(str(self.save_path),str(backup))
            except OSError:pass
            self.load_warning='Сохранение не удалось прочитать. Его копия сохранена рядом; начат новый мир.'


class GameServer(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    request_queue_size=32

    def __init__(self,address,world,join_code,title='Комната'):
        self.world=world;self.join_code=join_code;self.join_attempts={};self.stop_event=threading.Event()
        self.title=title
        super().__init__(address,Handler)

STATIC={'/':'index.html','/index.html':'index.html','/style.css':'style.css','/game.js':'game.js',
        '/sprites.js':'sprites.js','/render.js':'render.js','/audio.js':'audio.js','/icon.svg':'icon.svg'}
TYPES={'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'application/javascript; charset=utf-8','svg':'image/svg+xml'}

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
                    token=self.server.world.join(data.get('name',''),data.get('faction'),data.get('token'))
                    self._json(200,{'token':token,'state':self.server.world.snapshot(token)});return
                if path=='/api/host':
                    # Room settings are changed only on the host computer itself.
                    if not self._local():self._json(403,{'error':'Настройки меняет только ведущий.'});return
                    if 'ai' in data:self.server.world.settings['ai']=bool(data['ai'])
                    self.server.world.save()
                    if data.get('shutdown'):
                        self._json(200,{'settings':self.server.world.settings,'stopping':True})
                        self.server.stop_event.set()
                        threading.Thread(target=self.server.shutdown,daemon=True).start();return
                    self._json(200,{'settings':self.server.world.settings});return
                if path!='/api/action':self._json(404,{'error':'Команда не найдена.'});return
                token=self.headers.get('X-Session','')
                if token not in self.server.world.players:self._json(401,{'error':'Нужно войти в комнату.'});return
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
