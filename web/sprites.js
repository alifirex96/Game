/* After Silence. Original procedural 2D art: every sprite is painted by code into cached canvases.
   Top-down view with a narrow south facade, light from the north-west, shadows to the south-east. */
(function () {
'use strict';
const AS = window.AS = window.AS || {};
const cache = new Map();

function hash(a, b) { let n = Math.sin(a * 127.1 + b * 311.7) * 43758.5453123; return n - Math.floor(n); }
function rng(seed) { let s = Math.floor(seed * 2147483647) % 2147483647 || 1; return () => (s = s * 16807 % 2147483647) / 2147483647; }
function strSeed(str) { let h = 7; for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) % 1000003; return h / 1000003; }
function rr(c, x, y, w, h, r) { r = Math.min(r, w / 2, h / 2); c.beginPath(); c.moveTo(x + r, y); c.arcTo(x + w, y, x + w, y + h, r); c.arcTo(x + w, y + h, x, y + h, r); c.arcTo(x, y + h, x, y, r); c.arcTo(x, y, x + w, y, r); c.closePath(); }
function hex(c) { c = c.replace('#', ''); return [parseInt(c.slice(0, 2), 16), parseInt(c.slice(2, 4), 16), parseInt(c.slice(4, 6), 16)]; }
function mix(a, b, t) { const x = hex(a), y = hex(b); return '#' + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, '0')).join(''); }
function shade(a, t) { return t > 0 ? mix(a, '#ffffff', t) : mix(a, '#000000', -t); }
function canvas(w, h) { const im = document.createElement('canvas'); im.width = Math.max(1, Math.ceil(w)); im.height = Math.max(1, Math.ceil(h)); return im; }
function cached(key, make) { if (!cache.has(key)) cache.set(key, make()); return cache.get(key); }
AS.util = { hash, rng, strSeed, rr, mix, shade, canvas };

const FACTION = { survivors: '#7fa58f', bandits: '#b8543c', neutral: '#b7b69f' };
AS.colors = FACTION;

/* ---------- small painters reused by buildings and ruins ---------- */
function speckle(c, x, y, w, h, colors, count, size, r) {
  for (let i = 0; i < count; i++) { c.fillStyle = colors[i % colors.length]; const s = size * (.4 + r() * .8); c.fillRect(x + r() * w, y + r() * h, s, s * (.5 + r() * .7)); }
}
function rubble(c, x, y, w, h, r, n, tone) {
  const tones = tone || ['#7a7466', '#8d8676', '#5f5a50', '#9a8f7a', '#6d5444'];
  for (let i = 0; i < n; i++) {
    const px = x + r() * w, py = y + r() * h, s = 3 + r() * 7;
    c.fillStyle = '#00000033'; c.beginPath(); c.ellipse(px + 2, py + 2, s, s * .7, 0, 0, 7); c.fill();
    c.fillStyle = tones[Math.floor(r() * tones.length)]; c.beginPath();
    c.moveTo(px - s, py); c.lineTo(px - s * .3, py - s * .8); c.lineTo(px + s * .8, py - s * .4); c.lineTo(px + s, py + s * .4); c.lineTo(px, py + s * .7); c.closePath(); c.fill();
    c.fillStyle = '#ffffff14'; c.fillRect(px - s * .4, py - s * .6, s * .6, s * .3);
  }
  if (r() < .8) { c.strokeStyle = '#4e3b2a'; c.lineWidth = 2; for (let i = 0; i < 3; i++) { const px = x + r() * w, py = y + r() * h; c.beginPath(); c.moveTo(px, py); c.lineTo(px + 10 + r() * 14, py + (r() - .5) * 12); c.stroke(); } }
}
function weeds(c, x, y, w, h, r, n) {
  for (let i = 0; i < n; i++) { const px = x + r() * w, py = y + r() * h, s = 3 + r() * 6; c.fillStyle = ['#56693b', '#4a5d34', '#6b7a45'][i % 3]; c.beginPath(); c.arc(px, py, s, 0, 7); c.fill(); c.fillStyle = '#7f8e5333'; c.beginPath(); c.arc(px - 1, py - 1, s * .5, 0, 7); c.fill(); }
}
function hole(c, x, y, w, h, r) {
  c.fillStyle = '#1b1d18'; c.beginPath();
  const n = 9; for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2, k = .65 + r() * .45; const px = x + Math.cos(a) * w / 2 * k, py = y + Math.sin(a) * h / 2 * k; i ? c.lineTo(px, py) : c.moveTo(px, py); } c.closePath(); c.fill();
  c.strokeStyle = '#5d4632'; c.lineWidth = 2.5; c.beginPath();
  c.moveTo(x - w * .45, y - h * .1); c.lineTo(x + w * .4, y + h * .05); c.moveTo(x - w * .2, y - h * .4); c.lineTo(x - w * .1, y + h * .4); c.stroke();
  c.fillStyle = '#ffffff10'; c.fillRect(x - w * .3, y + h * .1, w * .2, 2);
}
function soot(c, x, y, w, h) { const g = c.createRadialGradient(x, y, 2, x, y, Math.max(w, h)); g.addColorStop(0, '#0d0d0b88'); g.addColorStop(1, '#0d0d0b00'); c.fillStyle = g; c.fillRect(x - w, y - h, w * 2, h * 2); }
function tarp(c, x, y, w, h, color) {
  c.fillStyle = color; c.beginPath(); c.moveTo(x, y + 2); c.lineTo(x + w, y); c.lineTo(x + w - 2, y + h); c.lineTo(x + 3, y + h - 1); c.closePath(); c.fill();
  c.strokeStyle = '#ffffff22'; c.lineWidth = 1; for (let i = 1; i < 4; i++) { c.beginPath(); c.moveTo(x + w * i / 4, y + 1); c.lineTo(x + w * i / 4 - 2, y + h - 1); c.stroke(); }
  c.fillStyle = '#00000030'; c.fillRect(x, y + h - 3, w, 3);
  c.fillStyle = '#d9d2b8'; [[x + 2, y + 2], [x + w - 4, y + 1], [x + 2, y + h - 4], [x + w - 5, y + h - 4]].forEach(p => c.fillRect(p[0], p[1], 2, 2));
}
function scaffold(c, x, y, w, h) {
  c.strokeStyle = '#a07c4d'; c.lineWidth = 2; c.strokeRect(x, y, w, h);
  c.lineWidth = 1.2; for (let i = 8; i < w; i += 10) { c.beginPath(); c.moveTo(x + i, y); c.lineTo(x + i, y + h); c.stroke(); }
  c.strokeStyle = '#c99a5c'; c.beginPath(); c.moveTo(x, y); c.lineTo(x + w, y + h); c.stroke();
  c.fillStyle = '#b48a55'; c.fillRect(x - 2, y + h / 2 - 2, w + 4, 4);
}
function planks(c, x, y, w, h, r) {
  for (let i = 0; i < 3; i++) { c.fillStyle = ['#8d6a42', '#7b5b36', '#9a7748'][i]; c.save(); c.translate(x + r() * w, y + r() * h); c.rotate((r() - .5) * 1.2); c.fillRect(-12, -2, 24, 4); c.restore(); }
}
function barrel(c, x, y, color) { c.fillStyle = '#00000040'; c.beginPath(); c.arc(x + 2, y + 2, 6, 0, 7); c.fill(); c.fillStyle = color || '#4f6a5a'; c.beginPath(); c.arc(x, y, 6, 0, 7); c.fill(); c.strokeStyle = '#00000055'; c.lineWidth = 1; c.beginPath(); c.arc(x, y, 4, 0, 7); c.stroke(); c.fillStyle = '#ffffff30'; c.beginPath(); c.arc(x - 2, y - 2, 1.6, 0, 7); c.fill(); }
function crate(c, x, y, s, color) { c.fillStyle = '#00000040'; c.fillRect(x + 2, y + 2, s, s); c.fillStyle = color || '#8b6c45'; c.fillRect(x, y, s, s); c.strokeStyle = '#4b3925'; c.lineWidth = 1; c.strokeRect(x + .5, y + .5, s - 1, s - 1); c.beginPath(); c.moveTo(x, y); c.lineTo(x + s, y + s); c.stroke(); c.fillStyle = '#ffffff1a'; c.fillRect(x + 1, y + 1, s - 2, 2); }
function sandbags(c, x, y, w, h) {
  c.fillStyle = '#00000033'; c.fillRect(x + 2, y + 3, w, h);
  for (let i = 0; i < w; i += 9) for (let j = 0; j < h; j += 6) { c.fillStyle = (i + j) % 18 ? '#a39470' : '#958763'; rr(c, x + i + (j % 12 ? 4 : 0), y + j, 9, 6, 3); c.fill(); }
}
function windowRow(c, x, y, w, count, lit, broken, color) {
  const step = w / count;
  for (let i = 0; i < count; i++) {
    const wx = x + i * step + step * .22, ww = step * .56;
    c.fillStyle = '#22282233'; c.fillRect(wx - 1, y - 1, ww + 2, 9);
    c.fillStyle = broken && (i * 7 % 3) ? '#141713' : lit ? (i % 3 ? '#d9b46a' : '#a7b8b0') : (color || '#3d5257');
    c.fillRect(wx, y, ww, 7);
    if (!broken) { c.fillStyle = '#ffffff30'; c.fillRect(wx, y, ww * .4, 2); c.fillStyle = '#00000040'; c.fillRect(wx + ww / 2 - .5, y, 1, 7); }
    else if (i % 2) { c.fillStyle = '#8a6a43'; c.fillRect(wx - 1, y + 2, ww + 2, 2); }
  }
}
function flag(c, x, y, color) { c.strokeStyle = '#c7c2ad'; c.lineWidth = 2; c.beginPath(); c.moveTo(x, y); c.lineTo(x, y - 26); c.stroke(); c.fillStyle = color; c.beginPath(); c.moveTo(x + 1, y - 26); c.lineTo(x + 17, y - 22); c.lineTo(x + 1, y - 16); c.fill(); }
function solar(c, x, y, n) { for (let i = 0; i < n; i++) { c.fillStyle = '#00000040'; c.fillRect(x + i * 15 + 2, y + 2, 13, 18); c.fillStyle = '#29425a'; c.fillRect(x + i * 15, y, 13, 18); c.strokeStyle = '#6f8fa8'; c.lineWidth = .7; c.strokeRect(x + i * 15 + .5, y + .5, 12, 17); c.beginPath(); c.moveTo(x + i * 15 + 6.5, y); c.lineTo(x + i * 15 + 6.5, y + 18); c.moveTo(x + i * 15, y + 9); c.lineTo(x + i * 15 + 13, y + 9); c.stroke(); c.fillStyle = '#ffffff22'; c.fillRect(x + i * 15 + 1, y + 1, 5, 2); } }
function lampPost(c, x, y) { c.fillStyle = '#00000044'; c.beginPath(); c.ellipse(x + 3, y + 2, 4, 2, 0, 0, 7); c.fill(); c.fillStyle = '#4b5049'; c.fillRect(x - 1, y - 12, 2, 13); c.fillStyle = '#e7d7a1'; c.beginPath(); c.arc(x, y - 13, 2.5, 0, 7); c.fill(); }
function flowerBed(c, x, y, w, h, r) { c.fillStyle = '#4a3a29'; rr(c, x, y, w, h, 3); c.fill(); for (let i = 0; i < w * h / 25; i++) { c.fillStyle = ['#c86e5a', '#e2c86f', '#d79cb7', '#6f9a54'][i % 4]; c.beginPath(); c.arc(x + 2 + r() * (w - 4), y + 2 + r() * (h - 4), 1.6, 0, 7); c.fill(); } }

