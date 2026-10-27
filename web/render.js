/* After Silence. World renderer: cached terrain chunks, depth-sorted objects, light, weather, particles. */
(function () {
'use strict';
const AS = window.AS = window.AS || {};
const { hash, rng, strSeed, rr, mix, shade, canvas } = AS.util;
const S = AS.sprites, COL = AS.colors;
const CHUNK = 512, CORE = [520, 480];
let BM = 100;   // world pixels per biome-map pixel; grows with the map so the climate map stays small
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
let streets = [], houses = [], houseGrid = new Map(), streetGrid = new Map();
// Highway asphalt width (two lanes each way, two cars side by side per lane); set from the config.
let RW = 240, roadWrecks = [];
let cfg = null, towns = [], townById = {}, roads = [], waterSegs = [], lakes = [], pois = [], pumps = [], nodeGrid = new Map();
let biomeMap = null, worldMap = null;
const chunks = new Map(); let chunkQueue = 0, chunkMissedCars = false;
const particles = []; const seenEffects = new Set(); let lightning = 0;
const townDecor = new Map();
const R = AS.render = { quality: 'high', onSound: null };
// Every player and clan has its own colour, sent by the host with the state.
let sides = {};
function col(id) { return (id && sides[id] && sides[id].color) || COL[id] || COL.neutral; }
R.col = col;

function segDist(px, py, ax, ay, bx, by) { const dx = bx - ax, dy = by - ay, l = dx * dx + dy * dy; const u = l ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / l)) : 0; return Math.hypot(px - ax - u * dx, py - ay - u * dy); }
function inPoly(x, y, poly) { let inside = false; for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) { const xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1]; if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside; } return inside; }
function inTown(x, y, pad) { pad = pad || 0; return towns.some(t => Math.abs(x - t.x) < t.r + pad && Math.abs(y - t.y) < t.h + pad); }
function inCore(x, y, pad) { pad = pad || 0; return towns.some(t => Math.abs(x - t.x) < CORE[0] + pad && Math.abs(y - t.y) < CORE[1] + pad); }
const gkey = (x, y) => Math.floor(x / 1000) + ',' + Math.floor(y / 1000);
function onStreet(x, y, pad) { return (streetGrid.get(gkey(x, y)) || []).some(s => segDist(x, y, s[0], s[1], s[2], s[3]) < s[4] / 2 + (pad || 0)); }
function houseAt(x, y, pad) { pad = pad || 0; for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) for (const h of houseGrid.get((Math.floor(x / 1000) + i) + ',' + (Math.floor(y / 1000) + j)) || []) if (Math.abs(x - h.x) < h.w / 2 + pad && Math.abs(y - h.y) < h.h / 2 + pad) return h; return null; }
R.houseAt = houseAt; R.onStreet = onStreet; R.inCore = inCore;
function onRoad(x, y, w) { return roads.some(r => segDist(x, y, r.ax, r.ay, r.bx, r.by) < w); }
function water(x, y, pad) { pad = pad || 0; if (inCore(x, y)) return false; for (const s of waterSegs) if (segDist(x, y, s[0], s[1], s[2], s[3]) < s[4] + pad) return true; for (const l of lakes) if (inPoly(x, y, l)) return true; return false; }
// Space kept clear of trees and bushes: houses, streets, the square.
function built(x, y, pad) { return inCore(x, y, pad - 200) || onStreet(x, y, pad) || !!houseAt(x, y, pad + 6); }
R.water = water; R.onRoad = onRoad; R.inTown = inTown;
function nearestTown(x, y) { let best = null, bd = 1e18; for (const t of towns) { const d = (t.x - x) * (t.x - x) + (t.y - y) * (t.y - y); if (d < bd) { bd = d; best = t; } } return best; }
function biomeAt(x, y) { const t = nearestTown(x, y); return cfg.regions[t.region] ? cfg.regions[t.region].biome : 'mixed'; }
R.biomeAt = biomeAt;
R.coldAt = (x, y) => { const t = nearestTown(x, y); return (cfg.regions[t.region] || { cold: 0 }).cold; };

R.init = function (config) {
  cfg = config; towns = cfg.towns.map(t => Object.assign({}, t)); townById = {}; towns.forEach(t => townById[t.id] = t);
  // Highways come from the host and end at town gates, continuing as the town's cross streets.
  RW = cfg.road_width || 240; roadWrecks = cfg.wrecks || [];
  roads = cfg.road_lines.map(e => Object.assign({}, e, { len: Math.hypot(e.bx - e.ax, e.by - e.ay) }));
  waterSegs = []; cfg.rivers.forEach(r => { for (let i = 0; i < r[2].length - 1; i++) waterSegs.push([r[2][i][0], r[2][i][1], r[2][i + 1][0], r[2][i + 1][1], r[1] / 2, r[0]]); });
  lakes = cfg.lakes.map(l => l[1]); pois = cfg.pois || [];
  nodeGrid.clear(); cfg.nodes.forEach(n => { const k = Math.floor(n.x / 1000) + ',' + Math.floor(n.y / 1000); if (!nodeGrid.has(k)) nodeGrid.set(k, []); nodeGrid.get(k).push(n); });
  streets = cfg.streets || []; houses = cfg.houses || [];
  streetGrid.clear(); streets.forEach(s => { for (let gx = Math.floor((Math.min(s[0], s[2]) - s[4]) / 1000); gx <= Math.floor((Math.max(s[0], s[2]) + s[4]) / 1000); gx++) for (let gy = Math.floor((Math.min(s[1], s[3]) - s[4]) / 1000); gy <= Math.floor((Math.max(s[1], s[3]) + s[4]) / 1000); gy++) { const k = gx + ',' + gy; if (!streetGrid.has(k)) streetGrid.set(k, []); streetGrid.get(k).push(s); } });
  houseGrid.clear(); houses.forEach(h => { const k = gkey(h.x, h.y); if (!houseGrid.has(k)) houseGrid.set(k, []); houseGrid.get(k).push(h); });
  pumps = cfg.pumps || [];
  BM = Math.round(100 * Math.max(1, (cfg.scale || 3) / 3));
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
    for (const hl of cfg.hills) { const e = ((wx - hl[1]) / hl[3]) ** 2 + ((wy - hl[2]) / hl[4]) ** 2; if (e < 1) { const m = (1 - e) * .45; col = col.map((v, i) => v + ([104, 101, 88][i] - v) * m); } }
    const n = (hash(x, y) - .5) * 8; const o = (y * w + x) * 4; img.data[o] = col[0] + n; img.data[o + 1] = col[1] + n; img.data[o + 2] = col[2] + n; img.data[o + 3] = 255;
  }
  c.putImageData(img, 0, 0);
}

function makeWorldMap() {
  const w = 1200, h = Math.round(1200 * cfg.height / cfg.width), s = w / cfg.width; worldMap = canvas(w, h); const c = worldMap.getContext('2d');
  c.imageSmoothingEnabled = true; c.drawImage(biomeMap, 0, 0, w, h); c.fillStyle = '#0e171433'; c.fillRect(0, 0, w, h);
  c.lineJoin = c.lineCap = 'round';
  cfg.rivers.forEach(r => { c.strokeStyle = '#3f6670'; c.lineWidth = Math.max(1.4, r[1] * s * 1.6); c.beginPath(); r[2].forEach((p, i) => i ? c.lineTo(p[0] * s, p[1] * s) : c.moveTo(p[0] * s, p[1] * s)); c.stroke(); });
  lakes.forEach(l => { c.fillStyle = l.length > 6 ? '#2f5560' : '#3f6670'; c.beginPath(); l.forEach((p, i) => i ? c.lineTo(p[0] * s, p[1] * s) : c.moveTo(p[0] * s, p[1] * s)); c.closePath(); c.fill(); });
  cfg.hills.forEach(hl => { c.fillStyle = '#8b8a7a'; for (let i = 0; i < 26; i++) { const a = hash(i, hl[1]) * 6.28, d = Math.sqrt(hash(hl[2], i)); const x = (hl[1] + Math.cos(a) * hl[3] * d) * s, y = (hl[2] + Math.sin(a) * hl[4] * d) * s; c.beginPath(); c.moveTo(x - 3, y + 2); c.lineTo(x, y - 3); c.lineTo(x + 3, y + 2); c.fill(); } });
  c.strokeStyle = '#d9cfa955'; c.lineWidth = 2.2; roads.forEach(r => { c.beginPath(); c.moveTo(r.ax * s, r.ay * s); c.lineTo(r.bx * s, r.by * s); c.stroke(); });
  c.strokeStyle = '#2a2b2499'; c.lineWidth = .8; roads.forEach(r => { c.setLineDash([3, 3]); c.beginPath(); c.moveTo(r.ax * s, r.ay * s); c.lineTo(r.bx * s, r.by * s); c.stroke(); }); c.setLineDash([]);

}

