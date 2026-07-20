// dxf.js — 최소 DXF 파서. LWPOLYLINE / POLYLINE의 정점을 추출해 대지 후보 폴리곤 반환.
import { polygonArea } from './geometry.js';

/** DXF 텍스트 → 폴리곤 배열(각 [{x,y}...]). 라이브러리 없이 태그 스트림 파싱. */
export function parseDXF(text) {
  const lines = text.split(/\r\n|\r|\n/);
  const pairs = [];
  for (let i = 0; i + 1 < lines.length; i += 2) {
    pairs.push({ code: parseInt(lines[i].trim(), 10), val: lines[i + 1] });
  }
  const polys = [];
  let cur = null;      // 현재 LWPOLYLINE 정점 수집
  let poly = null;     // 현재 POLYLINE(구형) 수집
  let pendingX = null;

  for (let i = 0; i < pairs.length; i++) {
    const { code, val } = pairs[i];
    if (code === 0) {
      const t = (val || '').trim().toUpperCase();
      if (cur && cur.length >= 3) polys.push(cur);
      cur = null;
      if (t === 'LWPOLYLINE') { cur = []; pendingX = null; }
      else if (t === 'POLYLINE') { poly = []; }
      else if (t === 'SEQEND') { if (poly && poly.length >= 3) polys.push(poly); poly = null; }
      continue;
    }
    if (cur) {
      if (code === 10) pendingX = parseFloat(val);
      else if (code === 20 && pendingX !== null) { cur.push({ x: pendingX, y: parseFloat(val) }); pendingX = null; }
    } else if (poly) {
      // POLYLINE 내부 VERTEX: 10/20 쌍
      if (code === 10) pendingX = parseFloat(val);
      else if (code === 20 && pendingX !== null) { poly.push({ x: pendingX, y: parseFloat(val) }); pendingX = null; }
    }
  }
  if (cur && cur.length >= 3) polys.push(cur);
  return polys;
}

/** 여러 폴리곤 중 면적이 가장 큰 것을 대지 경계로 채택 */
export function pickSitePolygon(polys) {
  if (!polys.length) return null;
  return polys.reduce((a, b) => (polygonArea(b) > polygonArea(a) ? b : a));
}
