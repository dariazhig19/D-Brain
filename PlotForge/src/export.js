// export.js — 배치 결과를 DXF(R12 호환 POLYLINE/TEXT)로 출력.
// 자체 dxf.js 파서와 왕복 가능(POLYLINE+VERTEX+SEQEND 파싱 지원).
import { cellToWorld } from './grid.js';

const num = (v) => String(Math.round(v * 1000) / 1000);

function pline(layer, pts, closed = true) {
  let s = `0\nPOLYLINE\n8\n${layer}\n66\n1\n70\n${closed ? 1 : 0}\n`;
  for (const p of pts) s += `0\nVERTEX\n8\n${layer}\n10\n${num(p.x)}\n20\n${num(p.y)}\n`;
  s += '0\nSEQEND\n';
  return s;
}

function text(layer, x, y, h, str) {
  return `0\nTEXT\n8\n${layer}\n10\n${num(x)}\n20\n${num(y)}\n40\n${num(h)}\n72\n1\n11\n${num(x)}\n21\n${num(y)}\n1\n${str}\n`;
}

function cellRectPts(grid, c, r, w, h) {
  const p = cellToWorld(grid, c, r);
  const s = grid.cellSize;
  return [
    { x: p.x, y: p.y },
    { x: p.x + w * s, y: p.y },
    { x: p.x + w * s, y: p.y + h * s },
    { x: p.x, y: p.y + h * s },
  ];
}

/** 도로 셀 집합을 행 단위 연속 구간(rect)으로 병합해 엔티티 수 축소 */
function mergeRoadRuns(grid, roadCells) {
  const set = new Set(roadCells);
  const runs = [];
  for (let r = 0; r < grid.rows; r++) {
    let start = -1;
    for (let c = 0; c <= grid.cols; c++) {
      const has = c < grid.cols && set.has(r * grid.cols + c);
      if (has && start === -1) start = c;
      else if (!has && start !== -1) { runs.push({ r, c0: start, c1: c - 1 }); start = -1; }
    }
  }
  return runs;
}

/**
 * DXF 문자열 생성.
 * 레이어: SITE(대지), ROAD(도로), BLDG_<타입명>(건물), ANNO(라벨)
 */
export function buildDXF(state, alt) {
  const { site, grid } = state;
  let e = '';
  if (site && site.length) e += pline('SITE', site, true);
  if (grid && alt) {
    const roadCells = [...new Set([...(state.roadNetwork || []), ...(alt.roads || [])])];
    for (const run of mergeRoadRuns(grid, roadCells)) {
      e += pline('ROAD', cellRectPts(grid, run.c0, run.r, run.c1 - run.c0 + 1, 1), true);
    }
    // 선형 요소: kind별 레이어(점유 셀 병합) + 중심선 벡터(30/60° CAD 후처리용)
    const KIND_LAYERS = { rack: 'RACK', tunnel: 'TUNNEL', conduit: 'CONDUIT', road: 'ROAD' };
    for (const k of state.corridors || []) {
      const layer = KIND_LAYERS[k.kind] || 'RACK';
      for (const run of mergeRoadRuns(grid, k.cells)) {
        e += pline(layer, cellRectPts(grid, run.c0, run.r, run.c1 - run.c0 + 1, 1), true);
      }
      if (k.waypoints && k.waypoints.length >= 2) {
        const pts = k.waypoints.map((idx) => {
          const p = cellToWorld(grid, idx % grid.cols, (idx / grid.cols) | 0);
          return { x: p.x + grid.cellSize / 2, y: p.y + grid.cellSize / 2 };
        });
        e += pline(layer + '_CL', pts, false); // 중심선 (open polyline)
      }
    }
    const layerName = (name) => (name || 'UNKNOWN').replace(/[\s,;=]/g, '_');
    for (const p of alt.placements) {
      const t = state.buildingTypes.find((x) => x.id === p.typeId);
      if (p.members && p.members.length) {
        // 블록: 외곽 bbox는 BLOCK_ 레이어, 멤버는 각 타입 레이어 — CAD에서 시설물 단위 후처리 가능
        e += pline('BLOCK_' + layerName(t?.name), cellRectPts(grid, p.c, p.r, p.w, p.h), true);
        for (const m of p.members) {
          const mt = state.buildingTypes.find((x) => x.id === m.typeId);
          e += pline('BLDG_' + layerName(mt?.name), cellRectPts(grid, p.c + m.dc, p.r + m.dr, m.w, m.h), true);
          if (mt) {
            const mc = cellToWorld(grid, p.c + m.dc, p.r + m.dr);
            e += text('ANNO', mc.x + (m.w * grid.cellSize) / 2, mc.y + (m.h * grid.cellSize) / 2,
              grid.cellSize * 0.25, mt.name);
          }
        }
      } else {
        e += pline('BLDG_' + layerName(t?.name), cellRectPts(grid, p.c, p.r, p.w, p.h), true);
        if (t) {
          const ctr = cellToWorld(grid, p.c, p.r);
          e += text('ANNO',
            ctr.x + (p.w * grid.cellSize) / 2,
            ctr.y + (p.h * grid.cellSize) / 2,
            grid.cellSize * 0.3, t.name);
        }
      }
    }
  }
  return `0\nSECTION\n2\nENTITIES\n${e}0\nENDSEC\n0\nEOF\n`;
}
