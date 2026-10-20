/* After Silence. Procedural sound: ambience, effects and generative music. No audio files needed. */
(function () {
'use strict';
const AS = window.AS = window.AS || {};
let ctx = null, master, sfx, music, amb, noise, delay, wind, windFilter, rain, engine, engineGain, engineFilter, drone, droneGain;
let nextChord = 0, nextNote = 0, chordIndex = 0, nextBird = 0, nextCricket = 0, nextStep = 0, tension = 0;
const A = AS.audio = { enabled: true, music: .55, sfx: .8 };
const CHORDS = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62], [50, 53, 57], [57, 60, 64], [52, 56, 59], [57, 60, 64]];
const PENTA = [57, 60, 62, 64, 67, 69, 72, 74, 76];
const hz = m => 440 * Math.pow(2, (m - 69) / 12);

function init() {
  if (ctx) return true;
  try { ctx = new (window.AudioContext || window.webkitAudioContext)(); } catch (e) { return false; }
  master = ctx.createGain(); master.connect(ctx.destination);
  sfx = ctx.createGain(); sfx.connect(master); music = ctx.createGain(); music.connect(master); amb = ctx.createGain(); amb.connect(master);
  noise = ctx.createBuffer(1, ctx.sampleRate * 2, ctx.sampleRate); const d = noise.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1;
  delay = ctx.createDelay(1); delay.delayTime.value = .38; const fb = ctx.createGain(); fb.gain.value = .32; const dl = ctx.createBiquadFilter(); dl.type = 'lowpass'; dl.frequency.value = 1800;
  delay.connect(dl); dl.connect(fb); fb.connect(delay); delay.connect(music);
  // Continuous beds: wind and rain.
  const loop = (filterType, freq, q) => { const s = ctx.createBufferSource(); s.buffer = noise; s.loop = true; const f = ctx.createBiquadFilter(); f.type = filterType; f.frequency.value = freq; f.Q.value = q || .7; const g = ctx.createGain(); g.gain.value = 0; s.connect(f); f.connect(g); g.connect(amb); s.start(); return { g, f }; };
  const w = loop('bandpass', 420, .5); wind = w.g; windFilter = w.f; rain = loop('highpass', 1400).g;
  engine = ctx.createOscillator(); engine.type = 'sawtooth'; engine.frequency.value = 38; engineFilter = ctx.createBiquadFilter(); engineFilter.type = 'lowpass'; engineFilter.frequency.value = 260; engineGain = ctx.createGain(); engineGain.gain.value = 0; engine.connect(engineFilter); engineFilter.connect(engineGain); engineGain.connect(sfx); engine.start();
  drone = ctx.createOscillator(); drone.type = 'sine'; drone.frequency.value = 55; droneGain = ctx.createGain(); droneGain.gain.value = 0; drone.connect(droneGain); droneGain.connect(music); drone.start();
  apply(); return true;
}
function apply() { if (!ctx) return; master.gain.value = A.enabled ? 1 : 0; sfx.gain.value = A.sfx; music.gain.value = A.music * .9; amb.gain.value = A.sfx * .9; }
A.setVolume = (kind, value) => { A[kind] = value; apply(); };
A.toggle = () => { A.enabled = !A.enabled; init(); apply(); return A.enabled; };
A.resume = () => { if (init() && ctx.state === 'suspended') ctx.resume(); };

function env(g, t, peak, attack, decay) { g.gain.cancelScheduledValues(t); g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(peak, t + attack); g.gain.exponentialRampToValueAtTime(.0001, t + attack + decay); }
function burst(dur, type, freq, peak, dest, q, sweepTo) {
  const t = ctx.currentTime, s = ctx.createBufferSource(); s.buffer = noise; const f = ctx.createBiquadFilter(); f.type = type; f.frequency.setValueAtTime(freq, t); if (sweepTo) f.frequency.exponentialRampToValueAtTime(sweepTo, t + dur); f.Q.value = q || 1;
  const g = ctx.createGain(); s.connect(f); f.connect(g); g.connect(dest || sfx); env(g, t, peak, .004, dur); s.start(t, Math.random()); s.stop(t + dur + .05);
}
function tone(freq, dur, type, peak, dest, to, attack) {
  const t = ctx.currentTime, o = ctx.createOscillator(), g = ctx.createGain(); o.type = type || 'sine'; o.frequency.setValueAtTime(freq, t); if (to) o.frequency.exponentialRampToValueAtTime(to, t + dur);
  o.connect(g); g.connect(dest || sfx); env(g, t, peak, attack || .005, dur); o.start(t); o.stop(t + dur + (attack || 0) + .05);
}
A.play = function (kind, distance) {
  if (!A.enabled || !init() || ctx.state !== 'running') return;
  const k = Math.max(0, 1 - (distance || 0) / 1500); if (k <= .02) return;
  if (kind.startsWith('shot')) {
    tension = Math.min(1, tension + .25);
    if (kind === 'shot1') { burst(.32, 'lowpass', 2400, .55 * k, sfx, .7, 300); tone(110, .25, 'sine', .5 * k, sfx, 40); }
    else if (kind === 'shot2') { burst(.09, 'bandpass', 1900, .42 * k, sfx, .9); tone(140, .1, 'square', .12 * k, sfx, 60); }
    else { burst(.16, 'bandpass', 1500, .4 * k, sfx, .8, 500); tone(150, .14, 'sine', .3 * k, sfx, 55); }
  } else if (kind === 'tower') { burst(.2, 'bandpass', 1100, .28 * k, sfx, .8, 400); }
  else if (kind === 'boom') { burst(1.4, 'lowpass', 900, .9 * k, sfx, .6, 70); tone(60, 1, 'sine', .7 * k, sfx, 30); tension = 1; }
  else if (kind === 'thunder') { burst(2.8, 'lowpass', 420, .6, amb, .5, 60); setTimeout(() => ctx && burst(1.6, 'lowpass', 200, .4, amb, .5, 50), 300); }
  else if (kind === 'step') { burst(.07, 'lowpass', A.surface === 'snow' ? 1800 : 700, .07, sfx, 1); }
  else if (kind === 'harvest') { [0, 120, 260].forEach(d => setTimeout(() => ctx && burst(.08, 'bandpass', 900 + Math.random() * 400, .25, sfx, 2), d)); }
  else if (kind === 'build') { [0, 220, 440].forEach(d => setTimeout(() => ctx && (tone(1800 + Math.random() * 300, .12, 'triangle', .14), burst(.05, 'highpass', 3000, .12)), d)); }
  else if (kind === 'door') { tone(180, .2, 'square', .06, sfx, 90); burst(.15, 'lowpass', 500, .2); }
  else if (kind === 'error') { tone(220, .18, 'triangle', .12, sfx, 160); }
  else if (kind === 'levelup') { [523, 659, 784, 1047].forEach((f, i) => setTimeout(() => ctx && tone(f, .35, 'triangle', .12), i * 110)); }
  else if (kind === 'success') { tone(660, .14, 'triangle', .1); setTimeout(() => ctx && tone(990, .25, 'triangle', .1), 110); }
  else { tone(760, .12, 'sine', .07, sfx, 1100); }
};