/* Roof painters return nothing; they fill (x, y, w, h). */
function roofFlat(c, x, y, w, h, base, r) {
  c.fillStyle = base; c.fillRect(x, y, w, h);
  speckle(c, x, y, w, h, [shade(base, -.12), shade(base, .08), '#00000018'], Math.floor(w * h / 60), 4, r);
  c.strokeStyle = shade(base, .18); c.lineWidth = 2; c.strokeRect(x + 1, y + 1, w - 2, h - 2);
  c.fillStyle = '#0000001c'; for (let i = 0; i < 3; i++) { c.beginPath(); c.ellipse(x + r() * w, y + r() * h, 6 + r() * 10, 4 + r() * 6, 0, 0, 7); c.fill(); }
}
function roofTiles(c, x, y, w, h, base) {
  c.fillStyle = base; c.fillRect(x, y, w, h);
  for (let j = 0; j < h; j += 6) { c.fillStyle = j % 12 ? shade(base, -.08) : shade(base, .05); c.fillRect(x, y + j, w, 3); for (let i = (j % 12 ? 0 : 5); i < w; i += 10) { c.fillStyle = '#00000022'; c.fillRect(x + i, y + j, 1, 6); } }
  c.fillStyle = shade(base, .2); c.fillRect(x, y + h / 2 - 1.5, w, 3);
  c.fillStyle = '#00000026'; c.fillRect(x, y + h / 2 + 1.5, w, h / 2 - 1.5);
}
function roofMetal(c, x, y, w, h, base, vertical) {
  c.fillStyle = base; c.fillRect(x, y, w, h);
  c.lineWidth = 1;
  if (vertical) for (let i = 2; i < w; i += 5) { c.strokeStyle = i % 10 < 5 ? shade(base, .14) : shade(base, -.15); c.beginPath(); c.moveTo(x + i, y); c.lineTo(x + i, y + h); c.stroke(); }
  else for (let j = 2; j < h; j += 5) { c.strokeStyle = j % 10 < 5 ? shade(base, .14) : shade(base, -.15); c.beginPath(); c.moveTo(x, y + j); c.lineTo(x + w, y + j); c.stroke(); }
}
function roofPlanks(c, x, y, w, h, base, r) {
  c.fillStyle = base; c.fillRect(x, y, w, h);
  for (let i = 0; i < w; i += 7) { c.fillStyle = shade(base, (r() - .5) * .25); c.fillRect(x + i, y, 6, h); c.fillStyle = '#00000030'; c.fillRect(x + i + 6, y, 1, h); }
  c.fillStyle = '#00000030'; c.fillRect(x, y + h / 2, w, h / 2);
  c.fillStyle = shade(base, .15); c.fillRect(x, y + h / 2 - 2, w, 3);
}
function facade(c, x, y, w, h, wall, level, r, opts) {
  opts = opts || {};
  c.fillStyle = wall; c.fillRect(x, y, w, h);
  c.fillStyle = '#00000030'; c.fillRect(x, y, w, 2);
  if (opts.brick) for (let j = 3; j < h; j += 4) { c.fillStyle = '#00000014'; c.fillRect(x, y + j, w, 1); }
  windowRow(c, x + 3, y + 4, w - 6, opts.windows || Math.max(2, Math.floor(w / 18)), false, level === 0, opts.glass);
  if (opts.door !== false) { const dx = x + w / 2 - 6; c.fillStyle = level === 0 ? '#151612' : '#3e3528'; c.fillRect(dx, y + h - 11, 12, 11); if (level) { c.fillStyle = '#c9a463'; c.fillRect(dx + 9, y + h - 6, 1.5, 1.5); } }
  if (level === 0) { soot(c, x + w * .3, y + 4, 12, 6); c.fillStyle = '#1a1b17'; c.fillRect(x + w * .7, y + 2, 9, h - 4); }
}

