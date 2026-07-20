// engine.js — 배치 규칙 평가 · 자동/수동 배치 · 최적위치 추천 · 배치가능성 검증 · 도로 자동생성
import {
  isBuildable, fits, buildOccupancy, maskOf, placementCovers, placementArea, rotateMembers,
} from './grid.js';

/** 시드 기반 RNG (mulberry32) — 대안별 재현 가능한 무작위 */
export function rng(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 두 셀 사각형 사이 이격(체비셰프, 셀 단위). 0 = 맞닿음/겹침 */
export function rectGap(a, b) {
  const ax2 = a.c + a.w, ay2 = a.r + a.h, bx2 = b.c + b.w, by2 = b.r + b.h;
  const gapX = Math.max(a.c - bx2, b.c - ax2, 0);
  const gapY = Math.max(a.r - by2, b.r - ay2, 0);
  return Math.max(gapX, gapY);
}

/** 배치의 실체 rect 목록: 블록이면 멤버 절대좌표 rect들, 아니면 자기 자신 */
function memberRects(p) {
  if (!p.members || !p.members.length) return [p];
  return p.members.map((m) => ({ typeId: m.typeId, c: p.c + m.dc, r: p.r + m.dr, w: m.w, h: m.h }));
}

/**
 * 배치 간 이격: 블록은 bbox가 아닌 멤버 rect 쌍의 최소 거리 (PLAN.md D1).
 * rectGap과 혼용 금지 — 규칙/점수 평가는 반드시 이 함수를 쓴다.
 */
export function placementGap(a, b) {
  if (!a.members && !b.members) return rectGap(a, b);
  let min = Infinity;
  for (const ra of memberRects(a))
    for (const rb of memberRects(b)) {
      const g = rectGap(ra, rb);
      if (g < min) min = g;
    }
  return min;
}

/**
 * targetType 대상 확장 (PLAN.md D2): 해당 타입의 단독 배치 + 블록 내부 동일 타입 멤버(가상 rect).
 * "Chemical shelter는 HRSG 가까이"가 Power block 안의 HRSG를 자동 타깃하게 하는 핵심.
 */
export function expandTargets(placements, targetType) {
  const out = [];
  for (const p of placements) {
    if (p.typeId === targetType) out.push(p);
    if (p.members)
      for (const m of p.members)
        if (m.typeId === targetType)
          out.push({ typeId: targetType, c: p.c + m.dc, r: p.r + m.dr, w: m.w, h: m.h });
  }
  return out;
}

/**
 * 일반화 거리장: isSource(c,r)=true인 이웃(비buildable 위치 포함)에 접한 buildable 셀=1,
 * 이후 buildable 셀 위 BFS. computeEdgeDist·도로/경계 개별 거리장의 공용 코어.
 */
export function computeDistFieldNear(grid, isSource) {
  const { cols, rows } = grid;
  const dist = new Int32Array(cols * rows).fill(-1);
  const q = [];
  const N = [[-1, 0], [1, 0], [0, -1], [0, 1]];
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (!isBuildable(grid, c, r)) continue;
      let touches = false;
      for (const [dc, dr] of N) if (isSource(c + dc, r + dr)) { touches = true; break; }
      if (touches) { dist[r * cols + c] = 1; q.push(r * cols + c); }
    }
  }
  for (let head = 0; head < q.length; head++) {
    const idx = q[head], c = idx % cols, r = (idx / cols) | 0;
    for (const [dc, dr] of N) {
      const cc = c + dc, rr = r + dr;
      if (!isBuildable(grid, cc, rr)) continue;
      const ni = rr * cols + cc;
      if (dist[ni] === -1) { dist[ni] = dist[idx] + 1; q.push(ni); }
    }
  }
  return dist;
}

/** 각 대지 셀 → 대지경계까지 거리(셀). 경계 접한 셀 = 1. 도로 근접의 프록시. */
export function computeEdgeDist(grid) {
  return computeDistFieldNear(grid, (c, r) => !isBuildable(grid, c, r));
}

/**
 * 규칙 컨텍스트 (placeGrid.ctx로 부착 — 시그니처 무변경 전파, PLAN.md D5/D12).
 * fields.fence: 원본 대지 경계 기준 거리장 (도로 마스킹 무시 — 도로 셀이 경계로 오염되지 않음)
 * fields.road : 도로망 셀 기준 거리장 (도로 없으면 null)
 * centroid    : buildable 질량중심 (centerOf/풍향의 기준점, Phase 3 소비)
 */
export function buildRuleContext(rawGrid, placeGrid, roadCells, opts = {}) {
  const fields = { fence: computeEdgeDist(rawGrid), road: null };
  if (roadCells && roadCells.length) {
    const roadSet = new Set(roadCells);
    const { cols, rows } = placeGrid;
    fields.road = computeDistFieldNear(placeGrid, (c, r) =>
      c >= 0 && r >= 0 && c < cols && r < rows && roadSet.has(r * cols + c));
  }
  let sc = 0, sr = 0, n = 0;
  for (let r = 0; r < rawGrid.rows; r++)
    for (let c = 0; c < rawGrid.cols; c++)
      if (rawGrid.buildable[r * rawGrid.cols + c]) { sc += c; sr += r; n++; }
  const centroid = n ? { c: sc / n, r: sr / n } : { c: rawGrid.cols / 2, r: rawGrid.rows / 2 };

  // 풍향 (D6): windDir = 바람이 불어오는 방위각(도, 0=N, 시계방향). 다운윈드 단위벡터
  // (셀좌표: r은 화면 아래로 증가 = 남쪽). uc=-sinθ, ur=cosθ (예: 북풍 0° → (0,1)=남쪽으로 붊)
  let wind = null;
  if (opts.windDir != null) {
    const th = (opts.windDir * Math.PI) / 180;
    const uc = -Math.sin(th), ur = Math.cos(th);
    let maxAbs = 1e-9;
    for (let r = 0; r < rawGrid.rows; r++)
      for (let c = 0; c < rawGrid.cols; c++) {
        if (!rawGrid.buildable[r * rawGrid.cols + c]) continue;
        const p = (c + 0.5 - centroid.c) * uc + (r + 0.5 - centroid.r) * ur;
        if (Math.abs(p) > maxAbs) maxAbs = Math.abs(p);
      }
    wind = { uc, ur, maxAbs };
  }
  return { fields, centroid, wind, anchors: opts.anchors || [] };
}

/** 후보 중심의 바람축 투영값 (양수 = 다운윈드 쪽). ctx.wind 필요 */
function windProj(ctx, cand) {
  const cx = cand.c + cand.w / 2, cy = cand.r + cand.h / 2;
  return (cx - ctx.centroid.c) * ctx.wind.uc + (cy - ctx.centroid.r) * ctx.wind.ur;
}

