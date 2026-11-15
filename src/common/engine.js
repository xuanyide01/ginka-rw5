// Bounded reader state & pure GINKA graph/flag/sprite transition logic (zero audio/video).
const copyMap = o => (o ? Object.assign({}, o) : {});

function resolveAssetUri(raw) {
  if (!raw) return '';
  const head = raw.charCodeAt(0);
  if (head === 126) return '/common/images/' + raw.slice(1); // '~'
  if (head === 94) return '/common/faces/' + raw.slice(1); // '^'
  return raw;
}

function create(graph, progress, entryKey) {
  const startNode = (entryKey && graph.entries && graph.entries[entryKey]) || graph.initial;
  return {
    format: 1,
    node: startNode,
    index: 0,
    flag: copyMap(graph.initialFlags || { flag: 0 }),
    progress: copyMap(progress),
    history: [],
  };
}

function checkpoint(state) {
  const { history, ...saved } = state;
  saved.flag = copyMap(state.flag);
  saved.progress = copyMap(state.progress);
  return saved;
}

function restore(graph, saved) {
  if (!saved || saved.format !== 1 || !saved.flag || typeof saved.flag !== 'object') {
    throw Error('存档数据不匹配');
  }
  const node = saved.node;
  if (!graph.nodes[node] || !Number.isInteger(saved.index) || saved.index < 0 || saved.index > graph.nodes[node].count) {
    throw Error('存档数据不匹配');
  }
  return {
    ...saved,
    node,
    flag: copyMap(saved.flag),
    progress: copyMap(saved.progress),
    history: [],
  };
}

function remember(state) {
  state.history.push(checkpoint(state));
  if (state.history.length > 24) state.history.shift();
}

function routeUnlocked(graph, routeKey, progress) {
  const reqs = (graph.unlock && graph.unlock[routeKey]) || [];
  const p = progress || {};
  return reqs.every(k => !!p[k]);
}

function enterRoute(graph, state, routeKey) {
  if (!routeUnlocked(graph, routeKey, state.progress)) return false;
  const target = graph.entries && graph.entries[routeKey];
  if (!target || !graph.nodes[target]) return false;
  state.node = target;
  state.index = 0;
  state.flag = copyMap(graph.initialFlags || { flag: 0 });
  state.history = [];
  return true;
}

function matches(when, state) {
  if (!when) return true;
  const [key, op, rhs] = when;
  const lhs = Number((state.flag && state.flag[key]) || 0);
  if (op === '==') return lhs === rhs;
  if (op === '>=') return lhs >= rhs;
  if (op === '<') return lhs < rhs;
  throw Error('未知分支条件: ' + op);
}

function applyEffects(effects, state) {
  if (!Array.isArray(effects)) return;
  for (const eff of effects) {
    const [kind, key, val] = eff;
    if (kind === 'set') state.flag[key] = val;
    else if (kind === 'add') state.flag[key] = Number(state.flag[key] || 0) + val;
    else throw Error('未知选项效果: ' + kind);
  }
}

function findChoiceStage(graph, choiceNodeId, fromNodeId) {
  const lastFrameOf = node => {
    if (!node || !node.chunks || !node.chunks.length) return null;
    const last = node.chunks[node.chunks.length - 1];
    return { file: last.file, index: last.count - 1, title: node.title || '' };
  };
  if (fromNodeId && graph.nodes[fromNodeId]) {
    const direct = lastFrameOf(graph.nodes[fromNodeId]);
    if (direct) return direct;
  }
  const nodes = Object.values(graph.nodes || {});
  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    if (!n || !n.next) continue;
    for (let j = 0; j < n.next.length; j++) {
      if (n.next[j].to === choiceNodeId) {
        const hit = lastFrameOf(n);
        if (hit) return hit;
      }
    }
  }
  return null;
}

