/* After Silence. Local Canvas 2D client. The server owns every game outcome. */
(function () {
'use strict';
const AS = window.AS, R = AS.render, SND = AS.audio;
const $=id=>document.getElementById(id), canvas=$('world'), ctx=canvas.getContext('2d',{alpha:false});
const screen=$('screen'), keys={}, pointer={x:0,y:0};
let cfg=null, state=null, token='', connected=false, joining=false, busy=false, panel='title', selected=null;
let cw=innerWidth,ch=innerHeight,dpr=1,cam={x:7300,y:5200}, drawPlayers={}, drawNpcs={};
let last=performance.now(), frame=0, netBusy=false, netFailures=0, latestStamp=0, lastMessage=0, lastHud=0, pollCount=0;
let zoom=Number(readStorage('as-zoom'))||1.3,aim={x:0,y:1}, nearest=null, currentTown=null, waypoint=null, lastAimAt=0;
let heroColor=readStorage('as-color'),dialogGiver=null,camKick=0,hurtFlash=0,lastHp=null;
let lastDry=0,requestSerial=0,lastShot=0,holdMouse=false,showedWarning=false,mapState={zoom:1,fx:null,fy:null,selected:null},mapTr=null;
const palette=AS.colors;
const sideName=id=>id&&state&&state.sides[id]?state.sides[id].name:'Независимые';
const sideColor=id=>id&&state&&state.sides[id]?state.sides[id].color:palette.neutral;
const myClan=()=>state&&state.clans[state.sides[state.me.faction].clan]||null;
const friendly=id=>id===state.me.faction||!!(myClan()&&myClan().members.includes(id));
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
$('menu').onclick=()=>showPause();$('minimap-wrap').onclick=()=>showMap();$('journal-hint').onclick=()=>showJournal();
addEventListener('pointerdown',()=>SND.resume(),{once:false});addEventListener('keydown',()=>SND.resume());

async function fetchJson(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),4500);
 try{const options={headers:{'X-Session':token},signal:controller.signal,cache:'no-store'};
 if(body){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
 const response=await fetch(path,options);const data=await response.json();if(!response.ok){const e=new Error(data.error||'Ошибка соединения');e.status=response.status;throw e;}return data;
 }finally{clearTimeout(timer);}
}
function acceptState(s){if(!s||s.stamp<latestStamp)return;latestStamp=s.stamp;
 if(state&&state.offers&&s.offers)s.offers.forEach(o=>{if(o.to===s.me.id&&!state.offers.some(x=>x.id===o.id))beep('ui');});
 // Light snapshots omit slow-changing settlement data; keep the last full copy.
 if(!s.full&&state){s.towns=state.towns;s.harvested=state.harvested;}
 if(!s.towns)return;
 state=s;
 s.messages.forEach(m=>{if(m.id>lastMessage){if(lastMessage!==0){notify(m.title,m.text,m.tone==='error');if(m.tone==='error')beep('error');}lastMessage=m.id;}});
 if(s.load_warning&&!showedWarning){showedWarning=true;notify('Сохранение',s.load_warning,true);}
}
async function join(){if(joining||!cfg)return;joining=true;const btn=$('join');btn.disabled=true;btn.textContent='Подключение…';SND.resume();
 try{const name=$('player-name').value,code=$('room-code')?$('room-code').value.trim():'';token=readStorage('as-token-'+location.host);
 const data=await fetchJson('/api/join',{name,code,token,color:heroColor});token=data.token;writeStorage('as-token-'+location.host,token);writeStorage('as-name',name);writeStorage('as-color',heroColor||'');
 latestStamp=0;lastMessage=0;state=null;acceptState(data.state);connected=true;drawPlayers={};drawNpcs={};cam={x:state.me.x,y:state.me.y};closePanel();$('hud').classList.remove('hidden');
 const camp=myCamp();if(camp&&distance(camp,state.me)>1500)waypoint={x:camp.x,y:camp.y,name:'Лагерь'};
 const near=Object.values(state.towns).sort((a,b)=>distance(a,state.me)-distance(b,state.me))[0];notify('Ты очнулся у дороги','Рядом: '+near.name+'. '+(camp?'Лагерь отмечен указателем.':'Лагеря нет: зайди в пустой дом или найди площадку и нажми L.'));
 notify('Экспедиция началась','Работу дают люди на площадях: подойди и нажми E. F — машина, J — журнал, O — обмен и клан.');beep('success');
 }catch(e){notify('Не удалось войти',e.message,true);btn.disabled=false;btn.innerHTML='Войти в мир '+icon('arrow');}finally{joining=false;}}
async function action(op,args){if(busy&&op!=='shoot')return null;if(op!=='shoot')busy=true;
 try{const data=await fetchJson('/api/action',Object.assign({op,request_id:Date.now().toString(36)+'-'+(++requestSerial)+'-'+Math.random().toString(36).slice(2,8)},args||{}));acceptState(data.state);
 const r=data.result||{};if(!r.quiet&&!r.event){let info=r.text||'';if(r.chance!=null&&!/Бросок/.test(info))info+=' Шанс '+r.chance+'%, бросок '+r.roll+'.';notify(r.title||'Готово',info,r.success===false);beep(r.success===false?'error':op==='build'?'build':op==='harvest'||op==='loot'||op==='airdrop'?'harvest':'success');}return r;
 }catch(e){if(op!=='shoot')notify('Действие не выполнено',e.message,true);if(op!=='shoot')beep('error');return null;}finally{if(op!=='shoot')busy=false;}}
async function network(){if(!connected||!state||netBusy)return;netBusy=true;
 try{const input=readInput();pollCount++;const data=await fetchJson('/api/action',{op:'input',x:input.x,y:input.y,sprint:input.sprint,ax:aim.x,ay:aim.y,paused:panel!==null,full:pollCount%10===0});acceptState(data.state);netFailures=0;
 }catch(e){netFailures++;if(e.status===401){connected=false;state=null;latestStamp=0;showTitle();notify(/новую игру/.test(e.message)?'Новая игра':'Комната завершилась',/новую игру/.test(e.message)?'Ведущий начал мир с нуля. Войди снова.':'Войди заново.',true);}else if(netFailures===2)notify('Нет связи с ведущим','Персонаж остановлен. Пробую восстановить соединение.',true);
 }finally{netBusy=false;}}
setInterval(network,100);
function readInput(){if(panel!==null)return{x:0,y:0,sprint:false};return{x:(keys.KeyD||keys.ArrowRight?1:0)-(keys.KeyA||keys.ArrowLeft?1:0),y:(keys.KeyS||keys.ArrowDown?1:0)-(keys.KeyW||keys.ArrowUp?1:0),sprint:!!(keys.ShiftLeft||keys.ShiftRight)};}
function clearKeys(){Object.keys(keys).forEach(k=>delete keys[k]);holdMouse=false;}
addEventListener('blur',clearKeys);document.addEventListener('visibilitychange',()=>{if(document.hidden){clearKeys();if(connected&&!panel)showPause();}});
addEventListener('keydown',e=>{
 if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;
 if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Tab'].includes(e.code))e.preventDefault();
 keys[e.code]=true;if(e.repeat)return;
 if(e.code==='Escape'){if(panel==='title')return;if(panel)closePanel();else showPause();}
 if(!connected)return;
 if(e.code==='KeyM'){if(panel==='map')closePanel();else showMap();}
 if(e.code==='KeyJ'){if(panel==='journal')closePanel();else showJournal();}
 if(e.code==='KeyO'){if(panel==='people')closePanel();else showPeople();}
 if(e.code==='KeyC'){if(panel==='craft')closePanel();else showCraft();}
 if(e.code==='KeyL'){if(panel==='camp')closePanel();else{const c=myCamp();if(!c)foundCamp();else if(distance(c,state.me)<(c.house?140:260))showCamp(c);else showCampFar(c);}}
 if(panel)return;
 if(e.code==='KeyE')interact();
 if(e.code==='KeyF')action('vehicle').then(r=>{if(r)beep('door');});
 if(e.code==='KeyH')action('heal');
 if(e.code==='KeyR')action('repair',{kit:true});
 if(e.code==='KeyT')action('refuel',{canister:true});
 if(e.code==='KeyI'||e.code==='Tab')showInventory();
 if(e.code==='KeyG')quickUse(['canned','crackers'],'Нечего есть. Еду продают в магазине, находят в тайниках и на складах с припасами.');
 if(e.code==='KeyV'){if(state&&R.water(state.me.x,state.me.y,70)&&!state.me.vehicle)action('drink');else quickUse(['water','tea'],'Нет воды. Подойди к реке или купи бутылку в магазине.');}
 if(e.code==='KeyQ'&&state){const own=state.me.weapons.slice().sort((a,b)=>a-b),i=own.indexOf(state.me.gear.weapon);equip(own[(i+1)%own.length]);}
 if(/^Digit[1-7]$/.test(e.code)&&state){const own=state.me.weapons.slice().sort((a,b)=>a-b),n=Number(e.code.slice(5))-1;if(own[n]!=null)equip(own[n]);}
 if(e.code==='KeyB')confirmPost();
 if(e.code==='KeyX')action('reload');
 if(e.code==='Space')shoot();
});
addEventListener('keyup',e=>{keys[e.code]=false;});
canvas.addEventListener('mousemove',e=>{pointer.x=e.clientX;pointer.y=e.clientY;updateAim();});
function updateAim(){const p=state&&drawPlayers[state.me.id];if(p){const dx=pointer.x-((p.x-cam.x)*zoom+cw/2),dy=pointer.y-((p.y-cam.y)*zoom+ch/2),n=Math.hypot(dx,dy)||1;aim={x:dx/n,y:dy/n};}}
canvas.addEventListener('mousedown',e=>{if(e.button===0&&!panel){holdMouse=true;shoot();}});addEventListener('mouseup',()=>holdMouse=false);
canvas.addEventListener('contextmenu',e=>e.preventDefault());
canvas.addEventListener('wheel',e=>{e.preventDefault();zoom=clamp(zoom*(e.deltaY<0?1.1:1/1.1),.7,2);writeStorage('as-zoom',String(zoom));},{passive:false});
function quickUse(list,empty){if(!state)return;const item=list.find(k=>state.me.items[k]>0);if(!item){notify('Пусто',empty,true);return;}action('use',{item});}
function showInventory(){if(!state)return;const me=state.me,used=slotsUsed(me.items),room=cfg.backpacks[me.gear.backpack].slots;
 let h='<div class="modal-body">'+vitalsHtml(true)+'<span class="eyebrow shop-eyebrow">СНАРЯЖЕНИЕ</span><div class="gear-list"><span>'+icon('gun')+esc(cfg.weapons[me.gear.weapon].name)+'</span><span>'+icon('vest')+esc(cfg.armor[me.gear.armor].name)+'</span><span>'+icon('thermo')+esc(cfg.clothes[me.gear.clothes].name)+' · тепло +'+cfg.clothes[me.gear.clothes].warm+'</span><span>'+icon('bag')+esc(cfg.backpacks[me.gear.backpack].name)+' · '+room+' мест</span></div>';
 h+='<span class="eyebrow shop-eyebrow">РЮКЗАК · '+used+' / '+room+'</span>'+(used?'<div class="craft-grid">'+Object.keys(me.items).map(k=>'<button class="decision" data-use="'+k+'" '+(k==='repairkit'||k==='canister'||cfg.items[k].mat||cfg.items[k].ammo?'disabled':'')+'><div><b>'+esc(cfg.items[k].name)+'</b><strong>×'+me.items[k]+'</strong></div><small>'+esc(cfg.items[k].desc)+'</small><span class="decision-cost">'+(k==='repairkit'?'R рядом с машиной':k==='canister'?'T рядом с машиной':cfg.items[k].ammo?'X — зарядить':cfg.items[k].mat?'Материал · C':'Использовать')+'</span></button>').join('')+'</div>':'<p class="small muted">Пусто. Еду, воду и медицину продают в магазине на площадях, их находят в тайниках и у мародёров.</p>')+'<p class="small muted" style="margin-top:14px">G — поесть, V — попить (у реки — из реки), H — лечение. В своём поселении на площади есть столовая и колодец.</p></div>';
 modal('inventory','<span class="eyebrow">ПЕРСОНАЖ</span><h2>Рюкзак и состояние</h2>',h);screen.querySelectorAll('[data-use]').forEach(b=>b.onclick=async()=>{await action('use',{item:b.dataset.use});showInventory();});}
function vitalsHtml(big){const me=state.me,bar=(ic,v,label,cls)=>'<div class="vital '+cls+(v<25?' low':'')+'" title="'+label+'">'+icon(ic)+'<i><em style="width:'+Math.round(v)+'%"></em></i>'+(big?'<b>'+label+' '+Math.round(v)+'%</b>':'')+'</div>';
 return '<div class="vitals'+(big?' big':'')+'">'+bar('bowl',me.food,'Сытость','food')+bar('drop',me.water,'Вода','water')+bar('thermo',me.warmth,'Тепло','warm')+(me.bleeding?'<span class="chip bad">Кровотечение · H</span>':'')+(me.sick>state.time?'<span class="chip bad">Отравление</span>':'')+'</div>';}
function equip(idx){if(!state||idx===state.me.gear.weapon)return;action('equip',{weapon:idx}).then(r=>{if(r){notify(cfg.weapons[idx].name,'Оружие в руках.');beep('door');}});}
function weaponCd(){return state?cfg.weapons[state.me.gear.weapon].cd*1000+20:490;}
function shoot(){if(!state||panel||state.me.vehicle||state.me.hp<=0)return;const now=performance.now();lastAimAt=now;if(now-lastShot<weaponCd()||state.me.reload>state.time)return;lastShot=now;
 const wd=cfg.weapons[state.me.gear.weapon];if(state.me.mag<=0){beep('click');if(state.me.items[wd.ammo_item]>0){action('reload');return;}if(now-lastDry>2500){lastDry=now;notify('Нет патронов',(cfg.items[wd.ammo_item]||{}).name+': ищи в домах, у убитых, в магазине или сделай на верстаке.',true);}return;}
 // A light camera kick, stronger for heavy guns.
 camKick=[.6,1.6,.5,2,1.1,2.2,.6][state.me.gear.weapon]||.6;action('shoot');}
const CAMP_R=110;
function carSpec(){return cfg.cars[state&&state.me.car.model!=null?state.me.car.model:2]||cfg.cars[2];}
function carTank(){return carSpec().tank;}
// About 90 km/h at 400 px/s: speeds feel right for the shortened map.
// Another player's stopped car with a free seat, close enough to get in as a passenger.
function rideNear(p){if(p.vehicle||p.hp<=0)return null;let best=null;state.players.forEach(q=>{if(q.id===p.id||q.ride||!q.car)return;const spec=cfg.cars[q.car.model]||cfg.cars[2],d=distance(q.car,p);if(d>spec.len*.6+30||(best&&best.d<d))return;
 const taken=state.players.filter(o=>o.ride===q.id&&o.vehicle).length;best={d,q,spec,free:(spec.seats||4)-1-taken};});return best;}
function rideOf(p){return p.ride?state.players.find(q=>q.id===p.ride):null;}
function kmh(car){return Math.round(Math.hypot(car.vx||0,car.vy||0)*.225);}
function closePanel(){panel=null;selected=null;screen.className='';screen.innerHTML='';document.body.classList.remove('dialog-open');clearKeys();}
function modal(type,head,body,width){panel=type;document.body.classList.add('dialog-open');screen.className='';screen.innerHTML='<section class="modal '+(width||'')+'"><div class="modal-head"><div>'+head+'</div><button class="close" id="close-panel" aria-label="Закрыть">'+icon('close')+'</button></div>'+body+'</section>';$('close-panel').onclick=closePanel;clearKeys();}
function showTitle(){panel='title';document.body.classList.remove('dialog-open');$('hud').classList.add('hidden');screen.className='title-screen';
 const local=cfg&&cfg.join_code,params=new URLSearchParams(location.search),preset=(params.get('code')||'').replace(/\D/g,'').slice(0,6),colors=cfg?cfg.side_colors:[];
 if(!colors.includes(heroColor))heroColor=colors[Math.floor(Math.random()*colors.length)];
 screen.innerHTML='<div class="title-layout"><div class="overline">РОССИЯ ПОСЛЕ КАТАСТРОФЫ</div><h1>ПОСЛЕ<br><span>ТИШИНЫ</span></h1><p class="story">Дороги остались. Государства — нет.<br>У тебя есть машина, пара досок и пустой рюкзак.<br>Остальное придётся взять самому.</p><div class="lobby"><label>ПОЗЫВНОЙ<input id="player-name" maxlength="20" value="'+esc(readStorage('as-name')||'Каскад')+'"></label>'+(local?'':'<label>КОД КОМНАТЫ<input id="room-code" inputmode="numeric" maxlength="6" placeholder="6 цифр от ведущего" value="'+esc(preset)+'"></label>')+
 '<div class="look-pick"><span>ЦВЕТ ТОЛСТОВКИ · <b>так тебя узнают другие</b></span><div class="hero-pick"><canvas id="hero-preview" width="96" height="96"></canvas><div class="swatches">'+colors.map(c=>'<button class="swatch'+(c===heroColor?' on':'')+'" data-color="'+c+'" style="background:'+c+'" aria-label="Цвет '+c+'"></button>').join('')+'</div></div></div>'+
 '<button class="primary" id="join">Войти в мир '+icon('arrow')+'</button><button class="quiet" id="help-title">Как играть</button>'+(cfg&&cfg.host?'<button class="quiet danger" id="title-new">Начать новую игру с нуля</button>':'')+'</div><div class="meta">ASTRA LINUX · КАЖДЫЙ САМ ЗА СЕБЯ · ДО '+(cfg?cfg.max_players:25)+' ИГРОКОВ<br>ВЕРСИЯ '+esc(cfg?cfg.version:'')+'</div></div><div class="title-footer">ВЫЖИТЬ. ДОГОВОРИТЬСЯ. УДЕРЖАТЬ.</div>'+(local?'<div class="room-card"><span class="eyebrow">КОМНАТА НА ЭТОМ ПК</span><b>Код '+esc(local)+'</b><span>'+(cfg.lan_addresses.length?'Другим игрокам: '+cfg.lan_addresses.map(esc).join('<br>'):'Одиночная игра: сеть не используется.')+'</span><small>Один компьютер хранит мир. Лагерь каждый строит сам — в лесу или в пустом доме; поселения держат мародёры. Объединяйтесь в кланы, торгуйте или воюйте.</small></div>':'');
 $('join').onclick=join;$('help-title').onclick=()=>showHelp(true);if($('title-new'))$('title-new').onclick=confirmNewWorld;
 const preview=()=>{const cv=$('hero-preview');if(!cv)return;const c=cv.getContext('2d');c.clearRect(0,0,96,96);const im=AS.sprites.heroIcon(0,heroColor);if(im)c.drawImage(im,8,8,80,80);else setTimeout(preview,200);};preview();
 screen.querySelectorAll('[data-color]').forEach(b=>b.onclick=()=>{heroColor=b.dataset.color;screen.querySelectorAll('.swatch').forEach(x=>x.classList.toggle('on',x===b));preview();beep('ui');});
 const nameInput=$('player-name');nameInput.addEventListener('keydown',e=>{if(e.key==='Enter')join();});
}
function showPause(){if(!state)return;modal('pause','<span class="eyebrow">ЭКСПЕДИЦИЯ</span><h2>Передышка</h2>',
 '<div class="modal-body"><div class="menu-list"><button class="primary" id="resume">Продолжить '+icon('arrow')+'</button><button class="secondary" id="journal-menu">'+icon('book')+' Журнал и сюжет</button><button class="secondary" id="people-menu">'+icon('trade')+' Обмен и кланы</button><button class="secondary" id="diplomacy-menu">'+icon('peace')+' Дипломатия</button><button class="secondary" id="map-menu">'+icon('map')+' Карта России</button><button class="secondary" id="settings-menu">'+icon('gear')+' Настройки</button><button class="secondary" id="help-menu">Управление и правила</button>'+(cfg.host?'<button class="quiet danger" id="new-world">Начать новую игру с нуля</button><button class="quiet danger" id="quit-host">Сохранить мир и завершить игру</button>':'')+'</div><div class="notice">В сетевой игре мир продолжается, пока играет хотя бы один участник. Мир сохраняется на компьютере ведущего.</div>'+(cfg.join_code&&cfg.lan_addresses.length?'<div class="room-inline"><b>Код комнаты: '+esc(cfg.join_code)+'</b><p>'+cfg.lan_addresses.map(esc).join('<br>')+'</p></div>':'')+'<p class="small muted" style="margin-top:15px">Закрой вкладку, чтобы выйти. Сессия на этой стороне сохраняется в браузере; не очищай его данные для продолжения тем же персонажем.</p></div>');
 $('resume').onclick=closePanel;$('journal-menu').onclick=showJournal;$('people-menu').onclick=()=>showPeople();$('map-menu').onclick=()=>showMap();$('help-menu').onclick=()=>showHelp(false);$('diplomacy-menu').onclick=showDiplomacy;$('settings-menu').onclick=showSettings;
 if($('new-world'))$('new-world').onclick=confirmNewWorld;
 if($('quit-host'))$('quit-host').onclick=async()=>{if(!confirm('Все игроки отключатся, мир будет сохранён. Завершить?'))return;try{await fetchJson('/api/host',{shutdown:true});}catch(e){}connected=false;screen.innerHTML='<section class="modal"><div class="modal-body"><h2>Мир сохранён</h2><p style="margin-top:15px">Игра завершена. Эту вкладку можно закрыть. Чтобы продолжить, снова запусти «Играть.sh» или ярлык.</p></div></section>';};
}
// Host only: wipe the world and start over. The old save stays next to the new one as a backup.
function confirmNewWorld(){modal('new-world','<span class="eyebrow">ВЕДУЩИЙ</span><h2>Новая игра с нуля</h2>',
 '<div class="modal-body"><p>Мир создаётся заново: все игроки, поселения, лагеря, машины, вещи и уровни исчезнут. Каждому придётся войти снова и начать с первого уровня.</p><p class="small muted" style="margin-top:10px">Старый мир не удаляется — он сохранится рядом резервной копией.</p><div class="event-options" style="margin-top:18px"><button class="primary" id="new-world-yes">Начать заново</button><button class="secondary" id="new-world-no">Отмена</button></div></div>');
 $('new-world-no').onclick=()=>connected?closePanel():showTitle();
 $('new-world-yes').onclick=async()=>{try{await fetchJson('/api/host',{new_world:true});}catch(e){notify('Не получилось',e.message,true);return;}
  connected=false;state=null;latestStamp=0;showTitle();notify('Новый мир создан','Войди — всё начнётся с нуля. Другие игроки тоже войдут заново.');};}
function showSettings(){modal('settings','<span class="eyebrow">ЭТОТ КОМПЬЮТЕР</span><h2>Настройки</h2>',
 '<div class="modal-body"><label class="setting">Музыка<input type="range" id="vol-music" min="0" max="1" step="0.05" value="'+SND.music+'"></label><label class="setting">Звуки и окружение<input type="range" id="vol-sfx" min="0" max="1" step="0.05" value="'+SND.sfx+'"></label><label class="setting">Качество графики<select id="quality"><option value="high">Высокое: свет, частицы, погода</option><option value="low">Экономное: для слабых компьютеров</option></select></label>'+(cfg.host?'<label class="setting check"><input type="checkbox" id="ai-toggle" '+(cfg.settings&&cfg.settings.ai===false?'':'checked')+'> Компьютер управляет стороной без игроков</label>':'<p class="small muted">Настройки комнаты меняет ведущий.</p>')+'<button class="primary" id="settings-done" style="width:100%;margin-top:18px">Готово</button></div>');
 $('quality').value=R.quality;
 $('vol-music').oninput=e=>{SND.setVolume('music',Number(e.target.value));writeStorage('as-music',e.target.value);};
 $('vol-sfx').oninput=e=>{SND.setVolume('sfx',Number(e.target.value));writeStorage('as-sfx',e.target.value);beep('ui');};
 $('quality').onchange=e=>{R.quality=e.target.value;writeStorage('as-quality',R.quality);resize();};
 if($('ai-toggle'))$('ai-toggle').onchange=async e=>{try{const r=await fetchJson('/api/host',{ai:e.target.checked});cfg.settings=r.settings;notify('Настройки комнаты',r.settings.ai?'Компьютер ведёт сторону без игроков.':'Компьютерный противник отключён.');}catch(err){notify('Не сохранено',err.message,true);}};
 $('settings-done').onclick=closePanel;
}
function showHelp(fromTitle){modal('help','<span class="eyebrow">ПОЛЕВОЕ РУКОВОДСТВО</span><h2>Твой первый день</h2>',
 '<div class="modal-body"><div class="controls-grid"><span><kbd>W A S D</kbd> / <kbd>↑ ↓ ← →</kbd></span><span>Движение пешком и на машине</span><span><kbd>Shift</kbd></span><span>Бег; выносливость восстанавливается</span><span><kbd>E</kbd></span><span>Поговорить, собрать, открыть здание, площадь, лагерь, дом, тайник или тело</span><span><kbd>F</kbd></span><span>Сесть в свою машину / выйти рядом с ней</span><span><kbd>H</kbd></span><span>Бинт или аптечка, иначе перевязка за 5 припасов</span><span><kbd>I</kbd> / <kbd>G</kbd> / <kbd>V</kbd></span><span>Рюкзак / поесть / попить (у реки — из реки)</span><span><kbd>Q</kbd> / <kbd>1</kbd>–<kbd>7</kbd></span><span>Сменить оружие</span><span><kbd>X</kbd></span><span>Перезарядка (сама начинается, когда магазин пуст)</span><span><kbd>R</kbd> / <kbd>T</kbd></span><span>Ремкомплект / канистра в бак своей машины</span><span><kbd>O</kbd></span><span>Обмен с игроками рядом и клан</span><span><kbd>L</kbd> / <kbd>C</kbd></span><span>Лагерь / крафт</span><span><kbd>B</kbd></span><span>Поставить пост на трассе</span><span><kbd>M</kbd> / <kbd>J</kbd></span><span>Карта (колесо — масштаб) / журнал заданий</span><span>Мышь + ЛКМ / <kbd>Space</kbd></span><span>Прицел и выстрел</span><span><kbd>Esc</kbd></span><span>Меню: дипломатия, кланы, настройки</span></div>'+
 '<p class="control-note">Каждый сам за себя. Дома нет — его строят. Зайди в пустой дом в городе или найди ровную площадку в лесу и нажми L: так основывается лагерь. В нём строят костёр, спальник (после гибели очнёшься здесь), ящик для вещей, верстак, сборник воды и ограду. Лагерь можно разгромить: чужие ломают стены и забирают всё из ящика.</p>'+
 '<p class="control-note" style="margin-top:12px">Крафт — C. Бинты и верёвку делают в руках, еду и чай — у огня, патроны, гвозди, снаряжение — на верстаке. Материалы (доски, гвозди, металлолом, ткань, порох, травы, шкуры) лежат в брошенных домах (E у дома), в тайниках, падают со зверей и людей. Патроны теперь вещь: без них оружие бесполезно. Погибнешь — рюкзак и монеты останутся на теле, его может обыскать любой.</p>'+
 '<p class="control-note" style="margin-top:12px">Задания дают только люди на площадях поселений: староста, торговец, механик, командир, охотник и медик. Подойди, нажми E, выслушай и возьми работу. Сдают её тому же человеку в любом поселении. В крупных городах сидят радисты — им сдают главы сюжета.</p>'+
 '<p class="control-note" style="margin-top:12px">Свободные поселения держат мародёры, в крупных городах — вместе с головорезами. Перебей их, затем начни захват на площади и удерживай круг 30 секунд. Твоё поселение охраняют твои люди; они не выходят за его пределы. Сторожевая вышка добавляет охранников.</p>'+
 '<p class="control-note" style="margin-top:12px">По окрестностям бродят банды, у руин — мародёры, в лесах — звери, ночью — мутанты. В Сибири и на Севере лежит снег: без тёплой одежды долго не протянуть.</p>'+
 '<p class="control-note" style="margin-top:12px">Игроки могут меняться монетами, вещами и ресурсами (O рядом с игроком) и объединяться в кланы до 6 человек: в клане не стреляют друг в друга и не захватывают чужое. Цель партии: 5 поселений и радиостанция второго уровня. Если погибнешь — теряешь захваченные поселения, а вещи и монеты остаются на теле.</p><button class="primary" id="help-back" style="width:100%;margin-top:20px">Понятно</button></div>');
 $('help-back').onclick=fromTitle?showTitle:closePanel;$('close-panel').onclick=fromTitle?showTitle:closePanel;
}
function costHtml(cost){return Object.keys(cost).map(k=>'<span class="cost '+(state.stock[k]>=cost[k]?'good':'bad')+'">'+icon(k)+'<b>'+cost[k]+'</b><em>/ '+Math.floor(state.stock[k])+'</em></span>').join('');}
function canPay(cost){return Object.keys(cost).every(k=>state.stock[k]>=cost[k]);}
function getBuildCost(t,k){const factor=[1,1.8,2.8][Math.min(t.levels[k],2)],base=cfg.buildings[k].cost,out={};Object.keys(base).forEach(k=>out[k]=Math.ceil(base[k]*factor));return out;}
function costText(cost){return Object.keys(cost).map(k=>icon(k)+' '+cost[k]).join(' ')||'Без затрат';}
function showBuilding(b){if(!state)return;const t=state.towns[b.town],def=cfg.buildings[b.kind],level=t.levels[b.kind],cost=getBuildCost(t,b.kind);
 const own=t.owner===state.me.faction,gate=b.kind==='depot'||level<t.levels.depot,con=t.construct&&t.construct[b.kind],fire=t.fires&&t.fires[b.kind];
 const need=def.workers*(level+1),output=def.output;
 let reason=!own?'Поселение принадлежит другой стороне или нейтрально. Захвати площадь, чтобы строить.':t.capture?'Строительство приостановлено до окончания захвата.':con?'Идут работы. Оставайся рядом — с союзниками стройка идёт быстрее.':!gate?'Для этого улучшения нужен опорный пункт следующего уровня.':level>=3?'Максимальный уровень.':Object.keys(t.construct||{}).length>=2?'В поселении уже две стройки.':!canPay(cost)?'Собери недостающие материалы или дождись производства.':'';
 let extra='';
 if(fire)extra+='<div class="notice danger-notice">'+icon('fire')+' Здание горит! Потуши его, пока огонь не уничтожил уровень. Осталось '+Math.max(0,Math.ceil(fire-state.time))+' сек.<button class="primary" id="extinguish" style="margin-top:10px;width:100%">Потушить</button></div>';
 if(b.kind==='workshop'&&own&&level>0){extra+='<span class="eyebrow">СНАРЯЖЕНИЕ · ЛИЧНОЕ</span><div class="craft-grid">';
  [['weapon',cfg.weapons,'gun'],['armor',cfg.armor,'vest']].forEach(([item,table,ic])=>table.forEach((it,tier)=>{if(!tier||!it.workshop)return;const have=item==='weapon'?state.me.weapons.includes(tier):state.me.gear[item]>=tier,lock=level<it.workshop;
  extra+='<button class="decision" data-craft="'+item+'" data-tier="'+tier+'" '+(have||lock||!canPay(it.cost)?'disabled':'')+'><div><b>'+icon(ic)+' '+esc(it.name)+'</b><strong>'+(have?'есть':lock?'мастерская '+it.workshop:'')+'</strong></div><small>'+(item==='weapon'?'Урон '+it.dmg+' · дальность '+it.range+' · '+(it.cd<.3?'очереди':'одиночные'):'Снижает урон на '+Math.round(it.reduce*100)+'%')+'</small><span class="decision-cost">'+costText(it.cost)+'</span></button>';}));extra+='</div>';}
 if(b.kind==='garage'&&own&&level>0)extra+='<div class="building-stat-row"><span>Твоя машина: '+Math.round(state.me.car.hp||100)+'%</span><button class="secondary" id="repair" '+((state.me.car.hp||100)>=100?'disabled':'')+'>'+icon('tool')+' Отремонтировать · 4 металла</button></div>';
 modal('building','<span class="eyebrow">'+esc(t.name.toUpperCase())+' / '+(level?'УРОВЕНЬ '+level:'РУИНЫ')+'</span><h2>'+esc(def.name)+'</h2>',
 '<div class="modal-body"><canvas id="building-art" class="building-art" width="600" height="230"></canvas><p>'+esc(def.desc)+'</p>'+(con?'<div class="bar big"><i style="width:'+Math.round(con.progress/con.total*100)+'%"></i></div><p class="small muted">Стройка уровня '+con.level+': '+Math.round(con.progress)+' / '+Math.round(con.total)+' сек.</p>':'')+'<div class="building-stat-row"><span>Следующий уровень</span><b>'+Math.min(3,level+1)+' / 3 · '+cfg.build_time[Math.min(level,2)]+' сек.</b></div><div class="building-stat-row"><span>'+(output?'Выпуск за 12 секунд':'Назначение')+'</span><b>'+(output?output[1]*(level+1)+' '+cfg.resources[output[0]].toLowerCase():b.kind==='house'?'+8 жителей':b.kind==='guard'?'+12 обороны, вышка стреляет':b.kind==='radio'?'+5% переговоров':b.kind==='warehouse'?'+'+cfg.storage[1]+' к пределу запасов':'Открывает улучшения')+'</b></div>'+(need?'<div class="building-stat-row"><span>Требуется рабочих / свободно</span><b>'+need+' / '+(t.population-t.workers)+'</b></div>':'')+'<span class="eyebrow">МАТЕРИАЛЫ</span><div class="costs">'+costHtml(cost)+'</div>'+(reason?'<div class="notice">'+esc(reason)+'</div>':'')+'<div class="modal-actions"><button class="primary" id="build" '+((reason||level>=3)?'disabled':'')+'>'+(level?'Улучшить здание':'Восстановить')+icon('tool')+'</button></div>'+extra+'</div>');
 selected=b.id;const art=$('building-art').getContext('2d');art.fillStyle='#2a3229';art.fillRect(0,0,600,230);
 for(let i=0;i<4;i++){const L=Math.min(3,i),sp=AS.sprites.building(b.kind,L,t.owner,b.w,b.h);art.globalAlpha=L===level?1:.42;const s=b.kind==='radio'?.62:.9;art.drawImage(sp.im,75+i*150-sp.ox*s,130-sp.oy*s,sp.im.width*s,sp.im.height*s);art.globalAlpha=1;art.fillStyle=L===level?'#e7a568':'#a5ada0';art.font='11px Segoe UI';art.textAlign='center';art.fillText(L?'Уровень '+L:'Руины',75+i*150,222);}
 $('build').onclick=async()=>{const r=await action('build',{id:b.id});if(r)showBuilding(b);};
 if($('extinguish'))$('extinguish').onclick=async()=>{const r=await action('extinguish',{id:b.id});if(r)showBuilding(b);};
 if($('repair'))$('repair').onclick=async()=>{const r=await action('repair',{});if(r)showBuilding(b);};
 screen.querySelectorAll('[data-craft]').forEach(btn=>btn.onclick=async()=>{const r=await action('craft',{item:btn.dataset.craft,tier:Number(btn.dataset.tier)});if(r)showBuilding(b);});
}
function showTown(id,tab){if(!state)return;const t=state.towns[id],f=state.me.faction,own=t.owner===f,cap=t.capture,big=t.guards>3&&!t.owner;tab=tab||'main';
 const held=t.guards>0&&!(t.owner&&friendly(t.owner));
 let html='<div class="modal-body"><div class="town-faction" style="color:'+sideColor(t.owner)+'">'+icon('flag')+' '+(t.owner?sideName(t.owner):'Под мародёрами')+' · '+esc(t.region)+'</div><div class="town-stats" style="margin:18px 0"><div><b>'+Math.round(t.loyalty)+'%</b><span>лояльность</span></div><div><b>'+t.population+'</b><span>жители</span></div><div><b>'+t.guards+'</b><span>'+(t.owner?'охрана':'мародёры')+'</span></div>'+(t.intel?'<div><b>+'+t.intel+'%</b><span>разведка</span></div>':'')+'</div>';
 html+='<div class="tabs"><button class="tab '+(tab==='main'?'on':'')+'" data-tab="main">Площадь</button><button class="tab '+(tab==='trade'?'on':'')+'" data-tab="trade">'+icon('trade')+' Торговля</button><button class="tab '+(tab==='shop'?'on':'')+'" data-tab="shop">'+icon('bag')+' Магазин</button></div>';
 if(tab==='shop'){html+=shopHtml(t,own);}
 else if(tab==='trade'){
  const prices=cfg.prices[t.region]||cfg.prices.default,hostile=t.owner&&!own&&!(state.truce.pairs[t.owner]>state.time)&&!friendly(t.owner);
  html+='<p>Местные меняют товары по ценам региона. '+(own?'В своём поселении курс лучше с ростом лояльности.':'Чужие торговцы берут наценку.')+'</p>'+(hostile?'<div class="notice">Торговцы чужой стороны не меняются с вами без перемирия.</div>':'')+'<div class="price-row">'+Object.keys(cfg.resources).map(k=>'<span>'+icon(k)+'<b>'+prices[k].toFixed(2)+'</b></span>').join('')+'</div><div class="trade-form"><label>Отдать<select id="give">'+Object.keys(cfg.resources).map(k=>'<option value="'+k+'">'+cfg.resources[k]+'</option>').join('')+'</select></label><label>Количество<select id="amount"><option>10</option><option>25</option><option>50</option></select></label><label>Получить<select id="get">'+Object.keys(cfg.resources).map(k=>'<option value="'+k+'" '+(k==='food'?'selected':'')+'>'+cfg.resources[k]+'</option>').join('')+'</select></label></div><div class="trade-preview" id="trade-preview"></div><button class="primary" id="trade" '+(hostile?'disabled':'')+' style="width:100%">'+icon('trade')+' Обменять</button>';
 }else{
 if(cap)html+='<div class="notice"><b>'+sideName(cap.faction)+' захватывают площадь</b><br>'+Math.max(0,Math.floor(cap.progress))+' / 30 сек. '+(cap.contested?'Рядом противник — прогресс остановлен.':'Закрой окно и удерживай круг пешком.')+'</div>';
 if(own){html+='<div class="town-buttons"><button class="secondary" id="refuel" '+(distance(state.me.car,t)>650||state.me.car.fuel>=carTank()-.5?'disabled':'')+'>Заправить машину <span>Бак '+Math.floor(state.me.car.fuel)+' / '+carTank()+' · из запаса ('+Math.floor(state.stock.fuel)+')'+(distance(state.me.car,t)>650?' · подгони машину':'')+'</span></button>'+(state.me.items.meat_raw?'<button class="secondary" id="cook">Пожарить мясо у костра <span>Сырое мясо ×'+state.me.items.meat_raw+'</span></button>':'')+'<button class="secondary" id="canteen">Столовая и колодец <span>Сытость +50, вода +70 · 3 припаса</span></button><button class="secondary" id="aid">Помочь жителям <span>8 припасов · +14 лояльности</span></button><button class="secondary" id="tax">Собрать дань <span>+12 металла и припасов · −18 лояльности</span></button></div>';
  const cargo=Object.values(t.cargo||{}).reduce((a,b)=>a+b,0);html+='<p class="small muted" style="margin-top:10px">Охрана поселения: '+t.guards+' · вышка добавляет бойцов. Груз для отправки в главное поселение: '+Math.floor(cargo)+'; колонна выходит, когда наберётся 10 единиц.</p>';}
 else if(!cap){
  const truce=t.owner&&(state.truce.pairs[t.owner]>state.time||friendly(t.owner));
  html+='<p>Выбери способ установить контроль. После успеха нужно удержать площадь 30 секунд.</p>'+(truce?'<div class="notice">Перемирие или общий клан: это поселение захватывать нельзя.</div>':'');
  if(held)html+='<div class="notice danger-notice">'+(t.owner?'Поселение охраняют бойцы '+esc(sideName(t.owner)):'Площадь держат мародёры'+(big?' и головорезы':''))+': '+t.guards+'. Пока они живы, захват невозможен. Охрана не выходит за пределы поселения.</div>';
  html+='<div class="capture-options">';
  const preps=[['intimidate','Запугивание','+15% на 4 мин., лояльность жителей −10',{metal:6}],['gift','Гуманитарная помощь','+15% на 4 мин., репутация +2',{food:10}]];
  const defs=[['talk','Переговоры','Больше лояльности, здания сохраняются',{food:12,wood:8}],['bribe','Подкуп','Дороже, но шанс обычно выше',{food:18,fuel:8}],['assault','Штурм','Ниже лояльность, одно здание повреждено; провал −25 здоровья',{metal:12,food:6}],['scout','Разведка','При успехе +20% на четыре минуты',{food:3}],...preps];
  defs.forEach(d=>{const prep=['scout','intimidate','gift'].includes(d[0]),chance=t.chances[d[0]]!=null?t.chances[d[0]]:(d[0]==='intimidate'?80:90);html+='<button class="decision" data-method="'+d[0]+'" '+(!canPay(d[3])||t.shield>state.time||truce||(held&&!prep)?'disabled':'')+'><div><b>'+d[1]+'</b><strong>'+chance+'%</strong></div><small>'+d[2]+'</small><span class="decision-cost">'+costText(d[3])+'</span></button>';});html+='</div>';
  if(t.shield>state.time)html+='<div class="notice">Защита после захвата: ещё '+Math.ceil(t.shield-state.time)+' сек.</div>';
  if(t.owner&&t.owner!==f)html+='<div class="town-buttons"><button class="secondary" id="raid" '+(truce?'disabled':'')+'>Набег <span>'+(t.chances.raid||0)+'% · 8 металла, 4 припаса · увести часть запасов</span></button></div>';
 }
 const delivery=state.me.quests.find(q=>q.kind==='deliver'&&q.town===id&&state.me.stats.deliver-q.start<q.target);
 html+='<div class="town-buttons"><button class="secondary" id="event" '+(!t.event_ready?'disabled':'')+'>Происшествие на площади <span>'+(t.event_ready?'Решение с шансом успеха':'Новое событие появится позже')+'</span></button>'+(delivery?'<button class="primary" id="deliver">Доставить 6 припасов</button>':'')+'</div>';
 }
 html+='</div>';
 modal('town','<span class="eyebrow">ПЛОЩАДЬ ПОСЕЛЕНИЯ</span><h2>'+esc(t.name)+'</h2>',html);
 selected=id;
 screen.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>showTown(id,b.dataset.tab));
 if(tab==='shop'){screen.querySelectorAll('[data-buy]').forEach(b=>b.onclick=async()=>{const r=await action('buy',{town:id,kind:b.dataset.buy,index:Number(b.dataset.index||0)});if(r)showTown(id,'shop');});screen.querySelectorAll('[data-equip]').forEach(b=>b.onclick=()=>{equip(Number(b.dataset.equip));setTimeout(()=>showTown(id,'shop'),300);});return;}
 if(tab==='trade'){const prices=cfg.prices[t.region]||cfg.prices.default;const upd=()=>{const g=$('give').value,r=$('get').value,a=Number($('amount').value),mod=own?.86+t.loyalty*.001:.78,n=g===r?0:Math.floor(a*prices[g]/prices[r]*mod);$('trade-preview').innerHTML=g===r?'Выбери разные товары.':'−'+a+' '+cfg.resources[g].toLowerCase()+' → <b>+'+n+' '+cfg.resources[r].toLowerCase()+'</b>';};['give','get','amount'].forEach(k=>$(k).onchange=upd);upd();
  $('trade').onclick=async()=>{await action('trade',{town:id,give:$('give').value,get:$('get').value,amount:Number($('amount').value)});};return;}
 if($('refuel'))$('refuel').onclick=async()=>{await action('refuel',{town:id});showTown(id);};
 if($('cook'))$('cook').onclick=async()=>{await action('cook',{town:id});showTown(id);};
 if($('canteen'))$('canteen').onclick=async()=>{await action('canteen',{town:id});showTown(id);};
 if($('aid'))$('aid').onclick=async()=>{await action('aid',{town:id});showTown(id);};
 if($('tax'))$('tax').onclick=async()=>{await action('tax',{town:id});showTown(id);};
 if($('raid'))$('raid').onclick=async()=>{await action('raid',{town:id});showTown(id);};
 if($('deliver'))$('deliver').onclick=async()=>{await action('deliver',{town:id});showTown(id);};
 if($('event'))$('event').onclick=async()=>{const r=await action('event_open',{town:id});if(r&&r.event)showEvent(r.event);};
 screen.querySelectorAll('[data-method]').forEach(button=>button.onclick=async()=>{const method=button.dataset.method,prep=['scout','intimidate','gift'].includes(method);const r=await action(prep?'scout':'capture',{town:id,method});if(r){if(r.success&&!prep)closePanel();else showTown(id);}});
}
function shopHtml(t,own){const me=state.me,hostile=t.owner&&!own&&!(state.truce.pairs[t.owner]>state.time)&&!friendly(t.owner);
 let h='<div class="shop-head">'+icon('coin')+' <b>'+me.coins+'</b> монет<span>Монеты платят люди на площадях за задания и радисты за главы сюжета. Покупки — личные.</span></div>'+(hostile?'<div class="notice">Торговцы чужой стороны тебе не продают.</div>':'');
 const row=(kind,idx,it,stat,owned)=>{const lock=me.level<(it.level||1),poor=me.coins<it.price;return '<button class="decision" data-buy="'+kind+'" data-index="'+idx+'" '+(owned||lock||poor||hostile?'disabled':'')+'><div><b>'+esc(it.name)+'</b><strong>'+(owned?'есть':icon('coin')+' '+it.price)+'</strong></div><small>'+stat+'</small><span class="decision-cost">'+(lock?'Нужен уровень '+it.level:poor&&!owned?'Не хватает монет':'')+'</span></button>';};
 h+='<span class="eyebrow shop-eyebrow">ОРУЖИЕ</span><div class="craft-grid">';cfg.weapons.forEach((w,i)=>{if(i)h+=row('weapon',i,w,'Урон '+w.dmg+' · дальность '+w.range+' · '+(w.cd<.3?'очереди':w.cd>1.2?'медленный, точный':'одиночные'),me.weapons.includes(i));});h+='</div>';
 h+='<span class="eyebrow shop-eyebrow">БРОНЯ</span><div class="craft-grid">';cfg.armor.forEach((a,i)=>{if(i)h+=row('armor',i,a,'Снижает урон на '+Math.round(a.reduce*100)+'%',me.gear.armor>=i);});h+='</div>';
 h+='<span class="eyebrow shop-eyebrow">ОДЕЖДА · ЗАЩИТА ОТ ХОЛОДА</span><div class="craft-grid">';cfg.clothes.forEach((a,i)=>{if(i)h+=row('clothes',i,a,'Тепло +'+a.warm+'. Нужна в Сибири и на Севере, ночью и в непогоду.',me.gear.clothes>=i);});h+='</div>';
 h+='<span class="eyebrow shop-eyebrow">РЮКЗАКИ</span><div class="craft-grid">';cfg.backpacks.forEach((a,i)=>{if(i)h+=row('backpack',i,a,a.slots+' мест для вещей',me.gear.backpack>=i);});h+='</div>';
 const used=Object.values(me.items).reduce((a,b)=>a+b,0),room=cfg.backpacks[me.gear.backpack].slots;
 h+='<span class="eyebrow shop-eyebrow">ЕДА, ВОДА, МЕДИЦИНА · РЮКЗАК '+used+' / '+room+'</span><div class="craft-grid">';Object.keys(cfg.items).forEach(k=>{const it=cfg.items[k];if(!it.price)return;h+=row(k,0,it,esc(it.desc)+' Есть: '+(me.items[k]||0)+'.',false);});h+='</div>';
 h+='<span class="eyebrow shop-eyebrow">ДЛЯ ФРАКЦИИ</span><div class="craft-grid">';Object.keys(cfg.shop).forEach(k=>{const it=cfg.shop[k];h+=row(k,0,it,esc(it.desc),false);});h+='</div>';
 h+='<span class="eyebrow shop-eyebrow">ТВОЁ ОРУЖИЕ · Q ИЛИ 1–7</span><div class="owned">'+me.weapons.slice().sort((a,b)=>a-b).map((i,n)=>'<button class="'+(i===me.gear.weapon?'primary':'secondary')+'" data-equip="'+i+'">'+(n+1)+' · '+esc(cfg.weapons[i].name)+'</button>').join('')+'</div>';
 return h;}
