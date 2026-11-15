import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

function loadUx(options = {}) {
  const map = new Map();
  const timers = new Map();
  let serial = 0;
  let time = 0;
  let exited = 0;

  const box = {
    console: { log() {}, error() {} },
    storage: {
      get(o) {
        if (options.initialStorage && o.key in options.initialStorage && !map.has(o.key)) {
          o.success(options.initialStorage[o.key]);
          return;
        }
        o.success(map.has(o.key) ? map.get(o.key) : o.default);
      },
      set(o) {
        map.set(o.key, o.value);
        o.success?.();
      },
      delete(o) {
        map.delete(o.key);
        o.success?.();
      },
    },
    file: {
      readText(o) {
        const rel = o.uri.replace(/^\//, '');
        o.success({ text: fs.readFileSync(path.join(root, 'src', rel), 'utf8') });
      },
    },
    prompt: { showToast() {} },
    setTimeout(f, ms) {
      const id = ++serial;
      timers.set(id, { f, at: time + ms });
      return id;
    },
    clearTimeout(id) {
      timers.delete(id);
    },
    Date: { now: () => time },
  };

  let code = '';
  code += fs.readFileSync(path.join(root, 'src/common/graph.js'), 'utf8').replace('export const graph=', 'globalThis.graph=');
  code += '\n' + fs.readFileSync(path.join(root, 'src/common/assets.js'), 'utf8').replace('export const assets=', 'globalThis.assets=');
  code += '\n' + fs.readFileSync(path.join(root, 'src/common/auto-reader.js'), 'utf8').replace(/export /g, '');
  code += '\n' + fs.readFileSync(path.join(root, 'src/common/engine.js'), 'utf8').replace(/export\s*\{[\s\S]*?\};?/m, '');

  const uxRaw = fs.readFileSync(path.join(root, 'src/pages/index/index.ux'), 'utf8');
  const script = uxRaw
    .match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/import\s+(?:\{[\s\S]*?\}|[^\n;]+?)\s+from\s+['"][^'"]+['"];?\r?\n?/gm, '')
    .replace('export default', 'globalThis.page=');

  vm.runInNewContext(code + '\n' + script, box);
  const p = box.page;
  Object.assign(p, JSON.parse(JSON.stringify(p.private)));
  p.$element = () => ({ scrollTo() {}, scrollBy() {}, focus() {} });
  p.$app = { exit() { exited++; } };
  p.onInit();

  return {
    p,
    map,
    timers,
    getExited: () => exited,
    advanceTime(ms) {
      const end = time + ms;
      let guard = 0;
      for (;;) {
        const due = [...timers.entries()].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at);
        if (!due.length) break;
        const [id, t] = due[0];
        time = t.at;
        timers.delete(id);
        t.f();
        if (++guard > 200000) throw Error('Timer loop');
      }
      time = end;
    },
  };
}

test('zero audio, zero opening video, and zero sound toggles anywhere in Watch 5 UI or manifest', () => {
  const ux = fs.readFileSync(path.join(root, 'src/pages/index/index.ux'), 'utf8');
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'src/manifest.json'), 'utf8'));
  const banned = /(@system\.audio|system\.audio|title-music|playOpening|toggleSound|游戏音量|soundEnabled|\.opus|\.ogg|\.mp3|\.wmv)/i;
  assert.equal(banned.test(ux), false);
  assert.equal(manifest.package, 'com.antigravity.ginka.rw5');
  assert.equal(manifest.config.designWidth, 432);
  assert.deepEqual(manifest.deviceTypeList, ['watch']);
  assert.equal(manifest.features.some(f => f.name === 'system.audio'), false);
});

test('30 save slots support explicit select, reload exact position, overwrite confirm, and clean lock reset', () => {
  const { p } = loadUx();
  p.startNew();
  p.advance(); // finish typing
  p.advance(); // advance to frame 1
  const wanted = p.session.index;
  assert.equal(wanted, 1);

  p.saveGame();
  p.selectSlot(29);
  assert.equal(p.mode, 'play');

  p.advance();
  p.advance();
  assert.equal(p.session.index, 2);

  p.loadGame();
  assert.equal(p._slotData.length, 30);
  p.selectSlot(29);
  assert.equal(p.session.index, wanted);

  p.saveGame();
  p.selectSlot(29);
  assert.equal(p.mode, 'overwrite');
  p.confirmOverwrite();
  assert.equal(p.storageBusy, false);
  p.onDestroy();
});

