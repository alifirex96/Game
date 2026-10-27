/* After Silence. Local Canvas 2D client. The server owns every game outcome. */
(function () {
'use strict';
const AS = window.AS, R = AS.render, SND = AS.audio;
const $=id=>document.getElementById(id), canvas=$('world'), ctx=canvas.getContext('2d',{alpha:false});
const screen=$('screen'), keys={}, pointer={x:0,y:0};
let cfg=null, state=null, token='', connected=false, joining=false, busy=false, panel='title';
let cw=innerWidth,ch=innerHeight,dpr=1,cam={x:150000,y:150000}, drawPlayers={}, drawNpcs={}, drawCars={};
let last=performance.now(), frame=0, netBusy=false, netFailures=0, latestStamp=0, lastMessage=0, lastHud=0, pollCount=0;
let zoom=Number(readStorage('as-zoom'))||1.3,aim={x:0,y:1}, nearest=null, carNear=null, waypoint=null, lastAimAt=0;
let heroColor=readStorage('as-color'),camKick=0,hurtFlash=0,lastHp=null,deadShown=false;
let lastDry=0,requestSerial=0,lastShot=0,holdMouse=false,showedWarning=false,mapState={zoom:1,fx:null,fy:null,selected:null},mapTr=null;
const palette=AS.colors;
const sideName=id=>id&&state&&state.sides[id]?state.sides[id].name:'Незнакомец';
const sideColor=id=>id&&state&&state.sides[id]?state.sides[id].color:palette.neutral;
const myClan=()=>state&&state.clans[(state.sides[state.me.faction]||{}).clan]||null;
const friendly=id=>!!state&&(id===state.me.faction||!!(myClan()&&myClan().members.includes(id)));
R.friend=id=>friendly(id);
const pathIcons={
 wood:'M5 20V7l7-4 7 4v13M5 11l7-4 7 4M12 7v14M8 13v4M16 13v4',
 stone:'m3 15 4-9 9-2 5 10-5 6H8Z M7 6l3 8 11 0M10 14l-2 6M10 14l6-10',
 metal:'m4 8 13-4 4 5-4 9-13 2-2-6Z M4 8l2 6 15-5M6 14l-2 6',
 food:'M7 6h10l2 4-1 11H6L5 10ZM8 6V3h8v3M8 13h8M12 10v7',
 fuel:'M7 3h7v4l4 3v11H5V7h2ZM7 3h7M9 12l6 6M15 12l-6 6',
 sound:'M4 9h4l5-4v14l-5-4H4ZM17 8q5 4 0 8M17 4q9 8 0 16',
 mute:'M4 9h4l5-4v14l-5-4H4ZM17 9l5 6M22 9l-5 6',
 full:'M8 3H3v5M16 3h5v5M21 16v5h-5M3 16v5h5',
 menu:'M4 6h16M4 12h16M4 18h16',close:'m6 6 12 12M18 6 6 18',
 arrow:'M4 12h16m-6-6 6 6-6 6',car:'m4 9 2-5h12l2 5v10h-3v-3H7v3H4ZM4 9h16M7 12h2M15 12h2',
 walk:'M12 4h0M12 8l-3 6 3 3-2 5M12 8l3 5 4 1M12 16l5 5M10 9l-5 4',
 flag:'M5 22V3m0 1c5-4 8 4 14 0v10c-6 4-9-4-14 0',
 heart:'M12 21 3 12C-3 2 8-1 12 7c4-8 15-5 9 5Z',
 shield:'m12 2 9 4v6q-1 7-9 10-8-3-9-10V6Z',
 radio:'M6 10h12v11H6ZM9 14h6M9 18h6M12 10V3M7 2q-5 4 0 7M17 2q5 4 0 7',
 map:'m3 5 6-3 6 3 6-3v17l-6 3-6-3-6 3ZM9 2v17M15 5v17',
 tool:'M14 3a6 6 0 0 0-7 8L2 18l4 4 7-7a6 6 0 0 0 8-7l-4 3-4-4Z',
 check:'m4 12 5 5 11-11',
 coin:'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 7v10M9 9.5c0-1 1.3-1.8 3-1.8s3 .8 3 1.8-1.3 1.6-3 1.8-3 .8-3 1.8 1.3 1.8 3 1.8 3-.8 3-1.8',
 bag:'M5 8h14l-1 13H6ZM9 8V6a3 3 0 0 1 6 0v2',
 drop:'M12 3s7 7.5 7 12a7 7 0 0 1-14 0c0-4.5 7-12 7-12Z',
 thermo:'M14 14V5a2 2 0 0 0-4 0v9a4 4 0 1 0 4 0ZM12 9v7',
 bowl:'M3 11h18a9 9 0 0 1-18 0ZM8 7c0-2 2-2 2-4M13 7c0-2 2-2 2-4',
 gun:'M2 9h17l2-2v5h-6l-2 4h-3l1-4H6l-2 3H2Z',
 vest:'M7 3 4 6v15h16V6l-3-3-2 3h-6ZM9 10h6M9 14h6',
 trade:'M4 8h13l-3-3M20 16H7l3 3',
 hand:'M7 11V5a2 2 0 0 1 4 0v5V4a2 2 0 0 1 4 0v7V6a2 2 0 0 1 4 0v8a7 7 0 0 1-14 1l-2-4a2 2 0 0 1 3-2Z',
 sun:'M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10M12 1v3M12 20v3M1 12h3M20 12h3M4 4l2 2M18 18l2 2M4 20l2-2M18 6l2-2',
 moon:'M20 15A8 8 0 0 1 9 4a8 8 0 1 0 11 11Z',
 rain:'M7 17a5 5 0 0 1 0-10 6 6 0 0 1 11 2 4 4 0 0 1 0 8M8 20l1-2M12 22l1-3M16 20l1-2',
 snow:'M12 2v20M4 6l16 12M20 6 4 18M9 3l3 3 3-3M9 21l3-3 3 3',
 fog:'M3 9h18M5 13h14M3 17h18M7 5h10',
 storm:'M7 15a5 5 0 0 1 0-10 6 6 0 0 1 11 2 4 4 0 0 1 0 8M12 13l-2 5h4l-2 5',
 peace:'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20M12 2v20M12 12l-7 6M12 12l7 6',
 gear:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1',
 book:'M4 4h7a3 3 0 0 1 3 3v14a2 2 0 0 0-2-2H4ZM20 4h-5a3 3 0 0 0-3 3v14a2 2 0 0 1 2-2h6Z',
 fire:'M12 22a7 7 0 0 0 7-7c0-5-5-8-5-13-3 3-4 5-4 8-1-1-2-2-2-4-2 2-3 5-3 9a7 7 0 0 0 7 7Z'};
function icon(name){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+(pathIcons[name]||pathIcons.tool)+'"/></svg>';}
function icon(name){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+(pathIcons[name]||pathIcons.tool)+'"/></svg>';}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function distance(a,b){return Math.hypot(a.x-b.x,a.y-b.y);}
function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
function readStorage(key){try{return localStorage.getItem(key)||'';}catch(e){return '';}}
function writeStorage(key,v){try{localStorage.setItem(key,v);}catch(e){}}
function notify(title,text,error){const div=document.createElement('div');div.className='toast'+(error?' error':'');div.innerHTML='<b>'+esc(title)+'</b>'+(text?'<p>'+esc(text)+'</p>':'');$('toast-stack').appendChild(div);while($('toast-stack').children.length>3)$('toast-stack').firstChild.remove();setTimeout(()=>div.remove(),5600);}
function beep(kind){SND.play(kind);}
function resize(){cw=innerWidth;ch=innerHeight;dpr=R.quality==='low'?.7:Math.min(devicePixelRatio||1,1.5);canvas.width=Math.round(cw*dpr);canvas.height=Math.round(ch*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);}
// Preferences live in this browser only.
(function prefs(){const q=readStorage('as-quality');if(q)R.quality=q;const m=readStorage('as-music'),s=readStorage('as-sfx');if(m!=='')SND.music=Number(m);if(s!=='')SND.sfx=Number(s);if(readStorage('as-sound')==='off')SND.enabled=false;})();
addEventListener('resize',resize);resize();
R.onSound=(kind,d)=>SND.play(kind,d);
$('sound').innerHTML=icon(SND.enabled?'sound':'mute');$('full').innerHTML=icon('full');$('menu').innerHTML=icon('menu');
$('sound').onclick=()=>{const on=SND.toggle();writeStorage('as-sound',on?'on':'off');$('sound').innerHTML=icon(on?'sound':'mute');beep('ui');};
$('full').onclick=()=>{if(document.fullscreenElement){if(document.exitFullscreen)document.exitFullscreen();}else if(document.documentElement.requestFullscreen)document.documentElement.requestFullscreen().catch(()=>{});};
$('menu').onclick=()=>showPause();$('minimap-wrap').onclick=()=>showMap();
addEventListener('pointerdown',()=>SND.resume(),{once:false});addEventListener('keydown',()=>SND.resume());

// Item helpers: names, icons from web/assets/loot.png, backpack slots.
const itemName=k=>(cfg.items[k]||{}).name||k;
function itemIcon(k,size){size=size||40;const cell=AS.sprites.lootCell(k);if(!cell)return '<i class="li li-none" style="width:'+size+'px;height:'+size+'px"></i>';const s=size/64;
 return '<i class="li" style="width:'+size+'px;height:'+size+'px;background-position:-'+cell.x*s+'px -'+cell.y*s+'px;background-size:'+512*s+'px '+448*s+'px"></i>';}
function slotsUsed(items){return Object.keys(items).reduce((a,k)=>a+Math.ceil(items[k]/((cfg.items[k]||{}).stack||1)),0);}
function slotsMax(){return cfg.backpacks[state.me.gear.backpack].slots;}
const gearTable=kind=>({clothes:cfg.clothes,backpack:cfg.backpacks,armor:cfg.armor})[kind];
function gearItem(kind,tier){return Object.keys(cfg.items).find(k=>{const g=cfg.items[k].gear;return g&&g[0]===kind&&g[1]===tier;});}
const isMelee=w=>!!(cfg.weapons[w]||{}).melee;
// Kilometres as the map shows them: the region is about 15 km across.
const km=d=>(d/20000).toFixed(d<200000?1:0)+' км';

async function fetchJson(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),4500);
 try{const options={headers:{'X-Session':token},signal:controller.signal,cache:'no-store'};
 if(body){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
 const response=await fetch(path,options);const data=await response.json();if(!response.ok){const e=new Error(data.error||'Ошибка соединения');e.status=response.status;throw e;}return data;
 }finally{clearTimeout(timer);}
}
function acceptState(s){if(!s||s.stamp<latestStamp)return;latestStamp=s.stamp;
 if(state&&state.offers&&s.offers)s.offers.forEach(o=>{if(o.to===s.me.id&&!state.offers.some(x=>x.id===o.id))beep('ui');});
 // Light snapshots omit the slow-changing list of harvested spots; keep the last full copy.
 if(!s.full&&state)s.harvested=state.harvested;
 if(!s.harvested)s.harvested={};
 if(s.me.hp<=0&&panel&&panel!=='pause'&&panel!=='settings'&&panel!=='help')closePanel();
 state=s;
 s.messages.forEach(m=>{if(m.id>lastMessage){if(lastMessage!==0){notify(m.title,m.text,m.tone==='error');if(m.tone==='error')beep('error');}lastMessage=m.id;}});
 if(s.load_warning&&!showedWarning){showedWarning=true;notify('Сохранение',s.load_warning,true);}
 if(panel==='inventory'&&invDirty())showInventory();
}
async function join(){if(joining||!cfg)return;joining=true;const btn=$('join');btn.disabled=true;btn.textContent='Подключение…';SND.resume();
 try{const name=$('player-name').value,code=$('room-code')?$('room-code').value.trim():'';token=readStorage('as-token-'+location.host);
 const data=await fetchJson('/api/join',{name,code,token,color:heroColor});token=data.token;writeStorage('as-token-'+location.host,token);writeStorage('as-name',name);writeStorage('as-color',heroColor||'');
 latestStamp=0;lastMessage=0;state=null;acceptState(data.state);connected=true;drawPlayers={};drawNpcs={};drawCars={};cam={x:state.me.x,y:state.me.y};closePanel();$('hud').classList.remove('hidden');
 const camp=myCamp();if(camp&&distance(camp,state.me)>1500)waypoint={x:camp.x,y:camp.y,name:'Лагерь'};
 notify('Ты на берегу Белогорья','Еда, вода, оружие — в домах. E — взять, I — инвентарь. Не беги без нужды: заражённые замечают бегущих издалека.');beep('success');
 }catch(e){notify('Не удалось войти',e.message,true);btn.disabled=false;btn.innerHTML='Войти в мир '+icon('arrow');}finally{joining=false;}}
async function action(op,args){if(busy&&op!=='shoot')return null;if(op!=='shoot')busy=true;
 try{const data=await fetchJson('/api/action',Object.assign({op,request_id:Date.now().toString(36)+'-'+(++requestSerial)+'-'+Math.random().toString(36).slice(2,8)},args||{}));acceptState(data.state);
 const r=data.result||{};if(!r.quiet){notify(r.title||'Готово',r.text||'',r.success===false);beep(r.success===false?'error':op==='camp_build'?'build':op==='harvest'||op==='pickup'||op==='loot_body'?'harvest':'success');}else if(op==='pickup'||op==='loot_body')beep('harvest');return r;
 }catch(e){if(op!=='shoot')notify('Не получилось',e.message,true);if(op!=='shoot')beep('error');return null;}finally{if(op!=='shoot')busy=false;}}
async function network(){if(!connected||!state||netBusy)return;netBusy=true;
 try{const input=readInput();pollCount++;const data=await fetchJson('/api/action',{op:'input',x:input.x,y:input.y,sprint:input.sprint,ax:aim.x,ay:aim.y,paused:panel==='pause'||panel==='settings'||panel==='help'||panel==='new-world',full:pollCount%10===0});acceptState(data.state);netFailures=0;
 }catch(e){netFailures++;if(e.status===401){connected=false;state=null;latestStamp=0;showTitle();notify(/новую игру/.test(e.message)?'Новая игра':'Комната завершилась',/новую игру/.test(e.message)?'Ведущий начал мир с нуля. Войди снова.':'Войди заново.',true);}else if(netFailures===2)notify('Нет связи с ведущим','Персонаж остановлен. Пробую восстановить соединение.',true);
 }finally{netBusy=false;}}
setInterval(network,100);
// Windows over the game do not stop the world: as in DayZ, the inventory is opened in the open.
const STILL=['inventory','craft','camp','people'];
function readInput(){if(panel!==null&&!STILL.includes(panel))return{x:0,y:0,sprint:false};return{x:(keys.KeyD||keys.ArrowRight?1:0)-(keys.KeyA||keys.ArrowLeft?1:0),y:(keys.KeyS||keys.ArrowDown?1:0)-(keys.KeyW||keys.ArrowUp?1:0),sprint:!!(keys.ShiftLeft||keys.ShiftRight)};}
function clearKeys(){Object.keys(keys).forEach(k=>delete keys[k]);holdMouse=false;}
addEventListener('blur',clearKeys);document.addEventListener('visibilitychange',()=>{if(document.hidden){clearKeys();if(connected&&!panel)showPause();}});
addEventListener('keydown',e=>{
 if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;
 if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Tab'].includes(e.code))e.preventDefault();
 keys[e.code]=true;if(e.repeat)return;
 if(e.code==='Escape'){if(panel==='title')return;if(panel)closePanel();else showPause();}
 if(!connected||!state)return;
 if(e.code==='KeyM'){if(panel==='map')closePanel();else showMap();}
 if(e.code==='KeyO'){if(panel==='people')closePanel();else showPeople();}
 if(e.code==='KeyC'){if(panel==='craft')closePanel();else showCraft();}
 if(e.code==='KeyI'||e.code==='Tab'){e.preventDefault();if(panel==='inventory')closePanel();else if(!panel||STILL.includes(panel))showInventory();}
 if(e.code==='KeyL'){if(panel==='camp')closePanel();else{const c=myCamp();if(!c)foundCamp();else if(distance(c,state.me)<(c.house?140:260))showCamp(c);else showCampFar(c);}}
 if(panel&&!STILL.includes(panel))return;
 if(e.code==='KeyE')interact();
 if(e.code==='KeyF')action('vehicle').then(r=>{if(r)beep('door');});
 if(e.code==='KeyH')action('heal');
 if(e.code==='KeyR')action('repair');
 if(e.code==='KeyT')action('refuel');
 if(e.code==='KeyG')quickUse(['canned','beans','meat','crackers','apple','soda'],'Нечего есть. Консервы и сухари лежат в домах, яблоки растут у деревень.');
 if(e.code==='KeyV'){if(R.water(state.me.x,state.me.y,70)&&!state.me.vehicle)action('drink');else quickUse(['water','soda','tea'],'Нет воды. Бутылки лежат в домах; пресная вода — в реках и озёрах.');}
 if(e.code==='KeyQ'){const own=ownWeapons(),i=own.indexOf(state.me.gear.weapon);equip(own[(i+1)%own.length]);}
 if(/^Digit[1-6]$/.test(e.code)){const own=ownWeapons(),n=Number(e.code.slice(5))-1;if(own[n]!=null)equip(own[n]);}
 if(e.code==='KeyX')action('reload');
 if(e.code==='Space'&&!panel)shoot();
});
addEventListener('keyup',e=>{keys[e.code]=false;});
canvas.addEventListener('mousemove',e=>{pointer.x=e.clientX;pointer.y=e.clientY;updateAim();});
function updateAim(){const p=state&&drawPlayers[state.me.id];if(p){const dx=pointer.x-((p.x-cam.x)*zoom+cw/2),dy=pointer.y-((p.y-cam.y)*zoom+ch/2),n=Math.hypot(dx,dy)||1;aim={x:dx/n,y:dy/n};}}
canvas.addEventListener('mousedown',e=>{if(e.button===0&&(!panel||STILL.includes(panel))){if(panel)closePanel();holdMouse=true;shoot();}});addEventListener('mouseup',()=>holdMouse=false);
canvas.addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=clamp(zoom*(e.deltaY<0?1.1:1/1.1),.7,2.2);writeStorage('as-zoom',String(zoom));},{passive:false});
function quickUse(list,empty){const item=list.find(k=>state.me.items[k]>0);if(!item){notify('Пусто',empty,true);return;}action('use',{item});}
// Fists first, then melee, then guns: the order of the number keys.
function ownWeapons(){const rank=w=>w===cfg.fists?-100:isMelee(w)?w-20:w;return state.me.weapons.slice().sort((a,b)=>rank(a)-rank(b));}
function equip(idx){if(idx==null||idx===state.me.gear.weapon)return;action('equip',{weapon:idx}).then(r=>{if(r)beep('door');});}
function weaponCd(){return state?cfg.weapons[state.me.gear.weapon].cd*1000+20:490;}
function shoot(){if(!state||state.me.vehicle||state.me.hp<=0)return;const now=performance.now();lastAimAt=now;if(now-lastShot<weaponCd()||state.me.reload>state.time)return;lastShot=now;
 const wd=cfg.weapons[state.me.gear.weapon];
 if(!wd.melee&&state.me.mag<=0){beep('click');if(state.me.items[wd.ammo_item]>0){action('reload');return;}if(now-lastDry>2500){lastDry=now;notify('Нет патронов',itemName(wd.ammo_item)+': ищи в домах, на базах и у мёртвых.',true);}return;}
 // A light camera kick, stronger for heavy guns.
 if(!wd.melee)camKick=[.6,1.6,.5,2,1.1,2.2,.6][state.me.gear.weapon]||.6;action('shoot');}
