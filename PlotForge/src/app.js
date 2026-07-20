// app.js — 앱 부트스트랩: 캔버스 상호작용 · UI 패널 · DXF 임포트 · 저장/Undo · 툴 로직
import { store, uid, bumpUidAbove, activeAlt, typeById, newAlternative } from './state.js';
import {
  buildGrid, worldToCell, fits, buildOccupancy, maskOf, placementCovers, placementArea,
} from './grid.js';
import {
  computeEdgeDist, computeDistFieldNear, candidateMap, autoPlace, feasibility, generateRoads,
  evaluateHard, layoutMetrics, coverageOK, addWouldViolate, generateRoadNetwork, buildRuleContext,
  typeVariants, CORRIDOR_KINDS, rasterizeCenterline, networkComponents,
  routeCorridor, expandTargets,
} from './engine.js';
import { compileRules, cellRuleToM, mCeil, mFloor } from './units.js';
import { fitView, draw, s2w } from './render.js';
import { parseDXF, pickSitePolygon } from './dxf.js';
import { buildDXF } from './export.js';

const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const $ = (id) => document.getElementById(id);

let edgeDist = null;      // 배치격자 기준 경계거리장 (도로망 있으면 도로변까지 거리)
let placeGrid = null;     // 배치용 격자: 도로망 셀을 배치불가로 마스킹. 도로망 없으면 grid와 동일
let compiledRules = [];   // m 정본 규칙(s.rules)의 셀 컴파일본 — 엔진은 이것만 소비 (units.compileRules)
let view = null;          // 현재 뷰 변환
let hoverCell = null;     // 마우스 아래 셀
let drag = null;          // {index, offC, offR} 드래그 중 건물
let candCache = null;     // {key, valid, best} 수동배치 후보 캐시
let feasResult = [];      // 배치가능성 검증 결과
let placingRot = 0;       // 배치 모드 회전 상태 (블록 타입만, R키로 0~3)
let selection = new Set(); // 선택 도구의 다중선택 placement 인덱스 (블록 묶기용)
let draftCorridor = [];   // 선형 그리기 중 웨이포인트(셀 인덱스)

/** 대형 격자(2만 셀 초과): 대안 1개만 생성·검증 온디맨드·어닐링 축소 — UI 블로킹 방지 */
const isHeavyGrid = () => !!placeGrid && placeGrid.cols * placeGrid.rows > 20000;

const CAT_LABELS = {
  building: '건물', equipment: '장비', block: '블록',
  road: '도로', rack: '파이프랙', tunnel: '터널', conduit: '도관',
};

/** 배치 모드의 현재 변형(회전 반영). 유닛이면 rot 0 고정 */
function placingVariant(t) {
  const vs = typeVariants(t);
  return vs[placingRot % vs.length];
}

// ---------- 캔버스 크기 ----------
function resize() {
  const r = canvas.parentElement.getBoundingClientRect();
  canvas.width = r.width; canvas.height = r.height;
  redraw();
}
window.addEventListener('resize', resize);

// ---------- 그리드 재생성 ----------
/**
 * 배치 컨텍스트 갱신 — 규칙/격자/도로망 관련 모든 파생 상태의 유일한 재계산 경로.
 * (규칙 저장·삭제, cellSize, 도로망, restore가 전부 여길 지나야 stale 캐시가 구조적으로 차단됨)
 */
function refreshPlacementContext() {
  const s = store.state;
  compiledRules = compileRules(s.rules, s.cellSize);
  if (!s.grid) { placeGrid = null; edgeDist = null; candCache = null; return; }

  // 배치 차단 셀 = 도로망 + blocks=true 선형(rack/conduit). tunnel(지하)은 차단 안 함 (D9)
  const roadCorridorCells = s.corridors.filter((k) => k.kind === 'road').flatMap((k) => k.cells);
  const roadAll = [...s.roadNetwork, ...roadCorridorCells];
  const blockedCells = [...roadAll,
    ...s.corridors.filter((k) => CORRIDOR_KINDS[k.kind]?.blocks && k.kind !== 'road').flatMap((k) => k.cells)];
  if (blockedCells.length) {
    const masked = s.grid.buildable.slice();
    for (const i of blockedCells) masked[i] = 0;
    placeGrid = { ...s.grid, buildable: masked };
  } else {
    // ctx 부착을 위해 얕은 사본 (원본 s.grid에 ctx를 붙이지 않음 — 직렬화 오염 방지)
    placeGrid = { ...s.grid };
  }

  // 'any' 거리장 = 경계+도로만. rack/conduit가 마스킹돼도 nearRoad 의미가 오염되지 않도록
  // 소스를 명시 분리 (D12 — 마스킹과 원자적 동시 적용)
  const roadSet = new Set(roadAll);
  const raw = s.grid;
  edgeDist = computeDistFieldNear(placeGrid, (c, r) => {
    if (c < 0 || r < 0 || c >= raw.cols || r >= raw.rows) return true; // 대지 밖
    if (!raw.buildable[r * raw.cols + c]) return true; // 대지 경계
    return roadSet.has(r * raw.cols + c); // 도로
  });

  placeGrid.ctx = buildRuleContext(s.grid, placeGrid, roadAll,
    { windDir: s.windDir, anchors: s.anchors }); // 직렬화 금지(파생 캐시)

  // 클리어런스 컨텍스트 (D11): kind별 거리장 + 카테고리 매트릭스(m→셀 올림)
  if (s.clearances.length || s.corridors.length) {
    const kindFields = {};
    for (const kind of Object.keys(CORRIDOR_KINDS)) {
      const cells = kind === 'road' ? roadAll
        : s.corridors.filter((k) => k.kind === kind).flatMap((k) => k.cells);
      if (!cells.length) continue;
      const kset = new Set(cells);
      kindFields[kind] = computeDistFieldNear(placeGrid, (c, r) =>
        c >= 0 && r >= 0 && c < raw.cols && r < raw.rows && kset.has(r * raw.cols + c));
    }
    const catMap = new Map(s.buildingTypes.map((t) =>
      [t.id, t.kind === 'block' ? 'block' : (t.category || 'building')]));
    const clrMap = new Map();
    for (const cl of s.clearances) {
      const key = [cl.a, cl.b].sort().join('|');
      clrMap.set(key, Math.max(clrMap.get(key) || 0, mCeil(cl.minM, s.cellSize)));
    }
    placeGrid.ctx.clear = {
      kindFields,
      catOf: (typeId) => catMap.get(typeId) || 'building',
      cells: (a, b) => clrMap.get([a, b].sort().join('|')) || 0,
    };
  }
  candCache = null;
}

function rebuildGrid() {
  const s = store.state;
  if (!s.site) { store.state.grid = null; refreshPlacementContext(); store.emit(); return; }
  store.state.grid = buildGrid(s.site, s.cellSize);
  refreshPlacementContext();
  if (!s.alternatives.length) {
    const alt = newAlternative('대안 1');
    s.alternatives.push(alt);
    s.activeAltId = alt.id;
  }
  store.emit();
}

// ---------- 저장/복원/Undo ----------
const SAVE_KEY = 'sitelayout_save_v1';

function serialize() {
  const s = store.state;
  return JSON.stringify({
    schemaVersion: 2,
    site: s.site, cellSize: s.cellSize, maxCoverage: s.maxCoverage,
    roadNetwork: s.roadNetwork, roadPattern: s.roadPattern, entryCell: s.entryCell,
    windDir: s.windDir, anchors: s.anchors,
    corridors: s.corridors, clearances: s.clearances, roadParams: s.roadParams,
    buildingTypes: s.buildingTypes,
    rules: s.rules, sequence: s.sequence, alternatives: s.alternatives,
    activeAltId: s.activeAltId,
  });
}

/** v1(셀 단위 규칙) → v2(m 정본) 마이그레이션. 소유자는 이 함수 하나 (PLAN.md D14) */
function migrateState(d) {
  let rules = migrateRules(d.rules || []); // 구형 kind(gapFrom 등) → distanceTo (셀 단위 유지)
  if (!d.schemaVersion || d.schemaVersion < 2) {
    const cs = d.cellSize || 10;
    rules = rules.map((r) => cellRuleToM(r, cs)); // 셀 → m 정본 (왕복 동등 역산)
  }
  return { ...d, rules, schemaVersion: 2 };
}

function restore(json) {
  const d = migrateState(JSON.parse(json));
  Object.assign(store.state, {
    site: d.site || null, cellSize: d.cellSize || 10,
    maxCoverage: d.maxCoverage ?? null,
    roadNetwork: d.roadNetwork || [],
    roadPattern: d.roadPattern || 'comb',
    entryCell: d.entryCell ?? null,
    windDir: d.windDir ?? null,
    anchors: d.anchors || [],
    corridors: d.corridors || [],
    clearances: d.clearances || [],
    roadParams: d.roadParams || { widthM: null, ringOffsetM: null },
    buildingTypes: d.buildingTypes || [], rules: d.rules || [],
    sequence: d.sequence || [], alternatives: d.alternatives || [],
    activeAltId: d.activeAltId || null,
    tool: 'select', placingTypeId: null, draftSite: [],
  });
  $('cellSize').value = store.state.cellSize;
  $('maxCoverage').value = store.state.maxCoverage ?? '';
  $('roadPattern').value = store.state.roadPattern;
  $('windDir').value = store.state.windDir == null ? '' : String(store.state.windDir);
  $('roadWidthM').value = store.state.roadParams.widthM ?? '';
  $('ringOffsetM').value = store.state.roadParams.ringOffsetM ?? '';
  bumpUidAbove([
    ...store.state.buildingTypes.map((t) => t.id),
    ...store.state.rules.map((r) => r.id),
    ...store.state.alternatives.map((a) => a.id),
    ...store.state.anchors.map((a) => a.id),
  ]);
  candCache = null;
  selection.clear(); syncGroupButtons();
  if (store.state.site) rebuildGrid(); else { refreshPlacementContext(); store.emit(); }
  syncToolButtons();
  runFeasibility();
  renderPanels();
}

