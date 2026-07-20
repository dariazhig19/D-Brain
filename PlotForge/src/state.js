// state.js — 앱 전역 상태 + 간단한 pub/sub 스토어

let _id = 1;
export const uid = (prefix = 'id') => `${prefix}_${_id++}`;
/** 저장본 복원 후 id 충돌 방지: 카운터를 기존 id들의 최대치 이상으로 올림 */
export function bumpUidAbove(ids) {
  for (const id of ids) {
    const m = /_(\d+)$/.exec(id || '');
    if (m) _id = Math.max(_id, parseInt(m[1], 10) + 1);
  }
}

/**
 * 도메인 모델
 * - site: 대지 폴리곤 (월드좌표 배열)
 * - cellSize: 격자 셀 크기
 * - buildingTypes: [{id, name, w, h, color}]   (w,h = 셀 단위)
 * - rules: [{id, buildingTypeId, kind, targetType, gap, mode}]
 *     kind: 'gapFrom'(target에서 gap셀 이상 이격) | 'adjacentTo'(target에서 gap셀 이내) |
 *           'nearRoad'(도로/대지경계에서 gap셀 이내) | 'insideOnly'
 *     mode: 'hard'(필수) | 'soft'(선호=점수)
 * - sequence: [buildingTypeId, ...]  배치 순서
 * - alternatives: [{id, name, placements:[{typeId,c,r,w,h}], roads:Set-like array}]
 * - activeAltId: 현재 편집/표시 중 대안
 */
export const store = {
  state: {
    site: null,
    cellSize: 10,
    maxCoverage: null, // 건폐율 상한(%), null = 제한 없음
    roadNetwork: [], // 도로 우선 모드: 선(先)생성된 도로 셀 인덱스 (사이트 전역, 대안 공유)
    roadPattern: 'comb', // 도로망 패턴: 'comb'(빗살) | 'grid'(격자) | 'loop'(루프)
    entryCell: null, // 진입점 셀 인덱스 (null = 자동)
    windDir: null, // 바람이 불어오는 방위각(도, 0=N 시계방향). null = 풍향 규칙 비활성
    anchors: [], // 사용자 지정점 [{id, name, c, r}] — Tie-in/Gate 등. distanceToAnchor 규칙의 기준
    // 선형 요소(수동 그리기, 사이트 전역): [{id, kind:'rack'|'tunnel'|'conduit', name, widthM, waypoints:[cellIdx], cells:[cellIdx]}]
    // tunnel은 지하 — 배치를 차단하지 않고 클리어런스에만 참여 (PLAN.md D9)
    corridors: [],
    // 전역 클리어런스 매트릭스(m, 대칭): a/b = 카테고리('equipment'|'building'|'block') 또는 선형 kind
    clearances: [], // [{id, a, b, minM}] 예: {a:'road', b:'equipment', minM:3}
    roadParams: { widthM: null, ringOffsetM: null }, // 도로망 폭·루프 링 이격(m). null=기본(1셀/기존 공식)
    grid: null,
    buildingTypes: [],
    rules: [],
    sequence: [],
    alternatives: [],
    activeAltId: null,
    tool: 'select', // 'select' | 'drawSite' | 'place'
    placingTypeId: null, // 'place' 툴에서 배치할 건물 타입
    draftSite: [], // drawSite 중 임시 정점
  },

  _subs: new Set(),
  subscribe(fn) { this._subs.add(fn); return () => this._subs.delete(fn); },
  emit() { for (const fn of this._subs) fn(this.state); },
  set(patch) { Object.assign(this.state, patch); this.emit(); },
  get() { return this.state; },
};

export function activeAlt(s = store.state) {
  return s.alternatives.find((a) => a.id === s.activeAltId) || null;
}

export function typeById(s, id) {
  return s.buildingTypes.find((t) => t.id === id) || null;
}

/** 새 빈 대안 생성 */
export function newAlternative(name) {
  return { id: uid('alt'), name, placements: [], roads: [] };
}
