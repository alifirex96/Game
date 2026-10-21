/* After Silence. World renderer: cached terrain chunks, depth-sorted objects, light, weather, particles. */
(function () {
'use strict';
const AS = window.AS = window.AS || {};
const { hash, rng, strSeed, rr, mix, shade, canvas } = AS.util;
const S = AS.sprites, COL = AS.colors;
const CHUNK = 512, TOWN_HALF = [480, 420], BM = 100;   // world pixels per biome-map pixel
// Muted, washed-out ground: the world has been empty for years. Siberia lies under snow.
const BIOME = { mixed: '#4a5537', steppe: '#68654a', ural: '#46503b', taiga: '#3b4733', tundra: '#8b918a', snowtaiga: '#aab2b1' };
const TREES = {
  mixed: { d: .42, kinds: ['birch', 'birch', 'pine', 'spruce', 'bush', 'birch', 'autumn', 'bush'] },
  steppe: { d: .12, kinds: ['bush', 'bush', 'birch', 'dead', 'bush', 'autumn'] },
  ural: { d: .55, kinds: ['spruce', 'spruce', 'pine', 'pine', 'birch', 'spruce', 'bush'] },
  taiga: { d: .6, kinds: ['spruce', 'spruce', 'spruce', 'pine', 'spruce', 'dead', 'bush'] },
  tundra: { d: .1, kinds: ['snow', 'bush', 'dead', 'snow', 'bush'] },
  snowtaiga: { d: .55, kinds: ['snow', 'snow', 'snow', 'spruce', 'snow', 'dead', 'birch', 'snow'] },
};
const SNOWY = { tundra: 1, snowtaiga: 1 };
let cfg = null, towns = [], townById = {}, roads = [], waterSegs = [], lakes = [], pois = [], nodeGrid = new Map(), buildingGrid = new Map();
let biomeMap = null, worldMap = null;
const chunks = new Map(); let chunkQueue = 0;
const particles = []; const seenEffects = new Set(); let lightning = 0;
const townDecor = new Map();
const R = AS.render = { quality: 'high', onSound: null };
// Every player and clan has its own colour, sent by the host with the state.
let sides = {};
function col(id) { return (id && sides[id] && sides[id].color) || COL[id] || COL.neutral; }
R.col = col;

function segDist(px, py, ax, ay, bx, by) { const dx = bx - ax, dy = by - ay, l = dx * dx + dy * dy; const u = l ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l)) : 0; return Math.hypot(px - ax - u * dx, py - ay - u * dy); }
function inPoly(x, y, poly) { let inside = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside; } return inside; }
function inTown(x, y, pad) { pad = pad || 0; return towns.some(t => Math.abs(x - t.x) < TOWN_HALF[0] + pad && Math.abs(y - t.y) < TOWN_HALF[1] + pad); }
function onRoad(x, y, w) { return roads.some(r => segDist(x, y, r.ax, r.ay, r.bx, r.by) < w); }
function water(x, y, pad) { pad = pad || 0; if (inTown(x, y)) return false; for (const s of waterSegs) if (segDist(x, y, s[0], s[1], s[2], s[3]) < s[4] + pad) return true; for (const l of lakes) if (inPoly(x, y, l)) return true; return false; }
function nearShelter(x, y, pad) { return (cfg.shelters || []).some(s => Math.abs(x - s.x) < 180 + pad && Math.abs(y - s.y) < 130 + pad); }
R.water = water; R.onRoad = onRoad; R.inTown = inTown;
function nearestTown(x, y) { let best = null, bd = 1e18; for (const t of towns) { const d = (t.x - x) * (t.x - x) + (t.y - y) * (t.y - y); if (d < bd) { bd = d; best = t; } } return best; }
function biomeAt(x, y) { const t = nearestTown(x, y); let b = cfg.regions[t.region] ? cfg.regions[t.region].biome : 'mixed'; if (y < 1250 * (cfg.scale || 1) && b !== 'tundra') b = 'tundra'; return b; }
R.biomeAt = biomeAt;
R.coldAt = (x, y) => { const t = nearestTown(x, y); return (cfg.regions[t.region] || { cold: 0 }).cold + (y < 1300 * (cfg.scale || 1) ? 1 : 0); };

R.init = function (config) {
  cfg = config; towns = cfg.towns.map(t => Object.assign({}, t)); townById = {}; towns.forEach(t => townById[t.id] = t);
  // Highways come from the host and end at town gates, continuing as the town's cross streets.
  roads = cfg.road_lines.map(e => Object.assign({}, e, { len: Math.hypot(e.bx - e.ax, e.by - e.ay) }));
  waterSegs = []; cfg.rivers.forEach(r => { for (let i = 0; i < r[2].length - 1; i++) waterSegs.push([r[2][i][0], r[2][i][1], r[2][i + 1][0], r[2][i + 1][1], r[1] / 2, r[0]]); });
  lakes = cfg.lakes.map(l => l[1]); pois = cfg.pois || [];
  nodeGrid.clear(); cfg.nodes.forEach(n => { const k = Math.floor(n.x / 1000) + ',' + Math.floor(n.y / 1000); if (!nodeGrid.has(k)) nodeGrid.set(k, []); nodeGrid.get(k).push(n); });
  buildingGrid.clear(); cfg.buildings_world.forEach(b => { const k = b.town; if (!buildingGrid.has(k)) buildingGrid.set(k, []); buildingGrid.get(k).push(b); });
  makeBiomeMap(); makeWorldMap(); chunks.clear(); townDecor.clear();
};

function makeBiomeMap() {
  const scale = BM, w = cfg.width / scale, h = cfg.height / scale;
  biomeMap = canvas(w, h); const c = biomeMap.getContext('2d'); const img = c.createImageData(w, h);
  const hex = s => [parseInt(s.slice(1, 3), 16), parseInt(s.slice(3, 5), 16), parseInt(s.slice(5, 7), 16)];
  const cols = {}; Object.keys(BIOME).forEach(k => cols[k] = hex(BIOME[k]));
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const wx = x * scale, wy = y * scale;
    // Inverse-distance blend of every settlement's climate gives smooth transitions.
    let col = [0, 0, 0], wsum = 0;
    for (const t of towns) { const d2 = (t.x - wx) ** 2 + (t.y - wy) ** 2 + 1e4, wgt = 1 / (d2 * d2); const bc = cols[cfg.regions[t.region].biome]; col[0] += bc[0] * wgt; col[1] += bc[1] * wgt; col[2] += bc[2] * wgt; wsum += wgt; }
    col = col.map(v => v / wsum);
    const north = Math.max(0, Math.min(1, (1500 * (cfg.scale || 1) - wy) / (700 * (cfg.scale || 1)))); col = col.map((v, i) => v + (cols.tundra[i] - v) * north);
    for (const hl of cfg.hills) { const e = ((wx - hl[1]) / hl[3]) ** 2 + ((wy - hl[2]) / hl[4]) ** 2; if (e < 1) { const m = (1 - e) * .45; col = col.map((v, i) => v + ([104, 101, 88][i] - v) * m); } }
    const n = (hash(x, y) - .5) * 8; const o = (y * w + x) * 4; img.data[o] = col[0] + n; img.data[o + 1] = col[1] + n; img.data[o + 2] = col[2] + n; img.data[o + 3] = 255;
  }
  c.putImageData(img, 0, 0);
}

function makeWorldMap() {
  const w = 1200, h = 600, s = w / cfg.width; worldMap = canvas(w, h); const c = worldMap.getContext('2d');
  c.imageSmoothingEnabled = true; c.drawImage(biomeMap, 0, 0, w, h); c.fillStyle = '#0e171433'; c.fillRect(0, 0, w, h);
  c.lineJoin = c.lineCap = 'round';
  cfg.rivers.forEach(r => { c.strokeStyle = '#3f6670'; c.lineWidth = Math.max(1.4, r[1] * s * 1.6); c.beginPath(); r[2].forEach((p, i) => i ? c.lineTo(p[0] * s, p[1] * s) : c.moveTo(p[0] * s, p[1] * s)); c.stroke(); });
  lakes.forEach(l => { c.fillStyle = '#3f6670'; c.beginPath(); l.forEach((p, i) => i ? c.lineTo(p[0] * s, p[1] * s) : c.moveTo(p[0] * s, p[1] * s)); c.closePath(); c.fill(); });
  cfg.hills.forEach(hl => { c.fillStyle = '#8b8a7a'; for (let i = 0; i < 26; i++) { const a = hash(i, hl[1]) * 6.28, d = Math.sqrt(hash(hl[2], i)); const x = (hl[1] + Math.cos(a) * hl[3] * d) * s, y = (hl[2] + Math.sin(a) * hl[4] * d) * s; c.beginPath(); c.moveTo(x - 3, y + 2); c.lineTo(x, y - 3); c.lineTo(x + 3, y + 2); c.fill(); } });
  c.strokeStyle = '#d9cfa955'; c.lineWidth = 2.2; roads.forEach(r => { c.beginPath(); c.moveTo(r.ax * s, r.ay * s); c.lineTo(r.bx * s, r.by * s); c.stroke(); });
  c.strokeStyle = '#2a2b2499'; c.lineWidth = .8; roads.forEach(r => { c.setLineDash([3, 3]); c.beginPath(); c.moveTo(r.ax * s, r.ay * s); c.lineTo(r.bx * s, r.by * s); c.stroke(); }); c.setLineDash([]);
  c.font = 'bold 11px Segoe UI, Arial'; c.fillStyle = '#e3dcc433'; c.textAlign = 'center';
  const k = cfg.scale || 1;
  [['ЕВРОПЕЙСКАЯ ЧАСТЬ', 2600, 5600], ['УРАЛ', 6650, 5000], ['ЗАПАДНАЯ СИБИРЬ', 10300, 3000], ['ВОСТОЧНАЯ СИБИРЬ', 14400, 2000], ['ДАЛЬНИЙ ВОСТОК', 18300, 6800], ['СЕВЕР', 5600, 600]].forEach(a => c.fillText(a[0], a[1] * k * s, a[2] * k * s));
}