const undoStack = [];
const redoStack = [];
function pushUndo() {
  undoStack.push(serialize());
  if (undoStack.length > 50) undoStack.shift();
  redoStack.length = 0; // 새 작업이 생기면 redo 이력 무효
}
function undo() {
  const j = undoStack.pop();
  if (!j) return flashHint('되돌릴 작업이 없습니다.');
  redoStack.push(serialize());
  restore(j);
  flashHint('되돌렸습니다.');
}
function redo() {
  const j = redoStack.pop();
  if (!j) return flashHint('다시 실행할 작업이 없습니다.');
  undoStack.push(serialize());
  restore(j);
  flashHint('다시 실행했습니다.');
}
$('undoBtn').addEventListener('click', undo);
$('redoBtn').addEventListener('click', redo);
window.addEventListener('keydown', (e) => {
  if (!(e.ctrlKey || e.metaKey)) return;
  const k = e.key.toLowerCase();
  if (k === 'z' && e.shiftKey) { e.preventDefault(); redo(); }
  else if (k === 'z') { e.preventDefault(); undo(); }
  else if (k === 'y') { e.preventDefault(); redo(); }
});

// 자동저장 (변경 0.5초 뒤 localStorage)
let saveTimer = null;
store.subscribe(() => {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try { localStorage.setItem(SAVE_KEY, serialize()); } catch { /* 저장공간 부족 등 무시 */ }
  }, 500);
});

$('saveJson').addEventListener('click', () => {
  const blob = new Blob([serialize()], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'sitelayout.json';
  a.click();
  URL.revokeObjectURL(a.href);
});

$('loadJson').addEventListener('change', async (e) => {
  const file = e.target.files[0]; if (!file) return;
  try {
    pushUndo();
    restore(await file.text());
    flashHint('프로젝트를 불러왔습니다.');
  } catch { flashHint('불러오기 실패: 올바른 저장 파일이 아닙니다.'); }
  e.target.value = '';
});

$('exportPng').addEventListener('click', () => {
  const a = document.createElement('a');
  a.href = canvas.toDataURL('image/png');
  a.download = 'sitelayout.png';
  a.click();
});

$('loadDemo').addEventListener('click', async () => {
  try {
    const res = await fetch('./demos/lng-ccpp.json', { cache: 'reload' });
    if (!res.ok) throw new Error(res.status);
    pushUndo();
    restore(await res.text());
    flashHint('LNG 복합화력 데모 로드 완료. 순서: ① 「도로망 생성」(루프·폭8m·링5m 사전설정) → ② 「자동 배치」. 규칙 탭에서 37개 규칙을 살펴보세요.');
  } catch (err) {
    flashHint('데모 파일을 불러오지 못했습니다: ' + err.message);
  }
});

// ---------- Claude(MCP) 라이브 브리지 (WebSocket) ----------
// BimOn-PlotForge MCP 서버(파이썬)가 ws://localhost:5179 를 호스팅한다. 이 앱은 클라이언트로
// 접속해, 서버가 보낸 {id,code}를 "살아있는 앱" 컨텍스트에서 실행하고 {id,result}로 회신한다.
// (Revit/AutoCAD 애드인이 앱 안에서 리스너를 여는 것과 동일한 라이브 모델 — 브라우저는 소켓을
//  열 수 없어 방향만 반대. 사용자에겐 동일: 열어두면 Claude가 실시간 조작, 버튼/파일 폴링 불필요.)
const BRIDGE_URL = (window.__PF_BRIDGE_URL) || 'ws://localhost:5179';
let bridgeWs = null;
let bridgeConnected = false;
let bridgeRetry = null;
let isBridgeLeader = false;   // 이 탭이 브리지 접속을 담당하는가 (Web Locks 리더)

/** MCP가 보낸 코드를 이 모듈 스코프에서 실행 (Revit execute_script 대응). 'return' 사용 가능. */
async function runBridgeCode(code) {
  // eslint-disable-next-line no-eval
  return await eval('(async () => {\n' + code + '\n})()');
}

/** 라이브 앱에서 도로망(옵션)+자동배치를 실제 엔진으로 실행 — 「도로망 생성」→「자동 배치」 버튼과 동일 흐름 */
function doRunLayout(opts) {
  const s = store.state;
  if (!s.grid) throw new Error('대지가 없습니다 (plotforge_new_project 먼저).');
  if (!s.sequence.length) throw new Error('배치 순서가 비어 있습니다 (plotforge_set_sequence 먼저).');
  const seed = Number.isFinite(opts.seed) ? opts.seed : 1;
  const withRoads = opts.roads !== false;
  pushUndo();
  if (withRoads && !s.roadNetwork.length && s.roadPattern) generateNetwork();
  const heavy = isHeavyGrid();
  const runOpts = { maxCoverage: s.maxCoverage, annealIters: heavy ? 120 : 300 };
  let alt = activeAlt(s);
  if (!alt) { alt = newAlternative('대안 1'); s.alternatives.push(alt); s.activeAltId = alt.id; }
  const t0 = performance.now();
  const res = autoPlace(placeGrid, edgeDist, s.buildingTypes, compiledRules, s.sequence, seed, runOpts);
  alt.placements = res.placements;
  regenRoads(alt);
  const m = layoutMetrics(placeGrid, edgeDist, alt.placements, compiledRules, s.sequence);
  runFeasibility();
  renderPanels();
  store.emit();
  const byId = new Map(s.buildingTypes.map((t) => [t.id, t.name]));
  return {
    ms: Math.round(performance.now() - t0), seed, roadsGenerated: withRoads,
    placed: m.placed, target: m.target,
    fillRatePct: Math.round(m.fillRate * 1000) / 10,
    score: m.score, hardViolations: m.hardViolations,
    unplaced: res.unplaced.map((id) => byId.get(id) || id),
  };
}

// 브리지가 조작하는 앱 표면 (MCP 서버의 시맨틱 도구는 이 위에서 동작)
window.__pf = {
  dump() { return JSON.parse(serialize()); },              // 현재 프로젝트 (객체)
  load(obj) {                                              // 프로젝트 통째로 반영 (undo 1스텝)
    pushUndo();
    restore(typeof obj === 'string' ? obj : JSON.stringify(obj));
    return { ok: true, types: store.state.buildingTypes.length };
  },
  runLayout(o) { return doRunLayout(o || {}); },
  status() {
    const s = store.state; const alt = activeAlt(s);
    return {
      app: 'BimOn-PlotForge', connected: true, hasSite: !!s.site, cellSize: s.cellSize,
      types: s.buildingTypes.length, rules: s.rules.length, sequence: s.sequence.length,
      alternatives: s.alternatives.length, placed: alt ? alt.placements.length : 0,
    };
  },
};

function setBridgeStatus(on) {
  bridgeConnected = on;
  const b = $('mcpSync');
  if (!b) return;
  b.classList.toggle('active', on);
  b.textContent = on ? '🔗 Claude 연결됨' : '🔗 Claude 대기…';
}

function connectBridge() {
  try { bridgeWs = new WebSocket(BRIDGE_URL); }
  catch { scheduleBridgeReconnect(); return; }
  bridgeWs.onopen = () => {
    setBridgeStatus(true);
    try { bridgeWs.send(JSON.stringify({ hello: 'BimOn-PlotForge-app' })); } catch { /* noop */ }
  };
  bridgeWs.onclose = () => { setBridgeStatus(false); scheduleBridgeReconnect(); };
  bridgeWs.onerror = () => { try { bridgeWs.close(); } catch { /* noop */ } };
  bridgeWs.onmessage = async (ev) => {
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }
    if (!msg || msg.id == null || typeof msg.code !== 'string') return;
    let out;
    try {
      const result = await runBridgeCode(msg.code);
      out = { id: msg.id, result: result === undefined ? null : result };
    } catch (err) {
      out = { id: msg.id, error: String((err && (err.stack || err.message)) || err) };
    }
    let payload;
    try { payload = JSON.stringify(out); }                 // 직렬화 불가 결과 방어
    catch { payload = JSON.stringify({ id: msg.id, result: String(out.result) }); }
    try { bridgeWs.send(payload); } catch { /* 연결 끊김 — 다음 접속에서 복구 */ }
  };
}

function scheduleBridgeReconnect() {
  if (!isBridgeLeader) return;                            // 리더 탭만 재접속 (경쟁 방지)
  clearTimeout(bridgeRetry);
  bridgeRetry = setTimeout(connectBridge, 2000);          // MCP 서버 미기동 시 조용히 재시도
}

// 여러 탭이 동시에 브리지를 물면 서로 밀어내며 버튼이 깜빡인다(브리지는 클라이언트 1개만 유지).
// Web Locks로 한 브라우저에서 탭 1개(리더)만 접속하게 하고, 나머지는 대기 → 리더가 닫히면 승계.
function startBridge() {
  if (navigator.locks && navigator.locks.request) {
    navigator.locks.request('plotforge-bridge', () => new Promise(() => {
      isBridgeLeader = true;   // 락 획득 = 리더. 이 Promise는 탭이 닫힐 때까지 미해결 → 락 유지
      connectBridge();
    }));
  } else {
    isBridgeLeader = true;     // 구형 브라우저 폴백 (Web Locks 미지원)
    connectBridge();
  }
}

$('mcpSync').addEventListener('click', () => {
  if (bridgeConnected) {
    flashHint('Claude(MCP) 브리지에 연결되어 있습니다 — 요청하면 화면에 바로 반영됩니다.');
  } else if (!isBridgeLeader) {
    flashHint('다른 탭이 이미 Claude 연동을 담당하고 있습니다. 이 탭은 대기 상태입니다(정상).');
  } else {
    flashHint('Claude(MCP) 브리지 연결 대기 중 — MCP 서버(BimOn-PlotForge)가 실행 중인지 확인합니다. 재접속을 시도합니다.');
    clearTimeout(bridgeRetry);
    connectBridge();
  }
});

