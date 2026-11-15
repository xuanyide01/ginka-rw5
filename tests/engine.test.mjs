import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function loadModule(relPath) {
  let code = fs.readFileSync(path.join(root, relPath), 'utf8').replace(/export\s*\{[\s\S]*?\};?/m, '');
  code += '\n;globalThis.__exp = {create,checkpoint,restore,routeUnlocked,enterRoute,matches,locate,advance,choose,skipChapter,previous,resolveStage};';
  const box = {};
  vm.runInNewContext(code, box);
  return box.__exp;
}

const e = loadModule('src/common/engine.js');
const graph = JSON.parse(fs.readFileSync(path.join(root, 'converted/graph.json'), 'utf8'));
const assets = JSON.parse(
  fs.readFileSync(path.join(root, 'src/common/assets.js'), 'utf8').replace('export const assets=', '').replace(/;\s*$/, '')
);

function copy(x) {
  return JSON.parse(JSON.stringify(x));
}

function fastToDecision(s) {
  for (let i = 0; i < 2000; i++) {
    const p = e.locate(graph, s);
    if (p.type === 'choice' || p.type === 'end') return p;
    s.index = graph.nodes[s.node].count;
  }
  throw Error('Traversal loop at ' + s.node);
}

test('all graph edges and choices resolve cleanly and story chunks match node counts', () => {
  let chunkTexts = 0;
  for (const [id, n] of Object.entries(graph.nodes)) {
    if (n.terminal) continue;
    assert.equal(n.count >= 0, true, id);
    const sum = (n.chunks || []).reduce((acc, c) => acc + c.count, 0);
    assert.equal(sum, n.count, id);
    chunkTexts += sum;
    for (const edge of [...n.next, ...n.choices]) {
      assert.ok(edge.to === '@end' || graph.nodes[edge.to], `${id} -> ${edge.to}`);
    }
  }
  assert.equal(chunkTexts, 14998);
});

test('branching paths reach start clear and bad endings, and unlock next -> after progressively', () => {
  assert.equal(e.routeUnlocked(graph, 'next', {}), false);
  assert.equal(e.routeUnlocked(graph, 'after', {}), false);

  const pending = [e.create(graph, {}, 'start')];
  const completes = new Set();
  let paths = 0;
  while (pending.length) {
    const s = pending.pop();
    const p = fastToDecision(s);
    if (p.type === 'end') {
      paths++;
      for (const k of Object.keys(s.progress)) completes.add(k);
      continue;
    }
    for (let i = 0; i < p.items.length; i++) {
      const nxt = copy(s);
      e.choose(graph, nxt, i);
      pending.push(nxt);
    }
  }
  assert.ok(paths >= 2, `Expected multiple paths, got ${paths}`);
  assert.ok(completes.has('start'));
  assert.ok(completes.has('scn901') || completes.has('scn902') || completes.has('scn903') || completes.has('scn904'));

  // NEXT requires start; AFTER requires next
  assert.equal(e.routeUnlocked(graph, 'next', { start: true }), true);
  assert.equal(e.routeUnlocked(graph, 'after', { start: true }), false);

  const stNext0 = e.create(graph, { start: true }, 'start');
  assert.equal(e.enterRoute(graph, stNext0, 'next'), true);
  const pNextChoice = fastToDecision(stNext0);
  assert.equal(pNextChoice.type, 'choice');
  assert.equal(pNextChoice.items.length, 2);

  const stNextBad = copy(stNext0);
  e.choose(graph, stNextBad, 0);
  assert.equal(fastToDecision(stNextBad).type, 'end');
  assert.equal(stNextBad.progress.scn904, true);

  const stNext = copy(stNext0);
  e.choose(graph, stNext, 1);
  const pNext = fastToDecision(stNext);
  assert.equal(pNext.type, 'end');
  assert.equal(stNext.progress.next, true);
  assert.equal(e.routeUnlocked(graph, 'after', stNext.progress), true);

  const stAfter = e.create(graph, stNext.progress, 'start');
  assert.equal(e.enterRoute(graph, stAfter, 'after'), true);
  const pAfter = fastToDecision(stAfter);
  assert.equal(pAfter.type, 'end');
  assert.equal(stAfter.progress.after, true);
});

