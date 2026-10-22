#!/usr/bin/env node
/* Rebuilds the extra hero frames in web/assets/hero.png from the hand-drawn ones.
   Usage: node tools/hero_frames.js [path/to/playwright]
   Needs Playwright with Chromium (dev machine only, not shipped). Cells 0-77 are the artist's frames and are kept
   as they are; everything from 78 on is rebuilt: the pickaxe from the chop frames, eating and drinking from the
   pistol pose, dressing a wound from the kneeling search, and the AK magazine change. Items are painted on top,
   moved parts are cut out of the same frame and the holes they leave are filled from the surrounding pixels. */
const path = require('path'), fs = require('fs');
const PW = process.argv[2] || '/opt/node22/lib/node_modules/playwright';
const { chromium } = require(PW);
const ATLAS = path.join(__dirname, '..', 'web', 'assets', 'hero.png');
const KEEP = 78;

async function main() {
  const browser = await chromium.launch(); const page = await browser.newPage();
  const src = 'data:image/png;base64,' + fs.readFileSync(ATLAS).toString('base64');
  const res = await page.evaluate(build, [src, KEEP]);
  fs.writeFileSync(ATLAS, Buffer.from(res.png.split(',')[1], 'base64'));
  console.log('hero.png:', res.w + 'x' + res.h, res.frames);
  await browser.close();
}