$('exportDxf').addEventListener('click', () => {
  const s = store.state;
  if (!s.site) return flashHint('내보낼 대지가 없습니다.');
  const dxf = buildDXF(s, activeAlt(s));
  const blob = new Blob([dxf], { type: 'application/dxf' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'sitelayout.dxf';
  a.click();
  URL.revokeObjectURL(a.href);
  flashHint('DXF 내보내기 완료 (레이어: SITE / ROAD / BLDG_* / ANNO).');
});

// ---------- 수동배치 후보 캐시 ----------
function getCand() {
  const s = store.state;
  const alt = activeAlt(s);
  if (s.tool !== 'place' || !s.placingTypeId || !s.grid || !alt) return null;
  const t = typeById(s, s.placingTypeId);
  if (!t) return null;
  const v = placingVariant(t);
  const key = s.placingTypeId + '|' + placingRot + '|' + alt.placements.length + '|' + s.activeAltId;
  if (candCache && candCache.key === key) return candCache;
  const cm = candidateMap(placeGrid, edgeDist, alt.placements, t.id, v.w, v.h, compiledRules, v.members);
  candCache = { key, ...cm, w: v.w, h: v.h };
  return candCache;
}

// ---------- 렌더 ----------
function redraw() {
  const s = store.state;
  view = fitView(s, canvas);
  const alt = activeAlt(s);
  const overlay = { alt };

  if (s.tool === 'place') {
    const cand = getCand();
    if (cand) {
      overlay.valid = cand.valid;
      if (cand.best) { overlay.best = cand.best; overlay.bestW = cand.w; overlay.bestH = cand.h; }
      if (hoverCell) {
        const t = typeById(s, s.placingTypeId);
        const v = placingVariant(t);
        const gcand = { typeId: t.id, c: hoverCell.c, r: hoverCell.r, w: v.w, h: v.h, members: v.members };
        const ok = alt && fits(placeGrid, buildOccupancy(placeGrid, alt.placements),
          hoverCell.c, hoverCell.r, v.w, v.h, maskOf(gcand))
          && evaluateHard(placeGrid, edgeDist, alt.placements, gcand, compiledRules)
          && !addWouldViolate(placeGrid, edgeDist, alt.placements, gcand, compiledRules);
        overlay.ghost = { c: hoverCell.c, r: hoverCell.r, w: v.w, h: v.h, members: v.members, valid: !!ok };
      }
    }
  }

  if (drag && alt) {
    overlay.dragIndex = drag.index;
    const p = alt.placements[drag.index];
    // 최적 드롭 추천: 드래그 중 불변이므로 시작 시 1회만 계산.
    // 대형 풋프린트×대형 격자(전수 스캔 수백 ms)는 생략 — 드래그 반응성 우선
    if (drag.bestCache === undefined) {
      const cost = placeGrid.cols * placeGrid.rows * (p.w * p.h + 1);
      // 대형 격자는 셀 수 × 규칙 평가(대상 확장·클리어런스) 비용이 커서 무조건 생략
      if (!isHeavyGrid() && cost <= 1.5e6) {
        const others = alt.placements.filter((_, i) => i !== drag.index);
        const cm = candidateMap(placeGrid, edgeDist, others, p.typeId, p.w, p.h, compiledRules, p.members || null);
        drag.bestCache = cm.best || null;
      } else {
        drag.bestCache = null;
      }
    }
    if (drag.bestCache) { overlay.best = drag.bestCache; overlay.bestW = p.w; overlay.bestH = p.h; }
  }
  overlay.selection = selection;
  if (s.tool === 'corridor' && draftCorridor.length) overlay.draftCorridor = draftCorridor;

  draw(ctx, s, view, overlay);
}
store.subscribe(redraw);

// ---------- 캔버스 마우스 ----------
function cellAt(evt) {
  const rect = canvas.getBoundingClientRect();
  const wpt = s2w(view, evt.clientX - rect.left, evt.clientY - rect.top);
  const s = store.state;
  if (s.grid) return worldToCell(s.grid, wpt.x, wpt.y);
  return null;
}

/** 클릭 위치에서 가장 가까운 대지 경계셀(edgeDist==1) — 진입점 스냅 */
function nearestBoundaryCell(wpt) {
  const g = store.state.grid;
  if (!g) return null;
  const ed = computeEdgeDist(g); // 도로망 마스킹 없는 원본 격자 기준
  let best = null, bd = Infinity;
  for (let r = 0; r < g.rows; r++)
    for (let c = 0; c < g.cols; c++) {
      if (ed[r * g.cols + c] !== 1) continue;
      const cx = g.origin.x + (c + 0.5) * g.cellSize;
      const cy = g.origin.y + (r + 0.5) * g.cellSize;
      const d = (cx - wpt.x) ** 2 + (cy - wpt.y) ** 2;
      if (d < bd) { bd = d; best = r * g.cols + c; }
    }
  return best;
}

canvas.addEventListener('mousedown', (e) => {
  const s = store.state;
  if (s.tool === 'entry') {
    if (!s.grid) return flashHint('먼저 대지를 만들어 주세요.');
    const rect = canvas.getBoundingClientRect();
    const wpt = s2w(view, e.clientX - rect.left, e.clientY - rect.top);
    const idx = nearestBoundaryCell(wpt);
    if (idx == null) return;
    pushUndo();
    s.entryCell = idx;
    const hadNet = s.roadNetwork.length > 0;
    if (hadNet) generateNetwork();
    s.tool = 'select';
    syncToolButtons();
    flashHint('진입점을 지정했습니다.' + (hadNet ? ' 도로망을 진입점 기준으로 재생성했습니다.' : ' 「도로망 생성」 시 반영됩니다.'));
    renderPanels();
    store.emit();
    return;
  }
  if (s.tool === 'corridor') {
    if (!s.grid) return flashHint('먼저 대지를 만들어 주세요.');
    const cell = cellAt(e); if (!cell) return;
    if (cell.c < 0 || cell.r < 0 || cell.c >= s.grid.cols || cell.r >= s.grid.rows) return;
    draftCorridor.push(cell.r * s.grid.cols + cell.c);
    $('finishCorridor').hidden = draftCorridor.length < 2;
    redraw();
    return;
  }
  if (s.tool === 'anchor') {
    if (!s.grid) return flashHint('먼저 대지를 만들어 주세요.');
    const cell = cellAt(e); if (!cell) return;
    if (cell.c < 0 || cell.r < 0 || cell.c >= s.grid.cols || cell.r >= s.grid.rows) return;
    pushUndo();
    const name = `앵커${s.anchors.length + 1}`;
    s.anchors.push({ id: uid('a'), name, c: cell.c, r: cell.r });
    refreshPlacementContext();
    s.tool = 'select';
    syncToolButtons();
    runFeasibility();
    renderPanels();
    store.emit();
    flashHint(`「${name}」 지정 (${cell.c},${cell.r}). 건물·순서 탭에서 이름을 바꿀 수 있습니다.`);
    return;
  }
  if (s.tool === 'drawSite') {
    const rect = canvas.getBoundingClientRect();
    const w = s2w(view, e.clientX - rect.left, e.clientY - rect.top);
    s.draftSite.push({ x: Math.round(w.x), y: Math.round(w.y) });
    $('finishSite').hidden = s.draftSite.length < 3;
    store.emit();
    return;
  }
  if (s.tool === 'place' && s.placingTypeId) {
    const cell = cellAt(e); if (!cell) return;
    placeAt(cell.c, cell.r);
    return;
  }
  if (s.tool === 'select') {
    const alt = activeAlt(s); if (!alt || !s.grid) return;
    const cell = cellAt(e); if (!cell) return;
    // 위에서부터 히트테스트 (블록은 실풋프린트 기준 — 노치 클릭은 통과)
    for (let i = alt.placements.length - 1; i >= 0; i--) {
      const p = alt.placements[i];
      if (placementCovers(p, cell.c, cell.r)) {
        if (e.shiftKey) {
          // 다중선택 토글 (블록 묶기용)
          if (selection.has(i)) selection.delete(i); else selection.add(i);
          syncGroupButtons();
          redraw();
          return;
        }
        selection.clear();
        syncGroupButtons();
        pushUndo();
        drag = { index: i, offC: cell.c - p.c, offR: cell.r - p.r };
        redraw();
        return;
      }
    }
    if (selection.size) { selection.clear(); syncGroupButtons(); redraw(); }
  }
});

canvas.addEventListener('mousemove', (e) => {
  const s = store.state;
  const cell = cellAt(e);
  hoverCell = cell;
  if (drag && cell && s.grid) {
    const alt = activeAlt(s);
    const p = alt.placements[drag.index];
    const nc = cell.c - drag.offC, nr = cell.r - drag.offR;
    const others = alt.placements.filter((_, i) => i !== drag.index);
    const occ = buildOccupancy(placeGrid, others);
    if (fits(placeGrid, occ, nc, nr, p.w, p.h, maskOf(p))) { p.c = nc; p.r = nr; }
    redraw();
    return;
  }
  if (s.tool === 'place') redraw();
});

canvas.addEventListener('mouseup', () => {
  if (drag) {
    const s = store.state;
    const alt = activeAlt(s);
    // 이동 후 도로/검증 갱신
    regenRoads(alt);
    runFeasibility();
    drag = null;
    store.emit();
    renderAlts();
  }
});

canvas.addEventListener('dblclick', () => {
  if (store.state.tool === 'drawSite') finishSite();
  if (store.state.tool === 'corridor') finishCorridor();
});

// ---------- 선형 요소 확정 (Phase 4) ----------
function finishCorridor() {
  const s = store.state;
  if (draftCorridor.length < 2) return;
  pushUndo();
  const kind = $('corKind').value;
  const widthM = Math.max(0.5, parseFloat($('corWidthM').value) || s.cellSize);
  const widthCells = Math.max(1, Math.round(widthM / s.cellSize));
  const cells = rasterizeCenterline(s.grid, draftCorridor, widthCells);
  const n = s.corridors.filter((k) => k.kind === kind).length + 1;
  s.corridors.push({
    id: uid('cor'), kind, name: `${CAT_LABELS[kind]} ${n}`, widthM,
    waypoints: draftCorridor.slice(), cells,
  });
  draftCorridor = [];
  $('finishCorridor').hidden = true;
  s.tool = 'select';
  syncToolButtons();
  refreshPlacementContext();
  for (const alt of s.alternatives) regenRoads(alt);
  runFeasibility();
  renderPanels();
  store.emit();
  flashHint(`${CAT_LABELS[kind]} 생성 (폭 ${widthM}m = ${widthCells}셀, ${cells.length}셀).`
    + (kind === 'tunnel' ? ' 터널은 지하 요소라 배치를 차단하지 않습니다.' : ''));
}
$('finishCorridor').addEventListener('click', finishCorridor);

function placeAt(c, r) {
  const s = store.state;
  const alt = activeAlt(s); if (!alt) return;
  const t = typeById(s, s.placingTypeId); if (!t) return;
  const v = placingVariant(t);
  const occ = buildOccupancy(placeGrid, alt.placements);
  const cand = { typeId: t.id, c, r, w: v.w, h: v.h, members: v.members };
  if (!fits(placeGrid, occ, c, r, v.w, v.h, maskOf(cand))
    || !evaluateHard(placeGrid, edgeDist, alt.placements, cand, compiledRules)
    || addWouldViolate(placeGrid, edgeDist, alt.placements, cand, compiledRules)) {
    flashHint('그 위치에는 배치할 수 없습니다 (대지 밖/도로/겹침/규칙 위반).');
    return;
  }
  if (!coverageOK(placeGrid, alt.placements, placementArea(cand), s.maxCoverage)) {
    flashHint(`건폐율 상한 ${s.maxCoverage}%를 초과합니다.`);
    return;
  }
  pushUndo();
  const placed = { typeId: t.id, c, r, w: v.w, h: v.h, rot: v.rot };
  if (v.members) placed.members = v.members.map((m) => ({ ...m })); // 스냅샷 (D1)
  alt.placements.push(placed);
  candCache = null;
  regenRoads(alt);
  runFeasibility();
  store.emit();
  renderAlts();
}

// ---------- 블록 묶기/해제 (Phase 2) ----------
function syncGroupButtons() {
  const alt = activeAlt(store.state);
  const sel = [...selection].map((i) => alt?.placements[i]).filter(Boolean);
  $('groupBtn').hidden = !(sel.length >= 2 && sel.every((p) => !p.members));
  $('ungroupBtn').hidden = !(sel.length === 1 && sel[0].members);
}

/** 선택된 유닛 배치들을 상대좌표 고정 블록 타입으로 승격 + placement 1개로 치환 */
function groupSelection() {
  const s = store.state;
  const alt = activeAlt(s); if (!alt) return;
  const idxs = [...selection].sort((a, b) => a - b);
  const sel = idxs.map((i) => alt.placements[i]).filter(Boolean);
  if (sel.length < 2 || sel.some((p) => p.members)) return;
  pushUndo();
  const minC = Math.min(...sel.map((p) => p.c));
  const minR = Math.min(...sel.map((p) => p.r));
  const w = Math.max(...sel.map((p) => p.c + p.w)) - minC;
  const h = Math.max(...sel.map((p) => p.r + p.h)) - minR;
  const members = sel.map((p) => ({ typeId: p.typeId, dc: p.c - minC, dr: p.r - minR, w: p.w, h: p.h }));
  const blockCount = s.buildingTypes.filter((t) => t.kind === 'block').length;
  const bt = {
    id: uid('t'), name: `블록 ${blockCount + 1}`, kind: 'block',
    w, h, members, color: '#546e7a',
  };
  s.buildingTypes.push(bt);
  alt.placements = alt.placements.filter((_, i) => !selection.has(i));
  alt.placements.push({ typeId: bt.id, c: minC, r: minR, w, h, rot: 0, members: members.map((m) => ({ ...m })) });
  selection.clear();
  syncGroupButtons();
  refreshPlacementContext();
  regenRoads(alt);
  runFeasibility();
  renderPanels();
  store.emit();
  flashHint(`「${bt.name}」 생성 (멤버 ${members.length}개). 타입 목록에서 이름을 바꾸거나 재배치할 수 있습니다.`);
}

/** 블록 placement를 유닛 placement들로 환원 (타입은 유지) */
function ungroupSelection() {
  const s = store.state;
  const alt = activeAlt(s); if (!alt) return;
  const idx = [...selection][0];
  const p = alt.placements[idx];
  if (!p || !p.members) return;
  pushUndo();
  const units = p.members.map((m) => ({ typeId: m.typeId, c: p.c + m.dc, r: p.r + m.dr, w: m.w, h: m.h }));
  alt.placements.splice(idx, 1, ...units);
  selection.clear();
  syncGroupButtons();
  regenRoads(alt);
  runFeasibility();
  renderPanels();
  store.emit();
  flashHint(`블록을 유닛 ${units.length}개로 해제했습니다 (블록 타입은 유지).`);
}

// R키: 배치 모드에서 블록 회전
window.addEventListener('keydown', (e) => {
  if (e.key.toLowerCase() !== 'r' || e.ctrlKey || e.metaKey) return;
  const s = store.state;
  if (s.tool !== 'place' || !s.placingTypeId) return;
  const t = typeById(s, s.placingTypeId);
  if (!t || t.kind !== 'block') return;
  placingRot = (placingRot + 1) % 4;
  candCache = null;
  flashHint(`회전: ${placingRot * 90}°`);
  redraw();
});

// ---------- 대지 완성 ----------
function finishSite() {
  const s = store.state;
  if (s.draftSite.length < 3) return;
  pushUndo();
  s.site = s.draftSite.slice();
  s.draftSite = [];
  s.roadNetwork = []; s.entryCell = null; s.anchors = []; s.corridors = []; // 대지가 바뀌면 셀 좌표 데이터 무효
  s.tool = 'select';
  $('finishSite').hidden = true;
  syncToolButtons();
  rebuildGrid();
}
$('finishSite').addEventListener('click', finishSite);
$('groupBtn').addEventListener('click', groupSelection);
$('ungroupBtn').addEventListener('click', ungroupSelection);

// ---------- 도로 · 검증 ----------
function regenRoads(alt) {
  if (!alt || !placeGrid) return;
  // 도로망 모드에서는 마스킹 격자 기준 → 진입로가 도로망 변까지 자동 연결
  const rr = generateRoads(placeGrid, alt.placements);
  alt.roads = rr.cells;
  alt.roadsMain = rr.main;
}
function runFeasibility(force = false) {
  const s = store.state;
  const alt = activeAlt(s);
  if (!alt || !s.grid) { feasResult = []; renderFeas(); return; }
  // 대형 격자: 순차 시뮬레이션이 수 초 걸리므로 온디맨드(검증 탭 버튼)로만 실행
  if (isHeavyGrid() && !force) { feasResult = ['__heavy__']; renderFeas(); return; }
  // 남은 순서 = sequence에서 이미 배치된 타입만큼 제거
  const counts = {};
  for (const p of alt.placements) counts[p.typeId] = (counts[p.typeId] || 0) + 1;
  const remaining = [];
  for (const id of s.sequence) {
    if (counts[id] > 0) counts[id]--;
    else remaining.push(id);
  }
  feasResult = feasibility(placeGrid, edgeDist, s.buildingTypes, compiledRules, remaining, alt.placements,
    { maxCoverage: s.maxCoverage });
  renderFeas();
}

// ---------- 툴바 ----------
function syncToolButtons() {
  document.querySelectorAll('.tool').forEach((b) =>
    b.classList.toggle('active', b.dataset.tool === store.state.tool));
  $('finishSite').hidden = !(store.state.tool === 'drawSite' && store.state.draftSite.length >= 3);
}
document.querySelectorAll('.tool').forEach((b) =>
  b.addEventListener('click', () => {
    store.state.tool = b.dataset.tool;
    selection.clear(); syncGroupButtons();
    if (b.dataset.tool !== 'corridor') { draftCorridor = []; $('finishCorridor').hidden = true; }
    if (b.dataset.tool !== 'place') store.state.placingTypeId = null;
    if (b.dataset.tool === 'drawSite') {
      pushUndo();
      store.state.site = null; store.state.draftSite = [];
      store.state.roadNetwork = []; store.state.entryCell = null; store.state.anchors = [];
      refreshPlacementContext();
    }
    syncToolButtons();
    renderPanels();
    store.emit();
  }));

$('windDir').addEventListener('change', (e) => {
  pushUndo();
  store.state.windDir = e.target.value === '' ? null : parseInt(e.target.value, 10);
  refreshPlacementContext();
  runFeasibility();
  renderAlts();
  store.emit();
});

$('maxCoverage').addEventListener('change', (e) => {
  const v = parseFloat(e.target.value);
  store.state.maxCoverage = isNaN(v) || v <= 0 ? null : Math.min(100, v);
  runFeasibility();
  renderAlts();
  store.emit();
});

$('cellSize').addEventListener('change', (e) => {
  store.state.cellSize = Math.max(0.5, parseFloat(e.target.value) || 10);
  if (store.state.site) {
    pushUndo();
    // 셀 크기 변경 시 셀 좌표 기반 데이터(배치·도로망·진입점·앵커·선형)는 초기화
    store.state.roadNetwork = [];
    store.state.entryCell = null;
    store.state.anchors = [];
    store.state.corridors = [];
    for (const a of store.state.alternatives) { a.placements = []; a.roads = []; a.roadsMain = []; }
    rebuildGrid();
    renderAlts();
  }
});

$('autoPlace').addEventListener('click', () => {
  const s = store.state;
  if (!s.grid) return flashHint('먼저 대지를 만들어 주세요.');
  if (!s.sequence.length) return flashHint('배치 순서를 먼저 설정하세요.');
  pushUndo();
  // 활성 대안을 자동배치로 채우고, 추가 대안 생성 (대형 격자는 1개만 — UI 블로킹 방지)
  const heavy = isHeavyGrid();
  const baseSeed = s.alternatives.length * 97 + 1;
  const opts = { maxCoverage: s.maxCoverage, annealIters: heavy ? 120 : 300 };
  const alt = activeAlt(s);
  const first = autoPlace(placeGrid, edgeDist, s.buildingTypes, compiledRules, s.sequence, baseSeed, opts);
  alt.placements = first.placements; regenRoads(alt);
  const extras = heavy ? 0 : 2;
  for (let k = 1; k <= extras; k++) {
    const na = newAlternative(`대안 ${s.alternatives.length + 1}`);
    const res = autoPlace(placeGrid, edgeDist, s.buildingTypes, compiledRules, s.sequence, baseSeed + k * 1237, opts);
    na.placements = res.placements; regenRoads(na);
    s.alternatives.push(na);
  }
  if (heavy) flashHint('대형 격자 — 대안 1개만 생성했습니다. 추가 대안은 「자동 배치」를 다시 누르세요(다른 시드).');
  if (first.unplaced.length)
    flashHint(`일부 건물을 배치하지 못했습니다: ${first.unplaced.map((id) => typeById(s, id)?.name).join(', ')}`);
  runFeasibility();
  renderPanels();
  store.emit();
});

$('cl-add').addEventListener('click', () => {
  const s = store.state;
  const a = $('cl-a').value, b = $('cl-b').value;
  const minM = Math.max(0, parseFloat($('cl-m').value) || 0);
  if (!minM) return flashHint('이격 거리(m)를 입력하세요.');
  pushUndo();
  s.clearances.push({ id: uid('cl'), a, b, minM });
  refreshPlacementContext();
  runFeasibility(); renderPanels(); store.emit();
});

$('roadWidthM').addEventListener('change', (e) => {
  const v = parseFloat(e.target.value);
  store.state.roadParams.widthM = isNaN(v) || v <= 0 ? null : v;
  if (store.state.roadNetwork.length && store.state.grid) {
    pushUndo(); generateNetwork(); renderPanels(); store.emit();
  }
});
$('ringOffsetM').addEventListener('change', (e) => {
  const v = parseFloat(e.target.value);
  store.state.roadParams.ringOffsetM = isNaN(v) || v < 0 ? null : v;
  if (store.state.roadNetwork.length && store.state.grid && store.state.roadPattern === 'loop') {
    pushUndo(); generateNetwork(); renderPanels(); store.emit();
  }
});

$('genRoads').addEventListener('click', () => {
  const alt = activeAlt(store.state);
  if (!alt) return;
  regenRoads(alt);
  store.emit();
});

// 도로 우선 모드: 패턴·진입점 기반 도로망 생성 (재사용 — 버튼/패턴변경/진입점변경)
const PATTERN_LABELS = { comb: '빗살형', grid: '격자형', loop: '루프형' };

function generateNetwork() {
  const s = store.state;
  // 가지 간격: 가장 큰 건물 치수 + 3 (블록 안 모든 필지가 도로에 접하도록)
  const maxDim = s.buildingTypes.reduce((m, t) => Math.max(m, t.w, t.h), 2);
  const widthCells = s.roadParams.widthM != null
    ? Math.max(1, Math.round(s.roadParams.widthM / s.cellSize)) : 1;
  const spacing = Math.min(24, Math.max(4, maxDim + 3 + (widthCells - 1)));
  // 루프 링 깊이: '경계 Xm 안쪽' = 빈 셀 ceil(X/cs) → ringDepth = 1 + ceil
  const ringDepth = s.roadParams.ringOffsetM != null
    ? 1 + mCeil(s.roadParams.ringOffsetM, s.cellSize) : null;
  s.roadNetwork = generateRoadNetwork(s.grid, spacing, s.roadPattern, s.entryCell,
    { widthCells, ringDepth });
  // 폐합/단절 검증 (P4 보완): 소방도로가 끊겨 있으면 경고
  const comps = networkComponents(s.grid, s.roadNetwork);
  if (comps > 1) flashHint(`⚠ 도로망이 ${comps}개 구간으로 단절되어 있습니다 (오목 대지에서 발생 가능). 패턴/링 이격을 조정하세요.`);
  // 기존 배치 중 도로망과 겹치는 건물 제거
  const netSet = new Set(s.roadNetwork);
  let removed = 0;
  for (const a of s.alternatives) {
    const before = a.placements.length;
    a.placements = a.placements.filter((p) => {
      for (let dr = 0; dr < p.h; dr++)
        for (let dc = 0; dc < p.w; dc++)
          if (netSet.has((p.r + dr) * s.grid.cols + (p.c + dc))) return false;
      return true;
    });
    removed += before - a.placements.length;
  }
  refreshPlacementContext();
  for (const a of s.alternatives) regenRoads(a);
  runFeasibility();
  return { spacing, removed };
}

$('roadNet').addEventListener('click', () => {
  const s = store.state;
  if (!s.grid) return flashHint('먼저 대지를 만들어 주세요.');
  pushUndo();
  if (s.roadNetwork.length) {
    s.roadNetwork = [];
    refreshPlacementContext();
    for (const a of s.alternatives) regenRoads(a);
    runFeasibility();
    flashHint('도로망을 제거했습니다.');
  } else {
    const { spacing, removed } = generateNetwork();
    flashHint(`${PATTERN_LABELS[s.roadPattern]} 도로망 생성 (간격 ${spacing}셀)${removed ? ` — 도로와 겹친 건물 ${removed}동 제거됨` : ''}. 규칙의 도로인접/세트백이 도로 기준으로 동작합니다.`);
  }
  renderPanels();
  store.emit();
});

$('roadPattern').addEventListener('change', (e) => {
  const s = store.state;
  s.roadPattern = e.target.value;
  if (s.roadNetwork.length && s.grid) {
    pushUndo();
    generateNetwork();
    flashHint(`${PATTERN_LABELS[s.roadPattern]}으로 도로망을 다시 생성했습니다.`);
    renderPanels();
    store.emit();
  }
});
store.subscribe(() => {
  $('roadNet').textContent = store.state.roadNetwork.length ? '도로망 제거' : '도로망 생성';
});

// ---------- DXF ----------
$('dxfInput').addEventListener('change', async (e) => {
  const file = e.target.files[0]; if (!file) return;
  const text = await file.text();
  const polys = parseDXF(text);
  const site = pickSitePolygon(polys);
  if (!site) return flashHint('DXF에서 폴리라인(대지)을 찾지 못했습니다.');
  pushUndo();
  store.state.site = site;
  store.state.draftSite = [];
  store.state.roadNetwork = [];
  store.state.entryCell = null;
  store.state.anchors = [];
  store.state.corridors = [];
  store.state.tool = 'select';
  syncToolButtons();
  rebuildGrid();
  flashHint(`DXF 로드 완료: 정점 ${site.length}개, 폴리곤 ${polys.length}개 중 최대 면적 채택.`);
  e.target.value = '';
});

// ---------- 패널 렌더 ----------
const colors = ['#e57373', '#64b5f6', '#81c784', '#ffb74d', '#ba68c8', '#4db6ac', '#f06292', '#a1887f'];

function renderPanels() {
  renderAlts(); renderTypes(); renderRules(); renderSeq(); renderFeas(); renderAnchors();
  renderCorridors(); renderClearances();
}

/** typeId(블록 멤버 포함)의 실풋프린트에 4-인접한 빈 셀들 — 라우팅 출발/도착점 */
function frontCellsOf(typeId) {
  const s = store.state;
  const alt = activeAlt(s);
  if (!alt || !placeGrid) return [];
  const rects = expandTargets(alt.placements, typeId);
  const occ = buildOccupancy(placeGrid, alt.placements);
  const out = new Set();
  const g = placeGrid;
  for (const rc of rects) {
    for (let dr = -1; dr <= rc.h; dr++)
      for (let dc = -1; dc <= rc.w; dc++) {
        const onBorder = dr === -1 || dr === rc.h || dc === -1 || dc === rc.w;
        if (!onBorder) continue;
        const cc = rc.c + dc, rr = rc.r + dr;
        if (cc < 0 || rr < 0 || cc >= g.cols || rr >= g.rows) continue;
        const i = rr * g.cols + cc;
        if (s.grid.buildable[i] && !occ[i]) out.add(i); // 원본 격자 기준(도로 위도 출발 가능)
      }
  }
  return [...out];
}

function runAutoRoute() {
  const s = store.state;
  const alt = activeAlt(s);
  if (!alt || !s.grid) return flashHint('먼저 대지와 배치가 필요합니다.');
  const fromId = $('rt-from').value, toId = $('rt-to').value;
  if (!fromId || !toId || fromId === toId) return flashHint('서로 다른 출발/도착 타입을 선택하세요.');
  const src = frontCellsOf(fromId), dst = frontCellsOf(toId);
  if (!src.length || !dst.length) return flashHint('활성 대안에 두 타입의 배치(또는 블록 멤버)가 있어야 합니다.');
  const kind = $('corKind').value;
  const widthM = Math.max(0.5, parseFloat($('corWidthM').value) || s.cellSize);
  const widthCells = Math.max(1, Math.round(widthM / s.cellSize));
  // 통과 정책: 대지 내부 + 건물 미점유 + 차단성 선형(rack/conduit) 회피. 도로·터널은 횡단 허용
  const occ = buildOccupancy(placeGrid, alt.placements);
  const hardCor = new Set(s.corridors
    .filter((k) => k.kind === 'rack' || k.kind === 'conduit').flatMap((k) => k.cells));
  const g = s.grid;
  const passable = (c, r) => {
    if (c < 0 || r < 0 || c >= g.cols || r >= g.rows) return false;
    const i = r * g.cols + c;
    return g.buildable[i] === 1 && !occ[i] && !hardCor.has(i);
  };
  const res = routeCorridor(s.grid, passable, src, dst, { widthCells, turnPenalty: 1 });
  if (!res) return flashHint('경로를 찾지 못했습니다 (막힘). 배치를 조정하거나 다른 종류로 시도하세요.');
  pushUndo();
  const name = `${typeById(s, fromId)?.name || '?'}→${typeById(s, toId)?.name || '?'} ${CAT_LABELS[kind]}`;
  s.corridors.push({
    id: uid('cor'), kind, name, widthM,
    waypoints: res.waypoints, cells: res.cells,
    route: { fromTypeId: fromId, toTypeId: toId },
  });
  refreshPlacementContext();
  for (const a2 of s.alternatives) regenRoads(a2);
  runFeasibility();
  renderPanels();
  store.emit();
  flashHint(`「${name}」 라우팅 완료 (${res.cells.length}셀, 방향전환 ${Math.max(0, res.waypoints.length - 2)}회).`);
}
$('rt-run').addEventListener('click', runAutoRoute);

function refreshRouteOptions() {
  const s = store.state;
  // 배치 단위 타입 + 블록 멤버로 쓰인 유닛 타입 모두 대상 (예: GIS→GT승압TR 터널)
  const opts = s.buildingTypes.map((t) => `<option value="${t.id}">${t.name}</option>`).join('');
  const keepF = $('rt-from').value, keepT = $('rt-to').value;
  $('rt-from').innerHTML = opts;
  $('rt-to').innerHTML = opts;
  if (keepF) $('rt-from').value = keepF;
  if (keepT) $('rt-to').value = keepT;
}

function renderCorridors() {
  refreshRouteOptions();
  const s = store.state;
  const el = $('corridorList');
  if (!s.corridors.length) {
    el.className = 'list muted';
    el.innerHTML = '「선형 그리기」 도구로 경유점을 클릭해 추가하세요.';
    return;
  }
  el.className = 'list';
  el.innerHTML = '';
  s.corridors.forEach((k) => {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<span class="grow">${k.name} <small>폭 ${k.widthM}m · ${k.cells.length}셀</small></span>
      <span class="x" data-del>✕</span>`;
    div.querySelector('[data-del]').onclick = () => {
      pushUndo();
      s.corridors = s.corridors.filter((x) => x.id !== k.id);
      refreshPlacementContext();
      for (const alt of s.alternatives) regenRoads(alt);
      runFeasibility(); renderPanels(); store.emit();
    };
    el.appendChild(div);
  });
}

function renderClearances() {
  const s = store.state;
  // 셀렉트 옵션 (최초 1회)
  if (!$('cl-a').options.length) {
    const opts = Object.entries(CAT_LABELS).map(([v, l]) => `<option value="${v}">${l}</option>`).join('');
    $('cl-a').innerHTML = opts;
    $('cl-b').innerHTML = opts;
    $('cl-a').value = 'road'; $('cl-b').value = 'equipment';
  }
  const el = $('clearList');
  if (!s.clearances.length) {
    el.className = 'list muted';
    el.innerHTML = '예: 도로 ↔ 장비 3m — 한 줄로 전 타입에 적용됩니다.';
    return;
  }
  el.className = 'list';
  el.innerHTML = '';
  s.clearances.forEach((cl) => {
    const cells = mCeil(cl.minM, s.cellSize);
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<span class="grow"><b>${CAT_LABELS[cl.a] || cl.a}</b> ↔ <b>${CAT_LABELS[cl.b] || cl.b}</b>
      : <b>${cl.minM}m</b><small>(${cells}셀)</small> 이상</span>
      <span class="x" data-del>✕</span>`;
    div.querySelector('[data-del]').onclick = () => {
      pushUndo();
      s.clearances = s.clearances.filter((x) => x.id !== cl.id);
      refreshPlacementContext(); runFeasibility(); renderPanels(); store.emit();
    };
    el.appendChild(div);
  });
}

function renderAnchors() {
  const s = store.state;
  const el = $('anchorList');
  if (!s.anchors.length) {
    el.className = 'list muted';
    el.innerHTML = '「앵커」 도구로 캔버스를 클릭해 Tie-in/Gate 지점을 지정하세요.';
    return;
  }
  el.className = 'list';
  el.innerHTML = '';
  s.anchors.forEach((a) => {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<input type="text" value="${a.name}" style="width:110px" data-name />
      <span class="grow"><small>(${a.c}, ${a.r})</small></span>
      <span class="x" data-del>✕</span>`;
    div.querySelector('[data-name]').addEventListener('change', (e) => {
      a.name = e.target.value.trim() || a.name;
      renderRules(); store.emit();
    });
    div.querySelector('[data-del]').onclick = () => {
      pushUndo();
      s.anchors = s.anchors.filter((x) => x.id !== a.id);
      refreshPlacementContext();
      renderPanels(); runFeasibility(); store.emit();
    };
    el.appendChild(div);
  });
}

function renderAlts() {
  const s = store.state;
  const el = $('altList'); el.innerHTML = '';
  s.alternatives.forEach((a) => {
    const div = document.createElement('div');
    div.className = 'item' + (a.id === s.activeAltId ? ' active' : '');
    let metricsHtml = '';
    if (placeGrid) {
      const m = layoutMetrics(placeGrid, edgeDist, a.placements, compiledRules, s.sequence);
      const pct = Math.round(m.fillRate * 100);
      const overCov = s.maxCoverage != null && pct > s.maxCoverage;
      let warn = m.hardViolations ? ` · <span class="badge-no">위반 ${m.hardViolations}</span>` : '';
      if (overCov) warn += ` · <span class="badge-no">건폐율 초과</span>`;
      metricsHtml = `<div class="metrics">배치 <b>${m.placed}/${m.target || '–'}</b> · 충전 <b>${pct}%</b> · 점수 <b>${m.score}</b>${warn}</div>`;
    }
    div.innerHTML = `<span class="col grow"><span>${a.name} <small>(${a.placements.length}동)</small></span>${metricsHtml}</span>
      <button class="mini" data-dup>복제</button><span class="x" data-del>✕</span>`;
    div.querySelector('.col').onclick = () => {
      s.activeAltId = a.id; candCache = null;
      selection.clear(); syncGroupButtons();
      runFeasibility(); store.emit(); renderAlts();
    };
    div.querySelector('[data-dup]').onclick = () => {
      const na = newAlternative(a.name + ' 복사');
      na.placements = a.placements.map((p) => ({ ...p }));
      na.roads = [...(a.roads || [])]; na.roadsMain = [...(a.roadsMain || [])];
      s.alternatives.push(na); s.activeAltId = na.id; candCache = null; store.emit(); renderAlts();
    };
    div.querySelector('[data-del]').onclick = () => {
      pushUndo();
      s.alternatives = s.alternatives.filter((x) => x.id !== a.id);
      if (s.activeAltId === a.id) s.activeAltId = s.alternatives[0]?.id || null;
      candCache = null; store.emit(); renderAlts();
    };
    el.appendChild(div);
  });
}
$('addAlt').onclick = () => {
  const s = store.state;
  const na = newAlternative(`대안 ${s.alternatives.length + 1}`);
  s.alternatives.push(na); s.activeAltId = na.id; candCache = null; store.emit(); renderAlts();
};

// ----- 건물 타입: 폼 -----
function renderTypes() {
  const s = store.state;
  const el = $('typeList'); el.innerHTML = '';
  s.buildingTypes.forEach((t) => {
    const div = document.createElement('div');
    div.className = 'item';
    const blockBadge = t.kind === 'block' ? ` <small class="badge-ok">[블록·${t.members?.length || 0}]</small>` : '';
    div.innerHTML = `<span class="swatch" style="background:${t.color}"></span>
      <span class="grow">${t.name}${blockBadge} <small>${t.w}×${t.h}</small></span>
      <button class="mini" data-place>배치</button>
      <button class="mini" data-seq>순서+</button>
      <span class="x" data-del>✕</span>`;
    div.querySelector('[data-place]').onclick = () => {
      s.tool = 'place'; s.placingTypeId = t.id; placingRot = 0; candCache = null;
      syncToolButtons();
      flashHint(`「${t.name}」 배치 모드: 초록칸을 클릭하세요. 노란 점선 = 추천 위치.${t.kind === 'block' ? ' R키 = 90° 회전.' : ''}`);
      store.emit();
    };
    div.querySelector('[data-seq]').onclick = () => { s.sequence.push(t.id); renderSeq(); runFeasibility(); store.emit(); };
    div.querySelector('[data-del]').onclick = () => {
      // 블록 멤버로 참조 중인 유닛 타입은 삭제 차단 (고아 멤버 방지)
      const refBlock = s.buildingTypes.find((b) => b.kind === 'block'
        && (b.members || []).some((m) => m.typeId === t.id));
      if (refBlock) return flashHint(`「${refBlock.name}」 블록의 멤버로 사용 중이라 삭제할 수 없습니다. 블록을 먼저 삭제하세요.`);
      pushUndo();
      s.buildingTypes = s.buildingTypes.filter((x) => x.id !== t.id);
      s.sequence = s.sequence.filter((id) => id !== t.id);
      s.rules = s.rules.filter((r) => r.buildingTypeId !== t.id && r.targetType !== t.id);
      // 이미 배치된 해당 타입 건물도 전 대안에서 제거 (고아 방지)
      for (const alt of s.alternatives) {
        const before = alt.placements.length;
        alt.placements = alt.placements.filter((p) => p.typeId !== t.id);
        if (alt.placements.length !== before) regenRoads(alt);
      }
      if (s.placingTypeId === t.id) { s.placingTypeId = null; s.tool = 'select'; syncToolButtons(); }
      refreshPlacementContext(); // 규칙 연쇄 삭제 반영 (컴파일 재실행)
      runFeasibility();
      renderPanels(); store.emit();
    };
    el.appendChild(div);
  });
}

$('addType').onclick = () => {
  const f = $('typeForm');
  f.hidden = !f.hidden;
  if (!f.hidden) $('tf-name').focus();
};
$('typeForm').addEventListener('submit', (e) => {
  e.preventDefault();
  const s = store.state;
  const name = $('tf-name').value.trim() || `건물${s.buildingTypes.length + 1}`;
  const w = Math.max(1, parseInt($('tf-w').value, 10) || 1);
  const h = Math.max(1, parseInt($('tf-h').value, 10) || 1);
  pushUndo();
  s.buildingTypes.push({
    id: uid('t'), name, w, h,
    category: $('tf-cat').value, // 클리어런스 카테고리 (building/equipment)
    color: colors[s.buildingTypes.length % colors.length],
  });
  $('tf-name').value = '';
  $('typeForm').hidden = true;
  renderTypes(); store.emit();
});
$('typeForm').querySelector('[data-cancel]').onclick = () => { $('typeForm').hidden = true; };

// ----- 배치 규칙: 종류 정의 · 문장화 · 마이그레이션 · 모달 편집 -----
const DIR_LABELS = { S: '남', N: '북', E: '동', W: '서' };

const RULE_KINDS = [
  { v: 'nearRoad', label: '도로/경계 인접', rows: ['basis', 'gap'], gapLabel: '최대 거리(m)',
    desc: '건물이 기준(도로/경계)에서 지정 거리(m) 이내에 있어야 합니다. 기준을 "도로만"으로 두면 도로망에만 반응합니다.' },
  { v: 'setback', label: '세트백 (이격)', rows: ['basis', 'gap'], gapLabel: '띄울 거리(m)',
    desc: '건물이 기준(도로/경계)에서 지정 거리(m) 이상 떨어져야 합니다.' },
  { v: 'distanceTo', label: '거리 범위', rows: ['target', 'minmax'], minmaxLabel: '최소~최대 (m)',
    desc: '기준 건물과의 거리를 m로 제한합니다. 최소만 쓰면 이격, 최대만 쓰면 인접 규칙이 됩니다. (예: Admin은 Cooling tower에서 50m 이상)' },
  { v: 'adjacentCount', label: '인접 개수', rows: ['target', 'gap', 'minmax'],
    gapLabel: '인접 판정 거리(m)', minmaxLabel: '개수 최소~최대',
    desc: '지정 거리(m) 이내의 기준 건물 "개수"를 제한합니다. 상한 초과는 배치 시 즉시 차단되고, 하한 미달은 대안 지표의 위반으로 표시됩니다.' },
  { v: 'directionOf', label: '방향 배치', rows: ['target', 'dir', 'gap'], gapLabel: '최대 거리(m)',
    desc: '기준 건물의 지정 방향(동/서/남/북)에, 지정 거리(m) 이내로 배치되어야 합니다.' },
  { v: 'sameRowCol', label: '행/열 정렬', rows: ['target', 'axis'],
    desc: '기준 건물과 같은 행(가로) 또는 같은 열(세로)에 시작점이 정렬되어야 합니다.' },
  { v: 'openSide', label: '방위 개방', rows: ['dir', 'gap'], gapLabel: '개방 깊이(m)',
    desc: '건물의 지정 방향 전면이 지정 거리(m)만큼 비어 있어야 합니다 (일조·조망 확보).' },
  { v: 'windSide', label: '풍향 배치', rows: ['side', 'gap'], gapLabel: '중심선 여유(m)',
    desc: '툴바 풍향 기준 부지 중심의 바람축 반평면에 배치합니다. hard=반평면 강제, soft=바깥쪽일수록 가점(Flare "가장 외곽" 표현). 풍향 미설정 시 비활성.' },
  { v: 'centerOf', label: '중앙 배치', rows: ['gap'], gapLabel: '중심 최대 거리(m)',
    desc: '부지 무게중심에서 지정 거리(m) 이내에 배치합니다. Power block "중앙 배치"에 사용. soft면 가까울수록 가점.' },
  { v: 'between', label: '중간 배치', rows: ['target', 'target2', 'gap'], gapLabel: '중점 허용 반경(m)',
    desc: '두 기준 건물의 중간 지점 근처에 배치합니다 (예: K.O Drum = Flare stack과 Power block의 중간). 두 기준이 아직 없으면 배치 시점엔 유보되고 최종 검증에서 위반으로 표시됩니다.' },
  { v: 'distanceToAnchor', label: '앵커 거리', rows: ['anchor', 'minmax'], minmaxLabel: '최소~최대 (m)',
    desc: '「앵커」 도구로 지정한 기준점(Tie-in/Gate)과의 거리를 제한합니다.' },
];
const BASIS_LABELS = { any: '경계+도로', road: '도로만', fence: '대지 경계만' };

/** 구형 규칙(gapFrom/adjacentTo/insideOnly) → distanceTo로 통합 */
function migrateRules(rules) {
  return (rules || [])
    .filter((r) => r.kind !== 'insideOnly')
    .map((r) => {
      if (r.kind === 'gapFrom') return { ...r, kind: 'distanceTo', min: r.gap, max: null };
      if (r.kind === 'adjacentTo') return { ...r, kind: 'distanceTo', min: 0, max: r.gap };
      return r;
    });
}

function ruleToText(r) {
  const s = store.state;
  const bt = typeById(s, r.buildingTypeId)?.name || '?';
  const tt = typeById(s, r.targetType)?.name || '?';
  const strength = r.mode === 'hard' ? '<small class="badge-no">[필수]</small>' : `<small class="badge-ok">[선호+${r.weight ?? 20}]</small>`;
  const c = compileRules([r], s.cellSize)[0]; // m→셀 환산 병기용
  const mc = (m, cells) => `<b>${m}m</b><small>(${cells}셀)</small>`;
  const basis = (r.basis && r.basis !== 'any') ? `${BASIS_LABELS[r.basis]}에서 ` : '도로/경계에서 ';
  let body;
  switch (r.kind) {
    case 'nearRoad': body = `${basis}${mc(r.gapM ?? 0, c.gap)} 이내`; break;
    case 'setback': body = `${basis}${mc(r.gapM ?? 0, c.gap)} 이상 이격`; break;
    case 'distanceTo': {
      const minM = r.minM || 0;
      body = r.maxM == null ? `<b>${tt}</b>에서 ${mc(minM, c.min)} 이상`
        : minM > 0 ? `<b>${tt}</b>에서 <b>${minM}~${r.maxM}m</b><small>(${c.min}~${c.max}셀)</small>`
        : `<b>${tt}</b>에서 ${mc(r.maxM, c.max)} 이내`;
      break;
    }
    case 'adjacentCount':
      body = `${mc(r.gapM ?? 0, c.gap)} 이내 <b>${tt}</b> <b>${r.min || 0}~${r.max == null ? '∞' : r.max}개</b>`; break;
    case 'directionOf': body = `<b>${tt}</b>의 <b>${DIR_LABELS[r.dir] || r.dir}쪽</b> ${mc(r.gapM ?? 0, c.gap)} 이내`; break;
    case 'sameRowCol': body = `<b>${tt}</b>와 같은 <b>${r.axis === 'col' ? '열' : '행'}</b> 정렬`; break;
    case 'openSide': body = `<b>${DIR_LABELS[r.dir] || r.dir}쪽</b> 전면 ${mc(r.gapM ?? 0, c.gap)} 개방`; break;
    case 'windSide':
      body = `바람 <b>${r.side === 'up' ? '거스르는 쪽(업윈드)' : '불어가는 쪽(다운윈드)'}</b> 배치`
        + (s.windDir == null ? ' <small class="badge-no">(풍향 미설정 — 비활성)</small>' : '');
      break;
    case 'centerOf': body = `부지 중심에서 ${mc(r.gapM ?? 0, c.gap)} 이내`; break;
    case 'between': {
      const tt2 = typeById(s, r.targetType2)?.name || '?';
      body = `<b>${tt}</b>와 <b>${tt2}</b>의 중간 (반경 ${mc(r.gapM ?? 0, c.gap)})`;
      break;
    }
    case 'distanceToAnchor': {
      const anc = s.anchors.find((x) => x.id === r.anchorId);
      const aname = anc ? anc.name : '<span class="badge-no">삭제된 앵커</span>';
      const minM = r.minM || 0;
      const range = r.maxM == null ? `${mc(minM, c.min)} 이상`
        : minM > 0 ? `<b>${minM}~${r.maxM}m</b><small>(${c.min}~${c.max}셀)</small>`
        : `${mc(r.maxM, c.max)} 이내`;
      body = `${aname}에서 ${range}`;
      break;
    }
    default: body = r.kind;
  }
  return `<b>${bt}</b>: ${body} ${strength}`;
}

function renderRules() {
  const s = store.state;
  const el = $('ruleList'); el.innerHTML = '';
  s.rules.forEach((r) => {
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<span class="grow">${ruleToText(r)}</span>
      <button class="mini" data-edit>편집</button><span class="x" data-del>✕</span>`;
    div.querySelector('[data-edit]').onclick = () => openRuleModal(r);
    div.querySelector('[data-del]').onclick = () => {
      pushUndo();
      s.rules = s.rules.filter((x) => x.id !== r.id);
      refreshPlacementContext();
      renderRules(); runFeasibility(); store.emit();
    };
    el.appendChild(div);
  });
  if (!s.rules.length) el.innerHTML = '<div class="muted">규칙 없음 — 「+ 새 규칙」으로 추가하세요.</div>';
}

// ----- 규칙 모달 -----
let editingRuleId = null;

function openRuleModal(rule = null) {
  const s = store.state;
  if (!s.buildingTypes.length) return flashHint('먼저 건물 타입을 추가하세요.');
  editingRuleId = rule ? rule.id : null;
  $('rm-title').textContent = rule ? '규칙 편집' : '새 배치 규칙';
  const optHtml = s.buildingTypes.map((t) => `<option value="${t.id}">${t.name} (${t.w}×${t.h})</option>`).join('');
  $('rm-type').innerHTML = optHtml;
  $('rm-target').innerHTML = optHtml;
  $('rm-target2').innerHTML = optHtml;
  $('rm-anchor').innerHTML = s.anchors.length
    ? s.anchors.map((x) => `<option value="${x.id}">${x.name} (${x.c},${x.r})</option>`).join('')
    : '<option value="">앵커 없음 — 「앵커」 도구로 먼저 지정</option>';
  $('rm-kind').innerHTML = RULE_KINDS.map((k) => `<option value="${k.v}">${k.label}</option>`).join('');
  if (rule) {
    $('rm-type').value = rule.buildingTypeId;
    $('rm-kind').value = RULE_KINDS.some((k) => k.v === rule.kind) ? rule.kind : 'distanceTo';
    if (rule.targetType) $('rm-target').value = rule.targetType;
    $('rm-basis').value = rule.basis || 'any';
    $('rm-gap').value = rule.gapM ?? '';
    // distanceTo는 m, adjacentCount는 개수
    $('rm-min').value = rule.kind === 'adjacentCount' ? (rule.min ?? 0) : (rule.minM ?? 0);
    $('rm-max').value = rule.kind === 'adjacentCount' ? (rule.max ?? '') : (rule.maxM ?? '');
    $('rm-dir').value = rule.dir || 'S';
    $('rm-axis').value = rule.axis || 'row';
    $('rm-side').value = rule.side || 'down';
    if (rule.targetType2) $('rm-target2').value = rule.targetType2;
    if (rule.anchorId) $('rm-anchor').value = rule.anchorId;
    $('rm-mode').value = rule.mode;
    $('rm-weight').value = rule.weight ?? 20;
  } else {
    $('rm-basis').value = 'any';
    $('rm-gap').value = '';
    $('rm-min').value = 0;
    $('rm-max').value = '';
  }
  syncModalRows();
  $('ruleModal').hidden = false;
}

function syncModalRows() {
  const kind = RULE_KINDS.find((k) => k.v === $('rm-kind').value) || RULE_KINDS[0];
  document.querySelectorAll('#ruleModal [data-row]').forEach((el) => {
    const row = el.dataset.row;
    if (row === 'weight') { el.style.display = $('rm-mode').value === 'soft' ? '' : 'none'; return; }
    el.style.display = kind.rows.includes(row) ? '' : 'none';
  });
  $('rm-gap-label').textContent = kind.gapLabel || '거리(m)';
  $('rm-minmax-label').textContent = kind.minmaxLabel || '최소~최대';
  $('rm-desc').textContent = kind.desc;
  updateRulePreview();
}

function ruleFromModal() {
  const kind = $('rm-kind').value;
  const def = RULE_KINDS.find((k) => k.v === kind);
  const mode = $('rm-mode').value;
  const num = (v) => { const n = parseFloat(v); return isNaN(n) ? 0 : Math.max(0, n); };
  const isCount = kind === 'adjacentCount'; // minmax가 개수인 유일 kind
  return {
    id: editingRuleId || uid('r'),
    buildingTypeId: $('rm-type').value,
    kind,
    targetType: def.rows.includes('target') ? $('rm-target').value : null,
    targetType2: def.rows.includes('target2') ? $('rm-target2').value : undefined,
    anchorId: def.rows.includes('anchor') ? ($('rm-anchor').value || null) : undefined,
    side: def.rows.includes('side') ? $('rm-side').value : undefined,
    basis: def.rows.includes('basis') ? $('rm-basis').value : undefined,
    dir: def.rows.includes('dir') ? $('rm-dir').value : null,
    axis: def.rows.includes('axis') ? $('rm-axis').value : null,
    gapM: def.rows.includes('gap') ? num($('rm-gap').value) : undefined,
    minM: def.rows.includes('minmax') && !isCount ? num($('rm-min').value) : undefined,
    maxM: def.rows.includes('minmax') && !isCount ? ($('rm-max').value === '' ? null : num($('rm-max').value)) : undefined,
    min: isCount ? Math.max(0, parseInt($('rm-min').value, 10) || 0) : undefined,
    max: isCount ? ($('rm-max').value === '' ? null : Math.max(0, parseInt($('rm-max').value, 10) || 0)) : undefined,
    mode,
    weight: mode === 'soft' ? Math.max(1, parseInt($('rm-weight').value, 10) || 20) : undefined,
  };
}

function updateRulePreview() {
  try {
    const r = ruleFromModal();
    const c = compileRules([r], store.state.cellSize)[0];
    let warn = '';
    // 내림 환산이 0셀이 되면 '접촉 요구'로 변질 — 경고
    if ((r.kind === 'distanceTo' && r.maxM != null && c.max === 0)
      || (['adjacentCount', 'directionOf'].includes(r.kind) && r.gapM != null && c.gap === 0)) {
      warn = ' <span class="badge-no">⚠ 셀 크기보다 작은 거리 — 접촉(0셀) 요구로 처리됨</span>';
    }
    $('rm-preview').innerHTML = '미리보기: ' + ruleToText(r) + warn;
  } catch { $('rm-preview').textContent = ''; }
}

function closeRuleModal() { $('ruleModal').hidden = true; editingRuleId = null; }

$('addRule').onclick = () => openRuleModal();
$('rm-close').onclick = closeRuleModal;
$('rm-cancel').onclick = closeRuleModal;
$('ruleModal').addEventListener('mousedown', (e) => { if (e.target === $('ruleModal')) closeRuleModal(); });
window.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('ruleModal').hidden) closeRuleModal(); });
$('rm-kind').addEventListener('change', syncModalRows);
$('rm-mode').addEventListener('change', syncModalRows);
['rm-type', 'rm-target', 'rm-target2', 'rm-anchor', 'rm-side', 'rm-basis',
  'rm-gap', 'rm-min', 'rm-max', 'rm-dir', 'rm-axis', 'rm-weight']
  .forEach((id) => $(id).addEventListener('input', updateRulePreview));