/* ---------- terrain chunks ---------- */
function getChunk(cx, cy) {
  const key = cx + ',' + cy; let ch = chunks.get(key);
  if (ch) { ch.used = performance.now(); return ch; }
  if (chunkQueue >= (R.quality === 'low' ? 1 : 2)) return null;
  chunkQueue++; ch = buildChunk(cx, cy); ch.used = performance.now(); chunks.set(key, ch);
  const limit = R.quality === 'low' ? 24 : 40;
  if (chunks.size > limit) { const old = [...chunks.entries()].sort((a, b) => a[1].used - b[1].used).slice(0, chunks.size - limit); old.forEach(o => chunks.delete(o[0])); }
  return ch;
}
function buildChunk(cx, cy) {
  const x0 = cx * CHUNK, y0 = cy * CHUNK, im = canvas(CHUNK, CHUNK), c = im.getContext('2d'), r = rng(hash(cx, cy) * .9 + .05);
  c.imageSmoothingEnabled = true;
  c.drawImage(biomeMap, x0 / BM - .5, y0 / BM - .5, CHUNK / BM + 1, CHUNK / BM + 1, -BM / 2, -BM / 2, CHUNK + BM, CHUNK + BM);
  c.translate(-x0, -y0);
  const biome = biomeAt(x0 + CHUNK / 2, y0 + CHUNK / 2);
  // Decorations come from a world-aligned grid, so neighbouring chunks paint the same shapes and no seams show.
  const grid = (cell, margin, fn) => { for (let gx = Math.floor((x0 - margin) / cell); gx <= Math.floor((x0 + CHUNK + margin) / cell); gx++) for (let gy = Math.floor((y0 - margin) / cell); gy <= Math.floor((y0 + CHUNK + margin) / cell); gy++) fn(gx * cell + hash(gx, gy * 1.3) * cell, gy * cell + hash(gy, gx * 1.7) * cell, hash(gx * 3.1, gy), hash(gx, gy * 2.9)); };
  grid(70, 60, (x, y, h1, h2) => { if (h1 > .55) return; c.fillStyle = h2 < .5 ? '#00000010' : '#ffffff09'; c.beginPath(); c.ellipse(x, y, 14 + h2 * 40, 8 + h1 * 30, h1 * 3, 0, 7); c.fill(); });
  grid(40, 30, (x, y, h1, h2) => {
    const b = biomeAt(x, y);
    if (SNOWY[b] && h1 < (b === 'snowtaiga' ? .6 : .35)) { c.fillStyle = h2 < .5 ? '#e3e9e755' : '#eef2f077'; c.beginPath(); c.ellipse(x, y, 6 + h2 * 18, 4 + h1 * 10, h2 * 3, 0, 7); c.fill(); }
    if ((b === 'ural' || b === 'tundra') && h2 > .9) { const sz = 2 + h1 * 6; c.fillStyle = '#00000033'; c.beginPath(); c.ellipse(x + 1, y + 1, sz, sz * .7, 0, 0, 7); c.fill(); c.fillStyle = '#86857a'; c.beginPath(); c.ellipse(x, y, sz, sz * .7, 0, 0, 7); c.fill(); c.fillStyle = '#a3a194'; c.beginPath(); c.ellipse(x - sz * .3, y - sz * .3, sz * .45, sz * .3, 0, 0, 7); c.fill(); }
    if ((b === 'mixed' || b === 'steppe') && h2 < .1) { c.fillStyle = ['#d8c96a', '#c9d2e0', '#c87a6a', '#e4e0d0'][Math.floor(h1 * 4)]; c.fillRect(x, y, 2, 2); c.fillRect(x + 4, y + 2, 2, 2); }
  });
  // Scars of the catastrophe: craters, burnt ground, rusted barrels and bones of machinery.
  grid(220, 60, (x, y, h1, h2) => {
    if (h1 > .16 || inTown(x, y, 120) || onRoad(x, y, 70) || water(x, y, 20) || nearShelter(x, y, 30)) return;
    if (h1 < .05) { const s = 14 + h2 * 22; c.fillStyle = '#2b2a2455'; c.beginPath(); c.ellipse(x, y, s * 1.5, s * 1.1, h2 * 3, 0, 7); c.fill(); c.fillStyle = '#1f1e1a'; c.beginPath(); c.ellipse(x, y, s, s * .7, h2 * 3, 0, 7); c.fill(); c.strokeStyle = '#6a6455'; c.lineWidth = 3; c.beginPath(); c.ellipse(x, y, s, s * .7, h2 * 3, 3.6, 6.4); c.stroke(); }
    else if (h1 < .1) { c.fillStyle = '#1c1b1733'; for (let k = 0; k < 5; k++) { c.beginPath(); c.ellipse(x + hash(k, x) * 50 - 25, y + hash(y, k) * 40 - 20, 18 + hash(k, y) * 26, 10 + hash(x, k) * 16, k, 0, 7); c.fill(); } }
    else if (h1 < .13) { for (let k = 0; k < 3; k++) { const bx = x + k * 13 - 13, by = y + (k % 2) * 8; c.fillStyle = '#00000033'; c.beginPath(); c.ellipse(bx + 3, by + 3, 7, 5, 0, 0, 7); c.fill(); c.fillStyle = ['#6a3d26', '#4d5446', '#7a5a2e'][k]; c.beginPath(); c.arc(bx, by, 6, 0, 7); c.fill(); c.strokeStyle = '#2a2520'; c.lineWidth = 1; c.beginPath(); c.arc(bx, by, 4, 0, 7); c.stroke(); } }
    else { c.save(); c.translate(x, y); c.rotate(h2 * 6); c.fillStyle = '#00000030'; c.fillRect(-14, -4, 34, 14); c.fillStyle = '#5c4334'; c.fillRect(-16, -6, 32, 12); c.fillStyle = '#7b5a3f'; c.fillRect(-16, -6, 32, 3); c.fillStyle = '#3d2f26'; c.fillRect(-10, -2, 6, 6); c.fillRect(4, -2, 6, 6); c.restore(); }
  });
  for (let i = 0; i < 520; i++) { const x = x0 + r() * CHUNK, y = y0 + r() * CHUNK, b = i % 8 ? biome : biomeAt(x, y); const tuft = b === 'steppe' ? ['#8d8550', '#7a7445', '#a39a5c'] : b === 'snowtaiga' ? ['#d7dddc', '#8e9690', '#c4cbca'] : b === 'tundra' ? ['#9aa08e', '#6f7a64', '#b9bfb2'] : ['#5d6e3f', '#4f6136', '#6c7d47']; c.fillStyle = tuft[i % 3]; c.fillRect(x, y, 1.5, 3 + r() * 3); c.fillRect(x + 2, y + 1, 1.2, 2 + r() * 3); }
  for (const hl of cfg.hills) { if (((x0 + 256 - hl[1]) / (hl[3] + 400)) ** 2 + ((y0 + 256 - hl[2]) / (hl[4] + 400)) ** 2 > 1) continue; grid(90, 40, (x, y, h1, h2) => { const e = ((x - hl[1]) / hl[3]) ** 2 + ((y - hl[2]) / hl[4]) ** 2; if (e > 1 || h1 > .45) return; const sz = 8 + h2 * 20; c.fillStyle = '#00000030'; c.beginPath(); c.moveTo(x - sz, y + sz * .5); c.lineTo(x, y - sz * .6); c.lineTo(x + sz * 1.2, y + sz * .5); c.fill(); c.fillStyle = '#7d7a6c'; c.beginPath(); c.moveTo(x - sz, y + sz * .4); c.lineTo(x - sz * .1, y - sz * .7); c.lineTo(x + sz * .8, y + sz * .3); c.fill(); c.fillStyle = '#9e9b8b'; c.beginPath(); c.moveTo(x - sz * .5, y); c.lineTo(x - sz * .1, y - sz * .7); c.lineTo(x + sz * .1, y - sz * .1); c.fill(); }); }
  // Fields around settlements on open plains.
  for (const t of towns) {
    if (Math.abs(t.x - x0 - 256) > 1600 || Math.abs(t.y - y0 - 256) > 1600) continue;
    const b = cfg.regions[t.region].biome; if (b === 'tundra' || b === 'taiga' || b === 'snowtaiga') continue;
    for (let k = 0; k < 4; k++) {
      const a = hash(k, t.x) * 6.28, d = 760 + hash(t.y, k) * 420, fx = t.x + Math.cos(a) * d, fy = t.y + Math.sin(a) * d;
      if (onRoad(fx, fy, 260) || water(fx, fy, 250) || inTown(fx, fy, 260)) continue;
      const fw = 300 + hash(k, 3) * 240, fh = 180 + hash(4, k) * 140;
      if (fx + fw / 2 < x0 || fx - fw / 2 > x0 + CHUNK || fy + fh / 2 < y0 || fy - fh / 2 > y0 + CHUNK) continue;
      c.save(); c.translate(fx, fy); c.rotate((hash(k, 9) - .5) * .5);
      const fc = ['#6b6236', '#5e6a36', '#776a3c', '#55603a'][k]; c.fillStyle = fc; c.fillRect(-fw / 2, -fh / 2, fw, fh);
      c.strokeStyle = shade(fc, -.18); c.lineWidth = 2; for (let i = -fh / 2 + 4; i < fh / 2; i += 7) { c.beginPath(); c.moveTo(-fw / 2, i); c.lineTo(fw / 2, i); c.stroke(); }
      c.strokeStyle = '#5a4a32'; c.lineWidth = 3; c.strokeRect(-fw / 2, -fh / 2, fw, fh);
      c.fillStyle = '#4f6136'; for (let i = 0; i < 30; i++) c.fillRect(-fw / 2 + hash(i, k) * fw, -fh / 2 + hash(k, i) * fh, 3, 3);
      c.restore();
    }
  }
  // Water: banks, depth and glints. Settlement embankments cut the water out.
  const box = [x0 - 200, y0 - 200, x0 + CHUNK + 200, y0 + CHUNK + 200];
  const hitSeg = s => !(Math.max(s[0], s[2]) + s[4] < box[0] || Math.min(s[0], s[2]) - s[4] > box[2] || Math.max(s[1], s[3]) + s[4] < box[1] || Math.min(s[1], s[3]) - s[4] > box[3]);
  const segs = waterSegs.filter(hitSeg), lks = lakes.filter(l => l.some(p => p[0] > box[0] - 900 && p[0] < box[2] + 900 && p[1] > box[1] - 900 && p[1] < box[3] + 900));
  const waterPts = [];
  if (segs.length || lks.length) {
    c.save(); c.beginPath(); c.rect(x0, y0, CHUNK, CHUNK); towns.forEach(t => c.rect(t.x + TOWN_HALF[0], t.y - TOWN_HALF[1], -TOWN_HALF[0] * 2, TOWN_HALF[1] * 2)); c.clip('evenodd');
    c.lineCap = c.lineJoin = 'round';
    const pass = (extra, color) => { c.strokeStyle = color; c.fillStyle = color; segs.forEach(s => { c.lineWidth = s[4] * 2 + extra; c.beginPath(); c.moveTo(s[0], s[1]); c.lineTo(s[2], s[3]); c.stroke(); }); lks.forEach(l => { c.lineWidth = extra; c.beginPath(); l.forEach((p, i) => i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1])); c.closePath(); c.fill(); if (extra > 0) c.stroke(); }); };
    pass(34, '#5b5a43'); pass(20, '#6d6a4f'); pass(8, '#2e464d'); pass(0, '#2f4b55');
    c.globalAlpha = .55; segs.forEach(s => { c.strokeStyle = '#3f6670'; c.lineWidth = s[4] * 1.1; c.beginPath(); c.moveTo(s[0], s[1]); c.lineTo(s[2], s[3]); c.stroke(); }); c.globalAlpha = 1;
    for (let i = 0; i < 160; i++) { const x = x0 + r() * CHUNK, y = y0 + r() * CHUNK; if (water(x, y, -6)) { if (waterPts.length < 50) waterPts.push([x, y, r()]); c.fillStyle = '#9fc0c522'; c.fillRect(x, y, 6 + r() * 10, 1.2); } }
    for (let i = 0; i < 40; i++) { const x = x0 + r() * CHUNK, y = y0 + r() * CHUNK; if (!water(x, y) && water(x, y, 22)) { c.fillStyle = ['#4f6a3c', '#62743f'][i % 2]; c.fillRect(x, y, 2, 6); c.fillRect(x + 2, y - 2, 1.5, 7); } }
    c.restore();
  }
  // Roads with shoulders, cracks, markings, potholes; bridges over water.
  const rs = roads.filter(rd => segDist(x0 + 256, y0 + 256, rd.ax, rd.ay, rd.bx, rd.by) < 500);
  c.lineCap = 'butt';
  rs.forEach(rd => { c.strokeStyle = '#6a644f'; c.lineWidth = 96; line(c, rd); c.strokeStyle = '#4f4f47'; c.lineWidth = 74; line(c, rd); c.strokeStyle = '#575750'; c.lineWidth = 62; line(c, rd); });
  rs.forEach(rd => {
    const ux = (rd.bx - rd.ax) / rd.len, uy = (rd.by - rd.ay) / rd.len, nx = -uy, ny = ux;
    const tc = (x0 + CHUNK / 2 - rd.ax) * ux + (y0 + CHUNK / 2 - rd.ay) * uy;
    const from = Math.max(0, tc - 560), to = Math.min(rd.len, tc + 560);
    for (let d = Math.floor(from / 40) * 40; d < to; d += 40) {
      const px = rd.ax + ux * d, py = rd.ay + uy * d, h1 = hash(d, rd.ax), h2 = hash(rd.ay, d);
      if (inTown(px, py, -30)) continue;
      if (water(px, py)) { // bridge deck
        c.fillStyle = '#7d7b72'; c.save(); c.translate(px, py); c.rotate(Math.atan2(uy, ux)); c.fillRect(-21, -46, 42, 92); c.fillStyle = '#5f5e57'; c.fillRect(-21, -38, 42, 76); c.fillStyle = '#9a978c'; c.fillRect(-21, -48, 42, 5); c.fillRect(-21, 43, 42, 5); c.fillStyle = '#3f3e3a'; for (let k = -18; k < 21; k += 10) { c.fillRect(k, -50, 3, 8); c.fillRect(k, 42, 3, 8); } c.fillStyle = '#00000040'; c.fillRect(-21, 48, 42, 10); c.restore();
        continue;
      }
      if (h1 < .45) { c.strokeStyle = '#3d3d38'; c.lineWidth = 1; c.beginPath(); const sx = px + nx * (h2 - .5) * 50, sy = py + ny * (h2 - .5) * 50; c.moveTo(sx, sy); c.lineTo(sx + ux * 14 + nx * 6, sy + uy * 14 + ny * 6); c.lineTo(sx + ux * 26 - nx * 4, sy + uy * 26 - ny * 4); c.stroke(); }
      if (h1 > .9) { c.fillStyle = '#3a3a35'; c.beginPath(); c.ellipse(px + nx * (h2 - .5) * 40, py + ny * (h2 - .5) * 40, 6 + h2 * 6, 4 + h2 * 3, 0, 0, 7); c.fill(); c.fillStyle = '#4b5b5e66'; c.beginPath(); c.ellipse(px + nx * (h2 - .5) * 40, py + ny * (h2 - .5) * 40, 4 + h2 * 4, 2 + h2 * 2, 0, 0, 7); c.fill(); }
      if (Math.floor(d / 40) % 2 === 0 && h2 > .25) { c.fillStyle = '#c8bf8c55'; c.save(); c.translate(px, py); c.rotate(Math.atan2(uy, ux)); c.fillRect(0, -1.2, 22, 2.4); c.restore(); }
      c.fillStyle = '#d6d0b52a'; c.save(); c.translate(px, py); c.rotate(Math.atan2(uy, ux)); c.fillRect(0, -29, 40, 1.5); c.fillRect(0, 28, 40, 1.5); c.restore();
      // Utility poles with sagging wires along the shoulder.
      if (Math.floor(d / 40) % 6 === 0) { const qx = px + nx * 58, qy = py + ny * 58; if (!water(qx, qy)) { c.fillStyle = '#00000040'; c.fillRect(qx + 3, qy + 2, 10, 3); c.fillStyle = '#5a4a38'; c.beginPath(); c.arc(qx, qy, 3.5, 0, 7); c.fill(); c.fillStyle = '#6e6a5e'; c.fillRect(qx - nx * 8 - 1, qy - ny * 8 - 1, nx * 16 + 2, ny * 16 + 2); } }
      if (Math.floor(d / 40) % 6 === 0) { c.strokeStyle = '#26262288'; c.lineWidth = .8; c.beginPath(); const qx = px + nx * 58, qy = py + ny * 58; c.moveTo(qx, qy); c.quadraticCurveTo(qx + ux * 120 + nx * 6, qy + uy * 120 + ny * 6, qx + ux * 240, qy + uy * 240); c.stroke(); }
      // Abandoned cars, stopped where the silence caught them.
      if (h1 > .94 && !water(px, py, 40)) { const v = S.vehicle(h2 < .2 ? 'bus' : 'wreck', ['#7c3b2f', '#56646d', '#8b7d55', '#3e4d40', '#b8b2a0', '#2d3a4f'][Math.floor(h2 * 6)], 2); c.save(); c.translate(px + nx * (h2 - .5) * 40, py + ny * (h2 - .5) * 40); c.rotate(Math.atan2(uy, ux) + (h1 - .98) * 30); c.drawImage(v.im, -v.ox, -v.oy); c.restore(); }
    }
  });
  // Trees: positions chosen here, painted later over characters (canopies are above people).
  const trees = []; const td = TREES[biome] || TREES.mixed;
  const step = 46;
  for (let gx = 0; gx < CHUNK; gx += step) for (let gy = 0; gy < CHUNK; gy += step) {
    const wx = x0 + gx + hash(gx + x0, gy) * step, wy = y0 + gy + hash(gy + y0, gx) * step;
    const tdl = TREES[biomeAt(wx, wy)] || td;
    const dens = tdl.d * (.4 + 1.2 * hash(Math.floor(wx / 700), Math.floor(wy / 700)));
    if (hash(wx, wy) > dens) continue;
    if (inTown(wx, wy, 60) || onRoad(wx, wy, 90) || water(wx, wy, 28) || nearShelter(wx, wy, 40)) continue;
    if (pois.some(p => Math.abs(p.x - wx) < 300 && Math.abs(p.y - wy) < 260)) continue;
    const kind = tdl.kinds[Math.floor(hash(wy, wx) * tdl.kinds.length)];
    trees.push({ x: wx, y: wy, kind, v: Math.floor(hash(wx * .3, wy) * 6) });
  }
  // Undergrowth and fallen logs stay in the chunk image.
  grid(128, 40, (x, y, h1, h2) => { if (h1 > .5 || inTown(x, y) || onRoad(x, y, 60) || water(x, y, 10) || nearShelter(x, y, 20)) return; if (h2 < .82) { const b = S.tree('bush', Math.floor(h2 * 6)); c.drawImage(b.im, x - b.ox, y - b.oy); } else { c.save(); c.translate(x, y); c.rotate(h1 * 6); c.fillStyle = '#00000033'; rr(c, -18, -2, 40, 9, 4); c.fill(); c.fillStyle = '#5e4a34'; rr(c, -20, -4, 40, 8, 4); c.fill(); c.fillStyle = '#a88c64'; c.beginPath(); c.ellipse(19, 0, 3, 4, 0, 0, 7); c.fill(); c.restore(); } });
  // Settlement ground: worn asphalt, sidewalks, the square's paving.
  towns.forEach(t => {
    if (Math.abs(t.x - x0 - 256) > 760 || Math.abs(t.y - y0 - 256) > 720) return;
    const hw = TOWN_HALF[0], hh = TOWN_HALF[1];
    c.fillStyle = '#58574b'; c.fillRect(t.x - hw, t.y - hh, hw * 2, hh * 2);
    const tr = rng(strSeed(t.id));
    for (let i = 0; i < 260; i++) { c.fillStyle = tr() < .5 ? '#00000014' : '#ffffff0a'; c.beginPath(); c.ellipse(t.x - hw + tr() * hw * 2, t.y - hh + tr() * hh * 2, 6 + tr() * 30, 4 + tr() * 18, tr() * 3, 0, 7); c.fill(); }
    for (let i = 0; i < 140; i++) { c.strokeStyle = '#3e3d36'; c.lineWidth = 1; c.beginPath(); const x = t.x - hw + tr() * hw * 2, y = t.y - hh + tr() * hh * 2; c.moveTo(x, y); c.lineTo(x + (tr() - .5) * 30, y + (tr() - .5) * 30); c.lineTo(x + (tr() - .5) * 40, y + (tr() - .5) * 40); c.stroke(); }
    c.fillStyle = '#4c4c45'; c.fillRect(t.x - hw, t.y - 34, hw * 2, 68); c.fillRect(t.x - 34, t.y - hh, 68, hh * 2);
    c.fillStyle = '#7d7a6c'; [[-hw, -40, hw * 2, 6], [-hw, 34, hw * 2, 6], [-40, -hh, 6, hh * 2], [34, -hh, 6, hh * 2]].forEach(a => c.fillRect(t.x + a[0], t.y + a[1], a[2], a[3]));
    c.fillStyle = '#c8bf8c44'; for (let i = -hw; i < hw; i += 40) c.fillRect(t.x + i, t.y - 1, 20, 2); for (let i = -hh; i < hh; i += 40) c.fillRect(t.x - 1, t.y + i, 2, 20);
    c.fillStyle = '#6e6b5e'; c.beginPath(); c.arc(t.x, t.y, 122, 0, 7); c.fill();
    c.strokeStyle = '#5d5a4f'; c.lineWidth = 1; for (let k = 20; k < 122; k += 14) { c.beginPath(); c.arc(t.x, t.y, k, 0, 7); c.stroke(); } for (let a = 0; a < 6.28; a += .26) { c.beginPath(); c.moveTo(t.x + Math.cos(a) * 20, t.y + Math.sin(a) * 20); c.lineTo(t.x + Math.cos(a) * 122, t.y + Math.sin(a) * 122); c.stroke(); }
    c.strokeStyle = '#8b8778'; c.lineWidth = 4; c.beginPath(); c.arc(t.x, t.y, 122, 0, 7); c.stroke();
    // Lawns in the corners of the blocks.
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach((q, i) => { c.fillStyle = '#4e5c37'; rr(c, t.x + q[0] * 70 - (q[0] < 0 ? 56 : 0), t.y + q[1] * 70 - (q[1] < 0 ? 40 : 0), 56, 40, 6); c.fill(); });
  });
  // Shelters: a concrete yard behind a fence of barbed wire.
  (cfg.shelters || []).forEach(sh => { if (Math.abs(sh.x - x0 - 256) > 700 || Math.abs(sh.y - y0 - 256) > 700) return; const pr = rng(strSeed(sh.id));
    c.fillStyle = '#5d5c55'; rr(c, sh.x - 170, sh.y - 120, 340, 250, 10); c.fill();
    for (let i = 0; i < 40; i++) { c.fillStyle = pr() < .5 ? '#00000018' : '#ffffff0c'; c.beginPath(); c.ellipse(sh.x - 160 + pr() * 320, sh.y - 110 + pr() * 230, 8 + pr() * 20, 4 + pr() * 10, 0, 0, 7); c.fill(); }
    c.fillStyle = '#4b4a44'; c.fillRect(sh.x - 22, sh.y + 20, 44, 110);
    c.strokeStyle = '#6f6a5c'; c.lineWidth = 2; c.strokeRect(sh.x - 176, sh.y - 126, 352, 262);
    c.strokeStyle = '#3a3a35'; c.lineWidth = 1; for (let i = -176; i < 176; i += 9) { c.beginPath(); c.moveTo(sh.x + i, sh.y - 129); c.lineTo(sh.x + i + 5, sh.y - 123); c.stroke(); c.beginPath(); c.moveTo(sh.x + i, sh.y + 133); c.lineTo(sh.x + i + 5, sh.y + 139); c.stroke(); } });
  // Ruins of places of interest get a cracked yard.
  pois.forEach(p => { if (Math.abs(p.x - x0 - 256) > 600 || Math.abs(p.y - y0 - 256) > 600) return; const pr = rng(strSeed(p.id)); c.fillStyle = '#5e5b4d'; rr(c, p.x - 230, p.y - 170, 460, 340, 30); c.fill(); for (let i = 0; i < 60; i++) { c.fillStyle = pr() < .5 ? '#00000018' : '#4f603a88'; c.beginPath(); c.ellipse(p.x - 230 + pr() * 460, p.y - 170 + pr() * 340, 6 + pr() * 22, 4 + pr() * 12, 0, 0, 7); c.fill(); } c.strokeStyle = '#6d6252'; c.lineWidth = 2; c.setLineDash([6, 4]); c.strokeRect(p.x - 236, p.y - 176, 472, 352); c.setLineDash([]); });
  return { im, trees, waterPts };
}
function line(c, rd) { c.beginPath(); c.moveTo(rd.ax, rd.ay); c.lineTo(rd.bx, rd.by); c.stroke(); }