test('directory two-level navigation refreshes keyed rows cleanly and back returns to routes', () => {
  const { p } = loadUx();
  p.openDirectory();
  const routeIds = p.directoryRows.map(x => x.id);
  p.pickDirectory(0);
  assert.equal(p.directoryTitle, '章节选择');
  assert.ok(p.directoryRows.length > 0);
  assert.ok(p.directoryRows.every(x => !routeIds.includes(x.id)));
  p.backDirectory();
  assert.equal(p.directoryTitle, '篇章选择');
  assert.equal(p.directoryRows[0].title, '本篇剧情');
  p.onDestroy();
});

test('typewriter updates keyed rows cleanly, drag suppresses tap, and timers clear on hide/destroy/exit', () => {
  const { p, timers, advanceTime, getExited } = loadUx();
  p.startNew();
  const initialIndex = p.session.index;
  advanceTime(5000);
  assert.equal(p.displayText, p.fullText);

  p.dialogueTouchStart({ touches: [{ clientX: 100, clientY: 400 }] });
  p.dialogueTouchEnd();
  p.dialogueTap();
  assert.equal(p.session.index, initialIndex + 1);

  advanceTime(5000);
  p.dialogueTouchStart({ touches: [{ clientX: 100, clientY: 400 }] });
  p.dialogueTouchMove({ touches: [{ clientX: 100, clientY: 320 }] });
  p.dialogueTouchEnd();
  p.dialogueTap();
  assert.equal(p.session.index, initialIndex + 1);

  // Keyed rows update when font size changes
  const rowCountBefore = p.dialogueLines.length;
  p.toggleFont();
  assert.equal(p.fontSize, 28);
  assert.ok(p.dialogueLines.length >= rowCountBefore);

  p.onHide();
  assert.equal(timers.size, 0);
  p.exitApplication();
  assert.equal(getExited(), 1);
  assert.equal(timers.size, 0);
});

test('CG gallery loads all 32 groups / 134 variants and cycles variants cleanly', () => {
  const { p } = loadUx();
  p.openGallery();
  assert.equal(p.mode, 'gallery');
  assert.equal(p._gallery.length, 32);
  assert.equal(p._gallery.reduce((a, g) => a + g.variants.length, 0), 134);
  p.viewCg(3);
  const firstSrc = p.cgSrc;
  p.cycleCg();
  assert.notEqual(p.cgSrc, firstSrc);
  p.backToGallery();
  assert.equal(p.mode, 'gallery');
  p.onDestroy();
});

test('long-press save slot prompts for delete confirmation, cancels cleanly, and deletes occupied slot', () => {
  const { p, map, advanceTime } = loadUx();
  const ux = fs.readFileSync(path.join(root, 'src/pages/index/index.ux'), 'utf8');
  assert.ok(ux.includes('onlongpress="longPressSlot($item.index)"'));
  assert.ok(ux.includes('confirmDelete'));

  p.startNew();
  p.advance();
  p.advance();
  p.saveGame();

  // Long-press empty slot stays in slots without deleting
  p.longPressSlot(1);
  assert.equal(p.mode, 'slots');

  // Save to slot 0, reopen slots, test long-press -> cancel -> long-press -> confirm delete
  advanceTime(700);
  p.selectSlot(0);
  assert.equal(p.mode, 'play');
  assert.ok(map.has('GINKA_RW5_slot_v1_1'));

  p.loadGame();
  assert.equal(p.mode, 'slots');
  assert.equal(p.slotRows[0].occupied, true);

  p.longPressSlot(0);
  assert.equal(p.mode, 'delete');
  assert.ok(p.deleteTitle.includes('01'));
  // Trailing click cannot slip through while in delete mode
  p.selectSlot(0);
  assert.equal(p.mode, 'delete');

  p.cancelDelete();
  assert.equal(p.mode, 'slots');
  assert.ok(map.has('GINKA_RW5_slot_v1_1'));

  p.longPressSlot(0);
  assert.equal(p.mode, 'delete');
  p.confirmDelete();
  assert.equal(p.mode, 'slots');
  assert.equal(p.storageBusy, false);
  assert.equal(map.has('GINKA_RW5_slot_v1_1'), false);
  assert.equal(p._slotData[0], null);
  assert.equal(p.slotRows[0].occupied, false);
  assert.equal(p.slotRows[0].meta, '空栏位');
  p.onDestroy();
});