/* ---------- settlement buildings by kind and restoration level ---------- */
const PAINT = {
  depot(c, w, h, L, owner, r) {
    const fh = 16, rh = h - fh;
    if (L === 0) { roofFlat(c, -w / 2, -h / 2, w, rh, '#6a685d', r); hole(c, -w * .15, -h / 2 + rh * .45, w * .35, rh * .5, r); soot(c, w * .2, -h / 2 + 10, 20, 14); }
    else roofFlat(c, -w / 2, -h / 2, w, rh, L >= 3 ? '#7f7f74' : '#77766b', r);
    facade(c, -w / 2, -h / 2 + rh, w, fh, L ? '#8a8573' : '#6d685a', L, r, { brick: true, windows: 5 });
    if (L >= 1) { c.fillStyle = '#3f443c'; c.fillRect(-w / 2 + 10, -h / 2 + 8, 18, 12); c.fillStyle = '#5d6458'; c.fillRect(-w / 2 + 12, -h / 2 + 10, 14, 3); }
    if (L === 1) { tarp(c, w * .02, -h / 2 + 12, 34, 22, '#4f6f84'); scaffold(c, w / 2 - 22, -h / 2 + 4, 18, rh - 8); }
    if (L >= 2) { sandbags(c, -w / 2 - 8, h / 2 + 3, 36, 12); sandbags(c, w / 2 - 28, h / 2 + 3, 36, 12); crate(c, w / 2 - 22, -h / 2 + 10, 12); crate(c, w / 2 - 34, -h / 2 + 14, 10, '#6f7d55'); }
    if (L >= 3) { solar(c, -w / 2 + 34, -h / 2 + 8, 3); c.strokeStyle = '#c3c6bb'; c.lineWidth = 2; c.beginPath(); c.moveTo(w / 2 - 14, -h / 2 + 30); c.lineTo(w / 2 - 14, -h / 2 - 8); c.stroke(); c.fillStyle = '#d7d9cf'; c.beginPath(); c.ellipse(w / 2 - 14, -h / 2 - 8, 7, 3, -.4, 0, 7); c.fill(); lampPost(c, -w / 2 - 6, h / 2 + 22); lampPost(c, w / 2 + 6, h / 2 + 22); }
    if (L) flag(c, -w / 2 + 6, -h / 2 + 4, FACTION[owner || 'neutral']);
    else rubble(c, -w / 2 - 10, h / 2, w + 20, 18, r, 12);
  },
  house(c, w, h, L, owner, r) {
    const fh = 20, rh = h - fh;
    roofFlat(c, -w / 2, -h / 2, w, rh, L ? (L >= 3 ? '#6d7069' : '#66675f') : '#5a5a52', r);
    for (let i = 0; i < 3; i++) { const vx = -w / 2 + 18 + i * (w - 36) / 2; c.fillStyle = '#4a4b45'; c.fillRect(vx - 5, -h / 2 + 10, 10, 8); c.fillStyle = '#2e2f2b'; c.fillRect(vx - 3, -h / 2 + 12, 6, 4); }
    if (L === 0) { hole(c, w * .18, -h / 2 + rh * .5, w * .32, rh * .55, r); hole(c, -w * .3, -h / 2 + rh * .35, w * .18, rh * .3, r); weeds(c, -w / 2, -h / 2, w, rh, r, 5); }
    c.fillStyle = L ? '#9c9a8d' : '#7b786c'; c.fillRect(-w / 2, -h / 2 + rh, w, fh);
    for (let row = 0; row < 2; row++) windowRow(c, -w / 2 + 4, -h / 2 + rh + 2 + row * 9, w - 8, 7, false, L === 0, '#3c4f55');
    for (let i = 0; i < 4; i++) { c.fillStyle = '#00000020'; c.fillRect(-w / 2 + i * w / 4, -h / 2 + rh, 1, fh); }
    if (L === 1) { tarp(c, -w * .28, -h / 2 + rh * .3, 30, 20, '#57725b'); scaffold(c, w / 2 - 26, -h / 2 + rh + 1, 24, fh - 2); planks(c, -w / 2, h / 2, w, 12, r); }
    if (L >= 2) { c.fillStyle = '#5e6b52'; for (let i = 0; i < 4; i++) { c.fillRect(-w / 2 + 10 + i * 26, h / 2 + 4, 14, 3); } c.strokeStyle = '#d8d3c0'; c.lineWidth = 1; c.beginPath(); c.moveTo(-w / 2 + 6, h / 2 + 10); c.lineTo(-w / 2 + 40, h / 2 + 12); c.stroke(); ['#c56f5a', '#d8c9a3', '#6c88a3'].forEach((col, i) => { c.fillStyle = col; c.fillRect(-w / 2 + 12 + i * 9, h / 2 + 11, 5, 6); }); }
    if (L >= 3) { solar(c, -w / 2 + 10, -h / 2 + 24, 4); flowerBed(c, w / 2 - 34, h / 2 + 4, 28, 10, r); lampPost(c, w / 2 + 6, h / 2 + 14); }
    if (L === 0) rubble(c, -w / 2 - 8, h / 2 - 2, w + 16, 20, r, 14);
  },
  sawmill(c, w, h, L, owner, r) {
    const fh = 14, rh = h - fh;
    c.fillStyle = '#5b4a35'; c.fillRect(-w / 2, -h / 2, w, rh);
    if (L === 0) { roofPlanks(c, -w / 2, -h / 2, w * .55, rh, '#6a5638', r); hole(c, w * .15, -h / 2 + rh / 2, w * .5, rh * .7, r); }
    else roofPlanks(c, -w / 2, -h / 2, w, rh, L >= 3 ? '#86683f' : '#7c6038', r);
    facade(c, -w / 2, -h / 2 + rh, w, fh, L ? '#7a6143' : '#5f4b34', L, r, { windows: 3 });
    // log piles and saw bench in front
    const logs = L ? 4 + L * 2 : 3;
    for (let i = 0; i < logs; i++) { const lx = -w / 2 + 4 + (i % 4) * 11, ly = h / 2 + 4 + Math.floor(i / 4) * 7; c.fillStyle = '#6b4f30'; rr(c, lx, ly, 34, 6, 3); c.fill(); c.fillStyle = '#c9a26a'; c.beginPath(); c.ellipse(lx + 33, ly + 3, 2.6, 3, 0, 0, 7); c.fill(); c.fillStyle = '#8c6b40'; c.beginPath(); c.arc(lx + 33, ly + 3, 1, 0, 7); c.fill(); }
    if (L >= 2) { c.fillStyle = '#717a72'; c.fillRect(w / 2 - 36, h / 2 + 2, 30, 10); c.fillStyle = '#b9bdb2'; c.beginPath(); c.arc(w / 2 - 21, h / 2 + 7, 6, 0, 7); c.fill(); c.strokeStyle = '#555c55'; c.lineWidth = 1; for (let a = 0; a < 6.28; a += .8) { c.beginPath(); c.moveTo(w / 2 - 21, h / 2 + 7); c.lineTo(w / 2 - 21 + Math.cos(a) * 6, h / 2 + 7 + Math.sin(a) * 6); c.stroke(); } }
    if (L === 1) scaffold(c, w / 2 - 30, -h / 2 + 6, 26, rh - 10);
    if (L >= 3) { c.fillStyle = '#4d5650'; c.fillRect(-w / 2 - 14, -h / 2 + 10, 12, rh - 16); c.fillStyle = '#b28a55'; for (let i = 0; i < 4; i++) c.fillRect(-w / 2 - 12, -h / 2 + 14 + i * 10, 8, 4); lampPost(c, w / 2 + 6, h / 2 + 18); }
    c.fillStyle = '#c7a5714d'; for (let i = 0; i < 18; i++) c.fillRect(-w / 2 + r() * w, h / 2 + r() * 18, 2, 1);
    if (L === 0) rubble(c, -w / 2, h / 2 + 4, w, 14, r, 8, ['#6b5236', '#7b6242', '#5b4630']);
  },
  quarry(c, w, h, L, owner, r) {
    // An open pit with terraces instead of a roof.
    const depth = [['#8f8a7c', 1], ['#7d786b', .8], ['#6a665b', .6], ['#57544b', .4]];
    depth.forEach((d, i) => { c.fillStyle = d[0]; rr(c, -w / 2 * d[1] - 4, -h / 2 * d[1], w * d[1] + 8, h * d[1], 14 * d[1]); c.fill(); c.strokeStyle = '#ffffff18'; c.lineWidth = 1.5; c.stroke(); });
    if (L === 0) { c.fillStyle = '#3f5560'; c.beginPath(); c.ellipse(0, 4, w * .2, h * .16, 0, 0, 7); c.fill(); c.fillStyle = '#ffffff18'; c.fillRect(-10, 0, 14, 2); weeds(c, -w / 2, -h / 2, w, h, r, 9); }
    speckle(c, -w / 2, -h / 2, w, h, ['#a39d8b', '#615d53'], 60, 4, r);
    if (L >= 1) { c.strokeStyle = '#8c6c45'; c.lineWidth = 3; c.beginPath(); c.moveTo(-w / 2 + 6, h / 2 - 8); c.lineTo(-10, 0); c.stroke(); }
    if (L >= 2) { // excavator
      c.save(); c.translate(w * .18, -h * .05); c.fillStyle = '#00000040'; c.fillRect(-10, -6, 26, 20); c.fillStyle = '#2f302b'; c.fillRect(-12, -9, 6, 22); c.fillRect(8, -9, 6, 22); c.fillStyle = '#c9a03d'; c.fillRect(-8, -6, 18, 15); c.fillStyle = '#39494d'; c.fillRect(-6, -4, 7, 6); c.strokeStyle = '#c9a03d'; c.lineWidth = 4; c.beginPath(); c.moveTo(4, 2); c.lineTo(-22, -10); c.stroke(); c.fillStyle = '#5d5b4f'; c.fillRect(-28, -14, 8, 8); c.restore();
    }
    if (L >= 3) { c.fillStyle = '#585d57'; c.fillRect(-w / 2 + 6, -h / 2 + 4, 36, 12); c.fillStyle = '#8c8f86'; for (let i = 0; i < 5; i++) c.fillRect(-w / 2 + 8 + i * 7, -h / 2 + 6, 5, 8); lampPost(c, w / 2, -h / 2 + 4); lampPost(c, -w / 2, h / 2); }
    for (let i = 0; i < 2 + L * 2; i++) { const bx = w / 2 - 6 - (i % 3) * 12, by = h / 2 - 4 + Math.floor(i / 3) * 10; c.fillStyle = '#9a9585'; c.beginPath(); c.moveTo(bx - 7, by + 4); c.lineTo(bx, by - 6); c.lineTo(bx + 7, by + 4); c.fill(); c.fillStyle = '#ffffff1c'; c.beginPath(); c.moveTo(bx - 3, by); c.lineTo(bx, by - 6); c.lineTo(bx + 1, by); c.fill(); }
  },
  workshop(c, w, h, L, owner, r) {
    const fh = 16, rh = h - fh;
    // Sawtooth industrial roof with skylights.
    c.fillStyle = '#5c625e'; c.fillRect(-w / 2, -h / 2, w, rh);
    for (let i = 0; i < 5; i++) { const sx = -w / 2 + i * w / 5; c.fillStyle = L ? '#7b827c' : '#626862'; c.fillRect(sx, -h / 2, w / 5 - 6, rh); c.fillStyle = L ? (L >= 2 ? '#8fb2b6' : '#6a7f80') : '#2a2d29'; c.fillRect(sx + w / 5 - 6, -h / 2, 6, rh); c.fillStyle = '#00000026'; c.fillRect(sx, -h / 2, 3, rh); }
    if (L === 0) { hole(c, -w * .1, -h / 2 + rh * .5, w * .4, rh * .6, r); soot(c, w * .25, -h / 2 + 18, 18, 14); }
    facade(c, -w / 2, -h / 2 + rh, w, fh, L ? '#857b6b' : '#695f52', L, r, { brick: true, windows: 4, door: false });
    c.fillStyle = L ? '#6f7871' : '#20221e'; c.fillRect(-14, -h / 2 + rh + 2, 28, fh - 2); if (L) { c.strokeStyle = '#00000033'; for (let i = 3; i < fh; i += 3) { c.beginPath(); c.moveTo(-14, -h / 2 + rh + i); c.lineTo(14, -h / 2 + rh + i); c.stroke(); } }
    if (L === 1) { tarp(c, w * .1, -h / 2 + 10, 30, 22, '#866142'); scaffold(c, -w / 2 + 4, -h / 2 + 4, 22, rh - 8); }
    if (L >= 2) { c.fillStyle = '#4d544f'; c.fillRect(w / 2 - 30, h / 2 + 2, 24, 12); c.fillStyle = '#aaa38d'; c.fillRect(w / 2 - 28, h / 2 + 4, 6, 8); barrel(c, -w / 2 + 10, h / 2 + 10, '#6a5a44'); barrel(c, -w / 2 + 24, h / 2 + 10, '#4e5e64'); }
    if (L >= 3) { c.fillStyle = '#6b6258'; c.beginPath(); c.arc(w / 2 - 14, -h / 2 + 14, 9, 0, 7); c.fill(); c.fillStyle = '#2b2622'; c.beginPath(); c.arc(w / 2 - 14, -h / 2 + 14, 5, 0, 7); c.fill(); lampPost(c, -w / 2 - 6, h / 2 + 16); }
    if (L === 0) rubble(c, -w / 2, h / 2, w, 16, r, 12, ['#6e6f68', '#7d6e5d', '#55564f']);
  },
  farm(c, w, h, L, owner, r) {
    // Greenhouses on the north half, beds to the south.
    const gh = h * .55;
    for (let k = 0; k < 2; k++) {
      const gx = -w / 2 + k * w / 2 + 3, gw = w / 2 - 6;
      c.fillStyle = '#00000038'; c.fillRect(gx + 3, -h / 2 + 3, gw, gh);
      c.fillStyle = L === 0 ? '#3d4637' : L === 1 && k ? '#4c5b48' : '#9fbab0aa'; c.fillRect(gx, -h / 2, gw, gh);
      c.strokeStyle = L ? '#d6dcd2' : '#70706a'; c.lineWidth = 1; for (let i = 0; i <= gw; i += 9) { c.beginPath(); c.moveTo(gx + i, -h / 2); c.lineTo(gx + i, -h / 2 + gh); c.stroke(); }
      c.beginPath(); c.moveTo(gx, -h / 2 + gh / 2); c.lineTo(gx + gw, -h / 2 + gh / 2); c.stroke();
      if (L) { c.fillStyle = '#ffffff26'; c.fillRect(gx + 2, -h / 2 + 2, gw * .4, gh * .35); if (L >= 2 || !k) { c.fillStyle = '#4e7d3f88'; for (let i = 4; i < gw - 4; i += 6) c.fillRect(gx + i, -h / 2 + gh * .55, 3, gh * .35); } }
      else { c.fillStyle = '#1e211b'; c.fillRect(gx + gw * .3, -h / 2 + 4, gw * .4, gh * .5); weeds(c, gx, -h / 2, gw, gh, r, 4); }
    }
    const by = -h / 2 + gh + 4, bh = h - gh - 4;
    for (let i = 0; i < 6; i++) {
      c.fillStyle = L ? '#5b4430' : '#4c4635'; c.fillRect(-w / 2 + 2 + i * (w / 6), by, w / 6 - 5, bh + 10);
      if (L) for (let j = 0; j < bh + 6; j += 5) { c.fillStyle = L >= 2 ? (i % 2 ? '#6c9c48' : '#86ad4f') : '#557a3a'; c.beginPath(); c.arc(-w / 2 + 2 + i * (w / 6) + (w / 6 - 5) / 2, by + 3 + j, L >= 2 ? 2.4 : 1.6, 0, 7); c.fill(); }
      else weeds(c, -w / 2 + 2 + i * (w / 6), by, w / 6 - 5, bh, r, 2);
    }
    if (L >= 2) { c.strokeStyle = '#8b6f4c'; c.lineWidth = 1.5; c.strokeRect(-w / 2 - 4, by - 2, w + 8, bh + 16); barrel(c, w / 2 + 8, by + 6, '#466a8a'); }
    if (L >= 3) { c.fillStyle = '#6a7c87'; c.beginPath(); c.arc(-w / 2 - 12, -h / 2 + 10, 8, 0, 7); c.fill(); c.fillStyle = '#9fb3be'; c.beginPath(); c.arc(-w / 2 - 12, -h / 2 + 10, 5, 0, 7); c.fill(); lampPost(c, w / 2 + 6, -h / 2); }
    if (L === 1) planks(c, -w / 2, -h / 2 + gh, w, 10, r);
  },
  garage(c, w, h, L, owner, r) {
    const fh = 18, rh = h - fh;
    roofMetal(c, -w / 2, -h / 2, w, rh, L ? '#6e746d' : '#5a5d55', true);
    if (L === 0) { hole(c, w * .2, -h / 2 + rh / 2, w * .3, rh * .55, r); c.fillStyle = '#7a4a2c88'; for (let i = 0; i < 8; i++) c.fillRect(-w / 2 + r() * w, -h / 2 + r() * rh, 8, 5); }
    c.fillStyle = L ? '#7c7a6d' : '#5f5c51'; c.fillRect(-w / 2, -h / 2 + rh, w, fh);
    for (let i = 0; i < 4; i++) { const dx = -w / 2 + 4 + i * (w - 8) / 4; c.fillStyle = L ? (i === 1 && L >= 2 ? '#2a2c27' : '#8a9087') : (i % 2 ? '#191a16' : '#6a5a48'); c.fillRect(dx, -h / 2 + rh + 3, (w - 8) / 4 - 4, fh - 3); if (L) { c.fillStyle = '#00000026'; for (let j = 4; j < fh; j += 3) c.fillRect(dx, -h / 2 + rh + j, (w - 8) / 4 - 4, 1); } }
    barrel(c, -w / 2 + 8, h / 2 + 10, '#8a3d2e'); barrel(c, -w / 2 + 21, h / 2 + 12, '#8a3d2e');
    if (L >= 2) { c.fillStyle = '#00000040'; c.beginPath(); c.ellipse(w / 2 - 14, h / 2 + 14, 16, 8, 0, 0, 7); c.fill(); c.fillStyle = '#b8b6a6'; rr(c, w / 2 - 30, h / 2 + 4, 30, 14, 7); c.fill(); c.fillStyle = '#8a3d2e'; c.fillRect(w / 2 - 20, h / 2 + 5, 3, 12); }
    if (L >= 3) { c.fillStyle = '#d4b04a'; c.fillRect(-8, h / 2 + 2, 16, 3); c.fillRect(-8, h / 2 + 12, 16, 3); lampPost(c, w / 2 + 6, -h / 2 + 4); solar(c, -w / 2 + 8, -h / 2 + 8, 3); }
    if (L === 1) tarp(c, -w * .15, -h / 2 + 8, 30, 20, '#3f5d6e');
    if (L === 0) rubble(c, -w / 2, h / 2 + 2, w, 14, r, 8);
  },
  warehouse(c, w, h, L, owner, r) {
    const fh = 14, rh = h - fh;
    // Arched corrugated hangar seen from above: banded shading.
    for (let j = 0; j < rh; j++) { const t = j / rh, k = Math.sin(t * Math.PI); c.fillStyle = mix(L ? '#5c6660' : '#4f5550', L ? '#a9b2a8' : '#7d827a', k * .8 - (t > .5 ? .25 : 0)); c.fillRect(-w / 2, -h / 2 + j, w, 1); }
    c.strokeStyle = '#00000022'; c.lineWidth = 1; for (let i = 3; i < w; i += 5) { c.beginPath(); c.moveTo(-w / 2 + i, -h / 2); c.lineTo(-w / 2 + i, -h / 2 + rh); c.stroke(); }
    if (L === 0) { hole(c, -w * .2, -h / 2 + rh * .45, w * .35, rh * .6, r); hole(c, w * .28, -h / 2 + rh * .3, w * .14, rh * .3, r); }
    facade(c, -w / 2, -h / 2 + rh, w, fh, L ? '#7d7f74' : '#5c5d55', L, r, { windows: 2, door: false });
    c.fillStyle = L ? '#4b524c' : '#171814'; c.fillRect(-16, -h / 2 + rh + 1, 32, fh - 1);
    const cols = ['#7b4636', '#3e5d73', '#577048', '#8a7a46'];
    const n = L ? L + 1 : 1;
    for (let i = 0; i < n; i++) { const cx = -w / 2 - 2 + i * 30, cy = h / 2 + 3; c.fillStyle = '#00000040'; c.fillRect(cx + 3, cy + 3, 26, 11); c.fillStyle = cols[i % 4]; c.fillRect(cx, cy, 26, 11); c.strokeStyle = '#00000030'; for (let k = 3; k < 26; k += 3) { c.beginPath(); c.moveTo(cx + k, cy); c.lineTo(cx + k, cy + 11); c.stroke(); } }
    if (L >= 3) { c.fillStyle = '#d0a33a'; c.fillRect(w / 2 - 16, h / 2 + 2, 12, 8); c.fillStyle = '#2d2d28'; c.fillRect(w / 2 - 20, h / 2 + 4, 4, 1.5); c.fillRect(w / 2 - 20, h / 2 + 8, 4, 1.5); lampPost(c, -w / 2 - 6, -h / 2 + 4); }
    if (L === 1) scaffold(c, w / 2 - 24, -h / 2 + 4, 20, rh - 8);
  },
  radio(c, w, h, L, owner, r) {
    // Operator hut at the base, lattice mast rising north (drawn foreshortened).
    c.fillStyle = '#00000038'; c.fillRect(-28, 10, 62, 34);
    roofFlat(c, -31, 6, 62, 20, L ? '#6a7067' : '#55574f', r);
    facade(c, -31, 26, 62, 14, L ? '#8b8574' : '#65604f', L, r, { windows: 3 });
    const top = -h / 2 - 40, col = L ? '#a8b0a0' : '#6d6f63';
    c.strokeStyle = '#00000040'; c.lineWidth = 4; c.beginPath(); c.moveTo(4, 12); c.lineTo(34, top + 70); c.stroke();
    c.strokeStyle = col; c.lineWidth = 2.5; c.beginPath(); c.moveTo(-8, 8); c.lineTo(0, top); c.lineTo(8, 8); c.stroke();
    c.lineWidth = 1; for (let y = 4; y > top; y -= 9) { const k = (y - top) / (8 - top) * 8; c.beginPath(); c.moveTo(-k, y); c.lineTo(k, y - 9); c.moveTo(k, y); c.lineTo(-k, y - 9); c.stroke(); }
    c.strokeStyle = '#c5c0aa55'; c.beginPath(); c.moveTo(0, top + 20); c.lineTo(-w / 2, 6); c.moveTo(0, top + 20); c.lineTo(w / 2, 6); c.stroke();
    if (L === 0) { c.strokeStyle = '#6d6f63'; c.lineWidth = 2; c.beginPath(); c.moveTo(0, top + 26); c.lineTo(22, top + 6); c.stroke(); rubble(c, -w / 2, 30, w, 14, r, 7); }
    if (L >= 2) { c.fillStyle = '#d9dbd0'; c.beginPath(); c.ellipse(-12, top + 30, 8, 4, -.5, 0, 7); c.fill(); c.strokeStyle = '#7d7f75'; c.stroke(); }
    if (L >= 3) { solar(c, -w / 2 + 2, 30, 1); solar(c, w / 2 - 15, 30, 1); c.fillStyle = '#d27b4e'; c.beginPath(); c.arc(0, top, 3, 0, 7); c.fill(); }
    if (L) flag(c, 27, 8, FACTION[owner || 'neutral']);
  },
  guard(c, w, h, L, owner, r) {
    // Watchtower: four legs, platform and roof, seen from above.
    c.fillStyle = '#00000044'; c.beginPath(); c.moveTo(-w / 2 + 6, -h / 2 + 12); c.lineTo(w / 2 + 22, -h / 2 + 26); c.lineTo(w / 2 + 22, h / 2 + 18); c.lineTo(-w / 2 + 18, h / 2 + 10); c.fill();
    c.strokeStyle = '#5a4630'; c.lineWidth = 4; [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(s => { c.beginPath(); c.moveTo(s[0] * w * .42, s[1] * h * .42); c.lineTo(s[0] * w * .3, s[1] * h * .3); c.stroke(); });
    const pw = w * .72, ph = h * .72;
    c.fillStyle = L ? '#7d6646' : '#5b4c37'; c.fillRect(-pw / 2, -ph / 2, pw, ph);
    if (L === 0) { c.fillStyle = '#1d1e19'; c.fillRect(-pw / 2 + 4, -ph / 2 + 6, pw * .5, ph * .4); c.strokeStyle = '#5a4630'; c.lineWidth = 2; c.beginPath(); c.moveTo(-pw / 2, ph / 2); c.lineTo(pw / 2, -ph / 3); c.stroke(); rubble(c, -w / 2, h / 2 - 6, w, 12, r, 6, ['#6b5236', '#5b4630']); return; }
    roofPlanks(c, -pw / 2 - 3, -ph / 2 - 3, pw + 6, ph * .7, L >= 2 ? '#576b52' : '#7c6038', r);
    if (L === 1) tarp(c, -pw / 2, -ph / 2, pw * .6, ph * .5, '#4f6f84');
    sandbags(c, -pw / 2, ph / 2 - 4, pw, 8);
    if (L >= 3) { c.fillStyle = '#e9e1b5'; c.beginPath(); c.arc(pw / 2 - 4, ph / 2 - 8, 4, 0, 7); c.fill(); c.fillStyle = '#2f342f'; c.fillRect(-4, ph / 2 - 10, 8, 5); }
    flag(c, -pw / 2 + 3, -ph / 2 + 2, FACTION[owner || 'neutral']);
  },
};

AS.sprites = {
  building(kind, level, owner, w, h) {
    const key = 'b:' + kind + level + (owner || 'n') + w + 'x' + h;
    return cached(key, () => {
      const pad = 60, top = kind === 'radio' ? 90 : pad;
      const im = canvas(w + pad * 2, h + top + pad), c = im.getContext('2d');
      c.translate(pad + w / 2, top + h / 2);
      // Contact shadow to the south-east.
      if (kind !== 'quarry' && kind !== 'guard') { c.fillStyle = '#10140f55'; c.beginPath(); c.moveTo(-w / 2 + 8, -h / 2 + 10); c.lineTo(w / 2 + 16, -h / 2 + 22); c.lineTo(w / 2 + 16, h / 2 + 12); c.lineTo(-w / 2 + 14, h / 2 + 12); c.closePath(); c.fill(); }
      const r = rng(strSeed(kind) + level * .1 + .03);
      PAINT[kind](c, w, h, level, owner, r);
      return { im, ox: pad + w / 2, oy: top + h / 2 };
    });
  },
  ruin(sprite, w, h, seed) {
    const key = 'r:' + sprite + w + 'x' + h + Math.floor(seed * 7);
    return cached(key, () => {
      const pad = 60, im = canvas(w + pad * 2, h + pad * 2 + 60), c = im.getContext('2d');
      c.translate(pad + w / 2, pad + 60 + h / 2);
      const r = rng(seed + .17);
      c.fillStyle = '#10140f55'; c.beginPath(); c.moveTo(-w / 2 + 8, -h / 2 + 10); c.lineTo(w / 2 + 16, -h / 2 + 22); c.lineTo(w / 2 + 16, h / 2 + 12); c.lineTo(-w / 2 + 14, h / 2 + 12); c.closePath(); c.fill();
      RUIN[sprite](c, w, h, r);
      return { im, ox: pad + w / 2, oy: pad + 60 + h / 2 };
    });
  },
};

/* ---------- abandoned places ---------- */
const RUIN = {
  hall(c, w, h, r) { PAINT.workshop(c, w, h, 0, null, r); hole(c, w * .3, -h * .1, w * .2, h * .3, r); rubble(c, -w / 2 - 10, h / 2, w + 20, 26, r, 20); weeds(c, -w / 2, -h / 2, w, h, r, 10); },
  chimney(c, w, h, r) { c.fillStyle = '#00000040'; c.beginPath(); c.moveTo(-w / 2, 0); c.lineTo(80, 50); c.lineTo(90, 30); c.lineTo(0, -w / 2); c.fill(); c.fillStyle = '#7b5444'; c.beginPath(); c.arc(0, 0, w / 2, 0, 7); c.fill(); c.fillStyle = '#5f3e33'; c.beginPath(); c.arc(0, 0, w / 2 - 4, 0, 7); c.fill(); c.fillStyle = '#141412'; c.beginPath(); c.arc(0, 0, w / 2 - 9, 0, 7); c.fill(); c.strokeStyle = '#d6cfc0'; c.lineWidth = 3; c.beginPath(); c.arc(0, 0, w / 2 - 1, 0, 1.4); c.stroke(); c.strokeStyle = '#b4473a'; c.beginPath(); c.arc(0, 0, w / 2 - 1, 1.6, 3); c.stroke(); },
  shed(c, w, h, r) { roofMetal(c, -w / 2, -h / 2, w, h - 12, '#6b6158', false); hole(c, 0, -h * .1, w * .4, h * .4, r); facade(c, -w / 2, h / 2 - 12, w, 12, '#5f574c', 0, r, { windows: 2 }); c.fillStyle = '#7a4a2c66'; for (let i = 0; i < 6; i++) c.fillRect(-w / 2 + r() * w, -h / 2 + r() * h, 9, 4); },
  shop(c, w, h, r) { roofFlat(c, -w / 2, -h / 2, w, h - 14, '#5f625b', r); facade(c, -w / 2, h / 2 - 14, w, 14, '#c9c2ad', 0, r, { windows: 4 }); c.fillStyle = '#a84235'; c.fillRect(-w / 2, h / 2 - 16, w, 3); // canopy and pumps south of the shop
    c.fillStyle = '#00000033'; c.fillRect(-w / 2 + 6, h / 2 + 22, w, 70); c.fillStyle = '#d8d3c3'; c.fillRect(-w / 2 - 4, h / 2 + 16, w + 8, 66); c.fillStyle = '#a84235'; c.fillRect(-w / 2 - 4, h / 2 + 16, w + 8, 6); c.strokeStyle = '#00000020'; for (let i = 0; i < w + 8; i += 8) { c.beginPath(); c.moveTo(-w / 2 - 4 + i, h / 2 + 22); c.lineTo(-w / 2 - 4 + i, h / 2 + 82); c.stroke(); } hole(c, w * .2, h / 2 + 52, 30, 22, r); },
  pump(c) { c.fillStyle = '#6a6a5e'; c.fillRect(-12, -5, 24, 10); c.fillStyle = '#b5493a'; c.fillRect(-10, -4, 8, 8); c.fillRect(2, -4, 8, 8); },
  hangar(c, w, h, r) { PAINT.warehouse(c, w, h, 0, null, r); c.fillStyle = '#4f5b40'; c.fillRect(-w / 2, -h / 2, 6, h - 14); },
  barracks(c, w, h, r) { roofTiles(c, -w / 2, -h / 2, w, h - 14, '#5d6a52'); hole(c, -w * .15, -h * .15, w * .3, h * .3, r); facade(c, -w / 2, h / 2 - 14, w, 14, '#8f8a6c', 0, r, { windows: 4 }); },
  barn(c, w, h, r) { roofPlanks(c, -w / 2, -h / 2, w, h - 14, '#6b4a33', r); hole(c, w * .15, -h * .1, w * .35, h * .45, r); facade(c, -w / 2, h / 2 - 14, w, 14, '#7a4b38', 0, r, { windows: 2 }); rubble(c, -w / 2, h / 2 + 2, w, 14, r, 6, ['#6b5236', '#7b6242']); },
  silo(c, w) { c.fillStyle = '#00000040'; c.beginPath(); c.ellipse(10, 10, w / 2 + 4, w / 2, 0, 0, 7); c.fill(); const g = c.createRadialGradient(-6, -6, 2, 0, 0, w / 2); g.addColorStop(0, '#c2c2b5'); g.addColorStop(1, '#6d6e66'); c.fillStyle = g; c.beginPath(); c.arc(0, 0, w / 2, 0, 7); c.fill(); c.strokeStyle = '#00000030'; c.beginPath(); c.arc(0, 0, w / 3, 0, 7); c.stroke(); c.fillStyle = '#7a4a2c88'; c.beginPath(); c.arc(6, 4, 7, 0, 7); c.fill(); },
  izba(c, w, h, r) { roofPlanks(c, -w / 2 - 3, -h / 2, w + 6, h - 10, '#5d6153', r); if (r() < .7) hole(c, (r() - .5) * w * .4, -h * .1, w * .38, h * .4, r); c.fillStyle = '#6a4c32'; c.fillRect(-w / 2, h / 2 - 10, w, 10); for (let j = 1; j < 10; j += 3) { c.fillStyle = '#00000024'; c.fillRect(-w / 2, h / 2 - 10 + j, w, 1); } windowRow(c, -w / 2 + 4, h / 2 - 8, w - 8, 3, false, true); c.fillStyle = '#7b5a3a'; c.fillRect(w / 2 - 10, -h / 2 + 4, 7, 7); weeds(c, -w / 2 - 10, h / 2, w + 20, 14, r, 6); c.strokeStyle = '#7b6242'; c.lineWidth = 1.5; c.beginPath(); c.moveTo(-w / 2 - 12, h / 2 + 18); for (let i = 0; i < 6; i++) c.lineTo(-w / 2 - 12 + i * 18, h / 2 + 18 + (i % 2) * 3); c.stroke(); },
  tank(c, w, h, r) { c.fillStyle = '#00000040'; c.beginPath(); c.ellipse(12, 12, w / 2 + 4, w / 2, 0, 0, 7); c.fill(); const g = c.createRadialGradient(-w / 6, -w / 6, 3, 0, 0, w / 2); g.addColorStop(0, '#d6d4c8'); g.addColorStop(1, '#8a8a80'); c.fillStyle = g; c.beginPath(); c.arc(0, 0, w / 2, 0, 7); c.fill(); c.strokeStyle = '#6f6f66'; c.lineWidth = 1; for (let k = 1; k < 4; k++) { c.beginPath(); c.arc(0, 0, w / 2 * k / 4, 0, 7); c.stroke(); } c.fillStyle = '#7a4a2caa'; for (let i = 0; i < 5; i++) { c.beginPath(); c.arc((r() - .5) * w * .7, (r() - .5) * w * .7, 3 + r() * 5, 0, 7); c.fill(); } c.fillStyle = '#3d3d38'; c.fillRect(-3, -3, 6, 6); },
  derrick(c, w) { c.strokeStyle = '#00000044'; c.lineWidth = 3; c.beginPath(); c.moveTo(0, 0); c.lineTo(60, 40); c.stroke(); c.strokeStyle = '#8a3d2e'; c.lineWidth = 2; c.strokeRect(-w / 2, -w / 2, w, w); c.beginPath(); c.moveTo(-w / 2, -w / 2); c.lineTo(w / 2, w / 2); c.moveTo(w / 2, -w / 2); c.lineTo(-w / 2, w / 2); c.stroke(); c.fillStyle = '#3a3a33'; c.fillRect(-4, -4, 8, 8); },
  headframe(c, w, h, r) { c.fillStyle = '#5f5a50'; c.fillRect(-w / 2, -h / 2, w, h); c.strokeStyle = '#86453a'; c.lineWidth = 3; c.strokeRect(-w / 2 + 6, -h / 2 + 6, w - 12, h - 12); c.beginPath(); c.moveTo(-w / 2 + 6, -h / 2 + 6); c.lineTo(w / 2 - 6, h / 2 - 6); c.moveTo(w / 2 - 6, -h / 2 + 6); c.lineTo(-w / 2 + 6, h / 2 - 6); c.stroke(); c.fillStyle = '#2b2a26'; c.beginPath(); c.arc(0, 0, 14, 0, 7); c.fill(); c.strokeStyle = '#c0b9a5'; c.lineWidth = 2; c.beginPath(); c.arc(0, 0, 14, 0, 7); c.stroke(); },
  heap(c, w, h, r) { for (let k = 0; k < 4; k++) { c.fillStyle = ['#4f4b44', '#5c5850', '#6b665c', '#7a756a'][k]; c.beginPath(); c.ellipse(0, 0, w / 2 * (1 - k * .2), h / 2 * (1 - k * .2), 0, 0, 7); c.fill(); } speckle(c, -w / 2, -h / 2, w, h, ['#3b3833', '#8c877a'], 50, 3, r); },
  station(c, w, h, r) { roofTiles(c, -w / 2, -h / 2, w, h - 16, '#7a5b49'); hole(c, w * .2, -h * .15, w * .2, h * .4, r); facade(c, -w / 2, h / 2 - 16, w, 16, '#c6b48a', 0, r, { windows: 7 }); // rails
    for (let k = 0; k < 2; k++) { const y = h / 2 + 30 + k * 34; c.fillStyle = '#5b4a3a'; for (let i = -w; i < w; i += 9) c.fillRect(i, y - 6, 4, 18); c.fillStyle = '#8c8c86'; c.fillRect(-w, y - 3, w * 2, 2); c.fillRect(-w, y + 7, w * 2, 2); } },
  wagon(c, w, h, r) { c.fillStyle = '#00000040'; c.fillRect(4, 4, w, h); c.translate(-w / 2, -h / 2); roofMetal(c, 0, 0, w, h, ['#6c3a2c', '#4f5a4a', '#5a5f66'][Math.floor(r() * 3)], true); c.fillStyle = '#7a4a2c88'; for (let i = 0; i < 6; i++) c.fillRect(r() * w, r() * h, 10, 6); c.fillStyle = '#1c1c18'; c.fillRect(w * .4, 0, w * .2, 4); },
};

/* ---------- trees and plants, viewed from above ---------- */
AS.sprites.tree = function (type, v) {
  return cached('t:' + type + v, () => {
    const s = type === 'bush' ? 36 : 96, im = canvas(s * 1.5, s * 1.5), c = im.getContext('2d'), cx = s * .62, cy = s * .62;
    const r = rng(.13 + v * .071 + type.length * .01);
    const shadow = (rad) => { c.fillStyle = '#0f150e55'; c.beginPath(); c.ellipse(cx + rad * .45, cy + rad * .5, rad * 1.02, rad * .82, .4, 0, 7); c.fill(); };
    if (type === 'spruce' || type === 'snow') {
      const rad = 22 + v * 2.5; shadow(rad);
      const layers = [[1, '#1f3326'], [.78, '#28402d'], [.56, '#325036'], [.32, '#3e6040']];
      layers.forEach(([k, col], li) => { c.fillStyle = col; c.beginPath(); const n = 11 + li; for (let i = 0; i <= n * 2; i++) { const a = i / (n * 2) * Math.PI * 2 + li * .3, rr2 = rad * k * (i % 2 ? .62 : 1) * (.9 + r() * .15); const px = cx + Math.cos(a) * rr2, py = cy + Math.sin(a) * rr2; i ? c.lineTo(px, py) : c.moveTo(px, py); } c.fill();
        if (type === 'snow' && li < 3) { c.fillStyle = '#dfe6e6' + (li === 2 ? 'ee' : 'aa'); c.beginPath(); for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2 + li * .3; c.moveTo(cx + Math.cos(a) * rad * k * .55, cy + Math.sin(a) * rad * k * .55); c.arc(cx + Math.cos(a) * rad * k * .8 - 2, cy + Math.sin(a) * rad * k * .8 - 2, 2.6 - li * .5, 0, 7); } c.fill(); } });
      c.fillStyle = '#ffffff12'; c.beginPath(); c.arc(cx - rad * .3, cy - rad * .3, rad * .45, 0, 7); c.fill();
      c.fillStyle = '#4a3b28'; c.beginPath(); c.arc(cx, cy, 2.2, 0, 7); c.fill();
    } else if (type === 'pine') {
      const rad = 20 + v * 2; shadow(rad);
      for (let k = 0; k < 7; k++) { const a = k * 2.4 + r(), d = rad * .45 * r(); c.fillStyle = ['#2b4630', '#355536', '#2f4b31'][k % 3]; c.beginPath(); c.arc(cx + Math.cos(a) * d, cy + Math.sin(a) * d, rad * (.45 + r() * .2), 0, 7); c.fill(); }
      for (let k = 0; k < 40; k++) { const a = r() * 6.28, d = r() * rad * .9; c.fillStyle = k % 2 ? '#47704566' : '#1a2b1c55'; c.fillRect(cx + Math.cos(a) * d, cy + Math.sin(a) * d, 2, 2); }
      c.fillStyle = '#ffffff10'; c.beginPath(); c.arc(cx - rad * .35, cy - rad * .35, rad * .5, 0, 7); c.fill();
    } else if (type === 'birch' || type === 'autumn') {
      const rad = 19 + v * 2; shadow(rad);
      c.strokeStyle = '#e8e3d6'; c.lineWidth = 3; c.beginPath(); c.moveTo(cx, cy); c.lineTo(cx + 6, cy + 10); c.stroke();
      const pal = type === 'birch' ? ['#5d7a3c', '#6d8a45', '#7f9c51', '#4e6934'] : ['#a6873a', '#b9933d', '#8f6f2f', '#7c7a3a'];
      for (let k = 0; k < 14; k++) { const a = r() * 6.28, d = r() * rad * .6; c.fillStyle = pal[k % 4]; c.beginPath(); c.arc(cx + Math.cos(a) * d, cy + Math.sin(a) * d, rad * (.3 + r() * .2), 0, 7); c.fill(); }
      for (let k = 0; k < 30; k++) { const a = r() * 6.28, d = r() * rad; c.fillStyle = k % 3 ? '#ffffff1c' : '#00000022'; c.beginPath(); c.arc(cx + Math.cos(a) * d, cy + Math.sin(a) * d, 1.6, 0, 7); c.fill(); }
    } else if (type === 'dead') {
      const rad = 16 + v * 2; c.strokeStyle = '#0f150e44'; c.lineWidth = 3; c.beginPath(); c.moveTo(cx + 4, cy + 4); c.lineTo(cx + rad + 10, cy + rad * .8 + 6); c.stroke();
      c.strokeStyle = '#5a4a38'; for (let k = 0; k < 7; k++) { const a = k / 7 * 6.28 + r(); c.lineWidth = 2.4; c.beginPath(); c.moveTo(cx, cy); const mx = cx + Math.cos(a) * rad * .55, my = cy + Math.sin(a) * rad * .55; c.lineTo(mx, my); c.lineTo(cx + Math.cos(a + .3) * rad, cy + Math.sin(a + .3) * rad); c.stroke(); c.lineWidth = 1; c.beginPath(); c.moveTo(mx, my); c.lineTo(cx + Math.cos(a - .4) * rad * .9, cy + Math.sin(a - .4) * rad * .9); c.stroke(); }
      c.fillStyle = '#6b5a45'; c.beginPath(); c.arc(cx, cy, 3.5, 0, 7); c.fill();
    } else { // bush
      const rad = 9 + v; c.fillStyle = '#0f150e44'; c.beginPath(); c.ellipse(cx + 3, cy + 4, rad, rad * .8, 0, 0, 7); c.fill();
      for (let k = 0; k < 6; k++) { const a = r() * 6.28; c.fillStyle = ['#43592f', '#506a37', '#5f7a40'][k % 3]; c.beginPath(); c.arc(cx + Math.cos(a) * rad * .4, cy + Math.sin(a) * rad * .4, rad * .55, 0, 7); c.fill(); }
      if (v % 3 === 0) for (let k = 0; k < 4; k++) { c.fillStyle = '#b8483c'; c.beginPath(); c.arc(cx + (r() - .5) * rad, cy + (r() - .5) * rad, 1.3, 0, 7); c.fill(); }
    }
    return { im, ox: cx, oy: cy };
  });
};