/* ---------- settlement dressing that follows development ---------- */
function townLevel(t) { return Object.values(t.levels).reduce((a, b) => a + b, 0); }
function decor(t) {
  const dev = Math.min(3, Math.floor(townLevel(t) / 7)), key = t.id + dev + (t.owner || 'n');
  let d = townDecor.get(key); if (d) return d;
  const im = canvas(1000, 900), c = im.getContext('2d'); c.translate(500, 450); const r = rng(strSeed(t.id) + dev * .1);
  const lmk = cfg.landmarks[t.id];
  const avoid = (x, y) => Math.hypot(x, y) < 140 || (lmk && Math.abs(x - lmk.x) < lmk.w / 2 + 30 && Math.abs(y - lmk.y) < lmk.h / 2 + 40) || Math.abs(x) < 42 || Math.abs(y) < 42 || (cfg.buildings_world.some(b => b.town === t.id && Math.abs(b.x - t.x - x) < b.w / 2 + 26 && Math.abs(b.y - t.y - y) < b.h / 2 + 40));
  const spots = n => { const out = []; for (let i = 0; i < n * 6 && out.length < n; i++) { const x = (r() - .5) * 900, y = (r() - .5) * 800; if (!avoid(x, y)) out.push([x, y]); } return out; };
  // Debris shrinks as the town is rebuilt; lamps, benches and gardens appear.
  spots([26, 16, 8, 3][dev]).forEach(p => { for (let i = 0; i < 6; i++) { const s = 3 + r() * 6; c.fillStyle = ['#7a7466', '#8d8676', '#5f5a50', '#6d5444'][i % 4]; c.beginPath(); c.ellipse(p[0] + (r() - .5) * 30, p[1] + (r() - .5) * 20, s, s * .7, r(), 0, 7); c.fill(); } });
  spots([10, 6, 2, 0][dev]).forEach(p => { c.fillStyle = '#2d2b26'; c.beginPath(); c.ellipse(p[0], p[1], 9, 6, 0, 0, 7); c.fill(); c.fillStyle = '#5e5a4c'; c.fillRect(p[0] - 6, p[1] - 3, 4, 3); c.fillStyle = '#a69e8a'; c.fillRect(p[0] + 2, p[1] - 1, 3, 2); });
  spots([4, 3, 1, 0][dev]).forEach(p => { const v = S.vehicle('wreck', ['#7c3b2f', '#56646d', '#8b7d55', '#3e4d40'][Math.floor(r() * 4)], 2); c.save(); c.translate(p[0], p[1]); c.rotate(r() * 6); c.drawImage(v.im, -v.ox, -v.oy); c.restore(); });
  if (dev >= 1) spots(dev * 3).forEach(p => { c.fillStyle = '#5f4a35'; c.fillRect(p[0] - 10, p[1] - 2, 20, 4); c.fillStyle = '#3f3a33'; c.fillRect(p[0] - 9, p[1] + 2, 2, 3); c.fillRect(p[0] + 7, p[1] + 2, 2, 3); });
  if (dev >= 2) spots(dev * 2).forEach(p => { c.fillStyle = '#4a3a29'; rr(c, p[0] - 12, p[1] - 6, 24, 12, 3); c.fill(); for (let i = 0; i < 8; i++) { c.fillStyle = ['#c86e5a', '#e2c86f', '#d79cb7', '#6f9a54'][i % 4]; c.beginPath(); c.arc(p[0] - 9 + r() * 18, p[1] - 4 + r() * 8, 1.6, 0, 7); c.fill(); } });
  if (dev >= 1) { c.strokeStyle = '#7b6242'; c.lineWidth = 2; c.setLineDash([10, 4]); c.strokeRect(-470, -410, 940, 820); c.setLineDash([]); }
  if (!t.owner && dev === 0) { c.fillStyle = '#8a3d2e'; c.fillRect(-120, 128, 26, 10); c.fillRect(100, -140, 20, 8); }
  d = { im, dev }; townDecor.set(key, d); if (townDecor.size > 10) townDecor.delete(townDecor.keys().next().value); return d;
}
function lampsOf(t) { const out = []; if (!t.owner || t.levels.depot < 2) return out; const n = t.levels.depot >= 3 ? 8 : 4; for (let i = 0; i < n; i++) { const a = i / n * 6.28 + .4; out.push([t.x + Math.cos(a) * 138, t.y + Math.sin(a) * 138]); } return out; }