/**
 * nearRoad/setback의 basis 분기: 'any'(기본)=기존 edgeDist(경계+마스킹된 도로),
 * 'fence'=경계만, 'road'=도로만. ctx 없으면(레거시/selftest 직접 호출) edgeDist 폴백.
 * 반환 null = 기준 자체가 없음(도로 미존재) — 호출측에서 kind별 의미 결정.
 */
function basisField(grid, edgeDist, rl) {
  const b = rl.basis || 'any';
  if (b === 'any' || !grid.ctx || !grid.ctx.fields) return edgeDist;
  if (b === 'road') return grid.ctx.fields.road; // null 가능
  return grid.ctx.fields.fence || edgeDist;
}

// 규칙 조회 캐시: 핫루프(후보×배치×규칙)에서 매번 filter 배열을 만들지 않도록
// rules 배열 정체성 기준 WeakMap (규칙 변경 = 새 배열 → 자동 무효화)
const rulesForCache = new WeakMap();
function rulesFor(rules, typeId) {
  let byType = rulesForCache.get(rules);
  if (!byType) { byType = new Map(); rulesForCache.set(rules, byType); }
  let arr = byType.get(typeId);
  if (!arr) {
    arr = rules.filter((rl) => rl.buildingTypeId === typeId);
    byType.set(typeId, arr);
  }
  return arr;
}

function minEdgeOfRect(grid, edgeDist, cand) {
  const mask = maskOf(cand); // 블록: 노치 제외 실풋프린트 기준
  let m = Infinity;
  for (let dr = 0; dr < cand.h; dr++)
    for (let dc = 0; dc < cand.w; dc++) {
      if (mask && !mask[dr * cand.w + dc]) continue;
      const v = edgeDist[(cand.r + dr) * grid.cols + (cand.c + dc)];
      if (v >= 0 && v < m) m = v;
    }
  return m === Infinity ? 0 : m;
}

/** 셀이 어떤 배치에도 점유되지 않았는지 (블록 노치는 free) */
function cellFree(placements, cc, rr) {
  return !placements.some((p) => placementCovers(p, cc, rr));
}

/**
 * 방위 개방(openSide): cand의 dir 방향 전면 gap셀이 모두 대지 내부이고 비어있는가.
 * dir: 'N'(위/-r) 'S'(아래/+r) 'E'(오른쪽/+c) 'W'(왼쪽/-c) — 화면 기준.
 */
function openSideOK(grid, placements, cand, dir, gap) {
  for (let k = 0; k < gap; k++) {
    if (dir === 'S' || dir === 'N') {
      const rr = dir === 'S' ? cand.r + cand.h + k : cand.r - 1 - k;
      for (let dc = 0; dc < cand.w; dc++) {
        const cc = cand.c + dc;
        if (!isBuildable(grid, cc, rr) || !cellFree(placements, cc, rr)) return false;
      }
    } else {
      const cc = dir === 'E' ? cand.c + cand.w + k : cand.c - 1 - k;
      for (let dr = 0; dr < cand.h; dr++) {
        const rr = cand.r + dr;
        if (!isBuildable(grid, cc, rr) || !cellFree(placements, cc, rr)) return false;
      }
    }
  }
  return true;
}

/** cand가 target의 dir 방향에 있는가 (수직축 투영이 겹쳐야 함) */
function inDirection(cand, target, dir) {
  const colOverlap = cand.c < target.c + target.w && target.c < cand.c + cand.w;
  const rowOverlap = cand.r < target.r + target.h && target.r < cand.r + cand.h;
  if (dir === 'S') return cand.r >= target.r + target.h && colOverlap;
  if (dir === 'N') return cand.r + cand.h <= target.r && colOverlap;
  if (dir === 'E') return cand.c >= target.c + target.w && rowOverlap;
  if (dir === 'W') return cand.c + cand.w <= target.c && rowOverlap;
  return false;
}

/**
 * 단일 규칙 만족 여부 (mode 무관).
 * opts.final=true: 최종 레이아웃 검증 — 배치 시점엔 판정 불가한 조건(adjacentCount의 min)까지 평가.
 * 구형 kind(gapFrom/adjacentTo)는 마이그레이션 전 저장본 호환용.
 */
function ruleSatisfied(grid, edgeDist, placements, cand, rl, opts = {}) {
  const targets = () => expandTargets(placements, rl.targetType); // 블록 멤버 자동 포함 (D2)
  switch (rl.kind) {
    case 'nearRoad': {
      const f = basisField(grid, edgeDist, rl);
      if (f === null) return false; // 도로 기준인데 도로 없음 → 불만족
      return minEdgeOfRect(grid, f, cand) <= rl.gap;
    }
    case 'setback': {
      const f = basisField(grid, edgeDist, rl);
      if (f === null) return true; // 기준 없음 → 이격 제약 무의미(통과)
      return minEdgeOfRect(grid, f, cand) >= rl.gap + 1;
    }
    case 'openSide': return openSideOK(grid, placements, cand, rl.dir || 'S', Math.max(1, rl.gap));
    case 'distanceTo': {
      const ts = targets();
      const minOk = ts.every((p) => placementGap(cand, p) >= (rl.min || 0));
      if (rl.max == null) return minOk;
      return minOk && ts.length > 0 && ts.some((p) => placementGap(cand, p) <= rl.max);
    }
    case 'adjacentCount': {
      const cnt = targets().filter((p) => placementGap(cand, p) <= rl.gap).length;
      if (rl.max != null && cnt > rl.max) return false;
      if (opts.final && cnt < (rl.min || 0)) return false;
      return true;
    }
    case 'directionOf': {
      const ts = targets();
      if (!ts.length) return false;
      return ts.some((p) => inDirection(cand, p, rl.dir || 'S') && placementGap(cand, p) <= (rl.gap ?? 3));
    }
    case 'sameRowCol': {
      const ts = targets();
      if (!ts.length) return false;
      return ts.some((p) => (rl.axis === 'col' ? p.c === cand.c : p.r === cand.r));
    }
    // ---- Phase 3 특수 규칙 (ctx 없거나 전제 미충족 시 '판정 유보'=통과, final에선 엄격) ----
    case 'windSide': {
      const ctx = grid.ctx;
      if (!ctx || !ctx.wind) return true; // 풍향 미설정 → 비활성
      const proj = windProj(ctx, cand);
      const slack = rl.gap || 0;
      return rl.side === 'up' ? proj <= slack : proj >= -slack;
    }
    case 'centerOf': {
      const ctx = grid.ctx;
      if (!ctx) return true;
      const d = Math.max(Math.abs(cand.c + cand.w / 2 - ctx.centroid.c),
        Math.abs(cand.r + cand.h / 2 - ctx.centroid.r));
      return d <= (rl.gap || 0) + 0.5; // 중심 셀 반칸 여유
    }
    case 'between': {
      // cand가 target1·target2 최근접 개체 중점의 gap셀 반경 안 (D7)
      const near = (tt) => {
        let best = null, bd = Infinity;
        for (const p of expandTargets(placements, tt)) {
          const d = placementGap(cand, p);
          if (d < bd) { bd = d; best = p; }
        }
        return best;
      };
      const t1 = near(rl.targetType), t2 = near(rl.targetType2);
      if (!t1 || !t2) return !opts.final; // 대상 미배치: 배치 시점 유보, 최종 검증에선 위반
      const mx = (t1.c + t1.w / 2 + t2.c + t2.w / 2) / 2;
      const my = (t1.r + t1.h / 2 + t2.r + t2.h / 2) / 2;
      const d = Math.max(Math.abs(cand.c + cand.w / 2 - mx), Math.abs(cand.r + cand.h / 2 - my));
      return d <= (rl.gap || 0) + 0.5;
    }
    case 'distanceToAnchor': {
      const ctx = grid.ctx;
      const a = ctx && ctx.anchors ? ctx.anchors.find((x) => x.id === rl.anchorId) : null;
      if (!a) return true; // 앵커 미지정/삭제 → 비활성 (규칙 목록에 표시)
      const rect = { c: a.c, r: a.r, w: 1, h: 1 };
      const d = placementGap(cand, rect);
      if (d < (rl.min || 0)) return false;
      if (rl.max != null && d > rl.max) return false;
      return true;
    }
    // ---- 구형 kind (저장본 호환) ----
    case 'gapFrom':
      return targets().every((p) => placementGap(cand, p) >= rl.gap);
    case 'adjacentTo':
      return targets().some((p) => placementGap(cand, p) <= rl.gap);
    default: return true; // insideOnly 등: fits가 보장
  }
}