/* Called every frame with the view: drives ambience, engine, footsteps and music. */
A.update = function (v) {
  if (!ctx || ctx.state !== 'running' || !v.state) return;
  const t = ctx.currentTime, st = v.state, me = st.me, kind = st.weather ? st.weather.kind : 'clear', night = (v.dark || 0) > .45;
  const snow = v.weatherMode === 'snow';
  A.surface = snow ? 'snow' : 'grass';
  wind.gain.setTargetAtTime(kind === 'storm' ? .32 : snow ? .2 : kind === 'rain' ? .12 : .06, t, 1.5);
  windFilter.frequency.setTargetAtTime(320 + Math.sin(t * .3) * 160 + (kind === 'storm' ? 300 : 0), t, .8);
  rain.gain.setTargetAtTime(v.weatherMode === 'rain' ? (kind === 'storm' ? .22 : .13) : 0, t, 1.2);
  const driving = me.vehicle, moving = me.moving;
  engineGain.gain.setTargetAtTime(driving ? (moving ? .11 : .05) : 0, t, .2);
  engine.frequency.setTargetAtTime(driving && moving ? 62 + Math.random() * 3 : 34, t, .4); engineFilter.frequency.setTargetAtTime(driving && moving ? 520 : 240, t, .4);
  if (!driving && moving && me.hp > 0 && t > nextStep) { nextStep = t + (me.sprint ? .28 : .42); A.play('step'); }
  if (!night && kind !== 'storm' && kind !== 'rain' && t > nextBird) { nextBird = t + 2 + Math.random() * 6; const f = 2200 + Math.random() * 1800; for (let i = 0; i < 2 + Math.floor(Math.random() * 3); i++) setTimeout(() => ctx && tone(f * (1 + Math.random() * .2), .09, 'sine', .025, amb, f * 1.3), i * 120); }
  if (night && kind === 'clear' && t > nextCricket) { nextCricket = t + .8 + Math.random() * 1.5; for (let i = 0; i < 4; i++) setTimeout(() => ctx && tone(4300, .03, 'sine', .012, amb), i * 45); }
  tension = Math.max(0, tension - .004);
  droneGain.gain.setTargetAtTime(tension * .05, t, .6);
  // Generative score: sparse minor chords with a pentatonic voice over a delay.
  if (A.music > 0 && t > nextChord) {
    nextChord = t + 9; const chord = CHORDS[chordIndex++ % CHORDS.length], low = night ? -12 : 0;
    chord.forEach((m, i) => { const o = ctx.createOscillator(), o2 = ctx.createOscillator(), f = ctx.createBiquadFilter(), g = ctx.createGain(); o.type = 'triangle'; o2.type = 'sawtooth'; o.frequency.value = hz(m + low); o2.frequency.value = hz(m + low) * 1.004; f.type = 'lowpass'; f.frequency.value = 700; o.connect(f); o2.connect(f); f.connect(g); g.connect(music); g.connect(delay); g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(.022 - i * .004, t + 2.5); g.gain.exponentialRampToValueAtTime(.0001, t + 9.5); o.start(t); o2.start(t); o.stop(t + 10); o2.stop(t + 10); });
  }
  if (A.music > 0 && t > nextNote) {
    nextNote = t + (night ? 2.4 : 1.4) + Math.random() * 2.5;
    if (Math.random() < .7) { const m = PENTA[Math.floor(Math.random() * PENTA.length)] + (night ? -12 : 0); const o = ctx.createOscillator(), g = ctx.createGain(); o.type = 'triangle'; o.frequency.value = hz(m); o.connect(g); g.connect(music); g.connect(delay); env(g, t, .035, .01, 2.2); o.start(t); o.stop(t + 2.4); }
  }
};
})();