/* ---------- vehicles, drawn facing +x and rotated at runtime ---------- */
AS.sprites.vehicle = function (type, tint, damage) {
  return cached('v:' + type + tint + (damage || 0), () => {
    const L = type === 'truck' ? 92 : type === 'bus' ? 110 : 64, W = type === 'truck' ? 36 : type === 'bus' ? 34 : 30;
    const im = canvas(L + 30, W + 30), c = im.getContext('2d'); c.translate(L / 2 + 15, W / 2 + 15);
    const r = rng(.31 + L * .001 + strSeed(tint));
    c.fillStyle = '#0d120e55'; rr(c, -L / 2 + 4, -W / 2 + 5, L, W, 8); c.fill();
    const wheel = (x, y) => { c.fillStyle = '#1b1c19'; rr(c, x - 7, y - 3.5, 14, 7, 2); c.fill(); c.fillStyle = '#3c3d37'; c.fillRect(x - 5, y - 1, 10, 2); };
    const wreck = type === 'wreck' || type === 'bus';
    if (!wreck || r() < .5) { const ax = L / 2 - 14; [[-ax + 2, -W / 2 + 1], [-ax + 2, W / 2 - 1], [ax - 4, -W / 2 + 1], [ax - 4, W / 2 - 1]].forEach(p => wheel(p[0], p[1])); if (type === 'truck') { wheel(-ax + 18, -W / 2 + 1); wheel(-ax + 18, W / 2 - 1); } }
    const body = tint;
    if (type === 'truck') {
      c.fillStyle = shade(body, -.1); rr(c, -L / 2, -W / 2 + 1, L - 26, W - 2, 3); c.fill();
      c.fillStyle = body; c.fillRect(-L / 2 + 2, -W / 2 + 3, L - 30, W - 6);
      c.strokeStyle = '#00000033'; c.lineWidth = 1; for (let i = -L / 2 + 8; i < L / 2 - 30; i += 9) { c.beginPath(); c.moveTo(i, -W / 2 + 3); c.lineTo(i, W / 2 - 3); c.stroke(); }
      c.fillStyle = '#ffffff1a'; c.fillRect(-L / 2 + 2, -W / 2 + 3, L - 30, 4);
      c.fillStyle = '#5c6a5d'; rr(c, L / 2 - 26, -W / 2 + 2, 26, W - 4, 4); c.fill();
      c.fillStyle = '#2f4148'; c.fillRect(L / 2 - 12, -W / 2 + 5, 7, W - 10); c.fillStyle = '#9fc2c855'; c.fillRect(L / 2 - 11, -W / 2 + 6, 2, W - 12);
      c.fillStyle = '#e8dca0'; c.fillRect(L / 2 - 2, -W / 2 + 4, 2, 5); c.fillRect(L / 2 - 2, W / 2 - 9, 2, 5);
      return { im, ox: L / 2 + 15, oy: W / 2 + 15, L, W };
    }
    c.fillStyle = shade(body, -.25); rr(c, -L / 2, -W / 2, L, W, 7); c.fill();
    c.fillStyle = body; rr(c, -L / 2 + 2, -W / 2 + 2, L - 4, W - 4, 6); c.fill();
    c.fillStyle = '#ffffff22'; rr(c, -L / 2 + 4, -W / 2 + 3, L - 8, 4, 2); c.fill();
    if (type === 'bus') {
      c.fillStyle = shade(body, -.1); c.fillRect(-L / 2 + 6, -W / 2 + 6, L - 12, W - 12);
      for (let i = 0; i < 6; i++) { c.fillStyle = '#26323a'; c.fillRect(-L / 2 + 10 + i * 16, -W / 2 + 1, 11, 2); c.fillRect(-L / 2 + 10 + i * 16, W / 2 - 3, 11, 2); }
      c.fillStyle = '#1d211e'; c.fillRect(-10, -6, 22, 14);
    } else {
      // Windscreen, roof, rear window. Front is +x.
      c.fillStyle = '#2b3c42'; c.beginPath(); c.moveTo(L * .14, -W / 2 + 4); c.lineTo(L * .3, -W / 2 + 6); c.lineTo(L * .3, W / 2 - 6); c.lineTo(L * .14, W / 2 - 4); c.closePath(); c.fill();
      c.fillStyle = '#9fc2c844'; c.fillRect(L * .2, -W / 2 + 6, 2, W - 12);
      if (type === 'pickup') {
        c.fillStyle = shade(body, .06); c.fillRect(-L * .1, -W / 2 + 4, L * .26, W - 8);
        c.fillStyle = shade(body, -.35); c.fillRect(-L / 2 + 3, -W / 2 + 4, L * .38, W - 8);
        c.strokeStyle = '#8b8d86'; c.lineWidth = 1.5; c.strokeRect(-L / 2 + 5, -W / 2 + 6, L * .34, W - 12); c.beginPath(); for (let i = 0; i < 4; i++) { c.moveTo(-L / 2 + 8 + i * 6, -W / 2 + 6); c.lineTo(-L / 2 + 8 + i * 6, W / 2 - 6); } c.stroke();
        c.fillStyle = '#5b5e58'; c.fillRect(L / 2 - 4, -W / 2 + 2, 4, W - 4); // welded ram
        c.fillStyle = '#7d8079'; for (let i = 0; i < 4; i++) c.fillRect(L / 2 - 3, -W / 2 + 4 + i * 6, 2, 3);
        barrel(c, -L / 2 + 14, 0, '#4f5a44');
      } else {
        c.fillStyle = shade(body, .06); c.fillRect(-L * .24, -W / 2 + 4, L * .4, W - 8);
        c.fillStyle = '#2b3c42'; c.fillRect(-L * .32, -W / 2 + 5, 4, W - 10);
        if (type === 'suv') { c.strokeStyle = '#3f3a32'; c.lineWidth = 1.5; c.strokeRect(-L * .22, -W / 2 + 6, L * .34, W - 12); for (let i = 0; i < 3; i++) { c.beginPath(); c.moveTo(-L * .2 + i * 7, -W / 2 + 6); c.lineTo(-L * .2 + i * 7, W / 2 - 6); c.stroke(); } crate(c, -L * .16, -5, 9, '#8b6c45'); c.fillStyle = '#1b1c19'; c.beginPath(); c.arc(-L / 2 + 1, 0, 6, 0, 7); c.fill(); c.fillStyle = '#3c3d37'; c.beginPath(); c.arc(-L / 2 + 1, 0, 3, 0, 7); c.fill(); }
      }
      c.fillStyle = '#e8dca0'; c.fillRect(L / 2 - 3, -W / 2 + 3, 3, 5); c.fillRect(L / 2 - 3, W / 2 - 8, 3, 5);
      c.fillStyle = '#9a3a2c'; c.fillRect(-L / 2, -W / 2 + 3, 2, 4); c.fillRect(-L / 2, W / 2 - 7, 2, 4);
    }
    if (wreck || damage) {
      for (let i = 0; i < 9; i++) { c.fillStyle = ['#7a4a2ccc', '#5d3a25aa', '#3a2a1e99'][i % 3]; c.beginPath(); c.arc((r() - .5) * L * .9, (r() - .5) * W * .8, 2 + r() * 5, 0, 7); c.fill(); }
      c.fillStyle = '#16171499'; c.beginPath(); c.arc(L * .22, (r() - .5) * 6, 5, 0, 7); c.fill();
      c.strokeStyle = '#d6dad055'; c.lineWidth = .8; c.beginPath(); c.moveTo(L * .17, -4); c.lineTo(L * .26, 2); c.moveTo(L * .2, 4); c.lineTo(L * .26, -3); c.stroke();
      if (damage > 1) { soot(c, 0, 0, L * .4, W * .6); }
    }
    return { im, ox: L / 2 + 15, oy: W / 2 + 15, L, W };
  });
};