/* ---------- terrain chunks ---------- */
function getChunk(cx, cy) {
  const key = cx + ',' + cy; let ch = chunks.get(key);
  // A chunk painted before the car drawings loaded is painted again once they are here.
  if (ch && ch.missedCars && S.carsReady()) { chunks.delete(key); ch = null; }
  if (ch) { ch.used = performance.now(); return ch; }
  if (chunkQueue >= (R.quality === 'low' ? 1 : 2)) return null;
  chunkQueue++; chunkMissedCars = false; ch = buildChunk(cx, cy); ch.missedCars = chunkMissedCars; ch.used = performance.now(); chunks.set(key, ch);
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
    if (h1 > .16 || built(x, y, 40) || onRoad(x, y, RW / 2 + 25) || water(x, y, 20)) return;
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
      if (onRoad(fx, fy, RW / 2 + 230) || water(fx, fy, 250) || inTown(fx, fy, 260)) continue;
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
  const segs = waterSegs.filter(hitSeg), lks = lakes.filter(l => { let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; l.forEach(p => { x0 = Math.min(x0, p[0]); y0 = Math.min(y0, p[1]); x1 = Math.max(x1, p[0]); y1 = Math.max(y1, p[1]); }); return x1 > box[0] && x0 < box[2] && y1 > box[1] && y0 < box[3]; });
  const waterPts = [];
  if (segs.length || lks.length) {
    c.save(); c.beginPath(); c.rect(x0, y0, CHUNK, CHUNK); towns.forEach(t => c.rect(t.x + CORE[0], t.y - CORE[1], -CORE[0] * 2, CORE[1] * 2)); c.clip('evenodd');
    c.lineCap = c.lineJoin = 'round';
    const pass = (extra, color) => { c.strokeStyle = color; c.fillStyle = color; segs.forEach(s => { c.lineWidth = s[4] * 2 + extra; c.beginPath(); c.moveTo(s[0], s[1]); c.lineTo(s[2], s[3]); c.stroke(); }); lks.forEach(l => { c.lineWidth = extra; c.beginPath(); l.forEach((p, i) => i ? c.lineTo(p[0], p[1]) : c.moveTo(p[0], p[1])); c.closePath(); c.fill(); if (extra > 0) c.stroke(); }); };
    pass(34, '#5b5a43'); pass(20, '#6d6a4f'); pass(8, '#2e464d'); pass(0, '#2f4b55');
    c.globalAlpha = .55; segs.forEach(s => { c.strokeStyle = '#3f6670'; c.lineWidth = s[4] * 1.1; c.beginPath(); c.moveTo(s[0], s[1]); c.lineTo(s[2], s[3]); c.stroke(); }); c.globalAlpha = 1;
    for (let i = 0; i < 160; i++) { const x = x0 + r() * CHUNK, y = y0 + r() * CHUNK; if (water(x, y, -6)) { if (waterPts.length < 50) waterPts.push([x, y, r()]); c.fillStyle = '#9fc0c522'; c.fillRect(x, y, 6 + r() * 10, 1.2); } }
    for (let i = 0; i < 40; i++) { const x = x0 + r() * CHUNK, y = y0 + r() * CHUNK; if (!water(x, y) && water(x, y, 22)) { c.fillStyle = ['#4f6a3c', '#62743f'][i % 2]; c.fillRect(x, y, 2, 6); c.fillRect(x + 2, y - 2, 1.5, 7); } }
    c.restore();
  }
  // Roads with shoulders, cracks, markings, potholes; bridges over water.
  const rs = roads.filter(rd => segDist(x0 + 256, y0 + 256, rd.ax, rd.ay, rd.bx, rd.by) < 380 + RW / 2 + 60);
  c.lineCap = 'butt';
  rs.forEach(rd => { c.strokeStyle = '#6a644f'; c.lineWidth = RW + 40; line(c, rd); c.strokeStyle = '#4f4f47'; c.lineWidth = RW + 14; line(c, rd); c.strokeStyle = '#575750'; c.lineWidth = RW; line(c, rd); });
  rs.forEach(rd => {
    const ux = (rd.bx - rd.ax) / rd.len, uy = (rd.by - rd.ay) / rd.len, nx = -uy, ny = ux;
    const tc = (x0 + CHUNK / 2 - rd.ax) * ux + (y0 + CHUNK / 2 - rd.ay) * uy;
    const from = Math.max(0, tc - 560), to = Math.min(rd.len, tc + 560);
    for (let d = Math.floor(from / 40) * 40; d < to; d += 40) {
      const px = rd.ax + ux * d, py = rd.ay + uy * d, h1 = hash(d, rd.ax), h2 = hash(rd.ay, d);
      if (inTown(px, py, -30)) continue;
      if (water(px, py)) { // bridge deck
        c.fillStyle = '#7d7b72'; c.save(); c.translate(px, py); c.rotate(Math.atan2(uy, ux)); c.fillRect(-21, -RW / 2 - 16, 42, RW + 32); c.fillStyle = '#5f5e57'; c.fillRect(-21, -RW / 2 - 8, 42, RW + 16); c.fillStyle = '#9a978c'; c.fillRect(-21, -RW / 2 - 18, 42, 5); c.fillRect(-21, RW / 2 + 13, 42, 5); c.fillStyle = '#3f3e3a'; for (let k = -18; k < 21; k += 10) { c.fillRect(k, -50, 3, 8); c.fillRect(k, 42, 3, 8); } c.fillStyle = '#00000040'; c.fillRect(-21, 48, 42, 10); c.restore();
        continue;
      }
      if (h1 < .45) { c.strokeStyle = '#3d3d38'; c.lineWidth = 1; c.beginPath(); const sx = px + nx * (h2 - .5) * RW * .8, sy = py + ny * (h2 - .5) * RW * .8; c.moveTo(sx, sy); c.lineTo(sx + ux * 14 + nx * 6, sy + uy * 14 + ny * 6); c.lineTo(sx + ux * 26 - nx * 4, sy + uy * 26 - ny * 4); c.stroke(); }
      if (h1 > .9) { c.fillStyle = '#3a3a35'; c.beginPath(); c.ellipse(px + nx * (h2 - .5) * RW * .7, py + ny * (h2 - .5) * RW * .7, 6 + h2 * 6, 4 + h2 * 3, 0, 0, 7); c.fill(); c.fillStyle = '#4b5b5e66'; c.beginPath(); c.ellipse(px + nx * (h2 - .5) * RW * .7, py + ny * (h2 - .5) * RW * .7, 4 + h2 * 4, 2 + h2 * 2, 0, 0, 7); c.fill(); }
      if (Math.floor(d / 40) % 2 === 0 && h2 > .2) { c.fillStyle = '#c8bf8c77'; c.save(); c.translate(px, py); c.rotate(Math.atan2(uy, ux)); c.fillRect(0, -1.6, 26, 3.2); c.restore(); }
      c.fillStyle = '#d6d0b52a'; c.save(); c.translate(px, py); c.rotate(Math.atan2(uy, ux)); c.fillRect(0, -RW / 2 + 4, 40, 1.5); c.fillRect(0, RW / 2 - 5.5, 40, 1.5); c.restore();
      // Utility poles with sagging wires along the shoulder.
      if (Math.floor(d / 40) % 6 === 0) { const qx = px + nx * (RW / 2 + 30), qy = py + ny * (RW / 2 + 30); if (!water(qx, qy)) { c.fillStyle = '#00000040'; c.fillRect(qx + 3, qy + 2, 10, 3); c.fillStyle = '#5a4a38'; c.beginPath(); c.arc(qx, qy, 3.5, 0, 7); c.fill(); c.fillStyle = '#6e6a5e'; c.fillRect(qx - nx * 8 - 1, qy - ny * 8 - 1, nx * 16 + 2, ny * 16 + 2); } }
      if (Math.floor(d / 40) % 6 === 0) { c.strokeStyle = '#26262288'; c.lineWidth = .8; c.beginPath(); const qx = px + nx * (RW / 2 + 30), qy = py + ny * (RW / 2 + 30); c.moveTo(qx, qy); c.quadraticCurveTo(qx + ux * 120 + nx * 6, qy + uy * 120 + ny * 6, qx + ux * 240, qy + uy * 240); c.stroke(); }
    }
  });
  // Abandoned cars on the highways: the host's list, the same for everyone and solid in the game.
  roadWrecks.forEach(w => { if (Math.abs(w[0] - x0 - CHUNK / 2) > CHUNK / 2 + 70 || Math.abs(w[1] - y0 - CHUNK / 2) > CHUNK / 2 + 70) return;
    c.save(); c.translate(w[0], w[1]); c.rotate(w[2]);
    if (!w[4] && !S.carsReady()) chunkMissedCars = true;
    if (w[4] || !S.carsReady()) { const im = S.vehicle(w[4] ? 'bus' : 'wreck', ['#7c3b2f', '#56646d', '#8b7d55', '#3e4d40', '#b8b2a0', '#2d3a4f'][w[3] % 6], 2); c.drawImage(im.im, -im.ox, -im.oy); }
    else { const spec = cfg.cars[w[3]]; S.car(c, { model: w[3], len: spec.len, wid: spec.wid, damage: w[5] ? 2 : 1 }); }
    c.restore(); });
  // Trees: positions chosen here, painted later over characters (canopies are above people).
  const trees = []; const td = TREES[biome] || TREES.mixed;
  const step = 46;
  for (let gx = 0; gx < CHUNK; gx += step) for (let gy = 0; gy < CHUNK; gy += step) {
    const wx = x0 + gx + hash(gx + x0, gy) * step, wy = y0 + gy + hash(gy + y0, gx) * step;
    const tdl = TREES[biomeAt(wx, wy)] || td;
    const dens = tdl.d * (.4 + 1.2 * hash(Math.floor(wx / 700), Math.floor(wy / 700)));
    if (hash(wx, wy) > dens) continue;
    // Cities are overgrown: trees grow between the houses, thinner than in the wild.
    if (built(wx, wy, 30) || onRoad(wx, wy, RW / 2 + 40) || water(wx, wy, 28) || (inTown(wx, wy) && hash(wy, wx * 1.7) > .45)) continue;
    if (pois.some(p => Math.abs(p.x - wx) < 300 && Math.abs(p.y - wy) < 260)) continue;
    const kind = tdl.kinds[Math.floor(hash(wy, wx) * tdl.kinds.length)];
    trees.push({ x: wx, y: wy, kind, v: Math.floor(hash(wx * .3, wy) * 6) });
  }
  // Undergrowth and fallen logs stay in the chunk image.
  grid(128, 40, (x, y, h1, h2) => { if (h1 > .5 || built(x, y, 20) || onRoad(x, y, 60) || water(x, y, 10)) return; if (h2 < .82) { const b = S.tree('bush', Math.floor(h2 * 6)); c.drawImage(b.im, x - b.ox, y - b.oy); } else { c.save(); c.translate(x, y); c.rotate(h1 * 6); c.fillStyle = '#00000033'; rr(c, -18, -2, 40, 9, 4); c.fill(); c.fillStyle = '#5e4a34'; rr(c, -20, -4, 40, 8, 4); c.fill(); c.fillStyle = '#a88c64'; c.beginPath(); c.ellipse(19, 0, 3, 4, 0, 0, 7); c.fill(); c.restore(); } });
  // Settlements lie on the land itself: cracked streets, kerbs, the paved square; no ground plate.
  const sbox = [x0 - 80, y0 - 80, x0 + CHUNK + 80, y0 + CHUNK + 80];
  const sts = streets.filter(st => !(Math.max(st[0], st[2]) + st[4] < sbox[0] || Math.min(st[0], st[2]) - st[4] > sbox[2] || Math.max(st[1], st[3]) + st[4] < sbox[1] || Math.min(st[1], st[3]) - st[4] > sbox[3]));
  c.lineCap = 'butt';
  sts.forEach(st => { c.strokeStyle = '#6b6756'; c.lineWidth = st[4] + 14; line(c, { ax: st[0], ay: st[1], bx: st[2], by: st[3] }); });
  sts.forEach(st => { c.strokeStyle = st[4] > 60 ? '#4d4d46' : '#555449'; c.lineWidth = st[4]; line(c, { ax: st[0], ay: st[1], bx: st[2], by: st[3] }); });
  sts.forEach(st => {
    const len = Math.hypot(st[2] - st[0], st[3] - st[1]), ux = (st[2] - st[0]) / len, uy = (st[3] - st[1]) / len;
    const tc = (x0 + CHUNK / 2 - st[0]) * ux + (y0 + CHUNK / 2 - st[1]) * uy, from = Math.max(0, tc - 420), to = Math.min(len, tc + 420);
    for (let d = Math.floor(from / 30) * 30; d < to; d += 30) {
      const px = st[0] + ux * d, py = st[1] + uy * d, h1 = hash(px, py), h2 = hash(py, px);
      if (water(px, py)) { c.fillStyle = '#7d7b72'; c.save(); c.translate(px, py); c.rotate(Math.atan2(uy, ux)); c.fillRect(-16, -st[4] / 2 - 6, 32, st[4] + 12); c.fillStyle = '#5f5e57'; c.fillRect(-16, -st[4] / 2, 32, st[4]); c.restore(); continue; }
      // Grass breaks through the asphalt; potholes and cracks.
      if (h1 < .35) { c.fillStyle = h2 < .5 ? '#5d6b3f66' : '#00000022'; c.beginPath(); c.ellipse(px + (h2 - .5) * st[4] * .8, py + (h1 - .2) * st[4] * .8, 3 + h2 * 8, 2 + h1 * 6, h1 * 3, 0, 7); c.fill(); }
      if (h1 > .92) { c.fillStyle = '#34342f'; c.beginPath(); c.ellipse(px, py, 5 + h2 * 5, 3 + h2 * 3, 0, 0, 7); c.fill(); }
      if (st[4] > 60 && Math.floor(d / 30) % 2 === 0 && h2 > .35) { c.fillStyle = '#c8bf8c40'; c.save(); c.translate(px, py); c.rotate(Math.atan2(uy, ux)); c.fillRect(0, -1, 16, 2); c.restore(); }
    }
  });
  // Ruins of places of interest get a cracked yard.
  pois.forEach(p => { if (Math.abs(p.x - x0 - 256) > 600 || Math.abs(p.y - y0 - 256) > 600) return; const pr = rng(strSeed(p.id)); c.fillStyle = '#5e5b4d'; rr(c, p.x - 230, p.y - 170, 460, 340, 30); c.fill(); for (let i = 0; i < 60; i++) { c.fillStyle = pr() < .5 ? '#00000018' : '#4f603a88'; c.beginPath(); c.ellipse(p.x - 230 + pr() * 460, p.y - 170 + pr() * 340, 6 + pr() * 22, 4 + pr() * 12, 0, 0, 7); c.fill(); } c.strokeStyle = '#6d6252'; c.lineWidth = 2; c.setLineDash([6, 4]); c.strokeRect(p.x - 236, p.y - 176, 472, 352); c.setLineDash([]); });
  return { im, trees, waterPts };
}
// Abandoned cars: the same models as the players', burnt out and rusting.
function wreck(c, h, bus) {
  if (bus || !S.carsReady()) { const v = S.vehicle(bus ? 'bus' : 'wreck', ['#7c3b2f', '#56646d', '#8b7d55', '#3e4d40', '#b8b2a0', '#2d3a4f'][Math.floor(h * 6)], 2); c.drawImage(v.im, -v.ox, -v.oy); return; }
  const m = Math.floor(h * 97) % cfg.cars.length, spec = cfg.cars[m]; S.car(c, { model: m, len: spec.len, wid: spec.wid, damage: h > .5 ? 2 : 1 });
}
function line(c, rd) { c.beginPath(); c.moveTo(rd.ax, rd.ay); c.lineTo(rd.bx, rd.by); c.stroke(); }