/**
 * 전역 클리어런스(D11): 규칙과 별개의 매트릭스 제약 — "도로↔장비 3m" 한 줄이 전 타입 커버.
 * ctx.clear = { cells(a,b)→최소 이격 셀수, catOf(typeId)→카테고리, kindFields:{kind:거리장} }
 */
function clearanceOK(grid, placements, cand) {
  const ctx = grid.ctx;
  if (!ctx || !ctx.clear) return true;
  const cc = ctx.clear;
  const catC = cc.catOf(cand.typeId);
  // (a) 후보 ↔ 선형 kind: 거리장 값 1=인접(빈 셀 0) → 빈 셀 = d-1 ≥ need 필요
  for (const kind in cc.kindFields) {
    const need = cc.cells(catC, kind);
    if (need <= 0) continue;
    const f = cc.kindFields[kind];
    if (!f) continue;
    const d = minEdgeOfRect(grid, f, cand);
    if (d > 0 && d - 1 < need) return false;
  }
  // (b) 후보 ↔ 기존 배치 (대칭 매트릭스라 역방향도 이 검사로 커버 — 이동은 layoutHardOK가 재평가)
  for (const p of placements) {
    const need = cc.cells(catC, cc.catOf(p.typeId));
    if (need > 0 && placementGap(cand, p) < need) return false;
  }
  return true;
}

/** 후보 배치가 모든 hard 규칙 + 전역 클리어런스를 만족하는가 (fits는 호출 전 통과 가정) */
export function evaluateHard(grid, edgeDist, placements, cand, rules, opts = {}) {
  for (const rl of rulesFor(rules, cand.typeId)) {
    if (rl.mode !== 'hard') continue;
    if (!ruleSatisfied(grid, edgeDist, placements, cand, rl, opts)) return false;
  }
  return clearanceOK(grid, placements, cand);
}

/**
 * cand 추가가 기존 배치들의 hard 규칙을 깨뜨리는가.
 * 추가로 깨질 수 있는 규칙만 검사: gapFrom(cand 타입이 target), openSide(전면 침범).
 */
export function addWouldViolate(grid, edgeDist, placements, cand, rules) {
  for (const p of placements) {
    for (const rl of rulesFor(rules, p.typeId)) {
      if (rl.mode !== 'hard') continue;
      // cand측 멤버 확장 (PLAN.md P2 최상위 리스크): cand가 블록이면 내부 멤버 타입도
      // 기존 배치의 target 매칭 대상 — "GT 멤버 포함 블록"이 Admin의 이격 hard를 뚫지 못하게.
      const candAsTargets = () => expandTargets([cand], rl.targetType);
      if (rl.kind === 'gapFrom') {
        for (const tr of candAsTargets())
          if (placementGap(p, tr) < rl.gap) return true;
      } else if (rl.kind === 'distanceTo' && (rl.min || 0) > 0) {
        for (const tr of candAsTargets())
          if (placementGap(p, tr) < rl.min) return true;
      } else if (rl.kind === 'adjacentCount' && rl.max != null) {
        const added = candAsTargets().filter((tr) => placementGap(p, tr) <= rl.gap).length;
        if (added > 0) {
          const existing = expandTargets(placements.filter((x) => x !== p), rl.targetType)
            .filter((tr) => placementGap(p, tr) <= rl.gap).length;
          if (existing + added > rl.max) return true;
        }
      } else if (rl.kind === 'openSide') {
        // p의 개방 구역에 cand(블록이면 실풋프린트)가 들어오는지 — cellFree가 placementCovers 사용
        if (!openSideOK(grid, [cand], p, rl.dir || 'S', Math.max(1, rl.gap))) return true;
      }
    }
  }
  return false;
}

/** 전체 레이아웃이 모든 hard 규칙을 만족하는가 (이동/재편 후 최종 검증용) */
export function layoutHardOK(grid, edgeDist, placements, rules) {
  for (let i = 0; i < placements.length; i++) {
    const others = placements.filter((_, j) => j !== i);
    if (!evaluateHard(grid, edgeDist, others, placements[i], rules)) return false;
  }
  return true;
}

/** 건폐율 상한 검사: 현재 배치 + extraCells 추가 시 상한(%) 이하인가 */
export function coverageOK(grid, placements, extraCells, maxCoverage) {
  if (maxCoverage == null) return true;
  let buildable = 0;
  for (let i = 0; i < grid.buildable.length; i++) buildable += grid.buildable[i];
  if (!buildable) return true;
  const occ = placements.reduce((n, p) => n + placementArea(p), 0) + extraCells; // 블록=실풋프린트
  return (occ / buildable) * 100 <= maxCoverage + 1e-9;
}