test('touch-hold fallback triggers delete dialog after 600ms and drag cancels hold', () => {
  const { p, advanceTime } = loadUx();
  p.startNew();
  p.advance();
  p.saveGame();
  p.selectSlot(0);
  assert.equal(p.mode, 'play');

  p.loadGame();
  assert.equal(p.mode, 'slots');

  // Dragging cancels the hold timer so scrolling does not trigger delete
  p.beginSlotTouch(0, { touches: [{ clientX: 200, clientY: 130 }] });
  p.moveSlotTouch({ touches: [{ clientX: 200, clientY: 160 }] });
  advanceTime(700);
  assert.equal(p.mode, 'slots');

  // Holding steady triggers delete at 600ms and ignores trailing click
  p.beginSlotTouch(0, { touches: [{ clientX: 200, clientY: 130 }] });
  advanceTime(620);
  assert.equal(p.mode, 'delete');
  p.selectSlot(0);
  assert.equal(p.mode, 'delete');
  p.cancelDelete();
  assert.equal(p.mode, 'slots');

  // Even if timer were throttled, releasing after >=550ms converts click to delete
  advanceTime(700);
  p.beginSlotTouch(0, { touches: [{ clientX: 200, clientY: 130 }] });
  p.clearSlotHold();
  advanceTime(580);
  p.selectSlot(0);
  assert.equal(p.mode, 'delete');
  p.confirmDelete();
  assert.equal(p.mode, 'slots');
  assert.equal(p._slotData[0], null);
  p.onDestroy();
});

test('progressive original title screen removes Frontwing logo, scales/compacts buttons, moves chapter directory into EXTRA, and locks True Ending CG', () => {
  const uxSource = fs.readFileSync(path.join(root, 'src', 'pages', 'index', 'index.ux'), 'utf8');
  assert.equal(uxSource.includes('narration-line'), false);
  assert.equal(uxSource.includes('title_copy.png'), false);
  assert.equal(uxSource.includes('Frontwing'), false);
  assert.ok(uxSource.includes("mode === 'extra'"));
  for (const sprite of [
    'title_btn_cont.png',
    'title_btn_after.png',
    'title_btn_next.png',
    'title_btn_start.png',
    'title_btn_load.png',
    'title_btn_system.png',
    'title_btn_extra.png',
    'title_btn_exit.png',
    'title_new.png',
  ]) {
    assert.ok(uxSource.includes('/common/ui/' + sprite), 'missing sprite ' + sprite);
  }
  assert.equal(uxSource.includes('title_lower_bg.jpg'), false);
  assert.equal(uxSource.includes('音量'), false);
  for (const bgSlice of [
    'title_bg1_top.jpg',
    'title_bg1_bot.jpg',
    'title_bg2_top.jpg',
    'title_bg2_bot.jpg',
    'title_bg3_top.jpg',
    'title_bg3_bot.jpg',
  ]) {
    assert.ok(fs.existsSync(path.join(root, 'src', 'common', 'ui', bgSlice)), 'missing title backdrop ' + bgSlice);
  }

  const { p, map } = loadUx();
  const toasts = [];
  const origToast = p.toast.bind(p);
  p.toast = msg => {
    toasts.push(msg);
    origToast(msg);
  };
  assert.equal(p.titleBgTop, '/common/ui/title_bg1_top.jpg');
  assert.equal(p.titleBgBot, '/common/ui/title_bg1_bot.jpg');
  assert.equal(p.titleRowH, 38);
  assert.equal(p.titleSpriteH, 30);
  assert.equal(p.nextUnlocked, false);
  assert.equal(p.afterUnlocked, false);
  assert.equal(p.hasAnySave, false);

  p.continueGame();
  assert.equal(p.mode, 'title');
  assert.equal(toasts[toasts.length - 1], '暂无存档进度');

  // EXTRA selector opens Directory and CG Gallery, returning back to EXTRA
  p.openExtra();
  assert.equal(p.mode, 'extra');
  p.openDirectory();
  assert.equal(p.mode, 'directory');
  p.backDirectory();
  assert.equal(p.mode, 'extra');
  p.toTitle();
  assert.equal(p.mode, 'title');

  // Unlock Part 1 completion -> 7-button compact layout, NEXT visible with New badge & title_bg2
  p._progress = { start: true };
  p.refreshProgress();
  assert.equal(p.nextUnlocked, true);
  assert.equal(p.afterUnlocked, false);
  assert.equal(p.nextStarted, false);
  assert.equal(p.titleBgTop, '/common/ui/title_bg2_top.jpg');
  assert.equal(p.titleBgBot, '/common/ui/title_bg2_bot.jpg');
  assert.equal(p.titleRowH, 34);
  assert.equal(p.titleSpriteH, 27);

  p.startNext();
  assert.equal(p.mode, 'play');
  assert.equal(p.nextStarted, true);
  assert.equal(JSON.parse(map.get('GINKA_RW5_progress_v1')).titleNextStarted, true);
  p.syncProgress();
  assert.equal(p.nextStarted, true);

  // Unlock True Ending (next) -> 8-button compact layout, AFTER visible with New badge & title_bg3
  p.toTitle();
  p._progress = Object.assign({}, p._progress, { next: true });
  p.refreshProgress();
  assert.equal(p.afterUnlocked, true);
  assert.equal(p.afterStarted, false);
  assert.equal(p.titleBgTop, '/common/ui/title_bg3_top.jpg');
  assert.equal(p.titleBgBot, '/common/ui/title_bg3_bot.jpg');
  assert.equal(p.titleRowH, 30);
  assert.equal(p.titleSpriteH, 25);

  // Even after finishing AFTER or replaying Part 1 (syncing older progress flags), True Ending CG remains fixed
  p.startAfter();
  assert.equal(p.mode, 'play');
  assert.equal(p.afterStarted, true);
  p.session.progress = { start: true, next: false, after: true };
  p.syncProgress();
  assert.equal(p.titleBgTop, '/common/ui/title_bg3_top.jpg');
  assert.equal(p.titleBgBot, '/common/ui/title_bg3_bot.jpg');

  // Saving enables CONTINUE; deleting sole save disables CONTINUE again
  p.saveGame();
  p.selectSlot(0);
  assert.equal(p.hasAnySave, true);
  p.toTitle();
  assert.equal(p.titleBgTop, '/common/ui/title_bg3_top.jpg');
  assert.equal(p.titleBgBot, '/common/ui/title_bg3_bot.jpg');
  p.continueGame();
  assert.equal(p.mode, 'slots');
  p.longPressSlot(0);
  p.confirmDelete();
  assert.equal(p.hasAnySave, false);
  p.onDestroy();
});

