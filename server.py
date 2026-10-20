#!/usr/bin/env python3
"""After Silence: authoritative LAN simulation. No third-party dependencies."""
import argparse
import copy
import hashlib
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
from world_data import (VERSION, WORLD_SIZE, FACTIONS, RESOURCES, TOWNS,
                        BASES, ROADS, BUILDINGS, SLOTS, EVENTS, QUESTS, config)

ROOT = Path(__file__).resolve().parent
SAVE_VERSION = 1

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

class World:
    def __init__(self, save_path=None, rng=None):
        self.lock = threading.RLock()
        self.rng = rng or random.SystemRandom()
        self.save_path = Path(save_path) if save_path else None
        self.players = {}
        self.elapsed = 0.0
        self.production_clock = 0.0
        self.save_clock = 0.0
        self.towns = {}
        self.harvested = {}
        self.events_done = {}
        self.log = []
        self.seq = 0
        self.effects = []
        self.winner = None
        self.stocks = {f:dict(wood=44.0,stone=32.0,metal=26.0,food=48.0,fuel=35.0) for f in FACTIONS}
        self.reputation = {f:0 for f in FACTIONS}
        self.nodes = {}
        self.buildings = {}
        self.dirty = False
        self.load_warning = None
        self._make_world()
        if self.save_path and self.save_path.exists():
            self.load()

    def _make_world(self):
        for idx, t in enumerate(TOWNS):
            tid,name,x,y,region = t
            owner = next((f for f,b in BASES.items() if b == tid), None)
            self.towns[tid] = {'id':tid,'name':name,'x':x,'y':y,'region':region,
                'owner':owner,'base':bool(owner),'loyalty':70 if owner else 45,
                'levels':{k:(1 if owner and k in ('depot','house') else 0) for k in BUILDINGS},
                'capture':None,'shield':0.0,'cooldowns':{},'intel':{}}
            for kind,dx,dy in SLOTS:
                bid=tid+':'+kind
                self.buildings[bid]={'id':bid,'town':tid,'kind':kind,'x':x+dx,'y':y+dy,'w':116 if kind!='guard' else 64,'h':86 if kind!='guard' else 64}
            # Guaranteed nearby supplies prevent an empty-fuel or empty-resource softlock.
            for n in range(24):
                angle=n*2.39996
                radius=490+(n%4)*85
                kind=list(RESOURCES)[n%5]
                nid=tid+':n'+str(n)
                self.nodes[nid]={'id':nid,'kind':kind,'x':x+math.cos(angle)*radius,
                                 'y':y+math.sin(angle)*radius,'amount':{'wood':8,'stone':8,'metal':6,'food':7,'fuel':8}[kind]}
            # A visible first harvest next to each spawn.
            self.nodes[tid+':first']={'id':tid+':first','kind':'wood','x':x+70,'y':y+100,'amount':8}

    def _notice(self, title, text='', faction=None, player=None, tone='info'):
        self.seq += 1
        self.log.append({'id':self.seq,'title':title,'text':text,'faction':faction,'player':player,'tone':tone})
        self.log=self.log[-50:]

    def _public_player(self, p):
        return {k:p[k] for k in ('id','name','faction','x','y','angle','hp','stamina','vehicle','car','dead_until')}

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
           'car':{'x':town['x']+90+slot*65,'y':town['y']+25,'angle':0.0},
           'dead_until':0.0,'last_seen':now,'last_input':now,'input':[0,0,False],
           'aim':[0,1],'paused':False,'last_action':{},'receipts':OrderedDict(),
           'stats':{'harvest':0,'build':0,'event':0,'explore':0,'deliver':0,'capture':0,'aid':0},
           'visited':[tid],'quests':[],'quest_serial':0,'completed':0,'pending':None}
        for q in range(3):
            p['quests'].append(self._quest(p,q))
        self.players[token]=p
        self._notice(name+' присоединился',FACTIONS[faction])
        self.dirty=True
        return token

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

    def _can_pay(self,f,cost):
        return all(self.stocks[f].get(k,0)+1e-6>=v for k,v in cost.items())

    def _pay(self,f,cost):
        if not self._can_pay(f,cost):
            raise GameError('Не хватает ресурсов фракции.')
        for k,v in cost.items():
            self.stocks[f][k]-=v

    def _reward(self,f,reward):
        for k,v in reward.items():
            self.stocks[f][k]=clamp(self.stocks[f].get(k,0)+v,0,99999)

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
        for k in ('farm','sawmill','quarry','workshop','garage'):
            req=BUILDINGS[k]['workers']*t['levels'][k]
            active[k]=bool(req and req<=free)
            if active[k]: free-=req
        return population,population-free,active

    def chance(self,p,t,method):
        f=p['faction']; levels=t['levels']
        intel=t['intel'].get(f,{})
        bonus=intel.get('bonus',0) if intel.get('until',0)>self.elapsed else 0
        allies=sum(1 for o in self.players.values() if o['faction']==f and o['hp']>0 and dist(o,t)<240 and time.monotonic()-o['last_seen']<8)
        defense=levels['guard']*12+levels['depot']*3+(t['loyalty']*.15 if t['owner'] else 0)
        radio=self.towns[BASES[f]]['levels']['radio']*5
        if method=='scout': return 85
        if method=='talk': value=63+(10 if f=='survivors' else -5)+self.reputation[f]*.15+radio+bonus-defense
        elif method=='bribe': value=72+bonus+radio-defense*.8
        else: value=60+(10 if f=='bandits' else 0)+max(0,allies-1)*12+bonus-defense
        return int(clamp(value,10,95))

    def town_view(self,p,t):
        population,workers,active=self.economy(t)
        result=copy.deepcopy(t)
        result.update(population=population,workers=workers,active=active)
        result['chances']={m:self.chance(p,t,m) for m in ('talk','bribe','assault','scout')}
        result['event_ready']=self.elapsed>=self.events_done.get(t['id']+':'+p['faction'],0)
        return result

    def snapshot(self,token):
        p=self.player(token); f=p['faction']; now=time.monotonic()
        me=self._public_player(p)
        for k in ('stats','quests','completed','visited','pending'):
            me[k]=copy.deepcopy(p[k])
        return {'version':VERSION,'stamp':time.monotonic(),'time':round(self.elapsed,2),'me':me,
                'players':[self._public_player(o) for o in self.players.values() if now-o['last_seen']<12 or o is p],
                'stock':{k:round(v,2) for k,v in self.stocks[f].items()},'reputation':self.reputation[f],
                'towns':{k:self.town_view(p,t) for k,t in self.towns.items()},
                'harvested':{k:v for k,v in self.harvested.items() if v>self.elapsed},
                'messages':[e for e in self.log if (e['faction'] in (None,f)) and (e['player'] in (None,p['id']))],
                'effects':self.effects[-30:],'winner':self.winner,'load_warning':self.load_warning}

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
        if op not in ('shoot','vehicle'):
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
            self._reward(f,{n['kind']:n['amount']}); self.harvested[n['id']]=self.elapsed+100
            p['stats']['harvest']+=1
            return {'title':'+'+str(n['amount'])+' · '+RESOURCES[n['kind']],'success':True}
        if op=='build':
            b=self.buildings.get(str(data.get('id')))
            if not b: raise GameError('Здание не найдено.')
            self._near(p,b,155)
            if p['vehicle']: raise GameError('Выйди из машины, чтобы восстановить здание.')
            t=self.towns[b['town']]; k=b['kind']; level=t['levels'][k]
            if t['owner']!=f: raise GameError('Сначала установи контроль над поселением на его площади.')
            if t['capture']: raise GameError('Строительство приостановлено: идёт захват.')
            if level>=3: raise GameError('Достигнут максимальный уровень.')
            if k!='depot' and level>=t['levels']['depot']: raise GameError('Сначала улучши опорный пункт.')
            self._pay(f,self.build_cost(t,k)); t['levels'][k]+=1
            t['loyalty']=min(100,t['loyalty']+4); p['stats']['build']+=1
            return {'title':BUILDINGS[k]['name']+': уровень '+str(level+1),'text':'Поселение: '+t['name'],'success':True}
        if op=='vehicle':
            self._cooldown(p,'vehicle',.4)
            if p['vehicle']:
                for angle in (0,math.pi/2,math.pi,3*math.pi/2):
                    x=p['x']+math.cos(angle)*44; y=p['y']+math.sin(angle)*44
                    if not self.blocked(x,y,11):
                        p['x']=x;p['y']=y;p['vehicle']=False
                        return {'title':'Ты вышел из машины'}
                raise GameError('Рядом нет места для выхода. Отъедь немного.')
            self._near(p,p['car'],85)
            p['vehicle']=True;p['x']=p['car']['x'];p['y']=p['car']['y']
            return {'title':'За рулём','text':'WASD — ехать, F — выйти. Топливо общее для фракции.'}
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
                self._reward(f,option['reward']); p['stats']['event']+=1
                self.reputation[f]=clamp(self.reputation[f]+option.get('rep',0),-100,100)
                if t['owner']==f: t['loyalty']=clamp(t['loyalty']+option.get('rep',0),0,100)
                p['hp']=min(100,p['hp']+option.get('heal',0))
                if option.get('intel'): t['intel'][f]={'bonus':option['intel'],'until':self.elapsed+240}
            else:
                self._damage(p,option['risk']); self.reputation[f]=max(-100,self.reputation[f]-2)
            return {'title':'Решение сработало' if ok else 'Неудача','success':ok,'roll':roll,'chance':option['chance'],
                    'text':('Получено: '+self.resource_text(option['reward']) if ok else 'Затраченные ресурсы потеряны. Здоровье −'+str(option['risk']))+' · Бросок '+str(roll)+' из 100.'}
        if op in ('capture','scout','aid','deliver','tax'):
            t=self._town_action(p,str(data.get('town')))
            if op=='deliver':
                q=next((q for q in p['quests'] if q['kind']=='deliver' and q.get('town')==t['id'] and p['stats']['deliver']-q['start']<q['target']),None)
                if not q: raise GameError('Для этого поселения нет активного задания на доставку.')
                self._pay(f,{'food':12}); p['stats']['deliver']+=1
                self.reputation[f]=min(100,self.reputation[f]+4)
                return {'title':'Припасы доставлены','text':'Забери награду в журнале J.','success':True}
            if op=='aid':
                if t['owner']!=f: raise GameError('Поддерживать можно своё поселение.')
                key='aid:'+f
                if self.elapsed<t['cooldowns'].get(key,0): raise GameError('Жители ещё распределяют предыдущую помощь.')
                self._pay(f,{'food':8});t['loyalty']=min(100,t['loyalty']+14)
                p['stats']['aid']+=1;self.reputation[f]=min(100,self.reputation[f]+3)
                t['cooldowns'][key]=self.elapsed+40
                return {'title':'Жители получили помощь','text':'Лояльность +14.','success':True}
            if op=='tax':
                if f!='bandits' or t['owner']!=f or t['base']: raise GameError('Дань доступна бандитам в захваченных поселениях.')
                if self.elapsed<t['cooldowns'].get('tax',0): raise GameError('Дань уже собрана. Подожди минуту.')
                t['cooldowns']['tax']=self.elapsed+60;t['loyalty']-=18
                self._reward(f,{'metal':12,'food':12})
                if t['loyalty']<20:
                    t['owner']=None;t['loyalty']=45
                    self._notice('Бунт в поселении',t['name']+' снова независимо.')
                return {'title':'Дань собрана','text':'+12 металла и припасов; лояльность −18. При лояльности ниже 20 поселение восстаёт.'}
            if t['owner']==f: raise GameError('Поселение уже принадлежит твоей стороне.')
            if t['base']: raise GameError('Стартовые убежища защищены от захвата.')
            if t['capture']: raise GameError('Уже идёт захват. Помоги удержать площадь.')
            if t['shield']>self.elapsed: raise GameError('После смены владельца поселение защищено две минуты.')
            cooldown_key='attempt:'+f
            if t['cooldowns'].get(cooldown_key,0)>self.elapsed: raise GameError('Подготовка новой попытки ещё не завершена.')
            method='scout' if op=='scout' else str(data.get('method'))
            costs={'scout':{'food':3},'talk':{'food':12,'wood':8},'bribe':{'food':18,'fuel':8},'assault':{'metal':12,'food':6}}
            if method not in costs: raise GameError('Неизвестный способ захвата.')
            chance=self.chance(p,t,method);self._pay(f,costs[method])
            roll=self.rng.randint(1,100);ok=roll<=chance
            t['cooldowns'][cooldown_key]=self.elapsed+(12 if method=='scout' else 35)
            if ok and method=='scout':
                t['intel'][f]={'bonus':20,'until':self.elapsed+240}
                return {'title':'Разведданные получены','text':'+20% к шансу захвата на 4 минуты.','success':True,'chance':chance,'roll':roll}
            if ok:
                t['capture']={'faction':f,'progress':0.0,'duration':30.0,'method':method,'contested':False,'active':True}
                self._notice('Начался захват',t['name']+' · '+FACTIONS[f]+' удерживают площадь.')
            elif method=='assault': self._damage(p,25)
            return {'title':('Удерживай площадь 30 секунд' if method!='scout' else 'Разведка не удалась') if ok else 'Попытка не удалась',
                    'text':('Нужен хотя бы один союзник пешком в круге. Защитники останавливают захват.' if ok else 'Ресурсы потрачены; повторная попытка станет доступна позже.'),
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
            p['quests'][idx]=self._quest(p,next_index)
            return {'title':'Задание выполнено','text':self.resource_text(q['reward']),'success':True}
        if op=='shoot':
            if p['vehicle']: raise GameError('Стрелять можно только пешком.')
            self._cooldown(p,'shoot',.45)
            self._pay(f,{'metal':.12})
            ax,ay=p['aim'];length=math.hypot(ax,ay) or 1;ax/=length;ay/=length
            hit=None; best=440
            for o in self.players.values():
                if o is p or o['faction']==f or o['hp']<=0 or time.monotonic()-o['last_seen']>8: continue
                dx=o['x']-p['x'];dy=o['y']-p['y'];along=dx*ax+dy*ay;side=abs(dx*ay-dy*ax)
                if 0<along<best and side<20 and not self._covered(p,o): hit=o;best=along
            end={'x':p['x']+ax*min(best,430),'y':p['y']+ay*min(best,430)}
            self.effects.append({'id':secrets.token_hex(4),'x':p['x'],'y':p['y'],'ex':end['x'],'ey':end['y'],'until':self.elapsed+.22,'faction':f})
            if hit:
                protected=dist(hit,self.towns[BASES[hit['faction']]])<240
                if not protected: self._damage(hit,18)
            return {'quiet':True}
        raise GameError('Неизвестное действие.')

    @staticmethod
    def resource_text(resources):
        return ', '.join(str(v)+' '+RESOURCES[k].lower() for k,v in resources.items()) or 'помощь и опыт'

    def _damage(self,p,amount):
        p['hp']=max(0,p['hp']-amount)
        if p['hp']==0:
            p['dead_until']=self.elapsed+7;p['vehicle']=False;p['input']=[0,0,False]
            self._notice('Ты ранен','Возвращение в убежище через 7 секунд.',player=p['id'],tone='error')

    def _covered(self,a,b):
        length=dist(a,b)
        for step in range(1,int(length/25)):
            mix=step*25/max(length,1)
            if self.blocked(a['x']+(b['x']-a['x'])*mix,a['y']+(b['y']-a['y'])*mix,0): return True
        return False

    def blocked(self,x,y,r):
        if not r<=x<=WORLD_SIZE[0]-r or not r<=y<=WORLD_SIZE[1]-r: return True
        for b in self.buildings.values():
            if abs(x-b['x'])<b['w']/2+r and abs(y-b['y'])<b['h']/2+r: return True
        return False

    def tick(self,dt):
        now=time.monotonic()
        active=[p for p in self.players.values() if now-p['last_seen']<8]
        if not active or all(p['paused'] for p in active): return
        dt=clamp(dt,0,.1);self.elapsed+=dt;self.production_clock+=dt;self.save_clock+=dt
        self.effects=[e for e in self.effects if e['until']>self.elapsed]
        for p in active:
            if p['hp']<=0:
                if self.elapsed>=p['dead_until']:
                    t=self.towns[BASES[p['faction']]]
                    p['x']=t['x'];p['y']=t['y']+70;p['hp']=100;p['dead_until']=0
                    # Rescue returns the vehicle too, preventing a distant death from stranding it.
                    p['car']={'x':t['x']+90,'y':t['y']+25,'angle':0}
                continue
            x,y,sprint=p['input'] if now-p['last_input']<.65 and not p['paused'] else (0,0,False)
            length=math.hypot(x,y)
            if length>1: x/=length;y/=length
            moving=bool(x or y)
            speed=140
            if p['vehicle']:
                speed=390 if self.stocks[p['faction']]['fuel']>.01 else 0
                if moving and speed: self.stocks[p['faction']]['fuel']=max(0,self.stocks[p['faction']]['fuel']-dt*.18)
            elif sprint and p['stamina']>1 and moving:
                speed=220;p['stamina']=max(0,p['stamina']-dt*22)
            else: p['stamina']=min(100,p['stamina']+dt*14)
            r=22 if p['vehicle'] else 10
            nx=p['x']+x*speed*dt;ny=p['y']+y*speed*dt
            if not self.blocked(nx,p['y'],r):p['x']=nx
            if not self.blocked(p['x'],ny,r):p['y']=ny
            if moving:p['angle']=math.atan2(y,x)
            if p['vehicle']:p['car']={'x':p['x'],'y':p['y'],'angle':p['angle']}
            for t in self.towns.values():
                if dist(p,t)<650 and t['id'] not in p['visited']:
                    p['visited'].append(t['id']);p['stats']['explore']+=1
                    self._notice('Новое место',t['name'],player=p['id'])
            home=self.towns[BASES[p['faction']]]
            if dist(p,home)<220:p['hp']=min(100,p['hp']+dt*4)
        for t in self.towns.values():
            c=t['capture']
            if not c:continue
            attackers=[p for p in active if p['faction']==c['faction'] and p['hp']>0 and not p['vehicle'] and dist(p,t)<160 and not p['paused']]
            enemies=[p for p in active if p['faction']!=c['faction'] and p['hp']>0 and dist(p,t)<185]
            c['contested']=bool(enemies);c['active']=bool(attackers)
            if attackers and not enemies:c['progress']+=dt
            elif not attackers:c['progress']-=dt*1.2
            if c['progress']< -4:
                t['capture']=None;self._notice('Захват сорван',t['name']+' · атакующие покинули площадь.')
            elif c['progress']>=c['duration']:
                f=c['faction'];t['owner']=f;t['shield']=self.elapsed+120
                t['loyalty']=38 if c['method']=='assault' else 72
                if c['method']=='assault':
                    candidates=[k for k in ('house','sawmill','quarry','workshop','farm') if t['levels'][k]>0]
                    if candidates:t['levels'][self.rng.choice(candidates)]-=1
                t['levels']['depot']=max(1,t['levels']['depot']);t['capture']=None
                for p in active:
                    if p['faction']==f:p['stats']['capture']+=1
                self._notice('Поселение под контролем',t['name']+' · '+FACTIONS[f]);self.dirty=True;self.save()
        if self.production_clock>=12:
            self.production_clock-=12
            for t in self.towns.values():
                f=t['owner']
                if not f or t['capture']:continue
                pop,workers,enabled=self.economy(t)
                enough=self.stocks[f]['food']>=pop*.035
                self.stocks[f]['food']=max(0,self.stocks[f]['food']-pop*.035)
                modifier=(.65+t['loyalty']*.005)*(1 if enough else .5)
                for k,on in enabled.items():
                    if on:
                        resource,amount=BUILDINGS[k]['output'];self._reward(f,{resource:amount*t['levels'][k]*modifier})
            self.dirty=True
        if not self.winner:
            for f in FACTIONS:
                count=sum(1 for t in self.towns.values() if t['owner']==f)
                if count>=5 and self.towns[BASES[f]]['levels']['radio']>=2:
                    self.winner=f;self._notice('Связь восстановлена',FACTIONS[f]+' связали пять поселений. Мир остаётся доступен для игры.');self.save()
        if self.save_clock>=10:
            self.save_clock=0;self.save()

    def save(self):
        if not self.save_path:return
        players={}
        for token,p in self.players.items():
            players[token]={k:v for k,v in p.items() if k not in ('last_seen','last_input','input','receipts','paused')}
        payload={'schema':SAVE_VERSION,'time':self.elapsed,'production_clock':self.production_clock,
                 'towns':self.towns,'stocks':self.stocks,'reputation':self.reputation,
                 'players':players,'harvested':self.harvested,'events_done':self.events_done,'winner':self.winner}
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
            if raw.get('schema')!=SAVE_VERSION:raise ValueError('Save version')
            # Validate into temporary structures: a partial read must never replace the live world.
            towns=copy.deepcopy(self.towns)
            for tid,t in towns.items():
                v=raw['towns'][tid]
                if v['owner'] not in (None,'survivors','bandits'):raise ValueError('Owner')
                t['owner']=v['owner'];t['levels']={k:int(clamp(finite(v['levels'][k]),0,3)) for k in BUILDINGS}
                t['loyalty']=clamp(finite(v['loyalty']),0,100)
                for key in ('shield','cooldowns','intel'):t[key]=v.get(key,t[key])
                t['capture']=None
            stocks={f:{r:clamp(finite(raw['stocks'][f][r]),0,99999) for r in RESOURCES} for f in FACTIONS}
            players={}
            for token,p in list(raw.get('players',{}).items())[:4]:
                if p['faction'] not in FACTIONS:raise ValueError('Faction')
                p['x']=clamp(finite(p['x']),25,WORLD_SIZE[0]-25);p['y']=clamp(finite(p['y']),25,WORLD_SIZE[1]-25)
                p.update(last_seen=-1000,last_input=-1000,input=[0,0,False],receipts=OrderedDict(),paused=False)
                players[token]=p
            self.elapsed=max(0,finite(raw['time']));self.production_clock=finite(raw.get('production_clock',0))%12
            self.towns=towns;self.stocks=stocks;self.players=players
            self.reputation={f:clamp(finite(raw['reputation'][f]),-100,100) for f in FACTIONS}
            self.harvested=raw.get('harvested',{});self.events_done=raw.get('events_done',{});self.winner=raw.get('winner')
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

    def __init__(self,address,world,join_code):
        self.world=world;self.join_code=join_code;self.join_attempts={};self.stop_event=threading.Event()
        super().__init__(address,Handler)

class Handler(BaseHTTPRequestHandler):
    server_version='AfterSilence/0.1'

    def log_message(self,fmt,*args):
        if len(args)>1 and str(args[1]) not in ('200','304'):print(fmt%args,flush=True)

    def _json(self,status,value):
        data=json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)))
        self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)

    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/api/config':
            cfg=config();cfg['buildings_world']=list(self.server.world.buildings.values());cfg['nodes']=list(self.server.world.nodes.values())
            cfg['join_code']=self.server.join_code if self.client_address[0] in ('127.0.0.1','::1') else None
            cfg['lan_addresses']=lan_addresses(self.server.server_port) if cfg['join_code'] else []
            self._json(200,cfg);return
        if path=='/api/state':
            with self.server.world.lock:
                try:self._json(200,self.server.world.snapshot(self.headers.get('X-Session','')))
                except GameError as e:self._json(401,{'error':str(e)})
            return
        allowed={'/':'index.html','/index.html':'index.html','/style.css':'style.css','/game.js':'game.js'}
        if path not in allowed:self._json(404,{'error':'Файл не найден'});return
        p=ROOT/'web'/allowed[path]
        try:blob=p.read_bytes()
        except OSError:self._json(404,{'error':'Файл не найден'});return
        self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','css':'text/css; charset=utf-8','js':'application/javascript; charset=utf-8'}[p.suffix[1:]])
        self.send_header('Content-Length',str(len(blob)));self.send_header('Cache-Control','no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
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
                    if ip not in ('127.0.0.1','::1') and not secrets.compare_digest(str(data.get('code','')),self.server.join_code):
                        attempts.append(now);self._json(403,{'error':'Неверный код комнаты.'});return
                    token=self.server.world.join(data.get('name',''),data.get('faction'),data.get('token'))
                    self._json(200,{'token':token,'state':self.server.world.snapshot(token)});return
                if path!='/api/action':self._json(404,{'error':'Команда не найдена.'});return
                token=self.headers.get('X-Session','')
                if token not in self.server.world.players:self._json(401,{'error':'Нужно войти в комнату.'});return
                result=self.server.world.command(token,data)
                self._json(200,{'result':result,'state':self.server.world.snapshot(token)})
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

def run():
    parser=argparse.ArgumentParser(description='После тишины — автономная игра и LAN-сервер')
    parser.add_argument('--host',default='0.0.0.0');parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--save',default=str(Path.home()/'.local/share/after-silence/world.json'))
    parser.add_argument('--open',action='store_true');args=parser.parse_args()
    world=World(args.save);code=str(secrets.randbelow(900000)+100000)
    try:server=GameServer((args.host,args.port),world,code)
    except OSError as exc:
        print('Не удалось открыть порт '+str(args.port)+': '+str(exc),flush=True)
        print('Возможно, игра уже запущена: http://127.0.0.1:'+str(args.port),flush=True)
        return 1
    print('\nПОСЛЕ ТИШИНЫ '+VERSION+'\nНа этом ПК: http://127.0.0.1:'+str(args.port),flush=True)
    print('Для друзей: '+', '.join(lan_addresses(args.port))+'\nКод комнаты: '+code+'\nЗакрытие этого окна завершит игру для всех.\n',flush=True)
    def simulation():
        before=time.monotonic()
        while not server.stop_event.wait(.05):
            now=time.monotonic()
            with world.lock:world.tick(now-before)
            before=now
    threading.Thread(target=simulation,daemon=True).start()
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