/* ---------- particles ---------- */
function puff(kind, x, y, vx, vy, life, size, color) { if (particles.length > (R.quality === 'low' ? 160 : 480)) particles.shift(); particles.push({ kind, x, y, vx, vy, life, max: life, size, color }); }
function updateParticles(dt) {
  for (let i = particles.length - 1; i >= 0; i--) { const p = particles[i]; p.life -= dt; if (p.life <= 0) { particles.splice(i, 1); continue; } p.x += p.vx * dt; p.y += p.vy * dt; if (p.kind === 'smoke') { p.vx += 6 * dt; p.size += dt * 5; } if (p.kind === 'spark' || p.kind === 'debris') { p.vx *= .92; p.vy *= .92; } if (p.kind === 'flame') p.size *= .985; }
}
function drawParticles(c, layer) {
  for (const p of particles) {
    const k = p.life / p.max;
    if (layer === 'low' && p.kind !== 'dust' && p.kind !== 'debris' && p.kind !== 'blood') continue;
    if (layer === 'high' && (p.kind === 'dust' || p.kind === 'debris' || p.kind === 'blood')) continue;
    if (p.kind === 'smoke' || p.kind === 'dust') { c.fillStyle = (p.color || '#8a8a80') + Math.floor(Math.min(1, k * 1.3) * (p.kind === 'dust' ? 60 : 52)).toString(16).padStart(2, '0'); c.beginPath(); c.arc(p.x, p.y, p.size, 0, 7); c.fill(); }
    else if (p.kind === 'flame') { const g = c.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.size); g.addColorStop(0, '#fff2b0'); g.addColorStop(.4, '#f39a3a' + Math.floor(k * 255).toString(16).padStart(2, '0')); g.addColorStop(1, '#c5401c00'); c.fillStyle = g; c.beginPath(); c.arc(p.x, p.y, p.size, 0, 7); c.fill(); }
    else if (p.kind === 'spark') { c.fillStyle = '#ffd98a'; c.fillRect(p.x, p.y, 2, 2); }
    else if (p.kind === 'debris') { c.fillStyle = p.color || '#4b4740'; c.fillRect(p.x, p.y, 3, 3); }
    else if (p.kind === 'blood') { c.fillStyle = '#6d1e18' + Math.floor(k * 200).toString(16).padStart(2, '0'); c.beginPath(); c.arc(p.x, p.y, p.size, 0, 7); c.fill(); }
  }
}
function effectsFrom(state, v) {
  for (const e of state.effects) {
    if (seenEffects.has(e.id)) continue; seenEffects.add(e.id); if (seenEffects.size > 600) seenEffects.delete(seenEffects.values().next().value);
    const near = Math.hypot(e.x - v.cam.x, e.y - v.cam.y);
    if (e.kind === 'boom') { for (let i = 0; i < 24; i++) { const a = Math.random() * 6.28, s = 40 + Math.random() * 160; puff('flame', e.x, e.y, Math.cos(a) * s * .4, Math.sin(a) * s * .4, .6 + Math.random() * .4, 14 + Math.random() * 10); puff('debris', e.x, e.y, Math.cos(a) * s, Math.sin(a) * s, .9, 2, '#2d2b27'); puff('smoke', e.x, e.y, Math.cos(a) * 20, Math.sin(a) * 20 - 10, 2.5, 10, '#3d3a36'); } if (R.onSound) R.onSound('boom', near); }
    else if (e.kind === 'levelup') { for (let i = 0; i < 36; i++) { const a = i / 36 * 6.28; puff('spark', e.x, e.y, Math.cos(a) * 140, Math.sin(a) * 140, .8, 1); puff('flame', e.x + Math.cos(a) * 20, e.y + Math.sin(a) * 20, Math.cos(a) * 30, Math.sin(a) * 30 - 20, .7, 5, null); } if (R.onSound && v.state && e.player === v.state.me.id) R.onSound('levelup', 0); }
    else if (e.kind === 'fall') { for (let i = 0; i < 8; i++) puff('blood', e.x + (Math.random() - .5) * 10, e.y + (Math.random() - .5) * 10, 0, 0, 30, 2 + Math.random() * 3); }
    else if (e.kind === 'bite') { for (let i = 0; i < 6; i++) puff('blood', e.ex + (Math.random() - .5) * 16, e.ey + (Math.random() - .5) * 16, 0, 0, 12, 1.5 + Math.random() * 2); if (R.onSound) R.onSound('bite', near); }
    else if (e.kind === 'acid') { for (let i = 0; i < 8; i++) puff('smoke', e.ex, e.ey, (Math.random() - .5) * 40, (Math.random() - .5) * 40, .8, 5, '#9cc23e'); if (R.onSound) R.onSound('acid', near); }
    else { puff('smoke', e.x, e.y, (Math.random() - .5) * 10, -8, .6, 3, '#a8a69a'); for (let i = 0; i < 4; i++) puff('spark', e.ex, e.ey, (Math.random() - .5) * 120, (Math.random() - .5) * 120, .25, 1); puff('dust', e.ex, e.ey, 0, 0, .5, 5, '#8d8673'); if (R.onSound) R.onSound(e.kind === 'tower' ? 'tower' : 'shot' + (e.weapon || 0), near); }
  }
}

/* ---------- light ---------- */
let lightCanvas = null;
function darkness(state) {
  const hour = (8 + state.time * 1.4 / 60) % 24;
  let d = hour >= 21.5 || hour < 4.5 ? .8 : hour >= 19 ? (hour - 19) / 2.5 * .8 : hour < 7 ? (7 - hour) / 2.5 * .8 : 0;
  const w = state.weather && state.weather.kind; d += w === 'storm' ? .22 : w === 'rain' ? .1 : w === 'fog' ? .08 : w === 'snow' ? .06 : 0;
  return { d: Math.min(.88, d), hour };
}
R.darkness = darkness;

