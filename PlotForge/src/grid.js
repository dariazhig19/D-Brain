// grid.js — 대지 폴리곤을 격자(cell) 모델로 변환. 배치 엔진의 근간.
import { pointInPolygon, bbox } from './geometry.js';

/**
 * 대지 폴리곤 → 격자.
 * 각 셀은 셀 중심이 폴리곤 내부이면 buildable=true.
 * @param {Array<{x,y}>} poly  월드좌표 폴리곤
 * @param {number} cellSize    셀 한 변 크기(월드 단위)
 */
export function buildGrid(poly, cellSize) {
  const b = bbox(poly);
  const origin = { x: b.minX, y: b.minY };
  const cols = Math.max(1, Math.ceil(b.w / cellSize));
  const rows = Math.max(1, Math.ceil(b.h / cellSize));
  // buildable[r*cols + c] : 대지 내부 여부
  const buildable = new Uint8Array(cols * rows);
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const cx = origin.x + (c + 0.5) * cellSize;
      const cy = origin.y + (r + 0.5) * cellSize;
      buildable[r * cols + c] = pointInPolygon({ x: cx, y: cy }, poly) ? 1 : 0;
    }
  }
  return { origin, cellSize, cols, rows, buildable };
}

export function inBounds(grid, c, r) {
  return c >= 0 && r >= 0 && c < grid.cols && r < grid.rows;
}

export function isBuildable(grid, c, r) {
  return inBounds(grid, c, r) && grid.buildable[r * grid.cols + c] === 1;
}

/** 셀(c,r) → 월드좌표(셀 좌상단) */
export function cellToWorld(grid, c, r) {
  return { x: grid.origin.x + c * grid.cellSize, y: grid.origin.y + r * grid.cellSize };
}

/** 월드좌표 → 셀 인덱스 (내림) */
export function worldToCell(grid, x, y) {
  return {
    c: Math.floor((x - grid.origin.x) / grid.cellSize),
    r: Math.floor((y - grid.origin.y) / grid.cellSize),
  };
}

// ---------- 블록(비직사각 풋프린트) 지원 — PLAN.md D1 ----------
// members: [{typeId, dc, dr, w, h}] 상대좌표 고정 멤버. 풋프린트 = 멤버 rect 합집합.
// mask는 파생 캐시(WeakMap) — state/JSON에 절대 넣지 않는다.

const maskCache = new WeakMap();

/** 타입/배치의 w*h 풋프린트 마스크(1=점유). members 없으면 null(=꽉 찬 직사각) */
export function maskOf(obj) {
  if (!obj || !obj.members || !obj.members.length) return null;
  let m = maskCache.get(obj);
  if (m) return m;
  m = new Uint8Array(obj.w * obj.h);
  for (const mem of obj.members)
    for (let dr = 0; dr < mem.h; dr++)
      for (let dc = 0; dc < mem.w; dc++) {
        const x = mem.dc + dc, y = mem.dr + dr;
        if (x >= 0 && y >= 0 && x < obj.w && y < obj.h) m[y * obj.w + x] = 1;
      }
  maskCache.set(obj, m);
  return m;
}

/** 배치 p가 셀(c,r)을 실제로 점유하는가 (블록 노치는 false) */
export function placementCovers(p, c, r) {
  if (c < p.c || r < p.r || c >= p.c + p.w || r >= p.r + p.h) return false;
  const m = maskOf(p);
  return !m || m[(r - p.r) * p.w + (c - p.c)] === 1;
}

/** 실점유 셀 수 (건폐율 분자 — 블록은 멤버 합집합 면적) */
export function placementArea(p) {
  const m = maskOf(p);
  if (!m) return p.w * p.h;
  let n = 0;
  for (let i = 0; i < m.length; i++) n += m[i];
  return n;
}

/** 멤버 90도 시계방향 1회 회전. (w,h)는 회전 전 bbox. 반환 멤버는 (h,w) bbox 기준 */
export function rotateMembers(members, w, h) {
  return members.map((m) => ({
    typeId: m.typeId, dc: h - (m.dr + m.h), dr: m.dc, w: m.h, h: m.w,
  }));
}

/** w×h 건물이 (c,r)에서 완전히 대지 내부이고 occupied와 겹치지 않는지. mask 셀=0은 검사 제외 */
export function fits(grid, occupied, c, r, w, h, mask = null) {
  for (let dr = 0; dr < h; dr++) {
    for (let dc = 0; dc < w; dc++) {
      if (mask && !mask[dr * w + dc]) continue; // 노치: 대지 밖/점유여도 무관
      const cc = c + dc, rr = r + dr;
      if (!isBuildable(grid, cc, rr)) return false;
      if (occupied && occupied[rr * grid.cols + cc]) return false;
    }
  }
  return true;
}

/** 배치들로부터 점유 맵(Uint8Array) 생성. 값 = placementIndex+1 (0=빈칸). 블록 노치는 비점유 */
export function buildOccupancy(grid, placements) {
  const occ = new Uint16Array(grid.cols * grid.rows);
  placements.forEach((p, i) => {
    const m = maskOf(p);
    for (let dr = 0; dr < p.h; dr++) {
      for (let dc = 0; dc < p.w; dc++) {
        if (m && !m[dr * p.w + dc]) continue;
        const cc = p.c + dc, rr = p.r + dr;
        if (cc >= 0 && rr >= 0 && cc < grid.cols && rr < grid.rows) {
          occ[rr * grid.cols + cc] = i + 1;
        }
      }
    }
  });
  return occ;
}