function kmh(car){return Math.round(Math.hypot(car.vx||0,car.vy||0)*.225);}
function carOf(id){return state&&(state.cars||[]).find(c=>c.id===id)||null;}
function carSpec(car){return cfg.cars[car&&car.model!=null?car.model:2]||cfg.cars[2];}
function closePanel(){panel=null;screen.className='';screen.innerHTML='';document.body.classList.remove('dialog-open');clearKeys();}
function modal(type,head,body,width){panel=type;document.body.classList.add('dialog-open');screen.className=STILL.includes(type)?'side':'';screen.innerHTML='<section class="modal '+(width||'')+'"><div class="modal-head"><div>'+head+'</div><button class="close" id="close-panel" aria-label="Закрыть">'+icon('close')+'</button></div>'+body+'</section>';$('close-panel').onclick=closePanel;clearKeys();}

function showTitle(){panel='title';document.body.classList.remove('dialog-open');$('hud').classList.add('hidden');screen.className='title-screen';
 const local=cfg&&cfg.join_code,params=new URLSearchParams(location.search),preset=(params.get('code')||'').replace(/\D/g,'').slice(0,6),colors=cfg?cfg.side_colors:[];
 if(!colors.includes(heroColor))heroColor=colors[Math.floor(Math.random()*colors.length)];
 screen.innerHTML='<div class="title-layout"><div class="overline">БЕЛОГОРЬЕ · ПОСЛЕ ЭПИДЕМИИ</div><h1>ПОСЛЕ<br><span>ТИШИНЫ</span></h1><p class="story">Ты очнулся на холодном берегу. В карманах — бинт и яблоко.<br>В городах бродят заражённые. Люди опаснее.<br>Всё, что найдёшь, можно потерять одной пулей.</p><div class="lobby"><label>ПОЗЫВНОЙ<input id="player-name" maxlength="20" value="'+esc(readStorage('as-name')||'Каскад')+'"></label>'+(local?'':'<label>КОД КОМНАТЫ<input id="room-code" inputmode="numeric" maxlength="6" placeholder="6 цифр от ведущего" value="'+esc(preset)+'"></label>')+
 '<div class="look-pick"><span>ЦВЕТ ТОЛСТОВКИ · <b>так тебя узнают другие</b></span><div class="hero-pick"><canvas id="hero-preview" width="96" height="96"></canvas><div class="swatches">'+colors.map(c=>'<button class="swatch'+(c===heroColor?' on':'')+'" data-color="'+c+'" style="background:'+c+'" aria-label="Цвет '+c+'"></button>').join('')+'</div></div></div>'+
 '<button class="primary" id="join">Войти в мир '+icon('arrow')+'</button><button class="quiet" id="help-title">Как играть</button>'+(cfg&&cfg.host?'<button class="quiet danger" id="title-new">Начать новую игру с нуля</button>':'')+'</div><div class="meta">ASTRA LINUX · ДО '+(cfg?cfg.max_players:25)+' ИГРОКОВ · ОДНА ЖИЗНЬ<br>ВЕРСИЯ '+esc(cfg?cfg.version:'')+'</div></div><div class="title-footer">НАЙТИ. ВЫЖИТЬ. НЕ ДОВЕРЯТЬ.</div>'+(local?'<div class="room-card"><span class="eyebrow">КОМНАТА НА ЭТОМ ПК</span><b>Код '+esc(local)+'</b><span>'+(cfg.lan_addresses.length?'Другим игрокам: '+cfg.lan_addresses.map(esc).join('<br>'):'Одиночная игра: сеть не используется.')+'</span><small>Один компьютер хранит мир. После гибели всё остаётся на теле, а ты снова начинаешь на берегу.</small></div>':'');
 $('join').onclick=join;$('help-title').onclick=()=>showHelp(true);if($('title-new'))$('title-new').onclick=confirmNewWorld;
 const preview=()=>{const cv=$('hero-preview');if(!cv)return;const c=cv.getContext('2d');c.clearRect(0,0,96,96);const im=AS.sprites.heroIcon(0,heroColor);if(im)c.drawImage(im,8,8,80,80);else setTimeout(preview,200);};preview();
 screen.querySelectorAll('[data-color]').forEach(b=>b.onclick=()=>{heroColor=b.dataset.color;screen.querySelectorAll('.swatch').forEach(x=>x.classList.toggle('on',x===b));preview();beep('ui');});
 $('player-name').addEventListener('keydown',e=>{if(e.key==='Enter')join();});
}
function showPause(){if(!state)return;modal('pause','<span class="eyebrow">БЕЛОГОРЬЕ</span><h2>Передышка</h2>',
 '<div class="modal-body"><div class="menu-list"><button class="primary" id="resume">Продолжить '+icon('arrow')+'</button><button class="secondary" id="people-menu">'+icon('trade')+' Обмен и группа</button><button class="secondary" id="map-menu">'+icon('map')+' Карта</button><button class="secondary" id="settings-menu">'+icon('gear')+' Настройки</button><button class="secondary" id="help-menu">Управление и правила</button>'+(cfg.host?'<button class="quiet danger" id="new-world">Начать новую игру с нуля</button><button class="quiet danger" id="quit-host">Сохранить мир и завершить игру</button>':'')+'</div><div class="notice">Мир не ставится на паузу, пока в нём есть другие игроки. Мир сохраняется на компьютере ведущего.</div>'+(cfg.join_code&&cfg.lan_addresses.length?'<div class="room-inline"><b>Код комнаты: '+esc(cfg.join_code)+'</b><p>'+cfg.lan_addresses.map(esc).join('<br>')+'</p></div>':'')+'</div>');
 $('resume').onclick=closePanel;$('people-menu').onclick=()=>showPeople();$('map-menu').onclick=()=>showMap();$('help-menu').onclick=()=>showHelp(false);$('settings-menu').onclick=showSettings;
 if($('new-world'))$('new-world').onclick=confirmNewWorld;
 if($('quit-host'))$('quit-host').onclick=async()=>{if(!confirm('Все игроки отключатся, мир будет сохранён. Завершить?'))return;try{await fetchJson('/api/host',{shutdown:true});}catch(e){}connected=false;screen.innerHTML='<section class="modal"><div class="modal-body"><h2>Мир сохранён</h2><p style="margin-top:15px">Игра завершена. Эту вкладку можно закрыть. Чтобы продолжить, снова запусти «Играть.sh» или ярлык.</p></div></section>';};
}
// Host only: wipe the world and start over. The old save stays next to the new one as a backup.
function confirmNewWorld(){modal('new-world','<span class="eyebrow">ВЕДУЩИЙ</span><h2>Новая игра с нуля</h2>',
 '<div class="modal-body"><p>Мир создаётся заново: все игроки, лагеря, машины и вещи исчезнут. Каждому придётся войти снова.</p><p class="small muted" style="margin-top:10px">Старый мир не удаляется — он сохранится рядом резервной копией.</p><div class="event-options" style="margin-top:18px"><button class="primary" id="new-world-yes">Начать заново</button><button class="secondary" id="new-world-no">Отмена</button></div></div>');
 $('new-world-no').onclick=()=>connected?showPause():showTitle();
 $('new-world-yes').onclick=async()=>{try{await fetchJson('/api/host',{new_world:true});}catch(e){notify('Не получилось',e.message,true);return;}
  connected=false;state=null;latestStamp=0;showTitle();notify('Новый мир создан','Войди — всё начнётся с нуля. Другие игроки тоже войдут заново.');};}