/** 후보 점수 (높을수록 좋음). soft 규칙 만족 + 접근성/집약도 휴리스틱 */
export function scoreCandidate(grid, edgeDist, placements, cand, rules) {
  let score = 0;
  for (const rl of rulesFor(rules, cand.typeId)) {
    if (rl.mode !== 'soft') continue;
    let v; // 0~1 만족도 — windSide/centerOf는 비례(graded), 나머지는 이진
    if (rl.kind === 'windSide' && grid.ctx && grid.ctx.wind) {
      const sign = rl.side === 'up' ? -1 : 1;
      const p = (sign * windProj(grid.ctx, cand)) / grid.ctx.wind.maxAbs;
      v = Math.min(1, Math.max(0, (p + 1) / 2)); // 극단(가장 외곽)일수록 1 — Flare 요구 표현
    } else if (rl.kind === 'centerOf' && grid.ctx) {
      const d = Math.max(Math.abs(cand.c + cand.w / 2 - grid.ctx.centroid.c),
        Math.abs(cand.r + cand.h / 2 - grid.ctx.centroid.r));
      v = 1 / (1 + d / Math.max(1, rl.gap || 1));
    } else {
      v = ruleSatisfied(grid, edgeDist, placements, cand, rl, { final: true }) ? 1 : 0;
    }
    score += (rl.weight ?? 20) * v;
  }
  // 접근성: 경계에 가까울수록 소폭 가점
  score += 5 / (1 + minEdgeOfRect(grid, edgeDist, cand));
  // 집약도: 가장 가까운 기존 건물과 가까울수록 가점 (빈 공간 분산 방지)
  if (placements.length) {
    let near = Infinity;
    for (const p of placements) near = Math.min(near, placementGap(cand, p));
    score += 8 / (1 + near);
  }
  return score;
}

/** placingType 배치 시 모든 셀의 유효성 맵 + 최적셀. 수동배치 하이라이트/추천용. members=블록 멤버 */
export function candidateMap(grid, edgeDist, placements, typeId, w, h, rules, members = null) {
  const occ = buildOccupancy(grid, placements);
  const valid = new Uint8Array(grid.cols * grid.rows);
  const proto = { typeId, w, h, members }; // maskOf WeakMap 캐시 활용을 위한 고정 객체
  const mask = maskOf(proto);
  let best = null, bestScore = -Infinity;
  for (let r = 0; r <= grid.rows - h; r++) {
    for (let c = 0; c <= grid.cols - w; c++) {
      const cand = { typeId, c, r, w, h, members };
      if (!fits(grid, occ, c, r, w, h, mask)) continue;
      if (!evaluateHard(grid, edgeDist, placements, cand, rules)) continue;
      if (addWouldViolate(grid, edgeDist, placements, cand, rules)) continue;
      valid[r * grid.cols + c] = 1;
      const s = scoreCandidate(grid, edgeDist, placements, cand, rules);
      if (s > bestScore) { bestScore = s; best = { c, r }; }
    }
  }
  return { valid, best };
}

/** 타입의 배치 변형 목록: 유닛=1개, 블록=회전 0~3 (D13. members는 회전 적용 후 좌표) */
export function typeVariants(t) {
  if (t.kind !== 'block' || !t.members || !t.members.length) {
    return [{ w: t.w, h: t.h, members: t.members || null, rot: 0 }];
  }
  const vs = [];
  let w = t.w, h = t.h, mem = t.members;
  for (let rot = 0; rot < 4; rot++) {
    vs.push({ w, h, members: mem, rot });
    mem = rotateMembers(mem, w, h);
    const tmp = w; w = h; h = tmp;
  }
  return vs;
}

/** 전체 배치 점수: 각 배치를 나머지에 대해 평가한 합 */
export function totalScore(grid, edgeDist, placements, rules) {
  let s = 0;
  for (let i = 0; i < placements.length; i++) {
    const others = placements.filter((_, j) => j !== i);
    s += scoreCandidate(grid, edgeDist, others, placements[i], rules);
  }
  return s;
}

/**
 * 로컬 개선 패스: 무작위 건물을 골라 최적 위치로 이전, 전체 점수가 오르면 채택.
 * 그리디 결과의 국소 최적 탈출용.
 */
/**
 * 이전(relocation) 후보 탐색이 무거우면 전수 스캔 대신 무작위 샘플링.
 * 기준은 연산량 예산(격자셀수 × 풋프린트): 소형 격자(수백 셀)는 항상 전수(기존 동작 유지),
 * 대형 격자(cellSize 2m급 수만 셀)는 샘플링. 성능 게이트(60×45 블록 전수 393ms/회) 완화책.
 */
const SAMPLE_OPS_BUDGET = 1.5e6;
const SAMPLE_TRIES = 40;
// 전수 스캔 비용 추정: 셀 수 × (풋프린트 + 규칙 평가가 기존 배치 수에 비례하는 항)
// — 규칙 평가(distanceTo/between/addWouldViolate)가 배치당 반복되므로 배치 수를 반영해야
//   대형 격자 + 다수 배치에서 개선/어닐링 패스가 수십 초로 폭발하지 않는다.
const scanCost = (grid, p, nOthers = 0) =>
  grid.cols * grid.rows * (p.w * p.h + 1 + 4 * nOthers);

/** p를 옮길 후보 1개 탐색: 저비용=전수 최적(best), 고비용=샘플 중 최고점 */
function relocationCandidate(grid, edgeDist, others, p, rules, rand) {
  if (scanCost(grid, p, others.length) <= SAMPLE_OPS_BUDGET) {
    const cm = candidateMap(grid, edgeDist, others, p.typeId, p.w, p.h, rules, p.members || null);
    return cm.best;
  }
  const occ = buildOccupancy(grid, others);
  const mask = maskOf(p);
  let best = null, bestScore = -Infinity;
  for (let t = 0; t < SAMPLE_TRIES; t++) {
    const c = Math.floor(rand() * (grid.cols - p.w + 1));
    const r = Math.floor(rand() * (grid.rows - p.h + 1));
    const cand = { typeId: p.typeId, c, r, w: p.w, h: p.h, members: p.members || null };
    if (!fits(grid, occ, c, r, p.w, p.h, mask)) continue;
    if (!evaluateHard(grid, edgeDist, others, cand, rules)) continue;
    if (addWouldViolate(grid, edgeDist, others, cand, rules)) continue;
    const s = scoreCandidate(grid, edgeDist, others, cand, rules);
    if (s > bestScore) { bestScore = s; best = { c, r }; }
  }
  return best;
}

export function improvePlacements(grid, edgeDist, rules, placements, iters = 80, seed = 7) {
  const rand = rng(seed);
  let cur = placements.map((p) => ({ ...p }));
  let curScore = totalScore(grid, edgeDist, cur, rules);
  for (let k = 0; k < iters && cur.length; k++) {
    const i = Math.floor(rand() * cur.length);
    const p = cur[i];
    const others = cur.filter((_, j) => j !== i);
    const best = relocationCandidate(grid, edgeDist, others, p, rules, rand);
    if (!best) continue;
    if (best.c === p.c && best.r === p.r) continue;
    const trial = [...others, { ...p, c: best.c, r: best.r }];
    // 이전(제거+추가)은 남은 건물들의 adjacentTo 등도 깨질 수 있어 전체 검증
    if (!layoutHardOK(grid, edgeDist, trial, rules)) continue;
    const ts = totalScore(grid, edgeDist, trial, rules);
    if (ts > curScore + 1e-9) { cur = trial; curScore = ts; }
  }
  return cur;
}