function showEvent(ev){let html='<div class="modal-body"><p>'+esc(ev.text)+'</p><div class="event-options">';
 ev.options.forEach((o,i)=>{html+='<button class="decision" data-choice="'+i+'" '+(!canPay(o.cost)?'disabled':'')+'><div><b>'+esc(o.name)+'</b><strong>'+o.chance+'%</strong></div><span class="decision-cost">'+costText(o.cost)+'</span><small>Успех: '+esc(Object.keys(o.reward).map(k=>o.reward[k]+' '+cfg.resources[k].toLowerCase()).join(', ')||'помощь')+(o.heal?' · здоровье +'+o.heal:'')+(o.intel?' · разведка +'+o.intel+'%':'')+(o.loyalty?' · лояльность '+(o.loyalty>0?'+':'')+o.loyalty:'')+' · репутация '+(o.rep>0?'+':'')+o.rep+'</small><small>Неудача: затраты теряются'+(o.risk?', здоровье −'+o.risk:'.')+'</small></button>';});
 html+='</div><div class="notice">Один бросок от 1 до 100 на компьютере ведущего. Успех — если результат не больше шанса. Событие общее для фракции: союзник может завершить его первым.</div></div>';
 modal('event','<span class="eyebrow">НЕБОЛЬШАЯ ИСТОРИЯ</span><h2>'+esc(ev.name)+'</h2>',html);
 screen.querySelectorAll('[data-choice]').forEach(b=>b.onclick=async()=>{const r=await action('event_choice',{id:ev.id,choice:Number(b.dataset.choice)});if(r)closePanel();});
}
const KIND_LABEL={harvest:'СБОР',build:'СТРОЙКА',deliver:'ДОСТАВКА',aid:'ПОМОЩЬ',explore:'РАЗВЕДКА',hunt:'ОХОТА',mutants:'МУТАНТЫ',capture:'КОНТРОЛЬ',event:'ПРОИСШЕСТВИЕ',kills:'ОХРАНА',loot:'ПОИСК',trade:'ТОРГОВЛЯ'};
function storyHtml(){const s=state.story,c=s.chapter;if(!c)return '<div class="story-card"><h3>Сюжет завершён</h3><p>Мир помнит ваши решения: '+esc(s.flags.join(', ')||'—')+'</p></div>';
 const radios=cfg.givers.filter(g=>g.type==='radio').map(g=>state.towns[g.town].name);
 let html='<div class="story-card"><div class="section-label"><span>ГЛАВА '+(s.index+1)+' · '+esc(sideName(state.me.faction).toUpperCase())+'</span><b class="'+(s.ready?'good':'')+'">'+s.progress[0]+' / '+s.progress[1]+'</b></div><h3>'+esc(c.title)+'</h3><p>'+esc(c.text)+'</p>';
 if(s.ready)html+='<div class="notice">Глава выполнена. Решение принимается у радиста крупного города: '+esc(radios.join(', '))+'.</div>';
 else if(c.goal.kind==='victory'){const radio=Math.max(0,...Object.values(state.towns).filter(t=>t.owner===state.me.faction).map(t=>t.levels.radio));html+='<p class="small muted">'+esc(sideName(state.me.faction))+': поселений '+Object.values(state.towns).filter(t=>t.owner===state.me.faction).length+' / 5 · лучшая радиостанция '+radio+' / 2</p>';}
 return html+'</div>';}