/* ---------- main frame ---------- */
const civilFor = new Map();
R.draw = function (c, v) {
  sides = (v.state && v.state.sides) || {};
  const { cam, state } = v, now = v.now, dt = v.dt, Z = v.zoom || 1;
  // World-space view size; the canvas is scaled by the camera zoom.
  const cw = v.cw / Z, ch = v.ch / Z;
  const vis = (x, y, m) => Math.abs(x - cam.x) < cw / 2 + (m || 150) && Math.abs(y - cam.y) < ch / 2 + (m || 150);
  chunkQueue = 0;
  c.fillStyle = '#3f4a33'; c.fillRect(0, 0, v.cw, v.ch);
  c.save(); c.translate(v.cw / 2, v.ch / 2); c.scale(Z, Z); c.translate(-Math.round(cam.x), -Math.round(cam.y));
  const cx0 = Math.floor((cam.x - cw / 2) / CHUNK), cx1 = Math.floor((cam.x + cw / 2) / CHUNK), cy0 = Math.floor((cam.y - ch / 2) / CHUNK), cy1 = Math.floor((cam.y + ch / 2) / CHUNK);
  const visibleChunks = [];
  for (let cy = cy0; cy <= cy1; cy++) for (let cx = cx0; cx <= cx1; cx++) { if (cx < 0 || cy < 0 || cx * CHUNK >= cfg.width || cy * CHUNK >= cfg.height) continue; const k = getChunk(cx, cy); if (k) { c.drawImage(k.im, cx * CHUNK, cy * CHUNK); visibleChunks.push(k); } else { c.drawImage(biomeMap, cx * CHUNK / BM, cy * CHUNK / BM, CHUNK / BM, CHUNK / BM, cx * CHUNK, cy * CHUNK, CHUNK, CHUNK); } }
  // Animated water glints.
  c.strokeStyle = '#b8d4d633'; c.lineWidth = 1;
  visibleChunks.forEach(k => k.waterPts.forEach(p => { const s = Math.sin(now * 1.3 + p[2] * 20); if (s > .3) { c.beginPath(); c.moveTo(p[0] + s * 6, p[1]); c.lineTo(p[0] + s * 6 + 14, p[1]); c.stroke(); } }));
  const towns2 = state ? state.towns : null;
  // Settlement dressing and squares.
  cfg.towns.forEach(t0 => { if (!vis(t0.x, t0.y, 520)) return; const t = towns2 ? Object.assign({}, t0, towns2[t0.id]) : t0; if (!t.levels) return; const d = decor(t); c.drawImage(d.im, t.x - 500, t.y - 450); drawSquare(c, t, v); });
  drawParticles(c, 'low');
  // Depth-sorted scene: buildings, ruins, nodes, posts, vehicles, people.
  const items = [];
  cfg.buildings_world.forEach(b => { if (!vis(b.x, b.y, 200)) return; const t = towns2 ? towns2[b.town] : null; items.push({ y: b.y + b.h / 2, f: () => drawBuilding(c, b, t, v) }); });
  cfg.towns.forEach(t => { const lm = cfg.landmarks[t.id]; if (!lm || !vis(t.x + lm.x, t.y + lm.y, 260)) return; items.push({ y: t.y + lm.y + lm.h / 2, f: () => { const sp = S.landmark(t.id, lm.w, lm.h); c.drawImage(sp.im, t.x + lm.x - sp.ox, t.y + lm.y - sp.oy); } }); });
  pois.forEach(p => { if (!vis(p.x, p.y, 420)) return; p.parts.forEach((part, i) => items.push({ y: part.y + part.h / 2, f: () => { const sp = S.ruin(part.sprite, part.w, part.h, strSeed(p.id) + i * .13); c.drawImage(sp.im, part.x - sp.ox, part.y - sp.oy); } })); items.push({ y: p.y + 10, f: () => drawCache(c, p, state, v) }); });
  const gx0 = Math.floor((cam.x - cw / 2 - 100) / 1000), gx1 = Math.floor((cam.x + cw / 2 + 100) / 1000), gy0 = Math.floor((cam.y - ch / 2 - 100) / 1000), gy1 = Math.floor((cam.y + ch / 2 + 100) / 1000);
  for (let gx = gx0; gx <= gx1; gx++) for (let gy = gy0; gy <= gy1; gy++) (nodeGrid.get(gx + ',' + gy) || []).forEach(n => { if (!vis(n.x, n.y, 60) || (state && state.harvested && state.harvested[n.id] > state.time)) return; items.push({ y: n.y, f: () => { const sp = S.node(n.kind, Math.floor(hash(n.x, n.y) * 3)); c.drawImage(sp.im, n.x - sp.ox, n.y - sp.oy); if (v.nearest && v.nearest.obj === n) { c.strokeStyle = '#e7ae6b'; c.lineWidth = 1.2; c.setLineDash([4, 3]); c.beginPath(); c.ellipse(n.x, n.y + 8, 30, 15, 0, 0, 7); c.stroke(); c.setLineDash([]); } } }); });
  if (state) {
    (cfg.shelters || []).forEach(sh => { if (vis(sh.x, sh.y, 300)) items.push({ y: sh.y + 20, f: () => drawShelter(c, sh, v) }); });
    (cfg.givers || []).forEach(g => { if (!vis(g.x, g.y)) return; items.push({ y: g.y, f: () => { c.save(); c.translate(g.x, g.y); c.rotate(Math.PI / 2 + Math.sin(now * .4 + g.x) * .4); S.giver(c, { art: g.art, look: g.look, phase: now * .7 + g.x }); c.restore(); if (v.nearest && v.nearest.obj === g) { c.strokeStyle = '#d9b27a'; c.lineWidth = 1.2; c.setLineDash([4, 3]); c.beginPath(); c.ellipse(g.x, g.y + 6, 26, 14, 0, 0, 7); c.stroke(); c.setLineDash([]); } } }); });
    (state.posts || []).forEach(p => { if (vis(p.x, p.y)) items.push({ y: p.y, f: () => drawPost(c, p, now) }); });
    (state.airdrops || []).forEach(d => { if (vis(d.x, d.y)) items.push({ y: d.y, f: () => drawDrop(c, d, now) }); });
    state.players.forEach(p => {
      const r = v.drawPlayers[p.id]; if (!r) return;
      const car = p.vehicle ? { x: r.x, y: r.y, angle: p.car.angle } : p.car;
      if (car && vis(car.x, car.y)) items.push({ y: car.y, f: () => drawCar(c, car, AS.util.strSeed(p.id) < .5 ? 'pickup' : 'suv', p.car.wrecked_until > state.time ? 2 : p.car.hp < 50 ? 1 : 0, p.vehicle && p.moving, now) });
      if (!p.vehicle && vis(r.x, r.y)) items.push({ y: r.y, f: () => drawPlayer(c, p, r, v) });
    });
    (state.npcs || []).forEach(n => { const r = v.drawNpcs[n.id] || n; if (!vis(r.x, r.y)) return; items.push({ y: r.y, f: () => drawNpc(c, n, r, v) }); });
    cfg.towns.forEach(t0 => { if (!vis(t0.x, t0.y, 500)) return; civilians(t0, towns2 && towns2[t0.id], now, v).forEach(cv => items.push({ y: cv.y, f: () => { c.save(); c.translate(cv.x, cv.y); c.rotate(cv.a); S.look(c, { look: SNOWY[biomeAt(t0.x, t0.y)] && cv.seed > .5 ? 15 : CIVIL_LOOKS[Math.floor(cv.seed * 5)], phase: now * 7 + cv.seed * 9, moving: cv.moving, weapon: 0, size: 34 }); c.restore(); } })); });
  } else { items.push({ y: 5225, f: () => drawCar(c, { x: 7390, y: 5225, angle: -.4 }, 'suv', 0, false, now) }); }
  items.sort((a, b) => a.y - b.y).forEach(i => i.f());
  // Tracers.
  if (state) state.effects.forEach(e => { if (e.kind !== 'shot' && e.kind !== 'tower' && e.kind !== 'acid') return; const k = Math.max(0, (e.until - state.time) / .22); if (e.kind === 'acid') { c.strokeStyle = '#b9e04a' + Math.floor(Math.min(1, k) * 200).toString(16).padStart(2, '0'); c.lineWidth = 4; c.setLineDash([4, 6]); c.beginPath(); c.moveTo(e.x, e.y); c.lineTo(e.ex, e.ey); c.stroke(); c.setLineDash([]); return; } c.strokeStyle = (e.kind === 'tower' ? '#ffcf7a' : '#f8e3a8') + Math.floor(k * 220).toString(16).padStart(2, '0'); c.lineWidth = 1.6; c.beginPath(); c.moveTo(e.x, e.y); c.lineTo(e.ex, e.ey); c.stroke(); });
  // Canopies over everything on the ground; trees near the player become see-through.
  const me = state && v.drawPlayers[state.me.id];
  visibleChunks.forEach(k => k.trees.forEach(t => { if (!vis(t.x, t.y, 80)) return; const sp = S.tree(t.kind, t.v); const near = me && Math.abs(me.x - t.x) < 44 && Math.abs(me.y - t.y) < 44; if (near) c.globalAlpha = .38; const sway = Math.sin(now * 1.2 + t.x * .01) * (state && state.weather.kind === 'storm' ? 2.5 : .8); c.drawImage(sp.im, t.x - sp.ox + sway, t.y - sp.oy); if (near) c.globalAlpha = 1; }));
  // Chimney smoke from working production and fires.
  if (state) emitters(c, state, v, dt, vis);
  updateParticles(dt); drawParticles(c, 'high');
  if (state) effectsFrom(state, v);
  if (state) labels(c, state, v, vis);
  c.restore();
  if (state) { lights(c, v, vis); weather(c, v, dt, now); }
};

