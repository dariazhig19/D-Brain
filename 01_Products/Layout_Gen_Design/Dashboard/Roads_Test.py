"""Road dashboard — Phase 06 sketch roads.

Run with:
    streamlit run 01_Products/Layout_Gen_Design/Dashboard/Roads_Test.py
"""

import streamlit as st
import sys, os, random
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

import importlib
import Core.Groups, Core.Grid, Core.Pathfind, Core.Layout06
importlib.reload(Core.Grid)
importlib.reload(Core.Pathfind)
importlib.reload(Core.Groups)
importlib.reload(Core.Layout06)

from Core.Groups import SHAPES
from Core.Layout06 import generate_sketch, CELL_SIZE, ROAD_BUFFER

plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

st.set_page_config(page_title="Roads Test", layout="wide")

# ── Shared sidebar: site + gate ────────────────────────────────────────────
st.sidebar.header("Site")
site_width  = st.sidebar.slider("Plot Width (A)",  100, 1000, 500, step=10)
site_length = st.sidebar.slider("Plot Length (B)", 100, 1000, 270, step=10)
wind_dir    = st.sidebar.selectbox("Wind Direction",
                                   ["North", "South", "East", "West"], index=2)

st.sidebar.divider()
st.sidebar.header("Site Gate")
gate_side  = st.sidebar.selectbox("Gate edge", ["N", "S", "E", "W"], index=0)
gate_ratio = st.sidebar.slider("Gate position along edge", 0.1, 0.9, 0.4, step=0.05)

st.sidebar.divider()
st.sidebar.header("Fixed Anchors")  # → §3.2
st.sidebar.subheader("Gate House")
gh_edge   = st.sidebar.selectbox("Edge (GH)",     ["N", "S", "E", "W"], index=0)
gh_ratio  = st.sidebar.slider("Position (GH)",    0.0, 1.0, 0.6, step=0.05)
gh_offset = st.sidebar.slider("Offset (GH)",      0, 50, 15, step=1)
bb_edge   = st.sidebar.selectbox("Boom Barrier Side (GH)", ["N", "S", "E", "W"], index=0)

st.sidebar.subheader("GIS")
gis_edge   = st.sidebar.selectbox("Edge (GIS)",   ["N", "S", "E", "W"], index=0)
gis_ratio  = st.sidebar.slider("Position (GIS)",  0.0, 1.0, 0.9, step=0.05)
gis_offset = st.sidebar.slider("Offset (GIS)",    0, 50, 15, step=1)

st.sidebar.subheader("RAW Water Tank")
water_edge   = st.sidebar.selectbox("Edge (RAW Water)", ["N", "S", "E", "W"], index=2)
water_ratio  = st.sidebar.slider("Position (RAW Water)", 0.0, 1.0, 0.2, step=0.05)
water_offset = st.sidebar.slider("Offset (RAW Water)",   0, 50, 0, step=1)

st.sidebar.divider()