function characterHtml(){const p=state.me,need=cfg.xp_table[p.level-1]||1;return '<div class="char-card"><div class="section-label"><span>ПЕРСОНАЖ · '+esc(p.name.toUpperCase())+'</span><b>'+p.level+' / '+cfg.max_level+' ур.</b></div><div class="bar big"><i style="width:'+(p.level>=cfg.max_level?100:Math.round(p.xp/need*100))+'%"></i></div><p class="small muted">Опыт '+p.xp+' / '+need+' · здоровье '+p.max_hp+' · урон +'+3*(p.level-1)+'%. Опыт дают сбор, стройка, события, разведка новых мест, бой, тайники, захваты и задания.</p>'+'<div class="perks">'+cfg.perks.map(k=>'<span class="perk '+(p.level>=k.level?'on':'')+'"><b>'+k.level+' ур. · '+esc(k.name)+'</b><small>'+esc(k.desc)+'</small></span>').join('')+'</div></div>';}
function showJournal(){if(!state)return;const qs=state.me.quests;let html='<div class="modal-body">'+characterHtml()+storyHtml()+'<span class="eyebrow" style="display:block;margin:18px 0 10px">ЗАДАНИЯ · '+qs.length+' / 3</span><div class="quests-list">';
 if(!qs.length)html+='<p class="small muted">Заданий нет. Работу дают люди на площадях поселений: подойди к ним и нажми E.</p>';
 qs.forEach(q=>{const n=Math.max(0,state.me.stats[q.kind]-q.start),done=n>=q.target,role=(cfg.givers.find(g=>g.type===q.giver)||{}).role||'';
 html+='<div class="quest-card"><div class="section-label"><span>'+esc(KIND_LABEL[q.kind]||'ПОРУЧЕНИЕ')+' · '+esc(q.from||'')+'</span><b class="'+(done?'good':'')+'">'+Math.min(n,q.target)+' / '+q.target+'</b></div><h3>'+esc(q.name)+'</h3><p>'+esc(q.text)+'</p><small>Награда: '+(q.coins?q.coins+' монет, ':'')+esc(Object.keys(q.reward).map(k=>q.reward[k]+' '+cfg.resources[k].toLowerCase()).join(', '))+'</small>'+(done?'<p class="good small">Готово. Сдать: '+esc(role.toLowerCase())+' в любом поселении.</p>':'')+(q.town?'<button class="quiet quest-waypoint" data-town="'+q.town+'">Отметить на карте</button>':'')+'<button class="quiet danger" data-drop="'+q.id+'">Отказаться</button></div>';});
 html+='</div><div class="notice">Главная цель: 5 поселений под контролем и радиостанция уровня 2. Выполнено заданий: '+state.me.completed+'. Репутация: '+Math.round(state.reputation)+'.</div></div>';
 modal('journal','<span class="eyebrow">ДНЕВНИК ВЫЖИВШЕГО</span><h2>Журнал экспедиции</h2>',html,'wide');
 screen.querySelectorAll('[data-drop]').forEach(b=>b.onclick=async()=>{if(!confirm('Бросить задание?'))return;await action('quest_drop',{id:b.dataset.drop});showJournal();});
 screen.querySelectorAll('.quest-waypoint').forEach(b=>b.onclick=()=>{waypoint=Object.assign({},state.towns[b.dataset.town]);showMap(b.dataset.town);});
}
function showDialog(d){dialogGiver=d.giver;const g=d.giver,t=state.towns[g.town];
 let html='<div class="modal-body dialog"><div class="dialog-head"><div class="portrait" style="background-position:'+(g.art%4*100/3).toFixed(3)+'% '+(Math.floor(g.art/4)*100)+'%"></div><div><p class="speech">«'+esc(d.greet)+'»</p><p class="lore">'+esc(d.lore)+'</p></div></div>';
 d.turnins.forEach(q=>{html+='<div class="quest-card done"><div class="section-label"><span>ЗАДАНИЕ ВЫПОЛНЕНО</span><b class="good">'+icon('coin')+' '+q.coins+'</b></div><h3>'+esc(q.name)+'</h3><small>Награда: '+esc(Object.keys(q.reward).map(k=>q.reward[k]+' '+cfg.resources[k].toLowerCase()).join(', '))+'</small><button class="primary" data-turnin="'+q.id+'">Сдать работу</button></div>';});
 d.progress.forEach(q=>{html+='<p class="small muted">'+esc(q.name)+': '+Math.min(q.n,q.target)+' / '+q.target+' — «Как сделаешь, приходи».</p>';});
 if(d.story){const s=d.story,c=s.chapter;html+='<span class="eyebrow shop-eyebrow">РАДИОСВЯЗЬ</span>';
  if(!c)html+='<p>«Эфир чист. Ты сделал всё, что мог».</p>';
  else if(s.ready){html+='<div class="story-card"><h3>'+esc(c.title)+'</h3><p>«Слышу тебя. Пора решать».</p><div class="event-options">';c.choices.forEach((o,i)=>{html+='<button class="decision" data-story="'+i+'" '+(o.cost&&!canPay(o.cost)?'disabled':'')+'><div><b>'+esc(o.name)+'</b><strong>'+(o.rep?'реп. '+(o.rep>0?'+':'')+o.rep:'')+'</strong></div><small>'+esc(o.text)+'</small><span class="decision-cost">'+icon('coin')+' '+cfg.story_coins+' '+(Object.keys(o.reward||{}).length?'Награда: '+costText(o.reward):'')+(o.cost?' Цена: '+costText(o.cost):'')+'</span></button>';});html+='</div></div>';}
  else html+='<div class="story-card"><h3>'+esc(c.title)+'</h3><p>'+esc(c.text)+'</p><p class="small muted">Выполнено: '+s.progress[0]+' / '+s.progress[1]+'. «Сделаешь — выходи на связь».</p></div>';}
 if(d.offers.length){html+='<span class="eyebrow shop-eyebrow">РАБОТА</span>';d.offers.forEach(o=>{html+='<div class="quest-card"><p class="speech">«'+esc(o.intro)+'»</p><h3>'+esc(o.name)+'</h3><p>'+esc(o.text)+'</p><small>Оплата: '+o.coins+' монет · '+esc(Object.keys(o.reward).map(k=>o.reward[k]+' '+cfg.resources[k].toLowerCase()).join(', '))+'</small><button class="secondary" data-accept="'+o.kind+'">Возьмусь</button></div>';});}
 else if(d.full)html+='<div class="notice">«У тебя и так дел по горло. Закончи начатое — потом приходи». Можно держать три задания.</div>';
 else if(!d.turnins.length&&!d.story)html+='<p class="small muted">«Пока ничего. Загляни позже — или к другим на площади».</p>';
 html+='<button class="quiet" id="bye" style="width:100%;margin-top:14px">«Бывай»</button></div>';
 modal('dialog','<span class="eyebrow">'+esc(g.role.toUpperCase())+' · '+esc(t.name.toUpperCase())+'</span><h2>'+esc(g.name)+'</h2>',html);
 $('bye').onclick=closePanel;
 const reopen=r=>{if(r&&r.dialog)showDialog(r.dialog);};
 screen.querySelectorAll('[data-accept]').forEach(b=>b.onclick=async()=>reopen(await action('quest_accept',{giver:g.id,kind:b.dataset.accept})));
 screen.querySelectorAll('[data-turnin]').forEach(b=>b.onclick=async()=>reopen(await action('quest_turnin',{giver:g.id,id:b.dataset.turnin})));
 screen.querySelectorAll('[data-story]').forEach(b=>b.onclick=async()=>{const r=await action('story_choice',{choice:Number(b.dataset.story)});if(r)reopen(await action('talk',{giver:g.id}));});
}
function showShelter(){showCamp(myCamp());}
// Camps: what is built, what can be built from the backpack, the crate.
function myCamp(){return state&&state.sides[state.me.faction].camp?(state.camps||[]).find(c=>c.id===state.sides[state.me.faction].camp):null;}
function slotsUsed(items){return Object.keys(items).reduce((a,k)=>a+Math.ceil(items[k]/((cfg.items[k]||{}).stack||1)),0);}
function needsHtml(needs){return Object.keys(needs||{}).map(k=>{const have=state.me.items[k]||0;return '<span class="cost '+(have>=needs[k]?'good':'bad')+'"><b>'+esc(cfg.items[k].name)+'</b> '+have+' / '+needs[k]+'</span>';}).join(' ');}
function hasNeeds(needs){return Object.keys(needs||{}).every(k=>(state.me.items[k]||0)>=needs[k]);}
function campCanUse(c){return c.owner===state.me.faction||friendly(c.owner);}
// The own camp seen from afar: where it is, what stands there, a waypoint, and abandoning it without walking back.
function showCampFar(camp){const me=state.me,parts=cfg.camp_parts,near=Object.values(state.towns).slice().sort((a,b)=>distance(a,camp)-distance(b,camp))[0];
 const built=['fire','bed','stash','bench','collector'].filter(k=>camp.parts[k]&&camp.parts[k].hp>0).map(k=>camp.house&&parts[k].house_name?parts[k].house_name:parts[k].name);
 const st=camp.stash||{items:{},coins:0},stashed=slotsUsed(st.items),owner=camp.owner===me.faction;
 let h='<div class="modal-body"><p>'+(camp.house?'Обжитый дом':'Лагерь под открытым небом')+' у поселения <b>'+esc(near?near.name:'—')+'</b> · отсюда '+(Math.round(distance(camp,me)/100)/10)+' км.</p>'+
  '<p class="small muted" style="margin-top:8px">Постройки: '+(built.length?esc(built.join(', ')):'пока нет')+'. Ограда '+(camp.breached?'не закрыта':'закрыта')+'.'+(camp.parts.stash&&camp.parts.stash.hp>0?' В ящике: '+stashed+' мест'+(st.coins?', '+st.coins+' монет':'')+'.':'')+'</p>'+
  '<div class="event-options" style="margin-top:16px"><button class="primary" id="camp-way">Указатель к лагерю</button>'+(owner?'<button class="quiet danger" id="camp-far-abandon">Бросить лагерь отсюда</button>':'')+'</div>'+
  (owner?'<p class="small muted" id="camp-far-note" style="margin-top:10px">Постройки исчезнут. Вещи и монеты из ящика останутся лежать на месте лагеря — их сможет забрать любой. После этого новый лагерь можно заложить там, где стоишь (L).</p>':'<p class="small muted" style="margin-top:10px">Это лагерь твоего клана; бросить его может только хозяин.</p>')+'</div>';
 modal('camp','<span class="eyebrow">ТВОЙ ЛАГЕРЬ · ДАЛЕКО</span><h2>'+(camp.house?'Обжитый дом':'Лагерь')+' · '+esc(sideName(camp.owner))+'</h2>',h);
 $('camp-way').onclick=()=>{waypoint={x:camp.x,y:camp.y,name:'Лагерь'};closePanel();notify('Указатель на лагерь','Следуй стрелке.');};
 const ab=$('camp-far-abandon');if(ab)ab.onclick=async()=>{
  if(!ab.dataset.sure){ab.dataset.sure='1';ab.textContent='Точно бросить? Нажми ещё раз';ab.classList.add('armed');return;}
  const r=await action('camp_abandon',{camp:camp.id});if(!r)return;if(waypoint&&waypoint.name==='Лагерь')waypoint=null;closePanel();};}
