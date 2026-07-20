// render.js — Canvas 2D 렌더링 + 월드↔화면 좌표 변환
import { bbox } from './geometry.js';
import { typeById } from './state.js';

/** 대지/격자에 맞춰 캔버스를 채우는 뷰 변환 계산 */
export function fitView(state, canvas) {
  const pad = 40;
  let box;
  if (state.grid) {
    const g = state.grid;
    box = { minX: g.origin.x, minY: g.origin.y, w: g.cols * g.cellSize, h: g.rows * g.cellSize };
  } else if (state.site && state.site.length) {
    const b = bbox(state.site);
    box = { minX: b.minX, minY: b.minY, w: b.w || 1, h: b.h || 1 };
  } else {
    box = { minX: 0, minY: 0, w: 1000, h: 1000 };
  }
  const scale = Math.min((canvas.width - pad * 2) / box.w, (canvas.height - pad * 2) / box.h);
  const offX = pad - box.minX * scale + (canvas.width - pad * 2 - box.w * scale) / 2;
  const offY = pad - box.minY * scale + (canvas.height - pad * 2 - box.h * scale) / 2;
  return { scale, offX, offY };
}

export const w2s = (v, x, y) => ({ x: v.offX + x * v.scale, y: v.offY + y * v.scale });
export const s2w = (v, x, y) => ({ x: (x - v.offX) / v.scale, y: (y - v.offY) / v.scale });

function cellRect(v, grid, c, r, w = 1, h = 1) {
  const p = w2s(v, grid.origin.x + c * grid.cellSize, grid.origin.y + r * grid.cellSize);
  return { x: p.x, y: p.y, w: w * grid.cellSize * v.scale, h: h * grid.cellSize * v.scale };
}