function drawSquare(c, t, v) {
  const color = col(t.owner);
  c.save(); c.translate(t.x, t.y);
  if (t.capture) { const cp = t.capture; c.fillStyle = col(cp.faction) + '1e'; c.beginPath(); c.arc(0, 0, 160, 0, 7); c.fill(); c.strokeStyle = cp.contested ? '#e0805f' : col(cp.faction); c.lineWidth = 5; c.beginPath(); c.arc(0, 0, 160, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(0, Math.min(1, cp.progress / 30))); c.stroke(); c.strokeStyle = '#ffffff22'; c.lineWidth = 1; c.setLineDash([6, 8]); c.beginPath(); c.arc(0, 0, 160, 0, 7); c.stroke(); c.setLineDash([]); }
  // Monument plinth and flagpole.
  c.fillStyle = '#00000040'; c.fillRect(-12, -8, 30, 26); c.fillStyle = '#8c887a'; c.fillRect(-16, -14, 32, 28); c.fillStyle = '#a19c8c'; c.fillRect(-16, -14, 32, 5);
  c.strokeStyle = '#00000044'; c.lineWidth = 3; c.beginPath(); c.moveTo(2, 0); c.lineTo(46, 22); c.stroke();
  c.strokeStyle = '#c9c4ae'; c.lineWidth = 3; c.beginPath(); c.moveTo(0, 2); c.lineTo(0, -64); c.stroke();
  const wave = Math.sin(v.now * 3 + t.x) * 3; c.fillStyle = color; c.beginPath(); c.moveTo(2, -62); c.quadraticCurveTo(18, -66 + wave, 36, -58 + wave); c.lineTo(34, -36 + wave * .6); c.quadraticCurveTo(18, -42 - wave, 2, -38); c.closePath(); c.fill(); c.fillStyle = '#ffffff22'; c.fillRect(2, -62, 30, 3);
  // Evening campfire in held settlements.
  if (t.owner) { c.fillStyle = '#3b3631'; c.beginPath(); c.arc(60, 46, 11, 0, 7); c.fill(); c.fillStyle = '#5a4a38'; c.fillRect(52, 44, 16, 3); c.fillRect(58, 38, 3, 16); if (v.dark > .3 && Math.random() < .5) puff('flame', 60 + (Math.random() - .5) * 6, 44, 0, -14, .5, 6 + Math.random() * 3); }
  if (t.event_ready && v.state) { c.fillStyle = '#d6b86d'; c.beginPath(); c.arc(64, -40, 12 + Math.sin(v.now * 4) * 1.2, 0, 7); c.fill(); c.fillStyle = '#253426'; c.font = 'bold 15px Segoe UI'; c.textAlign = 'center'; c.fillText('?', 64, -35); }
  c.restore();
}
function drawBuilding(c, b, t, v) {
  const level = t ? t.levels[b.kind] : (['depot', 'house'].includes(b.kind) && b.town === 'shabrovsky' ? 1 : 0), owner = t ? t.owner : null;
  const sp = S.building(b.kind, level, owner ? col(owner) : null, b.w, b.h); c.drawImage(sp.im, b.x - sp.ox, b.y - sp.oy);
  const con = t && t.construct && t.construct[b.kind];
  if (con) {
    c.save(); c.translate(b.x, b.y); c.strokeStyle = '#c99a5c'; c.lineWidth = 2; c.strokeRect(-b.w / 2 - 6, -b.h / 2 - 6, b.w + 12, b.h + 12); c.lineWidth = 1; for (let i = -b.w / 2; i < b.w / 2; i += 14) { c.beginPath(); c.moveTo(i, -b.h / 2 - 6); c.lineTo(i + 8, b.h / 2 + 6); c.stroke(); }
    c.fillStyle = '#16201ccc'; rr(c, -40, b.h / 2 + 14, 80, 8, 3); c.fill(); c.fillStyle = '#e7a568'; rr(c, -39, b.h / 2 + 15, 78 * Math.min(1, con.progress / con.total), 6, 3); c.fill();
    if (Math.random() < .2) puff('spark', b.x + (Math.random() - .5) * b.w, b.y + (Math.random() - .5) * b.h, (Math.random() - .5) * 60, -40, .3, 1);
    c.restore();
  }
  if (v.nearest && v.nearest.obj === b && !v.panel) { c.strokeStyle = '#e7b273'; c.lineWidth = 1.5; c.setLineDash([5, 5]); c.strokeRect(b.x - b.w / 2 - 9, b.y - b.h / 2 - 12, b.w + 18, b.h + 28); c.setLineDash([]); }
}
function drawCache(c, p, state, v) {
  const looted = state && state.loot && state.loot[p.id];
  c.save(); c.translate(p.x, p.y + 10);
  c.fillStyle = '#00000044'; c.fillRect(-14, -6, 32, 22); c.fillStyle = looted ? '#5a5244' : '#6b7d55'; c.fillRect(-16, -10, 32, 20); c.strokeStyle = '#2e3328'; c.lineWidth = 1.5; c.strokeRect(-16, -10, 32, 20); c.fillStyle = looted ? '#3a352c' : '#c9b46a'; c.fillRect(-3, -3, 6, 5);
  if (!looted) { c.strokeStyle = '#e7c27a' + (Math.floor(120 + Math.sin(v.now * 3) * 80)).toString(16); c.lineWidth = 1.2; c.beginPath(); c.arc(0, 0, 26, 0, 7); c.stroke(); }
  c.restore();
}
function drawPost(c, p, now) {
  c.save(); c.translate(p.x, p.y); const col = col(p.faction);
  c.fillStyle = '#00000044'; c.beginPath(); c.ellipse(8, 8, 40, 26, 0, 0, 7); c.fill();
  for (let a = 0; a < 6.28; a += .45) { c.fillStyle = (a * 10 | 0) % 2 ? '#a39470' : '#958763'; rr(c, Math.cos(a) * 30 - 5, Math.sin(a) * 22 - 3, 10, 6, 3); c.fill(); }
  c.fillStyle = '#5b4a35'; c.fillRect(-12, -10, 24, 20); c.fillStyle = col; c.fillRect(-12, -10, 24, 4);
  if (true) { c.fillStyle = '#d7d1bd'; c.fillRect(-46, -2, 34, 4); c.fillStyle = '#b8483c'; for (let i = 0; i < 4; i++) c.fillRect(-44 + i * 9, -2, 4, 4); }
  else { c.fillStyle = '#e8e3d0'; c.fillRect(-4, -6, 8, 3); c.fillRect(-1.5, -9, 3, 9); }
  c.strokeStyle = '#c9c4ae'; c.lineWidth = 2; c.beginPath(); c.moveTo(10, -6); c.lineTo(10, -36); c.stroke(); c.fillStyle = col; c.beginPath(); c.moveTo(11, -36); c.lineTo(26, -32 + Math.sin(now * 3) * 2); c.lineTo(11, -26); c.fill();
  c.fillStyle = '#16201ccc'; c.fillRect(-20, 26, 40, 4); c.fillStyle = col; c.fillRect(-20, 26, 40 * Math.max(0, p.hp) / 220, 4);
  c.restore();
}
function drawDrop(c, d, now) {
  c.save(); c.translate(d.x, d.y); c.fillStyle = '#00000044'; c.fillRect(-10, -6, 30, 22);
  c.fillStyle = '#d8d3c0aa'; c.beginPath(); c.moveTo(-30, -18); c.quadraticCurveTo(-10, -40, 20, -26); c.quadraticCurveTo(28, -8, 34, 4); c.lineTo(-24, 0); c.closePath(); c.fill(); c.fillStyle = '#c45a3a88'; c.fillRect(-20, -22, 30, 4);
  crateDraw(c); c.strokeStyle = '#ffd38a' + Math.floor(140 + Math.sin(now * 4) * 100).toString(16).padStart(2, '0'); c.lineWidth = 1.5; c.beginPath(); c.arc(0, 0, 30, 0, 7); c.stroke(); c.restore();
}
function crateDraw(c) { c.fillStyle = '#6b7d55'; c.fillRect(-12, -10, 24, 20); c.strokeStyle = '#2e3328'; c.strokeRect(-12, -10, 24, 20); c.beginPath(); c.moveTo(-12, -10); c.lineTo(12, 10); c.stroke(); }
function drawCar(c, car, faction, damage, moving, now) {
  const sp = S.vehicle(faction === 'pickup' ? 'pickup' : 'suv', faction === 'pickup' ? '#6e3b2c' : '#7d8664', damage);
  c.save(); c.translate(car.x, car.y); c.rotate(car.angle); c.drawImage(sp.im, -sp.ox, -sp.oy); c.restore();
  if (moving && Math.random() < .5) puff('dust', car.x - Math.cos(car.angle) * 34, car.y - Math.sin(car.angle) * 34, (Math.random() - .5) * 20, (Math.random() - .5) * 20, .8, 6, '#9d927a');
  if (damage === 2 && Math.random() < .3) puff('smoke', car.x, car.y, 4, -12, 2, 6, '#2f2c28');
}
function drawPlayer(c, p, r, v) {
  const isMe = v.state && p.id === v.state.me.id, t = v.state.time;
  const ang = isMe && !p.vehicle ? Math.atan2(v.aim.y, v.aim.x) : (t - p.shot < .6 ? p.angle : p.angle);
  const dead = p.hp <= 0;
  c.save(); c.translate(r.x, r.y); c.rotate(dead ? 0 : (isMe ? ang : (r.ang != null ? r.ang : p.angle)));
  S.look(c, { look: p.look || 0, weapon: p.gear ? p.gear.weapon : 0, phase: r.phase || 0, moving: p.moving, run: p.sprint, aim: (isMe && v.holdAim) || t - p.shot < 1.2, shot: t - p.shot < .25, flash: t - p.shot < .07, dead });
  c.restore();
  if (dead) return;
  const mx = p.max_hp || 100; if (p.hp < mx) { c.fillStyle = '#18271fcc'; c.fillRect(r.x - 18, r.y + 22, 36, 4); c.fillStyle = p.hp > mx * .4 ? '#9cc28c' : '#d27a5e'; c.fillRect(r.x - 18, r.y + 22, 36 * p.hp / mx, 4); }
}
const CREATURES = { wolf: 1, bear: 1, boar: 1, elk: 1, mutant: 1, spitter: 1, brute: 1 };
function drawNpc(c, n, r, v) {
  if (CREATURES[n.type]) {
    const t = v.state.time, dead = n.hp <= 0;
    c.save(); c.translate(r.x, r.y); c.rotate(dead ? 0 : (r.ang != null ? r.ang : n.angle));
    S.creature(c, { type: n.type, phase: (r.phase || 0) * (n.type === 'elk' || n.type === 'wolf' ? 1.4 : 1), moving: r.moving, attack: t - n.shot < .25, dead });
    c.restore();
    if (!dead && n.hp < n.max) bar(c, r.x, r.y + (n.type === 'bear' || n.type === 'brute' ? 34 : 24), n.hp / n.max, n.faction === 'mutants' ? '#a7c46a' : '#c9a36a');
    return;
  }
  if (n.type === 'convoy') {
    const sp = S.vehicle('truck', mix(col(n.faction), '#3d4236', .45), n.hp < n.max * .4 ? 1 : 0);
    c.save(); c.translate(r.x, r.y); c.rotate(r.ang != null ? r.ang : n.angle); c.drawImage(sp.im, -sp.ox, -sp.oy); c.restore();
    if (Math.random() < .4) puff('dust', r.x - Math.cos(n.angle) * 50, r.y - Math.sin(n.angle) * 50, 0, 0, .9, 7, '#9d927a');
    bar(c, r.x, r.y + 30, n.hp / n.max, col(n.faction)); return;
  }
  const dead = n.hp <= 0, t = v.state.time;
  c.save(); c.translate(r.x, r.y); c.rotate(dead ? 0 : (r.ang != null ? r.ang : n.angle));
  const look = n.look != null ? n.look : ({ marauder: 0, raider: 19, ranger: 7, militia: 6 })[n.type] || 0;
  S.look(c, { look, weapon: NPC_WEAPON[n.type] || 0, phase: r.phase || 0, moving: r.moving, aim: n.mode === 'fight', shot: t - n.shot < .25, flash: t - n.shot < .07, dead, size: n.type === 'guardian' ? 42 : 38 });
  c.restore();
  if (!dead && n.hp < n.max) bar(c, r.x, r.y + 24, n.hp / n.max, MONSTER[n.faction] ? '#b07a52' : col(n.faction));
}
const CIVIL_LOOKS = [0, 18, 5, 0, 18];
const NPC_WEAPON = { marauder: 0, occupier: 1, occupier_elite: 2, defender: 2, guardian: 6, bandit: 3, raider: 2, ranger: 4, militia: 1 };
const MONSTER = { marauders: 1, outlaws: 1 };
function drawShelter(c, sh, v) {
  const owner = Object.keys(sides).find(id => sides[id].shelter === sh.id), mine = owner && v.state.me.faction === owner;
  const friend = owner && (mine || (sides[owner].clan && sides[owner].clan === (sides[v.state.me.faction] || {}).clan));
  const zone = cfg.shelter_radius || 470;
  c.save(); c.translate(sh.x, sh.y);
  if (owner) { c.strokeStyle = friend ? '#7fa58f88' : '#c4554488'; c.lineWidth = 3; c.setLineDash([18, 12]); c.beginPath(); c.arc(0, 0, zone, 0, 7); c.stroke(); c.setLineDash([]); if (!friend) { c.fillStyle = '#c455440c'; c.beginPath(); c.arc(0, 0, zone, 0, 7); c.fill(); } }
  // Bunker entrance: earth mound, concrete portal, blast door.
  c.fillStyle = '#00000044'; c.beginPath(); c.ellipse(10, 10, 70, 44, 0, 0, 7); c.fill();
  c.fillStyle = '#4f5340'; c.beginPath(); c.ellipse(0, -10, 66, 40, 0, 0, 7); c.fill(); c.fillStyle = '#5d6249'; c.beginPath(); c.ellipse(-8, -18, 48, 26, 0, 0, 7); c.fill();
  c.fillStyle = '#7b786d'; c.fillRect(-30, 4, 60, 22); c.fillStyle = '#8f8b7f'; c.fillRect(-30, 4, 60, 4);
  c.fillStyle = '#3c4038'; c.fillRect(-20, 10, 40, 16); c.strokeStyle = '#2a2c27'; c.lineWidth = 2; c.beginPath(); c.arc(0, 18, 6, 0, 7); c.moveTo(-6, 18); c.lineTo(6, 18); c.moveTo(0, 12); c.lineTo(0, 24); c.stroke();
  c.fillStyle = '#9a9283'; c.fillRect(32, -40, 4, 30); c.fillRect(30, -42, 8, 3);
  for (let a = -2.6; a < -0.4; a += .32) { c.fillStyle = (a * 10 | 0) % 2 ? '#a39470' : '#8f835f'; rr(c, Math.cos(a) * 88 - 6, Math.sin(a) * 58 + 30 - 3, 12, 7, 3); c.fill(); }
  if (owner) { c.strokeStyle = '#c9c4ae'; c.lineWidth = 2; c.beginPath(); c.moveTo(-44, 0); c.lineTo(-44, -46); c.stroke(); c.fillStyle = col(owner); c.fillRect(-43, -46, 18, 11); }
  c.restore();
}
function bar(c, x, y, k, col) { c.fillStyle = '#18271fcc'; c.fillRect(x - 18, y, 36, 4); c.fillStyle = col; c.fillRect(x - 18, y, 36 * Math.max(0, k), 4); }