function showCamp(camp){if(!state)return;if(!camp){foundCamp();return;}
 const own=campCanUse(camp),parts=cfg.camp_parts,house=!!camp.house,me=state.me;
 let h='<div class="modal-body"><p>'+(house?'Лагерь в заброшенном доме: стены уже стоят, нужна только дверь.':'Лагерь под открытым небом: обнеси его частоколом из восьми секций с воротами.')+' '+(camp.breached?'<b class="bad">Ограда не закрыта — чужие могут залезть в ящик.</b>':'<b class="good">Ограда закрыта.</b>')+'</p>';
 if(own){h+='<span class="eyebrow shop-eyebrow">ПОСТРОЙКИ</span><div class="craft-grid">';
  ['fire','bed','stash','bench','collector'].forEach(k=>{const def=parts[k],part=camp.parts[k],built=part&&part.hp>0,name=house&&def.house_name?def.house_name:def.name;
   h+='<button class="decision" data-build="'+k+'" '+(built||!hasNeeds(def.needs)?'disabled':'')+'><div><b>'+esc(name)+'</b><strong>'+(built?'есть · '+part.hp+'/'+part.max:'')+'</strong></div><small>'+esc(def.desc)+'</small><span class="decision-cost">'+(built?'':needsHtml(def.needs))+'</span></button>';});
  const fence=Object.values(camp.fence).filter(f=>!f.house),walls=fence.filter(f=>f.kind==='wall'&&f.hp>0).length,gate=camp.fence.gate&&camp.fence.gate.hp>0;
  if(!house)h+='<button class="decision" data-build="wall" '+(walls>=8||!hasNeeds(parts.wall.needs)?'disabled':'')+'><div><b>Частокол</b><strong>'+walls+' / 8</strong></div><small>'+esc(parts.wall.desc)+'</small><span class="decision-cost">'+needsHtml(parts.wall.needs)+'</span></button>';
  h+='<button class="decision" data-build="gate" '+(gate||!hasNeeds(parts.gate.needs)?'disabled':'')+'><div><b>'+(house?'Дверь':'Ворота')+'</b><strong>'+(gate?'есть':'')+'</strong></div><small>'+esc(parts.gate.desc)+'</small><span class="decision-cost">'+(gate?'':needsHtml(parts.gate.needs))+'</span></button></div>';}
 else h+='<div class="notice">Это чужой лагерь ('+esc(sideName(camp.owner))+'). '+(camp.breached?'Ограда пробита: ящик можно открыть.':'Чтобы добраться до ящика, пробей стену или ворота: стреляй или ломай (E вплотную).')+'</div>';
 if(camp.stash&&camp.parts.stash&&camp.parts.stash.hp>0){const st=camp.stash;
  h+='<span class="eyebrow shop-eyebrow">ЯЩИК · '+slotsUsed(st.items)+' / '+cfg.stash_slots+' МЕСТ · '+st.coins+' МОНЕТ</span><div class="stash-cols"><div><b>Рюкзак</b>'+(own?Object.keys(me.items).map(k=>'<div class="stash-row"><span>'+esc(cfg.items[k].name)+' ×'+me.items[k]+'</span><button class="quiet" data-put="'+k+'" data-n="'+me.items[k]+'">Положить</button></div>').join('')+'<div class="stash-row"><span>Монеты: '+me.coins+'</span><button class="quiet" data-put="coins" data-n="'+me.coins+'">Положить</button></div>':'<p class="small muted">Класть в чужой ящик нельзя.</p>')+'</div><div><b>Ящик</b>'+Object.keys(st.items).map(k=>'<div class="stash-row"><span>'+esc(cfg.items[k].name)+' ×'+st.items[k]+'</span><button class="quiet" data-take="'+k+'" data-n="'+st.items[k]+'">Взять</button></div>').join('')+(st.coins?'<div class="stash-row"><span>Монеты: '+st.coins+'</span><button class="quiet" data-take="coins" data-n="'+st.coins+'">Взять</button></div>':'')+'</div></div>';}
 if(own)h+='<p class="small muted" style="margin-top:12px">C — крафт: у костра готовят еду и чай, на верстаке — патроны, гвозди, снаряжение. Спальник возвращает сюда после гибели. Рядом с костром заживают раны.</p>'+(camp.owner===me.faction?'<button class="quiet danger" id="camp-abandon" style="width:100%;margin-top:10px">Бросить лагерь</button>':'');
 h+='</div>';
 modal('camp','<span class="eyebrow">'+(own?'ТВОЙ ЛАГЕРЬ':'ЧУЖОЙ ЛАГЕРЬ')+'</span><h2>'+(house?'Обжитый дом':'Лагерь')+' · '+esc(sideName(camp.owner))+'</h2>',h,'wide');
 const again=()=>{const c=(state.camps||[]).find(x=>x.id===camp.id);if(c)showCamp(c);else closePanel();};
 screen.querySelectorAll('[data-build]').forEach(b=>b.onclick=async()=>{const r=await action('camp_build',{camp:camp.id,kind:b.dataset.build});if(r)setTimeout(again,150);});
 screen.querySelectorAll('[data-put]').forEach(b=>b.onclick=async()=>{await action('stash_put',{camp:camp.id,item:b.dataset.put,count:Number(b.dataset.n)});setTimeout(again,150);});
 screen.querySelectorAll('[data-take]').forEach(b=>b.onclick=async()=>{await action('stash_take',{camp:camp.id,item:b.dataset.take,count:Number(b.dataset.n)});setTimeout(again,150);});
 if($('camp-abandon'))$('camp-abandon').onclick=async()=>{if(!confirm('Бросить лагерь? Постройки исчезнут, вещи из ящика останутся лежать.'))return;await action('camp_abandon',{camp:camp.id});closePanel();};
}
function foundCamp(){const p=state.me,house=R.houseAt(p.x,p.y,-6);
 modal('camp','<span class="eyebrow">НОВЫЙ ЛАГЕРЬ</span><h2>'+(house?'Поселиться в этом доме':'Разбить лагерь здесь')+'</h2>','<div class="modal-body"><p>'+(house?'Стены у дома уже есть, их хватит надолго. Поставь дверь — и чужие не войдут, пока не выломают её или стену.':'Нужна ровная площадка примерно 200 × 200 без дорог и воды. Лагерь придётся обнести частоколом из восьми секций с воротами.')+'</p><p class="small muted">Лагерь у тебя один, клан пользуется им вместе с тобой. Потом в нём строят костёр, спальник, ящик, верстак и сборник воды — из досок, гвоздей, ткани и металлолома из рюкзака.</p><button class="primary" id="camp-ok" style="width:100%;margin-top:14px">'+(house?'Поселиться':'Основать лагерь')+'</button></div>');
 $('camp-ok').onclick=async()=>{const r=await action('camp_found');if(r)setTimeout(()=>showCamp(myCamp()),200);};}