function showSettings(){modal('settings','<span class="eyebrow">ЭТОТ КОМПЬЮТЕР</span><h2>Настройки</h2>',
 '<div class="modal-body"><label class="setting">Музыка<input type="range" id="vol-music" min="0" max="1" step="0.05" value="'+SND.music+'"></label><label class="setting">Звуки и окружение<input type="range" id="vol-sfx" min="0" max="1" step="0.05" value="'+SND.sfx+'"></label><label class="setting">Качество графики<select id="quality"><option value="high">Высокое: свет, частицы, погода</option><option value="low">Экономное: для слабых компьютеров</option></select></label><button class="primary" id="settings-done" style="width:100%;margin-top:18px">Готово</button></div>');
 $('quality').value=R.quality;
 $('vol-music').oninput=e=>{SND.setVolume('music',Number(e.target.value));writeStorage('as-music',e.target.value);};
 $('vol-sfx').oninput=e=>{SND.setVolume('sfx',Number(e.target.value));writeStorage('as-sfx',e.target.value);beep('ui');};
 $('quality').onchange=e=>{R.quality=e.target.value;writeStorage('as-quality',R.quality);resize();};
 $('settings-done').onclick=closePanel;
}
function showHelp(fromTitle){modal('help','<span class="eyebrow">ПАМЯТКА ВЫЖИВШЕГО</span><h2>Как здесь выжить</h2>',
 '<div class="modal-body"><div class="controls-grid"><span><kbd>W A S D</kbd></span><span>Ходьба; на машине — газ, тормоз, руль</span><span><kbd>Shift</kbd></span><span>Бег (заражённые замечают бегущих вдвое дальше); в машине — ручник</span><span>Мышь + ЛКМ / <kbd>Space</kbd></span><span>Удар или выстрел</span><span><kbd>E</kbd></span><span>Подобрать вещь, обыскать тело, срубить дерево, лагерь</span><span><kbd>I</kbd></span><span>Инвентарь: что на тебе, в рюкзаке и рядом на земле</span><span><kbd>Q</kbd> / <kbd>1</kbd>–<kbd>6</kbd></span><span>Сменить оружие</span><span><kbd>X</kbd></span><span>Перезарядка</span><span><kbd>H</kbd> / <kbd>G</kbd> / <kbd>V</kbd></span><span>Перевязка / поесть / попить</span><span><kbd>F</kbd></span><span>Сесть в машину или выйти</span><span><kbd>R</kbd> / <kbd>T</kbd></span><span>Ремкомплект / заправка (у колонки или из канистры)</span><span><kbd>L</kbd> / <kbd>C</kbd></span><span>Лагерь / крафт</span><span><kbd>O</kbd></span><span>Обмен с игроком рядом и группа</span><span><kbd>M</kbd> / <kbd>Esc</kbd></span><span>Карта / меню</span></div>'+
 '<p class="control-note">Ты начинаешь на побережье с бинтом и яблоком. Всё остальное лежит в домах: еда и вода — в жилых, лекарства — в больницах, инструменты — на заводах и в колхозах, оружие и патроны — на военных базах, в палатках и на аэродроме. Дома со временем снова наполняются.</p>'+
 '<p class="control-note" style="margin-top:12px">Заражённые бродят в каждом городе и у каждого заброшенного места. Они видят бегущих издалека, идущих — ближе, стоящих — совсем рядом; ночью и в тумане хуже. Выстрел, мотор и удары топора слышны далеко — на шум сбегаются. Укус может открыть кровотечение и занести заразу: перевяжись (H), от заразы и отравления помогает тетрациклин.</p>'+
 '<p class="control-note" style="margin-top:12px">Пресную воду пьют из рек и озёр (V), морскую — нельзя. Сырая вода и сырое мясо могут отравить: мясо жарят у костра. Холод опаснее ночью, в дождь и на севере — ищи тёплую одежду.</p>'+
 '<p class="control-note" style="margin-top:12px">Машины стоят у дорог и во дворах и ничьи: садись (F) и езжай, если в баке есть бензин. Заправка — у колонок на заправках или из канистры (T), ремонт — ремкомплектом (R). Оружие и одежда лежат на земле как вещи; больше трёх стволов не унести.</p>'+
 '<p class="control-note" style="margin-top:12px">Погибнешь — всё, что было на тебе, останется на теле, и его заберёт любой. Ты снова очнёшься на берегу. Другие игроки — главная опасность и главная надежда: можно меняться (O), собрать группу до 6 человек и построить лагерь (L) в пустом доме или в лесу.</p><p class="small muted" style="margin-top:14px">Графика из свободных наборов: Zombie sprites — Riley Gombart, OpenGameArt.org (OGA-BY 3.0); Trees — Liosan, OpenGameArt.org (CC-BY 3.0); деревья prime8 и иконки предметов Broken Vector и авторов Openclipart (CC0). Полный список — web/assets/CREDITS.md.</p><button class="primary" id="help-back" style="width:100%;margin-top:20px">Понятно</button></div>');
 $('help-back').onclick=fromTitle?showTitle:closePanel;$('close-panel').onclick=fromTitle?showTitle:closePanel;
}