export function draw(ctx, state, view, overlay = {}) {
  const cv = ctx.canvas;
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = '#0f1216';
  ctx.fillRect(0, 0, cv.width, cv.height);
  const v = view;

  // 대지 채우기 + 격자
  if (state.grid) {
    const g = state.grid;
    // buildable 셀 배경
    ctx.fillStyle = '#1b2129';
    for (let r = 0; r < g.rows; r++)
      for (let c = 0; c < g.cols; c++)
        if (g.buildable[r * g.cols + c]) {
          const rc = cellRect(v, g, c, r);
          ctx.fillRect(rc.x, rc.y, rc.w + 0.5, rc.h + 0.5);
        }
    // 격자선
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (let c = 0; c <= g.cols; c++) {
      const p1 = w2s(v, g.origin.x + c * g.cellSize, g.origin.y);
      const p2 = w2s(v, g.origin.x + c * g.cellSize, g.origin.y + g.rows * g.cellSize);
      ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y);
    }
    for (let r = 0; r <= g.rows; r++) {
      const p1 = w2s(v, g.origin.x, g.origin.y + r * g.cellSize);
      const p2 = w2s(v, g.origin.x + g.cols * g.cellSize, g.origin.y + r * g.cellSize);
      ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y);
    }
    ctx.stroke();
  }

  // 유효셀 하이라이트 (수동배치 중)
  if (overlay.valid && state.grid) {
    const g = state.grid;
    ctx.fillStyle = 'rgba(80,200,120,0.15)';
    for (let r = 0; r < g.rows; r++)
      for (let c = 0; c < g.cols; c++)
        if (overlay.valid[r * g.cols + c]) {
          const rc = cellRect(v, g, c, r);
          ctx.fillRect(rc.x, rc.y, rc.w, rc.h);
        }
  }

  // 선(先)생성 도로망 (도로 우선 모드) — 아스팔트 색
  if (state.roadNetwork && state.roadNetwork.length && state.grid) {
    const g = state.grid;
    ctx.fillStyle = '#3a3f47';
    for (const idx of state.roadNetwork) {
      const c = idx % g.cols, r = (idx / g.cols) | 0;
      const rc = cellRect(v, g, c, r);
      ctx.fillRect(rc.x, rc.y, rc.w + 0.5, rc.h + 0.5);
    }
  }

  // 선형 요소 (rack/tunnel/conduit) — kind별 스타일
  if (state.corridors && state.corridors.length && state.grid) {
    const g = state.grid;
    const styles = {
      rack: { fill: 'rgba(121,134,203,0.85)' },
      tunnel: { fill: 'rgba(77,208,225,0.28)', dash: true },
      conduit: { fill: 'rgba(38,166,154,0.8)' },
      road: { fill: '#3a3f47' },
    };
    for (const k of state.corridors) {
      const st = styles[k.kind] || styles.rack;
      ctx.fillStyle = st.fill;
      for (const idx of k.cells) {
        const c = idx % g.cols, r = (idx / g.cols) | 0;
        const rc = cellRect(v, g, c, r);
        ctx.fillRect(rc.x, rc.y, rc.w + 0.5, rc.h + 0.5);
        if (st.dash) { // 터널(지하): 점선 테두리로 구분
          ctx.strokeStyle = 'rgba(77,208,225,0.7)';
          ctx.setLineDash([3, 3]);
          ctx.strokeRect(rc.x, rc.y, rc.w, rc.h);
          ctx.setLineDash([]);
        }
      }
    }
  }

  // 선형 그리기 중 드래프트 (중심선 미리보기)
  if (overlay.draftCorridor && overlay.draftCorridor.length && state.grid) {
    const g = state.grid;
    ctx.strokeStyle = '#7986cb';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 4]);
    ctx.beginPath();
    overlay.draftCorridor.forEach((idx, i) => {
      const c = idx % g.cols, r = (idx / g.cols) | 0;
      const p = w2s(v, g.origin.x + (c + 0.5) * g.cellSize, g.origin.y + (r + 0.5) * g.cellSize);
      i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y);
    });
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.lineWidth = 1;
  }

  // 도로 (부도로 → 주도로 순서로 덮어 그림)
  const alt = overlay.alt;
  if (alt && alt.roads && alt.roads.length && state.grid) {
    const g = state.grid;
    const drawCells = (cells, color) => {
      ctx.fillStyle = color;
      for (const idx of cells) {
        const c = idx % g.cols, r = (idx / g.cols) | 0;
        const rc = cellRect(v, g, c, r);
        ctx.fillRect(rc.x, rc.y, rc.w + 0.5, rc.h + 0.5);
      }
    };
    drawCells(alt.roads, '#4a4032');
    if (alt.roadsMain && alt.roadsMain.length) drawCells(alt.roadsMain, '#6b5a3e');
  }

  // 진입점 마커
  if (state.entryCell != null && state.grid) {
    const g = state.grid;
    const c = state.entryCell % g.cols, r = (state.entryCell / g.cols) | 0;
    const rc = cellRect(v, g, c, r);
    const cx = rc.x + rc.w / 2, cy = rc.y + rc.h / 2;
    ctx.fillStyle = '#ffd166';
    ctx.strokeStyle = '#0f1216';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(cx, cy, Math.max(6, rc.w * 0.3), 0, Math.PI * 2);
    ctx.fill(); ctx.stroke();
    ctx.fillStyle = '#0f1216';
    ctx.font = `bold ${Math.max(8, rc.w * 0.35)}px system-ui`;
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('IN', cx, cy);
  }

  // 앵커 마커 (다이아몬드 + 이름)
  if (state.anchors && state.anchors.length && state.grid) {
    const g = state.grid;
    for (const a of state.anchors) {
      const rc = cellRect(v, g, a.c, a.r);
      const cx = rc.x + rc.w / 2, cy = rc.y + rc.h / 2;
      const rr = Math.max(5, rc.w * 0.3);
      ctx.fillStyle = '#4dd0e1';
      ctx.strokeStyle = '#0f1216';
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(cx, cy - rr); ctx.lineTo(cx + rr, cy); ctx.lineTo(cx, cy + rr); ctx.lineTo(cx - rr, cy);
      ctx.closePath(); ctx.fill(); ctx.stroke();
      ctx.fillStyle = '#4dd0e1';
      ctx.font = '10px system-ui';
      ctx.textAlign = 'center'; ctx.textBaseline = 'bottom';
      ctx.fillText(a.name, cx, cy - rr - 2);
    }
  }

  // 풍향 나침반 (좌상단): 화살표 = 바람이 불어가는 방향
  if (state.windDir != null) {
    const cx = 46, cy = 46, R = 26;
    const th = (state.windDir * Math.PI) / 180;
    const ux = -Math.sin(th), uy = Math.cos(th); // 다운윈드 (엔진과 동일 규약)
    ctx.fillStyle = 'rgba(19,26,34,0.85)';
    ctx.strokeStyle = '#2a3644';
    ctx.beginPath(); ctx.arc(cx, cy, R + 6, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
    ctx.strokeStyle = '#ffd166';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(cx - ux * R * 0.7, cy - uy * R * 0.7);
    ctx.lineTo(cx + ux * R * 0.7, cy + uy * R * 0.7);
    ctx.stroke();
    // 화살촉
    const ang = Math.atan2(uy, ux);
    ctx.beginPath();
    ctx.moveTo(cx + ux * R * 0.7, cy + uy * R * 0.7);
    ctx.lineTo(cx + Math.cos(ang + 2.6) * 8 + ux * R * 0.7, cy + Math.sin(ang + 2.6) * 8 + uy * R * 0.7);
    ctx.moveTo(cx + ux * R * 0.7, cy + uy * R * 0.7);
    ctx.lineTo(cx + Math.cos(ang - 2.6) * 8 + ux * R * 0.7, cy + Math.sin(ang - 2.6) * 8 + uy * R * 0.7);
    ctx.stroke();
    ctx.lineWidth = 1;
    ctx.fillStyle = '#8aa0b4';
    ctx.font = 'bold 9px system-ui';
    ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillText('N', cx, cy - R + 2);
    ctx.fillStyle = '#ffd166';
    ctx.fillText('바람', cx, cy + R + 12);
  }

  // 대지 경계선
  const poly = state.site || (state.draftSite.length ? state.draftSite : null);
  if (poly && poly.length) {
    ctx.strokeStyle = '#5aa9e6';
    ctx.lineWidth = 2;
    ctx.beginPath();
    poly.forEach((p, i) => {
      const s = w2s(v, p.x, p.y);
      i ? ctx.lineTo(s.x, s.y) : ctx.moveTo(s.x, s.y);
    });
    if (state.site) ctx.closePath();
    ctx.stroke();
    if (state.tool === 'drawSite')
      for (const p of poly) {
        const s = w2s(v, p.x, p.y);
        ctx.fillStyle = '#5aa9e6';
        ctx.beginPath(); ctx.arc(s.x, s.y, 4, 0, Math.PI * 2); ctx.fill();
      }
  }

  // 배치된 건물 (블록은 멤버별 표시)
  if (alt && state.grid) {
    alt.placements.forEach((p, i) => {
      const t = typeById(state, p.typeId);
      const dragging = overlay.dragIndex === i;
      if (p.members && p.members.length) {
        // 블록: 멤버 sub-rect를 멤버 타입 색으로 + bbox 외곽선(굵게) + 블록명
        ctx.globalAlpha = dragging ? 0.5 : 0.9;
        for (const m of p.members) {
          const mt = typeById(state, m.typeId);
          const mrc = cellRect(v, state.grid, p.c + m.dc, p.r + m.dr, m.w, m.h);
          ctx.fillStyle = (mt && mt.color) || '#888';
          ctx.fillRect(mrc.x + 1, mrc.y + 1, mrc.w - 2, mrc.h - 2);
          ctx.strokeStyle = 'rgba(0,0,0,0.4)';
          ctx.strokeRect(mrc.x + 1, mrc.y + 1, mrc.w - 2, mrc.h - 2);
          if (mt && mrc.w > 30 && mrc.h > 14) {
            ctx.fillStyle = '#000';
            ctx.font = '9px system-ui';
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(mt.name, mrc.x + mrc.w / 2, mrc.y + mrc.h / 2);
          }
        }
        ctx.globalAlpha = 1;
        const rc = cellRect(v, state.grid, p.c, p.r, p.w, p.h);
        ctx.strokeStyle = (t && t.color) || '#546e7a';
        ctx.lineWidth = 2.5;
        ctx.strokeRect(rc.x + 0.5, rc.y + 0.5, rc.w - 1, rc.h - 1);
        ctx.lineWidth = 1;
        if (t && rc.w > 40) {
          ctx.fillStyle = '#dfe6ee';
          ctx.font = 'bold 11px system-ui';
          ctx.textAlign = 'left'; ctx.textBaseline = 'top';
          ctx.fillText(t.name, rc.x + 4, rc.y + 3);
        }
      } else {
        const rc = cellRect(v, state.grid, p.c, p.r, p.w, p.h);
        ctx.fillStyle = (t && t.color) || '#888';
        ctx.globalAlpha = dragging ? 0.5 : 0.9;
        ctx.fillRect(rc.x + 1, rc.y + 1, rc.w - 2, rc.h - 2);
        ctx.globalAlpha = 1;
        ctx.strokeStyle = 'rgba(0,0,0,0.5)';
        ctx.strokeRect(rc.x + 1, rc.y + 1, rc.w - 2, rc.h - 2);
        if (t && rc.w > 24) {
          ctx.fillStyle = '#000';
          ctx.font = '11px system-ui';
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          ctx.fillText(t.name, rc.x + rc.w / 2, rc.y + rc.h / 2);
        }
      }
      // 다중선택 하이라이트 (블록 묶기 대상)
      if (overlay.selection && overlay.selection.has(i)) {
        const rc = cellRect(v, state.grid, p.c, p.r, p.w, p.h);
        ctx.strokeStyle = '#ffd166';
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 3]);
        ctx.strokeRect(rc.x - 1, rc.y - 1, rc.w + 2, rc.h + 2);
        ctx.setLineDash([]);
        ctx.lineWidth = 1;
      }
    });
  }

  // 추천 위치(최적셀)
  if (overlay.best && state.grid) {
    const rc = cellRect(v, state.grid, overlay.best.c, overlay.best.r, overlay.bestW || 1, overlay.bestH || 1);
    ctx.strokeStyle = '#ffd166';
    ctx.lineWidth = 2.5;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(rc.x + 1, rc.y + 1, rc.w - 2, rc.h - 2);
    ctx.setLineDash([]);
  }

  // 배치 고스트(호버) — 블록이면 멤버 실루엣
  if (overlay.ghost && state.grid) {
    const gh = overlay.ghost;
    ctx.fillStyle = gh.valid ? 'rgba(80,200,120,0.5)' : 'rgba(230,80,80,0.5)';
    if (gh.members && gh.members.length) {
      for (const m of gh.members) {
        const mrc = cellRect(v, state.grid, gh.c + m.dc, gh.r + m.dr, m.w, m.h);
        ctx.fillRect(mrc.x + 1, mrc.y + 1, mrc.w - 2, mrc.h - 2);
      }
      const rc = cellRect(v, state.grid, gh.c, gh.r, gh.w, gh.h);
      ctx.strokeStyle = gh.valid ? 'rgba(80,200,120,0.9)' : 'rgba(230,80,80,0.9)';
      ctx.setLineDash([4, 3]);
      ctx.strokeRect(rc.x + 0.5, rc.y + 0.5, rc.w - 1, rc.h - 1);
      ctx.setLineDash([]);
    } else {
      const rc = cellRect(v, state.grid, gh.c, gh.r, gh.w, gh.h);
      ctx.fillRect(rc.x + 1, rc.y + 1, rc.w - 2, rc.h - 2);
    }
  }
}