function nearPart(kind,r){return (state.camps||[]).some(c=>campCanUse(c)&&c.parts[kind]&&c.parts[kind].hp>0&&distance(c.parts[kind],state.me)<r);}
function showCraft(){if(!state)return;const me=state.me,fire=nearPart('fire',110)||Object.values(state.towns).some(t=>t.owner===me.faction&&Math.hypot(t.x+60-me.x,t.y+46-me.y)<120),bench=nearPart('bench',90);
 const groups=[['hand','В РУКАХ',true],['fire','У ОГНЯ'+(fire?'':' · подойди к костру'),fire],['bench','НА ВЕРСТАКЕ'+(bench?'':' · нужен верстак в лагере'),bench]];
 let h='<div class="modal-body"><p class="small muted">Рюкзак: '+slotsUsed(me.items)+' / '+cfg.backpacks[me.gear.backpack].slots+' мест. Материалы складываются: доски по 10, гвозди по 30, патроны по 20–40 в одно место.</p>';
 groups.forEach(([at,title,ok])=>{h+='<span class="eyebrow shop-eyebrow">'+title+'</span><div class="craft-grid">';
  cfg.recipes.filter(r=>r.at===at).forEach(r=>{const lvl=me.level>=(r.level||1),res=Object.keys(r.res||{}).every(k=>state.stock[k]>=r.res[k]),can=ok&&lvl&&res&&hasNeeds(r.needs);
   const what=r.makes?Object.keys(r.makes).map(k=>cfg.items[k].name+(r.makes[k]>1?' ×'+r.makes[k]:'')).join(', '):'надеть сразу';
   h+='<button class="decision" data-craft-id="'+r.id+'" '+(can?'':'disabled')+'><div><b>'+esc(r.name)+'</b><strong>'+(lvl?'':'ур. '+r.level)+'</strong></div><small>'+esc(what)+'</small><span class="decision-cost">'+needsHtml(r.needs)+(r.res?' '+costText(r.res):'')+'</span></button>';});
  h+='</div>';});
 modal('craft','<span class="eyebrow">РЕМЕСЛО</span><h2>Крафт</h2>',h+'</div>','wide');
 screen.querySelectorAll('[data-craft-id]').forEach(b=>b.onclick=async()=>{const r=await action('craft_item',{id:b.dataset.craftId});if(r)setTimeout(showCraft,150);});}