/* ---------- inventory: what is worn, what is in the backpack, and what lies around ---------- */
let invKey='';
function nearbyLoot(){const me=state.me;return (state.loot||[]).filter(l=>distance(l,me)<70).sort((a,b)=>distance(a,me)-distance(b,me));}
function nearbyBody(){const me=state.me;return (state.bodies||[]).filter(b=>distance(b,me)<90&&Object.keys(b.items).length).sort((a,b)=>distance(a,me)-distance(b,me))[0]||null;}
function invSignature(){const me=state.me,b=nearbyBody();return JSON.stringify([me.items,me.weapons,me.gear,me.mags,nearbyLoot().map(l=>l.id+':'+l.n),b?[b.id,b.items]:0]);}
function invDirty(){return invSignature()!==invKey;}
function showInventory(){if(!state)return;const me=state.me;invKey=invSignature();
 const row=(ic,name,sub,btns)=>'<div class="inv-row">'+ic+'<div class="inv-text"><b>'+name+'</b>'+(sub?'<small>'+sub+'</small>':'')+'</div><div class="inv-btns">'+btns+'</div></div>';
 // Worn and carried.
 let worn='';
 ownWeapons().forEach((w,i)=>{const wd=cfg.weapons[w],key=cfg.weapon_item[w];if(w===cfg.fists)return;
  worn+=row(itemIcon(key,40),esc(wd.name)+(w===me.gear.weapon?' · в руках':''),wd.melee?'Ближний бой · урон '+wd.dmg:'Магазин '+(me.mags[String(w)]||0)+' / '+wd.mag+' · '+esc(itemName(wd.ammo_item)),
   (w===me.gear.weapon?'':'<button class="quiet" data-equip="'+w+'">'+(i+1)+' · В руки</button>')+'<button class="quiet danger" data-drop="w:'+w+'">Бросить</button>');});
 ['clothes','backpack','armor'].forEach(kind=>{const tier=me.gear[kind],t=gearTable(kind)[tier];if(!tier)return;const key=gearItem(kind,tier);
  worn+=row(itemIcon(key,40),esc(t.name),kind==='clothes'?'Тепло +'+t.warm:kind==='backpack'?t.slots+' мест':'Пули теряют '+Math.round(t.reduce*100)+'% урона','<button class="quiet danger" data-drop="gear:'+kind+'">Снять</button>');});
 if(!worn)worn='<p class="small muted">Только ветровка и кулаки. Одежду, рюкзаки и оружие ищи в домах — они лежат на полу.</p>';
 // Backpack.
 const used=slotsUsed(me.items),room=slotsMax();
 let pack=Object.keys(me.items).map(k=>{const it=cfg.items[k]||{},usable=it.food!=null||it.water!=null||it.hp!=null||it.stop_bleed||it.cure||it.warmth;
  return row(itemIcon(k,40),esc(it.name)+' <span class="muted">×'+me.items[k]+'</span>',esc(it.desc||''),(usable?'<button class="quiet" data-use="'+k+'">Использовать</button>':'')+'<button class="quiet danger" data-drop="'+k+'" data-n="'+me.items[k]+'">Бросить</button>');}).join('');
 if(!pack)pack='<p class="small muted">Пусто.</p>';
 // On the ground and on a body nearby.
 const loot=nearbyLoot(),body=nearbyBody();
 let near=loot.map(l=>{const it=cfg.items[l.item]||{};return row(itemIcon(l.item,40),esc(it.name)+(l.n>1?' <span class="muted">×'+l.n+'</span>':''),it.weapon!=null&&!isMelee(it.weapon)&&l.mag?'В магазине '+l.mag:esc(it.desc||''),'<button class="secondary" data-pick="'+l.id+'">Взять</button>');}).join('');
 if(body){near+='<span class="eyebrow shop-eyebrow">'+esc(body.name.toUpperCase())+'</span>'+Object.keys(body.items).map(k=>row(itemIcon(k,40),esc(itemName(k))+(body.items[k]>1?' <span class="muted">×'+body.items[k]+'</span>':''),'','<button class="secondary" data-take="'+k+'">Взять</button>')).join('')+'<button class="quiet" id="take-all" style="width:100%;margin-top:6px">Забрать всё, что влезет</button>';}
 if(!near)near='<p class="small muted">Рядом ничего. Подойди к вещам на земле или к телу.</p>';
 modal('inventory','<span class="eyebrow">ИНВЕНТАРЬ · I</span><h2>'+esc(me.name)+'</h2>',
  '<div class="modal-body inv">'+vitalsHtml(true)+'<div class="inv-cols"><div><span class="eyebrow shop-eyebrow">НА ТЕБЕ</span>'+worn+'</div><div><span class="eyebrow shop-eyebrow">РЮКЗАК · '+used+' / '+room+'</span>'+pack+'</div><div><span class="eyebrow shop-eyebrow">РЯДОМ</span>'+near+'</div></div></div>','wide');
 screen.querySelectorAll('[data-use]').forEach(b=>b.onclick=()=>action('use',{item:b.dataset.use}));
 screen.querySelectorAll('[data-equip]').forEach(b=>b.onclick=()=>equip(Number(b.dataset.equip)));
 screen.querySelectorAll('[data-drop]').forEach(b=>b.onclick=()=>action('drop',{item:b.dataset.drop,count:Number(b.dataset.n||1)}));
 screen.querySelectorAll('[data-pick]').forEach(b=>b.onclick=()=>action('pickup',{id:b.dataset.pick}));
 screen.querySelectorAll('[data-take]').forEach(b=>b.onclick=()=>action('loot_body',{id:body.id,item:b.dataset.take}));
 if($('take-all'))$('take-all').onclick=()=>action('loot_body',{id:body.id});
}
function vitalsHtml(big){const me=state.me,bar=(ic,v,label,cls)=>'<div class="vital '+cls+(v<25?' low':'')+'" title="'+label+'">'+icon(ic)+'<i><em style="width:'+Math.round(v)+'%"></em></i>'+(big?'<b>'+label+' '+Math.round(v)+'%</b>':'')+'</div>';
 return '<div class="vitals'+(big?' big':'')+'">'+bar('bowl',me.food,'Сытость','food')+bar('drop',me.water,'Вода','water')+bar('thermo',me.warmth,'Тепло','warm')+(me.bleeding?'<span class="chip bad">Кровотечение · H</span>':'')+(me.sick>state.time?'<span class="chip bad">Болен · тетрациклин</span>':'')+'</div>';}

/* ---------- camps ---------- */
function myCamp(){if(!state)return null;const own=(state.sides[state.me.faction]||{}).camp;
 return own?(state.camps||[]).find(c=>c.id===own)||null:(state.camps||[]).find(c=>campCanUse(c))||null;}
function needsHtml(needs){return Object.keys(needs||{}).map(k=>{const have=state.me.items[k]||0;return '<span class="cost '+(have>=needs[k]?'good':'bad')+'"><b>'+esc(itemName(k))+'</b> '+have+' / '+needs[k]+'</span>';}).join(' ');}
function hasNeeds(needs){return Object.keys(needs||{}).every(k=>(state.me.items[k]||0)>=needs[k]);}
function campCanUse(c){return c.owner===state.me.faction||friendly(c.owner);}
const CAMP_KINDS=['fire','stash','bench','collector'];
// The own camp seen from afar: where it is, what stands there, a waypoint, and abandoning it without walking back.
function showCampFar(camp){const me=state.me,parts=cfg.camp_parts,near=cfg.towns.slice().sort((a,b)=>distance(a,camp)-distance(b,camp))[0];
 const built=CAMP_KINDS.filter(k=>camp.parts[k]&&camp.parts[k].hp>0).map(k=>camp.house&&parts[k].house_name?parts[k].house_name:parts[k].name);
 const owner=camp.owner===me.faction;
 let h='<div class="modal-body"><p>'+(camp.house?'Обжитый дом':'Лагерь под открытым небом')+' у места <b>'+esc(near?near.name:'—')+'</b> · отсюда '+km(distance(camp,me))+'.</p>'+
  '<p class="small muted" style="margin-top:8px">Постройки: '+(built.length?esc(built.join(', ')):'пока нет')+'. Ограда '+(camp.breached?'не закрыта':'закрыта')+'.</p>'+
  '<div class="event-options" style="margin-top:16px"><button class="primary" id="camp-way">Указатель к лагерю</button>'+(owner?'<button class="quiet danger" id="camp-far-abandon">Бросить лагерь отсюда</button>':'')+'</div>'+
  (owner?'<p class="small muted" style="margin-top:10px">Постройки исчезнут. Вещи из ящика останутся лежать на месте лагеря — их сможет забрать любой.</p>':'<p class="small muted" style="margin-top:10px">Это лагерь твоей группы; бросить его может только хозяин.</p>')+'</div>';
 modal('camp-far','<span class="eyebrow">ТВОЙ ЛАГЕРЬ · ДАЛЕКО</span><h2>'+(camp.house?'Обжитый дом':'Лагерь')+' · '+esc(sideName(camp.owner))+'</h2>',h);
 $('camp-way').onclick=()=>{waypoint={x:camp.x,y:camp.y,name:'Лагерь'};closePanel();notify('Указатель на лагерь','Следуй стрелке.');};
 const ab=$('camp-far-abandon');if(ab)ab.onclick=async()=>{
  if(!ab.dataset.sure){ab.dataset.sure='1';ab.textContent='Точно бросить? Нажми ещё раз';ab.classList.add('armed');return;}
  const r=await action('camp_abandon',{camp:camp.id});if(!r)return;if(waypoint&&waypoint.name==='Лагерь')waypoint=null;closePanel();};}