/* ---------- resource nodes ---------- */
AS.sprites.node = function (kind, v) {
  return cached('n:' + kind + v, () => {
    const im = canvas(80, 80), c = im.getContext('2d'); c.translate(40, 44); const r = rng(.5 + v * .1 + kind.length * .03);
    c.fillStyle = '#10140f55'; c.beginPath(); c.ellipse(5, 7, 24, 11, 0, 0, 7); c.fill();
    if (kind === 'wood') {
      for (let i = 0; i < 5; i++) { const y = -10 + (i % 3) * 7 - (i > 2 ? 4 : 0), x = i > 2 ? -2 : -6; c.fillStyle = '#6b4f30'; rr(c, x - 16, y, 36, 7, 3.5); c.fill(); c.fillStyle = '#c9a26a'; c.beginPath(); c.ellipse(x + 19, y + 3.5, 3, 3.5, 0, 0, 7); c.fill(); c.strokeStyle = '#8c6b40'; c.lineWidth = .8; c.beginPath(); c.arc(x + 19, y + 3.5, 1.6, 0, 7); c.stroke(); }
      c.fillStyle = '#7d8c8c'; c.save(); c.translate(14, 10); c.rotate(.5); c.fillRect(-2, -10, 4, 16); c.fillStyle = '#5b3e27'; c.fillRect(-1, 2, 2, 12); c.restore();
    } else if (kind === 'stone') {
      [[-10, 2, 13], [8, -2, 11], [0, -10, 9], [14, 9, 7]].forEach(s => { c.fillStyle = '#6f7064'; c.beginPath(); for (let i = 0; i < 7; i++) { const a = i / 7 * 6.28, k = s[2] * (.75 + r() * .3); i ? c.lineTo(s[0] + Math.cos(a) * k, s[1] + Math.sin(a) * k * .8) : c.moveTo(s[0] + Math.cos(a) * k, s[1] + Math.sin(a) * k * .8); } c.fill(); c.fillStyle = '#9b9a8a'; c.beginPath(); c.ellipse(s[0] - s[2] * .25, s[1] - s[2] * .25, s[2] * .5, s[2] * .35, -.5, 0, 7); c.fill(); });
    } else if (kind === 'metal') {
      c.save(); c.rotate(.2); c.fillStyle = '#5a5f5a'; c.fillRect(-22, -8, 30, 16); c.fillStyle = '#7a4a2c'; c.fillRect(-18, -6, 10, 6); c.fillStyle = '#8f948d'; c.fillRect(-4, -12, 6, 24); c.restore();
      c.strokeStyle = '#8f948d'; c.lineWidth = 3; c.beginPath(); c.moveTo(4, 8); c.lineTo(22, -6); c.stroke(); c.strokeStyle = '#6a3f2a'; c.lineWidth = 2; c.beginPath(); c.moveTo(8, 12); c.lineTo(24, 6); c.stroke();
      c.fillStyle = '#3c4140'; c.beginPath(); c.arc(-14, 12, 6, 0, 7); c.fill(); c.fillStyle = '#7d827d'; c.beginPath(); c.arc(-14, 12, 3, 0, 7); c.fill();
    } else if (kind === 'food') {
      crate(c, -18, -12, 18, '#8a6d48'); crate(c, 0, -10, 16, '#6f7d55'); c.fillStyle = '#b39d6f'; rr(c, -10, 4, 20, 12, 4); c.fill(); c.strokeStyle = '#7a6748'; c.beginPath(); c.moveTo(-8, 10); c.lineTo(8, 10); c.stroke(); c.fillStyle = '#c4553e'; c.beginPath(); c.arc(10, 10, 3, 0, 7); c.fill();
    } else {
      [[-8, -2, '#8a3d2e'], [6, -6, '#4f6a3e'], [2, 8, '#8a3d2e']].forEach(s => { c.fillStyle = '#00000040'; c.fillRect(s[0] - 6, s[1] - 7, 15, 17); c.fillStyle = s[2]; rr(c, s[0] - 8, s[1] - 9, 14, 17, 2); c.fill(); c.fillStyle = '#c9b477'; c.fillRect(s[0] - 4, s[1] - 11, 5, 3); c.strokeStyle = '#00000044'; c.lineWidth = 1.2; c.beginPath(); c.moveTo(s[0] - 6, s[1] - 6); c.lineTo(s[0] + 4, s[1] + 6); c.moveTo(s[0] + 4, s[1] - 6); c.lineTo(s[0] - 6, s[1] + 6); c.stroke(); });
    }
    return { im, ox: 40, oy: 44 };
  });
};