function showDiplomacy(){if(!state)return;const f=state.me.faction,tr=state.truce,now=state.time;
 let html='<div class="modal-body"><div class="town-stats"><div><b>'+Math.round(state.reputation)+'</b><span>твоя репутация</span></div><div><b>'+state.sides[f].towns+'</b><span>твоих поселений</span></div></div><p style="margin-top:16px">Каждый сам за себя. С любым игроком или кланом компьютера можно заключить перемирие на 10 минут: без стрельбы, захватов и набегов, с торговлей в их поселениях. Постоянный союз — это клан (O).</p><div class="side-list">';
 Object.keys(state.sides).filter(g=>g!==f).sort((a,b)=>state.sides[b].towns-state.sides[a].towns).forEach(g=>{const s=state.sides[g],until=tr.pairs[g]||0,incoming=tr.proposals.find(x=>x.from===g&&x.to===f),outgoing=tr.proposals.find(x=>x.from===f&&x.to===g),clan=state.clans[s.clan];
  html+='<div class="side-row"><span class="dot" style="background:'+s.color+'"></span><div><b>'+(clan?'['+esc(clan.tag)+'] ':'')+esc(s.name)+'</b><small>'+(s.ai?'клан компьютера':'игрок')+' · поселений: '+s.towns+'</small></div>';
  if(friendly(g))html+='<span class="chip">твой клан</span>';
  else if(until>now)html+='<button class="secondary" data-truce="truce_break" data-side="'+g+'">Мир ещё '+Math.ceil(until-now)+' с · разорвать</button>';
  else if(incoming)html+='<button class="primary" data-truce="truce_accept" data-side="'+g+'">Принять мир</button>';
  else html+='<button class="secondary" data-truce="truce_propose" data-side="'+g+'" '+(outgoing?'disabled':'')+'>'+(outgoing?'Ждём ответа…':'Предложить мир')+'</button>';
  html+='</div>';});
 html+='</div><p class="small muted" style="margin-top:16px">Разрыв перемирия — репутация −15. Набеги и сюжетные решения тоже меняют репутацию.</p></div>';
 modal('diplomacy','<span class="eyebrow">ДИПЛОМАТИЯ</span><h2>Соседи и соперники</h2>',html);
 screen.querySelectorAll('[data-truce]').forEach(b=>b.onclick=async()=>{await action(b.dataset.truce,{side:b.dataset.side});showDiplomacy();});
}
function showPeople(tab){if(!state)return;tab=tab||'trade';const me=state.me,f=me.faction,clan=myClan();
 let html='<div class="modal-body"><div class="tabs"><button class="tab '+(tab==='trade'?'on':'')+'" data-ptab="trade">'+icon('trade')+' Обмен</button><button class="tab '+(tab==='clan'?'on':'')+'" data-ptab="clan">'+icon('flag')+' Клан'+(state.invites.length?' · '+state.invites.length:'')+'</button></div>';
 if(tab==='trade'){
  const offers=state.offers||[];
  if(offers.length){html+='<span class="eyebrow shop-eyebrow">ПРЕДЛОЖЕНИЯ</span>';offers.forEach(o=>{const mine=o.from===me.id;html+='<div class="quest-card"><div class="section-label"><span>'+(mine?'ТЫ → '+esc(o.to_name):esc(o.from_name)+' → ТЕБЕ')+'</span><b>'+Math.max(0,Math.ceil(o.until-state.time))+' с</b></div><p>'+(mine?'Отдаёшь':'Отдаёт')+': <b>'+esc(o.give_text)+'</b><br>'+(mine?'Просишь':'Просит')+': <b>'+esc(o.want_text)+'</b></p><div class="town-buttons">'+(mine?'':'<button class="primary" data-offer="offer_accept" data-id="'+o.id+'">Согласиться</button>')+'<button class="secondary" data-offer="offer_cancel" data-id="'+o.id+'">'+(mine?'Отозвать':'Отказать')+'</button></div></div>';});}
  const near=state.players.filter(p=>p.id!==me.id&&p.hp>0&&distance(p,me)<260);
  html+='<span class="eyebrow shop-eyebrow">ИГРОКИ РЯДОМ</span>';
  if(!near.length)html+='<p class="small muted">Для обмена подойди к игроку вплотную (несколько шагов). Обмен честный: вещи переходят только после согласия второй стороны.</p>';
  else{const itemOpts=keys=>'<option value="">—</option>'+keys.map(k=>'<option value="'+k+'">'+esc(cfg.items[k].name)+'</option>').join(''),resOpts='<option value="">—</option>'+Object.keys(cfg.resources).map(k=>'<option value="'+k+'">'+esc(cfg.resources[k])+'</option>').join('');
   const side=(id,title,items)=>'<div class="offer-side"><b>'+title+'</b><label>Монеты<input type="number" min="0" id="'+id+'-coins" value="0"></label><label>Вещь<select id="'+id+'-item">'+itemOpts(items)+'</select></label><label>Сколько<input type="number" min="1" max="20" id="'+id+'-n" value="1"></label><label>Ресурс<select id="'+id+'-res">'+resOpts+'</select></label><label>Сколько<input type="number" min="1" id="'+id+'-rn" value="10"></label></div>';
   html+='<label class="setting">Кому<select id="offer-to">'+near.map(p=>'<option value="'+p.id+'">'+esc((p.tag?'['+p.tag+'] ':'')+p.name)+' · '+p.level+' ур.</option>').join('')+'</select></label><div class="offer-form">'+side('give','Отдаю',Object.keys(me.items))+side('want','Прошу',Object.keys(cfg.items))+'</div><button class="primary" id="offer-send" style="width:100%">'+icon('trade')+' Предложить обмен</button>';}
 }else{
  if(!clan){
   if(state.invites.length){html+='<span class="eyebrow shop-eyebrow">ПРИГЛАШЕНИЯ</span>';state.invites.forEach(cid=>{const c=state.clans[cid];if(!c)return;html+='<div class="side-row"><span class="dot" style="background:'+c.color+'"></span><div><b>['+esc(c.tag)+'] '+esc(c.name)+'</b><small>'+c.members.length+' чел. · глава '+esc(sideName(c.leader))+'</small></div><button class="primary" data-clan="clan_join" data-id="'+cid+'">Вступить</button><button class="quiet" data-clan="clan_decline" data-id="'+cid+'">Нет</button></div>';});}
   html+='<p style="margin-top:12px">Клан — до 6 игроков. Соклановцы не стреляют друг в друга, не захватывают поселения друг друга, их охрана вас не трогает, ворота лагеря пропускают, торговцы торгуют.</p><label class="setting">Название<input id="clan-name" maxlength="24" placeholder="Например: Северный ветер"></label><button class="primary" id="clan-create" style="width:100%" '+(me.coins<30?'disabled':'')+'>Основать клан · '+icon('coin')+' 30</button>';
  }else{
   const lead=clan.leader===f;
   html+='<div class="town-faction" style="color:'+clan.color+'">'+icon('flag')+' ['+esc(clan.tag)+'] '+esc(clan.name)+'</div><span class="eyebrow shop-eyebrow">СОСТАВ · '+clan.members.length+' / 6</span><div class="side-list">';
   clan.members.forEach(m=>{const s=state.sides[m];html+='<div class="side-row"><span class="dot" style="background:'+(s?s.color:'#888')+'"></span><div><b>'+esc(sideName(m))+(m===clan.leader?' · глава':'')+'</b><small>поселений: '+(s?s.towns:0)+'</small></div>'+(lead&&m!==f?'<button class="quiet danger" data-clan="clan_kick" data-side="'+m+'">Исключить</button>':'')+'</div>';});
   html+='</div>';
   if(lead){const free=state.players.filter(p=>p.faction!==f&&!(state.sides[p.faction]||{}).clan);html+='<span class="eyebrow shop-eyebrow">ПРИГЛАСИТЬ</span>'+(free.length?'<div class="side-list">'+free.map(p=>'<div class="side-row"><span class="dot" style="background:'+sideColor(p.faction)+'"></span><div><b>'+esc(p.name)+'</b><small>'+p.level+' ур. · '+Math.round(distance(p,me)/100)/10+' км</small></div><button class="secondary" data-clan="clan_invite" data-side="'+p.faction+'">Позвать</button></div>').join('')+'</div>':'<p class="small muted">Сейчас некого позвать: все игроки в кланах или не в сети.</p>');}
   html+='<button class="quiet danger" data-clan="clan_leave" style="width:100%;margin-top:14px">Выйти из клана</button>';
  }
 }
 html+='</div>';
 modal('people','<span class="eyebrow">ЛЮДИ</span><h2>Обмен и кланы</h2>',html);
 screen.querySelectorAll('[data-ptab]').forEach(b=>b.onclick=()=>showPeople(b.dataset.ptab));
 screen.querySelectorAll('[data-offer]').forEach(b=>b.onclick=async()=>{await action(b.dataset.offer,{id:b.dataset.id});showPeople('trade');});
 screen.querySelectorAll('[data-clan]').forEach(b=>b.onclick=async()=>{if(b.dataset.clan==='clan_leave'&&!confirm('Выйти из клана?'))return;await action(b.dataset.clan,{id:b.dataset.id,side:b.dataset.side});showPeople('clan');});
 if($('clan-create'))$('clan-create').onclick=async()=>{const r=await action('clan_create',{name:$('clan-name').value});if(r)showPeople('clan');};
 if($('offer-send'))$('offer-send').onclick=async()=>{const pack=id=>{const out={coins:Number($(id+'-coins').value)||0,items:{},res:{}};if($(id+'-item').value)out.items[$(id+'-item').value]=Number($(id+'-n').value)||1;if($(id+'-res').value)out.res[$(id+'-res').value]=Number($(id+'-rn').value)||1;return out;};
  const r=await action('offer_make',{to:$('offer-to').value,give:pack('give'),want:pack('want')});if(r)showPeople('trade');};
}
function confirmPost(){if(!state)return;const def=cfg.post;
 modal('post','<span class="eyebrow">КОНТРОЛЬ ТРАССЫ</span><h2>'+esc(def.name)+'</h2>','<div class="modal-body"><p>'+esc(def.desc)+'</p><p class="small muted">Ставится прямо на трассе, вдали от поселений и других постов. У стороны не больше трёх постов. Враги могут разрушить пост огнём.</p><span class="eyebrow">МАТЕРИАЛЫ</span><div class="costs">'+costHtml(cfg.post_cost)+'</div><button class="primary" id="post-ok" style="width:100%;margin-top:16px" '+(canPay(cfg.post_cost)?'':'disabled')+'>Поставить здесь</button></div>');
 $('post-ok').onclick=async()=>{const r=await action('post');if(r)closePanel();};}