$('rm-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const s = store.state;
  const rule = ruleFromModal();
  if (rule.kind === 'distanceTo' && rule.maxM != null && (rule.minM || 0) > rule.maxM) {
    return flashHint('최소값이 최대값보다 큽니다.');
  }
  if (rule.kind === 'adjacentCount' && rule.max != null && (rule.min || 0) > rule.max) {
    return flashHint('최소 개수가 최대 개수보다 큽니다.');
  }
  pushUndo();
  if (editingRuleId) {
    const i = s.rules.findIndex((x) => x.id === editingRuleId);
    if (i >= 0) s.rules[i] = rule; else s.rules.push(rule);
  } else {
    s.rules.push(rule);
  }
  closeRuleModal();
  refreshPlacementContext();
  renderRules(); runFeasibility(); store.emit();
});

// ----- 배치 순서 -----
function renderSeq() {
  const s = store.state;
  const el = $('seqList'); el.innerHTML = '';
  s.sequence.forEach((id, i) => {
    const t = typeById(s, id);
    const div = document.createElement('div');
    div.className = 'item';
    div.innerHTML = `<span class="grow">${i + 1}. ${t?.name || '?'}</span>
      <button class="mini" data-up>▲</button><button class="mini" data-down>▼</button>
      <span class="x" data-del>✕</span>`;
    div.querySelector('[data-up]').onclick = () => { if (i > 0) { [s.sequence[i - 1], s.sequence[i]] = [s.sequence[i], s.sequence[i - 1]]; renderSeq(); store.emit(); } };
    div.querySelector('[data-down]').onclick = () => { if (i < s.sequence.length - 1) { [s.sequence[i + 1], s.sequence[i]] = [s.sequence[i], s.sequence[i + 1]]; renderSeq(); store.emit(); } };
    div.querySelector('[data-del]').onclick = () => { s.sequence.splice(i, 1); renderSeq(); runFeasibility(); store.emit(); };
    el.appendChild(div);
  });
  if (!s.sequence.length) el.innerHTML = '<div class="muted">건물 타입의 「순서+」로 추가하세요.</div>';
}