/* ---------- characters: painted every frame for smooth animation ---------- */
const SKIN = ['#c9a283', '#b98e6d', '#d8b597', '#a77c5c'];
AS.sprites.person = function (c, o) {
  // o: {faction, type, armor, weapon, phase, moving, run, aim, shot, busy, dead, seed}
  const seed = o.seed || 0, run = o.run ? 1.5 : 1;
  const sw = o.moving ? Math.sin(o.phase) * 5 * run : 0;
  const bandit = o.faction === 'bandits' || o.type === 'raider', marauder = o.type === 'marauder', militia = o.type === 'militia';
  const jacket = marauder ? ['#5b5442', '#4d4a3d', '#665a46'][Math.floor(seed * 3)] : militia ? '#6a6b4e' : bandit ? ['#2c2a28', '#3a2f28', '#2f3330'][Math.floor(seed * 3)] : ['#56664a', '#4f5f58', '#64694c'][Math.floor(seed * 3)];
  const pants = bandit ? '#24262a' : marauder ? '#3c3a33' : '#3d4639';
  if (o.dead) { c.fillStyle = '#5b1d1666'; c.beginPath(); c.ellipse(3, 2, 15, 9, .3, 0, 7); c.fill(); c.rotate(1.3); }
  c.fillStyle = '#0c120d55'; c.beginPath(); c.ellipse(3, 4, 13, 10, 0, 0, 7); c.fill();
  // Legs (forward is +x).
  c.fillStyle = pants; rr(c, -4 + sw, -8, 11, 6, 3); c.fill(); rr(c, -4 - sw, 2, 11, 6, 3); c.fill();
  c.fillStyle = '#1d1a16'; c.beginPath(); c.arc(7 + sw, -5, 2.8, 0, 7); c.arc(7 - sw, 5, 2.8, 0, 7); c.fill();
  // Backpack or bedroll for survivors.
  if (!bandit && !marauder && !militia) { c.fillStyle = '#6b5a3c'; rr(c, -12, -7, 7, 14, 3); c.fill(); c.fillStyle = '#8a7a52'; c.fillRect(-12, -6, 2, 12); }
  else if (marauder) { c.fillStyle = '#4c4232'; rr(c, -11, -5, 5, 10, 2); c.fill(); }
  // Torso and shoulders.
  c.fillStyle = shade(jacket, -.2); c.beginPath(); c.ellipse(0, 0, 8, 11.5, 0, 0, 7); c.fill();
  c.fillStyle = jacket; c.beginPath(); c.ellipse(.5, 0, 6.8, 10.5, 0, 0, 7); c.fill();
  if (o.armor >= 1) { c.fillStyle = o.armor >= 2 ? '#3c4436' : '#5d5a41'; rr(c, -5, -7, 10, 14, 3); c.fill(); c.fillStyle = shade(o.armor >= 2 ? '#3c4436' : '#5d5a41', .15); for (let i = 0; i < 3; i++) c.fillRect(1, -6 + i * 4.5, 3, 3); if (o.armor >= 2) { c.fillStyle = '#2b3128'; c.fillRect(-5, -8, 10, 2); c.fillRect(-5, 6, 10, 2); } }
  if (bandit && !marauder) { c.fillStyle = '#9b2f22'; c.fillRect(-2, 8, 5, 3); }
  // Arms: aim pose holds the weapon forward, interact reaches forward, walking swings.
  const aiming = o.aim || o.shot, reach = o.busy;
  c.fillStyle = jacket; c.strokeStyle = jacket; c.lineCap = 'round'; c.lineWidth = 4.2;
  const hand = SKIN[Math.floor(seed * 4)];
  if (aiming) {
    const recoil = o.shot ? -2.5 : 0;
    c.beginPath(); c.moveTo(1, -8); c.lineTo(10 + recoil, -3); c.moveTo(1, 8); c.lineTo(13 + recoil, 1); c.stroke();
    c.fillStyle = hand; c.beginPath(); c.arc(10 + recoil, -2.5, 2.2, 0, 7); c.arc(13 + recoil, 1, 2.2, 0, 7); c.fill();
    drawWeapon(c, o.weapon, recoil);
    if (o.shot && o.flash) { c.fillStyle = '#ffe7a0'; c.beginPath(); const fx = (o.weapon === 1 ? 33 : o.weapon === 2 ? 31 : 22) + recoil; c.moveTo(fx, 0); c.lineTo(fx + 9, -4); c.lineTo(fx + 14, 0); c.lineTo(fx + 9, 4); c.closePath(); c.fill(); c.fillStyle = '#fff8dd'; c.beginPath(); c.arc(fx + 2, 0, 2.5, 0, 7); c.fill(); }
  } else if (reach) {
    const k = Math.sin(o.phase * 1.4) * 2;
    c.beginPath(); c.moveTo(1, -8); c.lineTo(12 + k, -5); c.moveTo(1, 8); c.lineTo(12 - k, 5); c.stroke();
    c.fillStyle = hand; c.beginPath(); c.arc(12 + k, -5, 2.2, 0, 7); c.arc(12 - k, 5, 2.2, 0, 7); c.fill();
  } else {
    c.beginPath(); c.moveTo(0, -9); c.lineTo(-sw * .9 + 2, -11); c.moveTo(0, 9); c.lineTo(sw * .9 + 2, 11); c.stroke();
    c.fillStyle = hand; c.beginPath(); c.arc(-sw * .9 + 2.5, -11, 2, 0, 7); c.arc(sw * .9 + 2.5, 11, 2, 0, 7); c.fill();
    if (o.weapon >= 1) { c.save(); c.translate(-3, -3); c.rotate(.9); c.fillStyle = '#2a2a26'; c.fillRect(-12, -1.5, 24, 3); c.restore(); }
  }
  // Head with headwear.
  c.fillStyle = hand; c.beginPath(); c.arc(1, 0, 5.4, 0, 7); c.fill();
  const hat = marauder ? '#3f3a2e' : militia ? '#5d6145' : bandit ? (seed < .5 ? '#1a1a1a' : '#8e2b20') : (seed < .33 ? '#5c6e48' : seed < .66 ? '#7a6a4b' : '#475864');
  c.fillStyle = hat;
  if (bandit && seed >= .5) { c.beginPath(); c.arc(1, 0, 5.6, Math.PI * .5, Math.PI * 1.5); c.fill(); c.fillRect(-6, -1, 3, 2); }
  else if (militia) { c.beginPath(); c.arc(0, 0, 6.3, 0, 7); c.fill(); c.fillStyle = '#6f7353'; c.beginPath(); c.arc(-1, -1, 3.5, 0, 7); c.fill(); }
  else { c.beginPath(); c.arc(0, 0, 5.6, Math.PI * .35, Math.PI * 1.65); c.fill(); if (!bandit) { c.fillStyle = shade(hat, .2); c.fillRect(-3, -1, 3, 2); } }
  c.fillStyle = '#ffffff1e'; c.beginPath(); c.arc(-1, -2, 2.4, 0, 7); c.fill();
};
function drawWeapon(c, tier, recoil) {
  c.save(); c.translate(recoil, 0);
  if (tier === 1) { c.fillStyle = '#5b3d25'; c.fillRect(4, -1.8, 12, 3.6); c.fillStyle = '#2b2b27'; c.fillRect(14, -1.4, 18, 2.8); c.fillStyle = '#56575a'; c.fillRect(16, -2, 3, 4); }
  else if (tier === 2) { c.fillStyle = '#4b3523'; c.fillRect(2, -2, 9, 4); c.fillStyle = '#25262a'; c.fillRect(10, -2, 15, 4); c.fillRect(24, -1, 7, 2); c.fillStyle = '#3c3f44'; c.beginPath(); c.moveTo(16, 2); c.quadraticCurveTo(18, 8, 14, 9); c.lineTo(13, 2); c.fill(); c.fillStyle = '#5b3d25'; c.fillRect(19, -2.5, 5, 1.5); }
  else { c.fillStyle = '#2b2b29'; c.fillRect(11, -1.6, 10, 3.2); c.fillStyle = '#4a4a46'; c.fillRect(11, -1.6, 4, 3.2); }
  c.restore();
}