// Runs inside the page.
async function build([src, KEEP]) {
  const HC = 160, COLS = 12;
  const im = new Image(); im.src = src; await im.decode();
  const canvas = () => { const c = document.createElement('canvas'); c.width = c.height = HC; return c; };
  const cell = n => { const c = canvas(); c.getContext('2d').drawImage(im, (n % COLS) * HC, Math.floor(n / COLS) * HC, HC, HC, 0, 0, HC, HC); return c; };
  const copy = s => { const c = canvas(); c.getContext('2d').drawImage(s, 0, 0); return c; };
  const pix = c => c.getContext('2d').getImageData(0, 0, HC, HC);
  const inEll = (x, y, e) => ((x - e[0]) / e[2]) ** 2 + ((y - e[1]) / (e[3] || e[2])) ** 2 <= 1;
  // Fill the masked pixels from their known neighbours, ring by ring (colour and alpha, premultiplied).
  function inpaint(c, mask) {
    const d = pix(c), p = d.data, hole = new Uint8Array(HC * HC);
    for (let y = 0; y < HC; y++) for (let x = 0; x < HC; x++) if (mask(x, y, p, (y * HC + x) * 4)) hole[y * HC + x] = 1;
    for (let pass = 0; pass < 80; pass++) {
      const next = [];
      for (let y = 0; y < HC; y++) for (let x = 0; x < HC; x++) {
        if (!hole[y * HC + x]) continue;
        let r = 0, g = 0, b = 0, a = 0, n = 0;
        for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
          const xx = x + dx, yy = y + dy; if ((!dx && !dy) || xx < 0 || yy < 0 || xx >= HC || yy >= HC || hole[yy * HC + xx]) continue;
          const i = (yy * HC + xx) * 4, al = p[i + 3] / 255; r += p[i] * al; g += p[i + 1] * al; b += p[i + 2] * al; a += al; n++;
        }
        if (n >= 2 || (n && pass > 40)) next.push([x, y, r, g, b, a, n]);
      }
      if (!next.length) break;
      next.forEach(([x, y, r, g, b, a, n]) => { const i = (y * HC + x) * 4; p[i] = a ? r / a : 0; p[i + 1] = a ? g / a : 0; p[i + 2] = a ? b / a : 0; p[i + 3] = a / n * 255; hole[y * HC + x] = 0; });
    }
    c.getContext('2d').putImageData(d, 0, 0); return c;
  }
  function erase(c, mask) {
    const d = pix(c), p = d.data;
    for (let y = 0; y < HC; y++) for (let x = 0; x < HC; x++) { const i = (y * HC + x) * 4; if (mask(x, y, p, i)) p[i + 3] = 0; }
    c.getContext('2d').putImageData(d, 0, 0); return c;
  }
  // A part of the frame inside an ellipse, soft at the rim; `keep` can drop pixels by colour.
  function cut(c, e, keep) {
    const out = canvas(), d = pix(c), p = d.data;
    for (let y = 0; y < HC; y++) for (let x = 0; x < HC; x++) {
      const i = (y * HC + x) * 4, k = Math.sqrt(((x - e[0]) / e[2]) ** 2 + ((y - e[1]) / (e[3] || e[2])) ** 2);
      if (k > 1 || (keep && !keep(p, i))) p[i + 3] = 0; else if (k > .82) p[i + 3] *= (1 - k) / .18;
    }
    out.getContext('2d').putImageData(d, 0, 0); return out;
  }
  const sat = (p, i) => Math.max(p[i], p[i + 1], p[i + 2]) - Math.min(p[i], p[i + 1], p[i + 2]);
  const skin = (p, i) => p[i] > 120 && p[i] - p[i + 2] > 45 && p[i] > p[i + 1];
  const OUT = '#1c1a19';
  // Painted items keep some colour (saturation above 0.14) or stay dark, so the hoodie tint by the grey mask leaves them alone.
  function outlined(x, path, fill, w) { x.save(); path(); x.lineJoin = 'round'; x.strokeStyle = OUT; x.lineWidth = w || 1.6; x.stroke(); x.fillStyle = fill; x.fill(); x.restore(); }

  /* ----- pickaxe: the chop frames with the axe head replaced ----- */
  // Per frame: grip A, end of the handle E, centre and radius of the axe head to remove.
  const PICK = [
    { n: 72, A: [77, 88], E: [111, 113], H: [113, 120], r: 12 },
    { n: 73, A: [45, 62], E: [37, 22], H: [35, 17], r: 13 },
    { n: 74, A: [80, 37], E: [49, 16], H: [41, 19], r: 13 },
    { n: 75, A: [82, 97], E: [95, 126], H: [95, 133], r: 10 },
    { n: 76, A: [79.5, 100], E: [79.5, 131], H: [82, 138], r: 14 },
    { n: 77, A: [90, 92], E: [110, 116], H: [111, 121], r: 11 },
  ];
  function pickaxe(x, A, E) {
    const L = Math.hypot(E[0] - A[0], E[1] - A[1]), d = [(E[0] - A[0]) / L, (E[1] - A[1]) / L], q = [-d[1], d[0]];
    const P = (u, v) => [E[0] + d[0] * u + q[0] * v, E[1] + d[1] * u + q[1] * v];
    // Handle runs on past the hands to the head.
    const h0 = P(-14, 0), h1 = P(3, 0);
    x.lineCap = 'round'; x.strokeStyle = OUT; x.lineWidth = 4.6; x.beginPath(); x.moveTo(h0[0], h0[1]); x.lineTo(h1[0], h1[1]); x.stroke();
    x.strokeStyle = '#7a4f2b'; x.lineWidth = 2.8; x.stroke(); x.strokeStyle = '#a06c3e'; x.lineWidth = 1; x.beginPath(); x.moveTo(...P(-14, -.6)); x.lineTo(...P(2, -.6)); x.stroke();
    // Head: a curved bar across the handle, both ends drawn to points and bent back towards the grip.
    const g = x.createLinearGradient(...P(4, 0), ...P(-3, 0)); g.addColorStop(0, '#b4c3d4'); g.addColorStop(.5, '#7f8ea0'); g.addColorStop(1, '#3f4650');
    outlined(x, () => { x.beginPath(); x.moveTo(...P(-6, -16)); x.quadraticCurveTo(...P(4, -9), ...P(3, 0)); x.quadraticCurveTo(...P(4, 9), ...P(-6, 16));
      x.quadraticCurveTo(...P(0, 8), ...P(-2.5, 0)); x.quadraticCurveTo(...P(0, -8), ...P(-6, -16)); x.closePath(); }, g, 1.5);
    // Steel eye around the handle and a glint along the top edge.
    outlined(x, () => { x.beginPath(); x.moveTo(...P(4, -3)); x.lineTo(...P(4, 3)); x.lineTo(...P(-3.5, 3)); x.lineTo(...P(-3.5, -3)); x.closePath(); }, '#4c5560', 1.2);
    x.strokeStyle = '#d2e0efaa'; x.lineWidth = .8; x.beginPath(); x.moveTo(...P(-3, -12)); x.quadraticCurveTo(...P(3, -6), ...P(3, -3)); x.stroke();
  }
  const mine = PICK.map(f => {
    const c = cell(f.n), x = c.getContext('2d');
    const L = Math.hypot(f.E[0] - f.A[0], f.E[1] - f.A[1]), d = [(f.E[0] - f.A[0]) / L, (f.E[1] - f.A[1]) / L];
    // Drop the axe head: everything there except wood beyond the end of the handle.
    erase(c, (px, py, p, i) => inEll(px, py, [f.H[0], f.H[1], f.r]) && (px - f.E[0]) * d[0] + (py - f.E[1]) * d[1] > -5 && !(p[i] - p[i + 2] > 30 && p[i] > 70));
    pickaxe(x, f.A, f.E);
    // The hands stay on top of the handle.
    x.drawImage(cut(cell(f.n), [f.A[0], f.A[1], 9], skin), 0, 0);
    return c;
  });

  /* ----- eating and drinking: the pistol pose with the gun taken out ----- */
  const BASE = 13, HEAD = [80, 33.5, 14.5, 15], HANDS = [79, 69, 14, 10];
  function pose(item, up, head) {
    const src = cell(BASE);
    // The hands without the gun.
    const hands = cut(src, HANDS, (p, i) => !(sat(p, i) < 26 && Math.max(p[i], p[i + 1], p[i + 2]) < 110));
    const headL = cut(src, HEAD);
    const c = copy(src); inpaint(c, (x, y) => inEll(x, y, HANDS) || (head && inEll(x, y, HEAD)));
    const x = c.getContext('2d');
    if (head) x.drawImage(headL, 0, head);
    x.drawImage(hands, 0, -up);
    item(x, 79, 69 - up);
    // Fingers close round the thing they hold.
    x.save(); x.beginPath(); x.ellipse(79, 69 - up, 8, 7, 0, 0, 7); x.ellipse(79, 69 - up, 3.5, 3, 0, 0, 7); x.clip('evenodd');
    x.drawImage(cut(src, HANDS, skin), 0, -up); x.restore();
    return c;
  }
  const can = (x, cx, cy) => {
    outlined(x, () => { x.beginPath(); x.ellipse(cx, cy, 5.6, 5, 0, 0, 7); }, '#a3b1c1', 1.4);
    const g = x.createRadialGradient(cx - 1, cy - 1, .5, cx, cy, 4.2); g.addColorStop(0, '#9b5a3a'); g.addColorStop(1, '#5e3020');
    x.fillStyle = g; x.beginPath(); x.ellipse(cx, cy, 4.1, 3.6, 0, 0, 7); x.fill();
    x.fillStyle = '#e2d6b0'; x.fillRect(cx - 2, cy - 1, 1.2, 1); x.fillRect(cx + 1, cy + 1, 1.2, 1);
  };
  const eat = [pose(can, 0, 0), pose(can, 4, 0), pose(can, 7, 0)];
  // A plastic water bottle: seen from above while held, then tipped up to the mouth (bottom towards the viewer).
  const flaskTop = (x, cx, cy) => {
    outlined(x, () => { x.beginPath(); x.ellipse(cx, cy + 1, 6.5, 4.2, 0, 0, 7); }, '#4f7f9a', 1.4);
    x.fillStyle = '#9cc6d8'; x.beginPath(); x.ellipse(cx - 1, cy, 4.4, 2.4, 0, 0, 7); x.fill();
    outlined(x, () => { x.beginPath(); x.arc(cx, cy - 3, 1.9, 0, 7); }, '#2b4f9a', 1);
  };
  const flaskUp = len => (x, cx, cy) => {
    const top = cy - 9, bot = top + len;
    outlined(x, () => { x.beginPath(); x.moveTo(cx - 2, top); x.lineTo(cx + 2, top); x.lineTo(cx + 5.5, top + 4); x.lineTo(cx + 5.5, bot); x.ellipse(cx, bot, 5.5, 3.4, 0, 0, Math.PI); x.lineTo(cx - 5.5, top + 4); x.closePath(); }, '#4f7f9a', 1.4);
    x.fillStyle = '#9cc6d8'; x.fillRect(cx - 3.5, top + 4, 2.5, len - 4);
    x.fillStyle = '#3b6a86'; x.beginPath(); x.ellipse(cx, bot, 4.4, 2.4, 0, 0, 7); x.fill();
  };
  const drink = [pose(flaskTop, 0, 0), pose(flaskUp(14), 5, 0), pose(flaskUp(10), 8, 0)];

  /* ----- dressing a wound: kneeling, the bag replaced by a roll of bandage on the forearm ----- */
  const KNEEL = 58, RHAND = [101, 63, 6.5, 7];
  function dress(wrap, roll, hand) {
    const src = cell(KNEEL), c = copy(src);
    const bag = (x, y, p, i) => x > 80 && x < 112 && y > 58 && y < 88 && p[i + 3] > 20 && p[i] > p[i + 2] + 12 && p[i + 1] > p[i + 2] + 8 && !skin(p, i);
    const glare = (x, y, p, i) => x > 88 && x < 104 && y > 48 && y < 66 && p[i] > 200 && p[i + 1] > 200 && p[i + 2] > 200;
    const handL = cut(src, RHAND, skin);
    inpaint(c, (x, y, p, i) => bag(x, y, p, i) || glare(x, y, p, i) || (hand && inEll(x, y, RHAND)));
    const x = c.getContext('2d');
    // Turns of bandage round the left forearm, near the wrist.
    x.save(); x.translate(80, 79); x.rotate(-.25);
    outlined(x, () => { x.beginPath(); x.roundRect(-wrap, -4.2, wrap + 3, 8.4, 2.5); }, '#efe3c8', 1.3);
    x.strokeStyle = '#c4b393'; x.lineWidth = .8; for (let k = -wrap + 3; k < 2; k += 3) { x.beginPath(); x.moveTo(k, -4); x.lineTo(k + 1.5, 4); x.stroke(); }
    x.fillStyle = '#b5413855'; x.fillRect(-wrap + 2, -1, 3, 2);
    x.restore();
    // The roll in the right hand, a tail running to the forearm.
    const [rx, ry] = roll;
    x.strokeStyle = '#ecdcba'; x.lineWidth = 2.4; x.beginPath(); x.moveTo(82, 78); x.quadraticCurveTo((rx + 82) / 2, ry + 6, rx, ry); x.stroke();
    outlined(x, () => { x.beginPath(); x.ellipse(rx, ry, 4.2, 3.6, -.4, 0, 7); }, '#f1e4c6', 1.3);
    x.fillStyle = '#c9b48e'; x.beginPath(); x.arc(rx, ry, 1.3, 0, 7); x.fill();
    x.drawImage(handL, hand ? hand[0] : 0, hand ? hand[1] : 0);
    return c;
  }
  const bandage = [dress(6, [100, 67], null), dress(10, [93, 74], [-7, 8]), dress(13, [96, 84], [-4, 18])];

  /* ----- AK magazine change, on frame 27 (the left hand is off the handguard) ----- */
  const AKB = 27, LH = [104, 65, 6.5, 7.5], MAG = (x, y, p, i) => x > 78 && x < 93 && y > 68 && y < 86 && sat(p, i) < 30 && Math.max(p[i], p[i + 1], p[i + 2]) < 95;
  const akMag = (x, cx, cy, a) => {
    x.save(); x.translate(cx, cy); x.rotate(a);
    outlined(x, () => { x.beginPath(); x.moveTo(-2.6, -6); x.lineTo(2.6, -6); x.quadraticCurveTo(3.6, 1, 5.5, 6); x.lineTo(.5, 7.5); x.quadraticCurveTo(-1.6, 1, -2.6, -6); x.closePath(); }, '#34322e', 1.2);
    x.strokeStyle = '#5b5852'; x.lineWidth = .8; x.beginPath(); x.moveTo(-1, -5); x.quadraticCurveTo(0, 1, 2.2, 6); x.stroke();
    x.restore();
  };
  // Pixels of the rifle itself (blued steel and wood), redrawn over a forearm that passes under it.
  const gunPx = (p, i) => p[i + 3] > 40 && ((sat(p, i) < 28 && Math.max(p[i], p[i + 1], p[i + 2]) < 90) || (p[i] > 70 && p[i + 1] < p[i] * .62 && p[i + 2] < p[i + 1]));
  function akFrame(noMag, hand, mag) {
    const src = cell(AKB), c = copy(src), handL = cut(src, LH, skin);
    inpaint(c, (x, y, p, i) => (noMag && MAG(x, y, p, i)) || (hand && inEll(x, y, LH)));
    const x = c.getContext('2d');
    if (hand) {
      // The forearm follows the hand under the rifle: a sleeve from the elbow to the moved wrist.
      const wx = LH[0] + hand[0] + 2, wy = LH[1] + hand[1] - 4;
      x.lineCap = 'round'; x.strokeStyle = OUT; x.lineWidth = 7; x.beginPath(); x.moveTo(107, 57); x.lineTo(wx, wy); x.stroke();
      x.strokeStyle = '#80807e'; x.lineWidth = 5; x.stroke();
      x.strokeStyle = '#a3a3a1'; x.lineWidth = 1.4; x.beginPath(); x.moveTo(107.5, 56); x.lineTo(wx + .8, wy - 1.2); x.stroke();
      x.drawImage(cut(src, [96, 70, 16, 12], gunPx), 0, 0);
    }
    if (mag) akMag(x, LH[0] + (hand ? hand[0] : 0) + mag[0], LH[1] + (hand ? hand[1] : 0) + mag[1], mag[2]);
    x.drawImage(handL, hand ? hand[0] : 0, hand ? hand[1] : 0);
    return c;
  }
  // Hand on the magazine (out, and later back in); hand by the pouch with the well empty; the fresh magazine in the hand.
  const reload = [akFrame(false, [-13, 12], null), akFrame(true, null, null), akFrame(true, null, [-1, 5, .9])];

  const added = { mine, eat, drink, bandage, reload }, frames = {};
  let n = KEEP; const list = [];
  Object.keys(added).forEach(k => { frames[k] = [n, added[k].length]; added[k].forEach(f => { list.push(f); n++; }); });
  const rows = Math.ceil(n / COLS), out = document.createElement('canvas'); out.width = COLS * HC; out.height = rows * HC;
  const o = out.getContext('2d');
  for (let i = 0; i < KEEP; i++) o.drawImage(im, (i % COLS) * HC, Math.floor(i / COLS) * HC, HC, HC, (i % COLS) * HC, Math.floor(i / COLS) * HC, HC, HC);
  list.forEach((f, i) => o.drawImage(f, ((KEEP + i) % COLS) * HC, Math.floor((KEEP + i) / COLS) * HC));
  return { png: out.toDataURL('image/png'), w: out.width, h: out.height, frames };
}

main().catch(e => { console.error(e); process.exit(1); });