/**
 * 시뮬레이티드 어닐링: 무작위 건물을 무작위 유효 위치로 이전.
 * 점수가 오르면 항상, 내리면 온도 기반 확률로 수락 → 국소 최적 탈출.
 * hard 규칙은 candidateMap(유효셀) + layoutHardOK로 항상 유지.
 */
export function annealPlacements(grid, edgeDist, rules, placements, opts = {}) {
  const { iters = 300, T0 = 8, cooling = 0.99, seed = 11 } = opts;
  const rand = rng(seed);
  let cur = placements.map((p) => ({ ...p }));
  let curScore = totalScore(grid, edgeDist, cur, rules);
  let best = cur, bestScore = curScore;
  let T = T0;
  for (let k = 0; k < iters && cur.length; k++, T *= cooling) {
    const i = Math.floor(rand() * cur.length);
    const p = cur[i];
    const others = cur.filter((_, j) => j !== i);
    let nc = -1, nr = -1;
    if (scanCost(grid, p, others.length) <= SAMPLE_OPS_BUDGET) {
      const cm = candidateMap(grid, edgeDist, others, p.typeId, p.w, p.h, rules, p.members || null);
      const cells = [];
      for (let idx = 0; idx < cm.valid.length; idx++) if (cm.valid[idx]) cells.push(idx);
      if (!cells.length) continue;
      const idx = cells[Math.floor(rand() * cells.length)];
      nc = idx % grid.cols; nr = (idx / grid.cols) | 0;
    } else {
      // 대형 풋프린트: 무작위 유효 위치 샘플링 (전수 스캔 회피 — 성능 게이트 완화책)
      const occ = buildOccupancy(grid, others);
      const mask = maskOf(p);
      for (let t = 0; t < SAMPLE_TRIES && nc === -1; t++) {
        const c = Math.floor(rand() * (grid.cols - p.w + 1));
        const r = Math.floor(rand() * (grid.rows - p.h + 1));
        const cand2 = { typeId: p.typeId, c, r, w: p.w, h: p.h, members: p.members || null };
        if (!fits(grid, occ, c, r, p.w, p.h, mask)) continue;
        if (!evaluateHard(grid, edgeDist, others, cand2, rules)) continue;
        if (addWouldViolate(grid, edgeDist, others, cand2, rules)) continue;
        nc = c; nr = r;
      }
      if (nc === -1) continue;
    }
    if (nc === p.c && nr === p.r) continue;
    const trial = [...others, { ...p, c: nc, r: nr }];
    if (!layoutHardOK(grid, edgeDist, trial, rules)) continue;
    const ts = totalScore(grid, edgeDist, trial, rules);
    const d = ts - curScore;
    if (d > 0 || rand() < Math.exp(d / Math.max(T, 1e-6))) {
      cur = trial; curScore = ts;
      if (ts > bestScore) { best = cur; bestScore = ts; }
    }
  }
  return best;
}

/**
 * 자동 배치: sequence 순서로 그리디(top-K 무작위) → 미배치 발생 시
 * 개선 패스 후 재시도 → 어닐링(전역 탐색) → 미배치 재시도 → 언덕오르기 마무리.
 */
export function autoPlace(grid, edgeDist, types, rules, sequence, seed = 1, opts = {}) {
  const rand = rng(seed);
  const byId = (id) => types.find((t) => t.id === id);

  const tryPlace = (placements, typeId) => {
    const t = byId(typeId);
    if (!t) return null;
    if (!coverageOK(grid, placements, placementArea(t), opts.maxCoverage)) return null;
    const occ = buildOccupancy(grid, placements);
    const cands = [];
    for (const v of typeVariants(t)) { // 블록: 회전 4변형 후보 포함
      const mask = maskOf({ w: v.w, h: v.h, members: v.members });
      // 대형 격자: 후보를 결정적 스트라이드로 희소화 (개선·어닐링 패스가 위치를 다듬음)
      const step = Math.max(1, Math.round(Math.sqrt(
        scanCost(grid, { w: v.w, h: v.h }, placements.length) / SAMPLE_OPS_BUDGET)));
      for (let r = 0; r <= grid.rows - v.h; r += step)
        for (let c = 0; c <= grid.cols - v.w; c += step) {
          const cand = { typeId, c, r, w: v.w, h: v.h, members: v.members };
          if (!fits(grid, occ, c, r, v.w, v.h, mask)) continue;
          if (!evaluateHard(grid, edgeDist, placements, cand, rules)) continue;
          if (addWouldViolate(grid, edgeDist, placements, cand, rules)) continue;
          cands.push({ v, c, r, score: scoreCandidate(grid, edgeDist, placements, cand, rules) });
        }
    }
    if (!cands.length) return null;
    cands.sort((a, b) => b.score - a.score);
    const K = Math.min(cands.length, 5);
    const pick = cands[Math.floor(rand() * K)];
    const placed = { typeId, c: pick.c, r: pick.r, w: pick.v.w, h: pick.v.h, rot: pick.v.rot };
    if (pick.v.members) placed.members = pick.v.members.map((m) => ({ ...m })); // 스냅샷
    return placed;
  };

  let placements = [];
  let unplaced = [];
  for (const typeId of sequence) {
    let p = tryPlace(placements, typeId);
    if (!p) {
      // 재시도: 기존 배치를 재편(집약)해 공간을 만들고 다시 시도
      placements = improvePlacements(grid, edgeDist, rules, placements, 60, seed + 13);
      p = tryPlace(placements, typeId);
    }
    if (p) placements.push(p);
    else unplaced.push(typeId);
  }
  // 어닐링: 전역 재배열로 점수 개선 + 공간 정리 (대형 격자는 opts.annealIters로 축소 가능)
  placements = annealPlacements(grid, edgeDist, rules, placements,
    { seed: seed + 17, iters: opts.annealIters ?? 300 });
  // 어닐링으로 공간이 정리됐으면 미배치 건물 재시도
  if (unplaced.length) {
    const still = [];
    for (const typeId of unplaced) {
      const p = tryPlace(placements, typeId);
      if (p) placements.push(p); else still.push(typeId);
    }
    unplaced = still;
  }
  // 언덕오르기 마무리(어닐링의 확률적 하강 잔재 제거)
  placements = improvePlacements(grid, edgeDist, rules, placements, 120, seed + 29);
  return { placements, unplaced };
}