/* ---------- landmarks: one recognisable monument per settlement ---------- */
function shadowLong(c, x, y, w, len) { c.fillStyle = '#10140f4d'; c.beginPath(); c.moveTo(x - w / 2, y); c.lineTo(x + w / 2, y); c.lineTo(x + w / 2 + len * .8, y + len * .45); c.lineTo(x - w / 2 + len * .8, y + len * .45); c.closePath(); c.fill(); }
function spire(c, x, y, height, color) { shadowLong(c, x, y, 6, height * .9); c.fillStyle = color; c.beginPath(); c.moveTo(x - 5, y); c.lineTo(x, y - height); c.lineTo(x + 5, y); c.closePath(); c.fill(); c.fillStyle = '#ffffff55'; c.beginPath(); c.moveTo(x - 2, y); c.lineTo(x, y - height); c.lineTo(x, y); c.fill(); }
function dome(c, x, y, r, color, tip) { c.fillStyle = '#10140f55'; c.beginPath(); c.ellipse(x + r * .5, y + r * .45, r, r * .8, 0, 0, 7); c.fill(); const g = c.createRadialGradient(x - r * .35, y - r * .4, 1, x, y, r); g.addColorStop(0, shade(color, .45)); g.addColorStop(.6, color); g.addColorStop(1, shade(color, -.35)); c.fillStyle = g; c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); if (tip) { c.strokeStyle = '#e8c86a'; c.lineWidth = 1.6; c.beginPath(); c.moveTo(x, y - r * .2); c.lineTo(x, y - r - 9); c.moveTo(x - 3, y - r - 5); c.lineTo(x + 3, y - r - 5); c.stroke(); } }
function tentTower(c, x, y, s, wall, roof) { c.fillStyle = '#10140f55'; c.fillRect(x - s / 2 + 8, y - s / 2 + 8, s, s); c.fillStyle = wall; c.fillRect(x - s / 2, y - s / 2, s, s); c.fillStyle = shade(roof, .15); c.beginPath(); c.moveTo(x - s / 2, y - s / 2); c.lineTo(x, y); c.lineTo(x + s / 2, y - s / 2); c.fill(); c.fillStyle = roof; c.beginPath(); c.moveTo(x - s / 2, y - s / 2); c.lineTo(x, y); c.lineTo(x - s / 2, y + s / 2); c.fill(); c.fillStyle = shade(roof, -.25); c.beginPath(); c.moveTo(x + s / 2, y - s / 2); c.lineTo(x, y); c.lineTo(x + s / 2, y + s / 2); c.fill(); c.fillStyle = shade(roof, -.4); c.beginPath(); c.moveTo(x - s / 2, y + s / 2); c.lineTo(x, y); c.lineTo(x + s / 2, y + s / 2); c.fill(); }
function plinth(c, x, y, w, h, color) { c.fillStyle = '#10140f55'; c.fillRect(x - w / 2 + 6, y - h / 2 + 6, w, h); c.fillStyle = color || '#8d8a80'; c.fillRect(x - w / 2, y - h / 2, w, h); c.fillStyle = '#ffffff22'; c.fillRect(x - w / 2, y - h / 2, w, 3); c.fillStyle = '#00000030'; c.fillRect(x - w / 2, y + h / 2 - 5, w, 5); }
function water(c, x, y, w, h) { c.fillStyle = '#5b5a43'; rr(c, x - w / 2 - 4, y - h / 2 - 4, w + 8, h + 8, 10); c.fill(); c.fillStyle = '#2f4b55'; rr(c, x - w / 2, y - h / 2, w, h, 8); c.fill(); c.strokeStyle = '#9fc0c533'; c.lineWidth = 1; for (let i = 0; i < 6; i++) { c.beginPath(); c.moveTo(x - w / 3 + i * w / 9, y - h / 4 + (i % 3) * h / 5); c.lineTo(x - w / 3 + i * w / 9 + 12, y - h / 4 + (i % 3) * h / 5); c.stroke(); } }
function pavement(c, w, h) { c.fillStyle = '#7b786c'; rr(c, -w / 2, -h / 2, w, h, 6); c.fill(); c.strokeStyle = '#6a675c'; c.lineWidth = 1; for (let i = -w / 2 + 10; i < w / 2; i += 12) { c.beginPath(); c.moveTo(i, -h / 2); c.lineTo(i, h / 2); c.stroke(); } for (let j = -h / 2 + 10; j < h / 2; j += 12) { c.beginPath(); c.moveTo(-w / 2, j); c.lineTo(w / 2, j); c.stroke(); } }
function statue(c, x, y, s, color, cape) { shadowLong(c, x, y, s * .8, s * 3.2); c.fillStyle = color; c.beginPath(); c.ellipse(x, y, s * .55, s * .8, 0, 0, 7); c.fill(); if (cape) { c.fillStyle = shade(color, -.2); c.beginPath(); c.moveTo(x - s * .5, y - s * .2); c.quadraticCurveTo(x - s * 1.3, y + s * .6, x - s * .2, y + s * 1.1); c.lineTo(x + s * .2, y + s * .4); c.fill(); } c.fillStyle = shade(color, .2); c.beginPath(); c.arc(x, y - s * .45, s * .32, 0, 7); c.fill(); c.strokeStyle = color; c.lineWidth = s * .2; c.lineCap = 'round'; c.beginPath(); c.moveTo(x + s * .3, y - s * .1); c.lineTo(x + s * .9, y - s * .9); c.stroke(); }
const LANDMARK = {
  petersburg(c, w, h) { pavement(c, w, h); roofFlat(c, -w / 2 + 6, -h / 2 + 10, w - 12, h - 40, '#c7b26b', rng(.2)); facade(c, -w / 2 + 6, h / 2 - 30, w - 12, 18, '#d9c27a', 2, rng(.3), { windows: 9 }); for (let i = 0; i < 6; i++) { c.fillStyle = '#f2ecd8'; c.fillRect(-28 + i * 11, h / 2 - 30, 4, 18); } spire(c, 0, -h / 2 + 30, 110, '#e3b84a'); c.fillStyle = '#e3b84a'; c.beginPath(); c.moveTo(0, -h / 2 - 80); c.lineTo(8, -h / 2 - 75); c.lineTo(0, -h / 2 - 72); c.fill(); },
  moscow(c, w, h) { pavement(c, w, h); c.fillStyle = '#8d3a2c'; c.fillRect(-w / 2 + 6, -8, w - 12, 16); for (let i = -w / 2 + 6; i < w / 2 - 6; i += 9) { c.fillStyle = '#a3463a'; c.beginPath(); c.moveTo(i, -8); c.lineTo(i + 3, -14); c.lineTo(i + 6, -8); c.fill(); } tentTower(c, 0, 0, 56, '#a3463a', '#3f6b4f'); c.fillStyle = '#f2ecd8'; c.beginPath(); c.arc(0, 30, 9, 0, 7); c.fill(); c.strokeStyle = '#222'; c.lineWidth = 1.2; c.beginPath(); c.moveTo(0, 30); c.lineTo(0, 24); c.moveTo(0, 30); c.lineTo(4, 31); c.stroke(); spire(c, 0, 0, 52, '#3f6b4f'); c.fillStyle = '#e04434'; c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 4 : 9; c.lineTo(Math.cos(a) * r, -54 + Math.sin(a) * r); } c.fill(); },
  nizhny(c, w, h) { pavement(c, w, h); c.fillStyle = '#9b4434'; c.fillRect(-w / 2 + 4, -10, w - 8, 20); for (let i = -w / 2 + 4; i < w / 2 - 6; i += 12) { c.fillStyle = '#b4513f'; c.beginPath(); c.moveTo(i, -10); c.lineTo(i + 2, -18); c.lineTo(i + 5, -14); c.lineTo(i + 8, -18); c.lineTo(i + 10, -10); c.fill(); } tentTower(c, 0, 0, 50, '#a84a39', '#4d7a5a'); spire(c, 0, 0, 34, '#4d7a5a'); c.fillStyle = '#d9b85a'; c.beginPath(); c.arc(0, -36, 4, 0, 7); c.fill(); },
  kazan(c, w, h) { pavement(c, w, h); c.fillStyle = '#10140f44'; c.fillRect(-w / 2 + 20, -h / 2 + 24, w - 30, h - 34); c.fillStyle = '#ecebe4'; rr(c, -w / 2 + 14, -h / 2 + 18, w - 28, h - 36, 6); c.fill(); dome(c, 0, -4, 28, '#3d7fb5', true); [[-w / 2 + 16, -h / 2 + 20], [w / 2 - 16, -h / 2 + 20], [-w / 2 + 16, h / 2 - 20], [w / 2 - 16, h / 2 - 20]].forEach(p => { spire(c, p[0], p[1], 70, '#3d7fb5'); c.fillStyle = '#ecebe4'; c.beginPath(); c.arc(p[0], p[1], 6, 0, 7); c.fill(); }); c.fillStyle = '#e8c86a'; c.beginPath(); c.arc(0, -50, 3, 0, 7); c.fill(); },
  perm(c, w, h) { pavement(c, w, h); roofTiles(c, -w / 2 + 12, -h / 2 + 30, w - 24, h - 56, '#7d8a7a'); facade(c, -w / 2 + 12, h / 2 - 26, w - 24, 16, '#ece6d4', 2, rng(.5), { windows: 7 }); tentTower(c, 0, -h / 2 + 22, 30, '#ece6d4', '#d9b85a'); spire(c, 0, -h / 2 + 22, 90, '#e3b84a'); },
  pervouralsk(c, w, h) { pavement(c, w, h); c.strokeStyle = '#d6cfb4'; c.lineWidth = 3; c.beginPath(); c.moveTo(0, -h / 2); c.lineTo(0, h / 2); c.stroke(); c.fillStyle = '#e6e0cc'; c.font = 'bold 9px Segoe UI'; c.textAlign = 'center'; c.fillText('ЕВРОПА', -32, h / 2 - 10); c.fillText('АЗИЯ', 32, h / 2 - 10); plinth(c, 0, 0, 34, 34, '#7e7a70'); spire(c, 0, 0, 120, '#f1ede2'); c.fillStyle = '#c94f3e'; c.fillRect(-3, -60, 6, 6); },
  shabrovsky(c, w, h) { c.fillStyle = '#4e5c37'; rr(c, -w / 2, -h / 2, w, h, 20); c.fill(); water(c, 10, 14, w - 40, h - 50); c.fillStyle = '#10140f55'; c.beginPath(); c.ellipse(-w / 2 + 50, -h / 2 + 44, 46, 28, 0, 0, 7); c.fill(); [['#c9c7bd', 0], ['#e3e1d8', 6], ['#b1afa4', 12]].forEach(([col, k]) => { c.fillStyle = col; c.beginPath(); c.moveTo(-w / 2 + 6 + k, -h / 2 + 50 - k); c.lineTo(-w / 2 + 30, -h / 2 + 12 + k); c.lineTo(-w / 2 + 72 - k, -h / 2 + 22 + k); c.lineTo(-w / 2 + 84 - k, -h / 2 + 56 - k); c.closePath(); c.fill(); }); const t = AS.sprites.tree('pine', 2); c.drawImage(t.im, w / 2 - 40 - t.ox, -h / 2 + 30 - t.oy); },
  ekaterinburg(c, w, h) { pavement(c, w, h); c.fillStyle = '#10140f44'; c.fillRect(-w / 2 + 22, -h / 2 + 22, w - 32, h - 30); c.fillStyle = '#efeadc'; rr(c, -w / 2 + 16, -h / 2 + 16, w - 32, h - 34, 8); c.fill(); facade(c, -w / 2 + 16, h / 2 - 32, w - 32, 14, '#efeadc', 2, rng(.6), { windows: 5, glass: '#5b6f7c' }); dome(c, 0, -10, 18, '#e3b84a', true); [[-34, -30], [34, -30], [-34, 12], [34, 12]].forEach(p => dome(c, p[0], p[1], 10, '#e3b84a', true)); },
  tyumen(c, w, h) { c.fillStyle = '#4e5c37'; c.fillRect(-w / 2, -h / 2, w, h); water(c, 0, 0, w, h * .5); c.fillStyle = '#10140f55'; c.fillRect(-w / 2 + 10, -2, w - 4, 16); c.fillStyle = '#b8473a'; c.fillRect(-w / 2, -8, w, 16); c.strokeStyle = '#d65a48'; c.lineWidth = 3; c.beginPath(); c.moveTo(-w / 2 + 10, -8); c.quadraticCurveTo(0, -46, w / 2 - 10, -8); c.stroke(); c.lineWidth = 1; for (let i = -w / 2 + 20; i < w / 2 - 10; i += 12) { const k = 1 - ((i / (w / 2 - 10)) ** 2); c.beginPath(); c.moveTo(i, -8); c.lineTo(i, -8 - k * 30); c.stroke(); } [-30, -10, 10, 30].forEach((x, i) => { c.fillStyle = ['#e2c86f', '#c87a6a', '#9fb3be', '#d79cb7'][i]; c.fillRect(x, -10, 4, 3); }); },
  novosibirsk(c, w, h) { pavement(c, w, h); c.fillStyle = '#10140f44'; c.fillRect(-w / 2 + 16, -h / 2 + 18, w - 24, h - 26); c.fillStyle = '#cbbd96'; rr(c, -w / 2 + 10, -h / 2 + 12, w - 20, h - 30, 6); c.fill(); facade(c, -w / 2 + 10, h / 2 - 32, w - 20, 16, '#d8cba5', 2, rng(.7), { windows: 8 }); for (let i = 0; i < 8; i++) { c.fillStyle = '#efe8d2'; c.fillRect(-42 + i * 12, h / 2 - 32, 4, 16); } dome(c, 0, -12, 40, '#b8c0c4'); c.strokeStyle = '#ffffff44'; c.lineWidth = 1; for (let a = 0; a < 6.28; a += .5) { c.beginPath(); c.moveTo(0, -12); c.lineTo(Math.cos(a) * 38, -12 + Math.sin(a) * 38); c.stroke(); } },
  krasnoyarsk(c, w, h) { c.fillStyle = '#4e5c37'; c.beginPath(); c.ellipse(0, 6, w / 2, h / 2 - 4, 0, 0, 7); c.fill(); c.fillStyle = '#5f6e43'; c.beginPath(); c.ellipse(-6, 0, w / 2 - 16, h / 2 - 18, 0, 0, 7); c.fill(); c.fillStyle = '#10140f55'; c.fillRect(-12, -8, 34, 34); c.fillStyle = '#f0ebdf'; c.fillRect(-18, -14, 34, 34); c.fillStyle = '#7d6a4f'; c.fillRect(-4, 14, 6, 6); tentTower(c, -1, -4, 22, '#f0ebdf', '#c9a85a'); dome(c, -1, -4, 8, '#e3b84a', true); },
  irkutsk(c, w, h) { water(c, 0, 0, w, h); c.save(); c.translate(0, 4); c.fillStyle = '#10140f55'; c.beginPath(); c.ellipse(8, 8, w / 2 - 12, 22, 0, 0, 7); c.fill(); c.fillStyle = '#1f2421'; c.beginPath(); c.moveTo(-w / 2 + 14, -18); c.lineTo(w / 2 - 34, -18); c.quadraticCurveTo(w / 2 - 6, 0, w / 2 - 34, 18); c.lineTo(-w / 2 + 14, 18); c.closePath(); c.fill(); c.fillStyle = '#a5392c'; c.fillRect(-w / 2 + 14, 12, w - 50, 6); c.fillStyle = '#e8e4d6'; c.fillRect(-36, -12, 60, 24); c.fillStyle = '#c9c4ae'; c.fillRect(-24, -8, 36, 16); c.fillStyle = '#d5a83f'; c.beginPath(); c.arc(-4, 0, 7, 0, 7); c.fill(); c.fillStyle = '#1f2421'; c.beginPath(); c.arc(-4, 0, 3, 0, 7); c.fill(); c.restore(); },
  yakutsk(c, w, h) { c.fillStyle = '#dfe6e6'; rr(c, -w / 2, -h / 2, w, h, 14); c.fill(); c.fillStyle = '#6b4f30'; for (let i = -w / 2 + 6; i < w / 2 - 6; i += 7) { c.fillRect(i, 22, 6, 14); c.beginPath(); c.moveTo(i, 22); c.lineTo(i + 3, 17); c.lineTo(i + 6, 22); c.fill(); } c.fillStyle = '#10140f55'; c.fillRect(-20, -18, 52, 52); c.fillStyle = '#7a5a38'; c.fillRect(-26, -24, 52, 52); for (let k = -24; k < 28; k += 6) { c.fillStyle = '#00000022'; c.fillRect(-26, k, 52, 1); } tentTower(c, 0, -2, 40, '#7a5a38', '#8d8a7c'); spire(c, 0, -2, 36, '#8d8a7c'); c.fillStyle = '#5b4630'; c.fillRect(-3, -42, 6, 8); },
  khabarovsk(c, w, h) { c.fillStyle = '#2f4b55'; c.fillRect(-w / 2, -h / 2, w, h); c.fillStyle = '#6f6d62'; c.beginPath(); c.moveTo(-w / 2, -h / 2); c.lineTo(w / 2 - 20, -h / 2); c.lineTo(w / 2 - 40, 10); c.lineTo(10, h / 2 - 10); c.lineTo(-w / 2, h / 2); c.closePath(); c.fill(); c.fillStyle = '#4e5c37'; c.beginPath(); c.moveTo(-w / 2, -h / 2); c.lineTo(w / 2 - 40, -h / 2); c.lineTo(w / 2 - 60, 0); c.lineTo(-w / 2, h / 2 - 20); c.fill(); dome(c, 10, -6, 22, '#4f7d64'); c.strokeStyle = '#f0ebdf'; c.lineWidth = 2; for (let a = 0; a < 6.28; a += .79) { c.beginPath(); c.arc(10 + Math.cos(a) * 20, -6 + Math.sin(a) * 20, 2, 0, 7); c.stroke(); } },
  vladivostok(c, w, h) { water(c, 0, 0, w, h); c.fillStyle = '#10140f55'; c.fillRect(-w / 2, 2, w, 18); c.fillStyle = '#8b8a84'; c.fillRect(-w / 2, -6, w, 16); c.fillStyle = '#d6d0b5'; c.fillRect(-w / 2, 1, w, 2); [-44, 44].forEach(x => { shadowLong(c, x, 2, 14, 90); c.fillStyle = '#c9cbc6'; c.beginPath(); c.moveTo(x - 10, 12); c.lineTo(x, -70); c.lineTo(x + 10, 12); c.lineTo(x + 4, 12); c.lineTo(x, -40); c.lineTo(x - 4, 12); c.fill(); c.strokeStyle = '#e9c45a'; c.lineWidth = .8; for (let k = -1; k <= 1; k += .25) { c.beginPath(); c.moveTo(x, -60); c.lineTo(x + k * 40, 2); c.stroke(); } }); },
  murmansk(c, w, h) { pavement(c, w, h); plinth(c, 0, 10, 44, 60, '#77746b'); statue(c, 0, -6, 18, '#9a978d', true); c.strokeStyle = '#5b5a52'; c.lineWidth = 3; c.beginPath(); c.moveTo(10, -14); c.lineTo(20, -40); c.stroke(); },
  arkhangelsk(c, w, h) { c.fillStyle = '#4e5c37'; rr(c, -w / 2, -h / 2, w, h, 16); c.fill(); c.fillStyle = '#10140f44'; c.fillRect(-30, -16, 70, 56); roofPlanks(c, -40, -8, 30, 40, '#7d7464', rng(.81)); roofPlanks(c, 10, -8, 30, 40, '#7d7464', rng(.82)); c.fillStyle = '#6b4c32'; c.fillRect(-40, 32, 80, 10); c.fillStyle = '#6b4c32'; c.fillRect(-14, -24, 28, 56); tentTower(c, 0, -2, 30, '#6b4c32', '#8f8a7c'); spire(c, 0, -2, 58, '#8f8a7c'); dome(c, 0, -58, 5, '#9aa3a6', true); },
  vorkuta(c, w, h) { pavement(c, w, h); shadowLong(c, 0, 20, 50, 80); c.strokeStyle = '#4d5a5f'; c.lineWidth = 4; c.beginPath(); c.moveTo(-30, 30); c.lineTo(-10, -50); c.lineTo(10, -50); c.lineTo(30, 30); c.moveTo(-24, 6); c.lineTo(24, 6); c.moveTo(-18, -20); c.lineTo(18, -20); c.stroke(); c.lineWidth = 1.5; c.beginPath(); c.moveTo(-30, 30); c.lineTo(18, -20); c.moveTo(30, 30); c.lineTo(-18, -20); c.stroke(); [-10, 10].forEach(x => { c.strokeStyle = '#2b3236'; c.lineWidth = 3; c.beginPath(); c.arc(x, -54, 9, 0, 7); c.stroke(); }); c.fillStyle = '#d9402f'; c.beginPath(); for (let i = 0; i < 10; i++) { const a = -Math.PI / 2 + i * Math.PI / 5, r = i % 2 ? 4 : 9; c.lineTo(Math.cos(a) * r, -70 + Math.sin(a) * r); } c.fill(); },
  norilsk(c, w, h) { pavement(c, w, h); [[-28, 10, 18], [26, -6, 15]].forEach(([x, y, r]) => { shadowLong(c, x, y, r * 2, 120); for (let k = 0; k < 4; k++) { c.fillStyle = k % 2 ? '#f0ece4' : '#c2402f'; c.beginPath(); c.arc(x, y, r - k * 3, 0, 7); c.fill(); } c.fillStyle = '#16181a'; c.beginPath(); c.arc(x, y, r - 12, 0, 7); c.fill(); }); },
  tagil(c, w, h) { pavement(c, w, h); plinth(c, 0, 4, 100, 60, '#8a877c'); c.save(); c.translate(0, 0); c.rotate(-.2); c.fillStyle = '#10140f55'; c.fillRect(-36, -14, 76, 40); c.fillStyle = '#2c2d27'; c.fillRect(-40, -22, 76, 10); c.fillRect(-40, 12, 76, 10); c.fillStyle = '#4f6342'; rr(c, -38, -14, 72, 28, 4); c.fill(); c.fillStyle = '#5c7350'; c.beginPath(); c.arc(-4, 0, 13, 0, 7); c.fill(); c.fillStyle = '#41543a'; c.fillRect(6, -2, 50, 4); c.fillStyle = '#c94f3e'; c.beginPath(); c.arc(-4, 0, 3, 0, 7); c.fill(); c.restore(); },
  revda(c, w, h) { c.fillStyle = '#4e5c37'; c.fillRect(-w / 2, -h / 2, w, h); water(c, 0, -h / 4, w, h / 2); c.fillStyle = '#10140f55'; c.fillRect(-w / 2, 4, w, 22); c.fillStyle = '#8b7d6a'; c.fillRect(-w / 2, -4, w, 22); for (let i = -w / 2; i < w / 2; i += 10) { c.fillStyle = (i / 10 | 0) % 2 ? '#9b8c77' : '#7d705f'; c.fillRect(i, -4, 9, 10); } c.fillStyle = '#3a3a35'; c.fillRect(-12, -6, 24, 26); c.fillStyle = '#9fc0c5aa'; c.fillRect(-8, 18, 16, 14); },
  polevskoy(c, w, h) { c.fillStyle = '#6a675c'; c.beginPath(); c.ellipse(0, 10, w / 2, h / 2 - 8, 0, 0, 7); c.fill(); c.fillStyle = '#7d7a6c'; c.beginPath(); c.ellipse(-6, 4, w / 2 - 20, h / 2 - 26, 0, 0, 7); c.fill(); plinth(c, 0, 4, 40, 34, '#5a5850'); statue(c, 0, -6, 18, '#2f8a6a', true); c.fillStyle = '#7fd0a5'; c.beginPath(); c.arc(0, -16, 3, 0, 7); c.fill(); },
  omsk(c, w, h) { pavement(c, w, h); c.fillStyle = '#10140f55'; c.fillRect(-w / 2 + 16, -12, w - 24, 38); c.fillStyle = '#efeadc'; c.fillRect(-w / 2 + 10, -18, w - 20, 34); c.fillStyle = '#3f6b4f'; c.fillRect(-w / 2 + 6, -24, w - 12, 14); c.fillStyle = '#5d5b52'; rr(c, -14, -2, 28, 18, 10); c.fill(); c.fillStyle = '#e3b84a'; c.beginPath(); c.arc(0, -17, 4, 0, 7); c.fill(); },
  magadan(c, w, h) { c.fillStyle = '#6a675c'; c.beginPath(); c.ellipse(0, 8, w / 2, h / 2 - 6, 0, 0, 7); c.fill(); shadowLong(c, 0, 0, 70, 70); const g = c.createRadialGradient(-12, -16, 4, 0, 0, 46); g.addColorStop(0, '#b4b0a6'); g.addColorStop(1, '#6f6c64'); c.fillStyle = g; c.beginPath(); c.ellipse(0, -4, 34, 44, 0, 0, 7); c.fill(); c.fillStyle = '#3d3b36'; c.beginPath(); c.ellipse(-12, -14, 6, 4, 0, 0, 7); c.ellipse(12, -14, 6, 4, 0, 0, 7); c.fill(); c.fillRect(-2, -8, 4, 16); c.fillRect(-10, 18, 20, 3); for (let i = 0; i < 4; i++) { c.fillStyle = '#4f4c46'; c.fillRect(-14 + (i % 2) * 22, -6 + i * 6, 3, 8); } },
};
AS.sprites.landmark = function (tid, w, h) {
  return cached('lm:' + tid + w + 'x' + h, () => {
    const pad = 60, top = 140, im = canvas(w + pad * 2, h + top + pad), c = im.getContext('2d');
    c.translate(pad + w / 2, top + h / 2);
    (LANDMARK[tid] || LANDMARK.pervouralsk)(c, w, h);
    return { im, ox: pad + w / 2, oy: top + h / 2 };
  });
};
AS.sprites.cache = cache;
})();