function civilians(t0, t, now, v) {
  if (!t) return [];
  const n = t.owner ? Math.min(10, 2 + Math.floor((t.population || 0) / 4)) : 2;
  const night = v.dark > .5, out = [];
  for (let i = 0; i < n; i++) {
    const seed = hash(i, t0.x), speed = 18 + seed * 14, ring = 150 + hash(t0.y, i) * 160;
    if (night && i % 3) { const a = i * 1.3; out.push({ x: t0.x + 60 + Math.cos(a) * 24, y: t0.y + 46 + Math.sin(a) * 18, a: a + Math.PI, moving: false, seed }); continue; }
    const per = ring * 6.28 / speed, ph = ((now + seed * 100) % per) / per * 6.28 * (i % 2 ? 1 : -1);
    const x = t0.x + Math.cos(ph) * ring, y = t0.y + Math.sin(ph) * ring * .8;
    const a = ph + (i % 2 ? Math.PI / 2 : -Math.PI / 2);
    out.push({ x, y, a, moving: true, seed });
  }
  return out;
}
function emitters(c, state, v, dt, vis) {
  const rate = R.quality === 'low' ? .3 : 1;
  cfg.buildings_world.forEach(b => {
    if (!vis(b.x, b.y, 300)) return; const t = state.towns[b.town]; if (!t) return;
    if (t.fires && t.fires[b.kind]) { for (let i = 0; i < 2 * rate; i++) puff('flame', b.x + (Math.random() - .5) * b.w * .8, b.y + (Math.random() - .5) * b.h * .6, (Math.random() - .5) * 10, -30 - Math.random() * 30, .7, 10 + Math.random() * 10); if (Math.random() < .5 * rate) puff('smoke', b.x + (Math.random() - .5) * b.w * .5, b.y - b.h * .3, 8, -26, 3, 10, '#2f2c28'); }
    else if (t.owner && t.active && t.active[b.kind] && Math.random() < dt * 2.2 * rate) puff('smoke', b.x + b.w * .3, b.y - b.h * .4, 6, -18, 3.2, 4, '#a9a69c');
    else if (!t.owner && t.levels[b.kind] === 0 && hash(b.x, 1) > .8 && Math.random() < dt * 1.5 * rate) puff('smoke', b.x, b.y - 10, 4, -14, 3, 4, '#55524a');
  });
  pois.forEach(p => { if (!vis(p.x, p.y, 300)) return; p.parts.forEach(part => { if (part.sprite === 'chimney' && Math.random() < dt * 1.2 * rate) puff('smoke', part.x, part.y, 10, -12, 4, 8, '#6b6862'); }); });
}
function labels(c, state, v, vis) {
  c.font = '11px Segoe UI, Arial'; c.textAlign = 'center';
  const me = v.drawPlayers[state.me.id];
  cfg.towns.forEach(t0 => { if (!vis(t0.x, t0.y, 200)) return; const t = state.towns[t0.id]; pill(c, t0.name.toUpperCase(), t0.x, t0.y - 104, col(t.owner)); if (!v.panel && me && Math.hypot(me.x - t0.x, me.y - t0.y) > 170) pill(c, 'E · ПЛОЩАДЬ', t0.x, t0.y + 136, '#d9d6bb'); });
  cfg.buildings_world.forEach(b => { if (!me || Math.abs(b.x - me.x) > 260 || Math.abs(b.y - me.y) > 220) return; const t = state.towns[b.town], L = t.levels[b.kind]; pill(c, cfg.buildings[b.kind].name + (L ? ' · ' + L : ' · руины') + (t.construct && t.construct[b.kind] ? ' · стройка' : ''), b.x, b.y - b.h / 2 - 22, L ? '#dce1cf' : '#c8c6b1'); });
  cfg.towns.forEach(t => { const lm = cfg.landmarks[t.id]; if (lm && me && Math.hypot(me.x - t.x - lm.x, me.y - t.y - lm.y) < 420) pill(c, '★ ' + lm.name, t.x + lm.x, t.y + lm.y - lm.h / 2 - 24, '#ecd29a'); });
  pois.forEach(p => { if (vis(p.x, p.y, 100)) pill(c, p.name.toUpperCase() + ' · ' + p.kind_name.toLowerCase(), p.x, p.y - 196, '#d8c79c'); });
  state.players.forEach(p => { const r = v.drawPlayers[p.id]; if (!r || p.vehicle || !vis(r.x, r.y) || p.id === state.me.id) return; if (me && Math.hypot(me.x - r.x, me.y - r.y) > 700) return; pill(c, (p.tag ? '[' + p.tag + '] ' : '') + p.name + ' · ' + (p.level || 1), r.x, r.y - 34, col(p.faction)); });
  (cfg.givers || []).forEach(g => { if (me && Math.abs(me.x - g.x) < 260 && Math.abs(me.y - g.y) < 200) pill(c, g.role + ' · ' + g.name, g.x, g.y - 34, '#e2d3b0'); });
  (cfg.shelters || []).forEach(sh => { if (!vis(sh.x, sh.y, 100)) return; const owner = Object.keys(sides).find(id => sides[id].shelter === sh.id); if (!owner) return; pill(c, 'УБЕЖИЩЕ · ' + sides[owner].name.toUpperCase(), sh.x, sh.y - 70, col(owner)); });
  (state.posts || []).forEach(p => { if (vis(p.x, p.y)) pill(c, p.name, p.x, p.y - 48, col(p.faction)); });
}
function pill(c, text, x, y, color, bg) { c.font = '11px Segoe UI, Arial'; const w = c.measureText(text).width + 14; c.fillStyle = bg || '#0e1311b8'; c.fillRect(x - w / 2, y - 9, w, 18); c.fillStyle = color || '#e3e3d4'; c.fillRect(x - w / 2, y - 9, 2, 18); c.fillStyle = '#d9d8cb'; c.textAlign = 'center'; c.fillText(text, x, y + 4); }
R.pill = pill;

function lights(c, v, vis) {
  const { cw, ch, cam, state } = v, Z = v.zoom || 1; const dk = darkness(state); v.dark = dk.d;
  if (dk.d < .04) return;
  const scale = R.quality === 'low' ? .35 : .5, w = Math.ceil(cw * scale), h = Math.ceil(ch * scale);
  if (!lightCanvas || lightCanvas.width !== w || lightCanvas.height !== h) lightCanvas = canvas(w, h);
  const l = lightCanvas.getContext('2d'); l.globalCompositeOperation = 'source-over'; l.clearRect(0, 0, w, h);
  l.fillStyle = 'rgba(8,12,26,' + dk.d + ')'; l.fillRect(0, 0, w, h);
  l.globalCompositeOperation = 'destination-out';
  const sx = x => ((x - cam.x) * Z + cw / 2) * scale, sy = y => ((y - cam.y) * Z + ch / 2) * scale, zs = scale * Z;
  const glow = [];
  const hole = (x, y, r, k, warm) => { if (!vis(x, y, r)) return; const g = l.createRadialGradient(sx(x), sy(y), 0, sx(x), sy(y), r * zs); g.addColorStop(0, 'rgba(0,0,0,' + k + ')'); g.addColorStop(1, 'rgba(0,0,0,0)'); l.fillStyle = g; l.fillRect(sx(x) - r * zs, sy(y) - r * zs, r * 2 * zs, r * 2 * zs); if (warm) glow.push([x, y, r * .7, warm]); };
  const flick = Math.sin(v.now * 13) * .04 + Math.sin(v.now * 7.7) * .03;
  cfg.towns.forEach(t0 => {
    if (!vis(t0.x, t0.y, 700)) return; const t = state.towns[t0.id];
    if (t.owner) hole(t0.x + 60, t0.y + 46, 150, .9 + flick, '#ff9c4a');
    lampsOf(Object.assign({}, t0, t)).forEach(p => hole(p[0], p[1], 120, .8, '#ffd58a'));
    cfg.buildings_world.forEach(b => { if (b.town !== t0.id) return; const L = t.levels[b.kind]; if (t.owner && L >= 1) hole(b.x, b.y + b.h / 2, 60 + L * 25, .55 + L * .1, L >= 2 ? '#f4c574' : null); if (t.fires && t.fires[b.kind]) hole(b.x, b.y, 230, 1, '#ff7a30'); });
    if (t.levels.guard >= 3) { const g = cfg.buildings_world.find(b => b.town === t0.id && b.kind === 'guard'); const a = v.now * .6; cone(l, sx(g.x), sy(g.y), a, .5, 380 * zs, .7); }
  });
  (state.posts || []).forEach(p => hole(p.x, p.y, 160, .8, '#ffc36a'));
  (cfg.shelters || []).forEach(sh => { if (Object.keys(sides).some(id => sides[id].shelter === sh.id)) { hole(sh.x, sh.y + 20, 140, .85, '#ffcf8a'); hole(sh.x - 160, sh.y - 110, 90, .7, '#e8f0ff'); hole(sh.x + 160, sh.y + 120, 90, .7, '#e8f0ff'); } });
  state.players.forEach(p => {
    const r = v.drawPlayers[p.id]; if (!r || p.hp <= 0) return;
    hole(r.x, r.y, 70, .5);
    const ang = p.id === state.me.id && !p.vehicle ? Math.atan2(v.aim.y, v.aim.x) : p.angle;
    if (p.vehicle) { cone(l, sx(r.x + Math.cos(ang) * 30), sy(r.y + Math.sin(ang) * 30), ang, .38, 460 * zs, .95); }
    else cone(l, sx(r.x), sy(r.y), ang, .42, 330 * zs, .85);
    if (state.time - p.shot < .07) hole(r.x, r.y, 160, 1, '#ffe2a0');
  });
  (state.npcs || []).forEach(n => { const r = v.drawNpcs[n.id] || n; if (n.type === 'convoy') cone(l, sx(r.x + Math.cos(n.angle) * 44), sy(r.y + Math.sin(n.angle) * 44), n.angle, .35, 420 * zs, .9); if (state.time - n.shot < .07) hole(r.x, r.y, 140, 1, '#ffe2a0'); });
  particles.forEach(p => { if (p.kind === 'flame' && p.size > 8) hole(p.x, p.y, p.size * 5, .5); });
  l.globalCompositeOperation = 'source-over';
  c.drawImage(lightCanvas, 0, 0, cw, ch);
  // Warm additive glow on top of the darkened scene.
  c.save(); c.globalCompositeOperation = 'lighter'; c.translate(cw / 2, ch / 2); c.scale(Z, Z); c.translate(-cam.x, -cam.y);
  glow.forEach(gl => { const g = c.createRadialGradient(gl[0], gl[1], 0, gl[0], gl[1], gl[2]); g.addColorStop(0, gl[3] + '30'); g.addColorStop(1, gl[3] + '00'); c.fillStyle = g; c.fillRect(gl[0] - gl[2], gl[1] - gl[2], gl[2] * 2, gl[2] * 2); });
  c.restore();
}
function cone(l, x, y, ang, spread, len, k) {
  const g = l.createRadialGradient(x, y, 0, x, y, len); g.addColorStop(0, 'rgba(0,0,0,' + k + ')'); g.addColorStop(.7, 'rgba(0,0,0,' + k * .5 + ')'); g.addColorStop(1, 'rgba(0,0,0,0)');
  l.fillStyle = g; l.beginPath(); l.moveTo(x, y); l.arc(x, y, len, ang - spread, ang + spread); l.closePath(); l.fill();
}