function showMap(id){if(!state)return;modal('map','<span class="eyebrow">СХЕМАТИЧЕСКАЯ КАРТА РОССИИ</span><h2>Дороги нового мира</h2>',
 '<div class="map-body"><div class="map-view"><canvas id="big-map"></canvas><div class="map-legend"><span><i></i>Ты</span>'+Object.keys(state.sides).map(id=>'<span><i style="background:'+sideColor(id)+'"></i>'+esc(sideName(id))+(id===state.me.faction?' (ты)':'')+'</span>').join('')+'<span><i style="background:'+palette.neutral+'"></i>Под мародёрами</span><span><i class="square"></i>Лагеря</span><span><i class="diamond"></i>Заброшенные места</span></div><div class="map-zoom"><button class="secondary" id="zoom-in">+</button><button class="secondary" id="zoom-out">−</button><button class="secondary" id="zoom-me">Я</button></div></div><aside class="map-info" id="map-info"></aside></div>','map-modal');
 mapState.selected=id||currentTown&&currentTown.id;mapInfo(mapState.selected);
 const big=$('big-map');let drag=null;
 const toWorld=(e)=>{const box=big.getBoundingClientRect();if(!mapTr)return null;return{x:(e.clientX-box.left-mapTr.ox)/mapTr.scale,y:(e.clientY-box.top-mapTr.oy)/mapTr.scale};};
 const zoom=(k,at)=>{const z=clamp(mapState.zoom*k,1,32);if(at){mapState.fx=at.x;mapState.fy=at.y;}else if(mapState.fx==null){mapState.fx=state.me.x;mapState.fy=state.me.y;}mapState.zoom=z;if(z===1){mapState.fx=mapState.fy=null;}};
 big.onwheel=e=>{e.preventDefault();zoom(e.deltaY<0?1.35:1/1.35,e.deltaY<0?toWorld(e):null);};
 $('zoom-in').onclick=()=>zoom(1.5);$('zoom-out').onclick=()=>zoom(1/1.5);$('zoom-me').onclick=()=>{mapState.zoom=Math.max(10,mapState.zoom);mapState.fx=state.me.x;mapState.fy=state.me.y;};
 big.onmousedown=e=>{drag={x:e.clientX,y:e.clientY,fx:mapState.fx!=null?mapState.fx:cfg.width/2,fy:mapState.fy!=null?mapState.fy:cfg.height/2,moved:false};};
 big.onmousemove=e=>{if(!drag||!mapTr)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(Math.abs(dx)+Math.abs(dy)>4)drag.moved=true;if(drag.moved&&mapState.zoom>1){mapState.fx=drag.fx-dx/mapTr.scale;mapState.fy=drag.fy-dy/mapTr.scale;}};
 big.onmouseup=e=>{const moved=drag&&drag.moved;drag=null;if(moved)return;const p=toWorld(e);if(!p)return;
  const list=Object.values(state.towns).sort((a,b)=>distance(a,p)-distance(b,p)),poi=cfg.pois.slice().sort((a,b)=>distance(a,p)-distance(b,p))[0],pick=14/mapTr.scale;
  if(distance(list[0],p)<pick*1.4){mapState.selected=list[0].id;mapInfo(list[0].id);}else if(poi&&distance(poi,p)<pick){poiInfo(poi);}else{waypoint={x:clamp(p.x,0,cfg.width),y:clamp(p.y,0,cfg.height),name:'Отметка'};notify('Маршрут отмечен','Указатель появится в игровом мире.');}};
}
function mapInfo(id){const t=state.towns[id];if(!t)return;$('map-info').innerHTML='<span class="eyebrow">'+esc(t.region.toUpperCase())+'</span><h3>'+esc(t.name)+'</h3><p style="color:'+sideColor(t.owner)+'">'+(t.owner?sideName(t.owner):'Под мародёрами')+'</p>'+(cfg.landmarks[id]?'<p>★ '+esc(cfg.landmarks[id].name)+'</p>':'')+'<p>Восстановлено: '+Object.values(t.levels).filter(n=>n>0).length+' / '+Object.keys(t.levels).length+' зданий<br>Жители: '+t.population+'<br>Лояльность: '+Math.round(t.loyalty)+'%'+(t.guards?'<br>'+(t.owner?'Охрана':'Мародёры')+': '+t.guards:'')+(t.capture?'<br><b class="bad">Идёт захват</b>':'')+'</p><button class="primary" id="set-waypoint">Поставить маршрут '+icon('arrow')+'</button><button class="quiet" id="clear-waypoint">Убрать отметку</button><p class="map-note">Колесо мыши — масштаб, перетаскивание — сдвиг. Ромбы — заброшенные места с тайниками.</p><p class="map-note small">Расположение схематическое, расстояния сокращены. Это игровой мир, не навигационная карта.</p>';
 $('set-waypoint').onclick=()=>{waypoint=Object.assign({},t);closePanel();notify('Цель: '+t.name,'Следуй указателю.');};$('clear-waypoint').onclick=()=>{waypoint=null;mapInfo(id);};}
function poiInfo(p){const looted=state.loot[p.id];$('map-info').innerHTML='<span class="eyebrow">ЗАБРОШЕННОЕ МЕСТО</span><h3>'+esc(p.name)+'</h3><p>'+esc(p.kind_name)+'</p><p>Тайник: '+(looted?'обыскан, восстановится через '+Math.ceil(looted-state.time)+' сек.':'не тронут')+'<br>Возможная добыча: '+costText(cfg.poi_kinds[p.kind].loot)+'</p><p class="small muted">Мародёры собираются у таких мест. Подходи подготовленным.</p><button class="primary" id="set-waypoint">Поставить маршрут '+icon('arrow')+'</button>';
 $('set-waypoint').onclick=()=>{waypoint={x:p.x,y:p.y,name:p.name};closePanel();notify('Цель: '+p.name,'Следуй указателю.');};}

function interact(){if(!state||state.me.hp<=0)return;if(state.me.vehicle){notify(state.me.ride?'Ты пассажир':'Ты за рулём','Нажми F, чтобы выйти и взаимодействовать.');return;}
 if(!nearest){notify('Рядом нет цели','Подойди к человеку, ресурсу, зданию, тайнику или флагу на площади.');return;}
 const n=nearest;
 if(n.type==='giver')action('talk',{giver:n.obj.id}).then(r=>{if(r&&r.dialog)showDialog(r.dialog);});
 else if(n.type==='camp')showCamp(n.obj);
 else if(n.type==='fence')action('camp_break',{camp:n.obj.camp.id,slot:n.obj.slot});
 else if(n.type==='house')action('search_house',{id:n.obj.id});
 else if(n.type==='body')action('loot_body',{id:n.obj.id});
 else if(n.type==='building')showBuilding(n.obj);
 else if(n.type==='town')showTown(n.obj.id);
 else if(n.type==='poi')action('loot',{id:n.obj.id});
 else if(n.type==='drop')action('airdrop',{id:n.obj.id});
 else action('harvest',{id:n.obj.id});
}
const WEATHER_ICON={clear:'sun',rain:'rain',fog:'fog',storm:'storm',snow:'snow'};
// The panel in the bottom right: the weapon in hand, or the car when driving or riding along.
function gearHtml(p){const ride=rideOf(p);
 if(p.vehicle){const car=ride?ride.car:p.car,spec=cfg.cars[car.model]||cfg.cars[2],fuel=car.fuel||0;
  return '<div class="g-top"><span class="g-name">'+(ride?'ПАССАЖИР · ':'')+esc(spec.name.toUpperCase())+'</span>'+(ride?'<small>ведёт '+esc(ride.name)+'</small>':'<span class="g-keys"><kbd>F</kbd> выйти</span>')+'</div>'+
  '<div class="g-big"><b>'+kmh(car)+'</b><span>км/ч</span></div>'+
  '<div class="g-row" title="Топливо">'+icon('fuel')+'<div class="g-bar"><i style="width:'+Math.min(100,fuel/spec.tank*100)+'%"></i></div><small>'+Math.floor(fuel)+' / '+spec.tank+'</small></div>'+
  '<div class="g-row" title="Состояние">'+icon('tool')+'<div class="g-bar car"><i style="width:'+Math.round(car.hp)+'%"></i></div><small>'+Math.round(car.hp)+'%</small></div>';}
 const wd=cfg.weapons[p.gear.weapon],reserve=p.items[wd.ammo_item]||0,reloading=p.reload>state.time,ammoName=(cfg.items[wd.ammo_item]||{}).name||'';
 let html='<div class="g-top"><span class="g-name">'+esc(wd.name.toUpperCase())+'</span><span class="g-keys"><kbd>Q</kbd> <kbd>X</kbd></span></div>';
 if(reloading){const k=1-(p.reload-state.time)/(wd.reload||1);html+='<div class="g-big reload"><b>Перезарядка</b></div><div class="g-bar"><i style="width:'+Math.round(clamp(k,0,1)*100)+'%"></i></div>';}
 else html+='<div class="g-big'+(p.mag===0?' empty':'')+'"><b>'+p.mag+'</b><span>/ '+reserve+'</span><small>'+esc(ammoName.toLowerCase())+'</small></div>'+(wd.mag<=40?'<div class="pips">'+Array.from({length:wd.mag},(_,i)=>'<i'+(i<p.mag?'':' class="off"')+'></i>').join('')+'</div>':'<div class="g-bar"><i style="width:'+Math.round(p.mag/wd.mag*100)+'%"></i></div>');
 return html+'<div class="g-sub">'+icon('vest')+esc(cfg.armor[p.gear.armor].name)+'</div>';}
// One short line about the current work; the journal (J) has the rest.
function questLine(){const p=state.me,s=state.story,qs=p.quests;
 const ready=qs.find(q=>p.stats[q.kind]-q.start>=q.target);
 if(ready)return '<b>'+esc(ready.name)+'</b> · готово, сдай: '+esc(ready.from||'');
 if(s.chapter&&s.ready)return '<b>Глава '+(s.index+1)+'</b> · сдай радисту в крупном городе';
 if(qs.length){const q=qs[0];return '<b>'+esc(q.name)+'</b> · '+Math.min(q.target,Math.max(0,p.stats[q.kind]-q.start))+' / '+q.target+(qs.length>1?' · ещё '+(qs.length-1):'');}
 if(s.chapter)return '<b>Глава '+(s.index+1)+' · '+esc(s.chapter.title)+'</b> · '+s.progress[0]+' / '+s.progress[1];
 return 'Нет заданий · люди на площадях ждут (E)';}