/** 대안 지표: 배치수, 충전율, 규칙만족도(soft 포함 점수), hard 위반 수 */
export function layoutMetrics(grid, edgeDist, placements, rules, sequence) {
  let buildableCells = 0;
  for (let i = 0; i < grid.buildable.length; i++) buildableCells += grid.buildable[i];
  const occCells = placements.reduce((n, p) => n + placementArea(p), 0);
  let hardViolations = 0;
  for (let i = 0; i < placements.length; i++) {
    const others = placements.filter((_, j) => j !== i);
    // 최종 검증: adjacentCount의 min 등 배치 시점엔 못 보는 조건까지 평가
    if (!evaluateHard(grid, edgeDist, others, placements[i], rules, { final: true })) hardViolations++;
  }
  return {
    placed: placements.length,
    target: sequence.length,
    fillRate: buildableCells ? occCells / buildableCells : 0,
    score: Math.round(totalScore(grid, edgeDist, placements, rules)),
    hardViolations,
  };
}

/**
 * 배치가능성 검증(순차 시뮬레이션): 현재 placements에서 시작해 남은 건물을
 * 순서대로 그리디(최고점) 배치해 보고 각 건물의 성공 여부를 반환.
 * 앞 건물의 가상 배치가 뒤 건물 검사에 반영되므로 "순서대로 모두 들어가는가"를 근사 보장.
 */
export function feasibility(grid, edgeDist, types, rules, remainingSeq, placements, opts = {}) {
  const byId = (id) => types.find((t) => t.id === id);
  const sim = placements.map((p) => ({ ...p }));
  const result = [];
  for (const typeId of remainingSeq) {
    const t = byId(typeId);
    if (!t) { result.push({ typeId, ok: false }); continue; }
    if (!coverageOK(grid, sim, placementArea(t), opts.maxCoverage)) { result.push({ typeId, ok: false }); continue; }
    const occ = buildOccupancy(grid, sim);
    let best = null, bestScore = -Infinity;
    for (const v of typeVariants(t)) {
      const mask = maskOf({ w: v.w, h: v.h, members: v.members });
      const step = Math.max(1, Math.round(Math.sqrt(
        scanCost(grid, { w: v.w, h: v.h }, sim.length) / SAMPLE_OPS_BUDGET)));
      for (let r = 0; r <= grid.rows - v.h; r += step)
        for (let c = 0; c <= grid.cols - v.w; c += step) {
          const cand = { typeId, c, r, w: v.w, h: v.h, members: v.members };
          if (!fits(grid, occ, c, r, v.w, v.h, mask)) continue;
          if (!evaluateHard(grid, edgeDist, sim, cand, rules)) continue;
          if (addWouldViolate(grid, edgeDist, sim, cand, rules)) continue;
          const sc = scoreCandidate(grid, edgeDist, sim, cand, rules);
          if (sc > bestScore) { bestScore = sc; best = cand; }
        }
    }
    if (best) { sim.push(best); result.push({ typeId, ok: true }); }
    else result.push({ typeId, ok: false });
  }
  return result;
}

// ---------- Phase 4: 선형 요소(corridors) · 확폭 · 래스터화 · 폐합 검증 ----------

/** 선형 kind 물성 (D9): blocks=true → placeGrid에서 배치 차단. tunnel=지하라 차단 안 함 */
export const CORRIDOR_KINDS = {
  road: { blocks: true, label: '도로' },
  rack: { blocks: true, label: '파이프랙' },
  tunnel: { blocks: false, label: '케이블터널(지하)' },
  conduit: { blocks: true, label: '도관(CW)' },
};

/**
 * 셀 집합을 폭 widthCells로 확폭: 진행축 추정 후 수직 방향(수평→아래, 수직→오른쪽)으로
 * 일관되게 (width-1)줄 추가. buildable 밖은 클리핑.
 */
export function widenNetwork(grid, cells, widthCells) {
  if (widthCells <= 1) return [...cells];
  const set = new Set(cells);
  const { cols } = grid;
  const out = new Set(cells);
  for (const idx of cells) {
    const c = idx % cols, r = (idx / cols) | 0;
    const horiz = set.has(r * cols + (c - 1)) || set.has(r * cols + (c + 1));
    for (let k = 1; k < widthCells; k++) {
      const cc = horiz ? c : c + k, rr = horiz ? r + k : r;
      if (isBuildable(grid, cc, rr)) out.add(rr * cols + cc);
    }
  }
  return [...out];
}

/**
 * 중심선(웨이포인트 셀 목록) → 점유 셀. 세그먼트는 Bresenham(직교/45° 정확, 그 외 계단 근사)
 * 후 widenNetwork 확폭. 수동 선형 그리기의 래스터화 코어.
 */
export function rasterizeCenterline(grid, waypoints, widthCells = 1) {
  const { cols } = grid;
  const line = new Set();
  for (let i = 0; i < waypoints.length; i++) {
    const c1 = waypoints[i] % cols, r1 = (waypoints[i] / cols) | 0;
    if (i === 0) { if (isBuildable(grid, c1, r1)) line.add(waypoints[i]); continue; }
    let x = waypoints[i - 1] % cols, y = (waypoints[i - 1] / cols) | 0;
    const dx = Math.abs(c1 - x), dy = Math.abs(r1 - y);
    const sx = x < c1 ? 1 : -1, sy = y < r1 ? 1 : -1;
    let err = dx - dy;
    for (let guard = 0; guard < 100000; guard++) {
      if (isBuildable(grid, x, y)) line.add(y * cols + x);
      if (x === c1 && y === r1) break;
      const e2 = 2 * err;
      if (e2 > -dy) { err -= dy; x += sx; }
      if (e2 < dx) { err += dx; y += sy; }
    }
  }
  return widenNetwork(grid, [...line], widthCells);
}

/**
 * 자동 라우팅 (P4b): src 셀군 → dst 셀군의 최소 회전 경로 (Dial 버킷 0-1 BFS,
 * 직진 비용 0 / 방향전환 비용 turnPenalty → "최대한 직선" 요구의 근사).
 * passable(c,r)로 통과 가능 셀 판정(건물·타 선형 차단, 도로는 횡단 허용 등 호출측 정책).
 * 반환: { cells(폭 적용), waypoints(방향전환점) } 또는 null(도달 불가).
 */