function renderFeas() {
  const el = $('feasList');
  if (feasResult[0] === '__heavy__') {
    el.className = 'list muted';
    el.innerHTML = '대형 격자 — 자동 검증이 비활성화되어 있습니다. <button class="mini primary" id="feasRun">지금 검증 실행</button>';
    const btn = document.getElementById('feasRun');
    if (btn) btn.onclick = () => { runFeasibility(true); };
    return;
  }
  if (!feasResult.length) { el.innerHTML = '건물을 배치하면 남은 건물들의 배치 가능 여부가 표시됩니다.'; el.className = 'list muted'; return; }
  el.className = 'list';
  el.innerHTML = feasResult.map((f) => {
    const t = typeById(store.state, f.typeId);
    return `<div class="item"><span class="grow">${t?.name || '?'}</span>
      <span class="${f.ok ? 'badge-ok' : 'badge-no'}">${f.ok ? '배치 가능 ✓' : '배치 불가 ✗'}</span></div>`;
  }).join('');
}

let hintTimer = null;
function flashHint(msg) {
  const el = $('hint'); el.innerHTML = msg; el.style.display = 'block';
  clearTimeout(hintTimer); hintTimer = setTimeout(() => { el.style.display = 'none'; }, 3500);
}

// ---------- 탭 ----------
document.querySelectorAll('#tabs .tab').forEach((b) =>
  b.addEventListener('click', () => {
    document.querySelectorAll('#tabs .tab').forEach((x) => x.classList.toggle('active', x === b));
    document.querySelectorAll('.pane').forEach((p) => { p.hidden = p.dataset.pane !== b.dataset.tab; });
  }));

// ---------- 시작 ----------
renderPanels();
resize();

// 이전 세션 자동 복원 (localStorage)
let restoredLocal = false;
try {
  const saved = localStorage.getItem(SAVE_KEY);
  if (saved) { restore(saved); restoredLocal = true; flashHint('이전 작업을 복원했습니다.'); }
} catch { /* 접근 불가 시 무시 */ }

// Claude(MCP) 라이브 브리지 접속 시작 — 여러 탭 중 리더 1개만 접속 (MCP 미기동 시 조용히 재시도)
startBridge();

// 디버그/테스트 훅
window.__app = {
  store, rebuildGrid, regenRoads, runFeasibility, renderPanels, redraw,
  refreshPlacementContext, // 규칙을 s.rules에 직접 주입하는 테스트는 이걸 호출해야 컴파일 반영됨
  activeAlt: () => activeAlt(store.state), uid, serialize, restore,
  bridgeState: () => ({ connected: bridgeConnected }),
};
