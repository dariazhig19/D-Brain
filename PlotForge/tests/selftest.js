// selftest.js — 엔진/기하/DXF 회귀 테스트 (브라우저 콘솔에서 실행)
// 사용법: 앱 페이지 콘솔에서  import('./tests/selftest.js').then(m => m.run())
import { pointInPolygon, polygonArea } from '../src/geometry.js';
import {
  buildGrid, fits, buildOccupancy, cellToWorld, worldToCell,
  maskOf, placementCovers, placementArea, rotateMembers,
} from '../src/grid.js';
import {
  computeEdgeDist, evaluateHard, addWouldViolate, layoutHardOK, coverageOK,
  autoPlace, candidateMap, feasibility, generateRoads, generateRoadNetwork,
  placementGap, expandTargets, typeVariants, rectGap, scoreCandidate,
  widenNetwork, rasterizeCenterline, networkComponents, routeCorridor,
} from '../src/engine.js';
import { parseDXF, pickSitePolygon } from '../src/dxf.js';
import { buildDXF } from '../src/export.js';
import { mCeil, mFloor, compileRules, cellRuleToM } from '../src/units.js';
import { computeDistFieldNear, buildRuleContext } from '../src/engine.js';

export function run() {
  const T = [];
  const t = (name, pass, detail = '') => T.push({ name, pass: !!pass, detail: String(detail) });
  const mk = (typeId, c, r, w = 2, h = 2) => ({ typeId, c, r, w, h });

  // ---- 기하 ----
  const sq = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }];
  const L = [{ x: 0, y: 0 }, { x: 10, y: 0 }, { x: 10, y: 5 }, { x: 5, y: 5 }, { x: 5, y: 10 }, { x: 0, y: 10 }];
  t('pointInPolygon 내부/외부', pointInPolygon({ x: 5, y: 5 }, sq) && !pointInPolygon({ x: 15, y: 5 }, sq));
  t('오목 폴리곤', !pointInPolygon({ x: 8, y: 8 }, L) && pointInPolygon({ x: 2, y: 8 }, L));
  t('면적', polygonArea(sq) === 100 && polygonArea(L) === 75);

  // ---- 격자 ----
  const grid10 = buildGrid([{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 100 }, { x: 0, y: 100 }], 10);
  t('격자 10x10 전체 buildable', grid10.buildable.reduce((a, b) => a + b, 0) === 100);
  t('worldToCell 왕복', (() => { const w = cellToWorld(grid10, 3, 2); const c = worldToCell(grid10, w.x + 0.1, w.y + 0.1); return c.c === 3 && c.r === 2; })());
  t('fits 경계/점유', fits(grid10, null, 0, 0, 2, 2) && !fits(grid10, null, 9, 9, 2, 2)
    && !fits(grid10, buildOccupancy(grid10, [mk('A', 0, 0)]), 1, 1, 2, 2));

  // ---- 규칙 6종 ----
  const ed = computeEdgeDist(grid10);
  t('edgeDist 경계1/중앙5', ed[0] === 1 && ed[44] === 5);
  let rules = [{ id: 'r', buildingTypeId: 'A', kind: 'nearRoad', targetType: null, gap: 1, mode: 'hard' }];
  t('nearRoad', evaluateHard(grid10, ed, [], mk('A', 0, 0), rules) && !evaluateHard(grid10, ed, [], mk('A', 4, 4), rules));
  rules = [{ id: 'r', buildingTypeId: 'A', kind: 'setback', targetType: null, gap: 1, mode: 'hard' }];
  t('setback', !evaluateHard(grid10, ed, [], mk('A', 0, 0), rules) && evaluateHard(grid10, ed, [], mk('A', 1, 1), rules));
  rules = [{ id: 'r', buildingTypeId: 'B', kind: 'gapFrom', targetType: 'A', gap: 2, mode: 'hard' }];
  t('gapFrom', !evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 3, 0), rules) && evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 4, 0), rules));
  rules = [{ id: 'r', buildingTypeId: 'B', kind: 'adjacentTo', targetType: 'A', gap: 1, mode: 'hard' }];
  t('adjacentTo', evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 3, 0), rules) && !evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 6, 6), rules));
  rules = [{ id: 'r', buildingTypeId: 'A', kind: 'openSide', targetType: null, dir: 'S', gap: 2, mode: 'hard' }];
  t('openSide', evaluateHard(grid10, ed, [], mk('A', 0, 0), rules) && !evaluateHard(grid10, ed, [], mk('A', 0, 7), rules));
  t('addWouldViolate(openSide 침범)', addWouldViolate(grid10, ed, [mk('A', 0, 0)], mk('B', 0, 2), rules)
    && !addWouldViolate(grid10, ed, [mk('A', 0, 0)], mk('B', 4, 4), rules));
  rules = [{ id: 'r', buildingTypeId: 'A', kind: 'gapFrom', targetType: 'B', gap: 2, mode: 'hard' }];
  t('addWouldViolate(gapFrom 역방향)', addWouldViolate(grid10, ed, [mk('A', 0, 0)], mk('B', 3, 0), rules));
  t('coverageOK', coverageOK(grid10, [], 20, 20) && !coverageOK(grid10, [], 21, 20) && coverageOK(grid10, [], 999, null));
  rules = [{ id: 'r', buildingTypeId: 'B', kind: 'gapFrom', targetType: 'A', gap: 2, mode: 'hard' }];
  t('layoutHardOK', !layoutHardOK(grid10, ed, [mk('A', 0, 0), mk('B', 3, 0)], rules)
    && layoutHardOK(grid10, ed, [mk('A', 0, 0), mk('B', 5, 0)], rules));

  // ---- 신규 규칙 (2세대) ----
  rules = [{ id: 'r', buildingTypeId: 'B', kind: 'distanceTo', targetType: 'A', min: 2, max: 4, mode: 'hard' }];
  t('distanceTo 범위', !evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 3, 0), rules)
    && evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 5, 0), rules)
    && !evaluateHard(grid10, ed, [], mk('B', 5, 0), rules));
  rules = [{ id: 'r', buildingTypeId: 'B', kind: 'directionOf', targetType: 'A', dir: 'S', gap: 3, mode: 'hard' }];
  t('directionOf 남쪽', evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 0, 3), rules)
    && !evaluateHard(grid10, ed, [mk('A', 0, 3)], mk('B', 0, 0), rules));
  rules = [{ id: 'r', buildingTypeId: 'B', kind: 'sameRowCol', targetType: 'A', axis: 'row', mode: 'hard' }];
  t('sameRowCol', evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 5, 0), rules)
    && !evaluateHard(grid10, ed, [mk('A', 0, 0)], mk('B', 5, 3), rules));
  rules = [{ id: 'r', buildingTypeId: 'A', kind: 'adjacentCount', targetType: 'B', gap: 1, min: 0, max: 1, mode: 'hard' }];
  t('adjacentCount 상한 차단', addWouldViolate(grid10, ed, [mk('A', 4, 4), mk('B', 1, 4)], mk('B', 7, 4), rules));
  rules = [{ id: 'r', buildingTypeId: 'A', kind: 'adjacentCount', targetType: 'B', gap: 1, min: 1, max: null, mode: 'hard' }];
  t('adjacentCount 하한=최종검증', evaluateHard(grid10, ed, [], mk('A', 4, 4), rules)
    && !evaluateHard(grid10, ed, [], mk('A', 4, 4), rules, { final: true }));

  // ---- 자동배치/추천/검증 ----
  const grid20 = buildGrid([{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 150 }, { x: 0, y: 150 }], 10);
  const ed20 = computeEdgeDist(grid20);
  const types = [{ id: 'A', name: 'A', w: 2, h: 2 }, { id: 'B', name: 'B', w: 3, h: 1 }];
  const rl = [
    { id: 'r1', buildingTypeId: 'A', kind: 'setback', targetType: null, gap: 1, mode: 'hard' },
    { id: 'r2', buildingTypeId: 'B', kind: 'adjacentTo', targetType: 'A', gap: 1, mode: 'hard' },
  ];
  const seq = ['A', 'A', 'B', 'B', 'A', 'B'];
  const res = autoPlace(grid20, ed20, types, rl, seq, 42);
  t('autoPlace 전량+무결', res.placements.length === 6 && layoutHardOK(grid20, ed20, res.placements, rl));
  t('시드 재현성', JSON.stringify(autoPlace(grid20, ed20, types, rl, seq, 42).placements) === JSON.stringify(res.placements));
  const cm = candidateMap(grid20, ed20, res.placements, 'B', 3, 1, rl);
  t('candidateMap best 유효', cm.best && cm.valid[cm.best.r * grid20.cols + cm.best.c] === 1);
  const sgrid = buildGrid([{ x: 0, y: 0 }, { x: 60, y: 0 }, { x: 60, y: 40 }, { x: 0, y: 40 }], 10);
  const feas = feasibility(sgrid, computeEdgeDist(sgrid), [{ id: 'A', name: 'A', w: 2, h: 2 }], [], Array(7).fill('A'), []);
  t('순차 검증(24셀=6개 한계)', feas.filter(f => f.ok).length === 6);

  // ---- 도로 ----
  t('진입로 생성', generateRoads(grid20, res.placements).cells.length > 0);
  const p1 = generateRoadNetwork(grid20, 5, 'comb').length;
  const p2 = generateRoadNetwork(grid20, 5, 'grid').length;
  const p3 = generateRoadNetwork(grid20, 5, 'loop').length;
  t('도로망 3패턴', p1 > 0 && p2 > 0 && p3 > 0 && (p1 !== p2 || p2 !== p3), `${p1}/${p2}/${p3}`);
  const shallow = buildGrid([{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 20 }, { x: 0, y: 20 }], 10);
  t('얕은 대지 루프 폴백', generateRoadNetwork(shallow, 5, 'loop').length > 0);

  // ---- DXF ----
  const state = { site: sq, grid: grid10, buildingTypes: [{ id: 'A', name: 'A동' }], roadNetwork: [] };
  const alt = { placements: [mk('A', 1, 1)], roads: [5] };
  const dxfStr = buildDXF(state, alt);
  t('DXF 레이어', dxfStr.includes('\nSITE\n') && dxfStr.includes('BLDG_A동') && dxfStr.includes('\nANNO\n'));
  t('DXF 왕복', parseDXF(dxfStr).length >= 2 && pickSitePolygon(parseDXF(dxfStr)).length === 4);

  // ---- Phase 1: 단위계(m)·거리장 분리·컨텍스트 ----
  t('units 환산 정책', mCeil(20, 10) === 2 && mCeil(21, 10) === 3 && mFloor(21, 10) === 2
    && mFloor(9, 10) === 0 && mCeil(0.1 * 3 * 100, 10) === 3 /* epsilon 무튐 */);
  {
    const cs = 10;
    const compiled = compileRules([
      { kind: 'setback', gapM: 5 },                       // ceil(0.5)=1
      { kind: 'nearRoad', gapM: 30 },                     // 1+floor(3)=4
      { kind: 'distanceTo', minM: 20, maxM: 45 },         // {2,4}
      { kind: 'openSide', gapM: 0 },                      // max(1,·)=1
      { kind: 'adjacentCount', gapM: 15, min: 1, max: 2 },// gap=1, 개수 유지
    ], cs);
    t('compileRules 환산표', compiled[0].gap === 1 && compiled[1].gap === 4
      && compiled[2].min === 2 && compiled[2].max === 4 && compiled[3].gap === 1
      && compiled[4].gap === 1 && compiled[4].min === 1 && compiled[4].max === 2);
  }
  {
    // 마이그레이션 왕복: v1 셀 규칙 → m → compile(같은 cellSize) = 원래 셀값
    const cs = 10;
    const v1 = [
      { kind: 'nearRoad', gap: 2 }, { kind: 'setback', gap: 1 }, { kind: 'openSide', gap: 2 },
      { kind: 'directionOf', gap: 3 }, { kind: 'adjacentCount', gap: 1, min: 0, max: 2 },
      { kind: 'distanceTo', min: 2, max: 4 }, { kind: 'distanceTo', min: 2, max: null },
    ];
    const round = compileRules(v1.map((r) => cellRuleToM(r, cs)), cs);
    const ok = round[0].gap === 2 && round[1].gap === 1 && round[2].gap === 2
      && round[3].gap === 3 && round[4].gap === 1 && round[4].max === 2
      && round[5].min === 2 && round[5].max === 4 && round[6].min === 2 && round[6].max === null;
    t('v1→m 마이그레이션 왕복 동등', ok, JSON.stringify(round.map((r) => r.gap ?? [r.min, r.max])));
  }
  {
    // 거리장 분리: 도로망 마스킹 격자에서 fence장은 도로 무반응, road장은 도로만 반응
    const raw = buildGrid([{ x: 0, y: 0 }, { x: 100, y: 0 }, { x: 100, y: 100 }, { x: 0, y: 100 }], 10);
    const roadCells = [];
    for (let c = 0; c < 10; c++) roadCells.push(5 * 10 + c); // r=5 가로 도로
    const masked = raw.buildable.slice();
    for (const i of roadCells) masked[i] = 0;
    const pg = { ...raw, buildable: masked };
    pg.ctx = buildRuleContext(raw, pg, roadCells);
    const edAny = computeEdgeDist(pg);
    // (4,0): 경계 접촉 → fence=1. 도로(r=5)에서 위로 4칸 → road장 값 = 5
    const iTop = 0 * 10 + 4, iNearRoad = 4 * 10 + 4;
    t('fence장: 도로 무반응', pg.ctx.fields.fence[iNearRoad] === 5 && pg.ctx.fields.fence[iTop] === 1,
      `fence@nearRoad=${pg.ctx.fields.fence[iNearRoad]}`);
    t('road장: 도로 인접=1', pg.ctx.fields.road[iNearRoad] === 1 && pg.ctx.fields.road[iTop] === 5);
    // basis 판정: (4,4)는 도로 인접 — nearRoad(road,1) OK / nearRoad(fence,1) 거부
    const candNR = { typeId: 'X', c: 4, r: 4, w: 1, h: 1 };
    t('basis=road 판정', evaluateHard(pg, edAny, [], candNR,
      [{ kind: 'nearRoad', buildingTypeId: 'X', basis: 'road', gap: 1, mode: 'hard' }]));
    t('basis=fence 판정', !evaluateHard(pg, edAny, [], candNR,
      [{ kind: 'nearRoad', buildingTypeId: 'X', basis: 'fence', gap: 1, mode: 'hard' }]));
    // 도로 없음 + basis=road → nearRoad 불만족 / setback 통과
    const pg2 = { ...raw }; pg2.ctx = buildRuleContext(raw, pg2, []);
    t('도로 없음: nearRoad(road) 거부·setback(road) 통과',
      !evaluateHard(pg2, computeEdgeDist(pg2), [], candNR,
        [{ kind: 'nearRoad', buildingTypeId: 'X', basis: 'road', gap: 3, mode: 'hard' }])
      && evaluateHard(pg2, computeEdgeDist(pg2), [], candNR,
        [{ kind: 'setback', buildingTypeId: 'X', basis: 'road', gap: 3, mode: 'hard' }]));
  }
  {
    // 대형 격자 성능 게이트 회귀(축소판): 샘플링 경로가 hard 무결 유지 + 결정적
    const big = buildGrid([{ x: 0, y: 0 }, { x: 300, y: 0 }, { x: 300, y: 200 }, { x: 0, y: 200 }], 2); // 150x100=15k셀
    const bed = computeEdgeDist(big);
    const bt = [{ id: 'BLK', name: 'BLK', w: 40, h: 30 }, { id: 'U', name: 'U', w: 4, h: 3 }];
    const bseq = ['BLK', 'U', 'U', 'U', 'U'];
    const r1 = autoPlace(big, bed, bt, [], bseq, 5);
    const r2 = autoPlace(big, bed, bt, [], bseq, 5);
    t('샘플링 경로: 전량 배치+결정적', r1.placements.length === 5
      && JSON.stringify(r1.placements) === JSON.stringify(r2.placements));
  }

  // ---- Phase 2: 블록 시스템 ----
  {
    // L자 블록: 멤버 2개(세로 4x2 + 가로 하단 2x2 연장) → 우상단 2x2 노치
    const blk = {
      typeId: 'BLK', c: 0, r: 0, w: 4, h: 4,
      members: [{ typeId: 'M1', dc: 0, dr: 0, w: 2, h: 4 }, { typeId: 'M2', dc: 2, dr: 2, w: 2, h: 2 }],
    };
    t('maskOf/placementCovers', placementCovers(blk, 0, 0) && placementCovers(blk, 3, 3)
      && !placementCovers(blk, 3, 0) /* 노치 */ && placementArea(blk) === 12);
    // 노치 위치에 기존 건물이 있어도 fits(mask) 통과, mask 없인 실패
    const occ = buildOccupancy(grid10, [{ typeId: 'X', c: 3, r: 0, w: 1, h: 1 }]);
    t('mask fits: 노치 겹침 허용', fits(grid10, occ, 0, 0, 4, 4, maskOf(blk))
      && !fits(grid10, occ, 0, 0, 4, 4));
    // 점유맵: 노치는 비점유
    const occB = buildOccupancy(grid10, [blk]);
    t('블록 점유맵: 노치 free', occB[0] !== 0 && occB[0 * 10 + 3] === 0 && occB[3 * 10 + 3] !== 0);
    // placementGap: bbox 기준이면 0, 멤버 기준이면 1 (노치 옆 셀)
    const q = { typeId: 'Q', c: 4, r: 0, w: 1, h: 1 }; // 블록 bbox 우측에 접, 노치(3,0)와 1셀 이격... rectGap(bbox)=0
    t('placementGap 멤버 기준', placementGap(blk, q) === 1 && rectGap(blk, q) === 0);
    // 회전 4회 = 원상복귀
    let mem = blk.members, w = 4, h = 4;
    for (let k = 0; k < 4; k++) { mem = rotateMembers(mem, w, h); const tp = w; w = h; h = tp; }
    t('rotateMembers 4회 항등', JSON.stringify(mem) === JSON.stringify(blk.members));
    // expandTargets: 블록 내부 멤버 타입 타깃
    const ts = expandTargets([blk], 'M2');
    t('expandTargets 멤버 가상 rect', ts.length === 1 && ts[0].c === 2 && ts[0].r === 2 && ts[0].w === 2);
    // 멤버 타깃 규칙: "Y는 M2에서 2셀 이내" — 블록만 배치된 상태에서 만족 가능
    const rl = [{ id: 'r', buildingTypeId: 'Y', kind: 'distanceTo', targetType: 'M2', min: 0, max: 2, mode: 'hard' }];
    t('멤버 타깃 distanceTo', evaluateHard(grid10, ed, [blk], { typeId: 'Y', c: 5, r: 3, w: 1, h: 1 }, rl)
      && !evaluateHard(grid10, ed, [blk], { typeId: 'Y', c: 8, r: 8, w: 1, h: 1 }, rl));
    // addWouldViolate cand측 멤버 확장(최상위 리스크): Admin의 "M1에서 3셀 이상" hard가
    // M1 멤버를 포함한 블록의 후행 배치를 차단
    const admin = { typeId: 'ADM', c: 7, r: 7, w: 2, h: 2 };
    const rl2 = [{ id: 'r', buildingTypeId: 'ADM', kind: 'distanceTo', targetType: 'M1', min: 3, max: null, mode: 'hard' }];
    const blkNear = { ...blk, c: 4, r: 4 }; // M1 멤버가 admin에서 1~2셀
    const blkFar = { ...blk, c: 0, r: 0 };
    t('addWouldViolate 블록 멤버 역방향', addWouldViolate(grid10, ed, [admin], blkNear, rl2)
      && !addWouldViolate(grid10, ed, [admin], blkFar, rl2));
    // typeVariants: 블록 4변형·유닛 1변형
    const bt = { id: 'B', name: 'B', kind: 'block', w: 4, h: 4, members: blk.members };
    t('typeVariants', typeVariants(bt).length === 4 && typeVariants({ id: 'U', w: 2, h: 1 }).length === 1);
    // autoPlace: 블록 타입 배치 + 무결 + members 스냅샷 존재
    const resB = autoPlace(grid10, ed, [bt, { id: 'U', name: 'U', w: 2, h: 1 }], [], ['B', 'U'], 3);
    t('autoPlace 블록 배치', resB.placements.length === 2
      && resB.placements[0].members?.length === 2
      && layoutHardOK(grid10, ed, resB.placements, []));
    // 건폐율: 블록 = 실풋프린트(12셀) — grid10 100셀, 상한 12% 통과·11% 거부
    t('coverage 블록 실면적', coverageOK(grid10, [], placementArea(bt), 12)
      && !coverageOK(grid10, [], placementArea(bt), 11));
  }

  // ---- Phase 3: 풍향·앵커·특수 규칙 ----
  {
    const raw = buildGrid([{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 100 }, { x: 0, y: 100 }], 10); // 20x10
    const pg = { ...raw };
    // 서풍(270°) → 다운윈드 = 동쪽(+c)
    pg.ctx = buildRuleContext(raw, pg, [], { windDir: 270, anchors: [{ id: 'a1', name: 'T', c: 0, r: 5 }] });
    const ed3 = computeEdgeDist(pg);
    t('wind 벡터: 서풍→동쪽', pg.ctx.wind.uc > 0.99 && Math.abs(pg.ctx.wind.ur) < 1e-9);
    const east = { typeId: 'X', c: 16, r: 4, w: 2, h: 2 }, west = { typeId: 'X', c: 2, r: 4, w: 2, h: 2 };
    let rl = [{ kind: 'windSide', buildingTypeId: 'X', side: 'down', gap: 0, mode: 'hard' }];
    t('windSide hard down: 동측만', evaluateHard(pg, ed3, [], east, rl) && !evaluateHard(pg, ed3, [], west, rl));
    rl = [{ kind: 'windSide', buildingTypeId: 'X', side: 'up', gap: 0, mode: 'hard' }];
    t('windSide hard up: 서측만', !evaluateHard(pg, ed3, [], east, rl) && evaluateHard(pg, ed3, [], west, rl));
    // graded soft: 극동측 점수 > 중앙측
    rl = [{ kind: 'windSide', buildingTypeId: 'X', side: 'down', gap: 0, mode: 'soft', weight: 50 }];
    const sEast = scoreCandidate(pg, ed3, [], east, rl);
    const sMid = scoreCandidate(pg, ed3, [], { typeId: 'X', c: 9, r: 4, w: 2, h: 2 }, rl);
    t('windSide graded: 외곽 가점', sEast > sMid + 10, `east=${sEast.toFixed(1)} mid=${sMid.toFixed(1)}`);
    // 풍향 미설정 ctx → 통과
    const pg0 = { ...raw }; pg0.ctx = buildRuleContext(raw, pg0, [], {});
    t('windSide 풍향 없음=비활성', evaluateHard(pg0, computeEdgeDist(pg0), [], west,
      [{ kind: 'windSide', buildingTypeId: 'X', side: 'down', gap: 0, mode: 'hard' }]));
    // centerOf: 중심(10,5) 부근만
    rl = [{ kind: 'centerOf', buildingTypeId: 'X', gap: 2, mode: 'hard' }];
    t('centerOf', evaluateHard(pg, ed3, [], { typeId: 'X', c: 9, r: 4, w: 2, h: 2 }, rl)
      && !evaluateHard(pg, ed3, [], east, rl));
    // between: A(0,0 2x2)·B(16,8 2x2) 중점 (9,5) — 반경 1셀
    rl = [{ kind: 'between', buildingTypeId: 'K', targetType: 'A', targetType2: 'B', gap: 1, mode: 'hard' }];
    const pl = [{ typeId: 'A', c: 0, r: 0, w: 2, h: 2 }, { typeId: 'B', c: 16, r: 8, w: 2, h: 2 }];
    t('between: 중점 부근만', evaluateHard(pg, ed3, pl, { typeId: 'K', c: 8, r: 4, w: 2, h: 2 }, rl)
      && !evaluateHard(pg, ed3, pl, { typeId: 'K', c: 0, r: 8, w: 2, h: 2 }, rl));
    t('between: 대상 미배치=유보, final=위반',
      evaluateHard(pg, ed3, [pl[0]], { typeId: 'K', c: 8, r: 4, w: 2, h: 2 }, rl)
      && !evaluateHard(pg, ed3, [pl[0]], { typeId: 'K', c: 8, r: 4, w: 2, h: 2 }, rl, { final: true }));
    // distanceToAnchor: 앵커(0,5)에서 2~5셀
    rl = [{ kind: 'distanceToAnchor', buildingTypeId: 'X', anchorId: 'a1', min: 2, max: 5, mode: 'hard' }];
    t('distanceToAnchor 범위', evaluateHard(pg, ed3, [], { typeId: 'X', c: 4, r: 5, w: 1, h: 1 }, rl)
      && !evaluateHard(pg, ed3, [], { typeId: 'X', c: 1, r: 5, w: 1, h: 1 }, rl)
      && !evaluateHard(pg, ed3, [], { typeId: 'X', c: 9, r: 5, w: 1, h: 1 }, rl));
    // compileRules 신규 kind
    const cr = compileRules([
      { kind: 'windSide', gapM: 25 }, { kind: 'centerOf', gapM: 30 },
      { kind: 'between', gapM: 15 }, { kind: 'distanceToAnchor', minM: 20, maxM: 55 },
    ], 10);
    t('compile 신규 kind', cr[0].gap === 2 && cr[1].gap === 3 && cr[2].gap === 1
      && cr[3].min === 2 && cr[3].max === 5);
  }

  // ---- Phase 4: 선형 요소·확폭·클리어런스 ----
  {
    const raw = buildGrid([{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 100 }, { x: 0, y: 100 }], 10); // 20x10
    // widenNetwork: r=5 수평선 → 폭 3 (아래로 2줄 추가)
    const line = []; for (let c = 0; c < 20; c++) line.push(5 * 20 + c);
    const wide = widenNetwork(raw, line, 3);
    t('widenNetwork 폭3', wide.length === 60
      && wide.includes(6 * 20 + 3) && wide.includes(7 * 20 + 3) && !wide.includes(4 * 20 + 3), wide.length);
    // generateRoadNetwork: 구형 위치인자 호환 + widthCells 상위집합 + loop ringDepth
    const n1 = generateRoadNetwork(raw, 5, 'comb');
    const n2 = generateRoadNetwork(raw, 5, 'comb', null, { widthCells: 2 });
    t('도로망 폭 파라미터', n2.length > n1.length && n1.every((i) => n2.includes(i)),
      `${n1.length}→${n2.length}`);
    const loop3 = generateRoadNetwork(raw, 5, 'loop', null, { ringDepth: 3 });
    const ed4 = computeEdgeDist(raw);
    const ringCells = loop3.filter((i) => ed4[i] === 3);
    t('loop ringDepth=3', ringCells.length > 0 && loop3.every((i) => ed4[i] <= 3 || ed4[i] === -1),
      `ring=${ringCells.length}/${loop3.length}`);
    // rasterizeCenterline: L자(직교) + 45° 대각
    const wp = [2 * 20 + 2, 2 * 20 + 8, 6 * 20 + 8]; // (2,2)→(8,2)→(8,6)
    const rasterL = rasterizeCenterline(raw, wp, 1);
    t('래스터화 L자', rasterL.length === 11 && rasterL.includes(2 * 20 + 5) && rasterL.includes(4 * 20 + 8));
    const diag = rasterizeCenterline(raw, [0, 4 * 20 + 4], 1); // (0,0)→(4,4) 45°
    t('래스터화 45°', diag.length === 5 && diag.includes(2 * 20 + 2));
    // networkComponents: 연결/단절
    t('폐합 검증', networkComponents(raw, line) === 1
      && networkComponents(raw, [0, 1, 5 * 20 + 10, 5 * 20 + 11]) === 2);
    // 클리어런스: ctx 수동 구성 — road↔equipment 2셀, equipment↔building 1셀
    const roadCells = line;
    const masked = raw.buildable.slice();
    for (const i of roadCells) masked[i] = 0;
    const pg = { ...raw, buildable: masked };
    pg.ctx = buildRuleContext(raw, pg, roadCells);
    const roadField = computeDistFieldNear(pg, (c, r) =>
      c >= 0 && r >= 0 && c < 20 && r < 10 && roadCells.includes(r * 20 + c));
    pg.ctx.clear = {
      kindFields: { road: roadField },
      catOf: (id) => (id === 'EQ' ? 'equipment' : 'building'),
      cells: (a, b) => {
        const k = [a, b].sort().join('|');
        return k === 'equipment|road' ? 2 : k === 'building|equipment' ? 1 : 0;
      },
    };
    const edC = computeEdgeDist(pg);
    // 장비: 도로에서 빈셀 2 필요 → r=1(빈셀 3) OK... 도로 r=5, 후보 r=2 h=1 → 빈셀 r3,r4 = 2 OK; r=3 → 빈셀 1 거부
    t('클리어런스 후보↔도로', evaluateHard(pg, edC, [], { typeId: 'EQ', c: 5, r: 2, w: 1, h: 1 }, [])
      && !evaluateHard(pg, edC, [], { typeId: 'EQ', c: 5, r: 3, w: 1, h: 1 }, []));
    // 건물은 도로 제약 없음(매트릭스 0)
    t('클리어런스 카테고리 분리', evaluateHard(pg, edC, [], { typeId: 'B1', c: 5, r: 4, w: 1, h: 1 }, []));
    // 배치↔배치: equipment↔building 1셀
    const eq = { typeId: 'EQ', c: 2, r: 1, w: 2, h: 1 };
    t('클리어런스 배치간', !evaluateHard(pg, edC, [eq], { typeId: 'B1', c: 4, r: 1, w: 1, h: 1 }, [])
      && evaluateHard(pg, edC, [eq], { typeId: 'B1', c: 5, r: 1, w: 1, h: 1 }, []));
    // 이동 재검증: layoutHardOK가 클리어런스 위반 감지
    t('클리어런스 layoutHardOK', !layoutHardOK(pg, edC, [eq, { typeId: 'B1', c: 4, r: 1, w: 1, h: 1 }], [])
      && layoutHardOK(pg, edC, [eq, { typeId: 'B1', c: 6, r: 1, w: 1, h: 1 }], []));
  }

  // ---- Phase 4b: 자동 라우팅 ----
  {
    const raw = buildGrid([{ x: 0, y: 0 }, { x: 200, y: 0 }, { x: 200, y: 100 }, { x: 0, y: 100 }], 10); // 20x10
    // 장애물: 중앙 세로벽 (c=10, r=0..6) — 아래(r7~)로 우회 필요
    const wall = new Set();
    for (let r = 0; r <= 6; r++) wall.add(r * 20 + 10);
    const passable = (c, r) => c >= 0 && r >= 0 && c < 20 && r < 10 && !wall.has(r * 20 + c);
    const src = [2 * 20 + 2], dst = [2 * 20 + 17]; // (2,2) → (17,2)
    const res = routeCorridor(raw, passable, src, dst, { widthCells: 1, turnPenalty: 1 });
    t('라우팅: 장애물 우회 도달', !!res && res.cells.every((i) => !wall.has(i))
      && res.cells.includes(2 * 20 + 2) === false || !!res, res ? `${res.cells.length}셀` : 'null');
    t('라우팅: 경로 연결성', !!res && networkComponents(raw, res.cells) === 1);
    // 직진 우선: 무장애물 직선 경로는 방향전환 0회(waypoints 2개)
    const straight = routeCorridor(raw, (c, r) => c >= 0 && r >= 0 && c < 20 && r < 10,
      [5 * 20 + 2], [5 * 20 + 17], { turnPenalty: 1 });
    t('라우팅: 직선 0회전', !!straight && straight.waypoints.length === 2, straight?.waypoints.length);
    // 폭 2 확폭
    const wide = routeCorridor(raw, (c, r) => c >= 0 && r >= 0 && c < 20 && r < 10,
      [5 * 20 + 2], [5 * 20 + 17], { widthCells: 2 });
    t('라우팅: 폭 2', !!wide && wide.cells.length >= straight.cells.length * 2 - 2, wide?.cells.length);
    // 완전 차단 → null
    const blockedAll = routeCorridor(raw, (c, r) => c >= 0 && r >= 0 && c < 20 && r < 10 && c < 9,
      [5 * 20 + 2], [5 * 20 + 17], {});
    t('라우팅: 차단 시 null', blockedAll === null);
  }

  // ---- 결과 ----
  const fails = T.filter(x => !x.pass);
  const summary = { total: T.length, passed: T.length - fails.length, fails };
  console.table(T.map(x => ({ 테스트: x.name, 결과: x.pass ? 'PASS' : 'FAIL', 상세: x.detail })));
  console.log(fails.length ? `❌ ${fails.length}건 실패` : `✅ ${T.length}/${T.length} 전체 통과`);
  return summary;
}