export function routeCorridor(grid, passable, srcCells, dstCells, opts = {}) {
  const { widthCells = 1, turnPenalty = 1, maxCost = 500 } = opts;
  const { cols, rows } = grid;
  const dst = new Set(dstCells);
  const N = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  const S = cols * rows;
  const cost = new Int32Array(S * 4).fill(-1);
  const prev = new Int32Array(S * 4).fill(-1);
  const buckets = [[]];
  for (const idx of srcCells) {
    const c = idx % cols, r = (idx / cols) | 0;
    if (!passable(c, r)) continue;
    for (let d = 0; d < 4; d++) {
      const st = idx * 4 + d;
      if (cost[st] === -1) { cost[st] = 0; buckets[0].push(st); }
    }
  }
  let found = -1;
  for (let cur = 0; cur < buckets.length && cur <= maxCost && found === -1; cur++) {
    const bucket = buckets[cur];
    if (!bucket) continue;
    for (let bi = 0; bi < bucket.length && found === -1; bi++) {
      const st = bucket[bi];
      if (cost[st] !== cur) continue; // 더 싼 경로로 이미 확정
      const idx = (st / 4) | 0, d = st % 4;
      if (dst.has(idx)) { found = st; break; }
      const c = idx % cols, r = (idx / cols) | 0;
      for (let nd = 0; nd < 4; nd++) {
        const cc = c + N[nd][0], rr = r + N[nd][1];
        if (cc < 0 || rr < 0 || cc >= cols || rr >= rows || !passable(cc, rr)) continue;
        const nst = (rr * cols + cc) * 4 + nd;
        const ncost = cur + (nd === d ? 0 : turnPenalty);
        if (cost[nst] === -1 || ncost < cost[nst]) {
          cost[nst] = ncost;
          prev[nst] = st;
          (buckets[ncost] = buckets[ncost] || []).push(nst);
        }
      }
    }
  }
  if (found === -1) return null;
  // 역추적 → 셀 경로 + 방향전환점(waypoints)
  const pathCells = [];
  const waypoints = [];
  let st = found, lastDir = -1;
  while (st !== -1) {
    const idx = (st / 4) | 0, d = st % 4;
    if (!pathCells.length || pathCells[pathCells.length - 1] !== idx) pathCells.push(idx);
    if (d !== lastDir) { waypoints.push(idx); lastDir = d; }
    st = prev[st];
  }
  pathCells.reverse(); waypoints.reverse();
  // 양 끝점 보장: waypoints = [시작, ...방향전환점..., 끝]
  if (waypoints[0] !== pathCells[0]) waypoints.unshift(pathCells[0]);
  if (waypoints[waypoints.length - 1] !== pathCells[pathCells.length - 1]) {
    waypoints.push(pathCells[pathCells.length - 1]);
  }
  return { cells: widenNetwork(grid, pathCells, widthCells), waypoints };
}

/** 셀 집합의 4-연결 성분 수 — 소방도로 폐합/단절 검증 리포트용 */
export function networkComponents(grid, cells) {
  const set = new Set(cells);
  const { cols } = grid;
  const seen = new Set();
  let comps = 0;
  for (const start of set) {
    if (seen.has(start)) continue;
    comps++;
    const q = [start]; seen.add(start);
    for (let h = 0; h < q.length; h++) {
      const idx = q[h], c = idx % cols, r = (idx / cols) | 0;
      for (const [dc, dr] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
        const ni = (r + dr) * cols + (c + dc);
        if (c + dc < 0 || c + dc >= cols) continue;
        if (set.has(ni) && !seen.has(ni)) { seen.add(ni); q.push(ni); }
      }
    }
  }
  return comps;
}

/** buildable 질량중심에 가장 가까운 경계셀(edgeDist==1) — 기본 진입점 */
export function pickDefaultEntry(grid, edgeDist) {
  const { cols, rows } = grid;
  let sc = 0, sr = 0, n = 0;
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++)
      if (grid.buildable[r * cols + c]) { sc += c; sr += r; n++; }
  if (!n) return null;
  const cc = sc / n, cr = sr / n;
  let best = null, bd = Infinity;
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++) {
      const i = r * cols + c;
      if (edgeDist[i] !== 1) continue;
      const d = (c - cc) ** 2 + (r - cr) ** 2;
      if (d < bd) { bd = d; best = i; }
    }
  return best;
}

/** 빗살형: 메인도로 1개(진입점 통과 또는 최적 라인) + spacing 간격 수직 가지 */
function combNetwork(grid, spacing, entryIdx) {
  const { cols, rows } = grid;
  let horiz, mainLine;
  if (entryIdx != null) {
    const ec = entryIdx % cols, er = (entryIdx / cols) | 0;
    // 진입점이 좌/우 경계에 접했으면 메인도로는 가로(그 행), 상/하 경계면 세로(그 열)
    const leftRight = !isBuildable(grid, ec - 1, er) || !isBuildable(grid, ec + 1, er);
    const topBottom = !isBuildable(grid, ec, er - 1) || !isBuildable(grid, ec, er + 1);
    horiz = leftRight && !topBottom ? true : topBottom && !leftRight ? false : cols >= rows;
    mainLine = horiz ? er : ec;
  } else {
    horiz = cols >= rows;
    const mainLen = horiz ? rows : cols;
    const crossLen = horiz ? cols : rows;
    const idx = (m, x) => (horiz ? m * cols + x : x * cols + m);
    let bestScore = -Infinity;
    const mid = (mainLen - 1) / 2;
    mainLine = 0;
    for (let m = 0; m < mainLen; m++) {
      let cnt = 0;
      for (let x = 0; x < crossLen; x++) if (grid.buildable[idx(m, x)]) cnt++;
      const score = cnt - Math.abs(m - mid) * 0.01;
      if (score > bestScore) { bestScore = score; mainLine = m; }
    }
  }
  const crossLen = horiz ? cols : rows;
  const mainLen = horiz ? rows : cols;
  const idx = (m, x) => (horiz ? m * cols + x : x * cols + m);
  const cells = new Set();
  for (let x = 0; x < crossLen; x++)
    if (grid.buildable[idx(mainLine, x)]) cells.add(idx(mainLine, x));
  for (let x = Math.floor(spacing / 2); x < crossLen; x += spacing) {
    if (!grid.buildable[idx(mainLine, x)]) continue;
    for (let m = 0; m < mainLen; m++)
      if (grid.buildable[idx(m, x)]) cells.add(idx(m, x));
  }
  return cells;
}

/** 격자형: 양방향 spacing 간격 도로. 진입점이 있으면 그 행/열에 라인 정렬 */
function gridNetwork(grid, spacing, entryIdx) {
  const { cols, rows } = grid;
  const offR = entryIdx != null ? ((entryIdx / cols) | 0) % spacing : Math.floor(spacing / 2);
  const offC = entryIdx != null ? (entryIdx % cols) % spacing : Math.floor(spacing / 2);
  const cells = new Set();
  for (let r = offR; r < rows; r += spacing)
    for (let c = 0; c < cols; c++)
      if (grid.buildable[r * cols + c]) cells.add(r * cols + c);
  for (let c = offC; c < cols; c += spacing)
    for (let r = 0; r < rows; r++)
      if (grid.buildable[r * cols + c]) cells.add(r * cols + c);
  return cells;
}

