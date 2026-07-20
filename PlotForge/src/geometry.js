// geometry.js — 폴리곤/기본 기하 유틸 (월드 좌표계, 단위: 그리드셀과 무관한 실좌표)

/** 점이 폴리곤 내부인지 (ray casting) */
export function pointInPolygon(pt, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y;
    const xj = poly[j].x, yj = poly[j].y;
    const intersect =
      yi > pt.y !== yj > pt.y &&
      pt.x < ((xj - xi) * (pt.y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

/** 폴리곤의 바운딩 박스 */
export function bbox(poly) {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const p of poly) {
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  return { minX, minY, maxX, maxY, w: maxX - minX, h: maxY - minY };
}

/** 폴리곤 면적 (shoelace, 절대값) */
export function polygonArea(poly) {
  let a = 0;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    a += (poly[j].x + poly[i].x) * (poly[j].y - poly[i].y);
  }
  return Math.abs(a / 2);
}

export function dist(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y);
}