/* Screen-space weather. */
const drops = []; let fogT = 0;
function weather(c, v, dt, now) {
  const { cw, ch, state, cam } = v; const kind = state.weather ? state.weather.kind : 'clear';
  const cold = R.coldAt(cam.x, cam.y);
  const mode = kind === 'snow' || ((kind === 'rain' || kind === 'storm') && cold >= 2) ? 'snow' : (kind === 'rain' || kind === 'storm') ? 'rain' : kind;
  v.weatherMode = mode;
  const target = mode === 'rain' ? (kind === 'storm' ? 260 : 170) : mode === 'snow' ? 190 : 0;
  const n = Math.floor(target * (R.quality === 'low' ? .4 : 1));
  while (drops.length < n) drops.push({ x: Math.random() * cw, y: Math.random() * ch, s: .5 + Math.random(), p: Math.random() * 6 });
  if (drops.length > n) drops.length = n;
  if (mode === 'rain') {
    c.strokeStyle = '#b9c8d266'; c.lineWidth = 1; c.beginPath();
    drops.forEach(d => { d.y += 900 * d.s * dt; d.x += -140 * dt; if (d.y > ch) { d.y = -20; d.x = Math.random() * (cw + 100); if (Math.random() < .15) puff('dust', cam.x - cw / 2 + d.x, cam.y - ch / 2 + Math.random() * ch, 0, 0, .3, 2, '#9fb3c0'); } if (d.x < -20) d.x = cw + 10; c.moveTo(d.x, d.y); c.lineTo(d.x + 4, d.y - 16 * d.s); }); c.stroke();
    c.fillStyle = '#1b2a3418'; c.fillRect(0, 0, cw, ch);
  } else if (mode === 'snow') {
    c.fillStyle = '#eef3f5cc';
    drops.forEach(d => { d.y += 60 * d.s * dt; d.x += Math.sin(now + d.p) * 20 * dt - 15 * dt; if (d.y > ch) { d.y = -5; d.x = Math.random() * cw; } if (d.x < -5) d.x = cw; c.fillRect(d.x, d.y, 2 * d.s + .5, 2 * d.s + .5); });
    c.fillStyle = '#dfe8ee14'; c.fillRect(0, 0, cw, ch);
  }
  if (mode === 'fog' || kind === 'storm') {
    fogT += dt * 12; const g = c.createRadialGradient(cw / 2, ch / 2, Math.min(cw, ch) * .18, cw / 2, ch / 2, Math.max(cw, ch) * .7);
    g.addColorStop(0, '#c7ccc600'); g.addColorStop(1, mode === 'fog' ? '#b8beb8d0' : '#9aa3a660'); c.fillStyle = g; c.fillRect(0, 0, cw, ch);
    c.fillStyle = '#c3c8c218'; for (let i = 0; i < 6; i++) { const x = ((i * 397 + fogT) % (cw + 600)) - 300, y = (i * 211) % ch; c.beginPath(); c.ellipse(x, y, 320, 120, 0, 0, 7); c.fill(); }
  }
  if (kind === 'storm') { if (Math.random() < dt * .08) { lightning = 1; if (R.onSound) setTimeout(() => R.onSound('thunder', 0), 400 + Math.random() * 1200); } }
  if (lightning > 0) { c.fillStyle = 'rgba(230,236,255,' + lightning * .55 + ')'; c.fillRect(0, 0, cw, ch); lightning -= dt * 3; }
}

/* ---------- maps ---------- */
R.drawMap = function (cv, big, v, mapState) {
  sides = (v.state && v.state.sides) || sides;
  const { state, dpr } = v; if (!state || !cv) return null;
  const c = cv.getContext('2d'), box = cv.getBoundingClientRect(); const w = big ? box.width : 250, h = big ? box.height : 160;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
  c.setTransform(dpr, 0, 0, dpr, 0, 0); c.fillStyle = '#14221b'; c.fillRect(0, 0, w, h);
  let scale, ox, oy;
  if (big) { scale = Math.min((w - 30) / cfg.width, (h - 30) / cfg.height) * (mapState.zoom || 1); const fx = mapState.fx != null ? mapState.fx : cfg.width / 2, fy = mapState.fy != null ? mapState.fy : cfg.height / 2; ox = w / 2 - fx * scale; oy = h / 2 - fy * scale; }
  else { scale = .07; ox = w / 2 - state.me.x * scale; oy = h / 2 - state.me.y * scale; }
  c.imageSmoothingEnabled = true; c.drawImage(worldMap, ox, oy, cfg.width * scale, cfg.height * scale);
  const P = (x, y) => [ox + x * scale, oy + y * scale];
  // Points of interest.
  pois.forEach(p => { const [x, y] = P(p.x, p.y); if (x < -5 || x > w + 5 || y < -5 || y > h + 5) return; const looted = state.loot && state.loot[p.id]; c.fillStyle = looted ? '#776f5e' : '#d8c79c'; c.save(); c.translate(x, y); c.rotate(.785); c.fillRect(-2.5, -2.5, 5, 5); c.restore(); if (big && (mapState.zoom || 1) > 1.6) { c.fillStyle = '#c9c0a2'; c.font = '9px Segoe UI'; c.textAlign = 'center'; c.fillText(p.name, x, y + 12); } });
  (state.airdrops || []).forEach(d => { const [x, y] = P(d.x, d.y); c.strokeStyle = '#ffd38a'; c.lineWidth = 1.5; c.beginPath(); c.arc(x, y, 5 + Math.sin(v.now * 5) * 1.5, 0, 7); c.stroke(); });
  (state.posts || []).forEach(p => { const [x, y] = P(p.x, p.y); c.fillStyle = col(p.faction); c.fillRect(x - 3, y - 3, 6, 6); });
  Object.values(state.towns).forEach(t => { const [x, y] = P(t.x, t.y); if (x < -40 || x > w + 40 || y < -20 || y > h + 20) return; const color = col(t.owner); c.fillStyle = '#0d1512'; c.beginPath(); c.arc(x, y, big ? 6 : 4, 0, 7); c.fill(); c.fillStyle = color; c.beginPath(); c.arc(x, y, big ? 4.5 : 3, 0, 7); c.fill(); if (big) { c.fillStyle = mapState.selected === t.id ? '#f0d09d' : '#e1e3d6'; c.font = (mapState.selected === t.id ? 'bold ' : '') + '11px Segoe UI, Arial'; c.textAlign = 'center'; c.fillText(t.name, x, y - 10); } if (t.capture) { c.strokeStyle = '#e3ad74'; c.lineWidth = 1.5; c.beginPath(); c.arc(x, y, 9 + Math.sin(v.now * 6) * 2, 0, 7); c.stroke(); } });
  (cfg.shelters || []).forEach(sh => { const owner = Object.keys(sides).find(id => sides[id].shelter === sh.id); if (!owner) return; const [x, y] = P(sh.x, sh.y); if (x < -10 || x > w + 10 || y < -10 || y > h + 10) return; const mine = owner === state.me.faction; c.fillStyle = '#0d1512'; c.fillRect(x - 5, y - 5, 10, 10); c.fillStyle = col(owner); c.fillRect(x - 3.5, y - 3.5, 7, 7); if (mine) { c.strokeStyle = '#edaf6b'; c.lineWidth = 1.5; c.strokeRect(x - 7, y - 7, 14, 14); if (big) { c.fillStyle = '#edaf6b'; c.font = 'bold 10px Segoe UI'; c.textAlign = 'center'; c.fillText('УБЕЖИЩЕ', x, y + 17); } } });
  (state.npcs || []).forEach(n => { if (n.type !== 'convoy' && !big) return; const [x, y] = P(n.x, n.y); if (n.type === 'convoy') { c.fillStyle = col(n.faction); c.fillRect(x - 3, y - 2, 6, 4); } else if (n.faction === 'marauders') { c.fillStyle = '#c98a5a99'; c.fillRect(x - 1, y - 1, 2, 2); } else { c.fillStyle = col(n.faction) || '#ccc'; c.fillRect(x - 1.5, y - 1.5, 3, 3); } });
  state.players.forEach(p => { const [x, y] = P(p.x, p.y); const me = p.id === state.me.id; c.fillStyle = me ? '#edaf6b' : col(p.faction); c.beginPath(); c.arc(x, y, me ? 4 : 3, 0, 7); c.fill(); if (me) { c.strokeStyle = '#eabf8a88'; c.lineWidth = 1; c.beginPath(); c.arc(x, y, 8 + Math.sin(v.now * 4) * 2, 0, 7); c.stroke(); const a = p.vehicle ? p.angle : Math.atan2(v.aim.y, v.aim.x); c.beginPath(); c.moveTo(x + Math.cos(a) * 11, y + Math.sin(a) * 11); c.lineTo(x + Math.cos(a + 2.5) * 5, y + Math.sin(a + 2.5) * 5); c.lineTo(x + Math.cos(a - 2.5) * 5, y + Math.sin(a - 2.5) * 5); c.fill(); } });
  if (v.waypoint) { const [x, y] = P(v.waypoint.x, v.waypoint.y), [mx, my] = P(state.me.x, state.me.y); c.strokeStyle = '#dfbb7c'; c.lineWidth = 1; c.setLineDash([4, 4]); c.beginPath(); c.moveTo(mx, my); c.lineTo(x, y); c.stroke(); c.setLineDash([]); c.strokeRect(x - 6, y - 6, 12, 12); }
  if (!big) { c.strokeStyle = '#ffffff22'; c.strokeRect(.5, .5, w - 1, h - 1); }
  return { scale, ox, oy };
};
})();