function updateHud(){if(!state)return;const p=state.me,all=Object.values(state.towns);currentTown=all.slice().sort((a,b)=>distance(a,p)-distance(b,p))[0];
 const clan=myClan();document.querySelector('.brand>span').textContent=(clan?'['+clan.tag+'] ':'')+sideName(p.faction).toUpperCase()+' / РЕП. '+Math.round(state.reputation)+(Object.values(state.truce.pairs).some(u=>u>state.time)?' / ПЕРЕМИРИЕ':'');
 const near=Math.abs(currentTown.x-p.x)<(cfg.towns.find(t=>t.id===currentTown.id).r||480)+150&&Math.abs(currentTown.y-p.y)<(cfg.towns.find(t=>t.id===currentTown.id).h||420)+150,poi=cfg.pois.find(o=>distance(o,p)<420);
 const inHouse=R.houseAt(p.x,p.y,0),campHere=(state.camps||[]).find(c=>distance(c,p)<(c.house?60:CAMP_R)),shOwner=campHere&&campHere.owner;
 $('location-name').textContent=shOwner?'Лагерь · '+sideName(shOwner):inHouse?'Заброшенный дом · '+currentTown.name:near?currentTown.name:poi?poi.name:'Старая трасса';$('location-desc').textContent=near?currentTown.region+' · '+(currentTown.owner?sideName(currentTown.owner):'Под мародёрами')+(cfg.landmarks[currentTown.id]?' · ★ '+cfg.landmarks[currentTown.id].name:''):shOwner?(friendly(shOwner)?'Свой лагерь':'Чужой лагерь'):poi?poi.kind_name:'Россия · между поселениями';
 $('resources').innerHTML=Object.keys(cfg.resources).map(k=>'<div class="resource'+(state.stock[k]>=state.storage-1?' full':'')+'" title="Общий запас фракции: '+esc(cfg.resources[k])+' · предел '+state.storage+'">'+icon(k)+'<div><b>'+Math.floor(state.stock[k])+'</b><span>'+cfg.resources[k].toUpperCase()+'</span></div></div>').join('');
 const minutes=8*60+Math.floor(state.time*1.4),days=1+Math.floor(minutes/1440),hour=Math.floor(minutes/60)%24,w=state.weather.kind;
 $('clock').innerHTML=icon(hour>=6&&hour<20?WEATHER_ICON[w]:(w==='clear'?'moon':WEATHER_ICON[w]))+'<span>ДЕНЬ '+String(days).padStart(2,'0')+' / '+String(hour).padStart(2,'0')+':'+String(minutes%60).padStart(2,'0')+' · '+esc(cfg.weather_names[w].toUpperCase())+'</span>';
 const need=cfg.xp_table[p.level-1]||1,maxLv=p.level>=cfg.max_level,clanTag=clan?'['+clan.tag+'] ':'';
 $('me-name').textContent=clanTag+p.name;
 $('level').innerHTML='<b>'+p.level+'</b> ур.<i><em style="width:'+(maxLv?100:Math.round(p.xp/need*100))+'%"></em></i>';$('level').title=maxLv?'Максимальный уровень':'Опыт '+p.xp+' / '+need;
 const hpBar=document.querySelector('#me-panel .hbar.hp');hpBar.firstElementChild.style.width=Math.max(0,p.hp/p.max_hp*100)+'%';hpBar.lastElementChild.textContent=Math.ceil(Math.max(0,p.hp))+' / '+p.max_hp;hpBar.classList.toggle('low',p.hp<p.max_hp*.3);
 document.querySelector('#me-panel .hbar.st').firstElementChild.style.width=p.stamina+'%';
 const mi=$('me-icon'),im=AS.sprites.heroIcon(0,sideColor(p.faction));if(im&&mi.dataset.c!==sideColor(p.faction)){const c=mi.getContext('2d');c.clearRect(0,0,128,128);c.drawImage(im,4,4,120,120);mi.dataset.c=sideColor(p.faction);}
 $('vitals').innerHTML=vitalsHtml(false);
 $('coins').innerHTML='<span title="Монеты">'+icon('coin')+'<b>'+p.coins+'</b></span><span title="Рюкзак · I">'+icon('bag')+slotsUsed(p.items)+' / '+cfg.backpacks[p.gear.backpack].slots+'</span>';
 $('gear-panel').innerHTML=gearHtml(p);
 $('autosave').textContent=netFailures?'Соединение с ведущим потеряно':'Мир сохраняется у ведущего · игроков '+state.players.length+' / '+cfg.max_players;$('autosave').classList.toggle('bad',!!netFailures);
 $('quest-line').innerHTML=questLine();
 const ti=$('town-info');ti.classList.toggle('hidden',!near);
 if(near){const t=currentTown,n=Object.values(t.levels).filter(v=>v>0).length,cap=t.capture,total=Object.keys(t.levels).length,cons=Object.keys(t.construct||{}).length;
 ti.innerHTML='<div class="section-label"><span>'+(cap?'БОРЬБА ЗА ПЛОЩАДЬ':'СОСТОЯНИЕ ПОСЕЛЕНИЯ')+'</span><span style="color:'+sideColor(t.owner)+'">'+(t.owner===p.faction?'СВОЁ':t.owner&&friendly(t.owner)?'КЛАН':t.owner?'ЧУЖОЕ':'МАРОДЁРЫ')+'</span></div><div class="city-title">'+esc(t.name)+'</div><div class="town-stats"><div><b>'+n+'<small> / '+total+'</small></b><span>зданий</span></div><div><b>'+t.workers+'<small> / '+t.population+'</small></b><span>занятых жителей</span></div><div><b>'+Math.round(t.loyalty)+'<small>%</small></b><span>лояльность</span></div></div><div class="bar"><i style="width:'+(cap?clamp(cap.progress/30*100,0,100):n/total*100)+'%"></i></div><div class="town-hint">'+(!t.owner&&t.guards?'Площадь держат мародёры: '+t.guards+'. Перебей их, чтобы захватить':cap?(cap.contested?'Оспаривается — убери противников из круга':!cap.active?'Атакующие покинули круг':sideName(cap.faction)+' · '+Math.floor(Math.max(0,cap.progress))+' / 30 сек.'):(Object.keys(t.fires||{}).length?'🔥 Пожар! Потуши горящее здание (E)':cons?'Идёт стройка: '+cons+' · стой рядом, чтобы ускорить':'Площадь: флаг в центре · E'))+'</div>';
 }
 nearest=null;const candidates=[];
 if(!p.vehicle&&p.hp>0){cfg.givers.forEach(g=>{const d=distance(g,p);if(d<120)candidates.push({type:'giver',obj:g,d:d-40});});
 (state.camps||[]).forEach(c=>{if(Math.abs(c.x-p.x)>400||Math.abs(c.y-p.y)>400)return;
  Object.keys(c.parts).forEach(k=>{const pt=c.parts[k];if(pt.hp>0&&distance(pt,p)<55&&(campCanUse(c)||c.breached))candidates.push({type:'camp',obj:c,d:distance(pt,p)-10});});
  if(!campCanUse(c))Object.keys(c.fence).forEach(k=>{const f=c.fence[k];if(f.hp>0&&Math.abs(f.x-p.x)<f.w/2+40&&Math.abs(f.y-p.y)<f.h/2+40)candidates.push({type:'fence',obj:{camp:c,slot:k,piece:f},d:30});});
  if(campCanUse(c)&&distance(c,p)<(c.house?50:70))candidates.push({type:'camp',obj:c,d:distance(c,p)});});
 (state.bodies||[]).forEach(b=>{const d=distance(b,p);if(d<70)candidates.push({type:'body',obj:b,d:d-30});});
 {const h=R.houseAt(p.x,p.y,40);if(h&&!(state.camps||[]).some(c=>c.house===h.id))candidates.push({type:'house',obj:h,d:60});}
 cfg.buildings_world.forEach(b=>{const d=distance(b,p);if(d<155){const t=state.towns[b.town];candidates.push({type:'building',obj:b,d:d-25-(t.fires&&t.fires[b.kind]?60:0)});}});
 cfg.nodes.forEach(n=>{if(Math.abs(n.x-p.x)>80||Math.abs(n.y-p.y)>80)return;const d=distance(n,p);if(d<70&&!(state.harvested[n.id]>state.time))candidates.push({type:'node',obj:n,d});});
 cfg.pois.forEach(o=>{const d=distance(o,p);if(d<170&&!state.loot[o.id])candidates.push({type:'poi',obj:o,d:d-20});});
 (state.airdrops||[]).forEach(o=>{const d=distance(o,p);if(d<80)candidates.push({type:'drop',obj:o,d:d-40});});
 all.forEach(t=>{const d=distance(t,p);if(d<165)candidates.push({type:'town',obj:t,d:d+15});});candidates.sort((a,b)=>a.d-b.d);nearest=candidates[0]||null;}
 const hint=$('interaction');const carNear=p.car&&!p.vehicle&&distance(p,p.car)<=carSpec().len*.6+30&&!(p.car.wrecked_until>state.time),seat=!carNear&&rideNear(p),rider=rideOf(p);hint.classList.toggle('hidden',!nearest&&!p.vehicle&&!carNear&&!seat);
 if(rider)hint.innerHTML='<kbd>F</kbd> '+(kmh(rider.car)>18?'Машина едет — выйти можно на остановке':'Выйти из машины')+'<small>Ты пассажир. Ведёт '+esc(rider.name)+'</small>';
 else if(p.vehicle)hint.innerHTML='<kbd>F</kbd> '+(kmh(p.car)>18?'Останови машину, чтобы выйти':'Выйти из машины')+'<small>'+(p.car.fuel<1?'Бак пуст. Канистра — T, заправка — в своём поселении.':'W газ · S тормоз и назад · A/D руль · Shift ручник · бак '+Math.floor(p.car.fuel)+' / '+carTank())+'</small>';
 else if(nearest){const o=nearest.obj,t=nearest.type==='building'&&state.towns[o.town];let name=nearest.type==='giver'?'Поговорить: '+o.role.toLowerCase()+' '+o.name:nearest.type==='camp'?(campCanUse(o)?'Лагерь':'Чужой лагерь: ящик'):nearest.type==='fence'?'Ломать: '+(o.piece.kind==='gate'?'ворота':'стену'):nearest.type==='house'?'Обыскать дом':nearest.type==='body'?'Забрать: '+o.name:nearest.type==='building'?(t.fires&&t.fires[o.kind]?'Потушить: ':'')+cfg.buildings[o.kind].name:nearest.type==='town'?'Площадь · '+o.name:nearest.type==='poi'?'Обыскать тайник · '+o.name:nearest.type==='drop'?'Забрать сброшенный груз':'Собрать: '+cfg.resources[o.kind].toLowerCase();
  hint.innerHTML='<kbd>E</kbd>'+esc(name)+'<small>'+(nearest.type==='giver'?'Работа, слухи, награда за сделанное':nearest.type==='camp'?'Постройки, ящик · C — крафт':nearest.type==='fence'?'Прочность '+o.piece.hp+' / '+o.piece.max+'. Можно и стрелять':nearest.type==='house'?'Ткань, гвозди, доски, патроны… · L — поселиться здесь':nearest.type==='body'?(Object.keys(o.items).length+' видов вещей'+(o.coins?' и '+o.coins+' монет':'')):nearest.type==='building'?(o.kind==='workshop'&&t.owner===p.faction?'Стройка и снаряжение':o.kind==='garage'&&t.owner===p.faction?'Стройка и ремонт машины':'Восстановить или улучшить'):nearest.type==='town'?'События · торговля · управление · захват':nearest.type==='poi'?costText(cfg.poi_kinds[o.kind].loot).replace(/<[^>]+>/g,'')+' · охраняют мародёры':nearest.type==='drop'?'Металл, топливо, припасы':'+'+o.amount+' в запас фракции')+'</small>';}
 else if(!p.vehicle&&R.water(p.x,p.y,70))hint.innerHTML='<kbd>V</kbd> Попить из реки<small>Сырая вода может вызвать отравление</small>';
 else if(seat)hint.innerHTML='<kbd>F</kbd> '+(seat.free>0?'Сесть пассажиром':'Мест нет')+'<small>'+esc(seat.spec.name)+' · '+esc(seat.q.name)+' · свободно мест: '+Math.max(0,seat.free)+'</small>';
 else if(carNear)hint.innerHTML='<kbd>F</kbd> Сесть в машину<small>'+esc(carSpec().name)+' · '+Math.round(p.car.hp)+'% · бак '+Math.floor(p.car.fuel)+' / '+carTank()+(p.items.canister&&p.car.fuel<carTank()-1?' · T — залить канистру':'')+'</small>';
 if(p.hp<=0)hint.classList.remove('hidden'),hint.innerHTML='Ты без сознания<small>Очнёшься '+(myCamp()&&myCamp().parts.bed&&myCamp().parts.bed.hp>0?'в лагере':'у дороги')+' через '+Math.ceil(Math.max(0,p.dead_until-state.time))+' секунд</small>';
}

/* Smoothly follow server positions; walking phase drives the animation. */
function interpolate(list,store,dt){const seen={};list.forEach(p=>{seen[p.id]=1;let r=store[p.id];if(!r||distance(r,p)>500)r=store[p.id]={x:p.x,y:p.y,phase:Math.random()*6,ang:p.angle};
 const ox=r.x,oy=r.y;r.x+=(p.x-r.x)*Math.min(1,dt*14);r.y+=(p.y-r.y)*Math.min(1,dt*14);const sp=Math.hypot(r.x-ox,r.y-oy)/Math.max(dt,.001);r.sp=(r.sp||0)+(sp-(r.sp||0))*Math.min(1,dt*8);r.moving=r.sp>12;
 // Step rate follows the actual speed, so feet do not slide over the ground.
 r.phase+=dt*Math.min(10,2.4+r.sp*.034)*(r.moving?1:0);
 let da=(p.angle-r.ang+Math.PI)%(Math.PI*2);if(da<0)da+=Math.PI*2;r.ang+=(da-Math.PI)*Math.min(1,dt*12);});Object.keys(store).forEach(k=>{if(!seen[k])delete store[k];});}
let slowFrames=0,measured=0;
// Cold frosts the screen edges; bleeding pulses red.
function conditionOverlay(now){const me=state.me;
 // A short red edge when hit.
 if(lastHp!=null&&me.hp<lastHp-1)hurtFlash=1;lastHp=me.hp;
 if(hurtFlash>0){ctx.strokeStyle='rgba(150,25,20,'+(hurtFlash*.45)+')';ctx.lineWidth=26;ctx.strokeRect(0,0,cw,ch);hurtFlash=Math.max(0,hurtFlash-.06);}
 const cold=clamp((35-me.warmth)/35,0,1),blood=me.bleeding?.35+Math.sin(now/260)*.15:0,low=me.hp<me.max_hp*.3?.25:0;
 if(cold>0){const g=ctx.createRadialGradient(cw/2,ch/2,Math.min(cw,ch)*.3,cw/2,ch/2,Math.max(cw,ch)*.7);g.addColorStop(0,'rgba(200,225,240,0)');g.addColorStop(1,'rgba(200,225,240,'+(.55*cold)+')');ctx.fillStyle=g;ctx.fillRect(0,0,cw,ch);}
 if(blood+low>0){const g=ctx.createRadialGradient(cw/2,ch/2,Math.min(cw,ch)*.35,cw/2,ch/2,Math.max(cw,ch)*.72);g.addColorStop(0,'rgba(120,10,10,0)');g.addColorStop(1,'rgba(120,10,10,'+(blood+low)+')');ctx.fillStyle=g;ctx.fillRect(0,0,cw,ch);}}
function render(now){const raw=(now-last)/1000,dt=Math.min(raw,.05);last=now;frame++;
 // On a slow computer switch to economical graphics once, unless the player chose a mode.
 if(state&&!panel&&measured<240&&!readStorage('as-quality')){measured++;if(raw>.042)slowFrames++;if(measured===240&&slowFrames>140&&R.quality!=='low'){R.quality='low';resize();notify('Экономная графика','Компьютер не успевает за полной графикой. Вернуть можно в Esc → Настройки.');}}
 if(state){interpolate(state.players,drawPlayers,dt);interpolate(state.npcs||[],drawNpcs,dt);const me=drawPlayers[state.me.id];if(me){const look=state.me.vehicle?120:0;const tx=me.x+(state.me.vehicle?Math.cos(state.me.angle)*look:0),ty=me.y+(state.me.vehicle?Math.sin(state.me.angle)*look:0);cam.x+=(tx-cam.x)*Math.min(1,dt*6);cam.y+=(ty-cam.y)*Math.min(1,dt*6);}updateAim();}
 ctx.setTransform(dpr,0,0,dpr,0,0);
 if(camKick>0){cam.x-=aim.x*camKick;cam.y-=aim.y*camKick;camKick=Math.max(0,camKick-dt*14);}
 const view={talkTo:panel==='dialog'&&dialogGiver?dialogGiver.id:null,cam,cw,ch,zoom,state,drawPlayers,drawNpcs,nearest,panel,aim,now:now/1000,dt,dpr,waypoint,holdAim:holdMouse||keys.Space||now-lastAimAt<900,dark:0};
 if(cfg)R.draw(ctx,view);
 if(state)conditionOverlay(now);
 if(state&&waypoint&&!panel){const dx=waypoint.x-cam.x,dy=waypoint.y-cam.y,len=Math.hypot(dx,dy);if(len*zoom>Math.min(cw,ch)*.3){const angle=Math.atan2(dy,dx),r=Math.min(cw*.31,ch*.31),x=cw/2+Math.cos(angle)*r,y=ch/2+Math.sin(angle)*r;ctx.save();ctx.translate(x,y);ctx.rotate(angle);ctx.fillStyle='#e5b378';ctx.beginPath();ctx.moveTo(10,0);ctx.lineTo(-6,-6);ctx.lineTo(-3,0);ctx.lineTo(-6,6);ctx.fill();ctx.restore();R.pill(ctx,(waypoint.name||'Цель')+' · '+Math.round(len/100)/10+' км',x,y+23,'#ead6b4');}}
 if(state){SND.update(view);if(now-lastHud>180){updateHud();lastHud=now;}if(frame%3===0)R.drawMap($('minimap'),false,view,mapState);if(panel==='map'&&frame%3===0)mapTr=R.drawMap($('big-map'),true,view,mapState);if(holdMouse||keys.Space)shoot();}
 requestAnimationFrame(render);
}
async function boot(){try{cfg=await fetchJson('/api/config');R.init(cfg);showTitle();}catch(e){screen.innerHTML='<section class="modal"><div class="modal-body"><h2>Сначала запусти игру</h2><p style="margin-top:15px">Этот файл открывается через локальный сервер. Запусти «Играть.sh» из папки игры. На другом ПК открой адрес, который показывает ведущий.</p></div></section>';console.error(e);}}
boot();requestAnimationFrame(render);
})();