function showCamp(camp){if(!state)return;if(!camp){foundCamp();return;}
 const own=campCanUse(camp),parts=cfg.camp_parts,house=!!camp.house,me=state.me;
 let h='<div class="modal-body"><p>'+(house?'Лагерь в заброшенном доме: стены уже стоят, нужна только дверь.':'Лагерь под открытым небом: обнеси его частоколом из восьми секций с воротами.')+' '+(camp.breached?'<b class="bad">Ограда не закрыта — чужие могут залезть в ящик.</b>':'<b class="good">Ограда закрыта.</b>')+'</p>';
 if(own){h+='<span class="eyebrow shop-eyebrow">ПОСТРОЙКИ</span><div class="craft-grid">';
  CAMP_KINDS.forEach(k=>{const def=parts[k],part=camp.parts[k],built=part&&part.hp>0,name=house&&def.house_name?def.house_name:def.name;
   h+='<button class="decision" data-build="'+k+'" '+(built||!hasNeeds(def.needs)?'disabled':'')+'><div><b>'+esc(name)+'</b><strong>'+(built?'есть · '+part.hp+'/'+part.max:'')+'</strong></div><small>'+esc(def.desc)+'</small><span class="decision-cost">'+(built?'':needsHtml(def.needs))+'</span></button>';});
  const walls=Object.values(camp.fence).filter(f=>!f.house&&f.kind==='wall'&&f.hp>0).length,gate=camp.fence.gate&&camp.fence.gate.hp>0;
  if(!house)h+='<button class="decision" data-build="wall" '+(walls>=8||!hasNeeds(parts.wall.needs)?'disabled':'')+'><div><b>Частокол</b><strong>'+walls+' / 8</strong></div><small>'+esc(parts.wall.desc)+'</small><span class="decision-cost">'+needsHtml(parts.wall.needs)+'</span></button>';
  const holes=Object.values(camp.fence).filter(f=>f.house&&f.hp<=0).length;
  if(house&&holes)h+='<button class="decision" data-build="wall" '+(!hasNeeds(parts.wall.needs)?'disabled':'')+'><div><b>Заделать стену</b><strong>пробито: '+holes+'</strong></div><small>Пробитую стену дома закрывают досками.</small><span class="decision-cost">'+needsHtml(parts.wall.needs)+'</span></button>';
  h+='<button class="decision" data-build="gate" '+(gate||!hasNeeds(parts.gate.needs)?'disabled':'')+'><div><b>'+(house?'Дверь':'Ворота')+'</b><strong>'+(gate?'есть':'')+'</strong></div><small>'+esc(parts.gate.desc)+'</small><span class="decision-cost">'+(gate?'':needsHtml(parts.gate.needs))+'</span></button></div>';}
 else h+='<div class="notice">Это чужой лагерь ('+esc(sideName(camp.owner))+'). '+(camp.breached?'Ограда пробита: ящик можно открыть.':'Чтобы добраться до ящика, пробей стену или ворота: стреляй или ломай (E вплотную).')+'</div>';
 if(camp.stash&&camp.parts.stash&&camp.parts.stash.hp>0){const st=camp.stash,canPut=k=>!cfg.items[k].weapon&&!cfg.items[k].gear;
  h+='<span class="eyebrow shop-eyebrow">ЯЩИК · '+slotsUsed(st.items)+' / '+cfg.stash_slots+' МЕСТ</span><div class="stash-cols"><div><b>Рюкзак</b>'+(own?Object.keys(me.items).filter(canPut).map(k=>'<div class="stash-row">'+itemIcon(k,28)+'<span>'+esc(itemName(k))+' ×'+me.items[k]+'</span><button class="quiet" data-put="'+k+'" data-n="'+me.items[k]+'">Положить</button></div>').join(''):'<p class="small muted">Класть в чужой ящик нельзя.</p>')+'</div><div><b>Ящик</b>'+Object.keys(st.items).map(k=>'<div class="stash-row">'+itemIcon(k,28)+'<span>'+esc(itemName(k))+' ×'+st.items[k]+'</span><button class="quiet" data-take="'+k+'" data-n="'+st.items[k]+'">Взять</button></div>').join('')+'</div></div>';}
 if(own)h+='<p class="small muted" style="margin-top:12px">C — крафт: у костра жарят мясо и заваривают чай, на верстаке делают гвозди, ремкомплекты, куртку и обрез. У костра заживают раны и не мёрзнешь.</p>'+(camp.owner===me.faction?'<button class="quiet danger" id="camp-abandon" style="width:100%;margin-top:10px">Бросить лагерь</button>':'');
 h+='</div>';
 modal('camp','<span class="eyebrow">'+(own?'ТВОЙ ЛАГЕРЬ':'ЧУЖОЙ ЛАГЕРЬ')+'</span><h2>'+(house?'Обжитый дом':'Лагерь')+' · '+esc(sideName(camp.owner))+'</h2>',h,'wide');
 const again=()=>{const c=(state.camps||[]).find(x=>x.id===camp.id);if(c)showCamp(c);else closePanel();};
 screen.querySelectorAll('[data-build]').forEach(b=>b.onclick=async()=>{const r=await action('camp_build',{camp:camp.id,kind:b.dataset.build});if(r)setTimeout(again,150);});
 screen.querySelectorAll('[data-put]').forEach(b=>b.onclick=async()=>{await action('stash_put',{camp:camp.id,item:b.dataset.put,count:Number(b.dataset.n)});setTimeout(again,150);});
 screen.querySelectorAll('[data-take]').forEach(b=>b.onclick=async()=>{await action('stash_take',{camp:camp.id,item:b.dataset.take,count:Number(b.dataset.n)});setTimeout(again,150);});
 if($('camp-abandon'))$('camp-abandon').onclick=async()=>{if(!confirm('Бросить лагерь? Постройки исчезнут, вещи из ящика останутся лежать.'))return;await action('camp_abandon',{camp:camp.id});closePanel();};
}
function foundCamp(){const p=state.me,house=R.houseAt(p.x,p.y,-6);
 modal('camp','<span class="eyebrow">НОВЫЙ ЛАГЕРЬ</span><h2>'+(house?'Поселиться в этом доме':'Разбить лагерь здесь')+'</h2>','<div class="modal-body"><p>'+(house?'Стены у дома уже есть. Поставь дверь — и чужие не войдут, пока не выломают её или стену.':'Нужна ровная площадка примерно 200 × 200 без дорог и воды. Лагерь придётся обнести частоколом из восьми секций с воротами.')+'</p><p class="small muted">Лагерь у тебя один, группа пользуется им вместе с тобой. В нём строят костёр, ящик, верстак и сборник воды — из досок, гвоздей, ткани и металлолома. Лагерь переживает твою гибель.</p><button class="primary" id="camp-ok" style="width:100%;margin-top:14px">'+(house?'Поселиться':'Основать лагерь')+'</button></div>');
 $('camp-ok').onclick=async()=>{const r=await action('camp_found');if(r)setTimeout(()=>showCamp(myCamp()),200);};}
function nearPart(kind,r){return (state.camps||[]).some(c=>campCanUse(c)&&c.parts[kind]&&c.parts[kind].hp>0&&distance(c.parts[kind],state.me)<r);}
function showCraft(){if(!state)return;const me=state.me,fire=nearPart('fire',110),bench=nearPart('bench',90);
 const groups=[['hand','В РУКАХ',true],['fire','У ОГНЯ'+(fire?'':' · нужен костёр в лагере'),fire],['bench','НА ВЕРСТАКЕ'+(bench?'':' · нужен верстак в лагере'),bench]];
 let h='<div class="modal-body"><p class="small muted">Рюкзак: '+slotsUsed(me.items)+' / '+slotsMax()+' мест.</p>';
 groups.forEach(([at,title,ok])=>{h+='<span class="eyebrow shop-eyebrow">'+title+'</span><div class="craft-grid">';
  cfg.recipes.filter(r=>r.at===at).forEach(r=>{const from=r.weapon_from,hasGun=!from||me.weapons.includes(from[0]),can=ok&&hasNeeds(r.needs)&&hasGun;
   const what=r.makes?Object.keys(r.makes).map(k=>itemName(k)+(r.makes[k]>1?' ×'+r.makes[k]:'')).join(', '):from?'из ружья: '+cfg.weapons[from[0]].name.toLowerCase():'надеть сразу';
   h+='<button class="decision" data-craft-id="'+r.id+'" '+(can?'':'disabled')+'><div><b>'+esc(r.name)+'</b></div><small>'+esc(what)+'</small><span class="decision-cost">'+needsHtml(r.needs)+(from&&!hasGun?' <span class="cost bad">нет ружья</span>':'')+'</span></button>';});
  h+='</div>';});
 modal('craft','<span class="eyebrow">РЕМЕСЛО · C</span><h2>Крафт</h2>',h+'</div>','wide');
 screen.querySelectorAll('[data-craft-id]').forEach(b=>b.onclick=async()=>{const r=await action('craft_item',{id:b.dataset.craftId});if(r)setTimeout(showCraft,150);});}

