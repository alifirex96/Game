/* After Silence. Local Canvas 2D client. The server owns every game outcome. */
(function () {
'use strict';
const $=id=>document.getElementById(id), canvas=$('world'), ctx=canvas.getContext('2d');
const screen=$('screen'), keys={}, pointer={x:0,y:0}, sprites=new Map();
let cfg=null, state=null, token='', connected=false, joining=false, busy=false, panel='title', selected=null;
let cw=innerWidth,ch=innerHeight,dpr=1,cam={x:7300,y:5200}, targetCam={x:7300,y:5200}, drawPlayers={};
let last=performance.now(), frame=0, netBusy=false, netFailures=0, latestStamp=0, lastMessage=0, lastHud=0;
let soundEnabled=true, audioCtx=null, aim={x:0,y:1}, nearest=null, currentTown=null, waypoint=null;
let requestSerial=0,lastShot=0,mapTransform=null,holdMouse=false,showedWarning=false;
const palette={survivors:'#91b6a4',bandits:'#d78e70',neutral:'#b7b69f'};
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
 check:'m4 12 5 5 11-11'};
function icon(name){return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="'+(pathIcons[name]||pathIcons.tool)+'"/></svg>';}
function esc(v){return String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function distance(a,b){return Math.hypot(a.x-b.x,a.y-b.y);}
function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
function readStorage(key){try{return localStorage.getItem(key)||'';}catch(e){return '';}}
function writeStorage(key,v){try{localStorage.setItem(key,v);}catch(e){}}
function noise(x,y){let n=Math.sin(x*127.1+y*311.7)*43758.5453123;return n-Math.floor(n);}
function rr(c,x,y,w,h,r){r=Math.min(r,w/2,h/2);c.beginPath();c.moveTo(x+r,y);c.arcTo(x+w,y,x+w,y+h,r);c.arcTo(x+w,y+h,x,y+h,r);c.arcTo(x,y+h,x,y,r);c.arcTo(x,y,x+w,y,r);c.closePath();}
function pill(c,text,x,y,color,bg){c.font='11px Segoe UI, Arial';const w=c.measureText(text).width+18;rr(c,x-w/2,y-10,w,21,4);c.fillStyle=bg||'#142019e8';c.fill();c.fillStyle=color||'#e3e3d4';c.textAlign='center';c.fillText(text,x,y+4);}
function notify(title,text,error){const div=document.createElement('div');div.className='toast'+(error?' error':'');div.innerHTML='<b>'+esc(title)+'</b>'+(text?'<p>'+esc(text)+'</p>':'');$('toast-stack').appendChild(div);while($('toast-stack').children.length>3)$('toast-stack').firstChild.remove();setTimeout(()=>div.remove(),5200);}
function beep(kind){if(!soundEnabled)return;try{if(!audioCtx)audioCtx=new(window.AudioContext||window.webkitAudioContext)();if(audioCtx.state==='suspended')audioCtx.resume();const o=audioCtx.createOscillator(),g=audioCtx.createGain();o.connect(g);g.connect(audioCtx.destination);o.type=kind==='shot'?'sawtooth':'sine';let now=audioCtx.currentTime;const f=kind==='shot'?110:kind==='error'?180:kind==='build'?520:740;o.frequency.setValueAtTime(f,now);o.frequency.exponentialRampToValueAtTime(kind==='shot'?45:f*1.4,now+.12);g.gain.setValueAtTime(kind==='shot'?.045:.035,now);g.gain.exponentialRampToValueAtTime(.001,now+.18);o.start();o.stop(now+.2);}catch(e){}}
function resize(){cw=innerWidth;ch=innerHeight;dpr=Math.min(devicePixelRatio||1,1.5);canvas.width=Math.round(cw*dpr);canvas.height=Math.round(ch*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);}
addEventListener('resize',resize);resize();
$('sound').innerHTML=icon('sound');$('full').innerHTML=icon('full');$('menu').innerHTML=icon('menu');
$('sound').onclick=()=>{soundEnabled=!soundEnabled;$('sound').innerHTML=icon(soundEnabled?'sound':'mute');beep('ui');};
$('full').onclick=()=>{if(document.fullscreenElement){if(document.exitFullscreen)document.exitFullscreen();}else if(document.documentElement.requestFullscreen)document.documentElement.requestFullscreen().catch(()=>{});};
$('menu').onclick=()=>showPause();$('minimap-wrap').onclick=()=>showMap();

async function fetchJson(path,body){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),4500);
 try{const options={headers:{'X-Session':token},signal:controller.signal,cache:'no-store'};
 if(body){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
 const response=await fetch(path,options);const data=await response.json();if(!response.ok){const e=new Error(data.error||'Ошибка соединения');e.status=response.status;throw e;}return data;
 }finally{clearTimeout(timer);}
}
function acceptState(s){if(!s||s.stamp<latestStamp)return;latestStamp=s.stamp;state=s;
 s.messages.forEach(m=>{if(m.id>lastMessage){if(lastMessage!==0)notify(m.title,m.text,m.tone==='error');lastMessage=m.id;}});
 if(s.load_warning&&!showedWarning){showedWarning=true;notify('Сохранение',s.load_warning,true);}
}
async function join(){if(joining||!cfg)return;joining=true;const btn=$('join');btn.disabled=true;btn.textContent='Подключение…';
 try{const name=$('player-name').value,faction=$('faction').value,code=$('room-code')?$('room-code').value:'';token=readStorage('as-faction-'+location.host)===faction?readStorage('as-token-'+location.host):'';
 const data=await fetchJson('/api/join',{name,faction,code,token});token=data.token;writeStorage('as-token-'+location.host,token);writeStorage('as-name',name);writeStorage('as-faction-'+location.host,data.state.me.faction);
 latestStamp=0;lastMessage=0;acceptState(data.state);connected=true;drawPlayers={};cam={x:state.me.x,y:state.me.y};closePanel();$('hud').classList.remove('hidden');
 notify('Экспедиция началась',cfg.factions[state.me.faction]+' · E — действие, F — машина, J — квесты.');beep('ui');
 }catch(e){notify('Не удалось войти',e.message,true);btn.disabled=false;btn.textContent='Войти в мир';}finally{joining=false;}}
async function action(op,args){if(busy&&op!=='shoot')return null;busy=true;
 try{const data=await fetchJson('/api/action',Object.assign({op,request_id:Date.now().toString(36)+'-'+(++requestSerial)+'-'+Math.random().toString(36).slice(2,8)},args||{}));acceptState(data.state);
 const r=data.result||{};if(!r.quiet&&!r.event){let info=r.text||'';if(r.chance!=null&&!/Бросок/.test(info))info+=' Шанс '+r.chance+'%, бросок '+r.roll+'.';notify(r.title||'Готово',info,r.success===false);beep(r.success===false?'error':op==='build'?'build':'ui');}return r;
 }catch(e){notify('Действие не выполнено',e.message,true);return null;}finally{busy=false;}}
async function network(){if(!connected||!state||netBusy)return;netBusy=true;
 try{const input=readInput();const data=await fetchJson('/api/action',{op:'input',x:input.x,y:input.y,sprint:input.sprint,ax:aim.x,ay:aim.y,paused:panel!==null});acceptState(data.state);netFailures=0;
 }catch(e){netFailures++;if(e.status===401){connected=false;state=null;latestStamp=0;showTitle();notify('Комната завершилась','Войди заново.',true);}else if(netFailures===2)notify('Нет связи с ведущим','Персонаж остановлен. Пробую восстановить соединение.',true);
 }finally{netBusy=false;}}
setInterval(network,100);
function readInput(){if(panel!==null)return{x:0,y:0,sprint:false};return{x:(keys.KeyD||keys.ArrowRight?1:0)-(keys.KeyA||keys.ArrowLeft?1:0),y:(keys.KeyS||keys.ArrowDown?1:0)-(keys.KeyW||keys.ArrowUp?1:0),sprint:!!(keys.ShiftLeft||keys.ShiftRight)};}
function clearKeys(){Object.keys(keys).forEach(k=>delete keys[k]);holdMouse=false;}
addEventListener('blur',clearKeys);document.addEventListener('visibilitychange',()=>{if(document.hidden){clearKeys();if(connected)showPause();}});
addEventListener('keydown',e=>{
 if(['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName))return;
 if(['Space','ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Tab'].includes(e.code))e.preventDefault();
 keys[e.code]=true;if(e.repeat)return;
 if(e.code==='Escape'){if(panel==='title')return;if(panel)closePanel();else showPause();}
 if(!connected)return;
 if(e.code==='KeyM'){if(panel==='map')closePanel();else showMap();}
 if(e.code==='KeyJ'){if(panel==='journal')closePanel();else showJournal();}
 if(panel)return;
 if(e.code==='KeyE')interact();
 if(e.code==='KeyF')action('vehicle');
 if(e.code==='Space')shoot();
});
addEventListener('keyup',e=>{keys[e.code]=false;});
canvas.addEventListener('mousemove',e=>{pointer.x=e.clientX;pointer.y=e.clientY;const p=drawPlayers[state&&state.me.id];if(p){const dx=e.clientX-(p.x-cam.x+cw/2),dy=e.clientY-(p.y-cam.y+ch/2),n=Math.hypot(dx,dy)||1;aim={x:dx/n,y:dy/n};}});
canvas.addEventListener('mousedown',e=>{if(e.button===0&&!panel){holdMouse=true;shoot();}});addEventListener('mouseup',()=>holdMouse=false);
function shoot(){if(!state||panel||state.me.vehicle||state.me.hp<=0)return;const now=performance.now();if(now-lastShot<490)return;lastShot=now;action('shoot').then(r=>{if(r)beep('shot');});}
function closePanel(){panel=null;selected=null;screen.className='';screen.innerHTML='';document.body.classList.remove('dialog-open');clearKeys();}
function modal(type,head,body,width){panel=type;document.body.classList.add('dialog-open');screen.className='';screen.innerHTML='<section class="modal '+(width||'')+'"><div class="modal-head"><div>'+head+'</div><button class="close" id="close-panel" aria-label="Закрыть">'+icon('close')+'</button></div>'+body+'</section>';$('close-panel').onclick=closePanel;clearKeys();}
function showTitle(){panel='title';document.body.classList.remove('dialog-open');$('hud').classList.add('hidden');screen.className='title-screen';
 const local=cfg&&cfg.join_code;
 screen.innerHTML='<div class="title-layout"><div class="overline">РОССИЯ ПОСЛЕ КАТАСТРОФЫ</div><h1>ПОСЛЕ<br><span>ТИШИНЫ</span></h1><p class="story">Дороги остались. Государства — нет.<br>Найди людей, верни жизнь поселениям<br>и реши, каким будет новый мир.</p><div class="lobby"><label>ПОЗЫВНОЙ<input id="player-name" maxlength="20" value="'+esc(readStorage('as-name')||'Каскад')+'"></label><label>СТОРОНА<select id="faction"><option value="survivors">Выжившие · помощь и договоры</option><option value="bandits">Бандиты · сила и контроль</option></select></label>'+(local?'':'<label>КОД КОМНАТЫ<input id="room-code" inputmode="numeric" maxlength="6" placeholder="6 цифр от ведущего"></label>')+'<button class="primary" id="join">Войти в мир '+icon('arrow')+'</button><button class="quiet" id="help-title">Как играть</button></div><div class="meta">ASTRA LINUX · ОДИНОЧНАЯ ИГРА И LAN 2 × 2<br>ВЕРСИЯ 0.1 · ИГРАБЕЛЬНЫЙ ПРОТОТИП</div></div><div class="title-footer">ВОССТАНОВИТЬ. ДОГОВОРИТЬСЯ. УДЕРЖАТЬ.</div>'+(local?'<div class="room-card"><span class="eyebrow">КОМНАТА НА ЭТОМ ПК</span><b>Код '+esc(local)+'</b><span>Другим игрокам: '+cfg.lan_addresses.map(esc).join('<br>')+'</span><small>Один компьютер хранит мир. До 2 игроков на сторону.</small></div>':'');
 $('faction').value=readStorage('as-faction-'+location.host)||'survivors';$('join').onclick=join;$('help-title').onclick=()=>showHelp(true);
}
function showPause(){if(!state)return;modal('pause','<span class="eyebrow">ЭКСПЕДИЦИЯ</span><h2>Передышка</h2>',
 '<div class="modal-body"><div class="menu-list"><button class="primary" id="resume">Продолжить '+icon('arrow')+'</button><button class="secondary" id="journal-menu">Журнал заданий</button><button class="secondary" id="map-menu">Карта России</button><button class="secondary" id="help-menu">Управление и правила</button></div><div class="notice">В сетевой игре мир продолжается, пока играет хотя бы один участник. Твой персонаж остаётся на месте. Автосохранение — на компьютере ведущего каждые 10 секунд.</div>'+(cfg.join_code?'<div class="room-inline"><b>Код комнаты: '+esc(cfg.join_code)+'</b><p>'+cfg.lan_addresses.map(esc).join('<br>')+'</p></div>':'')+'<p class="small muted" style="margin-top:15px">Закрой вкладку, чтобы выйти. Сессия на этой стороне сохраняется в браузере; не очищай его данные для продолжения тем же персонажем.</p></div>');
 $('resume').onclick=closePanel;$('journal-menu').onclick=showJournal;$('map-menu').onclick=showMap;$('help-menu').onclick=()=>showHelp(false);
}
function showHelp(fromTitle){modal('help','<span class="eyebrow">ПОЛЕВОЕ РУКОВОДСТВО</span><h2>Твой первый день</h2>',
 '<div class="modal-body"><div class="controls-grid"><span><kbd>W A S D</kbd> / <kbd>↑ ↓ ← →</kbd></span><span>Движение пешком и на машине</span><span><kbd>Shift</kbd></span><span>Бег; выносливость восстанавливается</span><span><kbd>E</kbd></span><span>Собрать ресурс, открыть здание или площадь</span><span><kbd>F</kbd></span><span>Сесть в свою машину / выйти рядом с ней</span><span><kbd>M</kbd> / <kbd>J</kbd></span><span>Карта / три коротких задания</span><span>Мышь + ЛКМ / <kbd>Space</kbd></span><span>Прицел и выстрел; союзники защищены</span><span><kbd>Esc</kbd></span><span>Меню или закрыть окно</span></div><p class="control-note">Начни с ресурсов рядом с убежищем, затем восстанови лесопилку и теплицу. Подходи к зданиям и нажимай E. Дома дают рабочих; если рабочих не хватает, часть производства простаивает.</p><p class="control-note" style="margin-top:12px">На площади поселения доступны события, доставка, помощь жителям и захват. У каждой рискованной попытки виден шанс. Бросок делает ведущий; неудача тратит указанные ресурсы.</p><p class="control-note" style="margin-top:12px">Для захвата успешно проведи переговоры, подкуп или штурм, затем стой пешком в круге 30 секунд. Противник в круге останавливает прогресс. После штурма лояльность ниже и одно восстановленное здание может пострадать.</p><p class="control-note" style="margin-top:12px">Цель партии: контролировать 5 поселений и улучшить радиостанцию своего убежища до уровня 2. После победы можно продолжать. География и расстояния условны.</p><div class="notice">Запасы общие у союзников. Производство работает каждые 12 секунд; нехватка еды снижает выпуск вдвое. Здоровье восстанавливается в своём убежище. После ранения тебя и машину возвращают домой.</div><button class="primary" id="help-back" style="width:100%;margin-top:20px">Понятно</button></div>');
 $('help-back').onclick=fromTitle?showTitle:closePanel;$('close-panel').onclick=fromTitle?showTitle:closePanel;
}
function costHtml(cost){return Object.keys(cost).map(k=>'<span class="cost '+(state.stock[k]>=cost[k]?'good':'bad')+'">'+icon(k)+'<b>'+cost[k]+'</b><em>/ '+Math.floor(state.stock[k])+'</em></span>').join('');}
function canPay(cost){return Object.keys(cost).every(k=>state.stock[k]>=cost[k]);}
function getBuildCost(t,k){const factor=[1,1.8,2.8][Math.min(t.levels[k],2)],base=cfg.buildings[k].cost,out={};Object.keys(base).forEach(k=>out[k]=Math.ceil(base[k]*factor));return out;}
function showBuilding(b){if(!state)return;const t=state.towns[b.town],def=cfg.buildings[b.kind],level=t.levels[b.kind],cost=getBuildCost(t,b.kind);
 const own=t.owner===state.me.faction,gate=b.kind==='depot'||level<t.levels.depot;
 const need=def.workers*(level+1),output=def.output;
 let reason=!own?'Поселение принадлежит другой стороне или нейтрально. Захвати площадь, чтобы строить.':t.capture?'Строительство приостановлено до окончания захвата.':!gate?'Для этого улучшения нужен опорный пункт следующего уровня.':level>=3?'Максимальный уровень.':!canPay(cost)?'Собери недостающие материалы или дождись производства.':'';
 modal('building','<span class="eyebrow">'+esc(t.name.toUpperCase())+' / '+(level?'УРОВЕНЬ '+level:'РУИНЫ')+'</span><h2>'+esc(def.name)+'</h2>',
 '<div class="modal-body"><canvas id="building-art" class="building-art" width="600" height="210"></canvas><p>'+esc(def.desc)+'</p><div class="building-stat-row"><span>Следующий уровень</span><b>'+Math.min(3,level+1)+' / 3</b></div><div class="building-stat-row"><span>'+(output?'Выпуск за 12 секунд':'Назначение')+'</span><b>'+(output?output[1]*(level+1)+' '+cfg.resources[output[0]].toLowerCase():b.kind==='house'?'+8 жителей':b.kind==='guard'?'+12 обороны':b.kind==='radio'?'+5% переговоров':'Открывает улучшения')+'</b></div>'+(need?'<div class="building-stat-row"><span>Требуется рабочих / свободно</span><b>'+need+' / '+(t.population-t.workers)+'</b></div>':'')+'<span class="eyebrow">МАТЕРИАЛЫ</span><div class="costs">'+costHtml(cost)+'</div>'+(reason?'<div class="notice">'+esc(reason)+'</div>':'')+'<div class="modal-actions"><button class="primary" id="build" '+((reason||level>=3)?'disabled':'')+'>'+(level?'Улучшить здание':'Восстановить')+icon('tool')+'</button></div></div>');
 selected=b.id;const a=$('building-art').getContext('2d');a.translate(300,120);a.scale(1.4,1.4);drawBuilding(a,Object.assign({},b,{x:0,y:0}),t,level||0,true);
 $('build').onclick=async()=>{const r=await action('build',{id:b.id});if(r)showBuilding(b);};
}
function showTown(id){if(!state)return;const t=state.towns[id],own=t.owner===state.me.faction,base=t.base,cap=t.capture;
 let html='<div class="modal-body"><div class="town-faction" style="color:'+palette[t.owner||'neutral']+'">'+icon('flag')+' '+(t.owner?cfg.factions[t.owner]:'Независимое поселение')+(base?' · убежище':'')+'</div><div class="town-stats" style="margin:18px 0"><div><b>'+Math.round(t.loyalty)+'%</b><span>лояльность</span></div><div><b>'+t.population+'</b><span>жители</span></div><div><b>'+t.levels.guard+'</b><span>укрепления</span></div></div>';
 if(cap)html+='<div class="notice"><b>'+cfg.factions[cap.faction]+' захватывают площадь</b><br>'+Math.max(0,Math.floor(cap.progress))+' / 30 сек. '+(cap.contested?'Присутствует противник — прогресс остановлен.':'Закрой окно и удерживай круг пешком.')+'</div>';
 if(own){html+='<div class="town-buttons"><button class="secondary" id="aid">Помочь жителям <span>8 припасов · +14 лояльности</span></button>'+(state.me.faction==='bandits'&&!base?'<button class="secondary" id="tax">Собрать дань <span>+12 металла и припасов · −18 лояльности</span></button>':'')+'</div>';}
 else if(!base&&!cap){
 html+='<p>Выбери способ установить контроль. После успеха нужно удержать площадь 30 секунд.</p><div class="capture-options">';
 const defs=[['talk','Переговоры','Больше лояльности, здания сохраняются',{food:12,wood:8}],['bribe','Подкуп','Дороже, но шанс обычно выше',{food:18,fuel:8}],['assault','Штурм','Ниже лояльность; ущерб зданию; при провале −25 здоровья',{metal:12,food:6}],['scout','Разведка','При успехе +20% на четыре минуты',{food:3}]];
 defs.forEach(d=>{html+='<button class="decision" data-method="'+d[0]+'" '+(!canPay(d[3])||t.shield>state.time?'disabled':'')+'><div><b>'+d[1]+'</b><strong>'+t.chances[d[0]]+'%</strong></div><small>'+d[2]+'</small><span class="decision-cost">'+Object.keys(d[3]).map(k=>icon(k)+' '+d[3][k]).join(' ')+'</span></button>';});html+='</div>';
 if(t.shield>state.time)html+='<div class="notice">Защита после захвата: ещё '+Math.ceil(t.shield-state.time)+' сек.</div>';
 }else if(base&&!own)html+='<div class="notice">Стартовое убежище защищено от захвата. Соперничайте за другие поселения.</div>';
 const delivery=state.me.quests.find(q=>q.kind==='deliver'&&q.town===id&&state.me.stats.deliver-q.start<q.target);
 html+='<div class="town-buttons"><button class="secondary" id="event" '+(!t.event_ready?'disabled':'')+'>Происшествие на площади <span>'+(t.event_ready?'Решение с шансом успеха':'Новое событие появится позже')+'</span></button>'+(delivery?'<button class="primary" id="deliver">Доставить 12 припасов</button>':'')+'</div></div>';
 modal('town','<span class="eyebrow">ПЛОЩАДЬ ПОСЕЛЕНИЯ</span><h2>'+esc(t.name)+'</h2>',html);
 selected=id;
 if($('aid'))$('aid').onclick=async()=>{await action('aid',{town:id});showTown(id);};
 if($('tax'))$('tax').onclick=async()=>{await action('tax',{town:id});showTown(id);};
 if($('deliver'))$('deliver').onclick=async()=>{await action('deliver',{town:id});showTown(id);};
 $('event').onclick=async()=>{const r=await action('event_open',{town:id});if(r&&r.event)showEvent(r.event);};
 screen.querySelectorAll('[data-method]').forEach(button=>button.onclick=async()=>{const method=button.dataset.method;const r=await action(method==='scout'?'scout':'capture',{town:id,method});if(r){if(r.success&&method!=='scout')closePanel();else showTown(id);}});
}
function showEvent(ev){let html='<div class="modal-body"><p>'+esc(ev.text)+'</p><div class="event-options">';
 ev.options.forEach((o,i)=>{html+='<button class="decision" data-choice="'+i+'" '+(!canPay(o.cost)?'disabled':'')+'><div><b>'+esc(o.name)+'</b><strong>'+o.chance+'%</strong></div><span class="decision-cost">'+(Object.keys(o.cost).length?Object.keys(o.cost).map(k=>icon(k)+' '+o.cost[k]).join(' '):'Без затрат')+'</span><small>Успех: '+esc(Object.keys(o.reward).map(k=>o.reward[k]+' '+cfg.resources[k].toLowerCase()).join(', ')||'помощь')+(o.heal?' · здоровье +'+o.heal:'')+(o.intel?' · разведка +'+o.intel+'%':'')+' · репутация '+(o.rep>0?'+':'')+o.rep+'</small><small>Неудача: затраты теряются'+(o.risk?', здоровье −'+o.risk:'.')+'</small></button>';});
 html+='</div><div class="notice">Один бросок от 1 до 100. Успех — если результат не больше шанса. Событие общее для фракции: союзник может завершить его первым.</div></div>';
 modal('event','<span class="eyebrow">НЕБОЛЬШАЯ ИСТОРИЯ</span><h2>'+esc(ev.name)+'</h2>',html);
 screen.querySelectorAll('[data-choice]').forEach(b=>b.onclick=async()=>{const r=await action('event_choice',{id:ev.id,choice:Number(b.dataset.choice)});if(r)closePanel();});
}
function showJournal(){if(!state)return;let html='<div class="modal-body"><p>Три поручения одновременно. За выполненное задание забери награду — появится новое.</p><div class="quests-list">';
 state.me.quests.forEach(q=>{const n=Math.max(0,state.me.stats[q.kind]-q.start),done=n>=q.target;
 html+='<div class="quest-card"><div class="section-label"><span>'+esc(q.kind==='capture'?'КОНТРОЛЬ':q.kind==='event'?'ПРОИСШЕСТВИЕ':'ПОРУЧЕНИЕ')+'</span><b class="'+(done?'good':'')+'">'+Math.min(n,q.target)+' / '+q.target+'</b></div><h3>'+esc(q.name)+'</h3><p>'+esc(q.text)+'</p><small>Награда: '+esc(Object.keys(q.reward).map(k=>q.reward[k]+' '+cfg.resources[k].toLowerCase()).join(', '))+'</small>'+(q.town?'<button class="quiet quest-waypoint" data-town="'+q.town+'">Отметить на карте</button>':'')+'<button class="'+(done?'primary':'secondary')+'" data-claim="'+q.id+'" '+(!done?'disabled':'')+'>'+(done?'Забрать награду':'В процессе')+'</button></div>';});
 html+='</div><div class="notice">Главная цель: 5 поселений под контролем и радиостанция уровня 2 в убежище. Выполнено поручений: '+state.me.completed+'.</div></div>';
 modal('journal','<span class="eyebrow">КАЖДЫЙ ДЕНЬ — НОВАЯ ЗАДАЧА</span><h2>Журнал экспедиции</h2>',html);
 screen.querySelectorAll('[data-claim]').forEach(b=>b.onclick=async()=>{await action('claim',{id:b.dataset.claim});showJournal();});
 screen.querySelectorAll('.quest-waypoint').forEach(b=>b.onclick=()=>{waypoint=Object.assign({},state.towns[b.dataset.town]);showMap(b.dataset.town);});
}
function showMap(id){if(!state)return;modal('map','<span class="eyebrow">СХЕМАТИЧЕСКАЯ КАРТА РОССИИ</span><h2>Дороги нового мира</h2>',
 '<div class="map-body"><div class="map-view"><canvas id="big-map"></canvas><div class="map-legend"><span><i></i>Твоя позиция</span><span><i></i>Выжившие</span><span><i style="background:#d78e70"></i>Бандиты</span><span><i></i>Нейтральные</span></div></div><aside class="map-info" id="map-info"></aside></div>','map-modal');
 selected=id||currentTown&&currentTown.id||cfg.bases[state.me.faction];mapInfo(selected);
 $('big-map').onclick=e=>{const box=$('big-map').getBoundingClientRect(),tr=mapTransform;if(!tr)return;const x=(e.clientX-box.left-tr.ox)/tr.scale,y=(e.clientY-box.top-tr.oy)/tr.scale;
 const list=Object.values(state.towns).sort((a,b)=>distance(a,{x,y})-distance(b,{x,y}));if(distance(list[0],{x,y})<700){selected=list[0].id;mapInfo(selected);}else{waypoint={x:clamp(x,0,cfg.width),y:clamp(y,0,cfg.height),name:'Отметка'};notify('Маршрут отмечен','Указатель появится в игровом мире.');}};
}
function mapInfo(id){const t=state.towns[id];if(!t)return;$('map-info').innerHTML='<span class="eyebrow">'+esc(t.region.toUpperCase())+'</span><h3>'+esc(t.name)+'</h3><p style="color:'+palette[t.owner||'neutral']+'">'+(t.owner?cfg.factions[t.owner]:'Независимое поселение')+'</p><p>Восстановлено: '+Object.values(t.levels).filter(n=>n>0).length+' / 9 зданий<br>Жители: '+t.population+'<br>Лояльность: '+Math.round(t.loyalty)+'%</p><button class="primary" id="set-waypoint">Поставить маршрут '+icon('arrow')+'</button><button class="quiet" id="clear-waypoint">Убрать отметку</button><p class="map-note">Перемещение свободное: закрой карту и отправляйся пешком или на машине. Карта показывает направление, а не переносит персонажа.</p><p class="map-note small">Расположение схематическое, расстояния сокращены. Это игровой мир, не навигационная карта.</p>';
 $('set-waypoint').onclick=()=>{waypoint=Object.assign({},t);closePanel();notify('Цель: '+t.name,'Следуй указателю.');};$('clear-waypoint').onclick=()=>{waypoint=null;mapInfo(id);};}

function interact(){if(!state||state.me.hp<=0)return;if(state.me.vehicle){notify('Ты за рулём','Нажми F, чтобы выйти и взаимодействовать.');return;}
 if(!nearest){notify('Рядом нет цели','Подойди к ресурсу, зданию или флагу на площади.');return;}
 if(nearest.type==='building')showBuilding(nearest.obj);
 else if(nearest.type==='town')showTown(nearest.obj.id);
 else action('harvest',{id:nearest.obj.id});
}
function updateHud(){if(!state)return;const p=state.me,all=Object.values(state.towns);currentTown=all.slice().sort((a,b)=>distance(a,p)-distance(b,p))[0];
 document.querySelector('.brand>span').textContent=cfg.factions[p.faction].toUpperCase()+' / РЕП. '+Math.round(state.reputation);
 const near=distance(currentTown,p)<740;
 $('location-name').textContent=near?currentTown.name:'Старая трасса';$('location-desc').textContent=near?currentTown.region+' · '+(currentTown.owner?cfg.factions[currentTown.owner]:'Независимое поселение'):'Россия · между поселениями';
 $('resources').innerHTML=Object.keys(cfg.resources).map(k=>'<div class="resource" title="Общий запас фракции: '+esc(cfg.resources[k])+'">'+icon(k)+'<div><b>'+Math.floor(state.stock[k])+'</b><span>'+cfg.resources[k].toUpperCase()+'</span></div></div>').join('');
 const minutes=8*60+Math.floor(state.time*1.4),days=1+Math.floor(minutes/1440);$('clock').textContent='ДЕНЬ '+String(days).padStart(2,'0')+' / '+String(Math.floor(minutes/60)%24).padStart(2,'0')+':'+String(minutes%60).padStart(2,'0');
 $('mode').innerHTML=icon(p.vehicle?'car':'walk')+'<span>'+(p.vehicle?'За рулём':'Пешком')+'</span><span class="hp">'+icon('heart')+Math.ceil(p.hp)+'</span>';
 $('stamina').firstElementChild.style.width=p.stamina+'%';$('autosave').textContent=netFailures?'Соединение с ведущим потеряно':'Мир сохраняется у ведущего · '+state.players.length+' / 4 игрока';
 const q=state.me.quests.find(q=>state.me.stats[q.kind]-q.start>=q.target)||state.me.quests[0],progress=Math.min(q.target,Math.max(0,p.stats[q.kind]-q.start));
 $('quest-title').textContent=q.name;$('quest-desc').textContent=q.text;$('quest-index').textContent='J';
 $('quest-progress').innerHTML='<div class="task '+(progress>=q.target?'done':'')+'"><i></i>'+progress+' / '+q.target+(progress>=q.target?' · Забери награду в журнале J':'')+'</div><div class="task"><i></i>Ещё 2 поручения · J</div>';
 const ti=$('town-info');ti.classList.toggle('hidden',!near);
 if(near){const t=currentTown,n=Object.values(t.levels).filter(v=>v>0).length,cap=t.capture;
 ti.innerHTML='<div class="section-label"><span>'+(cap?'БОРЬБА ЗА ПЛОЩАДЬ':'СОСТОЯНИЕ ПОСЕЛЕНИЯ')+'</span><span style="color:'+palette[t.owner||'neutral']+'">'+(t.owner===p.faction?'СВОЁ':t.owner?'ЧУЖОЕ':'НЕЙТРАЛЬНОЕ')+'</span></div><div class="city-title">'+esc(t.name)+'</div><div class="town-stats"><div><b>'+n+'<small> / 9</small></b><span>зданий</span></div><div><b>'+t.workers+'<small> / '+t.population+'</small></b><span>занятых жителей</span></div><div><b>'+Math.round(t.loyalty)+'<small>%</small></b><span>лояльность</span></div></div><div class="bar"><i style="width:'+(cap?clamp(cap.progress/30*100,0,100):n/9*100)+'%"></i></div><div class="town-hint">'+(cap?(cap.contested?'Оспаривается — убери противников из круга':!cap.active?'Атакующие покинули круг':cfg.factions[cap.faction]+' · '+Math.floor(Math.max(0,cap.progress))+' / 30 сек.'):'Площадь: флаг в центре · E')+'</div>';
 }
 nearest=null;const candidates=[];
 if(!p.vehicle&&p.hp>0){cfg.buildings_world.forEach(b=>{const d=distance(b,p);if(d<155)candidates.push({type:'building',obj:b,d:d-25});});
 cfg.nodes.forEach(n=>{const d=distance(n,p);if(d<70&&!(state.harvested[n.id]>state.time))candidates.push({type:'node',obj:n,d});});
 all.forEach(t=>{const d=distance(t,p);if(d<165)candidates.push({type:'town',obj:t,d:d+15});});candidates.sort((a,b)=>a.d-b.d);nearest=candidates[0]||null;}
 const hint=$('interaction');hint.classList.toggle('hidden',!nearest&&!p.vehicle&&distance(p,p.car)>85);
 if(p.vehicle)hint.innerHTML='<kbd>F</kbd> Выйти из машины<small>'+(state.stock.fuel<1?'Топливо закончилось. Собери канистры пешком.':'Топливо '+Math.floor(state.stock.fuel)+' · расход при движении')+'</small>';
 else if(nearest){let name=nearest.type==='building'?cfg.buildings[nearest.obj.kind].name:nearest.type==='town'?'Площадь · '+nearest.obj.name:'Собрать: '+cfg.resources[nearest.obj.kind].toLowerCase();hint.innerHTML='<kbd>E</kbd>'+esc(name)+'<small>'+(nearest.type==='building'?'Восстановить или улучшить':nearest.type==='town'?'События · управление · захват':'+'+nearest.obj.amount+' в запас фракции')+'</small>';}
 else if(distance(p,p.car)<=85)hint.innerHTML='<kbd>F</kbd> Сесть в машину<small>Твой внедорожник</small>';
 if(p.hp<=0)hint.classList.remove('hidden'),hint.innerHTML='Возвращение в убежище<small>'+Math.ceil(Math.max(0,p.dead_until-state.time))+' секунд</small>';
}

// Small, code-drawn sprites keep the game fully offline and inexpensive on older PCs.
function makeTexture(){const tile=document.createElement('canvas');tile.width=384;tile.height=384;const c=tile.getContext('2d');c.fillStyle='#404735';c.fillRect(0,0,384,384);
 for(let i=0;i<2300;i++){const x=noise(i,4)*384,y=noise(i,8)*384,n=noise(i,2);c.fillStyle=n<.5?'#b2b7860a':'#141c140c';c.fillRect(x,y,1+n*3,1+n*2);}return ctx.createPattern(tile,'repeat');}
let ground=makeTexture();
function treeSprite(seed){const key='tree'+seed;if(sprites.has(key))return sprites.get(key);const im=document.createElement('canvas');im.width=100;im.height=125;const c=im.getContext('2d');
 c.fillStyle='#141a143d';c.beginPath();c.ellipse(61,89,30,12,-.4,0,Math.PI*2);c.fill();c.fillStyle='#4c4130';c.fillRect(46,66,7,30);
 for(let j=0;j<4;j++){const yy=75-j*15,w=32-j*5;c.fillStyle=['#25382c','#2c4030','#354b34','#41543a'][j];c.beginPath();c.moveTo(50,yy-35);c.lineTo(50-w,yy+8);c.lineTo(50+w,yy+8);c.closePath();c.fill();c.fillStyle='#c2b4780d';c.beginPath();c.moveTo(50,yy-32);c.lineTo(50-w+3,yy+4);c.lineTo(50,yy);c.fill();}sprites.set(key,im);return im;}
function visible(x,y,r=150){return Math.abs(x-cam.x)<cw/2+r&&Math.abs(y-cam.y)<ch/2+r;}
function onRoad(x,y,width){if(!cfg)return false;return cfg.roads.some(edge=>{const a=cfg.towns.find(t=>t.id===edge[0]),b=cfg.towns.find(t=>t.id===edge[1]);const dx=b.x-a.x,dy=b.y-a.y,u=clamp(((x-a.x)*dx+(y-a.y)*dy)/(dx*dx+dy*dy),0,1);return Math.hypot(x-a.x-u*dx,y-a.y-u*dy)<width;});}
function drawRoads(c){if(!cfg)return;c.lineCap='round';cfg.roads.forEach(edge=>{const a=cfg.towns.find(t=>t.id===edge[0]),b=cfg.towns.find(t=>t.id===edge[1]);
 c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.strokeStyle='#76705a44';c.lineWidth=102;c.stroke();c.strokeStyle='#5c5b4a';c.lineWidth=76;c.stroke();c.strokeStyle='#77715a30';c.lineWidth=56;c.stroke();
 c.setLineDash([23,23]);c.strokeStyle='#c8ba8038';c.lineWidth=2;c.stroke();c.setLineDash([]);});
 cfg.towns.forEach(t=>{if(!visible(t.x,t.y,700))return;c.fillStyle='#5e5b4860';c.fillRect(t.x-460,t.y-400,920,800);c.strokeStyle='#81796155';c.lineWidth=62;c.beginPath();c.moveTo(t.x-440,t.y);c.lineTo(t.x+440,t.y);c.moveTo(t.x,t.y-390);c.lineTo(t.x,t.y+370);c.stroke();c.strokeStyle='#393e3060';c.lineWidth=2;c.strokeRect(t.x-460,t.y-400,920,800);});}
function drawNature(c){const size=125,x0=Math.floor((cam.x-cw/2-140)/size),x1=Math.ceil((cam.x+cw/2+140)/size),y0=Math.floor((cam.y-ch/2-140)/size),y1=Math.ceil((cam.y+ch/2+140)/size);
 const trees=[];for(let gy=y0;gy<=y1;gy++){for(let gx=x0;gx<=x1;gx++){const n=noise(gx,gy),x=gx*size+noise(gx+1,gy)*90,y=gy*size+noise(gx,gy+1)*90;
 const inTown=cfg&&cfg.towns.some(t=>Math.abs(x-t.x)<510&&Math.abs(y-t.y)<440);if(inTown||onRoad(x,y,75))continue;
 if(n<.54)trees.push({x,y,seed:Math.floor(n*8)});else{c.fillStyle='#9b9e6d22';c.fillRect(x,y,3,2);c.fillRect(x+8,y+3,2,3);if(n>.87){c.fillStyle='#292f2455';c.beginPath();c.ellipse(x,y,14,8,.3,0,7);c.fill();c.fillStyle='#70725a';c.beginPath();c.ellipse(x-2,y-3,10,6,.3,0,7);c.fill();}}}}
 trees.sort((a,b)=>a.y-b.y).forEach(t=>c.drawImage(treeSprite(t.seed),t.x-50,t.y-85));}
function drawBuilding(c,b,t,level,preview){const x=b.x,y=b.y,w=b.w,h=b.h,k=b.kind;const faction=t&&t.owner;const color=palette[faction||'neutral'];
 c.save();c.translate(x,y);c.fillStyle='#151b1555';c.beginPath();c.moveTo(-w/2+8,-h/2+15);c.lineTo(w/2+32,-h/2+34);c.lineTo(w/2+32,h/2+25);c.lineTo(-w/2+22,h/2+25);c.closePath();c.fill();
 if(k==='radio'){
 c.fillStyle=level?'#59645a':'#4c4c40';c.fillRect(-31,12,62,27);c.strokeStyle=level?'#adb6a0':'#686a59';c.lineWidth=4;c.beginPath();c.moveTo(-27,28);c.lineTo(0,-75);c.lineTo(27,28);c.moveTo(0,-75);c.lineTo(0,30);c.moveTo(-16,-20);c.lineTo(16,-20);c.moveTo(-22,2);c.lineTo(22,2);c.moveTo(-9,-45);c.lineTo(9,-45);c.stroke();c.fillStyle=level?'#d68b5b':'#5b5b45';c.beginPath();c.arc(0,-76,4,0,7);c.fill();if(level){c.strokeStyle='#a8c6ab88';c.lineWidth=1;c.beginPath();c.arc(0,-76,15+Math.sin(frame*.03)*3,-1,.8);c.stroke();}
 }else if(k==='guard'){
 c.fillStyle='#574a35';c.fillRect(-25,-18,8,55);c.fillRect(17,-18,8,55);c.strokeStyle='#ae9670';c.lineWidth=3;c.beginPath();c.moveTo(-24,0);c.lineTo(24,34);c.moveTo(24,0);c.lineTo(-24,34);c.stroke();c.fillStyle=level?'#7f7960':'#534c3d';c.fillRect(-35,-30,70,28);c.fillStyle=level?'#4f614e':'#484b38';c.beginPath();c.moveTo(-42,-31);c.lineTo(0,-51);c.lineTo(42,-31);c.fill();
 }else{
 c.fillStyle=level?'#a89d7f':'#797560';c.fillRect(-w/2,-h/2,w,h);c.fillStyle=level?'#5f6451':'#4b4e3d';c.fillRect(-w/2,h/2-12,w,17);
 let roof=level?(k==='house'?'#697563':k==='farm'?'#6e8a7b':k==='garage'?'#887554':k==='depot'?'#9b7859':'#6e7867'):'#5d604d';
 c.fillStyle=roof;c.beginPath();c.moveTo(-w/2-5,-h/2-7);c.lineTo(w/2+5,-h/2-7);c.lineTo(w/2+5,h/2-15);c.lineTo(-w/2-5,h/2-15);c.closePath();c.fill();
 c.fillStyle='#d5cba319';c.fillRect(-w/2,-h/2-4,w,20);c.strokeStyle=level?'#c3c1a52d':'#2b332b66';c.lineWidth=1;
 for(let sx=-w/2+8;sx<w/2;sx+=11){c.beginPath();c.moveTo(sx,-h/2-5);c.lineTo(sx,h/2-16);c.stroke();}
 c.fillStyle=level?'#e4b676':'#1d2921';c.fillRect(-w/2+12,h/2-7,14,6);c.fillRect(w/2-25,h/2-7,14,6);c.fillStyle='#303b2c';c.fillRect(-8,h/2-10,16,15);c.fillStyle='#a99d7c';c.fillRect(-11,h/2+4,22,5);
 if(!level){c.fillStyle='#202c24';c.beginPath();c.moveTo(-13,-h/2-5);c.lineTo(18,-h/2+9);c.lineTo(7,8);c.lineTo(-16,-1);c.lineTo(-26,-17);c.fill();c.strokeStyle='#a09b7d';c.lineWidth=3;c.beginPath();c.moveTo(-28,-3);c.lineTo(15,7);c.moveTo(-18,12);c.lineTo(-7,-25);c.stroke();c.fillStyle='#8a8267';for(let i=0;i<5;i++)c.fillRect(-w/2-9+i*23,h/2+10+noise(i,w)*13,11,5);}
 else{c.fillStyle=color;c.fillRect(-w/2+4,-h/2+2,5,16);if(level>=2){c.fillStyle='#32473d';c.fillRect(16,-h/2+2,30,17);c.strokeStyle='#94b0a033';c.strokeRect(16,-h/2+2,30,17);}if(level>=3){c.fillStyle='#b8ad88';c.fillRect(-42,-h/2-13,12,25);}}
 if(k==='sawmill'){for(let i=0;i<4;i++){c.fillStyle='#534b32';c.fillRect(-65+i*10,45,8,33);c.fillStyle='#b69a63';c.beginPath();c.ellipse(-61+i*10,76,4,3,0,0,7);c.fill();}}
 if(k==='quarry'){c.fillStyle='#96937a';for(let i=0;i<5;i++){c.beginPath();c.ellipse(-42+i*19,59-noise(i,6)*10,12,9,0,0,7);c.fill();}}
 if(k==='farm'){c.fillStyle=level?'#4a683b':'#514d37';for(let i=0;i<5;i++)c.fillRect(-45+i*20,53,13,29);c.strokeStyle='#b5b27c44';c.lineWidth=1;for(let i=0;i<4;i++){c.beginPath();c.moveTo(-50,57+i*7);c.lineTo(50,57+i*7);c.stroke();}}
 if(k==='garage'){c.fillStyle='#b08a51';for(let i=0;i<3;i++){c.fillRect(-55+i*19,50,14,21);c.fillStyle='#6a714e';}c.fillStyle='#303c30';c.fillRect(23,51,35,22);}
 }
 if(!preview&&visible(x,y,0))pill(c,cfg.buildings[k].name+(level?' · '+level:''),0,-h/2-22,level?'#dce1cf':'#c8c6b1');
 if(nearest&&nearest.type==='building'&&nearest.obj.id===b.id&&!panel){c.strokeStyle='#e7b273';c.lineWidth=1.5;c.setLineDash([5,5]);c.strokeRect(-w/2-9,-h/2-12,w+18,h+28);c.setLineDash([]);}
 c.restore();
}
function drawNode(c,n){if(state&&state.harvested[n.id]>state.time)return;if(!visible(n.x,n.y,80))return;c.save();c.translate(n.x,n.y);c.fillStyle='#14201855';c.beginPath();c.ellipse(5,10,22,10,0,0,7);c.fill();
 if(n.kind==='wood'){c.drawImage(treeSprite(1),-45,-83,90,112);c.fillStyle='#d8b776';c.fillRect(-3,12,6,4);}
 else if(n.kind==='stone'){c.fillStyle='#858878';c.beginPath();c.moveTo(-23,5);c.lineTo(-15,-15);c.lineTo(7,-22);c.lineTo(24,2);c.lineTo(15,13);c.lineTo(-18,12);c.fill();c.fillStyle='#a5a18a';c.beginPath();c.moveTo(-15,-15);c.lineTo(7,-22);c.lineTo(5,-4);c.lineTo(-16,0);c.fill();}
 else if(n.kind==='metal'){c.save();c.rotate(.15);c.fillStyle='#68796b';c.fillRect(-24,-15,48,30);c.fillStyle='#a4a48a';c.fillRect(-20,-15,12,8);c.fillStyle='#263a31';c.fillRect(2,-12,15,16);c.strokeStyle='#b9a77f';c.lineWidth=3;c.beginPath();c.moveTo(-20,12);c.lineTo(18,-15);c.stroke();c.restore();}
 else if(n.kind==='food'){c.fillStyle='#988562';c.fillRect(-19,-14,38,30);c.strokeStyle='#5b573f';c.lineWidth=3;c.strokeRect(-18,-13,36,28);c.beginPath();c.moveTo(-18,-12);c.lineTo(17,14);c.stroke();c.fillStyle='#b6b28a';c.fillRect(-5,-9,10,17);}
 else{c.fillStyle='#b59755';c.fillRect(-12,-18,24,34);c.fillStyle='#c9b477';c.fillRect(-8,-23,12,6);c.strokeStyle='#6c673f';c.lineWidth=2;c.beginPath();c.moveTo(-7,-11);c.lineTo(7,8);c.moveTo(7,-11);c.lineTo(-7,8);c.stroke();}
 if(nearest&&nearest.type==='node'&&nearest.obj.id===n.id){c.strokeStyle='#e7ae6b';c.lineWidth=1;c.beginPath();c.ellipse(0,12,29,16,0,0,7);c.stroke();}c.restore();}
function drawTown(c,t){const color=palette[t.owner||'neutral'];c.save();c.translate(t.x,t.y);c.fillStyle='#353e3055';c.beginPath();c.arc(0,0,110,0,7);c.fill();c.strokeStyle='#a69d7555';c.lineWidth=2;c.setLineDash([3,12]);c.beginPath();c.arc(0,0,110,0,7);c.stroke();c.setLineDash([]);
 if(t.capture){const cp=t.capture;c.fillStyle=palette[cp.faction]+'16';c.beginPath();c.arc(0,0,160,0,7);c.fill();c.strokeStyle=cp.contested?'#d58b68':palette[cp.faction];c.lineWidth=4;c.beginPath();c.arc(0,0,160,-Math.PI/2,-Math.PI/2+Math.PI*2*clamp(cp.progress/30,0,1));c.stroke();}
 c.fillStyle='#202e25';c.fillRect(-13,-12,26,23);c.strokeStyle='#b0ad8c';c.lineWidth=3;c.beginPath();c.moveTo(0,6);c.lineTo(0,-62);c.stroke();c.fillStyle=color;c.beginPath();c.moveTo(2,-59);c.lineTo(34,-54+Math.sin(frame*.04)*3);c.lineTo(31,-30);c.lineTo(2,-35);c.closePath();c.fill();pill(c,t.name.toUpperCase(),0,-100,color);pill(c,'E · ПЛОЩАДЬ',0,38,'#d9d6bb');
 if(t.event_ready){c.fillStyle='#c7b175';c.beginPath();c.arc(63,-39,12,0,7);c.fill();c.fillStyle='#253426';c.font='bold 15px Segoe UI';c.textAlign='center';c.fillText('?',63,-34);}c.restore();}
function drawCar(c,car,faction){c.save();c.translate(car.x,car.y);c.rotate(car.angle+Math.PI/2);c.fillStyle='#17201966';rr(c,-22,-29,45,68,8);c.fill();c.fillStyle='#1a2421';c.fillRect(-23,-21,8,17);c.fillRect(15,-21,8,17);c.fillRect(-23,17,8,17);c.fillRect(15,17,8,17);c.fillStyle=faction==='bandits'?'#8b5e44':'#8a9271';rr(c,-18,-35,36,70,5);c.fill();c.fillStyle='#b4b299';c.fillRect(-15,-33,30,4);c.fillStyle='#344c44';c.fillRect(-14,-20,28,14);c.fillStyle='#667c68';c.fillRect(-14,-16,28,4);c.fillStyle='#566951';c.fillRect(-14,0,28,24);c.strokeStyle='#a4ab8b';c.lineWidth=2;c.strokeRect(-13,1,26,21);c.fillStyle='#edd89c';c.fillRect(-15,-35,7,3);c.fillRect(8,-35,7,3);c.fillStyle='#a76b4c';c.fillRect(-15,33,6,3);c.fillRect(9,33,6,3);c.restore();}
function drawPerson(c,p,render){if(p.vehicle)return;c.save();c.translate(render.x,render.y);if(p.hp<=0){c.rotate(.7);c.globalAlpha=.6;}else c.rotate(Math.atan2(aim.y,aim.x)+(state&&p.id===state.me.id?Math.PI/2:0));
 if(!(state&&p.id===state.me.id)){c.rotate(p.angle+Math.PI/2-Math.atan2(aim.y,aim.x));}
 c.fillStyle='#101c1480';c.beginPath();c.ellipse(4,8,12,14,0,0,7);c.fill();c.fillStyle='#242c24';c.fillRect(-7,2,6,13);c.fillRect(2,2,6,13);c.fillStyle=palette[p.faction];rr(c,-10,-10,20,21,6);c.fill();c.fillStyle=p.faction==='bandits'?'#634c37':'#4e624c';c.fillRect(-8,5,16,10);c.fillStyle='#b39f7c';c.beginPath();c.arc(0,-10,7,0,7);c.fill();c.fillStyle='#566550';c.beginPath();c.arc(0,-12,7,Math.PI,Math.PI*2);c.fill();c.fillStyle='#3a4940';c.fillRect(8,-24,4,22);c.fillStyle='#ac9a77';c.fillRect(7,-7,6,6);c.restore();
 pill(c,p.name+(state&&p.id===state.me.id?' · ты':''),render.x,render.y-34,palette[p.faction]);if(p.hp<100){c.fillStyle='#18271f';c.fillRect(render.x-18,render.y+23,36,3);c.fillStyle='#c7a478';c.fillRect(render.x-18,render.y+23,36*p.hp/100,3);}}
function drawMap(canvas,big){if(!state||!canvas)return;const c=canvas.getContext('2d'),box=canvas.getBoundingClientRect();let w=big?box.width:250,h=big?box.height:160;if(canvas.width!==Math.round(w*dpr)||canvas.height!==Math.round(h*dpr)){canvas.width=Math.round(w*dpr);canvas.height=Math.round(h*dpr);}c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,w,h);c.fillStyle='#14221b';c.fillRect(0,0,w,h);
 let scale,ox,oy;if(big){scale=Math.min((w-45)/cfg.width,(h-65)/cfg.height);ox=(w-cfg.width*scale)/2;oy=(h-cfg.height*scale)/2;mapTransform={scale,ox,oy};}else{scale=.105;ox=w/2-state.me.x*scale;oy=h/2-state.me.y*scale;}
 c.strokeStyle='#a0af8a0f';c.lineWidth=1;for(let x=0;x<w;x+=35){c.beginPath();c.moveTo(x,0);c.lineTo(x,h);c.stroke();}for(let y=0;y<h;y+=35){c.beginPath();c.moveTo(0,y);c.lineTo(w,y);c.stroke();}
 c.save();c.translate(ox,oy);c.scale(scale,scale);c.lineWidth=big?1/scale:12;c.strokeStyle='#83916f50';cfg.roads.forEach(e=>{const a=state.towns[e[0]],b=state.towns[e[1]];c.beginPath();c.moveTo(a.x,a.y);c.lineTo(b.x,b.y);c.stroke();});c.restore();
 if(big){c.fillStyle='#8c9d7833';c.font='bold 12px Segoe UI';c.textAlign='center';[['ЕВРОПЕЙСКАЯ ЧАСТЬ',3500,800],['УРАЛ',7200,1700],['СИБИРЬ',12600,1800],['ДАЛЬНИЙ ВОСТОК',17200,950]].forEach(a=>c.fillText(a[0],ox+a[1]*scale,oy+a[2]*scale));}
 Object.values(state.towns).forEach(t=>{const x=ox+t.x*scale,y=oy+t.y*scale;if(x<0||x>w||y<0||y>h)return;const color=palette[t.owner||'neutral'];c.fillStyle=color;c.beginPath();c.arc(x,y,big?4:3,0,7);c.fill();if(big){c.fillStyle=selected===t.id?'#f0d09d':'#b8c1aa';c.font=(selected===t.id?'bold ':'')+'10px Segoe UI, Arial';c.textAlign='center';let dy= t.id==='shabrovsky'?16:t.id==='pervouralsk'?-11:t.id==='ekaterinburg'?16:-10;c.fillText(t.name,x,y+dy);}if(t.capture){c.strokeStyle='#e3ad74';c.beginPath();c.arc(x,y,7,0,7);c.stroke();}});
 state.players.forEach(p=>{const x=ox+p.x*scale,y=oy+p.y*scale;c.fillStyle=p.id===state.me.id?'#edaf6b':palette[p.faction];c.beginPath();c.arc(x,y,p.id===state.me.id?4:3,0,7);c.fill();if(p.id===state.me.id){c.strokeStyle='#eabf8a66';c.beginPath();c.arc(x,y,8,0,7);c.stroke();}});
 if(waypoint){const x=ox+waypoint.x*scale,y=oy+waypoint.y*scale;c.strokeStyle='#dfbb7c';c.lineWidth=1;c.setLineDash([4,4]);c.beginPath();c.moveTo(ox+state.me.x*scale,oy+state.me.y*scale);c.lineTo(x,y);c.stroke();c.setLineDash([]);c.strokeRect(x-6,y-6,12,12);}
}
function render(now){const dt=Math.min((now-last)/1000,.05);last=now;frame++;
 if(state){state.players.forEach(p=>{let r=drawPlayers[p.id];if(!r||distance(r,p)>500)r=drawPlayers[p.id]={x:p.x,y:p.y};r.x+=(p.x-r.x)*Math.min(1,dt*16);r.y+=(p.y-r.y)*Math.min(1,dt*16);});const me=drawPlayers[state.me.id];if(me){targetCam=me;cam.x+=(targetCam.x-cam.x)*Math.min(1,dt*7);cam.y+=(targetCam.y-cam.y)*Math.min(1,dt*7);}}
 ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,cw,ch);ctx.save();ctx.translate(cw/2-cam.x,ch/2-cam.y);ctx.fillStyle=ground;ctx.fillRect(cam.x-cw/2,cam.y-ch/2,cw,ch);
 if(cfg){drawRoads(ctx);drawNature(ctx);const towns=state?state.towns:null;
 cfg.nodes.forEach(n=>drawNode(ctx,n));
 cfg.towns.forEach(t=>{if(visible(t.x,t.y,200))drawTown(ctx,towns?towns[t.id]:Object.assign({},t,{owner:t.id==='shabrovsky'?'survivors':null,event_ready:true}));});
 const bs=cfg.buildings_world.filter(b=>visible(b.x,b.y,160)).sort((a,b)=>a.y-b.y);bs.forEach(b=>drawBuilding(ctx,b,towns?towns[b.town]:{owner:'survivors'},towns?towns[b.town].levels[b.kind]:['depot','house'].includes(b.kind)?1:0,false));
 if(state){state.players.forEach(p=>{const r=drawPlayers[p.id];const car=p.vehicle?{x:r.x,y:r.y,angle:p.car.angle}:p.car;if(visible(car.x,car.y))drawCar(ctx,car,p.faction);if(r&&visible(r.x,r.y))drawPerson(ctx,p,r);});
 state.effects.forEach(e=>{ctx.strokeStyle='#f5cf8dbb';ctx.lineWidth=1.7;ctx.beginPath();ctx.moveTo(e.x,e.y);ctx.lineTo(e.ex,e.ey);ctx.stroke();});
 }else{drawCar(ctx,{x:7390,y:5225,angle:-.4},'survivors');}
 }
 ctx.restore();
 if(state&&waypoint&&!panel){const dx=waypoint.x-cam.x,dy=waypoint.y-cam.y,len=Math.hypot(dx,dy);if(len>180){const angle=Math.atan2(dy,dx),r=Math.min(cw*.31,ch*.31),x=cw/2+Math.cos(angle)*r,y=ch/2+Math.sin(angle)*r;ctx.save();ctx.translate(x,y);ctx.rotate(angle);ctx.fillStyle='#e5b378';ctx.beginPath();ctx.moveTo(10,0);ctx.lineTo(-6,-6);ctx.lineTo(-3,0);ctx.lineTo(-6,6);ctx.fill();ctx.restore();pill(ctx,waypoint.name||'Цель',x,y+23,'#ead6b4');}}
 if(state){if(now-lastHud>180){updateHud();lastHud=now;}if(frame%3===0)drawMap($('minimap'),false);if(panel==='map'&&frame%4===0)drawMap($('big-map'),true);if(holdMouse||keys.Space)shoot();}
 requestAnimationFrame(render);
}
async function boot(){try{cfg=await fetchJson('/api/config');showTitle();}catch(e){screen.innerHTML='<section class="modal"><div class="modal-body"><h2>Сначала запусти игру</h2><p style="margin-top:15px">Этот файл открывается через локальный сервер. Запусти «Играть.sh» из папки игры. На другом ПК открой адрес, который показывает ведущий.</p></div></section>';}}
boot();requestAnimationFrame(render);
})();