test('checkpoint, restore, previous, and skipChapter maintain flag & history invariants', () => {
  const s = e.create(graph, {}, 'start');
  const firstChoice = fastToDecision(s);
  assert.equal(firstChoice.type, 'choice');
  const before = e.checkpoint(s);
  e.choose(graph, s, 0);
  const restored = e.restore(graph, e.checkpoint(s));
  assert.deepEqual(copy(restored.flag), copy(s.flag));
  e.previous(graph, s);
  assert.deepEqual(copy(s.flag), copy(before.flag));
  assert.equal(e.locate(graph, s).type, 'choice');

  const sk = e.create(graph, {}, 'start');
  const startScript = graph.nodes[sk.node].source[0];
  e.skipChapter(graph, sk);
  assert.notEqual(graph.nodes[sk.node].source[0], startScript);

  // Skipping across chapters onto a choice must resolve stageFile/stageIndex for CG & portraits
  let skChoice = e.locate(graph, sk);
  for (let i = 0; i < 6 && skChoice.type === 'text'; i++) {
    skChoice = e.skipChapter(graph, sk);
  }
  assert.equal(skChoice.type, 'choice');
  assert.ok(skChoice.stageFile);
  const stageFrames = JSON.parse(fs.readFileSync(path.join(root, 'src/common/story', skChoice.stageFile), 'utf8'));
  assert.ok(stageFrames[skChoice.stageIndex]);
});

test('chapter preview never modifies unlock progress', () => {
  const s = e.create(graph, {}, 'start');
  s.progression = 'chapter';
  const clearNode = Object.entries(graph.nodes).find(([, n]) => n.complete && n.complete.includes('start'))[0];
  s.node = clearNode;
  s.index = graph.nodes[clearNode].count;
  const p = e.locate(graph, s);
  assert.equal(p.type, 'end');
  assert.equal(s.progress.start, undefined);
});

test('resolveStage produces valid files and aligned portrait patches for real story chunks', () => {
  let checkedPortrait = false;
  let checkedFrames = 0;
  for (const node of Object.values(graph.nodes)) {
    for (const chunk of node.chunks || []) {
      const frames = JSON.parse(fs.readFileSync(path.join(root, 'src/common/story', chunk.file), 'utf8'));
      for (const fr of frames) {
        const st = e.resolveStage(assets, fr);
        checkedFrames++;
        if (st.background) {
          assert.ok(st.background.startsWith('/common/images/'));
          assert.ok(fs.existsSync(path.join(root, 'src', st.background)));
        }
        for (const p of st.portraits) {
          assert.ok(fs.existsSync(path.join(root, 'src', p.src)));
          if (p.patch) {
            assert.ok(fs.existsSync(path.join(root, 'src', p.patch)));
            assert.ok(p.patchWidth > 0 && p.patchHeight > 0);
            checkedPortrait = true;
          }
        }
      }
      if (checkedPortrait && checkedFrames >= 150) break;
    }
    if (checkedPortrait && checkedFrames >= 150) break;
  }
  assert.equal(checkedPortrait, true);
});

test('all static/composite backdrops normalize to exact 432x243 and ev005al+ev005a uses clean single CG', () => {
  const imageMap = JSON.parse(fs.readFileSync(path.join(root, 'converted/image-map.json'), 'utf8'));
  let checkedBackdrops = 0;
  for (const [aid, meta] of Object.entries(imageMap)) {
    if (!meta.portrait) {
      assert.equal(meta.width, 432, aid);
      assert.equal(meta.height, 243, aid);
      checkedBackdrops++;
    } else {
      assert.ok(meta.height <= 236, `${aid} portrait height ${meta.height} exceeds 236`);
    }
  }
  assert.ok(checkedBackdrops >= 450);
  const compMeta = imageMap['9c7eb9702681792f'];
  const singleMeta = imageMap['78f55cd644c4d537'];
  assert.ok(compMeta && singleMeta);
  const compBytes = fs.readFileSync(path.join(root, 'src', compMeta.src));
  const singleBytes = fs.readFileSync(path.join(root, 'src', singleMeta.src));
  assert.ok(Math.abs(compBytes.length - singleBytes.length) < 300, 'composite ev005al+ev005a should match standalone ev005a');
});

test('compact asset prefixes resolve cleanly, checkpoint clones isolate maps, and history stays bounded to 24', () => {
  const sampleRaw = Object.values(assets).find(row => typeof row[0] === 'string' && row[0].startsWith('~'));
  assert.ok(sampleRaw, 'expected ~ compact prefix in assets.js');
  const s = e.create(graph, { start: true }, 'start');
  const cp = e.checkpoint(s);
  s.flag.flag = 77;
  s.progress.extra = true;
  assert.notEqual(cp.flag.flag, 77);
  assert.equal(cp.progress.extra, undefined);
  for (let i = 0; i < 40; i++) {
    const p = e.locate(graph, s);
    if (p.type !== 'text') break;
    e.advance(graph, s);
  }
  assert.ok(s.history.length <= 24);
});