/* ---------- people: trade and groups ---------- */
function showPeople(tab){if(!state)return;tab=tab||'trade';const me=state.me,f=me.faction,clan=myClan();
 let html='<div class="modal-body"><div class="tabs"><button class="tab '+(tab==='trade'?'on':'')+'" data-ptab="trade">'+icon('trade')+' Обмен</button><button class="tab '+(tab==='clan'?'on':'')+'" data-ptab="clan">'+icon('flag')+' Группа'+(state.invites.length?' · '+state.invites.length:'')+'</button></div>';
 if(tab==='trade'){
  const offers=state.offers||[];
  if(offers.length){html+='<span class="eyebrow shop-eyebrow">ПРЕДЛОЖЕНИЯ</span>';offers.forEach(o=>{const mine=o.from===me.id;html+='<div class="quest-card"><div class="section-label"><span>'+(mine?'ТЫ → '+esc(o.to_name):esc(o.from_name)+' → ТЕБЕ')+'</span><b>'+Math.max(0,Math.ceil(o.until-state.time))+' с</b></div><p>'+(mine?'Отдаёшь':'Отдаёт')+': <b>'+esc(o.give_text)+'</b><br>'+(mine?'Просишь':'Просит')+': <b>'+esc(o.want_text)+'</b></p><div class="town-buttons">'+(mine?'':'<button class="primary" data-offer="offer_accept" data-id="'+o.id+'">Согласиться</button>')+'<button class="secondary" data-offer="offer_cancel" data-id="'+o.id+'">'+(mine?'Отозвать':'Отказать')+'</button></div></div>';});}
  const near=state.players.filter(p=>p.id!==me.id&&p.hp>0&&distance(p,me)<260);
  html+='<span class="eyebrow shop-eyebrow">ИГРОКИ РЯДОМ</span>';
  if(!near.length)html+='<p class="small muted">Для обмена подойди к игроку вплотную. Вещи переходят только после согласия второй стороны. Оружие и одежду передают из рук в руки: брось на землю.</p>';
  else{const tradable=k=>!cfg.items[k].weapon&&!cfg.items[k].gear,itemOpts=list=>'<option value="">—</option>'+list.filter(tradable).map(k=>'<option value="'+k+'">'+esc(itemName(k))+'</option>').join('');
   const side=(id,title,items)=>'<div class="offer-side"><b>'+title+'</b><label>Вещь<select id="'+id+'-item">'+itemOpts(items)+'</select></label><label>Сколько<input type="number" min="1" max="99" id="'+id+'-n" value="1"></label></div>';
   html+='<label class="setting">Кому<select id="offer-to">'+near.map(p=>'<option value="'+p.id+'">'+esc((p.tag?'['+p.tag+'] ':'')+p.name)+'</option>').join('')+'</select></label><div class="offer-form">'+side('give','Отдаю',Object.keys(me.items))+side('want','Прошу',Object.keys(cfg.items))+'</div><button class="primary" id="offer-send" style="width:100%">'+icon('trade')+' Предложить обмен</button>';}
 }else{
  if(!clan){
   if(state.invites.length){html+='<span class="eyebrow shop-eyebrow">ПРИГЛАШЕНИЯ</span>';state.invites.forEach(cid=>{const c=state.clans[cid];if(!c)return;html+='<div class="side-row"><span class="dot" style="background:'+c.color+'"></span><div><b>['+esc(c.tag)+'] '+esc(c.name)+'</b><small>'+c.members.length+' чел. · глава '+esc(sideName(c.leader))+'</small></div><button class="primary" data-clan="clan_join" data-id="'+cid+'">Вступить</button><button class="quiet" data-clan="clan_decline" data-id="'+cid+'">Нет</button></div>';});}
   html+='<p style="margin-top:12px">Группа — до 6 игроков. В группе не ранят друг друга, видят друг друга на карте и пользуются одним лагерем.</p><label class="setting">Название<input id="clan-name" maxlength="24" placeholder="Например: Северный ветер"></label><button class="primary" id="clan-create" style="width:100%">Собрать группу</button>';
  }else{
   const lead=clan.leader===f;
   html+='<div class="town-faction" style="color:'+clan.color+'">'+icon('flag')+' ['+esc(clan.tag)+'] '+esc(clan.name)+'</div><span class="eyebrow shop-eyebrow">СОСТАВ · '+clan.members.length+' / 6</span><div class="side-list">';
   clan.members.forEach(m=>{const s=state.sides[m],p=state.players.find(q=>q.faction===m);html+='<div class="side-row"><span class="dot" style="background:'+(s?s.color:'#888')+'"></span><div><b>'+esc(sideName(m))+(m===clan.leader?' · глава':'')+'</b><small>'+(p?km(distance(p,me)):'не в сети')+'</small></div>'+(lead&&m!==f?'<button class="quiet danger" data-clan="clan_kick" data-side="'+m+'">Исключить</button>':'')+'</div>';});
   html+='</div>';
   if(lead){const free=state.players.filter(p=>p.faction!==f&&!(state.sides[p.faction]||{}).clan&&distance(p,me)<400);html+='<span class="eyebrow shop-eyebrow">ПРИГЛАСИТЬ РЯДОМ</span>'+(free.length?'<div class="side-list">'+free.map(p=>'<div class="side-row"><span class="dot" style="background:'+sideColor(p.faction)+'"></span><div><b>'+esc(p.name)+'</b></div><button class="secondary" data-clan="clan_invite" data-side="'+p.faction+'">Позвать</button></div>').join('')+'</div>':'<p class="small muted">Позвать можно того, кто стоит рядом и ещё не в группе.</p>');}
   html+='<button class="quiet danger" data-clan="clan_leave" style="width:100%;margin-top:14px">Выйти из группы</button>';
  }
 }
 html+='</div>';
 modal('people','<span class="eyebrow">ЛЮДИ · O</span><h2>Обмен и группа</h2>',html);
 screen.querySelectorAll('[data-ptab]').forEach(b=>b.onclick=()=>showPeople(b.dataset.ptab));
 screen.querySelectorAll('[data-offer]').forEach(b=>b.onclick=async()=>{await action(b.dataset.offer,{id:b.dataset.id});showPeople('trade');});
 screen.querySelectorAll('[data-clan]').forEach(b=>b.onclick=async()=>{if(b.dataset.clan==='clan_leave'&&!confirm('Выйти из группы?'))return;await action(b.dataset.clan,{id:b.dataset.id,side:b.dataset.side});showPeople('clan');});
 if($('clan-create'))$('clan-create').onclick=async()=>{const r=await action('clan_create',{name:$('clan-name').value});if(r)showPeople('clan');};
 if($('offer-send'))$('offer-send').onclick=async()=>{const pack=id=>{const out={items:{}};if($(id+'-item').value)out.items[$(id+'-item').value]=Number($(id+'-n').value)||1;return out;};
  const r=await action('offer_make',{to:$('offer-to').value,give:pack('give'),want:pack('want')});if(r)showPeople('trade');};
}

/* ---------- map ---------- */
const KIND_NAME={city:'Город',town:'Посёлок',village:'Деревня'};
function showMap(id){if(!state)return;modal('map','<span class="eyebrow">'+esc((cfg.region_name||'').toUpperCase())+'</span><h2>Карта</h2>',
 '<div class="map-body"><div class="map-view"><canvas id="big-map"></canvas><div class="map-legend"><span><i></i>Ты</span>'+(myClan()?'<span><i style="background:'+myClan().color+'"></i>Группа</span>':'')+'<span><i class="square"></i>Лагерь</span><span><i class="diamond"></i>Базы, заводы, фермы</span></div><div class="map-zoom"><button class="secondary" id="zoom-in">+</button><button class="secondary" id="zoom-out">−</button><button class="secondary" id="zoom-me">Я</button></div></div><aside class="map-info" id="map-info"></aside></div>','map-modal');
 mapState.selected=id||null;mapInfo(mapState.selected);
 const big=$('big-map');let drag=null;
 const toWorld=e=>{const box=big.getBoundingClientRect();if(!mapTr)return null;return{x:(e.clientX-box.left-mapTr.ox)/mapTr.scale,y:(e.clientY-box.top-mapTr.oy)/mapTr.scale};};
 const zoomBy=(k,at)=>{const z=clamp(mapState.zoom*k,1,32);if(at){mapState.fx=at.x;mapState.fy=at.y;}else if(mapState.fx==null){mapState.fx=state.me.x;mapState.fy=state.me.y;}mapState.zoom=z;if(z===1){mapState.fx=mapState.fy=null;}};
 big.onwheel=e=>{e.preventDefault();zoomBy(e.deltaY<0?1.35:1/1.35,e.deltaY<0?toWorld(e):null);};
 $('zoom-in').onclick=()=>zoomBy(1.5);$('zoom-out').onclick=()=>zoomBy(1/1.5);$('zoom-me').onclick=()=>{mapState.zoom=Math.max(6,mapState.zoom);mapState.fx=state.me.x;mapState.fy=state.me.y;};
 big.onmousedown=e=>{drag={x:e.clientX,y:e.clientY,fx:mapState.fx!=null?mapState.fx:cfg.width/2,fy:mapState.fy!=null?mapState.fy:cfg.height/2,moved:false};};
 big.onmousemove=e=>{if(!drag||!mapTr)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4)drag.moved=true;if(drag.moved&&mapState.zoom>1){mapState.fx=drag.fx-dx/mapTr.scale;mapState.fy=drag.fy-dy/mapTr.scale;}};
 big.onmouseup=e=>{const moved=drag&&drag.moved;drag=null;if(moved)return;const p=toWorld(e);if(!p)return;
  const list=cfg.towns.slice().sort((a,b)=>distance(a,p)-distance(b,p)),poi=cfg.pois.slice().sort((a,b)=>distance(a,p)-distance(b,p))[0],pick=14/mapTr.scale;
  if(distance(list[0],p)<pick*1.4){mapState.selected=list[0].id;mapInfo(list[0].id);}else if(poi&&distance(poi,p)<pick){poiInfo(poi);}else{waypoint={x:clamp(p.x,0,cfg.width),y:clamp(p.y,0,cfg.height),name:'Отметка'};notify('Отметка на карте','Указатель появится в игровом мире.');}};
}
function mapInfo(id){const t=cfg.towns.find(x=>x.id===id);
 if(!t){$('map-info').innerHTML='<span class="eyebrow">'+esc((cfg.region_name||'').toUpperCase())+'</span><h3>Побережье и леса</h3><p>Нажми на город, чтобы узнать о нём, или в любое место — поставить отметку.</p><p class="map-note">Колесо мыши — масштаб, перетаскивание — сдвиг.</p>'+(waypoint?'<button class="quiet" id="clear-waypoint">Убрать отметку</button>':'');if($('clear-waypoint'))$('clear-waypoint').onclick=()=>{waypoint=null;mapInfo(null);};return;}
 $('map-info').innerHTML='<span class="eyebrow">'+esc(KIND_NAME[t.kind]||'')+'</span><h3>'+esc(t.name)+'</h3><p>'+(t.kind==='city'?'Много домов, больница, много заражённых.':t.kind==='town'?'Улицы, жилые дома и заражённые.':'Несколько изб и пара заражённых.')+'</p><p>Отсюда '+km(distance(t,state.me))+'.</p><button class="primary" id="set-waypoint">Отметить '+icon('arrow')+'</button><button class="quiet" id="clear-waypoint">Убрать отметку</button>';
 $('set-waypoint').onclick=()=>{waypoint={x:t.x,y:t.y,name:t.name};closePanel();notify('Цель: '+t.name,'Следуй указателю.');};$('clear-waypoint').onclick=()=>{waypoint=null;mapInfo(id);};}
function poiInfo(p){const kind=cfg.poi_kinds[p.kind]||{};const what={military:'оружие, патроны, бронежилеты',industrial:'инструменты, металлолом, канистры',farm:'еда, верёвки, топоры, ружья',gas:'бензин, канистры, газировка',rural:'еда, ткань, топоры'}[kind.loot]||'';
 $('map-info').innerHTML='<span class="eyebrow">'+esc((kind.name||'').toUpperCase())+'</span><h3>'+esc(p.name)+'</h3><p>Здесь находят: '+esc(what)+'.</p><p class="small muted">Заражённых: около '+(kind.infected||0)+'.</p><button class="primary" id="set-waypoint">Отметить '+icon('arrow')+'</button>';
 $('set-waypoint').onclick=()=>{waypoint={x:p.x,y:p.y,name:p.name};closePanel();notify('Цель: '+p.name,'Следуй указателю.');};}