/** 루프형: 경계에서 일정 깊이의 순환도로 + 진입점→루프 연결 스퍼 */
function loopNetwork(grid, spacing, entryIdx, edgeDist, ringDepth = null) {
  const { cols, rows } = grid;
  const ringD = ringDepth ?? Math.max(2, Math.round(spacing / 2));
  const cells = new Set();
  for (let i = 0; i < grid.buildable.length; i++)
    if (grid.buildable[i] && edgeDist[i] === ringD) cells.add(i);
  if (!cells.size) return combNetwork(grid, spacing, entryIdx); // 대지가 얕으면 빗살 폴백
  // 스퍼: 진입점에서 BFS 최단경로로 루프까지 연결
  const start = entryIdx != null ? entryIdx : pickDefaultEntry(grid, edgeDist);
  if (start != null && !cells.has(start)) {
    const prev = new Int32Array(cols * rows).fill(-2); // -2 미방문, -1 시작
    prev[start] = -1;
    const q = [start];
    const N = [[-1, 0], [1, 0], [0, -1], [0, 1]];
    let hit = -1;
    for (let head = 0; head < q.length && hit === -1; head++) {
      const cur = q[head], c = cur % cols, r = (cur / cols) | 0;
      for (const [dc, dr] of N) {
        const cc = c + dc, rr = r + dr;
        if (!isBuildable(grid, cc, rr)) continue;
        const ni = rr * cols + cc;
        if (prev[ni] !== -2) continue;
        prev[ni] = cur;
        if (cells.has(ni)) { hit = ni; break; }
        q.push(ni);
      }
    }
    for (let cur = hit; cur !== -1 && cur !== -2; cur = prev[cur]) cells.add(cur);
  }
  return cells;
}

/**
 * 도로 우선 모드: 패턴별 도로망 생성.
 * pattern: 'comb'(빗살) | 'grid'(격자) | 'loop'(루프)
 * entryIdx: 진입점 셀 인덱스(null=자동). 반환: 도로 셀 인덱스 배열.
 */
export function generateRoadNetwork(grid, spacing = 6, pattern = 'comb', entryIdx = null, opts = {}) {
  let cells;
  if (pattern === 'grid') cells = gridNetwork(grid, spacing, entryIdx);
  else if (pattern === 'loop') cells = loopNetwork(grid, spacing, entryIdx, computeEdgeDist(grid), opts.ringDepth ?? null);
  else cells = combNetwork(grid, spacing, entryIdx);
  const arr = [...cells];
  return (opts.widthCells || 1) > 1 ? widenNetwork(grid, arr, opts.widthCells) : arr;
}

/**
 * 도로 자동생성: 빈 셀 위 다중소스 BFS(대지경계 접한 빈셀=소스)로 거리장 구성 후,
 * 각 건물의 전면(인접 빈셀)에서 경계까지 경사 하강 경로를 도로로 마킹. 경로들의 합집합 = 도로망.
 */
export function generateRoads(grid, placements) {
  const { cols, rows } = grid;
  const occ = buildOccupancy(grid, placements);
  const isFree = (c, r) => isBuildable(grid, c, r) && !occ[r * cols + c];
  const dist = new Int32Array(cols * rows).fill(-1);
  const prev = new Int32Array(cols * rows).fill(-1);
  const q = [];
  const N = [[-1, 0], [1, 0], [0, -1], [0, 1]];
  // 소스: 대지경계(외부와 접함)에 닿은 빈 셀
  for (let r = 0; r < rows; r++)
    for (let c = 0; c < cols; c++) {
      if (!isFree(c, r)) continue;
      const touchesOutside = N.some(([dc, dr]) => !isBuildable(grid, c + dc, r + dr));
      if (touchesOutside) { dist[r * cols + c] = 0; q.push(r * cols + c); }
    }
  for (let head = 0; head < q.length; head++) {
    const idx = q[head], c = idx % cols, r = (idx / cols) | 0;
    for (const [dc, dr] of N) {
      const cc = c + dc, rr = r + dr;
      if (!isFree(cc, rr)) continue;
      const ni = rr * cols + cc;
      if (dist[ni] === -1) { dist[ni] = dist[idx] + 1; prev[ni] = idx; q.push(ni); }
    }
  }
  // 각 건물에서 경계까지 경로 추적, 셀별 사용 횟수 집계 → 2회 이상 = 주도로
  const usage = new Map();
  const N4 = [[-1, 0], [1, 0], [0, -1], [0, 1]];
  for (const p of placements) {
    // 건물 전면(실풋프린트 셀의 4-인접 빈 셀) 중 경계에 가장 가까운(dist 최소) 셀.
    // 블록은 bbox 테두리가 아닌 실제 시설 전면에서 진입로가 시작된다.
    let start = -1, sd = Infinity;
    for (let dr = 0; dr < p.h; dr++)
      for (let dc = 0; dc < p.w; dc++) {
        if (!placementCovers(p, p.c + dc, p.r + dr)) continue;
        for (const [nx, ny] of N4) {
          const cc = p.c + dc + nx, rr = p.r + dr + ny;
          if (!isFree(cc, rr)) continue;
          const d = dist[rr * cols + cc];
          if (d >= 0 && d < sd) { sd = d; start = rr * cols + cc; }
        }
      }
    // 경사 하강으로 경계까지 추적
    let cur = start;
    while (cur !== -1) { usage.set(cur, (usage.get(cur) || 0) + 1); cur = prev[cur]; }
    // ringRoad 플래그(블록 둘레도로): 풋프린트 인접 빈 셀 전체를 도로에 편입 — 대안별 alt.roads 귀속
    if (p.ringRoad) {
      for (let dr = 0; dr < p.h; dr++)
        for (let dc = 0; dc < p.w; dc++) {
          if (!placementCovers(p, p.c + dc, p.r + dr)) continue;
          for (const [nx, ny] of N4) {
            const cc = p.c + dc + nx, rr = p.r + dr + ny;
            if (isFree(cc, rr)) usage.set(rr * cols + cc, (usage.get(rr * cols + cc) || 0) + 1);
          }
        }
    }
  }
  const cellSet = new Set(usage.keys());
  const main = [...usage.keys()].filter((i) => usage.get(i) >= 2);

  // 주도로 확폭: 각 주도로 셀에 인접한 빈 셀 1개를 추가해 폭 2셀 확보.
  // 같은 축의 이웃(진행방향과 수직)을 우선해 일관된 측면으로 넓힘.
  const widened = new Set(main);
  for (const idx of main) {
    const c = idx % cols, r = (idx / cols) | 0;
    // 진행방향 추정: 좌우에 도로가 이어지면 수평 도로 → 상/하로 확폭
    const horiz = cellSet.has(r * cols + (c - 1)) || cellSet.has(r * cols + (c + 1));
    const prefer = horiz
      ? [[0, 1], [0, -1], [1, 0], [-1, 0]]
      : [[1, 0], [-1, 0], [0, 1], [0, -1]];
    for (const [dc, dr] of prefer) {
      const cc = c + dc, rr = r + dr;
      const ni = rr * cols + cc;
      if (!isFree(cc, rr) || cellSet.has(ni)) continue;
      cellSet.add(ni); widened.add(ni);
      break;
    }
  }
  return { cells: [...cellSet], main: [...widened] };
}
