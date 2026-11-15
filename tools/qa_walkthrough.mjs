import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const BASE = 'http://127.0.0.1:43196';
const RPK = path.join(ROOT, 'dist/com.antigravity.ginka.rw5.debug.0.1.2.rpk');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getJson(p) {
  const res = await fetch(BASE + p);
  const text = await res.text();
  if (!res.ok) throw Error(`${p} -> ${res.status}: ${text}`);
  return JSON.parse(text);
}

async function shot(name, delayMs = 800) {
  if (delayMs > 0) await sleep(delayMs);
  const res = await fetch(`${BASE}/screen?out=${encodeURIComponent(name)}`);
  if (!res.ok) throw Error(`screen ${name} -> ${res.status}: ${await res.text()}`);
  const buf = Buffer.from(await res.arrayBuffer());
  console.log('SHOT', name, buf.length, 'bytes');
  return buf;
}

const cmd = process.argv[2] || 'boot-and-start';

if (cmd === 'boot-and-start') {
  const deadline = Date.now() + 90000;
  let st = null;
  while (Date.now() < deadline) {
    try {
      st = await getJson('/status');
      if (st.bootReady && st.grpcReady) break;
    } catch {}
    await sleep(1000);
  }
  if (!st || !st.bootReady || !st.grpcReady) throw Error('Emulator did not become ready: ' + JSON.stringify(st));
  console.log('READY', JSON.stringify(st));
  const inst = await getJson('/install?rpk=' + encodeURIComponent(RPK));
  console.log('INSTALL', JSON.stringify(inst));
  const started = await getJson('/start');
  console.log('START', JSON.stringify(started));
  let shotBuf = await shot('30_title.png', 11500);
  if (shotBuf.length < 5000) {
    await getJson('/wake');
    shotBuf = await shot('30_title.png', 1500);
  }
  const info = await getJson('/info');
  console.log('INFO', JSON.stringify(info));
  const log = await getJson('/logtail?n=2500');
  console.log('LOGTAIL_START\n' + log.log + '\nLOGTAIL_END');
} else if (cmd === 'sequence') {
  const steps = JSON.parse(process.argv[3]);
  for (const s of steps) {
    if (s.tap) {
      await getJson(`/tap?x=${s.tap[0]}&y=${s.tap[1]}`);
      console.log('TAP', s.tap);
    } else if (s.longpress) {
      await getJson(`/longpress?x=${s.longpress[0]}&y=${s.longpress[1]}&ms=${s.ms || 750}`);
      console.log('LONGPRESS', s.longpress);
    } else if (s.drag) {
      await getJson(`/drag?x0=${s.drag[0]}&y0=${s.drag[1]}&x1=${s.drag[2]}&y1=${s.drag[3]}`);
      console.log('DRAG', s.drag);
    } else if (s.stop) {
      console.log('STOP', await getJson('/stop'));
    } else if (s.start) {
      console.log('START', await getJson('/start'));
      await getJson('/wake');
    } else if (s.shot) {
      await shot(s.shot, s.delay ?? 900);
    } else if (s.wait) {
      await sleep(s.wait);
    } else if (s.log) {
      const l = await getJson('/logtail?n=3000');
      console.log('LOGTAIL:\n' + l.log);
    }
  }
} else if (cmd === 'shutdown') {
  console.log(await getJson('/shutdown'));
}