if True:  # Phase 06 — Sketch roads
    st.title("Phase 06 — Block + Road Sketch")
    st.markdown("Reference: [Phase 06 Plan](file:///x:/CST%EB%B3%B8%EB%B6%80%20%28%EA%B5%AC%20%EA%B8%B0%EC%88%A0%EC%A7%80%EC%9B%90%EB%B6%80%20%ED%8F%B4%EB%8D%94%29/15.%20%EB%8B%A4%EB%A6%AC%EC%95%84/D-Brain/00_Input/Phase_06_Plan.md)")
    st.caption("Steps 1.1–1.5: blocks · ring + perimeter fire roads · stubs · 2-path verification + pruning")

    st.sidebar.header("Phase 06 Settings")
    show_grid     = st.sidebar.checkbox("§2 — 2m Grid", value=False)
    show_buffer       = st.sidebar.checkbox(f"§3.5.B — Block buffers ({ROAD_BUFFER}m / 16m)", value=True)
    show_rack_no_rack = st.sidebar.checkbox("§3.6.A — Rack baseline (no-rack: 8m / 16m)", value=False)
    show_rack_w_rack  = st.sidebar.checkbox("§3.6.A — Rack w-rack (6m / 14m / 22m / 28m)", value=True)
    show_b1_perimeter = st.sidebar.checkbox("§3.7.B — Perimeter segs (raw)", value=False)
    show_a1_ring      = st.sidebar.checkbox("§3.4 — Ring Road + Spurs", value=True)
    show_a2_raw       = st.sidebar.checkbox("§3.7.C — Group A access (raw)", value=False)
    show_a2_access    = st.sidebar.checkbox("§3.7.D — Cleaned segments", value=True)
    show_loop_line    = st.sidebar.checkbox("§3.7.E — Perimeter loop line", value=True)
    show_pts_N        = st.sidebar.checkbox("§3.7.E — N points (red)", value=False)
    show_pts_E        = st.sidebar.checkbox("§3.7.E — E points (green)", value=False)
    show_pts_S        = st.sidebar.checkbox("§3.7.E — S points (blue)", value=False)
    show_pts_W        = st.sidebar.checkbox("§3.7.E — W points (orange)", value=False)
    show_rack_b1      = st.sidebar.checkbox("§3.6.B — Rack spines + triangle", value=True)
    show_legend   = st.sidebar.checkbox("Legend", value=True)
    fix_seed      = st.sidebar.checkbox("Fix seed", value=True)
    seed_val      = st.sidebar.number_input("Seed", 0, 10000, 42, disabled=not fix_seed)

    if st.button("Generate Sketch", type="primary", use_container_width=True):
        if fix_seed:
            random.seed(int(seed_val))
        with st.spinner("Generating Phase 06 sketch..."):
            sketch = generate_sketch(  # → §3.1 Master Placement Sequence
                site_width, site_length, wind_dir,
                gate_side=gate_side, gate_ratio=gate_ratio,
                gh_edge=gh_edge,    gh_ratio=gh_ratio,    gh_offset=gh_offset,
                bb_edge=bb_edge,
                gis_edge=gis_edge,  gis_ratio=gis_ratio,  gis_offset=gis_offset,
                water_edge=water_edge, water_ratio=water_ratio, water_offset=water_offset,
            )
        if sketch is None:
            st.error("Could not place all blocks — try changing site size or parameters.")
            st.session_state["sketch06"] = None
        else:
            st.session_state["sketch06"] = sketch
            st.session_state["params06"] = (site_width, site_length)

    sketch = st.session_state.get("sketch06")
    if sketch is None:
        dbg = Core.Layout06._last_debug
        if dbg:
            st.error("Could not place all blocks — try changing site size or parameters.")
            st.markdown("#### Placement debug")
            attempts = dbg.get("total_attempts", 0)
            failed_at = dbg.get("failed_at", "?")
            section   = dbg.get("failed_section", "?")
            st.write(f"**Attempts:** {attempts} / {dbg.get('max_pool', '?')}  |  **Failed at:** `{failed_at}` ({section})")

            fail_counts = dbg.get("fail_counts", {})
            if fail_counts:
                st.markdown("**Block failure counts across all attempts:**")
                fc_rows = sorted([{"Block": k, "Fail count": v, "Fail %": f"{100*v//attempts}%"}
                                   for k, v in fail_counts.items()], key=lambda r: -r["Fail count"])
                st.dataframe(fc_rows, use_container_width=True, hide_index=True)

            last_placed = dbg.get("last_placed", {})
            ALL_BLOCKS = list(Core.Layout06.BLOCK_FOOTPRINTS.keys())
            st.markdown("**Last attempt — block placement status:**")
            status_rows = []
            for bname in ALL_BLOCKS:
                if bname in last_placed:
                    x, y, w, h = last_placed[bname]
                    status_rows.append({"Block": bname, "Status": "✓ placed",
                                        "x": round(x,1), "y": round(y,1), "w": round(w,1), "h": round(h,1)})
                elif bname == failed_at:
                    status_rows.append({"Block": bname, "Status": "✗ FAILED", "x": "-", "y": "-", "w": "-", "h": "-"})
                else:
                    status_rows.append({"Block": bname, "Status": "– not reached", "x": "-", "y": "-", "w": "-", "h": "-"})
            st.dataframe(status_rows, use_container_width=True, hide_index=True)
        else:
            st.info("Set parameters in the sidebar, then click **Generate Sketch**.")
        st.stop()

    sw, sl = st.session_state.get("params06", (site_width, site_length))
    blocks        = sketch["blocks"]
    ring_road     = sketch["ring_road"]
    perimeter     = sketch.get("perimeter_segments", [])
    gate_pt       = sketch["gate_point"]
    pb_center     = sketch["pb_center"]

    fig, ax = plt.subplots(figsize=(13, 8), dpi=110)

    # Site fill + boundary
    ax.fill([0,sw,sw,0,0], [0,0,sl,sl,0], color='#f0f8ff', zorder=0)
    ax.plot([0,sw,sw,0,0], [0,0,sl,sl,0], color='black', lw=1.2, zorder=1)

    # 2m grid
    if show_grid:
        cs = CELL_SIZE
        for i in range(int(sw // cs) + 1):
            ax.axvline(i * cs, color='#dddddd', lw=0.2, zorder=0.1)
        for j in range(int(sl // cs) + 1):
            ax.axhline(j * cs, color='#dddddd', lw=0.2, zorder=0.1)

    if show_b1_perimeter:  # → §3.7.B (raw perimeter segments before cleanup)
        perimeter_raw = sketch.get("perimeter_segments_raw", [])
        for k, ((x1, y1), (x2, y2)) in enumerate(perimeter_raw):
            ax.plot([x1, x2], [y1, y2], color='#ffff00', lw=2.5, alpha=1.0, zorder=3.0,
                    solid_capstyle='round', label='§3.7.B Perimeter (raw)' if k == 0 else "")
    if show_a1_ring:  # → §3.4.A (ring road) · §3.4.B (gate spur) · §3.4.D (ring spur)
        rx, ry = zip(*ring_road)
        ax.plot(rx, ry, color='#e91e8c', lw=2.5, alpha=0.95, zorder=2.5,
                solid_capstyle='round', label='§3.4.A Ring Road')
        # Gate spur (perimeter → gate point) — short primary segment  [→ §3.4.B]
        gs = sketch.get("gate_spur") or []
        if len(gs) >= 2:
            gsx, gsy = zip(*gs)
            ax.plot(gsx, gsy, color='#e91e8c', lw=2.5, alpha=0.95, zorder=2.5,
                    solid_capstyle='round')

    # Ring spur (ring → perimeter) — primary connector around blocks  [→ §3.4.D]
    if show_a1_ring:
        rs = sketch.get("ring_spur") or []
        if len(rs) >= 2:
            rsx, rsy = zip(*rs)
            ax.plot(rsx, rsy, color='#e91e8c', lw=2.5, alpha=0.95, zorder=2.5,
                    solid_capstyle='round')

    # A-2 Group A Access lines  [→ §3.7.C · §3.8.B]
    if show_a2_raw:
        group_a_raw = sketch.get("group_a_segments_raw", [])
        for k, ((x1, y1), (x2, y2)) in enumerate(group_a_raw):
            ax.plot([x1, x2], [y1, y2], color='#e67e22', lw=2.5, linestyle=':', alpha=0.8, zorder=2.8,
                    solid_capstyle='round', label='§3.7.C Group A (raw)' if k == 0 else "")

    if show_a2_access:  # → §3.7.D (cleaned + merged result)
        all_cleaned = sketch.get("all_segments_cleaned", [])
        for k, ((x1, y1), (x2, y2)) in enumerate(all_cleaned):
            ax.plot([x1, x2], [y1, y2], color='#00ff00', lw=2.5, alpha=1.0, zorder=3.5,
                    solid_capstyle='round', label='§3.7.D Cleaned' if k == 0 else "")

    # → §3.7.E perimeter loop line (single continuous loop, one color)
    if show_loop_line:
        _first = True
        for item in sketch.get("outer_loop", []):
            (x1, y1), (x2, y2) = item[0], item[1]
            ax.plot([x1, x2], [y1, y2], color='#8e44ad', lw=2.5, alpha=0.95,
                    zorder=3.7, linestyle='-', solid_capstyle='round',
                    label='§3.7.E perimeter loop' if _first else "")
            _first = False

    # → §3.7.E collected wall points — one toggle + color per wall
    _pts = sketch.get("outer_loop_pts", {})
    for wall, wcol, wshow in (("N", '#e74c3c', show_pts_N), ("E", '#27ae60', show_pts_E),
                              ("S", '#2980b9', show_pts_S), ("W", '#f39c12', show_pts_W)):
        if not wshow:
            continue
        first = True
        for (px, py) in _pts.get(wall, []):
            ax.plot(px, py, 'o', color=wcol, markersize=6,
                    markeredgecolor='white', markeredgewidth=0.7, zorder=3.8,
                    label=f'§3.7.E {wall}-pts' if first else "")
            first = False

    # Default buffer halos per block — magnetic snap boundaries  [→ §3.5.B gap rules]
    #  - Rack blocks: 14m road buffer (so two rack blocks touching sit 28m apart)
    #  - No-rack blocks: 8m road buffer (so two no-rack touching sit 16m apart)
    if show_buffer:
        legended_buffers = set()
        for b in blocks:
            is_rack = b["name"] in Core.Layout06.RACK_BLOCKS
            snap_buf = 14 if is_rack else 8
            color = '#2980b9' if is_rack else '#34495e'
            lbl = f'§3.5.B {snap_buf}m road snap buffer'
            
            xs = [b["x"] - snap_buf, b["x"] + b["width"] + snap_buf,
                  b["x"] + b["width"] + snap_buf, b["x"] - snap_buf, b["x"] - snap_buf]
            ys = [b["y"] - snap_buf, b["y"] - snap_buf,
                  b["y"] + b["height"] + snap_buf, b["y"] + b["height"] + snap_buf, b["y"] - snap_buf]
            
            ax.plot(xs, ys, color=color, linestyle='--', linewidth=1.0,
                    alpha=0.8, zorder=1.8,
                    label=lbl if lbl not in legended_buffers else "")
            legended_buffers.add(lbl)

    # Rack-block per-side buffer rectangles (Step A) for the 5 "need rack" blocks.  [→ §3.6.A]
    # 6 offsets total, split into two toggle groups:
    #   - "no rack" baseline (overlaps the default 8m+16m halos)
    #   - "with rack" (Case 1 / road 14m / Case 2 / b2b 28m)
    rack_buf = sketch.get("rack_buffers", {})
    if rack_buf:
        # (key, label, color, linestyle, linewidth, toggle_flag)
        rack_specs = [
            ("road_no_rack", '§3.6.A 8m road (no-rack)',   '#34495e', '--', 0.8, show_rack_no_rack),
            ("b2b_no_rack",  '§3.6.A 16m b2b (no-rack)',   '#c0392b', ':',  0.8, show_rack_no_rack),
            ("case1_rack",   '§3.6.A Case 1 CL (6m)',      '#00b894', '-',  1.6, show_rack_w_rack),
            ("road_w_rack",  '§3.6.A 14m road (w-rack)',   '#2980b9', '-',  1.2, show_rack_w_rack),
            ("case2_rack",   '§3.6.A Case 2 CL (22m)',     '#8e44ad', ':',  1.4, show_rack_w_rack),
            ("b2b_w_rack",   '§3.6.A 28m b2b (w-rack)',    '#e67e22', ':',  1.0, show_rack_w_rack),
        ]
        legended = {spec[0]: False for spec in rack_specs}
        for bname, offsets in rack_buf.items():
            for key, lbl, color, ls, lw, toggle in rack_specs:
                if not toggle or key not in offsets:
                    continue
                rx, ry, rw, rh = offsets[key]
                xs = [rx, rx + rw, rx + rw, rx, rx]
                ys = [ry, ry, ry + rh, ry + rh, ry]
                ax.plot(xs, ys, color=color, linestyle=ls, linewidth=lw,
                        alpha=0.9, zorder=2.5,
                        label=lbl if not legended[key] else "")
                legended[key] = True

    # Rack spines B-1..B-5  [→ §3.6.B]
    if show_rack_b1:
        rack_segments = sketch.get("rack_segments", [])
        for i, seg in enumerate(rack_segments):
            if seg and len(seg) == 2:
                xs, ys = zip(*seg)
                ax.plot(xs, ys, color='#d35400', linewidth=2, linestyle='-', zorder=3.5, 
                        label='§3.6.B Rack Spines' if i==0 else "")
                
        # Candidate points (B-2, B-3)  [→ §3.6.B]
        rack_candidates = sketch.get("rack_candidates", [])
        for i, pt in enumerate(rack_candidates):
            ax.plot(pt[0], pt[1], 'o', color='#bdc3c7', markersize=4, zorder=3.6, 
                    label='§3.6.B B-2/B-3 Candidates' if i==0 else "")

        # Water Triangle (B-4)  [→ §3.6.B]
        water_triangle = sketch.get("water_triangle", [])
        for i, pt in enumerate(water_triangle):
            ax.plot(pt[0], pt[1], '*', color='#f1c40f', markersize=12, markeredgecolor='black', zorder=3.7, 
                    label='§3.6.B B-4 Triangle' if i==0 else "")
        if len(water_triangle) == 3:
            # Draw lines connecting them
            wx, wy = zip(*(water_triangle + [water_triangle[0]]))
            ax.plot(wx, wy, color='#f1c40f', linestyle=':', linewidth=1, zorder=3.6)

    # Boom Barrier  [→ §3.1 step 5]
    boom_barrier = sketch.get("boom_barrier", [])
    if boom_barrier and len(boom_barrier) == 2:
        xs, ys = zip(*boom_barrier)
        ax.plot(xs, ys, color='#e74c3c', linewidth=4, linestyle='-', zorder=4.0, label='§3.1·5 Boom Barrier')

    # Gate Death Zone  [→ §3.4.C]
    gate_death_zone = sketch.get("gate_death_zone")
    if gate_death_zone:
        gx, gy, gw, gh = gate_death_zone
        import matplotlib.patches as patches
        rect = patches.Rectangle((gx, gy), gw, gh, linewidth=1.5, edgecolor='#c0392b',
                                 facecolor='#e74c3c', alpha=0.2, hatch='///', zorder=1.1, label='§3.4.C Gate Death Zone')
        ax.add_patch(rect)


    # Blocks (circles for Tanks + Flare per Groups.SHAPES, rectangles otherwise)
    for b in blocks:
        x, y, w, h = b["x"], b["y"], b["width"], b["height"]
        if SHAPES.get(b["name"]) == "circle":
            r = min(w, h) / 2
            cx, cy = x + w / 2, y + h / 2
            ax.add_patch(mpatches.Circle((cx, cy), r, facecolor=b["color"], alpha=0.55, zorder=2))
            ax.add_patch(mpatches.Circle((cx, cy), r, fill=False, edgecolor=b["color"], lw=1.0, zorder=2.1))
        else:
            ax.fill([x,x+w,x+w,x,x], [y,y,y+h,y+h,y], color=b["color"], alpha=0.55, zorder=2)
            ax.plot([x,x+w,x+w,x,x], [y,y,y+h,y+h,y], color=b["color"], lw=1.0, zorder=2.1)
        ax.text(x + w/2, y + h/2, b["name"], color='white', fontsize=5.5,
                fontweight='bold', ha='center', va='center', zorder=3,
                bbox=dict(facecolor='#333', alpha=0.75, edgecolor='none', pad=1))

    # Gate marker
    gx, gy = gate_pt
    ax.plot(gx, gy, '^', color='#27ae60', markersize=14, zorder=6,
            markeredgecolor='white', markeredgewidth=1.0)
    ax.text(gx, gy + 8, 'GATE', color='#27ae60', fontsize=9,
            fontweight='bold', ha='center', va='bottom', zorder=6)

    ax.set_xlim(-20, sw + 20)
    ax.set_ylim(-20, sl + 20)
    ax.set_aspect('equal', adjustable='box')
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_visible(False)
    if show_legend:
        ax.legend(loc='upper left', fontsize=8, framealpha=0.9)

    plt.tight_layout(pad=0.4)
    st.pyplot(fig, use_container_width=True)
    plt.close(fig)

    # Placement pass banner — shown below the layout
    _dbg = Core.Layout06._last_debug
    _tol_label = _dbg.get("boundary_pass_label", "")
    if _tol_label:
        if "pass 1" in _tol_label:
            st.success(f"✓ {_tol_label} — all blocks fit with 18m inner margin")
        elif "pass 2" in _tol_label:
            st.info(f"ℹ {_tol_label} — blocks fit inside plot boundary (no margin)")
        else:
            st.warning(f"⚠ {_tol_label} — tight site; some blocks may slightly exceed boundary")

    # §3.7.E debug expander
    with st.expander("§3.3 Debug — PB gate-side stop line"):
        gc = Core.Layout06._last_debug.get("pb_gate_check")
        if gc:
            st.json(gc)
            ne = gc.get("gh_near_edge (closest to center)")
            if ne == "buf_bottom":
                ok = gc["ring_top"] <= gc["buf_bottom"] + 0.01
                st.write(f"ring_top {gc['ring_top']} ≤ buf_bottom {gc['buf_bottom']} ? → {'✅' if ok else '❌ ABOVE'}")
            elif ne == "buf_top":
                ok = gc["ring_bottom"] >= gc["buf_top"] - 0.01
                st.write(f"ring_bottom {gc['ring_bottom']} ≥ buf_top {gc['buf_top']} ? → {'✅' if ok else '❌'}")
            elif ne == "buf_left":
                ok = gc["ring_right"] <= gc["buf_left"] + 0.01
                st.write(f"ring_right {gc['ring_right']} ≤ buf_left {gc['buf_left']} ? → {'✅' if ok else '❌'}")
            elif ne == "buf_right":
                ok = gc["ring_left"] >= gc["buf_right"] - 0.01
                st.write(f"ring_left {gc['ring_left']} ≥ buf_right {gc['buf_right']} ? → {'✅' if ok else '❌'}")
        else:
            st.warning("no pb_gate_check in debug")

    with st.expander("§3.7.E Debug — cleaned segments & buffers"):
        cleaned_dbg = sketch.get("all_segments_cleaned", [])
        loop_dbg = sketch.get("outer_loop", [])
        st.write(f"**Cleaned total:** {len(cleaned_dbg)}  |  **loop segs:** {len(loop_dbg)}")

        col_h, col_v = st.columns(2)
        with col_h:
            st.markdown("**H segments:**")
            h_rows = [{"#": i, "x0": round(min(a[0],b[0]),1), "x1": round(max(a[0],b[0]),1), "y": round(a[1],1), "len": round(abs(b[0]-a[0]),1)}
                      for i, (a, b) in enumerate(cleaned_dbg) if abs(a[1]-b[1]) < 0.1]
            st.dataframe(h_rows, use_container_width=True, hide_index=True)
        with col_v:
            st.markdown("**V segments:**")
            v_rows = [{"#": i, "x": round(a[0],1), "y0": round(min(a[1],b[1]),1), "y1": round(max(a[1],b[1]),1), "len": round(abs(b[1]-a[1]),1)}
                      for i, (a, b) in enumerate(cleaned_dbg) if abs(a[0]-b[0]) < 0.1]
            st.dataframe(v_rows, use_container_width=True, hide_index=True)

        _PERI = {"Power Block","Cooling Tower","WT/WWT","RAW Water Tank","GIS","Warehouse","Admin Building"}
        cb = sketch.get("computed_buffers_debug", {})
        st.markdown("**Perimeter block buffers (bx, by, bw, bh = left, bottom, width, height):**")
        peri_rows = [{"block": n, "bx(left)": round(b[0],1), "by(bot)": round(b[1],1),
                      "right": round(b[0]+b[2],1), "top": round(b[1]+b[3],1), "bw": round(b[2],1), "bh": round(b[3],1)}
                     for n, b in cb.items() if n in _PERI]
        st.dataframe(sorted(peri_rows, key=lambda r: r["bx(left)"]), use_container_width=True, hide_index=True)

        # Snap diagnostic: loop segments that run parallel within 0.1–30m of a
        # cleaned segment (should have snapped but didn't).
        st.markdown("**Snap check — loop segs with a parallel cleaned seg 0.1–30m away:**")
        loop_segs = sketch.get("outer_loop", [])
        clean_h = [(min(a[0],b[0]), max(a[0],b[0]), a[1]) for a,b in cleaned_dbg if abs(a[1]-b[1])<0.1]
        clean_v = [(a[0], min(a[1],b[1]), max(a[1],b[1])) for a,b in cleaned_dbg if abs(a[0]-b[0])<0.1]
        near = []
        for item in loop_segs:
            (ax, ay), (bx, by) = item[0], item[1]
            if abs(ay-by) < 0.1:   # horizontal loop seg
                lo, hi = min(ax,bx), max(ax,bx)
                for (cx0, cx1, cy) in clean_h:
                    d = abs(cy-ay)
                    if 0.1 < d <= 30 and min(hi,cx1) > max(lo,cx0):
                        near.append({"loop": f"H y={round(ay,1)} x[{round(lo,1)},{round(hi,1)}]", "clean_y": round(cy,1), "gap": round(d,1)}); break
            elif abs(ax-bx) < 0.1:  # vertical loop seg
                lo, hi = min(ay,by), max(ay,by)
                for (cx, cy0, cy1) in clean_v:
                    d = abs(cx-ax)
                    if 0.1 < d <= 30 and min(hi,cy1) > max(lo,cy0):
                        near.append({"loop": f"V x={round(ax,1)} y[{round(lo,1)},{round(hi,1)}]", "clean_x": round(cx,1), "gap": round(d,1)}); break
        if near:
            st.dataframe(near, use_container_width=True, hide_index=True)
        else:
            st.success("No loop seg is 0.1–30m parallel to a cleaned seg — snapping left nothing to collapse.")

    # Stats
    st.divider()
    st.markdown("#### Block stats")
    rows = [{"Block": b["name"], "X (m)": b["x"], "Y (m)": b["y"],
             "W (m)": b["width"], "H (m)": b["height"]} for b in blocks]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Blocks placed", len(blocks))
    c2.metric("Grid cell size", f"{CELL_SIZE}m")
    c3.metric("Fire segs (kept)",  len(sketch.get("fire_segments", [])))
    c4.metric("Secondary segs",    len(sketch.get("secondary_segs", [])))
    c5.metric("Pruned segs",       len(sketch.get("pruned_segments", [])))

    # Per-block kept path table (Step 1.5 — shorter of ring/perimeter, Power Block excluded)
    traces = sketch.get("path_traces", [])
    if traces:
        st.markdown("#### Kept paths (Step 1.5 — shorter of ring/perimeter)")
        trace_rows = []
        for t in traces:
            pts = t["world"]
            length = sum(((pts[i][0]-pts[i-1][0])**2 + (pts[i][1]-pts[i-1][1])**2)**0.5
                         for i in range(1, len(pts)))
            trace_rows.append({
                "Block":  t["block"],
                "via":    t["via"],
                "length (m)": round(length, 1),
                "cells":  len(pts),
            })
        st.dataframe(trace_rows, use_container_width=True, hide_index=True)