function locate(graph, state) {
  let prevNodeId = '';
  for (let steps = 0; steps < 1000; steps++) {
    if (state.node === '@end') return { type: 'end' };
    const n = graph.nodes[state.node];
    if (!n) throw Error('剧情连接缺失');
    if (state.index < n.count) {
      let offset = state.index;
      for (const c of n.chunks) {
        if (offset < c.count) {
          return { type: 'text', file: c.file, index: offset, title: n.title, route: n.route };
        }
        offset -= c.count;
      }
      throw Error('剧情块下标错误');
    }
    if (state.progression !== 'chapter' && Array.isArray(n.complete)) {
      for (const key of n.complete) state.progress[key] = true;
    }
    if (n.choices && n.choices.length) {
      const stage = (n.chunks && n.chunks.length ? findChoiceStage(graph, state.node, state.node) : null) ||
        findChoiceStage(graph, state.node, prevNodeId);
      return {
        type: 'choice',
        items: n.choices,
        title: n.title || (stage && stage.title) || '',
        stageFile: stage ? stage.file : '',
        stageIndex: stage ? stage.index : 0,
      };
    }
    const next = (n.next || []).find(x => matches(x.when, state));
    if (!next) throw Error('剧情意外中断');
    prevNodeId = state.node;
    state.node = next.to;
    state.index = 0;
  }
  throw Error('剧情连接超出范围');
}

function advance(graph, state) {
  const p = locate(graph, state);
  if (p.type !== 'text') return p;
  remember(state);
  state.index++;
  return locate(graph, state);
}

function choose(graph, state, index) {
  const p = locate(graph, state);
  if (p.type !== 'choice') throw Error('当前位置没有选项');
  const o = p.items[index];
  if (!o) throw Error('选项不存在');
  remember(state);
  applyEffects(o.effects, state);
  state.node = o.to;
  state.index = 0;
  return locate(graph, state);
}

function skipChapter(graph, state) {
  const cur = locate(graph, state);
  if (cur.type !== 'text') return cur;
  remember(state);
  const startNode = state.node;
  for (let steps = 0; steps < 1000; steps++) {
    const n = graph.nodes[state.node];
    state.index = n.count;
    const p = locate(graph, state);
    if (p.type !== 'text') return p;
    if (state.node !== startNode && graph.nodes[state.node].source[0] !== graph.nodes[startNode].source[0]) {
      return p;
    }
  }
  throw Error('章节跳转超出范围');
}

function previous(graph, state) {
  if (!state.history || !state.history.length) return locate(graph, state);
  const h = state.history;
  const s = h.pop();
  Object.assign(state, s, { history: h });
  return locate(graph, state);
}

function resolveStage(assets, frame) {
  const bgMeta = assets[frame.bg];
  const background = bgMeta ? resolveAssetUri(bgMeta[0]) : '';
  const list = frame.sp;
  if (!list || !list.length) return { background, portraits: [] };
  const portraits = [];
  for (let i = 0; i < list.length; i++) {
    const sp = list[i];
    const meta = assets[sp.id];
    if (!meta) continue;
    const src = resolveAssetUri(meta[0]);
    const width = meta[1];
    const height = meta[2];
    const patch = resolveAssetUri(meta[3]);
    const patchRect = meta[4];
    const patchAtlas = meta[5];
    const left = Math.round(216 + ((sp.x || 0) * 432) / 1280 - width / 2);
    const top = Math.max(0, 243 - height) + Math.round(((sp.y || 0) * 243) / 720);
    const opacity = sp.op != null ? Math.max(0, Math.min(1, sp.op / 255)) : 1;
    const out = {
      id: src + patch + left + ':' + i,
      src,
      width,
      height,
      left,
      top,
      opacity,
      patch,
    };
    if (patch && patchRect && patchAtlas) {
      out.patchLeft = left + patchRect[0];
      out.patchTop = top + patchRect[1];
      out.patchWidth = patchRect[2];
      out.patchHeight = patchRect[3];
      out.patchAtlasWidth = patchAtlas[0];
      out.patchAtlasHeight = patchAtlas[1];
      out.patchImageLeft = -patchAtlas[2];
      out.patchImageTop = -patchAtlas[3];
    }
    portraits.push(out);
  }
  return { background, portraits };
}

export {
  create,
  checkpoint,
  restore,
  routeUnlocked,
  enterRoute,
  matches,
  locate,
  advance,
  choose,
  skipChapter,
  previous,
  resolveStage,
};
