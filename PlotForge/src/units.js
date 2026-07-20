// units.js — m ↔ 셀 환산 정책의 단일 진실 (PLAN.md D3/D4).
// 규칙은 m 정본(gapM/minM/maxM)으로 저장되고, 엔진은 이 모듈이 컴파일한 셀 정수 규칙만 소비한다.
// 정책: 이격류(최소 보장)=올림, 이내류(최대 보장)=내림 — 양자화가 hard 요구를 완화하지 않는 안전 방향.

const EPS = 1e-9;

export const mCeil = (m, cs) => Math.max(0, Math.ceil(m / cs - EPS));
export const mFloor = (m, cs) => Math.max(0, Math.floor(m / cs + EPS));

/** 표시용: "20m(2셀)" */
export const fmtM = (m, cs) => (m == null ? '∞' : `${m}m`);

/**
 * m 정본 규칙 → 엔진용 셀 규칙 (kind별 환산표).
 * - nearRoad  : "Xm 이내" — edgeDist는 경계 접촉 셀=1이므로 gap = 1 + floor(X/cs)
 * - setback   : "Xm 이상 띄움" — 엔진 판정 minEdge ≥ gap+1 → gap = ceil(X/cs)
 * - openSide  : 개방 깊이 보장 → max(1, ceil)
 * - distanceTo: min=ceil(이격 보장), max=floor(인접 보장)
 * - adjacentCount: gap(판정 거리)=floor. min/max는 '개수'라 환산 없음
 * - directionOf: 최대 거리 → floor
 * - (구형) gapFrom=ceil, adjacentTo=floor — 마이그레이션 누락 대비 방어
 */
export function compileRule(r, cs) {
  const out = { ...r };
  switch (r.kind) {
    case 'nearRoad': out.gap = 1 + mFloor(r.gapM ?? cellsToM(r.gap, cs, 'nearRoad'), cs); break;
    case 'setback': out.gap = mCeil(r.gapM ?? 0, cs); break;
    case 'openSide': out.gap = Math.max(1, mCeil(r.gapM ?? cs, cs)); break;
    case 'directionOf': out.gap = mFloor(r.gapM ?? 3 * cs, cs); break;
    case 'adjacentCount': out.gap = mFloor(r.gapM ?? cs, cs); break; // min/max = 개수, 그대로
    case 'distanceTo':
      out.min = mCeil(r.minM ?? 0, cs);
      out.max = r.maxM == null ? null : mFloor(r.maxM, cs);
      break;
    case 'gapFrom': out.gap = mCeil(r.gapM ?? 0, cs); break;
    case 'adjacentTo': out.gap = mFloor(r.gapM ?? 0, cs); break;
    // ---- Phase 3 특수 규칙 ----
    case 'windSide': out.gap = mFloor(r.gapM ?? 0, cs); break;   // 중심선 여유(이내류=내림)
    case 'centerOf': out.gap = mFloor(r.gapM ?? 0, cs); break;   // 중심 최대 거리(이내류)
    case 'between': out.gap = mFloor(r.gapM ?? 0, cs); break;    // 중점 허용 반경(이내류)
    case 'distanceToAnchor':
      out.min = mCeil(r.minM ?? 0, cs);
      out.max = r.maxM == null ? null : mFloor(r.maxM, cs);
      break;
    default: break; // sameRowCol 등 거리 없음
  }
  return out;
}

export const compileRules = (rules, cs) => (rules || []).map((r) => compileRule(r, cs));

/** 마이그레이션 보조: nearRoad의 gapM 부재 시 셀값 역산용 (compileRule 방어 경로) */
function cellsToM(gapCells, cs, kind) {
  if (gapCells == null) return cs;
  return kind === 'nearRoad' ? Math.max(0, gapCells - 1) * cs : gapCells * cs;
}

/**
 * v1(셀 단위) 규칙 → v2(m 정본) 규칙. 같은 cellSize로 compileRule 하면
 * 원래 셀값이 정확히 복원되도록 역산한다 (왕복 동등성 = 마이그레이션 안전 증명).
 * 변환 후 셀 필드는 제거(이중 진실 금지). adjacentCount의 min/max(개수)는 유지.
 */
export function cellRuleToM(r, cs) {
  const out = { ...r };
  switch (r.kind) {
    case 'nearRoad': out.gapM = Math.max(0, (r.gap ?? 1) - 1) * cs; delete out.gap; break;
    case 'setback': out.gapM = (r.gap ?? 0) * cs; delete out.gap; break;
    case 'openSide': out.gapM = Math.max(1, r.gap ?? 1) * cs; delete out.gap; break;
    case 'directionOf': out.gapM = (r.gap ?? 3) * cs; delete out.gap; break;
    case 'adjacentCount': out.gapM = (r.gap ?? 1) * cs; delete out.gap; break;
    case 'distanceTo':
      out.minM = (r.min || 0) * cs;
      out.maxM = r.max == null ? null : r.max * cs;
      delete out.min; delete out.max;
      break;
    default: break;
  }
  return out;
}