/* ---------- particles ---------- */
function puff(kind, x, y, vx, vy, life, size, color) { if (particles.length > (R.quality === 'low' ? 160 : 480)) particles.shift(); particles.push({ kind, x, y, vx, vy, life, max: life, size, color }); }
function updateParticles(dt) {
  for (let i = particles.length - 1; i >= 0; i--) { const p = particles[i]; p.life -= dt; if (p.life <= 0) { particles.splice(i, 1); continue; } p.x += p.vx * dt; p.y += p.vy * dt; if (p.kind === 'smoke') { p.vx += 6 * dt; p.size += dt * 5; } if (p.kind === 'spark' || p.kind === 'debris') { p.vx *= .92; p.vy *= .92; } if (p.kind === 'flame') p.size *= .985; if (p.kind === 'shell') { const k = Math.pow(.02, dt); p.vx *= k; p.vy *= k; p.spin = (p.spin || 0) + Math.hypot(p.vx, p.vy) * dt * .3; } }
}
function drawParticles(c, layer) {
  for (const p of particles) {
    const k = p.life / p.max;
    const low = p.kind === 'dust' || p.kind === 'debris' || p.kind === 'blood' || p.kind === 'shell';
    if (layer === 'low' && !low) continue;
    if (layer === 'high' && low) continue;
    if (p.kind === 'shell') { c.save(); c.translate(p.x, p.y); c.rotate(p.spin || 0); c.fillStyle = '#c9a24a'; c.fillRect(-1.6, -.8, 3.2, 1.6); c.restore(); continue; }
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
    else if (e.kind === 'fall') { for (let i = 0; i < 8; i++) puff('blood', e.x + (Math.random() - .5) * 10, e.y + (Math.random() - .5) * 10, 0, 0, 30, 2 + Math.random() * 3); }
    else if (e.kind === 'bite') { for (let i = 0; i < 6; i++) puff('blood', e.ex + (Math.random() - .5) * 16, e.ey + (Math.random() - .5) * 16, 0, 0, 12, 1.5 + Math.random() * 2); if (R.onSound) R.onSound('bite', near); }
    else if (e.kind === 'crash') { const k = e.power || .3; for (let i = 0; i < 6 + k * 14; i++) { const a = Math.random() * 6.28, s = 60 + Math.random() * 140; puff('spark', e.x, e.y, Math.cos(a) * s, Math.sin(a) * s, .35, 1); puff('debris', e.x, e.y, Math.cos(a) * s * .6, Math.sin(a) * s * .6, .8, 2, i % 2 ? '#3d3a35' : '#8a9496'); } puff('dust', e.x, e.y, 0, 0, 1, 14, '#8d8673'); if (R.onSound) R.onSound('crash', near); }
    else if (e.kind === 'acid') { for (let i = 0; i < 8; i++) puff('smoke', e.ex, e.ey, (Math.random() - .5) * 40, (Math.random() - .5) * 40, .8, 5, '#9cc23e'); if (R.onSound) R.onSound('acid', near); }
    else if (e.kind === 'swing') { if (R.onSound) R.onSound('swing', near); }
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
  drawParticles(c, 'low');
  // Depth-sorted scene: ruins, nodes, loot, cars, people, infected.
  const items = [];
  pois.forEach(p => { if (!vis(p.x, p.y, 900)) return; p.parts.forEach((part, i) => { if (!vis(part.x, part.y, Math.max(part.w, part.h))) return; const flat = part.sprite === 'runway' || part.sprite === 'pump'; items.push({ y: flat ? -1e9 + part.y : part.y + part.h / 2, f: () => { const sp = S.ruin(part.sprite, part.w, part.h, strSeed(p.id) + i * .13); c.drawImage(sp.im, part.x - sp.ox, part.y - sp.oy); } }); }); });
  const gx0 = Math.floor((cam.x - cw / 2 - 100) / 1000), gx1 = Math.floor((cam.x + cw / 2 + 100) / 1000), gy0 = Math.floor((cam.y - ch / 2 - 100) / 1000), gy1 = Math.floor((cam.y + ch / 2 + 100) / 1000);
  for (let gx = gx0; gx <= gx1; gx++) for (let gy = gy0; gy <= gy1; gy++) (nodeGrid.get(gx + ',' + gy) || []).forEach(n => { if (!vis(n.x, n.y, 60) || (state && state.harvested && state.harvested[n.id] > state.time)) return; items.push({ y: n.y, f: () => { const sp = S.node(n.kind, Math.floor(hash(n.x, n.y) * 3)); c.drawImage(sp.im, n.x - sp.ox, n.y - sp.oy); if (v.nearest && v.nearest.obj === n) ring(c, n.x, n.y + 8, 30, 15); } }); });
  if (state) {
    // Houses: floors go under everyone, roofs sort with the scene by their south edge.
    const hx0 = Math.floor((cam.x - cw / 2 - 300) / 1000), hx1 = Math.floor((cam.x + cw / 2 + 300) / 1000), hy0 = Math.floor((cam.y - ch / 2 - 300) / 1000), hy1 = Math.floor((cam.y + ch / 2 + 300) / 1000);
    for (let gx = hx0; gx <= hx1; gx++) for (let gy = hy0; gy <= hy1; gy++) (houseGrid.get(gx + ',' + gy) || []).forEach(h => { if (!vis(h.x, h.y, Math.max(h.w, h.h))) return; drawHouse(c, h, v, 'floor'); items.push({ y: h.y + h.h / 2 + 2, f: () => drawHouse(c, h, v, 'roof') }); });
    (state.camps || []).forEach(camp => {
      if (!vis(camp.x, camp.y, 300)) return;
      Object.keys(camp.fence).forEach(k => { const piece = camp.fence[k]; items.push({ y: piece.y + piece.h / 2, f: () => drawFence(c, piece, camp, v) }); });
      Object.keys(camp.parts).forEach(k => { const part = camp.parts[k]; const house = camp.house; items.push({ y: house ? part.y - 400 : part.y, f: () => drawCampPart(c, k, part, camp, v) }); });
    });
    // Things on the ground lie under feet and under roofs (a roof hides what is inside until you step in).
    (state.loot || []).forEach(l => { if (!vis(l.x, l.y, 30)) return; items.push({ y: l.y - 30, f: () => drawLoot(c, l, v) }); });
    (state.bodies || []).forEach(b => { if (vis(b.x, b.y)) items.push({ y: b.y - 20, f: () => drawBody(c, b, v) }); });
    drawSkids(c, now, vis);
    const drawCars = v.drawCars || {};
    (state.cars || []).forEach(car => {
      const r = drawCars[car.id], at = r ? Object.assign({}, car, { x: r.x, y: r.y, angle: r.ang != null ? r.ang : car.angle }) : car;
      if (!vis(at.x, at.y)) return;
      const road = R.onRoad(at.x, at.y, RW / 2 + 10) || R.inTown(at.x, at.y), snow = R.coldAt(at.x, at.y) >= 2;
      items.push({ y: at.y, f: () => drawCar(c, at, r, now, dt, { damage: car.wrecked ? 2 : car.hp < 50 ? 1 : 0, engine: !!car.driver && !car.wrecked, door: (r && r.door) || 0, road, snow }) });
      if (v.carNear && v.carNear.car.id === car.id && !v.nearest) items.push({ y: at.y + 1, f: () => ring(c, at.x, at.y, carSpec(car).len * .62, carSpec(car).wid * .8) });
    });
    state.players.forEach(p => {
      const r = v.drawPlayers[p.id]; if (!r) return;
      if (p.vehicle) r.carId = p.car;
      if (r.inCar !== p.vehicle) { if (r.inCar != null) { r.carAt = now; r.carFrom = { x: r.footX != null ? r.footX : r.x, y: r.footY != null ? r.footY : r.y }; } r.inCar = p.vehicle; }
      if (!p.vehicle) { r.footX = r.x; r.footY = r.y; }
      const since = r.carAt ? now - r.carAt : 99, entering = p.vehicle && since < ENTER_TIME, leaving = !p.vehicle && since < EXIT_TIME;
      if (entering || leaving) {
        const car = (state.cars || []).find(k => k.id === r.carId), dr = car && drawCars[car.id]; if (!car) return;
        const acar = Object.assign({}, car, dr ? { x: dr.x, y: dr.y, angle: dr.ang != null ? dr.ang : car.angle } : {}), aspec = carSpec(car), sideSign = p.seat === 'passenger' || (leaving && car.driver && car.driver !== p.id) ? -1 : 1;
        const out = doorSpot(acar, aspec, false, sideSign), seat = doorSpot(acar, aspec, true, sideSign);
        if (dr && sideSign > 0) dr.door = entering ? Math.sin(Math.min(1, Math.max(0, (since - .12) / (ENTER_TIME - .12))) * Math.PI) : Math.sin(Math.min(1, since / EXIT_TIME) * Math.PI);
        let pos, alpha = 1, face = acar.angle, walk = false;
        if (entering) {
          const k1 = Math.min(1, since / .25), k2 = Math.max(0, (since - .25) / (ENTER_TIME - .25)), from = r.carFrom || out;
          pos = k2 > 0 ? { x: out.x + (seat.x - out.x) * k2, y: out.y + (seat.y - out.y) * k2 } : { x: from.x + (out.x - from.x) * k1, y: from.y + (out.y - from.y) * k1 };
          alpha = 1 - k2; walk = k2 === 0; face = k2 > 0 ? acar.angle : Math.atan2(out.y - from.y, out.x - from.x);
        } else {
          const k = Math.max(0, Math.min(1, (since - .12) / (EXIT_TIME - .2)));
          pos = { x: seat.x + (out.x - seat.x) * k, y: seat.y + (out.y - seat.y) * k }; alpha = since < .12 ? 0 : Math.min(1, k * 1.6); face = acar.angle - sideSign * (Math.PI / 2 * (1 - k) + .3 * k);
        }
        if (alpha > .02) items.push({ y: acar.y + 1, f: () => { c.save(); c.globalAlpha = alpha; c.translate(pos.x, pos.y); c.rotate(face); S.figure(c, { player: true, tint: col(p.faction), size: 38, phase: walk ? now * 7 : 0, speed: walk ? 1 : 0, weapon: p.gear ? p.gear.weapon : 0, time: now }); c.restore(); } });
      } else {
        const dr = r.carId && drawCars[r.carId]; if (dr) dr.door = 0;
        if (!p.vehicle && vis(r.x, r.y)) items.push({ y: r.y, f: () => drawPlayer(c, p, r, v) });
      }
    });
    (state.npcs || []).forEach(n => { const r = v.drawNpcs[n.id] || n; if (!vis(r.x, r.y)) return; items.push({ y: r.y, f: () => drawNpc(c, n, r, v) }); });
  } else { items.push({ y: 0, f: () => drawCar(c, { x: cam.x + 90, y: cam.y + 25, angle: -.4, model: 3 }, null, now, dt, {}) }); }
  items.sort((a, b) => a.y - b.y).forEach(i => i.f());
  // Tracers.
  if (state) state.effects.forEach(e => { if (e.kind !== 'shot' && e.kind !== 'tower' && e.kind !== 'acid') return; const k = Math.max(0, (e.until - state.time) / .22); if (e.kind === 'acid') { c.strokeStyle = '#b9e04a' + Math.floor(Math.min(1, k) * 200).toString(16).padStart(2, '0'); c.lineWidth = 4; c.setLineDash([4, 6]); c.beginPath(); c.moveTo(e.x, e.y); c.lineTo(e.ex, e.ey); c.stroke(); c.setLineDash([]); return; } c.strokeStyle = (e.kind === 'tower' ? '#ffcf7a' : '#f8e3a8') + Math.floor(k * 220).toString(16).padStart(2, '0'); c.lineWidth = 1.6; c.beginPath(); c.moveTo(e.x, e.y); c.lineTo(e.ex, e.ey); c.stroke(); });
  // Canopies over everything on the ground; trees near the player become see-through.
  const me = state && v.drawPlayers[state.me.id];
  // Trees inside a camp were cut down when it was founded.
  const clearings = (state && state.camps || []).filter(cp => !cp.house && vis(cp.x, cp.y, 300));
  visibleChunks.forEach(k => k.trees.forEach(t => { if (!vis(t.x, t.y, 80)) return; if (clearings.some(cp => Math.abs(cp.x - t.x) < 130 && Math.abs(cp.y - t.y) < 130)) return; const sp = S.tree(t.kind, t.v); const near = me && Math.abs(me.x - t.x) < 44 && Math.abs(me.y - t.y) < 44; if (near) c.globalAlpha = .38; const sway = Math.sin(now * 1.2 + t.x * .01) * (state && state.weather.kind === 'storm' ? 2.5 : .8); c.drawImage(sp.im, t.x - sp.ox + sway, t.y - sp.oy); if (near) c.globalAlpha = 1; }));
  // Chimney smoke from working production and fires.
  if (state) emitters(c, state, v, dt, vis);
  updateParticles(dt); drawParticles(c, 'high');
  if (state) effectsFrom(state, v);
  if (state) labels(c, state, v, vis);
  c.restore();
  if (state) { lights(c, v, vis); weather(c, v, dt, now); }
};

function ring(c, x, y, rx, ry) { c.strokeStyle = '#e7ae6b'; c.lineWidth = 1.2; c.setLineDash([4, 3]); c.beginPath(); c.ellipse(x, y, rx, ry, 0, 0, 7); c.stroke(); c.setLineDash([]); }
// A thing on the ground: its icon, a faint glint so it can be found, a ring when it is the nearest.
function drawLoot(c, l, v) {
  const near = v.nearest && v.nearest.type === 'loot' && v.nearest.obj.id === l.id, big = /^w_/.test(l.item) || (cfg.items[l.item] && cfg.items[l.item].gear);
  const size = big ? 34 : 24, a = strSeed(l.id) * 6.28;
  c.save(); c.translate(l.x, l.y); c.rotate(big ? a * .3 - .3 : a * .15);
  c.fillStyle = '#0a0f0b44'; c.beginPath(); c.ellipse(2, 3, size * .42, size * .3, 0, 0, 7); c.fill();
  S.lootIcon(c, l.item, size);
  c.restore();
  const g = .5 + .5 * Math.sin(v.now * 2.2 + a);
  if (g > .93) { c.fillStyle = '#fff6d8' + Math.floor((g - .93) / .07 * 200).toString(16).padStart(2, '0'); c.fillRect(l.x - 1, l.y - size * .3, 2, 2); }
  if (near) ring(c, l.x, l.y + 2, size * .7, size * .5);
}
// Tyre marks left by skids and hard braking; they fade over half a minute.
const skids = [];
function carSpec(car) { return (cfg.cars || [])[car.model != null ? car.model : 2] || { len: 92, wid: 50, door: .12, color: '#777', max: 400 }; }
function carFwd(car) { return (car.vx || 0) * Math.cos(car.angle) + (car.vy || 0) * Math.sin(car.angle); }
function drawSkids(c, now, vis) {
  while (skids.length && now - skids[0][4] > 30) skids.shift();
  c.lineCap = 'round'; c.lineWidth = 4;
  for (const s of skids) { if (!vis(s[0], s[1], 60)) continue; c.strokeStyle = 'rgba(22,20,18,' + (.32 * (1 - (now - s[4]) / 30)) + ')'; c.beginPath(); c.moveTo(s[0], s[1]); c.lineTo(s[2], s[3]); c.stroke(); }
}
// A player's car: the body pitches under braking and acceleration, rolls in turns and shakes at idle.
function drawCar(c, car, r, now, dt, o) {
  o = o || {};
  const spec = carSpec(car), damage = o.damage || 0, fwd = carFwd(car), speed = Math.hypot(car.vx || 0, car.vy || 0);
  const st = r ? (r.carState = r.carState || { pitch: 0, roll: 0, prevFwd: fwd, wheels: null }) : { pitch: 0, roll: 0, prevFwd: fwd };
  const acc = (fwd - st.prevFwd) / Math.max(dt, .001); st.prevFwd = fwd;
  st.pitch += (Math.max(-1, Math.min(1, -acc / 500)) - st.pitch) * Math.min(1, dt * 8);
  st.roll += (Math.max(-1, Math.min(1, (car.steer || 0) * fwd / 160)) - st.roll) * Math.min(1, dt * 6);
  const idle = o.engine && speed < 15 && damage < 2, shake = idle ? Math.sin(now * 60) * .35 : speed > 40 && o.engine ? Math.sin(now * 37) * Math.min(.6, speed / 900) * (o.road ? .3 : 1) : 0;
  c.save(); c.translate(car.x, car.y); c.rotate(car.angle);
  c.translate(st.pitch * 1.6 + shake * .4, st.roll * 2.2 + shake);
  S.car(c, { model: car.model != null ? car.model : 2, len: spec.len, wid: spec.wid, damage, door: o.door || 0, doorAt: spec.door, color: spec.color, brake: o.engine && car.brake && fwd > 5, reverse: o.engine && fwd < -5 });
  c.restore();
  if (!o.engine || damage === 2) { if (damage === 2 && Math.random() < .3) puff('smoke', car.x, car.y, 4, -12, 2, 6, '#2f2c28'); return; }
  const hx = Math.cos(car.angle), hy = Math.sin(car.angle), rear = spec.len / 2 - 6;
  // Rear wheels: skid marks when sliding or braking hard.
  const wheels = [-1, 1].map(sd => [car.x - hx * (rear - 10) - hy * sd * spec.wid * .36, car.y - hy * (rear - 10) + hx * sd * spec.wid * .36]);
  if (st.wheels && (car.slip || (car.brake && speed > 140)) && (o.road || Math.random() < .5)) wheels.forEach((w, i) => { skids.push([st.wheels[i][0], st.wheels[i][1], w[0], w[1], now]); if (skids.length > 900) skids.shift(); });
  st.wheels = wheels;
  if (Math.random() < (speed > 30 ? .55 : .2)) puff('smoke', car.x - hx * (rear + 4), car.y - hy * (rear + 4), -hx * 14, -hy * 14 - 4, 1.1 + Math.random() * .5, 2.5 + Math.min(4, Math.abs(st.pitch) * 6), '#77746c');
  if (speed > 60) {
    const k = Math.min(1, speed / 350), kind = o.snow ? '#e6ebec' : o.road ? '#8c887a' : '#9d927a';
    if (Math.random() < (o.road ? .25 : .8) * k) wheels.forEach(w => puff('dust', w[0], w[1], -hx * 30 + (Math.random() - .5) * 30, -hy * 30 + (Math.random() - .5) * 30, .7 + k * .6, 4 + k * 6, kind));
  }
  if (damage === 1 && Math.random() < .25) puff('smoke', car.x + hx * spec.len * .35, car.y + hy * spec.len * .35, 4, -14, 1.6, 5, '#4a4640');
}
// Getting in and out: walk to the driver's door, it opens, the hero slides into the seat (and back out).
// Passengers (sideSign -1) use the right-hand rear door.
function doorSpot(car, spec, inside, sideSign) {
  const s = sideSign || 1, hx = Math.cos(car.angle), hy = Math.sin(car.angle), lx = hy * s, ly = -hx * s, side = inside ? spec.wid * .16 : spec.wid / 2 + 14, f = s < 0 ? -spec.len * .12 : spec.door * spec.len * (inside ? .6 : 1);
  return { x: car.x + lx * side + hx * f, y: car.y + ly * side + hy * f };
}
const ENTER_TIME = .55, EXIT_TIME = .5;
// Per-weapon recoil (figure pixels the arms travel back) and how far shells fly.
const KICK = [2.5, 5, 2, 6, 3.5, 6, 2.2];
// Animation state that only the client needs: kept on the interpolated record r.
function animState(r, ent, now, dt, aimTarget) {
  if (ent.hp < (r.hpSeen != null ? r.hpSeen : ent.hp) - .5) { r.hitAt = now; if (ent.hp > 0) for (let i = 0; i < 3; i++) puff('blood', r.x + (Math.random() - .5) * 12, r.y + (Math.random() - .5) * 12, 0, 0, 14, 1.2 + Math.random() * 1.8); }
  if (ent.hp <= 0 && !(r.hpSeen <= 0)) r.deadAt = r.hpSeen == null ? now - 1 : now;
  if (ent.hp > 0) r.deadAt = null;
  r.hpSeen = ent.hp;
  if (ent.shot !== r.shotSeen) { if (r.shotSeen != null && ent.shot > 0) { r.shotAt = now; r.shells = (r.shells || 0) + 1; } r.shotSeen = ent.shot; }
  r.aimK = (r.aimK || 0) + (aimTarget - (r.aimK || 0)) * Math.min(1, dt * 11);
  return { kick: r.shotAt ? Math.max(0, 1 - (now - r.shotAt) / .13) : 0, hit: r.hitAt ? Math.max(0, 1 - (now - r.hitAt) / .25) : 0,
    dead: ent.hp <= 0 ? (r.deadAt != null ? Math.min(1, (now - r.deadAt) / .9) : 1) : 0 };
}
function ejectShell(r, ang, weapon) {
  if (!r.shells) return; r.shells = 0; if (weapon === 1 || weapon === 3) return;      // break-action guns keep their shells
  const side = ang + Math.PI / 2, sp = 70 + Math.random() * 40;
  puff('shell', r.x + Math.cos(ang) * 10, r.y + Math.sin(ang) * 10, Math.cos(side) * sp + (Math.random() - .5) * 20, Math.sin(side) * sp + (Math.random() - .5) * 20, 3.5, 1);
}
function drawPlayer(c, p, r, v) {
  const isMe = v.state && p.id === v.state.me.id, t = v.state.time, now = v.now;
  const ang = isMe && !p.vehicle ? Math.atan2(v.aim.y, v.aim.x) : (r.ang != null ? r.ang : p.angle);
  const a = animState(r, p, now, v.dt, (isMe && v.holdAim) || t - p.shot < 1.2 || p.reload > t ? 1 : 0);
  if (p.act && p.act.at !== r.actAt) { r.actAt = p.act.at; r.actStart = now - Math.max(0, Math.min(.3, t - p.act.at)); r.actKind = p.act.kind; }
  let act = r.actKind ? { kind: r.actKind, t: now - r.actStart } : null;
  // Standing next to an own construction site, the hero keeps hammering.
  if ((!act || act.t > 2.5) && !p.moving && p.hp > 0 && r.buildNear) act = { kind: 'hammer', t: now % 1.2 };
  ejectShell(r, ang, p.gear ? p.gear.weapon : 0);
  // The axe bites in: chips fly from in front of the feet.
  if (act && act.kind === 'chop' && act.t > .62 && act.t < 1.1 && r.chipAt !== r.actAt) {
    r.chipAt = r.actAt; const fx = r.x + Math.cos(ang) * 17, fy = r.y + Math.sin(ang) * 17;
    for (let i = 0; i < 7; i++) { const a = ang + (Math.random() - .5) * 3.6, sp = 40 + Math.random() * 70; puff('debris', fx, fy, Math.cos(a) * sp, Math.sin(a) * sp, .5 + Math.random() * .3, 1.5 + Math.random() * 1.5, i % 3 ? '#c9a46a' : '#7a5a36'); }
  }
  // The pick strikes further out: stone grit, a few sparks and a little dust.
  if (act && act.kind === 'mine' && act.t > .84 && act.t < 1.3 && r.chipAt !== r.actAt) {
    r.chipAt = r.actAt; const fx = r.x + Math.cos(ang) * 23, fy = r.y + Math.sin(ang) * 23;
    for (let i = 0; i < 8; i++) { const a = ang + (Math.random() - .5) * 3.8, sp = 35 + Math.random() * 60; puff('debris', fx, fy, Math.cos(a) * sp, Math.sin(a) * sp, .45 + Math.random() * .3, 1.2 + Math.random() * 1.6, i % 3 ? '#8f8b82' : '#5d5a54'); }
    for (let i = 0; i < 3; i++) { const a = ang + (Math.random() - .5) * 2.4, sp = 70 + Math.random() * 60; puff('spark', fx, fy, Math.cos(a) * sp, Math.sin(a) * sp, .22, 1); }
    puff('dust', fx, fy, 0, 0, .7, 6, '#8d8673');
  }
  // Stepping out of the car fades in; climbing in fades out (drawn by the caller while gliding to the car).
  const fade = r.carAt ? Math.min(1, (now - r.carAt) / .3) : 1;
  const w = p.gear ? p.gear.weapon : 0;
  c.save(); c.translate(r.x, r.y); c.rotate(a.dead ? (r.deadAng != null ? r.deadAng : (r.deadAng = ang)) : ang); if (a.dead === 0) r.deadAng = null;
  if (fade < 1) c.globalAlpha = r.inCar ? 1 - fade : fade;
  S.figure(c, { player: true, tint: col(p.faction), size: 38, phase: r.phase || 0, speed: p.moving ? (p.sprint ? 2 : 1) : 0, aim: r.aimK, kick: a.kick, kickLen: KICK[w], weapon: w, flash: t - p.shot < .07, hit: a.hit, dead: a.dead, fall: strSeed(p.id) > .5 ? 'front' : 'back', act, reloadTime: (cfgWeapons()[w] || {}).reload, time: now });
  c.restore();
  if (a.dead) return;
  const mx = p.max_hp || 100; if (p.hp < mx) { c.fillStyle = '#18271fcc'; c.fillRect(r.x - 18, r.y + 22, 36, 4); c.fillStyle = p.hp > mx * .4 ? '#9cc28c' : '#d27a5e'; c.fillRect(r.x - 18, r.y + 22, 36 * p.hp / mx, 4); }
  if (isMe && p.reload > t) { const wd = cfgWeapons()[w], k = 1 - (p.reload - t) / ((r.actKind === 'swap' ? .5 : wd.reload) || 1); c.strokeStyle = '#d9cfae'; c.lineWidth = 2; c.beginPath(); c.arc(r.x, r.y, 26, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(0, Math.min(1, k))); c.stroke(); }
}
function cfgWeapons() { return cfg.weapons || []; }
const CREATURES = { wolf: 1, bear: 1, boar: 1, elk: 1 };
// Which of the three looks an infected wears: soldiers in olive, some civilians in workers' orange.
function infLook(n) { return n.type === 'infected_soldier' ? 'military' : (n.look || 0) % 3 === 1 ? 'worker' : 'civil'; }
const INF_ATTACKS = ['attack_swipe', 'attack_lunge', 'attack_grab'];
function drawNpc(c, n, r, v) {
  const t = v.state.time, a = animState(r, n, v.now, v.dt, 0), dead = n.hp <= 0;
  if (CREATURES[n.type]) {
    // Predators lunge and pull back; the bite lands at the far point.
    const lunge = r.shotAt ? Math.sin(Math.min(1, (v.now - r.shotAt) / .32) * Math.PI) * (n.type === 'wolf' ? 10 : n.type === 'bear' ? 7 : 6) : 0;
    c.save(); c.translate(r.x, r.y); c.rotate(r.ang != null ? r.ang : n.angle); if (a.hit) c.translate(-a.hit * 3, 0);
    S.creature(c, { type: n.type, phase: (r.phase || 0) * (n.type === 'elk' || n.type === 'wolf' ? 1.4 : 1), moving: r.moving, attack: t - n.shot < .25, lunge, dead: a.dead });
    c.restore();
    if (!dead && n.hp < n.max) bar(c, r.x, r.y + (n.type === 'bear' ? 34 : 24), n.hp / n.max, '#c9a36a');
    return;
  }
  // The infected: shuffling, running at you, swiping; they fall the way the blow sends them.
  const attackT = v.now - (r.shotAt || -9), seed = strSeed(n.id);
  const anim = attackT < .6 ? INF_ATTACKS[Math.floor((seed * 7 + (r.shells || 0)) % 3)] : r.moving ? (n.run || r.sp > 120 ? 'run' : 'walk') : 'idle';
  if (r.shells) r.shells = 0;
  c.save(); c.translate(r.x, r.y); c.rotate(a.dead ? (r.deadAng != null ? r.deadAng : (r.deadAng = r.ang || n.angle)) : (r.ang != null ? r.ang : n.angle)); if (a.hit) c.translate(-a.hit * 4, 0);
  if (!S.infected(c, { anim, t: anim === 'idle' ? v.now + seed * 5 : attackT, phase: (r.phase || 0) * (anim === 'run' ? .8 : 1.1), look: infLook(n), size: n.type === 'infected_soldier' ? 40 : 38, dead: a.dead, fall: seed > .5 ? 'front' : 'back' }))
    S.figure(c, { look: n.look || 0, size: 38, phase: r.phase || 0, speed: r.moving ? 1 : 0, hit: a.hit, dead: a.dead, time: v.now });
  c.restore();
  if (!dead && n.hp < n.max) bar(c, r.x, r.y + 24, n.hp / n.max, '#b07a52');
}
/* ---------- abandoned houses: walls with a doorway, a floor, and a roof that clears when you step in ---------- */
const houseCache = new Map();
function houseWalls(h) {
  const x0 = -h.w / 2, y0 = -h.h / 2, x1 = h.w / 2, y1 = h.h / 2, W = 8, D = 28, out = [];
  const wall = (ax, ay, bx, by) => out.push([ax, ay, Math.max(W, bx - ax), Math.max(W, by - ay)]);
  [['n', x0, y0, x1, y0 + W], ['s', x0, y1 - W, x1, y1], ['w', x0, y0, x0 + W, y1], ['e', x1 - W, y0, x1, y1]].forEach(([side, ax, ay, bx, by]) => {
    if (side !== h.door) { wall(ax, ay, bx, by); return; }
    if (side === 'n' || side === 's') { wall(ax, ay, -D / 2, by); wall(D / 2, ay, bx, by); } else { wall(ax, ay, bx, -D / 2); wall(ax, D / 2, bx, by); }
  });
  return out;
}
function houseSprites(h) {
  let hs = houseCache.get(h.id); if (hs) return hs;
  const r = rng(strSeed(h.id)), pad = 10, w = h.w + pad * 2, hh = h.h + pad * 2;
  const floor = canvas(w, hh), f = floor.getContext('2d'); f.translate(w / 2, hh / 2);
  const wood = h.kind === 'izba', panel = h.kind === 'panel';
  f.fillStyle = '#00000040'; f.fillRect(-h.w / 2 + 4, -h.h / 2 + 5, h.w, h.h);
  f.fillStyle = wood ? '#5e4a33' : panel ? '#6f6d64' : '#6a5a4a'; f.fillRect(-h.w / 2, -h.h / 2, h.w, h.h);
  f.strokeStyle = '#00000022'; f.lineWidth = 1; if (wood) for (let y = -h.h / 2 + 6; y < h.h / 2; y += 6) { f.beginPath(); f.moveTo(-h.w / 2, y); f.lineTo(h.w / 2, y); f.stroke(); }
  for (let i = 0; i < h.w * h.h / 400; i++) { f.fillStyle = ['#3d3a33', '#7d7462', '#4a3c2c', '#8a8172'][i % 4]; f.fillRect((r() - .5) * (h.w - 16), (r() - .5) * (h.h - 16), 2 + r() * 4, 2 + r() * 3); }
  const wallCol = wood ? '#4a3826' : panel ? '#8f8c82' : '#8a5a44';
  houseWalls(h).forEach(([x, y, ww, wh]) => { f.fillStyle = wallCol; f.fillRect(x, y, ww, wh); f.fillStyle = '#ffffff18'; f.fillRect(x, y, ww, Math.min(2, wh)); });
  const roof = canvas(w, hh), c = roof.getContext('2d'); c.translate(w / 2, hh / 2);
  c.fillStyle = '#00000044'; c.fillRect(-h.w / 2 + 5, -h.h / 2 + 7, h.w + 2, h.h + 2);
  if (panel) {
    // Flat roof of a five-storey block: bitumen patches, a parapet, stairwell hatches.
    c.fillStyle = '#7f7d74'; c.fillRect(-h.w / 2 - 2, -h.h / 2 - 2, h.w + 4, h.h + 4); c.fillStyle = '#6b6961'; c.fillRect(-h.w / 2 + 3, -h.h / 2 + 3, h.w - 6, h.h - 6);
    for (let i = 0; i < 10; i++) { c.fillStyle = r() < .5 ? '#55534c' : '#77756c'; c.beginPath(); c.ellipse((r() - .5) * h.w * .8, (r() - .5) * h.h * .8, 4 + r() * 12, 3 + r() * 7, r() * 3, 0, 7); c.fill(); }
    const long = h.w > h.h, n = 2 + Math.floor(r() * 2); for (let i = 0; i < n; i++) { const k = (i + .5) / n - .5; c.fillStyle = '#4c4a44'; c.fillRect(long ? k * h.w - 6 : -6, long ? -6 : k * h.h - 6, 12, 12); c.fillStyle = '#9a978c'; c.fillRect(long ? k * h.w - 6 : -6, long ? -6 : k * h.h - 6, 12, 3); }
  } else {
    // Pitched roof along the long side: planks or slate, sagging, with holes.
    const long = h.w >= h.h, col = wood ? '#5c4b39' : '#666a66';
    c.fillStyle = col; c.fillRect(-h.w / 2 - 4, -h.h / 2 - 4, h.w + 8, h.h + 8);
    c.fillStyle = shade(col, -.18); if (long) c.fillRect(-h.w / 2 - 4, 0, h.w + 8, h.h / 2 + 4); else c.fillRect(0, -h.h / 2 - 4, h.w / 2 + 4, h.h + 8);
    c.strokeStyle = '#00000030'; c.lineWidth = 1; for (let k = -h.w / 2; k < h.w / 2; k += 5) { if (long) { c.beginPath(); c.moveTo(k, -h.h / 2 - 4); c.lineTo(k, h.h / 2 + 4); c.stroke(); } }
    c.strokeStyle = shade(col, .2); c.lineWidth = 2; c.beginPath(); if (long) { c.moveTo(-h.w / 2 - 4, 0); c.lineTo(h.w / 2 + 4, 0); } else { c.moveTo(0, -h.h / 2 - 4); c.lineTo(0, h.h / 2 + 4); } c.stroke();
    c.fillStyle = '#7a6f62'; c.fillRect(h.w * .2, -h.h * .3, 7, 7);
    for (let i = 0; i < 1 + Math.floor(r() * 3); i++) { c.fillStyle = '#1d1a16'; c.beginPath(); c.ellipse((r() - .5) * h.w * .7, (r() - .5) * h.h * .6, 4 + r() * 6, 3 + r() * 4, r() * 3, 0, 7); c.fill(); }
    c.fillStyle = '#5d6b3f66'; for (let i = 0; i < 6; i++) { c.beginPath(); c.arc((r() - .5) * h.w, (r() - .5) * h.h, 2 + r() * 4, 0, 7); c.fill(); }
  }
  hs = { floor, roof, ox: w / 2, oy: hh / 2 }; houseCache.set(h.id, hs); if (houseCache.size > 500) houseCache.delete(houseCache.keys().next().value);
  return hs;
}
function drawHouse(c, h, v, layer) {
  const hs = houseSprites(h);
  if (layer === 'floor') { c.drawImage(hs.floor, h.x - hs.ox, h.y - hs.oy); return; }
  const me = v.state && v.drawPlayers[v.state.me.id], inside = me && Math.abs(me.x - h.x) < h.w / 2 + 6 && Math.abs(me.y - h.y) < h.h / 2 + 6;
  c.globalAlpha = inside ? .12 : 1; c.drawImage(hs.roof, h.x - hs.ox, h.y - hs.oy); c.globalAlpha = 1;
}
/* ---------- camps: a palisade with a gate, a fire, a bed, a crate, a workbench, a rain barrel ---------- */
function drawFence(c, piece, camp, v) {
  if (piece.house) return;                     // a house camp uses the house's own walls
  c.save(); c.translate(piece.x, piece.y);
  const broken = piece.hp <= 0, horiz = piece.w > piece.h, len = horiz ? piece.w : piece.h;
  if (!horiz) c.rotate(Math.PI / 2);
  if (broken) { const r = rng(strSeed(camp.id + piece.x)); for (let i = 0; i < 8; i++) { c.fillStyle = '#5a4630'; c.save(); c.translate((r() - .5) * len, (r() - .5) * 14); c.rotate(r() * 3); c.fillRect(-8, -2, 16, 4); c.restore(); } c.restore(); return; }
  c.fillStyle = '#00000040'; c.fillRect(-len / 2 + 3, -3, len, 10);
  if (piece.kind === 'gate') {
    c.fillStyle = '#6b5236'; c.fillRect(-len / 2, -5, len, 10); c.fillStyle = '#4a3a28'; for (let k = -len / 2; k < len / 2; k += 7) c.fillRect(k, -5, 1.5, 10);
    c.fillStyle = '#7d8183'; c.fillRect(-len / 2, -5, len, 2); c.fillRect(-len / 2, 3, len, 2);
  } else {
    for (let k = -len / 2; k < len / 2; k += 7) { c.fillStyle = (k / 7 | 0) % 2 ? '#6a5235' : '#5d4830'; c.beginPath(); c.arc(k + 3.5, 0, 4, 0, 7); c.fill(); c.fillStyle = '#8a6e4c'; c.beginPath(); c.arc(k + 2.5, -1, 1.5, 0, 7); c.fill(); }
  }
  if (piece.hp < piece.max) { c.fillStyle = '#18271fcc'; c.fillRect(-14, 9, 28, 3); c.fillStyle = '#d27a5e'; c.fillRect(-14, 9, 28 * piece.hp / piece.max, 3); }
  c.restore();
}
function drawCampPart(c, kind, part, camp, v) {
  if (part.hp <= 0) return;
  c.save(); c.translate(part.x, part.y);
  c.fillStyle = '#00000040'; c.beginPath(); c.ellipse(3, 4, 14, 9, 0, 0, 7); c.fill();
  if (kind === 'fire') {
    for (let a = 0; a < 6.28; a += .7) { c.fillStyle = '#76736a'; c.beginPath(); c.arc(Math.cos(a) * 11, Math.sin(a) * 9, 3.5, 0, 7); c.fill(); }
    c.fillStyle = '#2a2420'; c.beginPath(); c.arc(0, 0, 8, 0, 7); c.fill(); c.fillStyle = '#5a4630'; c.fillRect(-8, -1.5, 16, 3); c.fillRect(-1.5, -8, 3, 16);
    if (Math.random() < .55) puff('flame', part.x + (Math.random() - .5) * 6, part.y - 2, (Math.random() - .5) * 6, -16, .5, 5 + Math.random() * 3);
    if (Math.random() < .08) puff('smoke', part.x, part.y - 8, 4, -18, 3, 4, '#8a8780');
  } else if (kind === 'bed') {
    c.fillStyle = '#4f5c3e'; rr(c, -9, -15, 18, 30, 6); c.fill(); c.fillStyle = '#606f4b'; rr(c, -9, -15, 18, 9, 4); c.fill(); c.fillStyle = '#c9c2ae'; rr(c, -6, -14, 12, 6, 3); c.fill();
  } else if (kind === 'stash') {
    c.fillStyle = '#6e5538'; c.fillRect(-11, -8, 22, 16); c.strokeStyle = '#3e2f20'; c.lineWidth = 1.5; c.strokeRect(-11, -8, 22, 16); c.beginPath(); c.moveTo(-11, -8); c.lineTo(11, 8); c.moveTo(11, -8); c.lineTo(-11, 8); c.stroke(); c.fillStyle = '#9a9283'; c.fillRect(-2, -9, 4, 3);
  } else if (kind === 'bench') {
    c.fillStyle = '#6b5236'; c.fillRect(-16, -8, 32, 16); c.fillStyle = '#7f6545'; c.fillRect(-16, -8, 32, 4); c.fillStyle = '#585c5e'; c.fillRect(8, -6, 6, 6); c.fillStyle = '#8d9192'; c.fillRect(-12, -2, 10, 2); c.fillRect(-4, 2, 2, 5);
  } else if (kind === 'collector') {
    c.fillStyle = '#3d5160'; c.beginPath(); c.arc(0, 0, 9, 0, 7); c.fill(); c.strokeStyle = '#2a3a44'; c.lineWidth = 2; c.stroke(); c.fillStyle = '#5d7a52aa'; c.beginPath(); c.moveTo(-13, -10); c.lineTo(13, -10); c.lineTo(3, 0); c.lineTo(-3, 0); c.fill(); c.fillStyle = '#7fa6b3'; c.beginPath(); c.arc(0, 0, 4, 0, 7); c.fill();
  }
  if (part.hp < part.max) { c.fillStyle = '#18271fcc'; c.fillRect(-12, 14, 24, 3); c.fillStyle = '#d27a5e'; c.fillRect(-12, 14, 24 * part.hp / part.max, 3); }
  c.restore();
}
function drawBody(c, b, v) {
  if (b.npc) {
    // A dead person or animal lies as it fell and fades in its last seconds.
    const n = b.npc, fade = Math.max(0, Math.min(1, (b.until - v.state.time) / 20));
    if (fade <= 0) return;
    c.save(); c.globalAlpha = fade; c.translate(b.x, b.y); c.rotate(n.angle || 0);
    if (CREATURES[n.type]) S.creature(c, { type: n.type, phase: 0, moving: false, dead: 1 });
    else if (!S.infected(c, { look: infLook(n), size: 38, dead: 1, fall: strSeed(b.id.slice(1)) > .5 ? 'front' : 'back' })) S.figure(c, { look: n.look || 0, size: 38, dead: 1, time: 0 });
    c.restore();
    if (Object.keys(b.items).length) { c.fillStyle = '#5b4a33'; rr(c, b.x + 12, b.y + 6, 10, 8, 2); c.fill(); }
    return;
  }
  c.save(); c.translate(b.x, b.y); c.rotate(strSeed(b.id) * 6);
  S.figure(c, { player: true, size: 38, dead: 1, fall: strSeed(b.id) > .5 ? 'front' : 'back', time: 0 });
  c.restore();
  c.fillStyle = '#5b4a33'; rr(c, b.x + 10, b.y + 4, 12, 9, 2); c.fill();
}
function bar(c, x, y, k, col) { c.fillStyle = '#18271fcc'; c.fillRect(x - 18, y, 36, 4); c.fillStyle = col; c.fillRect(x - 18, y, 36 * Math.max(0, k), 4); }

function emitters(c, state, v, dt, vis) {
  const rate = R.quality === 'low' ? .3 : 1;
  pois.forEach(p => { if (!vis(p.x, p.y, 300)) return; p.parts.forEach(part => { if (part.sprite === 'chimney' && Math.random() < dt * 1.2 * rate) puff('smoke', part.x, part.y, 10, -12, 4, 8, '#6b6862'); }); });
}
// Names of places as you enter them, people nearby, camps and bodies.
function labels(c, state, v, vis) {
  c.font = '11px Segoe UI, Arial'; c.textAlign = 'center';
  const me = v.drawPlayers[state.me.id];
  cfg.towns.forEach(t => { if (vis(t.x, t.y, 200)) pill(c, t.name.toUpperCase(), t.x, t.y - 140, '#d9d6bb'); });
  pois.forEach(p => { if (vis(p.x, p.y, 100)) pill(c, p.name.toUpperCase(), p.x, p.y - 196, '#d8c79c'); });
  state.players.forEach(p => { const r = v.drawPlayers[p.id]; if (!r || p.vehicle || !vis(r.x, r.y) || p.id === state.me.id || p.hp <= 0) return; if (me && Math.hypot(me.x - r.x, me.y - r.y) > 500) return; pill(c, (p.tag ? '[' + p.tag + '] ' : '') + p.name, r.x, r.y - 34, col(p.faction)); });
  (state.camps || []).forEach(cp => { if (!vis(cp.x, cp.y, 100) || !sides[cp.owner]) return; pill(c, 'ЛАГЕРЬ · ' + sides[cp.owner].name.toUpperCase(), cp.x, cp.y - (cp.house ? 60 : 124), col(cp.owner)); });
  (state.bodies || []).forEach(b => { if (me && Math.hypot(me.x - b.x, me.y - b.y) < 200 && Object.keys(b.items).length && !b.npc) pill(c, b.name, b.x, b.y - 30, '#c9a99a'); });
  if (v.nearest && v.nearest.type === 'loot') { const l = v.nearest.obj, it = cfg.items[l.item]; if (it) pill(c, it.name + (l.n > 1 ? ' ×' + l.n : ''), l.x, l.y - 26, '#e6cf9c'); }
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
  (state.camps || []).forEach(cp => { const f = cp.parts.fire; if (f && f.hp > 0) hole(f.x, f.y, 170, .9 + flick, '#ff9c4a'); });
  state.players.forEach(p => {
    const r = v.drawPlayers[p.id]; if (!r || p.hp <= 0) return;
    hole(r.x, r.y, 70, .5);
    const ang = p.id === state.me.id && !p.vehicle ? Math.atan2(v.aim.y, v.aim.x) : p.angle;
    if (p.vehicle) return;
    cone(l, sx(r.x), sy(r.y), ang, .42, 330 * zs, .85);
    if (state.time - p.shot < .07) hole(r.x, r.y, 160, 1, '#ffe2a0');
  });
  // Headlights of every car with somebody at the wheel; brake lights and reversing lights.
  (state.cars || []).forEach(car => { if (!car.driver || car.wrecked) return; const r = (v.drawCars || {})[car.id] || car, ang = r.ang != null ? r.ang : car.angle, sp = carSpec(car), hl = sp.len / 2;
    [-1, 1].forEach(s => cone(l, sx(r.x + Math.cos(ang) * hl - Math.sin(ang) * s * sp.wid * .3), sy(r.y + Math.sin(ang) * hl + Math.cos(ang) * s * sp.wid * .3), ang, .3, 470 * zs, .9));
    if (car.brake || carFwd(car) < -5) hole(r.x - Math.cos(ang) * hl, r.y - Math.sin(ang) * hl, 46, .7, carFwd(car) < -5 ? '#f4f1e0' : '#ff3020'); });
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
const drops = [];
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
  // Fog is an even white veil over the whole screen; a storm darkens the edges a little.
  if (mode === 'fog') { c.fillStyle = 'rgba(206,211,205,.5)'; c.fillRect(0, 0, cw, ch); }
  else if (kind === 'storm') {
    const g = c.createRadialGradient(cw / 2, ch / 2, Math.min(cw, ch) * .18, cw / 2, ch / 2, Math.max(cw, ch) * .7);
    g.addColorStop(0, '#9aa3a600'); g.addColorStop(1, '#9aa3a660'); c.fillStyle = g; c.fillRect(0, 0, cw, ch);
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
  else { scale = .012; ox = w / 2 - state.me.x * scale; oy = h / 2 - state.me.y * scale; }
  c.imageSmoothingEnabled = true; c.drawImage(worldMap, ox, oy, cfg.width * scale, cfg.height * scale);
  const P = (x, y) => [ox + x * scale, oy + y * scale];
  // Close up the base image is blurry: roads, streets and rivers are drawn again as sharp lines.
  if (scale > .006) {
    c.lineCap = 'round'; c.strokeStyle = '#3f6670'; cfg.rivers.forEach(r => { c.lineWidth = Math.max(1.5, r[1] * scale); c.beginPath(); r[2].forEach((p, i) => { const q = P(p[0], p[1]); i ? c.lineTo(q[0], q[1]) : c.moveTo(q[0], q[1]); }); c.stroke(); });
    c.strokeStyle = '#d9cfa9aa'; c.lineWidth = Math.max(1.5, RW * scale); roads.forEach(r => { const a = P(r.ax, r.ay), b = P(r.bx, r.by); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); });
    c.strokeStyle = '#bdb69a88'; streets.forEach(st => { const a = P(st[0], st[1]), b = P(st[2], st[3]); if (Math.max(a[0], b[0]) < 0 || Math.min(a[0], b[0]) > w || Math.max(a[1], b[1]) < 0 || Math.min(a[1], b[1]) > h) return; c.lineWidth = Math.max(1, st[4] * scale); c.beginPath(); c.moveTo(a[0], a[1]); c.lineTo(b[0], b[1]); c.stroke(); });
    c.fillStyle = '#8a7f6c'; houses.forEach(hs => { const q = P(hs.x, hs.y); if (q[0] < -5 || q[0] > w + 5 || q[1] < -5 || q[1] > h + 5) return; c.fillRect(q[0] - hs.w * scale / 2, q[1] - hs.h * scale / 2, Math.max(1.5, hs.w * scale), Math.max(1.5, hs.h * scale)); });
  }
  // Points of interest.
  pois.forEach(p => { const [x, y] = P(p.x, p.y); if (x < -5 || x > w + 5 || y < -5 || y > h + 5) return; c.fillStyle = '#d8c79c'; c.save(); c.translate(x, y); c.rotate(.785); c.fillRect(-2.5, -2.5, 5, 5); c.restore(); if (big && (mapState.zoom || 1) > 1.6) { c.fillStyle = '#c9c0a2'; c.font = '9px Segoe UI'; c.textAlign = 'center'; c.fillText(p.name, x, y + 12); } });
  cfg.towns.forEach(t => { const [x, y] = P(t.x, t.y); if (x < -60 || x > w + 60 || y < -20 || y > h + 20) return; const big2 = t.kind !== 'village';
    if (big || big2) { c.fillStyle = '#0d1512'; c.beginPath(); c.arc(x, y, big2 ? 4 : 3, 0, 7); c.fill(); c.fillStyle = mapState && mapState.selected === t.id ? '#f0d09d' : '#cfd2c4'; c.beginPath(); c.arc(x, y, big2 ? 3 : 2, 0, 7); c.fill(); }
    if (big && (big2 || (mapState.zoom || 1) > 1.5)) { c.fillStyle = mapState.selected === t.id ? '#f0d09d' : '#e1e3d6'; c.font = (big2 ? 'bold ' : '') + '11px Segoe UI, Arial'; c.textAlign = 'center'; c.fillText(t.name, x, y - 8); } });
  (state.camps || []).forEach(cp => { const [x, y] = P(cp.x, cp.y); if (x < -10 || x > w + 10 || y < -10 || y > h + 10) return; const mine = cp.owner === state.me.faction; c.fillStyle = '#0d1512'; c.fillRect(x - 4, y - 4, 8, 8); c.fillStyle = col(cp.owner); c.fillRect(x - 3, y - 3, 6, 6); if (mine) { c.strokeStyle = '#edaf6b'; c.lineWidth = 1.5; c.strokeRect(x - 6, y - 6, 12, 12); if (big) { c.fillStyle = '#edaf6b'; c.font = 'bold 10px Segoe UI'; c.textAlign = 'center'; c.fillText('ЛАГЕРЬ', x, y + 16); } } });
  state.players.forEach(p => { const me = p.id === state.me.id; if (!me && !(R.friend && R.friend(p.faction))) return; const [x, y] = P(p.x, p.y); c.fillStyle = me ? '#edaf6b' : col(p.faction); c.beginPath(); c.arc(x, y, me ? 4 : 3, 0, 7); c.fill(); if (me) { c.strokeStyle = '#eabf8a88'; c.lineWidth = 1; c.beginPath(); c.arc(x, y, 8 + Math.sin(v.now * 4) * 2, 0, 7); c.stroke(); const a = p.vehicle ? p.angle : Math.atan2(v.aim.y, v.aim.x); c.beginPath(); c.moveTo(x + Math.cos(a) * 11, y + Math.sin(a) * 11); c.lineTo(x + Math.cos(a + 2.5) * 5, y + Math.sin(a + 2.5) * 5); c.lineTo(x + Math.cos(a - 2.5) * 5, y + Math.sin(a - 2.5) * 5); c.fill(); } });
  if (v.waypoint) { const [x, y] = P(v.waypoint.x, v.waypoint.y), [mx, my] = P(state.me.x, state.me.y); c.strokeStyle = '#dfbb7c'; c.lineWidth = 1; c.setLineDash([4, 4]); c.beginPath(); c.moveTo(mx, my); c.lineTo(x, y); c.stroke(); c.setLineDash([]); c.strokeRect(x - 6, y - 6, 12, 12); }
  if (!big) { c.strokeStyle = '#ffffff22'; c.strokeRect(.5, .5, w - 1, h - 1); }
  return { scale, ox, oy };
};
})();