/* ---------- interaction ---------- */
function interact(){if(!state||state.me.hp<=0)return;if(state.me.vehicle){notify(state.me.seat==='passenger'?'Ты пассажир':'Ты за рулём','Нажми F, чтобы выйти.');return;}
 if(!nearest){if(carNear)notify('Машина рядом','F — сесть.');else notify('Рядом ничего нет','Подойди к вещи, телу, дереву или лагерю.');return;}
 const n=nearest;
 if(n.type==='loot')action('pickup',{id:n.obj.id});
 else if(n.type==='camp')showCamp(n.obj);
 else if(n.type==='fence')action('camp_break',{camp:n.obj.camp.id,slot:n.obj.slot});
 else if(n.type==='body')showInventory();
 else action('harvest',{id:n.obj.id});
}
function findNearest(p){
 const candidates=[];carNear=null;
 if(p.vehicle||p.hp<=0)return null;
 (state.loot||[]).forEach(l=>{if(Math.abs(l.x-p.x)>80||Math.abs(l.y-p.y)>80)return;const d=distance(l,p);if(d<70)candidates.push({type:'loot',obj:l,d:d-25});});
 (state.camps||[]).forEach(c=>{if(Math.abs(c.x-p.x)>400||Math.abs(c.y-p.y)>400)return;
  Object.keys(c.parts).forEach(k=>{const pt=c.parts[k];if(pt.hp>0&&distance(pt,p)<55&&(campCanUse(c)||c.breached))candidates.push({type:'camp',obj:c,d:distance(pt,p)-10});});
  if(!campCanUse(c))Object.keys(c.fence).forEach(k=>{const f=c.fence[k];if(f.hp>0&&Math.abs(f.x-p.x)<f.w/2+40&&Math.abs(f.y-p.y)<f.h/2+40)candidates.push({type:'fence',obj:{camp:c,slot:k,piece:f},d:30});});
  if(campCanUse(c)&&distance(c,p)<(c.house?50:70))candidates.push({type:'camp',obj:c,d:distance(c,p)});});
 (state.bodies||[]).forEach(b=>{const d=distance(b,p);if(d<90&&Object.keys(b.items).length)candidates.push({type:'body',obj:b,d:d-20});});
 cfg.nodes.forEach(n=>{if(Math.abs(n.x-p.x)>80||Math.abs(n.y-p.y)>80)return;const d=distance(n,p);if(d<70&&!(state.harvested[n.id]>state.time))candidates.push({type:'node',obj:n,d});});
 (state.cars||[]).forEach(c=>{const d=distance(c,p);if(d<carSpec(c).len*.6+30&&!c.wrecked&&(!carNear||d<carNear.d))carNear={car:c,d};});
 candidates.sort((a,b)=>a.d-b.d);return candidates[0]||null;}
const NODE_TEXT={wood:['Срубить дерево','Нужен топор · доски'],metal:['Разобрать железо','Металлолом'],food:['Собрать','Яблоки и травы']};
function hintHtml(p){
 if(p.hp<=0)return null;
 if(p.vehicle){const car=carOf(p.car);if(!car)return null;const spec=carSpec(car);
  if(p.seat==='passenger'){const d=state.players.find(q=>q.id===car.driver);return '<kbd>F</kbd> '+(kmh(car)>18?'Машина едет — выйти можно на остановке':'Выйти из машины')+'<small>Ты пассажир'+(d?'. Ведёт '+esc(d.name):'')+'</small>';}
  return '<kbd>F</kbd> '+(kmh(car)>18?'Останови машину, чтобы выйти':'Выйти из машины')+'<small>'+(car.fuel<1?'Бак пуст. Колонка на заправке или канистра — T.':'W газ · S тормоз и назад · A/D руль · Shift ручник · бак '+Math.floor(car.fuel)+' / '+spec.tank)+'</small>';}
 if(nearest){const o=nearest.obj;
  if(nearest.type==='loot'){const it=cfg.items[o.item]||{};return '<kbd>E</kbd> Взять: '+esc(it.name)+(o.n>1?' ×'+o.n:'')+'<small>'+(it.weapon!=null?'Оружие: сразу в руки, если они пусты':it.gear?'Наденешь вместо своего':esc(it.desc||''))+' · I — всё, что рядом</small>';}
  if(nearest.type==='body')return '<kbd>E</kbd> Обыскать: '+esc(o.name)+'<small>'+Object.keys(o.items).length+' видов вещей</small>';
  if(nearest.type==='camp')return '<kbd>E</kbd> '+(campCanUse(o)?'Лагерь':'Чужой лагерь: ящик')+'<small>Постройки, ящик · C — крафт</small>';
  if(nearest.type==='fence')return '<kbd>E</kbd> Ломать: '+(o.piece.kind==='gate'?'ворота':'стену')+'<small>Прочность '+o.piece.hp+' / '+o.piece.max+'. Шумно: на звук придут</small>';
  const t=NODE_TEXT[o.kind]||['Собрать',''];return '<kbd>E</kbd> '+t[0]+'<small>'+t[1]+'</small>';}
 if(carNear){const c=carNear.car,spec=carSpec(c),seats=c.driver?'Пассажиром: свободно '+Math.max(0,spec.seats-1-c.riders.length):'За руль';
  return '<kbd>F</kbd> '+esc(spec.name)+'<small>'+seats+' · '+Math.round(c.hp)+'% · бак '+Math.floor(c.fuel)+' / '+spec.tank+(p.items.repairkit&&c.hp<100?' · R — ремонт':'')+(p.items.canister&&c.fuel<spec.tank-1?' · T — канистра':'')+'</small>';}
 if(!p.vehicle&&R.water(p.x,p.y,70))return '<kbd>V</kbd> Попить<small>Морскую воду не пьют. Сырая речная вода может отравить</small>';
 return null;}
const WEATHER_ICON={clear:'sun',rain:'rain',fog:'fog',storm:'storm',snow:'snow'};
// The panel in the bottom right: the weapon in hand, or the car when driving or riding along.
function gearHtml(p){
 if(p.vehicle){const car=carOf(p.car)||{},spec=carSpec(car),fuel=car.fuel||0,d=p.seat==='passenger'&&state.players.find(q=>q.id===car.driver);
  return '<div class="g-top"><span class="g-name">'+(p.seat==='passenger'?'ПАССАЖИР · ':'')+esc(spec.name.toUpperCase())+'</span>'+(d?'<small>ведёт '+esc(d.name)+'</small>':'<span class="g-keys"><kbd>F</kbd> выйти</span>')+'</div>'+
  '<div class="g-big"><b>'+kmh(car)+'</b><span>км/ч</span></div>'+
  '<div class="g-row" title="Топливо">'+icon('fuel')+'<div class="g-bar"><i style="width:'+Math.min(100,fuel/spec.tank*100)+'%"></i></div><small>'+Math.floor(fuel)+' / '+spec.tank+'</small></div>'+
  '<div class="g-row" title="Состояние">'+icon('tool')+'<div class="g-bar car"><i style="width:'+Math.round(car.hp||0)+'%"></i></div><small>'+Math.round(car.hp||0)+'%</small></div>';}
 const wd=cfg.weapons[p.gear.weapon],reloading=p.reload>state.time,own=ownWeapons();
 let html='<div class="g-top"><span class="g-name">'+esc(wd.name.toUpperCase())+'</span><span class="g-keys"><kbd>Q</kbd>'+(wd.melee?'':' <kbd>X</kbd>')+'</span></div>';
 if(wd.melee)html+='<div class="g-big melee">'+(p.gear.weapon===cfg.fists?'<i class="li fist">'+icon('hand')+'</i>':itemIcon(cfg.weapon_item[p.gear.weapon],44))+'<span>урон '+wd.dmg+(wd.chop?' · рубит деревья':'')+'</span></div>';
 else if(reloading){const k=1-(p.reload-state.time)/(wd.reload||1);html+='<div class="g-big reload"><b>Перезарядка</b></div><div class="g-bar"><i style="width:'+Math.round(clamp(k,0,1)*100)+'%"></i></div>';}
 else{const reserve=p.items[wd.ammo_item]||0,ammoName=itemName(wd.ammo_item);html+='<div class="g-big'+(p.mag===0?' empty':'')+'"><b>'+p.mag+'</b><span>/ '+reserve+'</span><small>'+esc(ammoName.charAt(0).toLowerCase()+ammoName.slice(1))+'</small></div>'+(wd.mag<=40?'<div class="pips">'+Array.from({length:wd.mag},(_,i)=>'<i'+(i<p.mag?'':' class="off"')+'></i>').join('')+'</div>':'<div class="g-bar"><i style="width:'+Math.round(p.mag/wd.mag*100)+'%"></i></div>');}
 // Every weapon carried, with its number key; the one in hand is lit.
 const SHORT=['ПМ','Ружьё','АК','Обрез','СКС','СВД','ПКМ','Кулаки','Нож','Топор','Лом'];
 if(own.length>1)html+='<div class="g-guns">'+own.map((w,i)=>'<span'+(w===p.gear.weapon?' class="on"':'')+'><kbd>'+(i+1)+'</kbd>'+SHORT[w]+'</span>').join('')+'</div>';
 return html+'<div class="g-sub">'+icon('vest')+esc(cfg.armor[p.gear.armor].name)+' · '+icon('thermo')+esc(cfg.clothes[p.gear.clothes].name)+'</div>';}