test('CG bottom directly touches dialogue textbox top with zero gap inside 432x514 layout and omits speaker-row chapter label', () => {
  const uxSource = fs.readFileSync(path.join(root, 'src/pages/index/index.ux'), 'utf8');
  const bgMatch = uxSource.match(/\.background\s*\{[\s\S]*?top:\s*(\d+)px;[\s\S]*?height:\s*(\d+)px;/);
  const dlgMatch = uxSource.match(/\.dialogue-panel,\s*\.choice-panel\s*\{[\s\S]*?top:\s*(\d+)px;[\s\S]*?height:\s*(\d+)px;/);
  const pgMatch = uxSource.match(/\.portrait-group\s*\{[\s\S]*?top:\s*(\d+)px;[\s\S]*?height:\s*(\d+)px;/);
  assert.ok(bgMatch && dlgMatch && pgMatch);
  const bgTop = Number(bgMatch[1]);
  const bgH = Number(bgMatch[2]);
  const dlgTop = Number(dlgMatch[1]);
  const dlgH = Number(dlgMatch[2]);
  assert.equal(bgTop + bgH, dlgTop);
  assert.equal(dlgTop + dlgH, 514);
  assert.equal(Number(pgMatch[1]), bgTop);
  assert.equal(Number(pgMatch[2]), bgH);
  assert.equal(uxSource.includes('class="chapter"'), false);
});

test('typewriter updates active row key for Vela rendering, supports auto-play in both speeds, and keeps bounded caches', () => {
  const { p, advanceTime } = loadUx();
  p.startNew();
  const id0 = p.dialogueLines[0].id;
  const text0 = p.dialogueLines[0].text;
  const trailingId0 = p.dialogueLines.length > 1 ? p.dialogueLines[1].id : null;
  advanceTime(35);
  assert.notEqual(p.dialogueLines[0].id, id0);
  assert.ok(p.dialogueLines[0].text.length > text0.length);
  if (trailingId0 !== null) {
    assert.equal(p.dialogueLines[1].id, trailingId0);
  }

  advanceTime(5000);
  assert.equal(p.displayText, p.fullText);

  // Auto-play in typewriter mode finishes text and advances
  const startIdx = p.session.index;
  p.showMenu();
  p.toggleAuto();
  p.resume();
  advanceTime(3000);
  assert.ok(p.session.index > startIdx);
  assert.ok(p.dialogueLines.map(x => x.text).join('').trim().length > 1);

  // Auto-play in instant mode displays full text immediately without getting stuck on 1st char
  p.showMenu();
  p.toggleSpeed(); // textSpeed = 0
  assert.equal(p.textSpeed, 0);
  p.resume();
  advanceTime(3000);
  assert.equal(p.displayText, p.fullText);
  assert.ok(p.dialogueLines[0].text.length > 1);

  p.stopAuto();
  const portraitsRef0 = p.portraits;
  const bg0 = p.backgroundSrc;
  p.advance();
  assert.equal(p.backgroundSrc, bg0);
  assert.equal(p.portraits, portraitsRef0);

  // Bounded 2-chunk LRU cache & memory release on save/closeSlots/toTitle
  p.storeChunk('a.txt', [{ s: '', t: 'A' }]);
  p.storeChunk('b.txt', [{ s: '', t: 'B' }]);
  p.storeChunk('c.txt', [{ s: '', t: 'C' }]);
  assert.equal(p._chunkOrder.length, 2);
  assert.equal('a.txt' in p._chunkCache, false);

  p.saveGame();
  assert.equal(p._slotData.length, 30);
  p.closeSlots();
  assert.equal(p._slotData.length, 0);

  p.toTitle();
  assert.equal(p._chunkOrder.length, 0);
  assert.equal(p.frames.length, 0);
  assert.equal(p.backgroundSrc, '');
  assert.equal(p.portraits.length, 0);
  p.onDestroy();
});

test('skipChapter stopping at a choice updates background CG and portraits to match the choice frame', () => {
  const { p } = loadUx();
  p.startNew();
  const bgAtStart = p.backgroundSrc;
  p.showMenu();
  p.goNextChapter(); // -> scn001__start
  p.showMenu();
  p.goNextChapter(); // -> scn002__start (first frame)
  assert.equal(p.mode, 'play');
  const bgBeforeChoiceSkip = p.backgroundSrc;
  // Clear chunk cache to also exercise async loadStoryChunk path for choice stage alignment
  p._chunkCache = {};
  p._chunkOrder = [];
  p.cachedFile = '';
  p.showMenu();
  p.goNextChapter(); // -> scn002__dummyselect1
  assert.equal(p.mode, 'choice');
  assert.notEqual(p.backgroundSrc, bgAtStart);
  assert.notEqual(p.backgroundSrc, bgBeforeChoiceSkip);
  assert.ok(p.backgroundSrc.length > 0);
  p.onDestroy();
});

test('CG gallery viewer supports slider zoom, focus, key zoom, clamped touch pan, drag tap suppression, and reset', () => {
  const focusCalls = [];
  const { p, advanceTime } = loadUx();
  p.$element = id => ({
    scrollTo() {},
    scrollBy() {},
    focus(opts) {
      focusCalls.push({ id, opts });
    },
  });
  p.openGallery();
  assert.equal(p.mode, 'gallery');
  const multiIdx = p._gallery.findIndex(g => g.variants.length > 1);
  assert.ok(multiIdx >= 0);
  p.viewCg(multiIdx);
  assert.equal(p.mode, 'cg');
  assert.equal(p.cgZoom, 1);
  assert.equal(p.cgZoomPct, 100);
  assert.equal(p.cgImgW, 338);
  assert.equal(p.cgImgH, 190);
  assert.equal(p.cgImgLeft, 0);
  assert.equal(p.cgImgTop, 29);
  advanceTime(70);
  assert.ok(focusCalls.some(c => c.id === 'cg-zoom-slider' && c.opts && c.opts.focus === true));

  // Slider change to midpoint (progress = 175 -> 1.75x)
  p.cgSliderChange({ progress: 175 });
  assert.equal(p.cgZoom, 1.75);
  assert.equal(p.cgZoomPct, 175);
  assert.equal(p.cgImgW, Math.round(338 * 1.75));
  assert.equal(p.cgImgH, Math.round(190 * 1.75));

  // Dragging across zoomed CG pans within frame bounds and does NOT trigger variant switch on cgTap
  const srcBeforeDrag = p.cgSrc;
  const variantBeforeDrag = p.cgVariant;
  p.cgTouchStart({ touches: [{ clientX: 160, clientY: 120 }] });
  p.cgTouchMove({ touches: [{ clientX: 210, clientY: 140 }] });
  p.cgTouchEnd();
  assert.equal(p.cgImgLeft, Math.round((338 - p.cgImgW) / 2 + 50));
  assert.equal(p.cgImgTop, Math.round((248 - p.cgImgH) / 2 + 20));
  p.cgTap();
  assert.equal(p.cgVariant, variantBeforeDrag);
  assert.equal(p.cgSrc, srcBeforeDrag);

  // Overshooting drag clamps cleanly to zoomed image edges
  p.cgTouchStart({ touches: [{ clientX: 160, clientY: 120 }] });
  p.cgTouchMove({ touches: [{ clientX: 900, clientY: 900 }] });
  p.cgTouchEnd();
  assert.equal(p.cgImgLeft, 0);
  assert.equal(p.cgImgTop, 0);

  // Slider max clamps at 2.5x, clean tap cycles variant while preserving zoom/pan
  p.cgSliderChange({ progress: 999 });
  assert.equal(p.cgZoom, 2.5);
  assert.equal(p.cgZoomPct, 250);
  p.cgTouchStart({ touches: [{ clientX: 160, clientY: 120 }] });
  p.cgTouchEnd();
  p.cgTap();
  assert.notEqual(p.cgVariant, variantBeforeDrag);
  assert.equal(p.cgZoom, 2.5);

  // Key fallback & zoom buttons step and keep cgZoomPct synchronized
  p.cgKey({ keyCode: 20 }); // down -> 2.25x
  assert.equal(p.cgZoom, 2.25);
  assert.equal(p.cgZoomPct, 225);
  p.cgZoomOut(); // -> 2.0x
  assert.equal(p.cgZoom, 2);
  assert.equal(p.cgZoomPct, 200);

  // Switching to next CG group resets zoom & pan to 1.0x center
  p.nextCg();
  assert.equal(p.cgZoom, 1);
  assert.equal(p.cgZoomPct, 100);
  assert.equal(p.cgImgLeft, 0);
  assert.equal(p.cgImgTop, 29);
  p.onDestroy();
});

test('dialogue scroll overflow, focus activation, scroll controls, and drag-tap suppression work reliably', () => {
  const focusCalls = [];
  const scrollByCalls = [];
  const scrollToCalls = [];
  const { p, advanceTime } = loadUx();
  p.$element = id => ({
    focus(opts) {
      focusCalls.push({ id, opts });
    },
    scrollBy(opts) {
      scrollByCalls.push({ id, opts });
    },
    scrollTo(opts) {
      scrollToCalls.push({ id, opts });
    },
  });
  p.startNew();
  assert.equal(p.mode, 'play');
  advanceTime(70);
  assert.ok(focusCalls.some(c => c.id === 'dialogue-scroll' && c.opts && c.opts.focus === true));

  // Long text overflowing 156px viewport marks dialogueScrollable and exposes scrollBy controls
  p.fontSize = 24;
  p.showFrame({
    s: 'GINKA',
    t: '这是一段很长的测试文本，用来确认对话滚动容器在超过四行之后能够准确触发溢出状态并支持上下滑动。' +
       '再补充第二段足够长度的文字，确保在 Watch 5 的文本框内稳定超过五行的显示高度。',
  });
  advanceTime(4000);
  assert.equal(p.dialogueScrollable, true);
  assert.ok(p.dialogueHeight > 156);

  // Explicit scroll buttons and key handler call scrollBy vertically
  p.dialogueScrollDown();
  p.dialogueScrollUp();
  p.dialogueKey({ keyCode: 20 });
  assert.deepEqual(
    scrollByCalls.map(c => c.opts.top),
    [68, -68, 48]
  );

  // Real user scroll event suppresses accidental tap advance within 450ms
  const beforeText = p.fullText;
  advanceTime(200);
  p.dialogueScrolled();
  p.dialogueTap();
  assert.equal(p.fullText, beforeText);

  // After cool-down, scroll reset uses { left: 0, top: 0, behavior: 'instant' } and resumes cleanly
  advanceTime(500);
  p.showFrame({ s: 'GINKA', t: '短句切换。' });
  assert.equal(p.dialogueScrollable, false);
  assert.equal(p.dialogueHeight, 156);
  assert.ok(scrollToCalls.some(c => c.id === 'dialogue-scroll' && c.opts.top === 0 && c.opts.behavior === 'instant'));

  p.showMenu();
  p.resume();
  advanceTime(70);
  assert.ok(focusCalls.filter(c => c.id === 'dialogue-scroll').length >= 2);
  p.onDestroy();
});