function aliveText(p){const m=Math.max(0,Math.floor((state.time-(p.born||0))/60));return m<60?m+' мин':Math.floor(m/60)+' ч '+m%60+' мин';}
function updateHud(){if(!state)return;const p=state.me;
 const town=cfg.towns.slice().sort((a,b)=>distance(a,p)-distance(b,p))[0],inTown=Math.abs(town.x-p.x)<(town.r||480)+150&&Math.abs(town.y-p.y)<(town.h||420)+150,poi=cfg.pois.find(o=>distance(o,p)<420);
 const inHouse=R.houseAt(p.x,p.y,0),campHere=(state.camps||[]).find(c=>distance(c,p)<(c.house?60:110));
 $('location-name').textContent=campHere?'Лагерь · '+sideName(campHere.owner):inTown?town.name:poi?poi.name:'Белогорье';
 $('location-desc').textContent=campHere?(campCanUse(campHere)?'Свой лагерь':'Чужой лагерь'):inHouse?'Внутри дома':inTown?KIND_NAME[town.kind]||'':poi?poi.kind_name:'Окрестности · до '+town.name+' '+km(distance(town,p));
 const clan=myClan();
 $('status-line').innerHTML='<span title="Сколько прожил этот персонаж">'+icon('heart')+'<b>'+aliveText(p)+'</b><small>ЖИЗНЬ</small></span><span title="Убито заражённых">'+icon('fire')+'<b>'+p.stats.infected+'</b><small>ЗАРАЖЁННЫХ</small></span><span title="Убито игроков">'+icon('gun')+'<b>'+p.stats.players+'</b><small>ИГРОКОВ</small></span><span title="Игроков в мире">'+icon('walk')+'<b>'+state.players.length+'</b><small>В МИРЕ</small></span>';
 document.querySelector('.brand>span').textContent=(clan?'['+clan.tag+'] '+clan.name.toUpperCase()+' · ':'')+(cfg.region_name||'').toUpperCase();
 const minutes=8*60+Math.floor(state.time*1.4),days=1+Math.floor(minutes/1440),hour=Math.floor(minutes/60)%24,w=state.weather.kind;
 $('clock').innerHTML=icon(hour>=6&&hour<20?WEATHER_ICON[w]:(w==='clear'?'moon':WEATHER_ICON[w]))+'<span>ДЕНЬ '+String(days).padStart(2,'0')+' / '+String(hour).padStart(2,'0')+':'+String(minutes%60).padStart(2,'0')+' · '+esc(cfg.weather_names[w].toUpperCase())+'</span>';
 $('me-name').textContent=(clan?'['+clan.tag+'] ':'')+p.name;
 $('level').innerHTML='<small>жив '+aliveText(p)+'</small>';
 const mx=p.max_hp||100,hpBar=document.querySelector('#me-panel .hbar.hp');hpBar.firstElementChild.style.width=Math.max(0,p.hp/mx*100)+'%';hpBar.lastElementChild.textContent=Math.ceil(Math.max(0,p.hp))+' / '+mx;hpBar.classList.toggle('low',p.hp<mx*.3);
 document.querySelector('#me-panel .hbar.st').firstElementChild.style.width=p.stamina+'%';
 const mi=$('me-icon'),im=AS.sprites.heroIcon(0,sideColor(p.faction));if(im&&mi.dataset.c!==sideColor(p.faction)){const c=mi.getContext('2d');c.clearRect(0,0,128,128);c.drawImage(im,4,4,120,120);mi.dataset.c=sideColor(p.faction);}
 $('vitals').innerHTML=vitalsHtml(false);
 $('coins').innerHTML='<span title="Рюкзак · I">'+icon('bag')+slotsUsed(p.items)+' / '+slotsMax()+'</span>'+(p.items.bandage?'<span title="Бинты · H">'+icon('heart')+p.items.bandage+'</span>':'');
 $('gear-panel').innerHTML=gearHtml(p);
 $('autosave').textContent=netFailures?'Соединение с ведущим потеряно':'Мир сохраняется у ведущего';$('autosave').classList.toggle('bad',!!netFailures);
 nearest=findNearest(p);
 const hint=$('interaction'),h=hintHtml(p);hint.classList.toggle('hidden',!h);if(h)hint.innerHTML=h;
 deathScreen(p);
}
// Death: everything stays on the body; a short summary while the next life is prepared.
function deathScreen(p){let d=$('death');
 if(p.hp>0){if(d)d.remove();deadShown=false;return;}
 if(!d){d=document.createElement('div');d.id='death';document.body.appendChild(d);}
 if(!deadShown){deadShown=true;beep('error');d.dataset.lived=aliveText(p);d.dataset.inf=p.stats.infected;d.dataset.pl=p.stats.players;}
 d.innerHTML='<div><span class="eyebrow">ТЫ ПОГИБ</span><h2>Всё осталось на теле</h2><p>Прожито '+esc(d.dataset.lived)+' · заражённых '+esc(d.dataset.inf)+' · игроков '+esc(d.dataset.pl)+'</p><small>Новая жизнь на побережье через '+Math.ceil(Math.max(0,p.dead_until-state.time))+' с</small></div>';}

/* Smoothly follow server positions; walking phase drives the animation. */
function interpolate(list,store,dt){const seen={};list.forEach(p=>{seen[p.id]=1;let r=store[p.id];if(!r||distance(r,p)>500)r=store[p.id]={x:p.x,y:p.y,phase:Math.random()*6,ang:p.angle};
 const ox=r.x,oy=r.y;r.x+=(p.x-r.x)*Math.min(1,dt*14);r.y+=(p.y-r.y)*Math.min(1,dt*14);const sp=Math.hypot(r.x-ox,r.y-oy)/Math.max(dt,.001);r.sp=(r.sp||0)+(sp-(r.sp||0))*Math.min(1,dt*8);r.moving=r.sp>12;
 // Step rate follows the actual speed, so feet do not slide over the ground.
 r.phase+=dt*Math.min(10,2.4+r.sp*.034)*(r.moving?1:0);
 let da=(p.angle-r.ang+Math.PI)%(Math.PI*2);if(da<0)da+=Math.PI*2;r.ang+=(da-Math.PI)*Math.min(1,dt*12);});Object.keys(store).forEach(k=>{if(!seen[k])delete store[k];});}
let slowFrames=0,measured=0;
// Cold frosts the screen edges; bleeding pulses red.
function conditionOverlay(now){const me=state.me;
 if(lastHp!=null&&me.hp<lastHp-1)hurtFlash=1;lastHp=me.hp;
 if(hurtFlash>0){ctx.strokeStyle='rgba(150,25,20,'+(hurtFlash*.45)+')';ctx.lineWidth=26;ctx.strokeRect(0,0,cw,ch);hurtFlash=Math.max(0,hurtFlash-.06);}
 const cold=clamp((35-me.warmth)/35,0,1),blood=me.bleeding?.35+Math.sin(now/260)*.15:0,low=me.hp<(me.max_hp||100)*.3?.25:0;
 if(cold>0){const g=ctx.createRadialGradient(cw/2,ch/2,Math.min(cw,ch)*.3,cw/2,ch/2,Math.max(cw,ch)*.7);g.addColorStop(0,'rgba(200,225,240,0)');g.addColorStop(1,'rgba(200,225,240,'+(.55*cold)+')');ctx.fillStyle=g;ctx.fillRect(0,0,cw,ch);}
 if(blood+low>0){const g=ctx.createRadialGradient(cw/2,ch/2,Math.min(cw,ch)*.35,cw/2,ch/2,Math.max(cw,ch)*.72);g.addColorStop(0,'rgba(120,10,10,0)');g.addColorStop(1,'rgba(120,10,10,'+(blood+low)+')');ctx.fillStyle=g;ctx.fillRect(0,0,cw,ch);}
 if(me.hp<=0){ctx.fillStyle='rgba(20,8,8,.45)';ctx.fillRect(0,0,cw,ch);}}
function infectedNear(){const me=drawPlayers[state.me.id];if(!me)return null;let best=null;(state.npcs||[]).forEach(n=>{if(n.faction!=='infected'||n.hp<=0)return;const d=distance(n,me);if(d<900&&(!best||d<best.d))best={d,run:n.run};});return best;}
function render(now){const raw=(now-last)/1000,dt=Math.min(raw,.05);last=now;frame++;
 // On a slow computer switch to economical graphics once, unless the player chose a mode.
 if(state&&!panel&&measured<240&&!readStorage('as-quality')){measured++;if(raw>.042)slowFrames++;if(measured===240&&slowFrames>140&&R.quality!=='low'){R.quality='low';resize();notify('Экономная графика','Компьютер не успевает за полной графикой. Вернуть можно в Esc → Настройки.');}}
 if(state){interpolate(state.players,drawPlayers,dt);interpolate(state.npcs||[],drawNpcs,dt);interpolate(state.cars||[],drawCars,dt);
  const me=drawPlayers[state.me.id],car=state.me.vehicle&&drawCars[state.me.car];const at=car||me;
  if(at){const look=car?120:0,ang=car?car.ang:0;const tx=at.x+Math.cos(ang)*look,ty=at.y+Math.sin(ang)*look;cam.x+=(tx-cam.x)*Math.min(1,dt*6);cam.y+=(ty-cam.y)*Math.min(1,dt*6);}updateAim();}
 ctx.setTransform(dpr,0,0,dpr,0,0);
 if(camKick>0){cam.x-=aim.x*camKick;cam.y-=aim.y*camKick;camKick=Math.max(0,camKick-dt*14);}
 const view={cam,cw,ch,zoom,state,drawPlayers,drawNpcs,drawCars,nearest,carNear,panel,aim,now:now/1000,dt,dpr,waypoint,holdAim:holdMouse||keys.Space||now-lastAimAt<900,dark:0};
 if(state){view.myCar=state.me.vehicle?carOf(state.me.car):null;if(frame%15===0)view.infectedNear=infectedNear();}
 if(cfg)R.draw(ctx,view);
 if(state)conditionOverlay(now);
 if(state&&waypoint&&!panel){const dx=waypoint.x-cam.x,dy=waypoint.y-cam.y,len=Math.hypot(dx,dy);if(len*zoom>Math.min(cw,ch)*.3){const angle=Math.atan2(dy,dx),r=Math.min(cw*.31,ch*.31),x=cw/2+Math.cos(angle)*r,y=ch/2+Math.sin(angle)*r;ctx.save();ctx.translate(x,y);ctx.rotate(angle);ctx.fillStyle='#e5b378';ctx.beginPath();ctx.moveTo(10,0);ctx.lineTo(-6,-6);ctx.lineTo(-3,0);ctx.lineTo(-6,6);ctx.fill();ctx.restore();R.pill(ctx,(waypoint.name||'Цель')+' · '+km(len),x,y+23,'#ead6b4');}}
 if(state){SND.update(view);if(now-lastHud>180){updateHud();lastHud=now;}if(frame%3===0)R.drawMap($('minimap'),false,view,mapState);if(panel==='map'&&frame%3===0)mapTr=R.drawMap($('big-map'),true,view,mapState);if((holdMouse||keys.Space)&&!panel)shoot();}
 requestAnimationFrame(render);
}
async function boot(){try{cfg=await fetchJson('/api/config');R.init(cfg);showTitle();}catch(e){screen.innerHTML='<section class="modal"><div class="modal-body"><h2>Сначала запусти игру</h2><p style="margin-top:15px">Этот файл открывается через локальный сервер. Запусти «Играть.sh» из папки игры. На другом ПК открой адрес, который показывает ведущий.</p></div></section>';console.error(e);}}
boot();requestAnimationFrame(render);
})();
